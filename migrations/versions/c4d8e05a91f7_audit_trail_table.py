"""audit trail: ตาราง tdl_audit แบบเติมได้อย่างเดียว + hash chain

Revision ID: c4d8e05a91f7
Revises: b7e3d91c5a2f
Create Date: 2026-08-03 08:20:00.000000

สร้างตารางใหม่ล้วน ไม่แตะข้อมูลเดิมสักคอลัมน์ — ฐานข้อมูลที่มีอยู่จึงเริ่มสาย
audit ที่แถวแรกหลัง upgrade ไม่ใช่ย้อนหลัง (ประวัติก่อนหน้านี้ไม่มีใครบันทึกไว้
จะแกล้งสร้างขึ้นมาก็เป็นหลักฐานปลอม)

**ไม่มี foreign key ไป tdl_user โดยตั้งใจ** — audit ต้องอยู่รอดโดยไม่ผูกชะตา
กับตารางข้อมูล และ `actor_id` ต้องชี้ไป tombstone ของคนที่ถูก purge ได้

`prev_hash` เป็น unique เพื่อกันไม่ให้สาย hash แตกเป็นสองสายในระดับ DB
(สองแถวชี้ไปแถวก่อนหน้าตัวเดียวกันไม่ได้) ดูเหตุผลเต็มใน app/audit.py
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c4d8e05a91f7"
down_revision = "b7e3d91c5a2f"
branch_labels = None
depends_on = None

TABLE = "tdl_audit"
HASH_LENGTH = 64


def upgrade():
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("event", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=8), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=True),
        sa.Column("table_name", sa.String(length=64), nullable=True),
        sa.Column("row_id", sa.Integer(), nullable=True),
        sa.Column("changes", sa.Text(), nullable=False),
        sa.Column("prev_hash", sa.String(length=HASH_LENGTH), nullable=False),
        sa.Column("row_hash", sa.String(length=HASH_LENGTH), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tdl_audit")),
        sa.UniqueConstraint("prev_hash", name="uq_audit_prev_hash"),
        sa.UniqueConstraint("row_hash", name="uq_audit_row_hash"),
    )
    op.create_index(op.f("ix_tdl_audit_created_at"), TABLE, ["created_at"], unique=False)
    op.create_index(op.f("ix_tdl_audit_event"), TABLE, ["event"], unique=False)
    op.create_index(op.f("ix_tdl_audit_actor_id"), TABLE, ["actor_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_tdl_audit_actor_id"), table_name=TABLE)
    op.drop_index(op.f("ix_tdl_audit_event"), table_name=TABLE)
    op.drop_index(op.f("ix_tdl_audit_created_at"), table_name=TABLE)
    op.drop_table(TABLE)
