from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # .env dibaca bila ada (uji lokal dari folder proyek). Di Docker nilainya datang dari compose.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # "mock"   = hanya menampilkan bagian dokumen yang relevan, tanpa OpenAI (gratis)
    # "openai" = jawaban disusun model dari dokumen yang ditemukan (RAG)
    llm_mode: Literal["mock", "openai"] = "mock"

    # Kosong = backend/corpus/corpus.jsonl (dibuat oleh ingest/build_corpus.py).
    corpus_path: str = ""

    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5.4-mini"
    # Seri GPT-5: minimal | low | medium | high. Makin tinggi makin lambat dan mahal.
    openai_reasoning_effort: Literal["minimal", "low", "medium", "high"] = "low"
    # Batas token keluaran (termasuk token berpikir model).
    openai_max_output_tokens: int = 4000
    openai_timeout_seconds: float = 90.0

    # "bm25" = pencarian kata (v1). "hybrid" = BM25 digabung kemiripan makna (embedding OpenAI), lebih tahan
    # terhadap bahasa santai dan kata tidak baku. Hybrid otomatis kembali ke BM25 bila embedding tidak tersedia.
    search_mode: Literal["bm25", "hybrid"] = "bm25"
    embedding_model: str = "text-embedding-3-small"
    embeddings_path: str = "data/embeddings.npz"
    embedding_timeout_seconds: float = 6.0
    # Potongan dengan kemiripan makna di bawah ini diabaikan dari peringkat makna (pertanyaan di luar topik).
    sim_floor: float = 0.25

    # Mode agentic: kutipan awal tetap dicari otomatis, tetapi model boleh memanggil alat cari_dokumen untuk
    # mencari lagi dengan kata kunci lain. Lebih mahal dan lebih lambat, jadi nonaktif secara default.
    agentic: bool = False
    agentic_max_rounds: int = 3  # panggilan model per pertanyaan (yang terakhir selalu jawaban akhir)
    agentic_max_searches: int = 4  # pencarian tambahan per pertanyaan
    agentic_force_search: bool = False  # wajibkan minimal satu pencarian tambahan (bahan uji; menambah biaya)

    # Login bersama untuk pemakai internal (lihat auth.py). AUTH_PASSWORD kosong = tanpa login (pengembangan lokal).
    auth_user: str = "hubter"
    auth_password: SecretStr | None = None
    auth_secret: SecretStr | None = None  # kunci tanda tangan cookie; kosong = diturunkan dari kata sandi
    auth_session_days: int = 30

    # Halaman Dokumen: folder unggahan, batas per berkas, dan batas total folder (MB). Di Docker: bind mount ./uploads.
    upload_dir: str = "data/uploads"
    upload_max_mb: int = 25
    upload_quota_mb: int = 1000

    # Menambahkan baris "Status:" (berlaku/dicabut, lihat doc_status.py) pada kutipan yang dikirim ke model.
    doc_status: bool = True

    # Label versi cara kerja (pencarian, prompt, model). Naikkan tiap perubahan yang memengaruhi jawaban
    # agar hasil evaluasi di log bisa dibandingkan antarversi. Tampil di bilah kiri dan tersimpan di log.
    app_version: str = "v4.3"

    # Log pertanyaan/jawaban/umpan balik untuk evaluasi (SQLite). Di Docker: volume di /data.
    log_enabled: bool = True
    log_db_path: str = "data/hubter.db"

    max_messages: int = 20
    max_message_chars: int = 4000

    # Pembatas permintaan per alamat IP dan total harian (pelindung biaya). 0 = nonaktif.
    # Nilai untuk pemakaian internal beberapa orang yang bisa berbagi satu jaringan (satu IP). Dapat diubah lewat
    # .env (RATE_LIMIT_PER_MINUTE, RATE_LIMIT_PER_DAY, DAILY_REQUEST_CAP, LOGIN_RATE_PER_MINUTE, LOGIN_RATE_PER_DAY).
    rate_limit_per_minute: int = 30
    rate_limit_per_day: int = 300
    daily_request_cap: int = 600  # ≈ US$5-6 per hari pada gpt-5.4-mini; satu-satunya pelindung total kredit
    login_rate_per_minute: int = 30  # percobaan masuk per IP
    login_rate_per_day: int = 500


settings = Settings()
