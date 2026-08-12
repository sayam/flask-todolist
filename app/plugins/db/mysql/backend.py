"""ระดับการแยก transaction ของ mysql — **READ COMMITTED** (ADR 0036)

ค่าเริ่มต้นของยี่ห้อนี้คือ REPEATABLE READ ซึ่งตั้ง snapshot ไว้ตั้งแต่ query
แรกของ transaction · สาย audit ต้องอ่าน "หางสายล่าสุด" ให้ได้ **หลัง** ที่มัน
ต่อคิวสำเร็จ ซึ่งขัดกับ snapshot ที่ถูกตั้งไปก่อนหน้านั้นเสมอ เพราะคำขอจริง
ทุกใบอ่านข้อมูลก่อนเขียน — ผลคือผู้เขียนที่ต่อคิวกันเรียบร้อยยังต่อสายด้วย
`prev_hash` เดียวกัน แล้วชนกุญแจ unique (MySQL) หรือถูกปฏิเสธด้วย
`Record has changed since last read` (MariaDB ที่เปิด innodb_snapshot_isolation)

**ทำไมถึงเป็นของ plugin ไม่ใช่ของ core**: SQLite ไม่รู้จักค่านี้ด้วยซ้ำ
การตั้งที่ core แปลว่าต้องมี if ของยี่ห้อในโค้ดที่ไม่ควรรู้จักยี่ห้อไหนเลย
(ADR 0026 — backend เป็นเจ้าของ *ทาง* ที่ข้อมูลวิ่งผ่าน ซึ่งรวมค่าที่ต้องตั้ง
ทุกครั้งที่ต่อ) · หลักเดียวกับ PRAGMA ของ SQLite ที่อยู่ใน backend ของมันเอง
"""

import pymysql
from sqlalchemy import event
from sqlalchemy.engine import Engine

ISOLATION_LEVEL = "READ COMMITTED"


@event.listens_for(Engine, "connect")
def _set_read_committed(dbapi_connection: object, _connection_record: object) -> None:
    """ตั้งระดับการแยกให้ทุก connection — เป็นค่าต่อ session ไม่ใช่ต่อฐานข้อมูล

    ผูกกับคลาส `Engine` เพราะ Flask-SQLAlchemy สร้าง engine ตอนมี app context
    ครั้งแรก และเทสต์กับ migration สร้าง engine ของตัวเองอีกหลายตัว

    **ตัวเช็คชนิดของ connection ไม่ใช่ของเกิน** — listener ผูกกับคลาส `Engine`
    จึงโดนทุก engine ในโปรเซส รวมของยี่ห้ออื่นที่อาจถูกสร้างพร้อมกัน
    """
    if isinstance(dbapi_connection, pymysql.connections.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute(f"SET SESSION TRANSACTION ISOLATION LEVEL {ISOLATION_LEVEL}")
        cursor.close()
