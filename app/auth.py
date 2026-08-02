from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import limiter
from app.models import User

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit(
    lambda: current_app.config["LOGIN_RATE_LIMIT"],
    methods=["POST"],
    # หักโควตาเฉพาะตอนล็อกอินไม่ผ่าน คนที่พิมพ์ถูกไม่โดนกัน
    deduct_when=lambda response: response.status_code == 401,
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
            flash("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
            return render_template("login.html"), 401
        login_user(user)
        return redirect(url_for("main.index"))

    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
