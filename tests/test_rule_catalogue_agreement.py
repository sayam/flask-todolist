"""กฎ portable ที่นี่ กับคลังกฎของ verifiable-gates ต้องเป็นเรื่องเดียวกัน

ตั้งแต่ขั้น 6 ของการถอด **บ้านของ *กฎ* คือ `vendor/verifiable-gates/rules.yaml`**
ส่วนที่นี่เก็บ *การบังคับ* ของกฎเหล่านั้น — เทสต์ไฟล์ไหน job ไหน · สองอย่างนี้
อายุไม่เท่ากัน ตัวบังคับย้ายทุกครั้งที่จัดระเบียบเทสต์ใหม่ ส่วนกฎเปลี่ยนเมื่อ
ความจริงสอนอะไรใหม่เท่านั้น

**ทำไมยังเก็บถ้อยคำไว้สองที่**: ทะเบียนที่นี่ถูกอ่านโดยเครื่องมืออีกหลายตัว
(หน้าค้าง · GATES-ASVS · ตัวนับ pillar) ซึ่งต้องการ `title`/`born_from` ในไฟล์
เดียวกับที่มันอ่านอยู่แล้ว · ทางที่ถูกจึงไม่ใช่ลบสำเนาทิ้ง แต่คือ **บังคับให้
สำเนาตรงกันแบบ byte-for-byte สองทิศ** — หลักเดียวกับ `docs/asvs-5.0.0.json`
และ outline ของ ISO ที่ตรึงไว้แล้วมีเทสต์อ่านคู่

ถ้าไม่มีไฟล์นี้ การแก้ถ้อยคำข้างใดข้างหนึ่งจะเงียบสนิท แล้วกฎที่ vg เผยแพร่
ให้คนอื่นจะเลิกเป็นกฎเดียวกับที่ repo นี้ถูกบังคับด้วย — ซึ่งทำให้คำว่า
"reference implementation" ไม่มีความหมายอีกต่อไป
"""

from __future__ import annotations

import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "vendor" / "verifiable-gates" / "rules.yaml"
REGISTRY = ROOT / "gates.yaml"


def flat(text: object) -> str:
    """ยุบช่องว่างให้เหลือช่องเดียว — ทั้งสองไฟล์ตัดบรรทัดคนละที่กันโดยธรรมชาติ"""
    return re.sub(r"\s+", " ", str(text)).strip()


def catalogue() -> dict[str, dict]:
    rules = yaml.safe_load(CATALOGUE.read_text(encoding="utf-8"))["rules"]
    return {rule["id"]: rule for rule in rules}


def portable_gates() -> dict[str, dict]:
    gates = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["gates"]
    return {gate["id"]: gate for gate in gates if gate.get("portable")}


def gate_ids() -> list[str]:
    return sorted(portable_gates())


def test_there_are_portable_gates_to_compare() -> None:
    """ยามของยาม — ถ้าฝั่งนี้ว่าง เทสต์ข้างล่างทั้งหมดจะผ่านโดยไม่ได้เทียบอะไร"""
    assert portable_gates(), "ไม่มี gate portable เหลือแล้ว — เทสต์ข้างล่างจะเขียวเปล่า ๆ"


def test_the_catalogue_and_the_registry_name_the_same_rules() -> None:
    """สองทิศ: กฎที่นี่ต้องมีในคลัง และกฎในคลังต้องมีตัวบังคับที่นี่

    ทิศที่สองคือทิศที่เงียบกว่า — กฎที่ vg เผยแพร่แต่ repo นี้ไม่ได้บังคับ
    คือกฎที่ไม่มีใครพิสูจน์ว่าบังคับได้จริง ซึ่งเป็นสิ่งที่ทั้งโครงการนี้
    ตั้งใจไม่ทำ
    """
    here, there = set(portable_gates()), set(catalogue())
    assert here - there == set(), (
        f"gate portable ที่ไม่มีในคลังของ vg: {sorted(here - there)} — "
        "เพิ่มกฎใหม่ต้องเพิ่มที่ rules.yaml ของ vg ก่อน"
    )
    assert there - here == set(), (
        f"กฎที่ vg เผยแพร่แต่ไม่มีตัวบังคับที่นี่: {sorted(there - here)} — "
        "reference implementation ที่ไม่บังคับกฎของตัวเอง คือคำโฆษณา"
    )


@pytest.mark.parametrize("gate_id", gate_ids())
def test_the_wording_is_the_same_on_both_sides(gate_id: str) -> None:
    """ถ้อยคำไทยต้องตรงกันเป๊ะ — คลังเก็บต้นฉบับไว้ในฟิลด์ `*_th`"""
    gate, rule = portable_gates()[gate_id], catalogue()[gate_id]
    assert flat(gate["title"]) == flat(rule["title_th"]), (
        f"{gate_id}: หัวข้อกฎไม่ตรงกับ title_th ในคลังของ vg"
    )
    assert flat(gate.get("born_from", "")) == flat(rule["born_from_th"]), (
        f"{gate_id}: บทเรียนไม่ตรงกับ born_from_th ในคลังของ vg"
    )


@pytest.mark.parametrize("gate_id", gate_ids())
def test_the_classification_is_the_same_on_both_sides(gate_id: str) -> None:
    gate, rule = portable_gates()[gate_id], catalogue()[gate_id]
    assert gate["layer"] == rule["layer"], f"{gate_id}: ชั้นไม่ตรงกัน"
    assert gate["pillar"] == rule["pillar"], f"{gate_id}: pillar ไม่ตรงกัน"


@pytest.mark.parametrize("gate_id", gate_ids())
def test_the_catalogue_cites_the_enforcement_that_is_really_here(gate_id: str) -> None:
    """คลังอ้างว่า reference บังคับกฎนี้ที่ไหน — ต้องเป็นที่ที่มีอยู่จริงตอนนี้

    นี่คือทิศที่ล้าสมัยง่ายที่สุด เพราะการจัดระเบียบเทสต์ใหม่ที่นี่ไม่มีอะไร
    เตือนให้ไปแก้ไฟล์ในอีก repo หนึ่ง
    """
    gate, rule = portable_gates()[gate_id], catalogue()[gate_id]
    reference = rule["reference"]
    assert gate["kind"] == reference["kind"], f"{gate_id}: ชนิดของตัวบังคับไม่ตรงกัน"
    assert gate["enforced_by"]["job"] == reference["job"], f"{gate_id}: job ไม่ตรงกัน"
    if gate["kind"] == "test":
        assert gate["enforced_by"]["tests"] == reference["tests"], (
            f"{gate_id}: คลังอ้างไฟล์เทสต์คนละชุดกับที่บังคับอยู่จริง"
        )
    if gate["kind"] == "step":
        assert gate["enforced_by"]["step"] == reference["step"], (
            f"{gate_id}: คลังอ้างชื่อ step ที่ไม่ตรงกับ workflow จริง"
        )
