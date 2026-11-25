"""Menjalankan pertanyaan yang rawan peraturan lama vs pengganti lewat alur sungguhan (pencarian + model) dan
menyimpan jawaban serta kutipan yang dipakai. Label lengan dari env ARM; hasil ke /eval/status_<ARM>.json.

    docker compose run --rm -T --no-deps -v $HOME/hubter-eval:/eval -e PYTHONPATH=/srv -e ARM=v1 \
        backend python /eval/status_run.py
"""
import asyncio
import json
import os
import re
import time

from app.providers import get_provider
from app.rag import retrieve

ARM = os.environ["ARM"]
PRICE_IN, PRICE_OUT = 0.75, 4.50

QUESTIONS = [
    # NPPBKC: PMK 200/2008 (+191/2010) dicabut PMK 66/2018, diubah PMK 68/2023
    "Apa syarat permohonan NPPBKC untuk pengusaha pabrik hasil tembakau?",
    "Dalam keadaan apa NPPBKC dapat dibekukan?",
    "Siapa yang berwenang mencabut NPPBKC dan kapan bisa dicabut?",
    "Apa dasar hukum NPPBKC saat ini?",
    "Apakah PMK 200/PMK.04/2008 masih berlaku?",
    "Apa saja kewajiban pemegang NPPBKC menurut PMK 200 tahun 2008?",
    "berapa lama pembekuan nppbkc kalau pabrik gak jalanin kegiatan?",
    # Hubter lama: PER-39/2012 dicabut PER-21/2013, dicabut PER-27/2013
    "Apa yang dimaksud hubungan istimewa pengusaha pabrik hasil tembakau?",
    "Apakah PER-39/BC/2012 masih berlaku?",
    "Bagaimana pemeriksaan pengusaha pabrik yang tidak menyampaikan pernyataan hubungan keterkaitan?",
    "Sampai kapan pengusaha pabrik harus menyampaikan pernyataan memiliki atau tidak memiliki hubungan keterkaitan?",
    "gimana kalo pabrik gak nyerahin pernyataan hubter, diperiksa pake aturan apa?",
    # Pemeriksaan kepatuhan: PER-10/2023 dicabut PER-12/2026
    "Bagaimana tata laksana pemeriksaan kepatuhan pengusaha barang kena cukai?",
    "Apakah PER-10/BC/2023 masih berlaku?",
    "siapa yang periksa kepatuhan pengusaha bkc dan seberapa sering?",
    # Tarif: PMK 192/2021 diubah 109/2022, 191/2022, 97/2024; tata cara PER-16/2022 diubah
    "Peraturan apa yang mengatur tarif cukai hasil tembakau saat ini?",
    "Bagaimana tata cara penetapan tarif cukai untuk merek baru hasil tembakau?",
    "Berapa tarif cukai SKM golongan I yang berlaku sekarang?",
    # Hubter berlaku
    "Apa perubahan PMK 131 terhadap PMK 78 dan mana yang berlaku sekarang?",
    "Apa aturan yang berlaku sekarang untuk penetapan hubungan keterkaitan?",
]


class Msg:
    def __init__(self, content):
        self.role, self.content = "user", content


async def one(q):
    t0 = time.monotonic()
    usage, parts = {}, []
    srcs = await retrieve(q)
    async for piece in get_provider().stream_answer([Msg(q)], srcs, usage):
        parts.append(piece)
    text = "".join(parts)
    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", text)})
    return {
        "q": q, "answer": text, "cited": cited,
        "sources": [{"id": s.id, "title": s.title, "location": s.location or ""} for s in srcs],
        "sec": round(time.monotonic() - t0, 1),
        "cost": (usage.get("input_tokens", 0) * PRICE_IN + usage.get("output_tokens", 0) * PRICE_OUT) / 1e6,
    }


async def main():
    get_provider()
    sem = asyncio.Semaphore(4)

    async def guarded(q):
        async with sem:
            return await one(q)

    rows = await asyncio.gather(*(guarded(q) for q in QUESTIONS))
    with open(f"/eval/status_{ARM}.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print(f"{ARM}: {len(rows)} jawaban, biaya rata-rata ${sum(r['cost'] for r in rows)/len(rows):.4f}")


asyncio.run(main())
