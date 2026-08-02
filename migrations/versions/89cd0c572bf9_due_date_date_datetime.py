"""due_date: date -> datetime

Revision ID: 89cd0c572bf9
Revises: cb0dcf2ef467
Create Date: 2026-08-02 16:07:50.223814

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "89cd0c572bf9"
down_revision = "cb0dcf2ef467"
branch_labels = None
depends_on = None


# หมายเหตุสำคัญ:
# batch_alter_table ของ alembic บน SQLite จะสร้างตารางใหม่แล้วคัดลอกข้อมูลด้วย
# CAST(due_date AS DATETIME) — และ DATETIME ใน SQLite มี NUMERIC affinity
# ทำให้ CAST ตัดเอาเฉพาะส่วนหน้าที่เป็นตัวเลข '2026-08-02' จึงกลายเป็น 2026
#
# จึงต้องอ่านค่าเก็บไว้ก่อน ปล่อยให้ batch alter ทำลายค่าไป แล้วค่อยเขียนกลับ
# การ UPDATE ด้วยพารามิเตอร์ที่เป็นข้อความไม่โดน affinity แปลง เพราะสตริงอย่าง
# '2026-08-02 00:00:00.000000' ไม่ใช่ตัวเลขที่ well-formed


def _fetch_due_dates(conn):
    return conn.execute(
        sa.text("SELECT id, due_date FROM todo WHERE due_date IS NOT NULL")
    ).fetchall()


def _restore(conn, rows):
    for todo_id, value in rows:
        conn.execute(
            sa.text("UPDATE todo SET due_date = :value WHERE id = :id"),
            {"value": value, "id": todo_id},
        )


def upgrade():
    conn = op.get_bind()
    # 'YYYY-MM-DD' -> 'YYYY-MM-DD 00:00:00.000000' (ครบกำหนดเที่ยงคืนของวันนั้น)
    saved = [
        (row[0], f"{row[1]} 00:00:00.000000" if len(str(row[1])) == 10 else str(row[1]))
        for row in _fetch_due_dates(conn)
    ]

    with op.batch_alter_table("todo", schema=None) as batch_op:
        batch_op.alter_column(
            "due_date", existing_type=sa.DATE(), type_=sa.DateTime(), existing_nullable=True
        )

    _restore(conn, saved)


def downgrade():
    conn = op.get_bind()
    # ตัดเวลาทิ้ง เหลือแค่วัน
    saved = [(row[0], str(row[1])[:10]) for row in _fetch_due_dates(conn)]

    with op.batch_alter_table("todo", schema=None) as batch_op:
        batch_op.alter_column(
            "due_date", existing_type=sa.DateTime(), type_=sa.DATE(), existing_nullable=True
        )

    _restore(conn, saved)
