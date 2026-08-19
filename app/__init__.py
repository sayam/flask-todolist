"""app factory — `create_app()` กับ extension ทุกตัวของ core อยู่ที่นี่ที่เดียว

**การ import ในไฟล์นี้บางบรรทัดมีไว้เพื่อผลข้างเคียง ไม่ใช่เพื่อใช้ชื่อ**
(เช่น `db_engine` ที่ผูก event listener เปิดบังคับ foreign key ของ SQLite)
ลบทิ้งแล้วจะไม่มี error อะไรให้เห็น มีแต่ข้อมูลที่ค่อย ๆ เสีย — ดูคอมเมนต์กำกับ
"""

from pathlib import Path

from flask import Flask, render_template, request
from flask_babel import Babel
from flask_babel import lazy_gettext as _l
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

from app import db_engine, plugins
from app.cache import init_cache, warn_if_counters_are_not_shared
from app.logging_setup import init_logging
from app.metrics import init_metrics
from app.proxy import init_proxy_fix
from app.secrets import init_secrets, secrets_source
from app.security_headers import init_security_headers
from config import Config, check_secret_key

# **เวอร์ชันของ *แอป* ไม่ใช่ของสัญญา API** — `API_VERSION` ใน `config.py` เป็นคนละตัว
# และตั้งใจให้แยกจากกัน: สัญญา `/api/v1` แก้ไม่ได้ตาม ADR 0018 ส่วนแอปออกรุ่นใหม่
# ได้เรื่อย ๆ · ตอนนี้เลขบังเอิญตรงกันเพราะทั้งคู่เริ่มที่ 1.0.0 พร้อมกัน
# เลขนี้ต้องตรงกับหัวข้อบนสุดของ CHANGELOG.md (`tests/test_changelog.py` บังคับ)
__version__ = "2.0.1"

# constraint/index ที่ไม่ได้ตั้งชื่อจะได้ชื่อ auto ที่ **ต่างกันตามยี่ห้อ DB**
# ทำให้ alembic drop/alter constraint ข้ามยี่ห้อไม่ได้ (MySQL เจ็บสุด)
# ประกาศครั้งเดียวที่ MetaData แล้วทุก constraint ที่เกิดหลังจากนี้ได้ชื่อที่คาดเดาได้
# ดู docs/STANDARDS.md ข้อ 1.2 — ห้ามแก้รูปแบบนี้โดยไม่มี migration รองรับ
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """base ของทุก model — SQLAlchemy 2.0 typed style (`Mapped[]`)"""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


db = SQLAlchemy(model_class=Base)
migrate = Migrate()
csrf = CSRFProtect()
babel = Babel()
limiter = Limiter(key_func=get_remote_address)
login_manager = LoginManager()
login_manager.login_view = "auth.login"
# ผูก session กับ IP + user agent — คุกกี้ที่ถูกก๊อปไปใช้ที่เครื่องอื่นจะใช้ไม่ได้
# **ยอมรับผลข้างเคียง**: คนที่สลับเครือข่ายกลางคัน (มือถือ → wifi) จะถูกให้
# login ใหม่ แลกกับการที่คุกกี้ที่หลุดออกไปใช้ต่อที่อื่นไม่ได้ (ดู ADR 0020)
login_manager.session_protection = "strong"
# lazy_gettext เพราะข้อความนี้ถูกกำหนดตอน import ซึ่งยังไม่มี request
# ให้แปลตอนเอาไปแสดงจริง ไม่ใช่ตอนประกาศ
login_manager.login_message = _l("Please sign in first")


@login_manager.user_loader
def load_user(user_id):
    """โหลด `User` จากไอดีในคุกกี้ session — Flask-Login เรียกให้เองทุก request"""
    from app.models import User

    return db.session.get(User, int(user_id))


