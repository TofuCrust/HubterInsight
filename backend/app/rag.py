"""Pencarian konteks dari korpus dokumen referensi (RAG).

Korpus (corpus/corpus.jsonl) dibangun oleh ingest/build_corpus.py. Pencarian memakai BM25
di memori, jadi berjalan tanpa biaya dan tanpa OpenAI. Embedding (OpenAI + pgvector) bisa
ditambahkan di belakang antarmuka `retrieve` yang sama bila kelak diperlukan.
"""

import json
import logging
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from .config import settings
from .doc_status import status_of
from .embeddings import corpus_hash, embed_query, load_vectors
from .schemas import Source

log = logging.getLogger("hubter")

TOP_K = 8  # sumber yang dikirim ke model; 8 dipilih karena kutipan yang tepat sering berperingkat 7-8 pada pertanyaan sehari-hari
MAX_PER_DOC = 3  # supaya satu dokumen besar tidak memenuhi seluruh hasil
FUSE_DEPTH = 50  # berapa teratas dari tiap peringkat yang digabung (hybrid)
RRF_K = 60  # konstanta Reciprocal Rank Fusion; makin besar, makin landai pengaruh peringkat atas
BM25_RRF_WEIGHT = 1.0
SEMANTIC_RRF_WEIGHT = 1.0
GROUP_MAX_CHARS = 5000  # batas teks satu sumber setelah potongan satu Pasal digabung
SNIPPET_CHARS = 600
K1, B = 1.4, 0.75

# Pembobotan menurut jenis sumber: regulasi diutamakan, analisis AI paling akhir.
KIND_WEIGHT = {
    "Regulasi": 1.0,
    "Data tarif": 1.0,
    "Hasil telaah": 0.75,
    "Publikasi": 0.75,
}
DEFAULT_KIND_WEIGHT = 0.6  # riwayat diskusi (analisis AI)
_STOPWORDS = frozenset(
    """yang dan di ke dari untuk atau dengan pada adalah dalam itu ini apa bagaimana siapa kapan
    mengapa kenapa apakah sebagai oleh akan dapat telah sudah juga serta bagi tersebut dimaksud
    sebagaimana jika bila maka karena agar saya anda kami kita ada tidak bukan para suatu setiap
    secara antara terhadap tentang menurut berapa mana sebutkan jelaskan uraikan tolong mohon
    kalo kalau gimana gak nggak ga dong sih deh""".split()
)

# Singkatan -> istilah yang dipakai dalam peraturan (hanya untuk memperluas pertanyaan).
_ALIASES = {
    "nppbkc": "nomor pokok pengusaha barang kena cukai",
    "dtfc": "direktorat teknis fasilitas cukai",
    "kppbc": "kantor pengawasan pelayanan bea cukai",
    "hje": "harga jual eceran",
}

# Kata dasar (hasil stem) yang dipakai penanya -> kata yang lazim dipakai peraturan.
_SYNONYMS = {
    "kriteria": "aspek dianggap",
    "syarat": "persyaratan",
    "sanksi": "denda pidana",
    "definisi": "dimaksud",
    "tagih": "kekurangan pembayaran tagihan",
}

_TOKEN = re.compile(r"[a-z0-9]+")
_HUBTER_SPACED = re.compile(r"\bhub[\s.-]+ter\b")
_PASAL_IN_QUERY = re.compile(r"\bpasal\s+(\d{1,3}[a-z]?)\b")
_PASAL_IN_LOCATION = re.compile(r"^Pasal (\d{1,3}[A-Z]?)\b")
PASAL_BOOST = 1.6
TITLE_WEIGHT = 0.35  # bobot kata di judul dokumen dibanding kata di isi
TOPIC_TITLE_WEIGHT = 0.5  # judul yang merangkum topik (telaah, diskusi, publikasi)
PEMBUKAAN_WEIGHT = 0.55  # konsiderans ("Menimbang/Mengingat") jarang memuat jawaban


# "PMK 78", "PER-16/BC/2022", dan daftar nomor sesudahnya: "PMK 78 dan 131", "PMK 78, 131".
_DOC_REF_IN_QUERY = re.compile(r"\b(pmk|per|se|ins|uu)[\s-]*(\d{1,3})\b((?:\s*(?:,|dan|sama|atau|dengan|vs)\s*\d{1,3}\b)*)")
_DOC_HEAD = re.compile(r"^(PMK|PER|SE|INS|UU)[\s-]*(\d{1,3})\b")
DOC_REF_BOOST = 1.5
REVOKED_WEIGHT = 0.6  # peraturan yang sudah dicabut turun peringkat, kecuali pertanyaan menyebut nomornya


