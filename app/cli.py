"""คำสั่ง flask CLI สำหรับผู้ดูแลระบบ

ข้อความในไฟล์นี้ไม่ผ่าน gettext เพราะ CLI รันนอก request context
ซึ่งไม่มีข้อมูลว่าจะใช้ภาษาไหน — ใช้ภาษาอังกฤษตายตัวไปเลย
"""

import click
from flask.cli import with_appcontext

from app import db
from app.models import Category, User
from app.purge import PURGE_AFTER_DAYS, preview_expired, purge_expired
from config import DEFAULT_LANGUAGE, LANGUAGES

# หมวดตั้งต้นที่สร้างให้ user ใหม่ แยกตามภาษาที่เลือกตอนสร้าง
# ตัวนี้เป็นข้อมูลของผู้ใช้ ไม่ใช่ข้อความ UI จึงไม่ได้ผ่าน gettext —
# สร้างแล้วผู้ใช้แก้ชื่อเองได้ และจะไม่เปลี่ยนตามภาษาที่เลือกทีหลัง
DEFAULT_CATEGORIES = {
    "en": [
        "Personal",
        "Work",
    ],
    "th": [
        "งานส่วนตัว",
        "งานที่ทำงาน",
    ],
}

MIN_PASSWORD_LENGTH = 8


@click.command("create-user")
@click.argument("username")
@click.option(
    "--lang",
    type=click.Choice(sorted(LANGUAGES)),
    default=DEFAULT_LANGUAGE,
    show_default=True,
    help="Interface language for the user, and the language of their starter categories.",
)
@click.option(
    "--no-categories",
    is_flag=True,
    help="Skip creating the starter categories.",
)
@with_appcontext
def create_user(username, lang, no_categories):
    """Create a new user (prompts for a password without echoing it)."""
    username = username.strip()
    if User.query.filter_by(username=username).first():
        raise click.ClickException(f"A user named {username!r} already exists.")

    password = click.prompt("Password", hide_input=True, confirmation_prompt="Repeat password")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise click.ClickException(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )

    user = User(username=username, locale=lang)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()  # ต้องได้ user.id ก่อนผูกหมวด

    categories = DEFAULT_CATEGORIES[lang]
    if not no_categories:
        for name in categories:
            db.session.add(Category(name=name, user_id=user.id))

    db.session.commit()
    click.echo(f"Created user {username!r} (id={user.id}, language={lang}).")
    if not no_categories:
        click.echo(f"Added {len(categories)} starter categories: {', '.join(categories)}")


@click.command("delete-user")
@click.argument("username")
@click.option("--yes", is_flag=True, help="Delete without asking for confirmation.")
@with_appcontext
def delete_user(username, yes):
    """Delete a user along with all their categories and tasks (cannot be undone)."""
    user = User.query.filter_by(username=username.strip()).first()
    if user is None:
        raise click.ClickException(f"No user named {username!r}.")

    todos = len(user.todos)
    categories = len(user.categories)
    click.echo(
        f"About to delete user {user.username!r} (id={user.id}) "
        f"with {categories} categories and {todos} tasks."
    )
    if not yes:
        click.confirm("Delete?", abort=True)

    # soft delete: แถวยังอยู่แต่ถูกซ่อนทุก query จนกว่า purge job จะล้างเมื่อพ้น
    # 30 วัน (ดู docs/DATA-CLASSIFICATION.md) — ต้องไล่ทำเองทั้งงานและหมวดด้วย
    # เพราะ cascade ของ ORM ผูกกับการลบจริงเท่านั้น ไม่ทำงานกับการตั้ง deleted_at
    for todo in user.todos:
        todo.soft_delete()
    for category in user.categories:
        category.soft_delete()
    user.soft_delete()
    # credential เป็นชั้น C1 ล้างทันที ไม่รอ grace — กู้บัญชีได้แต่ต้องตั้งรหัสใหม่
    user.disable_password()
    db.session.commit()
    click.echo(
        f"Deleted {username!r} (soft delete — purged for real after "
        f"{PURGE_AFTER_DAYS} days; run `flask purge-expired`)."
    )


@click.command("list-users")
@with_appcontext
def list_users():
    """List all users with their id, username and language."""
    users = User.query.order_by(User.id).all()
    if not users:
        click.echo("No users yet — create one with `flask create-user <name>`.")
        return
    for user in users:
        click.echo(f"{user.id}\t{user.username}\t{user.locale or '-'}")


@click.command("purge-expired")
@click.option(
    "--days",
    type=int,
    default=PURGE_AFTER_DAYS,
    show_default=True,
    help="Purge rows soft-deleted longer ago than this.",
)
@click.option("--dry-run", is_flag=True, help="Report what would be purged without deleting.")
@with_appcontext
def purge_expired_command(days, dry_run):
    """Permanently remove data whose retention period has passed.

    This is the only command in the system that deletes real rows.
    """
    if dry_run:
        # คนละฟังก์ชันกับของจริง ไม่ใช่ flag ที่ย้อน transaction ทีหลัง — ดู app/purge.py
        result = preview_expired(days)
        click.echo(
            f"[dry run] would purge {result.todos} tasks, {result.categories} categories, "
            f"{result.users_purged} users (nothing was deleted)."
        )
        return

    result = purge_expired(days)
    click.echo(
        f"Purged {result.todos} tasks, {result.categories} categories "
        f"and scrubbed {result.users_purged} users."
    )


def register_cli(app):
    """ผูกทุก command เข้ากับ flask CLI — ตัว command ประกาศระดับ module"""
    app.cli.add_command(create_user)
    app.cli.add_command(delete_user)
    app.cli.add_command(list_users)
    app.cli.add_command(purge_expired_command)
