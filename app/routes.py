from datetime import date, datetime

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
from flask_babel import gettext as _, ngettext
from flask_login import current_user, login_required

from app import db, plugins, tz
from app.filters import (
    DEFAULT_UPCOMING,
    STATUS_FILTERS,
    UPCOMING_CHOICES,
    WHEN_FILTERS,
    apply_when,
    normalise_status,
    normalise_when,
    normalise_within,
    parse_boundary,
)
from app.filters import DAY_END, DAY_START
from app.i18n import SESSION_KEY, is_supported
from app.theme import (
    MODE_SESSION_KEY,
    THEME_SESSION_KEY,
    mode_is_supported,
    theme_is_supported,
)
from app.models import Category, Todo

bp = Blueprint("main", __name__)

SHOW_START_KEY = "show_start"


def _owned_todo(todo_id):
    """ดึง todo ที่เป็นของ current_user เท่านั้น — ของคนอื่นตอบ 404 ไม่ใช่ 403
    เพื่อไม่ให้รู้ว่า id นั้นมีอยู่จริง"""
    todo = db.session.get(Todo, todo_id)
    if todo is None or todo.user_id != current_user.id:
        abort(404)
    return todo


def _owned_category(category_id):
    category = db.session.get(Category, category_id)
    if category is None or category.user_id != current_user.id:
        abort(404)
    return category


def _resolve_category_id(raw):
    """แปลงค่า category จาก form เป็น id ที่ยืนยันแล้วว่าเป็นของ current_user"""
    if not raw:
        return None
    return _owned_category(int(raw)).id


