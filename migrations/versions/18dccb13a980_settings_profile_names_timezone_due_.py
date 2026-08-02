"""settings: profile names, timezone, due_date to UTC

Revision ID: 18dccb13a980
Revises: 81b7c3f4e01f
Create Date: 2026-08-02 17:43:28.341630

"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "18dccb13a980"
down_revision = "81b7c3f4e01f"
branch_labels = None
depends_on = None

# ก่อน revision นี้ due_date ถูกเก็บเป็น "เวลาท้องถิ่นของเครื่องที่รัน server"
# ซึ่งตอนนั้นคือค่า BABEL_DEFAULT_TIMEZONE — ใช้ค่านั้นเป็นต้นทางในการแปลง
LEGACY_TZ = "Asia/Bangkok"
STORED_FORMAT = "%Y-%m-%d %H:%M:%S.%f"


def _rows(conn):
    return conn.execute(
        sa.text("SELECT id, due_date FROM todo WHERE due_date IS NOT NULL")
    ).fetchall()


def _shift(conn, from_tz, to_tz):
    """แปลง due_date ทุกแถวจาก from_tz ไป to_tz

    อ่านออกมาแปลงใน Python แล้วเขียนกลับเป็นสตริง เพราะ SQLite ไม่มีฟังก์ชัน
    แปลง timezone ที่รู้จัก DST และการเขียนกลับด้วยพารามิเตอร์ข้อความ
    ไม่โดน NUMERIC affinity แปลงค่า
    """
    for row_id, raw in _rows(conn):
        text = str(raw)
        try:
            naive = datetime.strptime(text, STORED_FORMAT)
        except ValueError:
            # เผื่อแถวที่ไม่มีเศษวินาที
            naive = datetime.fromisoformat(text)
        converted = naive.replace(tzinfo=from_tz).astimezone(to_tz).replace(tzinfo=None)
        conn.execute(
            sa.text("UPDATE todo SET due_date = :value WHERE id = :id"),
            {"value": converted.strftime(STORED_FORMAT), "id": row_id},
        )


def upgrade():
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(sa.Column("timezone_name", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("first_name", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("last_name", sa.String(length=80), nullable=True))

    # เวลาท้องถิ่นเดิม -> UTC
    _shift(op.get_bind(), ZoneInfo(LEGACY_TZ), UTC)


def downgrade():
    # UTC -> เวลาท้องถิ่นแบบเดิม
    _shift(op.get_bind(), UTC, ZoneInfo(LEGACY_TZ))

    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_column("last_name")
        batch_op.drop_column("first_name")
        batch_op.drop_column("timezone_name")
