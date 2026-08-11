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
from app.services.lookup import by_id
from app.soft_delete import INCLUDE_DELETED


def list_categories(user: User) -> list[Category]:
    """หมวดทั้งหมดของผู้ใช้ เรียงตามชื่อ"""
    statement = select(Category).where(Category.user_id == user.id).order_by(Category.name)
    return list(db.session.scalars(statement))


def get_category(user: User, category_id: int) -> Category:
    """หมวดของผู้ใช้คนนี้เท่านั้น — ของคนอื่นตอบเหมือนไม่มีอยู่ (ADR 0004)"""
    category = by_id(Category, category_id)
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


def _named(user: User, name: str, exclude_id: int | None = None) -> Category | None:
    """หมวดชื่อนี้ของผู้ใช้คนนี้ **รวมที่ถูกลบไปแล้ว**

    **ต้องมองเห็นแถวที่ถูกลบด้วย** เพราะ `uq_category_user_name` ไม่รู้จัก
    `deleted_at` — การถามด้วยตัวกรองปกติจึงตอบว่า "ยังไม่มีชื่อนี้" แล้ว INSERT
    ไปชนกุญแจ unique เป็น 500 · เจอด้วย job `dast` ตอนที่ ZAP ลบหมวดแล้วสร้างใหม่
    ด้วยชื่อเดิม (ไม่มีเทสต์ตัวไหนเดินเส้นทางนั้นมาก่อน)
    """
    statement = select(Category).where(Category.user_id == user.id, Category.name == name)
    if exclude_id is not None:
        statement = statement.where(Category.id != exclude_id)
    return db.session.scalars(statement.execution_options(**INCLUDE_DELETED)).first()


def create_category(user: User, name: str | None) -> Category:
    """สร้างหมวดใหม่ — ชื่อที่ตรงกับหมวดที่ถูกลบไปแล้ว **กู้หมวดนั้นคืนมา**

    ไม่ใช่การสร้างแถวใหม่ เพราะการลบหมวดทำได้เฉพาะตอนไม่มีงานเหลืออยู่แล้ว
    ของที่กู้คืนจึงว่างเปล่าเท่ากับของใหม่ทุกประการ ต่างกันแค่ id เดิมและประวัติ
    ใน audit ที่ยังต่อกัน — ซึ่งดีกว่าการมี id ใหม่ที่ไม่มีใครอธิบายได้
    """
    cleaned = _clean_name(name, _("Please enter a category name"))
    existing = _named(user, cleaned)
    if existing is not None:
        if not existing.is_deleted:
            raise ConflictError(
                _("Category “%(name)s” already exists", name=cleaned),
                code="category_exists",
                field="name",
            )
        existing.deleted_at = None  # audit บันทึกเป็น category.restore ให้เอง
        db.session.commit()
        return existing
    category = Category(name=cleaned, user_id=user.id)
    db.session.add(category)
    db.session.commit()
    return category


def rename_category(user: User, category_id: int, name: str | None) -> Category:
    """เปลี่ยนชื่อหมวด — ชื่อเดิมของตัวเองไม่นับว่าซ้ำ"""
    category = get_category(user, category_id)
    cleaned = _clean_name(name, _("Category name cannot be empty"))
    existing = _named(user, cleaned, exclude_id=category.id)
    if existing is not None:
        # **ชื่อที่ถูกจองโดยหมวดที่ถูกลบไปแล้วก็ยังชนกุญแจ unique** จึงต้องปฏิเสธ
        # ตรงนี้ ไม่ใช่ปล่อยให้ไปพังที่ฐานข้อมูล · บอกทางออกไปด้วยเพราะหมวดนั้น
        # มองไม่เห็นบนหน้าเว็บ คนอ่านข้อความจึงไม่มีทางเดาได้ว่าเกิดอะไรขึ้น
        raise ConflictError(
            _("Category “%(name)s” already exists", name=cleaned)
            if not existing.is_deleted
            else _(
                "The name “%(name)s” belongs to a category you deleted. "
                "Create a category with that name to bring it back.",
                name=cleaned,
            ),
            code="category_exists",
            field="name",
        )
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
