"""รายการยกเว้น CVE ของ image ต้องผูกกับเหตุผลที่เขียนไว้ และต้องมีคนรันมันจริง

`scripts/audit_image.py` ตรวจ**ผลสแกน OS layer** เทียบกับรายการยกเว้น
(สองทิศ: เจอของที่ไม่ได้ยกเว้น = แดง · ยกเว้นของที่ไม่เจอแล้ว = แดง) —
แต่มันต้องมีรายงาน trivy ซึ่งเกิดได้เฉพาะใน job `image` (เครื่อง dev ไม่มี
container runtime — P5-09) ที่นี่คุมสิ่งที่ตรวจได้โดยไม่ต้อง build image แทน
ตามแบบแผนเดียวกับ `tests/test_pins_audit.py` ทุกข้อ:

1. **ทุก ID ที่ยกเว้นไว้ ต้องมีเหตุผลอยู่ใน `docs/SECURITY-CADENCE.md`**
   ในหัวข้อของ image โดยเฉพาะ — ไม่ใช่แค่ ID โผล่ที่ไหนสักแห่งในไฟล์
   (เอกสารนั้นเล่า CVE เรื่องอื่นอยู่หลายตัว การ scan ทั้งไฟล์จะทำให้
   การเล่าประวัติกลายเป็นการยกเว้นโดยบังเอิญ)
2. **และกลับกัน** — ID ที่หัวข้อนั้นบอกว่ารับไว้ ต้องอยู่ในไฟล์จริง ๆ
3. **job `image` ต้องเรียกทั้ง trivy และตัวตัดสินจริง** — ด่านที่ไม่มีใครรัน
   คือไฟล์ข้อความ และการสแกนที่ไม่มีตัวตัดสินคือรายงานที่ไม่มีใครอ่าน
"""

import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
ACCEPTED = ROOT / "deploy" / "accepted-image-advisories.txt"
CADENCE = ROOT / "docs" / "SECURITY-CADENCE.md"
SCRIPT = ROOT / "scripts" / "audit_image.py"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

SECTION_HEAD = "### ช่องโหว่ใน OS layer ของ image"

# ID ที่ trivy พิมพ์ออกมา — CVE ของ NVD หรือ advisory ของ Debian
ADVISORY_ID = re.compile(r"\b(?:CVE-\d{4}-\d+|DLA-\d+-\d+|DSA-\d+-\d+)\b")


@pytest.fixture(scope="module")
def accepted() -> set[str]:
    assert ACCEPTED.is_file(), "ไม่มี deploy/accepted-image-advisories.txt"
    lines = ACCEPTED.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


@pytest.fixture(scope="module")
def documented() -> set[str]:
    """ID ใน backtick **เฉพาะใต้หัวข้อของ image** — จบที่หัวข้อระดับเดียวกันถัดไป"""
    text = CADENCE.read_text(encoding="utf-8")
    assert SECTION_HEAD in text, f"ไม่มีหัวข้อ '{SECTION_HEAD}' ใน {CADENCE.name}"
    section = text.split(SECTION_HEAD, 1)[1]
    section = re.split(r"\n#{2,3} ", section, maxsplit=1)[0]
    return {
        match
        for quoted in re.findall(r"`([^`]+)`", section)
        for match in ADVISORY_ID.findall(quoted)
    }


def test_every_accepted_advisory_has_a_reason_on_record(accepted, documented):
    unexplained = sorted(accepted - documented)
    assert not unexplained, (
        f"ยกเว้นไว้แต่ไม่มีเหตุผลใต้หัวข้อ image ใน {CADENCE.name}: {unexplained}\n"
        "รายการยกเว้นที่ไม่มีเหตุผลกำกับ คือรายการที่ไม่มีใครรู้ว่าจะถอดได้เมื่อไหร่"
    )


def test_every_documented_acceptance_is_actually_in_effect(accepted, documented):
    """เอกสารที่อธิบายด่านที่ไม่มีอยู่ แย่กว่าไม่เขียนอะไรเลย"""
    orphaned = sorted(documented - accepted)
    assert not orphaned, (
        f"หัวข้อ image บอกว่ารับไว้ แต่ไม่ได้อยู่ใน {ACCEPTED.name}: {orphaned}\n"
        "แปลว่าถ้ามันโผล่ขึ้นมาจริง job `image` จะแดง ทั้งที่มีคนตัดสินไปแล้ว"
    )


@pytest.fixture(scope="module")
def image_job() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["image"]


def test_the_image_job_actually_scans_and_judges(image_job):
    """**ด่านที่ไม่มีใครรัน คือไฟล์ข้อความ** — ต้องมีทั้งตัวสแกนและตัวตัดสิน"""
    assert SCRIPT.is_file(), "ไม่มี scripts/audit_image.py"

    used = [step.get("uses", "") for step in image_job["steps"]]
    assert any(u.startswith("aquasecurity/trivy-action@") for u in used), (
        "job `image` ไม่ได้รัน trivy — OS layer ของ image กลับไปเป็นครึ่งที่ไม่มีใครสแกนเหมือนก่อน ADR 0054"
    )

    commands = " ".join(step.get("run", "") for step in image_job["steps"])
    assert "scripts/audit_image.py" in commands, (
        "job `image` สแกนแต่ไม่ได้เรียก scripts/audit_image.py — รายงานที่"
        "ไม่มีตัวตัดสินคือรายงานที่ไม่มีใครอ่าน และรายการยกเว้นจะไม่ถูกตรวจย้อน"
    )


def test_the_scan_scope_is_declared_once_in_the_workflow(image_job):
    """ขอบเขต (HIGH/CRITICAL · ignore-unfixed) ประกาศที่ step ของ trivy ที่เดียว

    ตัวตัดสินอ่านทุกแถวในรายงานโดยไม่กรองซ้ำ — ตัวกรองสองที่คือตัวกรองที่
    วันหนึ่งจะไม่ตรงกันเอง ถ้าขอบเขตหายจาก workflow ด่านจะกลายเป็นด่านที่
    แดงด้วย MEDIUM/LOW ที่ไม่มีใครตั้งใจให้มันตัดสิน
    """
    trivy = [s for s in image_job["steps"] if s.get("uses", "").startswith("aquasecurity/")]
    assert trivy, "ไม่เจอ step ของ trivy"
    with_ = trivy[0].get("with", {})
    assert with_.get("severity") == "HIGH,CRITICAL", "ขอบเขต severity ไม่ตรง ADR 0054"
    assert str(with_.get("ignore-unfixed")).lower() == "true", (
        "ignore-unfixed หาย — ด่านจะแดงด้วยของที่ Debian ยังไม่มี patch ซึ่งการกระทำเดียวที่ทำได้คือรอ (ADR 0054)"
    )
