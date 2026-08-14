"""ปิดบัญชีตัวเอง (ADR 0034 ข้อ 4)

**เทสต์ที่ตรวจแค่ "login ไม่ได้แล้ว" ผ่านได้ทั้งที่ความลับยังอยู่ในฐานข้อมูล**
ซึ่งเป็นข้อบกพร่องที่มีอยู่จริงใน `flask delete-user` มาก่อน ADR 0034 —
เทสต์ที่นี่จึงตรวจ *สิ่งที่ต้องหายไป* ทีละอย่าง ไม่ใช่ตรวจผลลัพธ์ปลายทางอย่างเดียว
"""

import pytest

from app import db
from app.models import ApiToken, Category, Todo, User
from app.services import personal_data
from app.services import roles as roles_service
from app.services.errors import ConflictError
from tests.conftest import PASSWORD


def _closed_user(user_id):
    """อ่านแถวที่ถูก soft delete แล้ว — ตัวกรองซ่อนมันจากทุก query ที่ไม่ได้ขอยกเว้น"""
    return db.session.scalars(
        db.select(User).where(User.id == user_id).execution_options(include_deleted=True)
    ).first()


@pytest.fixture
def furnished(app, user_id):
    """ผู้ใช้ที่มีของครบทุกชนิดที่การปิดบัญชีต้องจัดการ"""
    with app.app_context():
        user = db.session.get(User, user_id)
        category = Category(name="งานบ้าน", user_id=user.id)
        db.session.add(category)
        db.session.commit()
        db.session.add(Todo(title="ล้างจาน", user_id=user.id, category_id=category.id))
        db.session.add(ApiToken(user_id=user.id, name="กุญแจ", token_hash="c" * 64))
        db.session.commit()
    return user_id


def test_closing_removes_everything_it_promised(app, furnished):
    with app.app_context():
        user = db.session.get(User, furnished)
        summary = personal_data.close_account(user, actor=user)

    assert summary["todos"] == 1
    assert summary["categories"] == 1
    assert summary["tokens"] == 1

    with app.app_context():
        db.session.expunge_all()
        closed = _closed_user(furnished)
        assert closed.deleted_at is not None
        # ตัวกรอง soft delete ซ่อนของที่ถูกลบไปแล้ว — ไม่เหลืออะไรให้เห็น
        assert db.session.scalars(db.select(Todo).where(Todo.user_id == furnished)).all() == []
        assert (
            db.session.scalars(db.select(Category).where(Category.user_id == furnished)).all() == []
        )


def test_the_password_is_cleared_immediately_not_after_the_grace_period(app, furnished):
    """C1 ล้างทันที ไม่รอ 30 วัน (ADR 0014) — และคุกกี้ทุกใบตายไปพร้อมกัน"""
    with app.app_context():
        user = db.session.get(User, furnished)
        before = user.password_hash
        personal_data.close_account(user, actor=user)

        db.session.expunge_all()
        closed = _closed_user(furnished)
        assert closed.password_hash != before
        assert not closed.check_password(PASSWORD)


def test_api_keys_are_revoked_not_just_hidden(app, furnished):
    """กู้แถวคืนมาก็ต้องใช้ไม่ได้ — ใบที่ยังไม่หมดอายุคือกุญแจที่ยังเปิดประตูได้"""
    with app.app_context():
        user = db.session.get(User, furnished)
        personal_data.close_account(user, actor=user)

        db.session.expunge_all()
        token = db.session.scalars(
            db.select(ApiToken)
            .where(ApiToken.user_id == furnished)
            .execution_options(include_deleted=True)
        ).first()
        assert token.deleted_at is not None
        assert token.token_hash != "c" * 64, "hash ต้องถูกล้าง ไม่ใช่แค่ซ่อนแถว"


def test_the_last_administrator_cannot_close_their_own_account(app, user_id):
    """ระบบที่ไม่เหลือผู้ดูแลคือระบบที่ไม่มีใครสร้างบัญชีหรือกู้รหัสให้ใครได้อีก"""
    with app.app_context():
        user = db.session.get(User, user_id)
        roles_service.set_role(user, "admin")
        db.session.commit()

        with pytest.raises(ConflictError) as raised:
            personal_data.close_account(user, actor=user)
        assert raised.value.code == "last_administrator"
        assert user.deleted_at is None, "ปฏิเสธแล้วต้องไม่แตะอะไรเลย"
        # ข้อความต้องบอกทางออก ไม่ใช่บอกแค่ว่าทำไม่ได้
        assert "administrator" in raised.value.message


