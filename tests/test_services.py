"""พฤติกรรมของ service layer ที่เรียกตรง ๆ (Phase 3)

เทสต์ผ่าน HTTP ครอบทางที่ผู้ใช้เดินจริงอยู่แล้ว ไฟล์นี้เจาะสิ่งที่ HTML
ส่งมาไม่ได้แต่ API ส่งได้ (เช่น PATCH ที่ส่งมาบางฟิลด์ หรือชื่อฟิลด์มั่ว)
และกติกาที่ต้องจริงไม่ว่าจะเรียกจากทางไหน (เจ้าของข้อมูล, การไม่เขียนครึ่ง ๆ)
"""

from datetime import datetime

import pytest

from app import db
from app.filters import FilterSpec
from app.models import Category, Todo, User
from app.services import ConflictError, NotFoundError, ValidationError
from app.services import categories as categories_service
from app.services import settings as settings_service
from app.services import todos as todos_service


@pytest.fixture
def owner(app):
    """เจ้าของข้อมูล ตั้ง timezone เป็นกรุงเทพเพื่อให้เห็นผลการแปลงเวลาชัด ๆ"""
    with app.app_context():
        user = User(username="owner", timezone_name="Asia/Bangkok")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
        yield user


@pytest.fixture
def stranger(app):
    with app.app_context():
        user = User(username="stranger")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
        yield user


# ---------------------------------------------------------------- งาน


def test_create_todo_stores_the_local_time_as_utc(app, owner):
    """เวลาที่ส่งเข้า service เป็นเวลาท้องถิ่นของเจ้าของงาน ไม่ใช่ UTC"""
    with app.app_context():
        todo = todos_service.create_todo(owner, title="ประชุม", due_date=datetime(2026, 9, 1, 16, 0))
        # กรุงเทพ +07:00 → 16:00 ท้องถิ่นคือ 09:00 UTC
        assert todo.due_date == datetime(2026, 9, 1, 9, 0)
        assert todo.due_local == datetime(2026, 9, 1, 16, 0)


def test_create_todo_rejects_an_empty_title(app, owner):
    with app.app_context():
        with pytest.raises(ValidationError) as raised:
            todos_service.create_todo(owner, title="   ")
        assert raised.value.code == "title_required"
        assert raised.value.field == "title"


def test_update_todo_only_touches_the_fields_it_was_given(app, owner):
    """PATCH ที่ส่งมาแค่ฟิลด์เดียวต้องไม่ล้างฟิลด์อื่นทิ้ง"""
    with app.app_context():
        todo = todos_service.create_todo(owner, title="เดิม", due_date=datetime(2026, 9, 1, 16, 0))
        todos_service.update_todo(owner, todo.id, {"title": "ใหม่"})
        assert todo.title == "ใหม่"
        assert todo.due_date == datetime(2026, 9, 1, 9, 0), "กำหนดส่งหายทั้งที่ไม่ได้ส่งมาแก้"


def test_update_todo_can_clear_a_date_by_sending_null(app, owner):
    """`None` ที่ส่งมาจริงแปลว่า "ล้างค่า" — ต่างจากการไม่ส่งฟิลด์นั้นมาเลย"""
    with app.app_context():
        todo = todos_service.create_todo(owner, title="เดิม", due_date=datetime(2026, 9, 1, 16, 0))
        todos_service.update_todo(owner, todo.id, {"due_date": None})
        assert todo.due_date is None


def test_update_todo_refuses_unknown_fields(app, owner):
    """ชื่อฟิลด์ที่ไม่รู้จักต้องดัง ไม่ใช่ถูกเมินเงียบ ๆ

    client ที่พิมพ์ `done` แทน `is_done` ต้องรู้ตัวทันที ไม่ใช่คิดว่าบันทึกแล้ว
    """
    with app.app_context():
        todo = todos_service.create_todo(owner, title="งาน")
        with pytest.raises(ValidationError) as raised:
            todos_service.update_todo(owner, todo.id, {"done": True})
        assert raised.value.code == "unknown_field"
        assert todo.is_done is False


def test_update_todo_rejects_a_category_of_someone_else(app, owner, stranger):
    with app.app_context():
        theirs = categories_service.create_category(stranger, "ของคนอื่น")
        todo = todos_service.create_todo(owner, title="งาน")
        with pytest.raises(NotFoundError):
            todos_service.update_todo(owner, todo.id, {"category_id": theirs.id})
        assert todo.category_id is None


def test_get_todo_hides_other_peoples_rows(app, owner, stranger):
    """ของคนอื่นต้องตอบเหมือนไม่มีอยู่ (ADR 0004) ไม่ใช่ "ห้ามเข้า" """
    with app.app_context():
        theirs = todos_service.create_todo(stranger, title="ความลับ")
        with pytest.raises(NotFoundError) as raised:
            todos_service.get_todo(owner, theirs.id)
        assert raised.value.code == "todo_not_found"


