"""คำสั่ง flask CLI สำหรับผู้ดูแลระบบ

ข้อความในไฟล์นี้ไม่ผ่าน gettext เพราะ CLI รันนอก request context
ซึ่งไม่มีข้อมูลว่าจะใช้ภาษาไหน — ใช้ภาษาอังกฤษตายตัวไปเลย
"""

import click
from flask.cli import with_appcontext
from sqlalchemy import select

from app import audit, db
from app.models import Category, User
from app.purge import AUDIT_RETAIN_DAYS, PURGE_AFTER_DAYS, preview_expired, purge_expired
from app.services import ServiceError
from app.services import tokens as tokens_service
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


def _find_user(username):
    """หา user จากชื่อ — คืน None ถ้าไม่มี (ผู้ที่ถูก soft delete ถูกกรองออกให้เอง)"""
    return db.session.scalars(select(User).where(User.username == username)).first()


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
    if _find_user(username) is not None:
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
    user = _find_user(username.strip())
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
    # token ที่ยังไม่หมดอายุคือกุญแจที่ยังเปิดประตูได้ ต้องตายไปพร้อมบัญชี
    # (ตัวกรอง soft delete ซ่อนเจ้าของไปแล้วก็จริง แต่ "ปิดสองชั้น" ถูกกว่าการ
    # ต้องพิสูจน์ว่าชั้นเดียวไม่มีทางพลาด)
    for token in user.api_tokens:
        token.soft_delete()
        token.disable()
    db.session.commit()
    click.echo(
        f"Deleted {username!r} (soft delete — purged for real after "
        f"{PURGE_AFTER_DAYS} days; run `flask purge-expired`)."
    )


@click.command("list-users")
@with_appcontext
def list_users():
    """List all users with their id, username and language."""
    users = db.session.scalars(select(User).order_by(User.id)).all()
    if not users:
        click.echo("No users yet — create one with `flask create-user <name>`.")
        return
    for user in users:
        click.echo(f"{user.id}\t{user.username}\t{user.locale or '-'}")


@click.command("token-create")
@click.argument("username")
@click.option("--name", required=True, help="What this token is for (shown in the token list).")
@click.option(
    "--expires-days",
    type=int,
    default=tokens_service.DEFAULT_EXPIRY_DAYS,
    show_default=True,
    help="Days until the token expires. Use 0 for a token that never expires.",
)
@with_appcontext
def token_create(username, name, expires_days):
    """Issue a personal access token for a user (shown once, never again)."""
    user = _find_user(username.strip())
    if user is None:
        raise click.ClickException(f"No user named {username!r}.")
    try:
        secret = tokens_service.issue(user, name, expires_days)
    except ServiceError as error:
        raise click.ClickException(error.message) from error

    click.echo(f"Token for {user.username!r} created. Copy it now — it is not stored anywhere:")
    click.echo(secret)


@click.command("token-list")
@click.argument("username")
@with_appcontext
def token_list(username):
    """List a user's active tokens (revoked ones are hidden)."""
    user = _find_user(username.strip())
    if user is None:
        raise click.ClickException(f"No user named {username!r}.")
    rows = tokens_service.list_tokens(user)
    if not rows:
        click.echo(f"No tokens for {user.username!r} — create one with `flask token-create`.")
        return
    for token in rows:
        expiry = token.expires_at.isoformat() if token.expires_at else "never"
        state = "expired" if token.is_expired else "active"
        click.echo(f"{token.id}\t{token.name}\t{state}\texpires: {expiry}")


@click.command("token-revoke")
@click.argument("username")
@click.argument("token_id", type=int)
@with_appcontext
def token_revoke(username, token_id):
    """Revoke one token immediately (its secret is wiped, not just hidden)."""
    user = _find_user(username.strip())
    if user is None:
        raise click.ClickException(f"No user named {username!r}.")
    try:
        token = tokens_service.revoke(user, token_id)
    except ServiceError as error:
        raise click.ClickException(error.message) from error
    click.echo(f"Revoked token {token.id} ({token.name!r}) of {user.username!r}.")


@click.command("purge-expired")
@click.option(
    "--days",
    type=int,
    default=PURGE_AFTER_DAYS,
    show_default=True,
    help="Purge rows soft-deleted longer ago than this.",
)
@click.option(
    "--audit-days",
    type=int,
    default=AUDIT_RETAIN_DAYS,
    show_default=True,
    help="Purge audit entries older than this (they keep a longer retention than data).",
)
@click.option("--dry-run", is_flag=True, help="Report what would be purged without deleting.")
@with_appcontext
def purge_expired_command(days, audit_days, dry_run):
    """Permanently remove data whose retention period has passed.

    This is the only command in the system that deletes real rows.
    """
    if dry_run:
        # คนละฟังก์ชันกับของจริง ไม่ใช่ flag ที่ย้อน transaction ทีหลัง — ดู app/purge.py
        result = preview_expired(days, audit_days)
        click.echo(
            f"[dry run] would purge {result.todos} tasks, {result.categories} categories, "
            f"{result.api_tokens} tokens, {result.users_purged} users, "
            f"{result.audit_entries} audit entries (nothing was deleted)."
        )
        return

    result = purge_expired(days, audit_days)
    click.echo(
        f"Purged {result.todos} tasks, {result.categories} categories, "
        f"{result.api_tokens} tokens, {result.audit_entries} audit entries "
        f"and scrubbed {result.users_purged} users."
    )


@click.command("audit-verify")
@with_appcontext
def audit_verify():
    """Walk the audit hash chain and report whether it is intact."""
    try:
        checked = audit.verify_chain()
    except audit.ChainError as broken:
        raise click.ClickException(str(broken)) from broken
    click.echo(f"Audit chain OK — {checked} entries verified.")


@click.command("audit-log")
@click.option("--limit", type=int, default=20, show_default=True, help="How many entries to show.")
@with_appcontext
def audit_log(limit):
    """Show the most recent audit entries (newest first, read only)."""
    rows = audit.entries(limit)
    if not rows:
        click.echo("No audit entries yet.")
        return
    for row in rows:
        actor = f"user:{row.actor_id}" if row.actor_id is not None else row.source
        target = f" {row.table_name}:{row.row_id}" if row.table_name else ""
        click.echo(f"{row.id}\t{row.created_at.isoformat()}\t{actor}\t{row.event}{target}")
        click.echo(f"\t{row.changes}")


def register_cli(app):
    """ผูกทุก command เข้ากับ flask CLI — ตัว command ประกาศระดับ module"""
    app.cli.add_command(create_user)
    app.cli.add_command(delete_user)
    app.cli.add_command(list_users)
    app.cli.add_command(token_create)
    app.cli.add_command(token_list)
    app.cli.add_command(token_revoke)
    app.cli.add_command(purge_expired_command)
    app.cli.add_command(audit_verify)
    app.cli.add_command(audit_log)
