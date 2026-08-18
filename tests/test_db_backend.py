"""DB backend เป็น plugin ชนิด `db` — สัญญาตาม ADR 0026 (Phase 5 · P5-05)

ชนิดนี้ต่างจาก theme/auth สามข้อ และเทสต์ชุดนี้คือที่ที่ความต่างถูกบังคับ:
ถอดตัวสุดท้ายออกแล้วไม่มีระบบเหลือ · active ได้ทีละตัว · การสลับคือการย้ายข้อมูล

**ไม่มีเทสต์ไหนในไฟล์นี้ต่อฐานข้อมูลยี่ห้ออื่นจริง** — ทั้งหมดตรวจ *การเลือก*
และ *ข้อห้าม* ซึ่งพิสูจน์ได้โดยไม่ต้องมี server และรันได้ในโหมด `bare`
ส่วนพฤติกรรมจริงของแต่ละยี่ห้อเป็นงานของ CI matrix (P5-04)
"""

import json
import os
import shutil

import pytest

from app import db, db_engine, plugins
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
                else {
                    "type": "db",
                    "name": backend_id,
                    "schemes": [backend_id],
                    "migration": "cold",
                }
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
    temp_backend(
        "cockroach",
        manifest={"type": "db", "name": "x", "schemes": ["cockroachdb"], "migration": "cold"},
    )
    with app.app_context():
        assert db_engine.active("cockroachdb://u@h/d").key == "db/cockroach"


# --- ข้อห้ามของชนิดนี้ ---


def test_the_active_backend_cannot_be_switched_off(app):
    """สวิตช์ของ ADR 0025 ตั้งอยู่บนสมมติฐานว่า "ปิดแล้วระบบยังเดินได้"

    ซึ่งใช้กับ backend ที่ใช้อยู่ไม่ได้เลย — ปล่อยให้ปิดคือการเสนอปุ่มที่กดแล้วดับ
    """
    with app.app_context():
        # ถามว่าตอนนี้ใครคือตัวที่ใช้อยู่ แทนที่จะสมมติว่าเป็น sqlite — เทสต์นี้
        # ต้องให้ผลเดียวกันตอน CI matrix ยิงด้วย TEST_DATABASE_URL ของยี่ห้ออื่น
        in_use = db_engine.active(TestConfig.SQLALCHEMY_DATABASE_URI).key
        app.config["DISABLED_PLUGINS"] = frozenset({in_use})
        with pytest.raises(plugins.PluginError, match="DATABASE_URL"):
            db_engine.active(TestConfig.SQLALCHEMY_DATABASE_URI)


def test_a_backend_that_is_not_in_use_may_be_switched_off(app):
    """ตัวที่ไม่ได้ใช้ปิดได้ตามปกติ — ข้อห้ามข้างบนแคบเท่าที่จำเป็นเท่านั้น"""
    with app.app_context():
        in_use = db_engine.active(TestConfig.SQLALCHEMY_DATABASE_URI)
        spare = next(key for key in {SQLITE_KEY, MYSQL_KEY} if key != in_use.key)
        app.config["DISABLED_PLUGINS"] = frozenset({spare})
        assert db_engine.active(TestConfig.SQLALCHEMY_DATABASE_URI).key == in_use.key


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
        # ระบุ URL ของ sqlite ตรง ๆ ไม่ใช่ค่าที่ config ชี้อยู่ — เทสต์นี้ถามถึง
        # backend ตัวนั้นโดยเฉพาะ ไม่ได้ถามถึงตัวที่บังเอิญถูกใช้ตอนรัน
        module = db_engine.load("sqlite:///:memory:")
    assert module is not None, "backend ของ sqlite ต้องมี backend.py ให้โหลด"
    assert "PRAGMA foreign_keys=ON" in (
        plugins.PLUGIN_ROOT / "db" / "sqlite" / "backend.py"
    ).read_text(encoding="utf-8")


