import logging
from logging.config import fileConfig

from alembic import context
from flask import current_app
from sqlalchemy import text as sa_text

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
#
# **`disable_existing_loggers=False` สำคัญ** — ค่าเริ่มต้นของ `fileConfig` คือ True
# ซึ่งไปตั้ง `disabled = True` ให้ทุก logger ที่มีอยู่แล้วและไม่ได้ถูกระบุใน
# alembic.ini รวมถึง logger ของแอปเอง ผลคือ log ของแอป**เงียบสนิทตลอดทั้ง process
# ที่รัน migration** โดยไม่มีอะไรฟ้อง (เจอตอน Phase 4.5: เทสต์ที่ยืนยันว่าแอป
# เขียน log เตือนเรื่องสวิตช์ปิด plugin กลายเป็นแดงเฉพาะตอนรันทั้งชุด เพราะ
# tests/test_migrations.py รันก่อนตามลำดับตัวอักษร)
fileConfig(config.config_file_name, disable_existing_loggers=False)
logger = logging.getLogger("alembic.env")

# ตารางของ alembic เองก็ต้องมี prefix เหมือนตารางอื่น ไม่งั้น `alembic_version`
# ลอยอยู่กลางฐานข้อมูลที่อาจมีแอปอื่นใช้ร่วม (ดู docs/STANDARDS.md ข้อ 1.1)
VERSION_TABLE = "tdl_alembic_version"


def get_engine():
    try:
        # this works with Flask-SQLAlchemy<3 and Alchemical
        return current_app.extensions["migrate"].db.get_engine()
    except (TypeError, AttributeError):
        # this works with Flask-SQLAlchemy>=3
        return current_app.extensions["migrate"].db.engine


def get_engine_url():
    try:
        return get_engine().url.render_as_string(hide_password=False).replace("%", "%%")
    except AttributeError:
        return str(get_engine().url).replace("%", "%%")


# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
config.set_main_option("sqlalchemy.url", get_engine_url())
target_db = current_app.extensions["migrate"].db

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_metadata():
    if hasattr(target_db, "metadatas"):
        return target_db.metadatas[None]
    return target_db.metadata


def include_object(object_, name, type_, reflected, compare_to):  # noqa: ARG001 - documented suppression
    """ตารางของ plugin ไม่อยู่ในสาย migration ของ core (Phase 4 — ADR 0023)

    ถ้าไม่กรองออก: วาง plugin ลงไปแล้ว `flask db migrate` ตัวถัดไปของ core จะมี
    `create_table` ของ plugin ติดไปด้วย และ **ถอน plugin แล้วตัวถัดไปจะ
    `drop_table` ทิ้งเงียบ ๆ** — วงจรชีวิตของตารางจะขึ้นกับว่าใครรัน migrate
    ตอนไหน ซึ่งไม่ใช่สิ่งที่ใครตั้งใจ

    วงจรชีวิตของตารางเหล่านี้เป็นของ plugin เอง (`flask plugin-install` /
    `plugin-uninstall`) core รู้แค่ว่า "ไม่ใช่ของฉัน"
    """
    from app import plugins

    owned = plugins.owned_tables()
    if type_ == "table":
        return name not in owned
    # index/column/constraint บอกชื่อของตัวเอง ไม่ใช่ชื่อตาราง — ต้องถามผ่าน
    # `.table` ไม่งั้น index ของ plugin จะหลุดเข้า migration ของ core
    # (เจอตอน Phase 4: ตารางถูกกรองแล้วแต่ `ix_..._user_id` ยังโผล่)
    table = getattr(object_, "table", None)
    return getattr(table, "name", None) not in owned


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=get_metadata(),
        literal_binds=True,
        version_table=VERSION_TABLE,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def _adopt_legacy_version_table(engine):
    """เปลี่ยนชื่อ `alembic_version` เดิมเป็น `tdl_alembic_version` ถ้ายังไม่ได้เปลี่ยน

    ต้องทำ **ก่อน** `context.configure()` เพราะ alembic อ่านเวอร์ชันปัจจุบัน
    จากตารางชื่อใหม่ ถ้าไม่เจอมันจะสรุปว่าฐานข้อมูลยังว่าง แล้วไล่รัน migration
    ตั้งแต่ตัวแรก — ซึ่งจะพังทันทีเพราะตารางมีอยู่แล้ว

    **ต้องใช้ connection ของตัวเองที่ commit แล้วปิดให้เรียบร้อยก่อน** ห้ามใช้
    connection ตัวเดียวกับที่ส่งให้ `context.configure()` — การแตะ connection นั้น
    ก่อน configure จะเปิด transaction ค้างไว้ ทำให้ migration ทั้งชุดถูก rollback
    ตอนปิด connection โดย **ไม่มี error และ exit code ยังเป็น 0**
    (เจอมาแล้วตอน Phase 2: log ขึ้น "Running upgrade" ครบทุกตัวแต่ฐานข้อมูลไม่เปลี่ยน)

    เป็นงานครั้งเดียว: พอเปลี่ยนชื่อแล้วรอบถัดไปจะไม่เข้าเงื่อนไขอีก
    ฐานข้อมูลที่สร้างใหม่ก็ไม่เข้า เพราะไม่มีตารางชื่อเก่าตั้งแต่แรก
    """
    from sqlalchemy import inspect

    # begin() commit ให้เองตอนออกจาก block และปิด connection ทันที
    with engine.begin() as connection:
        names = set(inspect(connection).get_table_names())
        if "alembic_version" in names and VERSION_TABLE not in names:
            logger.info("renaming alembic_version -> %s", VERSION_TABLE)
            connection.execute(sa_text(f"ALTER TABLE alembic_version RENAME TO {VERSION_TABLE}"))


