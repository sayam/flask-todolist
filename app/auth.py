"""login/logout และขั้นที่สองของการยืนยันตัวตน — blueprint `auth`

core รู้จักปัจจัยที่สองผ่าน `app/services/mfa.py` เท่านั้น (`is_enrolled` /
`verify`) และรู้จักปัจจัยหลักที่ไม่ใช่รหัสผ่านผ่าน `app/services/sso.py`
(`begin` / `finish`) **ไม่รู้จักชื่อ plugin ตัวไหนเลยแม้แต่ในคอมเมนต์**
— ดู ADR 0024 และ ADR 0028
"""

import hashlib
from http import HTTPStatus

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_babel import gettext as _
from flask_login import current_user, login_required
from sqlalchemy import select

from app import audit, db, limiter
from app.i18n import SESSION_KEY, is_supported
from app.models import User
from app.services import mfa, sso
from app.services.errors import ServiceError, ValidationError
from app.session_security import (
    begin_pending,
    clear_pending,
    end_session,
    pending_user_id,
    start_session,
)

bp = Blueprint("auth", __name__)


def _login_page():
    """หน้า login พร้อมรายชื่อผู้ให้บริการภายนอกที่ติดตั้งอยู่จริง

    **ส่งจาก view ไม่ใช่ context processor** เพราะการหาว่ามีปัจจัยหลักตัวไหน
    ติดตั้งอยู่ต้องอ่านดิสก์และถามฐานข้อมูลว่าตารางของ plugin มีจริงไหม —
    งานเท่านั้นไม่ควรเกิดกับทุกหน้าของทั้งเว็บเพียงเพราะหน้า login ต้องใช้
    """
    return render_template("login.html", sso_providers=sso.available())


def _failed_login(response):
    """หักโควตาเฉพาะตอนล็อกอินไม่ผ่าน คนที่พิมพ์ถูกไม่โดนกัน"""
    return response.status_code == HTTPStatus.UNAUTHORIZED


def username_bucket() -> str:
    """กุญแจของโควตาที่นับต่อชื่อผู้ใช้ (Phase 4 — ปิดช่องที่ค้างไว้ตั้งแต่ Phase 0)

    โควตาต่อ IP กันคนยิงจากที่เดียวได้ แต่ไม่กันคนที่เปลี่ยน IP ไปเรื่อย ๆ
    ซึ่งเป็นวิธีที่ botnet ใช้จริง — ตัวนี้จึงนับตาม "บัญชีที่ถูกยิง" แทน

    **เก็บเป็น hash ไม่ใช่ชื่อดิบ** เพราะกุญแจนี้จะไปอยู่ใน storage ของ
    rate limiter (วันหนึ่งคือ redis ที่ใช้ร่วมกัน — ROADMAP ข้อ 4.3)
    ชื่อผู้ใช้เป็นชั้น C2 ไม่ควรไปนอนอยู่ในระบบที่ไม่ได้ออกแบบมาเก็บ PII

    normalize ด้วย casefold ก่อน hash ไม่งั้นคนยิงแค่สลับตัวพิมพ์ใหญ่เล็ก
    ก็ได้โควตาใหม่ทั้งชุด (`Tester` กับ `tester` คือบัญชีเดียวกันในสายตาคนยิง)
    """
    raw = (request.form.get("username") or "").strip().casefold()
    return "login-user:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit(
    lambda: current_app.config["LOGIN_RATE_LIMIT"],
    methods=["POST"],
    deduct_when=_failed_login,
)
@limiter.limit(
    lambda: current_app.config["LOGIN_USERNAME_RATE_LIMIT"],
    methods=["POST"],
    key_func=username_bucket,
    deduct_when=_failed_login,
)
def login():
    """หน้า login — บัญชีที่เปิดปัจจัยที่สองไว้จะหยุดครึ่งทางที่ `/login/verify`

    ยังไม่เรียก `login_user()` ในขั้นนี้ ไม่งั้นคนที่รู้แค่รหัสผ่านเข้าถึงข้อมูล
    ได้ทันทีด้วยการพิมพ์ URL อื่น (ADR 0024)
    """
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.session.scalars(select(User).where(User.username == username)).first()
        # ไม่แยกว่า user ผิดหรือรหัสผิด กัน username enumeration
        if user is None or not user.check_password(password):
            # **ห้ามบันทึก username ที่กรอกมา** เป็นชั้น C2 และเป็นของคนนอกด้วยซ้ำ
            # บันทึกได้แค่ว่าเป้าหมายเป็นบัญชีไหน (เลข = C4) หรือไม่มีอยู่จริง
            audit.record(
                "auth.login_failed", table_name="tdl_user", row_id=user.id if user else None
            )
            db.session.commit()
            flash(_("Incorrect username or password"))
            return _login_page(), 401
        # รหัสผ่านถูกแล้วก็จริง แต่ถ้ามีปัจจัยที่สองต้องหยุดไว้ครึ่งทางก่อน
        # **ห้ามเรียก start_session() ตรงนี้** ไม่งั้นคนที่รู้แค่รหัสผ่านเข้าถึง
        # ข้อมูลได้ทันที = มี MFA ไว้เฉย ๆ โดยไม่ได้บังคับอะไรเลย
        if mfa.is_required(user):
            begin_pending(user, current_app.config["MFA_PENDING_SECONDS"])
            audit.record("auth.mfa_pending", table_name="tdl_user", row_id=user.id)
            db.session.commit()
            return redirect(url_for("auth.verify"))

        _complete_login(user)
        return redirect(url_for("main.index"))

    return _login_page()