def create_app(config_class=Config):
    """สร้างแอปหนึ่งตัวจาก config ที่ส่งมา แล้วผูก extension/blueprint/error handler

    **ไม่เรียก `db.create_all()`** — schema มาจาก migration เท่านั้น
    """
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    # **ต้องมาก่อน `check_secret_key()`** — ความลับอาจไม่ได้มาจาก environment
    # อีกต่อไป (ADR 0030) ถ้าเช็คก่อนเติม แอปจะปฏิเสธที่จะ start ทั้งที่ค่ามีอยู่
    init_secrets(app)
    check_secret_key(app.config.get("SECRET_KEY"))
    # ให้พังตั้งแต่ตอน start ถ้าโครงสร้าง plugin ไม่ถูกต้อง — **ต้องอยู่ใน
    # app context** เพราะด่านที่อ่าน config (DISABLED_PLUGINS/AUTH_PROFILES)
    # คืนค่าว่างเงียบ ๆ เมื่อไม่มี context: ด่านที่มีอยู่แต่ไม่เคยถูกเรียกในสภาพ
    # ที่มันตรวจได้ คือด่านที่เขียวเปล่า ๆ (เจอตอนเฟส 17 — เทสต์ "config ผิด
    # ต้องไม่ start" ผ่านเฉพาะตอนเรียกด่านเองใน context ไม่ใช่ผ่าน create_app)
    with app.app_context():
        plugins.check_installation()

    # เลือก backend ของฐานข้อมูลจาก scheme ของ URL แล้วโหลดค่าเฉพาะยี่ห้อของมัน
    # (ADR 0026) — **ต้องทำก่อน `db.init_app()`** เพราะ listener ที่ backend ผูกไว้
    # ต้องอยู่ครบก่อน engine ตัวแรกถูกสร้าง ไม่งั้น connection ชุดแรกจะหลุดค่าที่
    # ตั้งไว้ไปเงียบ ๆ (ของ SQLite คือ FK ไม่ถูกบังคับ — tests/test_db_integrity.py ดักไว้)
    db_engine.load(app.config["SQLALCHEMY_DATABASE_URI"])
    # cache ก็เลือก backend จาก scheme แบบเดียวกัน — ให้ config ที่ผิดพังตั้งแต่
    # start ไม่ใช่ตอนมีคนเรียกใช้ครั้งแรก (ROADMAP ข้อ 4.3)
    init_cache(app)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    # ตั้ง log ก่อนอย่างอื่น จะได้เห็น log ของขั้นตอน init ที่เหลือด้วย
    init_logging(app)
    # แหล่งความลับถูกเลือกไปแล้วตั้งแต่ก่อนหน้านี้ (ต้องมาก่อน config จะครบ)
    # แต่เพิ่งมา log ตรงนี้เพื่อให้อยู่ในรูป JSON เหมือน event อื่น (ADR 0011)
    # **log ได้แค่ชื่อแหล่ง ห้าม log ค่าที่ได้มาไม่ว่ากรณีใด** (ADR 0030)
    app.logger.info("secrets source ready", extra={"secrets_source": secrets_source(app)})
    # **ต้องมาก่อน `init_security_headers`** เพราะ Talisman ตัดสินใจ redirect ไป
    # https จาก `request.scheme` — ถ้า proxy เป็นคนจบ TLS แล้วเรายังไม่แปลง
    # `X-Forwarded-Proto` การเปิด HTTPS_ENABLED จะได้ redirect วนแทน (P5-11/P5-12)
    init_proxy_fix(app)
    init_security_headers(app)
    # **ต้องมาหลัง `init_logging`** เพราะใช้เวลาเริ่มต้นที่ `before_request` ของมัน
    # ตั้งไว้ — จับเวลาสองที่แปลว่ามีสองตัวเลขที่ต้องตรงกันตลอดไป
    init_metrics(app)

    db.init_app(app)
    # import เพื่อ **ผลข้างเคียง** อีกตัว — ตัวโมดูลผูก event ที่ทำให้ทุก write
    # ถูกบันทึกลง audit เอง และประกาศตาราง tdl_audit เข้า metadata
    # ต้อง import หลัง db ถูกสร้างแล้ว จึงอยู่ในนี้ไม่ใช่หัวไฟล์ (ดู app/audit.py)
    from app import audit  # noqa: F401

    # render_as_batch: SQLite ALTER TABLE ทำได้จำกัด ต้องให้ alembic สร้างตารางใหม่แทน
    migrate.init_app(app, db, render_as_batch=True)
    # คุมทุก POST/PUT/PATCH/DELETE ทั้งแอป ไม่ต้องไปใส่ทีละ route
    csrf.init_app(app)
    limiter.init_app(app)
    # โควตาที่นับแยกต่อ process = เพดานจริงเป็น N เท่าตามจำนวน worker
    # ให้ระบบพูดออกมาตอน start แทนที่จะเป็นความรู้ในหัวคนตั้ง config (P5-07)
    warn_if_counters_are_not_shared(app)
    login_manager.init_app(app)

    from app.i18n import select_locale

    babel.init_app(app, locale_selector=select_locale)

    @app.context_processor
    def inject_i18n():
        from flask_babel import get_locale

        from app.theme import (
            MODES,
            resolve_mode,
            select_mode,
            select_theme,
        )
        from app.theme import (
            themes as select_themes,
        )

        return {
            "current_locale": str(get_locale() or app.config["BABEL_DEFAULT_LOCALE"]),
            "languages": app.config["LANGUAGES"],
            # ธีมมาจากการค้นหา plugin ทุก request จะได้เห็นตัวที่เพิ่งวางลงไป
            "themes": select_themes(),
            "current_theme": select_theme(),
            # โหมดที่ผู้ใช้เลือก (อาจเป็น auto) กับโหมดที่ตัดสินแล้วว่าจะแสดงอะไร
            "current_mode": select_mode(),
            "resolved_mode": resolve_mode(),
            "modes": MODES,
        }

    @app.errorhandler(429)
    def too_many_requests(error):
        # **ต้องเช็ค path เองที่นี่ด้วย** ถึงจะมี `_errors_stay_in_their_own_language`
        # ของ app/api อยู่แล้ว — Flask ค้น error handler ด้วย **status code ก่อน**
        # แล้วค่อยไล่ scope ตัวนี้ที่ผูกกับเลข 429 ตรง ๆ จึงชนะทั้ง handler ของ
        # blueprint และ handler แบบ `HTTPException` ของ API เสมอ
        # ปล่อยไว้ = client ของ API ได้หน้า login เป็น HTML กลับไปตอนโดนกันโควตา
        # แล้ว JSON parser พังด้วยข้อความที่ไม่เกี่ยวกับสาเหตุจริงเลย (P5-08)
        from app.api import API_PREFIX
        from app.api.errors import http_error_response

        if request.path.startswith(API_PREFIX):
            return http_error_response(error)
        # หน้าเว็บ: คืนหน้า login พร้อมข้อความ ไม่ใช่หน้า error ดิบ ๆ แต่คง status ไว้
        return render_template("login.html", rate_limited=str(error.description)), 429

    from app.admin import bp as admin_bp
    from app.auth import bp as auth_bp
    from app.health import bp as health_bp
    from app.routes import bp as main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    # liveness/readiness (ADR 0048) — ไม่มี token ไม่มีข้อมูลภายใน ดู app/health.py
    app.register_blueprint(health_bp)

    # /api/v1 — ต้องมาหลัง csrf.init_app() เพราะตัวมันขอยกเว้น CSRF ให้ blueprint ของ API
    from app.api import init_api

    init_api(app)

    # ต้องมาหลัง init_api() เพราะด่านนี้ต้องรู้ path ของ API เพื่อ **ไม่** ไปยุ่งกับมัน
    from app.session_security import init_session_security

    init_session_security(app)

    from app.cli import register_cli

    register_cli(app)

    return app
