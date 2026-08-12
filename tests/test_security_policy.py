"""`SECURITY.md` ต้องไม่สัญญาคนละอย่างกับที่นโยบายภายในถืออยู่

ไฟล์นี้เป็นคำสัญญาที่ให้กับคนนอก ส่วน `docs/SECURITY-CADENCE.md` เป็นกรอบเวลา
ที่โปรเจกต์ถือกับตัวเอง — **เลขชุดเดียวกันอยู่สามที่** (ตารางอังกฤษใน
`SECURITY.md` · ประโยคไทยในไฟล์เดียวกัน · ตารางใน cadence) วันที่มีคนขยับที่หนึ่ง
แล้วลืมอีกสอง โปรเจกต์จะสัญญากับคนภายนอกคนละแบบกับที่ทำจริง โดยไม่มีอะไรส่งเสียง

อีกข้อที่คุมคือ **ห้ามมีอีเมลในไฟล์นี้** — เป็นการตัดสินใจตอนเปิด public ว่า
ช่องทางเดียวคือ private vulnerability reporting ของ GitHub เพื่อไม่ให้ที่อยู่จริง
ไปนอนใน repo สาธารณะให้ crawler เก็บ · เผลอเติมกลับมาเมื่อไหร่ต้องแดง
"""

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
POLICY = ROOT / "SECURITY.md"
CADENCE = ROOT / "docs" / "SECURITY-CADENCE.md"

SEVERITIES = ("critical", "high", "medium")

# `| critical | **7 วัน** |` และ `| Critical | **7 days** |`
TABLE_ROW = re.compile(
    r"^\|\s*(critical|high|medium)\s*\|\s*\*\*(\d+)\s*(?:days?|วัน)\*\*\s*\|",
    re.IGNORECASE | re.MULTILINE,
)

# ประโยคไทยในนโยบาย: `(critical 7 วัน · high 30 · medium 90)`
THAI_SENTENCE = re.compile(r"critical\s+(\d+)\s*วัน\s*·\s*high\s+(\d+)\s*·\s*medium\s+(\d+)")

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _deadlines(path: pathlib.Path) -> dict[str, int]:
    found = {
        match.group(1).lower(): int(match.group(2))
        for match in TABLE_ROW.finditer(path.read_text(encoding="utf-8"))
    }
    assert set(found) == set(SEVERITIES), (
        f"อ่านตารางกรอบเวลาใน {path.name} ไม่ครบ — ได้ {sorted(found)} "
        f"ต้องการ {sorted(SEVERITIES)} · รูปแบบตารางเปลี่ยนไปแล้วหรือเปล่า"
    )
    return found


@pytest.fixture(scope="module")
def policy_text():
    assert POLICY.is_file(), "ไม่มี SECURITY.md ที่รากของ repo — คนนอกไม่รู้จะแจ้งช่องโหว่ทางไหน"
    return POLICY.read_text(encoding="utf-8")


def test_the_public_promise_matches_the_internal_cadence():
    promised, internal = _deadlines(POLICY), _deadlines(CADENCE)
    assert promised == internal, (
        f"กรอบเวลาที่สัญญากับคนนอก {promised} ไม่ตรงกับที่ถือไว้จริง {internal}\n"
        "ขยับที่หนึ่งต้องขยับทั้งสองที่ ไม่งั้นคำสัญญากับความจริงจะแยกทางกันเงียบ ๆ"
    )


def test_the_thai_half_promises_the_same_numbers_as_the_english_half(policy_text):
    """แปลไม่ครบคือทางที่เลขแตกกันได้ง่ายที่สุด เพราะสองครึ่งไม่ได้อยู่ติดกัน"""
    match = THAI_SENTENCE.search(policy_text)
    assert match, "หาประโยคกรอบเวลาฉบับภาษาไทยใน SECURITY.md ไม่เจอ"

    thai = dict(zip(SEVERITIES, (int(group) for group in match.groups()), strict=True))
    assert thai == _deadlines(POLICY), (
        f"ครึ่งภาษาไทยบอก {thai} แต่ตารางภาษาอังกฤษบอก {_deadlines(POLICY)}"
    )


def test_the_policy_carries_no_email_address(policy_text):
    """ช่องทางเดียวคือ private vulnerability reporting — ที่อยู่จริงห้ามอยู่ในไฟล์สาธารณะ"""
    found = EMAIL.findall(policy_text)
    assert not found, (
        f"เจออีเมลใน SECURITY.md: {found}\n"
        "ตัดสินใจไว้ว่าช่องทางเดียวคือ private vulnerability reporting ของ GitHub"
    )


def test_the_policy_points_at_a_reporting_channel_that_exists(policy_text):
    """ลิงก์ต้องชี้ไปที่ repo นี้จริง ไม่ใช่ที่ก๊อปมาจากตัวอย่าง"""
    assert "security/advisories/new" in policy_text, (
        "ไม่มีลิงก์ไปหน้าแจ้งช่องโหว่แบบส่วนตัว — นโยบายที่ไม่บอกทางส่งคือนโยบายที่ไม่มีใครใช้ได้"
    )
    assert policy_text.count("github.com/sayam/flask-todolist") >= 1, "ลิงก์แจ้งช่องโหว่ไม่ได้ชี้มาที่ repo นี้"


def test_the_out_of_scope_list_still_matches_decisions_we_actually_made(policy_text):
    """ข้อยกเว้นทุกข้อต้องผูกกับการตัดสินใจที่มีเอกสาร ไม่ใช่ข้ออ้างลอย ๆ

    ที่นี่ตรวจแค่ว่า ADR ที่ยกมาอ้างมีไฟล์อยู่จริง — เอกสารที่ชี้ไปหาเหตุผล
    ที่ไม่มีอยู่ แย่กว่าไม่ชี้ไปไหนเลย (หลักเดียวกับ `tests/test_asvs.py`)
    """
    referenced = set(re.findall(r"docs/(adr/[\w./-]+\.md|[\w./-]+\.md)", policy_text))
    assert referenced, "SECURITY.md ไม่ได้อ้างเอกสารประกอบสักฉบับ"

    missing = sorted(name for name in referenced if not (ROOT / "docs" / name).is_file())
    assert not missing, f"SECURITY.md ชี้ไปหาเอกสารที่ไม่มีอยู่: {missing}"
