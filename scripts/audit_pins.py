"""audit เครื่องมือของ CI ใน `pins/` — และบังคับให้รายการยกเว้นไม่เน่า

job `security` มี pip-audit ของ core และของ `[deploy]` อยู่แล้ว ส่วน `pins/`
เป็น supply chain ก้อนที่สามที่ไม่มีใครดูให้: มันไม่ได้ถูกติดตั้งด้วย
`pipenv sync --dev` จึงไม่อยู่ในรอบของ core และไม่ใช่ไลบรารีของ plugin

**ครอบทั้งสองฝั่ง** — `requirements.txt` ด้วย `pip-audit` และ `package-lock.json`
ด้วย `npm audit` · ด่านที่ครอบภาษาเดียวในไดเรกทอรีที่มีสองภาษา คือด่านที่ชื่อของ
มันชวนให้เข้าใจว่าครอบแล้ว ซึ่งอันตรายกว่าไม่มีด่านเลย

**ทำไมต้องมีรายการยกเว้น** — `semgrep` pin `mcp` ไว้ตายตัว การอัปเกรดตามที่
advisory บอกจึงทำไม่ได้จนกว่า upstream จะขยับ ด่านที่แดงตั้งแต่วันแรกและแดง
ต่อไปเรื่อย ๆ คือด่านที่ถูกปิดเสียงภายในสองสัปดาห์ แล้วของจริงที่โผล่ทีหลัง
ก็ถูกมองข้ามไปด้วย

**ทำไมรายการยกเว้นต้องถูกตรวจย้อนกลับด้วย** — `pip-audit --ignore-vuln` เงียบ
เสมอเมื่อ ID นั้นไม่โผล่แล้ว รายการที่ไม่มีใครถอดจึงค่อย ๆ กลายเป็นรายการที่
ปิดของจริงโดยไม่มีใครรู้ ที่นี่จึงตรวจสองทิศ: **เจอของที่ไม่ได้ยกเว้น = แดง**
และ **ยกเว้นของที่ไม่เจอแล้ว = แดง**

รันเองบนเครื่อง: `PYTHONPATH=. pipenv run python scripts/audit_pins.py`

บทบาท: decider — ตัดสินผ่าน/ไม่ผ่าน — หลักฐานคือเทสต์ที่ฝังความผิดแล้วต้องจับได้ · ของสะอาดต้องไม่ถูกจับ
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# **เพดานเวลาของคำสั่งที่เรายิงออกไป** (audit รอบ 11 · ADR 0067) — `subprocess.run`
# ที่ไม่มี `timeout=` รอตลอดกาล และเครื่องมือพวกนี้รันอยู่ใน job ของ CI ผลคือ
# `gh` ที่ไม่ตอบกลายเป็น job ที่กินเพดานของ job ไปทั้งก้อนโดยไม่ทำอะไรเลย
NETWORK_TIMEOUT_SECONDS = 120  # pip-audit/npm audit ต้องต่อเน็ตและช้ากว่า gh มาก
PINS = ROOT / "pins"
ACCEPTED = PINS / "accepted-advisories.txt"


def accepted_advisories() -> set[str]:
    """ID ที่ประเมินแล้วว่ารับไว้ — บรรทัดว่างและคอมเมนต์ไม่นับ"""
    lines = ACCEPTED.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


def _fixes(vuln: dict[str, list[str]]) -> str:
    """รุ่นที่แก้แล้ว — **"ยังไม่มี" ต่างจาก "มีแต่เราขยับไม่ได้" อย่างสิ้นเชิง**

    ข้อแรกคือรอ upstream ข้อหลังคือมีทางออกอยู่แล้วแต่มีอะไรขวางอยู่ที่ฝั่งเรา
    """
    return ", ".join(vuln["fix_versions"]) or "ยังไม่มี"


def _run(command: list[str], where: pathlib.Path, tool: str) -> str:
    """รันตัว audit แล้วคืน stdout — **exit 1 คือ "เจอช่องโหว่" ไม่ใช่ "พัง"**

    ทั้ง pip-audit และ npm audit ใช้กติกาเดียวกัน · อย่างอื่นคือตัวมันเองมีปัญหา
    (ไม่มี node, ต่อ registry ไม่ได้) ซึ่ง **ต้องดัง ไม่ใช่ข้ามเงียบ ๆ** —
    ด่านที่ข้ามตัวเองตอนเครื่องมือหาย คือด่านที่เขียวในวันที่มันไม่ได้ตรวจอะไร
    """
    try:
        result = subprocess.run(  # noqa: S603 — อาร์กิวเมนต์คงที่ + path จาก glob ของ repo เอง
            command,
            cwd=where,
            capture_output=True,
            text=True,
            check=False,
            timeout=NETWORK_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        print(f"ไม่มี {tool} บนเครื่องนี้ — ติดตั้งก่อน อย่าข้าม", file=sys.stderr)
        raise SystemExit(2) from None

    if result.returncode not in (0, 1):
        print(f"{tool} ล้มด้วย exit {result.returncode} ที่ {where}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(2)
    return result.stdout


def audit_pip(lock: pathlib.Path) -> dict[str, str]:
    """ID ที่เจอในไฟล์ล็อกของ python → คำอธิบายสั้น ๆ ว่าเป็นของ package ไหน

    **ไม่ส่ง `--ignore-vuln` ให้ pip-audit** เพราะเราต้องเห็นของทั้งหมดก่อน
    ถึงจะรู้ได้ว่ารายการยกเว้นยังตรงกับความจริงอยู่ไหม
    """
    command = [sys.executable, "-m", "pip_audit", "--no-deps", "--format", "json", "-r", lock.name]
    report = json.loads(_run(command, lock.parent, "pip-audit"))
    return {
        vuln["id"]: f"{dep['name']}=={dep['version']} (fix: {_fixes(vuln)})"
        for dep in report["dependencies"]
        for vuln in dep.get("vulns", [])
    }


def audit_npm(project: pathlib.Path) -> dict[str, str]:
    """ID ที่เจอในไฟล์ล็อกของ node — **ไม่ต้องมี `node_modules`**

    `npm audit` สร้างต้นไม้จาก `package-lock.json` แล้วถาม registry เอง

    รายงานของมันถูก **จัดกลุ่มตาม package ที่ได้รับผลกระทบ ไม่ใช่ตาม advisory**
    ตัวที่เป็น advisory จริงคือสมาชิกของ `via` ที่เป็น object ส่วนที่เป็นสตริงคือ
    "ติดมาจากตัวนั้น" — นับตามหัวข่าวจะได้ 6 ทั้งที่ต้นตอมีอันเดียว และรายการ
    ยกเว้นจะบวมตามจำนวน package ที่บังเอิญ depend กันแทนที่จะตามจำนวนเรื่อง
    """
    report = json.loads(_run(["npm", "audit", "--json"], project, "npm"))
    if "vulnerabilities" not in report:
        print(f"npm audit ไม่ได้คืนรายงานที่อ่านได้ที่ {project}", file=sys.stderr)
        raise SystemExit(2)

    return {
        _advisory_id(via): f"{via['name']}{via['range']} ({via['severity']})"
        for entry in report["vulnerabilities"].values()
        for via in entry["via"]
        if isinstance(via, dict)
    }


def _advisory_id(via: dict[str, str]) -> str:
    """GHSA จาก URL ของ advisory — ตกกลับไปที่ URL เต็มถ้ารูปแบบเปลี่ยน

    **ห้ามใช้ `source` ที่เป็นเลข** มันเป็นไอดีภายในของ registry ซึ่งอ้างถึง
    จากที่อื่นไม่ได้ และคนอ่านรายการยกเว้นจะไม่มีทางรู้ว่ามันคือเรื่องอะไร
    """
    _, marker, tail = via.get("url", "").partition("/advisories/")
    return tail if marker and tail else via.get("url", via["name"])


def main() -> int:
    """ตรวจทุกไฟล์ล็อกใน `pins/` แล้วเทียบผลกับรายการยกเว้นทั้งสองทิศ"""
    pip_locks = sorted(PINS.glob("*/requirements.txt"))
    npm_locks = sorted(PINS.glob("*/package-lock.json"))
    if not pip_locks or not npm_locks:
        # **เช็คทั้งสองฝั่ง** — ฝั่งที่หาไม่เจอจะ "ผ่าน" เงียบ ๆ ทั้งที่ไม่ได้ตรวจอะไร
        print(f"หาไฟล์ล็อกไม่ครบ (python {len(pip_locks)} · node {len(npm_locks)})", file=sys.stderr)
        return 2

    found: dict[str, str] = {}
    for lock in pip_locks:
        print(f"== {lock.relative_to(ROOT)}")
        found.update(audit_pip(lock))
    for lock in npm_locks:
        print(f"== {lock.relative_to(ROOT)}")
        found.update(audit_npm(lock.parent))

    accepted = accepted_advisories()
    unexpected = sorted(found.keys() - accepted)
    stale = sorted(accepted - found.keys())

    for advisory in sorted(found):
        mark = "ยกเว้นไว้" if advisory in accepted else "ใหม่"
        print(f"   {advisory:<20} {found[advisory]}  [{mark}]")

    if unexpected:
        print("\n** advisory ที่ยังไม่มีใครประเมิน:", file=sys.stderr)
        for advisory in unexpected:
            print(f"   {advisory}  {found[advisory]}", file=sys.stderr)
        print(
            "ตัดสินใจก่อน: อัปเกรดได้ก็อัปเกรด · รับไว้ก็เขียนเหตุผลลง\n"
            "docs/SECURITY-CADENCE.md แล้วเติม ID ลง pins/accepted-advisories.txt",
            file=sys.stderr,
        )

    if stale:
        print("\n** ยกเว้นไว้แต่ไม่เจอแล้ว — ถอดออกได้:", file=sys.stderr)
        for advisory in stale:
            print(f"   {advisory}", file=sys.stderr)
        print(
            "รายการยกเว้นที่ไม่มีใครถอด คือรายการที่วันหนึ่งจะปิดของจริง\n"
            "ถอดออกจากทั้ง pins/accepted-advisories.txt และ docs/SECURITY-CADENCE.md",
            file=sys.stderr,
        )

    if not unexpected and not stale:
        print(f"\nไม่มีอะไรใหม่ — ยกเว้นไว้ {len(accepted)} ข้อ และยังตรงกับความจริงทุกข้อ")
    return 1 if (unexpected or stale) else 0


if __name__ == "__main__":
    raise SystemExit(main())
