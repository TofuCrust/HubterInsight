"""Membangun korpus pencarian dari folder "HubTer Insight Data".

Skrip ini dijalankan secara lokal (bukan di server). Hasilnya, backend/corpus/corpus.jsonl,
ikut masuk ke image backend dan dibaca oleh app/rag.py.

    python backend/ingest/build_corpus.py --data "HubTer Insight Data" --out backend/corpus/corpus.jsonl

Tahap:
  1. Ekstraksi teks per berkas (PDF, xlsx, docx, pptx, md/txt). PDF hasil pindai di-OCR
     (hasil OCR disimpan di backend/ingest/.ocr-cache supaya tidak diulang).
  2. Pemotongan (chunking): peraturan dipotong per Pasal; dokumen lain per paragraf/slide/judul.
  3. Tulis satu baris JSON per potongan.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
OCR_CACHE = HERE / ".ocr-cache"

MAX_CHARS = 1500  # ukuran target satu potongan
HARD_MAX = 2200  # satu Pasal lebih panjang dari ini dipecah
MIN_TEXT_PER_PAGE = 40  # di bawah ini halaman dianggap hasil pindai

# Jenis sumber. Dipakai untuk label di UI dan pembobotan saat pencarian.
K_REGULASI = "Regulasi"
K_TARIF = "Data tarif"
K_TELAAH = "Hasil telaah"
K_PUBLIKASI = "Publikasi"
K_DISKUSI = "Riwayat diskusi (analisis AI, bukan sumber hukum)"

# Judul yang dipakai sebagai kutipan. Kunci: nama berkas.
# Tanggal batas telaah tabel tarif (lihat catatan di lembar dasar); perbarui bila tabel diperbarui.
TELAAH_CUTOFF = "22-11-2026"

TITLES: dict[str, str] = {
    "109-PMK.010-2022Per.pdf": "PMK 109/PMK.010/2022 (perubahan PMK 192/PMK.010/2021)",
    "191-PMK.010-2022.pdf": "PMK 191/PMK.010/2022 (perubahan kedua PMK 192/PMK.010/2021)",
    "192-PMK.010-2021Per.pdf": "PMK 192/PMK.010/2021 tentang Tarif Cukai HT (sigaret, cerutu, rokok daun/klobot, tembakau iris)",
    "2023pmkeuangan068.pdf": "PMK 68 Tahun 2023 (perubahan PMK 66/PMK.04/2018 tentang NPPBKC)",
    "2024pmkeuangan097.pdf": "PMK 97 Tahun 2024 (perubahan ketiga PMK 192/PMK.010/2021)",
    "2024pmkeuangan124-1-.pdf": "PMK 124 Tahun 2024 tentang Organisasi dan Tata Kerja Kementerian Keuangan",
    "20260310124650_889000746_UU_Nomor_1_Tahun_2026_compressed.pdf": "UU 1 Tahun 2026 tentang Penyesuaian Pidana",
    "230926-170926-C6_1_1-PER-14-BC-2023.pdf": "PER-14/BC/2023 (petunjuk teknis pemberian, pembekuan, pencabutan NPPBKC)",
    "39TAHUN2007UU.pdf": "UU 39 Tahun 2007 (perubahan UU 11 Tahun 1995 tentang Cukai)",
    "66-PMK.04-2018Per.pdf": "PMK 66/PMK.04/2018 tentang Tata Cara Pemberian, Pembekuan, dan Pencabutan NPPBKC",
    "INS_07_bc_2013.pdf": "INS-07/BC/2013 (penelitian Kepala Kantor untuk mendapatkan indikasi hubungan keterkaitan)",
    "per-39-2012.pdf": "PER-39/BC/2012 tentang Penetapan Hubungan Istimewa Pengusaha Pabrik Hasil Tembakau",
    "PMK_200_2008.pdf": "PMK 200/PMK.04/2008 tentang Tata Cara Pemberian, Pembekuan, dan Pencabutan NPPBKC",
    "SE-07-2017.pdf": "SE-07/BC/2017 tentang Ketentuan Pengusaha Pabrik Hasil Tembakau yang Melakukan Kerja Sama dengan Pihak Lain",
    "SE-8bc_2013.pdf": "SE-8/BC/2013 tentang Petunjuk Pelaksanaan dan Pemesanan Pita Cukai terhadap Pengusaha Pabrik HT yang Memiliki Hubungan Keterkaitan",
    "INS_2_bc_2013.pdf":"INS-2/BC/2013 (penelitian Kepala Kantor atas indikasi hubungan keterkaitan)",
    "omk_191_2010.pdf": "PMK 191/PMK.04/2010 (perubahan PMK 200/PMK.04/2008 tentang NPPBKC)",
    "PER-10_BC_2023.pdf": "PER-10/BC/2023 tentang Tata Laksana Pemeriksaan Kepatuhan Pengusaha BKC",
    "PER-12_BC_2026.pdf": "PER-12/BC/2026 tentang Tata Laksana Pemeriksaan Kepatuhan Pengusaha BKC",
    "PER-16-BC-2025.pdf": "PER-16/BC/2025 (perubahan kedua PER-16/BC/2022)",
    "PER-16_BC_2022.pdf": "PER-16/BC/2022 tentang Tata Cara Penetapan Tarif Cukai HT (sigaret, cerutu, rokok daun/klobot, tembakau iris)",
    "PER-19-BC-2024-Perubahan-Tarif-SITUKLOTIS.pdf": "PER-19/BC/2024 (perubahan PER-16/BC/2022)",
    "PER-21_bc_2013.pdf": "PER-21/BC/2013 tentang Pemeriksaan terhadap Pengusaha Pabrik HT yang tidak menyampaikan data hubungan keterkaitan",
    "PER_227bc_2013.pdf": "PER-27/BC/2013 tentang Pemeriksaan terhadap Pengusaha Pabrik HT yang tidak menyampaikan data hubungan keterkaitan",
    "PMK_131_2013.pdf": "PMK 131/PMK.011/2013 (perubahan PMK 78/PMK.011/2013)",
    "PMK_78_2013.pdf": "PMK 78/PMK.011/2013 tentang Penetapan Golongan dan Tarif Cukai HT terhadap Pengusaha Pabrik HT yang Memiliki Hubungan Keterkaitan",
    "Salinan-UU-Nomor-7-Tahun-2021.pdf": "UU 7 Tahun 2021 tentang Harmonisasi Peraturan Perpajakan",
    "SDSN-2023-7.1_0.pdf": "Susunan Dalam Satu Naskah Undang-Undang Perpajakan (Edisi 2023)",
    "SE-23-BC-2015-Pengelolaan-Administrasi-HUTAN.pdf": "SE-23/BC/2014 tentang Pengelolaan Administrasi Penetapan Hubungan Keterkaitan",
    "uu11-1995.pdf": "UU 11 Tahun 1995 tentang Cukai",
    "Bahan analisis.pdf": "Bahan analisis: tidak diterbitkannya keputusan penetapan hubungan keterkaitan dalam perspektif tindak pidana korupsi",
    "Bahan Paparan PMK Hubungan Keterkaitan (Ka. PKPN)_edited.pdf": "Bahan paparan sosialisasi PMK 78/PMK.011/2013",
    "Materi Sosialisasi 21 Okt 2013.pdf": "Materi sosialisasi 21 Oktober 2013: sistematika penetapan hubungan keterkaitan",
    "Briefsheet paparan.pptx": "Briefsheet paparan hubungan keterkaitan",
    "Pertanggungjawaban DTFC.docx": "Pertanggungjawaban DTFC atas penelitian dan penetapan hubungan keterkaitan",
    "#-Telaah-Kebijakan-PMK-191-PMK.04-2010.txt": "Telaah kebijakan PMK 191/PMK.04/2010",
    "Tabel_Tarif_HJE_SKM_SPM_SKT_2010_2026.xlsx": "Tabel tarif dan HJE SKM, SPM, SKT 2010-2026",
}

# Berkas diskusi yang hanya membahas pengarsipan/rancangan platform, bukan substansi hukum.
SKIP_FILES = {
    "Pengarsipan proyek HubTer ke Google Drive.md",
    "Rancang Platform Telaah Hukum - cuplikan.md",
}


@dataclass
class Chunk:
    doc: str
    title: str
    kind: str
    location: str
    text: str
    page: int | None = None


@dataclass
class Stats:
    rows: list[tuple[str, int, int]] = field(default_factory=list)


# --------------------------------------------------------------------------- utilitas teks

_NOISE_LINE = re.compile(
    r"^(?:\d{1,4}|-\s*\d{1,4}\s*-|\+\d+|www\.[\w./-]+|jdih\.[\w./-]+|[\w-]+\.(?:go\.id|com|org)"
    r"|\W*MENTER\W{0,2}\s*KEUANGAN\s*REPUBLIK\s*INDONESIA\W*"  # kop halaman berulang
    r"|Worked for [\dms ]+)$",  # sisa antarmuka ChatGPT pada riwayat diskusi
    re.IGNORECASE,
)
_LIST_START = re.compile(r"^(?:\(\d+[a-z]?\)|\(?[a-z]\)|[a-z]\.|\d{1,2}\.|[-•▪])\s")
# Lapisan teks pada berkas pindai sering salah: "Pasal3" (tanpa spasi), "PasalI5" (I untuk 1).
_PASAL_RAW = re.compile(r"^Pasal\s*([0-9IlOo]{1,3}\s?[A-Z]?)$")


class _PasalMatch:
    """Pembungkus supaya `_PASAL.match(x).group(1)` selalu mengembalikan nomor yang sudah dinormalkan."""

    def __init__(self, num: str) -> None:
        self._num = num

    def group(self, _n: int = 1) -> str:
        return self._num


class _PasalPattern:
    def match(self, line: str) -> _PasalMatch | None:
        m = _PASAL_RAW.match(line)
        if not m:
            return None
        num = m.group(1)
        if not re.search(r"\d", num):  # "Pasal I", "Pasal Il": bukan nomor Pasal
            return None
        return _PasalMatch(num.translate(str.maketrans("IlOo", "1100")))


_PASAL = _PasalPattern()
_PENJELASAN = re.compile(r"^PENJELASAN\b")
_SENT_SPLIT = re.compile(r"(?<=[.;:!?])\s+(?=[A-Z0-9(])")


def reflow(raw: str) -> list[str]:
    """Gabungkan baris hasil ekstraksi menjadi paragraf; pertahankan awal butir/ayat/Pasal."""
    out: list[str] = []
    for line in raw.splitlines():
        line = re.sub(r"[ \t ]+", " ", line).strip()
        if not line or _NOISE_LINE.match(line):
            continue
        start_new = (
            not out
            or _LIST_START.match(line)
            or _PASAL.match(line)
            or re.match(r"^(BAB|Bagian|Paragraf|PENJELASAN|Menimbang|Mengingat|MEMUTUSKAN|Menetapkan)\b", line)
            or _PASAL.match(out[-1])
        )
        if start_new:
            out.append(line)
        elif out[-1].endswith("-") and line[:1].islower():
            out[-1] = out[-1][:-1] + line
        else:
            out[-1] += " " + line
    return out


def split_long(text: str, limit: int) -> list[str]:
    """Pecah teks panjang pada batas kalimat, tanpa memotong di tengah kalimat bila bisa."""
    if len(text) <= limit:
        return [text]
    pieces, cur = [], ""
    for sent in _SENT_SPLIT.split(text):
        while len(sent) > limit:  # kalimat tunggal yang sangat panjang (mis. tabel)
            cut = sent.rfind(" ", 0, limit)
            cut = cut if cut > limit // 2 else limit
            if cur:
                pieces.append(cur)
                cur = ""
            pieces.append(sent[:cut].strip())
            sent = sent[cut:].strip()
        if cur and len(cur) + len(sent) + 1 > limit:
            pieces.append(cur)
            cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        pieces.append(cur)
    return pieces


def pack(blocks: list[tuple[str, int | None]], limit: int = MAX_CHARS) -> list[tuple[str, int | None]]:
    """Gabungkan paragraf berurutan menjadi potongan <= limit. Mengembalikan (teks, halaman awal)."""
    out: list[tuple[str, int | None]] = []
    cur, cur_page = "", None
    for text, page in blocks:
        for piece in split_long(text, limit):
            if cur and len(cur) + len(piece) + 1 > limit:
                out.append((cur, cur_page))
                cur, cur_page = "", None
            if not cur:
                cur_page = page
            cur = f"{cur}\n{piece}" if cur else piece
    if cur:
        out.append((cur, cur_page))
    return out


# --------------------------------------------------------------------------- PDF + OCR


def _ocr_page(page, engine) -> str:
    import pymupdf

    pix = page.get_pixmap(matrix=pymupdf.Matrix(2.5, 2.5), alpha=False)
    result, _ = engine(pix.tobytes("png"))
    if not result:
        return ""
    items = []
    for box, text, _score in result:
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        items.append((min(ys), max(ys), min(xs), text))
    items.sort()
    heights = [b - a for a, b, _, _ in items] or [1]
    tol = statistics.median(heights) * 0.6
    lines: list[list[tuple[float, str]]] = []
    last_y = None
    for top, bottom, x, text in items:
        mid = (top + bottom) / 2
        if last_y is not None and abs(mid - last_y) <= tol:
            lines[-1].append((x, text))
        else:
            lines.append([(x, text)])
        last_y = mid
    return "\n".join(" ".join(t for _, t in sorted(ln)) for ln in lines)


# Berkas bertulisan lapisan teks yang bersih; dipakai sebagai kamus untuk memperbaiki spasi hasil OCR.
VOCAB_SOURCES = ["uu11-1995.pdf", "39TAHUN2007UU.pdf", "PER-16_BC_2022.pdf", "66-PMK.04-2018Per.pdf"]
_LETTERS = re.compile(r"[A-Za-z]{9,}")
_vocab_cache: dict[str, float] | None = None


def _vocab(folder: Path) -> dict[str, float]:
    """Biaya (-log frekuensi) tiap kata yang dikenal."""
    global _vocab_cache
    if _vocab_cache is None:
        import math

        import pymupdf

        counts: dict[str, int] = {}
        for name in VOCAB_SOURCES:
            p = folder / name
            if not p.exists():
                continue
            for page in pymupdf.open(p):
                for w in re.findall(r"[a-z]{2,}", page.get_text().lower()):
                    counts[w] = counts.get(w, 0) + 1
        total = sum(counts.values()) or 1
        _vocab_cache = {w: -math.log(c / total) for w, c in counts.items() if c >= 2}
    return _vocab_cache


def fix_spacing(text: str, folder: Path) -> str:
    """OCR sering menggabungkan kata ("tentangPenetapanGolongan"). Pisahkan kembali dengan
    segmentasi kata berbasis kamus (jalur biaya terendah) untuk deretan huruf yang tidak dikenal."""
    vocab = _vocab(folder)
    if not vocab:
        return text
    max_len = 24
    unknown = 14.0

    def split(run: str) -> str:
        low = run.lower()
        if low in vocab or len(run) > 80:
            return run
        n = len(low)
        best = [0.0] + [float("inf")] * n
        back = [0] * (n + 1)
        for i in range(1, n + 1):
            for j in range(max(0, i - max_len), i):
                w = low[j:i]
                cost = vocab.get(w, unknown + 3.0 * len(w) if len(w) > 1 else unknown * 2)
                if best[j] + cost < best[i]:
                    best[i], back[i] = best[j] + cost, j
        parts, i = [], n
        while i > 0:
            parts.append(run[back[i] : i])
            i = back[i]
        return " ".join(reversed(parts))

    return _LETTERS.sub(lambda m: split(m.group(0)), text)


def pdf_pages(path: Path) -> tuple[list[str], bool]:
    """Teks per halaman. Halaman tanpa teks di-OCR. Mengembalikan (halaman, ada_ocr)."""
    import pymupdf

    doc = pymupdf.open(path)
    pages = [p.get_text() for p in doc]
    needs_ocr = [i for i, t in enumerate(pages) if len(t.strip()) < MIN_TEXT_PER_PAGE]
    if len(needs_ocr) < max(1, len(pages) // 2) and len(pages) > 3:
        # Hanya sebagian kecil halaman kosong (mis. halaman gambar/tanda tangan): biarkan.
        return pages, False

    key = hashlib.sha1(f"{path.name}:{path.stat().st_size}".encode()).hexdigest()[:12]
    cache = OCR_CACHE / f"{key}.json"
    if cache.exists():
        raw = json.loads(cache.read_text(encoding="utf-8"))
        return [fix_spacing(t, path.parent) for t in raw], True

    from rapidocr_onnxruntime import RapidOCR

    engine = RapidOCR()
    print(f"  OCR {path.name} ({len(needs_ocr)} halaman)…", flush=True)
    for n, i in enumerate(needs_ocr, 1):
        pages[i] = _ocr_page(doc[i], engine)
        print(f"    {n}/{len(needs_ocr)}", end="\r", flush=True)
    OCR_CACHE.mkdir(exist_ok=True)
    cache.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
    return [fix_spacing(t, path.parent) for t in pages], True


def chunk_regulation(pages: list[str], doc: str, title: str, kind: str) -> list[Chunk]:
    """Potong per Pasal; bagian Penjelasan dilabeli terpisah. Tanpa Pasal -> potong per halaman."""
    paras: list[tuple[str, int]] = []
    for pno, text in enumerate(pages, 1):
        for p in reflow(text):
            paras.append((p, pno))

    if sum(1 for p, _ in paras if _PASAL.match(p)) < 3:
        return chunk_plain(paras, doc, title, kind)

    chunks: list[Chunk] = []
    label = "Pembukaan"
    penjelasan = False
    buf: list[tuple[str, int]] = []

    def flush() -> None:
        if not buf:
            return
        body = [(t, p) for t, p in buf if not _PASAL.match(t)]
        if not body:
            buf.clear()
            return
        first_page = buf[0][1]
        last_page = buf[-1][1]
        loc_page = f"hlm. {first_page}" if first_page == last_page else f"hlm. {first_page}-{last_page}"
        for text, page in pack([(t, p) for t, p in body], HARD_MAX if len(body) == 1 else MAX_CHARS):
            chunks.append(Chunk(doc, title, kind, f"{label} · {loc_page}", f"{label}\n{text}", page))
        buf.clear()

    for text, page in paras:
        if _PENJELASAN.match(text):
            flush()
            penjelasan = True
            label = "Penjelasan"
            buf.append((text, page))
            continue
        m = _PASAL.match(text)
        if m:
            flush()
            num = m.group(1).replace(" ", "")
            label = f"Penjelasan Pasal {num}" if penjelasan else f"Pasal {num}"
            buf.append((text, page))
            continue
        buf.append((text, page))
    flush()
    return chunks


def chunk_plain(paras: list[tuple[str, int]], doc: str, title: str, kind: str) -> list[Chunk]:
    return [
        Chunk(doc, title, kind, f"hlm. {page}", text, page)
        for text, page in pack([(t, p) for t, p in paras])
    ]


# --------------------------------------------------------------------------- format lain


def chunk_markdown(text: str, doc: str, title: str, kind: str) -> list[Chunk]:
    """Potong per judul (#..###); isi dikemas per paragraf."""
    chunks: list[Chunk] = []
    heading = "Pembukaan"
    section: list[tuple[str, int | None]] = []
    question = ""  # pertanyaan pengguna pada percakapan asli; dipasang di depan jawaban sesudahnya

    def flush() -> None:
        nonlocal question
        # Giliran "Pengguna" hanya pertanyaan, tanpa jawaban. Sebagai potongan sendiri ia pendek dan
        # mudah mengalahkan jawaban sebenarnya dalam pencarian, jadi tidak diindeks terpisah.
        if re.fullmatch(r"\d+\.\s*Pengguna", heading):
            question = re.sub(r"\s+", " ", " ".join(t for t, _ in section))[:300]
            section.clear()
            return
        # Judul bagian seperti "2. ChatGPT" tidak informatif sebagai kutipan: tambahkan awal isinya.
        generic = re.fullmatch(r"\d+\.\s*ChatGPT", heading) is not None
        for n, (body, _) in enumerate(pack(section), 1):
            text = f"{heading}\n{body}"
            if generic:
                first = re.sub(r"\s+", " ", body.split("\n", 1)[0])[:70].rstrip()
                label = f"{heading} · bagian {n}: {first}…"
                if n == 1 and question:
                    text = f"{heading}\nPertanyaan pengguna: {question}\n{body}"
            else:
                label = heading
            chunks.append(Chunk(doc, title, kind, label, text))
        if generic:
            question = ""
        section.clear()

    for line in text.splitlines():
        line = line.rstrip()
        if not line.strip() or _NOISE_LINE.match(line.strip()):
            continue
        m = re.match(r"^#{1,4}\s+(.*)$", line)
        if m:
            flush()
            heading = re.sub(r"[*_`]", "", m.group(1)).strip()[:120]
            continue
        if line.startswith("Sumber: http"):
            continue
        section.append((line.strip(), None))
    flush()
    return chunks


def chunk_docx(path: Path, doc: str, title: str, kind: str) -> list[Chunk]:
    import docx

    d = docx.Document(path)
    blocks: list[tuple[str, int | None]] = []
    for p in d.paragraphs:
        if p.text.strip():
            blocks.append((p.text.strip(), None))
    for t in d.tables:
        for row in t.rows:
            cells = []
            for c in row.cells:
                v = re.sub(r"\s+", " ", c.text).strip()
                if v and v not in cells:
                    cells.append(v)
            if cells:
                blocks.append((" | ".join(cells), None))
    return [Chunk(doc, title, kind, f"bagian {i}", t) for i, (t, _) in enumerate(pack(blocks), 1)]


def chunk_pptx(path: Path, doc: str, title: str, kind: str) -> list[Chunk]:
    from pptx import Presentation

    chunks: list[Chunk] = []
    prs = Presentation(path)
    for n, slide in enumerate(prs.slides, 1):
        parts: list[str] = []

        def walk(shapes) -> None:
            for sh in shapes:
                if sh.shape_type == 6:  # grup
                    walk(sh.shapes)
                elif sh.has_text_frame:
                    for para in sh.text_frame.paragraphs:
                        t = "".join(r.text for r in para.runs).strip()
                        if t:
                            parts.append(t)
                elif getattr(sh, "has_table", False) and sh.has_table:
                    for row in sh.table.rows:
                        cells = [re.sub(r"\s+", " ", c.text).strip() for c in row.cells]
                        cells = [c for c in cells if c]
                        if cells:
                            parts.append(" | ".join(cells))

        walk(slide.shapes)
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
            note = slide.notes_slide.notes_text_frame.text.strip()
            if note:
                parts.append(f"Catatan: {note}")
        text = "\n".join(parts)
        if len(text) < 30:
            continue
        for body, _ in pack([(p, n) for p in parts]):
            chunks.append(Chunk(doc, title, kind, f"slide {n}", body, n))
    return chunks


def chunk_tariff_xlsx(path: Path, doc: str, title: str, kind: str) -> list[Chunk]:
    """Satu potongan per periode (R01..Rnn): rujukan hukum + seluruh lapisan tarif periode itu."""
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True)
    tarif, dasar = wb.worksheets[0], wb.worksheets[1]

    legal: dict[str, list[str]] = {}
    legal_head: dict[str, str] = {}
    code = None
    for a, b in dasar.iter_rows(values_only=True):
        if a and re.fullmatch(r"R\d+", str(a)):
            code = str(a)
            legal_head[code] = str(b)
            legal[code] = []
        elif code and b:
            legal[code].append(str(b))

    rows: dict[str, list[str]] = {}
    years: dict[str, set[int]] = {}
    for r in tarif.iter_rows(min_row=8, values_only=True):
        if not r[0] or not r[7]:
            continue
        jenis, batas, rate, hje, _year, start, end, ref = r[:8]
        code = str(ref).split("·")[0].strip()
        f = lambda d: d.strftime("%d-%m-%Y") if hasattr(d, "strftime") else str(d)
        years.setdefault(code, set()).update({start.year, end.year} if hasattr(start, "year") else set())
        # Tulis dalam kata biasa ("SKM golongan I") supaya cocok dengan cara orang bertanya.
        # Tanggal akhir pada baris terbaru adalah batas telaah dokumen, bukan berakhirnya peraturan (catatan di
        # lembar dasar). Ditandai di tiap baris supaya pembaca tidak mengira tarifnya berhenti di tanggal itu.
        if f(end) == TELAAH_CUTOFF:
            period = f"berlaku sejak {f(start)} (data ditelaah sampai {f(end)}; belum ada keterangan berakhir)"
        else:
            period = f"berlaku {f(start)} s.d. {f(end)}"
        rows.setdefault(code, []).append(
            f"{str(jenis).replace(' · ', ' golongan ')}: produksi {batas}; {hje}; "
            f"tarif Rp{rate} per batang; {period}"
        )

    chunks = []
    for code in sorted(rows):
        yrs = sorted(years.get(code, ()))
        header = f"Tarif cukai SKM, SPM, SKT tahun {' dan '.join(map(str, yrs))}. Periode {legal_head.get(code, code)}"
        notes = [n for n in legal.get(code, []) if not n.startswith("http")]
        body = [header, *notes, "Tarif cukai per batang menurut golongan:", *rows[code]]
        for i, (text, _) in enumerate(pack([(ln, None) for ln in body]), 1):
            suffix = f" ({i})" if i > 1 else ""
            chunks.append(Chunk(doc, title, kind, f"{code} · {legal_head.get(code, '')}{suffix}", text))
    return chunks


