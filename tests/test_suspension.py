"""ระงับการใช้บัญชี (PDPA ม.34) — ระงับ ≠ ลบ · ย้อนกลับได้ · ครอบทุกช่องทางเข้า

สัญญาที่ต้องพิสูจน์สองทิศ:

1. ระงับแล้ว: login ไม่ได้ (รหัสถูกก็ตาม — พร้อมเหตุผลบนหน้า) · session ที่
   เปิดค้างถูกตัด*ทันทีที่ request ถัดไปมาถึง* ไม่ใช่รอ timeout · ข้อมูล
   **ไม่ถูกแตะแม้แต่แถวเดียว**
2. เลิกระงับแล้ว: ทุกอย่างกลับเป็นปกติทั้งใบ
3. ด่านสิทธิ์อยู่ใน service · ระงับตัวเองไม่ได้ (เหตุผลเดียวกับ ADR 0022)
"""

import pytest

from app import db
from app.models import Todo, User
from app.services import ConflictError, ForbiddenError, ValidationError, suspension
from app.services import roles as roles_service
from tests.conftest import PASSWORD


def _people(app):
    with app.app_context():
        boss = User(username="boss", role=roles_service.ROLE_ADMIN)
        boss.set_password(PASSWORD)
        member = User(username="member")
        member.set_password(PASSWORD)
        db.session.add_all([boss, member])
        db.session.commit()
        db.session.add(Todo(title="workitem", user_id=member.id))
        db.session.commit()
        return boss.id, member.id


def _sign_in(app, username):
    client = app.test_client()
    resp = client.post("/login", data={"username": username, "password": PASSWORD})
    assert resp.status_code == 302
    return client


# ---------------------------------------------------------------- ตัว service


def test_suspend_blocks_login_even_with_the_right_password(app):
    _, member_id = _people(app)
    with app.app_context():
        boss = db.session.query(User).filter_by(username="boss").one()
        suspension.suspend(boss, member_id)

    client = app.test_client()
    resp = client.post("/login", data={"username": "member", "password": PASSWORD})
    assert resp.status_code == 403, "รหัสถูกแต่บัญชีถูกระงับ ต้องเข้าไม่ได้"
    assert "suspended" in resp.data.decode() or "ระงับ" in resp.data.decode()


def test_a_live_session_dies_on_the_next_request_after_suspension(app):
    """การระงับที่ปล่อย session เดิมทำงานต่อ ไม่ใช่การหยุดการประมวลผล"""
    _, member_id = _people(app)
    client = _sign_in(app, "member")
    assert client.get("/").status_code == 200

    with app.app_context():
        boss = db.session.query(User).filter_by(username="boss").one()
        suspension.suspend(boss, member_id)

    resp = client.get("/")
    assert resp.status_code == 302, "session ค้างต้องถูกตัดทันที ไม่ใช่รอ timeout"
    assert "/login" in resp.headers["Location"]


def test_suspension_touches_no_data_and_unsuspend_restores_everything(app):
    """ระงับ = หยุดการประมวลผล ไม่ใช่หยุดการเก็บ — ของทุกแถวต้องอยู่ครบเหมือนเดิม"""
    _, member_id = _people(app)
    with app.app_context():
        boss = db.session.query(User).filter_by(username="boss").one()
        suspension.suspend(boss, member_id)
        todos = db.session.query(Todo).filter_by(user_id=member_id).count()
        assert todos == 1, "ข้อมูลหายระหว่างระงับ — นี่คือการลบ ไม่ใช่การระงับ"
        suspension.unsuspend(boss, member_id)

    client = app.test_client()
    resp = client.post("/login", data={"username": "member", "password": PASSWORD})
    assert resp.status_code == 302, "เลิกระงับแล้วต้อง login ได้ตามปกติ"


def test_only_admins_can_suspend_and_never_themselves(app):
    boss_id, _member_id = _people(app)
    with app.app_context():
        boss = db.session.query(User).filter_by(username="boss").one()
        member = db.session.query(User).filter_by(username="member").one()
        with pytest.raises(ForbiddenError):
            suspension.suspend(member, boss_id)
        with pytest.raises(ValidationError):
            suspension.suspend(boss, boss_id)


