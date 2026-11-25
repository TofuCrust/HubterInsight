"""Menghitung seberapa sering frasa meta ("di luar dokumen", "kutipan", dst.) muncul di jawaban hasil uji.

    python phrase_stats.py /eval/out_bm25_v2.json /eval/out_bm25.json /eval/status_v2b.json /eval/status_v3.json

Berkas boleh berformat arm_eval ({"cases": [...]}) atau status_run (daftar). Jawaban penolakan di luar topik tidak dihitung.
"""
import json
import re
import sys

PATTERNS = {
    "di luar dokumen": r"di luar dokumen",
    "berdasarkan dokumen/kutipan": r"berdasarkan (dokumen|kutipan)",
    "dokumen referensi": r"dokumen referensi",
    "kata 'kutipan'": r"\bkutipan\b",
    "belum ada/tersedia di dokumen": r"belum (ada|tersedia|tercantum|termuat)",
}


def answers(path: str) -> list[str]:
    data = json.load(open(path, encoding="utf-8"))
    rows = data["cases"] if isinstance(data, dict) else data
    return [r["answer"] for r in rows if r.get("answer")]


def general_paragraphs(text: str) -> int:
    """Paragraf tanpa [n] selain penutup 'Bukan nasihat hukum', butir daftar, dan tabel (perkiraan penjelasan umum)."""
    n = 0
    for para in re.split(r"\n\s*\n", text):
        p = para.strip()
        if not p or "Bukan nasihat hukum" in p or re.search(r"\[\d+\]", p) or p.startswith(("-", "|", "*", "#")):
            continue
        if len(p) > 60:
            n += 1
    return n


for path in sys.argv[1:]:
    rows = answers(path)
    n = len(rows)
    print(f"\n== {path.split('/')[-1]} ({n} jawaban)")
    for name, pat in PATTERNS.items():
        c = sum(1 for a in rows if re.search(pat, a, re.I))
        print(f"  {name:32} {c:>3} ({c / n:4.0%})")
    g = sum(1 for a in rows if general_paragraphs(a))
    print(f"  {'paragraf tanpa [n] (umum)':32} {g:>3} ({g / n:4.0%})")
