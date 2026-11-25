"""Mode agentic: kutipan awal tetap dicari otomatis (BM25), tetapi model boleh memanggil alat `cari_dokumen`
untuk mencari lagi dengan kata kunci lain bila kutipan awal kurang. Putaran pencarian tidak di-streaming;
hanya jawaban akhir yang dialirkan.

Menghasilkan peristiwa (jenis, nilai): ("status", teks), ("sources", daftar Source lengkap sejauh ini), ("token", teks).
"""

import json
import logging
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Any

from .config import settings
from .providers import SYSTEM_PROMPT, build_messages
from .rag import get_index, search_more
from .schemas import Message, Source

log = logging.getLogger("hubter")

AGENT_PROMPT = """Alat pencarian
18. Kutipan awal dicarikan otomatis dari pertanyaan apa adanya, dan sering meleset bila pertanyaan memakai bahasa santai, istilah tidak baku, atau memuat beberapa hal sekaligus. Sebelum menjawab, periksa apakah kutipan awal benar-benar memuat jawaban atas pertanyaan, bukan sekadar membahas topik yang sama. Bila jawaban langsungnya tidak ada atau hanya sebagian, panggil alat `cari_dokumen` sebelum menyatakan bahwa informasinya belum ada. Pertanyaan bertingkat (alur, perbandingan, beberapa syarat) boleh dipecah menjadi beberapa pencarian sekaligus.
19. Tulis kata kunci dengan istilah dalam bahasa peraturan ("berwenang menetapkan hubungan keterkaitan", bukan "nentuin hubter") dan arahkan ke dokumen yang tepat memakai Peta dokumen di bawah. Peraturan perubahan memuat ketentuan terbaru: bila pertanyaan menyangkut sebuah peraturan induk, cari juga peraturan perubahannya. JANGAN menebak nomor pasal atau nomor peraturan yang tidak ada di pertanyaan, di kutipan, atau di Peta dokumen; tebakan yang salah menyesatkan pencarian.
20. Jangan mencari bila kutipan awal sudah cukup menjawab, dan jangan mencari untuk pertanyaan di luar topik. Jangan menulis teks apa pun sebelum memanggil alat. Setelah hasil pencarian diterima, bila masih kurang, Anda boleh mencari sekali lagi dengan kata kunci berbeda; jangan mengulang kata kunci yang sama.
21. Kutipan dari pencarian tambahan memakai id lanjutan (misalnya 9, 10). Rujukan [n] dan semua aturan di atas berlaku sama untuk kutipan awal maupun tambahan.

Peta dokumen (seluruh isi yang bisa dicari):
{catalog}"""


@lru_cache(maxsize=1)
def agent_instructions() -> str:
    """Prompt sistem mode agentic: prompt biasa, aturan alat, dan daftar dokumen yang ada di korpus."""
    index = get_index()
    by_kind: dict[str, list[str]] = {}
    if index is not None:
        for c in index.chunks:
            titles = by_kind.setdefault(c.kind, [])
            if c.title not in titles:
                titles.append(c.title)
    catalog = "\n".join(f"- {kind}: " + "; ".join(titles) for kind, titles in by_kind.items())
    return SYSTEM_PROMPT + "\n\n" + AGENT_PROMPT.format(catalog=catalog)


TOOL = {
    "type": "function",
    "name": "cari_dokumen",
    "description": (
        "Mencari bagian dokumen referensi (peraturan, tabel tarif, telaah, riwayat diskusi) dengan kata kunci. "
        "Mengembalikan kutipan baru yang belum ada di kutipan sebelumnya."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "kata_kunci": {
                "type": "string",
                "description": "Kata kunci atau frasa dalam bahasa peraturan; boleh memuat nomor peraturan dan pasal.",
            }
        },
        "required": ["kata_kunci"],
        "additionalProperties": False,
    },
    "strict": False,
}


