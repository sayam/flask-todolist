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


# ความลับทุกตัวที่ทบทวนแล้วว่ายอมรับกติกา "ห้ามออกจากระบบทุกกรณี" ได้
# **เพิ่มชื่อที่นี่ = ประกาศว่าทบทวนแล้ว** ไม่ใช่แค่ทำให้เทสต์เขียว
REVIEWED_SECRETS = {
    "tdl_user.password_hash",  # C1 ตั้งแต่ Phase 2 (ADR 0014)
    "tdl_api_token.token_hash",  # C1 เพิ่มตอน Phase 3 พร้อม PAT (ADR 0017)
}


def test_every_secret_was_explicitly_reviewed(classified):
    """C1 ต้องตรงกับรายการที่ทบทวนแล้วเป๊ะ — ทั้งเพิ่มและลดต้องผ่านสายตาคน

    ความลับใหม่แต่ละตัวมีต้นทุนตามมาเสมอ (ห้ามอยู่ใน export/log/audit,
    ต้องมีเส้นทางล้างทิ้งของตัวเอง) การเพิ่มโดยไม่ทบทวนคือการรับหนี้เงียบ ๆ
    """
    text = DOC.read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.startswith("| **C1**"))
    listed = set(re.findall(r"`([^`]+)`", row))
    assert listed == REVIEWED_SECRETS, f"C1 ในเอกสารไม่ตรงกับรายการที่ทบทวนแล้ว: {listed}"
