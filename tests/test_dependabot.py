"""PR ที่ Dependabot เปิดให้ ต้องผ่านด่านของโปรเจกต์นี้ตั้งแต่ใบแรก

หัว commit ของ Dependabot ถูกประกอบจาก `commit-message.prefix` ใน
`.github/dependabot.yml` **ถ้า prefix นั้นไม่ใช่ชนิดที่ `scripts/lint_commits.py`
รับ PR ทุกใบจะแดงที่ job `commit-lint` ทันที** แล้วสิ่งที่เกิดขึ้นจริงคือคนดูแล
เรียนรู้ที่จะเมิน PR ของ Dependabot ทั้งหมด — ซึ่งแย่กว่าไม่เปิดมันเลย เพราะ
ตอนนั้นจะมีทั้ง PR ค้างและความรู้สึกว่ามีคนเฝ้าอยู่

ที่นี่จึงผูกไฟล์ config เข้ากับตัวตรวจ commit จริง ๆ ไม่ใช่เทียบกับสตริงที่
เขียนซ้ำไว้ในเทสต์ — ขยับข้างไหนแล้วอีกข้างต้องรู้ตัว
"""

import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG = ROOT / ".github" / "dependabot.yml"
LINTER = ROOT / "scripts" / "lint_commits.py"


@pytest.fixture(scope="module")
def config():
    assert CONFIG.is_file(), "ไม่มี .github/dependabot.yml"
    loaded = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert loaded.get("version") == 2, "dependabot.yml ต้องเป็น version 2"
    assert loaded.get("updates"), "ไม่มีรายการ updates สักอัน — ไฟล์นี้ไม่ทำอะไรเลย"
    return loaded


@pytest.fixture(scope="module")
def accepted_types():
    """ชนิดของ commit ที่ `scripts/lint_commits.py` ยอมรับ — อ่านจากตัวจริง"""
    match = re.search(r'^TYPES\s*=\s*"([^"]+)"', LINTER.read_text(encoding="utf-8"), re.MULTILINE)
    assert match, "อ่าน TYPES จาก scripts/lint_commits.py ไม่ได้ — ชื่อตัวแปรเปลี่ยนไปแล้ว"
    return set(match.group(1).split("|"))


def test_every_prefix_is_a_type_the_commit_linter_accepts(config, accepted_types):
    for entry in config["updates"]:
        prefix = (entry.get("commit-message") or {}).get("prefix")
        assert prefix, (
            f"`{entry['package-ecosystem']}` ไม่ได้ตั้ง commit-message.prefix — "
            "หัว commit ของ Dependabot จะไม่ใช่ Conventional Commits แล้ว commit-lint จะแดง"
        )
        assert prefix in accepted_types, (
            f"prefix {prefix!r} ไม่อยู่ในชนิดที่ตัวตรวจรับ ({sorted(accepted_types)})"
        )


def test_pip_version_updates_stay_off(config):
    """เปิด pip เมื่อไหร่จะมี PR แทบทุกวัน — **security update ของ pip เปิดอยู่แล้ว**

    ตั้งในหน้า repo ไม่ใช่ในไฟล์นี้ · ถ้าวันหนึ่งตัดสินใจว่าอยากได้ version update
    ของ pip จริง ๆ ให้แก้เทสต์นี้พร้อมเหตุผล ไม่ใช่เติม entry เงียบ ๆ แล้วมางง
    ทีหลังว่าทำไม PR เยอะขึ้น
    """
    ecosystems = {entry["package-ecosystem"] for entry in config["updates"]}
    assert "pip" not in ecosystems, "เปิด version update ของ pip แล้ว — ตั้งใจหรือเปล่า? (ดู docstring)"


def test_the_actions_updates_arrive_as_one_pull_request(config):
    """PR ห้าใบที่แก้เรื่องเดียวกัน คือห้าใบที่ไม่มีใครอ่านสักใบ"""
    actions = [e for e in config["updates"] if e["package-ecosystem"] == "github-actions"]
    assert actions, "ไม่ได้เฝ้า github-actions เลย ทั้งที่มันรันด้วยสิทธิ์ของ workflow เรา"

    for entry in actions:
        assert entry.get("groups"), f"{entry['package-ecosystem']}: ไม่ได้รวมเป็นกลุ่ม"
        assert entry.get("schedule", {}).get("interval"), "ไม่ได้ตั้งรอบ"


def test_the_config_covers_the_directory_the_workflows_live_in(config):
    """`directory` ผิดแปลว่า Dependabot ไม่เจอ workflow แล้วเงียบไปเฉย ๆ"""
    for entry in config["updates"]:
        if entry["package-ecosystem"] != "github-actions":
            continue
        directory = entry.get("directory") or entry.get("directories")
        assert directory in ("/", ["/"]), (
            f"github-actions ต้องชี้ที่ราก repo (ได้ {directory!r}) — "
            "Dependabot หา workflow จาก `.github/workflows/` ใต้ path นั้น"
        )
