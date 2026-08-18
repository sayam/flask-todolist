"""`within_days` ที่เราสัญญาไว้ ทำได้จริงไหม — audit รอบ 11 ข้อ 2

ADR 0066 ให้ทุก gate ที่บล็อกใครไม่ได้ประกาศ `watched_by.within_days` ว่า **ใครเห็น
ภายในกี่วัน** · แต่สิ่งเดียวที่ตรวจมันคือ *รูปแบบ* (เป็นเลข · ไม่เกิน 90) —
คำสัญญาที่ไม่มีเครื่องวัดคือคำสัญญาที่หมดอายุเงียบ

ตัวนี้วัดสิ่งที่วัดได้ด้วยข้อมูลที่มีอยู่แล้ว: **ความแดงยืนอยู่บน `main` นานเท่าไหร่
ก่อนกลับเขียว** โดยจับคู่ "แดงครั้งแรก → เขียวครั้งถัดไป" ของแต่ละ workflow

**เรียกให้ถูก: นี่คือ *ขอบบน* ของเวลาที่ใช้รับรู้+แก้ ไม่ใช่ MTTA** — มันไม่รู้ว่า
คนเห็นตอนไหน รู้แค่ว่าสภาพนั้นยืนอยู่นานแค่ไหน · ขอบบนที่วัดได้มีค่ากว่าตัวเลข
ที่แม่นกว่าแต่ไม่มีใครเก็บ และมันเพียงพอจะตอบคำถามเดียวที่ ADR 0066 ถาม:
เราสัญญาเกินกว่าที่ทำได้หรือเปล่า

วัดครั้งแรก (200 run บน main · 2026-08-14 → 08-18):

    ci.yml         แดงยาวสุด  0.4 ชม.   ← required check
    release.yml    แดงยาวสุด  0.2 ชม.
    scorecard.yml  แดงยาวสุด 14.6 ชม.   ← ไม่ใช่ required check · ต่างกัน 36 เท่า

**รวมด้วย `path` ไม่ใช่ `name`** — run ที่ GitHub ปฏิเสธทั้งไฟล์ถูกตั้งชื่อด้วย
*path ของ workflow* ไม่ใช่ชื่อที่ประกาศใน `name:` การรวมด้วยชื่อจึงตัดประวัติเดียว
ออกเป็นสองก้อนเงียบ ๆ (ฉบับแรกของการวัดนี้ได้ 2.2 ชม. แทนที่จะเป็น 14.6)

**ความละเอียดที่ GitHub ให้คือระดับไฟล์ ไม่ใช่ระดับ job** — ผลของ run เป็นของทั้ง
workflow · ไฟล์ที่มีทั้ง job ที่บล็อกและ job ที่ถูกเฝ้าปนกัน (เช่น `ci.yml`) จึงวัด
คำสัญญาของตัวที่ถูกเฝ้าไม่ได้: ตัวเลขจะถูกครอบด้วยความแดงของ job ที่บล็อก ซึ่งถูกแก้
เร็วอยู่แล้วเพราะมันหยุด merge · **ตัวนี้จึงเทียบเฉพาะไฟล์ที่ไม่มี job ไหนรันบน
`pull_request` เลย** (= ทุก job ในไฟล์นั้นบล็อกไม่ได้ตามนิยามของ ADR 0066) ที่เหลือ
พิมพ์ตัวเลขไว้ให้อ่าน แต่ไม่เอาไปตัดสิน — เขียวที่ไม่ได้แปลว่าอะไร แย่กว่าไม่วัด

ใช้:
    python3 scripts/red_streak_census.py                 # ดึงสดผ่าน gh
    python3 scripts/red_streak_census.py --input x.json  # ตัดสินจากไฟล์ (ออฟไลน์)
"""

from __future__ import annotations

import argparse
import collections
import datetime
import json
import pathlib
import shutil
import subprocess
import sys
import typing

# pyyaml มากับ dev tools และไม่มี stub — เหตุผลเดียวกับ build_gates_crosswalk.py
import yaml  # type: ignore[import-untyped]

ROOT = pathlib.Path(__file__).resolve().parent.parent

# **เพดานเวลาของคำสั่งที่เรายิงออกไป** (ADR 0067) — `subprocess.run` ที่ไม่มี
# `timeout=` รอตลอดกาล ซึ่งกลายเป็น job ที่ไม่มีวันจบเมื่อรันใน CI
NETWORK_TIMEOUT_SECONDS = 60

GATES = ROOT / "gates.yaml"
WORKFLOWS = ROOT / ".github" / "workflows"
PAGE_SIZE = 100
HOURS_PER_DAY = 24


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


def promised_days() -> dict[str, int]:
    """ไฟล์ workflow → จำนวนวันที่ **สั้นที่สุด** ที่ gate ในไฟล์นั้นสัญญาไว้

    สั้นที่สุดเพราะไฟล์เดียวถือได้หลาย gate และคำสัญญาที่แคบที่สุดคือคำสัญญาที่
    ผิดก่อน — ผ่านตัวนั้นแล้วตัวอื่นผ่านตามโดยอัตโนมัติ
    """
    owner: dict[str, str] = {}
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        triggers = workflow.get(True) or workflow.get("on") or {}
        # ไฟล์ที่รันบน pull_request มี job ที่บล็อกได้ปนอยู่ — ผลของ run เป็นของ
        # ทั้งไฟล์ ตัวเลขจึงตอบคำถามของ job ที่ถูกเฝ้าไม่ได้ (ดูหัวไฟล์)
        if "pull_request" in (triggers if isinstance(triggers, dict) else {triggers: None}):
            continue
        for job in workflow.get("jobs") or {}:
            owner[job] = f".github/workflows/{path.name}"

    promised: dict[str, int] = {}
    for gate in yaml.safe_load(GATES.read_text(encoding="utf-8"))["gates"]:
        watcher = gate.get("watched_by")
        job = (gate.get("enforced_by") or {}).get("job")
        if not watcher or job not in owner:
            continue
        days = int(watcher["within_days"])
        promised[owner[job]] = min(promised.get(owner[job], days), days)
    return promised


