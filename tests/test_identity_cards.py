"""บัตรประจำตัวสองใบต้องตรงกันเอง และตัวเลขในนั้นต้องนับจากทะเบียนได้ — audit รอบ 24

รีโปนี้มีไฟล์ระบุตัวตนสองใบที่ราก และทั้งคู่ถูกอ่านโดย**คนละคนที่ไม่ใช่เรา**:

- `CITATION.cff` — โปรแกรมอ้างอิงและปุ่ม "Cite this repository" ของ GitHub อ่าน
- `.zenodo.json` — Zenodo อ่านตอน archive **ทุกรุ่น** แล้วตีพิมพ์เป็นระเบียนที่มี
  DOI ถาวร ซึ่งแก้ย้อนหลังไม่ได้ตามนิยามของการ archive

ทั้งคู่ประกาศชื่องาน ผู้แต่ง สัญญาอนุญาต คำสำคัญ และบทคัดย่อ**ชุดเดียวกัน** แต่
ก่อนรอบนี้ไม่มีเทสต์ใดเปิดอ่าน `.zenodo.json` เลยแม้แต่ตัวเดียว — ผลที่วัดได้เมื่อ
2026-08-22: ประโยคสุดท้ายของบทคัดย่อบอกจำนวนรอบ audit ไว้**สามค่าสำหรับข้อเท็จจริง
เดียว** — `.zenodo.json` ว่า Sixteen · `CITATION.cff` ว่า Twenty · ทะเบียนบนดิสก์
(`docs/AUDIT-LOG.md`) ว่า 23 — และค่าที่ถูกตีพิมพ์ใต้ DOI คือค่าที่เก่าที่สุด

รูปของความล้มเหลวคือ **ยิ่งข้อความเดินทางไกลจากรีโป เครื่องที่เฝ้ามันยิ่งน้อยลง**
ทั้งที่ปลายทางไกลสุดคือปลายทางเดียวที่แก้ไม่ได้ · สามทิศที่บังคับที่นี่:

- **สองใบต้องตรงกันเอง** ในช่องที่ทับกัน (ชื่อ · สัญญาอนุญาต · ผู้แต่ง · คำสำคัญ)
- **เลขจำนวนรอบต้องเท่ากับจำนวนแถวในทะเบียน** — ทิศเดียวกับที่
  `tests/test_audit_log.py` บังคับกับใบตอบ badge แต่กับไฟล์ที่ออกไปไกลกว่า
- **ต้องเขียนเป็นตัวเลข ไม่ใช่คำ** — `Twenty` รอดมาได้เพราะด่านที่มีอยู่อ่าน
  เฉพาะเลขอารบิก · ข้อความที่เครื่องอ่านไม่ออกคือข้อความที่ไม่มีใครตรวจ
"""

import json
import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CITATION = ROOT / "CITATION.cff"
ZENODO = ROOT / ".zenodo.json"
LOG = ROOT / "docs" / "AUDIT-LOG.md"

ROW = re.compile(r"^\|\s*(\d+)\s*\|", re.MULTILINE)
# คำ/เลขที่นำหน้าวลี "recorded audit rounds" — จับทั้งรูปที่อ่านออกและอ่านไม่ออก
ROUNDS_CLAIM = re.compile(r"([\w-]+)\s+recorded audit rounds")
TAG = re.compile(r"<[^>]+>")


def _squash(text: str) -> str:
    """ตัดขึ้นบรรทัดใหม่ของ YAML block กับแท็ก HTML ของ Zenodo ทิ้งก่อนเทียบ"""
    return " ".join(TAG.sub(" ", text).split())


@pytest.fixture(scope="module")
def citation() -> dict:
    return yaml.safe_load(CITATION.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def zenodo() -> dict:
    return json.loads(ZENODO.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rounds() -> int:
    found = ROW.findall(LOG.read_text(encoding="utf-8"))
    assert found, "อ่านตารางใน docs/AUDIT-LOG.md ไม่ได้เลย — รูปตารางเปลี่ยนหรือ regex เพี้ยน"
    return len(found)


def test_the_two_cards_give_the_same_title(citation, zenodo):
    assert _squash(citation["title"]) == _squash(zenodo["title"]), (
        "ชื่องานใน CITATION.cff กับ .zenodo.json ไม่ตรงกัน — Zenodo ตีพิมพ์ของมัน ส่วนโปรแกรมอ้างอิงอ่านของอีกใบ"
    )


def test_the_two_cards_give_the_same_licence(citation, zenodo):
    assert citation["license"] == zenodo["license"], (
        f"สัญญาอนุญาตไม่ตรงกัน: CITATION.cff={citation['license']!r} "
        f".zenodo.json={zenodo['license']!r} — ระเบียนที่ archive ไปแล้วแก้ไม่ได้"
    )


def test_the_two_cards_credit_the_same_people(citation, zenodo):
    from_cff = [
        (f"{one['family-names']}, {one['given-names']}", one.get("affiliation"))
        for one in citation["authors"]
    ]
    from_zenodo = [(one["name"], one.get("affiliation")) for one in zenodo["creators"]]
    assert from_cff == from_zenodo, f"ผู้แต่งไม่ตรงกัน: {from_cff} vs {from_zenodo}"


def test_the_two_cards_carry_the_same_keywords(citation, zenodo):
    assert citation["keywords"] == zenodo["keywords"], (
        "คำสำคัญไม่ตรงกัน — สองใบนี้อธิบายงานเดียวกันให้เครื่องมือคนละตัวอ่าน"
    )


@pytest.mark.parametrize("name", ["CITATION.cff", ".zenodo.json"])
def test_the_round_count_is_written_as_a_number(name):
    """`Twenty` รอดด่านของ audit รอบ 23 มาได้เพราะไม่มีตัวเลขให้ regex ตัวไหนเห็น"""
    claims = ROUNDS_CLAIM.findall((ROOT / name).read_text(encoding="utf-8"))
    assert claims, f"{name} ไม่ได้บอกจำนวนรอบ audit ในรูปที่เทสต์อ่านได้"

    words = [one for one in claims if not one.isdigit()]
    assert not words, (
        f"{name} เขียนจำนวนรอบเป็นคำ ({words}) — ต้องเป็นตัวเลข ไม่งั้นไม่มีด่านไหนเทียบกับ docs/AUDIT-LOG.md ได้"
    )


@pytest.mark.parametrize("name", ["CITATION.cff", ".zenodo.json"])
def test_the_round_count_equals_the_register(name, rounds):
    claims = {
        int(one)
        for one in ROUNDS_CLAIM.findall((ROOT / name).read_text(encoding="utf-8"))
        if one.isdigit()
    }
    wrong = sorted(one for one in claims if one != rounds)
    assert not wrong, (
        f"{name} อ้างว่ามี audit {wrong} รอบ แต่ docs/AUDIT-LOG.md มี {rounds} แถว — "
        "ไฟล์นี้ถูกตีพิมพ์ออกไปพร้อม DOI ที่แก้ย้อนหลังไม่ได้"
    )
