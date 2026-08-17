"""เทสต์ flask CLI commands

จุดที่ต้องระวังคือ delete-user ต้องลบ category/todo ตามไปด้วย
SQLite ไม่บังคับ FK ให้ ถ้า cascade พังจะไม่มีอะไรฟ้อง แค่เหลือแถวกำพร้า
"""

from app import cli, db
from app.cli import DEFAULT_CATEGORIES
from app.models import Category, Todo, User
from app.services import ServiceError
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


def _fake_state(rows):
    """สถานะปัจจัยแบบปลอม — CLI เป็น adapter ตรรกะจริงมีเทสต์ของตัวเองใน service"""
    return lambda _user: rows


def test_mfa_status_lists_each_factor_with_its_state(app, user_id, monkeypatch):
    """สามสถานะต้องอ่านออกจากกัน — pending คือ "เริ่มตั้งแล้วไม่เคยยืนยัน" ซึ่งต้องปิดได้ด้วย"""
    monkeypatch.setattr(
        cli.mfa_service,
        "state",
        _fake_state(
            [
                {"key": "auth/totp", "enrolled": True, "pending": False},
                {"key": "auth/webauthn", "enrolled": False, "pending": True},
                {"key": "auth/sms", "enrolled": False, "pending": False},
            ]
        ),
    )

    result = app.test_cli_runner().invoke(args=["mfa-status", "tester"])

    assert result.exit_code == 0, result.output
    assert "auth/totp" in result.output
    assert "enrolled" in result.output
    assert "pending" in result.output
    assert "not enrolled" in result.output


def test_mfa_disable_turns_every_enrolled_factor_off(app, user_id, monkeypatch):
    """ไม่ระบุ --factor = ปิดทุกตัวที่เปิดค้าง (คนที่โทรมาขอความช่วยเหลือไม่รู้ชื่อ plugin)"""
    monkeypatch.setattr(
        cli.mfa_service,
        "state",
        _fake_state(
            [
                {"key": "auth/totp", "enrolled": True, "pending": False},
                {"key": "auth/webauthn", "enrolled": False, "pending": True},
            ]
        ),
    )
    disabled = []
    monkeypatch.setattr(cli.mfa_service, "disable", lambda _u, key: disabled.append(key) or True)

    result = app.test_cli_runner().invoke(args=["mfa-disable", "tester", "--yes"])

    assert result.exit_code == 0, result.output
    assert disabled == ["auth/totp", "auth/webauthn"], "ต้องปิดทั้งตัวที่ enrolled และที่ค้าง pending"


def test_mfa_disable_asks_before_acting(app, user_id, monkeypatch):
    """ไม่ใส่ --yes แล้วตอบ n ต้องไม่แตะอะไรเลย — คำสั่งนี้ลดระดับความปลอดภัยของบัญชีคนอื่น"""
    monkeypatch.setattr(
        cli.mfa_service,
        "state",
        _fake_state([{"key": "auth/totp", "enrolled": True, "pending": False}]),
    )
    touched = []
    monkeypatch.setattr(cli.mfa_service, "disable", lambda _u, key: touched.append(key))

    result = app.test_cli_runner().invoke(args=["mfa-disable", "tester"], input="n\n")

    assert result.exit_code != 0, "ตอบ n แล้วต้อง abort"
    assert touched == [], "abort แล้วต้องไม่มีการปิดปัจจัยใด ๆ"


def test_mfa_disable_reports_a_plugin_that_cannot_act(app, user_id, monkeypatch):
    """plugin ถูกปิดด้วย DISABLED_PLUGINS หรือหายจากดิสก์ = ต้องบอกตรง ๆ ไม่ใช่เงียบ"""
    monkeypatch.setattr(
        cli.mfa_service,
        "state",
        _fake_state([{"key": "auth/totp", "enrolled": True, "pending": False}]),
    )

    def _raise(_user, _key):
        raise ServiceError("plugin auth/totp is not available", code="plugin_unavailable")

    monkeypatch.setattr(cli.mfa_service, "disable", _raise)

    result = app.test_cli_runner().invoke(args=["mfa-disable", "tester", "--yes"])

    assert result.exit_code != 0
    assert "not available" in result.output
