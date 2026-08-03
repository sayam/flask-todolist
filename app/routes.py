"""view ของฝั่ง HTML — **adapter บาง ๆ เท่านั้น** (Phase 3 — ดู ADR 0016)

หน้าที่ของไฟล์นี้มีสามอย่าง: อ่าน request, เรียก service, แล้วเลือกว่าจะ
render อะไร/เด้งไปไหน/flash อะไร ตรรกะว่าอะไรถูกอะไรผิดอยู่ใน `app/services/`
ทั้งหมด เพื่อให้ `/api/v1` เรียกตรรกะชุดเดียวกันได้โดยไม่ต้องก๊อป

การแปลงความล้มเหลวเป็นภาษา HTTP เขียนไว้ตรง ๆ ทุกจุดโดยตั้งใจ ไม่ทำเป็น
decorator กลาง เพราะแต่ละหน้าเด้งกลับคนละที่เมื่อมีข้อผิดพลาด
"""

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from flask_babel import gettext as _
from flask_login import current_user, login_required

from app import plugins, tz
from app.filters import UPCOMING_CHOICES, FilterSpec
from app.i18n import SESSION_KEY, is_supported
from app.services import NotFoundError, ServiceError, ValidationError
from app.services import categories as categories_service
from app.services import settings as settings_service
from app.services import todos as todos_service
from app.theme import (
    MODE_SESSION_KEY,
    THEME_SESSION_KEY,
    mode_is_supported,
)

bp = Blueprint("main", __name__)

SHOW_START_KEY = "show_start"


def _safe_referrer():
    """path ของหน้าก่อนหน้า รับเฉพาะที่อยู่ในเว็บเรา ไม่งั้นเป็น open redirect"""
    target = request.referrer or ""
    if not target.startswith(request.host_url):
        return url_for("main.index")
    path = target[len(request.host_url) :]
    if not path or path.startswith("/"):
        return url_for("main.index")
    return "/" + path


def _form_datetime(field):
    """ค่าจาก `<input type="datetime-local">` เป็น datetime ท้องถิ่นแบบ naive

    browser ส่งรูปแบบถูกเสมอ แต่คนยิง POST ตรง ๆ ส่งอะไรมาก็ได้ — รูปแบบที่
    ย่อยไม่ได้ถูกแปลงเป็น `ValidationError` เพื่อให้ทางเดินของข้อผิดพลาด
    เหมือนกับที่มาจาก service ไม่ต้องมีทางที่สอง
    """
    try:
        return tz.parse_naive(request.form.get(field))
    except ValueError as bad:
        raise ValidationError(_("Invalid date format"), code="date_invalid", field=field) from bad


def _todo_fields():
    """ฟิลด์ของงานจากฟอร์ม — ฟอร์ม HTML ส่งมาครบทุกช่องเสมอ (ต่างจาก PATCH ของ API)"""
    return {
        "title": request.form.get("title", ""),
        "category_id": request.form.get("category_id"),
        "start_date": _form_datetime("start_date"),
        "due_date": _form_datetime("due_date"),
    }


@bp.route("/")
@login_required
def index():
    try:
        spec = FilterSpec.from_params(request.args)
    except ValueError:
        # วันที่ที่ย่อยไม่ได้ ให้แสดงทุกงานแทนที่จะแสดงผลลัพธ์ที่ตีความไปเอง
        flash(_("Invalid date format"))
        spec = FilterSpec.from_params(request.args, ignore_dates=True)

    try:
        todos = todos_service.list_todos(current_user, spec)
    except NotFoundError:
        abort(404)

    # ติ๊กว่าจะโชว์วันเริ่มในลิสต์ไหม จำไว้ใน session จะได้ไม่ต้องติ๊กใหม่ทุกครั้ง
    # ต้องมี marker เพราะ checkbox ที่ไม่ติ๊กจะไม่ถูกส่งมาเลย แยกไม่ออกจาก
    # การกดลิงก์ตัวกรองอื่นที่ไม่ได้ส่ง show_start มาด้วย
    if request.args.get("filters_submitted"):
        # เทียบค่า "1" ตรง ๆ (ค่าที่ checkbox ส่ง) แทน bool() ครอบ user input
        session[SHOW_START_KEY] = request.args.get(SHOW_START_KEY) == "1"

    return render_template(
        "index.html",
        todos=todos,
        categories=categories_service.list_categories(current_user),
        status=spec.status,
        category_arg=spec.category,
        selected_category=int(spec.category) if spec.category.isdigit() else None,
        when=spec.when,
        within=spec.within,
        upcoming_choices=UPCOMING_CHOICES,
        range_from=(request.args.get("date_from") or "").strip(),
        range_to=(request.args.get("date_to") or "").strip(),
        show_start=bool(session.get(SHOW_START_KEY)),
    )


@bp.route("/add", methods=["POST"])
@login_required
def add():
    try:
        todos_service.create_todo(current_user, **_todo_fields())
    except NotFoundError:
        abort(404)
    except ServiceError as error:
        flash(error.message)
    return redirect(url_for("main.index"))


@bp.route("/edit/<int:todo_id>", methods=["GET", "POST"])
@login_required
def edit(todo_id):
    """หน้าแก้งาน — แยกออกมาจากลิสต์เพราะมีทั้งชื่อ วันเริ่ม และกำหนดส่ง
    ใส่ครบในแถวเดียวแล้วอ่านไม่ออก"""
    if request.method == "GET":
        try:
            todo = todos_service.get_todo(current_user, todo_id)
        except NotFoundError:
            abort(404)
        return render_template(
            "edit_todo.html",
            todo=todo,
            categories=categories_service.list_categories(current_user),
        )

    try:
        todos_service.update_todo(current_user, todo_id, _todo_fields())
    except NotFoundError:
        abort(404)
    except ServiceError as error:
        flash(error.message)
        return redirect(url_for("main.edit", todo_id=todo_id))

    flash(_("Task saved"))
    return redirect(url_for("main.index"))


