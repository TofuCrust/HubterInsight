#!/bin/sh
# Dijalankan oleh entrypoint resmi image nginx setelah template dirender ke /etc/nginx/conf.d.
# Memilih mode berdasarkan ada/tidaknya sertifikat Let's Encrypt.
# Ditulis tanpa "exit" supaya aman dijalankan maupun di-source.

CONF=/etc/nginx/conf.d
CERT="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"

# Hapus server bawaan image agar tidak bentrok dengan konfigurasi kita
rm -f "$CONF/default.conf"

if [ -f "$CERT" ]; then
    echo "40-select-mode: sertifikat ditemukan -> mode HTTPS untuk ${DOMAIN}"
    rm -f "$CONF/bootstrap.conf"
else
    echo "40-select-mode: sertifikat belum ada -> mode BOOTSTRAP (HTTP saja) untuk ${DOMAIN}"
    rm -f "$CONF/redirect.conf" "$CONF/https.conf"
fi

# Muat ulang Nginx tiap 6 jam supaya sertifikat hasil pembaruan certbot terpakai
( while :; do sleep 6h; nginx -s reload; done ) >/dev/null 2>&1 &