def _complete_login(user):
    """ขั้นตอนที่เหมือนกันทั้งทางที่มี MFA และไม่มี — ต้องมีที่เดียว

    แยกออกมาเพราะถ้าก๊อปสองที่ วันหนึ่งจะมีทางเดียวที่ได้ของใหม่ (เช่นการ
    บันทึกภาษา) แล้วอีกทางเงียบหายไปโดยไม่มีอะไรฟ้อง
    """
    # ล้าง session เก่าทิ้งก่อนเขียนของใหม่ (session fixation — ดู ADR 0020)
    # ไม่ใช่ `login_user()` เปล่า ๆ ซึ่งเขียนทับเฉพาะคีย์ของตัวเอง
    chosen = session_language()
    start_session(user)
    # record หลัง login เพื่อให้ actor_id เป็นคนที่เพิ่งเข้ามา ไม่ใช่ค่าว่าง
    audit.record("auth.login", table_name="tdl_user", row_id=user.id)
    # ภาษาที่เลือกไว้ก่อน login ถือว่าเป็นความตั้งใจล่าสุด เก็บลงโปรไฟล์เลย
    if chosen and chosen != user.locale:
        user.locale = chosen
    db.session.commit()


# ---------------------------------------------------- ปัจจัยหลักที่ไม่ใช่รหัสผ่าน
# คีย์ของ session ที่เก็บของฝากระหว่างทางไป IdP — core **ไม่ตีความข้างใน**
# มันเป็น state/nonce/PKCE ของ plugin ซึ่งเป็นรายละเอียดของโพรโทคอลที่ core ไม่ควรรู้
SSO_PENDING_KEY = "_sso_pending"
SSO_PROVIDER_KEY = "_sso_provider"


def _callback_url(key):
    """URL ที่ IdP จะส่งผู้ใช้กลับมา — **ประกอบจาก config ไม่ใช่จาก header `Host`**

    `url_for(..., _external=True)` สร้าง URL จาก `Host` ของคำขอ ซึ่งคนยิงตั้งเองได้
    (semgrep จับข้อนี้ให้) ผลคือ redirect_uri ที่ส่งให้ IdP ชี้ไปโดเมนของคนอื่นได้
    — ในทางปฏิบัติ IdP ที่ตั้งค่าถูกจะปฏิเสธเพราะไม่ตรงรายการที่ลงทะเบียนไว้
    แต่การพึ่งการตั้งค่าที่ *ปลายทาง* ไม่ใช่การป้องกันที่ฝั่งเรา

    **ไม่มีค่าเริ่มต้นให้เดา** — redirect_uri ต้องตรงเป๊ะกับที่ลงทะเบียนไว้ที่ IdP
    อยู่แล้ว ผู้ดูแลจึงรู้ค่านี้แน่นอน ส่วนการเดาจาก request แปลว่าวันที่เดาผิด
    จะได้ข้อความจาก IdP ว่า redirect_uri ไม่ถูกต้อง ซึ่งชี้ไปผิดที่
    """
    base = current_app.config.get("EXTERNAL_URL", "")
    if not base:
        raise ValidationError(_("Single sign-on is not configured"), code="sso_no_external_url")
    return f"{base}{url_for('auth.sso_callback', key=key)}"


@bp.route("/login/sso/<path:key>")
def sso_begin(key):
    """ส่งผู้ใช้ไปยืนยันตัวตนที่ผู้ให้บริการภายนอก

    เป็น GET เพราะเป็นการเดินทางออกไป ไม่ใช่การส่งข้อมูล — ตัวที่กัน CSRF ของ
    ขากลับคือ `state` ที่ plugin สร้างและเราเก็บไว้ใน session (ADR 0028)
    """
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    try:
        plugin = sso.find(key)
        target, pending = sso.begin(plugin, _callback_url(key))
    except ServiceError as error:
        flash(error.message)
        return _login_page(), HTTPStatus.BAD_REQUEST
    session[SSO_PENDING_KEY] = pending
    session[SSO_PROVIDER_KEY] = key
    return redirect(target)


