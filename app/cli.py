import click

from app import db
from app.models import Category, User

# หมวดตั้งต้นที่สร้างให้ user ใหม่ ปรับ/ลบทีหลังได้จากหน้า /categories
DEFAULT_CATEGORIES = [
    "งานส่วนตัว",
    "งาน delivery",
    "งานตอบจดหมาย",
    "งาน Admin/Troubleshoot/Fix",
]


def register_cli(app):
    @app.cli.command("create-user")
    @click.argument("username")
    @click.option(
        "--no-categories",
        is_flag=True,
        help="ไม่ต้องสร้างหมวดตั้งต้นให้",
    )
    def create_user(username, no_categories):
        """สร้าง user ใหม่ (ถามรหัสผ่านแบบไม่โชว์บนจอ)"""
        username = username.strip()
        if User.query.filter_by(username=username).first():
            raise click.ClickException(f"มี user ชื่อ {username!r} อยู่แล้ว")

        password = click.prompt(
            "รหัสผ่าน", hide_input=True, confirmation_prompt="ยืนยันรหัสผ่าน"
        )
        if len(password) < 8:
            raise click.ClickException("รหัสผ่านต้องยาวอย่างน้อย 8 ตัวอักษร")

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # ต้องได้ user.id ก่อนผูกหมวด

        if not no_categories:
            for name in DEFAULT_CATEGORIES:
                db.session.add(Category(name=name, user_id=user.id))

        db.session.commit()
        click.echo(f"สร้าง user {username!r} เรียบร้อย (id={user.id})")
        if not no_categories:
            click.echo(f"สร้างหมวดตั้งต้น {len(DEFAULT_CATEGORIES)} หมวด")

    @app.cli.command("list-users")
    def list_users():
        """ดูรายชื่อ user ทั้งหมด"""
        users = User.query.order_by(User.id).all()
        if not users:
            click.echo("ยังไม่มี user — สร้างด้วย `flask create-user <ชื่อ>`")
            return
        for user in users:
            click.echo(f"{user.id}\t{user.username}")
