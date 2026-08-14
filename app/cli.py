"""คำสั่ง flask CLI สำหรับผู้ดูแลระบบ

ข้อความในไฟล์นี้ไม่ผ่าน gettext เพราะ CLI รันนอก request context
ซึ่งไม่มีข้อมูลว่าจะใช้ภาษาไหน — ใช้ภาษาอังกฤษตายตัวไปเลย
"""

import json
import pathlib

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy import select

from app import audit, db
from app.models import Category, User
from app.purge import AUDIT_RETAIN_DAYS, PURGE_AFTER_DAYS, preview_expired, purge_expired
from app.services import ServiceError
from app.services import passwords as passwords_service
from app.services import personal_data as personal_data_service
from app.services import roles as roles_service
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
    # นโยบายเดียวกับฝั่งเว็บเป๊ะ — ประตูหลังที่ยอมให้ตั้งรหัสอ่อนกว่าคือช่องที่
    # คนจะใช้จริง เพราะมันสะดวกกว่า (ดู app/services/passwords.py)
    try:
        password = passwords_service.validate(password, username=username)
    except ServiceError as error:
        raise click.ClickException(error.message) from error

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

    # **ทางเดียวที่ปิดบัญชีได้คือ service ตัวนี้** — ตอนที่ CLI ไล่ลบเอง มันลืม
    # ล้างความลับของปัจจัยที่สองไปทั้งดุ้น ทั้งที่คอมเมนต์ตรงนี้อ้างกติกา C1 อยู่
    # (ADR 0034 ข้อ 4) หน้าเว็บที่เพิ่มทีหลังจะไม่มีทางลืมซ้ำ เพราะไม่มีที่ให้ลืม
    try:
        summary = personal_data_service.close_account(user)
    except ServiceError as error:
        raise click.ClickException(error.message) from error

    erased = sum(summary["plugins"].values())
    if erased:
        click.echo(f"Erased {erased} row(s) held by plugins.")
    click.echo(
        f"Deleted {username!r} (soft delete — purged for real after "
        f"{PURGE_AFTER_DAYS} days; run `flask purge-expired`)."
    )


@click.command("set-password")
@click.argument("username")
@with_appcontext
def set_password(username):
    """Set a user's password without asking for the old one (admin recovery path).

    There is no self-service password reset by design (no email is stored),
    so this is how a forgotten password gets fixed.
    """
    user = _find_user(username.strip())
    if user is None:
        raise click.ClickException(f"No user named {username!r}.")

    password = click.prompt("New password", hide_input=True, confirmation_prompt="Repeat password")
    try:
        passwords_service.set_password(user, password)
    except ServiceError as error:
        raise click.ClickException(error.message) from error
    click.echo(f"Password of {user.username!r} changed.")


@click.command("export-user")
@click.argument("username")
@click.option(
    "--output",
    type=click.Path(dir_okay=False, writable=True),
    help="Write to this file instead of stdout.",
)
@with_appcontext
def export_user(username, output):
    """Export everything the system stores about a user, as JSON.

    The admin-side path for a data subject request. The web page at /settings
    does the same thing for the account holder, through the same service —
    two ways in, one set of rules about what leaves the system.
    """
    user = _find_user(username.strip())
    if user is None:
        raise click.ClickException(f"No user named {username!r}.")

    payload = personal_data_service.export(user)
    audit.record("user.export", table_name="tdl_user", row_id=user.id)
    db.session.commit()

    text = json.dumps(payload, ensure_ascii=False, indent=1)
    if output:
        pathlib.Path(output).write_text(text + "\n", encoding="utf-8")
        click.echo(f"Wrote {output}.")
    else:
        # **ห้ามให้ log ปนกับ JSON บน stdout** — เครื่องที่รับต่อจะย่อยไม่ได้
        # (เทสต์ test_machine_readable_output_is_not_polluted_by_logs ดักไว้)
        click.echo(text)


