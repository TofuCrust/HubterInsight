"""Status berlaku, dicabut, atau belum berlakunya peraturan di korpus, dibaca model lewat baris "Status:" pada tiap
kutipan dan lewat peringatan tepat sebelum pertanyaan.

Sumber: ketentuan penutup yang tertulis di peraturan dalam korpus, DIVALIDASI AHLI pada 25 November 2026
(dokumen docs/validasi-status-regulasi-2026-11-25.md; tiap entri menyebut pasal dan tanggalnya). Daftar ini tidak
menelusuri peraturan di luar yang divalidasi: "BERLAKU" berarti "belum ditemukan pencabutan", bukan jaminan status
hukum terkini. Tinjau dan perbarui bila korpus bertambah atau peraturan baru terbit.

Jenis status: None (berlaku atau tanpa keterangan), "revoked" (sudah dicabut atau tidak berlaku), "pending"
(sudah ditetapkan tetapi belum mulai berlaku). Status "revoked" dan "pending" sama-sama diturunkan peringkatnya di
pencarian dan diberi peringatan, karena bukan ketentuan yang berlaku sekarang. Beberapa entri bergantung tanggal
(PER-10 dan PER-12/BC/2026) dan berganti sendiri pada 1 Januari 2027.
"""

from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone

REVOKED = "revoked"
PENDING = "pending"

_WIB = timezone(timedelta(hours=7))
PER12_EFFECTIVE = date(2027, 1, 1)  # PER-12/BC/2026 ditetapkan 25 September 2026, berlaku 1 Januari 2027 (Pasal 13)

_NPPBKC_NEW = "PMK 66/PMK.04/2018 sebagaimana diubah dengan PMK 68 Tahun 2023"
_SE_NPPBKC = "(dicabut), jadi untuk perizinan sekarang baca PMK 66/PMK.04/2018 jo. PMK 68/2023 dan PER-14/BC/2023"


def _per10(today: date) -> tuple[str, str | None]:
    if today < PER12_EFFECTIVE:
        return (
            "MASIH BERLAKU sampai 31 Desember 2026. Akan dicabut oleh PER-12/BC/2026 (Pasal 12 huruf a) mulai 1 Januari "
            "2027 (Pasal 13); PER-12 sudah ditetapkan 25 September 2026 tetapi belum berlaku.",
            None,
        )
    return "DICABUT sejak 1 Januari 2027 oleh PER-12/BC/2026 (Pasal 12 huruf a). Ketentuan yang berlaku: PER-12/BC/2026.", REVOKED


def _per12(today: date) -> tuple[str, str | None]:
    if today < PER12_EFFECTIVE:
        return (
            "DITETAPKAN 25 September 2026 tetapi BELUM BERLAKU: mulai berlaku 1 Januari 2027 (Pasal 13). Pada tanggal itu "
            "mencabut PER-10/BC/2023 dan SE-08/BC/2025 (Pasal 12). Sampai 31 Desember 2026 yang berlaku adalah PER-10/BC/2023.",
            PENDING,
        )
    return "BERLAKU sejak 1 Januari 2027 (mencabut PER-10/BC/2023 dan SE-08/BC/2025); belum ditemukan pencabutan.", None


# Entri: (awalan judul di korpus, teks status atau fungsi(tanggal) -> (teks, jenis), jenis untuk teks statis).
# Awalan dicocokkan dari yang paling panjang.
_Entry = tuple[str, "str | Callable[[date], tuple[str, str | None]]", "str | None"]

