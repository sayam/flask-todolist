"""ดัชนี ADR ต้องครอบไฟล์ ADR ที่มีอยู่จริงครบทุกใบ

`docs/adr/README.md` เป็นทางเดียวที่คนจะรู้ว่ามีการตัดสินใจอะไรบันทึกไว้บ้าง
โดยไม่ต้องไล่ `ls` — **ดัชนีที่ค้างอยู่แย่กว่าไม่มีดัชนี** เพราะคนอ่านจะเชื่อว่า
เห็นครบแล้วทั้งที่การตัดสินใจล่าสุดไม่อยู่ในนั้น

เจอจริงตอน Phase 7: ดัชนีหยุดอยู่ที่ 0026 ขณะที่ 0027–0033 มีไฟล์อยู่ครบ
ทั้งเจ็ดใบมาจาก Phase 5 กับ 6 ซึ่งเป็นเฟสที่ตัดสินใจเรื่องใหญ่ที่สุดหลายเรื่อง

ที่นี่ **ไม่ตัดสินว่าคำอธิบายในดัชนีเขียนดีไหม** — ตรวจแค่ว่าไม่มีใบไหนหลุด
และไม่มีบรรทัดไหนชี้ไปหาไฟล์ที่ไม่มีอยู่ (หลักเดียวกับ `tests/test_asvs.py`)
"""

import pathlib
import re

import pytest

ADR_DIR = pathlib.Path(__file__).resolve().parent.parent / "docs" / "adr"
INDEX = ADR_DIR / "README.md"

FILENAME = re.compile(r"^(\d{4})-[a-z0-9-]+\.md$")
ROW = re.compile(r"^\|\s*\[(\d{4})\]\(([^)]+)\)\s*\|")


@pytest.fixture(scope="module")
def listed():
    """(เลข ADR, ชื่อไฟล์ที่ดัชนีชี้ไป) ของทุกแถวในดัชนี"""
    rows = [ROW.match(line) for line in INDEX.read_text(encoding="utf-8").splitlines()]
    found = {match.group(1): match.group(2) for match in rows if match}
    assert found, "อ่านดัชนี ADR ไม่ได้เลย — รูปแบบตารางเปลี่ยนไปแล้ว"
    return found


@pytest.fixture(scope="module")
def on_disk():
    """เลข ADR ของทุกไฟล์ที่มีอยู่จริง"""
    numbers = {
        match.group(1): path.name
        for path in ADR_DIR.glob("*.md")
        if (match := FILENAME.match(path.name))
    }
    assert numbers, "ไม่เจอไฟล์ ADR สักใบ"
    return numbers


def test_every_adr_file_is_in_the_index(listed, on_disk):
    missing = sorted(set(on_disk) - set(listed))
    assert not missing, (
        f"ADR ที่มีไฟล์แต่ไม่อยู่ในดัชนี: {[on_disk[n] for n in missing]}\n"
        "ตัดสินใจแล้วต้องมีคนอื่นหาเจอได้ ไม่ใช่แค่มีไฟล์"
    )


def test_the_index_does_not_point_at_missing_files(listed, on_disk):
    dangling = sorted(number for number in listed if number not in on_disk)
    assert not dangling, f"ดัชนีอ้าง ADR ที่ไม่มีไฟล์: {dangling}"


def test_the_index_links_to_the_right_file(listed, on_disk):
    """เลขในดัชนีต้องตรงกับไฟล์ที่ลิงก์ชี้ไป — ก๊อปบรรทัดมาแก้เลขแล้วลืมแก้ลิงก์"""
    wrong = [
        f"{number} → {target}" for number, target in listed.items() if target != on_disk[number]
    ]
    assert not wrong, f"เลขกับไฟล์ที่ลิงก์ไม่ตรงกัน: {wrong}"


def test_adr_numbers_are_unique_and_unbroken(on_disk):
    """เลขห้ามข้ามและห้ามซ้ำ — ช่องว่างแปลว่ามีใบที่หายไปโดยไม่มีใครรู้"""
    numbers = sorted(int(number) for number in on_disk)
    expected = list(range(1, len(numbers) + 1))
    assert numbers == expected, f"เลข ADR ไม่ต่อเนื่อง: ได้ {numbers}"
