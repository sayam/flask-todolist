"""พฤติกรรมของ service layer ที่เรียกตรง ๆ (Phase 3)

เทสต์ผ่าน HTTP ครอบทางที่ผู้ใช้เดินจริงอยู่แล้ว ไฟล์นี้เจาะสิ่งที่ HTML
ส่งมาไม่ได้แต่ API ส่งได้ (เช่น PATCH ที่ส่งมาบางฟิลด์ หรือชื่อฟิลด์มั่ว)
และกติกาที่ต้องจริงไม่ว่าจะเรียกจากทางไหน (เจ้าของข้อมูล, การไม่เขียนครึ่ง ๆ)

**app context อยู่ที่ fixture ตัวเทสต์ห้ามเปิดซ้อน** — Flask-SQLAlchemy ผูก
session ไว้กับ app context ดังนั้น `with app.app_context():` ซ้อนเข้าไปอีกชั้น
จะได้ session **คนละตัว** กับที่ `owner` ผูกอยู่ การแก้ค่าบน object นั้นแล้ว
commit จึงไม่ถูกเขียนลงฐานข้อมูลเลย ทั้งที่ค่าในหน่วยความจำเปลี่ยนไปแล้ว
(เทสต์ที่ assert แต่ค่าในหน่วยความจำจะเขียวทั้งที่ไม่มีอะไรถูกบันทึก — เคยเป็น
มาแล้วในไฟล์นี้)

**การพิสูจน์ว่า "ลงฐานข้อมูลจริง" ต้องใช้ `db.session.remove()`** ไม่ใช่การเปิด
context ใหม่แล้วอ่านซ้ำ เพราะ sqlite แบบ `:memory:` ใช้ connection เดียวร่วมกัน
(StaticPool) session ใหม่จึงยังอยู่ใน transaction เดิมและ **มองเห็นค่าที่ยังไม่
commit** — เทสต์แบบนั้นเขียวต่อให้ถอด `db.session.commit()` ออกจาก service
ส่วน `remove()` ปิด session ทิ้งพร้อม rollback ของที่ยังไม่ commit จึงแยกออก
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
    """เจ้าของข้อมูล ตั้ง timezone เป็นกรุงเทพเพื่อให้เห็นผลการแปลงเวลาชัด ๆ

    context ถูกเปิดค้างไว้ตลอดเทสต์โดยตั้งใจ (ดูหัวข้อบนสุดของไฟล์)
    """
    with app.app_context():
        user = User(username="owner", timezone_name="Asia/Bangkok")
        user.set_password("password123")
        db.session.add(user)
        db.session.commit()
        yield user


@pytest.fixture
def stranger(app, owner):
    """คนอื่นที่ใช้ session เดียวกับ `owner` — ต้องมาหลัง owner เพื่อไม่เปิด context ซ้อน"""
    user = User(username="stranger")
    user.set_password("password123")
    db.session.add(user)
    db.session.commit()
    return user


# ---------------------------------------------------------------- งาน


def test_create_todo_stores_the_local_time_as_utc(owner):
    """เวลาที่ส่งเข้า service เป็นเวลาท้องถิ่นของเจ้าของงาน ไม่ใช่ UTC"""
    todo = todos_service.create_todo(owner, title="ประชุม", due_date=datetime(2026, 9, 1, 16, 0))
    # กรุงเทพ +07:00 → 16:00 ท้องถิ่นคือ 09:00 UTC
    assert todo.due_date == datetime(2026, 9, 1, 9, 0)
    assert todo.due_local == datetime(2026, 9, 1, 16, 0)


def test_create_todo_rejects_an_empty_title(owner):
    with pytest.raises(ValidationError) as raised:
        todos_service.create_todo(owner, title="   ")
    assert raised.value.code == "title_required"
    assert raised.value.field == "title"


def test_update_todo_only_touches_the_fields_it_was_given(owner):
    """PATCH ที่ส่งมาแค่ฟิลด์เดียวต้องไม่ล้างฟิลด์อื่นทิ้ง"""
    todo = todos_service.create_todo(owner, title="เดิม", due_date=datetime(2026, 9, 1, 16, 0))
    todos_service.update_todo(owner, todo.id, {"title": "ใหม่"})
    assert todo.title == "ใหม่"
    assert todo.due_date == datetime(2026, 9, 1, 9, 0), "กำหนดส่งหายทั้งที่ไม่ได้ส่งมาแก้"


def test_update_todo_can_clear_a_date_by_sending_null(owner):
    """`None` ที่ส่งมาจริงแปลว่า "ล้างค่า" — ต่างจากการไม่ส่งฟิลด์นั้นมาเลย"""
    todo = todos_service.create_todo(owner, title="เดิม", due_date=datetime(2026, 9, 1, 16, 0))
    todos_service.update_todo(owner, todo.id, {"due_date": None})
    assert todo.due_date is None


def test_update_todo_refuses_unknown_fields(owner):
    """ชื่อฟิลด์ที่ไม่รู้จักต้องดัง ไม่ใช่ถูกเมินเงียบ ๆ

    client ที่พิมพ์ `done` แทน `is_done` ต้องรู้ตัวทันที ไม่ใช่คิดว่าบันทึกแล้ว
    """
    todo = todos_service.create_todo(owner, title="งาน")
    with pytest.raises(ValidationError) as raised:
        todos_service.update_todo(owner, todo.id, {"done": True})
    assert raised.value.code == "unknown_field"
    assert todo.is_done is False


def test_update_todo_rejects_a_category_of_someone_else(owner, stranger):
    theirs = categories_service.create_category(stranger, "ของคนอื่น")
    todo = todos_service.create_todo(owner, title="งาน")
    with pytest.raises(NotFoundError):
        todos_service.update_todo(owner, todo.id, {"category_id": theirs.id})
    assert todo.category_id is None


def test_get_todo_hides_other_peoples_rows(owner, stranger):
    """ของคนอื่นต้องตอบเหมือนไม่มีอยู่ (ADR 0004) ไม่ใช่ "ห้ามเข้า" """
    theirs = todos_service.create_todo(stranger, title="ความลับ")
    with pytest.raises(NotFoundError) as raised:
        todos_service.get_todo(owner, theirs.id)
    assert raised.value.code == "todo_not_found"


def test_list_todos_rejects_filtering_by_someone_elses_category(owner, stranger):
    """ตัวกรองที่ยอมให้ชี้ไปหมวดของคนอื่นคือช่องบอกว่าหมวดนั้นมีอยู่จริง"""
    theirs = categories_service.create_category(stranger, "ของคนอื่น")
    with pytest.raises(NotFoundError):
        todos_service.list_todos(owner, FilterSpec(category=str(theirs.id)))


def test_clear_completed_counts_only_the_callers_finished_tasks(owner, stranger):
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


def test_create_category_rejects_a_duplicate_name(owner):
    categories_service.create_category(owner, "งานบ้าน")
    with pytest.raises(ConflictError) as raised:
        categories_service.create_category(owner, "งานบ้าน")
    assert raised.value.code == "category_exists"


def test_the_same_name_is_free_for_a_different_user(owner, stranger):
    """ชื่อหมวดห้ามซ้ำเฉพาะภายในของคนเดียวกัน"""
    categories_service.create_category(owner, "งานบ้าน")
    assert categories_service.create_category(stranger, "งานบ้าน").id is not None


def test_renaming_a_category_to_its_own_name_is_allowed(owner):
    category = categories_service.create_category(owner, "งานบ้าน")
    assert categories_service.rename_category(owner, category.id, "งานบ้าน").name == "งานบ้าน"


def test_a_category_with_finished_tasks_still_cannot_be_deleted(owner):
    """งานที่ทำเสร็จแล้วก็ยังนับ เพราะมันยังโผล่ในตัวกรอง "เสร็จแล้ว" """
    category = categories_service.create_category(owner, "งานบ้าน")
    todo = todos_service.create_todo(owner, title="ล้างจาน", category_id=category.id)
    todos_service.toggle_todo(owner, todo.id)

    with pytest.raises(ConflictError) as raised:
        categories_service.delete_category(owner, category.id)
    assert raised.value.code == "category_in_use"
    assert category.deleted_at is None


def test_a_deleted_task_no_longer_blocks_deleting_its_category(owner):
    category = categories_service.create_category(owner, "งานบ้าน")
    todo = todos_service.create_todo(owner, title="ล้างจาน", category_id=category.id)
    todos_service.delete_todo(owner, todo.id)

    categories_service.delete_category(owner, category.id)
    assert category.deleted_at is not None


# ---------------------------------------------------------------- ตั้งค่า


def test_save_preferences_writes_nothing_when_one_value_is_invalid(owner):
    """ค่าที่ผ่านตัวแรกต้องไม่ถูกบันทึกถ้าค่าถัดไปไม่ผ่าน — ไม่เหลือสถานะครึ่ง ๆ"""
    user_id = owner.id
    with pytest.raises(ValidationError) as raised:
        settings_service.save_preferences(
            owner,
            locale="th",
            theme="system",
            mode="dark",
            timezone_name="Mars/Olympus_Mons",
        )
    assert raised.value.code == "timezone_invalid"
    db.session.remove()
    stored = db.session.get(User, user_id)
    assert stored.locale is None
    assert stored.mode is None


def test_save_profile_stores_blank_names_as_null(owner):
    """ช่องว่างต้องเป็น NULL ไม่ใช่สตริงว่าง ไม่งั้น full_name จะมีช่องว่างเกิน"""
    user_id = owner.id
    # ตั้งค่าเดิมไว้ก่อนโดยไม่ผ่าน service เพื่อให้ "ล้างเป็น NULL" เป็นความเปลี่ยนแปลงจริง
    owner.first_name = "สมชาย"
    owner.last_name = "ใจดี"
    db.session.commit()

    settings_service.save_profile(owner, "  ", "  ")
    assert owner.full_name == ""
    db.session.remove()
    stored = db.session.get(User, user_id)
    assert stored.first_name is None
    assert stored.last_name is None


def test_service_writes_land_in_the_database(owner):
    """service commit เอง — ผู้เรียกไม่ต้องรู้เรื่อง transaction

    `remove()` ปิด session ทิ้งพร้อม rollback ของที่ยังไม่ commit — ของที่ยัง
    อ่านได้หลังจากนั้นคือของที่ลงฐานข้อมูลไปแล้วจริง ๆ เท่านั้น
    """
    category_id = categories_service.create_category(owner, "งานบ้าน").id
    todos_service.create_todo(owner, title="ล้างจาน", category_id=category_id)
    db.session.remove()
    assert db.session.get(Category, category_id) is not None
    assert db.session.scalars(db.select(Todo)).one().title == "ล้างจาน"
