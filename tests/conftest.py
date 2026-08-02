import pytest

from app import create_app, db
from app.models import Category, User

PASSWORD = "password123"


class TestConfig:
    SECRET_KEY = "test"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TESTING = True


def _make_user(username):
    user = User(username=username)
    user.set_password(PASSWORD)
    db.session.add(user)
    db.session.commit()
    return user.id


@pytest.fixture
def app():
    app = create_app(TestConfig)
    # ไม่มี db.create_all() ใน create_app แล้ว (ใช้ Flask-Migrate) เทสต์จึงสร้างเอง
    with app.app_context():
        db.create_all()
    yield app


@pytest.fixture
def user_id(app):
    with app.app_context():
        return _make_user("tester")


@pytest.fixture
def other_user_id(app):
    with app.app_context():
        return _make_user("intruder")


def _login_as(app, username):
    client = app.test_client()
    resp = client.post(
        "/login", data={"username": username, "password": PASSWORD}
    )
    assert resp.status_code == 302, f"login เป็น {username} ไม่สำเร็จ"
    return client


@pytest.fixture
def client(app, user_id):
    """client ที่ login เป็น tester แล้ว"""
    return _login_as(app, "tester")


@pytest.fixture
def other_client(app, other_user_id):
    """client ที่ login เป็นคนอื่น ใช้ทดสอบว่าข้ามไปยุ่งข้อมูลกันไม่ได้"""
    return _login_as(app, "intruder")


@pytest.fixture
def anon_client(app):
    """client ที่ยังไม่ได้ login"""
    return app.test_client()


@pytest.fixture
def category_id(app, user_id):
    with app.app_context():
        category = Category(name="งานส่วนตัว", user_id=user_id)
        db.session.add(category)
        db.session.commit()
        return category.id