def longest_red_hours(runs: list[dict]) -> dict[str, float]:
    """ไฟล์ workflow → ช่วงที่แดงยาวที่สุด (ชั่วโมง)

    **รวมด้วย `path`** เพราะ run ที่ไม่ได้ start ถูกตั้งชื่อด้วย path ไม่ใช่ `name`
    ช่วงที่ยัง**แดงค้างอยู่ตอนนี้** นับถึง run ล่าสุดที่เห็น ไม่ใช่ปล่อยหายไป —
    ความแดงที่ยังไม่จบคือความแดงที่ยาวที่สุดเสมอเมื่อมองจากตอนนี้
    """
    grouped: dict[str, list[tuple[str, str | None]]] = collections.defaultdict(list)
    for run in runs:
        grouped[str(run.get("path") or "?")].append((str(run["created_at"]), run.get("conclusion")))

    newest = max((run["created_at"] for run in runs), default=None)
    longest: dict[str, float] = {}
    for path, rows in grouped.items():
        rows.sort()
        started: datetime.datetime | None = None
        worst = 0.0
        for stamp, conclusion in rows:
            moment = datetime.datetime.fromisoformat(stamp)
            if conclusion == "failure" and started is None:
                started = moment
            elif conclusion == "success" and started is not None:
                worst = max(worst, (moment - started).total_seconds() / 3600)
                started = None
        if started is not None and newest:
            still = (datetime.datetime.fromisoformat(newest) - started).total_seconds() / 3600
            worst = max(worst, still)
        longest[path] = round(worst, 1)
    return longest


def problems(promised: dict[str, int], measured: dict[str, float]) -> list[str]:
    """สัญญาไว้กี่วัน แล้วของจริงยืนอยู่นานกว่านั้นไหม"""
    found = []
    for path, days in sorted(promised.items()):
        hours = measured.get(path)
        if hours is None:
            continue  # ไม่มี run ในหน้าต่างที่ดึงมา — เป็นคำถามของ schedule_census
        if hours > days * HOURS_PER_DAY:
            found.append(
                f"{path}: ความแดงเคยยืนอยู่ {hours / HOURS_PER_DAY:.1f} วัน "
                f"แต่ `watched_by` สัญญาไว้ว่าจะเห็นภายใน {days} วัน — "
                "แก้ที่ใดที่หนึ่งในสองข้าง: ทำให้เห็นเร็วขึ้น หรือเลิกสัญญาเกินจริง"
            )
    return found


def main(argv: list[str] | None = None) -> int:
    """วัดความยาวของช่วงแดง → เทียบกับที่สัญญาไว้ · คืน 1 เมื่อสัญญาเกินจริง"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="ไฟล์ JSON ของ run (ข้ามการต่อเน็ต)")
    parser.add_argument("--limit", type=int, default=200, help="จำนวน run บน main ที่ดึงมา")
    args = parser.parse_args(argv)

    try:
        if args.input:
            runs = json.loads(pathlib.Path(args.input).read_text(encoding="utf-8"))
        else:
            runs = []
            page = 1
            while len(runs) < args.limit:
                size = min(PAGE_SIZE, args.limit - len(runs))
                batch = _gh(
                    f"repos/:owner/:repo/actions/runs?branch=main&per_page={size}&page={page}"
                ).get("workflow_runs", [])
                if not batch:
                    break
                runs += batch
                page += 1
    except (PermissionError, RuntimeError) as problem:
        print(
            f"อ่านประวัติ run ไม่ได้: {problem}\n"
            "**ห้ามแปลงกรณีนี้เป็นการข้ามเงียบ ๆ** — ตัววัดที่เงียบตอนอ่านไม่ได้ "
            "คือตัวที่รายงานว่าทุกคำสัญญายังทำได้อยู่ในวันที่มันมองไม่เห็นอะไรเลย",
            file=sys.stderr,
        )
        return 2

    measured = longest_red_hours(runs)
    promised = promised_days()
    for path, hours in sorted(measured.items()):
        bound = promised.get(path)
        note = f"สัญญาไว้ {bound} วัน" if bound else "ไม่มี gate ที่ประกาศผู้เฝ้า (บล็อกอยู่แล้ว)"
        print(f"  {path:35s} แดงยาวสุด {hours:6.1f} ชม. · {note}")

    found = problems(promised, measured)
    if found:
        print("คำสัญญาที่ทำไม่ได้จริง:", file=sys.stderr)
        for line in found:
            print(f"  - {line}", file=sys.stderr)
        return 1

    print(f"ทุกคำสัญญาของ `watched_by` ยังทำได้จริง ({len(promised)} workflow ที่มีผู้เฝ้า)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
