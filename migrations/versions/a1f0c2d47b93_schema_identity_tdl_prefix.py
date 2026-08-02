"""schema identity: tdl_ prefix, naming convention, done -> is_done

Revision ID: a1f0c2d47b93
Revises: 7de41b01a108
Create Date: 2026-08-03 05:10:00.000000

**เขียนมือ ไม่ได้ autogenerate** — alembic มองการเปลี่ยนชื่อตารางเป็น
"drop ของเก่า + create ของใหม่" ซึ่งจะทำข้อมูลหายทั้งหมด

วิธีที่ใช้: สร้างตารางใหม่ครบก่อน → คัดลอกข้อมูลด้วย INSERT ... SELECT
ที่ระบุคอลัมน์ชัดเจน → ค่อย drop ของเก่าตามลำดับ dependency
(todo → category → user)

**ไม่ใช้ `batch_alter_table`** เพราะ batch mode บน SQLite คัดลอกข้อมูลด้วย
`CAST(col AS <type>)` ซึ่งเคยทำคอลัมน์ DATETIME พังมาแล้ว (ดู migration
89cd0c572bf9) ที่นี่ชนิดคอลัมน์ไม่เปลี่ยนเลย การ INSERT ... SELECT ตรง ๆ
จึงเป็นการคัดลอกค่าดิบ ไม่มีการแปลงชนิดให้พลาด

ตาราง `"user"` ถูก quote ทุกจุดเพราะเป็น reserved word ของ
PostgreSQL/Oracle/MSSQL — หลัง migration นี้ปัญหานั้นหมดไปถาวร
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1f0c2d47b93"
down_revision = "7de41b01a108"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tdl_user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("locale", sa.String(length=8), nullable=True),
        sa.Column("theme", sa.String(length=32), nullable=True),
        sa.Column("mode", sa.String(length=8), nullable=True),
        sa.Column("timezone_name", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=80), nullable=True),
        sa.Column("last_name", sa.String(length=80), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tdl_user")),
        sa.UniqueConstraint("username", name=op.f("uq_tdl_user_username")),
    )
    op.create_table(
        "tdl_category",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["tdl_user.id"], name=op.f("fk_tdl_category_user_id_tdl_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tdl_category")),
        sa.UniqueConstraint("user_id", "name", name=op.f("uq_category_user_name")),
    )
    op.create_index(
        op.f("ix_tdl_category_user_id"), "tdl_category", ["user_id"], unique=False
    )
    op.create_table(
        "tdl_todo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("is_done", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("start_date", sa.DateTime(), nullable=True),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["tdl_category.id"],
            name=op.f("fk_tdl_todo_category_id_tdl_category"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["tdl_user.id"], name=op.f("fk_tdl_todo_user_id_tdl_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tdl_todo")),
    )
    op.create_index(op.f("ix_tdl_todo_user_id"), "tdl_todo", ["user_id"], unique=False)

    # ระบุคอลัมน์ทุกตัวชัดเจน ไม่ใช้ SELECT * — ลำดับคอลัมน์ของตารางเก่า
    # ไม่จำเป็นต้องตรงกับของใหม่ และ done เปลี่ยนชื่อเป็น is_done ด้วย
    op.execute(
        'INSERT INTO tdl_user (id, username, password_hash, created_at, locale, theme, '
        "mode, timezone_name, first_name, last_name) "
        "SELECT id, username, password_hash, created_at, locale, theme, "
        'mode, timezone_name, first_name, last_name FROM "user"'
    )
    op.execute(
        "INSERT INTO tdl_category (id, name, user_id) SELECT id, name, user_id FROM category"
    )
    op.execute(
        "INSERT INTO tdl_todo (id, title, is_done, created_at, updated_at, start_date, "
        "due_date, user_id, category_id) "
        "SELECT id, title, done, created_at, updated_at, start_date, "
        "due_date, user_id, category_id FROM todo"
    )

    # drop ตามลำดับ dependency — ลูกก่อนแม่ เผื่อ DB ที่บังคับ FK จริง
    op.drop_table("todo")
    op.drop_table("category")
    op.drop_table("user")


def downgrade():
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("locale", sa.String(length=8), nullable=True),
        sa.Column("theme", sa.String(length=32), nullable=True),
        sa.Column("mode", sa.String(length=8), nullable=True),
        sa.Column("timezone_name", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=80), nullable=True),
        sa.Column("last_name", sa.String(length=80), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "category",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name", name="uq_category_user_name"),
    )
    op.create_index("ix_category_user_id", "category", ["user_id"], unique=False)
    op.create_table(
        "todo",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("start_date", sa.DateTime(), nullable=True),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["category_id"], ["category.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_todo_user_id", "todo", ["user_id"], unique=False)

    op.execute(
        'INSERT INTO "user" (id, username, password_hash, created_at, locale, theme, '
        "mode, timezone_name, first_name, last_name) "
        "SELECT id, username, password_hash, created_at, locale, theme, "
        "mode, timezone_name, first_name, last_name FROM tdl_user"
    )
    op.execute(
        "INSERT INTO category (id, name, user_id) SELECT id, name, user_id FROM tdl_category"
    )
    op.execute(
        "INSERT INTO todo (id, title, done, created_at, updated_at, start_date, "
        "due_date, user_id, category_id) "
        "SELECT id, title, is_done, created_at, updated_at, start_date, "
        "due_date, user_id, category_id FROM tdl_todo"
    )

    op.drop_index(op.f("ix_tdl_todo_user_id"), table_name="tdl_todo")
    op.drop_table("tdl_todo")
    op.drop_index(op.f("ix_tdl_category_user_id"), table_name="tdl_category")
    op.drop_table("tdl_category")
    op.drop_table("tdl_user")
