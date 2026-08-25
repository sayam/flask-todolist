"""`skill/` (แพ็กเกจ agent skill — ADR 0050) ต้องเป็นผล generate ล้วน ไม่ใช่สำเนาที่แก้เอง

หลักเดียวกับ `test_skill.py`/`test_gates.py`: ของที่ derive ได้ต้องถูกเทียบกับ
ผล generate สดทุกครั้งที่รันเทสต์ — รวมทั้ง**เซตไฟล์** (ไฟล์แปลกปลอมที่วางเพิ่ม
ใน `skill/` คือทะเบียนที่สามที่ไม่มีใครคุม ต้องแดง ไม่ใช่ถูกเมิน)
"""

import re

import pytest
import yaml  # type: ignore[import-untyped]

from scripts import build_agent_skill
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


# ---------------- ตัวสั่งงาน: เขียนลงจริงและเก็บของค้าง (ขั้น 2e)
#
# `targets()` ถูกเทสต์ไว้แล้ว แต่ `main()` ไม่เคยถูกเรียก — และหน้าที่ที่มีแต่
# `main()` ทำคือ **ลบไฟล์ที่ไม่อยู่ในเป้าทิ้ง** ซึ่งเป็นสิ่งเดียวที่กันไม่ให้
# แพ็กเกจสะสมของค้างจากรุ่นก่อน · ถ้ามันพัง `targets()` ยังเขียวสนิท


def test_main_writes_the_package_and_sweeps_what_is_no_longer_a_target(monkeypatch, tmp_path):
    monkeypatch.setattr(build_agent_skill, "SKILL_DIR", tmp_path)
    stale = tmp_path / "scripts" / "scan_gone.py"
    stale.parent.mkdir(parents=True)
    stale.write_text("ของค้างจากรุ่นก่อน\n", encoding="utf-8")

    assert build_agent_skill.main() == 0

    fresh = build_agent_skill.targets()
    for rel in fresh:
        assert (tmp_path / rel).is_file(), f"ไม่ได้เขียน {rel}"
    assert not stale.exists(), "ของค้างไม่ถูกเก็บกวาด — แพ็กเกจจะสะสมไฟล์ผีไปเรื่อย ๆ"


def test_main_reports_nothing_changed_on_a_second_run(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(build_agent_skill, "SKILL_DIR", tmp_path)
    build_agent_skill.main()
    capsys.readouterr()

    assert build_agent_skill.main() == 0
    assert "ไม่มีอะไรเปลี่ยน" in capsys.readouterr().out
