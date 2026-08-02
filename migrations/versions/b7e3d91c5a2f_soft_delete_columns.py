"""soft delete: deleted_at ทุกตาราง + purged_at ของ user

Revision ID: b7e3d91c5a2f
Revises: a1f0c2d47b93
Create Date: 2026-08-03 06:05:00.000000

เพิ่มคอลัมน์ nullable ล้วน ไม่แตะข้อมูลเดิมเลย — แถวที่มีอยู่ได้ `deleted_at`
เป็น NULL ซึ่งแปลว่า "ยังอยู่" ตรงตามความหมายที่ต้องการพอดี

ใส่ index ให้ `deleted_at` เพราะทุก SELECT ในระบบมีเงื่อนไขนี้ต่อท้ายเสมอ
(ตัวกรองถูกเติมอัตโนมัติใน `app/soft_delete.py`) และ purge job ก็ค้นด้วยคอลัมน์นี้
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b7e3d91c5a2f"
down_revision = "a1f0c2d47b93"
branch_labels = None
depends_on = None

TABLES = ("tdl_user", "tdl_category", "tdl_todo")


def upgrade():
    for table in TABLES:
        op.add_column(table, sa.Column("deleted_at", sa.DateTime(), nullable=True))
        op.create_index(op.f(f"ix_{table}_deleted_at"), table, ["deleted_at"], unique=False)

    # เฉพาะ user เท่านั้นที่ถูกเก็บไว้เป็น tombstone หลัง purge (ดู ADR 0014)
    # todo/category ถูกลบแถวจริง จึงไม่ต้องมีคอลัมน์นี้
    op.add_column("tdl_user", sa.Column("purged_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("tdl_user", "purged_at")
    for table in reversed(TABLES):
        op.drop_index(op.f(f"ix_{table}_deleted_at"), table_name=table)
        op.drop_column(table, "deleted_at")
