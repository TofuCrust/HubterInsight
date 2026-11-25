"""Menilai kasus yang gagal pada uji sintetis: apakah 8 kutipan teratas BM25 sebenarnya sudah memuat jawaban
(alternatif sah, mis. topik yang sama diatur beberapa peraturan), apakah pertanyaannya tidak mandiri, atau
benar-benar meleset. Hasil ke /eval/synth_judged.json.

    docker compose run --rm -T --no-deps -v $HOME/hubter-eval:/eval -e PYTHONPATH=/srv backend python /eval/synth_judge.py
"""
import asyncio
import json

from openai import AsyncOpenAI

from app.config import settings
from app.rag import get_index

SYSTEM = """Anda menilai hasil pencarian untuk sistem tanya-jawab hukum cukai. Diberikan pertanyaan pengguna dan 8 kutipan dokumen teratas.
Keluarkan JSON: {"ambigu": true/false, "ada_jawaban": true/false, "alasan": "satu kalimat"}
- ambigu=true bila pertanyaan tidak bisa dijawab tanpa mengetahui peraturan atau konteks yang dimaksud (misalnya "mulainya kapan?", "pengusaha pabrik itu maksudnya siapa?" tanpa dokumen).
- ada_jawaban=true bila SALAH SATU kutipan memuat informasi yang cukup untuk menjawab pertanyaan secara benar (walau dari peraturan lain dari yang mungkin dimaksud). Bila kutipan hanya satu topik tetapi tidak memuat jawabannya, false."""


async def main() -> None:
    index = get_index()
    fails = json.load(open("/eval/synth_fail_bm25.json", encoding="utf-8"))
    client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value(), timeout=90, max_retries=3)
    sem = asyncio.Semaphore(8)

    async def judge(f):
        res = index.search(f["question"], 8)
        blocks = "\n".join(f"[{n}] {c.title} · {c.location}\n{c.text[:900]}" for n, c in enumerate(res, 1))
        async with sem:
            try:
                r = await client.chat.completions.create(
                    model="gpt-5.4-mini",
                    messages=[{"role": "system", "content": SYSTEM},
                              {"role": "user", "content": f"Pertanyaan: {f['question']}\n\nKutipan:\n{blocks}"}],
                    response_format={"type": "json_object"},
                    reasoning_effort="low",
                    max_completion_tokens=800,
                )
                return {**f, **json.loads(r.choices[0].message.content)}
            except Exception as e:
                print("gagal:", type(e).__name__)
                return {**f, "ambigu": None, "ada_jawaban": None, "alasan": "gagal dinilai"}

    out = await asyncio.gather(*(judge(f) for f in fails))
    with open("/eval/synth_judged.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    amb = sum(1 for o in out if o["ambigu"])
    ok = sum(1 for o in out if not o["ambigu"] and o["ada_jawaban"])
    miss = [o for o in out if o["ambigu"] is False and o["ada_jawaban"] is False]
    print(f"{len(out)} gagal: ambigu={amb}, alternatif sah (ada jawaban)={ok}, benar-benar meleset={len(miss)}")


asyncio.run(main())
