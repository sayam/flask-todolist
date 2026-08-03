"""งาน (todo) — อ่านตามตัวกรอง สร้าง แก้ ติ๊กเสร็จ และลบ

**เวลาที่รับเข้า/ส่งออกของ service นี้เป็น "เวลาท้องถิ่นของเจ้าของงาน" แบบ naive**
การแปลงเป็น UTC ก่อนเก็บเกิดขึ้นในนี้ที่เดียว ผู้เรียกจึงไม่ต้องรู้เรื่อง tz เลย
(ฟอร์ม HTML กับ JSON ของ API ส่งเวลาท้องถิ่นมาเหมือนกัน — ดู `app/tz.py`)

การแก้ค่าใช้ **dict ของเฉพาะฟิลด์ที่ผู้เรียกส่งมา** ไม่ใช่ argument ตัวละฟิลด์
เพราะ `None` ของ `due_date` แปลว่า "ล้างกำหนดส่ง" ซึ่งต้องแยกให้ออกจาก
"ไม่ได้ส่งฟิลด์นี้มา" — PATCH ของ API ต้องการความต่างนี้ ส่วนฟอร์ม HTML
ส่งครบทุกฟิลด์อยู่แล้วจึงใช้ทางเดียวกันได้โดยไม่ต้องมีโค้ดสาขาที่สอง
"""

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from flask_babel import gettext as _
from sqlalchemy import select

from app import db, tz
from app.filters import CATEGORY_NONE, FilterSpec, apply_when
from app.models import Todo, User
from app.services.categories import get_category
from app.services.errors import NotFoundError, ValidationError
from app.services.lookup import by_id

# ฟิลด์ที่แก้ผ่าน `update_todo()` ได้ — ค่าที่ไม่อยู่ในนี้ถูกปฏิเสธ ไม่ใช่ถูกเมิน
# (การเมินเงียบ ๆ ทำให้ client ที่พิมพ์ชื่อฟิลด์ผิดคิดว่าบันทึกสำเร็จ)
EDITABLE_FIELDS = frozenset({"title", "category_id", "start_date", "due_date", "is_done"})

# เรียง: งานที่มีกำหนดส่งขึ้นก่อน (ใกล้ครบกำหนดสุดก่อน) แล้วค่อยงานไม่มีกำหนด
# เรียงตาม created_at ล่าสุดก่อน — `is_(None)` ให้ False(0) มาก่อน True(1)
ORDER_BY = (Todo.due_date.is_(None), Todo.due_date.asc(), Todo.created_at.desc())


def list_todos(user: User, spec: FilterSpec) -> list[Todo]:
    """งานของผู้ใช้ตามตัวกรองที่ normalise มาแล้ว

    หมวดที่ระบุมาต้องเป็นของผู้ใช้คนนี้ ไม่งั้น `NotFoundError` —
    ตัวกรองที่ยอมให้ชี้ไปหมวดของคนอื่นคือช่องบอกว่าหมวดนั้นมีจริงหรือไม่
    """
    statement = select(Todo).where(Todo.user_id == user.id)
    if spec.status == "active":
        statement = statement.where(Todo.is_done.is_(False))
    elif spec.status == "completed":
        statement = statement.where(Todo.is_done.is_(True))

    if spec.category == CATEGORY_NONE:
        statement = statement.where(Todo.category_id.is_(None))
    elif spec.category:
        category = get_category(user, int(spec.category))
        statement = statement.where(Todo.category_id == category.id)

    statement = apply_when(statement, Todo, spec, user.timezone_name)
    return list(db.session.scalars(statement.order_by(*ORDER_BY)))


def get_todo(user: User, todo_id: int) -> Todo:
    """งานของผู้ใช้คนนี้เท่านั้น — ของคนอื่นตอบเหมือนไม่มีอยู่ (ADR 0004)"""
    todo = by_id(Todo, todo_id)
    if todo is None or todo.user_id != user.id:
        raise NotFoundError(_("Task not found"), code="todo_not_found")
    return todo


