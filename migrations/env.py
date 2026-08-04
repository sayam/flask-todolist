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
fileConfig(config.config_file_name)
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


def include_object(object_, name, type_, reflected, compare_to):  # noqa: ARG001
    """ตารางของ plugin ไม่อยู่ในสาย migration ของ core (Phase 4 — ADR 0023)

    ถ้าไม่กรองออก: วาง plugin ลงไปแล้ว `flask db migrate` ตัวถัดไปของ core จะมี
    `create_table` ของ plugin ติดไปด้วย และ **ถอน plugin แล้วตัวถัดไปจะ
    `drop_table` ทิ้งเงียบ ๆ** — วงจรชีวิตของตารางจะขึ้นกับว่าใครรัน migrate
    ตอนไหน ซึ่งไม่ใช่สิ่งที่ใครตั้งใจ

    วงจรชีวิตของตารางเหล่านี้เป็นของ plugin เอง (`flask plugin-install` /
    `plugin-uninstall`) core รู้แค่ว่า "ไม่ใช่ของฉัน"
    """
    from app import plugins

    return not (type_ == "table" and name in plugins.owned_tables())


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
    _adopt_legacy_version_table(connectable)

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
