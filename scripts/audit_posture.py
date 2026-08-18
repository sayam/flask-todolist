"""ท่าทีฝั่งแพลตฟอร์มต้องถูกเครื่องตรวจ ไม่ใช่แค่ประกาศไว้ในเอกสาร — ADR 0061

ADR 0053 ประกาศว่า main รับของทาง PR เท่านั้น · `enforce_admins` เปิด · required
check ครบทุก job ที่รันบน pull request — **ทั้งหมดนี้เป็น setting ฝั่ง GitHub
ที่ไม่มีอะไรในเรโปตรวจเลย** (audit รอบ 7) · กดปิดในหน้า settings หรือ GitHub
เปลี่ยนพฤติกรรมเมื่อไหร่ เอกสารก็ยังอ้างเหมือนเดิมโดยไม่มีใครรู้ · ตัวควบคุมที่
ด่านอื่นทุกตัวพิงอยู่ จึงเป็นตัวเดียวที่ไม่มีใครเฝ้า

ตรวจสามอย่างที่คนละแหล่ง:

1. **required check ครบสองทิศ** — job ที่รันบน pull request ทุกตัวต้องอยู่ในรายการ
   บังคับ (ยกเว้นที่ประกาศไว้พร้อมเหตุผล) และรายการบังคับต้องไม่มีชื่อผี
   (context ที่ไม่มี job ไหนสร้างได้ = PR รอ check ที่ไม่มีวันมา)
2. **ธงของ branch protection** — enforce_admins · linear history · ห้าม force push
   และห้ามลบ branch
3. **สวิตช์ระดับ repo** — auto-merge (วิธี merge มาตรฐานของทุก PR) และ
   `sha_pinning_required` ที่ให้แพลตฟอร์มบังคับสิ่งที่เทสต์เราบังคับอยู่แล้ว

**สิทธิ์ไม่พอ = แดง ไม่ใช่ข้าม** — ด่านที่ข้ามเงียบ ๆ ตอนอ่านไม่ได้ คือด่านที่
รายงานว่าทุกอย่างเรียบร้อยในวันที่มันมองไม่เห็นอะไรเลย

ใช้:
    python3 scripts/audit_posture.py                 # ถาม GitHub ผ่าน gh
    python3 scripts/audit_posture.py --input x.json  # ตัดสินจากไฟล์ (ออฟไลน์)
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys

# pyyaml มากับ dev tools และไม่มี stub — เหตุผลเดียวกับ build_gates_crosswalk.py
import yaml  # type: ignore[import-untyped]

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
CADENCE = ROOT / "docs" / "SECURITY-CADENCE.md"

# job ที่ไม่ต้องอยู่ในรายการ required — พร้อมเหตุผลที่ต้องอ่านได้จากที่นี่ที่เดียว
EXEMPT = {
    "release-sign": "รันตอนออก release ไม่ใช่บน pull request — บังคับแล้ว PR จะรอตลอดกาล",
    "scorecard": "เป็นคะแนนไม่ใช่ผ่าน/ตก และไม่รันบน pull request (ADR 0039 · หัวไฟล์ scorecard.yml)",
}

# ธงที่ ADR 0053 ประกาศ — ค่าที่ต้องเป็น ไม่ใช่ค่าที่บังเอิญเป็น
EXPECTED_FLAGS = {
    "enforce_admins": True,
    "required_linear_history": True,
    "allow_force_pushes": False,
    "allow_deletions": False,
}

MATRIX_REF = re.compile(r"\$\{\{\s*matrix\.([a-zA-Z0-9_.]+)\s*\}\}")
# "required check **27 จาก 29**" — เลขที่เอกสารโฆษณา ต้องตรงกับของจริงทั้งคู่
CLAIM = re.compile(r"required check \*\*(\d+) จาก (\d+)\*\*")


def _gh(path: str) -> dict:
    """ถาม GitHub API — แยกไว้จุดเดียวให้เทสต์ปลอมได้ และให้ข้อผิดพลาดสิทธิ์ดังพอ"""
    binary = shutil.which("gh")
    if not binary:
        raise RuntimeError("ไม่มี gh บนเครื่องนี้ — ตัวตรวจนี้ต้องถาม GitHub API ผ่านมัน")
    result = subprocess.run(  # noqa: S603 — path มาจาก shutil.which และ argument เป็นของเราเอง
        [binary, "api", path], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise PermissionError(f"อ่าน {path} ไม่ได้: {result.stderr.strip()}")
    return dict(json.loads(result.stdout))


def _resolve(name: str, combo: object) -> str:
    """แทน `${{ matrix.x.y }}` ในชื่อ job ด้วยค่าจริงของ matrix แถวนั้น"""

    def value(match: re.Match) -> str:
        node = combo
        for part in match.group(1).split(".")[1:] if "." in match.group(1) else []:
            node = node[part] if isinstance(node, dict) else node
        if isinstance(node, dict):
            node = node.get(match.group(1).split(".")[-1], node)
        return str(node)

    return MATRIX_REF.sub(value, name)


def pull_request_checks(workflows: dict[str, dict]) -> set[str]:
    """ชื่อ check ที่ *จะ* ขึ้นบน pull request — matrix นับตามจำนวนแถวเหมือนที่ GitHub ทำ"""
    names: set[str] = set()
    for workflow in workflows.values():
        triggers = workflow.get(True) or workflow.get("on") or {}
        if "pull_request" not in (triggers if isinstance(triggers, dict) else {triggers: None}):
            continue
        for key, job in workflow.get("jobs", {}).items():
            base = job.get("name") or key
            strategy = job.get("strategy") or {}
            matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
            if not matrix:
                names.add(base)
                continue
            names.update(
                _resolve(base, combo) if _resolve(base, combo) != base else f"{base} ({combo})"
                for combos in matrix.values()
                for combo in combos
            )
    return names


def total_checks(workflows: dict[str, dict]) -> int:
    """จำนวน check ทั้งหมดที่ repo นี้ผลิตได้ — ใช้เทียบกับเลขที่เอกสารโฆษณา"""
    total = 0
    for workflow in workflows.values():
        for job in workflow.get("jobs", {}).values():
            strategy = job.get("strategy") or {}
            matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
            total += len(next(iter(matrix.values()))) if matrix else 1
    return total


def compare(
    state: dict, expected: set[str], produced: int, claim: tuple[int, int] | None
) -> list[str]:
    """เทียบท่าทีจริงกับสิ่งที่ประกาศไว้ — คืนรายการปัญหา (ว่าง = ตรงกันหมด)"""
    problems = []
    required = set(state.get("required_checks") or [])

    missing = sorted(name for name in expected - required if name.split(" (")[0] not in EXEMPT)
    if missing:
        problems.append(f"job ที่รันบน PR แต่ไม่ได้ถูกบังคับ: {missing}")

    ghosts = sorted(required - expected)
    if ghosts:
        problems.append(f"required check ที่ไม่มี job ไหนสร้างได้ (PR จะรอตลอดกาล): {ghosts}")

    problems.extend(
        f"{flag} = {state.get(flag)!r} แต่ ADR 0053 ประกาศไว้ว่า {want!r}"
        for flag, want in EXPECTED_FLAGS.items()
        if state.get(flag) != want
    )
    problems.extend(
        f"{flag} = {state.get(flag)!r} — ต้องเปิด (ADR 0061)"
        for flag in ("allow_auto_merge", "sha_pinning_required")
        if state.get(flag) is False
    )

    if claim and claim != (len(required), produced):
        problems.append(
            f"เอกสารโฆษณาว่า required {claim[0]} จาก {claim[1]} "
            f"แต่ของจริงคือ {len(required)} จาก {produced}"
        )
    return problems


# ฟิลด์ที่ GitHub **ไม่คืนให้ token ที่มีสิทธิ์อ่านอย่างเดียว** — เอกสารของ
# endpoint `GET /repos/{owner}/{repo}` ระบุว่า "To view merge-related settings,
# you must have the contents:read and contents:write permissions" · การให้สิทธิ์
# *เขียนโค้ด* แก่ตัวตรวจที่มีหน้าที่อ่านอย่างเดียว แพงกว่าค่าที่ได้จากบูลีนตัวเดียว
# มาก (ADR 0061 โน้ต 2026-08-18) → รายงานเป็น "ตรวจด้วยเครื่องไม่ได้" ไม่ใช่
# "ปิดอยู่" เพราะสองอย่างนั้นต่างกันคนละขั้ว และการรายงานผิดฝั่งคือการโกหก
UNREADABLE_AT_LEAST_PRIVILEGE = {
    "allow_auto_merge": "ต้องการ contents:write จึงจะเห็น — ตรวจด้วยมือตามรอบ cadence",
}


def unreadable(state: dict) -> list[str]:
    """ฟิลด์ที่หายไปจากคำตอบ (None) เพราะสิทธิ์ ไม่ใช่เพราะถูกปิด"""
    return [
        f"{flag} = อ่านไม่ได้ ({why})"
        for flag, why in UNREADABLE_AT_LEAST_PRIVILEGE.items()
        if state.get(flag) is None
    ]


def claimed_counts() -> tuple[int, int] | None:
    """เลขที่ `docs/SECURITY-CADENCE.md` โฆษณาไว้ — ไม่มีก็ไม่เป็นไร แต่มีแล้วต้องตรง"""
    found = CLAIM.search(CADENCE.read_text(encoding="utf-8"))
    return (int(found.group(1)), int(found.group(2))) if found else None


def fetch() -> dict:
    """รวมท่าทีจากสาม endpoint ให้เป็นก้อนเดียวที่ `compare()` อ่านได้"""
    protection = _gh("repos/:owner/:repo/branches/main/protection")
    repo = _gh("repos/:owner/:repo")
    actions = _gh("repos/:owner/:repo/actions/permissions")
    return {
        "required_checks": (protection.get("required_status_checks") or {}).get("contexts", []),
        "enforce_admins": (protection.get("enforce_admins") or {}).get("enabled"),
        "required_linear_history": (protection.get("required_linear_history") or {}).get("enabled"),
        "allow_force_pushes": (protection.get("allow_force_pushes") or {}).get("enabled"),
        "allow_deletions": (protection.get("allow_deletions") or {}).get("enabled"),
        "allow_auto_merge": repo.get("allow_auto_merge"),
        "sha_pinning_required": actions.get("sha_pinning_required"),
    }


def main(argv: list[str] | None = None) -> int:
    """อ่านท่าที → เทียบกับสิ่งที่ประกาศ → รายงาน · คืน 1 เมื่อไม่ตรง · 2 เมื่ออ่านไม่ได้"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="ไฟล์ JSON ของท่าที (ข้ามการต่อเน็ต)")
    args = parser.parse_args(argv)

    workflows = {
        path.name: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in sorted(WORKFLOWS.glob("*.y*ml"))
    }

    try:
        state = (
            json.loads(pathlib.Path(args.input).read_text(encoding="utf-8"))
            if args.input
            else fetch()
        )
    except (PermissionError, RuntimeError) as problem:
        reason = str(problem)
        print(
            f"อ่านท่าทีของ repo ไม่ได้: {reason}\n"
            "  · 403/404 = สิทธิ์ไม่พอ → job ต้องประกาศ `permissions: administration: read` "
            "หรือใช้ token ที่อ่าน branch protection ได้\n"
            "  · 5xx = GitHub เองมีปัญหา → รันใหม่ ไม่ใช่ปิดด่าน\n"
            "**ห้ามแปลงกรณีนี้เป็นการข้ามเงียบ ๆ ทั้งสองแบบ** — ด่านที่ข้ามตอนอ่านไม่ได้ "
            "คือด่านที่รายงานว่าเรียบร้อยในวันที่มันมองไม่เห็นอะไรเลย",
            file=sys.stderr,
        )
        return 2

    problems = compare(
        state, pull_request_checks(workflows), total_checks(workflows), claimed_counts()
    )
    if problems:
        print("ท่าทีของแพลตฟอร์มไม่ตรงกับสิ่งที่ประกาศไว้:", file=sys.stderr)
        for line in problems:
            print(f"  - {line}", file=sys.stderr)
        for line in unreadable(state):
            print(f"  หมายเหตุ (ไม่ใช่ข้อผิด): {line}", file=sys.stderr)
        return 1

    print(f"ท่าทีตรงกับที่ประกาศ — required {len(state['required_checks'])} check · ธงครบตาม ADR 0053")
    for line in unreadable(state):
        print(f"  หมายเหตุ: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
