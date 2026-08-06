"""ค่าระดับ connection ของ SQLite — ย้ายมาจาก `app/db_engine.py` ของ core (ADR 0026)

**SQLite ปิดการบังคับ foreign key ไว้เป็นค่าเริ่มต้น** และเป็นค่าที่ตั้ง
**ต่อ connection** ไม่ใช่ต่อไฟล์ฐานข้อมูล — ตั้งครั้งเดียวตอน migrate ไม่พอ
ทุก connection ใหม่ (รวมที่ connection pool สร้างเพิ่มระหว่างทาง) ต้องตั้งเอง

ผลของการไม่ตั้ง: `ondelete="SET NULL"` ของ `Todo.category_id` ไม่ทำงานเลย
ลบหมวดแล้วงานจะเหลือ `category_id` ที่ชี้ไปแถวที่ไม่มีอยู่ — ข้อมูลเสียแบบเงียบ ๆ
และ query ที่ join จะได้ผลลัพธ์หายไปโดยไม่มี error

**ทำไมถึงเป็นของ plugin ไม่ใช่ของ core**: นี่คือเรื่องของยี่ห้อนี้ล้วน ๆ
ยี่ห้ออื่นบังคับ FK อยู่แล้วโดยไม่ต้องสั่ง การเก็บไว้ใน core แปลว่าโค้ดที่
เจาะจงยี่ห้อหนึ่งจะค้างอยู่ตลอดไปแม้ระบบจะไม่ได้ใช้ยี่ห้อนั้นแล้ว (ADR 0026:
backend เป็นเจ้าของ *ทาง* ที่ข้อมูลวิ่งผ่าน ซึ่งรวมค่าที่ต้องตั้งทุกครั้งที่ต่อ)
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

    **ตัวเช็ค `isinstance` ไม่ใช่ของเกิน** ถึงโมดูลนี้จะถูกโหลดเฉพาะตอนที่
    SQLite เป็น backend ที่ใช้อยู่ แต่ listener ผูกกับคลาส `Engine` จึงโดน
    ทุก engine ในโปรเซส รวม engine ของยี่ห้ออื่นที่อาจถูกสร้างขึ้นมาพร้อมกัน
    (เช่นสคริปต์ย้ายข้อมูลข้ามยี่ห้อ) — pragma นี้สั่งกับยี่ห้ออื่นแล้ว error
    """
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
