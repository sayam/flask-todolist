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

from app import audit, db, limiter
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
            # **ห้ามบันทึก username ที่กรอกมา** เป็นชั้น C2 และเป็นของคนนอกด้วยซ้ำ
            # บันทึกได้แค่ว่าเป้าหมายเป็นบัญชีไหน (เลข = C4) หรือไม่มีอยู่จริง
            audit.record(
                "auth.login_failed", table_name="tdl_user", row_id=user.id if user else None
            )
            db.session.commit()
            flash(_("Incorrect username or password"))
            return render_template("login.html"), 401
        login_user(user)
        # record หลัง login_user เพื่อให้ actor_id เป็นคนที่เพิ่งเข้ามา ไม่ใช่ค่าว่าง
        audit.record("auth.login", table_name="tdl_user", row_id=user.id)
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
    # ต้องบันทึกก่อน logout_user() ไม่งั้น actor_id กลายเป็นค่าว่างเพราะไม่มีใคร login แล้ว
    audit.record("auth.logout", table_name="tdl_user", row_id=current_user.id)
    db.session.commit()
    logout_user()
    return redirect(url_for("auth.login"))
