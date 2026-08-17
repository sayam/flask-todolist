"""เทสต์ flask CLI commands

จุดที่ต้องระวังคือ delete-user ต้องลบ category/todo ตามไปด้วย
SQLite ไม่บังคับ FK ให้ ถ้า cascade พังจะไม่มีอะไรฟ้อง แค่เหลือแถวกำพร้า
"""

from app import db
from app.cli import DEFAULT_CATEGORIES
from app.models import Category, Todo, User
from tests.conftest import PASSWORD


def test_create_user_seeds_default_categories(app):
    result = app.test_cli_runner().invoke(
        args=["create-user", "somchai"], input=f"{PASSWORD}\n{PASSWORD}\n"
    )
    assert result.exit_code == 0, result.output
    with app.app_context():
        user = User.query.filter_by(username="somchai").one()
        names = {c.name for c in user.categories}
        assert names == set(DEFAULT_CATEGORIES["en"])


def test_create_user_rejects_short_password(app):
    result = app.test_cli_runner().invoke(args=["create-user", "somchai"], input="sh0rt\nsh0rt\n")
    assert result.exit_code != 0
    with app.app_context():
        assert User.query.filter_by(username="somchai").first() is None


def test_create_user_rejects_duplicate(app, user_id):
    result = app.test_cli_runner().invoke(args=["create-user", "tester"])
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_create_user_no_categories_flag(app):
    app.test_cli_runner().invoke(
        args=["create-user", "somchai", "--no-categories"],
        input=f"{PASSWORD}\n{PASSWORD}\n",
    )
    with app.app_context():
        assert User.query.filter_by(username="somchai").one().categories == []


def test_delete_user_removes_categories_and_todos(app, user_id, category_id):
    with app.app_context():
        db.session.add(Todo(title="งานที่ต้องหายไปด้วย", user_id=user_id, category_id=category_id))
        db.session.commit()

    result = app.test_cli_runner().invoke(args=["delete-user", "tester", "--yes"])
    assert result.exit_code == 0, result.output

    with app.app_context():
        assert User.query.filter_by(username="tester").first() is None
        assert Category.query.count() == 0, "หมวดของ user ที่ถูกลบต้องหายไปด้วย"
        assert Todo.query.count() == 0, "งานของ user ที่ถูกลบต้องหายไปด้วย"


def test_delete_user_not_found(app):
    result = app.test_cli_runner().invoke(args=["delete-user", "ไม่มีคนนี้", "--yes"])
    assert result.exit_code != 0
    assert "No user named" in result.output


def test_delete_user_aborts_without_confirmation(app, user_id):
    """ไม่ใส่ --yes แล้วตอบ n ต้องไม่ลบ"""
    result = app.test_cli_runner().invoke(args=["delete-user", "tester"], input="n\n")
    assert result.exit_code != 0
    with app.app_context():
        assert User.query.filter_by(username="tester").first() is not None


def test_delete_user_keeps_other_users_data(app, user_id, other_user_id):
    with app.app_context():
        db.session.add(Category(name="ของคนอื่น", user_id=other_user_id))
        db.session.commit()

    app.test_cli_runner().invoke(args=["delete-user", "tester", "--yes"])

    with app.app_context():
        assert User.query.filter_by(username="intruder").first() is not None
        assert Category.query.filter_by(name="ของคนอื่น").count() == 1


# --------------------------------------------------------------------------
# ทางกู้เมื่ออุปกรณ์ปัจจัยที่สองหาย (audit governance รอบ 5 · ADR 0033 หมายเหตุ)
# — หน้าเว็บปิดปัจจัยได้เฉพาะของคนที่ login อยู่ ซึ่งคือคนที่ login ไม่ได้พอดี
# ก่อนมีคำสั่งพวกนี้ ผู้ดูแลต้องแตะฐานข้อมูลเอง ซึ่งไม่มีใครอยากทำตอนตีสาม
# --------------------------------------------------------------------------


def test_mfa_status_reports_a_user_with_no_factor(app, user_id):
    """ผู้ใช้ที่ยังไม่เปิดปัจจัยที่สองต้องอ่านออกว่า "ยังไม่เปิด" ไม่ใช่เงียบ"""
    result = app.test_cli_runner().invoke(args=["mfa-status", "tester"])

    assert result.exit_code == 0, result.output
    assert "not enrolled" in result.output or "No second-factor plugin" in result.output


def test_mfa_status_refuses_an_unknown_user(app):
    result = app.test_cli_runner().invoke(args=["mfa-status", "nobody"])

    assert result.exit_code != 0
    assert "No user named" in result.output


def test_mfa_disable_says_nothing_to_do_when_no_factor_is_on(app, user_id):
    """ไม่มีอะไรให้ปิดต้องบอกตรง ๆ — ไม่ใช่ตอบเหมือนทำสำเร็จ"""
    result = app.test_cli_runner().invoke(args=["mfa-disable", "tester", "--yes"])

    assert result.exit_code == 0, result.output
    assert "nothing to do" in result.output


def test_mfa_disable_refuses_a_factor_the_user_does_not_have(app, user_id):
    """ขอปิดตัวที่ไม่ได้เปิดไว้ = ผิดคาดของคนสั่ง ต้องล้มดัง ไม่ใช่เงียบแล้วผ่าน"""
    result = app.test_cli_runner().invoke(
        args=["mfa-disable", "tester", "--factor", "auth/totp", "--yes"]
    )

    assert result.exit_code != 0
    assert "no factor" in result.output


def test_mfa_disable_refuses_an_unknown_user(app):
    result = app.test_cli_runner().invoke(args=["mfa-disable", "nobody", "--yes"])

    assert result.exit_code != 0
    assert "No user named" in result.output
