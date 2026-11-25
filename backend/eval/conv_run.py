"""Menjalankan percakapan simulasi (beberapa giliran) lewat alur sungguhan: search_query (penggabungan pertanyaan
lanjutan), retrieve, dan model. Riwayat jawaban sebelumnya ikut dikirim seperti di situs.

Masukan /eval/personas.json: {"personas":[{"persona":..., "conversations":[{"turns":[{"q":..., "intent":...}]}]}]}
Keluaran /eval/personas_out.json. Jalankan:
    ... -e PYTHONPATH=/srv backend python /eval/conv_run.py
"""
import asyncio
import json
import os
import re
import time

from app.main import search_query
from app.providers import get_provider
from app.rag import retrieve
from app.schemas import ChatRequest, Message

PRICE_IN, PRICE_OUT = 0.75, 4.50


async def run_conversation(persona: str, turns: list[dict]) -> list[dict]:
    history: list[Message] = []
    out = []
    for t in turns:
        q = t["q"].strip()
        history.append(Message(role="user", content=q))
        req = ChatRequest(messages=history[-12:])
        sq = search_query(req)
        t0 = time.monotonic()
        usage, parts = {}, []
        try:
            srcs = await retrieve(sq)
            async for piece in get_provider().stream_answer(req.messages, srcs, usage):
                parts.append(piece)
            answer = "".join(parts)
            error = None
        except Exception as e:  # satu giliran gagal tidak menghentikan simulasi
            srcs, answer, error = [], "", f"{type(e).__name__}: {e}"
        cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", answer)})
        out.append(
            {
                "persona": persona, "q": q, "intent": t.get("intent", ""), "search_query": sq, "answer": answer, "error": error,
                "cited": [f"[{s.id}] {s.title[:60]} · {s.location or '-'}" for s in srcs if s.id in cited],
                "n_sources": len(srcs), "sec": round(time.monotonic() - t0, 1),
                "cost": (usage.get("input_tokens", 0) * PRICE_IN + usage.get("output_tokens", 0) * PRICE_OUT) / 1e6,
            }
        )
        history.append(Message(role="assistant", content=answer or "(gagal)"))
    return out


async def main() -> None:
    get_provider()
    data = json.load(open(os.environ.get("PERSONAS", "/eval/personas.json"), encoding="utf-8"))
    jobs = [(p["persona"], c["turns"]) for p in data["personas"] for c in p["conversations"]]
    sem = asyncio.Semaphore(4)

    async def guarded(job):
        async with sem:
            return await run_conversation(*job)

    results = await asyncio.gather(*(guarded(j) for j in jobs))
    flat = [r for conv in results for r in conv]
    with open(os.environ.get("OUT", "/eval/personas_out.json"), "w", encoding="utf-8") as f:
        json.dump(flat, f, ensure_ascii=False, indent=1)
    print(f"{len(jobs)} percakapan, {len(flat)} giliran, galat {sum(1 for r in flat if r['error'])}, "
          f"biaya total ${sum(r['cost'] for r in flat):.3f}, rata-rata ${sum(r['cost'] for r in flat)/max(len(flat),1):.4f}")


asyncio.run(main())
