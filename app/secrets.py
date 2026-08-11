"""ความลับมาจาก *แหล่ง* ที่ประกาศไว้ ไม่ใช่จาก environment อย่างเดียว (ADR 0030)

เลือก backend ด้วย scheme ของ `SECRETS_URL` แบบเดียวกับที่ `app/db_engine.py`
เลือกยี่ห้อฐานข้อมูล (ADR 0026) และ `app/cache.py` เลือก cache — หนึ่ง URL
หนึ่งตัวเลือก ไม่มี config ตัวที่สองให้ขัดกันเอง

**สัญญาของ backend** (`source.py` ในไดเรกทอรีของ plugin) มีสองตัวเท่านั้น:

* `connect(url)` → object อะไรก็ได้ที่ backend ใช้เอง (`None` ได้)
  **ยิงจริงตรงนี้เลยถ้าจำเป็น** เพราะแหล่งที่ถามไม่ได้ต้องทำให้แอปไม่ start
* `get(handle, name)` → ค่า หรือ `None` ถ้าไม่มีชื่อนั้น

**ไม่มี `list`, ไม่มี `set`, ไม่มี lease** โดยตั้งใจ (ADR 0030 ข้อ 3) —
ความสามารถที่ backend ตัวหนึ่งมีแต่ตัวอื่นไม่มี ห้ามโผล่ในสัญญา ไม่งั้นโค้ด
ที่เขียนบนสัญญานั้นจะย้ายกลับไม่ได้ ซึ่งเท่ากับยกเลิก exit path ที่ ROADMAP บังคับ

**สองสถานะที่ต้องแยกให้ขาด**:

* *ไม่มีชื่อนั้นในแหล่ง* → ตกกลับไป environment (ข้อ 4 — แหล่งความลับเองยังต้อง
  มี credential จากที่อื่น ไก่กับไข่ข้อนี้แก้ไม่ได้ แก้ได้แค่ทำให้เล็กที่สุด)
* *ถามแหล่งไม่ได้เลย* → **ไม่ start** (ข้อ 6) ไม่งั้นวันที่แหล่งล่ม ระบบจะรัน
  ต่อด้วยความลับชุดเก่าที่ค้างอยู่ใน env โดยไม่มีใครรู้

**ค่าที่ได้จากที่นี่ห้ามโผล่ใน log ไม่ว่ากรณีใด** — log ได้แค่ *ชื่อ* กับ
*แหล่งที่ตอบ*
"""

import os
from typing import Any

from flask import current_app, has_app_context

from app import plugins

SECRETS_TYPE = "secrets"
SOURCE_MODULE = "source"
DEFAULT_URL = "env://"

# คีย์ของ core ที่ถือความลับ — **ของ plugin ไม่อยู่ที่นี่** (ADR 0023)
# plugin ถามเองผ่าน `get()` ด้วยชื่อคีย์ของมัน core จึงไม่ต้องรู้จักชื่อพวกนั้น
CORE_SECRETS = ("SECRET_KEY", "AUDIT_HMAC_KEY", "DATABASE_URL", "CACHE_URL")
# ชื่อคีย์ใน config ที่ไม่ตรงกับชื่อ env (มีตัวเดียว)
CONFIG_ALIASES = {"DATABASE_URL": "SQLALCHEMY_DATABASE_URI"}

# **สถานะอยู่ที่ `app.extensions` ไม่ใช่ตัวแปรระดับโมดูล** (หลักเดียวกับ
# `app/cache.py`) — เทสต์สร้างแอปหลายตัวในโปรเซสเดียว ตัวแปรระดับโมดูลจะทำให้
# แหล่งความลับของเทสต์หนึ่งรั่วไปให้อีกเทสต์ แล้วผลจะขึ้นกับลำดับการรัน
EXTENSION_KEY = "todolist_secrets"


def scheme_of(url: str) -> str:
    return url.split("://", 1)[0].strip().lower()


def sources() -> dict[str, plugins.Plugin]:
    """map scheme → backend ที่รับ scheme นั้น (อ่านจากดิสก์ ไม่สนสวิตช์ปิด)

    ไม่สนสวิตช์ปิดด้วยเหตุผลเดียวกับชนิด `db`: ปิดแหล่งที่ใช้อยู่ไม่ได้
    (ADR 0026) — ระบบที่อ่านความลับไม่ได้ไม่ใช่ระบบที่ทำงานได้แบบจำกัด
    """
    found: dict[str, plugins.Plugin] = {}
    for plugin in plugins.plug_points_on_disk():
        if plugin.type != SECRETS_TYPE:
            continue
        for scheme in plugin.manifest.get("schemes", []):
            found[str(scheme)] = plugin
    return found


