"""ข้อเท็จจริงของระบบสำหรับหน้า admin — อ่านจาก runtime จริง ไม่เขียนมือ (เฟส 14)

สามก้อน: environment (interpreter/แพลตฟอร์ม/ฐานข้อมูล) · lifecycle (เวอร์ชัน
แอป · สถานะ migration · สถานะ plugin) · observability (histogram ของ process
ตัวเอง) — ทุกก้อนตรวจสิทธิ์ผู้ดูแลใน service ตามกติกา ADR 0022 และของที่
อ่านไม่ได้ต้องตอบว่า "อ่านไม่ได้" อย่างเปิดเผย ไม่ใช่เดาหรือเงียบ

หลักที่ต้องไม่ลืม (บทเรียนรอบตรวจเอกสาร): **เลขที่ไม่ได้อ่านจากของจริงคือเลข
ที่ผิดอยู่แล้ว** — ทุกค่าที่หน้าเหล่านี้แสดงจึงมาจาก runtime/ดิสก์ ณ ตอนเรียก
"""

from __future__ import annotations

import pathlib
import platform
import sys
from typing import Any

from sqlalchemy import text

from app import __version__, db
from app.metrics import EXTENSION_KEY
from app.services.roles import require_admin

MIGRATIONS_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "migrations"

#: ป้ายกำกับที่หน้า observability ต้องแสดงเสมอ — ADR 0031: ค่าที่นับเป็นของ
#: process เดียว และตัวเลขฝั่ง server ไม่ใช่ตัวตัดสิน DoD (ตัวตัดสินคือ k6)
PROCESS_LOCAL_CAVEAT = (
    "ตัวเลขนับเฉพาะ process นี้ process เดียว และไม่รวมเวลารอคิวก่อนถึงแอป — "
    "ใช้วินิจฉัยว่า endpoint ไหนช้า ไม่ใช่ตัดสินเป้าประสิทธิภาพ (ADR 0031)"
)


def environment(actor: Any) -> dict[str, str]:
    """interpreter · แพลตฟอร์ม · ยี่ห้อฐานข้อมูลที่ใช้อยู่จริง"""
    require_admin(actor)
    dialect = db.engine.dialect
    server = getattr(dialect, "server_version_info", None)
    return {
        "app_version": __version__,
        "python_version": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "database_dialect": dialect.name,
        "database_server": ".".join(str(part) for part in server) if server else "—",
    }


def _alembic_head() -> str | None:
    """revision ล่าสุดของสาย migration บนดิสก์ — อ่านไม่ได้ = None ไม่ใช่เดา"""
    try:
        from alembic.config import Config as AlembicConfig
        from alembic.script import ScriptDirectory

        config = AlembicConfig()
        config.set_main_option("script_location", str(MIGRATIONS_DIR))
        heads = ScriptDirectory.from_config(config).get_heads()
        return heads[0] if len(heads) == 1 else ",".join(sorted(heads))
    except Exception:  # noqa: BLE001 — สภาพ "อ่านไม่ได้" เป็นคำตอบที่ถูกต้องของหน้านี้
        return None


def _alembic_current() -> str | None:
    """revision ที่ฐานข้อมูลอยู่จริง — ตารางยังไม่มี (ยังไม่เคย upgrade) = None"""
    try:
        return db.session.execute(text("SELECT version_num FROM tdl_alembic_version")).scalar()
    except Exception:  # noqa: BLE001 — ฐานที่ยังไม่ migrate เป็นสถานะจริงที่ต้องรายงาน
        return None


def lifecycle(actor: Any) -> dict[str, Any]:
    """เวอร์ชันแอป · สถานะ migration (current เทียบ head) · สถานะ plugin ทุกตัว

    plugin ไล่จาก**ดิสก์** (รวมตัวที่ถูกสวิตช์ปิด) — เหตุผลเดียวกับ
    `flask plugin-list`: ผู้ดูแลต้องแยกออกว่า "ปิดไว้" กับ "ไดเรกทอรีหายไปแล้ว"
    """
    require_admin(actor)
    from app import plugins

    current = _alembic_current()
    head = _alembic_head()
    enabled_keys = {plugin.key for plugin in plugins.installed()}
    rows = [
        {
            "key": plugin.key,
            "migration": plugin.migration,
            "enabled": plugin.key in enabled_keys,
        }
        for plugin in plugins.installed_on_disk()
    ]
    return {
        "app_version": __version__,
        "migration_current": current,
        "migration_head": head,
        "migration_in_sync": current is not None and head is not None and current == head,
        "plugins": rows,
    }


def observability(actor: Any) -> dict[str, Any]:
    """สรุป histogram ของ process ตัวเอง — พร้อมป้ายกำกับข้อจำกัดเสมอ"""
    require_admin(actor)
    from flask import current_app

    histogram = current_app.extensions[EXTENSION_KEY]
    rows = [
        {
            "endpoint": endpoint,
            "method": method,
            "status": status,
            "count": total,
            "avg_ms": round(elapsed / total * 1000, 1) if total else 0.0,
        }
        for (endpoint, method, status), _counts, total, elapsed in sorted(histogram.snapshot())
    ]
    return {"caveat": PROCESS_LOCAL_CAVEAT, "rows": rows}
