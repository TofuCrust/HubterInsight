"""Membaca log evaluasi (pertanyaan, jawaban, umpan balik) dari SQLite.

Dijalankan lewat SSH di dalam container backend; hasilnya ke layar atau dialihkan ke berkas:

    docker compose exec -T backend python -m app.export_log --format md > log.md
    docker compose exec -T backend python -m app.export_log --format csv > log.csv
    docker compose exec -T backend python -m app.export_log --format stats

Pilihan: --since 2026-11-24 (tanggal UTC), --rated (hanya yang diberi 👍/👎 atau komentar), --bad (hanya 👎).
"""

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path

from .config import settings

# Harga per 1 juta token untuk perkiraan biaya (USD): (masuk, keluar). Perbarui bila model diganti.
PRICES = {"gpt-5.4-mini": (0.75, 4.50), "gpt-5-mini": (0.25, 2.00)}

QUERY = """
SELECT c.*, f.rating AS rating, f.comment AS comment
FROM chats c LEFT JOIN feedback f ON f.chat_id = c.id
WHERE c.ts >= ? {extra}
ORDER BY c.ts
"""


def fetch(db: Path, since: str, rated: bool, bad: bool) -> list[sqlite3.Row]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    extra = ""
    if bad:
        extra = "AND f.rating = -1"
    elif rated:
        extra = "AND (f.rating IS NOT NULL OR f.comment IS NOT NULL)"
    return conn.execute(QUERY.format(extra=extra), (since,)).fetchall()


def cost(row: sqlite3.Row) -> float:
    price = PRICES.get(row["model"])
    if not price or row["input_tokens"] is None:
        return 0.0
    return (row["input_tokens"] * price[0] + (row["output_tokens"] or 0) * price[1]) / 1_000_000


def print_markdown(rows: list[sqlite3.Row]) -> None:
    for r in rows:
        mark = {1: "👍", -1: "👎"}.get(r["rating"], "")
        print(f"## {r['ts']} · {r['version']} · {r['model']} · sesi {str(r['session'])[:8]} {mark}\n")
        print(f"**Pertanyaan:** {r['question']}\n")
        if r["history_len"]:
            print(f"_(lanjutan percakapan, {r['history_len']} pesan sebelumnya)_\n")
        if r["comment"]:
            print(f"**Komentar penilai:** {r['comment']}\n")
        print(f"**Jawaban** ({r['status']}, {r['latency_ms']} ms, token {r['input_tokens']}/{r['output_tokens']}):\n")
        print(f"{r['answer']}\n")
        if "[agentic]" in (r["search_query"] or ""):
            print(f"**Pencarian tambahan oleh model:** {r['search_query'].split('[agentic]', 1)[1].strip()}\n")
        sources = json.loads(r["sources"] or "[]")
        if sources:
            print("**Sumber terambil:**")
            for i, s in enumerate(sources, 1):
                print(f"{i}. {s['title']} · {s.get('location') or '-'}")
            print()
        print("---\n")


def print_csv(rows: list[sqlite3.Row]) -> None:
    out = csv.writer(sys.stdout)
    out.writerow(["waktu", "versi", "model", "sesi", "pertanyaan", "jawaban", "rating", "komentar", "status",
                  "latensi_ms", "token_masuk", "token_keluar", "kata_kunci_cari", "sumber"])
    for r in rows:
        sources = " | ".join(f"{s['title']} · {s.get('location') or '-'}" for s in json.loads(r["sources"] or "[]"))
        out.writerow([r["ts"], r["version"], r["model"], r["session"], r["question"], r["answer"], r["rating"],
                      r["comment"], r["status"], r["latency_ms"], r["input_tokens"], r["output_tokens"],
                      r["search_query"], sources])


def print_stats(rows: list[sqlite3.Row]) -> None:
    n = len(rows)
    print(f"Jumlah pertanyaan: {n}")
    if not n:
        return
    for version in sorted({r["version"] for r in rows}):
        part = [r for r in rows if r["version"] == version]
        up = sum(1 for r in part if r["rating"] == 1)
        down = sum(1 for r in part if r["rating"] == -1)
        lat = sorted(r["latency_ms"] or 0 for r in part)
        print(f"- {version}: {len(part)} pertanyaan, 👍 {up}, 👎 {down}, "
              f"median {lat[len(lat) // 2] / 1000:.1f} dtk, perkiraan biaya ${sum(cost(r) for r in part):.3f}")
    bad = {s: sum(1 for r in rows if r["status"] == s) for s in {r["status"] for r in rows}}
    print("Status:", ", ".join(f"{k}={v}" for k, v in sorted(bad.items())))
    print(f"Sesi berbeda: {len({r['session'] for r in rows})}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--format", choices=["md", "csv", "stats"], default="md")
    ap.add_argument("--since", default="1970-01-01")
    ap.add_argument("--rated", action="store_true")
    ap.add_argument("--bad", action="store_true")
    args = ap.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    db = Path(settings.log_db_path)
    if not db.exists():
        sys.exit(f"Belum ada log di {db}.")
    rows = fetch(db, args.since, args.rated, args.bad)
    {"md": print_markdown, "csv": print_csv, "stats": print_stats}[args.format](rows)


if __name__ == "__main__":
    main()
