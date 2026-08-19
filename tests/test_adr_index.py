"""ดัชนี ADR ต้องครอบไฟล์ ADR ที่มีอยู่จริงครบทุกใบ

`docs/adr/README.md` เป็นทางเดียวที่คนจะรู้ว่ามีการตัดสินใจอะไรบันทึกไว้บ้าง
โดยไม่ต้องไล่ `ls` — **ดัชนีที่ค้างอยู่แย่กว่าไม่มีดัชนี** เพราะคนอ่านจะเชื่อว่า
เห็นครบแล้วทั้งที่การตัดสินใจล่าสุดไม่อยู่ในนั้น

เจอจริงตอน Phase 7: ดัชนีหยุดอยู่ที่ 0026 ขณะที่ 0027–0033 มีไฟล์อยู่ครบ
ทั้งเจ็ดใบมาจาก Phase 5 กับ 6 ซึ่งเป็นเฟสที่ตัดสินใจเรื่องใหญ่ที่สุดหลายเรื่อง

ที่นี่ **ไม่ตัดสินว่าคำอธิบายในดัชนีเขียนดีไหม** — ตรวจแค่ว่าไม่มีใบไหนหลุด
และไม่มีบรรทัดไหนชี้ไปหาไฟล์ที่ไม่มีอยู่ (หลักเดียวกับ `tests/test_asvs.py`)

## การแทนที่ต้องถูกบันทึกสองทิศ (audit รอบ 14 ข้อ 1)

ทะเบียนทุกใบของ repo นี้ถูกตรวจสองทิศมาตั้งแต่ audit รอบ 9 — **ยกเว้นทะเบียน
คำตัดสิน ซึ่งเก่าที่สุดและถูกอ้างบ่อยที่สุด** · ผลคือ ADR 0035 บอกว่าตัวเองแทน
ข้อ 1 ของ ADR 0032 ตั้งแต่ 2026-08-12 แต่ **หน้าของ 0032 เองไม่มีบรรทัดไหนรู้ตัว**
และดัชนียังขึ้นว่า `accepted` เฉย ๆ

ราคาที่จ่ายไปจริง: docstring หัวไฟล์ของ `app/audit.py` — สิ่งแรกที่คนอ่านก่อนแก้ —
ชี้มาที่ ADR 0032 ในฐานะ*กลไกปัจจุบัน* ทั้งที่ `CLAUDE.md` ห้ามกลับไปใช้กลไกนั้น
ตรง ๆ · **คนที่เปิดใบเก่าใบเดียวไม่มีทางรู้ว่ามันถูกแทนแล้ว** และนั่นคือคนที่จะ
พาโค้ดกลับไปสู่ deadlock ที่ ADR 0035 เพิ่งแก้

จึงตรวจสามอย่าง: ใบที่ถูกแทนต้องประกาศบนหน้าตัวเอง · ดัชนีต้องบอกด้วย · และ
**ทิศกลับ** — ใบที่ประกาศว่าตัวเองถูกแทน ต้องมีใบที่แทนมันอยู่จริง
"""

import pathlib
import re

import pytest

ADR_DIR = pathlib.Path(__file__).resolve().parent.parent / "docs" / "adr"
INDEX = ADR_DIR / "README.md"

FILENAME = re.compile(r"^(\d{4})-[a-z0-9-]+\.md$")
ROW = re.compile(r"^\|\s*\[(\d{4})\]\(([^)]+)\)\s*\|(.*)$")

# "แทนที่ ADR 0032" / "แทนที่วิธีของ [ADR 0032](...)" — **ต้องมีเลขตามหลังเสมอ**
# ไม่งั้นจะไปจับ "แทนที่จะ" ซึ่งเป็นคำเชื่อมภาษาไทยธรรมดาที่โผล่ทั่วทุกใบ
SUPERSEDES = re.compile(r"แทน(?:ที่|วิธีของ)?\s*(?:วิธีของ\s*)?\[?ADR (\d{4})")
# ฝั่งใบที่ถูกแทน — ประกาศบนหน้าตัวเองว่าโดนใบไหนแทน
SUPERSEDED_BY = re.compile(r"ถูกแทน(?:ที่)?โดย\s*\[?ADR (\d{4})")
# หัวใบ = ตั้งแต่บรรทัดแรกจนถึงหัวข้อแรก · ประกาศต้องอยู่ตรงนี้ ไม่ใช่ซ่อน
# อยู่กลางใบ เพราะคนที่เปิดมาอ่านต้องเห็นก่อนเชื่อเนื้อข้างใน
HEADER_LINES = 12


