import asyncio
import json
import logging
import re
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from . import auth, files, store
from .agent import run_agent
from .config import settings
from .providers import GREETING_TOPIC, OpenAIProvider, _GREETING_PREFIX, get_provider, today_wib
from .ratelimit import RateLimiter
from .rag import retrieve, tokenize
from .schemas import ChatRequest, FeedbackRequest, LoginRequest, Source

log = logging.getLogger("hubter")

# Dokumentasi otomatis dimatikan karena situs ini publik.
app = FastAPI(title="HubTer Insight API", docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(files.router)

limiter = RateLimiter(settings.rate_limit_per_minute, settings.rate_limit_per_day, settings.daily_request_cap)
login_limiter = RateLimiter(settings.login_rate_per_minute, settings.login_rate_per_day, 0)  # tebakan kata sandi per IP
feedback_limiter = RateLimiter(per_minute=30, per_day=500, daily_cap=0)  # melindungi basis data dari banjir kiriman

FOLLOWUP_MAX_TERMS = 3  # pertanyaan dengan sedikit kata kunci dianggap lanjutan ("bagaimana pasal 5?")
FOLLOWUP_MAX_WORDS = 18  # isyarat lanjutan hanya dihitung pada pesan pendek; pesan panjang berdiri sendiri
_FOLLOWUP_CUE = re.compile(
    r"\b(itu|tadi|tersebut|barusan|sederhana|simpel|ringkas|singkat|poin|poin2|dipoin2?|tabel|contoh|contohnya|"
    r"maksudnya|artinya|terus|lanjut|lagi|kutip|persisnya|bunyi|berarti|kalau gitu|kalo gitu|yang tadi|"
    r"dasarnya|tiap tahap|kalau iya|kalo iya|diubah sama|bedanya sama|yg tadi|yg diubah|yang diubah)\b",
    re.I,
)
_TARIF_TERM = re.compile(r"\b(tarif|hje|harga jual eceran|per batang|cukai skm|cukai skt|cukai spm)\b", re.I)
_RECENT_TERM = re.compile(
    r"\b(sekarang|skrg|saat ini|terbaru|terkini|paling baru|tahun ini|yang baru|mutakhir|berlaku|tabel)\b", re.I
)
_HAS_YEAR = re.compile(r"\b(19|20)\d{2}\b")


def _is_followup(text: str) -> bool:
    """Pesan lanjutan: sedikit kata kunci, atau pesan pendek dengan isyarat ("itu", "lebih sederhana", "contoh")."""
    return len(tokenize(text)) <= FOLLOWUP_MAX_TERMS or (
        len(text.split()) <= FOLLOWUP_MAX_WORDS and _FOLLOWUP_CUE.search(text) is not None
    )


ANSWER_SNIPPET_CHARS = 250


def _answer_topic(req: ChatRequest) -> str:
    """Potongan awal jawaban sistem terakhir sebagai pengingat topik untuk pencarian lanjutan: "tolong jadi tabel"
    harus mencari sumber yang sama dengan jawaban yang mau ditabelkan. Teks sapaan tidak berisi topik; contoh
    pertanyaannya yang dipakai."""
    prev = next((m.content for m in reversed(req.messages[:-1]) if m.role == "assistant"), "")
    if prev.startswith(_GREETING_PREFIX):
        return GREETING_TOPIC
    text = re.sub(r"\[\d+\]|[*#|>_`]|-{3,}|:?-{2,}:?", " ", prev)  # rujukan, markdown, garis tabel
    text = text.split("Bukan nasihat hukum")[0]
    return re.sub(r"\s+", " ", text).strip()[:ANSWER_SNIPPET_CHARS]


def search_query(req: ChatRequest) -> str:
    """Teks untuk pencarian dokumen. Pertanyaan lanjutan digabung dengan pertanyaan substantif terdekat sebelumnya
    supaya konteksnya tidak hilang. Pertanyaan yang sudah lengkap berdiri sendiri, agar topik lama tidak
    mencemari pencarian topik baru. Pertanyaan tarif "sekarang/terbaru" ditambah tahun berjalan supaya baris
    tabel periode terkini ikut terambil, bukan baris tahun lama."""
    user_msgs = [m.content for m in req.messages if m.role == "user"]
    last = user_msgs[-1]
    query = last
    if len(user_msgs) > 1 and _is_followup(last):
        earlier = user_msgs[:-1]
        base = next((m for m in reversed(earlier) if not _is_followup(m)), None)
        if base is None:
            # Semua pesan sebelumnya miskin kata kunci: pakai yang paling banyak kata kuncinya (yang terbaru bila seri),
            # bukan sekadar pesan terakhir yang bisa saja "ya tolong jelaskan".
            base = max(reversed(earlier), key=lambda m: len(tokenize(m)))
        query = f"{base}\n{last}"
        # Potongan jawaban sebelumnya hanya untuk pesan yang nyaris tanpa topik sendiri ("jadi tabel", "lebih sederhana").
        # Pesan yang membawa topik baru ("terus PMK 78 masih dipakai gak?") tidak boleh dibanjiri topik jawaban lama.
        if len(tokenize(last)) <= FOLLOWUP_MAX_TERMS:
            topic = _answer_topic(req)
            if topic:
                query += f"\n{topic}"
    if _TARIF_TERM.search(query) and _RECENT_TERM.search(last) and not _HAS_YEAR.search(last):
        year = today_wib().year
        query += f"\n{year} {year - 1}"
    return query


async def _plain(pieces: AsyncIterator[str]) -> AsyncIterator[tuple[str, Any]]:
    async for piece in pieces:
        yield "token", piece


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/session")
async def session(request: Request) -> dict[str, bool]:
    """Dipanggil halaman saat dibuka: perlu menampilkan layar login atau tidak."""
    return {"auth_required": auth.enabled(), "authenticated": auth.is_authenticated(request)}


@app.post("/api/login")
async def login(req: LoginRequest, request: Request, response: Response) -> dict[str, bool]:
    if not auth.enabled():
        return {"ok": True}
    reason = login_limiter.check(request.client.host if request.client else "unknown")
    if reason:
        raise HTTPException(429, "Terlalu banyak percobaan masuk. Tunggu sebentar lalu coba lagi.")
    if not auth.check_credentials(req.username, req.password):
        await asyncio.sleep(0.8)  # memperlambat tebakan beruntun
        raise HTTPException(401, "Nama pengguna atau kata sandi salah.")
    response.set_cookie(
        auth.COOKIE,
        auth.make_token(),
        max_age=settings.auth_session_days * 86400,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )
    return {"ok": True}


@app.post("/api/logout")
async def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(auth.COOKIE, path="/")
    return {"ok": True}


@app.get("/api/config", dependencies=[Depends(auth.require_auth)])
async def config() -> dict[str, str]:
    return {"mode": settings.llm_mode, "version": settings.app_version}


@app.post("/api/chat", dependencies=[Depends(auth.require_auth)])
async def chat(req: ChatRequest, request: Request) -> StreamingResponse:
    if req.messages[-1].role != "user":
        raise HTTPException(422, "Pesan terakhir harus dari pengguna.")
    if len(req.messages) > settings.max_messages:
        raise HTTPException(422, "Percakapan terlalu panjang. Mulai percakapan baru.")
    if any(len(m.content) > settings.max_message_chars for m in req.messages):
        raise HTTPException(422, f"Pesan terlalu panjang (maksimal {settings.max_message_chars} karakter).")

    if settings.llm_mode != "mock":  # hanya mode berbayar yang dibatasi
        reason = limiter.check(request.client.host if request.client else "unknown")
        if reason:
            raise HTTPException(429, reason)

    query = search_query(req)
    chat_id = uuid.uuid4().hex

    async def stream():
        started = time.monotonic()
        answer: list[str] = []
        sources: list[Source] = []
        usage: dict = {}
        searches: list[str] = []  # kata kunci tambahan yang dicari model (mode agentic)
        status = "dibatalkan"  # tetap ini bila klien menutup koneksi sebelum jawaban selesai
        try:
            yield sse("meta", {"id": chat_id})
            sources = await retrieve(query)
            yield sse("sources", [s.model_dump() for s in sources])
            provider = get_provider()
            if settings.agentic and isinstance(provider, OpenAIProvider) and sources:
                events = run_agent(provider.client, req.messages, sources, usage, searches)
            else:
                events = _plain(provider.stream_answer(req.messages, sources, usage))
            async for kind, value in events:
                if kind == "token":
                    answer.append(value)
                    yield sse("token", {"t": value})
                elif kind == "sources":
                    sources = value
                    yield sse("sources", [s.model_dump() for s in sources])
                elif kind == "status":
                    yield sse("status", {"text": value})
            status = "ok"
            yield sse("done", {})
        except asyncio.CancelledError:
            raise
        except Exception:
            # Isi pertanyaan tidak masuk log server (stdout); penyimpanan evaluasi ada di store.py.
            status = "error"
            log.exception("Permintaan chat gagal")
            yield sse("error", {"message": "Terjadi kesalahan di server. Silakan coba lagi."})
        finally:
            store.save_chat(
                chat_id=chat_id,
                session=req.session_id,
                question=req.messages[-1].content,
                history_len=len(req.messages) - 1,
                search_query=query + (f"\n[agentic] {' | '.join(searches)}" if searches else ""),
                sources=[{"title": s.title, "location": s.location} for s in sources],
                answer="".join(answer),
                status=status,
                latency_ms=int((time.monotonic() - started) * 1000),
                usage=usage,
            )

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/feedback", dependencies=[Depends(auth.require_auth)])
async def feedback(req: FeedbackRequest, request: Request) -> dict[str, bool]:
    reason = feedback_limiter.check(request.client.host if request.client else "unknown")
    if reason:
        raise HTTPException(429, reason)
    comment = req.comment.strip() if req.comment and req.comment.strip() else None
    if req.rating is None and comment is None:
        raise HTTPException(422, "Isi penilaian atau komentar.")
    if not store.save_feedback(req.chat_id, req.rating, comment):
        raise HTTPException(404, "Jawaban tidak ditemukan.")
    return {"ok": True}