def _doc_refs(query: str) -> set[str]:
    refs: set[str] = set()
    for kind, num, rest in _DOC_REF_IN_QUERY.findall(query.lower()):
        refs.add(f"{kind} {num}")
        refs.update(f"{kind} {n}" for n in re.findall(r"\d{1,3}", rest))
    return refs


def _doc_head(title: str) -> str | None:
    """Jenis dan nomor dari awal judul, mis. "PMK 131/PMK.011/2013 (...)" -> "pmk 131"."""
    m = _DOC_HEAD.match(title)
    return f"{m.group(1).lower()} {m.group(2)}" if m else None


def _pasal_of(location: str) -> str | None:
    m = _PASAL_IN_LOCATION.match(location)
    return m.group(1) if m else None


_SUFFIXES = ("kannya", "annya", "nya", "kan", "lah", "kah", "an")
_PREFIXES = ("memper", "diper", "meng", "meny", "peng", "peny", "mem", "men", "pem", "pen",
             "ber", "ter", "per", "me", "pe", "di", "ke", "se")
_VOWELS = "aiueo"


@lru_cache(maxsize=None)
def stem(word: str) -> str:
    """Pemotong imbuhan sederhana supaya "menagih", "penagihan", "tagihan", "ditagih" bertemu di satu
    bentuk dasar. Tidak sempurna, tetapi konsisten: dipakai sama untuk dokumen dan pertanyaan."""
    if len(word) < 5 or not word.isalpha():
        return word
    for suf in _SUFFIXES:
        if word.endswith(suf) and len(word) - len(suf) >= 4:
            word = word[: -len(suf)]
            break
    for _ in range(2):
        for pre in _PREFIXES:
            if word.startswith(pre) and len(word) - len(pre) >= 4:
                rest = word[len(pre):]
                if pre in ("men", "pen") and rest[0] in _VOWELS:  # menagih <- tagih (t luluh)
                    rest = "t" + rest
                word = rest
                break
        else:
            break
    return word


# Singkatan yang dipakai di dokumen dan oleh penanya -> istilah lengkapnya.
_ABBREV = {"hubter": ("hubungan", "keterkaitan")}


def tokenize(text: str) -> list[str]:
    tokens = []
    text = _HUBTER_SPACED.sub("hubter", text.lower())  # "hub ter", "Hub-Ter" -> "hubter"
    for raw in _TOKEN.findall(text):
        if raw in _STOPWORDS or (len(raw) <= 1 and not raw.isdigit()):
            continue
        if raw in _ABBREV:
            tokens += [stem(w) for w in _ABBREV[raw]]
        else:
            tokens.append(stem(raw))
    return tokens


EXPANSION_WEIGHT = 0.4  # kata tambahan dari singkatan/sinonim berbobot lebih kecil dari kata penanya


def query_terms(query: str) -> dict[str, float]:
    """Kata pertanyaan beserta bobotnya. Kata yang diucapkan penanya berbobot penuh (sedikit naik bila
    diulang); perluasan singkatan dan sinonim berbobot lebih kecil agar tidak
    menenggelamkan kata kunci asli."""
    weights = {t: 1 + 0.3 * math.log(n) for t, n in Counter(tokenize(query)).items()}
    for raw in _TOKEN.findall(query.lower()):
        extra = tokenize(_ALIASES.get(raw, "")) + tokenize(_SYNONYMS.get(stem(raw), ""))
        for t in extra:
            weights.setdefault(t, EXPANSION_WEIGHT)
    return weights


@dataclass(frozen=True)
class Chunk:
    id: int
    title: str
    kind: str
    location: str
    text: str


