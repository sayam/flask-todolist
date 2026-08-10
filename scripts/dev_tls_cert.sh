#!/usr/bin/env bash
# สร้างใบรับรอง self-signed สำหรับ **ทดสอบ TLS ในเครื่องเท่านั้น** (Phase 5 · P5-12)
#
#   ./scripts/dev_tls_cert.sh
#   docker compose -f compose.yaml -f compose.mysql.yaml \
#       -f compose.scale.yaml -f compose.tls.yaml up -d
#
# **ห้ามเอาไปใช้จริง** — ใบนี้ไม่มีใครรับรอง browser จะเตือนทุกครั้ง และคีย์
# ถูกสร้างโดยไม่มีรหัสผ่านคุ้มครอง ของจริงต้องมาจาก CA (Let's Encrypt ฯลฯ)
# แล้ววางไว้ที่เดียวกันด้วยชื่อเดียวกัน
#
# ไฟล์ที่ได้ถูก gitignore ไว้ — **ใบรับรองกับคีย์ไม่ควรอยู่ใน git แม้จะเป็นของ dev**
# เพราะวันหนึ่งจะมีคนคัดลอกไปใช้ที่อื่นด้วยเหตุผลว่า "มันมีอยู่แล้ว"
set -euo pipefail

dir="$(cd "$(dirname "$0")/.." && pwd)/deploy/tls"
mkdir -p "$dir"

if [ -e "$dir/server.key" ] || [ -e "$dir/server.crt" ]; then
    # **ไม่เขียนทับ** — ถ้าเครื่องนี้ชี้ไปที่ใบจริงอยู่ การรันสคริปต์นี้ผิดพลาด
    # ครั้งเดียวจะทำให้ของจริงหายไปโดยไม่มีทางกู้
    echo "มีใบรับรองอยู่แล้วที่ $dir — ลบเองก่อนถ้าต้องการออกใหม่" >&2
    exit 1
fi

openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "$dir/server.key" -out "$dir/server.crt" \
    -days 365 -subj "/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" 2>/dev/null

chmod 600 "$dir/server.key"
echo "ออกใบรับรองสำหรับ dev แล้วที่ $dir (อายุ 365 วัน, CN=localhost)"