def test_an_administrator_can_close_when_someone_else_can_still_run_the_place(
    app, user_id, other_user_id
):
    with app.app_context():
        user = db.session.get(User, user_id)
        other = db.session.get(User, other_user_id)
        roles_service.set_role(user, "admin")
        roles_service.set_role(other, "admin")
        db.session.commit()

        personal_data.close_account(user, actor=user)
        assert user.deleted_at is not None


def test_the_cli_can_still_close_the_last_administrator(app, user_id):
    """CLI เป็นตัวตนที่แรงกว่าและเป็นทางกู้ระบบทางเดียวที่เหลือ (หลักเดียวกับ ADR 0022)"""
    with app.app_context():
        user = db.session.get(User, user_id)
        roles_service.set_role(user, "admin")
        db.session.commit()

    result = app.test_cli_runner().invoke(args=["delete-user", "tester", "--yes"])
    assert result.exit_code == 0, result.output

    with app.app_context():
        db.session.expunge_all()
        assert _closed_user(user_id).deleted_at is not None


@pytest.mark.plugin_deps  # start_enrollment เขียนความลับแบบ encrypt แล้ว (ADR 0046)
def test_secrets_held_by_plugins_are_erased_too(app, user_id):
    """**นี่คือบั๊กที่ ADR 0034 หาเจอ** — `flask delete-user` เดิมล้างรหัสผ่านกับ
    token ครบ แต่ไม่เคยแตะความลับของปัจจัยที่สองเลย ทั้งที่คอมเมนต์ในฟังก์ชันนั้น
    อ้างกติกา C1 อยู่ · ตารางของ plugin อยู่นอกวงจร purge ของ core ความลับจึงค้าง
    อยู่ตลอดกาลของบัญชีที่ปิดไปแล้ว

    core ไม่รู้จักชื่อ plugin ตัวไหน — ถามผ่าน registry เหมือนที่โค้ดจริงทำ
    """
    from app import plugins

    with app.app_context():
        plugin = plugins.find("auth/totp")
        module = plugins.factor_module(plugin)
        user = db.session.get(User, user_id)
        module.start_enrollment(user)
        db.session.commit()

        contributor = plugins.load_module(plugin, "personal_data")
        assert contributor.export_for(user) is not None, (
            "ต้องมีความลับอยู่ก่อน ไม่งั้นเทสต์นี้ผ่านเพราะไม่มีอะไรให้ลบ"
        )

        summary = personal_data.close_account(user, actor=user)
        assert summary["plugins"]["auth/totp"] == 1, "plugin ต้องรายงานว่าลบไปกี่แถว"

        assert contributor.export_for(user) is None, "ความลับต้องไม่เหลืออยู่เลย"


# ---------------------------------------------------------------- หน้าเว็บ


def test_the_web_page_needs_the_current_password(app, client, user_id):
    resp = client.post("/settings/close", data={"password": "ไม่ใช่รหัสของฉัน"})
    assert resp.status_code == 302
    with app.app_context():
        assert db.session.get(User, user_id).deleted_at is None, "รหัสผิดแล้วต้องไม่มีอะไรเกิดขึ้น"


def test_closing_from_the_web_page_ends_the_session(app, client, user_id):
    resp = client.post("/settings/close", data={"password": PASSWORD})
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    # session ต้องจบจริง ไม่ใช่แค่ redirect
    # (`?next=` ที่ Flask-Login ต่อท้ายมาถูกเมินอยู่แล้ว — หน้า login ไม่รองรับมัน)
    assert "/login" in client.get("/", follow_redirects=False).headers["Location"]


def test_signing_in_again_is_refused_after_closing(app, client, anon_client, user_id):
    client.post("/settings/close", data={"password": PASSWORD})
    resp = anon_client.post("/login", data={"username": "tester", "password": PASSWORD})
    assert resp.status_code == 401, "บัญชีที่ปิดแล้วต้อง login ไม่ได้"


def test_closing_the_account_is_recorded(app, client, user_id):
    from app.audit import AuditEntry

    client.post("/settings/close", data={"password": PASSWORD})
    with app.app_context():
        events = [row.event for row in db.session.scalars(db.select(AuditEntry))]
    assert "user.close_account" in events


def test_a_stranger_cannot_close_someone_elses_account(anon_client, app, user_id):
    resp = anon_client.post("/settings/close", data={"password": PASSWORD})
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    with app.app_context():
        assert db.session.get(User, user_id).deleted_at is None
