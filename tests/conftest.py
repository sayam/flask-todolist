import pytest

from app import create_app, db, limiter
from app.models import Category, User
from config import Config

PASSWORD = "password123"


class TestConfig(Config):
    """สืบทอดจาก Config จริงแล้ว override เฉพาะที่ต่าง

    เคยประกาศแยกเป็น class เปล่า แล้วคีย์ใหม่ใน Config ทำเทสต์พังทั้งชุด
    มาแล้ว 4 รอบ (LANGUAGES, RATELIMIT_STORAGE_URI, THEMES, LOG_LEVEL)
    — สืบทอดแล้วคีย์ใหม่ไหลมาเองโดยไม่ต้องแก้ไฟล์นี้
    """

    # ต้องยาวพอผ่าน check_secret_key() ค่าคงที่ได้ เพราะไม่ใช่คีย์จริง
    SECRET_KEY = "test-secret-key-for-pytest-only-not-a-real-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TESTING = True
    # ปิด CSRF ในเทสต์ทั่วไปเพื่อไม่ต้องแนบ token ทุกคำขอ
    # ตัว CSRF เองมีเทสต์แยกใน test_csrf.py ที่เปิดใช้จริง
    WTF_CSRF_ENABLED = False
    # ปิด rate limit ด้วย ไม่งั้น fixture ที่ login ซ้ำ ๆ จะโดนกันเอง
    # ตัว rate limit มีเทสต์แยกใน test_ratelimit.py
    RATELIMIT_ENABLED = False
    LOGIN_RATE_LIMIT = "5 per minute"
    BABEL_DEFAULT_TIMEZONE = "Asia/Bangkok"


class CsrfTestConfig(TestConfig):
    WTF_CSRF_ENABLED = True


class RateLimitTestConfig(TestConfig):
    RATELIMIT_ENABLED = True
    LOGIN_RATE_LIMIT = "3 per minute"


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
    return app


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
    resp = client.post("/login", data={"username": username, "password": PASSWORD})
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
def csrf_app():
    """แอปที่เปิด CSRF จริง พร้อม user 'tester' หนึ่งคน"""
    app = create_app(CsrfTestConfig)
    with app.app_context():
        db.create_all()
        _make_user("tester")
    return app


@pytest.fixture
def ratelimit_app():
    """แอปที่เปิด rate limit จริง (3 ครั้ง/นาที) พร้อม user 'tester'

    limiter เป็น singleton ระดับโมดูล storage จึงค้างข้ามเทสต์
    ต้อง reset ทั้งก่อนและหลัง ไม่งั้นเทสต์ที่รันทีหลังจะเริ่มด้วยโควตาที่ถูกใช้ไปแล้ว
    (reset ได้หลัง init_app เท่านั้น ก่อนหน้านั้น storage ยังไม่ถูกสร้าง)
    """
    app = create_app(RateLimitTestConfig)
    with app.app_context():
        db.create_all()
        _make_user("tester")
        limiter.reset()
    yield app
    with app.app_context():
        limiter.reset()


@pytest.fixture
def category_id(app, user_id):
    with app.app_context():
        category = Category(name="งานส่วนตัว", user_id=user_id)
        db.session.add(category)
        db.session.commit()
        return category.id
