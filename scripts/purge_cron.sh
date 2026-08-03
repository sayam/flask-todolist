#!/usr/bin/env bash
#
# รัน `flask purge-expired` ตามตารางเวลา — วิธีติดตั้งอยู่ใน docs/OPERATIONS.md
#
# ระยะเก็บรักษาที่อนุมัติแล้ว (soft delete 30 วัน / audit 1 ปี) จะเป็นจริงก็ต่อเมื่อ
# มีอะไรสั่งลบตามรอบ ไม่ใช่แค่เขียนไว้ในเอกสาร สคริปต์นี้คือตัวที่ทำให้มันเกิดจริง
#
# ตั้งใจให้รันจาก cron/timer ซึ่งไม่มีตัวแปรแวดล้อมเหมือน shell ที่คนใช้ จึงต้อง
# หา path เอง เข้าไดเรกทอรี repo เอง และห้ามพึ่ง PATH ที่ระบบให้มา
set -euo pipefail

# หา repo root จากตำแหน่งไฟล์จริง (ผ่าน symlink ได้) ไม่ใช่จาก cwd ตอนถูกเรียก
SCRIPT_PATH="$(readlink -f -- "$0")"
REPO_ROOT="$(cd -- "$(dirname -- "$SCRIPT_PATH")/.." && pwd)"

# ล็อกกันสองรอบทับกัน — รอบที่แล้วยังไม่จบแล้วรอบใหม่เข้ามาจะแย่งลบแถวเดียวกัน
LOCK_FILE="${TDL_PURGE_LOCK:-/tmp/todolist-purge.lock}"

# ตรวจสาย audit ต่อท้ายทุกครั้ง — ตั้ง 0 เพื่อข้าม (ดูเหตุผลใน docs/OPERATIONS.md)
VERIFY_AUDIT="${TDL_PURGE_VERIFY_AUDIT:-1}"

log() {
    printf '%s purge-cron: %s\n' "$(date -Is)" "$*"
}

# fd 9 ค้างไว้ตลอดอายุ process ระบบจะปลดล็อกให้เองตอนจบ ไม่ต้องลบไฟล์ทิ้ง
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    log "รอบก่อนหน้ายังไม่จบ ข้ามรอบนี้ไป"
    exit 0
fi

cd -- "$REPO_ROOT"
log "เริ่มที่ $REPO_ROOT"

# **ต้องรับ exit code ด้วย `|| status=$?` เท่านั้น** ห้ามเขียนเป็น `if ! cmd; then status=$?`
# เพราะในกิ่งนั้น `$?` คือผลของ `!` ซึ่งเป็น 0 เสมอ สคริปต์จะจบด้วย 0 ทั้งที่งานล้มเหลว
# แล้ว cron จะเงียบสนิท — งานตามรอบที่รายงานผลผิดแย่กว่าไม่มีงานตามรอบเลย
#
# `pipenv run` โหลด .env ให้เอง จึงได้ SECRET_KEY/DATABASE_URL ตามที่ตั้งไว้
status=0
pipenv run flask purge-expired || status=$?
if [ "$status" -ne 0 ]; then
    log "purge-expired ล้มเหลว (exit=$status) — ข้อมูลที่พ้นระยะยังค้างอยู่"
    exit "$status"
fi

# purge เป็นงานเดียวที่ลบแถว audit ได้จริง (ตัดจากหัวสายแล้วเขียน checkpoint)
# จึงเป็นจังหวะที่คุ้มที่สุดที่จะพิสูจน์ว่าสายยังต่อกันอยู่ ถ้าเพี้ยนต้องรู้ทันที
if [ "$VERIFY_AUDIT" = "1" ]; then
    status=0
    pipenv run flask audit-verify || status=$?
    if [ "$status" -ne 0 ]; then
        log "audit-verify ไม่ผ่านหลัง purge (exit=$status) — สายขาดหรือถูกแก้ ต้องตรวจด้วยคน"
        exit "$status"
    fi
fi

log "เสร็จเรียบร้อย"
