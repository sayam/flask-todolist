"""cache เป็น *optimization* ห้ามเป็น *correctness* (Phase 5 · ROADMAP ข้อ 4.3)

**กติกาข้อเดียวที่สำคัญที่สุดของไฟล์นี้**: ถอด cache ออกแล้วระบบต้องยังให้คำตอบ
เดิมทุกอย่าง แค่ช้าลง — ค่าเริ่มต้นจึงเป็น **no-op จริง ๆ** ไม่ใช่ dict ใน process

ทำไมไม่ใช้ dict ต่อ process เป็นค่าเริ่มต้น: แอปนี้ตั้งใจจะรันหลาย worker
(Phase 5 ข้อ ≥2 replica) cache ที่ไม่แชร์กันจะทำให้คำขอสองอันที่เหมือนกันได้
คำตอบต่างกันตาม worker ที่รับ ซึ่งอ่านจากภายนอกแยกไม่ออกจากบั๊ก — **cache ที่
ผิดเงียบ ๆ แย่กว่าไม่มี cache** ส่วนที่ต้องการความเร็วจริงให้ตั้ง backend ที่แชร์ได้

backend จริงเป็น plugin ชนิด `cache` เลือกด้วย scheme ของ `CACHE_URL` แบบเดียวกับ
ที่ `app/db_engine.py` เลือกยี่ห้อฐานข้อมูล (ADR 0026) — driver อยู่ใน category
ของ plugin นั้น คนที่ไม่ใช้ redis จึงไม่ต้องติดตั้งและไม่ต้องเฝ้า CVE ของมัน

**สัญญาของ backend** (`cache.py` ในไดเรกทอรีของ plugin):

* `connect(url)` → คืน object อะไรก็ได้ที่ backend ใช้เอง (None ได้)
* `get(handle, key)` → ค่าที่เก็บไว้ หรือ None
* `set(handle, key, value, ttl)` → เก็บ (วินาที, None = ไม่หมดอายุ)
* `invalidate(handle, key)` → ลบทิ้ง

**host เป็นคนตรวจสัญญา ไม่ใช่ registry** (ADR 0025) — ตรวจตอน start ไม่ใช่ตอนใช้
"""

from types import ModuleType
from typing import Any

from flask import current_app

from app import plugins

CACHE_TYPE = "cache"
BACKEND_MODULE = "cache"
# ฟังก์ชันที่ backend ต้องมีครบ — ขาดตัวไหนคือแพ็กมาไม่ครบ ต้องดังตั้งแต่ start
CACHE_CONTRACT = ("connect", "get", "set", "invalidate")


def _schemes_of(plugin: plugins.Plugin) -> list[str]:
    declared = plugin.manifest.get("schemes", [])
    if not isinstance(declared, list):
        raise plugins.PluginError(f"{plugin.key}: `schemes` ต้องเป็น list")
    return [str(item) for item in declared]


def scheme_of(url: str) -> str:
    """ส่วนหน้า `://` ของ URL — `redis://host:6379/0` → `redis`"""
    return url.split("://", 1)[0].strip().lower()


def backends() -> dict[str, plugins.Plugin]:
    """map scheme → backend ที่รับ scheme นั้น (อ่านจากดิสก์ ไม่สนสวิตช์ปิด)"""
    found: dict[str, plugins.Plugin] = {}
    for plugin in plugins.installed_on_disk():
        if plugin.type != CACHE_TYPE:
            continue
        for scheme in _schemes_of(plugin):
            found[scheme] = plugin
    return found


def active(url: str) -> plugins.Plugin:
    """backend ที่ URL นี้ต้องใช้ — ไม่มีก็ raise พร้อมบอกว่ามีอะไรให้เลือก

    **ไม่ตกกลับไป no-op เงียบ ๆ** ด้วยเหตุผลเดียวกับ `db_engine.active()`:
    คนที่ตั้ง `CACHE_URL` ผิดตั้งใจจะได้ cache ที่แชร์กัน การเงียบแล้วให้ no-op
    แปลว่าเขาจะคิดว่ามี cache อยู่ทั้งที่ไม่มี แล้วไปหาสาเหตุที่ประสิทธิภาพผิดคาด
    ในที่ที่ไม่มีอะไรผิด
    """
    scheme = scheme_of(url)
    found = backends()
    chosen = found.get(scheme)
    if chosen is None:
        raise plugins.PluginError(
            f"CACHE_URL ขึ้นต้นด้วย {scheme!r} แต่ไม่มี plugin ชนิด {CACHE_TYPE} ตัวไหนรับ scheme นี้ "
            f"(รับได้ตอนนี้: {', '.join(sorted(found)) or 'ไม่มีเลย'})"
        )
    if plugins.is_disabled(chosen):
        raise plugins.PluginError(
            f"{chosen.key}: ปิดไม่ได้เพราะเป็น cache backend ที่ CACHE_URL กำลังใช้อยู่ "
            "— ชี้ CACHE_URL ไปที่ `memory://` ก่อนถ้าอยากปิดตัวนี้"
        )
    return chosen


