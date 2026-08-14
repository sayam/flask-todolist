"""`docs/ARCHITECTURE.md` (42010) ต้องชี้ไปหาของที่มีจริงเท่านั้น (เฟส 13-05)

ไฟล์นั้นประกาศตัวเองว่าเป็น *ดัชนีที่จัดเรียงตามมุมมอง* ไม่ใช่เอกสารที่เล่าเรื่อง
คู่ขนาน — คำสัญญานั้นตรวจได้: ทุก backtick ต้อง resolve (ไฟล์ · ADR · เทสต์)
และหัวข้อที่ 42010 เรียกร้องต้องอยู่ครบ · ที่เหลือ (เนื้อหาถูกไหม) เป็นหน้าที่
ของ ADR ที่มันชี้ไป ซึ่งมีด่านของตัวเองอยู่แล้ว
"""

import pathlib
import re

import pytest

from tests.test_asvs import _unresolved

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "ARCHITECTURE.md"

BACKTICK = re.compile(r"`([^`]+)`")

# หัวข้อที่ 42010 เรียกร้อง — หายไปหัวข้อเดียวคือไม่ conformant แล้ว
REQUIRED_HEADINGS = (
    "## 1. ระบบและบริบท",
    "## 2. ผู้มีส่วนได้เสียและความกังวล",
    "## 3. มุมมอง (viewpoints)",
    "## 4. กติกาความสอดคล้องข้ามภาพ",
    "## 5. เหตุผลของการตัดสินใจ",
    "## 6. การเทียบกับข้อกำหนดของ 42010",
)

VIEWPOINTS = ("Structure", "Data", "Security", "Deployment", "Development")


@pytest.fixture(scope="module")
def text():
    return DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def ci_jobs():
    """ชื่อ job จริงจาก ci.yml — ให้ resolver ตรวจการอ้าง `ci:<job>` ได้"""
    jobs = set()
    ci = ROOT / ".github" / "workflows" / "ci.yml"
    for line in ci.read_text(encoding="utf-8").splitlines():
        found = re.match(r"^  ([a-z][\w-]*):\s*$", line)
        if found:
            jobs.add(found.group(1))
    return jobs


def test_every_required_heading_is_present(text):
    """โครงตาม 42010 ต้องครบ — เอกสาร conformance ที่โครงหายคือเอกสารธรรมดา"""
    missing = [h for h in REQUIRED_HEADINGS if h not in text]
    assert not missing, f"หัวข้อที่หายจาก ARCHITECTURE.md: {missing}"


def test_all_five_viewpoints_are_declared(text):
    missing = [v for v in VIEWPOINTS if v not in text]
    assert not missing, f"viewpoint ที่หาย: {missing}"


def test_every_citation_resolves(text, ci_jobs):
    """backtick ทุกอันชี้ไปหาของจริง — ดัชนีที่อ้างของที่ถูกลบไปแล้วคือดัชนีที่โกหก"""
    broken = []
    for reference in BACKTICK.findall(text):
        problem = _unresolved(reference, ci_jobs)
        if problem:
            broken.append(f"`{reference}` — {problem}")
    assert not broken, "\n  ".join(["การอ้างอิงที่ตาย:", *broken])


def test_correspondence_rules_are_tests_not_prose(text):
    """หัวข้อ 4 สัญญาว่าทุกคู่มีเทสต์บังคับ — ทุกแถวในตารางนั้นจึงต้องอ้างไฟล์เทสต์"""
    section = text.split("## 4.", 1)[1].split("## 5.", 1)[0]
    rows = [line for line in section.splitlines() if line.startswith("| ") and "↔" in line]
    assert rows, "ตาราง correspondence หายไปทั้งตาราง"
    bare = [row for row in rows if "tests/" not in row]
    assert not bare, f"แถว correspondence ที่ไม่มีเทสต์บังคับ: {bare}"


def test_the_rationale_points_at_the_adr_index(text):
    """42010 ต้องการ rationale — ของ repo นี้คือ ADR ทั้งชุด ดัชนีต้องถูกชี้ถึง"""
    assert "docs/adr/README.md" in text
