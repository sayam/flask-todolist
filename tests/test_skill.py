"""`SKILL.md` ต้องเป็นเงาของ portable gate — และห้ามเอ่ยชื่อไลบรารีของ Flask

สองอันตรายของเอกสาร skill ที่ export ไปใช้ที่อื่น:

1. **drift** — เขียนมือแล้วมีคนแก้ gates.yaml ฝั่งเดียว กฎที่ส่งออกไปจะเป็น
   รุ่นเก่าโดยไม่มีอะไรฟ้อง → generate ทั้งใบ แล้วที่นี่เทียบไบต์ต่อไบต์
2. **framework รั่วเข้าไปในชั้นที่ประกาศว่าสากล** — กฎที่เอ่ยชื่อไลบรารีของ
   Flask คือกฎที่ import ไป framework อื่นแล้วอ่านไม่รู้เรื่อง · เทคนิคเดียวกับ
   ที่ `tests/test_plugins.py` ห้าม core เอ่ยชื่อ plugin: grep แล้วแดง
   — ban list ตรวจที่*ผล render สด* ไม่ใช่แค่ไฟล์ จึงจับได้ตั้งแต่ตอนคำต้องห้าม
   ถูกพิมพ์ลง gates.yaml ไม่ใช่ตอน regenerate
"""

import pathlib
import re

import pytest

from scripts.build_skill import OUT, portable_gates, render

ROOT = pathlib.Path(__file__).resolve().parent.parent

# ไลบรารีของ ecosystem Flask/Python-web ที่กฎสากลห้ามพึ่งชื่อ — ชั้นที่ผูกได้
# คือ overlay เท่านั้น · คำกลาง ๆ อย่าง redis/mysql เป็นชื่อ *ระบบภายนอก*
# ไม่ใช่ไลบรารีของ framework จึงไม่อยู่ในรายการนี้
BANNED = (
    "flask",
    "werkzeug",
    "jinja",
    "sqlalchemy",
    "alembic",
    "talisman",
    "wtform",
    "marshmallow",
    "smorest",
    "gunicorn",
    "pipenv",
)


def test_the_skill_is_a_render_of_the_registry_not_a_second_copy():
    """แก้ gates.yaml แล้วไม่ regenerate = แดง · แก้ SKILL.md มือ = แดง"""
    assert OUT.is_file(), "ไม่มี SKILL.md — รัน scripts/build_skill.py"
    assert OUT.read_text(encoding="utf-8") == render(), (
        "SKILL.md ไม่ตรงกับผล generate จาก gates.yaml — "
        "รัน pipenv run python scripts/build_skill.py แล้ว commit มาด้วยกัน"
    )


def test_every_portable_gate_appears_and_nothing_else():
    """หัวข้อในไฟล์ == เซตของ portable gate เป๊ะ — ขาดหรือเกินคือเงาที่โกหก"""
    text = OUT.read_text(encoding="utf-8")
    in_file = set(re.findall(r"^### `([a-z0-9-]+)`$", text, re.MULTILINE))
    expected = {g["id"] for g in portable_gates()}
    assert in_file == expected, (
        f"ขาด: {sorted(expected - in_file)} · เกิน: {sorted(in_file - expected)}"
    )


def test_no_flask_library_name_leaks_into_the_universal_layer():
    """ตรวจผล render สด — จับคำต้องห้ามตั้งแต่ตอนมันถูกพิมพ์ลง gates.yaml

    ยกเว้นบรรทัด "ตัวบังคับใน reference" ซึ่งชี้ไฟล์/job ของ repo นี้โดยตั้งใจ
    (นั่นคือส่วน reference ไม่ใช่ส่วนกฎ) — กฎกับบทเรียนต้องสะอาด
    """
    leaked = []
    for line in render().splitlines():
        if line.startswith("**ตัวบังคับใน reference:**"):
            continue
        lowered = line.lower()
        leaked += [f"{word!r} ใน: {line.strip()[:80]}" for word in BANNED if word in lowered]
    assert not leaked, "\n  ".join(["ชื่อไลบรารีของ framework หลุดเข้าชั้นสากล:", *leaked])


def test_every_rule_still_carries_its_origin():
    """ทุกข้อในไฟล์ต้องมีทั้งกฎและบทเรียน — โครงที่หายไปเงียบ ๆ คือ generator พัง"""
    text = OUT.read_text(encoding="utf-8")
    rules = text.count("**กฎ:**")
    origins = text.count("**เกิดจาก:**")
    total = len(portable_gates())
    assert rules == origins == total, f"กฎ {rules} · เกิดจาก {origins} · gate {total} — ต้องเท่ากัน"


@pytest.mark.parametrize("word", ["mutation", "ratchet", "ADR", "สองทิศ"])
def test_the_central_practices_survive_in_the_preamble(word):
    """หลักปฏิบัติกลาง (ของคน อยู่ใน PREAMBLE) ต้องไม่หายตอนมีคนแก้ generator"""
    assert word in OUT.read_text(encoding="utf-8"), f"หลักปฏิบัติเรื่อง {word!r} หายจาก SKILL.md"
