"""ระงับการใช้บัญชีชั่วคราว (PDPA ม.34) — คอลัมน์เดียว ย้อนกลับได้เสมอ

`suspended_at` เป็น UTC naive เหมือนคอลัมน์เวลาทุกตัว (ADR 0002) และใช้
`UTCDateTime` ตามวินัย dialect — ค่า NULL = ใช้งานปกติ · มีค่า = ห้าม login
และ session เดิมถูกตัด แต่ข้อมูลไม่ถูกแตะ (ต่างจาก deleted_at ที่คือปิดบัญชี)

Revision ID: a7c41d90b3ef
Revises: e0252b0a560c
Create Date: 2026-08-14
"""

import sqlalchemy as sa
from alembic import op

from app.db_types import UTCDateTime

revision = "a7c41d90b3ef"
down_revision = "e0252b0a560c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """เพิ่มคอลัมน์เปล่า — ไม่มีข้อมูลเดิมให้ย้าย จึงไม่ต้องสำรอง/เขียนกลับ"""
    with op.batch_alter_table("tdl_user") as batch:
        batch.add_column(sa.Column("suspended_at", UTCDateTime, nullable=True))


def downgrade() -> None:
    """ถอดคอลัมน์ทิ้ง — สถานะระงับหายไปด้วย ซึ่งเป็นความหมายที่ถูกของ downgrade"""
    with op.batch_alter_table("tdl_user") as batch:
        batch.drop_column("suspended_at")
