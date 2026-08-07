"""foreign key ต้องถูกบังคับจริงระดับฐานข้อมูล ไม่ใช่แค่ประกาศไว้ใน model

SQLite ปิดการบังคับ FK เป็นค่าเริ่มต้น และเป็นค่า **ต่อ connection**
ถ้า listener ใน `app/db_engine.py` ไม่ทำงาน ทุกอย่างจะดูปกติดีทุกประการ —
ไม่มี error ไม่มีเทสต์แดง มีแต่ข้อมูลที่ชี้ไปแถวที่ไม่มีอยู่จริงสะสมไปเรื่อย ๆ
ชุดนี้จึงตรวจ "ผล" ของการบังคับ ไม่ใช่แค่ค่า pragma
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import Category, Todo
from tests.conftest import TestConfig

# `PRAGMA` เป็นคำสั่งของ SQLite เท่านั้น ยี่ห้ออื่นบังคับ FK อยู่แล้วโดยไม่ต้องสั่ง
# **ข้ามอย่างเปิดเผยด้วย skipif ไม่ใช่ try/except** — pytest รายงานจำนวนที่ข้ามทุกครั้ง
# ส่วนเทสต์ที่วัด *ผล* ของการบังคับ (ข้างล่าง) ไม่ข้าม เพราะเป็นข้อกำหนดของทุกยี่ห้อ
sqlite_only = pytest.mark.skipif(
    not TestConfig.SQLALCHEMY_DATABASE_URI.startswith("sqlite"),
    reason="PRAGMA เป็นของ SQLite — ยี่ห้ออื่นบังคับ FK เองอยู่แล้ว",
)


@sqlite_only
def test_pragma_is_on_for_a_fresh_connection(app):
    with app.app_context():
        value = db.session.execute(text("PRAGMA foreign_keys")).scalar()
    assert value == 1, "foreign_keys ต้องเป็น 1 ทุก connection ไม่ใช่แค่ตัวแรก"


@sqlite_only
def test_pragma_survives_a_new_connection(app):
    """connection pool สร้าง connection เพิ่มระหว่างทางได้ ตัวใหม่ต้องได้ค่าเดียวกัน"""
    with app.app_context():
        db.session.execute(text("SELECT 1"))
        db.session.remove()  # คืน connection แล้วขอใหม่
        value = db.session.execute(text("PRAGMA foreign_keys")).scalar()
    assert value == 1


def test_todo_cannot_point_at_a_missing_user(app, user_id):
    """งานที่ user_id ชี้ไปคนที่ไม่มีอยู่ต้องเขียนลงไม่ได้เลย"""
    with app.app_context():
        db.session.add(Todo(title="งานของผีน้อย", user_id=user_id + 999))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_category_cannot_point_at_a_missing_user(app, user_id):
    with app.app_context():
        db.session.add(Category(name="หมวดของผีน้อย", user_id=user_id + 999))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_deleting_a_category_nulls_the_link_not_the_task(app, user_id, category_id):
    """`ondelete="SET NULL"` ต้องทำงานจริง — ไม่งั้นงานจะเหลือ category_id
    ที่ชี้ไปหมวดที่ไม่มีอยู่ ซึ่งเป็นข้อมูลเสียแบบที่ไม่มีใครเห็น

    ลบด้วย SQL ตรง ๆ เพื่อวัดพฤติกรรมของฐานข้อมูล ไม่ใช่ของ ORM
    (route จริงห้ามลบหมวดที่ยังมีงานอยู่ — คนละด่านกัน)
    """
    with app.app_context():
        todo = Todo(title="งานที่มีหมวด", user_id=user_id, category_id=category_id)
        db.session.add(todo)
        db.session.commit()
        todo_id = todo.id

        db.session.execute(text("DELETE FROM tdl_category WHERE id = :id"), {"id": category_id})
        db.session.commit()
        db.session.expire_all()

        survivor = db.session.get(Todo, todo_id)
        assert survivor is not None, "ลบหมวดแล้วงานต้องไม่หายไปด้วย"
        assert survivor.category_id is None, "ลิงก์ไปหมวดที่ถูกลบต้องกลายเป็น NULL"
