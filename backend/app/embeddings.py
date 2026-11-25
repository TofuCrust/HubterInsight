"""Embedding (kemiripan makna) untuk pencarian hybrid.

Vektor seluruh potongan dihitung sekali dengan `python -m app.embed_corpus` (di VPS, tempat kunci OpenAI
berada) dan disimpan di volume data. Saat pertanyaan masuk, hanya pertanyaannya yang di-embed (satu panggilan
murah). Bila vektor tidak ada, tidak cocok dengan korpus, atau panggilan gagal, pencarian jalan terus
dengan BM25 saja.
"""

import hashlib
import logging
from pathlib import Path

import numpy as np

from .config import settings

log = logging.getLogger("hubter")

MAX_EMBED_CHARS = 6000  # sekitar 2.000 token; batas model 8.191 token
MAX_QUERY_CHARS = 2000


def corpus_hash(corpus_path: Path) -> str:
    return hashlib.sha1(corpus_path.read_bytes()).hexdigest()


def chunk_text(title: str, location: str, text: str) -> str:
    """Teks yang di-embed: judul dan lokasi ikut, supaya "Pasal 14 PMK 78" dan topik dokumen terwakili."""
    return f"{title}\n{location}\n{text}"[:MAX_EMBED_CHARS]


def load_vectors(path: Path, expected_hash: str, expected_rows: int) -> np.ndarray | None:
    """Vektor ter-normalisasi (float32), atau None bila tidak tersedia atau tidak cocok dengan korpus."""
    if not path.exists():
        log.warning("Berkas embedding %s tidak ada; pencarian hybrid nonaktif (BM25 saja).", path)
        return None
    try:
        data = np.load(path, allow_pickle=False)
        if str(data["corpus_hash"]) != expected_hash or str(data["model"]) != settings.embedding_model:
            log.warning("Embedding tidak cocok dengan korpus/model saat ini; jalankan ulang embed_corpus.")
            return None
        vectors = data["vectors"].astype(np.float32)
    except Exception:
        log.exception("Gagal memuat embedding; pencarian hybrid nonaktif.")
        return None
    if vectors.shape[0] != expected_rows:
        log.warning("Jumlah vektor (%d) berbeda dari jumlah potongan (%d).", vectors.shape[0], expected_rows)
        return None
    log.info("Embedding dimuat: %d vektor", vectors.shape[0])
    return vectors


_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import AsyncOpenAI

        if settings.openai_api_key is None:
            return None
        _client = AsyncOpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=settings.embedding_timeout_seconds,
            max_retries=1,
        )
    return _client


async def embed_query(text: str) -> np.ndarray | None:
    """Vektor ter-normalisasi untuk satu pertanyaan, atau None bila gagal (pencarian lanjut tanpa embedding)."""
    client = _get_client()
    if client is None:
        return None
    try:
        res = await client.embeddings.create(model=settings.embedding_model, input=[text[:MAX_QUERY_CHARS]])
        vec = np.asarray(res.data[0].embedding, dtype=np.float32)
        norm = np.linalg.norm(vec)
        return vec / norm if norm else None
    except Exception:
        log.warning("Embedding pertanyaan gagal; memakai BM25 saja.", exc_info=True)
        return None
