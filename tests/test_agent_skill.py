"""`skill/` (แพ็กเกจ agent skill — ADR 0050) ต้องเป็นผล generate ล้วน ไม่ใช่สำเนาที่แก้เอง

หลักเดียวกับ `test_skill.py`/`test_gates.py`: ของที่ derive ได้ต้องถูกเทียบกับ
ผล generate สดทุกครั้งที่รันเทสต์ — รวมทั้ง**เซตไฟล์** (ไฟล์แปลกปลอมที่วางเพิ่ม
ใน `skill/` คือทะเบียนที่สามที่ไม่มีใครคุม ต้องแดง ไม่ใช่ถูกเมิน)
"""

import re

import pytest
import yaml  # type: ignore[import-untyped] - library lacks type stubs

from scripts.build_agent_skill import MANIFEST, SKILL_DIR, targets
from scripts.build_skill import render


@pytest.fixture(scope="module")
def fresh():
    return targets()


def test_every_file_is_a_fresh_render(fresh):
    stale = [
        rel
        for rel, content in fresh.items()
        if not (SKILL_DIR / rel).exists()
        or (SKILL_DIR / rel).read_text(encoding="utf-8") != content
    ]
    assert not stale, (
        f"ไฟล์ใน skill/ ไม่ตรงกับผล generate สด: {stale} — "
        "รัน PYTHONPATH=. pipenv run python scripts/build_agent_skill.py"
    )


def test_the_package_has_no_stray_files(fresh):
    on_disk = {str(p.relative_to(SKILL_DIR)) for p in SKILL_DIR.rglob("*") if p.is_file()}
    strays = sorted(on_disk - fresh.keys())
    assert not strays, f"ไฟล์แปลกปลอมใน skill/ ที่ generator ไม่รู้จัก: {strays}"


def test_frontmatter_declares_name_and_description(fresh):
    text = fresh["SKILL.md"]
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "skill/SKILL.md ไม่มี frontmatter คั่นด้วย ---"
    meta = yaml.safe_load(match.group(1))
    assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", meta.get("name", "")), (
        f"name ต้องเป็น kebab-case: {meta.get('name')!r}"
    )
    assert len(meta.get("description", "")) > 20, "description ต้องบอกว่า skill นี้คืออะไร"


def test_the_rules_are_the_same_render_not_a_fork(fresh):
    assert fresh["SKILL.md"].endswith(render("baseline")), (
        "ส่วนกฎใน skill/SKILL.md ต้องเป็น render ชั้น baseline ตัวเดียวกับ SKILL.md ที่ราก"
    )
    assert fresh["reference/SKILL-TODOLIST.md"] == render("business"), (
        "reference ต้องเป็น render ชั้น business ตัวเดิมไบต์ต่อไบต์"
    )


def test_every_manifest_checker_ships(fresh):
    import json

    ship = json.loads(MANIFEST.read_text(encoding="utf-8"))["ship"]
    expected = {
        f"scripts/{name.split('/')[-1]}" for name in ship if name.startswith("checks/scan_")
    }
    shipped = {rel for rel in fresh if rel.startswith("scripts/")}
    assert shipped == expected, (
        f"checker ไม่ตรง manifest — ขาด: {sorted(expected - shipped)} · "
        f"เกิน: {sorted(shipped - expected)}"
    )
