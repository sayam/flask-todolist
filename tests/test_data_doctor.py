"""ตัวตรวจสุขภาพข้อมูล ต้องเห็นของที่ปลูกไว้ และต้องเงียบกับฐานที่สะอาด

**audit รอบ 19** ปลูกความผิดที่ชั้นข้อมูลลงในฐานที่ migrate สด แล้ววัดว่าใครเห็น —
คำตอบคือแทบไม่มีใคร: แถวกำพร้าผ่านทุกคำสั่ง ทุก healthcheck และทุก job ·
`foreign_key_check` ไม่ปรากฏที่ไหนใน repo แม้แต่ครั้งเดียว · CLI 26 คำสั่ง
มีตัวที่ *ถาม* ข้อมูลว่ายังดีอยู่ไหมอยู่ตัวเดียว และมันตรวจแค่สาย audit

ไฟล์นี้บังคับสองทิศต่อข้อ: **ปลูกแล้วต้องเห็น** และ **ฐานสะอาดต้องเงียบ** —
ตัวตรวจที่ดังกับของปกติ คือตัวตรวจที่จะถูกถอดภายในสัปดาห์เดียว
"""

import hashlib
import pathlib

from sqlalchemy import text

from app import db
from app.models import Category, Todo, User
from app.services import data_doctor
from tests.conftest import PASSWORD


def _without_foreign_keys(statement: str, params: dict) -> None:
    """รันคำสั่งเดียวโดยปิดการบังคับ FK ชั่วคราว — **ทางเดียวที่แถวกำพร้าเกิดได้จริง**

    FK ถูกบังคับตอนเขียนอยู่แล้วทุกยี่ห้อ (นั่นคือเหตุผลที่ต้องปิดก่อนถึงจะปลูกได้) ·
    ของจริงมาจากทางที่ไม่ผ่านการบังคับ: การกู้คืนที่ไม่ครบ · การย้ายฐาน · คนแก้ด้วย
    SQL ตรง ๆ · คำสั่งปิดต่างกันตามยี่ห้อ จึงเลือกตาม dialect ไม่ใช่ตรึงเป็น PRAGMA
    ของ SQLite (job `dialects` รันไฟล์นี้บน MySQL/MariaDB ด้วย)
    """
    off, on = {
        "sqlite": ("PRAGMA foreign_keys=OFF", "PRAGMA foreign_keys=ON"),
    }.get(db.engine.dialect.name, ("SET FOREIGN_KEY_CHECKS=0", "SET FOREIGN_KEY_CHECKS=1"))
    db.session.execute(text(off))
    db.session.execute(text(statement), params)
    db.session.commit()
    db.session.execute(text(on))
    db.session.commit()


def _fingerprint() -> str:
    """ลายนิ้วมือของทุกตารางที่มีข้อมูล — ใช้พิสูจน์ว่าไม่มีอะไรถูกเขียน"""
    digest = hashlib.sha256()
    for table in sorted(db.metadata.sorted_tables, key=lambda t: t.name):
        rows = db.session.execute(text(f"SELECT * FROM {table.name}")).fetchall()  # noqa: S608
        digest.update(repr(sorted(map(repr, rows))).encode("utf-8"))
    return digest.hexdigest()


def test_a_clean_database_reports_nothing(app, user_id):
    """ทิศ "เงียบเมื่อควรเงียบ" — และต้องบอกด้วยว่าตรวจไปกี่ข้อ"""
    with app.app_context():
        report = data_doctor.examine()

    assert report.healthy, [finding.detail for finding in report.findings]
    assert report.checks > 5, "ตรวจน้อยผิดปกติ — ตัวนับอาจไม่ได้เดินจริง"


