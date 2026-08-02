"""ทุกคอลัมน์ในฐานข้อมูลต้องถูกจำแนกชั้นไว้ใน docs/DATA-CLASSIFICATION.md

เอกสารจำแนกชั้นข้อมูลจะมีประโยชน์ก็ต่อเมื่อมันตรงกับของจริง — เอกสารที่ตกหล่น
คอลัมน์ใหม่ไปเงียบ ๆ แย่กว่าไม่มีเอกสารเลย เพราะทำให้เชื่อว่าครบทั้งที่ไม่ครบ
เทสต์นี้บังคับว่าเพิ่มคอลัมน์แล้วต้องกลับไปตอบให้ได้ว่ามันอยู่ชั้นไหน

ไม่ตรวจว่า "จัดชั้นถูกไหม" — นั่นเป็นการตัดสินใจของคน (ดู ADR 0014)
ตรวจแค่ว่า **ไม่มีคอลัมน์ไหนหลุดการพิจารณา**
"""

import fnmatch
import pathlib
import re

import pytest

from app import db
from app.models import Category, Todo, User  # noqa: F401  ต้อง import ให้ metadata ครบ

DOC = pathlib.Path(__file__).resolve().parent.parent / "docs" / "DATA-CLASSIFICATION.md"

# ตารางชั้นข้อมูลจบตรงหัวข้อถัดไป — อ่านเฉพาะช่วงนั้น ไม่ใช่ทั้งไฟล์
# (ไม่งั้นชื่อคอลัมน์ที่โผล่ในหัวข้ออื่นจะถูกนับว่า "จำแนกแล้ว" ทั้งที่ไม่ได้อยู่ในตาราง)
SECTION = "## ชั้นข้อมูล"
NEXT_SECTION = "## ระยะเก็บรักษา"


@pytest.fixture(scope="module")
def classified():
    """ชื่อทุกอย่างที่ถูกใส่ backtick ไว้ในตารางชั้นข้อมูล"""
    text = DOC.read_text(encoding="utf-8")
    start = text.index(SECTION)
    end = text.index(NEXT_SECTION, start)
    return set(re.findall(r"`([^`]+)`", text[start:end]))


def _is_classified(table_name, column_name, classified):
    """คอลัมน์นับว่าจำแนกแล้วถ้าเอกสารอ้างชื่อเปล่า, `ตาราง.คอลัมน์` หรือ pattern"""
    candidates = {column_name, f"{table_name}.{column_name}"}
    if candidates & classified:
        return True
    return any(fnmatch.fnmatch(column_name, pattern) for pattern in classified if "*" in pattern)


def test_every_column_is_classified(app, classified):
    with app.app_context():
        unclassified = [
            f"{table.name}.{column.name}"
            for table in db.metadata.sorted_tables
            for column in table.columns
            if not _is_classified(table.name, column.name, classified)
        ]
    assert not unclassified, (
        "คอลัมน์ที่ยังไม่ถูกจำแนกชั้นใน docs/DATA-CLASSIFICATION.md:\n"
        + "\n".join(unclassified)
        + "\nเพิ่มคอลัมน์แล้วต้องระบุด้วยว่าอยู่ชั้นไหน (ดู ADR 0014)"
    )


def test_the_document_lists_every_class(classified):
    """ตัวเอกสารเองต้องยังมีครบทั้ง 6 ชั้น — กันการลบทิ้งบางส่วนโดยไม่ตั้งใจ"""
    text = DOC.read_text(encoding="utf-8")
    for label in ("C1", "C2", "C3", "C4", "C5", "C6"):
        assert f"**{label}**" in text, f"เอกสารขาดชั้น {label}"


def test_password_hash_is_the_only_secret(classified):
    """C1 ต้องมีตัวเดียว — เพิ่มความลับใหม่ต้องมาทบทวนกติกา 'ห้ามออกจากระบบ' ด้วย"""
    text = DOC.read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.startswith("| **C1**"))
    assert row.count("`") == 2, f"C1 ควรมีฟิลด์เดียว แถวคือ: {row}"
    assert "password_hash" in row
