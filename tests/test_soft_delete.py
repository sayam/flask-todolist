"""ลบแล้วต้องหายจากสายตา แต่ยังอยู่ในฐานข้อมูลจนกว่าจะพ้นระยะ

จุดที่พังง่ายที่สุดคือ **ลืมกรอง** — query ใหม่ที่ไม่ได้ใส่ `deleted_at IS NULL`
จะทำให้ของที่ผู้ใช้สั่งลบโผล่กลับมาโดยไม่มีใครสังเกต ตัวกรองจึงถูกเติมอัตโนมัติ
ที่ระดับ session (app/soft_delete.py) ไม่ใช่ให้แต่ละจุดเรียกเอง
ชุดนี้ตรวจว่ากลไกนั้นครอบทุกทางเข้าจริง: query, get, relationship
"""

from datetime import timedelta

import pytest

from app import db, tz
from app.models import Category, Todo, User
from app.purge import PURGE_AFTER_DAYS, purge_expired
from app.soft_delete import INCLUDE_DELETED


def _make_todo(user_id, title="งานสำหรับทดสอบการลบ", category_id=None):
    todo = Todo(title=title, user_id=user_id, category_id=category_id)
    db.session.add(todo)
    db.session.commit()
    return todo.id


def _age(model, row_id, days):
    """ย้อนเวลา deleted_at ให้เก่าลง เพื่อทดสอบ purge โดยไม่ต้องรอจริง"""
    row = db.session.get(model, row_id, execution_options=INCLUDE_DELETED)
    row.deleted_at = tz.now_utc() - timedelta(days=days)
    db.session.commit()


# --- ตัวกรองอัตโนมัติครอบทุกทางเข้า ---


def test_soft_deleted_row_disappears_from_query(app, user_id):
    with app.app_context():
        todo_id = _make_todo(user_id)
        db.session.get(Todo, todo_id).soft_delete()
        db.session.commit()

        assert Todo.query.filter_by(user_id=user_id).count() == 0


def test_soft_deleted_row_disappears_from_get(app, user_id):
    """`session.get()` ที่ต้องยิง query จริงต้องถูกกรองด้วย

    ต้อง `expunge_all()` ก่อน ไม่ใช่แค่ `expire_all()` — ถ้า object ยังอยู่ใน
    identity map `get()` จะคืนตัวนั้นกลับมาโดยไม่ query เลย ตัวกรองจึงไม่มีโอกาส
    ทำงาน (ข้อจำกัดของ with_loader_criteria — ดู app/soft_delete.py)
    request จริงไม่เจอปัญหานี้เพราะแต่ละ request ได้ session ใหม่
    """
    with app.app_context():
        todo_id = _make_todo(user_id)
        db.session.get(Todo, todo_id).soft_delete()
        db.session.commit()
        db.session.expunge_all()

        assert db.session.get(Todo, todo_id) is None


def test_soft_deleted_row_disappears_from_relationship(app, user_id, category_id):
    """โหลดผ่าน relationship ก็ต้องไม่เห็น ไม่งั้นหน้าเว็บที่ใช้ user.todos จะเผลอโชว์"""
    with app.app_context():
        _make_todo(user_id, category_id=category_id)
        user = db.session.get(User, user_id)
        assert len(user.todos) == 1

        user.todos[0].soft_delete()
        db.session.commit()
        db.session.expire_all()

        assert db.session.get(User, user_id).todos == []


def test_the_row_is_still_in_the_database(app, user_id):
    """ "ลบ" ต้องแปลว่าซ่อน ไม่ใช่หาย — ไม่งั้นกู้คืนใน 30 วันไม่ได้"""
    with app.app_context():
        todo_id = _make_todo(user_id)
        db.session.get(Todo, todo_id).soft_delete()
        db.session.commit()

        found = db.session.get(Todo, todo_id, execution_options=INCLUDE_DELETED)
        assert found is not None
        assert found.deleted_at is not None


def test_soft_delete_twice_keeps_the_first_time(app, user_id):
    """ลบซ้ำต้องไม่เลื่อนกำหนด purge ออกไป ไม่งั้นของที่ควรถูกล้างจะค้างตลอดกาล"""
    with app.app_context():
        todo_id = _make_todo(user_id)
        todo = db.session.get(Todo, todo_id)
        todo.soft_delete()
        first = todo.deleted_at
        todo.soft_delete()
        assert todo.deleted_at == first


# --- route ต้องเลิก hard delete ---


def test_deleting_a_task_keeps_the_row(app, client, user_id):
    with app.app_context():
        todo_id = _make_todo(user_id, title="งานที่จะกดลบ")

    client.post(f"/delete/{todo_id}")

    with app.app_context():
        assert db.session.get(Todo, todo_id) is None
        kept = db.session.get(Todo, todo_id, execution_options=INCLUDE_DELETED)
        assert kept is not None, "route ยังลบแถวจริงอยู่ — ต้องเป็น soft delete"


