"""DB backend เป็น plugin ชนิด `db` — สัญญาตาม ADR 0026 (Phase 5 · P5-05)

ชนิดนี้ต่างจาก theme/auth สามข้อ และเทสต์ชุดนี้คือที่ที่ความต่างถูกบังคับ:
ถอดตัวสุดท้ายออกแล้วไม่มีระบบเหลือ · active ได้ทีละตัว · การสลับคือการย้ายข้อมูล

**ไม่มีเทสต์ไหนในไฟล์นี้ต่อฐานข้อมูลยี่ห้ออื่นจริง** — ทั้งหมดตรวจ *การเลือก*
และ *ข้อห้าม* ซึ่งพิสูจน์ได้โดยไม่ต้องมี server และรันได้ในโหมด `bare`
ส่วนพฤติกรรมจริงของแต่ละยี่ห้อเป็นงานของ CI matrix (P5-04)
"""

import json
import shutil

import pytest

from app import db_engine, plugins
from tests.conftest import TestConfig

SQLITE_KEY = "db/sqlite"
MYSQL_KEY = "db/mysql"


@pytest.fixture
def temp_backend():
    """วาง backend ชั่วคราวลงดิสก์จริงแล้วเก็บกวาดให้ — เหมือนการเพิ่มยี่ห้อจริง"""
    created = []

    def make(backend_id, manifest=None, module=None):
        directory = plugins.PLUGIN_ROOT / plugins.DB_TYPE / backend_id
        directory.mkdir(parents=True)
        created.append(directory)
        (directory / "plugin.json").write_text(
            json.dumps(
                manifest
                if manifest is not None
                else {"type": "db", "name": backend_id, "schemes": [backend_id]}
            )
        )
        if module is not None:
            (directory / "backend.py").write_text(module)
        plugins.forget_models()
        return directory

    yield make
    for directory in created:
        shutil.rmtree(directory, ignore_errors=True)
    plugins.forget_models()


# --- การเลือก backend จาก URL ---


def test_the_url_scheme_picks_the_backend(app):
    """ไม่มี config ตัวที่สองให้ขัดกันเอง — scheme ของ URL เป็นตัวตัดสินตัวเดียว"""
    with app.app_context():
        assert db_engine.active("sqlite:///x.db").key == SQLITE_KEY
        assert db_engine.active("mysql+pymysql://u@h/d").key == MYSQL_KEY
        assert db_engine.active("mariadb+pymysql://u@h/d").key == "db/mariadb"


def test_mariadb_is_not_treated_as_mysql(app):
    """คนละ dialect ใน SQLAlchemy 2.0 — รวมเป็นตัวเดียวแล้ว variant จะเพี้ยน

    (ดู `app/db_types.py`: `with_variant` ตัดสินจากชื่อ dialect ไม่ใช่จาก driver)
    """
    with app.app_context():
        assert db_engine.active("mariadb://u@h/d").key != db_engine.active("mysql://u@h/d").key


def test_an_unknown_scheme_refuses_to_start(app):
    """**ห้ามตกกลับไป SQLite เงียบ ๆ** (ADR 0026 ข้อ 2)

    prod ที่ตั้ง config ผิดจะเขียนลงไฟล์เปล่าแล้ว "ทำงานได้" จนถึงวันที่มีคนถาม
    ว่าข้อมูลหายไปไหน — ความเสียหายของการเดาให้มากกว่าความไม่สะดวกของการไม่ start
    """
    with app.app_context(), pytest.raises(plugins.PluginError, match="postgresql") as caught:
        db_engine.active("postgresql://u@h/d")
    assert "sqlite" in str(caught.value), "ต้องบอกด้วยว่ามีอะไรให้เลือกบ้าง"


def test_adding_a_brand_new_brand_touches_no_core_code(app, temp_backend):
    """วางไดเรกทอรีแล้วต่อยี่ห้อใหม่ได้ทันที ไม่ต้องแก้ core สักบรรทัด"""
    temp_backend("cockroach", manifest={"type": "db", "name": "x", "schemes": ["cockroachdb"]})
    with app.app_context():
        assert db_engine.active("cockroachdb://u@h/d").key == "db/cockroach"


# --- ข้อห้ามของชนิดนี้ ---


