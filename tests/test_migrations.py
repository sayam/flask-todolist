"""migration ต้องรันได้จริงกับฐานข้อมูลจริง ไม่ใช่แค่ import ผ่าน

เทสต์ที่เหลือใช้ `db.create_all()` ซึ่งสร้างตารางจาก model ตรง ๆ **ไม่ได้ผ่าน
migration เลย** ชุดนี้จึงเป็นที่เดียวที่พิสูจน์ว่า `flask db upgrade` ทำงานจริง

เหตุที่ต้องมี: ตอน Phase 2 เคยมีบั๊กที่ env.py แตะ connection ก่อน
`context.configure()` ทำให้ migration ทั้งชุด **ถูก rollback เงียบ ๆ**
log ขึ้น "Running upgrade" ครบทุกตัว exit code เป็น 0 แต่ฐานข้อมูลไม่เปลี่ยนเลย
ไม่มี gate ตัวไหนในโปรเจกต์จับได้ เพราะเทสต์อื่นไม่เคยรัน migration
"""

import sqlite3

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import upgrade
from sqlalchemy import create_engine

from app import create_app, db
from tests.conftest import TestConfig

# ตารางของ core หลัง Phase 2 — ทุกตัวต้องมี prefix (ดู docs/STANDARDS.md ข้อ 1.1)
CORE_TABLES = {"tdl_user", "tdl_category", "tdl_todo"}
VERSION_TABLE = "tdl_alembic_version"

# ชื่อเดิมก่อนใส่ prefix ต้องไม่หลงเหลือ — `user` เป็น reserved word ของ
# PostgreSQL/Oracle/MSSQL ด้วย
LEGACY_TABLES = {"user", "category", "todo", "alembic_version"}


