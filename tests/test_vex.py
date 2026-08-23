"""เอกสาร VEX ต้องตรงกับทะเบียนที่มันอ้างว่าแปลมา — `OSPS-VM-04.02`

โปรเจกต์นี้ตัดสิน CVE ทุกใบอยู่แล้วและบังคับให้เหตุผลอยู่ใน
`docs/SECURITY-CADENCE.md` สองทิศ — แต่คำตัดสินนั้นเป็นร้อยแก้วภาษาไทย ปลายทางที่
รันสแกนเนอร์ใส่ image ของเราแล้วเห็น CVE เดียวกันจึงไม่มีทางรู้ว่าเราตัดสินไว้ว่าอย่างไร

`docs/vex.openvex.json` เป็น *ภาพพิมพ์* ของทะเบียน ไม่ใช่แหล่งความจริงใบที่สอง —
สิ่งที่ต้องบังคับจึงเป็น **มันตรงกับต้นทางสองทิศ** และ **ไม่ตอบเกินกว่าที่ทะเบียนพูด**

ทิศที่บังคับ:

- ทุก advisory ในทะเบียน ต้องมี statement · ทุก statement ต้องมาจากทะเบียน
- ไฟล์ที่ commit ต้องตรงกับผล generate สด (หลักฐานของ generator)
- `not_affected` ต้องมี justification หรือ impact_statement เสมอ (ข้อบังคับของ OpenVEX)
- **`affected` ต้องมี `action_statement`** — และของที่อยู่ใน image จริงต้องเป็น
  `affected` ไม่ใช่ `not_affected` เพราะสแกนเนอร์ของผู้ใช้จับการโกหกข้อนี้ได้เอง
"""

import json
import pathlib

import pytest

from scripts import build_vex

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "vex.openvex.json"
OPENVEX_STATUSES = {"not_affected", "affected", "fixed", "under_investigation"}
OPENVEX_JUSTIFICATIONS = {
    "component_not_present",
    "vulnerable_code_not_present",
    "vulnerable_code_not_in_execute_path",
    "vulnerable_code_cannot_be_controlled_by_adversary",
    "inline_mitigations_already_exist",
}


@pytest.fixture(scope="module")
def doc() -> dict:
    return json.loads(OUT.read_text(encoding="utf-8"))


def test_the_committed_file_is_what_the_generator_produces():
    """หลักฐานที่ถูกชนิดของ generator — ผลลัพธ์ต้องตรงกับที่ commit ไว้"""
    assert OUT.read_text(encoding="utf-8") == build_vex.render(), (
        "docs/vex.openvex.json ไม่ตรงกับทะเบียน — รัน PYTHONPATH=. python3 scripts/build_vex.py"
    )


def test_every_accepted_advisory_has_a_statement(doc):
    """ทิศแรก — ใบที่รับไว้แล้วแต่ไม่มีใน VEX คือคำตัดสินที่ปลายทางไม่มีทางรู้"""
    declared = {advisory for advisory, _register in build_vex.declared()}
    stated = {row["vulnerability"]["name"] for row in doc["statements"]}

    assert declared - stated == set(), f"advisory ที่ไม่มี statement: {sorted(declared - stated)}"


def test_every_statement_comes_from_a_register(doc):
    """ทิศกลับ — statement ที่ไม่มีต้นทางคือคำพูดที่ไม่มีใครตัดสิน"""
    declared = {advisory for advisory, _register in build_vex.declared()}
    stated = {row["vulnerability"]["name"] for row in doc["statements"]}

    assert stated - declared == set(), f"statement ที่ไม่มีในทะเบียน: {sorted(stated - declared)}"


def test_every_statement_is_shaped_the_way_openvex_requires(doc):
    assert doc["@context"] == build_vex.CONTEXT
    for row in doc["statements"]:
        name = row["vulnerability"]["name"]
        assert row["status"] in OPENVEX_STATUSES, f"{name}: สถานะที่ OpenVEX ไม่รู้จัก"
        assert row["products"], f"{name}: ไม่ได้บอกว่าเป็นของผลิตภัณฑ์ไหน"
        assert row["products"][0]["subcomponents"], f"{name}: ไม่ได้บอกว่าเป็นของแพ็กเกจไหน"
        if row["status"] == "not_affected":
            assert row.get("justification") in OPENVEX_JUSTIFICATIONS or row.get(
                "impact_statement"
            ), f"{name}: not_affected ต้องมี justification หรือ impact_statement"
        if row["status"] == "affected":
            assert row.get("action_statement"), f"{name}: affected ต้องบอกว่าจะทำอะไรต่อ"


def test_what_is_inside_the_image_is_not_claimed_to_be_absent(doc):
    """ของที่อยู่ใน OS layer จริง ต้องเป็น `affected` — สแกนเนอร์ของผู้ใช้จับได้เอง"""
    from_image = {advisory for advisory, register in build_vex.declared() if "image" in register}
    lying = [
        row["vulnerability"]["name"]
        for row in doc["statements"]
        if row["vulnerability"]["name"] in from_image and row["status"] != "affected"
    ]

    assert not lying, f"advisory ที่อยู่ใน image จริงแต่ตอบว่าไม่กระทบ: {lying}"


def test_an_advisory_without_a_named_package_is_loud_not_skipped():
    """VEX ที่ไม่บอกว่าเป็นของชิ้นไหน คือเอกสารที่ปลายทางเอาไปทำอะไรไม่ได้"""
    with pytest.raises(ValueError, match="หาแพ็กเกจ"):
        build_vex.package_of("CVE-0000-00000")
