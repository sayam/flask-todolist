from flask import Blueprint, redirect, render_template, request, url_for

from app import db
from app.models import Todo

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    todos = Todo.query.order_by(Todo.created_at.desc()).all()
    return render_template("index.html", todos=todos)


@bp.route("/add", methods=["POST"])
def add():
    title = request.form.get("title", "").strip()
    if title:
        db.session.add(Todo(title=title))
        db.session.commit()
    return redirect(url_for("main.index"))


@bp.route("/toggle/<int:todo_id>", methods=["POST"])
def toggle(todo_id):
    todo = db.get_or_404(Todo, todo_id)
    todo.done = not todo.done
    db.session.commit()
    return redirect(url_for("main.index"))


@bp.route("/delete/<int:todo_id>", methods=["POST"])
def delete(todo_id):
    todo = db.get_or_404(Todo, todo_id)
    db.session.delete(todo)
    db.session.commit()
    return redirect(url_for("main.index"))


@bp.route("/clear-completed", methods=["POST"])
def clear_completed():
    Todo.query.filter_by(done=True).delete()
    db.session.commit()
    return redirect(url_for("main.index"))
