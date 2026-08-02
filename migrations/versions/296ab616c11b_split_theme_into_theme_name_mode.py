"""split theme into theme name + mode

Revision ID: 296ab616c11b
Revises: 18dccb13a980
Create Date: 2026-08-02 19:50:32.111065

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '296ab616c11b'
down_revision = '18dccb13a980'
DEFAULT_THEME = "system"

branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('mode', sa.String(length=8), nullable=True))
        batch_op.alter_column('theme',
               existing_type=sa.VARCHAR(length=8),
               type_=sa.String(length=32),
               existing_nullable=True)

    # theme เดิมเก็บ 'light'/'dark' ซึ่งตอนนี้กลายเป็นความหมายของ mode
    # ส่วน theme กลายเป็นชื่อชุดสี ทุกคนจึงได้ชุดเดียวที่มีอยู่
    # theme เดิมที่เป็น NULL แปลว่า "ตามระบบ" ซึ่งเลิกใช้แล้ว -> ปล่อย mode
    # เป็น NULL คือใช้ค่าเริ่มต้น (auto)
    conn = op.get_bind()
    conn.execute(sa.text(
        "UPDATE user SET mode = theme WHERE theme IN ('light', 'dark')"
    ))
    conn.execute(sa.text(f"UPDATE user SET theme = '{DEFAULT_THEME}'"))


def downgrade():
    # คืน theme ให้เก็บระดับความสว่างเหมือนเดิม auto กลับไปเป็น NULL (ตามระบบ)
    conn = op.get_bind()
    conn.execute(sa.text(
        "UPDATE user SET theme = CASE WHEN mode IN ('light','dark') THEN mode END"
    ))

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.alter_column('theme',
               existing_type=sa.String(length=32),
               type_=sa.VARCHAR(length=8),
               existing_nullable=True)
        batch_op.drop_column('mode')