@pytest.fixture(scope="module")
def listed():
    """(เลข ADR, ชื่อไฟล์ที่ดัชนีชี้ไป) ของทุกแถวในดัชนี"""
    rows = [ROW.match(line) for line in INDEX.read_text(encoding="utf-8").splitlines()]
    found = {match.group(1): match.group(2) for match in rows if match}
    assert found, "อ่านดัชนี ADR ไม่ได้เลย — รูปแบบตารางเปลี่ยนไปแล้ว"
    return found


@pytest.fixture(scope="module")
def listed_rows():
    """เลข ADR → ส่วนที่เหลือของแถวในดัชนี (คำอธิบาย + สถานะ)"""
    rows = [ROW.match(line) for line in INDEX.read_text(encoding="utf-8").splitlines()]
    found = {match.group(1): match.group(3) for match in rows if match}
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


# ---------------------------------------------------------------- การแทนที่


@pytest.fixture(scope="module")
def pages(on_disk) -> dict[str, str]:
    """เลข ADR → เนื้อไฟล์ทั้งใบ"""
    return {
        number: (ADR_DIR / name).read_text(encoding="utf-8") for number, name in on_disk.items()
    }


def _header(text: str) -> str:
    """หัวใบ — ที่ที่คนอ่านเห็นก่อนตัดสินใจเชื่อเนื้อข้างใน"""
    return "\n".join(text.splitlines()[:HEADER_LINES])


@pytest.fixture(scope="module")
def supersessions(pages) -> dict[str, set[str]]:
    """เลขใบที่ถูกแทน → เซตของใบที่แทนมัน (อ่านจากหัวใบของฝั่งที่มาแทน)"""
    found: dict[str, set[str]] = {}
    for number, text in pages.items():
        for target in SUPERSEDES.findall(_header(text)):
            if target != number:
                found.setdefault(target, set()).add(number)
    return found


def test_a_superseded_adr_says_so_on_its_own_page(supersessions, pages, on_disk):
    """ทิศแรก — ใบที่ถูกแทนต้องรู้ตัว

    คนที่เปิดใบเก่าใบเดียว (เช่นเพราะ docstring ในโค้ดชี้มา) ต้องเห็นทันทีว่า
    คำตัดสินนี้ถูกแทนแล้ว ไม่ใช่รู้ก็ต่อเมื่อบังเอิญไปอ่านใบใหม่
    """
    silent = []
    for target, replacements in sorted(supersessions.items()):
        acknowledged = set(SUPERSEDED_BY.findall(_header(pages[target])))
        missing = replacements - acknowledged
        if missing:
            silent.append(f"{on_disk[target]} ไม่ได้บอกว่าถูกแทนโดย {sorted(missing)}")
    assert not silent, (
        "ADR ที่ถูกแทนแล้วแต่หน้าตัวเองไม่รู้ตัว:\n  " + "\n  ".join(silent) + "\n"
        "เติมบรรทัด '**ข้อ N ถูกแทนที่โดย [ADR XXXX](...)**' ในหัวใบ — "
        "การแทนที่ที่บันทึกทางเดียว คือกับดักที่รอคนถัดไปเปิดใบเก่า"
    )


def test_the_index_marks_superseded_decisions(supersessions, listed_rows, on_disk):
    """ดัชนีต้องบอกด้วย — คนส่วนใหญ่เห็นดัชนีก่อนเห็นใบ"""
    plain = []
    for target, replacements in sorted(supersessions.items()):
        rest = listed_rows[target]
        if not any(number in rest for number in replacements):
            plain.append(f"{on_disk[target]} → แถวในดัชนีไม่ได้บอกว่าถูกแทนโดย {sorted(replacements)}")
    assert not plain, "แถวในดัชนีที่ยังขึ้นเหมือนใบที่ยังใช้อยู่:\n  " + "\n  ".join(plain)


def test_every_claim_of_being_superseded_has_a_replacement(pages, supersessions, on_disk):
    """ทิศกลับ — ใบที่บอกว่าตัวเองถูกแทน ต้องมีใบที่แทนมันอยู่จริง

    ป้ายที่ชี้ไปหาใบที่ไม่ได้แทนอะไร แย่กว่าไม่มีป้าย เพราะมันทำให้คนเลิกอ่าน
    คำตัดสินที่ยังใช้อยู่ (หลักเดียวกับทะเบียนข้อยกเว้นที่ ID หายไปแล้ว)
    """
    dangling = [
        f"{on_disk[number]} อ้างว่าถูกแทนโดย {claimed} แต่ใบนั้นไม่ได้บอกว่าแทนใคร"
        for number, text in sorted(pages.items())
        for claimed in SUPERSEDED_BY.findall(_header(text))
        if claimed not in supersessions.get(number, set())
    ]
    assert not dangling, "\n  ".join(["ป้ายการแทนที่ที่ชี้ไปหาที่ว่าง:", *dangling])
