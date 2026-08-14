"""ข้อเท็จจริงของระบบสำหรับหน้า admin — อ่านจาก runtime จริง ไม่เขียนมือ (เฟส 14)

สามก้อน: environment (interpreter/แพลตฟอร์ม/ฐานข้อมูล) · lifecycle (เวอร์ชัน
แอป · สถานะ migration · สถานะ plugin) · observability (histogram ของ process
ตัวเอง) — ทุกก้อนตรวจสิทธิ์ผู้ดูแลใน service ตามกติกา ADR 0022 และของที่
อ่านไม่ได้ต้องตอบว่า "อ่านไม่ได้" อย่างเปิดเผย ไม่ใช่เดาหรือเงียบ

หลักที่ต้องไม่ลืม (บทเรียนรอบตรวจเอกสาร): **เลขที่ไม่ได้อ่านจากของจริงคือเลข
ที่ผิดอยู่แล้ว** — ทุกค่าที่หน้าเหล่านี้แสดงจึงมาจาก runtime/ดิสก์ ณ ตอนเรียก
"""

from __future__ import annotations

import datetime
import json
import pathlib
import platform
import sys
from importlib import metadata
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


# ---------------------------------------------------------------- active SBOM

LOCKFILE = MIGRATIONS_DIR.parent / "Pipfile.lock"
EOL_TABLE = MIGRATIONS_DIR.parent / "docs" / "eol-pinned.json"


def _normalized(name: str) -> str:
    """ชื่อ package แบบ canonical ของ pip — เทียบข้ามแหล่งได้"""
    return name.lower().replace("_", "-")


def _declared_packages() -> dict[str, dict[str, str]] | None:
    """package ที่ lock ประกาศ ต่อชื่อ: {version, category} — ไม่มี lock = None

    category คือคำตอบของ "ของใคร": `default`/`deploy` = core ·
    `plugin-<ชนิด>-<ไอดี>` = supply chain ของ plugin ตัวนั้น (ADR 0025)
    """
    if not LOCKFILE.is_file():
        return None
    lock = json.loads(LOCKFILE.read_text(encoding="utf-8"))
    declared: dict[str, dict[str, str]] = {}
    for section, packages in lock.items():
        if section.startswith("_"):
            continue
        for name, spec in packages.items():
            version = (spec.get("version") or "").lstrip("=")
            declared[_normalized(name)] = {"version": version, "category": section}
    return declared


def _python_eol() -> dict[str, Any] | None:
    """สถานะ EOL ของ python cycle ที่กำลังรัน จากตารางที่ตรึงไว้ — อ่านไม่ได้ = None"""
    try:
        data = json.loads(EOL_TABLE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    running = f"{sys.version_info.major}.{sys.version_info.minor}"
    for row in data.get("python", []):
        if row.get("cycle") == running:
            eol = datetime.date.fromisoformat(row["eol"])
            return {
                "cycle": running,
                "eol": row["eol"],
                "days_left": (eol - datetime.date.today()).days,
                "fetched_on": data.get("_fetched_on", "—"),
            }
    return None


def sbom(actor: Any) -> dict[str, Any]:
    """SBOM ฉบับ runtime: ของที่ติดตั้ง*จริง*เทียบกับที่ lock ประกาศ + เจ้าของต่อ package

    ความต่างจาก SBOM ในเอกสาร (job `sbom` ของ CI): อันนั้นคือ*คำประกาศ* —
    อันนี้คือ*ความจริงของ process นี้* สองอย่างต่างกันได้ และความต่างนั่นแหละ
    คือสิ่งที่หน้านี้มีไว้จับ (drift = มีของที่ไม่ได้ประกาศ หรือรุ่นไม่ตรง)
    """
    require_admin(actor)
    installed = {
        _normalized(dist.metadata["Name"]): dist.version
        for dist in metadata.distributions()
        if dist.metadata["Name"]
    }
    declared = _declared_packages()

    rows = []
    for name, version in sorted(installed.items()):
        spec = declared.get(name) if declared else None
        if spec is None:
            status = "unlisted" if declared is not None else "unknown"
            category = "—"
            declared_version = "—"
        else:
            declared_version = spec["version"]
            category = spec["category"]
            status = "match" if spec["version"] == version else "drift"
        rows.append(
            {
                "name": name,
                "installed": version,
                "declared": declared_version,
                "category": category,
                "status": status,
            }
        )
    missing = sorted(set(declared) - set(installed)) if declared is not None else []
    return {
        "lockfile_readable": declared is not None,
        "rows": rows,
        "missing": missing,
        "drift_count": sum(1 for row in rows if row["status"] == "drift"),
        "unlisted_count": sum(1 for row in rows if row["status"] == "unlisted"),
        "python_eol": _python_eol(),
    }
