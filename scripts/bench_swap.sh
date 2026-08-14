#!/usr/bin/env bash
# bench การสลับ plugin ใต้โหลด (Phase 10 · 10-03) — ตัวเลขจริงของ migration class
#
# รันบน host ที่มี docker จาก**รากของสำเนา repo** (สคริปต์ up stack เอง):
#   ./scripts/bench_swap.sh            # ทุกสถานการณ์ อย่างละ 3 รอบ
#   ./scripts/bench_swap.sh themes     # เฉพาะสถานการณ์เดียว
#
# หลักที่สคริปต์นี้ยึด (ดู docs/PERFORMANCE.md หัวข้อ "การสลับ plugin"):
# - **ทุกสถานการณ์มีตัวคุมว่าการสลับมีผลจริง** — การวัดที่ swap ไม่เกิดคือการวัด
#   ความว่างเปล่า (เจอจริง: แหล่ง secrets ไม่ถูกอ่านเพราะชื่อไฟล์ผิดตัวพิมพ์
#   และ bench รายงานตัวเลขสวย ๆ ของสิ่งที่ไม่ได้ทดสอบ)
# - เกณฑ์ตัดสินคือ "ไม่มีรอบไหนตก" ต่อ class — ไม่ใช่ค่าเฉลี่ย (วินัย Phase 6)
# - `db` สลับทับ volume เดิมไม่ได้ (คนละ engine format) — datadir สดทุกครั้ง
#   การย้ายข้อมูลอยู่นอกขอบเขต (ADR 0040)
set -euo pipefail
cd "$(dirname "$0")/.."

BASE="-f compose.yaml -f compose.mysql.yaml -f compose.scale.yaml -f compose.bench.yaml"
URL=http://127.0.0.1:8080

need() { command -v "$1" >/dev/null || { echo "ต้องมี $1" >&2; exit 2; }; }
need docker; need curl; need python3

# ---------------------------------------------------------------- เครื่องมือวัด
loadgen() { # $1=url $2=log $3=stopfile [$4=cookie jar]
    while [ ! -f "$3" ]; do
        local code
        code=$(curl -s ${4:+-b "$4"} -o /dev/null -m 2 -w "%{http_code}" "$1")
        echo "$(date +%s%3N) $code" >> "$2"
        sleep 0.1
    done
}

stats() { # $1=log $2=t0 $3=t1 → "total=.. fails=.. max_gap_ms=.."
    python3 - "$1" "$2" "$3" <<'PY'
import sys
rows = [l.split() for l in open(sys.argv[1]) if l.strip()]
t0, t1 = int(sys.argv[2]), int(sys.argv[3])
inwin = [(int(t), c) for t, c in rows if t0 <= int(t) <= t1]
gap_start = gap_max = 0
prev_ok = None
for t, c in inwin:
    if c == "200":
        if prev_ok is not None and gap_start:
            gap_max = max(gap_max, t - gap_start)
            gap_start = 0
        prev_ok = t
    elif not gap_start:
        gap_start = prev_ok or t
fails = sum(1 for _, c in inwin if c != "200")
print(f"total={len(inwin)} fails={fails} max_gap_ms={gap_max}")
PY
}

wait_healthy_apps() {
    for _ in $(seq 90); do
        n=$(docker ps --format '{{.Names}} {{.Status}}' | grep -c 'app.*healthy' || true)
        [ "$n" = "2" ] && return 0
        sleep 2
    done
    echo "replica ไม่ healthy ครบสอง" >&2; return 1
}

rolling() { # ฆ่า replica ทีละตัว ให้ compose สร้างตัวแทนด้วย config ปัจจุบัน
    local files="$1"
    for name in $(docker ps --format '{{.Names}}' | grep -E '\bapp' | grep app- | sort); do
        docker stop -t 15 "$name" >/dev/null && docker rm "$name" >/dev/null
        # shellcheck disable=SC2086
        docker compose $files up -d --scale app=2 --no-recreate >/dev/null 2>&1
        wait_healthy_apps
    done
}

