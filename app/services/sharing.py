"""การแชร์งานเข้าวง (ADR 0049 ข้อ 1) — opt-in ต่อใบ · เผยสี่ฟิลด์เท่านั้น

สิ่งที่สมาชิกวงเห็นจากงานที่แชร์: **ชื่องาน · กำหนดส่ง · สถานะ · ชื่อเจ้าของ**
ผ่าน `SharedTodoView` เท่านั้น — ห้ามส่ง `Todo` ดิบข้ามเส้นเจ้าของออกไปจาก
ไฟล์นี้ เพราะ template/serializer ที่ได้ object เต็มจะเผลอเผยฟิลด์อื่นได้เสมอ

กติกาการตัด dependency (ADR 0049 ข้อ 2): dependency มีชีวิตอยู่ได้ก็ต่อเมื่อ
เจ้าของมัน**ยังมองเห็น**งานปลายทางผ่านการแชร์อย่างน้อยหนึ่งวง — เลิกแชร์/
ถอดสมาชิก/ลบวง ล้วนจบที่คำถามเดียวกันนี้ จึงรวมไว้ที่
`sever_invisible_dependencies()` ที่เดียว
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from flask_babel import gettext as _
from sqlalchemy import select

from app import db
from app.models import Team, TeamMember, Todo, TodoDependency, TodoShare, User
from app.services import teams as teams_service
from app.services.errors import ConflictError, NotFoundError
from app.services.lookup import by_id
from app.services.todos import get_todo
from app.soft_delete import INCLUDE_DELETED


@dataclass(frozen=True)
class SharedTodoView:
    """สี่ฟิลด์ที่ ADR 0049 อนุญาต — และ id ไว้ใช้อ้างตอนขอพึ่ง (ไม่ใช่ข้อมูลเพิ่ม
    เพราะคนที่เห็น view นี้มีสิทธิ์เห็นงานใบนี้อยู่แล้ว)"""

    todo_id: int
    title: str
    due_date: datetime | None
    is_done: bool
    owner_username: str


def _view(todo: Todo) -> SharedTodoView:
    return SharedTodoView(
        todo_id=todo.id,
        title=todo.title,
        due_date=todo.due_date,
        is_done=todo.is_done,
        owner_username=todo.user.username,
    )


def share(owner: User, todo_id: int, team_id: int) -> TodoShare:
    """แชร์งานของตัวเองเข้าวงที่ตัวเองเป็นสมาชิก — วงที่ไม่ได้อยู่ = ไม่มีวงนั้น"""
    todo = get_todo(owner, todo_id)
    team = teams_service.visible_team(owner, team_id)
    existing = db.session.scalars(
        select(TodoShare)
        .where(TodoShare.todo_id == todo.id, TodoShare.team_id == team.id)
        .execution_options(**INCLUDE_DELETED)
    ).first()
    if existing is not None:
        if not existing.is_deleted:
            raise ConflictError(_("Already shared with this team"), code="already_shared")
        existing.deleted_at = None
        db.session.commit()
        return existing
    row = TodoShare(todo_id=todo.id, team_id=team.id)
    db.session.add(row)
    db.session.commit()
    return row


def unshare(owner: User, todo_id: int, team_id: int) -> TodoShare:
    """เลิกแชร์ — dependency ที่มองเห็นงานนี้ผ่านวงนี้ทางเดียวถูกตัดตาม (ADR 0049)"""
    todo = get_todo(owner, todo_id)
    row = db.session.scalars(
        select(TodoShare).where(TodoShare.todo_id == todo.id, TodoShare.team_id == team_id)
    ).first()
    if row is None:
        raise NotFoundError(_("Not shared with this team"), code="share_not_found")
    row.soft_delete()
    # flush ก่อนถามการมองเห็น — เงื่อนไขข้างล่างเป็น SQL ที่ต้องเห็นแถวที่เพิ่งซ่อน
    db.session.flush()
    for dependency in db.session.scalars(
        select(TodoDependency).where(TodoDependency.depends_on_todo_id == todo.id)
    ):
        depender = by_id(User, dependency.todo.user_id)
        if depender is None or not can_see_todo(depender, todo.id):
            dependency.soft_delete()
    db.session.commit()
    return row


def shares_of(owner: User, todo_id: int) -> list[TodoShare]:
    todo = get_todo(owner, todo_id)
    return list(db.session.scalars(select(TodoShare).where(TodoShare.todo_id == todo.id)))


def can_see_todo(viewer: User, todo_id: int) -> bool:
    """งานนี้ถูกแชร์เข้าวงที่ viewer เป็นสมาชิกอย่างน้อยหนึ่งวงไหม — จุดตัดสินเดียว

    ครอบเจ้าของด้วย (เจ้าของเห็นงานตัวเองเสมอ) เพื่อให้ผู้เรียกไม่ต้องแยกกรณี
    """
    todo = by_id(Todo, todo_id)
    if todo is None:
        return False
    if todo.user_id == viewer.id:
        return True
    row = db.session.scalars(
        select(TodoShare)
        .join(TeamMember, TeamMember.team_id == TodoShare.team_id)
        .join(Team, Team.id == TodoShare.team_id)
        .where(TodoShare.todo_id == todo_id, TeamMember.user_id == viewer.id)
    ).first()
    return row is not None


def visible_shared_todo(viewer: User, todo_id: int) -> SharedTodoView:
    """งานที่แชร์ในสายตาสมาชิกวง — มองไม่เห็น = ไม่มีงานนั้นอยู่ (ADR 0004)"""
    todo = by_id(Todo, todo_id)
    if todo is None or todo.user_id == viewer.id or not can_see_todo(viewer, todo_id):
        raise NotFoundError(_("Task not found"), code="todo_not_found")
    return _view(todo)


def shared_in_team(viewer: User, team_id: int) -> list[SharedTodoView]:
    """งานทั้งหมดที่แชร์เข้าวงนี้ — เรียกได้เฉพาะสมาชิก (ไม่ใช่สมาชิก = ไม่มีวง)"""
    team = teams_service.visible_team(viewer, team_id)
    todos = db.session.scalars(
        select(Todo)
        .join(TodoShare, TodoShare.todo_id == Todo.id)
        .where(TodoShare.team_id == team.id)
        .order_by(Todo.due_date.is_(None), Todo.due_date)
    )
    return [_view(todo) for todo in todos]


def sever_invisible_dependencies(depender: User) -> int:
    """ตัด dependency ของคนนี้ที่ชี้ไปงานซึ่งเขามองไม่เห็นแล้ว — คืนจำนวนที่ตัด

    จุดรวมของทุกทางที่การมองเห็นหายไป (ถอดสมาชิก/ลบวง) · **ไม่ commit เอง**
    เพราะถูกเรียกกลางทรานแซกชันของ service อื่นเสมอ
    """
    severed = 0
    for dependency in db.session.scalars(
        select(TodoDependency)
        .join(Todo, Todo.id == TodoDependency.todo_id)
        .where(Todo.user_id == depender.id)
    ):
        if not can_see_todo(depender, dependency.depends_on_todo_id):
            dependency.soft_delete()
            severed += 1
    return severed


def retire_team_shares(team: Team) -> None:
    """ซ่อนการแชร์ทั้งหมดของวงที่กำลังถูกลบ แล้วตัด dependency ที่มืดบอดตาม

    **ไม่ commit เอง** — เป็นส่วนหนึ่งของทรานแซกชัน `delete_team()`
    """
    dependers: set[int] = set()
    shares = list(db.session.scalars(select(TodoShare).where(TodoShare.team_id == team.id)))
    for row in shares:
        row.soft_delete()
    db.session.flush()
    for row in shares:
        for dependency in db.session.scalars(
            select(TodoDependency).where(TodoDependency.depends_on_todo_id == row.todo_id)
        ):
            dependers.add(dependency.todo.user_id)
    for user_id in dependers:
        person = by_id(User, user_id)
        if person is not None:
            sever_invisible_dependencies(person)


def severed_recently(owner: User, within_days: int = 30) -> int:
    """จำนวน dependency ของเราที่เพิ่งถูกตัดจากฝั่งโน้น — "แจ้งฝั่งที่พึ่ง" ตาม ADR

    บอกได้แค่*จำนวนกับช่วงเวลา* — ชื่องาน/เจ้าของบอกไม่ได้แล้วเพราะสิทธิ์
    การมองเห็นจบไปพร้อมการแชร์ (การเก็บชื่อไว้โชว์คือการรั่วย้อนหลัง)
    """
    from app import tz

    cutoff = tz.now_utc() - timedelta(days=within_days)
    rows = db.session.scalars(
        select(TodoDependency)
        .join(Todo, Todo.id == TodoDependency.todo_id)
        .where(Todo.user_id == owner.id, TodoDependency.deleted_at.is_not(None))
        .where(TodoDependency.deleted_at >= cutoff)
        .execution_options(**INCLUDE_DELETED)
    )
    return len(list(rows))