@bp.route("/login/sso/<path:key>/callback")
def sso_callback(key):
    """ผู้ใช้กลับมาจากผู้ให้บริการแล้ว

    **ของฝากถูกใช้ได้ครั้งเดียว** (`pop`) ไม่ว่าจะสำเร็จหรือไม่ — ปล่อยค้างไว้
    แปลว่า code หรือ state ชุดเดิมถูกยิงซ้ำได้เรื่อย ๆ
    """
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    pending = session.pop(SSO_PENDING_KEY, None)
    started_with = session.pop(SSO_PROVIDER_KEY, None)
    try:
        plugin = sso.find(key)
        if pending is None or started_with != key:
            # ไม่ได้เริ่มจากที่นี่ หรือเริ่มกับผู้ให้บริการคนละเจ้า
            raise ValidationError(
                _("Sign-in session expired — please try again"), code="sso_no_pending"
            )
        user = sso.finish(plugin, request.args.to_dict(), pending)
    except ServiceError as error:
        # **ไม่บันทึกค่าที่ผู้ใช้/IdP ส่งมา** ด้วยเหตุผลเดียวกับ login ที่ผิดรหัส
        audit.record("auth.sso_failed", table_name="tdl_user", row_id=None)
        db.session.commit()
        flash(error.message)
        return _login_page(), HTTPStatus.UNAUTHORIZED

    # **ด่านที่เหลือเหมือนทางรหัสผ่านเป๊ะ** รวมทั้งปัจจัยที่สอง (ADR 0028 ข้อ 6)
    # ปัจจัยที่สองเป็นของแอป ไม่ใช่ของ IdP — ใครที่เปิดไว้ยังต้องผ่านมัน
    if mfa.is_required(user):
        begin_pending(user, current_app.config["MFA_PENDING_SECONDS"])
        audit.record("auth.mfa_pending", table_name="tdl_user", row_id=user.id)
        db.session.commit()
        return redirect(url_for("auth.verify"))

    _complete_login(user)
    return redirect(url_for("main.index"))


def pending_bucket() -> str:
    """กุญแจโควตาของขั้นที่สอง — นับตามบัญชีที่กำลังถูกยิง ไม่ใช่ตาม IP

    รหัสจากแอป authenticator มีแค่หกหลัก การไล่เดาจึงเป็นไปได้จริงถ้าไม่มีเพดาน
    (ไม่มีชื่อผู้ใช้ให้ hash ตรงนี้ ใช้เลข id ที่อยู่ใน session แทน)
    """
    return f"mfa-user:{pending_user_id() or 0}"


@bp.route("/login/verify", methods=["GET", "POST"])
@limiter.limit(
    lambda: current_app.config["LOGIN_USERNAME_RATE_LIMIT"],
    methods=["POST"],
    key_func=pending_bucket,
    deduct_when=_failed_login,
)
def verify():
    """ขั้นที่สองของ login — มาถึงได้เฉพาะคนที่ผ่านรหัสผ่านมาแล้ว"""
    user_id = pending_user_id()
    if user_id is None:
        # หมดเวลาหรือเข้ามาตรง ๆ — กลับไปเริ่มใหม่ ไม่บอกว่ามีสถานะอะไรค้างอยู่
        return redirect(url_for("auth.login"))

    user = db.session.get(User, user_id)
    if user is None:
        clear_pending()
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        if not mfa.verify(user, request.form.get("code", "")):
            audit.record("auth.mfa_failed", table_name="tdl_user", row_id=user.id)
            db.session.commit()
            flash(_("That code is not valid"))
            return render_template("login_verify.html"), 401

        clear_pending()
        _complete_login(user)
        return redirect(url_for("main.index"))

    return render_template("login_verify.html")


def session_language():
    """ภาษาที่ผู้ใช้กดสลับไว้ใน session (None ถ้ายังไม่เคยกด หรือค่าที่ค้างอยู่เลิกรองรับแล้ว)"""
    from flask import session

    value = session.get(SESSION_KEY)
    return value if is_supported(value) else None


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """ออกจากระบบ — บันทึก audit ก่อนล้าง session เสมอ"""
    # ต้องบันทึกก่อน end_session() ไม่งั้น actor_id กลายเป็นค่าว่างเพราะไม่มีใคร login แล้ว
    audit.record("auth.logout", table_name="tdl_user", row_id=current_user.id)
    db.session.commit()
    end_session()
    return redirect(url_for("auth.login"))