@click.command("set-role")
@click.argument("username")
@click.argument("role", type=click.Choice(roles_service.ROLES))
@with_appcontext
def set_role(username, role):
    """Set a user's role (this is how the first administrator is created).

    The web page refuses to change your own role, on purpose. This command
    does not: whoever can run it already has full access to the machine.
    """
    user = _find_user(username.strip())
    if user is None:
        raise click.ClickException(f"No user named {username!r}.")
    try:
        roles_service.set_role(user, role)
    except ServiceError as error:
        raise click.ClickException(error.message) from error
    click.echo(f"{user.username!r} is now {role!r}.")


@click.command("list-users")
@with_appcontext
def list_users():
    """List all users with their id, username, language and role."""
    users = db.session.scalars(select(User).order_by(User.id)).all()
    if not users:
        click.echo("No users yet — create one with `flask create-user <name>`.")
        return
    for user in users:
        click.echo(f"{user.id}\t{user.username}\t{user.locale or '-'}\t{user.role}")


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


def _serving_keys(points):
    """คีย์ของส่วนเสริมที่กำลังให้บริการความสามารถของมันอยู่จริง

    **ไม่คำนวณเหตุผลซ้ำเอง** — ถาม `provider()` ตัวเดียวกับที่ host เรียกจริง
    ซึ่งจะ log บอกด้วยว่าทำไมถึงไม่ได้ให้บริการ (มีหลายตัวแต่ไม่มี pick จึงปิดไว้
    ทั้งหมด / pick ชี้ไปตัวที่ตอนนี้ใช้ไม่ได้) ซึ่งคือคำถามของคนที่รันคำสั่งนี้
    ตอนที่ความสามารถหนึ่งหายไปโดยที่ไดเรกทอรียังอยู่และไลบรารีก็ยังครบ

    **ถามครั้งเดียวต่อความสามารถ ไม่ใช่ครั้งเดียวต่อส่วนเสริม** — คำตอบเป็นของ
    ความสามารถทั้งอัน (ใครได้ให้บริการ) ไม่ใช่ของผู้สมัครแต่ละราย ถามทีละราย
    จึงได้คำเตือนข้อความเดียวกันซ้ำตามจำนวนผู้สมัคร แล้วคนอ่าน log จะนึกว่า
    เป็นคนละเหตุการณ์กัน ทั้งที่เป็นเรื่องเดียวที่ถูกถามซ้ำ
    """
    from app import plugins

    # (คีย์ของ host, ชื่อความสามารถ) → host — ตัวเดียวกันโผล่ได้หลายรอบตามจำนวนผู้สมัคร
    capabilities: dict[tuple[str, str], plugins.Plugin] = {}
    for point in points:
        if point.host is not None and point.provides is not None:
            capabilities.setdefault((point.host.key, point.provides), point.host)

    serving = set()
    for (_, capability), host in capabilities.items():
        chosen = plugins.provider(host, capability)
        if chosen is not None:
            serving.add(chosen.key)
    return serving


def _serving_state(plugin, serving):
    """คอลัมน์ `provides <ความสามารถ> (serving / NOT serving)` ของแถวนี้

    ว่างเปล่าสำหรับ plugin ที่ไม่ได้ให้ความสามารถผ่านชั้นนี้ (ตัวแม่กับธีม)
    """
    if plugin.host is None or plugin.provides is None:
        return ""
    verb = "serving" if plugin.key in serving else "NOT serving"
    return f"provides {plugin.provides} ({verb}); "


@click.command("suspend-user")
@click.argument("username")
@with_appcontext
def suspend_user(username):
    """Suspend an account (PDPA article 34) — reversible with unsuspend-user."""
    from datetime import UTC, datetime

    from sqlalchemy import select

    from app.models import User

    user = db.session.scalars(select(User).where(User.username == username)).first()
    if user is None:
        raise click.ClickException(f"No user named {username!r}.")
    if user.suspended_at is not None:
        raise click.ClickException(f"{username} is already suspended.")
    user.suspended_at = datetime.now(UTC).replace(tzinfo=None)
    db.session.commit()
    click.echo(f"Suspended {username}. Sign-in is blocked and live sessions will be cut.")


