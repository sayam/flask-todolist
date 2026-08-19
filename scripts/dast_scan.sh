#!/usr/bin/env bash
# ยิง ZAP baseline ใส่ stack ที่รันอยู่จริง — **แบบที่ login แล้ว** (Phase 7 · P7-03)
#
# **การสแกนโดยไม่ login เห็นแค่หน้า login** ซึ่งเป็นหน้าเดียวที่ไม่มีข้อมูลของใคร
# เลย ด่านแบบนั้น "มีอยู่" แต่ไม่ได้ครอบชั้นที่พังจริง (บทเรียนของ Phase 5 —
# ดู docs/ROADMAP.md) สคริปต์นี้จึง login ด้วย curl ก่อน แล้วยัดคุกกี้ให้ ZAP
# แนบไปกับทุกคำขอผ่าน replacer ของมัน
#
# ใช้:
#   TODOLIST_USER=somchai TODOLIST_PASSWORD='...' ./scripts/dast_scan.sh https://127.0.0.1:8443
#
# คืน exit ตามที่ ZAP ตัดสิน: 0 = ไม่มีข้อที่ตั้งเป็น FAIL · 1 = มี
# กติกาต่อรายการอยู่ใน .zap/rules.tsv ซึ่งทุกบรรทัดต้องมีเหตุผลกำกับ

set -euo pipefail

BASE="${1:?ต้องบอก base URL เช่น https://127.0.0.1:8443}"
USERNAME="${TODOLIST_USER:?ต้องตั้ง TODOLIST_USER}"
PASSWORD="${TODOLIST_PASSWORD:?ต้องตั้ง TODOLIST_PASSWORD}"
# **ตรึงด้วย digest ไม่ใช่ tag `stable`** (audit รอบ 15) — ตัวนี้เป็นตัว *ตัดสิน*
# ผลด้านความปลอดภัยของทุก push · tag ลอยแปลว่าเขียวเมื่อวานกับเขียววันนี้อาจมา
# จาก scanner คนละตัว และแดงพรุ่งนี้อาจไม่ใช่เพราะโค้ดเรา — ผลที่ทำซ้ำไม่ได้
# ไม่ใช่หลักฐาน · Dependabot ecosystem `docker` ขยับ digest นี้ให้ (ดู dependabot.yml)
ZAP_IMAGE="${ZAP_IMAGE:-ghcr.io/zaproxy/zaproxy:stable@sha256:781a2bdaea47324e7bab583e2263f21d257b0aee61ed51521a5be45f5f5081ef}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# **curl กับ ZAP ต้องเป็นเบราว์เซอร์ตัวเดียวกัน** — `session_protection="strong"`
# ของ Flask-Login ผูก session ไว้กับ User-Agent ของคนที่ login แล้ว**ทิ้ง session
# ทั้งใบ**เมื่อไม่ตรง (ดู tests/test_session_security.py::test_a_cookie_used_from_another_browser_is_rejected)
# ตอนแรกไม่รู้เรื่องนี้ แล้ว ZAP ก็สแกนโดยได้ 302 ทุกหน้าอย่างเงียบ ๆ
# — คุกกี้ถูกส่งไปจริง แค่ปลายทางไม่รับ ซึ่งแยกไม่ออกจาก "ลืมส่งคุกกี้"
# **ห้ามมีช่องว่างในค่านี้** — `-z` ของ zap-baseline.py แยกอาร์กิวเมนต์ด้วย
# ช่องว่าง ค่าที่มีช่องว่างจะกลายเป็นอ็อพชันคนละตัวแล้ว ZAP พ่นหน้าช่วยเหลือออกมา
# แทนที่จะสแกน · ค่านี้ไม่ต้องเหมือนเบราว์เซอร์จริง แค่ต้อง**ตรงกันทั้งสองฝั่ง**
USER_AGENT="todolist-dast-scanner/1"

jar=$(mktemp)
trap 'rm -f "$jar"' EXIT

