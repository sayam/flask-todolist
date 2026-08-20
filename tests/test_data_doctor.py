"""ตัวตรวจสุขภาพข้อมูล ต้องเห็นของที่ปลูกไว้ และต้องเงียบกับฐานที่สะอาด

**audit รอบ 19** ปลูกความผิดที่ชั้นข้อมูลลงในฐานที่ migrate สด แล้ววัดว่าใครเห็น —
คำตอบคือแทบไม่มีใคร: แถวกำพร้าผ่านทุกคำสั่ง ทุก healthcheck และทุก job ·
`foreign_key_check` ไม่ปรากฏที่ไหนใน repo แม้แต่ครั้งเดียว · CLI 26 คำสั่ง
มีตัวที่ *ถาม* ข้อมูลว่ายังดีอยู่ไหมอยู่ตัวเดียว และมันตรวจแค่สาย audit

ไฟล์นี้บังคับสองทิศต่อข้อ: **ปลูกแล้วต้องเห็น** และ **ฐานสะอาดต้องเงียบ** —
ตัวตรวจที่ดังกับของปกติ คือตัวตรวจที่จะถูกถอดภายในสัปดาห์เดียว
"""

import hashlib
import os
import pathlib
from datetime import datetime

import pytest
from sqlalchemy import func, select, text

from app import db
from app.audit import AuditEntry
from app.models import Category, Todo, User
from app.services import data_doctor, personal_data, tokens
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
        # `select(table)` ไม่ใช่ `text(f"SELECT * FROM {name}")` — semgrep จับตัวหลัง
        # ได้ถูกแล้ว (`avoid-sqlalchemy-text`) และตัวแรกก็อ่านง่ายกว่าด้วย
        rows = db.session.execute(select(table)).fetchall()
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
        # **อ่าน id มาก่อนแล้วค่อยลบ** — MySQL ปฏิเสธ subquery ที่อ่านตารางเดียวกับ
        # ที่กำลังลบ (error 1093) · เจอตอน job `dialects` แดงใน PR ของข้อนี้เอง
        newest = db.session.scalar(select(func.max(AuditEntry.id)))
        db.session.execute(text("DELETE FROM tdl_audit WHERE id = :id"), {"id": newest})
        db.session.commit()

        report = data_doctor.examine()

    assert "audit-anchor" in {finding.kind for finding in report.findings}


@pytest.mark.skipif(
    os.environ.get("TEST_DATABASE_URL", "sqlite").startswith(("mysql", "mariadb")),
    reason=(
        "MySQL/MariaDB เทียบ unique index ด้วย collation ที่ไม่สนตัวพิมพ์ — "
        "สภาพ 'ชนกันอยู่แล้ว' สร้างไม่ได้บนยี่ห้อนั้นตามนิยาม (ฐานกันให้ตั้งแต่แรก)"
    ),
)
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


def test_a_plugin_table_that_is_not_installed_is_skipped(app, user_id):
    """models ของ plugin อยู่ใน metadata ตั้งแต่ import แต่ตารางเกิดตอน plugin-install

    ถามหาข้อมูลในตารางที่ยังไม่มี = ล้มทั้งคำสั่ง ทั้งที่คำตอบที่ถูกคือ
    "ไม่มีข้อมูลให้ตรวจ" (หลักเดียวกับที่ core เช็ค `is_installed()` ก่อนใช้)
    """
    with app.app_context():
        plugin_tables = [t for t in db.metadata.sorted_tables if t.name.startswith("tdl_auth_")]
        assert plugin_tables, "ไม่มีตารางของ plugin ใน metadata — เทสต์นี้วัดผิดที่แล้ว"
        plugin_tables[0].drop(db.session.get_bind())

        report = data_doctor.examine()

    assert report.healthy, [finding.detail for finding in report.findings]


def test_a_tampered_audit_row_is_reported_as_a_chain_break(client, app, user_id):
    """สองอาการของสาย audit ต้องแยกกันในรายงานด้วย ไม่ใช่รวมเป็นข้อเดียว"""
    client.post("/add", data={"title": "ซื้อนม"})
    with app.app_context():
        db.session.execute(text("UPDATE tdl_audit SET actor_id = 999 WHERE id = 1"))
        db.session.commit()

        report = data_doctor.examine()

    assert "audit-chain" in {finding.kind for finding in report.findings}


# ------------- credential ที่ยังใช้ได้บนแถวที่ปิดไปแล้ว (ใบ #171)


def _close(user):
    """ปิดบัญชีตามเส้นทางเดียวที่ถูก แล้วคืน id — ทางอื่นคือทางที่ ADR 0034 ห้ามไว้"""
    personal_data.close_account(user)
    return user.id