def module_of(plugin: plugins.Plugin) -> ModuleType:
    """โค้ดของ backend — ต้องมีและต้องทำสัญญาครบ (ตรวจตอน start)"""
    module = plugins.load_module(plugin, BACKEND_MODULE)
    if module is None:
        raise plugins.PluginError(f"{plugin.key}: ไม่มี {BACKEND_MODULE}.py")
    missing = [name for name in CACHE_CONTRACT if not callable(getattr(module, name, None))]
    if missing:
        raise plugins.PluginError(
            f"{plugin.key}: {BACKEND_MODULE}.py ต้องมีฟังก์ชัน {', '.join(missing)}"
        )
    return module


class Cache:
    """ตัวที่โค้ดของแอปเรียกใช้ — ผูกกับ backend ตัวเดียวตลอดอายุแอป"""

    def __init__(self, url: str) -> None:
        self.url = url
        self.plugin = active(url)
        self._module = module_of(self.plugin)
        self._handle = self._module.connect(url)

    @property
    def is_shared(self) -> bool:
        """แชร์ข้ามโปรเซสได้ไหม — `False` แปลว่าไม่มี cache จริง (no-op)

        ตัวที่ต้องการ storage ที่แชร์ได้จริง (rate limiter — P5-07) ถามข้อนี้ก่อน
        แทนที่จะเดาจากชื่อ backend
        """
        return bool(self.plugin.manifest.get("shared", False))

    def get(self, key: str) -> Any:
        return self._module.get(self._handle, key)

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        self._module.set(self._handle, key, value, ttl)

    def invalidate(self, key: str) -> None:
        self._module.invalidate(self._handle, key)


def is_shared_uri(url: str) -> bool | None:
    """URL นี้เก็บของไว้ที่ที่โปรเซสอื่นเห็นด้วยไหม — **`None` = ไม่รู้จัก**

    แยกสามสถานะโดยตั้งใจ ไม่ยุบ `None` เข้ากับ `False`: `limits` (ตัวที่อยู่ใต้
    Flask-Limiter) รองรับ store หลายตัวที่เราไม่มี cache plugin ให้ เช่น
    `memcached://` หรือ `mongodb://` — พวกนั้นแชร์ได้จริงแต่เราตอบแทนไม่ได้
    การเดาว่า "ไม่แชร์" จะกลายเป็นคำเตือนที่ผิด แล้วคำเตือนที่ผิดคือคำเตือนที่
    คนเลิกอ่าน ซึ่งแพงกว่าการไม่เตือน
    """
    backend = backends().get(scheme_of(url))
    if backend is None:
        return None
    return bool(backend.manifest.get("shared", False))


def warn_if_counters_are_not_shared(app: Any) -> None:
    """เตือนตอน start ถ้าโควตา rate limit จะถูกนับแยกต่อ process

    **นี่คือส่วนที่ปิดหนี้จริง ๆ ของ P5-07** — การชี้ค่าเริ่มต้นไปที่ `CACHE_URL`
    แก้ให้คนที่ตั้ง cache ไว้แล้ว แต่คนที่ยังไม่ได้ตั้งอะไรเลยยังอยู่ในสภาพเดิม
    ต่างกันตรงที่ตอนนี้ระบบ *พูดออกมา* แทนที่จะให้เป็นความรู้ในหัวคนตั้ง config

    ไม่ refuse to start เพราะ `memory://` ถูกต้องสมบูรณ์สำหรับ dev และ single
    worker ซึ่งเป็นวิธีรันที่พบบ่อยที่สุด — สิ่งที่ผิดคือการ *ไม่รู้* ว่าตัวเอง
    อยู่สภาพไหน ไม่ใช่การอยู่ในสภาพนั้น
    """
    uri = app.config["RATELIMIT_STORAGE_URI"]
    if is_shared_uri(uri) is False:
        app.logger.warning(
            "rate limit ถูกนับแยกต่อ process เพราะ RATELIMIT_STORAGE_URI = %r "
            "— รันหลาย worker เมื่อไหร่ เพดานจริงจะเป็น N เท่าของที่ตั้งไว้ "
            "(ตั้ง CACHE_URL ไปที่ store ที่แชร์ได้ แล้วตัวนี้จะตามไปเอง)",
            uri,
        )


def current() -> Cache:
    """cache ของแอปที่กำลังทำงานอยู่ — สร้างครั้งเดียวตอน `init_cache()`"""
    cache: Cache = current_app.extensions["todolist_cache"]
    return cache


def init_cache(app: Any) -> Cache:
    """ผูก cache เข้ากับแอป — เรียกตอน `create_app` ให้พังตั้งแต่ start ถ้า config ผิด"""
    cache = Cache(app.config["CACHE_URL"])
    app.extensions["todolist_cache"] = cache
    return cache
