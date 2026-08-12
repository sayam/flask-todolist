"""audit chain lock row so appends queue instead of deadlocking

Revision ID: 33fa4aea8bf7
Revises: 5ffefa218ed7
Create Date: 2026-08-12 08:01:13.871510

ตารางแถวเดียวที่ทุกคนที่จะต่อสาย audit ต้องล็อกก่อน (ADR 0035)

**การ INSERT แถวนั้นเป็นส่วนหนึ่งของ migration ไม่ใช่ของแอปตอนรัน** — แอปที่
สร้างแถวให้เองเมื่อไม่เจอ คือแอปที่ผู้เขียนหลายรายสร้างแถวพร้อมกันได้ ซึ่งพา
กลับไปที่ปัญหาเดิมพอดี · ไม่มีแถวนี้ = `_last_hash()` raise ทันที ไม่เดินต่อเงียบ ๆ
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "33fa4aea8bf7"
down_revision = "5ffefa218ed7"
branch_labels = None
depends_on = None

LOCK_ROW_ID = 1


def upgrade():
    lock = op.create_table(
        "tdl_audit_lock",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tdl_audit_lock")),
    )
    op.bulk_insert(lock, [{"id": LOCK_ROW_ID}])


def downgrade():
    op.drop_table("tdl_audit_lock")
