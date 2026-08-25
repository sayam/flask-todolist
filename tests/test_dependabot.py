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
    """ชนิดของ commit ที่ตัวตัดสินยอมรับ — **import มาจากตัวจริง ไม่ใช่ grep ข้อความ**

    เดิมอ่านด้วย regex บนไฟล์ ซึ่งใช้ได้ตราบที่ค่าเป็นตัวอักษรอยู่ในไฟล์นั้น ·
    ตั้งแต่ ADR 0077 ขั้น 3a ตัวจริงอยู่ที่ `verifiable-gates` และที่นี่เหลือ adapter
    · การ import จึงเดินเส้นทางเดียวกับที่ hook กับ CI ใช้จริง แทนที่จะเดาว่า
    ค่านั้นหน้าตายังเหมือนเดิม
    """
    from scripts.lint_commits import TYPES

    assert LINTER.is_file(), "ไม่มี scripts/lint_commits.py — hook กับ CI เรียกพาธนี้"
    return set(TYPES.split("|"))


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


def test_pip_version_updates_never_reach_the_app_lock_file(config):
    """version update ของ `Pipfile.lock` จะมี PR แทบทุกวัน — **ไม่เปิด**

    ร้อยกว่า package ที่ประกาศเป็น `"*"` แปลว่าตัวใดตัวหนึ่งออกรุ่นใหม่เมื่อไหร่
    ก็มี PR · **security update ของ pip เปิดอยู่แล้ว** (ตั้งในหน้า repo ไม่ใช่
    ในไฟล์นี้) ซึ่งตอบคำถามที่เร่งด่วนจริงคือ "มี CVE ไหม"

    **แต่ ecosystem `pip` เองไม่ได้ถูกห้าม** — `pins/` เป็นของที่ *ถูกตรึงไว้*
    ที่รุ่นหนึ่งอย่างเจาะจง ซึ่งกลับกันเลย: ไม่มีใครขยับให้ก็คือแช่ช่องโหว่ไว้
    (ดู `tests/test_ci_pinning.py::test_dependabot_keeps_every_pin_fresh`)
    เส้นแบ่งจึงเป็น **path ไม่ใช่ชื่อ ecosystem**
    """
    for entry in config["updates"]:
        if entry["package-ecosystem"] != "pip":
            continue
        directories = entry.get("directories") or [entry["directory"]]
        assert all(d.startswith("/pins/") for d in directories), (
            f"pip ชี้ไปที่ {directories} — ที่รากคือ Pipfile ของแอปเอง "
            "ซึ่งจะเปิด PR แทบทุกวัน · ที่ตั้งใจเฝ้าคือของที่ตรึงไว้ใน pins/ เท่านั้น"
        )


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
