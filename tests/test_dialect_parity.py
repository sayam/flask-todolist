"""พฤติกรรมต้องเท่ากันทุกยี่ห้อ — ส่วนที่พิสูจน์ได้โดยไม่ต้องมี server (Phase 5)

ด่านนี้ตรวจ **DDL ที่จะถูกสร้าง** ไม่ใช่ผลของการรันจริง จึงรันได้ทุกที่รวมถึง
job `bare` ที่ไม่มี driver ของยี่ห้อไหนติดตั้งเลย (dialect ของ SQLAlchemy เป็น
โค้ด python ล้วน ๆ ส่วน driver ต้องมีก็ต่อเมื่อจะ *ต่อ* จริง)

ส่วนที่ต้องมี server จริงถึงจะพิสูจน์ได้ — ค่าที่เขียนไปแล้วอ่านกลับมาได้เท่าเดิม,
พฤติกรรมของ transaction, การเรียงลำดับตอนเวลาเท่ากัน — อยู่ใน CI matrix (P5-04)
**สองชั้นนี้ไม่แทนกัน**: ชั้นนี้จับ "ประกาศผิดตั้งแต่ต้น" ซึ่งถูกกว่าและเร็วกว่ามาก
ส่วนชั้นนั้นจับ "ประกาศถูกแต่ยี่ห้อนั้นทำอีกอย่าง"
"""

import pathlib

from sqlalchemy import DateTime
from sqlalchemy.dialects import mysql, registry, sqlite

from app import create_app, db
from tests.conftest import TestConfig

MIGRATIONS = pathlib.Path(__file__).resolve().parent.parent / "migrations" / "versions"

# MariaDB นับเป็นคนละ dialect กับ MySQL ใน SQLAlchemy 2.0 และ `with_variant`
# ตัดสินจาก **ชื่อ dialect** — ประกาศครอบแค่ `mysql` แล้ว MariaDB จะหลุดทันที
# `registry.load()` คืน dialect ที่ใช้ได้เลยโดยไม่ต้องมี driver ของยี่ห้อนั้น
MARIADB = registry.load("mariadb")


def _timestamp_columns():
    """คอลัมน์เวลาทุกตัวที่ระบบนี้มี — รวมของ plugin ที่ประกาศตารางของตัวเอง"""
    create_app(TestConfig)  # โหลด model ของ plugin เข้า metadata ด้วย (ADR 0023)
    return [
        column
        for table in db.metadata.tables.values()
        for column in table.columns
        if isinstance(column.type, DateTime)
    ]


def test_the_scanner_sees_the_timestamps_of_core_and_plugins():
    """กันเทสต์ข้างล่างเขียวเพราะ metadata ว่าง ไม่ใช่เพราะทุกคอลัมน์ถูกต้อง"""
    names = {f"{c.table.name}.{c.name}" for c in _timestamp_columns()}
    assert "tdl_user.created_at" in names
    assert "tdl_audit.created_at" in names
    assert "tdl_auth_totp_secret.confirmed_at" in names, "ตารางของ plugin ต้องถูกตรวจด้วย"


def test_no_timestamp_loses_its_fraction_on_mysql():
    """**`DATETIME` เปล่าของ MySQL/MariaDB ตัดเศษวินาทีทิ้งเงียบ ๆ**

    ไม่มี warning ไม่มี error — ค่าที่เขียนไปพร้อม microsecond จะอ่านกลับมาได้
    แค่ระดับวินาที ผลคืองานสองชิ้นที่สร้างห่างกันไม่กี่มิลลิวินาทีจะมี `created_at`
    เท่ากันเป๊ะ แล้วการเรียงลำดับจะสลับกันเองตามที่ engine คืนมา

    บั๊กแบบนี้โผล่เฉพาะตอนย้ายยี่ห้อ และตอนที่โผล่ ข้อมูลที่ถูกปัดไปแล้วก็
    ย้อนกลับไม่ได้ — ด่านนี้จึงตรวจตอนประกาศ ไม่ใช่ตอนเจอ
    """
    offenders = []
    for column in _timestamp_columns():
        for dialect in (mysql.dialect(), MARIADB):
            rendered = column.type.compile(dialect=dialect)
            if "DATETIME(6)" not in rendered:
                offenders.append(f"{column.table.name}.{column.name} → {rendered}")
    assert not offenders, (
        "คอลัมน์เวลาที่จะถูกตัดเศษวินาทีบน MySQL/MariaDB:\n"
        + "\n".join(offenders)
        + "\n\nใช้ `UTCDateTime` จาก app/db_types.py แทน `DateTime` เปล่า"
    )


def test_the_variant_does_not_touch_sqlite():
    """SQLite ต้องได้ DDL เหมือนเดิมเป๊ะ — ฐานที่มีอยู่แล้วจึงไม่ต้อง migrate

    ถ้าวันหนึ่งมีคนเปลี่ยน `UTCDateTime` เป็นชนิดที่ SQLite เห็นต่างไปจากเดิม
    ฐานข้อมูลของทุกคนที่ใช้อยู่จะกลายเป็น "ไม่ตรงกับ model" ทันทีโดยไม่มี
    migration รองรับ แล้ว `flask db check` จะแดงโดยที่ไม่มีใครตั้งใจแก้อะไร
    """
    rendered = {c.type.compile(dialect=sqlite.dialect()) for c in _timestamp_columns()}
    assert rendered == {"DATETIME"}, rendered


def test_migrations_declare_timestamps_the_same_way():
    """migration ที่เขียนใหม่ต้องไม่ถอยกลับไปใช้ `sa.DateTime` เปล่า

    `flask db migrate` ออกโค้ดเป็น `sa.DateTime()` ให้เสมอ — ต้องแก้เป็น
    `UTCDateTime` ด้วยมือทุกครั้ง ไม่งั้นตารางที่สร้างบน MySQL จะตัดเศษวินาที
    ทั้งที่ model ประกาศไว้ถูก (และ `flask db check` บนยี่ห้อนั้นจะแดงตามมา)
    """
    offenders = [
        f"{path.name}:{lineno}"
        for path in sorted(MIGRATIONS.glob("*.py"))
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if "sa.DateTime" in line
    ]
    assert not offenders, (
        "migration ประกาศเวลาด้วย `sa.DateTime` เปล่า: " + ", ".join(offenders) + "\nใช้ `UTCDateTime`"
    )