def test_suspend_twice_is_a_conflict_not_a_silent_success(app):
    _, member_id = _people(app)
    with app.app_context():
        boss = db.session.query(User).filter_by(username="boss").one()
        suspension.suspend(boss, member_id)
        with pytest.raises(ConflictError):
            suspension.suspend(boss, member_id)
        suspension.unsuspend(boss, member_id)
        with pytest.raises(ConflictError):
            suspension.unsuspend(boss, member_id)


def test_the_change_lands_in_the_audit_trail(app):
    """การระงับต้องทิ้งหลักฐาน — ผ่าน after_flush อัตโนมัติเหมือนการแก้ user ทุกครั้ง"""
    from app.audit import AuditEntry

    _, member_id = _people(app)
    with app.app_context():
        boss = db.session.query(User).filter_by(username="boss").one()
        suspension.suspend(boss, member_id)
        entries = (
            db.session.query(AuditEntry)
            .filter(AuditEntry.table_name == "tdl_user", AuditEntry.row_id == member_id)
            .all()
        )
        assert any("suspended_at" in (entry.changes or "") for entry in entries), (
            "ไม่มีแถว audit ที่บันทึกการเปลี่ยน suspended_at"
        )


# ---------------------------------------------------------------- หน้า admin


def test_the_admin_page_can_suspend_and_lift_with_buttons(app):
    _, member_id = _people(app)
    client = _sign_in(app, "boss")

    resp = client.post(f"/admin/users/{member_id}/suspend", follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert db.session.get(User, member_id).suspended_at is not None

    resp = client.post(f"/admin/users/{member_id}/unsuspend", follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert db.session.get(User, member_id).suspended_at is None


def test_a_regular_user_cannot_suspend_anyone(app):
    boss_id, _ = _people(app)
    client = _sign_in(app, "member")
    assert client.post(f"/admin/users/{boss_id}/suspend").status_code == 403


def test_the_admin_page_reports_conflicts_and_missing_targets(app):
    """เส้นทาง error ของปุ่ม: 404 เมื่อไม่มีคน · Conflict = flash แล้วพากลับหน้าเดิม
    · ระงับตัวเอง = flash เหตุผล (ServiceError → ไม่ใช่ 500)"""
    boss_id, member_id = _people(app)
    client = _sign_in(app, "boss")

    assert client.post("/admin/users/99999/suspend").status_code == 404

    client.post(f"/admin/users/{member_id}/suspend")
    resp = client.post(f"/admin/users/{member_id}/suspend", follow_redirects=True)
    assert resp.status_code == 200, "ระงับซ้ำต้องพากลับหน้าเดิมพร้อมข้อความ ไม่ใช่พัง"
    assert "ถูกระงับอยู่แล้ว" in resp.data.decode()

    resp = client.post(f"/admin/users/{boss_id}/suspend", follow_redirects=True)
    assert "ตัวเอง" in resp.data.decode(), "ระงับตัวเองต้องถูกปฏิเสธพร้อมเหตุผล"


def test_the_cli_refuses_unknown_users_and_double_suspend(app):
    """เส้นทาง error ของ CLI ต้องดังพร้อมเหตุผล ไม่ใช่เงียบหรือ traceback"""
    _people(app)
    runner = app.test_cli_runner()

    result = runner.invoke(args=["suspend-user", "nobody"])
    assert "No user named" in result.output

    runner.invoke(args=["suspend-user", "member"])
    result = runner.invoke(args=["suspend-user", "member"])
    assert "already suspended" in result.output

    result = runner.invoke(args=["unsuspend-user", "nobody"])
    assert "No user named" in result.output


def test_the_cli_can_suspend_and_lift(app):
    """CLI ต้องเดินเส้นทางเดียวกับหน้าเว็บ — พฤติกรรมเดียว สองประตู"""
    _people(app)
    runner = app.test_cli_runner()
    result = runner.invoke(args=["suspend-user", "member"])
    assert "Suspended member" in result.output
    with app.app_context():
        assert db.session.query(User).filter_by(username="member").one().suspended_at is not None

    result = runner.invoke(args=["unsuspend-user", "member"])
    assert "active again" in result.output

    result = runner.invoke(args=["unsuspend-user", "member"])
    assert "not suspended" in result.output, "เลิกระงับซ้ำต้องบอกตรง ๆ ไม่ใช่เงียบ"
