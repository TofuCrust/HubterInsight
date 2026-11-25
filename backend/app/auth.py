"""Login bersama untuk pemakai internal: satu nama pengguna dan satu kata sandi, tanpa registrasi.

Setelah masuk, browser menyimpan cookie sesi bertanda tangan HMAC (HttpOnly, SameSite=Lax, Secure di HTTPS).
Cookie tidak berisi data pribadi: hanya nama pengguna dan waktu kedaluwarsa. Login nonaktif bila AUTH_PASSWORD
kosong (pengembangan lokal). Mengganti kata sandi atau AUTH_SECRET otomatis mengeluarkan semua sesi lama.
"""

import base64
import hashlib
import hmac
import time

from fastapi import HTTPException, Request

from .config import settings

COOKIE = "hubter_session"


def enabled() -> bool:
    return settings.auth_password is not None and bool(settings.auth_password.get_secret_value())


def _key() -> bytes:
    secret = settings.auth_secret.get_secret_value() if settings.auth_secret else ""
    base = secret or f"{settings.auth_user}|{settings.auth_password.get_secret_value() if settings.auth_password else ''}"
    return hashlib.sha256(("hubter-session|" + base).encode()).digest()


def _norm_user(user: str) -> str:
    # Keyboard HP sering membuat huruf pertama kapital dan menambah spasi di ujung.
    return user.strip().lower()


def check_credentials(user: str, password: str) -> bool:
    ok_user = hmac.compare_digest(_norm_user(user).encode(), _norm_user(settings.auth_user).encode())
    ok_pass = hmac.compare_digest(password.strip().encode(), settings.auth_password.get_secret_value().encode())
    return ok_user and ok_pass  # kedua pembandingan selalu dihitung


def make_token() -> str:
    expires = int(time.time()) + settings.auth_session_days * 86400
    payload = f"{_norm_user(settings.auth_user)}|{expires}".encode()
    sig = hmac.new(_key(), payload, hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=") + "." + sig


def valid_token(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    body, _, sig = token.partition(".")
    try:
        payload = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        _, _, expires = payload.decode().partition("|")
        expected = hmac.new(_key(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected) and int(expires) > time.time()
    except (ValueError, UnicodeDecodeError):
        return False


def is_authenticated(request: Request) -> bool:
    return not enabled() or valid_token(request.cookies.get(COOKIE))


def require_auth(request: Request) -> None:
    """Dependensi FastAPI untuk endpoint yang memakai kredit atau menyimpan data."""
    if not is_authenticated(request):
        raise HTTPException(401, "Silakan masuk terlebih dahulu.")
