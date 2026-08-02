"""เทสต์ flask CLI commands

จุดที่ต้องระวังคือ delete-user ต้องลบ category/todo ตามไปด้วย
SQLite ไม่บังคับ FK ให้ ถ้า cascade พังจะไม่มีอะไรฟ้อง แค่เหลือแถวกำพร้า
"""

from app import db
from app.cli import DEFAULT_CATEGORIES
from app.models import Category, Todo, User


def test_create_user_seeds_default_categories(app):
    result = app.test_cli_runner().invoke(
        args=["create-user", "somchai"], input="password123\npassword123\n"
    )
    assert result.exit_code == 0, result.output
    with app.app_context():
        user = User.query.filter_by(username="somchai").one()
        names = {c.name for c in user.categories}
        assert names == set(DEFAULT_CATEGORIES["en"])


def test_create_user_rejects_short_password(app):
    result = app.test_cli_runner().invoke(
        args=["create-user", "somchai"], input="sh0rt\nsh0rt\n"
    )
    assert result.exit_code != 0
    with app.app_context():
        assert User.query.filter_by(username="somchai").first() is None


def test_create_user_rejects_duplicate(app, user_id):
    result = app.test_cli_runner().invoke(args=["create-user", "tester"])
    assert result.exit_code != 0
    assert "already exists" in result.output


def test_create_user_no_categories_flag(app):
    app.test_cli_runner().invoke(
        args=["create-user", "somchai", "--no-categories"],
        input="password123\npassword123\n",
    )
    with app.app_context():
        assert User.query.filter_by(username="somchai").one().categories == []


def test_delete_user_removes_categories_and_todos(app, user_id, category_id):
    with app.app_context():
        db.session.add(
            Todo(title="งานที่ต้องหายไปด้วย", user_id=user_id, category_id=category_id)
        )
        db.session.commit()

    result = app.test_cli_runner().invoke(args=["delete-user", "tester", "--yes"])
    assert result.exit_code == 0, result.output

    with app.app_context():
        assert User.query.filter_by(username="tester").first() is None
        assert Category.query.count() == 0, "หมวดของ user ที่ถูกลบต้องหายไปด้วย"
        assert Todo.query.count() == 0, "งานของ user ที่ถูกลบต้องหายไปด้วย"


def test_delete_user_not_found(app):
    result = app.test_cli_runner().invoke(args=["delete-user", "ไม่มีคนนี้", "--yes"])
    assert result.exit_code != 0
    assert "No user named" in result.output


def test_delete_user_aborts_without_confirmation(app, user_id):
    """ไม่ใส่ --yes แล้วตอบ n ต้องไม่ลบ"""
    result = app.test_cli_runner().invoke(args=["delete-user", "tester"], input="n\n")
    assert result.exit_code != 0
    with app.app_context():
        assert User.query.filter_by(username="tester").first() is not None


def test_delete_user_keeps_other_users_data(app, user_id, other_user_id):
    with app.app_context():
        db.session.add(Category(name="ของคนอื่น", user_id=other_user_id))
        db.session.commit()

    app.test_cli_runner().invoke(args=["delete-user", "tester", "--yes"])

    with app.app_context():
        assert User.query.filter_by(username="intruder").first() is not None
        assert Category.query.filter_by(name="ของคนอื่น").count() == 1
