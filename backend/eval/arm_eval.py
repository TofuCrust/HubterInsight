"""Uji ujung-ke-ujung satu lengan: ARM=bm25 | hybrid | agentic. Jalankan di container backend (OPENAI_API_KEY ada)."""
import asyncio
import json
import os
import re
import time

import app.rag as rag
from app.agent import run_agent
from app.providers import OpenAIProvider, get_provider
from app.rag import retrieve

ARM = os.environ["ARM"]
PRICE_IN, PRICE_OUT = 0.75, 4.50

CASES = [
    ("Apa saja kriteria penetapan hubungan keterkaitan antara pengusaha pabrik hasil tembakau menurut PMK 78/PMK.011/2013?", [("PMK 78", "Pasal 2 ")]),
    ("Berapa tarif cukai SKM golongan I tahun 2024?", [("Tabel tarif", "R15")]),
    ("Apakah penyertaan modal 20 persen pada pabrik lain dianggap hubungan keterkaitan?", [("PMK 78", "Pasal 2 ")]),
    ("Bagaimana pemeriksaan terhadap pengusaha pabrik yang tidak menyampaikan data hubungan keterkaitan?", [("PER-21", ""), ("PER-27", "")]),
    ("Pasal 3 PMK 78/PMK.011/2013", [("PMK 78", "Pasal 3 ")]),
    ("Apa perubahan yang dibuat PMK 131 terhadap PMK 78?", [("PMK 131", "")]),
    ("Apa isi penelitian Kepala Kantor untuk mendapatkan indikasi hubungan keterkaitan?", [("INS-", ""), ("PMK 78", "Pasal 5")]),
    ("cara menagih kalo perusahaan kena hubter oleh KPPBC?", [("PMK 78", "Pasal 14"), ("Diskusi: Mekanisme", "")]),
    ("siapa yang nentuin sebuah perusahaan itu kena hubter?", [("PMK 78", "Pasal 12"), ("PMK 78", "Pasal 16"), ("PMK 78", "Pasal 10"), ("PMK 78", "Pasal 5")]),
    ("Siapa yang berwenang menetapkan hubungan keterkaitan?", [("PMK 78", "Pasal 12"), ("PMK 78", "Pasal 16"), ("PMK 78", "Pasal 10"), ("PMK 78", "Pasal 5")]),
    ("kalo hubungan keluarga masih dianggap hubter gak sih?", [("PMK 131", ""), ("PMK 78", "Pasal 2 ")]),
    ("perusahaan yang gak nyerahin pernyataan hubter diapain?", [("PER-21", ""), ("PER-27", "")]),
    ("apa bedanya PMK 78 sama 131?", [("PMK 131", "")]),
    ("sampai kapan pita cukai tarif lama boleh dipakai setelah hubter ditetapkan?", [("PMK 78", "Pasal 12")]),
    ("tarif SPM golongan 2 tahun 2025 berapa sih", [("Tabel tarif", "R16")]),
    ("berapa tarif rokok kretek tangan golongan 1 di tahun 2013?", [("Tabel tarif", "R05")]),
    ("apa yang dimaksud manajemen kunci dalam hubter?", [("PMK 78", "Pasal 2 ")]),
    ("kapan PMK 131 mulai berlaku?", [("PMK 131", "")]),
    ("batas waktu pengusaha ngaku sendiri punya hubter setelah aturan baru berlaku", [("PMK 131", ""), ("Materi sosialisasi", ""), ("PER-21", ""), ("PER-27", "")]),
    ("pabrik kecil yang cuma bikin SKT golongan 3 kena hubter juga nggak?", [("PMK 131", "")]),
    ("gimana nasib surat pernyataan yang masuk antara Juni sampai Oktober 2013?", [("PMK 131", "")]),
    ("pejabat mana yang ngawasin hubter di wilayah?", [("Diskusi: Pengawasan HubTer oleh Kanwil", ""), ("Pertanggungjawaban DTFC", ""), ("PMK 78", ""), ("Diskusi: Pengawasan HubTer oleh KPPBC", "")]),
]
OFFTOPIC = ["Berikan resep nasi goreng.", "siapa presiden amerika serikat", "cara membuat website dengan python"]


def hit(srcs, exp):
    return any(any(s.title.startswith(t) and (s.location or "").startswith(l) for t, l in exp) for s in srcs)


class Msg:
    def __init__(self, content):
        self.role, self.content = "user", content


async def answer(q):
    t0 = time.monotonic()
    usage, searches, parts = {}, [], []
    srcs = await retrieve(q)
    msgs = [Msg(q)]
    if ARM.startswith("agentic"):
        provider = get_provider()
        async for kind, val in run_agent(provider.client, msgs, srcs, usage, searches):
            if kind == "token":
                parts.append(val)
            elif kind == "sources":
                srcs = val
    else:
        async for piece in get_provider().stream_answer(msgs, srcs, usage):
            parts.append(piece)
    text = "".join(parts)
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", text)}
    cited_srcs = [s for s in srcs if s.id in cited]
    return {
        "q": q, "answer": text, "searches": searches, "n_sources": len(srcs),
        "titles": [f"{s.id}. {s.title} · {s.location}" for s in srcs],
        "cited": sorted(cited), "usage": usage, "sec": round(time.monotonic() - t0, 1),
        "_srcs": srcs, "_cited": cited_srcs,
    }


async def main():
    if ARM == "hybrid":
        rag.FUSE_DEPTH, rag.SEMANTIC_RRF_WEIGHT = 10, 0.3
        assert rag.get_index().vectors is not None, "vektor embedding tidak termuat"
    get_provider()
    rows = []
    for i, (q, exp) in enumerate(CASES, 1):
        r = await answer(q)
        r["avail"] = hit(r["_srcs"], exp)
        r["cited_hit"] = hit(r["_cited"], exp)
        r["cost"] = (r["usage"].get("input_tokens", 0) * PRICE_IN + r["usage"].get("output_tokens", 0) * PRICE_OUT) / 1e6
        rows.append(r)
        print(f"{i:>2} avail={int(r['avail'])} cited={int(r['cited_hit'])} cari={len(r['searches'])} "
              f"{r['sec']:>5}s ${r['cost']:.4f}  {q[:60]}", flush=True)
        for s in r["searches"]:
            print(f"      > {s}", flush=True)
    off = []
    for q in OFFTOPIC:
        r = await answer(q)
        off.append(r)
        print(f"OFF searches={len(r['searches'])} cited={r['cited']} :: {q} -> {r['answer'][:90]!r}", flush=True)
    n = len(CASES)
    print(f"\n== {ARM}: avail {sum(r['avail'] for r in rows)}/{n}, cited {sum(r['cited_hit'] for r in rows)}/{n}, "
          f"biaya rata-rata ${sum(r['cost'] for r in rows)/n:.4f}, median {sorted(r['sec'] for r in rows)[n//2]}s, "
          f"cari rata-rata {sum(len(r['searches']) for r in rows)/n:.2f}")
    for r in rows + off:
        r.pop("_srcs"), r.pop("_cited")
    os.makedirs("/eval", exist_ok=True)
    with open(f"/eval/out_{ARM}.json", "w", encoding="utf-8") as f:
        json.dump({"cases": rows, "offtopic": off}, f, ensure_ascii=False, indent=1)


asyncio.run(main())
