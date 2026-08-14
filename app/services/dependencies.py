"""dependency ข้ามคน (ADR 0049 ข้อ 2) — เชิญ → ยอมรับ เท่านั้น · และสัญญาณ
impact แบบ deterministic (ข้อ 3)

สถานะมีสองค่า: `invited` (ยังไม่มีผลใด ๆ รวมทั้งต่อ impact) และ `accepted`
การปฏิเสธ/ถอน/เพิกถอน = soft delete แถว — ไม่มีสถานะ "declined" ค้างไว้
เพราะรายการปฏิเสธที่เก็บถาวรคือบันทึกว่าใครไม่อยากยุ่งกับใคร ซึ่งไม่ใช่ข้อมูล
ที่ feature นี้ต้องการเก็บ (audit มีบันทึกการเปลี่ยนแปลงอยู่แล้วตามวงจรปกติ)

impact (ข้อ 3): งานของเราเสี่ยงเมื่องานที่เราพึ่ง — ตรงหรือผ่านโซ่ของ
dependency ที่ *ยอมรับแล้ว* — เลยกำหนดและยังไม่เสร็จ · คำนวณจากของที่แชร์
เท่านั้น ไม่มีการแอบรวมงาน private เข้าโซ่แม้จะแม่นขึ้น (การรู้มากกว่าที่เห็น
คือช่องรั่วแบบ inference)
"""

from flask_babel import gettext as _
from sqlalchemy import select

from app import db, tz
from app.models import (
    DEPENDENCY_ACCEPTED,
    DEPENDENCY_INVITED,
    Todo,
    TodoDependency,
    User,
)
from app.services import sharing
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.services.lookup import by_id
from app.services.todos import get_todo
from app.soft_delete import INCLUDE_DELETED


def invite(owner: User, todo_id: int, depends_on_todo_id: int) -> TodoDependency:
    """ประกาศ "งานของฉันพึ่งงานใบนั้น" — เกิดเป็นคำเชิญ รอเจ้าของปลายทางยอมรับ

    ปลายทางต้องเป็นงานที่เรามองเห็นผ่านวง (มองไม่เห็น = ไม่มีงานนั้น — ADR 0004)
    และห้ามพึ่งงานของตัวเอง (โซ่ภายในคนเดียวไม่ต้องมีพิธียอมรับ และ impact
    ของงานตัวเองอ่านได้ตรง ๆ จากกำหนดส่งอยู่แล้ว)
    """
    todo = get_todo(owner, todo_id)
    target = by_id(Todo, depends_on_todo_id)
    if (
        target is None
        or target.user_id == owner.id
        or not sharing.can_see_todo(owner, depends_on_todo_id)
    ):
        if target is not None and target.user_id == owner.id:
            raise ValidationError(
                _("A task cannot depend on your own task"), code="self_dependency"
            )
        raise NotFoundError(_("Task not found"), code="todo_not_found")
    existing = db.session.scalars(
        select(TodoDependency)
        .where(TodoDependency.todo_id == todo.id, TodoDependency.depends_on_todo_id == target.id)
        .execution_options(**INCLUDE_DELETED)
    ).first()
    if existing is not None:
        if not existing.is_deleted:
            raise ConflictError(_("Dependency already exists"), code="dependency_exists")
        # คืนชีพ = คำเชิญใหม่เสมอ — การยอมรับครั้งก่อนตายไปพร้อมการถอนครั้งก่อน
        existing.deleted_at = None
        existing.status = DEPENDENCY_INVITED
        existing.accepted_at = None
        db.session.commit()
        return existing
    row = TodoDependency(todo_id=todo.id, depends_on_todo_id=target.id)
    db.session.add(row)
    db.session.commit()
    return row


def _incoming_row(target_owner: User, dependency_id: int) -> TodoDependency:
    """แถวที่ชี้มาหางานของเรา — ของคนอื่นตอบเหมือนไม่มีอยู่"""
    row = by_id(TodoDependency, dependency_id)
    if row is None or row.depends_on.user_id != target_owner.id:
        raise NotFoundError(_("Dependency not found"), code="dependency_not_found")
    return row


def accept(target_owner: User, dependency_id: int) -> TodoDependency:
    row = _incoming_row(target_owner, dependency_id)
    if row.status == DEPENDENCY_ACCEPTED:
        raise ConflictError(_("Already accepted"), code="already_accepted")
    row.status = DEPENDENCY_ACCEPTED
    row.accepted_at = tz.now_utc()
    db.session.commit()
    return row


def decline(target_owner: User, dependency_id: int) -> TodoDependency:
    """ปฏิเสธคำเชิญ หรือเพิกถอนที่เคยยอมรับ — ทั้งคู่จบแบบเดียวกัน (ADR 0049:
    ถอนได้ทั้งสองฝั่งทุกเมื่อ)"""
    row = _incoming_row(target_owner, dependency_id)
    row.soft_delete()
    db.session.commit()
    return row