@bp.route("/toggle/<int:todo_id>", methods=["POST"])
@login_required
def toggle(todo_id):
    try:
        todos_service.toggle_todo(current_user, todo_id)
    except NotFoundError:
        abort(404)
    return redirect(url_for("main.index"))


@bp.route("/delete/<int:todo_id>", methods=["POST"])
@login_required
def delete(todo_id):
    try:
        todos_service.delete_todo(current_user, todo_id)
    except NotFoundError:
        abort(404)
    return redirect(url_for("main.index"))


@bp.route("/clear-completed", methods=["POST"])
@login_required
def clear_completed():
    todos_service.clear_completed(current_user)
    return redirect(url_for("main.index"))


@bp.route("/categories")
@login_required
def categories():
    return render_template(
        "categories.html",
        categories=categories_service.list_categories(current_user),
    )


@bp.route("/categories/add", methods=["POST"])
@login_required
def add_category():
    try:
        categories_service.create_category(current_user, request.form.get("name"))
    except ServiceError as error:
        flash(error.message)
    return redirect(url_for("main.categories"))


@bp.route("/categories/edit/<int:category_id>", methods=["POST"])
@login_required
def edit_category(category_id):
    try:
        categories_service.rename_category(current_user, category_id, request.form.get("name"))
    except NotFoundError:
        abort(404)
    except ServiceError as error:
        flash(error.message)
    return redirect(url_for("main.categories"))


@bp.route("/categories/delete/<int:category_id>", methods=["POST"])
@login_required
def delete_category(category_id):
    try:
        categories_service.delete_category(current_user, category_id)
    except NotFoundError:
        abort(404)
    except ServiceError as error:
        # ลบหมวดที่ยังมีงานอยู่ไม่ได้ — ปุ่มถูก disable ไว้แล้ว แต่การกันจริงอยู่ที่นี่
        flash(error.message)
    return redirect(url_for("main.categories"))


@bp.route("/lang/<code>")
def set_language(code):
    """สลับภาษา แล้วกลับไปหน้าเดิม

    ใช้ GET เพราะเป็นลิงก์ในเมนู และเปลี่ยนแค่การแสดงผล ไม่ได้แก้ข้อมูลงาน
    ไม่ต้อง login เพราะหน้า login เองก็ต้องสลับภาษาได้
    """
    if not is_supported(code):
        abort(404)

    session[SESSION_KEY] = code
    if current_user.is_authenticated:
        settings_service.save_locale(current_user, code)

    return redirect(_safe_referrer())


@bp.route("/mode/<value>")
def set_mode(value):
    """สลับโหมดสว่าง/มืด/อัตโนมัติ แล้วกลับไปหน้าเดิม

    ใช้จากหน้า login ซึ่งเข้า settings ไม่ได้ จึงไม่บังคับ login
    """
    if not mode_is_supported(value):
        abort(404)

    session[MODE_SESSION_KEY] = value
    if current_user.is_authenticated:
        settings_service.save_mode(current_user, value)

    return redirect(_safe_referrer())


# --- ตั้งค่า ---


@bp.route("/settings")
@login_required
def settings():
    return render_template(
        "settings.html",
        timezones=tz.all_timezones(),
        current_timezone=current_user.timezone_name or tz.default_name(),
    )


@bp.route("/settings/profile", methods=["POST"])
@login_required
def save_profile():
    """แก้ชื่อ-นามสกุล — username เป็นตัวระบุตอน login จึงแก้ที่นี่ไม่ได้"""
    settings_service.save_profile(
        current_user,
        request.form.get("first_name"),
        request.form.get("last_name"),
    )
    flash(_("Profile saved"))
    return redirect(url_for("main.settings"))


@bp.route("/settings/preferences", methods=["POST"])
@login_required
def save_preferences():
    """ภาษา ธีม และ timezone อยู่ในฟอร์มเดียวกัน บันทึกทีเดียวจบ"""
    try:
        settings_service.save_preferences(
            current_user,
            locale=request.form.get("locale"),
            theme=request.form.get("theme"),
            mode=request.form.get("mode"),
            timezone_name=request.form.get("timezone"),
        )
    except ServiceError as error:
        flash(error.message)
        return redirect(url_for("main.settings"))

    # session ชนะโปรไฟล์ในลำดับการเลือก ต้องอัปเดตด้วยไม่งั้นค่าที่เพิ่งบันทึกจะไม่มีผล
    session[SESSION_KEY] = current_user.locale
    session[THEME_SESSION_KEY] = current_user.theme
    session[MODE_SESSION_KEY] = current_user.mode

    flash(_("Settings saved"))
    return redirect(url_for("main.settings"))


@bp.route("/plugin/themes/<theme_id>/style.css")
def theme_stylesheet(theme_id):
    """เสิร์ฟ stylesheet ของธีม

    ไม่ต้อง login เพราะหน้า login ก็ต้องใช้ และเป็นไฟล์สาธารณะอยู่แล้ว
    theme_id ถูกตรวจกับรายการที่ค้นเจอจริงก่อน จึงไม่มีทาง traverse ออกนอก
    """
    theme = plugins.get_theme(theme_id)
    if theme is None or not theme.stylesheet:
        abort(404)
    return send_from_directory(theme.directory, theme.stylesheet, mimetype="text/css")
