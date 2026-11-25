"""Uji pencarian (tanpa memanggil model jawaban) pada pertanyaan sintetis /eval/synth.json.

Kunci jawaban = potongan asal pertanyaan (dibandingkan per kelompok Pasal, jadi potongan bersaudara dalam satu
Pasal dianggap sama). Dijalankan di container backend dengan SEARCH_MODE=hybrid agar vektor termuat:

    docker compose run --rm -T --no-deps -v $HOME/hubter-eval:/eval -e PYTHONPATH=/srv -e SEARCH_MODE=hybrid \
        backend python /eval/synth_eval.py
"""
import asyncio
import json
from collections import defaultdict

import app.rag as rag
from app.doc_status import status_of
from app.embeddings import embed_query
from app.rag import get_index

K = 8
DEEP = 20

ARMS = [  # (nama, qvec dipakai?, FUSE_DEPTH, SEMANTIC_RRF_WEIGHT)
    ("bm25", False, 0, 0),
]


def kind_group(kind: str) -> str:
    if kind.startswith("Riwayat"):
        return "Diskusi"
    return {"Regulasi": "Regulasi", "Data tarif": "Tarif"}.get(kind, "Telaah/publikasi")


async def main() -> None:
    index = get_index()
    assert index.vectors is not None, "vektor embedding tidak termuat (SEARCH_MODE=hybrid?)"
    rows = json.load(open("/eval/synth.json", encoding="utf-8"))
    id_to_idx = {c.id: i for i, c in enumerate(index.chunks)}
    sem = asyncio.Semaphore(8)

    async def vec(q):
        async with sem:
            return await embed_query(q)

    qvecs = await asyncio.gather(*(vec(r["question"]) for r in rows))
    print(f"{len(rows)} pertanyaan; vektor kosong: {sum(v is None for v in qvecs)}")

    failures = []
    for name, use_vec, depth, weight in ARMS:
        if use_vec:
            rag.FUSE_DEPTH, rag.SEMANTIC_RRF_WEIGHT = depth, weight
        stats = defaultdict(lambda: [0, 0, 0, 0.0])  # n, hit@K, hit@DEEP, rr
        for r, v in zip(rows, qvecs):
            want = index.group_id[id_to_idx[r["chunk_id"]]]
            res = index.search(r["question"], DEEP, qvec=v if use_vec else None)
            groups = [index.group_id[id_to_idx[c.id]] for c in res]
            rank = groups.index(want) + 1 if want in groups else None
            keys = ["semua", r["style"], kind_group(r["kind"])]
            keys.append("kunci dicabut" if status_of(r["title"])[1] else "kunci berlaku/lain")
            for key in keys:
                s = stats[key]
                s[0] += 1
                s[1] += bool(rank and rank <= K)
                s[2] += rank is not None
                s[3] += 1 / rank if rank and rank <= K else 0
            if name == "bm25" and not (rank and rank <= K):
                failures.append({**{k: r[k] for k in ("style", "title", "location", "question")},
                                 "rank": rank, "top": [f"{c.title[:30]} · {c.location[:24]}" for c in res[:3]]})
        print(f"\n== {name}")
        for key in ("semua", "baku", "santai", "Regulasi", "Tarif", "Diskusi", "Telaah/publikasi", "kunci dicabut", "kunci berlaku/lain"):
            n, h, d, rr = stats[key]
            print(f"  {key:17} n={n:<4} hit@{K}={h/n:6.1%}  hit@{DEEP}={d/n:6.1%}  MRR@{K}={rr/n:.3f}")
    with open("/eval/synth_fail_bm25.json", "w", encoding="utf-8") as f:
        json.dump(failures, f, ensure_ascii=False, indent=1)
    print(f"\nkegagalan BM25 disimpan: {len(failures)}")


asyncio.run(main())
