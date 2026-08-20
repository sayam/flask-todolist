"""ของที่รันตามเวลา ต้องพิสูจน์ได้ว่ามันยังยิงอยู่ — audit รอบ 10 ข้อ 2

ADR 0064 ปิดชั้น "workflow ที่ไม่ได้ start = 0 job" ไปแล้ว · **ชั้นถัดขึ้นไปยัง
เปิดอยู่: workflow ที่ไม่เคยถูกทริกเกอร์เลย = 0 run** — และ "ไม่มี run เลย"
หน้าตาเหมือน "ไม่มี run ไหนแดง" เป๊ะในทุกเครื่องมือที่เรามี รวมทั้ง
`scripts/rerun_census.py` ซึ่งนับจากสิ่งที่ *เกิดขึ้น* ไม่ใช่สิ่งที่ *ควรเกิด*

สิ่งที่ตัวนี้ตอบคือคำถามเดียว: **ตารางเวลาที่เราประกาศไว้ ยิงจริงครั้งล่าสุด
เมื่อไหร่ และช้ากว่าที่ประกาศไปกี่เท่า**

เกณฑ์:

- ทุก workflow ที่ประกาศ `on.schedule` ต้องมี run ชนิด `schedule` อย่างน้อยหนึ่งใบ
  — ประกาศ cron แล้วไม่เคยยิงเลยคืออาการของ workflow ที่ GitHub ปฏิเสธทั้งไฟล์
  (เกิดจริงมาแล้วกับ `scorecard.yml` — ADR 0064) หรือของ repo ที่ถูกปิด schedule
  อัตโนมัติเพราะไม่มีความเคลื่อนไหว 60 วัน ซึ่งเป็นพฤติกรรมที่ GitHub ประกาศไว้
- run ล่าสุดต้องไม่เก่ากว่ารอบที่ประกาศ × `--tolerance` (ค่าเริ่มต้น 2 เท่า)
  — เผื่อ cron ของ GitHub ที่เลื่อนได้เป็นสิบนาทีในชั่วโมงที่คนใช้เยอะ

**Dependabot อยู่ในรายงานนี้ในฐานะสิ่งที่ตรวจด้วยเครื่องไม่ได้** — ไม่มี REST
endpoint สาธารณะที่บอกว่ามันรันล่าสุดเมื่อไหร่ (`/dependabot/updates` ตอบ 404)
หลักฐานเดียวที่มีคือ "มี PR โผล่มา" ซึ่งไม่โผล่เลยก็ถูกต้องเมื่อไม่มีอะไรต้อง
อัปเดต · ตัวนี้จึง **รายงานตัวเลขพร้อมป้ายว่าเป็นตัวแทน และไม่ทำให้แดง** —
หลักเดียวกับชั้น "ต้องอ่านเอง" ของ `rerun_census.py` (ADR 0064): ของที่จำแนก
ด้วยเครื่องไม่ได้ ต้องถูกเรียกว่าอย่างนั้น ไม่ใช่ถูกเดาไปข้างใดข้างหนึ่ง

ใช้:
    python3 scripts/schedule_census.py                 # ถาม GitHub ผ่าน gh
    python3 scripts/schedule_census.py --input x.json  # ตัดสินจากไฟล์ (ออฟไลน์)

บทบาท: reader — อ่านแล้วรายงาน — หลักฐานคือตัวเลขที่พิมพ์ต้องตรงกับแหล่ง · ห้ามตัดของทิ้งเงียบ
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import shutil
import subprocess
import sys
import typing

# pyyaml มากับ dev tools และไม่มี stub — เหตุผลเดียวกับ build_gates_crosswalk.py
import yaml  # type: ignore[import-untyped]

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import workflows

ROOT = pathlib.Path(__file__).resolve().parent.parent

# **เพดานเวลาของคำสั่งที่เรายิงออกไป** (audit รอบ 11 · ADR 0067) — `subprocess.run`
# ที่ไม่มี `timeout=` รอตลอดกาล และเครื่องมือพวกนี้รันอยู่ใน job ของ CI ผลคือ
# `gh` ที่ไม่ตอบกลายเป็น job ที่กินเพดานของ job ไปทั้งก้อนโดยไม่ทำอะไรเลย
NETWORK_TIMEOUT_SECONDS = 60  # หนึ่งคำขอไป GitHub API
WORKFLOWS = ROOT / ".github" / "workflows"
DEPENDABOT = ROOT / ".github" / "dependabot.yml"

HOUR = 1
DAY = 24
WEEK = 7 * DAY
MONTH = 30 * DAY

# รอบของ cron ประเมินจากช่องที่ *ไม่ใช่* `*` ที่หยาบที่สุด — พอสำหรับคำถาม
# "มันควรยิงทุกกี่ชั่วโมง" โดยไม่ต้องลาก dependency ตัวแปลง cron เข้ามา
CRON_FIELDS = ("minute", "hour", "dom", "month", "dow")


def _gh(path: str) -> typing.Any:
    """ถาม GitHub API — แยกไว้จุดเดียวให้เทสต์ปลอมได้ และให้ข้อผิดพลาดสิทธิ์ดังพอ"""
    binary = shutil.which("gh")
    if not binary:
        raise RuntimeError("ไม่มี gh บนเครื่องนี้ — ตัวตรวจนี้ต้องถาม GitHub API ผ่านมัน")
    result = subprocess.run(  # noqa: S603 — path มาจาก shutil.which และ argument เป็นของเราเอง
        [binary, "api", path],
        capture_output=True,
        text=True,
        check=False,
        timeout=NETWORK_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise PermissionError(f"อ่าน {path} ไม่ได้: {result.stderr.strip()}")
    return json.loads(result.stdout)


def period_hours(cron: str) -> int:
    """รอบโดยประมาณของ cron หนึ่งบรรทัด เป็นชั่วโมง

    อ่านจากช่องที่หยาบที่สุดที่ถูกตรึงไว้: ตรึงวันในสัปดาห์ = ทุกสัปดาห์ ·
    ตรึงวันที่ = ทุกเดือน · ตรึงชั่วโมง = ทุกวัน · ที่เหลือ = ทุกชั่วโมง
    """
    fields = dict(zip(CRON_FIELDS, cron.split(), strict=False))
    if fields.get("dow", "*") != "*":
        return WEEK
    if fields.get("dom", "*") != "*":
        return MONTH
    if fields.get("hour", "*") != "*":
        return DAY
    return HOUR


def declared_schedules() -> dict[str, int]:
    """ไฟล์ workflow → รอบที่สั้นที่สุดที่มันประกาศไว้ (ชั่วโมง)"""
    found: dict[str, int] = {}
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        crons = workflows.schedules(workflows.load(path))
        if crons:
            found[path.name] = min(period_hours(cron) for cron in crons)
    return found


def dependabot_ecosystems() -> list[str]:
    """ecosystem ที่ประกาศรอบไว้ใน dependabot.yml — ไม่มีทางถามสถานะจริงด้วยเครื่อง"""
    if not DEPENDABOT.is_file():
        return []
    config = yaml.safe_load(DEPENDABOT.read_text(encoding="utf-8")) or {}
    return [
        f"{entry.get('package-ecosystem')} ({(entry.get('schedule') or {}).get('interval')})"
        for entry in config.get("updates", [])
    ]


def fetch(files: typing.Iterable[str]) -> dict:
    """เวลาที่ run ชนิด schedule ล่าสุดของแต่ละไฟล์เกิดขึ้น (None = ไม่เคยเลย)"""
    last: dict[str, str | None] = {}
    for name in files:
        runs = _gh(f"repos/:owner/:repo/actions/workflows/{name}/runs?event=schedule&per_page=1")
        rows = runs.get("workflow_runs") or []
        last[name] = rows[0]["created_at"] if rows else None
    return {"last_scheduled_run": last}


def problems(schedules: dict[str, int], last: dict, now: str, tolerance: int) -> list[str]:
    """ตารางเวลาที่หยุดยิง ต้องดังกว่าตารางเวลาที่ไม่เคยมี"""
    moment = datetime.datetime.fromisoformat(now)
    found = []
    for name, hours in sorted(schedules.items()):
        stamp = last.get(name)
        if stamp is None:
            found.append(
                f"{name}: ประกาศ cron ไว้แต่**ไม่เคยมี run ชนิด schedule เลย** — "
                "workflow ที่ GitHub ปฏิเสธทั้งไฟล์ หรือ schedule ถูกปิดอัตโนมัติ "
                "(repo ที่เงียบเกิน 60 วัน) ให้ผลหน้าตาเหมือนกันทั้งคู่"
            )
            continue
        age = (moment - datetime.datetime.fromisoformat(stamp)).total_seconds() / 3600
        if age > hours * tolerance:
            found.append(
                f"{name}: run ชนิด schedule ล่าสุดเมื่อ {age / 24:.1f} วันที่แล้ว "
                f"แต่ประกาศรอบไว้ทุก {hours / 24:.1f} วัน (เผื่อไว้ {tolerance} เท่าแล้ว) — "
                "ตารางเวลาหยุดยิงคือความเงียบที่หน้าตาเหมือนความสำเร็จ"
            )
    return found


def main(argv: list[str] | None = None) -> int:
    """อ่านตารางที่ประกาศ → ถามว่ายิงจริงครั้งล่าสุดเมื่อไหร่ → คืน 1 ถ้าเงียบเกินรอบ"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="ไฟล์ JSON ของผลที่ดึงมาแล้ว (ข้ามการต่อเน็ต)")
    parser.add_argument("--tolerance", type=int, default=2, help="ยอมให้ช้าได้กี่เท่าของรอบ")
    parser.add_argument("--now", help="เวลาอ้างอิงรูป ISO (สำหรับเทสต์)")
    args = parser.parse_args(argv)

    schedules = declared_schedules()
    if not schedules:
        print("ไม่มี workflow ไหนประกาศ cron ไว้เลย — ไม่มีอะไรต้องเฝ้า")
        return 0

    try:
        state = (
            json.loads(pathlib.Path(args.input).read_text(encoding="utf-8"))
            if args.input
            else fetch(schedules)
        )
    except (PermissionError, RuntimeError) as problem:
        print(
            f"อ่านประวัติ run ไม่ได้: {problem}\n"
            "**ห้ามแปลงกรณีนี้เป็นการข้ามเงียบ ๆ** — ตัวเฝ้าที่เงียบตอนอ่านไม่ได้ "
            "คือตัวที่รายงานว่าทุกตารางยังยิงอยู่ในวันที่มันมองไม่เห็นอะไรเลย",
            file=sys.stderr,
        )
        return 2

    now = args.now or datetime.datetime.now(datetime.UTC).isoformat()
    found = problems(schedules, state.get("last_scheduled_run") or {}, now, args.tolerance)

    for line in dependabot_ecosystems():
        print(f"  ตรวจด้วยเครื่องไม่ได้ (ไม่มี endpoint สาธารณะ): dependabot {line}")

    if found:
        print("ตารางเวลาที่ประกาศไว้กับที่ยิงจริงไม่ตรงกัน:", file=sys.stderr)
        for line in found:
            print(f"  - {line}", file=sys.stderr)
        return 1

    print(f"ตารางเวลาทุกตัวยังยิงอยู่ในรอบที่ประกาศ ({len(schedules)} workflow)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
