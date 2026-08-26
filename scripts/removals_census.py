"""หน้าเดียวที่ตอบว่า "ช่วงหลังมีอะไรถูกถอดออกไปบ้าง" — audit รอบ 16 ข้อ 3

**กลไกอยู่ที่ verifiable-gates แล้ว** (ADR 0077 · ขั้น 3d) — `verifiable_gates.removals`
อ่านประวัติและแยก "ถูกถอด" ออกจาก "ถูกเขียนใหม่" · **ที่นี่เหลือทะเบียนว่ากองไหน
อยู่ไฟล์ไหน** ซึ่งเป็นของ todolist ล้วน ๆ

บันทึกของการถอด **มีอยู่ครบแล้วใน git history** ไม่มีอะไรหายจริงในเชิงข้อมูล ·
สิ่งที่ไม่มีคือ *ใครสักคนหรืออะไรสักอย่างที่อ่านมัน* — และนี่เป็นครั้งที่สามที่
โปรเจกต์นี้เจอรูปเดียวกัน (รอบ 13: ไม่มีที่*อ่าน* ไม่ใช่ไม่มีที่*เขียน* · รอบ 15:
ด่านที่รันบนเครื่องได้แต่ไม่มีใครเรียกในจังหวะที่ยังมีประโยชน์)

**ปัญหาที่แท้จริงคือแยกไม่ออก**: `git log -p -- docs/SECURITY-CADENCE.md` ให้บรรทัด
ตารางที่ถูกลบ 31 บรรทัดตลอดอายุ repo · ในนั้นแยกไม่ออกด้วยตาเปล่าว่าอันไหนคือ
"แถวที่ถูกถอด" อันไหนคือ "แถวที่ถูกเขียนใหม่" ต้องเปิดอ่านทีละ diff ซึ่งไม่มีใครทำ

**ตัวนี้ไม่ใช่ทะเบียนใหม่** และตั้งใจให้ไม่เป็น: ไม่เก็บสถานะของตัวเองเลย อ่าน
git log อย่างเดียวแล้วพิมพ์ออกมาหน้าเดียว · ทะเบียนใบที่สิบเอ็ดคือสิ่งสุดท้ายที่
ระบบนี้ต้องการ (audit รอบ 13 วัดไว้แล้ว)

**สิ่งที่นับ**: ของที่ *หายไปจากไฟล์แล้วไม่ได้ถูกเพิ่มกลับ* ในช่วงเวลาที่ถาม —
ไม่ใช่ทุกบรรทัดที่ขึ้นต้นด้วย `-` ในทุก diff · การเปลี่ยนชื่อ (ถอดออกแล้วเพิ่ม
ชื่อใหม่ใน commit เดียวกัน) จึงไม่ถูกนับเป็นการถอด ซึ่งตรงกับความจริง: gate สองตัว
ที่หายไปตลอดอายุ repo เป็นการเปลี่ยนชื่อทั้งคู่

ใช้:
    python3 scripts/removals_census.py                 # 30 วันล่าสุด
    python3 scripts/removals_census.py --since 90.days # ช่วงอื่น

บทบาท: reader — อ่านแล้วรายงาน — หลักฐานคือตัวเลขที่พิมพ์ต้องตรงกับแหล่ง · ห้ามตัดของทิ้งเงียบ
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vendor" / "verifiable-gates" / "src"))

from verifiable_gates import removals  # noqa: E402 — ต้องต่อ path ให้ vendor ก่อน import

# สิ่งที่ถอดแล้วเงียบ — ชื่อกอง → (path ที่ดู, regex ของ "หนึ่งรายการ")
# path ที่ลงท้ายด้วย `/` แปลว่านับ**ไฟล์ที่ถูกลบ** ใต้ไดเรกทอรีนั้น ไม่ใช่บรรทัด
WATCHED: dict[str, removals.Pile] = {
    "gate": removals.Pile("gates.yaml", re.compile(r"^  - id: (\S+)")),
    "แถวตรวจตามรอบ": removals.Pile(
        "docs/SECURITY-CADENCE.md", re.compile(r"^\| \*{0,2}([^|*]{6,60})")
    ),
    "แถวทะเบียนความเสี่ยง": removals.Pile(
        "docs/RISK-ASSESSMENT.md",
        re.compile(r"^\| ([^|]{6,60})\|\s*(?:ต่ำ|กลาง|สูง)"),
    ),
    "ของที่จงใจเลื่อน": removals.Pile("docs/GOVERNANCE.md", re.compile(r"^\| \[?([^|\]]{6,60})")),
    "ไฟล์เทสต์": removals.Pile("tests/", re.compile(r"^(tests/test_\w+\.py)$")),
    "ADR": removals.Pile("docs/adr/", re.compile(r"^(docs/adr/\d{4}-[\w-]+\.md)$")),
}

EPILOGUE = (
    "จำนวนของแต่ละกองถูกประกาศไว้ใน [tool.todolist.removals] ของ pyproject.toml\n"
    "และ scripts/check_ratchets.py ทำให้การถอดต้องมาแก้เลขนั้น (ADR 0069)"
)


def census(since: str) -> tuple[dict[str, list[tuple[str, str, str]]], int]:
    """(ทุกกอง → รายการที่ถูกถอด, จำนวนที่ตีความว่าเป็นการแก้ข้อความ)"""
    return removals.census(ROOT, WATCHED, since)


def main(argv: list[str] | None = None) -> int:
    """พิมพ์รายงาน — คืน 0 เสมอ เพราะนี่คือของอ่าน ไม่ใช่ด่าน"""
    given = list(sys.argv[1:] if argv is None else argv)
    return removals.main(
        ["--root", str(ROOT), *given], root=ROOT, watched=WATCHED, epilogue=EPILOGUE
    )


if __name__ == "__main__":
    sys.exit(main())
