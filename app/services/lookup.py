"""หาแถวตาม primary key แบบที่ id มั่ว ๆ ไม่ทำให้ระบบพัง

`<int:...>` ของ werkzeug รับตัวเลขยาวเท่าไหร่ก็ได้ และ id ที่ฝังมาในตัว token
ก็เป็นตัวเลขที่คนนอกพิมพ์มาเองได้เช่นกัน ตัวเลขที่ใหญ่เกินช่วงของ 64 บิตทำให้
ไดรเวอร์ฐานข้อมูล **โยน `OverflowError` ออกมาก่อนจะได้ query ด้วยซ้ำ** ผลคือ 500
ทั้งที่คำตอบที่ถูกต้องคือ "ไม่มีแถวนี้" (เจอจากการ fuzz ด้วย schemathesis —
กระทบทั้งหน้าเว็บและ API เพราะทั้งคู่เดินผ่าน service ตัวเดียวกัน)
"""

from typing import cast

from app import db

# ช่วงของ INTEGER แบบมีเครื่องหมาย 64 บิต — เพดานของ SQLite/MySQL/PostgreSQL ตรงกัน
INT64_MAX = 2**63 - 1
INT64_MIN = -(2**63)


def by_id[T](model: type[T], row_id: int) -> T | None:
    """แถวตาม primary key — id ที่อยู่นอกช่วงของคอลัมน์แปลว่าไม่มีวันมีอยู่จริง"""
    if not INT64_MIN <= row_id <= INT64_MAX:
        return None
    # `db.Model` เป็น attribute แบบ dynamic ของ flask-sqlalchemy mypy จึงเห็น
    # `session.get()` คืน Any — cast ที่นี่ที่เดียวแทนที่จะให้ Any ไหลไปทั้ง service
    return cast("T | None", db.session.get(model, row_id))
