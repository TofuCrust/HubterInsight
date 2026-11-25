"""Membuat pertanyaan uji sintetis dari korpus: tiap potongan dokumen yang dipilih diberi 2 pertanyaan
(baku dan santai) yang jawabannya ada di potongan itu. Potongan asal menjadi kunci jawaban untuk uji pencarian.

Dijalankan di container backend (butuh OPENAI_API_KEY), hasil ke /eval/synth.json:

    docker compose run --rm -T --no-deps -v $HOME/hubter-eval:/eval -e PYTHONPATH=/srv backend \
        python /eval/synth_gen.py [--limit 10]
"""
import argparse
import asyncio
import json
import random
import re

from openai import AsyncOpenAI

from app.config import settings
from app.rag import get_index

MODEL = "gpt-5.4-mini"
MAX_CHARS = 1800
# Dokumen umum yang besar: jarang ditanyakan penilai, jadi jatahnya kecil agar tidak mendominasi.
GENERIC = ("PMK 124", "UU 7 Tahun", "Susunan Dalam", "UU 1 Tahun 2026", "UU 11 Tahun 1995", "UU 39 Tahun")
QUOTA = {"Regulasi": 12, "Data tarif": 20, "Hasil telaah": 8, "Publikasi": 8}
DEFAULT_QUOTA = 10  # riwayat diskusi
GENERIC_QUOTA = 6

SYSTEM = """Anda membuat pertanyaan uji untuk sistem tanya-jawab hukum cukai hasil tembakau (hubungan keterkaitan atau HubTer, tarif cukai, golongan pengusaha pabrik, NPPBKC). Diberikan satu potongan dokumen. Buat pertanyaan yang jawabannya ada di potongan itu, seolah ditulis praktisi yang tidak sedang melihat dokumennya.

Keluarkan JSON: {"layak": true/false, "baku": "...", "santai": "..."}

Aturan:
- layak=false bila potongan hanya daftar isi, judul, konsiderans, tabel tanpa makna, atau terlalu terpotong untuk ditanyakan. Isi baku dan santai dengan "" bila tidak layak.
- baku: kalimat tanya formal dan lengkap. Boleh menyebut nama peraturan (misalnya "PMK 78") bila wajar. Jangan menulis "potongan", "dokumen ini", atau "pasal ini".
- santai: seperti chat singkat seorang praktisi: huruf kecil, boleh singkatan (hubter, kppbc, dtfc, nppbkc, skm, skt, spm) dan kata tidak baku (nentuin, gimana, gak, kalo, udah, yg). Tanpa nomor pasal dan tanpa nomor peraturan. JANGAN menyalin frasa khas dari teks; pakai kata sehari-hari atau parafrase.
- Setiap pertanyaan menanyakan SATU hal saja dan paling banyak 20 kata, seperti pertanyaan pendek yang biasa diketik pengguna. Jangan memuat beberapa pertanyaan sekaligus dan jangan merinci semua isi potongan.
- Keduanya harus bisa dipahami tanpa potongan dan spesifik pada isi potongan (angka, pejabat, syarat, tenggat, golongan, periode)."""


def pick(index, rng: random.Random):
    by_title: dict[str, list[int]] = {}
    seen_groups: set[int] = set()
    for i, c in enumerate(index.chunks):
        if len(c.text) < 250 or c.location.startswith("Pembukaan"):
            continue
        g = index.group_id[i]
        if g in seen_groups:
            continue
        seen_groups.add(g)
        by_title.setdefault(c.title, []).append(i)
    picked: list[int] = []
    for title, ids in by_title.items():
        kind = index.chunks[ids[0]].kind
        quota = GENERIC_QUOTA if title.startswith(GENERIC) else QUOTA.get(kind, DEFAULT_QUOTA)
        picked += rng.sample(ids, min(quota, len(ids)))
    return picked


async def ask(client: AsyncOpenAI, sem: asyncio.Semaphore, index, i: int) -> list[dict]:
    c = index.chunks[i]
    text = re.sub(r"^Pertanyaan pengguna:.*\n?", "", c.text, count=1)[:MAX_CHARS]  # jangan bocorkan pertanyaan asli
    user = f"Jenis: {c.kind}\nDokumen: {c.title}\nBagian: {c.location}\n\n{text}"
    async with sem:
        try:
            r = await client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                response_format={"type": "json_object"},
                reasoning_effort="none",
                max_completion_tokens=600,
            )
            data = json.loads(r.choices[0].message.content)
        except Exception as e:  # satu potongan gagal tidak menghentikan yang lain
            print("gagal:", c.title, c.location, type(e).__name__)
            return []
    if not data.get("layak"):
        return []
    base = {"chunk_id": c.id, "title": c.title, "kind": c.kind, "location": c.location}
    return [{**base, "style": s, "question": data[s].strip()} for s in ("baku", "santai") if data.get(s, "").strip()]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    index = get_index()
    ids = pick(index, random.Random(args.seed))
    if args.limit:
        ids = random.Random(args.seed).sample(ids, args.limit)
    print(f"{len(ids)} potongan dipilih")
    client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value(), timeout=60, max_retries=3)
    sem = asyncio.Semaphore(8)
    results = await asyncio.gather(*(ask(client, sem, index, i) for i in ids))
    rows = [r for part in results for r in part]
    out = "/eval/synth_sample.json" if args.limit else "/eval/synth.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    print(f"{len(rows)} pertanyaan dari {sum(1 for p in results if p)} potongan -> {out}")


asyncio.run(main())