class Index:
    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self._titles = sorted({c.title for c in chunks})
        self._inactive: set[str] = set()  # judul yang dicabut atau belum berlaku; dihitung ulang tiap pencarian (peka tanggal)
        self.postings: dict[str, list[tuple[int, float]]] = defaultdict(list)
        self.lengths: list[int] = []
        for i, c in enumerate(chunks):
            # Isi + lokasi adalah bidang utama. Judul dokumen ikut diindeks (agar "pasal 5 PMK 78" cocok)
            # tetapi berbobot kecil, supaya sebutan nomor peraturan dalam pertanyaan tidak mengalahkan isi.
            body = Counter(tokenize(f"{c.location} {c.text}"))
            title = Counter(tokenize(c.title))
            self.lengths.append(sum(body.values()))
            # Judul peraturan hanya nama ("PMK 78/..."), sedangkan judul telaah dan diskusi merangkum topiknya.
            tw = TITLE_WEIGHT if c.kind in ("Regulasi", "Data tarif") else TOPIC_TITLE_WEIGHT
            for term in body.keys() | title.keys():
                self.postings[term].append((i, body.get(term, 0) + tw * title.get(term, 0)))
        n = max(len(chunks), 1)
        self.avg_len = (sum(self.lengths) / n) or 1.0
        self.idf = {t: math.log(1 + (n - len(p) + 0.5) / (len(p) + 0.5)) for t, p in self.postings.items()}

        # Satu Pasal yang panjang dipecah menjadi beberapa potongan berurutan. Kelompokkan agar jawaban
        # dapat memakai seluruh ayat Pasal itu, bukan hanya potongan yang kebetulan cocok.
        self.vectors: np.ndarray | None = None  # diisi bila pencarian hybrid aktif dan embedding tersedia
        self.group_id: list[int] = []
        self.group_bounds: list[tuple[int, int]] = []
        prev_key: tuple[str, str] | None = None
        for i, c in enumerate(chunks):
            label = c.location.split(" · ")[0]
            key = (c.title, label) if label.startswith(("Pasal ", "Penjelasan Pasal ")) else None
            if key is None or key != prev_key:
                self.group_bounds.append((i, i))
            else:
                self.group_bounds[-1] = (self.group_bounds[-1][0], i)
            self.group_id.append(len(self.group_bounds) - 1)
            prev_key = key

    def _expand(self, i: int) -> Chunk:
        """Potongan i beserta saudaranya dalam Pasal yang sama (dibatasi GROUP_MAX_CHARS)."""
        start, end = self.group_bounds[self.group_id[i]]
        if start == end:
            return self.chunks[i]
        lo = hi = i
        size = len(self.chunks[i].text)
        while True:  # lebarkan jendela dari potongan yang cocok ke kiri dan kanan
            grew = False
            for j, side in ((lo - 1, "lo"), (hi + 1, "hi")):
                if start <= j <= end and size + len(self.chunks[j].text) <= GROUP_MAX_CHARS:
                    size += len(self.chunks[j].text)
                    lo, hi = (j, hi) if side == "lo" else (lo, j)
                    grew = True
            if not grew:
                break
        first = self.chunks[lo]
        label = first.text.split("\n", 1)[0]
        parts = [first.text]
        for j in range(lo + 1, hi + 1):
            t = self.chunks[j].text
            parts.append(t.split("\n", 1)[1] if t.startswith(label + "\n") else t)  # buang label yang berulang
        return Chunk(first.id, first.title, first.kind, first.location, "\n".join(parts))

    def _bm25(self, query: str) -> dict[int, float]:
        scores: dict[int, float] = defaultdict(float)
        for term, weight in query_terms(query).items():
            idf = self.idf.get(term)
            if idf is None:
                continue
            for i, tf in self.postings[term]:
                norm = K1 * (1 - B + B * self.lengths[i] / self.avg_len)
                scores[i] += idf * tf * (K1 + 1) / (tf + norm) * weight
        return scores

    def _multiplier(self, i: int, wanted: set[str], refs: set[str]) -> float:
        """Bobot per jenis sumber, ditambah dorongan bila pertanyaan menyebut pasal atau dokumen tertentu."""
        c = self.chunks[i]
        named = bool(refs) and _doc_head(c.title) in refs
        return (
            (REVOKED_WEIGHT if c.title in self._inactive and not named and settings.doc_status else 1.0)
            * KIND_WEIGHT.get(c.kind, DEFAULT_KIND_WEIGHT)            * (PASAL_BOOST if wanted and _pasal_of(c.location) in wanted else 1.0)
            * (PEMBUKAAN_WEIGHT if c.location.startswith("Pembukaan") else 1.0)
            * (DOC_REF_BOOST if refs and _doc_head(c.title) in refs else 1.0)
        )

    def search(self, query: str, k: int = TOP_K, qvec: "np.ndarray | None" = None) -> list[Chunk]:
        self._inactive = {t for t in self._titles if status_of(t)[1]}
        # Pertanyaan yang menyebut "Pasal 3" diutamakan ke potongan Pasal 3 (bukan Penjelasannya).
        wanted = {m.upper() for m in _PASAL_IN_QUERY.findall(query.lower())}
        # Pertanyaan yang menyebut "PMK 131" atau "PER-16/BC/2022" diutamakan ke dokumen itu.
        refs = _doc_refs(query)
        bm25 = sorted(((s * self._multiplier(i, wanted, refs), i) for i, s in self._bm25(query).items()), reverse=True)
        ranked = [i for _, i in bm25]

        if qvec is not None and self.vectors is not None:
            # Gabungkan peringkat kata (BM25) dan peringkat makna (embedding) dengan Reciprocal Rank Fusion.
            sims = self.vectors @ qvec
            depth = min(FUSE_DEPTH, len(sims))
            top = np.argpartition(-sims, depth - 1)[:depth]
            semantic = sorted(
                ((float(sims[i]) * self._multiplier(int(i), wanted, refs), int(i)) for i in top if sims[i] >= settings.sim_floor),
                reverse=True,
            )
            fused: dict[int, float] = defaultdict(float)
            for r, i in enumerate(ranked[:FUSE_DEPTH]):
                fused[i] += BM25_RRF_WEIGHT / (RRF_K + r + 1)
            for r, (_, i) in enumerate(semantic):
                fused[i] += SEMANTIC_RRF_WEIGHT / (RRF_K + r + 1)
            ranked = sorted(fused, key=fused.__getitem__, reverse=True)

        picked: list[Chunk] = []
        per_doc: Counter[str] = Counter()
        seen_groups: set[int] = set()
        for i in ranked:
            g = self.group_id[i]
            c = self.chunks[i]
            if g in seen_groups or per_doc[c.title] >= MAX_PER_DOC:
                continue
            seen_groups.add(g)
            per_doc[c.title] += 1
            picked.append(self._expand(i))
            if len(picked) == k:
                break
        return picked