def test_the_active_backend_cannot_be_switched_off(app):
    """สวิตช์ของ ADR 0025 ตั้งอยู่บนสมมติฐานว่า "ปิดแล้วระบบยังเดินได้"

    ซึ่งใช้กับ backend ที่ใช้อยู่ไม่ได้เลย — ปล่อยให้ปิดคือการเสนอปุ่มที่กดแล้วดับ
    """
    with app.app_context():
        app.config["DISABLED_PLUGINS"] = frozenset({SQLITE_KEY})
        with pytest.raises(plugins.PluginError, match="DATABASE_URL"):
            db_engine.active(TestConfig.SQLALCHEMY_DATABASE_URI)


def test_a_backend_that_is_not_in_use_may_be_switched_off(app):
    """ตัวที่ไม่ได้ใช้ปิดได้ตามปกติ — ข้อห้ามข้างบนแคบเท่าที่จำเป็นเท่านั้น"""
    with app.app_context():
        app.config["DISABLED_PLUGINS"] = frozenset({MYSQL_KEY})
        assert db_engine.active(TestConfig.SQLALCHEMY_DATABASE_URI).key == SQLITE_KEY


def test_a_backend_may_not_own_tables(app, temp_backend):
    """**เป็นเจ้าของทางที่ข้อมูลวิ่งผ่าน ไม่ใช่เจ้าของข้อมูล** (ADR 0026 ข้อ 3)"""
    directory = temp_backend("greedy")
    (directory / "models.py").write_text(
        "from sqlalchemy.orm import Mapped, mapped_column\n"
        "from app import db\n\n\n"
        "class Greedy(db.Model):\n"
        '    __tablename__ = "tdl_db_greedy_thing"\n'
        "    id: Mapped[int] = mapped_column(primary_key=True)\n"
    )
    plugins.forget_models()
    with app.app_context(), pytest.raises(plugins.PluginError, match="ห้ามมีตารางของตัวเอง"):
        plugins.check_installation()
    from app import db

    table = db.metadata.tables.get("tdl_db_greedy_thing")
    if table is not None:  # เก็บกวาด metadata ไม่ให้ค้างไปเทสต์ตัวถัดไป
        db.metadata.remove(table)


def test_uninstall_says_why_it_is_the_wrong_command(app):
    """`plugin-uninstall db/sqlite` ต้องไม่ตอบว่า "ไม่มีตารางให้ลบ" เฉย ๆ

    ประโยคนั้นจริงแต่ทำให้คนอ่านเข้าใจว่าถอนสำเร็จแล้ว ทั้งที่ยังต่อยี่ห้อนั้นอยู่
    """
    result = app.test_cli_runner().invoke(args=["plugin-uninstall", SQLITE_KEY, "--yes"])
    assert result.exit_code != 0
    assert "owns no data" in result.output
    assert "DATABASE_URL" in result.output, "ต้องบอกทางที่ถูกต้องด้วย"


# --- ค่าเฉพาะยี่ห้อย้ายไปอยู่กับยี่ห้อนั้นแล้ว ---


def test_the_sqlite_pragma_lives_with_sqlite_not_in_core(app):
    """core ต้องไม่มีโค้ดที่เจาะจงยี่ห้อหลงเหลือ (ADR 0026)

    ตัว pragma ทำงานจริงหรือไม่ วัดที่ `tests/test_db_integrity.py` ซึ่งดู *ผล*
    (insert ที่ผิดต้อง IntegrityError) ไม่ใช่ดูว่าโค้ดอยู่ไฟล์ไหน — สองด่านนี้
    คนละหน้าที่กัน ตัวนั้นจับว่ามันพัง ตัวนี้จับว่ามันกลับไปกองรวมที่เดิม
    """
    core = (plugins.PLUGIN_ROOT.parent / "db_engine.py").read_text(encoding="utf-8")
    assert "PRAGMA" not in core
    assert "sqlite3" not in core

    with app.app_context():
        module = db_engine.load(TestConfig.SQLALCHEMY_DATABASE_URI)
    assert module is not None, "backend ของ sqlite ต้องมี backend.py ให้โหลด"
    assert "PRAGMA foreign_keys=ON" in (
        plugins.PLUGIN_ROOT / "db" / "sqlite" / "backend.py"
    ).read_text(encoding="utf-8")


def test_a_backend_without_settings_needs_no_module(app):
    """ไม่ต้องตั้งอะไรก็ไม่ต้องมีไฟล์ — "ไม่มีของชิ้นนี้" เป็นเส้นทางปกติ (ADR 0025)"""
    with app.app_context():
        assert db_engine.load("mysql+pymysql://u@h/d") is None