def test_clear_completed_soft_deletes_every_finished_task(app, client, user_id):
    with app.app_context():
        done_id = _make_todo(user_id, title="ล้างรถ")
        open_id = _make_todo(user_id, title="ตัดผม")
        db.session.get(Todo, done_id).is_done = True
        db.session.commit()

    client.post("/clear-completed")

    with app.app_context():
        assert db.session.get(Todo, done_id) is None
        assert db.session.get(Todo, done_id, execution_options=INCLUDE_DELETED) is not None
        assert db.session.get(Todo, open_id) is not None, "งานที่ยังไม่เสร็จต้องไม่ถูกแตะ"


def test_deleting_a_category_keeps_the_row(app, client, user_id, category_id):
    client.post(f"/categories/delete/{category_id}")

    with app.app_context():
        assert db.session.get(Category, category_id) is None
        assert db.session.get(Category, category_id, execution_options=INCLUDE_DELETED) is not None


def test_a_deleted_task_no_longer_blocks_deleting_its_category(app, client, user_id, category_id):
    """งานที่ถูกลบไม่ควรนับเป็น "ยังมีงานอยู่" — ผู้ใช้มองว่ามันหายไปแล้ว"""
    with app.app_context():
        todo_id = _make_todo(user_id, category_id=category_id)
    client.post(f"/delete/{todo_id}")
    client.post(f"/categories/delete/{category_id}")

    with app.app_context():
        assert db.session.get(Category, category_id) is None


# --- purge: จุดเดียวที่ลบจริง ---


def test_purge_leaves_recent_deletions_alone(app, user_id):
    with app.app_context():
        todo_id = _make_todo(user_id)
        db.session.get(Todo, todo_id).soft_delete()
        db.session.commit()

        result = purge_expired()

        assert result.todos == 0
        assert db.session.get(Todo, todo_id, execution_options=INCLUDE_DELETED) is not None


def test_purge_removes_rows_past_the_retention_window(app, user_id):
    with app.app_context():
        todo_id = _make_todo(user_id)
        db.session.get(Todo, todo_id).soft_delete()
        db.session.commit()
        _age(Todo, todo_id, PURGE_AFTER_DAYS + 1)

        result = purge_expired()

        assert result.todos == 1
        assert db.session.get(Todo, todo_id, execution_options=INCLUDE_DELETED) is None


def test_purge_never_touches_live_rows(app, user_id):
    """เงื่อนไขต้องเป็น "ถูกลบแล้วและเก่าพอ" ไม่ใช่ "เก่าพอ" อย่างเดียว"""
    with app.app_context():
        todo_id = _make_todo(user_id)
        purge_expired(days=0)
        assert db.session.get(Todo, todo_id) is not None


def test_purging_a_user_scrubs_pii_but_keeps_the_row(app, user_id):
    """แถวต้องเหลือไว้เป็น tombstone ให้ audit อ้าง actor_id ได้ (ADR 0014)"""
    with app.app_context():
        user = db.session.get(User, user_id)
        user.first_name = "สยาม"
        user.last_name = "ศรีผัว"
        user.soft_delete()
        db.session.commit()
        _age(User, user_id, PURGE_AFTER_DAYS + 1)

        purge_expired()

        tomb = db.session.get(User, user_id, execution_options=INCLUDE_DELETED)
        assert tomb is not None, "แถว user ต้องไม่ถูกลบทิ้ง"
        assert tomb.username == f"#deleted-{user_id}"
        assert tomb.first_name is None
        assert tomb.last_name is None
        assert tomb.purged_at is not None


def test_purging_a_user_is_not_repeated(app, user_id):
    with app.app_context():
        db.session.get(User, user_id).soft_delete()
        db.session.commit()
        _age(User, user_id, PURGE_AFTER_DAYS + 1)

        assert purge_expired().users_purged == 1
        assert purge_expired().users_purged == 0, "ผู้ใช้ที่ถูกล้างแล้วต้องไม่ถูกนับซ้ำ"


# --- credential (ชั้น C1) ---


def test_disabled_password_never_matches(app, user_id):
    from tests.conftest import PASSWORD

    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.check_password(PASSWORD) is True
        user.disable_password()
        assert user.check_password(PASSWORD) is False
        assert user.check_password("") is False


def test_purge_disables_the_password(app, user_id):
    from tests.conftest import PASSWORD

    with app.app_context():
        db.session.get(User, user_id).soft_delete()
        db.session.commit()
        _age(User, user_id, PURGE_AFTER_DAYS + 1)
        purge_expired()

        tomb = db.session.get(User, user_id, execution_options=INCLUDE_DELETED)
        assert tomb.check_password(PASSWORD) is False


# --- ผู้ใช้ที่ถูกลบต้องเข้าระบบไม่ได้ ---


