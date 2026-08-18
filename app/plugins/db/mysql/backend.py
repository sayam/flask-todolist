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


# **เพดานของการ *รอคำตอบ* ต่างจากเพดานของการ *ต่อสาย*** (audit รอบ 11 · ADR 0067)
# `read_timeout`/`write_timeout` ของ pymysql มีค่าเริ่มต้นเป็น `None` = รอตลอดกาล
# ฐานที่รับ TCP แล้วเงียบจึงทำให้คำขอค้างจนกว่า gunicorn จะฆ่า worker ทิ้ง
# — เพดานที่มีอยู่จึงเป็นของคนอื่นทั้งคู่ ไม่ใช่ของเรา
#
# 60 วินาทีเลือกให้ **ยาวกว่างานที่ยาวที่สุดที่เราตั้งใจให้เกิด** (การลบตามรอบของ
# `purge-expired` ซึ่งหน่วย systemd ให้เวลาไว้ 30 นาที แต่แต่ละคำสั่งจบในไม่กี่วินาที)
# และสั้นกว่า "ตลอดกาล" อย่างมีความหมาย · ถ้าวันหนึ่ง purge ชนเพดานนี้ แปลว่า
# ข้อมูลโตเกินกว่าที่การลบครั้งเดียวจะไหว ซึ่งเป็นข่าวที่ควรดัง ไม่ใช่ควรรอเงียบ ๆ
READ_TIMEOUT_SECONDS = 60
WRITE_TIMEOUT_SECONDS = 60
# ค่าเริ่มต้นของ pymysql คือ 10 อยู่แล้ว — ประกาศซ้ำเพราะค่าที่สำคัญต้องอ่านได้
# จากไฟล์ของเรา ไม่ใช่จากเอกสารของไลบรารีที่เปลี่ยนใต้เท้าได้
CONNECT_TIMEOUT_SECONDS = 10


@event.listens_for(Engine, "do_connect")
def bound_every_wait(dialect: object, _record: object, _cargs: object, cparams: dict) -> None:
    """ประกาศเพดานของการรอ ตอนที่ connection ถูกสร้าง (เรียกตรง ๆ ได้จากเทสต์)

    ใช้ `do_connect` ไม่ใช่ `connect` เพราะค่าพวกนี้ต้องส่งเข้า driver **ตอนต่อ**
    ไม่ใช่สั่งหลังต่อเสร็จ · `setdefault` เพื่อให้ `DATABASE_URL` ที่ระบุค่ามาเอง
    ชนะเสมอ — ผู้ deploy ที่รู้สภาพของตัวเองดีกว่าเรา ต้องแทนที่ได้โดยไม่ต้องแก้โค้ด
    """
    if getattr(dialect, "driver", "") != "pymysql":
        return
    cparams.setdefault("connect_timeout", CONNECT_TIMEOUT_SECONDS)
    cparams.setdefault("read_timeout", READ_TIMEOUT_SECONDS)
    cparams.setdefault("write_timeout", WRITE_TIMEOUT_SECONDS)