def test_a_backend_without_settings_needs_no_module(app, temp_backend):
    """ไม่ต้องตั้งอะไรก็ไม่ต้องมีไฟล์ — "ไม่มีของชิ้นนี้" เป็นเส้นทางปกติ (ADR 0025)

    **ใช้ backend ชั่วคราวแทนการชี้ไปที่ยี่ห้อจริง** เพราะยี่ห้อจริงทุกตัวมี
    `backend.py` แล้ว (sqlite ตั้ง PRAGMA · mysql/mariadb ตั้งระดับการแยก
    transaction — ADR 0036) เทสต์ที่อ้างอิงยี่ห้อจริงจึงพังทันทีที่ยี่ห้อนั้น
    มีอะไรต้องตั้งเพิ่ม ทั้งที่กติกาที่มันคุ้มอยู่ไม่ได้เปลี่ยนเลย
    """
    temp_backend("plainbrand")
    with app.app_context():
        assert db_engine.load("plainbrand://u@h/d") is None


@pytest.mark.skipif(
    "sqlite" in os.environ.get("TEST_DATABASE_URL", "sqlite"),
    reason="SQLite ไม่มีระดับการแยก transaction ให้ตั้ง — ค่านี้เป็นของยี่ห้อที่มี MVCC",
)
def test_the_connection_really_runs_at_read_committed(app):
    """**ตรวจค่าที่ connection ใช้จริง ไม่ใช่ตรวจว่ามีบรรทัดที่สั่ง**

    ค่านี้เป็นของต่อ session การตั้งพลาดจึงไม่มี error ให้เห็นเลย — อาการคือ
    การเขียนขนานล้มเป็นครั้งคราวด้วยข้อความที่ไม่ได้ชี้มาทางนี้ (ADR 0036)
    """
    from sqlalchemy import text

    with app.app_context():
        level = db.session.execute(text("SELECT @@transaction_isolation")).scalar()
    assert level.replace("-", " ").upper() == "READ COMMITTED", (
        f"connection รันอยู่ที่ {level!r} ซึ่งไม่ใช่ READ COMMITTED — "
        "backend.py ของยี่ห้อนี้ไม่ได้ถูกโหลด หรือ listener ไม่ทำงาน"
    )


# ------------------------------------- เพดานของการรอ (audit รอบ 11 · ADR 0067)


@pytest.mark.plugin_deps
@pytest.mark.parametrize("brand", ["mysql", "mariadb"])
def test_the_brand_declares_how_long_a_connection_may_wait(brand):
    """`read_timeout` ของ pymysql เป็น `None` = รอตลอดกาล — ฐานที่เงียบจึงค้างคำขอ

    ค่าพวกนี้อยู่ใน `backend.py` ของยี่ห้อ ไม่ใช่ที่ core (ADR 0026) เพราะมันเป็น
    ค่าของ *ทาง* ที่ข้อมูลวิ่งผ่าน · SQLite ไม่รู้จักด้วยซ้ำ

    import ในฟังก์ชันโดยตั้งใจ — โมดูลพวกนี้ผูก event listener ตอน import
    การ import ที่หัวไฟล์จะผูกให้ทุกเทสต์ในโปรเซสโดยไม่มีใครขอ
    """
    import importlib
    import types

    module = importlib.import_module(f"app.plugins.db.{brand}.backend")

    theirs: dict = {}
    module.bound_every_wait(types.SimpleNamespace(driver="pymysql"), None, [], theirs)
    for key in ("connect_timeout", "read_timeout", "write_timeout"):
        assert theirs.get(key), f"{brand}: ไม่ได้ประกาศ {key}"

    # **ต้องไม่แตะยี่ห้ออื่น** — listener ผูกกับคลาส Engine จึงโดนทุก engine ในโปรเซส
    others: dict = {}
    module.bound_every_wait(types.SimpleNamespace(driver="pysqlite"), None, [], others)
    assert others == {}, f"{brand}: ไปตั้งค่าให้ driver อื่นด้วย"

    # และค่าที่ผู้ deploy ระบุมาเองต้องชนะเสมอ
    chosen: dict = {"read_timeout": 5}
    module.bound_every_wait(types.SimpleNamespace(driver="pymysql"), None, [], chosen)
    assert chosen["read_timeout"] == 5, f"{brand}: เขียนทับค่าที่ผู้ deploy ตั้งมาเอง"
