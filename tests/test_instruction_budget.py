"""`CLAUDE.md` มีเพดานที่ประกาศไว้ และเพดานนั้นลอยเหนือของจริงไม่ได้ (ADR 0065)

ไฟล์นี้ต่างจากเอกสารอื่นทุกฉบับตรงที่ **ถูกอ่านทั้งไฟล์ทุก session ทุกครั้ง**
ต้นทุนของมันจึงจ่ายซ้ำตลอดไป ไม่ใช่จ่ายตอนมีคนเปิดอ่าน · วัดตอนตั้งกติกา
(audit r8 · 2026-08-18): 22 บรรทัดในวันแรกของโปรเจกต์ → **1,240 บรรทัด /
8,488 คำ ใน 16 วัน** และ 66 commit ใน 7 วันล่าสุดแตะมัน — โตทุกครั้งที่มีงาน
governance โดยไม่มีใครเคยตัดสินว่าโตได้แค่ไหน

**ทางที่เลือกคือ ratchet ไม่ใช่ห้ามโต** (ADR 0065) — บังคับสองทิศ:

1. **ห้ามเกินเพดาน** · เต็มแล้วให้ย้ายเนื้อไปเอกสารเฉพาะแล้วลิงก์กลับมา
   ไม่ใช่ขยับเพดาน (ขยับขึ้นต้องมี ADR กำกับเสมอ)
2. **เพดานต้องไม่ลอยเหนือของจริงเกินระยะที่กำหนด** — เพดานที่ลอยสูงคือเพดาน
   ที่ไม่ได้ตั้ง · ทิศนี้คือตัว ratchet เอง: วันที่มีคนย้ายเนื้อออกไป เพดาน
   **ต้องถูกลดตาม** ไม่งั้นที่ว่างที่เพิ่งได้มาจะถูกถมกลับเงียบ ๆ ในรอบถัดไป

**นับสองหน่วยโดยตั้งใจ** — บรรทัดคือสิ่งที่คนเห็น ส่วนคำคือสิ่งที่โมเดลจ่ายจริง
ถ้านับแต่บรรทัด การรวมบรรทัดให้ยาวขึ้นจะกลายเป็นการ "ลด" ขนาดโดยไม่ลดอะไรเลย
"""

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
# **ไฟล์ที่มีเพดาน กับเหตุผลว่าทำไมเพดานไม่เท่ากัน** (ADR 0065 · ขยาย audit รอบ 12)
#
# `CLAUDE.md` ถูกอ่าน**ทั้งไฟล์ทุก session** ต้นทุนจึงจ่ายซ้ำตลอดไป — เพดานจึงแคบ
# และที่ว่างที่ยอมให้ลอยเหนือของจริงก็แคบตาม
#
# `docs/GOVERNANCE.md` เกิดจากการ**ย้ายเนื้อออกมาจากไฟล์นั้น** (รอบ 11) ต้นทุนของมัน
# จ่ายตอนมีคนเปิดอ่าน ไม่ใช่ทุกครั้งที่มี session — เพดานจึงกว้างกว่าได้ · **แต่มันต้องมี
# เพดาน** ไม่งั้นสิ่งที่เกิดคือการย้ายต้นทุน ไม่ใช่การลด (audit รอบ 12 ข้อ 4) และเรารู้
# อัตราการโตของไฟล์แบบนี้แล้ว: `CLAUDE.md` โตจาก 22 เป็น 1,265 บรรทัดใน 16 วัน
#
# **เพดาน: ขยับขึ้นต้องมี ADR · ลดลงทำได้เสมอและควรทำทุกครั้งที่ย้ายเนื้อออก**
# **slack: ระยะที่เพดานลอยเหนือของจริงได้** — ที่ว่างสำหรับงานปกติหนึ่งรอบ ไม่ใช่ถาวร
BUDGETS = {
    "CLAUDE.md": {"lines": 1_200, "words": 8_100, "line_slack": 40, "word_slack": 300},
    "docs/GOVERNANCE.md": {"lines": 180, "words": 1_400, "line_slack": 60, "word_slack": 500},
}


def _size(name: str) -> tuple[int, int]:
    text = (ROOT / name).read_text(encoding="utf-8")
    return len(text.splitlines()), len(text.split())


@pytest.mark.parametrize("name", sorted(BUDGETS))
def test_the_file_stays_under_its_ceiling(name):
    """ทิศที่หนึ่ง — เกินแล้วให้ย้ายเนื้อออก ไม่ใช่ขยับเพดาน"""
    lines, words = _size(name)
    budget = BUDGETS[name]

    assert lines <= budget["lines"], (
        f"{name} มี {lines} บรรทัด เกินเพดาน {budget['lines']} — "
        "ย้ายเนื้อไปเอกสารเฉพาะแล้วลิงก์กลับมา (ADR 0065) การขยับเพดานต้องมี ADR"
    )
    assert words <= budget["words"], (
        f"{name} มี {words} คำ เกินเพดาน {budget['words']} — การรวมบรรทัดให้ยาวขึ้นไม่นับว่าลดขนาด"
    )