# `-k` เพราะ stack ของ CI/dev ใช้ใบรับรอง self-signed — ความถูกต้องของ TLS
# มีด่านของตัวเองอยู่แล้วใน job `stack` (ปฏิเสธ 1.0/1.1 ที่ฝั่ง server)
token=$(curl -sfk -A "$USER_AGENT" -c "$jar" "$BASE/login" \
  | grep -oP 'name="csrf_token"[^>]*value="\K[^"]+' | head -1)
[ -n "$token" ] || { echo "ไม่เจอ csrf_token ในหน้า login — แอปตอบอะไรกลับมาไม่ทราบ"; exit 1; }

code=$(curl -sk -A "$USER_AGENT" -b "$jar" -c "$jar" -o /dev/null -w '%{http_code}' \
  -e "$BASE/login" -X POST \
  -d "username=$USERNAME&password=$PASSWORD&csrf_token=$token" "$BASE/login")
[ "$code" = "302" ] || { echo "login ไม่ผ่าน ($code) — สแกนต่อไปก็เห็นแค่หน้า login"; exit 1; }

session=$(awk '$6 == "session" {print $7}' "$jar" | tail -1)
[ -n "$session" ] || { echo "login สำเร็จแต่ไม่มีคุกกี้ session ในถัง"; exit 1; }

# **พิสูจน์ว่าคุกกี้ใช้ได้จริงก่อนส่งให้ ZAP** — ถ้าคุกกี้ตายแล้ว ZAP จะสแกน
# หน้า login 30 หน้าแล้วรายงานว่า "ไม่พบอะไร" ซึ่งอ่านเหมือนผลดี
home=$(curl -sk -A "$USER_AGENT" -b "session=$session" -o /dev/null -w '%{http_code}' "$BASE/")
[ "$home" = "200" ] || { echo "คุกกี้ที่จะส่งให้ ZAP ใช้ไม่ได้ (GET / → $home)"; exit 1; }

out="$ROOT/.zap/out"
rm -rf "$out"
mkdir -p "$out"
# ZAP ใน image รันด้วยผู้ใช้ zap ไม่ใช่ root — ไดเรกทอรีที่ mount เข้าไปต้อง
# เขียนได้ ไม่งั้นการสแกนจะ "สำเร็จ" แล้วเขียนรายงานไม่ได้ (AccessDeniedException)
chmod 777 "$out"

# **ห้ามใส่ backslash หน้าวงเล็บ** — ค่าตรงนี้ไม่ได้ผ่าน shell อีกชั้น ZAP จะได้
# ชื่อ config เป็น `replacer.full_list\(0\)...` ซึ่งไม่ตรงกับอะไรเลยแล้ว**ไม่บ่นสักคำ**
zap_config="-config replacer.full_list(0).description=session"
zap_config="$zap_config -config replacer.full_list(0).enabled=true"
zap_config="$zap_config -config replacer.full_list(0).matchtype=REQ_HEADER"
zap_config="$zap_config -config replacer.full_list(0).matchstr=Cookie"
zap_config="$zap_config -config replacer.full_list(0).regex=false"
zap_config="$zap_config -config replacer.full_list(0).replacement=session=$session"
zap_config="$zap_config -config replacer.full_list(1).description=useragent"
zap_config="$zap_config -config replacer.full_list(1).enabled=true"
zap_config="$zap_config -config replacer.full_list(1).matchtype=REQ_HEADER"
zap_config="$zap_config -config replacer.full_list(1).matchstr=User-Agent"
zap_config="$zap_config -config replacer.full_list(1).regex=false"
zap_config="$zap_config -config replacer.full_list(1).replacement=$USER_AGENT"