def _clean_title(raw: Any, message: str) -> str:
    title = str(raw or "").strip()
    if not title:
        raise ValidationError(message, code="title_required", field="title")
    return title


def _resolve_category_id(user: User, raw: Any) -> int | None:
    """ยืนยันว่าหมวดที่อ้างถึงเป็นของผู้ใช้จริง — ค่าว่างแปลว่า "ไม่มีหมวด" """
    if raw in (None, "", CATEGORY_NONE):
        return None
    try:
        category_id = int(raw)
    except (TypeError, ValueError) as bad:
        raise ValidationError(
            _("Invalid category"), code="category_invalid", field="category_id"
        ) from bad
    return get_category(user, category_id).id


def _to_utc(user: User, value: datetime | None) -> datetime | None:
    return tz.to_utc(value, user.timezone_name)


def create_todo(
    user: User,
    *,
    title: str | None,
    category_id: Any = None,
    start_date: datetime | None = None,
    due_date: datetime | None = None,
) -> Todo:
    """สร้างงานใหม่ — วันที่ที่ส่งมาเป็นเวลาท้องถิ่นของผู้ใช้"""
    todo = Todo(
        title=_clean_title(title, _("Please enter a task name")),
        user_id=user.id,
        category_id=_resolve_category_id(user, category_id),
        start_date=_to_utc(user, start_date),
        due_date=_to_utc(user, due_date),
    )
    db.session.add(todo)
    db.session.commit()
    return todo


def update_todo(user: User, todo_id: int, changes: Mapping[str, Any]) -> Todo:
    """แก้เฉพาะฟิลด์ที่ส่งมาใน `changes` (ดู docstring ของโมดูลว่าทำไมเป็น dict)"""
    unknown = sorted(set(changes) - EDITABLE_FIELDS)
    if unknown:
        raise ValidationError(
            _("Unknown field: %(name)s", name=unknown[0]),
            code="unknown_field",
            field=unknown[0],
        )

    todo = get_todo(user, todo_id)
    if "title" in changes:
        todo.title = _clean_title(changes["title"], _("Task name cannot be empty"))
    if "category_id" in changes:
        todo.category_id = _resolve_category_id(user, changes["category_id"])
    if "start_date" in changes:
        todo.start_date = _to_utc(user, changes["start_date"])
    if "due_date" in changes:
        todo.due_date = _to_utc(user, changes["due_date"])
    if "is_done" in changes:
        todo.is_done = bool(changes["is_done"])
    db.session.commit()
    return todo


def toggle_todo(user: User, todo_id: int) -> Todo:
    """สลับสถานะเสร็จ/ไม่เสร็จ — ปุ่มติ๊กในลิสต์ใช้ตัวนี้"""
    todo = get_todo(user, todo_id)
    todo.is_done = not todo.is_done
    db.session.commit()
    return todo


def delete_todo(user: User, todo_id: int) -> Todo:
    """ซ่อนงาน (soft delete) — ของจริงถูกล้างโดย purge job เมื่อพ้นระยะ"""
    todo = get_todo(user, todo_id)
    todo.soft_delete()
    db.session.commit()
    return todo


def clear_completed(user: User) -> int:
    """ซ่อนงานที่ทำเสร็จแล้วทั้งหมด คืนจำนวนที่ถูกซ่อน

    ไล่ทีละแถวผ่าน ORM ไม่ใช้ bulk delete — งานของคนเดียวมีไม่มาก และ event
    `after_flush` ต้องเห็นทุกแถวที่ถูกแตะ ไม่งั้นการลบชุดนี้จะไม่ลง audit เลย
    """
    statement = select(Todo).where(Todo.user_id == user.id, Todo.is_done.is_(True))
    cleared = list(db.session.scalars(statement))
    for todo in cleared:
        todo.soft_delete()
    db.session.commit()
    return len(cleared)