def _run_search(query: str, known: dict, all_sources: list[Source]) -> tuple[str, bool]:
    fresh, repeated = search_more(query, known, len(all_sources) + 1)
    all_sources.extend(fresh)
    if not fresh:
        ids = ", ".join(f"[{i}]" for i in sorted(set(repeated))) or "-"
        return f"Tidak ada kutipan baru untuk \"{query}\". Hasilnya sudah tercakup di kutipan: {ids}.", False
    blocks = "\n".join(f'<kutipan id="{s.id}">\n{s.context or s.snippet}\n</kutipan>' for s in fresh)
    text = f"Kutipan baru untuk \"{query}\":\n{blocks}"
    if repeated:
        text += "\n\nHasil lain sudah ada di kutipan: " + ", ".join(f"[{i}]" for i in sorted(set(repeated))) + "."
    return text, True


async def run_agent(
    client: Any,
    messages: list[Message],
    sources: list[Source],
    usage: dict,
    searches: list[str],
) -> AsyncIterator[tuple[str, Any]]:
    """`searches` diisi kata kunci yang dicari model (untuk log). `usage` diisi total token semua putaran.

    Memakai Responses API karena gpt-5.4-mini tidak mendukung alat fungsi bersama reasoning_effort di Chat
    Completions. store=False: percakapan tidak disimpan di sisi OpenAI; bagian "reasoning" dikirim balik terenkripsi."""
    all_sources = list(sources)
    known = {(s.title, s.location): s.id for s in sources}
    built = build_messages(messages, sources)
    items: list[dict[str, Any]] = built[1:]
    instructions = agent_instructions()
    if settings.agentic_force_search:
        instructions += (
            "\n\nLangkah pertama Anda WAJIB memanggil cari_dokumen satu kali dengan kata kunci baku bahasa peraturan "
            "yang melengkapi kutipan awal (hasilnya belum tentu kutipan awal sudah benar)."
        )
    searches_left = settings.agentic_max_searches

    for round_no in range(settings.agentic_max_rounds):
        final = round_no == settings.agentic_max_rounds - 1 or searches_left <= 0
        stream = await client.responses.create(
            model=settings.openai_model,
            instructions=instructions,
            input=items,
            tools=[TOOL],
            tool_choice="none" if final else ("required" if round_no == 0 and settings.agentic_force_search else "auto"),
            reasoning={"effort": settings.openai_reasoning_effort},
            max_output_tokens=settings.openai_max_output_tokens,
            include=["reasoning.encrypted_content"],
            store=False,
            stream=True,
        )
        output: list[Any] = []
        async for ev in stream:
            kind = ev.type
            if kind == "response.output_text.delta":
                yield "token", ev.delta
            elif kind in ("response.completed", "response.incomplete"):
                resp = ev.response
                output = list(resp.output or [])
                if resp.usage:
                    usage["input_tokens"] = usage.get("input_tokens", 0) + resp.usage.input_tokens
                    usage["output_tokens"] = usage.get("output_tokens", 0) + resp.usage.output_tokens
                if kind == "response.incomplete":
                    yield "token", "\n\n*Jawaban terpotong karena terlalu panjang. Coba pertanyaan yang lebih spesifik.*"
            elif kind == "response.failed":
                raise RuntimeError(f"Responses API gagal: {getattr(ev.response, 'error', None)}")

        calls = [it for it in output if it.type == "function_call"]
        if not calls:
            return  # jawaban akhir sudah dialirkan

        items += [it.model_dump(exclude_none=True) for it in output]
        grew = False
        for c in calls:
            if c.name != "cari_dokumen":
                result = "Alat tidak dikenal."
            elif searches_left <= 0:
                result = "Batas pencarian tercapai. Jawab dari kutipan yang ada."
            else:
                try:
                    query = str(json.loads(c.arguments or "{}").get("kata_kunci", "")).strip()[:300]
                except (ValueError, AttributeError):
                    query = ""
                if not query:
                    result = "Kata kunci kosong."
                else:
                    searches_left -= 1
                    searches.append(query)
                    yield "status", f"Mencari: {query}"
                    result, added = _run_search(query, known, all_sources)
                    grew = grew or added
            items.append({"type": "function_call_output", "call_id": c.call_id, "output": result})
        if grew:
            yield "sources", list(all_sources)
