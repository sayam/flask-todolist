"""ตั้งค่าระดับ connection ที่ต้องทำทุกครั้งที่ต่อฐานข้อมูล

**SQLite ปิดการบังคับ foreign key ไว้เป็นค่าเริ่มต้น** และเป็นค่าที่ตั้ง
**ต่อ connection** ไม่ใช่ต่อไฟล์ฐานข้อมูล — ตั้งครั้งเดียวตอน migrate ไม่พอ
ทุก connection ใหม่ (รวมที่ connection pool สร้างเพิ่มระหว่างทาง) ต้องตั้งเอง

ผลของการไม่ตั้ง: `ondelete="SET NULL"` ของ `Todo.category_id` ไม่ทำงานเลย
ลบหมวดแล้วงานจะเหลือ `category_id` ที่ชี้ไปหมวดที่ไม่มีอยู่ — ข้อมูลเสียแบบเงียบ ๆ
และ query ที่ join จะได้ผลลัพธ์หายไปโดยไม่มี error

ยี่ห้ออื่น (PostgreSQL/MySQL/MariaDB) บังคับ FK อยู่แล้วโดยไม่ต้องสั่ง
โมดูลนี้จึงเช็ค dialect ก่อน และเป็นที่สำหรับใส่ค่าเฉพาะยี่ห้ออื่นใน Phase 5
"""

import sqlite3

from sqlalchemy import event
from sqlalchemy.engine import Engine


@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection: object, _connection_record: object) -> None:
    """เปิดการบังคับ foreign key ให้ทุก connection ของ SQLite

    ผูกกับคลาส `Engine` (ไม่ใช่ engine ตัวใดตัวหนึ่ง) เพราะ Flask-SQLAlchemy
    สร้าง engine ตอนมี app context ครั้งแรก และเทสต์กับ migration สร้าง engine
    ของตัวเองอีกหลายตัว — ผูกที่คลาสจึงครอบทุกตัวโดยไม่ต้องไล่ผูกทีละที่

    เช็คด้วย `isinstance` กับ `sqlite3.Connection` ตามที่เอกสาร SQLAlchemy แนะนำ
    ยี่ห้ออื่นไม่มี pragma นี้ สั่งไปจะ error
    """
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
