"""สร้างข้อมูลตั้งต้นสำหรับสแกน a11y (pa11y)

หน้าแรกที่ไม่มีงานเลยแทบไม่มีอะไรให้ตรวจ — checkbox, ป้ายเลยกำหนด, ปุ่มแก้ไข/ลบ
ล้วนอยู่ในแถวงานทั้งนั้น สคริปต์นี้จึงเติมงานที่ครอบ state ที่ต่างกันให้ครบ

ใช้กับ **ฐานข้อมูลชั่วคราวเท่านั้น** — ตั้ง DATABASE_URL ชี้ไปที่ไฟล์ทิ้ง ๆ ก่อนรัน
สคริปต์จะปฏิเสธถ้าชี้ไปที่ฐานข้อมูลจริงของ instance

    DATABASE_URL=sqlite:////tmp/a11y.db pipenv run flask db upgrade
    DATABASE_URL=sqlite:////tmp/a11y.db PYTHONPATH=. pipenv run python scripts/a11y_fixture.py

ต้องมี PYTHONPATH=. เพราะ repo ไม่ได้ติดตั้งเป็น package (pytest ตั้งให้เองผ่าน
`pythonpath` ใน pyproject.toml แต่ `python` เปล่า ๆ ไม่รู้)
"""

import os
import sys
from datetime import UTC, datetime, timedelta

from app import create_app
from app.models import Category, Todo, User, db

USERNAME = "a11y"
PASSWORD = "A11yProbe!2026"  # noqa: S105  บัญชีชั่วคราวในฐานข้อมูลทิ้ง ไม่ใช่ความลับ


def _guard(app) -> None:
    """กันเผลอรันใส่ฐานข้อมูลจริง"""
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    if "instance" in uri or uri.endswith("todolist.db"):
        sys.exit(f"ปฏิเสธ: DATABASE_URL ชี้ไปฐานข้อมูลจริง ({uri})")


def main() -> None:
    if not os.environ.get("DATABASE_URL"):
        sys.exit("ต้องตั้ง DATABASE_URL ให้ชี้ไปฐานข้อมูลชั่วคราวก่อน")

    app = create_app()
    _guard(app)

    with app.app_context():
        user = User(username=USERNAME, role="admin")  # ให้สแกนหน้า Site administration ได้
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.flush()

        category = Category(name="Work", user_id=user.id)
        db.session.add(category)
        db.session.flush()

        now = datetime.now(UTC).replace(tzinfo=None)
        rows = [
            # (ชื่อ, กำหนดส่ง, เสร็จแล้ว, หมวด) — ครอบทุก state ที่ทำให้ UI ต่างกัน
            ("Task due tomorrow", now + timedelta(days=1), False, category.id),
            ("Overdue task", now - timedelta(days=2), False, None),
            ("Task due today", now + timedelta(hours=2), False, category.id),
            ("Completed task", None, True, None),
            ("Task with no due date", None, False, None),
        ]
        for title, due, is_done, category_id in rows:
            db.session.add(
                Todo(
                    title=title,
                    due_date=due,
                    start_date=now - timedelta(days=1),
                    is_done=is_done,
                    user_id=user.id,
                    category_id=category_id,
                )
            )
        # org graph (ADR 0049) — วงหนึ่งวง เพื่อนร่วมวงหนึ่งคน งานแชร์ +
        # คำเชิญ dependency ค้าง ให้หน้า /teams กับหน้าวงมีของครบทุก state
        from app.models import Team, TeamMember, TeamNameChange, TodoDependency, TodoShare

        colleague = User(username="a11ymate")
        colleague.set_password(PASSWORD)
        db.session.add(colleague)
        db.session.flush()
        team = Team(name="A11y crew")
        db.session.add(team)
        db.session.flush()
        db.session.add(TeamMember(team_id=team.id, user_id=user.id))
        db.session.add(TeamMember(team_id=team.id, user_id=colleague.id))
        theirs = Todo(
            title="Shared upstream task",
            due_date=now + timedelta(days=2),
            user_id=colleague.id,
        )
        db.session.add(theirs)
        db.session.flush()
        db.session.add(TodoShare(todo_id=theirs.id, team_id=team.id))
        mine_shared = Todo(title="Task shared by me", due_date=None, user_id=user.id)
        db.session.add(mine_shared)
        db.session.flush()
        db.session.add(TodoShare(todo_id=mine_shared.id, team_id=team.id))
        db.session.add(TodoDependency(todo_id=theirs.id, depends_on_todo_id=mine_shared.id))
        # หนึ่งแถวใน change log — ให้หน้า /teams/1/info มีตารางจริงให้ pa11y สแกน
        db.session.add(
            TeamNameChange(
                team_id=team.id,
                changed_by_id=user.id,
                old_name="A11y krew",
                new_name="A11y crew",
                reason="Fixed the spelling",
            )
        )

        db.session.commit()
        print(f"เตรียมข้อมูลแล้ว: user={USERNAME} todos={len(rows)}")


if __name__ == "__main__":
    main()
