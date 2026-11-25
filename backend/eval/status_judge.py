"""Menilai jawaban dari status_run.py: apakah jawaban menyajikan ketentuan peraturan yang sudah dicabut sebagai
ketentuan yang berlaku, tanpa menyebut bahwa sudah dicabut? Peta status dipakai sebagai kunci.

    ... python /eval/status_judge.py v1 v2
"""
import asyncio
import json
import sys

from openai import AsyncOpenAI

from app.config import settings
from app.doc_status import as_prompt_table

SYSTEM = f"""Anda menilai jawaban sistem tanya-jawab hukum cukai terhadap PETA STATUS peraturan berikut (kunci jawaban):
{as_prompt_table()}

Diberikan pertanyaan, jawaban, dan daftar kutipan yang dirujuk jawaban. Keluarkan JSON:
{{"memakai_dicabut": true/false, "menyesatkan": true/false, "menyebut_pengganti": true/false, "alasan": "satu kalimat"}}
- memakai_dicabut=true bila jawaban memuat ketentuan, angka, syarat, atau prosedur yang bersumber dari peraturan berstatus DICABUT/TIDAK BERLAKU.
- menyesatkan=true bila (memakai_dicabut) jawaban menyajikan ketentuan itu sebagai ketentuan yang berlaku sekarang, atau tidak menyebut sama sekali bahwa peraturan itu sudah dicabut/diganti. Bila jawaban jelas menyatakan peraturan itu sudah dicabut (misalnya karena pengguna bertanya tentangnya) dan hanya memakainya sebagai riwayat, menyesatkan=false.
- menyebut_pengganti=true bila jawaban menyebut peraturan pengganti yang benar menurut peta, bila ada peraturan dicabut yang disinggung."""


async def main() -> None:
    labels = sys.argv[1:]
    client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value(), timeout=90, max_retries=3)
    sem = asyncio.Semaphore(6)

    async def judge(r):
        cited = [f"[{s['id']}] {s['title']} · {s['location']}" for s in r["sources"] if s["id"] in r["cited"]]
        user = f"Pertanyaan: {r['q']}\n\nKutipan yang dirujuk:\n" + "\n".join(cited) + f"\n\nJawaban:\n{r['answer']}"
        async with sem:
            res = await client.chat.completions.create(
                model="gpt-5.4-mini",
                messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                response_format={"type": "json_object"},
                reasoning_effort="low",
                max_completion_tokens=800,
            )
        return {**json.loads(res.choices[0].message.content), "q": r["q"]}

    results = {}
    for label in labels:
        rows = json.load(open(f"/eval/status_{label}.json", encoding="utf-8"))
        results[label] = await asyncio.gather(*(judge(r) for r in rows))
        res = results[label]
        print(f"\n== {label}: memakai peraturan dicabut {sum(x['memakai_dicabut'] for x in res)}/{len(res)}, "
              f"menyesatkan {sum(x['menyesatkan'] for x in res)}/{len(res)}")
        for i, x in enumerate(res, 1):
            if x["menyesatkan"]:
                print(f"  {i:>2}. MENYESATKAN: {x['q'][:70]} | {x['alasan'][:150]}")
    with open("/eval/status_judged.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)


asyncio.run(main())
