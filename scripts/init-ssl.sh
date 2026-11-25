#!/usr/bin/env bash
# Menerbitkan sertifikat Let's Encrypt pertama kali, lalu mengaktifkan HTTPS di Nginx.
# Jalankan di VPS, dari folder proyek:  ./scripts/init-ssl.sh
#
# Opsi:
#   --dry-run-only     hanya uji coba ke server staging Let's Encrypt, tidak menerbitkan sertifikat
#   --skip-dns-check   lewati pemeriksaan DNS
#
# Dengan menjalankan skrip ini Anda menyetujui Subscriber Agreement Let's Encrypt
# (flag --agree-tos): https://letsencrypt.org/repository/

set -euo pipefail
cd "$(dirname "$0")/.."

DRY_RUN_ONLY=0
SKIP_DNS=0
for arg in "$@"; do
  case "$arg" in
    --dry-run-only)   DRY_RUN_ONLY=1 ;;
    --skip-dns-check) SKIP_DNS=1 ;;
    *) echo "Opsi tidak dikenal: $arg"; exit 1 ;;
  esac
done

[ -f .env ] || { echo "ERROR: file .env belum ada. Jalankan: cp .env.example .env lalu isi."; exit 1; }
set -a
# shellcheck disable=SC1090
. <(tr -d '\r' < .env)
set +a
: "${DOMAIN:?DOMAIN belum diisi di .env}"
: "${LETSENCRYPT_EMAIL:?LETSENCRYPT_EMAIL belum diisi di .env}"
HTTP_PORT="${HTTP_PORT:-80}"

if [ "$SKIP_DNS" -eq 0 ]; then
  SERVER_IP="$(curl -s -4 -m 10 https://ifconfig.me || true)"
  echo "==> Memeriksa DNS (IP server: ${SERVER_IP:-tidak terdeteksi})"
  for name in "$DOMAIN" "www.$DOMAIN"; do
    DNS_IP="$(getent ahostsv4 "$name" | awk 'NR==1{print $1}' || true)"
    echo "    $name -> ${DNS_IP:-belum ada record A}"
    if [ -z "$DNS_IP" ] || [ "$DNS_IP" != "$SERVER_IP" ]; then
      echo "ERROR: record A $name belum mengarah ke IP server ini."
      echo "       Atur DNS dulu dan tunggu propagasi, atau gunakan --skip-dns-check."
      exit 1
    fi
  done
fi

echo "==> Menjalankan Nginx (memuat konfigurasi terbaru)"
docker compose up -d nginx
docker compose restart nginx

echo "==> Menunggu Nginx siap"
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${HTTP_PORT}/healthz" >/dev/null 2>&1; then break; fi
  sleep 1
done
curl -fsS "http://127.0.0.1:${HTTP_PORT}/healthz" >/dev/null || { docker compose logs --tail=30 nginx; echo "ERROR: Nginx tidak merespons."; exit 1; }

CERTBOT=(docker compose run --rm --entrypoint certbot certbot certonly
  --webroot -w /var/www/certbot
  -d "$DOMAIN" -d "www.$DOMAIN"
  --email "$LETSENCRYPT_EMAIL"
  --agree-tos --no-eff-email --non-interactive --keep-until-expiring --expand)

echo "==> Uji coba (dry run, server staging)"
"${CERTBOT[@]}" --dry-run

if [ "$DRY_RUN_ONLY" -eq 1 ]; then
  echo "Dry run berhasil. Jalankan tanpa --dry-run-only untuk menerbitkan sertifikat sungguhan."
  exit 0
fi

echo "==> Menerbitkan sertifikat sungguhan"
"${CERTBOT[@]}"

echo "==> Mengaktifkan HTTPS (restart Nginx) dan menjalankan pembaruan otomatis"
docker compose restart nginx
docker compose up -d certbot

sleep 2
echo "==> Verifikasi"
curl -sSI "https://${DOMAIN}" | head -n 5 || echo "Peringatan: verifikasi HTTPS dari server ini gagal, coba dari browser."
echo "Selesai. Buka https://${DOMAIN}"
