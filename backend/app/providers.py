"""Penyedia jawaban. Antarmuka sama untuk mode demo dan (nanti) OpenAI."""

import asyncio
import re
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from .config import settings
from .doc_status import PENDING, REVOKED, status_info
from .schemas import Message, Source


class ChatProvider(Protocol):
    def stream_answer(
        self, messages: list[Message], sources: list[Source], usage: dict | None = None
    ) -> AsyncIterator[str]:
        """Mengalirkan jawaban. Bila `usage` diberikan, diisi input_tokens dan output_tokens di akhir."""
        ...


class MockProvider:
    """Jawaban contoh yang dialirkan sedikit demi sedikit, mirip model sungguhan."""

    async def stream_answer(
        self, messages: list[Message], sources: list[Source], usage: dict | None = None
    ) -> AsyncIterator[str]:
        question = messages[-1].content.strip().replace("\n", " ")
        if len(question) > 200:
            question = question[:200] + "…"

        found = "\n".join(
            f"{s.id}. **{s.title}**" + (f", {s.location}" if s.location else "") + f" [{s.id}]"
            for s in sources
        )
        text = (
            "> **Mode pencarian.** Belum terhubung ke OpenAI, jadi belum ada jawaban yang disusun. "
            "Berikut bagian dokumen referensi yang paling relevan dengan pertanyaan Anda.\n\n"
            f"Pertanyaan Anda: *{question}*\n\n"
            f"{found}\n\n"
            "Kutipan lengkap ada di daftar sumber. Ini bukan nasihat hukum."
        )
        for piece in re.findall(r"\S+\s*", text):
            yield piece
            await asyncio.sleep(0.025)


# Petunjuk model ada di berkas teks tersendiri supaya mudah ditinjau dan diubah tanpa menyentuh kode.
SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.txt").read_text(encoding="utf-8")

NO_SOURCES_TEXT = (
    "Saya belum menemukan bagian dokumen yang cocok dengan pertanyaan itu di dokumen situs ini. "
    "Coba ulangi dengan kata kunci yang lebih spesifik, misalnya nomor peraturan, nama jenis rokok "
    "(SKM, SPM, SKT), atau istilah seperti hubungan keterkaitan."
)

GREETING_TEXT = (
    "Halo! Saya asisten telaah HubTer Insight. Saya menjawab dari peraturan dan bahan internal tentang hubungan "
    "keterkaitan (HubTer) pengusaha pabrik hasil tembakau, tarif dan golongan cukai hasil tembakau, NPPBKC, dan "
    "pemeriksaan kepatuhan pengusaha barang kena cukai. Silakan bertanya, misalnya: "
    "\"Apa saja aspek yang membuat pabrik dianggap punya hubungan keterkaitan?\""
)
_GREETING_PREFIX = "Halo! Saya asisten telaah"
GREETING_TOPIC = "Apa saja aspek yang membuat pabrik dianggap punya hubungan keterkaitan?"  # contoh yang disarankan sapaan
THANKS_TEXT = "Sama-sama. Silakan bertanya lagi kapan saja."

_GREETING = re.compile(
    r"^(halo+|hai+|hi+|hello|hey|permisi|selamat (pagi|siang|sore|malam)|assalamu\W?alaikum( wr\.? ?wb\.?)?|"
    r"salam|pagi|siang|sore|malam)( (kak|pak|bu|min|bot|admin|semua|tim))?$"
)
_THANKS = re.compile(r"^(terima ?kasih|makasih|trims|thanks|thank you|thx)( (banyak|ya|yaa|atas bantuannya))*( (kak|pak|bu|min))?$")


def smalltalk_reply(text: str) -> str | None:
    """Balasan tetap untuk sapaan atau ucapan terima kasih saja; None bila pesan berisi pertanyaan."""
    t = re.sub(r"[^\w\s.]", " ", text.lower()).strip()
    t = re.sub(r"\s+", " ", t).rstrip(". ")
    if len(t) > 40:
        return None
    if _GREETING.match(t):
        return GREETING_TEXT
    if _THANKS.match(t):
        return THANKS_TEXT
    return None

MAX_HISTORY_MESSAGES = 6  # pesan sebelumnya yang ikut dikirim sebagai konteks percakapan


_BULAN = ("Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember")
_WIB = timezone(timedelta(hours=7))


def today_wib() -> datetime:
    return datetime.now(_WIB)


def today_text() -> str:
    d = today_wib()
    return f"{d.day} {_BULAN[d.month - 1]} {d.year}"