def _tables(db_path):
    with sqlite3.connect(db_path) as conn:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _upgrade_into(db_path, revision="head"):
    class MigrationConfig(TestConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"

    app = create_app(MigrationConfig)
    with app.app_context():
        upgrade(revision=revision)


@pytest.fixture
def migrated(tmp_path):
    """ฐานข้อมูลเปล่าที่ผ่าน `flask db upgrade` มาจริง ๆ"""
    db_path = tmp_path / "migrated.db"
    _upgrade_into(db_path)
    return db_path


def test_running_a_migration_does_not_silence_the_app_log(app, migrated):
    """`fileConfig()` ของ alembic ต้องไม่ปิด logger ของแอปทิ้ง

    ค่าเริ่มต้นของ `fileConfig` คือ `disable_existing_loggers=True` ซึ่งตั้ง
    `disabled = True` ให้ทุก logger ที่ไม่ได้ถูกระบุใน alembic.ini — รวมถึงของแอปเอง
    ผลคือทุกอย่างที่แอปเขียนหลังจากนั้น **หายเงียบทั้ง process** ไม่มี error ให้เห็น
    ซึ่งแปลว่าเหตุการณ์ด้านความปลอดภัยก็หายไปด้วย (เจอเพราะเทสต์ของ Phase 4.5
    แดงเฉพาะตอนรันทั้งชุด)
    """
    import logging

    lines = []

    class Grab(logging.Handler):
        def emit(self, record):
            lines.append(record.getMessage())

    handler = Grab(level=logging.WARNING)
    app.logger.addHandler(handler)
    try:
        app.logger.warning("ยังได้ยินอยู่ไหม")
    finally:
        app.logger.removeHandler(handler)
    assert lines == ["ยังได้ยินอยู่ไหม"], "log ของแอปถูกปิดไปตอนรัน migration"


def test_upgrade_creates_the_core_tables(migrated):
    missing = CORE_TABLES - _tables(migrated)
    assert not missing, f"migration ไม่ได้สร้างตาราง: {missing}"


def test_upgrade_actually_stamps_the_version(migrated):
    """ด่านที่จับบั๊ก rollback เงียบ — ตารางเวอร์ชันว่าง = migration ไม่ได้ commit"""
    with sqlite3.connect(migrated) as conn:
        # S608: VERSION_TABLE เป็นค่าคงที่ในไฟล์นี้ ไม่ได้มาจาก input ภายนอก
        stamped = conn.execute(f"SELECT version_num FROM {VERSION_TABLE}").fetchall()  # noqa: S608
    assert len(stamped) == 1, f"{VERSION_TABLE} ต้องมีเวอร์ชันหัวปัจจุบันหนึ่งแถว ได้ {stamped}"


def test_no_legacy_table_names_remain(migrated):
    left = LEGACY_TABLES & _tables(migrated)
    assert not left, f"ยังมีตารางชื่อเก่าเหลืออยู่: {left}"


def test_todo_uses_is_done_not_done(migrated):
    with sqlite3.connect(migrated) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(tdl_todo)")}
    assert "is_done" in columns
    assert "done" not in columns


def test_constraints_follow_the_naming_convention(migrated):
    """ชื่อ constraint ต้องมาจาก NAMING_CONVENTION ไม่ใช่ชื่อ auto ของ DB"""
    with sqlite3.connect(migrated) as conn:
        ddl = "\n".join(
            row[0] for row in conn.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL")
        )
    for expected in (
        "pk_tdl_user",
        "uq_tdl_user_username",
        "fk_tdl_category_user_id_tdl_user",
        "fk_tdl_todo_user_id_tdl_user",
        "ix_tdl_todo_user_id",
    ):
        assert expected in ddl, f"ไม่พบ constraint/index ชื่อ {expected}"


def _is_plugin(entry):
    """ตารางของ plugin ไม่อยู่ในสาย migration ของ core โดยตั้งใจ (ADR 0023)

    กรองด้วยเกณฑ์เดียวกับ `include_object` ใน `migrations/env.py` — ถ้าที่นี่กับ
    ที่นั่นใช้คนละเกณฑ์ เทสต์จะแดงทั้งที่ `flask db check` เขียว (หรือกลับกัน)
    """
    from app import plugins

    if not isinstance(entry, tuple):
        return False
    target = entry[1]
    # index/constraint บอกชื่อของตัวเอง ไม่ใช่ชื่อตาราง ต้องถามผ่าน `.table` ก่อน
    # (ไม่งั้น `ix_tdl_auth_totp_secret_user_id` จะไม่ถูกกรอง ทั้งที่ตารางถูกกรองแล้ว)
    table = getattr(target, "table", None)
    name = getattr(table, "name", None) or getattr(target, "name", None)
    return name in plugins.owned_tables()


def test_models_match_the_migrated_schema(migrated):
    """model กับ schema ที่ได้จาก migration ต้องตรงกันเป๊ะ (เทียบเท่า `flask db check`)

    เหตุที่ต้องมี: `SoftDeleteMixin.deleted_at` เคยไม่ประกาศ `index=True` ทั้งที่
    migration b7e3d91c5a2f สร้าง index ไว้ ผลคือ `flask db migrate` ครั้งถัดไป
    จะออก migration ที่ **drop index ทิ้งทั้งสามตาราง** เงียบ ๆ ทำให้ทุก SELECT
    ในระบบ (ซึ่งมี `deleted_at IS NULL` ต่อท้ายเสมอ) เสียประสิทธิภาพ
    ไม่มี gate ตัวไหนจับได้ เพราะเทสต์อื่นสร้างตารางจาก model ด้วย `db.create_all()`
    จึงตรงกับ model เสมอโดยนิยาม — ต้องเทียบกับของที่ migration สร้างเท่านั้น
    """

    class MigrationConfig(TestConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{migrated}"

    app = create_app(MigrationConfig)
    engine = create_engine(f"sqlite:///{migrated}")
    with app.app_context(), engine.connect() as conn:
        # version_table ต้องตรงกับ env.py ไม่งั้น alembic จะรายงานว่ามันเป็นตารางส่วนเกิน
        context = MigrationContext.configure(conn, opts={"version_table": VERSION_TABLE})
        diff = [entry for entry in compare_metadata(context, db.metadata) if not _is_plugin(entry)]
    engine.dispose()

    assert not diff, f"model กับ migration ไม่ตรงกัน: {diff}"


def test_legacy_version_table_is_adopted(migrated):
    """ฐานข้อมูลที่ยังใช้ชื่อ `alembic_version` เดิมต้องอัปเกรดต่อได้

    ถ้า env.py ไม่เปลี่ยนชื่อให้ alembic จะมองว่าฐานข้อมูลว่าง แล้วไล่รัน
    migration ตั้งแต่ตัวแรก → พังเพราะตารางมีอยู่แล้ว
    """
    with sqlite3.connect(migrated) as conn:
        conn.execute(f"ALTER TABLE {VERSION_TABLE} RENAME TO alembic_version")
        conn.commit()

    _upgrade_into(migrated)  # ต้องไม่ raise

    names = _tables(migrated)
    assert VERSION_TABLE in names
    assert "alembic_version" not in names


# --- การยุบสายเดิม (Phase 5 — P5-02) ---
# สายเดิม 13 ตัวถูกยุบเป็น baseline ตัวเดียวเพราะมี raw SQL สามจุดที่อ้างตาราง
# `user` โดยไม่ quote (reserved word ของ PostgreSQL/Oracle/MSSQL)
# ฐานข้อมูลที่มีอยู่แล้วจึงชี้ไปเวอร์ชันที่ไม่มีไฟล์อยู่จริงอีกต่อไป

SQUASHED_HEAD = "401e0ce7011f"
# baseline ที่ยุบสายเดิมทั้งชุดมาไว้ในตัวเดียว (P5-02)
BASELINE = "5ffefa218ed7"
MID_CHAIN = "18dccb13a980"


def _version_of(db_path):
    with sqlite3.connect(db_path) as conn:
        # S608 ปลอดภัยตรงนี้ — VERSION_TABLE เป็นค่าคงที่ในไฟล์นี้ ไม่ได้มาจากภายนอก
        return conn.execute(f"SELECT version_num FROM {VERSION_TABLE}").fetchone()[0]  # noqa: S608


def _stamp(db_path, revision):
    """ตั้งเวอร์ชันที่ฐานข้อมูลอ้าง เพื่อจำลองฐานที่ค้างอยู่ที่จุดต่าง ๆ ของสายเดิม"""
    with sqlite3.connect(db_path) as conn:
        conn.execute(f"UPDATE {VERSION_TABLE} SET version_num = ?", (revision,))  # noqa: S608
        conn.commit()


def _upgrade_via_cli(db_path):
    """รัน `flask db upgrade` ผ่าน CLI จริง เพื่อดู **สิ่งที่ผู้ดูแลเห็น**

    ไม่เรียก `flask_migrate.upgrade()` ตรง ๆ เพราะมันถูกห่อด้วย `catch_errors`
    ที่แปลง `RuntimeError` เป็น log + `sys.exit(1)` — การทดสอบที่ข้ามชั้นนั้นไป
    จะพิสูจน์ว่ามี exception ขึ้น แต่ไม่ได้พิสูจน์ว่าคำสั่งจบด้วยรหัสที่ไม่ใช่ 0
    และไม่ได้พิสูจน์ว่าข้อความบอกทางออกไว้ ซึ่งเป็นสองอย่างที่มีผลจริงตอนใช้งาน
    """

    class MigrationConfig(TestConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{db_path}"

    return create_app(MigrationConfig).test_cli_runner().invoke(args=["db", "upgrade"])


def test_a_database_at_the_old_head_is_adopted_without_asking(migrated):
    """ฐานที่อยู่ปลายสายเดิมต้องอัปเกรดต่อได้เลย ไม่ต้องให้ใครไปพิมพ์ `db stamp`

    ขั้นตอนที่ต้องทำด้วยมือคือขั้นตอนที่วันหนึ่งจะมีคนข้าม แล้วไปเจอ
    "Can't locate revision" ตอนตีสามโดยไม่มีบริบทว่าต้องทำอะไรต่อ
    (หลักเดียวกับ `test_legacy_version_table_is_adopted` ข้างบน)
    """
    # **ต้องสร้างฐานที่ baseline ไม่ใช่ที่ปลายสายปัจจุบัน** — ฐานจริงที่ค้างอยู่ที่
    # สายเดิมย่อมไม่มีตารางของ migration ที่มาทีหลัง การ stamp ฐานที่อัปเกรดครบ
    # แล้วย้อนกลับไป จึงเป็นการจำลองสถานการณ์ที่ไม่มีอยู่จริง (และทำให้เทสต์นี้
    # แดงด้วย "table already exists" ทันทีที่มีใครเพิ่ม migration ตัวถัดไป)
    fresh = migrated.parent / "at-baseline.db"
    _upgrade_into(fresh, revision=BASELINE)
    _stamp(fresh, SQUASHED_HEAD)
    before = _tables(fresh)

    _upgrade_into(fresh)  # ต้องไม่ raise

    assert _version_of(fresh) != SQUASHED_HEAD, "ต้องถูกรับช่วงไปเป็น baseline แล้ว"
    # **ไม่ยืนยันว่าตารางเท่าเดิม** เพราะ migration ที่มาหลัง baseline เพิ่มตารางได้
    # สิ่งที่การรับช่วงห้ามทำคือ *ทำของหาย* ไม่ใช่ห้ามเดินหน้าต่อ
    assert before <= _tables(fresh), "การรับช่วงต้องไม่ทำให้ตารางไหนหายไป"


def test_a_database_stuck_mid_chain_is_refused_not_stamped(migrated):
    """ฐานที่ค้างกลางสายเดิมต้องถูกปฏิเสธ **ไม่ใช่ถูกดันไป baseline ให้**

    ตารางของมันยังไม่ครบ การ stamp ให้คือการโกหกว่า schema พร้อมแล้ว
    แล้วแอปจะไปพังตอน query ด้วย "no such column" ซึ่งไล่กลับมาหาต้นเหตุยากมาก
    """
    _stamp(migrated, MID_CHAIN)

    result = _upgrade_via_cli(migrated)

    assert result.exit_code != 0, "ต้องจบด้วยรหัสที่ไม่ใช่ 0 ไม่งั้นสคริปต์ deploy จะเดินต่อ"
    assert "กลางสายเดิม" in result.output
    assert SQUASHED_HEAD in result.output, "ต้องบอกด้วยว่าต้อง upgrade ไปถึงตัวไหนก่อน"
    assert _version_of(migrated) == MID_CHAIN, "ถูกปฏิเสธแล้วต้องไม่แก้เวอร์ชันทิ้งไว้"
