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

import json
import pathlib

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