@pytest.mark.parametrize("name", sorted(BUDGETS))
def test_the_ceiling_ratchets_down_when_the_file_shrinks(name):
    """ทิศที่สอง — เพดานที่ลอยสูงเกินคือเพดานที่ไม่ได้ตั้ง

    ตัวนี้คือ ratchet: ย้ายเนื้อออกไปแล้วต้องลดเพดานลงมาด้วย ไม่งั้นที่ว่าง
    ที่เพิ่งได้จะถูกถมกลับในรอบถัดไปโดยไม่มีใครสังเกต
    """
    lines, words = _size(name)
    budget = BUDGETS[name]

    assert budget["lines"] - lines <= budget["line_slack"], (
        f"{name}: เพดาน {budget['lines']} ลอยเหนือของจริง ({lines}) เกิน "
        f"{budget['line_slack']} บรรทัด — ลดเพดานลงมาที่ราว {lines + budget['line_slack']} ก่อน"
    )
    assert budget["words"] - words <= budget["word_slack"], (
        f"{name}: เพดาน {budget['words']} คำ ลอยเหนือของจริง ({words}) เกิน "
        f"{budget['word_slack']} คำ — ลดเพดานลงมาที่ราว {words + budget['word_slack']} ก่อน"
    )


def test_every_file_with_a_budget_exists():
    """เพดานของไฟล์ที่ถูกลบไปแล้ว คือเพดานที่ผ่านตลอดกาล"""
    missing = [name for name in BUDGETS if not (ROOT / name).is_file()]
    assert not missing, f"ตั้งเพดานให้ไฟล์ที่ไม่มีอยู่: {missing}"


# ------------------ เลขที่เขียนซ้ำต้องตรงกัน (audit r13 · ข้อ 3)
#
# เพดานถูกเขียนไว้สามที่: ตารางในไฟล์นี้ · หัว `CLAUDE.md` · หัว `docs/GOVERNANCE.md`
# repo นี้มีธรรมเนียมตรวจ "เลขที่โฆษณาต้องตรงกับของจริง" อยู่แล้วหลายที่ (จำนวน job ·
# จำนวน ADR · พื้น coverage · จำนวน gate ของแกน supply chain) — **กฎที่เพิ่งสร้างใน
# รอบ 11–12 เป็นกฎเดียวที่ยังไม่มี** และเลขที่เขียนซ้ำโดยไม่มีใครเทียบ คือเลขที่
# จะเพี้ยนในวันที่มีคนขยับเพดานแล้วลืมหัวไฟล์

HEADER_LINES = 25  # เพดานถูกประกาศไว้ในย่อหน้าแรกของทั้งสองไฟล์
DECLARED_LINES = re.compile(r"([\d,]+)\s*บรรทัด")
DECLARED_WORDS = re.compile(r"([\d,]+)\s*คำ")


def _declared_in_header(name: str) -> tuple[int | None, int | None]:
    """เลขที่หัวไฟล์ประกาศไว้เอง — อ่านจากย่อหน้าแรกเท่านั้น"""
    head = "\n".join((ROOT / name).read_text(encoding="utf-8").splitlines()[:HEADER_LINES])
    lines = DECLARED_LINES.search(head)
    words = DECLARED_WORDS.search(head)
    return (
        int(lines.group(1).replace(",", "")) if lines else None,
        int(words.group(1).replace(",", "")) if words else None,
    )


@pytest.mark.parametrize("name", sorted(BUDGETS))
def test_the_file_header_quotes_the_same_ceiling_as_the_table(name):
    """หัวไฟล์บอกเพดานของตัวเอง — ถ้ามันไม่ตรงกับที่บังคับจริง คนอ่านจะเชื่อเลขผิด"""
    lines, words = _declared_in_header(name)
    budget = BUDGETS[name]

    assert lines == budget["lines"], (
        f"{name}: หัวไฟล์บอกเพดาน {lines} บรรทัด แต่ที่บังคับจริงคือ {budget['lines']} — "
        "ขยับเพดานแล้วต้องแก้หัวไฟล์ในคอมมิตเดียวกัน"
    )
    assert words == budget["words"], (
        f"{name}: หัวไฟล์บอกเพดาน {words} คำ แต่ที่บังคับจริงคือ {budget['words']}"
    )