# ---------------------------------------------------------------- สถานการณ์
bench_dir_swap() { # live: ถอด/คืนไดเรกทอรี plugin — $1=path $2=control cmd $3=ป้าย
    local plugin="$1" control="$2" label="$3" r log stop t0 t1 gone back
    for r in 1 2 3; do
        log=$(mktemp) stop=$(mktemp -u)
        loadgen "$URL/login" "$log" "$stop" & sleep 2
        t0=$(date +%s%3N)
        mv "app/plugins/$plugin" "/tmp/bench-parked"
        sleep 2; gone=$(eval "$control"); sleep 2
        mv "/tmp/bench-parked" "app/plugins/$plugin"
        sleep 1; back=$(eval "$control"); sleep 1
        t1=$(date +%s%3N); touch "$stop"; sleep 0.5
        echo "[$label รอบ $r] $(stats "$log" "$t0" "$t1") control=$gone→$back"
    done
}

bench_cache_roll() { # warm: rolling swap ของ CACHE_URL — session ต้องรอด
    local r target log slog stop t0 t1 after
    for r in 1 2 3; do
        [ $((r % 2)) = 1 ] && target="memory://" || target="redis://redis:6379/0"
        log=$(mktemp) slog=$(mktemp) stop=$(mktemp -u)
        loadgen "$URL/login" "$log" "$stop" &
        loadgen "$URL/" "$slog" "$stop" /tmp/bench-jar & sleep 2
        t0=$(date +%s%3N)
        BENCH_CACHE_URL="$target" rolling "$BASE"
        sleep 3; t1=$(date +%s%3N); touch "$stop"; sleep 0.5
        after=$(curl -s -b /tmp/bench-jar -o /dev/null -w '%{http_code}' "$URL/")
        echo "[cache→$target รอบ $r] anon: $(stats "$log" "$t0" "$t1") · session: $(stats "$slog" "$t0" "$t1") after=$after"
    done
}

bench_auth_roll() { # warm: เปิด/ปิดปัจจัยหลัก OIDC ด้วย DISABLED_PLUGINS (rolling)
    local files="$BASE -f compose.sso.yaml -f compose.bench-sso.yaml" r disabled expect log slog stop t0 t1 link after
    for r in 1 2 3; do
        if [ $((r % 2)) = 1 ]; then disabled="auth/oidc"; expect=0; else disabled=""; expect=1; fi
        log=$(mktemp) slog=$(mktemp) stop=$(mktemp -u)
        loadgen "$URL/login" "$log" "$stop" &
        loadgen "$URL/" "$slog" "$stop" /tmp/bench-jar & sleep 2
        t0=$(date +%s%3N)
        BENCH_DISABLED="$disabled" rolling "$files"
        sleep 3; t1=$(date +%s%3N); touch "$stop"; sleep 0.5
        link=$(curl -s "$URL/login" | grep -c '/login/sso/' || true)
        after=$(curl -s -b /tmp/bench-jar -o /dev/null -w '%{http_code}' "$URL/")
        echo "[auth disabled='${disabled}' รอบ $r] anon: $(stats "$log" "$t0" "$t1") · session after=$after · sso_link=$link (คาด $expect)"
    done
}

bench_secrets_cold() { # cold: env↔file — env ถูกตั้งว่างใน overlay เพื่อบังคับแหล่ง file
    local r files log stop t0 t1
    for r in 1 2 3; do
        [ $((r % 2)) = 1 ] && files="$BASE -f compose.bench-secrets.yaml" || files="$BASE"
        log=$(mktemp) stop=$(mktemp -u)
        loadgen "$URL/login" "$log" "$stop" & sleep 2
        t0=$(date +%s%3N)
        # shellcheck disable=SC2086
        docker compose $files up -d --scale app=2 --force-recreate --no-deps app >/dev/null 2>&1
        for _ in $(seq 90); do curl -sf -o /dev/null -m 2 "$URL/login" && break; sleep 1; done
        sleep 3; t1=$(date +%s%3N); touch "$stop"; sleep 0.5
        echo "[secrets รอบ $r] $(stats "$log" "$t0" "$t1")"
    done
}