def _corpus_path() -> Path:
    if settings.corpus_path:
        return Path(settings.corpus_path)
    return Path(__file__).resolve().parent.parent / "corpus" / "corpus.jsonl"


@lru_cache(maxsize=1)
def get_index() -> Index | None:
    path = _corpus_path()
    if not path.exists():
        log.warning("Korpus tidak ditemukan di %s; memakai sumber contoh.", path)
        return None
    chunks = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            chunks.append(Chunk(r["id"], r["title"], r["kind"], r["location"], r["text"]))
    log.info("Korpus dimuat: %d potongan", len(chunks))
    index = Index(chunks)
    if settings.search_mode == "hybrid":
        index.vectors = load_vectors(Path(settings.embeddings_path), corpus_hash(path), len(chunks))
    return index


def _snippet(c: Chunk) -> str:
    text = c.text
    first, _, rest = text.partition("\n")
    if rest and len(first) < 80 and (first in c.location or c.location.startswith(first)):
        text = rest  # baris pertama hanya label (mis. "Pasal 5") yang sudah ada di lokasi
    text = re.sub(r"\s*\n\s*", " ", text).strip()
    if len(text) > SNIPPET_CHARS:
        text = text[:SNIPPET_CHARS].rsplit(" ", 1)[0] + "…"
    return text


_DEMO_SOURCES = [
    Source(
        id=1,
        title="Contoh Dokumen A (demo)",
        location="Pasal 1 ayat (1)",
        snippet="Korpus dokumen belum dimuat; ini hanya contoh kutipan untuk menguji tampilan sumber.",
    ),
]


async def retrieve(query: str) -> list[Source]:
    index = get_index()
    if index is None:
        if settings.llm_mode == "mock":
            return list(_DEMO_SOURCES)
        raise RuntimeError("Korpus dokumen belum tersedia.")
    qvec = await embed_query(query) if index.vectors is not None else None
    return [_to_source(n, c) for n, c in enumerate(index.search(query, qvec=qvec), 1)]


def _to_source(n: int, c: Chunk) -> Source:
    status, _ = status_of(c.title)
    status_line = f"Status: {status}\n" if status and settings.doc_status else ""
    return Source(
        id=n,
        title=c.title,
        location=c.location,
        snippet=_snippet(c),
        context=f"Jenis: {c.kind}\nDokumen: {c.title}\n{status_line}Bagian: {c.location}\n\n{c.text}",
    )


EXTRA_NEW_MAX = 4  # kutipan baru per pencarian tambahan oleh model


def search_more(query: str, known: dict[tuple[str, str], int], next_id: int) -> tuple[list[Source], list[int]]:
    """Pencarian tambahan oleh model (mode agentic). Mengembalikan kutipan baru dengan id lanjutan
    dan id kutipan yang sudah pernah dikirim ke model. `known` (judul, lokasi -> id) diperbarui."""
    index = get_index()
    if index is None:
        return [], []
    fresh: list[Source] = []
    repeated: list[int] = []
    for c in index.search(query, TOP_K):
        key = (c.title, c.location)
        if key in known:
            repeated.append(known[key])
        elif len(fresh) < EXTRA_NEW_MAX:
            known[key] = next_id + len(fresh)
            fresh.append(_to_source(known[key], c))
    return fresh, repeated
