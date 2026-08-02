import os

from flask import Flask, render_template
from flask_babel import Babel, lazy_gettext as _l
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

from config import Config, check_secret_key

db = SQLAlchemy()
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

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
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

        from app.theme import AUTO, CHOICES, select_theme

        return {
            "current_locale": str(get_locale() or app.config["BABEL_DEFAULT_LOCALE"]),
            "languages": app.config["LANGUAGES"],
            "current_theme": select_theme(),
            "theme_choices": CHOICES,
            "theme_auto": AUTO,
        }

    @app.errorhandler(429)
    def too_many_requests(error):
        # คืนหน้า login พร้อมข้อความ ไม่ใช่หน้า error ดิบ ๆ แต่คง status 429 ไว้
        return render_template("login.html", rate_limited=str(error.description)), 429

    from app.routes import bp as main_bp
    from app.auth import bp as auth_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)

    from app.cli import register_cli
    register_cli(app)

    return app
