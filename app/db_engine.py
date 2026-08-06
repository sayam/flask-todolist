"""เลือก backend ของฐานข้อมูลจาก `DATABASE_URL` แล้วโหลดค่าของยี่ห้อนั้น (ADR 0026)

core **ไม่รู้จักยี่ห้อไหนเป็นการเฉพาะ** — รู้แค่ว่า plugin ชนิด `db` ประกาศ
`schemes` ไว้ใน manifest ของตัวเอง และ scheme ของ URL เป็นตัวบอกว่าใช้ตัวไหน
เพิ่มยี่ห้อ = วางไดเรกทอรี ไม่ต้องแก้ไฟล์นี้

**scheme ที่ไม่ตรงกับ backend ตัวไหนเลย = แอปไม่ start** ห้ามตกกลับไป SQLite
เงียบ ๆ (ADR 0026 ข้อ 2) เพราะ prod ที่ตั้ง config ผิดจะเขียนลงไฟล์ SQLite เปล่า
แล้ว "ทำงานได้" จนถึงวันที่มีคนถามว่าข้อมูลหายไปไหน — ความเสียหายของการเดาให้
ในกรณีนี้มากกว่าความไม่สะดวกของการไม่ start อย่างเทียบกันไม่ได้

**ค่าเฉพาะยี่ห้ออยู่ใน `backend.py` ของ plugin นั้น ไม่ใช่ที่นี่** โมดูลนั้นถูก
import เพื่อ *ผลข้างเคียง* (ผูก event listener) เหมือนที่ไฟล์นี้เคยทำเองตอนที่ยัง
รองรับยี่ห้อเดียว — backend ที่ไม่ต้องตั้งอะไรก็ไม่ต้องมีไฟล์นั้น (ADR 0025:
"ไม่มีของชิ้นนี้" ต้องเป็นเส้นทางปกติ ไม่ใช่เส้นทางสำรองที่เขียนเพิ่ม)
"""

from types import ModuleType

from app import plugins

DB_TYPE = "db"
# ชื่อโมดูลที่ backend ใช้ตั้งค่าระดับ connection (ไม่มีก็ได้)
BACKEND_MODULE = "backend"


def _schemes_of(plugin: plugins.Plugin) -> list[str]:
    """scheme ที่ backend ตัวนี้ประกาศว่ารับได้"""
    declared = plugin.manifest.get("schemes", [])
    if not isinstance(declared, list):
        raise plugins.PluginError(f"{plugin.key}: `schemes` ต้องเป็น list")
    return [str(item) for item in declared]


def scheme_of(url: str) -> str:
    """ส่วนหน้า `://` ของ URL — `mysql+pymysql://user@host/db` → `mysql+pymysql`"""
    return url.split("://", 1)[0].strip().lower()


def backends() -> dict[str, plugins.Plugin]:
    """map scheme → backend ที่รับ scheme นั้น

    **อ่านจากดิสก์โดยไม่สนสวิตช์ปิด** เพราะคำถามว่า "ยี่ห้อนี้มีอยู่ไหม" ต้องได้
    คำตอบเดียวกันเสมอ ส่วน "ถูกปิดอยู่ไหม" เป็นคนละคำถามที่ `active()` ตอบ
    """
    found: dict[str, plugins.Plugin] = {}
    for plugin in plugins.installed_on_disk():
        if plugin.type != DB_TYPE:
            continue
        for scheme in _schemes_of(plugin):
            found[scheme] = plugin
    return found


def active(url: str) -> plugins.Plugin:
    """backend ที่ URL นี้ต้องใช้ — ไม่มีก็ raise พร้อมบอกว่ามีอะไรให้เลือก"""
    scheme = scheme_of(url)
    found = backends()
    chosen = found.get(scheme)
    if chosen is None:
        raise plugins.PluginError(
            f"DATABASE_URL ขึ้นต้นด้วย {scheme!r} แต่ไม่มี plugin ชนิด {DB_TYPE} ตัวไหนรับ scheme นี้ "
            f"(รับได้ตอนนี้: {', '.join(sorted(found)) or 'ไม่มีเลย'}) "
            "— วางไดเรกทอรีของยี่ห้อนั้นใน app/plugins/db/ หรือแก้ DATABASE_URL"
        )
    if plugins.is_disabled(chosen):
        raise plugins.PluginError(
            f"{chosen.key}: ปิดไม่ได้เพราะเป็น backend ที่ DATABASE_URL กำลังใช้อยู่ "
            "— เอาคีย์นี้ออกจาก DISABLED_PLUGINS (สวิตช์มีไว้ปิดของที่ถอดแล้วระบบยังเดินต่อได้)"
        )
    return chosen


def load(url: str) -> ModuleType | None:
    """โหลดค่าเฉพาะยี่ห้อของ backend ที่ใช้อยู่ — คืน None ถ้ามันไม่ต้องตั้งอะไร

    เรียกตอนสร้างแอป **ก่อนมี connection แรก** เพราะ listener ที่โมดูลนั้นผูกไว้
    ต้องอยู่ครบก่อน engine ตัวแรกถูกสร้าง ไม่งั้น connection ชุดแรกจะหลุดค่าที่
    ตั้งไว้ไปเงียบ ๆ (ของ SQLite คือ FK ไม่ถูกบังคับ — ข้อมูลเสียโดยไม่มี error)
    """
    return plugins.load_module(active(url), BACKEND_MODULE)