# **spider thread เดียว** — ไม่ใช่เพื่อความสุภาพ แต่เพื่อให้ด่านนี้วัดสิ่งที่มัน
# ตั้งใจวัด · ZAP submit ฟอร์มด้วย การ crawl หลาย thread จึงกลายเป็นการเขียน
# พร้อมกันหลายทาง ซึ่งไปชน **MySQL deadlock (1213)** ที่ ADR 0032 บันทึกไว้แล้ว
# ว่ายังไม่ได้แก้ · ผลคือ 500 โผล่มาแล้วกฎ "ห้ามคายข้อความ error" แดง —
# แดงด้วยเรื่องที่รู้อยู่แล้วและไม่เกี่ยวกับสิ่งที่ PR นั้นแก้
#
# คำถามของ job นี้คือ "แอปคายข้อมูลหรือขาด header ไหม" ส่วนคำถาม "ทนการเขียน
# พร้อมกันไหม" มีเจ้าของอยู่แล้วที่ loadtest/journey.js และ docs/PERFORMANCE.md
# **ไม่ใช่การซ่อนปัญหา** — deadlock ยังอยู่ในรายการของที่ยังไม่ทำ และการที่มัน
# โผล่ตอน crawl ธรรมดาด้วย เป็นหลักฐานเพิ่มว่าควรแก้ ไม่ใช่หลักฐานว่าไม่ต้อง
zap_config="$zap_config -config spider.thread=1"

# **ตัวกรองของหน้ารายการทำให้ URL เดียวกลายเป็นสิบกว่า URL** — `?status=`,
# `?when=`, `?within=`, `?category=` ผสมกันได้หลายสิบแบบ และ spider ที่มีงบเวลา
# จำกัดจะใช้งบไปกับ*ค่าของพารามิเตอร์*จนไม่เหลือไปถึงหน้าอื่น · `IGNORE_VALUE`
# ยุบให้เหลือหนึ่ง URL ต่อชุดชื่อพารามิเตอร์ ซึ่งตรงกับคำถามของ job นี้พอดี
# (baseline เป็นการสแกนแบบ passive — มันไม่ได้ยิงค่าเข้าไปทดสอบอยู่แล้ว)
#
# เกิดจริงสามครั้งใน 2 วัน: FAIL-NEW 0 แต่ด่านความครอบคลุมแดงเพราะ spider
# ไม่เคยไปถึง `/settings` (2026-08-17 สองครั้ง · 2026-08-18 หนึ่งครั้ง) —
# เกณฑ์ flake ใน docs/SECURITY-CADENCE.md สั่งให้แก้ความไม่แน่นอน ไม่ใช่ rerun
zap_config="$zap_config -config spider.handleParameters=IGNORE_VALUE"

status=0
docker run --rm --network host \
  -v "$ROOT/.zap:/zap/wrk/:rw" \
  "$ZAP_IMAGE" zap-baseline.py \
  -t "$BASE" \
  -m 3 \
  -c rules.tsv \
  -r out/report.html \
  -w out/report.md \
  -J out/report.json \
  -I \
  -z "$zap_config" || status=$?

# **ด่านที่วัดว่าการสแกนได้ตรวจจริง ไม่ได้อยู่ที่นี่ — และเคยอยู่ผิดที่มาตลอด**
#
# ของเดิมที่ตรงนี้ grep หา `/settings` กับ `/categories` ใน `report.json` ของ ZAP
# ซึ่งเป็นวิธีที่ `CLAUDE.md` เตือนไว้เองว่าใช้ไม่ได้: **รายงานมีแค่ URL ที่มี alert**
# วันที่แก้จนไม่เหลือ alert (หรือวันที่ยุบ URL ซ้ำทิ้ง) การเช็คแบบนั้นจะอ่านว่า
# "ไม่เจอ = ไม่ได้สแกน" ทั้งที่สแกนครบ · เกิดจริง 2026-08-18: หลังยุบ URL ซ้ำ
# จำนวน URL ในรายงานลดจาก 61 เหลือ 22 แล้วด่านนี้แดงทั้งที่ login และ crawl ปกติ
#
# **ตัวจริงอยู่ใน job `dast` ของ CI** ซึ่งนับจาก *access log ของแอป* ว่าถูกเรียกจริง
# กี่ครั้ง — สัญญาณที่ไม่ขึ้นกับว่ามี alert หรือไม่ · รันเองบนเครื่องก็ใช้วิธีเดียวกัน:
#
#   docker compose -f compose.yaml -f compose.mysql.yaml -f compose.scale.yaml \
#     -f compose.tls.yaml logs app | grep -c '"path": "/settings"'

exit "$status"
