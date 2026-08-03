"""หมวดของงาน — สร้าง เปลี่ยนชื่อ ลบ

กติกาที่ย้ายมาจาก route ตรง ๆ ไม่ได้เปลี่ยนความหมาย:

* ชื่อหมวดห้ามซ้ำ **ภายในของคนเดียวกัน** (ข้าม user ซ้ำได้ — มี unique constraint คุมอีกชั้น)
* **ลบได้เฉพาะหมวดที่ไม่มีงานเลย** งานที่ทำเสร็จแล้วก็ยังนับ เพราะมันยังโผล่
  ในตัวกรอง "เสร็จแล้ว" — ปุ่มบนหน้าเว็บถูก disable ไว้ด้วย แต่การกันจริงอยู่ที่นี่

query เขียนแบบ SQLAlchemy 2.0 (`select()`) ไม่ใช่ `Model.query` แบบเก่า —
ตัวกรอง soft delete ยังถูกเติมให้เองทั้งสองแบบ (ทดสอบแล้วรวมถึง `func.count()`)
"""

from flask_babel import gettext as _
from flask_babel import ngettext
from sqlalchemy import func, select

from app import db
from app.models import Category, Todo, User
from app.services.errors import ConflictError, NotFoundError, ValidationError


def list_categories(user: User) -> list[Category]:
    """หมวดทั้งหมดของผู้ใช้ เรียงตามชื่อ"""
    statement = select(Category).where(Category.user_id == user.id).order_by(Category.name)
    return list(db.session.scalars(statement))


def get_category(user: User, category_id: int) -> Category:
    """หมวดของผู้ใช้คนนี้เท่านั้น — ของคนอื่นตอบเหมือนไม่มีอยู่ (ADR 0004)"""
    category = db.session.get(Category, category_id)
    if category is None or category.user_id != user.id:
        raise NotFoundError(_("Category not found"), code="category_not_found")
    return category


def task_count(category: Category) -> int:
    """จำนวนงานที่ยังอยู่ในหมวดนี้ — งานที่ถูกลบไปแล้วไม่นับ"""
    statement = select(func.count(Todo.id)).where(Todo.category_id == category.id)
    return int(db.session.scalar(statement) or 0)


def _clean_name(raw: str | None, message: str) -> str:
    name = (raw or "").strip()
    if not name:
        raise ValidationError(message, code="name_required", field="name")
    return name


def _reject_duplicate(user: User, name: str, exclude_id: int | None = None) -> None:
    statement = select(Category.id).where(Category.user_id == user.id, Category.name == name)
    if exclude_id is not None:
        statement = statement.where(Category.id != exclude_id)
    if db.session.scalars(statement).first() is not None:
        raise ConflictError(
            _("Category “%(name)s” already exists", name=name),
            code="category_exists",
            field="name",
        )


def create_category(user: User, name: str | None) -> Category:
    """สร้างหมวดใหม่ให้ผู้ใช้"""
    cleaned = _clean_name(name, _("Please enter a category name"))
    _reject_duplicate(user, cleaned)
    category = Category(name=cleaned, user_id=user.id)
    db.session.add(category)
    db.session.commit()
    return category


def rename_category(user: User, category_id: int, name: str | None) -> Category:
    """เปลี่ยนชื่อหมวด — ชื่อเดิมของตัวเองไม่นับว่าซ้ำ"""
    category = get_category(user, category_id)
    cleaned = _clean_name(name, _("Category name cannot be empty"))
    _reject_duplicate(user, cleaned, exclude_id=category.id)
    category.name = cleaned
    db.session.commit()
    return category


def delete_category(user: User, category_id: int) -> Category:
    """ซ่อนหมวด (soft delete) — ปฏิเสธถ้ายังมีงานอยู่ในหมวดนั้น

    ข้อความบอกจำนวนงานที่เหลือด้วย เพราะ "ลบไม่ได้" เฉย ๆ ไม่ได้บอกว่าต้องไปทำอะไรต่อ
    """
    category = get_category(user, category_id)
    remaining = task_count(category)
    if remaining:
        raise ConflictError(
            ngettext(
                "Cannot delete “%(name)s” — it still has %(num)d task.",
                "Cannot delete “%(name)s” — it still has %(num)d tasks.",
                remaining,
                name=category.name,
            ),
            code="category_in_use",
        )
    category.soft_delete()
    db.session.commit()
    return category
