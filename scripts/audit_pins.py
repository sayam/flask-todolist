"""audit เครื่องมือของ CI ใน `pins/` — และบังคับให้รายการยกเว้นไม่เน่า

job `security` มี pip-audit ของ core และของ `[deploy]` อยู่แล้ว ส่วน `pins/`
เป็น supply chain ก้อนที่สามที่ไม่มีใครดูให้: มันไม่ได้ถูกติดตั้งด้วย
`pipenv sync --dev` จึงไม่อยู่ในรอบของ core และไม่ใช่ไลบรารีของ plugin

**ทำไมต้องมีรายการยกเว้น** — `semgrep` pin `mcp` ไว้ตายตัว การอัปเกรดตามที่
advisory บอกจึงทำไม่ได้จนกว่า upstream จะขยับ ด่านที่แดงตั้งแต่วันแรกและแดง
ต่อไปเรื่อย ๆ คือด่านที่ถูกปิดเสียงภายในสองสัปดาห์ แล้วของจริงที่โผล่ทีหลัง
ก็ถูกมองข้ามไปด้วย

**ทำไมรายการยกเว้นต้องถูกตรวจย้อนกลับด้วย** — `pip-audit --ignore-vuln` เงียบ
เสมอเมื่อ ID นั้นไม่โผล่แล้ว รายการที่ไม่มีใครถอดจึงค่อย ๆ กลายเป็นรายการที่
ปิดของจริงโดยไม่มีใครรู้ ที่นี่จึงตรวจสองทิศ: **เจอของที่ไม่ได้ยกเว้น = แดง**
และ **ยกเว้นของที่ไม่เจอแล้ว = แดง**

รันเองบนเครื่อง: `PYTHONPATH=. pipenv run python scripts/audit_pins.py`
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
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


def audit(lock: pathlib.Path) -> dict[str, str]:
    """ID ที่เจอในไฟล์ล็อกหนึ่งไฟล์ → คำอธิบายสั้น ๆ ว่าเป็นของ package ไหน

    **ไม่ส่ง `--ignore-vuln` ให้ pip-audit** เพราะเราต้องเห็นของทั้งหมดก่อน
    ถึงจะรู้ได้ว่ารายการยกเว้นยังตรงกับความจริงอยู่ไหม
    """
    result = subprocess.run(  # noqa: S603 — อาร์กิวเมนต์คงที่ + path จาก glob ของ repo เอง
        [sys.executable, "-m", "pip_audit", "--no-deps", "--format", "json", "-r", str(lock)],
        capture_output=True,
        text=True,
        check=False,
    )
    # pip-audit คืน 1 เมื่อ *เจอช่องโหว่* ซึ่งเป็นผลปกติที่นี่ — อย่างอื่นคือมันเองพัง
    if result.returncode not in (0, 1):
        print(f"pip-audit ล้มด้วย exit {result.returncode} ที่ {lock}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(2)

    report = json.loads(result.stdout)
    return {
        vuln["id"]: f"{dep['name']}=={dep['version']} (fix: {_fixes(vuln)})"
        for dep in report["dependencies"]
        for vuln in dep.get("vulns", [])
    }


def main() -> int:
    """ตรวจทุกไฟล์ล็อกใน `pins/` แล้วเทียบผลกับรายการยกเว้นทั้งสองทิศ"""
    locks = sorted(PINS.glob("*/requirements.txt"))
    if not locks:
        print("ไม่เจอไฟล์ล็อกใน pins/ เลย — ตัวหาพังหรือเปล่า", file=sys.stderr)
        return 2

    found: dict[str, str] = {}
    for lock in locks:
        print(f"== {lock.relative_to(ROOT)}")
        found.update(audit(lock))

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
