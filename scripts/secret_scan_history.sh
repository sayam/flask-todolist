#!/usr/bin/env bash
# กวาดหาความลับใน **ประวัติทั้งหมด** ไม่ใช่แค่ commit ที่เพิ่ง push
#
# **ทำไมต้องมีตัวนี้ทั้งที่ CI มี job `secret-scan` อยู่แล้ว**
# gitleaks-action บน event `push` ตรวจเฉพาะ commit ที่อยู่ในการ push ครั้งนั้น
# ซึ่งถูกต้องสำหรับงานประจำวัน (จับของที่กำลังจะเข้ามา) แต่ **ตอบคำถาม
# "ตลอดประวัติที่ผ่านมามีอะไรหลุดไปหรือยัง" ไม่ได้** — สองคำถามนี้คนละคำถาม
# และเป็นตัวอย่างอีกอันของบทเรียน Phase 5: ด่านที่มีอยู่ กับด่านที่ครอบชั้นที่
# พังจริง ต่างกันที่สัญญาณที่วัด
#
# รันเมื่อไหร่: ก่อนเปิด repo สู่สาธารณะ · หลังเขียนประวัติใหม่ทุกครั้ง ·
# และตามรอบใน docs/SECURITY-CADENCE.md
#
# ใช้: scripts/secret_scan_history.sh [ไฟล์รายงาน.json]
set -euo pipefail

report="${1:-}"
root="$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)"
cd "$root"

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "ไม่มี gitleaks — ติดตั้งลง ~/.local/bin ได้จาก" >&2
  echo "  https://github.com/gitleaks/gitleaks/releases (ไบนารีเดี่ยว ไม่ต้อง sudo)" >&2
  exit 127
fi

args=(git --log-opts=--all --no-banner --redact)
[ -n "$report" ] && args+=(--report-format json --report-path "$report")

echo "กวาดทั้งประวัติ ($(git rev-list --count --all) commit) ด้วย $(gitleaks version)"
echo "ข้อยกเว้นที่ประกาศไว้: $(grep -cvE '^\s*(#|$)' .gitleaksignore || true) รายการ ใน .gitleaksignore"
echo

# **ห้ามเขียนเป็น `if ! gitleaks ...; then status=$?`** — `$?` ในกิ่งนั้นเป็น 0
# เสมอ การสแกนที่เจอของจะรายงานว่าผ่าน (กับดักเดียวกับ scripts/purge_cron.sh)
status=0
gitleaks "${args[@]}" || status=$?

echo
if [ "$status" -eq 0 ]; then
  echo "สะอาด — ไม่พบความลับที่ยังไม่ถูกประกาศเป็นข้อยกเว้น"
else
  echo "พบของ (exit $status) — อ่านผลข้างบน" >&2
  echo "ถ้าเป็นของจริง: **ถือว่าหลุดแล้ว** ต้องเพิกถอนความลับนั้นก่อนเป็นอันดับแรก" >&2
  echo "การลบออกจากประวัติเป็นขั้นที่สอง ไม่ใช่ขั้นแรก และไม่ทดแทนการเพิกถอน" >&2
  echo "ถ้าเป็นของปลอม/ค่าตัวอย่าง: เติม fingerprint ลง .gitleaksignore พร้อมเหตุผล" >&2
fi
exit "$status"
