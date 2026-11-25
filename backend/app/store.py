"""Penyimpanan pertanyaan, jawaban, dan umpan balik penilai (SQLite) untuk tahap evaluasi.

Sengaja tanpa IP atau identitas: hanya ID sesi acak dari browser agar percakapan bisa dibaca berurutan.
Berkas ada di volume Docker (bukan di image) dan dibaca lewat SSH dengan `python -m app.export_log`,
tidak lewat URL, karena situs ini tidak punya login.
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .config import settings

log = logging.getLogger("hubter")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    session TEXT,
    version TEXT,
    mode TEXT,
    model TEXT,
    question TEXT NOT NULL,
    history_len INTEGER,
    search_query TEXT,
    sources TEXT,
    answer TEXT,
    status TEXT,
    latency_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER
);
CREATE INDEX IF NOT EXISTS chats_ts ON chats (ts);
CREATE TABLE IF NOT EXISTS feedback (
    chat_id TEXT PRIMARY KEY,
    ts TEXT NOT NULL,
    rating INTEGER,
    comment TEXT
);
"""

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _db() -> sqlite3.Connection | None:
    global _conn
    if not settings.log_enabled:
        return None
    if _conn is None:
        path = Path(settings.log_db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(_SCHEMA)
        _conn = conn
    return _conn


def save_chat(
    *,
    chat_id: str,
    session: str | None,
    question: str,
    history_len: int,
    search_query: str,
    sources: list[dict],
    answer: str,
    status: str,
    latency_ms: int,
    usage: dict,
) -> None:
    """Gagal menyimpan tidak boleh mengganggu jawaban: kesalahan hanya dicatat di log server."""
    try:
        with _lock:
            db = _db()
            if db is None:
                return
            db.execute(
                "INSERT OR REPLACE INTO chats (id, ts, session, version, mode, model, question, history_len,"
                " search_query, sources, answer, status, latency_ms, input_tokens, output_tokens)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    chat_id,
                    _now(),
                    session,
                    settings.app_version,
                    settings.llm_mode,
                    settings.openai_model if settings.llm_mode == "openai" else "mock",
                    question,
                    history_len,
                    search_query,
                    json.dumps(sources, ensure_ascii=False),
                    answer,
                    status,
                    latency_ms,
                    usage.get("input_tokens"),
                    usage.get("output_tokens"),
                ),
            )
            db.commit()
    except Exception:
        log.exception("Gagal menyimpan log percakapan")


def save_feedback(chat_id: str, rating: int | None, comment: str | None) -> bool:
    """Menyimpan (atau memperbarui) umpan balik. False bila chat_id tidak dikenal."""
    try:
        with _lock:
            db = _db()
            if db is None:
                return False
            if db.execute("SELECT 1 FROM chats WHERE id = ?", (chat_id,)).fetchone() is None:
                return False
            db.execute(
                "INSERT INTO feedback (chat_id, ts, rating, comment) VALUES (?,?,?,?)"
                " ON CONFLICT(chat_id) DO UPDATE SET ts = excluded.ts,"
                " rating = COALESCE(excluded.rating, rating),"
                " comment = COALESCE(excluded.comment, comment)",
                (chat_id, _now(), rating, comment),
            )
            db.commit()
            return True
    except Exception:
        log.exception("Gagal menyimpan umpan balik")
        return False
