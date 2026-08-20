"""ตารางที่ generate มาแล้ว commit ไว้ ต้องยังใช้ได้จริง — audit รอบ 17 ข้อ 4

สองไฟล์นี้ผลิตโดยสคริปต์ชนิด `generator` ที่**ไม่มีใครแตะเลย**ก่อนรอบ 17:
`scripts/build_eol_table.py` และ `scripts/build_password_blocklist.py` ·
ทั้งคู่ดึงข้อมูลจากภายนอกตอนสร้าง จึงรันซ้ำในเทสต์ไม่ได้ (ด่านที่ต้องต่อเน็ต
คือด่านที่แดงเพราะเน็ต) — **หลักฐานที่ถูกชนิดของ generator คือผลลัพธ์ ไม่ใช่
บรรทัดที่ถูกเดินผ่าน** ที่นี่จึงตรวจตัวไฟล์ที่ commit ไว้ว่ายังอยู่ในรูปที่
ผู้บริโภคของมันอ่านได้

ตรวจสิ่งที่พังได้จริง: ไฟล์หาย · รูปเปลี่ยนจนผู้ใช้อ่านไม่ออก · ว่างเปล่า
(ซึ่งเป็นสภาพที่ script เขียนทับด้วยผลลัพธ์ที่ล้มเหลวได้โดยไม่มีใครรู้)
"""

import datetime
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
EOL_TABLE = ROOT / "docs" / "eol-pinned.json"
BLOCKLIST = ROOT / "app" / "password_blocklist.txt"


def _output_of(script: str, constant: str) -> pathlib.Path:
    """อ่านปลายทางจากสคริปต์เอง — ไม่ใช่เขียนชื่อไฟล์ซ้ำไว้ที่นี่

    เขียนซ้ำเมื่อไหร่ ที่ที่สองจะ drift ทันทีที่มีคนแก้ฝั่งเดียว (ADR 0039)
    """
    source = (ROOT / "scripts" / f"{script}.py").read_text(encoding="utf-8")
    assert f"\n{constant} = " in source, f"{script}.py ไม่ได้ประกาศ {constant} แล้ว"
    return source


def test_the_eol_table_is_still_readable_by_the_page_that_uses_it():
    """หน้า SBOM ของผู้ดูแลอ่านตารางนี้ — รูปพังเมื่อไหร่หน้านั้นพังตาม"""
    _output_of("build_eol_table", "OUT")
    assert EOL_TABLE.is_file(), "ไม่มี docs/eol-pinned.json ทั้งที่ build_eol_table.py ชี้ไปที่มัน"

    data = json.loads(EOL_TABLE.read_text(encoding="utf-8"))
    assert data, "ตาราง EOL ว่างเปล่า — สคริปต์เขียนทับด้วยผลที่ล้มเหลวได้โดยไม่มีใครรู้"

    # คีย์ที่ขึ้นต้นด้วย `_` เป็นข้อมูลกำกับ (แหล่ง · วันที่ดึง) ไม่ใช่ผลิตภัณฑ์ —
    # **และมันคือส่วนที่ทำให้ตารางนี้เทียบได้ทีหลัง** จึงบังคับให้ต้องมี
    for stamp in ("_source", "_fetched_on"):
        assert data.get(stamp), f"ตาราง EOL ไม่มี {stamp} — ตัวเลขที่ไม่รู้ว่ามาจากไหนและเมื่อไหร่"

    products = {name: rows for name, rows in data.items() if not name.startswith("_")}
    assert products, "มีแต่ข้อมูลกำกับ ไม่มีผลิตภัณฑ์สักตัว"
    for name, rows in products.items():
        assert isinstance(rows, list), f"{name}: ต้องเป็นรายการรอบรุ่น"
        assert rows, f"{name}: รายการรอบรุ่นว่างเปล่า"
        for row in rows:
            assert row.get("cycle"), f"{name}: มีแถวที่ไม่บอกว่าเป็นรอบรุ่นไหน"
            assert "eol" in row, (
                f"{name} รอบ {row.get('cycle')}: ไม่มีช่อง eol ซึ่งเป็นเหตุผลทั้งหมดของตาราง"
            )


def test_the_password_blocklist_still_has_entries_in_the_form_the_service_expects():
    """บัญชีดำที่ว่างเปล่าทำให้ทุกรหัสผ่านผ่านนโยบายโดยไม่มีอะไรฟ้อง"""
    _output_of("build_password_blocklist", "OUTPUT_PATH")
    assert BLOCKLIST.is_file(), "ไม่มี app/password_blocklist.txt"

    text = BLOCKLIST.read_text(encoding="utf-8")
    assert "ห้ามแก้ด้วยมือ" in text, "หัวไฟล์ไม่ได้บอกว่ามันถูก generate มา — คนถัดไปจะแก้มือ"

    entries = [
        line for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")
    ]
    assert len(entries) > 10_000, f"บัญชีดำเหลือ {len(entries)} บรรทัด — สั้นผิดปกติ"
    assert all(line == line.strip().lower() for line in entries[:500]), (
        "บางบรรทัดไม่ได้อยู่ในรูปที่ `blocklist_key()` ผลิต — เทียบไม่เจอเงียบ ๆ"
    )


