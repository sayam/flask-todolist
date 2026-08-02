from datetime import date, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required

from app import db
from app.i18n import SESSION_KEY, is_supported
from app.models import Category, Todo

bp = Blueprint("main", __name__)

STATUS_FILTERS = ("all", "active", "completed")


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
    """แปลงค่าจาก <input type="datetime-local"> เป็น datetime (naive, เวลาท้องถิ่น)

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
    return parsed


@bp.route("/")
@login_required
def index():
    status = request.args.get("status", "all")
    if status not in STATUS_FILTERS:
        status = "all"

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
        today=date.today(),
    )


@bp.route("/add", methods=["POST"])
@login_required
def add():
    title = request.form.get("title", "").strip()
    if not title:
        flash(_("Please enter a task name"))
        return redirect(url_for("main.index"))
    try:
        due_date = _parse_due_date(request.form.get("due_date"))
    except ValueError:
        flash(_("Invalid date format"))
        return redirect(url_for("main.index"))
    db.session.add(
        Todo(
            title=title,
            user_id=current_user.id,
            category_id=_resolve_category_id(request.form.get("category_id")),
            due_date=due_date,
        )
    )
    db.session.commit()
    return redirect(url_for("main.index"))


@bp.route("/edit/<int:todo_id>", methods=["POST"])
@login_required
def edit(todo_id):
    todo = _owned_todo(todo_id)
    title = request.form.get("title", "").strip()
    if not title:
        flash(_("Task name cannot be empty"))
        return redirect(url_for("main.index"))
    try:
        due_date = _parse_due_date(request.form.get("due_date"))
    except ValueError:
        flash(_("Invalid date format"))
        return redirect(url_for("main.index"))
    todo.title = title
    todo.category_id = _resolve_category_id(request.form.get("category_id"))
    todo.due_date = due_date
    db.session.commit()
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
    # ปลดหมวดออกจาก todo ก่อน งานไม่หายไปด้วย
    Todo.query.filter_by(category_id=category.id).update({"category_id": None})
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

    # กลับไปหน้าเดิม แต่รับเฉพาะ path ภายในเว็บเรา ไม่งั้นจะเป็น open redirect
    target = request.referrer or ""
    path = target.split(request.host_url, 1)[-1] if target.startswith(request.host_url) else ""
    if path and not path.startswith("//"):
        return redirect("/" + path.lstrip("/"))
    return redirect(url_for("main.index"))
