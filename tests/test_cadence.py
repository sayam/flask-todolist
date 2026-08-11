"""รอบการตรวจสอบใน docs/SECURITY-CADENCE.md ต้องเป็นของจริง ไม่ใช่ความตั้งใจ

**นโยบายที่ไม่มีอะไรบังคับคือเอกสารที่ทำให้เชื่อว่ามีคนตรวจอยู่ทั้งที่ไม่มี**
ซึ่งแย่กว่าไม่เขียนไว้เลย เพราะมันทำให้หยุดถาม (หลักเดียวกับ
`tests/test_asvs.py` และ `tests/test_data_classification.py`)

เทสต์นี้ตรวจสามอย่าง:

1. ทุกแถวของการตรวจที่ต้องทำด้วยมือ ต้องบอกกำหนดในรูปแบบที่ตัดสินได้ —
   **วันที่** หรือ **เงื่อนไข** ที่คนอื่นดูออกว่าเกิดขึ้นแล้วหรือยัง
2. แถวที่เป็นวันที่ **ต้องไม่เลยกำหนด** — เลยแล้วต้องไปทำ หรือเลื่อนอย่าง
   เปิดเผยด้วยการแก้ตารางพร้อมเหตุผล ซึ่งเป็น commit ที่มีคนเห็น
3. ลิงก์ในเอกสารนี้ที่ชี้ไปหาไฟล์ใน repo ต้องมีไฟล์นั้นอยู่จริง —
   นโยบายที่อ้างหลักฐานซึ่งหายไปแล้วก็เน่าแบบเดียวกับ checklist
"""

import datetime
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "SECURITY-CADENCE.md"

SECTION = "## ส่วนที่ต้องมีคนลงมือ"
NEXT_SECTION = "## กรอบเวลาแก้ช่องโหว่"

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# เงื่อนไขต้องขึ้นต้นด้วย "เมื่อ" เพื่อให้แยกออกจากคำว่า "ยังไม่รู้" ที่ตัดสินอะไรไม่ได้
CONDITION = re.compile(r"^เมื่อ\s*\S")
LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")

# เผื่อไว้ให้งานปกติเดินได้ ไม่ใช่ให้ปล่อยผ่าน — เลยกำหนดวันแรก CI ยังไม่แดง
# แต่ผ่านไปหนึ่งสัปดาห์แล้วยังไม่มีใครแตะ แปลว่าไม่มีใครกำลังจะทำ
GRACE_DAYS = 7


@pytest.fixture(scope="module")
def rows():
    """แถวของตาราง "การตรวจที่ต้องมีคนลงมือ" — (ชื่อ, รอบ, ครั้งล่าสุด, ครบกำหนด, หลักฐาน)"""
    text = DOC.read_text(encoding="utf-8")
    start = text.index(SECTION)
    end = text.index(NEXT_SECTION, start)
    parsed = []
    for line in text[start:end].splitlines():
        if not line.startswith("|") or line.startswith("|---") or "ครบกำหนด" in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        assert len(cells) == 5, f"แถวนี้มี {len(cells)} ช่อง ต้องมี 5: {line[:60]}"
        parsed.append(tuple(cells))
    assert parsed, "อ่านตารางการตรวจที่ต้องมีคนลงมือไม่ได้เลย — รูปแบบเอกสารเปลี่ยนไปแล้ว"
    return parsed


def test_every_review_says_when_it_is_due(rows):
    """กำหนดต้องตัดสินได้ — เป็นวันที่ หรือเงื่อนไขที่ดูออกว่าเกิดหรือยัง"""
    vague = [row[0] for row in rows if not (DATE.match(row[3]) or CONDITION.match(row[3]))]
    assert not vague, (
        f'การตรวจที่บอกกำหนดแบบตัดสินไม่ได้: {vague}\nใช้วันที่ YYYY-MM-DD หรือเงื่อนไขที่ขึ้นต้นด้วย "เมื่อ"'
    )


def test_no_dated_review_is_overdue(rows):
    """เลยกำหนดแล้วต้องแดง — ไปทำ หรือเลื่อนอย่างเปิดเผยพร้อมเหตุผล"""
    today = datetime.date.today()
    overdue = [
        f"{row[0]} (ครบกำหนด {row[3]})"
        for row in rows
        if DATE.match(row[3])
        and datetime.date.fromisoformat(row[3]) + datetime.timedelta(days=GRACE_DAYS) < today
    ]
    assert not overdue, (
        "การตรวจที่เลยกำหนดมาเกิน "
        f"{GRACE_DAYS} วัน:\n" + "\n".join(overdue) + "\n"
        "ทำแล้วขยับวันที่ หรือเลื่อนโดยแก้ตารางพร้อมเหตุผล — ห้ามแก้เทสต์ให้เงียบ"
    )


def test_conditional_reviews_still_name_a_trigger(rows):
    """เงื่อนไขต้องยาวพอจะเป็นประโยค ไม่ใช่คำว่า "เมื่อพร้อม" ที่ไม่มีวันมาถึง"""
    thin = [row[0] for row in rows if CONDITION.match(row[3]) and len(row[3]) < 20]
    assert not thin, f"เงื่อนไขสั้นจนตัดสินไม่ได้: {thin}"


def test_every_link_to_a_repo_file_resolves():
    """เอกสารนโยบายที่อ้างของซึ่งหายไปแล้ว เน่าแบบเดียวกับ checklist ที่ไม่มีใครตรวจ"""
    text = DOC.read_text(encoding="utf-8")
    missing = []
    for target in LINK.findall(text):
        if target.startswith(("http://", "https://", "#")):
            continue
        if not (DOC.parent / target.split("#", 1)[0]).exists():
            missing.append(target)
    assert not missing, f"ลิงก์ที่ชี้ไปหาไฟล์ที่ไม่มีอยู่: {missing}"
