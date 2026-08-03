from pathlib import Path

from flask import Flask, render_template
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

# `db_engine` import ไว้เพื่อ **ผลข้างเคียง** — ตัวโมดูลผูก event listener ระดับ
# Engine ที่เปิดบังคับ foreign key ของ SQLite ต้องถูก import ก่อนมี connection แรก
# ถ้าลบบรรทัดนี้ FK จะไม่ถูกบังคับเลยโดยไม่มี error (tests/test_db_integrity.py ดักไว้)
from app import (
    db_engine,  # noqa: F401  — ดู app/db_engine.py
    plugins,
)
from app.logging_setup import init_logging
from app.security_headers import init_security_headers
from config import Config, check_secret_key

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
# lazy_gettext เพราะข้อความนี้ถูกกำหนดตอน import ซึ่งยังไม่มี request
# ให้แปลตอนเอาไปแสดงจริง ไม่ใช่ตอนประกาศ
login_manager.login_message = _l("Please sign in first")


@login_manager.user_loader
def load_user(user_id):
    from app.models import User

    return db.session.get(User, int(user_id))


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    check_secret_key(app.config.get("SECRET_KEY"))
    # ให้พังตั้งแต่ตอน start ถ้าโครงสร้าง plugin ไม่ถูกต้อง
    plugins.check_installation()

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    # ตั้ง log ก่อนอย่างอื่น จะได้เห็น log ของขั้นตอน init ที่เหลือด้วย
    init_logging(app)
    init_security_headers(app)

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
        # คืนหน้า login พร้อมข้อความ ไม่ใช่หน้า error ดิบ ๆ แต่คง status 429 ไว้
        return render_template("login.html", rate_limited=str(error.description)), 429

    from app.auth import bp as auth_bp
    from app.routes import bp as main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)

    # /api/v1 — ต้องมาหลัง csrf.init_app() เพราะตัวมันขอยกเว้น CSRF ให้ blueprint ของ API
    from app.api import init_api

    init_api(app)

    from app.cli import register_cli

    register_cli(app)

    return app