def test_an_orphan_row_is_found(app, user_id):
    """แถวที่ชี้ไปหาแถวที่ไม่มีอยู่ — คลาสที่ไม่มีใครในระบบเคยมองหาเลย"""
    with app.app_context():
        category = Category(name="งาน", user_id=user_id)
        db.session.add(category)
        db.session.commit()
        todo = Todo(title="ซื้อนม", user_id=user_id, category_id=category.id)
        db.session.add(todo)
        db.session.commit()
        _without_foreign_keys(
            "UPDATE tdl_todo SET category_id = 424242 WHERE id = :id", {"id": todo.id}
        )

        report = data_doctor.examine()

    kinds = {finding.kind for finding in report.findings}
    assert "orphan-row" in kinds, [f.detail for f in report.findings]


def test_a_truncated_audit_chain_is_found(app, user_id):
    """ต่อจากข้อ 1 ของรอบเดียวกัน — ตัวตรวจสุขภาพต้องเห็นสมอที่ไม่ตรงด้วย"""
    with app.app_context():
        db.session.execute(text("DELETE FROM tdl_audit WHERE id = (SELECT MAX(id) FROM tdl_audit)"))
        db.session.commit()

        report = data_doctor.examine()

    assert "audit-anchor" in {finding.kind for finding in report.findings}


def test_colliding_usernames_are_found(app, user_id):
    """ของที่ชนกันอยู่แล้วก่อนกฎของข้อ 2 เกิด ต้องมีคนบอก"""
    with app.app_context():
        me = db.session.get(User, user_id)
        twin = User(username=me.username.upper())
        twin.set_password(PASSWORD)
        db.session.add(twin)
        db.session.commit()

        report = data_doctor.examine()

    assert "username-collision" in {finding.kind for finding in report.findings}


def test_data_past_its_retention_is_found(app, user_id):
    """ระยะเก็บรักษาเป็นจริงก็ต่อเมื่อมีอะไรรัน purge — ไม่ใช่เพราะเอกสารเขียนไว้"""
    with app.app_context():
        todo = Todo(title="ซื้อนม", user_id=user_id)
        db.session.add(todo)
        db.session.commit()
        db.session.execute(
            text("UPDATE tdl_todo SET deleted_at = :old WHERE id = :id"),
            {"old": "2020-01-01 00:00:00", "id": todo.id},
        )
        db.session.commit()

        report = data_doctor.examine()

    assert "retention-overdue" in {finding.kind for finding in report.findings}


def test_examining_never_writes_anything(app, user_id):
    """**อ่านอย่างเดียว** — เครื่องมือที่ซ่อมเองคือเครื่องมือที่ไม่มีใครกล้ารันบนฐานจริง

    วัดด้วยลายนิ้วมือของทุกตาราง ไม่ใช่ด้วยการอ่านโค้ดแล้วเชื่อ
    """
    with app.app_context():
        db.session.add(Todo(title="ซื้อนม", user_id=user_id))
        db.session.commit()
        before = _fingerprint()

        data_doctor.examine()
        db.session.remove()

        assert _fingerprint() == before


def test_the_cli_reports_a_healthy_database_and_exits_zero(app, user_id):
    result = app.test_cli_runner().invoke(args=["data-doctor"])

    assert result.exit_code == 0, result.output
    assert "healthy" in result.output


def test_the_cli_fails_when_something_is_wrong(app, user_id):
    """แดงต้องแดงจริง — ตัวตรวจที่ exit 0 เสมอคือตัวที่ไม่มีใครสังเกตว่าเจออะไร"""
    with app.app_context():
        db.session.execute(text("DELETE FROM tdl_audit"))
        db.session.commit()

    result = app.test_cli_runner().invoke(args=["data-doctor"])

    assert result.exit_code != 0, result.output
    assert "audit-anchor" in result.output


def test_the_command_is_registered_where_operators_will_look():
    """คำสั่งที่ไม่ได้ลงทะเบียน คือคำสั่งที่มีอยู่เฉพาะในเอกสาร"""
    source = (pathlib.Path(__file__).resolve().parent.parent / "app" / "cli.py").read_text(
        encoding="utf-8"
    )

    assert "app.cli.add_command(data_doctor)" in source
