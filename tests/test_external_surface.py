"""ผิวที่อยู่นอกการควบคุมเวอร์ชัน ต้องมีทะเบียนและทุกแถวต้องมีเจ้าของ — audit รอบ 24 · ADR 0072

`scripts/audit_posture.py` เฝ้าท่าทีของแพลตฟอร์มมาตั้งแต่ ADR 0061 และทำได้ครบตาม
ที่มันประกาศไว้ — แต่ขอบเขตของมันสืบทอดมาจากคำถามที่สร้างมันขึ้นมา ("สิ่งที่
ADR 0053 ประกาศยังจริงไหม") มันจึงมองไม่เห็นของที่เราไม่เคยประกาศ · วัดจริง
2026-08-22: สาม endpoint ที่มันเรียกอยู่แล้วคืนค่ามา 75 ฟิลด์ · อ่านอยู่ 12

ทะเบียน `docs/EXTERNAL-SURFACE.md` จึงถือ*ทั้งผิว* ไม่ใช่เฉพาะส่วนที่ถูกตรวจ และ
สิ่งที่เทสต์นี้บังคับคือ **ทุกแถวต้องบอกว่าใครเทียบมันกับของจริง** ด้วยคำศัพท์ปิด
สี่คำ · `ยังไม่มีใคร` เป็นคำตอบที่ยอมรับได้และถูกนับด้วยเพดานที่โตไม่ได้ —
เพราะคำตอบที่ไม่มีใครนับจะกลายเป็นค่าเริ่มต้นเงียบ ๆ ของทุกฟิลด์ใหม่

ทิศที่สำคัญที่สุดคือ **ผูกสองทิศกับตัวตรวจจริง**: แถวที่อ้างว่า `ci:posture`
ดูแลอยู่ ต้องเป็นฟิลด์ที่ `audit_posture.judged_fields()` ตัดสินจริง และทุกฟิลด์
ที่มันตัดสินต้องมีแถว — ทะเบียนที่ drift จากตัวตรวจอ่านแล้วเข้าใจผิดกว่าไม่มีทะเบียน
"""

import pathlib
import re

import pytest

from scripts import audit_posture, check_ratchets

ROOT = pathlib.Path(__file__).resolve().parent.parent
REGISTER = ROOT / "docs" / "EXTERNAL-SURFACE.md"
CADENCE = ROOT / "docs" / "SECURITY-CADENCE.md"

ROW = re.compile(r"^\|([^|\n]+)\|([^|\n]+)\|([^|\n]+)\|\s*$", re.MULTILINE)
FIELD = re.compile(r"`([a-z_]+)`")
OWNED_BY_MACHINE = "ci:posture"
NOBODY = "ยังไม่มีใคร"


@pytest.fixture(scope="module")
def rows() -> list[tuple[str, str]]:
    """(ช่องแรก, เจ้าของ) ของทุกแถวข้อมูล — ตัดหัวตารางกับเส้นคั่นทิ้ง"""
    found = [
        (what.strip(), owner.strip())
        for what, _want, owner in ROW.findall(REGISTER.read_text(encoding="utf-8"))
        if not set(what.strip()) <= set("-: ") and owner.strip() != "ใครเทียบ"
    ]
    assert found, "อ่านตารางใน docs/EXTERNAL-SURFACE.md ไม่ได้เลย — รูปตารางเปลี่ยนไปแล้ว"
    return found


def _owners(cell: str) -> list[str]:
    return [one.strip().strip("`") for one in cell.split("·")]


def test_every_row_names_an_owner_from_the_closed_vocabulary(rows):
    """ช่องที่เขียนอะไรก็ได้ คือช่องที่ทุกแถวจะกลายเป็น "มีคนดูแลอยู่" ภายในสองเดือน"""
    strange = [
        (what, owner)
        for what, cell in rows
        for owner in _owners(cell)
        if owner not in (OWNED_BY_MACHINE, NOBODY) and not owner.startswith(("tests/", "cadence:"))
    ]
    assert not strange, f"เจ้าของที่ไม่อยู่ในคำศัพท์สี่คำ: {strange}"


def test_owners_that_point_at_a_test_file_exist(rows):
    ghosts = [
        owner
        for _what, cell in rows
        for owner in _owners(cell)
        if owner.startswith("tests/") and not (ROOT / owner).is_file()
    ]
    assert not ghosts, f"แถวชี้ไปหาไฟล์เทสต์ที่ไม่มีอยู่: {ghosts}"


def test_owners_that_point_at_a_cadence_row_exist(rows):
    """`cadence:` ที่ชี้ไปหาแถวที่ไม่มี คือการบอกว่ามีคนตรวจให้ทั้งที่ไม่มี"""
    text = CADENCE.read_text(encoding="utf-8")
    ghosts = [
        owner
        for _what, cell in rows
        for owner in _owners(cell)
        if owner.startswith("cadence:") and owner.removeprefix("cadence:") not in text
    ]
    assert not ghosts, f"แถวอ้างรอบตรวจที่หาไม่เจอใน docs/SECURITY-CADENCE.md: {ghosts}"


def test_the_register_and_the_checker_agree_both_ways(rows):
    """ตัวตรวจเลิกอ่านฟิลด์ไหน ทะเบียนต้องเปลี่ยนตามในคอมมิตเดียวกัน"""
    claimed = {
        name
        for what, cell in rows
        if OWNED_BY_MACHINE in _owners(cell)
        for name in FIELD.findall(what)
    }
    judged = audit_posture.judged_fields()

    assert not judged - claimed, f"ตัวตรวจอ่านฟิลด์ที่ทะเบียนไม่มีแถวให้: {sorted(judged - claimed)}"
    assert not claimed - judged, (
        f"ทะเบียนอ้างว่า ci:posture ดูแลฟิลด์ที่มันไม่ได้อ่าน: {sorted(claimed - judged)}"
    )


def test_the_ceiling_counts_the_same_rows_this_test_reads(rows):
    """ตัวนับของเพดาน (`scripts/check_ratchets.py`) กับตัวอ่านทะเบียนต้องเห็นเซตเดียวกัน

    เพดานเองอยู่ที่ `pyproject.toml` และถูกบังคับสองทิศโดย `check_ratchets` อยู่แล้ว —
    สิ่งที่ยังไม่มีใครยืนยันคือ *มันนับแถวชุดเดียวกับที่ทะเบียนบอกไหม* · ตัวนับที่
    อ่านคนละเซตกับทะเบียน จะรายงานเพดานของกองที่ไม่มีใครหมายถึง
    """
    from_register = sum(1 for _what, cell in rows if NOBODY in _owners(cell))

    assert check_ratchets.external_surface_unowned() == from_register
