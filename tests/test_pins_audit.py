"""รายการยกเว้นของ `pins/` ต้องผูกกับเหตุผลที่เขียนไว้ และต้องมีคนรันมันจริง

`scripts/audit_pins.py` ตรวจ **ผลของการ audit** เทียบกับรายการยกเว้น (สองทิศ:
เจอของที่ไม่ได้ยกเว้น = แดง · ยกเว้นของที่ไม่เจอแล้ว = แดง) — แต่มันต้องต่อเน็ต
จึงไม่เหมาะเป็นเทสต์ใน pytest ที่นี่คุมสิ่งที่ตรวจได้โดยไม่ต้องต่อเน็ตแทน:

1. **ทุก ID ที่ยกเว้นไว้ ต้องมีเหตุผลอยู่ใน `docs/SECURITY-CADENCE.md`**
   รายการยกเว้นที่ไม่มีเหตุผลกำกับคือรายการที่คนถัดไปไม่มีทางรู้ว่าจะถอดได้เมื่อไหร่
2. **และกลับกัน** — ID ที่เอกสารบอกว่ารับไว้ ต้องอยู่ในไฟล์จริง ๆ ไม่งั้นคือ
   เอกสารที่อธิบายด่านที่ไม่มีอยู่
3. **job `security` ต้องเรียกสคริปต์นั้นจริง** — ด่านที่ไม่มีใครรัน คือไฟล์ข้อความ
"""

import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
ACCEPTED = ROOT / "pins" / "accepted-advisories.txt"
CADENCE = ROOT / "docs" / "SECURITY-CADENCE.md"
SCRIPT = ROOT / "scripts" / "audit_pins.py"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

# ID ที่ pip-audit พิมพ์ออกมา — `PYSEC-2026-3481` หรือ `GHSA-xxxx-xxxx-xxxx`
ADVISORY_ID = re.compile(r"\b(?:PYSEC-\d{4}-\d+|GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4})\b")


@pytest.fixture(scope="module")
def accepted() -> set[str]:
    assert ACCEPTED.is_file(), "ไม่มี pins/accepted-advisories.txt"
    lines = ACCEPTED.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


@pytest.fixture(scope="module")
def documented() -> set[str]:
    """ID ที่ถูกอ้างใน backtick ในเอกสาร — backtick คือสิ่งที่ทำให้มันเป็น ID

    หลักเดียวกับช่องหลักฐานของ `docs/ASVS.md`: ของใน backtick คือของที่ถูกตรวจ
    """
    text = CADENCE.read_text(encoding="utf-8")
    return {
        match for quoted in re.findall(r"`([^`]+)`", text) for match in ADVISORY_ID.findall(quoted)
    }


def test_every_accepted_advisory_has_a_reason_on_record(accepted, documented):
    assert accepted, "ไม่มี ID ในรายการยกเว้นเลย — ตัวอ่านพังหรือเปล่า"

    unexplained = sorted(accepted - documented)
    assert not unexplained, (
        f"ยกเว้นไว้แต่ไม่มีเหตุผลใน {CADENCE.name}: {unexplained}\n"
        "รายการยกเว้นที่ไม่มีเหตุผลกำกับ คือรายการที่ไม่มีใครรู้ว่าจะถอดได้เมื่อไหร่"
    )


def test_every_documented_acceptance_is_actually_in_effect(accepted, documented):
    """เอกสารที่อธิบายด่านที่ไม่มีอยู่ แย่กว่าไม่เขียนอะไรเลย"""
    assert documented, "ไม่เจอ ID ของ advisory ใน backtick ในเอกสารเลย"

    orphaned = sorted(documented - accepted)
    assert not orphaned, (
        f"เอกสารบอกว่ารับไว้ แต่ไม่ได้อยู่ใน {ACCEPTED.name}: {orphaned}\n"
        "แปลว่าถ้ามันโผล่ขึ้นมาจริง job `security` จะแดง ทั้งที่มีคนตัดสินไปแล้ว"
    )


def test_the_security_job_actually_runs_the_pins_audit():
    """**ด่านที่ไม่มีใครรัน คือไฟล์ข้อความ** — และไม่มีอะไรฟ้องเวลาถูกถอดออก"""
    assert SCRIPT.is_file(), "ไม่มี scripts/audit_pins.py"

    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    commands = " ".join(step.get("run", "") for step in workflow["jobs"]["security"]["steps"])
    assert "scripts/audit_pins.py" in commands, (
        "job `security` ไม่ได้เรียก scripts/audit_pins.py — supply chain ของ pins/ "
        "จึงไม่มีใครตรวจให้ ทั้งที่เครื่องมือพวกนั้นรันด้วยสิทธิ์ของ workflow"
    )
