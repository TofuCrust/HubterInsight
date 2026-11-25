"""Pembatas permintaan di memori: per alamat IP (per menit dan per hari) dan total harian.

Tujuannya melindungi kredit OpenAI pada situs publik. Hitungan hilang saat backend restart,
yang dapat diterima untuk pelindung biaya sederhana ini.
"""

import time
from collections import defaultdict, deque

MINUTE = 60.0
DAY = 24 * 3600.0
MAX_TRACKED_IPS = 20_000


class RateLimiter:
    def __init__(self, per_minute: int, per_day: int, daily_cap: int) -> None:
        self.per_minute = per_minute
        self.per_day = per_day
        self.daily_cap = daily_cap
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._all: deque[float] = deque()

    def check(self, key: str) -> str | None:
        """Mencatat satu permintaan bila diizinkan. Mengembalikan alasan penolakan, atau None."""
        now = time.monotonic()
        while self._all and now - self._all[0] > DAY:
            self._all.popleft()
        if self.daily_cap and len(self._all) >= self.daily_cap:
            return "Layanan sedang mencapai batas pemakaian harian. Silakan coba lagi besok."

        if len(self._hits) > MAX_TRACKED_IPS:
            self._prune(now)
        hits = self._hits[key]
        while hits and now - hits[0] > DAY:
            hits.popleft()
        if self.per_day and len(hits) >= self.per_day:
            return "Batas pertanyaan harian untuk alamat Anda tercapai. Silakan coba lagi besok."
        if self.per_minute and sum(1 for t in hits if now - t <= MINUTE) >= self.per_minute:
            return "Terlalu banyak pertanyaan dalam waktu singkat. Tunggu sebentar lalu coba lagi."

        hits.append(now)
        self._all.append(now)
        return None

    def _prune(self, now: float) -> None:
        for k in [k for k, h in self._hits.items() if not h or now - h[-1] > DAY]:
            del self._hits[k]