def _parse_due_date(raw):
    """แปลงค่าจาก <input type="datetime-local"> เป็น datetime แบบ naive UTC

    คืน None ถ้าเว้นว่าง และ raise ValueError ถ้ารูปแบบใช้ไม่ได้
    (browser ส่งมาถูกเสมอ แต่คนยิง POST ตรง ๆ ส่งอะไรมาก็ได้)

    รับ "YYYY-MM-DD" เปล่า ๆ ด้วย โดยถือว่าเป็นเที่ยงคืนของวันนั้น —
    เผื่อ client เก่าหรือคนยิง API ที่ยังส่งแค่วัน
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is not None:
        raise ValueError("ไม่รับ timezone offset — ใช้เวลาท้องถิ่นเท่านั้น")
    # ค่าที่ได้เป็นเวลาท้องถิ่นของผู้ใช้ แปลงเป็น UTC ก่อนส่งไปเก็บ
    return tz.to_utc(parsed, current_user.timezone_name)


def _safe_referrer():
    """path ของหน้าก่อนหน้า รับเฉพาะที่อยู่ในเว็บเรา ไม่งั้นเป็น open redirect"""
    target = request.referrer or ""
    if not target.startswith(request.host_url):
        return url_for("main.index")
    path = target[len(request.host_url) :]
    if not path or path.startswith("/"):
        return url_for("main.index")
    return "/" + path


@bp.route("/")
@login_required
def index():
    status = normalise_status(request.args.get("status", "all"))

    query = Todo.query.filter_by(user_id=current_user.id)
    if status == "active":
        query = query.filter_by(done=False)
    elif status == "completed":
        query = query.filter_by(done=True)

    # ตัวกรองหมวด: "none" = เฉพาะงานที่ไม่มีหมวด, ตัวเลข = id ของหมวด
    category_arg = (request.args.get("category") or "").strip()
    selected_category = None
    if category_arg == "none":
        query = query.filter(Todo.category_id.is_(None))
    elif category_arg.isdigit():
        selected_category = _owned_category(int(category_arg)).id
        query = query.filter_by(category_id=selected_category)
    else:
        category_arg = ""

    # ตัวกรองตามวัน (ดูจาก due_date)
    when = normalise_when(request.args.get("when", "all"))
    within = normalise_within(request.args.get("within"))
    range_from_raw = (request.args.get("date_from") or "").strip()
    range_to_raw = (request.args.get("date_to") or "").strip()
    try:
        range_from = parse_boundary(range_from_raw, DAY_START)
        range_to = parse_boundary(range_to_raw, DAY_END)
    except ValueError:
        flash(_("Invalid date format"))
        range_from = range_to = None
        when = "all"

    query = apply_when(
        query, Todo, when, within, range_from, range_to, current_user.timezone_name
    )

    # ติ๊กว่าจะโชว์วันเริ่มในลิสต์ไหม จำไว้ใน session จะได้ไม่ต้องติ๊กใหม่ทุกครั้ง
    # ต้องมี marker เพราะ checkbox ที่ไม่ติ๊กจะไม่ถูกส่งมาเลย แยกไม่ออกจาก
    # การกดลิงก์ตัวกรองอื่นที่ไม่ได้ส่ง show_start มาด้วย
    if request.args.get("filters_submitted"):
        session[SHOW_START_KEY] = bool(request.args.get(SHOW_START_KEY))
    show_start = bool(session.get(SHOW_START_KEY))

    todos = query.order_by(
        # งานที่มีกำหนดส่งขึ้นก่อน เรียงจากใกล้ครบกำหนดสุด
        # is_(None) ให้ False(0) มาก่อน True(1) เวลาเรียงจากน้อยไปมาก
        Todo.due_date.is_(None),
        Todo.due_date.asc(),
        Todo.created_at.desc(),
    ).all()

    categories = (
        Category.query.filter_by(user_id=current_user.id)
        .order_by(Category.name)
        .all()
    )
    return render_template(
        "index.html",
        todos=todos,
        categories=categories,
        status=status,
        category_arg=category_arg,
        selected_category=selected_category,
        when=when,
        within=within,
        upcoming_choices=UPCOMING_CHOICES,
        range_from=range_from_raw,
        range_to=range_to_raw,
        show_start=show_start,
    )


@bp.route("/add", methods=["POST"])
@login_required
def add():
    title = request.form.get("title", "").strip()
    if not title:
        flash(_("Please enter a task name"))
        return redirect(url_for("main.index"))
    try:
        start_date = _parse_due_date(request.form.get("start_date"))
        due_date = _parse_due_date(request.form.get("due_date"))
    except ValueError:
        flash(_("Invalid date format"))
        return redirect(url_for("main.index"))
    db.session.add(
        Todo(
            title=title,
            user_id=current_user.id,
            category_id=_resolve_category_id(request.form.get("category_id")),
            start_date=start_date,
            due_date=due_date,
        )
    )
    db.session.commit()
    return redirect(url_for("main.index"))


@bp.route("/edit/<int:todo_id>", methods=["GET", "POST"])
@login_required
def edit(todo_id):
    """หน้าแก้งาน — แยกออกมาจากลิสต์เพราะมีทั้งชื่อ วันเริ่ม และกำหนดส่ง
    ใส่ครบในแถวเดียวแล้วอ่านไม่ออก"""
    todo = _owned_todo(todo_id)
    if request.method == "GET":
        categories = (
            Category.query.filter_by(user_id=current_user.id)
            .order_by(Category.name)
            .all()
        )
        return render_template("edit_todo.html", todo=todo, categories=categories)

    title = request.form.get("title", "").strip()
    if not title:
        flash(_("Task name cannot be empty"))
        return redirect(url_for("main.edit", todo_id=todo.id))
    try:
        start_date = _parse_due_date(request.form.get("start_date"))
        due_date = _parse_due_date(request.form.get("due_date"))
    except ValueError:
        flash(_("Invalid date format"))
        return redirect(url_for("main.edit", todo_id=todo.id))

    todo.title = title
    todo.category_id = _resolve_category_id(request.form.get("category_id"))
    todo.start_date = start_date
    todo.due_date = due_date
    db.session.commit()
    flash(_("Task saved"))
    return redirect(url_for("main.index"))


@bp.route("/toggle/<int:todo_id>", methods=["POST"])
@login_required
def toggle(todo_id):
    todo = _owned_todo(todo_id)
    todo.done = not todo.done
    db.session.commit()
    return redirect(url_for("main.index"))


@bp.route("/delete/<int:todo_id>", methods=["POST"])
@login_required
def delete(todo_id):
    db.session.delete(_owned_todo(todo_id))
    db.session.commit()
    return redirect(url_for("main.index"))


@bp.route("/clear-completed", methods=["POST"])
@login_required
def clear_completed():
    Todo.query.filter_by(user_id=current_user.id, done=True).delete()
    db.session.commit()
    return redirect(url_for("main.index"))


@bp.route("/categories")
@login_required
def categories():
    items = (
        Category.query.filter_by(user_id=current_user.id)
        .order_by(Category.name)
        .all()
    )
    return render_template("categories.html", categories=items)


@bp.route("/categories/add", methods=["POST"])
@login_required
def add_category():
    name = request.form.get("name", "").strip()
    if not name:
        flash(_("Please enter a category name"))
    elif Category.query.filter_by(user_id=current_user.id, name=name).first():
        flash(_("Category “%(name)s” already exists", name=name))
    else:
        db.session.add(Category(name=name, user_id=current_user.id))
        db.session.commit()
    return redirect(url_for("main.categories"))


@bp.route("/categories/edit/<int:category_id>", methods=["POST"])
@login_required
def edit_category(category_id):
    category = _owned_category(category_id)
    name = request.form.get("name", "").strip()
    if not name:
        flash(_("Category name cannot be empty"))
    elif (
        Category.query.filter_by(user_id=current_user.id, name=name)
        .filter(Category.id != category.id)
        .first()
    ):
        flash(_("Category “%(name)s” already exists", name=name))
    else:
        category.name = name
        db.session.commit()
    return redirect(url_for("main.categories"))


@bp.route("/categories/delete/<int:category_id>", methods=["POST"])
@login_required
def delete_category(category_id):
    category = _owned_category(category_id)
    # ลบได้เฉพาะหมวดที่ว่างเปล่า — งานที่ทำเสร็จแล้วก็ยังนับ
    # เพราะมันคือประวัติที่ผู้ใช้ยังเห็นอยู่ในตัวกรอง "เสร็จแล้ว"
    remaining = Todo.query.filter_by(category_id=category.id).count()
    if remaining:
        flash(
            ngettext(
                "Cannot delete “%(name)s” — it still has %(num)d task.",
                "Cannot delete “%(name)s” — it still has %(num)d tasks.",
                remaining,
                name=category.name,
            )
        )
        return redirect(url_for("main.categories"))

    db.session.delete(category)
    db.session.commit()
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
        current_user.locale = code
        db.session.commit()

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
        current_user.mode = value
        db.session.commit()

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
    current_user.first_name = (request.form.get("first_name") or "").strip() or None
    current_user.last_name = (request.form.get("last_name") or "").strip() or None
    db.session.commit()
    flash(_("Profile saved"))
    return redirect(url_for("main.settings"))


@bp.route("/settings/preferences", methods=["POST"])
@login_required
def save_preferences():
    """ภาษา ธีม และ timezone อยู่ในฟอร์มเดียวกัน บันทึกทีเดียวจบ"""
    lang = request.form.get("locale")
    if not is_supported(lang):
        flash(_("Unsupported language"))
        return redirect(url_for("main.settings"))

    theme_value = request.form.get("theme")
    if not theme_is_supported(theme_value):
        flash(_("Unsupported theme"))
        return redirect(url_for("main.settings"))

    mode_value = request.form.get("mode")
    if not mode_is_supported(mode_value):
        flash(_("Unsupported mode"))
        return redirect(url_for("main.settings"))

    tz_name = request.form.get("timezone")
    if not tz.is_supported(tz_name):
        flash(_("Unsupported timezone"))
        return redirect(url_for("main.settings"))

    current_user.locale = lang
    current_user.theme = theme_value
    current_user.mode = mode_value
    current_user.timezone_name = tz_name
    db.session.commit()

    # session ชนะโปรไฟล์ในลำดับการเลือก ต้องอัปเดตด้วยไม่งั้นค่าที่เพิ่งบันทึกจะไม่มีผล
    session[SESSION_KEY] = lang
    session[THEME_SESSION_KEY] = theme_value
    session[MODE_SESSION_KEY] = mode_value

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