# สายเดิม 13 ตัวของ Phase 1–4 ที่ถูกยุบเป็น baseline ตัวเดียวใน Phase 5
# **ตัวสุดท้ายเท่านั้นที่รับช่วงได้** — ดู `_adopt_squashed_history()`
SQUASHED_HEAD = "401e0ce7011f"
BASELINE = "5ffefa218ed7"
SQUASHED_HISTORY = {
    "c98b7f2ca563", "cb0dcf2ef467", "89cd0c572bf9", "8caa5996801f", "81b7c3f4e01f",
    "18dccb13a980", "296ab616c11b", "7de41b01a108", "a1f0c2d47b93", "b7e3d91c5a2f",
    "c4d8e05a91f7", "c7f1db5e54e4", SQUASHED_HEAD,
}


def _adopt_squashed_history(engine):
    """ฐานข้อมูลที่อยู่ปลายสายเดิม ให้ถือว่าอยู่ที่ baseline แทน

    สายเดิมถูกยุบเป็น migration ตัวเดียว (`5ffefa218ed7`) ไฟล์ของมันจึงไม่มีอยู่
    แล้ว ถ้าไม่ทำอะไร alembic จะหาเวอร์ชันที่ฐานข้อมูลอ้างไม่เจอแล้วหยุดด้วย
    "Can't locate revision" ซึ่งเป็นข้อความที่ไม่ได้บอกว่าต้องทำอะไรต่อ

    ทำให้อัตโนมัติแทนที่จะสั่งให้คนไปพิมพ์ `flask db stamp` เอง — หลักเดียวกับ
    `_adopt_legacy_version_table()` ข้างบน: ขั้นตอนที่ต้องทำด้วยมือคือขั้นตอนที่
    วันหนึ่งจะมีคนข้าม แล้วไปเจอ error ตอนตีสามโดยไม่มีบริบทอะไรเลย

    **รับช่วงเฉพาะฐานที่อยู่ที่ปลายสายเดิมเท่านั้น** ฐานที่ค้างอยู่กลางสาย
    (เช่นเพิ่ง upgrade ไปได้ครึ่งทางแล้วหยุด) ต้องไม่ถูกดันไป baseline เพราะ
    ตารางของมันยังไม่ครบ — การ stamp ให้จะกลายเป็นการโกหกว่า schema พร้อมแล้ว
    แล้วแอปจะพังตอน query ด้วย "no such column" ซึ่งไล่กลับมาหาต้นเหตุยากมาก
    กรณีนั้นให้หยุดพร้อมบอกว่าต้อง upgrade ด้วยโค้ดเวอร์ชันก่อนหน้าให้จบก่อน
    """
    from sqlalchemy import inspect

    with engine.begin() as connection:
        if VERSION_TABLE not in set(inspect(connection).get_table_names()):
            return  # ฐานใหม่เอี่ยม ไม่มีอะไรให้รับช่วง
        rows = connection.execute(sa_text(f"SELECT version_num FROM {VERSION_TABLE}")).fetchall()
        current = {row[0] for row in rows}
        if not current & SQUASHED_HISTORY:
            return  # อยู่ที่ baseline หรือใหม่กว่าอยู่แล้ว

        if current != {SQUASHED_HEAD}:
            raise RuntimeError(
                f"ฐานข้อมูลนี้อยู่ที่ {', '.join(sorted(current))} ซึ่งเป็นเวอร์ชันกลางสายเดิม "
                f"ที่ถูกยุบไปแล้ว — ให้ upgrade ด้วยโค้ดเวอร์ชันก่อน Phase 5 จนถึง "
                f"{SQUASHED_HEAD} ก่อน แล้วค่อยกลับมารันตัวนี้"
            )
        logger.info("adopting squashed history: %s -> %s", SQUASHED_HEAD, BASELINE)
        connection.execute(
            sa_text(f"UPDATE {VERSION_TABLE} SET version_num = :new WHERE version_num = :old"),
            {"new": BASELINE, "old": SQUASHED_HEAD},
        )


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    # this callback is used to prevent an auto-migration from being generated
    # when there are no changes to the schema
    # reference: http://alembic.zzzcomputing.com/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, "autogenerate", False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info("No changes in schema detected.")

    conf_args = current_app.extensions["migrate"].configure_args
    if conf_args.get("process_revision_directives") is None:
        conf_args["process_revision_directives"] = process_revision_directives
    conf_args.setdefault("include_object", include_object)

    connectable = get_engine()
    # ลำดับสำคัญ: เปลี่ยนชื่อตารางก่อน แล้วค่อยอ่าน/แก้ค่าข้างในตารางนั้น
    _adopt_legacy_version_table(connectable)
    _adopt_squashed_history(connectable)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            version_table=VERSION_TABLE,
            **conf_args,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
