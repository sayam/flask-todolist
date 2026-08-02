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

    @app.cli.command("delete-user")
    @click.argument("username")
    @click.option("--yes", is_flag=True, help="ลบเลยไม่ต้องถาม")
    def delete_user(username, yes):
        """ลบ user พร้อมหมวดและงานทั้งหมดของเขา (กู้คืนไม่ได้)"""
        user = User.query.filter_by(username=username.strip()).first()
        if user is None:
            raise click.ClickException(f"ไม่พบ user ชื่อ {username!r}")

        todos = len(user.todos)
        categories = len(user.categories)
        click.echo(
            f"จะลบ user {user.username!r} (id={user.id}) "
            f"พร้อม {categories} หมวด และ {todos} งาน"
        )
        if not yes:
            click.confirm("ยืนยันลบ?", abort=True)

        # ลบผ่าน ORM เพื่อให้ cascade ทำงาน — SQLite ไม่บังคับ FK ให้
        # ลบด้วย SQL ตรง ๆ จะเหลือ category/todo ค้างที่ชี้ไปหา user ที่ไม่มีแล้ว
        db.session.delete(user)
        db.session.commit()
        click.echo(f"ลบ {username!r} เรียบร้อย")

    @app.cli.command("list-users")
    def list_users():
        """ดูรายชื่อ user ทั้งหมด"""
        users = User.query.order_by(User.id).all()
        if not users:
            click.echo("ยังไม่มี user — สร้างด้วย `flask create-user <ชื่อ>`")
            return
        for user in users:
            click.echo(f"{user.id}\t{user.username}")