@click.command("unsuspend-user")
@click.argument("username")
@with_appcontext
def unsuspend_user(username):
    """Lift a suspension — the account returns to normal, nothing else changes."""
    from sqlalchemy import select

    from app.models import User

    user = db.session.scalars(select(User).where(User.username == username)).first()
    if user is None:
        raise click.ClickException(f"No user named {username!r}.")
    if user.suspended_at is None:
        raise click.ClickException(f"{username} is not suspended.")
    user.suspended_at = None
    db.session.commit()
    click.echo(f"{username} is active again.")


@click.command("plugin-list")
@with_appcontext
def plugin_list():
    """List installed plugins and the tables they own, if any."""
    from sqlalchemy import inspect

    from app import plugins

    existing = set(inspect(db.engine).get_table_names())
    # ไล่จากดิสก์ ไม่ใช่จากของที่ใช้งานได้ — ตัวที่ถูกสวิตช์ปิดต้องยังโผล่ในรายการ
    # ไม่งั้นผู้ดูแลแยกไม่ออกว่า "ปิดไว้" กับ "ไดเรกทอรีหายไปแล้ว"
    #
    # และต้องครบทุกชั้น (รวมส่วนเสริม) เพราะคีย์ที่ใส่ลง DISABLED_PLUGINS
    # มาจากรายการนี้ — คีย์ที่ไม่เคยถูกพิมพ์ออกมาคือคีย์ที่ไม่มีใครใส่ได้ถูก
    points = plugins.plug_points_on_disk()
    serving = _serving_keys(points)
    for plugin in points:
        tables = sorted(plugins.tables_of(plugin))
        needed = plugins.requirements(plugin)
        if tables:
            verb = "installed" if all(name in existing for name in tables) else "NOT installed"
            state = f"{verb}: {', '.join(tables)}"
        elif needed:
            missing = set(plugins.missing_requirements(plugin))
            state = ", ".join(f"{item}{' MISSING' if item in missing else ''}" for item in needed)
        else:
            state = "no tables"
        core = " (core)" if plugin.is_core else ""
        off = " DISABLED" if plugins.is_disabled(plugin) else ""
        column = _serving_state(plugin, serving)
        click.echo(f"{plugin.key}\tv{plugin.version}{core}{off}\t{column}{state}")
        _echo_profiles_of(plugin)


def _echo_profiles_of(plugin):
    """auth profile (ADR 0047) พิมพ์เป็นลูกของ plugin แม่ **รวมตัวที่ถูกปิด**

    คีย์พวกนี้ใส่ลง DISABLED_PLUGINS ได้ทีละตัว จึงต้องถูกพิมพ์ออกมาเหมือน
    คีย์อื่นทุกตัว — ไล่จากที่ประกาศ ไม่ใช่จากที่ใช้งานได้
    """
    from app import plugins

    for raw in current_app.config.get("AUTH_PROFILES", ()):
        plugin_id, name = plugins.parse_profile_entry(raw)
        if f"{plugins.AUTH_TYPE}/{plugin_id}" != plugin.key:
            continue
        profile_key = f"{plugin.key}{plugins.PROFILE_SEPARATOR}{name}"
        profile_off = " DISABLED" if profile_key in plugins.disabled_keys() else ""
        click.echo(f"{profile_key}\tprofile of {plugin.key}{profile_off}")


@click.command("plugin-deps")
@click.option(
    "--categories",
    is_flag=True,
    help="Print just the pipenv categories, ready to paste into `pipenv sync --categories`.",
)
@with_appcontext
def plugin_deps(categories):
    """Show which libraries each plugin needs, and whether they are installed.

    Plugin libraries are deliberately outside the core `[packages]` (ADR 0025):
    removing a plugin has to remove its supply chain too, not just its code.
    Install one with: pipenv sync --categories="<category>"
    """
    from app import plugins

    if categories:
        # ให้ CI/สคริปต์เอาไปต่อท้าย `pipenv sync --categories` ได้เลยโดยไม่ต้อง
        # รู้จักชื่อ plugin ตัวไหนเป็นการเฉพาะ
        wanted = [
            plugins.category_of(point)
            for point in plugins.plug_points()
            if plugins.requirements(point)
        ]
        click.echo(" ".join(sorted(wanted)))
        return

    for point in plugins.plug_points():
        needed = plugins.requirements(point)
        if not needed:
            click.echo(f"{point.key}\t(no libraries)")
            continue
        missing = set(plugins.missing_requirements(point))
        for requirement in needed:
            state = "MISSING" if requirement in missing else "ok"
            click.echo(f"{point.key}\t{requirement}\t{state}\t[{plugins.category_of(point)}]")


