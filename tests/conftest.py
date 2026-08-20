import ast
import os
import pathlib

import pytest

from app import create_app, db, limiter
from app.models import Category, User
from app.services import tokens as tokens_service
from config import Config

# ต้องผ่านนโยบายของ `app/services/passwords.py` ด้วย เพราะเทสต์บางตัวสร้าง user
# ผ่าน `flask create-user` ซึ่งบังคับนโยบายเต็ม — ค่าเดิม ("password123")
# อยู่ในรายการรหัสที่หลุดแล้ว จึงถูกปฏิเสธตั้งแต่ Phase 4
PASSWORD = "pytest-fixture-passphrase"


# ---------------------------------------------------------------- marker ที่ derive มา
#
# **เทสต์ชั้นกติกาอ่านไฟล์อย่างเดียว — ผลไม่ขึ้นกับยี่ห้อฐานข้อมูลเลย** (audit รอบ 18)
# แต่มันเดินครบทุกรอบใน job `bare` และ `dialect` ทั้งสองยี่ห้อ · วัดได้ 94 วินาที
# จาก 258 บนเครื่อง แล้วคูณสี่ตามจำนวน job ที่รันชุดเต็ม
#
# **มาร์กถูก derive จากไฟล์ ไม่ใช่พิมพ์มือ** (บทเรียนของรอบ 17–18): ไฟล์ที่ไม่
# import `app` และไม่ใช้ fixture ที่สร้างแอปเลย = ชั้นกติกา · รายการที่พิมพ์มือ
# จะครบเฉพาะวันที่มีคนนึกได้ และไฟล์ที่เพิ่มทีหลังจะเดินสี่รอบต่อไปเงียบ ๆ

APP_FIXTURES = frozenset(
    {
        "app",
        "client",
        "other_client",
        "anon_client",
        "csrf_app",
        "ratelimit_app",
        "username_ratelimit_app",
        "user_id",
        "other_user_id",
        "issue_token",
    }
)


def touches_the_app(source: str) -> bool:
    """โมดูลนี้ต้องมีแอปจริงถึงจะรันได้ไหม — import `app` หรือขอ fixture ที่สร้างแอป"""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return True  # อ่านไม่ออก = ถือว่าแตะไว้ก่อน ปลอดภัยกว่าการข้าม
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "app":
            return True
        if isinstance(node, ast.Import) and any(a.name.split(".")[0] == "app" for a in node.names):
            return True
        if isinstance(node, ast.FunctionDef) and APP_FIXTURES & {a.arg for a in node.args.args}:
            return True
    return False


def pytest_collection_modifyitems(items):
    """ติดมาร์ก `governance` ให้เทสต์ในโมดูลที่ไม่ต้องมีแอปเลย"""
    verdicts: dict[pathlib.Path, bool] = {}
    for item in items:
        path = pathlib.Path(str(item.path))
        if path not in verdicts:
            verdicts[path] = touches_the_app(path.read_text(encoding="utf-8"))
        if not verdicts[path]:
            item.add_marker(pytest.mark.governance)


class TestConfig(Config):
    # คีย์ encrypt คงที่สำหรับเทสต์ (ADR 0046) — base64 ของ 32 ไบต์ศูนย์ล้วน
    DATA_ENCRYPTION_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    """สืบทอดจาก Config จริงแล้ว override เฉพาะที่ต่าง

    เคยประกาศแยกเป็น class เปล่า แล้วคีย์ใหม่ใน Config ทำเทสต์พังทั้งชุด
    มาแล้ว 4 รอบ (LANGUAGES, RATELIMIT_STORAGE_URI, THEMES, LOG_LEVEL)
    — สืบทอดแล้วคีย์ใหม่ไหลมาเองโดยไม่ต้องแก้ไฟล์นี้
    """

    # ต้องยาวพอผ่าน check_secret_key() ค่าคงที่ได้ เพราะไม่ใช่คีย์จริง
    SECRET_KEY = "test-secret-key-for-pytest-only-not-a-real-key"
    # ตรึงโหมด worker เดียว — `.env`/เครื่องที่ตั้ง WEB_CONCURRENCY ไว้ต้องไม่ทำ
    # เทสต์แดง (หลักเดียวกับ RATELIMIT_ENABLED) · เทสต์ multiproc ตั้งค่าเองรายตัว
    WEB_CONCURRENCY = 1
    METRICS_MULTIPROC_DIR = None
    # **อ่านจาก `TEST_DATABASE_URL` เท่านั้น ไม่ใช่ `DATABASE_URL`** — `.env` ของ
    # เครื่องที่รันต้องไม่มีผลกับเทสต์ (หลักเดียวกับ RATELIMIT_ENABLED/DISABLED_PLUGINS
    # ข้างล่าง) ตัวแปรนี้ไม่ถูกตั้งไว้ที่ไหนโดยปริยาย มีไว้ให้ CI matrix กับคนที่
    # อยากยิงยี่ห้ออื่นตั้งเองตอนรัน — ค่าเริ่มต้นยังเป็น SQLite ในหน่วยความจำ
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")
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
    # **ตรึงสภาพของ plugin ไม่ให้ขึ้นกับ .env ของเครื่องที่รัน** — สองค่านี้อ่านจาก
    # environment ใน `Config` ผู้ดูแลที่ใช้สวิตช์จริงตามที่ docs/OPERATIONS.md บอก
    # จะรันเทสต์ไม่ผ่านทันที ทั้งที่โค้ดไม่ได้ผิดอะไรเลย (หลักเดียวกับ RATELIMIT_ENABLED)
    # ตัวสวิตช์เองมีเทสต์ที่ตั้งค่าเองอยู่แล้วใน tests/test_plugins.py
    DISABLED_PLUGINS = frozenset()
    PLUGIN_PICKS = {}
    AUTH_PROFILES = ()
    # ตรึงด้วยเหตุผลเดียวกัน — เครื่องที่ตั้งไว้เพราะรันหลัง proxy จริงจะทำให้
    # เทสต์ที่ยิงตรงเข้าแอปเชื่อ `X-Forwarded-For` ที่ตัวเทสต์ไม่ได้ตั้งใจส่ง
    # ตัวมันเองมีเทสต์ที่ตั้งค่าเองอยู่ใน tests/test_proxy.py
    TRUSTED_PROXY_HOPS = 0


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


