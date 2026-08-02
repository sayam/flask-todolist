from http import HTTPStatus

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_babel import gettext as _
from flask_login import current_user, login_required, login_user, logout_user

from app import db, limiter
from app.i18n import SESSION_KEY, is_supported
from app.models import User

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit(
    lambda: current_app.config["LOGIN_RATE_LIMIT"],
    methods=["POST"],
    # หักโควตาเฉพาะตอนล็อกอินไม่ผ่าน คนที่พิมพ์ถูกไม่โดนกัน
    deduct_when=lambda response: response.status_code == HTTPStatus.UNAUTHORIZED,
)
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        # ไม่แยกว่า user ผิดหรือรหัสผิด กัน username enumeration
        if user is None or not user.check_password(password):
            flash(_("Incorrect username or password"))
            return render_template("login.html"), 401
        login_user(user)
        # ภาษาที่เลือกไว้ก่อน login ถือว่าเป็นความตั้งใจล่าสุด เก็บลงโปรไฟล์เลย
        chosen = session_language()
        if chosen and chosen != user.locale:
            user.locale = chosen
            db.session.commit()
        return redirect(url_for("main.index"))

    return render_template("login.html")


def session_language():
    from flask import session

    value = session.get(SESSION_KEY)
    return value if is_supported(value) else None


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
