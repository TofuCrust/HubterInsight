"""Unggah, daftar, dan unduh dokumen oleh pemakai yang sudah masuk (halaman Dokumen).

Berkas hanya disimpan di folder unggahan di VPS untuk dikurasi nanti (ditambahkan ke korpus lewat ingest); tidak
otomatis dibaca model dan tidak ditampilkan di browser: unduhan selalu sebagai lampiran. Pertahanan: hanya tipe yang
diizinkan, isi berkas dicocokkan dengan tipenya, nama berkas dibersihkan, ukuran dan total folder dibatasi.
"""

import codecs
import logging
import os
import re
import unicodedata
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from . import auth
from .config import settings
from .ratelimit import RateLimiter

log = logging.getLogger("hubter")

router = APIRouter(prefix="/api/files", dependencies=[Depends(auth.require_auth)])
upload_limiter = RateLimiter(per_minute=10, per_day=200, daily_cap=0)

ALLOWED = {"md", "pdf", "xlsx", "pptx", "docx", "png", "jpg", "jpeg"}
# Berkas Office adalah ZIP; anggota wajibnya membedakan docx/xlsx/pptx dari ZIP sembarang.
OFFICE_MEMBER = {"docx": "word/document.xml", "xlsx": "xl/workbook.xml", "pptx": "ppt/presentation.xml"}
CHUNK = 64 * 1024
MAX_LISTED = 2000


def _dir() -> Path:
    path = Path(settings.upload_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def clean_name(raw: str) -> str:
    """Nama aman dan jujur: tanpa folder, tanpa karakter aneh, ekstensi huruf kecil."""
    name = unicodedata.normalize("NFC", unquote(raw)).replace("\\", "/").split("/")[-1].strip()
    stem, dot, ext = name.rpartition(".")
    ext = ext.lower()
    if not dot or ext not in ALLOWED:
        raise HTTPException(415, "Jenis berkas tidak diizinkan. Boleh: .md .pdf .xlsx .pptx .docx .png .jpg .jpeg")
    stem = re.sub(r"[^\w\-. ()\[\]&,+]", "_", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" ._")[:120] or "berkas"
    return f"{stem}.{ext}"


def _unique(folder: Path, name: str) -> Path:
    stem, _, ext = name.rpartition(".")
    path = folder / name
    n = 2
    while path.exists():
        path = folder / f"{stem}-{n}.{ext}"
        n += 1
    return path


def _content_ok(path: Path, ext: str) -> bool:
    """Isi berkas harus sesuai ekstensinya (bukan sekadar nama)."""
    with path.open("rb") as f:
        head = f.read(16)
    if ext == "pdf":
        return head.startswith(b"%PDF-")
    if ext == "png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in ("jpg", "jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext in OFFICE_MEMBER:
        try:
            with zipfile.ZipFile(path) as z:
                return OFFICE_MEMBER[ext] in z.namelist()
        except zipfile.BadZipFile:
            return False
    if ext == "md":  # teks UTF-8 tanpa byte NUL
        decoder = codecs.getincrementaldecoder("utf-8")()
        try:
            with path.open("rb") as f:
                for block in iter(lambda: f.read(CHUNK), b""):
                    if b"\x00" in block:
                        return False
                    decoder.decode(block)
            decoder.decode(b"", final=True)
        except UnicodeDecodeError:
            return False
        return True
    return False


def _used_bytes(folder: Path) -> int:
    return sum(p.stat().st_size for p in folder.iterdir() if p.is_file())


@router.get("")
async def list_files() -> dict:
    folder = _dir()
    items = []
    for p in folder.iterdir():
        if not p.is_file() or p.name.startswith(".") or p.suffix.lower().lstrip(".") not in ALLOWED:
            continue
        st = p.stat()
        items.append(
            {
                "name": p.name,
                "size": st.st_size,
                "modified": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(timespec="seconds"),
            }
        )
    items.sort(key=lambda x: x["modified"], reverse=True)
    return {
        "files": items[:MAX_LISTED],
        "used_bytes": sum(i["size"] for i in items),
        "max_file_mb": settings.upload_max_mb,
        "quota_mb": settings.upload_quota_mb,
    }


@router.post("")
async def upload(request: Request) -> dict:
    """Isi permintaan = isi berkas mentah; nama berkas di header X-Filename (di-URL-encode)."""
    reason = upload_limiter.check(request.client.host if request.client else "unknown")
    if reason:
        raise HTTPException(429, "Terlalu banyak unggahan dalam waktu singkat. Tunggu sebentar lalu coba lagi.")

    name = clean_name(request.headers.get("x-filename", ""))
    ext = name.rsplit(".", 1)[1]
    folder = _dir()
    max_bytes = settings.upload_max_mb * 1024 * 1024
    room = settings.upload_quota_mb * 1024 * 1024 - _used_bytes(folder)
    if room <= 0:
        raise HTTPException(507, "Folder unggahan penuh. Hubungi pengelola untuk menambah kapasitas.")
    limit = min(max_bytes, room)

    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise HTTPException(413, f"Berkas terlalu besar (maksimal {settings.upload_max_mb} MB).")

    tmp = folder / f".tmp-{uuid.uuid4().hex}"
    size = 0
    try:
        with tmp.open("wb") as out:
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, f"Berkas terlalu besar (maksimal {settings.upload_max_mb} MB, atau kapasitas folder habis).")
                out.write(chunk)
        if size == 0:
            raise HTTPException(422, "Berkas kosong.")
        if not _content_ok(tmp, ext):
            raise HTTPException(415, f"Isi berkas tidak sesuai dengan jenis .{ext}.")
        final = _unique(folder, name)
        os.replace(tmp, final)
        os.chmod(final, 0o664)  # pengelola di host dapat membaca dan menghapus
    except HTTPException:
        raise
    except OSError:
        log.exception("Gagal menyimpan berkas unggahan")
        raise HTTPException(500, "Gagal menyimpan berkas di server.")
    finally:
        tmp.unlink(missing_ok=True)
    return {"ok": True, "name": final.name, "size": size}


@router.get("/{name}")
async def download(name: str) -> FileResponse:
    folder = _dir().resolve()
    path = (folder / name).resolve()
    if name != Path(name).name or path.parent != folder or name.startswith(".") or not path.is_file():
        raise HTTPException(404, "Berkas tidak ditemukan.")
    if path.suffix.lower().lstrip(".") not in ALLOWED:
        raise HTTPException(404, "Berkas tidak ditemukan.")
    return FileResponse(
        path,
        filename=path.name,
        media_type="application/octet-stream",  # selalu diunduh, tidak pernah ditampilkan di browser
        headers={"X-Content-Type-Options": "nosniff"},
    )
