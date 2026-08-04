"""rbac: คอลัมน์ role ของผู้ใช้ (Phase 4 — ดู ADR 0022)

แถวที่มีอยู่ก่อนหน้าได้ค่า 'user' จาก server_default ไม่ใช่ NULL —
NULL แปลว่า "ไม่รู้ว่ามีสิทธิ์แค่ไหน" ซึ่งเป็นสถานะที่ระบบสิทธิ์ต้องไม่มี
ผู้ดูแลคนแรกตั้งด้วย `flask set-role <ชื่อผู้ใช้> admin` หลัง upgrade

Revision ID: 401e0ce7011f
Revises: c7f1db5e54e4
Create Date: 2026-08-04 08:08:26.692689

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "401e0ce7011f"
down_revision = "c7f1db5e54e4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tdl_user", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("role", sa.String(length=16), server_default="user", nullable=False)
        )


def downgrade():
    with op.batch_alter_table("tdl_user", schema=None) as batch_op:
        batch_op.drop_column("role")