def test_list_todos_rejects_filtering_by_someone_elses_category(app, owner, stranger):
    """ตัวกรองที่ยอมให้ชี้ไปหมวดของคนอื่นคือช่องบอกว่าหมวดนั้นมีอยู่จริง"""
    with app.app_context():
        theirs = categories_service.create_category(stranger, "ของคนอื่น")
        with pytest.raises(NotFoundError):
            todos_service.list_todos(owner, FilterSpec(category=str(theirs.id)))


def test_clear_completed_counts_only_the_callers_finished_tasks(app, owner, stranger):
    with app.app_context():
        done = todos_service.create_todo(owner, title="เสร็จแล้ว")
        todos_service.toggle_todo(owner, done.id)
        todos_service.create_todo(owner, title="ยังไม่เสร็จ")
        theirs = todos_service.create_todo(stranger, title="ของคนอื่นที่เสร็จแล้ว")
        todos_service.toggle_todo(stranger, theirs.id)

        assert todos_service.clear_completed(owner) == 1
        assert [t.title for t in todos_service.list_todos(owner, FilterSpec())] == ["ยังไม่เสร็จ"]
        assert [t.title for t in todos_service.list_todos(stranger, FilterSpec())] == [
            "ของคนอื่นที่เสร็จแล้ว"
        ]


# ---------------------------------------------------------------- หมวด


def test_create_category_rejects_a_duplicate_name(app, owner):
    with app.app_context():
        categories_service.create_category(owner, "งานบ้าน")
        with pytest.raises(ConflictError) as raised:
            categories_service.create_category(owner, "งานบ้าน")
        assert raised.value.code == "category_exists"


def test_the_same_name_is_free_for_a_different_user(app, owner, stranger):
    """ชื่อหมวดห้ามซ้ำเฉพาะภายในของคนเดียวกัน"""
    with app.app_context():
        categories_service.create_category(owner, "งานบ้าน")
        assert categories_service.create_category(stranger, "งานบ้าน").id is not None


def test_renaming_a_category_to_its_own_name_is_allowed(app, owner):
    with app.app_context():
        category = categories_service.create_category(owner, "งานบ้าน")
        assert categories_service.rename_category(owner, category.id, "งานบ้าน").name == "งานบ้าน"


def test_a_category_with_finished_tasks_still_cannot_be_deleted(app, owner):
    """งานที่ทำเสร็จแล้วก็ยังนับ เพราะมันยังโผล่ในตัวกรอง "เสร็จแล้ว" """
    with app.app_context():
        category = categories_service.create_category(owner, "งานบ้าน")
        todo = todos_service.create_todo(owner, title="ล้างจาน", category_id=category.id)
        todos_service.toggle_todo(owner, todo.id)

        with pytest.raises(ConflictError) as raised:
            categories_service.delete_category(owner, category.id)
        assert raised.value.code == "category_in_use"
        assert category.deleted_at is None


def test_a_deleted_task_no_longer_blocks_deleting_its_category(app, owner):
    with app.app_context():
        category = categories_service.create_category(owner, "งานบ้าน")
        todo = todos_service.create_todo(owner, title="ล้างจาน", category_id=category.id)
        todos_service.delete_todo(owner, todo.id)

        categories_service.delete_category(owner, category.id)
        assert category.deleted_at is not None


# ---------------------------------------------------------------- ตั้งค่า


def test_save_preferences_writes_nothing_when_one_value_is_invalid(app, owner):
    """ค่าที่ผ่านตัวแรกต้องไม่ถูกบันทึกถ้าค่าถัดไปไม่ผ่าน — ไม่เหลือสถานะครึ่ง ๆ"""
    with app.app_context():
        with pytest.raises(ValidationError) as raised:
            settings_service.save_preferences(
                owner,
                locale="th",
                theme="system",
                mode="dark",
                timezone_name="Mars/Olympus_Mons",
            )
        assert raised.value.code == "timezone_invalid"
        assert owner.locale is None
        assert owner.mode is None


def test_save_profile_stores_blank_names_as_null(app, owner):
    """ช่องว่างต้องเป็น NULL ไม่ใช่สตริงว่าง ไม่งั้น full_name จะมีช่องว่างเกิน"""
    with app.app_context():
        settings_service.save_profile(owner, "  ", "  ")
        assert owner.first_name is None
        assert owner.last_name is None
        assert owner.full_name == ""


def test_service_writes_land_in_the_database(app, owner):
    """service commit เอง — ผู้เรียกไม่ต้องรู้เรื่อง transaction"""
    with app.app_context():
        category_id = categories_service.create_category(owner, "งานบ้าน").id
        todos_service.create_todo(owner, title="ล้างจาน", category_id=category_id)
    with app.app_context():
        assert db.session.get(Category, category_id) is not None
        assert db.session.scalars(db.select(Todo)).one().title == "ล้างจาน"
