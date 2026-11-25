"""Memeriksa jawaban pertanyaan tarif "sekarang/terbaru" lewat alur sungguhan (termasuk search_query).

    ... -e PYTHONPATH=/srv backend python /eval/tarif_check.py
"""
import asyncio

from app.main import search_query
from app.providers import get_provider
from app.rag import retrieve
from app.schemas import ChatRequest, Message

QUESTIONS = [
    "tarif cukai SKM golongan 1 sekarang berapa?",
    "tarif cukai SKT golongan 2 skrg berapa per batang",
    "tarif cukai SKM golongan 1 yg terbaru berapa ya? buat bahan briefing besok",
    "berapa tarif SPM golongan 2 yang berlaku saat ini?",
    "tarif cukai SKM golongan 1 tahun 2024 berapa?",
]


async def main():
    get_provider()
    for q in QUESTIONS:
        req = ChatRequest(messages=[Message(role="user", content=q)])
        srcs = await retrieve(search_query(req))
        parts = []
        async for piece in get_provider().stream_answer(req.messages, srcs, {}):
            parts.append(piece)
        print(f"\n######## {q}\n{''.join(parts)}")


asyncio.run(main())
