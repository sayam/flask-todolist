#!/usr/bin/env bash
#
# ติดตั้ง systemd timer ที่ลบข้อมูลพ้นระยะเก็บรักษา (Phase 5 · P5-16)
#
# **ระยะเก็บรักษาที่ docs/DATA-CLASSIFICATION.md ประกาศไว้เป็นความจริงก็ต่อเมื่อ
# มีอะไรรันตามรอบจริง ๆ** — ก่อนหน้านั้นเอกสารอ้างสิ่งที่ไม่เกิดขึ้น
#
#   sudo ./scripts/install_purge_timer.sh                    # โหมด repo (pipenv)
#   sudo TDL_PURGE_RUNNER="docker compose -f /srv/todolist/compose.yaml \
#        -f /srv/todolist/compose.mysql.yaml run --rm -T app" \
#        ./scripts/install_purge_timer.sh                    # โหมด container
#
# **สคริปต์นี้แตะระบบจริง** (เขียนไฟล์ใน /etc/systemd/system แล้ว enable timer)
# จึงพิมพ์ทุกอย่างที่จะทำก่อน และรับ `--dry-run` ให้ดูก่อนได้
set -euo pipefail

UNIT_DIR="${TDL_UNIT_DIR:-/etc/systemd/system}"
SERVICE_USER="${TDL_PURGE_USER:-$(id -un)}"
RUNNER="${TDL_PURGE_RUNNER:-pipenv run}"
DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

SCRIPT_PATH="$(readlink -f -- "$0")"
REPO_ROOT="$(cd -- "$(dirname -- "$SCRIPT_PATH")/.." && pwd)"
SOURCE_DIR="$REPO_ROOT/deploy/systemd"

echo "จะติดตั้งจาก : $SOURCE_DIR"
echo "ไปที่        : $UNIT_DIR"
echo "รันในนามผู้ใช้: $SERVICE_USER"
echo "ไดเรกทอรีงาน : $REPO_ROOT"
echo "ตัวรันคำสั่ง  : $RUNNER"

if [ "$DRY_RUN" = "1" ]; then
    echo "(--dry-run: ไม่ได้เขียนอะไรลงไป)"
    exit 0
fi

# **ปฏิเสธตั้งแต่ต้นถ้า repo อยู่ใต้ home** — หน่วยนี้ตั้ง `ProtectHome=true`
# ซึ่งทำให้ /home และ /root มองไม่เห็นจากในหน่วย ผลคือ systemd ตอบ
# `203/EXEC` ที่**ไม่บอกสาเหตุอะไรเลย** (อ่านแล้วนึกว่าลืม chmod +x)
# เจอจริงตอนติดตั้งครั้งแรก — ของจริงวางไว้ที่ /opt หรือ /srv อยู่แล้ว
case "$REPO_ROOT" in
    /home/*|/root|/root/*)
        echo "ติดตั้งไม่ได้: $REPO_ROOT อยู่ใต้ home ซึ่งหน่วยนี้มองไม่เห็น" >&2
        echo "(ProtectHome=true) — ย้าย repo ไปที่ /opt หรือ /srv ก่อน" >&2
        exit 1
        ;;
esac

# **แทนค่าลงไปตอนติดตั้ง ไม่ใช่ให้คนแก้ไฟล์ในที่เก็บโค้ด** — ไฟล์ใน deploy/
# ต้องเป็นตัวเดียวกับที่ CI ตรวจ ถ้าให้คนแก้ก่อนติดตั้ง สิ่งที่ CI ตรวจกับสิ่งที่
# รันจริงจะเป็นคนละไฟล์ตั้งแต่วันแรก
# **`Environment=` ต้องอยู่ใน `[Service]`** — ต่อท้ายไฟล์เฉย ๆ จะไปตกใน
# `[Install]` แล้ว systemd เตือนว่า "Unknown key name" *แล้วรันต่อ* โดยไม่มี
# ตัวแปรนั้น (เจอจริงตอนติดตั้งครั้งแรก: หน่วยรันด้วย runner ค่าเริ่มต้นแทน)
# จึงแทรกต่อจากบรรทัด `ExecStart=` ซึ่งอยู่ใน `[Service]` แน่นอน
#
# **และต้องใส่เครื่องหมายคำพูดรอบค่า** — `Environment=` ของ systemd แยกคำตาม
# ช่องว่าง ค่าที่มีช่องว่าง (เช่น `docker compose -f ... run --rm -T app`) จะ
# เหลือแค่คำแรก ส่วนคำที่เหลือถูกตีความเป็น assignment ใหม่แล้วทิ้งไปพร้อม
# คำเตือนใน journal — ผลคือ runner กลายเป็น `docker` เฉย ๆ แล้วล้มด้วย
# "unknown command: docker flask" ซึ่งอ่านแล้วไม่มีทางเดาสาเหตุถูก (เจอจริง)
sed \
    -e "s|^User=.*|User=$SERVICE_USER|" \
    -e "s|^WorkingDirectory=.*|WorkingDirectory=$REPO_ROOT|" \
    -e "s|^ExecStart=.*|ExecStart=$REPO_ROOT/scripts/purge_cron.sh\nEnvironment=\"TDL_PURGE_RUNNER=$RUNNER\"|" \
    "$SOURCE_DIR/todolist-purge.service" > "$UNIT_DIR/todolist-purge.service"

install -m 0644 "$SOURCE_DIR/todolist-purge.timer" "$UNIT_DIR/todolist-purge.timer"
chmod 0644 "$UNIT_DIR/todolist-purge.service"

# ให้ CI (และคนที่อยากดูผลก่อน) สร้างไฟล์ได้โดยไม่แตะ systemd ของเครื่อง
if [ "${TDL_INSTALL_ONLY:-0}" = "1" ]; then
    echo "TDL_INSTALL_ONLY=1: เขียนไฟล์แล้ว ไม่ได้ enable อะไร"
    exit 0
fi

systemctl daemon-reload
# **enable `--now` เพื่อให้ timer เริ่มนับทันที** ไม่ใช่รอ reboot ครั้งหน้า
systemctl enable --now todolist-purge.timer

echo
systemctl list-timers todolist-purge.timer --no-pager
echo
echo "ทดสอบเดี๋ยวนี้ได้ด้วย: systemctl start todolist-purge.service"
echo "ดูผลรอบล่าสุด        : systemctl status todolist-purge.service"
echo "ดู log ย้อนหลัง       : journalctl -u todolist-purge.service"
