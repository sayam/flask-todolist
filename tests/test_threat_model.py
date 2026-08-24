"""threat model ต้องผูกกับโค้ดจริง ไม่ใช่จริงเฉพาะวันที่เขียน — `OSPS-SA-03.02`

`docs/THREAT-MODEL.md` ตอบคำถามที่ทะเบียนความเสี่ยงกับใบประเมิน ASVS/ISO ตอบไม่ได้
(ใครโจมตีอะไรได้ ผ่านทางไหน อะไรขวางอยู่) · เอกสารชนิดนี้เน่าเงียบที่สุดในบรรดา
เอกสารทั้งหมด เพราะ **ผิวการโจมตีเปลี่ยนทุกครั้งที่มี route ใหม่** แต่ไม่มีอะไร
บังคับให้ใครกลับมาอ่านมัน

สามทิศที่บังคับ:

- **รายการ route สาธารณะต้องตรงกับตัวบังคับจริงสองทิศ** — `PUBLIC_ROUTES` ของ
  `tests/test_route_authz.py` คือรายการที่ *แอปจริง* ถูกตรวจด้วย · เพิ่ม route ที่
  ไม่ต้อง login โดยไม่มาแก้ threat model = แดง · และชื่อผีในเอกสารก็แดงเหมือนกัน
- **gate ที่เอกสารอ้างต้องมีอยู่จริง** — หลักเดียวกับหลักฐานใน `docs/ASVS.md`
- **ADR ที่อ้างต้องมีไฟล์** — คำอ้างที่ชี้ไปที่ว่างเปล่าไม่ใช่หลักฐาน
"""

import pathlib
import re

import pytest
import yaml

import tests.test_route_authz as route_authz

ROOT = pathlib.Path(__file__).resolve().parent.parent
MODEL = ROOT / "docs" / "THREAT-MODEL.md"
GATES = ROOT / "gates.yaml"

# จับ **ทุกอย่างที่อยู่ในเครื่องหมาย** ไม่ใช่เฉพาะรูปที่ถูกต้อง — รูปที่แคบไป
# ทำให้ชื่อที่พิมพ์ผิดหลุดออกจากเซตแล้วด่านผ่านฟรี (จับได้ตอน mutation ทิศที่ 3)
GATE_REF = re.compile(r"`gate ([^`]+)`")
ADR_REF = re.compile(r"ADR (\d{4})")
ROUTE_ROW = re.compile(r"\| HTTP ที่ไม่ต้องมีตัวตน \| (.+?) \|")


@pytest.fixture(scope="module")
def text() -> str:
    return MODEL.read_text(encoding="utf-8")


def test_the_public_routes_match_the_list_the_app_is_held_to(text):
    """สองทิศ — ผิวที่เปิดสาธารณะเปลี่ยนเมื่อไหร่ threat model ต้องเปลี่ยนตาม"""
    row = ROUTE_ROW.search(text)
    assert row, "หาแถว 'HTTP ที่ไม่ต้องมีตัวตน' ในตารางผิวการโจมตีไม่เจอ"

    named = set(re.findall(r"`(\w+)`", row.group(1)))
    enforced = set(route_authz.PUBLIC_ROUTES)

    assert not enforced - named, (
        f"route ที่เปิดสาธารณะแต่ threat model ไม่ได้พูดถึง: {sorted(enforced - named)} — "
        "ผิวใหม่ต้องเข้ามาในเอกสารในคอมมิตเดียวกับที่มันเกิด"
    )
    assert not named - enforced, (
        f"threat model อ้าง route สาธารณะที่ไม่มีจริงแล้ว: {sorted(named - enforced)}"
    )


def test_the_number_it_advertises_is_the_number_that_is_enforced(text):
    """เลขที่เขียนไว้ในร้อยแก้วเน่าเร็วกว่าตาราง — ให้เครื่องอ่านคู่ตั้งแต่แรก"""
    said = re.search(r"route สาธารณะ (\d+) ตัว", text)

    assert said, "ข้อ 3 ไม่ได้บอกจำนวน route สาธารณะในรูปที่เทสต์อ่านได้"
    assert int(said.group(1)) == len(route_authz.PUBLIC_ROUTES), (
        f"threat model บอก {said.group(1)} ตัว แต่รายการที่บังคับจริงมี {len(route_authz.PUBLIC_ROUTES)}"
    )


def test_every_gate_it_leans_on_exists(text):
    ids = {gate["id"] for gate in yaml.safe_load(GATES.read_text(encoding="utf-8"))["gates"]}
    ghosts = sorted(set(GATE_REF.findall(text)) - ids)

    assert not ghosts, f"threat model อ้าง gate ที่ไม่มีใน gates.yaml: {ghosts}"


def test_every_adr_it_cites_exists(text):
    missing = sorted(
        {
            number
            for number in ADR_REF.findall(text)
            if not list((ROOT / "docs" / "adr").glob(f"{number}-*.md"))
        }
    )

    assert not missing, f"threat model อ้าง ADR ที่ไม่มีไฟล์: {missing}"


def test_it_says_what_it_cannot_answer(text):
    """model ที่ไม่บอกขอบเขตของตัวเอง ถูกอ่านเป็นคำสัญญาที่มันไม่ได้ให้"""
    assert "สิ่งที่ model นี้ตอบไม่ได้" in text
    assert "residual" in text.lower(), "ต้องมีตารางของสิ่งที่รู้ว่ายังไม่ได้ป้องกัน"
