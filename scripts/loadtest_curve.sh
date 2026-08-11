#!/usr/bin/env bash
#
# ไล่หา **จุดที่ระบบเริ่มพัง** ไม่ใช่แค่ยืนยันว่าเป้าผ่าน (Phase 6 · ADR 0031 ข้อ 2)
#
#   ./scripts/loadtest_curve.sh http://127.0.0.1:8000 "1 5 10 25 50 100"
#
# **รายงานที่มีแต่ตัวเลขที่ผ่านคือรายงานที่ไม่ได้บอกอะไร** — ที่ 5 concurrent
# ระบบนี้แทบผ่านทุกอย่างโดยไม่ต้องพยายาม สิ่งที่บอกว่าเรามีที่ว่างเหลือแค่ไหน
# คือระยะห่างระหว่างเป้ากับจุดที่ p95 ทะลุ
#
# ปิด threshold ระหว่างไล่เส้นโค้ง เพราะ "ไม่ผ่าน" คือผลลัพธ์ที่เรากำลังตามหา
# ไม่ใช่ความล้มเหลวของการทดสอบ
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"
LEVELS="${2:-1 5 10 25 50}"
DURATION="${TDL_LOAD_DURATION:-20s}"
SCRIPT_DIR="$(cd -- "$(dirname -- "$(readlink -f -- "$0")")/.." && pwd)"

printf '%-6s %-10s %-10s %-10s %-8s\n' "VUs" "p95(ms)" "p99(ms)" "req/s" "ล้มเหลว"
for vus in $LEVELS; do
    summary=$(docker run --rm -i --network host \
        -e BASE_URL="$BASE_URL" -e VUS="$vus" -e DURATION="$DURATION" \
        -e NO_THRESHOLDS=1 -e SUMMARY_JSON=1 \
        -e TODOLIST_USER="${TODOLIST_USER:-loadtest}" \
        -e TODOLIST_PASSWORD="${TODOLIST_PASSWORD:-k6-journey-passphrase-not-a-secret}" \
        grafana/k6 run --quiet - \
        < "$SCRIPT_DIR/loadtest/journey.js" 2>/dev/null | tail -1)
    # ดึงตัวเลขด้วย python เพราะ jq อาจไม่มีบนเครื่องที่รัน
    printf '%s\n' "$summary" | python3 -c '
import json, sys
row = json.loads(sys.stdin.read())
print("%-6d %-10.1f %-10.1f %-10.1f %-8.2f%%" % (
    row["vus"], row["p95"], row["p99"], row["rps"], row["failed"]))
'
done