@pytest.mark.parametrize(
    ("script", "constant", "produced"),
    [("build_eol_table", "OUT", EOL_TABLE), ("build_password_blocklist", "OUTPUT_PATH", BLOCKLIST)],
)
def test_the_generator_and_its_output_still_point_at_each_other(script, constant, produced):
    """ปลายทางที่สคริปต์ประกาศ ต้องเป็นไฟล์ที่มีอยู่จริงและถูก commit ไว้"""
    source = _output_of(script, constant)
    assert produced.name in source, (
        f"{script}.py ไม่ได้ชี้ไปที่ {produced.name} แล้ว — ไฟล์ที่ commit ไว้กับตัวสร้างหลุดจากกัน"
    )
    assert produced.is_file()


# ------------- ตัวเลขที่ตารางบอก ต้องมีคนรับ (audit รอบ 20 ข้อ 2)
#
# ระบบรู้ว่า runtime ที่มันรันอยู่หมดอายุเมื่อไหร่ และแสดง "เหลือกี่วัน" บนหน้า
# ผู้ดูแล — แต่ก่อนรอบ 20 **ไม่มีแถวในตารางตรวจตามรอบและไม่มี gate ที่เปลี่ยน
# ตัวเลขนั้นเป็นการกระทำ** · ตัวเลขที่เปลี่ยนทุกวันโดยไม่มีเกณฑ์ ไม่ต่างจาก
# ตัวเลขที่ไม่ได้เก็บ
#
# สองด่านข้างล่างจะแดงเองเมื่อเวลาผ่านไป — ตั้งใจให้เป็นแบบนั้น เหมือน
# `tests/test_cadence.py` · แก้ได้สองทาง: ขยับรุ่น หรือเลื่อนอย่างเปิดเผย

RUNWAY_DAYS = 180  # ต้องเหลือเวลาพอวางแผนขยับรุ่น ไม่ใช่รู้ตอนหมดอายุแล้ว
FETCH_STALE_DAYS = 190  # 6 เดือน + ระยะผ่อน — ตรงกับแถวในตารางตรวจตามรอบ


def test_the_runtime_we_run_on_still_has_runway():
    """python ที่รันอยู่ต้องเหลืออายุพอที่จะวางแผนขยับรุ่นได้

    **ค่าที่ตัดสินคือรอบที่ interpreter ของ CI รันอยู่จริง** ไม่ใช่รอบที่ใหม่ที่สุด
    ในตาราง — ตารางรู้จัก python 3.14 อยู่แล้ว แต่ถ้าเรายังรัน 3.13 อยู่
    ความเสี่ยงเป็นของ 3.13
    """
    running = f"{sys.version_info.major}.{sys.version_info.minor}"
    table = json.loads(EOL_TABLE.read_text(encoding="utf-8"))
    row = next((r for r in table.get("python", []) if r.get("cycle") == running), None)

    assert row, f"ตาราง EOL ไม่รู้จัก python {running} ที่กำลังรันอยู่ — ดึงตารางใหม่"

    left = (datetime.date.fromisoformat(row["eol"]) - datetime.date.today()).days
    assert left >= RUNWAY_DAYS, (
        f"python {running} หมดอายุ {row['eol']} — เหลือ {left} วัน (เกณฑ์ {RUNWAY_DAYS})\n"
        "ขยับรุ่นของ Dockerfile/CI/pyproject หรือเลื่อนอย่างเปิดเผยพร้อมเหตุผลใน "
        "docs/SECURITY-CADENCE.md — ห้ามลดเกณฑ์ให้เงียบ"
    )


def test_the_pinned_table_declares_when_it_was_fetched_and_is_not_stale():
    """ตารางที่ตรึงไว้ต้องมีกฎว่าจะดึงใหม่เมื่อไหร่

    การตรึงถูกแล้ว (ด่านที่ต้องต่อเน็ตคือด่านที่แดงเพราะเน็ต — หลักเดียวกับ
    `docs/asvs-5.0.0.json`) แต่ **ของที่ตรึงไว้โดยไม่มีวันหมดอายุ คือของที่จะ
    ค้างอยู่จนไม่มีใครรู้ว่ามันเก่าแค่ไหน**
    """
    table = json.loads(EOL_TABLE.read_text(encoding="utf-8"))
    fetched = table.get("_fetched_on")

    assert fetched, "ตาราง EOL ไม่ได้บอกว่าดึงมาเมื่อไหร่"

    age = (datetime.date.today() - datetime.date.fromisoformat(fetched)).days
    assert age <= FETCH_STALE_DAYS, (
        f"ตาราง EOL ดึงมาตั้งแต่ {fetched} ({age} วันที่แล้ว · เกณฑ์ {FETCH_STALE_DAYS})\n"
        "รัน `python3 scripts/build_eol_table.py` แล้ว commit ผลลัพธ์"
    )


def test_the_cadence_table_owns_this():
    """เกณฑ์ข้างบนต้องมีแถวในตารางตรวจตามรอบเป็นเจ้าของ — ไม่ใช่ลอยอยู่ในเทสต์

    ด่านที่แดงเองตามเวลาโดยไม่มีใครรับผิดชอบ คือด่านที่จะถูกปิดเสียงในวันที่มันแดง
    """
    cadence = (ROOT / "docs" / "SECURITY-CADENCE.md").read_text(encoding="utf-8")

    assert "eol-pinned.json" in cadence, "ไม่มีแถวในตารางตรวจตามรอบที่เป็นเจ้าของวันหมดอายุของ runtime"
