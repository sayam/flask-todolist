import pytest

from app import create_app, db, limiter
from app.models import Category, User
from app.services import tokens as tokens_service
from config import Config

# ต้องผ่านนโยบายของ `app/services/passwords.py` ด้วย เพราะเทสต์บางตัวสร้าง user
# ผ่าน `flask create-user` ซึ่งบังคับนโยบายเต็ม — ค่าเดิม ("password123")
# อยู่ในรายการรหัสที่หลุดแล้ว จึงถูกปฏิเสธตั้งแต่ Phase 4
PASSWORD = "pytest-fixture-passphrase"


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


class UsernameRateLimitTestConfig(TestConfig):
    """โควตาต่อ IP ตั้งหลวมมากเพื่อให้เห็นผลของโควตาต่อ *ชื่อผู้ใช้* ล้วน ๆ

    ถ้าตั้งสองตัวใกล้กัน เทสต์จะแยกไม่ออกว่าที่โดนกันเป็นเพราะมิติไหน
    """

    RATELIMIT_ENABLED = True
    LOGIN_RATE_LIMIT = "1000 per minute"
    LOGIN_USERNAME_RATE_LIMIT = "3 per minute"


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
    # ปิด connection pool ทิ้งท้ายเทสต์ ไม่งั้น sqlite ในหน่วยความจำถูกเก็บโดย GC
    # แล้วโผล่เป็น ResourceWarning เป็นร้อย ๆ อัน — เสียงรบกวนขนาดนั้นกลบ warning จริง
    with app.app_context():
        db.engine.dispose()


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
def username_ratelimit_app():
    """แอปที่โควตาต่อชื่อผู้ใช้เหลือ 3 ครั้ง/นาที ส่วนโควตาต่อ IP หลวมจนไม่มีผล

    reset ทั้งก่อนและหลังด้วยเหตุผลเดียวกับ `ratelimit_app`
    """
    app = create_app(UsernameRateLimitTestConfig)
    with app.app_context():
        db.create_all()
        _make_user("tester")
        _make_user("somchai")
        limiter.reset()
    yield app
    with app.app_context():
        limiter.reset()


def issue_token(app, user_id, name="pytest"):
    """ออก token ให้ผู้ใช้คนนั้น คืนสตริงเต็มที่เอาไปใส่ header ได้เลย"""
    with app.app_context():
        return tokens_service.issue(db.session.get(User, user_id), name)


def bearer_client(app, token):
    """client ที่แนบ `Authorization: Bearer ...` ให้ทุกคำขอเอง"""
    client = app.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client


@pytest.fixture
def api_token(app, user_id):
    return issue_token(app, user_id)


@pytest.fixture
def api_client(app, api_token):
    """client ที่ยิง `/api/v1` ในนามของ tester ด้วย token (ไม่มี session cookie)"""
    return bearer_client(app, api_token)


@pytest.fixture
def other_api_client(app, other_user_id):
    """client ที่ยิง API ในนามของคนอื่น ใช้ทดสอบว่าข้ามไปยุ่งข้อมูลกันไม่ได้"""
    return bearer_client(app, issue_token(app, other_user_id))


@pytest.fixture
def category_id(app, user_id):
    with app.app_context():
        category = Category(name="งานส่วนตัว", user_id=user_id)
        db.session.add(category)
        db.session.commit()
        return category.id