bench_db_cold() { # cold: สลับยี่ห้อ ฐานเปล่า + migrate — datadir สดทุกครั้ง
    local MY="-f compose.yaml -f compose.scale.yaml -f compose.bench.yaml -f compose.mysql.yaml"
    local MA="-f compose.yaml -f compose.scale.yaml -f compose.bench.yaml -f compose.mariadb.yaml"
    local project r from to log stop t0 t1 brand
    project=$(basename "$PWD")
    for r in 1 2 3; do
        if [ $((r % 2)) = 1 ]; then from="$MY" to="$MA"; else from="$MA" to="$MY"; fi
        log=$(mktemp) stop=$(mktemp -u)
        loadgen "$URL/login" "$log" "$stop" & sleep 2
        t0=$(date +%s%3N)
        # shellcheck disable=SC2086
        docker compose $from stop app db >/dev/null 2>&1
        # shellcheck disable=SC2086
        docker compose $from rm -f app db >/dev/null 2>&1
        docker volume rm -f "${project}_db-data" >/dev/null 2>&1
        # shellcheck disable=SC2086
        docker compose $to up -d --scale app=2 >/dev/null 2>&1
        for _ in $(seq 90); do docker compose $to exec -T app true 2>/dev/null && break; sleep 1; done
        # shellcheck disable=SC2086
        docker compose $to exec -T app flask db upgrade >/dev/null 2>&1
        for _ in $(seq 90); do curl -sf -o /dev/null -m 2 "$URL/login" && break; sleep 1; done
        sleep 3; t1=$(date +%s%3N); touch "$stop"; sleep 0.5
        brand=$(docker ps --format '{{.Names}}' | grep db | head -1 | xargs -I{} docker inspect {} --format '{{.Config.Image}}')
        echo "[db รอบ $r] $(stats "$log" "$t0" "$t1") db_now=$brand"
    done
}

setup() { # up stack + migrate + ผู้ใช้/SESSION สำหรับสาย warm — รันครั้งแรกครั้งเดียว
    [ -f .env ] || {
        {
            echo "SECRET_KEY=$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')"
            echo "DB_PASSWORD=$(python3 -c 'import secrets;print(secrets.token_urlsafe(16))')"
            echo "DB_ROOT_PASSWORD=$(python3 -c 'import secrets;print(secrets.token_urlsafe(16))')"
            echo "KEYCLOAK_ADMIN_PASSWORD=$(python3 -c 'import secrets;print(secrets.token_urlsafe(16))')"
        } > .env
    }
    mkdir -p secretdir && grep '^SECRET_KEY=' .env | cut -d= -f2 > secretdir/secret_key
    # shellcheck disable=SC2086
    docker compose $BASE up -d --scale app=2 --build
    sleep 15
    # shellcheck disable=SC2086
    docker compose $BASE exec -T app flask db upgrade
    # shellcheck disable=SC2086
    docker compose $BASE exec -T app flask plugin-install auth/totp || true
    # shellcheck disable=SC2086
    docker compose $BASE exec -T app flask plugin-install auth/oidc || true
    printf 'bench-passphrase-agreed\nbench-passphrase-agreed\n' \
        | docker compose $BASE run --rm -T app flask create-user bencher || true
    local token
    token=$(curl -sf -c /tmp/bench-jar "$URL/login" \
        | grep -oP 'name="csrf_token"[^>]*value="\K[^"]+' | head -1)
    curl -s -b /tmp/bench-jar -c /tmp/bench-jar -o /dev/null -X POST \
        -d "username=bencher&password=bench-passphrase-agreed&csrf_token=$token" "$URL/login"
    curl -s -b /tmp/bench-jar -o /dev/null -w 'setup เสร็จ — session=%{http_code}\n' "$URL/"
}

# ---------------------------------------------------------------- ทางเข้า
what="${1:-all}"
case "$what" in
    setup) setup ;;
    themes) bench_dir_swap themes/ocean \
        "curl -s -o /dev/null -w %{http_code} $URL/plugin/themes/ocean/style.css" "themes live" ;;
    totp) bench_dir_swap auth/totp \
        "docker compose $BASE exec -T app flask plugin-list 2>/dev/null | grep -c auth/totp || true" "totp live" ;;
    cache) bench_cache_roll ;;
    auth) bench_auth_roll ;;
    secrets) bench_secrets_cold ;;
    db) bench_db_cold ;;
    all)
        setup
        for s in themes totp cache auth secrets db; do "$0" "$s"; done ;;
    *) echo "ไม่รู้จักสถานการณ์: $what (themes|totp|cache|auth|secrets|db|all)" >&2; exit 2 ;;
esac
