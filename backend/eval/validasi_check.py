"""Memeriksa jawaban untuk fakta yang divalidasi ahli (docs/validasi-status-regulasi-2026-11-25.md).

    ... -e PYTHONPATH=/srv backend python /eval/validasi_check.py
"""
import asyncio

from app.main import search_query
from app.providers import get_provider
from app.rag import retrieve
from app.schemas import ChatRequest, Message

CASES = [
    ("Apakah PER-10/BC/2023 masih berlaku?", "masih berlaku sampai 31 Des 2026; dicabut PER-12 mulai 1 Jan 2027"),
    ("Apakah PER-12/BC/2026 sudah berlaku?", "ditetapkan 25 Sep 2026; belum berlaku, mulai 1 Jan 2027"),
    ("siapa yang periksa kepatuhan pengusaha bkc dan seberapa sering?", "pakai PER-10 sebagai yang berlaku; sebut PER-12 mulai 2027"),
    ("Apakah INS-2/BC/2013 masih berlaku?", "dicabut INS-07/BC/2013 Diktum KEENAM sejak 1 Okt 2013"),
    ("Apakah PMK 191/PMK.04/2010 masih berlaku?", "Pasal 21A dicabut PMK 78/2013 Pasal 15 sejak 10 Jun 2013; induk dicabut 2018"),
    ("SE-8/BC/2013 dasar hukumnya apa dan apakah masih berlaku?", "belum ditemukan pencabutan; dasar PMK 78, bukan PMK 200/2008"),
    ("Apakah UU 1 Tahun 2026 mengubah ketentuan pidana di UU Cukai?", "ya, berlaku 2 Jan 2026; Lampiran I nomor 53"),
    ("PMK 124 Tahun 2024 apakah ada perubahannya?", "diubah PMK 117/2025, efektif 31 Des 2025, khusus penataan jabatan DJP"),
    ("Apakah PMK 200/PMK.04/2008 masih berlaku?", "dicabut 5 Juli 2018 oleh PMK 66/2018 Pasal 75"),
    ("Pengusaha pabrik harus menyampaikan pernyataan hubungan keterkaitan paling lambat 16 Oktober 2013, itu masih berlaku?", "tenggat historis, bukan kewajiban berkala"),
    ("Dasar hukum tarif cukai SKT untuk tahun 2026 apa?", "PMK 192/2021 sebagaimana terakhir diubah PMK 97/2024"),
    ("Apakah ada PMK tarif cukai baru setelah PMK 97 Tahun 2024?", "belum ditemukan untuk SKM, SPM, SKT"),
]


async def main():
    get_provider()
    for q, expect in CASES:
        req = ChatRequest(messages=[Message(role="user", content=q)])
        srcs = await retrieve(search_query(req))
        parts = []
        async for piece in get_provider().stream_answer(req.messages, srcs, {}):
            parts.append(piece)
        print(f"\n######## {q}\nHARAPAN AHLI: {expect}\n{''.join(parts)}")


import os
if os.environ.get('SUBSET'):
    CASES[:] = [CASES[0], CASES[11], CASES[9]]
asyncio.run(main())