def withdraw(owner: User, dependency_id: int) -> TodoDependency:
    """ฝั่งคนพึ่งถอนเอง — ใช้ได้ทั้งคำเชิญที่ยังค้างและที่ยอมรับแล้ว"""
    row = by_id(TodoDependency, dependency_id)
    if row is None or row.todo.user_id != owner.id:
        raise NotFoundError(_("Dependency not found"), code="dependency_not_found")
    row.soft_delete()
    db.session.commit()
    return row


def incoming_invites(target_owner: User) -> list[TodoDependency]:
    """คำเชิญที่รอเราตัดสิน — dependency ชี้มาหางานของเราและยัง `invited`"""
    return list(
        db.session.scalars(
            select(TodoDependency)
            .join(Todo, Todo.id == TodoDependency.depends_on_todo_id)
            .where(Todo.user_id == target_owner.id, TodoDependency.status == DEPENDENCY_INVITED)
            .order_by(TodoDependency.created_at)
        )
    )


def accepted_on_my_todos(target_owner: User) -> list[TodoDependency]:
    """dependency ที่ยอมรับแล้วซึ่งชี้มาหางานของเรา — ไว้เพิกถอนภายหลังได้"""
    return list(
        db.session.scalars(
            select(TodoDependency)
            .join(Todo, Todo.id == TodoDependency.depends_on_todo_id)
            .where(Todo.user_id == target_owner.id, TodoDependency.status == DEPENDENCY_ACCEPTED)
            .order_by(TodoDependency.created_at)
        )
    )


def dependencies_of(owner: User, todo_id: int) -> list[TodoDependency]:
    """dependency ทั้งหมดของงานเราหนึ่งใบ (ทั้ง invited และ accepted)"""
    todo = get_todo(owner, todo_id)
    return list(
        db.session.scalars(
            select(TodoDependency)
            .where(TodoDependency.todo_id == todo.id)
            .order_by(TodoDependency.created_at)
        )
    )


# ---------------------------------------------------------------- impact (ข้อ 3)


def _overdue(todo: Todo) -> bool:
    return not todo.is_done and todo.due_date is not None and todo.due_date < tz.now_utc()


def at_risk_todo_ids(owner: User) -> set[int]:
    """id ของงานเราที่เสี่ยง — เดินโซ่ dependency ที่ยอมรับแล้วแบบกันวงวน

    เดินบนกราฟทั้งก้อนของ dependency ที่ accepted (ตารางเดียว โหลดครั้งเดียว)
    — ความถูกต้องของ privacy ไม่ได้อยู่ที่การจำกัดการอ่านตรงนี้ แต่อยู่ที่
    ทุกแถว accepted เกิดจากการเชิญ+ยอมรับบนงานที่แชร์เท่านั้น (invariant ของ
    `invite()`/`sever_invisible_dependencies()`) และผลลัพธ์ที่คืนคือ id งาน
    ของเราเองล้วน ๆ ไม่พกรายละเอียดของใครติดมา
    """
    edges: dict[int, list[int]] = {}
    for row in db.session.scalars(
        select(TodoDependency).where(TodoDependency.status == DEPENDENCY_ACCEPTED)
    ):
        edges.setdefault(row.todo_id, []).append(row.depends_on_todo_id)

    risky_cache: dict[int, bool] = {}

    def chain_is_risky(todo_id: int, trail: set[int]) -> bool:
        if todo_id in risky_cache:
            return risky_cache[todo_id]
        if todo_id in trail:
            return False  # วงวน — ไม่มีจุดเลยกำหนดจริงในวงก็ไม่เสี่ยง
        todo = by_id(Todo, todo_id)
        if todo is None:
            risky_cache[todo_id] = False
            return False
        if _overdue(todo):
            risky_cache[todo_id] = True
            return True
        result = any(chain_is_risky(child, trail | {todo_id}) for child in edges.get(todo_id, []))
        risky_cache[todo_id] = result
        return result

    mine = db.session.scalars(select(Todo).where(Todo.user_id == owner.id, ~Todo.is_done))
    at_risk: set[int] = set()
    for todo in mine:
        # ความเสี่ยงของงานเรามาจาก "สิ่งที่เราพึ่ง" ไม่ใช่ตัวเราเลยกำหนดเอง
        # (อย่างหลังมีป้าย overdue อยู่แล้ว — สองป้ายต้องไม่ทับความหมายกัน)
        if any(chain_is_risky(child, {todo.id}) for child in edges.get(todo.id, [])):
            at_risk.add(todo.id)
    return at_risk