STATUS: list[_Entry] = [
    # NPPBKC
    ("PMK 200/PMK.04/2008",
     f"DICABUT sejak 5 Juli 2018 oleh PMK 66/PMK.04/2018 (Pasal 75 angka 1; berlaku saat diundangkan, Pasal 76). "
     f"Ketentuan yang berlaku: {_NPPBKC_NEW}.", REVOKED),
    ("PMK 191/PMK.04/2010",
     "TIDAK BERLAKU sebagai dasar HubTer sejak 10 Juni 2013: satu-satunya pasal substantif yang disisipkannya ke "
     "PMK 200/2008 (Pasal 21A) dicabut oleh PMK 78/PMK.011/2013 (Pasal 15 jo. Pasal 16). PMK induknya (PMK 200/2008) "
     "dicabut sejak 5 Juli 2018. Label \"dicabut\" pada riwayat JDIH dibaca menurut objek yang disebut Pasal 15. "
     f"Ketentuan yang berlaku: {_NPPBKC_NEW}.", REVOKED),
    ("PMK 66/PMK.04/2018",
     "BERLAKU sebagaimana diubah dengan PMK 68 Tahun 2023 (perubahan berlaku 1 Agustus 2023). Menggantikan "
     "PMK 200/PMK.04/2008 (dicabut sejak 5 Juli 2018).", None),
    ("PMK 68 Tahun 2023", "BERLAKU sejak 1 Agustus 2023. Mengubah PMK 66/PMK.04/2018; baca bersama PMK 66/PMK.04/2018.", None),
    ("PER-14/BC/2023",
     "BERLAKU sejak 1 Agustus 2023 (petunjuk teknis NPPBKC); belum ditemukan perubahan atau pengganti.", None),
    # Hubungan istimewa dan keterkaitan
    ("PER-39/BC/2012",
     "DICABUT sejak 10 Juni 2013 oleh PER-21/BC/2013 (Pasal 5), yang kemudian dicabut sejak 1 Oktober 2013 oleh "
     "PER-27/BC/2013 (Pasal 5).", REVOKED),
    ("PER-21/BC/2013",
     "DICABUT sejak 1 Oktober 2013 oleh PER-27/BC/2013 (Pasal 5; berlaku 1 Oktober 2013 meski ditandatangani "
     "8 Oktober 2013). Ketentuan yang berlaku: PER-27/BC/2013.", REVOKED),
    ("PER-27/BC/2013",
     "BERLAKU (mencabut PER-21/BC/2013); belum ditemukan pencabutan. Tenggat pernyataan 16 Oktober 2013 (Pasal 2 "
     "ayat (1)) bersifat historis, bukan kewajiban berkala; pemeriksaan menurut Pasal 2 ayat (4) terkait pernyataan itu.", None),
    ("PMK 78/PMK.011/2013",
     "BERLAKU sebagaimana diubah dengan PMK 131/PMK.011/2013 (efektif 1 Oktober 2013); belum ditemukan pencabutan. "
     "Dasar langsung penetapan golongan dan tarif karena HubTer, berdasarkan delegasi Pasal 5 ayat (5) UU Cukai.", None),
    ("PMK 131/PMK.011/2013",
     "BERLAKU sejak 1 Oktober 2013. Mengubah PMK 78/PMK.011/2013; baca bersama PMK 78/PMK.011/2013.", None),
    ("INS-2/BC/2013",
     "DICABUT sejak 1 Oktober 2013 oleh INS-07/BC/2013 (Diktum KEENAM). Ketentuan yang berlaku: INS-07/BC/2013.", REVOKED),
    ("INS-07/BC/2013",
     "BERLAKU sejak 1 Oktober 2013 (ditandatangani 8 Oktober 2013); mencabut INS-2/BC/2013 (Diktum KEENAM).", None),
    # Surat edaran
    ("SE-8/BC/2013",
     "Belum ditemukan pencabutan eksplisit. Dasar HubTer yang dirujuk adalah PMK 78/PMK.011/2013 (dasar hukum bagian D "
     "tidak memuat PMK 200/2008). Untuk penetapan tarif dan layanan pita cukai saat ini, baca petunjuk 2013 bersama "
     "ketentuan teknis yang berlaku.", None),
    ("SE-23/BC/2014",
     "Belum ditemukan pencabutan eksplisit. Dasar hukum bagian D merujuk PMK 200/PMK.04/2008 (dicabut) dan PMK 78/2013 "
     "jo. PMK 131/2013: bedakan administrasi penetapan HubTer dari prosedur wawancara NPPBKC yang merujuk aturan lama; "
     "untuk perizinan baca PMK 66/PMK.04/2018 jo. PMK 68/2023.", None),
    ("SE-07/BC/2017",
     "Belum ditemukan pencabutan eksplisit. Mengatur kerja sama pabrik dengan pihak lain; bagian perizinan merujuk "
     f"PMK 200/PMK.04/2008 {_SE_NPPBKC}. Adanya kerja sama saja tidak menetapkan HubTer.", None),
    # Tarif cukai hasil tembakau
    ("PMK 192/PMK.010/2021",
     "BERLAKU (mencabut PMK 198/PMK.010/2020; berlaku 20 Desember 2021 menurut Pasal 20-21; batasan produksi, HJE, dan "
     "tarif mulai diterapkan 1 Januari 2022 menurut Pasal 19), sebagaimana diubah dengan PMK 109/PMK.010/2022, "
     "PMK 191/PMK.010/2022, dan PMK 97 Tahun 2024. Tarif dan batasan HJE periode sebelumnya diganti lampiran perubahan "
     "berikutnya; periksa periode berlaku.", None),
    ("PMK 109/PMK.010/2022", "BERLAKU. Perubahan pertama atas PMK 192/PMK.010/2021; periksa periode berlaku tarifnya.", None),
    ("PMK 191/PMK.010/2022", "BERLAKU. Perubahan kedua atas PMK 192/PMK.010/2021; periksa periode berlaku tarifnya.", None),
    ("PMK 97 Tahun 2024",
     "BERLAKU. Perubahan ketiga atas PMK 192/PMK.010/2021; lampiran tarif dan HJE berlaku sejak 1 Januari 2025 (Pasal II "
     "angka 2). Belum ditemukan PMK tarif yang lebih baru untuk SKM, SPM, dan SKT; baris 2026 tetap berdasar PMK "
     "192/2021 sebagaimana terakhir diubah dengan PMK 97/2024.", None),
    ("PER-16/BC/2022",
     "BERLAKU (mencabut PER-16/BC/2021 efektif 16 Desember 2022, Pasal 26-27), sebagaimana diubah dengan PER-19/BC/2024 "
     "dan PER-16/BC/2025 (perubahan kedua).", None),
    ("PER-19/BC/2024", "BERLAKU. Perubahan atas PER-16/BC/2022; baca bersama PER-16/BC/2022 dan PER-16/BC/2025.", None),
    ("PER-16/BC/2025", "BERLAKU. Perubahan kedua atas PER-16/BC/2022; perubahan terakhir yang ada di dokumen referensi.", None),
    # Pemeriksaan kepatuhan (bergantung tanggal)
    ("PER-10/BC/2023", _per10, None),
    ("PER-12/BC/2026", _per12, None),
    # Undang-undang dan organisasi
    ("UU 11 Tahun 1995",
     "BERLAKU sebagaimana diubah dengan UU 39 Tahun 2007 dan UU 7 Tahun 2021 (Pasal 14), dengan penyesuaian ketentuan "
     "pidana berdasarkan UU 1 Tahun 2026 sejak 2 Januari 2026. Pasal 51 sudah dihapus oleh UU 39/2007 (Pasal I angka 48).", None),
    ("UU 39 Tahun 2007",
     "BERLAKU. Perubahan atas UU 11 Tahun 1995; baca bersama UU 11/1995, UU 7/2021, dan penyesuaian pidana UU 1/2026.", None),
    ("UU 7 Tahun 2021", "BERLAKU. Pasal 14 mengubah UU 11 Tahun 1995 tentang Cukai.", None),
    ("UU 1 Tahun 2026",
     "BERLAKU sejak 2 Januari 2026 (Pasal IX). Menyesuaikan ancaman pidana cukai: Lampiran I nomor 53 mencantumkan "
     "Pasal 50, 52, 53, 55, 56, 57, 58, dan 58A ayat (1)-(2) UU 11/1995; ketentuan pidana di luar lampiran (mis. "
     "Pasal 54) dibaca dengan Pasal I-III dan kaidah Pasal VIII (termasuk penghapusan ancaman minimum khusus). Catatan: "
     "Lampiran I nomor 8 mencantumkan Pasal 51 dan Pasal 59 ayat (2), padahal Pasal 51 sudah dihapus UU 39/2007; "
     "pencantuman itu saja tidak membuktikan delik Pasal 51 berlaku kembali.", None),
    ("PMK 124 Tahun 2024",
     "BERLAKU sebagaimana diubah dengan PMK 117 Tahun 2025 (efektif 31 Desember 2025; perubahannya khusus penataan "
     "jabatan di lingkungan DJP).", None),
]

_SORTED = sorted(STATUS, key=lambda e: -len(e[0]))


def _today() -> date:
    return datetime.now(_WIB).date()


def status_info(title: str, today: date | None = None) -> tuple[str | None, str | None]:
    """(teks status, jenis) untuk judul dokumen di korpus; (None, None) bila tidak ada keterangan.
    Jenis: None (berlaku), "revoked", atau "pending" (belum mulai berlaku)."""
    for prefix, text, kind in _SORTED:
        if title.startswith(prefix):
            if callable(text):
                return text(today or _today())
            return text, kind
    return None, None


def status_of(title: str) -> tuple[str | None, bool]:
    """Kompatibilitas: (teks status, bukan ketentuan yang berlaku sekarang?). True untuk dicabut maupun belum berlaku."""
    text, kind = status_info(title)
    return text, kind is not None


def as_prompt_table() -> str:
    """Seluruh peta status untuk hari ini sebagai teks (dipakai penilai uji)."""
    lines = []
    for prefix, _text, _kind in STATUS:
        text, _ = status_info(prefix)
        lines.append(f"- {prefix}: {text}")
    return "\n".join(lines)
