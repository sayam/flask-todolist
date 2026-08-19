"""preflight — เดินด่านของ CI บนเครื่องตัวเอง โดย **อ่านคำสั่งจาก workflow**

hook ก่อน commit ตรวจ ruff/format/mypy เท่านั้น ส่วน xenon · interrogate ·
coverage floor · diff-cover · การ regenerate ไฟล์ที่ derive มา อยู่ใน CI อย่างเดียว
— ความผิดพลาดคลาสนี้ทำให้ PR แดงสองรอบติดกันมาแล้ว (audit governance รอบ 6)
ทั้งที่ทุกอย่างเขียวบนเครื่องก่อน push

**คำสั่งไม่ได้ถูกลอกมาไว้ที่นี่** (ADR 0039 ห้ามเก็บคำสั่งซ้ำ — ที่ที่สองจะ drift
ทันทีที่มีคนแก้ฝั่งเดียว) ตัวสคริปต์อ่าน workflow ทุกไฟล์ใต้ `.github/workflows/`
แล้วรัน step ของ job ที่ประกาศไว้ตามลำดับเดิม · step ที่รันไม่ได้บนเครื่องถูก
**ข้ามพร้อมเหตุผล** ไม่ใช่หายเงียบ ๆ (หลักเดียวกับ `scripts/run_gates.py`)

**ไฟล์นี้ถูกส่งออกไปกับ overlay ด้วย** (ADR 0063) จึงห้ามผูกกับชื่อ job หรือ
ชื่อไฟล์ workflow ของ repo ใดเป็นการเฉพาะ — job ที่จะเดินมาจาก `scaffold.json`
คีย์ `preflight_jobs` (ไม่มีก็ใช้ค่าเริ่มต้น) และ job ถูกค้นจาก workflow ทุกไฟล์
เพราะชื่อ job ไม่ซ้ำกันข้ามไฟล์อยู่แล้ว

ใช้:
    pipenv run python scripts/preflight.py                 # ทุก job ที่ประกาศไว้
    pipenv run python scripts/preflight.py --only lint     # เฉพาะ job นั้น (ซ้ำได้)
    pipenv run python scripts/preflight.py --base main     # ฐานของ diff-cover

บทบาท: decider — ตัดสินผ่าน/ไม่ผ่าน — หลักฐานคือเทสต์ที่ฝังความผิดแล้วต้องจับได้ · ของสะอาดต้องไม่ถูกจับ
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

# pyyaml มากับ dev tools และไม่มี stub — เหตุผลเดียวกับ build_gates_crosswalk.py
import yaml  # type: ignore[import-untyped]

# **เพดานเวลาของคำสั่งที่เรายิงออกไป** (audit รอบ 11 · ADR 0067) — `subprocess.run`
# ที่ไม่มี `timeout=` รอตลอดกาล ซึ่งกลายเป็น job ที่ไม่มีวันจบเมื่อรันใน CI
STEP_TIMEOUT_SECONDS = 3600  # หนึ่ง step ของ workflow — ชุดเต็ม + coverage อยู่ในนี้

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW_DIR = pathlib.Path(".github") / "workflows"
CONFIG = "scaffold.json"

# job ที่เดินเมื่อ config ไม่ได้บอก — job อื่นมักต้องใช้ docker/service/secret ของ CI
DEFAULT_JOBS = ("lint", "test")

# step ที่ข้ามบนเครื่อง พร้อมเหตุผลที่ต้องพิมพ์ออกมาเสมอ
SKIP_RUNS = (
    ("pip install", "ติดตั้งเครื่องมือของ runner — บนเครื่องมี venv ของ pipenv อยู่แล้ว"),
    ("pipenv sync", "จัดสภาพแวดล้อม ไม่ใช่ด่าน — และมันแก้ .venv ของคนรัน"),
)

EXPRESSION = re.compile(r"\$\{\{[^}]*\}\}")


def _substitute(text: str, base: str, temp: str) -> str:
    """แทนค่า expression ของ CI ที่มีของเทียบเท่าบนเครื่อง — ที่เหลือปล่อยให้ผู้เรียกข้าม"""
    return text.replace("${{ github.base_ref }}", base).replace("${{ runner.temp }}", temp)


def _label(step: dict) -> str:
    """ชื่อที่พิมพ์ให้คนอ่าน — ใช้ name ถ้ามี ไม่งั้นใช้บรรทัดแรกของคำสั่ง"""
    if step.get("name"):
        return str(step["name"])
    lines = str(step.get("run") or step.get("uses") or "?").strip().splitlines()
    return lines[0][:70] if lines else "?"


def jobs_on_disk(root: pathlib.Path) -> dict[str, dict]:
    """job → นิยามของมัน จาก workflow **ทุกไฟล์** — ชื่อ job ไม่ซ้ำข้ามไฟล์อยู่แล้ว"""
    found: dict[str, dict] = {}
    for path in sorted((root / WORKFLOW_DIR).glob("*.y*ml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        found.update(workflow.get("jobs") or {})
    return found


def wanted_jobs(root: pathlib.Path, chosen: list[str]) -> tuple[str, ...]:
    """job ที่จะเดิน — บรรทัดคำสั่งชนะ config และ config ชนะค่าเริ่มต้น"""
    if chosen:
        return tuple(chosen)
    config = root / CONFIG
    if config.is_file():
        declared = json.loads(config.read_text(encoding="utf-8")).get("preflight_jobs")
        if declared:
            return tuple(declared)
    return DEFAULT_JOBS


def plan(workflow: dict, jobs: tuple[str, ...], base: str, temp: str | None = None) -> list[dict]:
    """แปลง step ของ job ที่เลือก เป็นรายการ 'รัน' หรือ 'ข้ามพร้อมเหตุผล'

    ทุก step ต้องปรากฏในผลลัพธ์พอดีหนึ่งครั้ง — preflight ที่ทิ้ง step เงียบ ๆ
    ให้ความมั่นใจผิดชนิดเดียวกับ harness ที่รายงานผ่านตอนเทสต์แดง

    **`env:` ของ step เป็นส่วนหนึ่งของคำสั่ง ไม่ใช่ของประกอบ** (audit รอบ 17) —
    ตอนที่ยังทิ้งไป step ที่วัด coverage ของ `scripts/` เขียนทับ `.coverage` ของ
    แอปบนเครื่อง ทั้งที่ CI ตั้ง `COVERAGE_FILE` ไว้นอก workspace เพื่อกันเรื่องนี้
    โดยเฉพาะ · preflight ที่รันคำสั่งเดียวกันใน**สภาพแวดล้อมคนละชุด** คือ preflight
    ที่ตอบคำถามอื่นกับที่ CI ถาม
    """
    temp = tempfile.gettempdir() if temp is None else temp
    made: list[dict] = []
    for job in jobs:
        for step in workflow["jobs"][job]["steps"]:
            entry = {"job": job, "label": _label(step)}
            command = step.get("run")
            if command is None:
                uses = step.get("uses", "?")
                made.append({**entry, "skip": f"เป็น action ({uses}) — ตัวตัดสินคือรุ่นใน CI"})
                continue
            head = command.strip()
            skip = next((why for prefix, why in SKIP_RUNS if head.startswith(prefix)), None)
            if skip:
                made.append({**entry, "skip": skip})
                continue
            resolved = _substitute(command, base, temp)
            left = EXPRESSION.search(resolved)
            if left:
                made.append({**entry, "skip": f"มี expression ของ CI ที่แทนค่าไม่ได้: {left.group(0)}"})
                continue
            declared = (step.get("env") or {}).items()
            env = {str(k): _substitute(str(v), base, temp) for k, v in declared}
            unresolved = next((m for v in env.values() if (m := EXPRESSION.search(v))), None)
            if unresolved:
                made.append(
                    {**entry, "skip": f"env มี expression ที่แทนค่าไม่ได้: {unresolved.group(0)}"}
                )
                continue
            made.append({**entry, "run": resolved, "env": env})
    return made


def execute(entries: list[dict], root: pathlib.Path) -> int:
    """รันตามแผน พิมพ์ผลทีละบรรทัด — คืนจำนวน step ที่แดง"""
    # runner ของ GitHub รัน step ด้วย `bash -e {0}` — ที่นี่ต้องเป็น bash ตัวจริง
    # ไม่ใช่ `/bin/sh` ที่ `shell=True` จะให้ (คำสั่งใน workflow เขียนด้วยกติกา bash)
    bash = shutil.which("bash")
    if not bash:
        raise RuntimeError("ไม่มี bash บนเครื่องนี้ — step ของ workflow ต้องใช้ bash")

    failed = 0
    for entry in entries:
        head = f"[{entry['job']}] {entry['label']}"
        if "skip" in entry:
            print(f"–  {head}\n   ข้าม: {entry['skip']}")
            continue
        result = subprocess.run(  # noqa: S603 — คำสั่งมาจาก workflow ของ repo เอง ซึ่งมีด่านคุมอยู่
            [bash, "-e", "-c", entry["run"]],
            cwd=root,
            check=False,
            timeout=STEP_TIMEOUT_SECONDS,
            env={**os.environ, **entry.get("env", {})},
        )
        if result.returncode == 0:
            print(f"✓  {head}")
        else:
            failed += 1
            print(f"✗  {head}  (exit {result.returncode})")
    return failed


def main(argv: list[str] | None = None) -> int:
    """อ่าน workflow → วางแผน → รัน → สรุป (exit 1 ถ้ามีอะไรแดง)"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(REPO_ROOT), help="รากของ tree ที่จะตรวจ")
    parser.add_argument("--base", default="main", help="branch ฐานของ diff-cover")
    parser.add_argument("--only", action="append", default=[], help="เดินเฉพาะ job นี้ (ซ้ำได้)")
    args = parser.parse_args(argv)

    root = pathlib.Path(args.root).resolve()
    workflow = {"jobs": jobs_on_disk(root)}
    jobs = wanted_jobs(root, args.only)
    unknown = [j for j in jobs if j not in workflow["jobs"]]
    if unknown:
        print(f"ไม่มี job {unknown} ใน {WORKFLOW_DIR}/", file=sys.stderr)
        return 2

    entries = plan(workflow, jobs, args.base)
    failed = execute(entries, root)
    skipped = sum(1 for e in entries if "skip" in e)
    print(f"\nสรุป: {len(entries) - skipped - failed} ผ่าน · {failed} แดง · {skipped} ข้ามพร้อมเหตุผล")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