@click.command("plugin-install")
@click.argument("key")
@with_appcontext
def plugin_install(key):
    """Create the tables owned by a plugin (safe to run twice).

    Plugin tables are deliberately outside the core migration chain: dropping
    a plugin directory must not make the next core migration delete its data.
    """
    from app import plugins

    # ตั้งใจใช้ตัวที่ไม่สนสวิตช์ปิด เพราะวงจรชีวิตของ *ข้อมูล* ต้องทำได้เสมอ
    # แม้ *โค้ด* ของ plugin จะถูกปิดไว้ชั่วคราวเพราะ CVE
    plugin = plugins.find_on_disk(key)
    if plugin is None:
        raise click.ClickException(f"No plugin named {key!r} (see `flask plugin-list`).")
    tables = plugins.install(plugin)
    if not tables:
        click.echo(f"{plugin.key} has no tables of its own — nothing to do.")
        return
    click.echo(f"Installed {plugin.key}: {', '.join(sorted(tables))}")


@click.command("plugin-uninstall")
@click.argument("key")
@click.option("--yes", is_flag=True, help="Drop without asking for confirmation.")
@with_appcontext
def plugin_uninstall(key, yes):
    """Drop the tables owned by a plugin — the data in them is gone for good."""
    from app import plugins

    # ตั้งใจใช้ตัวที่ไม่สนสวิตช์ปิด เพราะวงจรชีวิตของ *ข้อมูล* ต้องทำได้เสมอ
    # แม้ *โค้ด* ของ plugin จะถูกปิดไว้ชั่วคราวเพราะ CVE
    plugin = plugins.find_on_disk(key)
    if plugin is None:
        raise click.ClickException(f"No plugin named {key!r} (see `flask plugin-list`).")
    if plugin.type == plugins.DB_TYPE:
        # ตอบให้ชัดว่าทำไมคำสั่งนี้ไม่ใช่ทางที่ถูก แทนที่จะบอกว่า "ไม่มีตารางให้ลบ"
        # ซึ่งจริงแต่ทำให้คนเข้าใจว่าถอนสำเร็จแล้ว (ADR 0026 ข้อ 3 กับ 4)
        raise click.ClickException(
            f"{plugin.key} is a database backend: it owns no data of its own, so there is "
            "nothing to uninstall. Point DATABASE_URL at another backend and migrate the "
            "data across, then remove the directory if you want its driver gone too."
        )
    tables = sorted(plugins.tables_of(plugin))
    if not tables:
        click.echo(f"{plugin.key} has no tables of its own — nothing to do.")
        return

    click.echo(f"About to drop {', '.join(tables)} and everything in them.")
    if not yes:
        click.confirm("Drop?", abort=True)
    plugins.uninstall(plugin)
    click.echo(f"Uninstalled {plugin.key}.")


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
    app.cli.add_command(set_password)
    app.cli.add_command(export_user)
    app.cli.add_command(set_role)
    app.cli.add_command(list_users)
    app.cli.add_command(token_create)
    app.cli.add_command(token_list)
    app.cli.add_command(token_revoke)
    app.cli.add_command(plugin_list)
    app.cli.add_command(plugin_deps)
    app.cli.add_command(plugin_install)
    app.cli.add_command(plugin_uninstall)
    app.cli.add_command(suspend_user)
    app.cli.add_command(unsuspend_user)
    app.cli.add_command(purge_expired_command)
    app.cli.add_command(audit_verify)
    app.cli.add_command(audit_log)
