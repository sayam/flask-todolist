"""keep the audit chain tail on the lock row

Revision ID: e0252b0a560c
Revises: 33fa4aea8bf7
Create Date: 2026-08-12 10:24:35.982177

หางสายย้ายมาอยู่บนแถวล็อก (ADR 0035) เพราะ **locking read เห็นค่าล่าสุดที่
commit แล้วเสมอ** ส่วนการอ่านแบบธรรมดาใต้ REPEATABLE READ เห็น snapshot ที่ตั้งไว้
ตั้งแต่ query แรกของ transaction — และคำขอจริงทุกใบอ่านข้อมูลก่อนเขียน

**ต้องเติมค่าเดิมให้ครบ ไม่ใช่ปล่อยเป็นค่าเริ่มต้น** — ฐานที่มีแถว audit อยู่แล้ว
แล้วเริ่มต่อสายจาก genesis ใหม่ จะได้แถวที่ `prev_hash` ชี้ไปหาแถวที่ไม่ใช่
แถวก่อนหน้า ซึ่งทำให้ `flask audit-verify` ไม่ผ่านตลอดกาลโดยที่ไม่มีใครทำอะไรผิด
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e0252b0a560c"
down_revision = "33fa4aea8bf7"
branch_labels = None
depends_on = None

LOCK_ROW_ID = 1
GENESIS_HASH = "0" * 64


def upgrade():
    with op.batch_alter_table("tdl_audit_lock", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("last_hash", sa.String(length=64), nullable=False, server_default=GENESIS_HASH)
        )

    # เติมด้วยหางสายจริงของฐานนี้ ถ้ายังไม่มีแถว audit เลยก็คงค่า genesis ไว้
    connection = op.get_bind()
    tail = connection.execute(
        sa.select(sa.column("row_hash"))
        .select_from(sa.table("tdl_audit", sa.column("id"), sa.column("row_hash")))
        .order_by(sa.column("id").desc())
        .limit(1)
    ).scalar()
    if tail:
        connection.execute(
            sa.table("tdl_audit_lock", sa.column("id"), sa.column("last_hash"))
            .update()
            .where(sa.column("id") == LOCK_ROW_ID)
            .values(last_hash=tail)
        )


def downgrade():
    with op.batch_alter_table("tdl_audit_lock", schema=None) as batch_op:
        batch_op.drop_column("last_hash")
