from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.models import Category, Todo

bp = Blueprint("main", __name__)


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


@bp.route("/")
@login_required
def index():
    todos = (
        Todo.query.filter_by(user_id=current_user.id)
        .order_by(Todo.created_at.desc())
        .all()
    )
    categories = (
        Category.query.filter_by(user_id=current_user.id)
        .order_by(Category.name)
        .all()
    )
    return render_template("index.html", todos=todos, categories=categories)


@bp.route("/add", methods=["POST"])
@login_required
def add():
    title = request.form.get("title", "").strip()
    if not title:
        flash("กรุณาใส่ชื่องาน")
        return redirect(url_for("main.index"))
    db.session.add(
        Todo(
            title=title,
            user_id=current_user.id,
            category_id=_resolve_category_id(request.form.get("category_id")),
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
        flash("ชื่องานว่างไม่ได้")
        return redirect(url_for("main.index"))
    todo.title = title
    todo.category_id = _resolve_category_id(request.form.get("category_id"))
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
        flash("กรุณาใส่ชื่อหมวด")
    elif Category.query.filter_by(user_id=current_user.id, name=name).first():
        flash(f"มีหมวด “{name}” อยู่แล้ว")
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
        flash("ชื่อหมวดว่างไม่ได้")
    elif (
        Category.query.filter_by(user_id=current_user.id, name=name)
        .filter(Category.id != category.id)
        .first()
    ):
        flash(f"มีหมวด “{name}” อยู่แล้ว")
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
