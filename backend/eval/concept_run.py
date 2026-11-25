"""Menjalankan pertanyaan konseptual (arti istilah, perbedaan istilah, alasan aturan) dan mencetak jawabannya,
untuk memeriksa apakah penjelasan umum tanpa label tetap muncul.

    ... -e PYTHONPATH=/srv backend python /eval/concept_run.py
"""
import asyncio

from app.providers import get_provider
from app.rag import retrieve

QUESTIONS = [
    "apa bedanya hubungan istimewa dan hubungan keterkaitan?",
    "apa itu hubungan istimewa?",
    "kenapa pabrik yang saling terkait dihitung gabungan produksinya?",
    "apa maksud indikasi dan penetapan dalam hubter?",
    "jelaskan konsep hubungan keterkaitan secara sederhana",
]


class Msg:
    def __init__(self, content):
        self.role, self.content = "user", content


async def main():
    get_provider()
    for q in QUESTIONS:
        srcs = await retrieve(q)
        parts = []
        async for piece in get_provider().stream_answer([Msg(q)], srcs, {}):
            parts.append(piece)
        print(f"\n######## {q}\n{''.join(parts)}")


asyncio.run(main())
