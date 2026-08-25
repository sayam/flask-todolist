"""ท่าทีฝั่งแพลตฟอร์มต้องถูกเครื่องตรวจ ไม่ใช่แค่ประกาศไว้ในเอกสาร — ADR 0061

ADR 0053 ประกาศว่า main รับของทาง PR เท่านั้น · `enforce_admins` เปิด · required
check ครบทุก job ที่รันบน pull request — **ทั้งหมดนี้เป็น setting ฝั่ง GitHub
ที่ไม่มีอะไรในเรโปตรวจเลย** (audit รอบ 7) · กดปิดในหน้า settings หรือ GitHub
เปลี่ยนพฤติกรรมเมื่อไหร่ เอกสารก็ยังอ้างเหมือนเดิมโดยไม่มีใครรู้ · ตัวควบคุมที่
ด่านอื่นทุกตัวพิงอยู่ จึงเป็นตัวเดียวที่ไม่มีใครเฝ้า

ตรวจสามอย่างที่คนละแหล่ง:

1. **required check ครบสามทิศ** — job ที่รันบน pull request ทุกตัวต้องอยู่ในรายการ
   บังคับ · รายการบังคับต้องไม่มีชื่อผี (context ที่ไม่มี job ไหนสร้างได้ = PR รอ
   check ที่ไม่มีวันมา) · และ **check ที่ repo ผลิตได้แต่ไม่ถูกบังคับ ต้องถูก
   ประกาศไว้พร้อมเหตุผล** (ADR 0066 — ทิศที่สามเพิ่มตอน audit รอบ 10: ทะเบียน
   `EXEMPT` มีมาก่อนแล้วแต่ถูกใช้กรองเซตที่มันไม่มีทางอยู่ในนั้น จึงไม่เคยถูก
   ปรึกษาเลยสักครั้ง — แฟ้มข้อยกเว้นที่ไม่มีใครอ่าน คือไฟล์ข้อความ)
2. **ธงของ branch protection** — enforce_admins · linear history · ห้าม force push
   และห้ามลบ branch
3. **สวิตช์ระดับ repo** — auto-merge (วิธี merge มาตรฐานของทุก PR) และ
   `sha_pinning_required` ที่ให้แพลตฟอร์มบังคับสิ่งที่เทสต์เราบังคับอยู่แล้ว
4. **alert บนหน้า Security** — ทุกใบที่โผล่ (เปิดอยู่ก็ตาม ถูก dismiss ไปแล้วก็ตาม)
   ต้องมีบรรทัดใน `.github/accepted-code-scanning-alerts.txt` และทุกบรรทัดในนั้น
   ต้องยังตรงกับ alert จริง — **สองทิศ แบบเดียวกับ `audit_pins.py`** (audit รอบ 10
   ข้อ 3: คำตัดสินอยู่ในเรโปครบแล้ว แต่พื้นผิวที่คนนอกอ่านก่อนเพื่อนยังค้างว่า
   "high · เปิดอยู่" 4 ใบนาน 5.6 วัน โดยไม่มีรอบทบทวนไหนครอบ — แถวที่มีอยู่
   ครอบเฉพาะ alert ที่ถูก dismiss แล้ว)

**สิทธิ์ไม่พอ = แดง ไม่ใช่ข้าม** — ด่านที่ข้ามเงียบ ๆ ตอนอ่านไม่ได้ คือด่านที่
รายงานว่าทุกอย่างเรียบร้อยในวันที่มันมองไม่เห็นอะไรเลย

ใช้:
    python3 scripts/audit_posture.py                 # ถาม GitHub ผ่าน gh
    python3 scripts/audit_posture.py --input x.json  # ตัดสินจากไฟล์ (ออฟไลน์)

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
import typing
import urllib.error
import urllib.request

# pyyaml มากับ dev tools และไม่มี stub — เหตุผลเดียวกับ build_gates_crosswalk.py
import yaml  # type: ignore[import-untyped] - library lacks type stubs

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import workflows as gha

ROOT = pathlib.Path(__file__).resolve().parent.parent

# **เพดานเวลาของคำสั่งที่เรายิงออกไป** (audit รอบ 11 · ADR 0067) — `subprocess.run`
# ที่ไม่มี `timeout=` รอตลอดกาล และเครื่องมือพวกนี้รันอยู่ใน job ของ CI ผลคือ
# `gh` ที่ไม่ตอบกลายเป็น job ที่กินเพดานของ job ไปทั้งก้อนโดยไม่ทำอะไรเลย
NETWORK_TIMEOUT_SECONDS = 60  # หนึ่งคำขอไป GitHub API
WORKFLOWS = ROOT / ".github" / "workflows"
CADENCE = ROOT / "docs" / "SECURITY-CADENCE.md"
AUDIT_LOG = ROOT / "docs" / "AUDIT-LOG.md"
GATES_FILE = ROOT / "gates.yaml"
ADR_DIR = ROOT / "docs" / "adr"
# แถวของทะเบียนรอบ audit — ขึ้นต้นด้วยเลขรอบ (รูปเดียวกับ tests/test_audit_log.py)
AUDIT_ROW = re.compile(r"^\|\s*(\d+)\s*\|", re.MULTILINE)
ALERT_REGISTER = ROOT / ".github" / "accepted-code-scanning-alerts.txt"

# **alert อ่านด้วย token คนละใบกับท่าที** — `POSTURE_TOKEN` เป็น fine-grained PAT
# ที่มีแค่ Administration+Metadata (อ่าน branch protection) ส่วน code scanning
# ต้องการ `security-events: read` ซึ่ง `GITHUB_TOKEN` ของ job ขอเองได้ฟรี —
# ขยาย scope ของ PAT เพื่ออ่าน alert คือการจ่ายสิทธิ์ถาวรให้ของที่ยืมได้ต่อ run
ALERTS_ENV = "GH_TOKEN_ALERTS"
PAGE_SIZE = 100

# job ที่ไม่ต้องอยู่ในรายการ required — พร้อมเหตุผลที่ต้องอ่านได้จากที่นี่ที่เดียว
EXEMPT = {
    "release-sign": "รันตอนออก release ไม่ใช่บน pull request — บังคับแล้ว PR จะรอตลอดกาล",
    "scorecard": "เป็นคะแนนไม่ใช่ผ่าน/ตก และไม่รันบน pull request (ADR 0039 · หัวไฟล์ scorecard.yml)",
    # **ตัวเองก็อยู่ในรายการนี้** — และมันหายไปจนถึง audit รอบ 10 ซึ่งเป็นหลักฐาน
    # ตรงตัวว่าทะเบียนที่ไม่มีใครอ่านไม่ครบเสมอ: job นี้เกิดตอนรอบ 9 แล้วไม่มีอะไร
    # ทวงให้มาลงทะเบียน เพราะทิศที่ปรึกษา EXEMPT ยังไม่มี
    "posture": "อ่านสถานะระดับ repo (branch protection ของ main) ไม่ใช่ของ commit — "
    "รันบน PR แล้วจะแดง/เขียวตามสิ่งที่ PR นั้นไม่ได้แตะ (ADR 0066)",
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


def _request(path: str, token_env: str | None = None) -> typing.Any:
    """ถาม GitHub API — แยกไว้จุดเดียวให้เทสต์ปลอมได้ และให้ข้อผิดพลาดสิทธิ์ดังพอ

    `token_env` ชี้ตัวแปรที่ถือ token ของ *คำถามนั้น* — ไม่ตั้งหรือไม่มีค่าก็ตกกลับ
    ไปใช้ token เริ่มต้นของ `gh` ซึ่งคือสิ่งที่เกิดตอนรันบนเครื่องผู้ดูแล
    """
    binary = shutil.which("gh")
    if not binary:
        raise RuntimeError("ไม่มี gh บนเครื่องนี้ — ตัวตรวจนี้ต้องถาม GitHub API ผ่านมัน")
    env = None
    borrowed = os.environ.get(token_env or "")
    if borrowed:
        env = {**os.environ, "GH_TOKEN": borrowed, "GITHUB_TOKEN": borrowed}
    result = subprocess.run(  # noqa: S603 — path มาจาก shutil.which และ argument เป็นของเราเอง
        [binary, "api", path],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=NETWORK_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise PermissionError(f"อ่าน {path} ไม่ได้: {result.stderr.strip()}")
    return json.loads(result.stdout)


def _gh(path: str) -> dict:
    """คำตอบที่เป็น object เดียว"""
    return dict(_request(path))


def _gh_pages(path: str, token_env: str | None = None) -> list[dict]:
    """คำตอบที่เป็นรายการ — **ไล่ทีละหน้า** เพราะ `per_page` ของ GitHub ตันที่ 100

    audit รอบ 9 เจอมาแล้วว่าการขอเกิน 100 ได้ 100 มาเงียบ ๆ ตัวตรวจที่อ่านหน้าเดียว
    จึงประกาศว่า "ไม่มี alert ค้าง" ได้ทั้งที่ใบที่ 101 ค้างอยู่
    """
    rows: list[dict] = []
    page = 1
    while True:
        joiner = "&" if "?" in path else "?"
        batch = _request(f"{path}{joiner}per_page={PAGE_SIZE}&page={page}", token_env)
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            return rows
        page += 1


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
        if not gha.runs_on(workflow, "pull_request"):
            continue
        for key, job in gha.jobs(workflow).items():
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


def all_checks(workflows: dict[str, dict]) -> set[str]:
    """ชื่อ check **ทุกตัวที่ repo นี้ผลิตได้** ไม่ว่าจะรันบนทริกเกอร์ไหน"""
    names: set[str] = set()
    for workflow in workflows.values():
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


def unrequired_problems(produced: set[str], required: set[str]) -> list[str]:
    """check ที่ไม่ถูกบังคับ ต้องถูกประกาศไว้ — และรายการที่ประกาศต้องยังมีของจริง

    ทิศนี้คือตัวที่ทำให้ `EXEMPT` ถูกอ่านจริง (ADR 0066) · ก่อนหน้านี้มันถูกใช้
    กรองเซต "job ที่รันบน PR แต่ไม่ถูกบังคับ" ซึ่งสมาชิกของมันไม่มีทางอยู่ในนั้น
    ผลคือทะเบียนที่อ่านแล้วเข้าใจว่ามีการบังคับอยู่ แต่ไม่เคยถูกปรึกษาสักครั้ง
    """
    bare = {name.split(" (")[0] for name in produced - required}
    undeclared = sorted(bare - set(EXEMPT))
    problems = []
    if undeclared:
        problems.append(
            f"check ที่ไม่ได้ถูกบังคับและไม่ได้ประกาศไว้: {undeclared} — "
            "บังคับมัน หรือประกาศใน EXEMPT พร้อมเหตุผล และให้ gate ของมันมี watched_by "
            "(ADR 0066: ด่านที่ไม่บล็อกใครไม่ผิด แต่ต้องบอกได้ว่าใครเห็นและภายในกี่วัน)"
        )

    everything = {name.split(" (")[0] for name in produced}
    problems += [
        f"EXEMPT ยกเว้น {job!r} ไว้ แต่ไม่มี job ชื่อนี้แล้ว — ถอดออก"
        for job in sorted(set(EXEMPT) - everything)
    ]
    return problems


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
    # **เทียบเฉพาะที่อ่านได้** — `None` แปลว่าสิทธิ์ไม่พอ ไม่ใช่ว่าปิดอยู่
    problems.extend(
        f"{flag} = {state.get(flag)!r} แต่ทะเบียน merge setting ประกาศไว้ว่า {want!r}"
        for flag, (want, _why) in MERGE_SETTINGS.items()
        if state.get(flag) is not None and state.get(flag) != want
    )
    # **เทียบเฉพาะที่อ่านได้** เหมือนกลุ่มบน — `None` = สิทธิ์ไม่พอ ไม่ใช่ปิดอยู่
    problems.extend(
        f"{flag} = {state.get(flag)!r} แต่ทะเบียนท่าทีของ Actions ประกาศไว้ว่า {want!r} ({why})"
        for flag, (want, why) in ACTIONS_FLAGS.items()
        if state.get(flag) is not None and state.get(flag) != want
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
#
# **แต่ "อ่านไม่ได้ที่นี่" ไม่ใช่เหตุผลที่จะไม่ประกาศว่าค่าควรเป็นอะไร** (5-Why
# ของ branch ค้าง 64 ใบ · 2026-08-21): `delete_branch_on_merge` ตกจากแผนที่ไป
# ทั้งใบเพราะมันอยู่ในคลาสนี้ — ทะเบียนเดิมบันทึกว่า *เครื่องมองไม่เห็นอะไร*
# แต่ไม่มีที่ไหนบันทึกว่า *ค่าที่ควรเป็นคืออะไร* setting ที่พิสูจน์ไม่ได้จึงไม่มี
# เจ้าของ และ setting ที่ไม่มีเจ้าของก็ไม่มีค่าตั้งต้น · ผลคือกติกาข้อ 7 ของ
# CONTRIBUTING ถูกบังคับด้วยความจำของคนคนเดียว แล้วลืมไป 30 กว่าครั้งติดกัน
#
# ทะเบียนนี้จึงถือ **ค่าที่ควรเป็น** ด้วย · ตัวตัดสินใช้มันสองจังหวะ: เทียบจริง
# เมื่ออ่านได้ (คนที่มีสิทธิ์รันเอง) และรายงานว่า "ควรเป็นอะไร" เมื่ออ่านไม่ได้
# (CI ที่สิทธิ์ต่ำสุด) — ค่าที่ประกาศไว้จึงมีคนตรวจได้เสมอ แค่ไม่ใช่ทุกที่
#
# ที่ *ไม่* อยู่ในทะเบียนโดยตั้งใจ: `merge_commit_title`/`merge_commit_message`
# (มีผลเฉพาะเมื่อเปิด merge commit ซึ่งปิดอยู่) · `squash_merge_commit_*` และ
# `use_squash_pr_title_as_default` (มีผลเฉพาะเมื่อเปิด squash ซึ่งปิดแล้ว) ·
# `allow_update_branch` (ไม่มีกติกาข้อไหนพึ่งมัน)
MERGE_SETTINGS = {
    "allow_auto_merge": (True, "วิธี merge มาตรฐานของทุก PR (CONTRIBUTING ข้อ 7)"),
    "delete_branch_on_merge": (
        True,
        (
            "ปิดแล้ว branch ที่ merge ไปกองค้าง — และ `git branch --merged` มองไม่เห็น "
            "เพราะ rebase เขียน commit ใหม่ ทำให้ไม่มีใครสังเกตจนกองถึง 64 ใบ"
        ),
    ),
    "allow_merge_commit": (False, "ประวัติต้องเป็นเส้นเดียว (คู่กับ required_linear_history)"),
    "allow_rebase_merge": (True, "ทางเดียวที่ ADR 0053 กับ CONTRIBUTING ข้อ 7 รับ"),
    "allow_squash_merge": (
        False,
        (
            "CONTRIBUTING ข้อ 7 ห้ามไว้ตรง ๆ — squash ต่อ ` (#N)` ท้าย subject แล้วดัน "
            "เกิน 72 ตัว และ commit-lint ที่จะจับได้รันหลังของลง main ไปแล้ว · "
            "`required_linear_history` ไม่กันให้เพราะ squash ก็ให้ประวัติเส้นเดียว"
        ),
    ),
}

# ท่าทีของ Actions มาจากสอง endpoint — `actions/permissions` (ตัวแรก) กับ
# `actions/permissions/workflow` (สองตัวหลัง) · สองตัวหลังคือสิ่งที่ Scorecard
# เรียกว่า Token-Permissions และเป็นชั้นที่รองรับตอนมี workflow ไหนลืมประกาศ
# `permissions:` ของตัวเอง — **ทั้งคู่อยู่ใน endpoint ที่ตัวตรวจนี้เรียกอยู่แล้ว
# ตั้งแต่วันแรก แต่ไม่เคยถูกอ่าน** (audit รอบ 24: อ่าน 12 จาก 75 ฟิลด์ที่ถืออยู่
# ในมือ — ขอบเขตของด่านสืบทอดคำถามที่สร้างมันขึ้นมา ไม่ใช่สิ่งที่มันมองเห็นได้)
ACTIONS_FLAGS: dict[str, tuple[object, str]] = {
    "sha_pinning_required": (True, "ให้แพลตฟอร์มบังคับสิ่งที่ gate actions-sha-pinned บังคับอยู่แล้ว"),
    "default_workflow_permissions": ("read", "GITHUB_TOKEN เริ่มที่อ่านอย่างเดียว · job ที่ต้องเขียนขอเอง"),
    "can_approve_pull_request_reviews": (False, "workflow อนุมัติ PR แทนคนไม่ได้ — ทางเข้า main ที่ไม่มีคนดู"),
}


def judged_fields() -> set[str]:
    """ฟิลด์ที่ตัวตรวจนี้ **ตัดสิน** — `docs/EXTERNAL-SURFACE.md` ผูกสองทิศกับรายการนี้

    ทะเบียนที่ drift จากตัวตรวจ อ่านแล้วเข้าใจผิดกว่าไม่มีทะเบียนเลย (ADR 0072)
    """
    return {
        "required_checks",
        "alerts",
        "description",
        *EXPECTED_FLAGS,
        *MERGE_SETTINGS,
        *ACTIONS_FLAGS,
    }


UNREADABLE_AT_LEAST_PRIVILEGE = {
    flag: f"ต้องการ contents:write จึงจะเห็น — ควรเป็น {want!r} ({why})"
    for flag, (want, why) in MERGE_SETTINGS.items()
}


def accepted_alerts() -> dict[str, str]:
    """ทะเบียน alert ที่รับไว้ — `<tool>/<rule id>` → เหตุผล"""
    rows = {}
    for line in ALERT_REGISTER.read_text(encoding="utf-8").splitlines():
        body = line.strip()
        if not body or body.startswith("#"):
            continue
        name, _, why = body.partition("#")
        rows[name.strip()] = why.strip()
    return rows


def live_alerts(alerts: list[dict] | None) -> list[dict]:
    """alert ที่ยังมีอยู่จริง — ตัด `fixed` ทิ้ง เพราะมันหายไปด้วยการแก้ ไม่ใช่ด้วยการยกเว้น"""
    return [alert for alert in (alerts or []) if alert.get("state") != "fixed"]


def alert_problems(alerts: list[dict] | None, accepted: dict[str, str]) -> list[str]:
    """alert ทุกใบต้องถูกตัดสินแล้ว และทุกบรรทัดในทะเบียนต้องยังตรงกับของจริง

    "ถูกตัดสินแล้ว" มีสองรูปที่ยอมรับเท่ากัน: มีบรรทัดในทะเบียนของเรา **หรือ**
    ถูก dismiss พร้อมเหตุผลที่ไม่ว่าง — สิ่งที่ห้ามคือใบที่ไม่มีทั้งสองอย่าง
    เพราะนั่นคือ alert ที่นั่งอยู่บนหน้าที่คนนอกอ่านก่อนเพื่อน โดยไม่มีใครเคยอ่าน
    """
    if alerts is None:
        return ["อ่าน alert ของ code scanning ไม่ได้ — ต้องมี `security-events: read`"]

    problems = []
    seen = set()
    # `fixed` = หายไปแล้วเพราะโค้ดถูกแก้ ไม่ใช่เพราะมีคนตัดสิน — ไม่ต้องมีทะเบียน
    # และ**ต้องไม่ถูกนับเป็น "ยังมีอยู่"** ไม่งั้นบรรทัดที่ควรถอดจะอยู่ต่อได้ตลอด
    for alert in live_alerts(alerts):
        name = f"{(alert.get('tool') or {}).get('name')}/{(alert.get('rule') or {}).get('id')}"
        seen.add(name)
        if name in accepted:
            continue
        if alert.get("state") == "dismissed" and (alert.get("dismissed_comment") or "").strip():
            continue
        problems.append(
            f"alert {name} (#{alert.get('number')} · {alert.get('state')}) ยังไม่ถูกตัดสิน — "
            "แก้ หรือ dismiss พร้อมเหตุผล หรือลงทะเบียนใน "
            ".github/accepted-code-scanning-alerts.txt"
        )

    problems.extend(
        f"ทะเบียนยกเว้น alert {name} ไว้ แต่ไม่มี alert ชื่อนี้แล้ว — ถอดบรรทัดออก "
        "(การยกเว้นเงียบเสมอเมื่อของที่ยกเว้นหายไป)"
        for name in sorted(set(accepted) - seen)
    )
    return problems


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


def advertised_counts(required: int) -> dict[str, int]:
    """เลขทุกตัวที่ช่อง About โฆษณา — นับจากดิสก์หรือจากท่าทีจริงได้ทั้งหมด (ADR 0072)

    ทะเบียนนี้คือคำประกาศว่า *ช่องนั้นโฆษณาอะไรอยู่* — ถอดวลีไหนออกจากช่อง About
    ต้องมาถอดที่นี่ด้วย ซึ่งเป็นคำตัดสินที่มีคนรีวิว ต่างจากการหายไปเงียบ ๆ
    """
    gates = yaml.safe_load(GATES_FILE.read_text(encoding="utf-8"))["gates"]
    audits = AUDIT_ROW.findall(AUDIT_LOG.read_text(encoding="utf-8"))
    return {
        "machine-checked gates": len(gates),
        "ADRs": len(list(ADR_DIR.glob("0*.md"))),
        "recorded governance audits": len(audits),
        "required checks": required,
    }


def description_problems(description: str | None, required: int) -> list[str]:
    """คำโฆษณาบนช่อง About ต้องบอกรุ่นปัจจุบัน **และเลขทุกตัวต้องนับจากของจริงได้**

    **ช่องนี้คือสิ่งแรกที่คนเห็นก่อนกดเข้ามา** และมันไม่ได้อยู่ใน git จึงไม่มี
    diff ไหนทำให้ใครสังเกตว่ามันเก่า — วัดเมื่อ 2026-08-20: ยังเขียนว่า v2.0.0
    ขณะที่รุ่นจริงคือ v2.0.2 (และเลข gate กับจำนวนรอบ audit ก็ค้างมาสองรอบ)

    ฉบับแรกตรวจแค่เลขรุ่น เพราะ "เลขอื่นไม่มีสัญญาว่าจะอยู่ในรูปไหน" —
    **audit รอบ 24 พบว่าเหตุผลนั้นหมดอายุไปแล้ว**: ทั้งสี่เลขมีแหล่งนับที่เป็น
    ทะเบียนจริงหมด (`gates.yaml` · `docs/adr/` · `docs/AUDIT-LOG.md` ที่เพิ่งเกิด
    · และรายการ required check ที่ตัวตรวจนี้ถืออยู่แล้ว) · เลขที่นับได้แต่ไม่มี
    ใครนับ คือเลขที่ค้างจนกว่าจะมีคนบังเอิญสังเกต — ซึ่งตอน v2.2.0 คือสามที่พร้อมกัน
    """
    if description is None:
        return []
    version = (ROOT / "app" / "__init__.py").read_text(encoding="utf-8")
    found = re.search(r'__version__ = "([^"]+)"', version)
    if not found:
        return ["อ่าน __version__ จาก app/__init__.py ไม่ได้"]
    current = found.group(1)

    problems = []
    if f"v{current}" not in description:
        problems.append(
            f"ช่อง About ของ repo ไม่ได้บอกรุ่นปัจจุบัน (v{current}) — ตอนนี้เขียนว่า: {description[:90]!r}"
        )
    for phrase, want in advertised_counts(required).items():
        said = re.search(rf"(\d+) {re.escape(phrase)}", description)
        if said is None:
            problems.append(
                f"ช่อง About เลิกโฆษณา {phrase!r} แล้ว — ถ้าตั้งใจถอด ให้ถอดออกจาก "
                "advertised_counts() ในคอมมิตเดียวกัน ไม่งั้นด่านนี้เฝ้าของที่ไม่มีอยู่"
            )
        elif int(said.group(1)) != want:
            problems.append(f"ช่อง About บอก {said.group(1)} {phrase} แต่ของจริงคือ {want}")
    return problems


# ------------------------------------------- ใบตอบ badge (audit รอบ 27 ข้อ 3)
#
# `docs/SUPPLY-CHAIN.md` มีแถวเดียวที่ตอบว่า "**ไม่มีเครื่องตรวจ**" คือ
# bestpractices.dev — และมันเป็นแถวที่นาฬิกาเป็นของเขาล้วน ๆ: **เขาแก้เกณฑ์ได้
# โดยที่เราไม่ได้ทำอะไร** แล้วคำตอบที่เคยผ่านกลายเป็นไม่ผ่าน badge ลดระดับเงียบ ๆ
# ตัวทวงที่มีคือแถวรอบ **12 เดือน** ซึ่งแปลว่าเลขที่ค้างจะค้างได้นานสุดหนึ่งปี
#
# ตอนตั้งด่านนี้ก็พบของค้างจริงทันที: บรรทัดสถานะเขียน `gold เริ่มนับ 26%`
# ขณะที่เว็บตอบ 57% มาตั้งแต่ v2.1.0
#
# **อ่านอย่างเดียว ไม่ต้องล็อกอิน** — endpoint สาธารณะ · อ่านไม่ได้ = แดง ไม่ใช่ข้าม
# ตามหลักเดียวกับทั้งไฟล์นี้ (job `posture` เป็น `severity: watched` จึงไม่บล็อกใคร)
BEST_PRACTICES_URL = "https://www.bestpractices.dev/projects/14085.json"
BEST_PRACTICES_DOC = ROOT / "docs" / "BEST-PRACTICES.md"
# `| passing | `badge_percentage_0` | 100% |`
BADGE_ROW = re.compile(
    r"^\|\s*([\w-]+)\s*\|\s*`(badge_percentage_[\w]+)`\s*\|\s*(\d+)%\s*\|", re.MULTILINE
)


def advertised_badges() -> dict[str, tuple[str, int]]:
    """ชุด → (ชื่อฟิลด์, เปอร์เซ็นต์) ที่ `docs/BEST-PRACTICES.md` ประกาศ"""
    text = BEST_PRACTICES_DOC.read_text(encoding="utf-8")
    return {name: (field, int(pct)) for name, field, pct in BADGE_ROW.findall(text)}


def badge_problems(answer: dict | None, advertised: dict[str, tuple[str, int]]) -> list[str]:
    """เลขที่เอกสารประกาศ ต้องตรงกับที่เว็บตอบ — และตารางต้องไม่หายไปเงียบ ๆ"""
    if answer is None:
        return [
            (
                f"อ่าน {BEST_PRACTICES_URL} ไม่ได้ — ด่านที่ข้ามตอนอ่านไม่ได้ "
                "คือด่านที่รายงานว่าเลขตรงในวันที่มันไม่เคยอ่านอะไรเลย"
            )
        ]
    if not advertised:
        return [
            (
                "docs/BEST-PRACTICES.md ไม่มีตารางเปอร์เซ็นต์ที่เครื่องอ่านได้แล้ว — "
                "ถ้าตั้งใจถอด ให้ถอดด่านนี้ออกในคอมมิตเดียวกัน ไม่งั้นมันเขียวโดยไม่ได้ตรวจอะไร"
            )
        ]
    found = []
    for name, (field, said) in sorted(advertised.items()):
        if field not in answer:
            found.append(f"ใบตอบ badge ไม่มีฟิลด์ {field} แล้ว (แถว {name}) — เกณฑ์ของเขาเปลี่ยนรูป")
        elif int(answer[field]) != said:
            found.append(f"badge {name}: เอกสารบอก {said}% แต่เว็บตอบ {answer[field]}%")
    return found


def best_practices() -> dict | None:
    """ใบตอบ badge — `None` เมื่ออ่านไม่ได้ (ตัวเรียกเป็นคนตัดสินว่าจะดังแค่ไหน)

    ปลายทางเป็นค่าคงที่ `https://` ในไฟล์นี้ ไม่มีอินพุตจากใครมาประกอบเป็น URL
    จึงไม่ต้องปิดเครื่องตรวจข้อไหนเลย
    """
    try:
        with urllib.request.urlopen(BEST_PRACTICES_URL, timeout=NETWORK_TIMEOUT_SECONDS) as answer:
            return dict(json.loads(answer.read()))
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def fetch() -> dict:
    """รวมท่าทีจากสี่ endpoint ให้เป็นก้อนเดียวที่ตัวตัดสินอ่านได้"""
    protection = _gh("repos/:owner/:repo/branches/main/protection")
    repo = _gh("repos/:owner/:repo")
    actions = _gh("repos/:owner/:repo/actions/permissions")
    workflow = _gh("repos/:owner/:repo/actions/permissions/workflow")
    alerts = _gh_pages("repos/:owner/:repo/code-scanning/alerts?state=all", ALERTS_ENV)
    return {
        "alerts": alerts,
        "required_checks": (protection.get("required_status_checks") or {}).get("contexts", []),
        "enforce_admins": (protection.get("enforce_admins") or {}).get("enabled"),
        "required_linear_history": (protection.get("required_linear_history") or {}).get("enabled"),
        "allow_force_pushes": (protection.get("allow_force_pushes") or {}).get("enabled"),
        "allow_deletions": (protection.get("allow_deletions") or {}).get("enabled"),
        **{flag: repo.get(flag) for flag in MERGE_SETTINGS},
        "sha_pinning_required": actions.get("sha_pinning_required"),
        "default_workflow_permissions": workflow.get("default_workflow_permissions"),
        "can_approve_pull_request_reviews": workflow.get("can_approve_pull_request_reviews"),
        "description": repo.get("description") or "",
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
            "  · 403/404 = สิทธิ์ไม่พอ → ท่าที: token ที่อ่าน branch protection ได้ "
            "(`POSTURE_TOKEN`) · alert: `permissions: security-events: read` ของ job\n"
            "  · 5xx = GitHub เองมีปัญหา → รันใหม่ ไม่ใช่ปิดด่าน\n"
            "**ห้ามแปลงกรณีนี้เป็นการข้ามเงียบ ๆ ทั้งสองแบบ** — ด่านที่ข้ามตอนอ่านไม่ได้ "
            "คือด่านที่รายงานว่าเรียบร้อยในวันที่มันมองไม่เห็นอะไรเลย",
            file=sys.stderr,
        )
        return 2

    problems = compare(
        state, pull_request_checks(workflows), total_checks(workflows), claimed_counts()
    )
    problems += unrequired_problems(all_checks(workflows), set(state.get("required_checks") or []))
    problems += alert_problems(state.get("alerts"), accepted_alerts())
    problems += description_problems(
        state.get("description"), len(state.get("required_checks") or [])
    )
    problems += badge_problems(best_practices(), advertised_badges())
    if problems:
        print("ท่าทีของแพลตฟอร์มไม่ตรงกับสิ่งที่ประกาศไว้:", file=sys.stderr)
        for line in problems:
            print(f"  - {line}", file=sys.stderr)
        for line in unreadable(state):
            print(f"  หมายเหตุ (ไม่ใช่ข้อผิด): {line}", file=sys.stderr)
        return 1

    print(
        f"ท่าทีตรงกับที่ประกาศ — required {len(state['required_checks'])} check "
        f"· ธงครบตาม ADR 0053 · alert ที่ยังมีอยู่และถูกตัดสินแล้ว "
        f"{len(live_alerts(state.get('alerts')))} ใบ"
    )
    for line in unreadable(state):
        print(f"  หมายเหตุ: {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
