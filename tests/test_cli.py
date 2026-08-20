"""เทสต์ flask CLI commands

จุดที่ต้องระวังคือ delete-user ต้องลบ category/todo ตามไปด้วย
SQLite ไม่บังคับ FK ให้ ถ้า cascade พังจะไม่มีอะไรฟ้อง แค่เหลือแถวกำพร้า
"""

import os

import pytest
from sqlalchemy import func, select

from app import cli, db
from app.cli import DEFAULT_CATEGORIES
from app.models import Category, Todo, User
from app.services import ServiceError, usernames
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


def test_mfa_status_says_so_when_no_plugin_is_installed(app, user_id, monkeypatch):
    """ติดตั้งแบบไม่มี plugin ปัจจัยที่สองเลย = สถานะปกติ ต้องบอก ไม่ใช่พิมพ์ตารางว่าง"""
    monkeypatch.setattr(cli.mfa_service, "state", _fake_state([]))

    result = app.test_cli_runner().invoke(args=["mfa-status", "tester"])

    assert result.exit_code == 0, result.output
    assert "No second-factor plugin" in result.output


def test_mfa_disable_refuses_a_factor_that_exists_but_is_not_on(app, user_id, monkeypatch):
    """plugin มีอยู่แต่ผู้ใช้ไม่ได้เปิด — สั่งปิดต้องล้ม ไม่ใช่รายงานว่าปิดให้แล้ว"""
    monkeypatch.setattr(
        cli.mfa_service,
        "state",
        _fake_state([{"key": "auth/totp", "enrolled": False, "pending": False}]),
    )

    result = app.test_cli_runner().invoke(
        args=["mfa-disable", "tester", "--factor", "auth/totp", "--yes"]
    )

    assert result.exit_code != 0
    assert "no factor" in result.output


def test_mfa_disable_can_target_one_factor_and_leave_the_rest(app, user_id, monkeypatch):
    """ระบุ --factor = ปิดตัวเดียว — ผู้ใช้ที่มีสองปัจจัยไม่ควรเสียตัวที่ยังใช้ได้"""
    monkeypatch.setattr(
        cli.mfa_service,
        "state",
        _fake_state(
            [
                {"key": "auth/totp", "enrolled": True, "pending": False},
                {"key": "auth/webauthn", "enrolled": True, "pending": False},
            ]
        ),
    )
    disabled = []
    monkeypatch.setattr(cli.mfa_service, "disable", lambda _u, key: disabled.append(key) or True)

    result = app.test_cli_runner().invoke(
        args=["mfa-disable", "tester", "--factor", "auth/totp", "--yes"]
    )

    assert result.exit_code == 0, result.output
    assert disabled == ["auth/totp"], "ต้องแตะเฉพาะตัวที่ระบุ"


# ---------------- ชื่อที่ชนกันแบบ casefold (audit รอบ 19 ข้อ 2)
#
# ตัวตนเทียบตรงตัวพิมพ์ (`app/auth.py`) แต่โควตากันเดารหัสผ่านเทียบแบบ casefold
# (ADR 0021 · ตั้งใจ) · ปล่อยให้มี `alice` กับ `Alice` พร้อมกันเมื่อไหร่ คนนอกยิง
# รหัสผิดใส่ชื่อหนึ่งห้าครั้ง จะล็อกอีกชื่อออกจากระบบ — **ปฏิเสธบริการข้ามบัญชี
# โดยไม่ต้องรู้อะไรเกี่ยวกับเป้าเลย** · วัดจริงในรอบ 19: create-user Alice สำเร็จ


def test_create_user_rejects_a_name_that_only_differs_in_case(app):
    """ทิศที่บั๊กอยู่ — `Alice` ต้องถูกปฏิเสธเมื่อมี `alice` แล้ว"""
    runner = app.test_cli_runner()
    runner.invoke(args=["create-user", "alice"], input=f"{PASSWORD}\n{PASSWORD}\n")

    result = runner.invoke(args=["create-user", "Alice"], input=f"{PASSWORD}\n{PASSWORD}\n")

    assert result.exit_code != 0, result.output
    assert "alice" in result.output
    with app.app_context():
        # **นับจำนวน ไม่ใช่ค้นด้วยชื่อ** — collation เริ่มต้นของ MySQL/MariaDB
        # ไม่สนตัวพิมพ์ การค้น "Alice" จึงคืนแถวของ `alice` มาให้ (ซึ่งถูกของมัน)
        assert db.session.scalar(select(func.count()).select_from(User)) == 1


def test_create_user_still_accepts_a_genuinely_new_name(app):
    """ทิศ "ผ่านเมื่อควรผ่าน" — ด่านที่กันชื่อที่ไม่ได้ชนกัน คือด่านที่ต้องถูกถอด"""
    runner = app.test_cli_runner()
    runner.invoke(args=["create-user", "alice"], input=f"{PASSWORD}\n{PASSWORD}\n")

    result = runner.invoke(args=["create-user", "alicia"], input=f"{PASSWORD}\n{PASSWORD}\n")

    assert result.exit_code == 0, result.output


@pytest.mark.skipif(
    os.environ.get("TEST_DATABASE_URL", "sqlite").startswith(("mysql", "mariadb")),
    reason=(
        "MySQL/MariaDB เทียบ unique index ด้วย collation ที่ไม่สนตัวพิมพ์ — "
        "สภาพ 'ชนกันอยู่แล้ว' จึงสร้างไม่ได้บนยี่ห้อนั้นตามนิยาม (ฐานกันให้ตั้งแต่แรก) · "
        "SQLite ใช้ BINARY จึงเป็นยี่ห้อเดียวที่ของแบบนี้เกิดได้ และเป็นค่าเริ่มต้นของ dev"
    ),
)
def test_the_collision_scan_reports_names_that_are_already_clashing(app):
    """ของที่ชนกันก่อนกฎข้อนี้เกิด ต้องมีคนบอก ไม่ใช่รอให้เจอตอนล็อกอินไม่ได้"""
    with app.app_context():
        for name in ("alice", "Alice", "bob"):
            person = User(username=name)
            person.set_password(PASSWORD)
            db.session.add(person)
        db.session.commit()

        assert usernames.collisions() == [["Alice", "alice"]]


def test_the_collision_scan_is_quiet_when_nothing_clashes(app):
    with app.app_context():
        for name in ("alice", "bob"):
            person = User(username=name)
            person.set_password(PASSWORD)
            db.session.add(person)
        db.session.commit()

        assert usernames.collisions() == []
