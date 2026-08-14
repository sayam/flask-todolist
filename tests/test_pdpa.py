"""`docs/PDPA.md` — worksheet ชั้น legal ต้องไม่เน่า (เฟส 13-04 · ADR 0042)

หลักเดียวกับ `tests/test_asvs.py`: เอกสารที่อ้างหลักฐานซึ่งไม่มีใครตรวจ คือ
เอกสารที่วันหนึ่งจะโกหกโดยไม่มีอะไรฟ้อง — ทุกอย่างใน backtick ของช่องหลักฐาน
ถูกตรวจว่ามีอยู่จริง (ไฟล์ · `ADR 00NN` · `ci:job` · `path::test`) และ
สถานะ `ยังไม่ผ่าน` ทุกแถวต้องมีคู่ใน backlog

ตัว resolver ยืมจาก `tests/test_asvs.py` ตรง ๆ — ด่านสองใบที่ตรวจหลักฐาน
คนละวิธีกัน คือด่านที่วันหนึ่งจะให้คำตอบไม่ตรงกัน
"""

import pathlib
import re

import pytest

from tests.test_asvs import _unresolved

ROOT = pathlib.Path(__file__).resolve().parent.parent
PDPA = ROOT / "docs" / "PDPA.md"

STATUSES = {"ผ่าน", "ไม่เกี่ยวข้อง", "ยังไม่ผ่าน"}
BACKTICK = re.compile(r"`([^`]+)`")

# มาตราที่ worksheet สัญญาว่าจะตอบ — ลดจำนวนเงียบ ๆ ไม่ได้ (ratchet แบบเดียว
# กับ UNASSESSED_CEILING ของ ASVS) · เพิ่มได้เสมอ
REQUIRED_SECTIONS = {
    "ม.19",
    "ม.22",
    "ม.23",
    "ม.24",
    "ม.26",
    "ม.28",
    "ม.30",
    "ม.31",
    "ม.32",
    "ม.33",
    "ม.34",
    "ม.35",
    "ม.37(1)",
    "ม.37(2)",
    "ม.37(3)",
    "ม.37(4)",
    "ม.39",
    "ม.41",
}


@pytest.fixture(scope="module")
def text():
    return PDPA.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def rows(text):
    """(มาตรา, สถานะ, ช่องหลักฐาน) จากตารางประเมิน — ไม่รวมตาราง backlog"""
    parsed = []
    in_backlog = False
    for line in text.splitlines():
        if line.startswith("## Backlog"):
            in_backlog = True
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[0].startswith("ม.") and not in_backlog:
            parsed.append((cells[0], cells[2], cells[3]))
    assert parsed, "อ่านตารางประเมินใน docs/PDPA.md ไม่ได้เลย — รูปแบบเปลี่ยนไปแล้ว"
    return parsed


@pytest.fixture(scope="module")
def ci_jobs():
    jobs = set()
    for line in (
        (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8").splitlines()
    ):
        found = re.match(r"^  ([a-z][\w-]*):\s*$", line)
        if found:
            jobs.add(found.group(1))
    return jobs


def test_every_promised_section_has_a_row(rows):
    """มาตราที่สัญญาไว้ต้องอยู่ครบ — worksheet ที่แถวหายเงียบ ๆ คือ worksheet ที่โกหก"""
    present = {section for section, _, _ in rows}
    missing = sorted(REQUIRED_SECTIONS - present)
    assert not missing, f"มาตราที่หายจากตาราง: {missing}"


def test_every_status_is_one_of_the_three(rows):
    bad = [(s, status) for s, status, _ in rows if status not in STATUSES]
    assert not bad, f"สถานะที่ไม่รู้จัก: {bad}"


def test_every_evidence_reference_resolves(rows, ci_jobs):
    """ทุกอย่างใน backtick ต้องชี้ไปหาของที่มีจริง — ทุกสถานะ ไม่ใช่แค่แถวผ่าน

    แถว "ไม่เกี่ยวข้อง" ที่อ้างไฟล์ซึ่งถูกลบไปแล้ว คือเหตุผลที่ตรวจไม่ได้อีกต่อไป
    """
    broken = []
    for section, _, evidence in rows:
        for reference in BACKTICK.findall(evidence):
            problem = _unresolved(reference, ci_jobs)
            if problem:
                broken.append(f"{section}: `{reference}` — {problem}")
    assert not broken, "\n  ".join(["หลักฐานที่ชี้ไปหาของที่ไม่มีจริง:", *broken])


def test_passing_rows_carry_at_least_one_evidence(rows):
    """แถวที่บอกว่าผ่านโดยไม่มีหลักฐานสักชิ้น คือแถวที่ขอให้เชื่อ"""
    empty = [
        s for s, status, evidence in rows if status == "ผ่าน" and not BACKTICK.findall(evidence)
    ]
    assert not empty, f"แถวผ่านที่ไม่มีหลักฐานใน backtick: {empty}"


def test_every_gap_is_in_the_backlog(rows, text):
    """`ยังไม่ผ่าน` ทุกแถวต้องมีคู่ใน backlog — ช่องว่างที่ไม่มีแผนคือช่องว่างถาวร"""
    backlog = text.split("## Backlog", 1)[1]
    missing = [s for s, status, _ in rows if status == "ยังไม่ผ่าน" and s not in backlog]
    assert not missing, f"แถวยังไม่ผ่านที่ไม่อยู่ใน backlog: {missing}"


def test_the_disclaimer_survives(text):
    """คำเตือน "ไม่ใช่คำปรึกษากฎหมาย" ห้ามหาย — worksheet นี้อันตรายทันทีถ้าถูกอ่านเป็นคำรับรอง"""
    assert "ไม่ใช่คำปรึกษากฎหมาย" in text
    assert "ผู้ควบคุมข้อมูล" in text, "ต้องบอกชัดว่าหน้าที่ตามกฎหมายเป็นของผู้ deploy"


def test_the_72_hour_window_matches_the_runbook(text):
    """กรอบเวลาแจ้งเหตุใน worksheet ต้องเป็นเลขเดียวกับใน runbook จริง"""
    assert "72 ชั่วโมง" in text
    runbook = (ROOT / "docs" / "RUNBOOK-BREACH.md").read_text(encoding="utf-8")
    assert "72 ชั่วโมง" in runbook, "runbook ไม่มีกรอบ 72 ชั่วโมงแล้ว — สองไฟล์ต้องเล่าเรื่องเดียวกัน"