# --------------------------------------------------------------------------- orkestrasi

FOLDER_KIND = {
    "01_Regulasi": K_REGULASI,
    "02_Dokumen Pendukung": K_TARIF,
    "03_Riwayat_Diskusi": K_DISKUSI,
    "04_Hasil Telaah": K_TELAAH,
    "06_Publikasi": K_PUBLIKASI,
}


def build(data_dir: Path) -> tuple[list[Chunk], Stats]:
    chunks: list[Chunk] = []
    stats = Stats()
    for folder, kind in FOLDER_KIND.items():
        for path in sorted((data_dir / folder).glob("*")):
            if not path.is_file() or path.name in SKIP_FILES:
                continue
            ext = path.suffix.lower()
            if folder == "03_Riwayat_Diskusi" and ext != ".md":
                continue  # berkas tanpa ekstensi hanya pembungkus tautan berbagi
            doc = path.stem
            title = TITLES.get(path.name) or (path.stem if folder != "03_Riwayat_Diskusi" else f"Diskusi: {path.stem}")
            print(f"- {folder}/{path.name}", flush=True)

            if ext == ".pdf":
                pages, _ = pdf_pages(path)
                if kind == K_REGULASI:
                    out = chunk_regulation(pages, doc, title, kind)
                else:
                    paras = [(p, n) for n, t in enumerate(pages, 1) for p in reflow(t)]
                    out = chunk_plain(paras, doc, title, kind)
            elif ext == ".xlsx":
                out = chunk_tariff_xlsx(path, doc, title, kind)
            elif ext == ".docx":
                out = chunk_docx(path, doc, title, kind)
            elif ext == ".pptx":
                out = chunk_pptx(path, doc, title, kind)
            elif ext in {".md", ".txt"}:
                out = chunk_markdown(path.read_text(encoding="utf-8"), doc, title, kind)
            else:
                continue
            chunks.extend(out)
            stats.rows.append((path.name, len(out), sum(len(c.text) for c in out)))
    return chunks, stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    chunks, stats = build(args.data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as f:
        for i, c in enumerate(chunks, 1):
            row = {"id": i, "doc": c.doc, "title": c.title, "kind": c.kind, "location": c.location, "text": c.text}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("\nRingkasan")
    for name, n, chars in stats.rows:
        print(f"  {name[:60]:<60} {n:>5} potongan {chars:>9,} karakter")
    print(f"Total: {len(chunks)} potongan, {sum(len(c.text) for c in chunks):,} karakter -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