def init_secrets(app: Any) -> plugins.Plugin:
    """เลือกและเปิดแหล่งความลับ แล้วเขียนความลับของ core ทับค่าจาก environment

    **ต้องเรียกเป็นอย่างแรกใน `create_app` ก่อน `check_secret_key()`** ไม่งั้น
    แอปจะปฏิเสธที่จะ start เพราะ `SECRET_KEY` ที่ยังไม่ได้ถูกเติมจากแหล่ง
    """
    url = str(app.config.get("SECRETS_URL") or DEFAULT_URL)
    scheme = scheme_of(url)
    available = sources()
    if scheme not in available:
        # **ห้ามตกกลับ env เงียบ ๆ** — scheme ที่พิมพ์ผิดคือ config ที่ผิด
        # ไม่ใช่คำสั่งให้ใช้ค่าเริ่มต้น (หลักเดียวกับ ADR 0026)
        raise plugins.PluginError(
            f"ไม่มีแหล่งความลับที่รับ scheme {scheme!r} — มีให้เลือก: "
            f"{', '.join(sorted(available)) or '(ไม่มีเลย)'}"
        )
    plugin = available[scheme]
    module = plugins.load_module(plugin, SOURCE_MODULE)
    if module is None:
        raise plugins.PluginError(f"{plugin.key}: ไม่มี {SOURCE_MODULE}.py")
    # `connect()` ยิงจริงตรงนี้ถ้าจำเป็น — แหล่งที่ถามไม่ได้ต้องทำให้ไม่ start
    handle = module.connect(url)
    app.extensions[EXTENSION_KEY] = (plugin, handle)
    _apply_core_secrets(app, plugin, module, handle)
    # **ไม่ log ที่นี่** — ตัวนี้ถูกเรียกก่อน `init_logging()` เพราะ config ต้อง
    # มีค่าครบก่อน ถ้า log ตรงนี้จะได้บรรทัดที่ไม่ใช่ JSON ปนออกมาบรรทัดเดียว
    # (ADR 0011: log ของแอปเป็น JSON บรรทัดละ event) `create_app` เป็นคน log ให้
    # หลังตั้ง log เสร็จแล้ว
    return plugin


def active() -> plugins.Plugin | None:
    """แหล่งที่แอปนี้ใช้อยู่ — `None` นอก app context หรือยังไม่ได้ init"""
    if not has_app_context():
        return None
    entry = current_app.extensions.get(EXTENSION_KEY)
    return entry[0] if entry else None


def secrets_source(app: Any) -> str:
    """คีย์ของแหล่งที่แอปนี้ใช้ — สำหรับเอาไป log เท่านั้น"""
    entry = app.extensions.get(EXTENSION_KEY)
    return str(entry[0].key) if entry else "(ยังไม่ได้ตั้ง)"


def _lookup(module: Any, handle: Any, name: str, default: str = "") -> str:
    """ถามแหล่งก่อน แล้วค่อย environment — **ไม่พึ่ง app context**

    `init_secrets()` ทำงาน *ก่อน* จะมี context ให้ใช้ ตัวที่พึ่ง `current_app`
    จึงตกไปอ่าน environment เสมอตอนนั้น แล้วความลับของ core จะไม่เคยถูกเติม
    จากแหล่งเลย — บั๊กนี้เงียบสนิทเพราะระบบยังทำงานได้ด้วยค่าจาก env
    """
    value = module.get(handle, name)
    return str(value) if value is not None else os.environ.get(name, default)


def _apply_core_secrets(app: Any, plugin: plugins.Plugin, module: Any, handle: Any) -> None:
    if "env" in plugin.manifest.get("schemes", []):
        # แหล่งเริ่มต้นให้ผลเหมือน config ที่อ่าน environment มาแล้ว จึงไม่มี
        # อะไรต้องเขียนทับ — เส้นทางปกติของทุกคนจึงไม่ต้องเดินโค้ดข้างล่างเลย
        return
    for name in CORE_SECRETS:
        value = _lookup(module, handle, name)
        if not value:
            continue
        app.config[CONFIG_ALIASES.get(name, name)] = value
        # **`RATELIMIT_STORAGE_URI` ตามหลัง `CACHE_URL` (P5-07)** และความสัมพันธ์
        # นั้นถูกคำนวณไปแล้วตอนสร้างคลาส `Config` — ถ้าไม่ตามมาแก้ตรงนี้ด้วย
        # การย้าย `CACHE_URL` ไปไว้ในแหล่งความลับจะทำให้โควตา rate limit
        # เงียบ ๆ ย้อนกลับไปนับแยกต่อ process (ซึ่งคือหนี้ที่ P5-07 เพิ่งปิดไป)
        if name == "CACHE_URL" and not os.environ.get("RATELIMIT_STORAGE_URI"):
            app.config["RATELIMIT_STORAGE_URI"] = value


def get(name: str, default: str = "") -> str:
    """ค่าของความลับชื่อนั้น — แหล่งก่อน แล้วค่อย environment (ADR 0030 ข้อ 4)

    **ไม่ cache ผลไว้ที่นี่** เพราะ backend เป็นคนตัดสินเองว่าจะอ่านซ้ำหรือไม่
    (`env`/`file` ราคาถูกอยู่แล้ว ส่วนตัวที่ยิงข้ามเครือข่ายเก็บของมันเองตอน
    `connect()` — ดู ADR 0030 ข้อ 5: อ่านครั้งเดียวตอน start)

    นอก app context ตอบจาก environment ตรง ๆ — สคริปต์ที่รันนอกแอปจึงยังใช้ได้
    (หลักเดียวกับ `plugins.disabled_keys()`)
    """
    if has_app_context():
        entry = current_app.extensions.get(EXTENSION_KEY)
        if entry is not None:
            plugin, handle = entry
            module = plugins.load_module(plugin, SOURCE_MODULE)
            if module is not None:
                return _lookup(module, handle, name, default)
    return os.environ.get(name, default)
