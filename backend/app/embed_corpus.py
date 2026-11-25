"""Menghitung embedding seluruh potongan korpus. Dijalankan sekali (dan setiap korpus berubah) di VPS:

    docker compose exec -T backend python -m app.embed_corpus

Hasilnya ke volume data (EMBEDDINGS_PATH). Biaya: sekitar 1,3 juta token, kurang dari US$0,03.
"""

import json
import sys
import time
from pathlib import Path

import numpy as np

from .config import settings
from .embeddings import chunk_text, corpus_hash
from .rag import _corpus_path

BATCH = 64
PRICE_PER_MTOKEN = 0.02  # text-embedding-3-small, USD


def main() -> None:
    from openai import OpenAI

    if settings.openai_api_key is None:
        sys.exit("OPENAI_API_KEY belum diisi.")
    corpus = _corpus_path()
    rows = [json.loads(line) for line in corpus.read_text(encoding="utf-8").splitlines() if line.strip()]
    texts = [chunk_text(r["title"], r["location"], r["text"]) for r in rows]
    print(f"{len(texts)} potongan dari {corpus}; model {settings.embedding_model}", flush=True)

    client = OpenAI(api_key=settings.openai_api_key.get_secret_value(), timeout=60, max_retries=3)
    vectors: list[list[float]] = []
    tokens = 0
    started = time.time()
    for i in range(0, len(texts), BATCH):
        res = client.embeddings.create(model=settings.embedding_model, input=texts[i : i + BATCH])
        vectors += [d.embedding for d in sorted(res.data, key=lambda d: d.index)]
        tokens += res.usage.total_tokens
        print(f"  {min(i + BATCH, len(texts))}/{len(texts)}  ({time.time() - started:.0f} dtk)", end="\r", flush=True)

    mat = np.asarray(vectors, dtype=np.float32)
    mat /= np.linalg.norm(mat, axis=1, keepdims=True).clip(min=1e-9)
    out = Path(settings.embeddings_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out,
        vectors=mat.astype(np.float16),  # separuh ukuran; cukup akurat untuk peringkat
        corpus_hash=np.str_(corpus_hash(corpus)),
        model=np.str_(settings.embedding_model),
    )
    print(f"\nSelesai: {mat.shape} -> {out} | {tokens:,} token ≈ ${tokens / 1e6 * PRICE_PER_MTOKEN:.3f}")


if __name__ == "__main__":
    main()
