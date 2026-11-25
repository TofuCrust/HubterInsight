"""Menjalankan pertanyaan berbentuk skenario (pengguna menjelaskan kondisi, lalu bertanya aturan mana yang berlaku)
dan mencetak jawaban beserta sumber yang dirujuk.

    ... -e PYTHONPATH=/srv backend python /eval/scenario_run.py
"""
import asyncio
import re

from app.providers import get_provider
from app.rag import retrieve

SCENARIOS = [
    "Saya punya pabrik rokok SKT. Adik kandung saya juga punya pabrik rokok lain, dan saya memegang 25% saham di pabriknya. Apakah pabrik kami dianggap punya hubungan keterkaitan?",
    "Direktur pabrik saya merangkap jadi komisaris di pabrik rokok lain. Kena hubungan keterkaitan nggak, dan aturan mana yang mengatur?",
    "Pabrik saya baru dapat surat pemberitahuan kesimpulan sementara soal hubungan keterkaitan dari kantor wilayah. Saya harus ngapain dan berapa lama waktunya?",
    "Kami belum menyampaikan pernyataan soal hubungan keterkaitan ke Kepala Kantor padahal sudah lewat batas waktunya. Apa yang bakal terjadi ke kami?",
    "Pabrik tetangga saya jual rokok tanpa pita cukai. Itu kena aturan apa dan sanksinya apa?",
    "Pabrik kami sudah ditetapkan punya hubungan keterkaitan, tapi stok pita cukai dengan tarif lama masih banyak. Boleh dipakai sampai kapan?",
    "tadi pagi aku liat orang maling kambing, kena pasal apa ya dia?",
]


class Msg:
    def __init__(self, content):
        self.role, self.content = "user", content


async def main():
    get_provider()
    for q in SCENARIOS:
        srcs = await retrieve(q)
        parts = []
        async for piece in get_provider().stream_answer([Msg(q)], srcs, {}):
            parts.append(piece)
        text = "".join(parts)
        cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", text)})
        print(f"\n######## {q}\nSUMBER DIRUJUK: {[f'{s.id}. {s.title[:28]} {s.location or chr(45)}'[:60] for s in srcs if s.id in cited]}\n{text}")


asyncio.run(main())
