"""การซ้อม backup → เสียหาย → restore ต้องรันจริงทุก push — ไม่ใช่พิธีในเอกสาร

ปิดข้อ A.5.30/A.8.13 ของ ISO 27001: สร้างฐาน scratch ที่มี**ข้อมูลจริง**
(schema ของแอป + แถวจริงผ่าน ORM) แล้วเดิน `scripts/backup_drill.py` เต็มวง
— restore ที่ซ้อมทุก push คือ restore ที่เชื่อได้ · และ runbook ต้องไม่เน่า:
ทุกไฟล์ที่มันอ้างต้องมีจริง และคำเตือนเรื่องคีย์ encrypt ต้องยังอยู่
(คีย์หาย = TOTP อ่านไม่ได้ถาวร — คำเตือนที่หายไปเงียบ ๆ อันตรายกว่าไม่มีไฟล์)
"""

import pathlib
import re
import sqlite3

import pytest

from app import create_app, db
from app.models import Category, Todo, User
from scripts.backup_drill import drill
from tests.conftest import TestConfig

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNBOOK = ROOT / "docs" / "RUNBOOK-BACKUP.md"


@pytest.fixture
def scratch_db(tmp_path):
    """ฐาน sqlite เป็นไฟล์จริง (ไม่ใช่ :memory:) พร้อมข้อมูลผ่าน ORM"""

    class FileDbConfig(TestConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'scratch.db'}"

    app = create_app(FileDbConfig)
    with app.app_context():
        db.create_all()
        user = User(username="drill")
        user.set_password("Backup-Drill-2026!")
        db.session.add(user)
        db.session.flush()
        category = Category(name="drill-cat", user_id=user.id)
        db.session.add(category)
        db.session.flush()
        db.session.add(Todo(title="drill-task", user_id=user.id, category_id=category.id))
        db.session.commit()
        db.session.remove()
    return tmp_path / "scratch.db"


def test_the_full_drill_passes_on_a_real_schema(scratch_db, tmp_path):
    problems = drill(scratch_db, tmp_path / "work")
    assert not problems, "การซ้อมล้มเหลว: " + " · ".join(problems)


def test_the_drill_detects_data_loss_in_restore(scratch_db, tmp_path, monkeypatch):
    """สองทิศ: restore ที่ข้อมูลหายไปหนึ่งแถวต้องถูกรายงาน ไม่ใช่ผ่านเงียบ"""
    import shutil

    import scripts.backup_drill as bd

    real_copy = shutil.copy

    def lossy_copy(src, dst):
        real_copy(src, dst)
        with sqlite3.connect(dst) as conn:
            conn.execute("DELETE FROM tdl_todo")

    monkeypatch.setattr(bd.shutil, "copy", lossy_copy)
    problems = bd.drill(scratch_db, tmp_path / "work")
    assert problems, "restore ที่แถวงานหายทั้งตารางต้องถูกรายงานว่าไม่ตรงต้นฉบับ"


def test_a_corrupt_or_empty_database_is_reported_not_crashed(tmp_path):
    junk = tmp_path / "junk.db"
    junk.write_bytes(b"this is not a sqlite file at all" * 64)
    assert drill(junk, tmp_path / "w1"), "ไฟล์ที่ไม่ใช่ sqlite ต้องได้รายงานปัญหา ไม่ใช่ traceback"
    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()
    assert drill(empty, tmp_path / "w2"), "ฐานที่ไม่มีตารางเลยต้องถูกรายงานว่าซ้อมไม่ได้ความหมาย"


def test_the_runbook_references_resolve():
    text = RUNBOOK.read_text(encoding="utf-8")
    dead = []
    for ref in re.findall(r"`([^`\n]+)`", text):
        pathlike = "/" in ref or ref.endswith((".md", ".py", ".db", ".example"))
        if ref.startswith(
            (
                "sqlite3 ",
                "mysql",
                "pipenv ",
                "cp ",
                ".backup",
                "flask ",
                "--",
                "instance/",
                "backup/",
            )
        ):  # สองตัวท้าย: path ตอน deploy จริง
            continue
        if re.fullmatch(r"(?:A\.)?\d+\.\d+", ref) or re.fullmatch(r"ADR \d{4}", ref):
            continue
        if pathlike and not (ROOT / ref).exists():
            dead.append(ref)
    assert not dead, f"runbook อ้างไฟล์ที่ไม่มีจริง: {dead}"


def test_the_key_loss_warning_survives():
    text = RUNBOOK.read_text(encoding="utf-8")
    warning_gone = "คำเตือนเรื่องคีย์ encrypt หายไปจาก runbook — คีย์หาย = TOTP กู้ไม่ได้"
    assert "DATA_ENCRYPTION_KEY" in text, warning_gone
    assert "อ่านไม่ได้ถาวร" in text, warning_gone
