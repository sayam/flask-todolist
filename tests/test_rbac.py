"""RBAC ขั้นต่ำ: บทบาท admin/user (Phase 4 — ดู ADR 0022)

สิ่งที่ต้องพิสูจน์ไม่ใช่แค่ "admin เข้าได้" แต่คือ **"คนที่ไม่ใช่ admin เข้าไม่ได้
และข้อมูลไม่ถูกแก้"** — เทสต์ที่เช็คแค่ status code จะเขียวต่อให้ด่านถูกถอดออก
แล้วการเขียนเกิดขึ้นจริงก่อนถูกปฏิเสธ

**app context อยู่ที่ fixture ตัวเทสต์ห้ามเปิดซ้อน** (เหตุผลใน tests/test_services.py)
"""

import pytest

from app import db
from app.audit import AuditEntry
from app.models import User
from app.services import ConflictError, ForbiddenError, ValidationError
from app.services import roles as roles_service
from tests.conftest import PASSWORD


def _add_user(username, role="user"):
    user = User(username=username, role=role)
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def boss(app):
    """ผู้ดูแลระบบหนึ่งคน (context เปิดค้างไว้ให้)"""
    with app.app_context():
        yield _add_user("boss", role=roles_service.ROLE_ADMIN)


@pytest.fixture
def member(app, boss):
    """ผู้ใช้ธรรมดา — ต้องมาหลัง boss เพื่อไม่เปิด context ซ้อน"""
    return _add_user("member")


@pytest.fixture
def two_people(app):
    """สร้างทั้งสองคนแล้ว **ปิด app context ทิ้ง** — สำหรับเทสต์ฝั่งเว็บเท่านั้น

    **ห้ามยิง HTTP ขณะที่มี app context ค้างอยู่** Flask ใช้ app context เดิม
    ถ้ามีของแอปเดียวกันค้างอยู่แล้ว (ไม่ push ใหม่) ซึ่งแปลว่า `g` เป็นก้อนเดียว
    กันทุก request — Flask-Login cache `current_user` ไว้ใน `g` ผลคือ **ผู้ใช้
    ของ request ก่อนหน้าติดมาให้ request ถัดไป** เทสต์ที่ login เป็นคนละคน
    สองรอบจะกลายเป็นคนเดิมทั้งสองรอบโดยไม่มีอะไรฟ้อง (เจอมาแล้วตอนเขียนไฟล์นี้:
    เทสต์เมนูของผู้ดูแลเห็นเมนูของ boss ตอนที่ login เป็น member)
    """
    with app.app_context():
        boss = _add_user("boss", role=roles_service.ROLE_ADMIN)
        member = _add_user("member")
        return boss.id, member.id


def _sign_in(app, username):
    client = app.test_client()
    resp = client.post("/login", data={"username": username, "password": PASSWORD})
    assert resp.status_code == 302, f"login เป็น {username} ไม่สำเร็จ"
    return client


# ---------------------------------------------------------------- ตัวบทบาทเอง


def test_a_new_user_is_not_an_administrator(app, user_id):
    """ค่าเริ่มต้นต้องเป็นสิทธิ์ต่ำสุดเสมอ ไม่ใช่สิ่งที่ต้องไปปิดทีหลัง"""
    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.role == roles_service.ROLE_USER
        assert not user.is_admin


def test_require_admin_lets_an_administrator_through(boss):
    assert roles_service.require_admin(boss) is None


def test_require_admin_stops_everyone_else(member):
    with pytest.raises(ForbiddenError) as raised:
        roles_service.require_admin(member)
    assert raised.value.code == "admin_required"


# ---------------------------------------------------------------- service


def test_listing_users_is_for_administrators_only(member):
    with pytest.raises(ForbiddenError):
        roles_service.list_users(member)


def test_an_administrator_sees_everyone(boss, member):
    names = {person.username for person in roles_service.list_users(boss)}
    assert {"boss", "member"} <= names


def test_assigning_a_role_is_written_to_the_database(app, boss, member):
    member_id = member.id
    roles_service.assign_role(boss, member_id, roles_service.ROLE_ADMIN)
    db.session.remove()

    assert db.session.get(User, member_id).role == roles_service.ROLE_ADMIN


def test_an_unknown_role_is_rejected(boss, member):
    with pytest.raises(ValidationError) as raised:
        roles_service.assign_role(boss, member.id, "superuser")
    assert raised.value.code == "role_invalid"


def test_nobody_can_change_their_own_role(boss):
    """ผู้ดูแลคนสุดท้ายที่ถอดสิทธิ์ตัวเอง = ไม่เหลือใครเข้าหน้าผู้ดูแลได้อีก"""
    with pytest.raises(ConflictError) as raised:
        roles_service.assign_role(boss, boss.id, roles_service.ROLE_USER)
    assert raised.value.code == "role_self_change"
    assert boss.role == roles_service.ROLE_ADMIN