def _app_with_tables(config_class):
    """แอปพร้อมตารางเปล่า แล้วเก็บกวาดให้หลังเทสต์จบ

    **ทุก fixture ที่สร้างแอปต้องเดินทางเส้นนี้** ไม่ใช่เรียก `create_all()` เอง —
    `sqlite:///:memory:` ตายไปพร้อม engine จึงให้อภัยการลืมเก็บกวาดมาตลอด
    แต่ยี่ห้ออื่นเก็บตารางไว้ข้ามเทสต์ ข้อมูลของตัวก่อนหน้าจะค้างมาให้ตัวถัดไปเห็น
    (เจอจริงตอน P5-04: `Duplicate entry 'tester'` เพราะ fixture สามตัวสร้างเองแล้วไม่ลบ)
    """
    app = create_app(config_class)
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.drop_all()
        # ปิด connection pool ทิ้งท้ายเทสต์ ไม่งั้น sqlite ในหน่วยความจำถูกเก็บโดย GC
        # แล้วโผล่เป็น ResourceWarning เป็นร้อย ๆ อัน — เสียงรบกวนขนาดนั้นกลบ warning จริง
        db.engine.dispose()


@pytest.fixture
def app():
    yield from _app_with_tables(TestConfig)


@pytest.fixture
def warnings_of(app):
    """เก็บ log ระดับ WARNING จาก logger ของแอปตรง ๆ

    ไม่ใช้ `caplog` ที่นี่โดยตั้งใจ — มันดักด้วย handler บน root logger ส่วน
    `init_logging()` ตั้ง `root.handlers = [handler]` ทับทุกครั้งที่สร้างแอป
    ผลคือเทสต์เขียวตอนรันไฟล์เดียวแต่แดงตอนรันทั้งชุด ขึ้นกับว่าแอปตัวไหน
    ถูกสร้างตอนไหน (เจอจริงตอนเขียนเทสต์ของ plugin)

    **อยู่ใน conftest เพราะมีคนใช้สองไฟล์แล้ว** (plugin กับ cache) — คำเตือน
    ที่ระบบพูดตอน start เป็นสิ่งที่หลายเรื่องต้องพิสูจน์ ไม่ใช่ของเฉพาะเรื่องเดียว
    """
    import logging

    lines: list[str] = []

    class Grab(logging.Handler):
        def emit(self, record):
            lines.append(record.getMessage())

    handler = Grab(level=logging.WARNING)
    app.logger.addHandler(handler)
    yield lines
    app.logger.removeHandler(handler)


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
    for app in _app_with_tables(CsrfTestConfig):
        with app.app_context():
            _make_user("tester")
        yield app


@pytest.fixture
def ratelimit_app():
    """แอปที่เปิด rate limit จริง (3 ครั้ง/นาที) พร้อม user 'tester'

    limiter เป็น singleton ระดับโมดูล storage จึงค้างข้ามเทสต์
    ต้อง reset ทั้งก่อนและหลัง ไม่งั้นเทสต์ที่รันทีหลังจะเริ่มด้วยโควตาที่ถูกใช้ไปแล้ว
    (reset ได้หลัง init_app เท่านั้น ก่อนหน้านั้น storage ยังไม่ถูกสร้าง)
    """
    for app in _app_with_tables(RateLimitTestConfig):
        with app.app_context():
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
    for app in _app_with_tables(UsernameRateLimitTestConfig):
        with app.app_context():
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
