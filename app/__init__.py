import os

from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from config import Config

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "กรุณาเข้าสู่ระบบก่อน"


@login_manager.user_loader
def load_user(user_id):
    from app.models import User

    return db.session.get(User, int(user_id))


def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    # render_as_batch: SQLite ALTER TABLE ทำได้จำกัด ต้องให้ alembic สร้างตารางใหม่แทน
    migrate.init_app(app, db, render_as_batch=True)
    login_manager.init_app(app)

    from app.routes import bp as main_bp
    from app.auth import bp as auth_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)

    from app.cli import register_cli
    register_cli(app)

    return app