def test_a_soft_deleted_user_cannot_log_in(app, anon_client, user_id):
    from tests.conftest import PASSWORD

    with app.app_context():
        db.session.get(User, user_id).soft_delete()
        db.session.commit()

    resp = anon_client.post("/login", data={"username": "tester", "password": PASSWORD})
    # 401 = รหัสถูกแต่หาบัญชีไม่เจอ (ดูตารางสถานะใน CLAUDE.md) ที่ห้ามได้คือ 302
    assert resp.status_code == 401, "บัญชีที่ถูกลบต้องเข้าระบบไม่ได้"


@pytest.mark.parametrize("path", ["/", "/categories", "/settings"])
def test_pages_still_render_after_everything_is_deleted(app, client, user_id, path):
    """หน้าเว็บต้องไม่พังเมื่อทุกอย่างถูกซ่อน — เคยพลาดกันตรงที่ template
    สมมติว่า relationship มีค่าเสมอ"""
    with app.app_context():
        _make_todo(user_id)
        for todo in db.session.get(User, user_id).todos:
            todo.soft_delete()
        db.session.commit()

    assert client.get(path).status_code == 200


# --- คำสั่ง CLI ---


def test_delete_user_command_soft_deletes_everything(app, user_id, category_id):
    """`flask delete-user` ต้องซ่อนทั้งชุด แต่ยังกู้คืนได้ภายในระยะที่กำหนด"""
    with app.app_context():
        todo_id = _make_todo(user_id, category_id=category_id)

    result = app.test_cli_runner().invoke(args=["delete-user", "tester", "--yes"])
    assert result.exit_code == 0, result.output
    assert "soft delete" in result.output

    with app.app_context():
        for model, row_id in ((User, user_id), (Category, category_id), (Todo, todo_id)):
            assert db.session.get(model, row_id) is None, f"{model.__name__} ยังโผล่อยู่"
            kept = db.session.get(model, row_id, execution_options=INCLUDE_DELETED)
            assert kept is not None, f"{model.__name__} ถูกลบแถวจริง — ต้องเป็น soft delete"
            assert kept.deleted_at is not None


def test_delete_user_command_disables_the_password(app, user_id):
    from tests.conftest import PASSWORD

    app.test_cli_runner().invoke(args=["delete-user", "tester", "--yes"])

    with app.app_context():
        user = db.session.get(User, user_id, execution_options=INCLUDE_DELETED)
        assert user.check_password(PASSWORD) is False, "credential ต้องถูกล้างทันที ไม่รอ grace"


def test_purge_command_reports_what_it_removed(app, user_id):
    with app.app_context():
        todo_id = _make_todo(user_id)
        db.session.get(Todo, todo_id).soft_delete()
        db.session.commit()
        _age(Todo, todo_id, PURGE_AFTER_DAYS + 1)

    result = app.test_cli_runner().invoke(args=["purge-expired"])
    assert result.exit_code == 0, result.output
    assert "Purged 1 tasks" in result.output

    with app.app_context():
        assert db.session.get(Todo, todo_id, execution_options=INCLUDE_DELETED) is None


def test_purge_command_dry_run_changes_nothing(app, user_id):
    """--dry-run ต้องบอกได้ว่าจะกระทบอะไร โดยไม่ลบอะไรเลยจริง ๆ"""
    with app.app_context():
        todo_id = _make_todo(user_id)
        db.session.get(Todo, todo_id).soft_delete()
        db.session.commit()
        _age(Todo, todo_id, PURGE_AFTER_DAYS + 1)

    result = app.test_cli_runner().invoke(args=["purge-expired", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "[dry run]" in result.output
    assert "would purge 1 tasks" in result.output

    with app.app_context():
        still_there = db.session.get(Todo, todo_id, execution_options=INCLUDE_DELETED)
        assert still_there is not None, "dry run ต้องไม่ลบอะไรเลย"


def test_purge_command_honours_a_custom_window(app, user_id):
    with app.app_context():
        todo_id = _make_todo(user_id)
        db.session.get(Todo, todo_id).soft_delete()
        db.session.commit()
        _age(Todo, todo_id, 3)

    assert "Purged 0 tasks" in app.test_cli_runner().invoke(args=["purge-expired"]).output
    result = app.test_cli_runner().invoke(args=["purge-expired", "--days", "2"])
    assert "Purged 1 tasks" in result.output


def test_purge_removes_expired_categories(app, user_id, category_id):
    with app.app_context():
        db.session.get(Category, category_id).soft_delete()
        db.session.commit()
        _age(Category, category_id, PURGE_AFTER_DAYS + 1)

        result = purge_expired()

        assert result.categories == 1
        assert result.total == 1
        assert db.session.get(Category, category_id, execution_options=INCLUDE_DELETED) is None


def test_is_deleted_reflects_the_flag(app, user_id):
    with app.app_context():
        todo = db.session.get(Todo, _make_todo(user_id))
        assert todo.is_deleted is False
        todo.soft_delete()
        assert todo.is_deleted is True