def status_warning(sources: list[Source]) -> str:
    """Peringatan tepat sebelum pertanyaan bila ada kutipan dari peraturan yang sudah dicabut atau belum berlaku
    (model sering mengabaikan baris Status di tengah kutipan)."""
    if not settings.doc_status:
        return ""
    revoked, pending = [], []
    for s in sources:
        text, kind = status_info(s.title)
        if text and kind:
            (pending if kind == PENDING else revoked).append(
                f"- Kutipan [{s.id}] ({s.title.split(' tentang ')[0]}): {text}"
            )
    out = ""
    if revoked:
        out += (
            "PERINGATAN STATUS: kutipan berikut berasal dari peraturan yang sudah tidak berlaku. Jangan menyajikan isinya "
            "sebagai ketentuan yang berlaku sekarang, dan jangan memakai kata \"berlaku\", \"kini berlaku\", atau \"saat ini\" "
            "untuk isinya. Bila Anda memakai isi kutipan itu (karena ditanyakan atau sebagai riwayat), KALIMAT PERTAMA jawaban "
            "harus menyatakan bahwa peraturan itu sudah dicabut dan oleh apa. Bila ada kutipan dari peraturan pengganti yang "
            "memuat hal yang sama, utamakan itu.\n" + "\n".join(revoked) + "\n\n"
        )
    if pending:
        out += (
            "PERINGATAN STATUS: kutipan berikut berasal dari peraturan yang sudah ditetapkan tetapi BELUM BERLAKU. Jangan "
            "menyajikan isinya sebagai ketentuan yang berlaku sekarang; sebut tanggal mulai berlakunya dan peraturan yang "
            "masih berlaku saat ini (bila ada di kutipan lain). Boleh dijelaskan sebagai ketentuan yang akan datang.\n"
            + "\n".join(pending) + "\n\n"
        )
    return out


def build_messages(messages: list[Message], sources: list[Source]) -> list[dict[str, str]]:
    """Susun pesan untuk model: petunjuk, riwayat singkat, lalu pertanyaan terakhir beserta kutipannya."""
    blocks = "\n".join(f'<kutipan id="{s.id}">\n{s.context or s.snippet}\n</kutipan>' for s in sources)
    history = messages[:-1][-MAX_HISTORY_MESSAGES:]
    out: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    out += [{"role": m.role, "content": m.content} for m in history]
    out.append(
        {"role": "user", "content": f"<kutipan>\n{blocks}\n</kutipan>\n\nTanggal hari ini: {today_text()}.\n{status_warning(sources)}Pertanyaan: {messages[-1].content}"}
    )
    return out


class OpenAIProvider:
    """Menyusun jawaban dengan OpenAI dari bagian dokumen yang ditemukan oleh rag.retrieve."""

    def __init__(self) -> None:
        from openai import AsyncOpenAI

        if settings.openai_api_key is None:
            raise RuntimeError("OPENAI_API_KEY belum diisi.")
        self._client = AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=settings.openai_timeout_seconds,
            max_retries=2,
        )

    @property
    def client(self):
        return self._client

    async def stream_answer(
        self, messages: list[Message], sources: list[Source], usage: dict | None = None
    ) -> AsyncIterator[str]:
        reply = smalltalk_reply(messages[-1].content)
        if reply:
            yield reply
            return
        if not sources:
            yield NO_SOURCES_TEXT
            return

        stream = await self._client.chat.completions.create(
            model=settings.openai_model,
            messages=build_messages(messages, sources),
            stream=True,
            stream_options={"include_usage": True},
            reasoning_effort=settings.openai_reasoning_effort,
            max_completion_tokens=settings.openai_max_output_tokens,
        )
        async for chunk in stream:
            if usage is not None and getattr(chunk, "usage", None):
                usage["input_tokens"] = chunk.usage.prompt_tokens
                usage["output_tokens"] = chunk.usage.completion_tokens
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            if choice.delta.content:
                yield choice.delta.content
            if choice.finish_reason == "length":
                yield "\n\n*Jawaban terpotong karena terlalu panjang. Coba pertanyaan yang lebih spesifik.*"
            elif choice.finish_reason == "content_filter":
                yield "\n\n*Jawaban dihentikan oleh filter konten.*"


_provider: ChatProvider | None = None


def get_provider() -> ChatProvider:
    global _provider
    if _provider is None:
        _provider = MockProvider() if settings.llm_mode == "mock" else OpenAIProvider()
    return _provider