def test_a_closed_account_that_kept_its_password_is_found(app, user_id):
    """ปิดบัญชีแล้วเขียน hash ที่ใช้ได้กลับเข้าไป — ต้องเห็น"""
    with app.app_context():
        victim = User(username="ปิดแล้วแต่ยังเข้าได้")
        victim.set_password(PASSWORD)
        db.session.add(victim)
        db.session.commit()
        closed_id = _close(victim)

        # **ต้องเขียนด้วย SQL ตรง ๆ** — เส้นทางของแอปไม่มีทางสร้างสถานะนี้ได้
        # ซึ่งเป็นเหตุผลที่ตัวตรวจมีอยู่: ของแบบนี้มาจาก backup เก่า/มือคน
        db.session.execute(
            text("UPDATE tdl_user SET password_hash = :h WHERE id = :i"),
            {"h": "scrypt:32768:8:1$fake$deadbeef", "i": closed_id},
        )
        db.session.commit()

        report = data_doctor.examine()

    kinds = {finding.kind for finding in report.findings}
    assert "live-credential-on-closed-row" in kinds, [f.detail for f in report.findings]


def test_a_revoked_token_that_kept_its_hash_is_found(app, user_id):
    """เพิกถอนแล้วเขียน hash กลับเข้าไป — ต้องเห็น"""
    with app.app_context():
        owner = db.session.get(User, user_id)
        tokens.issue(owner, "ของเครื่องพิมพ์")
        issued = tokens.list_tokens(owner)[0]
        tokens.revoke(owner, issued.id)

        db.session.execute(
            text("UPDATE tdl_api_token SET token_hash = :h WHERE id = :i"),
            {"h": "0" * 64, "i": issued.id},
        )
        db.session.commit()

        report = data_doctor.examine()

    assert "live-credential-on-closed-row" in {f.kind for f in report.findings}


def test_closing_an_account_the_normal_way_reports_nothing(app, user_id):
    """เส้นทางปกติต้องเงียบ — ตัวตรวจที่ดังกับของปกติจะถูกถอดภายในสัปดาห์เดียว"""
    with app.app_context():
        leaving = User(username="ลาออกตามระเบียบ")
        leaving.set_password(PASSWORD)
        db.session.add(leaving)
        db.session.commit()
        _close(leaving)

        report = data_doctor.examine()

    assert report.healthy, [finding.detail for finding in report.findings]


def test_a_token_that_only_expired_is_not_reported(app, user_id):
    """หมดอายุ ≠ ถูกเพิกถอน — `revoke()` เท่านั้นที่ล้าง hash

    ใบที่หมดอายุแต่ยังไม่ถูกเพิกถอนยังถือ hash ไว้อย่างถูกต้อง รอ `purge-expired`
    มาเก็บ · ถ้าตัวตรวจนับมันเป็นความผิด ฐานที่สุขภาพดีทุกฐานที่เคยออก token
    จะรายงานว่าป่วย
    """
    with app.app_context():
        owner = db.session.get(User, user_id)
        tokens.issue(owner, "ใบที่ปล่อยให้หมดอายุ")
        issued = tokens.list_tokens(owner)[0]
        db.session.execute(
            text("UPDATE tdl_api_token SET expires_at = :t WHERE id = :i"),
            {"t": datetime(2020, 1, 1), "i": issued.id},
        )
        db.session.commit()

        report = data_doctor.examine()

    assert report.healthy, [finding.detail for finding in report.findings]


def test_the_check_reads_rows_the_soft_delete_filter_hides(app, user_id):
    """ถามตรง ๆ โดยไม่ขอ `INCLUDE_DELETED` จะได้ศูนย์แถวเสมอ แล้วด่านเขียวเปล่า

    เทสต์นี้วัด *กลไก* ไม่ใช่ผลลัพธ์: แถวที่ปลูกไว้ต้องมองไม่เห็นด้วย query
    ธรรมดา — ถ้าวันหนึ่งมันเห็นได้เอง แปลว่าตัวกรองหลุด และเทสต์ข้างบนก็จะ
    ผ่านด้วยเหตุผลที่ไม่ใช่ของมัน
    """
    with app.app_context():
        victim = User(username="ซ่อนอยู่หลังตัวกรอง")
        victim.set_password(PASSWORD)
        db.session.add(victim)
        db.session.commit()
        closed_id = _close(victim)
        db.session.execute(
            text("UPDATE tdl_user SET password_hash = :h WHERE id = :i"),
            {"h": "scrypt:32768:8:1$fake$deadbeef", "i": closed_id},
        )
        db.session.commit()

        visible = db.session.scalar(
            select(func.count()).select_from(User).where(User.id == closed_id)
        )
        assert visible == 0, "ตัวกรอง soft delete ไม่ได้ซ่อนแถวนี้ — เทสต์ตัวอื่นวัดผิดที่แล้ว"

        report = data_doctor.examine()

    assert "live-credential-on-closed-row" in {f.kind for f in report.findings}
