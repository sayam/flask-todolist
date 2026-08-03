"""api token: ตาราง tdl_api_token สำหรับ personal access token

Revision ID: c7f1db5e54e4
Revises: c4d8e05a91f7
Create Date: 2026-08-03 18:54:12.691524

สร้างตารางใหม่ล้วน ไม่แตะข้อมูลเดิม — ฐานข้อมูลที่มีอยู่จึงไม่มี token ใบไหน
จนกว่าจะออกเอง (`flask token-create`)

`token_hash` เป็น sha256 hex = 64 ตัวพอดี ไม่ใช่ 255 เหมือน `password_hash`
เพราะไม่ได้ผ่าน scrypt (เหตุผลอยู่ใน app/services/tokens.py)

index บน `user_id` ไว้ list token ของคนเดียว ส่วน `deleted_at` มีเพราะทุก SELECT
ในระบบมี `deleted_at IS NULL` ต่อท้ายเสมอ (ตัวกรองใน app/soft_delete.py)
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c7f1db5e54e4"
down_revision = "c4d8e05a91f7"
branch_labels = None
depends_on = None

TABLE = "tdl_api_token"
HASH_LENGTH = 64
NAME_LENGTH = 80


def upgrade():
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=NAME_LENGTH), nullable=False),
        sa.Column("token_hash", sa.String(length=HASH_LENGTH), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["tdl_user.id"], name=op.f("fk_tdl_api_token_user_id_tdl_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tdl_api_token")),
    )
    with op.batch_alter_table(TABLE, schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_tdl_api_token_deleted_at"), ["deleted_at"])
        batch_op.create_index(batch_op.f("ix_tdl_api_token_user_id"), ["user_id"])


def downgrade():
    with op.batch_alter_table(TABLE, schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_tdl_api_token_user_id"))
        batch_op.drop_index(batch_op.f("ix_tdl_api_token_deleted_at"))

    op.drop_table(TABLE)