def test_a_normal_user_cannot_promote_themselves(app, boss, member):
    member_id = member.id
    with pytest.raises(ForbiddenError):
        roles_service.assign_role(member, member_id, roles_service.ROLE_ADMIN)
    db.session.remove()

    assert db.session.get(User, member_id).role == roles_service.ROLE_USER, (
        "ต้องไม่มีการเขียนเกิดขึ้นก่อนถูกปฏิเสธ"
    )


def test_the_role_change_is_readable_in_the_audit_trail(boss, member):
    """`role` เป็นชั้น C4 จึงบันทึกค่าจริงได้ — ถ้าเก็บเป็น HMAC จะตอบคำถาม
    "ใครยกระดับใครเป็น admin" ไม่ได้เลย ซึ่งเป็นคำถามแรก ๆ ตอนสืบเหตุ"""
    roles_service.assign_role(boss, member.id, roles_service.ROLE_ADMIN)

    dump = " ".join(row.changes for row in db.session.query(AuditEntry).all())
    assert '"to":"admin"' in dump


def test_the_cli_path_validates_the_role_too(member):
    """`set_role()` ข้ามด่านสิทธิ์ (ทางของ CLI) แต่ห้ามข้ามการตรวจค่า —
    ไม่งั้นพิมพ์ผิดครั้งเดียวได้บทบาทที่ไม่มีใครรู้จักค้างอยู่ในฐานข้อมูล"""
    with pytest.raises(ValidationError) as raised:
        roles_service.set_role(member, "superuser")
    assert raised.value.code == "role_invalid"
    assert member.role == roles_service.ROLE_USER


# ---------------------------------------------------------------- ฝั่งเว็บ


def test_the_admin_page_is_closed_to_normal_users(app, two_people):
    assert _sign_in(app, "member").get("/admin/users").status_code == 403


def test_the_admin_page_opens_for_administrators(app, two_people):
    body = _sign_in(app, "boss").get("/admin/users").get_data(as_text=True)
    assert "member" in body


def test_the_admin_page_needs_a_signed_in_user(app, anon_client):
    resp = anon_client.get("/admin/users")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_the_menu_shows_the_admin_link_only_to_administrators(app, two_people):
    assert "/admin/users" in _sign_in(app, "boss").get("/").get_data(as_text=True)
    assert "/admin/users" not in _sign_in(app, "member").get("/").get_data(as_text=True)


def test_changing_a_role_from_the_web_page(app, two_people):
    _, member_id = two_people
    resp = _sign_in(app, "boss").post(
        f"/admin/users/{member_id}/role", data={"role": roles_service.ROLE_ADMIN}
    )
    assert resp.status_code == 302

    with app.app_context():
        assert db.session.get(User, member_id).role == roles_service.ROLE_ADMIN


def test_posting_a_role_change_as_a_normal_user_changes_nothing(app, two_people):
    """ด่านต้องอยู่ที่ route ไม่ใช่แค่ที่การซ่อนเมนู"""
    boss_id, member_id = two_people
    resp = _sign_in(app, "member").post(
        f"/admin/users/{boss_id}/role", data={"role": roles_service.ROLE_USER}
    )
    assert resp.status_code == 403

    with app.app_context():
        assert db.session.get(User, boss_id).role == roles_service.ROLE_ADMIN
        assert db.session.get(User, member_id).role == roles_service.ROLE_USER


def test_changing_the_role_of_someone_who_does_not_exist(app, two_people):
    assert (
        _sign_in(app, "boss").post("/admin/users/999999/role", data={"role": "admin"}).status_code
        == 404
    )


def test_a_bad_role_value_is_reported_not_stored(app, two_people):
    _, member_id = two_people
    resp = _sign_in(app, "boss").post(
        f"/admin/users/{member_id}/role", data={"role": "superuser"}, follow_redirects=True
    )
    assert "Unknown role" in resp.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(User, member_id).role == roles_service.ROLE_USER


# ---------------------------------------------------------------- CLI


def test_set_role_command_creates_the_first_administrator(app, user_id):
    """ระบบที่ยังไม่มีผู้ดูแลเลยต้องมีทางตั้งคนแรกได้ — ทางนั้นคือ CLI"""
    result = app.test_cli_runner().invoke(args=["set-role", "tester", "admin"])
    assert result.exit_code == 0, result.output
    with app.app_context():
        assert db.session.get(User, user_id).is_admin


def test_set_role_command_rejects_an_unknown_role(app, user_id):
    result = app.test_cli_runner().invoke(args=["set-role", "tester", "superuser"])
    assert result.exit_code != 0
    with app.app_context():
        assert db.session.get(User, user_id).role == roles_service.ROLE_USER


def test_set_role_command_rejects_an_unknown_user(app):
    result = app.test_cli_runner().invoke(args=["set-role", "ไม่มีคนนี้", "admin"])
    assert result.exit_code != 0
    assert "No user named" in result.output


def test_list_users_shows_the_role(app, user_id):
    result = app.test_cli_runner().invoke(args=["list-users"])
    assert "tester" in result.output
    assert "user" in result.output
