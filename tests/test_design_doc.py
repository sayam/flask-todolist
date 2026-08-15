"""`docs/DESIGN.md` ต้องตรงกับ UI บนดิสก์ — เอกสาร design ที่เน่าคือเอกสารที่พาหน้าใหม่หลงทาง

สองทิศแบบเดียวกับ DATA-CLASSIFICATION: หน้าเต็มทุกหน้าใน `app/templates/`
ต้องถูกตัดสินว่าอยู่โหมดไหน (Operate/Read/Enter) ในตารางของเอกสาร และทุกแถว
ของตารางต้องชี้ไฟล์ที่มีจริง · ชุดตัวแปรสีที่เอกสารประกาศต้องตรงกับที่
`base.css` ใช้จริงทั้งสองทาง — ตัวแปรที่เพิ่มโดยไม่บอกเอกสาร หรือเอกสารอวด
ตัวแปรที่ไม่มีใครใช้ ต้องแดงทั้งคู่
"""

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "DESIGN.md"
TEMPLATES = ROOT / "app" / "templates"
BASE_CSS = ROOT / "app" / "static" / "base.css"

MODES = ("Operate", "Read", "Enter")

# แถวของตารางหน้า↔โหมด: | `foo.html` | Operate | ... |
ROW = re.compile(r"^\|\s*`([a-z0-9_]+\.html)`\s*\|\s*(\w+)\s*\|", re.MULTILINE)


@pytest.fixture(scope="module")
def text():
    return DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def table(text):
    return dict(ROW.findall(text))


def _full_pages():
    """หน้าเต็ม = ทุก template ยกเว้นโครง base.html และ partial ที่ขึ้นต้น _"""
    return {
        p.name
        for p in TEMPLATES.glob("*.html")
        if p.name != "base.html" and not p.name.startswith("_")
    }


def test_every_full_page_is_assigned_a_mode(table):
    missing = sorted(_full_pages() - table.keys())
    assert not missing, (
        "หน้าเต็มที่ยังไม่ถูกตัดสินโหมดใน docs/DESIGN.md: "
        f"{missing} — เพิ่มแถวในตารางข้อ 2 (Operate/Read/Enter)"
    )


def test_every_table_row_points_at_a_real_template(table):
    ghosts = sorted(table.keys() - _full_pages())
    assert not ghosts, f"ตารางใน docs/DESIGN.md อ้างหน้าที่ไม่มีจริงบนดิสก์: {ghosts} — ลบแถวหรือแก้ชื่อไฟล์ให้ตรง"


def test_every_mode_in_the_table_is_a_declared_mode(table):
    unknown = sorted({(name, mode) for name, mode in table.items() if mode not in MODES})
    assert not unknown, f"โหมดที่ไม่ได้ประกาศในข้อ 2: {unknown} — มีแค่ {MODES}"


def test_theme_variables_in_doc_match_base_css(text):
    doc_vars = set(re.findall(r"`(--[a-z-]+)`", text))
    css_vars = set(re.findall(r"var\((--[a-z-]+)\)", BASE_CSS.read_text(encoding="utf-8")))
    assert doc_vars == css_vars, (
        "ชุดตัวแปรสีในเอกสารกับที่ base.css ใช้จริงไม่ตรงกัน — "
        f"เอกสารมีเกิน: {sorted(doc_vars - css_vars)} · "
        f"base.css ใช้แต่เอกสารไม่บอก: {sorted(css_vars - doc_vars)}"
    )
