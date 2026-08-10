"""ระบบ plugin — core ไม่รู้จัก plugin ตัวไหนเป็นการเฉพาะ

**สัญญาของสถาปัตยกรรมนี้**

* core รู้แค่ *วิธีค้นหา* plugin ไม่ได้ hardcode ชื่อ plugin ไว้ที่ไหนเลย
* plugin หนึ่งตัว = หนึ่งไดเรกทอรีใต้ `app/plugins/<ชนิด>/<ไอดี>/`
  ชื่อไดเรกทอรีคือไอดีของ plugin
* เพิ่ม plugin = วางไดเรกทอรีลงไป **ไม่ต้องแก้โค้ด core แม้แต่บรรทัดเดียว**
* ลบ plugin = ลบไดเรกทอรีทิ้ง ระบบต้องยังทำงานได้ ผู้ใช้ที่เลือก plugin นั้นไว้
  จะตกกลับไปใช้ตัว core อัตโนมัติ
* plugin ที่ต้องเก็บข้อมูลเพิ่ม **ดูแล table ของตัวเอง** ห้ามแก้ table ของ core
  (กลไกอยู่ในไฟล์นี้ — ดูหัวข้อ "plugin ที่มีข้อมูลของตัวเอง" ข้างล่าง และ ADR 0023)

## plugin ที่มีข้อมูลของตัวเอง (Phase 4)

plugin ที่ต้องเก็บข้อมูลวาง `models.py` ไว้ในไดเรกทอรีของตัวเอง ประกาศ model
ตามปกติ โดย **ชื่อตารางต้องขึ้นต้นด้วย `tdl_<ชนิด>_<ไอดี>_`** (บังคับตอนโหลด
ไม่ใช่แค่ธรรมเนียม) core รู้ว่าตารางไหนเป็นของ plugin ตัวไหนด้วยการดูว่ามีตาราง
อะไรโผล่เข้า metadata ระหว่าง import ไฟล์นั้น — ไม่ต้องประกาศซ้ำใน manifest
ให้มีโอกาสไม่ตรงกัน

ตารางของ plugin **ไม่อยู่ในสาย migration ของ core** โดยตั้งใจ: `flask db migrate`
ของ core จะมองไม่เห็นมันเลย (env.py กรองออกด้วย `owned_tables()`) ไม่งั้นการ
วาง plugin ลงไปจะทำให้ migration ตัวถัดไปของ core มีตารางของ plugin ติดไปด้วย
และการถอด plugin จะทำให้ migration ตัวถัดไป **drop ตารางนั้นทิ้งเงียบ ๆ**

วงจรชีวิตจึงเป็นของ plugin เอง: `flask plugin-install` สร้างตาราง
`flask plugin-uninstall` ลบทิ้ง — ถอนแล้วข้อมูลของ plugin หายไปด้วยจริง ๆ
ส่วน core ไม่รู้จักแม้แต่ชื่อตาราง

ตอนนี้รองรับสองชนิดคือ `themes` (ไม่มีข้อมูลของตัวเอง) กับ `auth`
แต่ตัว registry ออกแบบให้เพิ่มชนิดอื่นได้โดยไม่ต้องรื้อ
"""

import importlib.metadata
import importlib.util
import json
import logging
import pathlib
import re
import sys
from types import ModuleType
from typing import Any

from flask import current_app, has_app_context

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent
MANIFEST_NAME = "plugin.json"

THEME_TYPE = "themes"

# ไอดีของ plugin ที่ core ต้องมีเสมอ ใช้เป็นตัวสำรองเวลา plugin อื่นหายไป
# ตัวนี้ลบไม่ได้ — ถ้าหายแอปจะไม่ start (ดู load_all)
CORE_THEME = "system"


class PluginError(RuntimeError):
    """manifest เสียหรือโครงสร้าง plugin ไม่ถูกต้อง"""


AUTH_TYPE = "auth"

# backend ของฐานข้อมูล — **เป็นเจ้าของ *ทาง* ที่ข้อมูลวิ่งผ่าน ไม่ใช่เจ้าของ *ข้อมูล***
# จึงห้ามมีตารางของตัวเอง (ADR 0026 ข้อ 3) ต่างจากชนิดอื่นตรงที่ต้องมีตัวที่ active
# หนึ่งตัวเสมอ และการสลับตัวคือการย้ายข้อมูล ไม่ใช่การ plug
DB_TYPE = "db"

# ชื่อโมดูลที่ plugin ใช้ประกาศ model ของตัวเอง (ไม่มีก็ได้ = ไม่มีข้อมูลของตัวเอง)
MODELS_MODULE = "models"
# โมดูลที่ plugin ชนิด auth ต้องมี ถ้าประกาศตัวเองเป็นปัจจัยที่สอง
FACTOR_MODULE = "factor"
# ไดเรกทอรีที่ plugin วางส่วนเสริมของตัวเอง และชื่อโมดูลที่ส่วนเสริมต้องมี (ADR 0025)
ENHANCEMENTS_DIR = "enhancements"
PROVIDE_MODULE = "provide"
# ฟังก์ชันที่ปัจจัยที่สองต้องมีครบ — core เรียกแค่สองตัวนี้ ไม่รู้อะไรมากกว่านี้
SECOND_FACTOR_CONTRACT = ("is_enrolled", "verify")


class Plugin:
    """ข้อมูลของ plugin หนึ่งตัวที่อ่านมาจาก manifest"""

    def __init__(
        self,
        plugin_type: str,
        plugin_id: str,
        directory: pathlib.Path,
        manifest: dict[str, Any],
        host: "Plugin | None" = None,
    ) -> None:
        self.type = plugin_type
        self.id = plugin_id
        self.directory = directory
        self.manifest = manifest
        # ส่วนเสริมรู้จัก plugin ที่มันเสียบอยู่ ส่วน plugin ระดับบนสุดมี host เป็น None
        self.host = host

    @property
    def name(self) -> str:
        """ชื่อที่เอาไปแสดง — ไม่ผ่าน gettext เพราะเป็นข้อมูลของ plugin
        ไม่ใช่ข้อความของ core (plugin จะแปลเองต้องมี lang pack ของตัวเอง)"""
        return str(self.manifest.get("name", self.id))

    @property
    def version(self) -> str:
        return str(self.manifest.get("version", "0"))

    @property
    def is_core(self) -> bool:
        """plugin ที่มากับระบบ ลบไม่ได้"""
        return bool(self.manifest.get("core", False))

    @property
    def stylesheet(self) -> str | None:
        value = self.manifest.get("stylesheet")
        return str(value) if value is not None else None

    @property
    def key(self) -> str:
        """ชื่อเต็มที่ใช้อ้างถึงจุด plug นี้ — `auth/totp` หรือ `auth/totp#qr-segno`"""
        if self.host is not None:
            return f"{self.host.key}#{self.id}"
        return f"{self.type}/{self.id}"

    @property
    def provides(self) -> str | None:
        """ชื่อความสามารถที่ส่วนเสริมตัวนี้ให้ — host ขอด้วยชื่อนี้ ไม่ได้ขอด้วยไอดี"""
        value = self.manifest.get("provides")
        return str(value) if value is not None else None

    @property
    def table_prefix(self) -> str:
        """ตารางของ plugin ตัวนี้ต้องขึ้นต้นด้วยอะไร (docs/STANDARDS.md ข้อ 1.1)"""
        return f"tdl_{self.type}_{self.id}_"

    def file(self, filename: str) -> pathlib.Path:
        """path ของไฟล์ใน plugin — กันไม่ให้หลุดออกนอกไดเรกทอรีตัวเอง"""
        target = (self.directory / filename).resolve()
        if not target.is_relative_to(self.directory):
            raise PluginError(f"{self.id}: ไฟล์อยู่นอกไดเรกทอรีของ plugin")
        return target

    def __repr__(self) -> str:
        return f"<Plugin {self.type}/{self.id} v{self.version}>"


def _read_manifest(directory: pathlib.Path) -> dict[str, Any] | None:
    path = directory / MANIFEST_NAME
    try:
        manifest = json.loads(path.read_text())
    except FileNotFoundError:
        return None  # ไม่ใช่ไดเรกทอรีของ plugin ข้ามไป
    except json.JSONDecodeError as exc:
        raise PluginError(f"{directory.name}: {MANIFEST_NAME} อ่านไม่ได้ — {exc}") from exc
    if not isinstance(manifest, dict):
        raise PluginError(f"{directory.name}: {MANIFEST_NAME} ต้องเป็น object")
    return manifest


# ---------------------------------------------------------------- สวิตช์ปิด (ADR 0025)


def disabled_keys() -> frozenset[str]:
    """คีย์ของจุด plug ที่ config สั่งปิดไว้ (`DISABLED_PLUGINS`)

    นอก app context ถือว่าไม่มีอะไรถูกปิด — สคริปต์ที่รันนอกแอปจึงเห็นของครบ
    """
    if not has_app_context():
        return frozenset()
    keys: frozenset[str] = current_app.config.get("DISABLED_PLUGINS", frozenset())
    return keys


def is_disabled(plugin: Plugin) -> bool:
    """จุด plug นี้ถูกสวิตช์ปิดอยู่ไหม (ปิด host = ปิดทุกอย่างที่เสียบอยู่ข้างใน)

    **ปิดแล้วต้องเหมือนไม่เคยวางไดเรกทอรีลงไป** ไม่ใช่เส้นทางสำรองที่เขียนเพิ่ม
    เพราะเส้นทาง "ไม่มีของชิ้นนี้" ถูกทดสอบไว้แล้วทั้งชุด ส่วนเส้นทาง "มีแต่ปิดอยู่"
    จะเป็นสถานะใหม่ที่ไม่มีใครเคยเดินผ่าน
    """
    keys = disabled_keys()
    if plugin.key in keys:
        return True
    return plugin.host is not None and plugin.host.key in keys


def disabled() -> list[Plugin]:
    """จุด plug ที่มีอยู่บนดิสก์แต่ถูกสั่งปิด — มีไว้ให้ `plugin-list` บอกผู้ดูแล

    ถ้าของที่ปิดแล้วหายไปจากรายการเฉย ๆ ผู้ดูแลจะแยกไม่ออกว่า "ปิดไว้"
    กับ "ไดเรกทอรีหายไปแล้ว" ซึ่งเป็นคนละเรื่องกันตอนแก้ปัญหา
    """
    switched_off = []
    for plugin_type in types():
        for plugin in _scan(plugin_type).values():
            if is_disabled(plugin):
                switched_off.append(plugin)
            # ไล่ข้างในต่อแม้ host จะถูกปิดไปแล้ว เพื่อให้รายการบอกครบว่าอะไร
            # หายไปจากระบบบ้าง — ปิด host หนึ่งตัวอาจหมายถึงหลายความสามารถ
            switched_off.extend(
                item for item in _scan_enhancements(plugin).values() if is_disabled(item)
            )
    return switched_off


def _scan(plugin_type: str) -> dict[str, Plugin]:
    """สิ่งที่อยู่บนดิสก์จริง ๆ **ไม่สนสวิตช์ปิด** — ดู `discover()` สำหรับของที่ใช้งานได้

    อ่านจากดิสก์ทุกครั้งที่เรียก — แอปนี้เล็กพอที่จะไม่ต้อง cache
    และทำให้วาง plugin ใหม่แล้วเห็นผลทันทีโดยไม่ต้อง restart
    """
    base = PLUGIN_ROOT / plugin_type
    if not base.is_dir():
        return {}

    found = {}
    for directory in sorted(base.iterdir()):
        if not directory.is_dir() or directory.name.startswith(("_", ".")):
            continue
        manifest = _read_manifest(directory)
        if manifest is None:
            continue
        found[directory.name] = Plugin(plugin_type, directory.name, directory.resolve(), manifest)
    return found


def discover(plugin_type: str) -> dict[str, Plugin]:
    """plugin ของชนิดนั้นที่ **ใช้งานได้จริงตอนนี้** เรียงตามไอดี

    ตัวที่ถูกสวิตช์ปิด (`DISABLED_PLUGINS`) หายไปจากผลลัพธ์เหมือนไม่เคยมี
    ไดเรกทอรีอยู่ — เพราะนั่นคือเส้นทางที่ทั้งระบบทดสอบไว้แล้ว (ดู `is_disabled`)
    """
    return {
        plugin_id: plugin
        for plugin_id, plugin in _scan(plugin_type).items()
        if not is_disabled(plugin)
    }


# ---------------------------------------------------------------- ส่วนเสริม (ADR 0025)


def _scan_enhancements(plugin: Plugin) -> dict[str, Plugin]:
    """ส่วนเสริมทุกตัวที่วางอยู่ใต้ plugin นี้ — **ยังไม่สนว่าใช้งานได้ไหม**

    ใช้กติกาเดิมของ ADR 0006 ซ้อนอีกชั้น: ไดเรกทอรีที่มี `plugin.json` คือจุด plug
    หนึ่งจุด ต่างกันแค่ว่าตัวนี้มี host

    **ส่วนเสริมห้ามมี `models.py`** — ถ้ามีข้อมูลของตัวเอง การสลับไป
    implementation ตัวอื่นจะกลายเป็นการย้ายข้อมูล ซึ่งไม่ใช่การ plug อีกต่อไป
    (ADR 0025) ข้อมูลที่จำเป็นเป็นของ plugin แม่ซึ่งเป็นเจ้าของตารางอยู่แล้ว
    """
    base = plugin.directory / ENHANCEMENTS_DIR
    if not base.is_dir():
        return {}

    found = {}
    for directory in sorted(base.iterdir()):
        if not directory.is_dir() or directory.name.startswith(("_", ".")):
            continue
        manifest = _read_manifest(directory)
        if manifest is None:
            continue
        if (directory / f"{MODELS_MODULE}.py").is_file():
            raise PluginError(
                f"{plugin.key}#{directory.name}: ส่วนเสริมห้ามมี {MODELS_MODULE}.py — "
                "ข้อมูลถาวรต้องเป็นของ plugin แม่ ไม่งั้นสลับ implementation ไม่ได้"
            )
        found[directory.name] = Plugin(
            plugin.type, directory.name, directory.resolve(), manifest, host=plugin
        )
    return found


def enhancements(plugin: Plugin) -> dict[str, Plugin]:
    """ส่วนเสริมที่ยังไม่ถูกสวิตช์ปิด — ตัวที่ปิดแล้วหายไปเหมือนไม่เคยมีไดเรกทอรี"""
    return {
        enhancement_id: enhancement
        for enhancement_id, enhancement in _scan_enhancements(plugin).items()
        if not is_disabled(enhancement)
    }


def usable_enhancements(plugin: Plugin) -> list[Plugin]:
    """ส่วนเสริมที่ **ไลบรารีครบ** — ตัวที่ยังไม่ได้ติดตั้งของถูกข้ามไปเงียบ ๆ

    ไม่ใช่ข้อผิดพลาด: ADR 0025 ถือว่า "ยังไม่ได้ติดตั้งไลบรารีของส่วนเสริม"
    เป็นสถานะปกติที่ออกแบบไว้ (หลักเดียวกับตารางของ plugin ที่ยังไม่ถูกสร้าง)
    """
    return [
        enhancement
        for enhancement in enhancements(plugin).values()
        if not missing_requirements(enhancement)
    ]


def enhancement_module(enhancement: Plugin) -> ModuleType | None:
    """โหลดโค้ดของส่วนเสริม — **`ImportError` = ปิดตัวเอง ไม่ใช่พัง**

    จับเฉพาะ `ImportError` โดยตั้งใจ ข้อผิดพลาดอื่น (syntax ผิด, ตัวแปรไม่มี)
    เป็นบั๊กของ plugin ที่ต้องดังให้ได้ยิน ไม่ใช่สิ่งที่ควรถูกกลืนหาย
    """
    try:
        return load_module(enhancement, PROVIDE_MODULE)
    except ImportError:
        return None


def _names_of(candidates: list[Plugin]) -> str:
    """ไอดีของผู้ให้บริการเรียงแล้ว สำหรับใส่ในข้อความเตือน"""
    return ", ".join(sorted(item.id for item in candidates))


def _unpicked(plugin: Plugin, capability: str, candidates: list[Plugin]) -> Plugin | None:
    """ไม่มีใครระบุตัวเลือกไว้ — เหลือตัวเดียวก็ใช้ตัวนั้น หลายตัวคือกำกวม

    **กำกวมเมื่อไหร่ปิดไว้ก่อน (fail closed)** ไม่ใช่เดาให้ เพราะการเดาแปลว่า
    วางไดเรกทอรีเพิ่มแล้วพฤติกรรมของระบบเปลี่ยนโดยไม่มีใครสั่ง
    """
    if len(candidates) == 1:
        return candidates[0]
    _warn(
        f"{plugin.key}: มีส่วนเสริมที่ให้ความสามารถ {capability!r} หลายตัว "
        f"({_names_of(candidates)}) "
        f"แต่ PLUGIN_PICKS ไม่ได้ระบุว่าจะใช้ตัวไหน — ปิดไว้ทั้งหมด"
    )
    return None


def provider(plugin: Plugin, capability: str) -> Plugin | None:
    """ส่วนเสริมที่ถูกเลือกให้ทำความสามารถนั้น — ไม่มีหรือกำกวมก็คืน None

    **ถ้า config ระบุตัวเลือกไว้ ตัวเลือกนั้นชนะเสมอ แม้จะเหลือตัวเดียว** —
    ไม่งั้นวันที่ตัวที่ถูกเลือกใช้ไม่ได้ (ปิดเพราะ CVE หรือไลบรารีหาย) ตัวที่
    ผู้ดูแล**ไม่ได้เลือก**จะถูกเลื่อนขึ้นมาแทนเงียบ ๆ ซึ่งเป็นสิ่งเดียวกับที่
    กฎ fail closed (ดู `_unpicked`) มีไว้ป้องกัน
    """
    candidates = [item for item in usable_enhancements(plugin) if item.provides == capability]
    if not candidates:
        return None

    wanted = _picks().get(f"{plugin.key}#{capability}")
    if wanted is None:
        return _unpicked(plugin, capability, candidates)

    chosen = next((item for item in candidates if item.id == wanted), None)
    if chosen is None:
        _warn(
            f"{plugin.key}: PLUGIN_PICKS เลือก {wanted!r} ไว้สำหรับความสามารถ "
            f"{capability!r} แต่ตัวนั้นใช้งานไม่ได้ตอนนี้ "
            f"(มีอยู่: {_names_of(candidates) or 'ไม่มีเลย'}) "
            "— ปิดไว้ ไม่เลื่อนตัวอื่นขึ้นมาแทน"
        )
    return chosen


def capability(plugin: Plugin, name: str) -> ModuleType | None:
    """โค้ดของความสามารถนั้นพร้อมใช้ไหม — คืนโมดูล หรือ None ถ้าไม่มี/ใช้ไม่ได้

    นี่คือฟังก์ชันเดียวที่ host ต้องเรียก ส่วนการตรวจว่ามีฟังก์ชันครบตามสัญญาไหม
    เป็นเรื่องของ host เพราะ registry ไม่รู้ว่าความสามารถแต่ละอย่างต้องมีอะไรบ้าง
    """
    chosen = provider(plugin, name)
    return None if chosen is None else enhancement_module(chosen)


def _picks() -> dict[str, str]:
    """ค่าที่ config ระบุไว้ว่าความสามารถไหนให้ใช้ส่วนเสริมตัวไหน"""
    if not has_app_context():
        return {}
    picks: dict[str, str] = current_app.config.get("PLUGIN_PICKS", {})
    return picks


def _warn(message: str) -> None:
    if has_app_context():
        current_app.logger.warning(message)
    else:  # pragma: no cover — นอก request/app context (เช่นตอน import)
        logging.getLogger(__name__).warning(message)


# ---------------------------------------------------------------- dependency ของ plugin


def category_of(plugin: Plugin) -> str:
    """ชื่อ category ของ pipenv ที่ dependency ของจุด plug นี้อยู่

    **คำนวณจากคีย์ ไม่ให้ manifest ประกาศเอง** (ADR 0025) — ค่าที่ประกาศซ้ำได้
    คือค่าที่วันหนึ่งจะไม่ตรงกับของจริงโดยไม่มีใครสังเกต
    """
    return "plugin-" + plugin.key.replace("/", "-").replace("#", "-")


def requirements(plugin: Plugin) -> list[str]:
    """แพ็กเกจ pip ที่จุด plug นี้ประกาศว่าตัวเองต้องใช้ (ว่าง = ไม่พึ่งอะไรเลย)"""
    declared = plugin.manifest.get("requires", {})
    if not isinstance(declared, dict):
        raise PluginError(f"{plugin.key}: `requires` ต้องเป็น object")
    return [str(item) for item in declared.get("pip", [])]


def distribution_name(requirement: str) -> str:
    """ชื่อแพ็กเกจล้วน ๆ จากสตริงแบบ `segno~=1.6` หรือ `foo[extra]>=2`"""
    return re.split(r"[<>=!~;\[\s]", requirement, maxsplit=1)[0].strip()


def missing_requirements(plugin: Plugin) -> list[str]:
    """แพ็กเกจที่ประกาศไว้แต่ยังไม่ได้ติดตั้งในสภาพแวดล้อมนี้

    **ตัวเลขเวอร์ชันไม่ได้ตรวจที่นี่** — `Pipfile.lock` เป็นคนคุมว่าเวอร์ชันไหน
    ถูกติดตั้ง ตรงนี้ตอบแค่ "มีหรือไม่มี" ซึ่งเป็นคำถามที่โค้ดตอนรันต้องใช้
    """
    missing = []
    for requirement in requirements(plugin):
        try:
            importlib.metadata.version(distribution_name(requirement))
        except importlib.metadata.PackageNotFoundError:
            missing.append(requirement)
    return missing


def types() -> list[str]:
    """ชนิดของ plugin ที่มีไดเรกทอรีอยู่จริง — core ไม่ได้ประกาศรายชื่อไว้ที่ไหน"""
    return sorted(
        directory.name
        for directory in PLUGIN_ROOT.iterdir()
        if directory.is_dir() and not directory.name.startswith(("_", "."))
    )


def installed_on_disk() -> list[Plugin]:
    """plugin ทุกตัวที่มีไดเรกทอรีอยู่จริง รวมตัวที่ถูกสวิตช์ปิด"""
    return [plugin for plugin_type in types() for plugin in _scan(plugin_type).values()]


def installed() -> list[Plugin]:
    """plugin ทุกตัวทุกชนิดที่ใช้งานได้ ณ ตอนนี้"""
    return [plugin for plugin_type in types() for plugin in discover(plugin_type).values()]


def _split_key(key: str) -> tuple[str, str, str]:
    host_key, _, enhancement_id = key.partition("#")
    plugin_type, _, plugin_id = host_key.partition("/")
    return plugin_type, plugin_id, enhancement_id


def find(key: str) -> Plugin | None:
    """หาจุด plug ที่ใช้งานได้ — รับทั้ง `<ชนิด>/<ไอดี>` และ `<ชนิด>/<ไอดี>#<ส่วนเสริม>`"""
    plugin_type, plugin_id, enhancement_id = _split_key(key)
    if not plugin_id:
        return None
    host = discover(plugin_type).get(plugin_id)
    if host is None or not enhancement_id:
        return host
    return enhancements(host).get(enhancement_id)


def find_on_disk(key: str) -> Plugin | None:
    """หาจุด plug โดย **ไม่สนสวิตช์ปิด** — สำหรับงานที่ต้องทำได้แม้ปิดโค้ดไว้แล้ว

    ที่ใช้จริงคือคำสั่งจัดการตารางของ plugin: ปิดโค้ดไว้ชั่วคราวเพราะมี CVE
    แล้วยังต้อง `plugin-uninstall` เก็บกวาดข้อมูลได้ ถ้าใช้ `find()` คำสั่งนั้น
    จะตอบว่า "ไม่รู้จัก plugin นี้" ทั้งที่ไดเรกทอรีกับตารางยังอยู่ครบ
    """
    plugin_type, plugin_id, enhancement_id = _split_key(key)
    if not plugin_id:
        return None
    host = _scan(plugin_type).get(plugin_id)
    if host is None or not enhancement_id:
        return host
    return _scan_enhancements(host).get(enhancement_id)


def plugin_of(path: str) -> Plugin | None:
    """plugin ที่เป็นเจ้าของไฟล์นั้น — ให้โค้ดของ plugin อ้างถึง *ตัวเอง* ได้

    เรียกด้วย `plugins.plugin_of(__file__)` จากในไฟล์ของ plugin เอง
    เพื่อไม่ต้องเขียนไอดีของตัวเองเป็นสตริงลงไป ซึ่งจะกลายเป็นค่าที่ผิดเงียบ ๆ
    ในวันที่มีคนเปลี่ยนชื่อไดเรกทอรี (ความสามารถหายไปโดยไม่มีอะไรฟ้อง)

    ครอบทุกชั้น (รวมส่วนเสริม) และไม่สนสวิตช์ปิด เพราะโค้ดที่ถามคำถามนี้
    คือโค้ดที่กำลังทำงานอยู่แล้ว
    """
    directory = pathlib.Path(path).resolve().parent
    return next(
        (plugin for plugin in plug_points_on_disk() if plugin.directory == directory),
        None,
    )


def plug_points() -> list[Plugin]:
    """จุด plug ทุกจุดทุกชั้น — plugin ทุกตัวบวกส่วนเสริมของแต่ละตัว

    ใช้ตอบคำถามที่ต้องครอบทุกชั้น เช่น "ระบบนี้พึ่งไลบรารีอะไรบ้าง"
    """
    points = []
    for plugin in installed():
        points.append(plugin)
        points.extend(enhancements(plugin).values())
    return points


def plug_points_on_disk() -> list[Plugin]:
    """จุด plug ทุกจุดทุกชั้นที่ **มีไดเรกทอรีอยู่จริง** รวมตัวที่ถูกสวิตช์ปิด

    ใช้ตอบคำถามที่ต้องเห็นของครบไม่ว่าจะเปิดหรือปิด — `flask plugin-list`
    (ผู้ดูแลต้องเห็นว่าอะไรถูกปิดอยู่) และ `plugin_of()` (โค้ดที่กำลังรันอยู่
    ถามหาตัวเอง)
    """
    points = []
    for plugin in installed_on_disk():
        points.append(plugin)
        points.extend(_scan_enhancements(plugin).values())
    return points


# ---------------------------------------------------------------- ข้อมูลของ plugin

# ผลของการ import models.py ของทุก plugin — cache ไว้เพราะ import ซ้ำจะไม่เห็น
# ตารางใหม่อีก (โมดูลถูก cache ไว้แล้ว) การอ่านค่าจึงต้องมาจากที่นี่ที่เดียว
_owned: dict[str, frozenset[str]] | None = None
# โมดูล `models.py` ที่โหลดไปแล้ว เก็บไว้เพื่อถามค่าที่ plugin ประกาศ (เช่น
# `AUDIT_POLICIES`) โดยไม่ต้อง import ซ้ำ
_modules: dict[str, ModuleType] = {}


def load_module(plugin: Plugin, module_name: str) -> ModuleType | None:
    """โหลดโมดูลของ plugin ตามชื่อไฟล์ (`models`, `factor`, …) — ไม่มีไฟล์คืน None

    โหลดจาก path ตรง ๆ ไม่ผ่านชื่อโมดูลปกติ เพราะไอดีของ plugin เป็นชื่อ
    ไดเรกทอรีที่มีขีดกลางได้ ซึ่งเป็นชื่อโมดูล python ที่ import ตรง ๆ ไม่ได้
    """
    path = plugin.directory / f"{module_name}.py"
    if not path.is_file():
        return None
    # ชื่อโมดูลมาจาก **คีย์เต็ม** ไม่ใช่แค่ชนิดกับไอดี — ส่วนเสริมชื่อเดียวกัน
    # ที่อยู่ใต้ plugin คนละตัวต้องไม่ชนกันใน sys.modules (ตัวหลังจะได้โค้ดของ
    # ตัวแรกกลับไปเงียบ ๆ เพราะ python คืนของที่ cache ไว้)
    name = f"app.plugins.{re.sub(r'[^0-9a-zA-Z]+', '_', plugin.key)}.{module_name}"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover — ไฟล์มีอยู่แล้ว
        raise PluginError(f"{plugin.key}: โหลด {path.name} ไม่ได้")
    module = importlib.util.module_from_spec(spec)
    # ใส่เข้า sys.modules ก่อน exec เพื่อให้ import ซ้อนภายในโมดูลทำงานได้
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        # **ต้องถอนออกถ้า exec ล้ม** ไม่งั้นโมดูลที่รันไม่จบค้างอยู่ใน cache
        # แล้วการเรียกครั้งถัดไปจะได้ของครึ่ง ๆ กลาง ๆ กลับไปโดยไม่มี error
        # (เส้นทางนี้เป็นเรื่องปกติของส่วนเสริม เพราะ `ImportError` ถูกกลืน
        # ไว้เป็นการปิดตัวเอง — ครั้งแรกได้ None ครั้งที่สองได้โมดูลเปล่า)
        # ทำแบบเดียวกับ importlib เองใน `_bootstrap._load`
        del sys.modules[name]
        raise
    return module


def load_models() -> dict[str, frozenset[str]]:
    """import model ของ plugin ทุกตัว คืน map `<ชนิด>/<ไอดี>` → ชื่อตารางที่มันเป็นเจ้าของ

    **รู้ว่าตารางไหนเป็นของใครด้วยการดูว่ามีอะไรโผล่เข้า metadata ระหว่าง import**
    ไม่ใช่ให้ plugin ประกาศรายชื่อตารางไว้ใน manifest ซึ่งจะไม่ตรงกับของจริง
    ในวันที่มีคนเพิ่ม model แล้วลืมแก้ manifest
    """
    global _owned  # noqa: PLW0603  ผลของการ import เป็นสถานะระดับ process อยู่แล้ว
    if _owned is not None:
        return _owned

    from app import db

    found: dict[str, frozenset[str]] = {}
    _modules.clear()
    # **อ่านจากดิสก์ตรง ๆ ไม่ผ่านสวิตช์ปิด** — สวิตช์ปิด *โค้ด* ไม่ได้ปิด *ข้อมูล*
    # ถ้าตรงนี้เคารพสวิตช์ ตารางของ plugin ที่ถูกปิดจะกลายเป็นตารางไม่มีเจ้าของ
    # แล้ว `flask db migrate` ตัวถัดไปของ core จะออก migration ที่ drop มันทิ้ง
    # (env.py กรองตาราง "ของ plugin" ออกจาก autogenerate ด้วย `owned_tables()`)
    # วงจรชีวิตของข้อมูลเป็นของ `plugin-install`/`plugin-uninstall` เท่านั้น
    for plugin in installed_on_disk():
        before = set(db.metadata.tables)
        module = load_module(plugin, MODELS_MODULE)
        if module is None:
            continue
        _modules[plugin.key] = module
        # ตารางที่ "เพิ่งโผล่" บอกได้ว่า plugin ตัวนี้ประกาศอะไรผิด prefix ไหม
        # (ตรวจได้เฉพาะรอบที่ import จริง — รอบถัดไป python คืนโมดูลจาก cache)
        added = set(db.metadata.tables) - before
        wrong = sorted(name for name in added if not name.startswith(plugin.table_prefix))
        if wrong:
            raise PluginError(
                f"{plugin.key}: ตาราง {', '.join(wrong)} ต้องขึ้นต้นด้วย {plugin.table_prefix!r} "
                "ไม่งั้นแยกไม่ออกว่าเป็นของ plugin ตัวไหนตอนถอน"
            )
        # **ความเป็นเจ้าของอ่านจาก prefix ไม่ใช่จาก delta** — ถ้าอ่านจาก delta
        # รอบที่โมดูลถูก cache ไว้แล้ว (เช่นหลัง `forget_models()`) จะได้ผลว่า
        # plugin ไม่มีตารางเลย แล้ว `owned_tables()` ที่ env.py กับ CLI ใช้จะว่าง
        # → migration ของ core กลับมาเห็นตารางของ plugin อีก (เจอตอนเขียนเทสต์ CLI)
        owned_now = frozenset(
            name for name in db.metadata.tables if name.startswith(plugin.table_prefix)
        )
        if owned_now:
            found[plugin.key] = owned_now
    _owned = found
    return _owned


def audit_policies() -> dict[str, str]:
    """ชั้น audit ของคอลัมน์ที่ plugin แต่ละตัวประกาศไว้ใน `models.py` ของตัวเอง

    core เรียกตัวนี้ตอนตัดสินว่าจะบันทึกค่าคอลัมน์ลง audit ยังไง — ชื่อคอลัมน์
    ของ plugin จึงไม่ต้องไปโผล่ในโค้ด core เลย (ADR 0023)
    """
    load_models()
    merged: dict[str, str] = {}
    for module in _modules.values():
        merged.update(getattr(module, "AUDIT_POLICIES", {}))
    return merged


def forget_models() -> None:
    """ลืมผลการ import ทิ้ง เพื่อให้ `load_models()` อ่านดิสก์ใหม่

    ต่างจาก `discover()` ที่อ่านดิสก์ทุกครั้ง — ตรงนี้ cache ไว้เพราะการ import
    ซ้ำจะไม่เห็นตารางใหม่อีก (python cache โมดูลไว้แล้ว) ใช้ตอนเทสต์ที่วาง
    plugin ลงไประหว่างรัน ของจริงไม่ต้องเรียกเพราะ plugin มาพร้อมตอน deploy
    """
    global _owned  # noqa: PLW0603  ตัวเดียวกับที่ load_models() ดูแล
    _owned = None


def tables_of(plugin: Plugin) -> frozenset[str]:
    """ชื่อตารางที่ plugin ตัวนี้เป็นเจ้าของ"""
    return load_models().get(plugin.key, frozenset())


def owned_tables() -> frozenset[str]:
    """ตารางทั้งหมดที่เป็นของ plugin — **core ใช้ตัวนี้เพื่อ "ไม่ยุ่ง" กับมัน**

    ที่ใช้จริง: `migrations/env.py` กรองออกจาก autogenerate ไม่งั้น migration
    ตัวถัดไปของ core จะสร้าง/drop ตารางของ plugin ตามการวาง/ถอนไดเรกทอรี
    """
    return frozenset(name for tables in load_models().values() for name in tables)


def _table_objects(plugin: Plugin) -> list[Any]:
    from app import db

    return [db.metadata.tables[name] for name in sorted(tables_of(plugin))]


def is_installed(plugin: Plugin) -> bool:
    """ตารางของ plugin ตัวนี้มีอยู่จริงในฐานข้อมูลแล้วหรือยัง

    **core ต้องถามข้อนี้ก่อนใช้งาน plugin ที่มีข้อมูล** ไม่งั้นการวางไดเรกทอรี
    ลงไปโดยยังไม่ `flask plugin-install` จะทำให้ทุกหน้าที่แตะ plugin นั้นพัง
    ด้วย "no such table" — รวมถึงหน้า login (เจอจริงตอน Phase 4: job a11y ใน CI
    ล้มทั้ง job เพราะ CI รันแค่ `flask db upgrade` ซึ่งไม่สร้างตารางของ plugin
    ตามดีไซน์)

    plugin ที่ไม่มีตารางของตัวเอง (เช่นธีม) ถือว่าติดตั้งแล้วเสมอ
    """
    from sqlalchemy import inspect

    from app import db

    tables = tables_of(plugin)
    if not tables:
        return True
    return tables <= set(inspect(db.engine).get_table_names())


def install(plugin: Plugin) -> frozenset[str]:
    """สร้างตารางของ plugin ตัวนี้ (ทำซ้ำได้ ไม่พังถ้ามีอยู่แล้ว)"""
    from app import db

    tables = _table_objects(plugin)
    if tables:
        db.metadata.create_all(bind=db.engine, tables=tables, checkfirst=True)
    return tables_of(plugin)


def uninstall(plugin: Plugin) -> frozenset[str]:
    """ลบตารางของ plugin ตัวนี้ทิ้ง — **ข้อมูลหายจริง ไม่ใช่ soft delete**

    ต่างจากข้อมูลของ core โดยตั้งใจ: การถอน plugin คือการบอกว่า "ไม่ใช้
    ความสามารถนี้แล้ว" ข้อมูลที่ค้างอยู่ของความสามารถที่ไม่มีอยู่แล้วคือของที่
    ไม่มีใครดูแล และตัว plugin เองก็ไม่อยู่ให้ purge job เรียกใช้อีกต่อไป
    """
    from app import db

    tables = _table_objects(plugin)
    if tables:
        db.metadata.drop_all(bind=db.engine, tables=tables, checkfirst=True)
    return tables_of(plugin)


# ---------------------------------------------------------------- ปัจจัยยืนยันตัวตน


def second_factors() -> list[Plugin]:
    """plugin ชนิด `auth` ที่ประกาศตัวเองเป็นปัจจัยที่สอง

    core รู้แค่ว่า "มีกี่ตัว" กับ "เรียกอะไรได้บ้าง" ไม่รู้จักชื่อตัวไหนเลย
    ถอนไดเรกทอรีทิ้งแล้วระบบกลับไปเป็น login ด้วยรหัสผ่านอย่างเดียวทันที
    """
    return [
        plugin
        for plugin in discover(AUTH_TYPE).values()
        if plugin.manifest.get("factor") == "second"
    ]


# รูปแบบของปัจจัยหลัก (ADR 0029) — **manifest ประกาศเอง core ไม่เดา**
# `redirect` = พาผู้ใช้ออกไปยืนยันตัวตนที่อื่นแล้วเดินกลับมา (`begin`/`finish`)
# `credential` = รับชื่อกับรหัสผ่านมาตรวจให้ตรง ๆ (`authenticate`)
REDIRECT_STYLE = "redirect"
CREDENTIAL_STYLE = "credential"


def factor_style(plugin: Plugin) -> str:
    """รูปแบบของปัจจัยหลักตัวนี้ — ไม่ประกาศ = `redirect`

    ค่าเริ่มต้นเป็น `redirect` เพื่อความเข้ากันได้กับ plugin ที่เขียนไว้ก่อน
    ADR 0029 (และเพราะตอนนั้นมีอยู่แบบเดียว) — **ไม่ใช่การเดาจากฟังก์ชันที่มี**
    ซึ่งจะทำให้ชื่อฟังก์ชันที่พิมพ์ผิดกลายเป็นการเปลี่ยนรูปแบบเงียบ ๆ
    """
    return str(plugin.manifest.get("style", REDIRECT_STYLE))


def primary_factors(style: str | None = None) -> list[Plugin]:
    """ปัจจัยหลักที่ **ไม่ใช่รหัสผ่าน** (ADR 0028) กรองตามรูปแบบได้ (ADR 0029)

    `password` ถูกกันออกด้วย `"core": true` ไม่ใช่ด้วยชื่อ — core จึงยังไม่รู้จัก
    ชื่อ plugin ตัวไหนเลย และวันที่มีปัจจัยหลักของ core ตัวอื่นก็ไม่ต้องมาแก้ที่นี่
    (ตัวที่เป็น core คือตัวที่ core เรียกเองอยู่แล้ว ไม่ต้องผ่าน seam นี้)
    """
    return [
        plugin
        for plugin in discover(AUTH_TYPE).values()
        if plugin.manifest.get("factor") == "primary"
        and not plugin.manifest.get("core")
        and (style is None or factor_style(plugin) == style)
    ]


def factor_module(plugin: Plugin) -> ModuleType:
    """โมดูลที่ทำงานจริงของปัจจัยตัวนั้น — ต้องมีเสมอ (ตรวจตอน start)"""
    module = load_module(plugin, FACTOR_MODULE)
    if module is None:
        raise PluginError(f"{plugin.key}: ไม่มี {FACTOR_MODULE}.py")
    return module


def themes() -> dict[str, Plugin]:
    return discover(THEME_TYPE)


def get_theme(theme_id: str) -> Plugin | None:
    """คืน plugin ธีมตามไอดี — ไม่มีก็คืน None (ปล่อยให้ผู้เรียกตัดสินใจ)"""
    return themes().get(theme_id)


def core_theme() -> Plugin:
    """ธีมสำรองที่ต้องมีเสมอ"""
    found = get_theme(CORE_THEME)
    if found is None:
        raise PluginError(
            f"ไม่พบธีม core '{CORE_THEME}' — ต้องมีไดเรกทอรี app/plugins/{THEME_TYPE}/{CORE_THEME}/ เสมอ"
        )
    return found


def _check_switch() -> None:
    """ตรวจสวิตช์ปิดตอน start — ปิดของ core ไม่ได้ และของที่ปิดต้องถูกบันทึกไว้

    **ปิด plugin ของ core ไม่ได้** และต้องบอกให้ชัดว่าเพราะอะไร ถ้าปล่อยผ่าน
    แอปจะไปพังทีหลังด้วยข้อความ "ไม่พบธีม core" ซึ่งชี้ไปผิดที่ (ไดเรกทอรียังอยู่ครบ
    แค่ถูกสั่งปิด) — คนที่กำลังแก้ปัญหาตอนตีสามไม่ควรต้องเดา

    ที่เหลือแค่ log ไว้ ไม่ได้ห้าม เพราะการปิดคือสิ่งที่สวิตช์นี้มีไว้ทำ แต่ต้องมี
    ร่องรอยทุกครั้งที่แอป start ว่าตอนนั้นระบบเดินอยู่โดยไม่มีความสามารถอะไรบ้าง
    """
    for key in sorted(disabled_keys()):
        point = find_on_disk(key)
        if point is not None and point.is_core:
            raise PluginError(
                f"DISABLED_PLUGINS: ปิด {key} ไม่ได้เพราะเป็น plugin ของ core "
                "— core ต้องมีตัวสำรองเสมอ เอาคีย์นี้ออกจาก DISABLED_PLUGINS"
            )
        if point is None:
            # ไม่ใช่ข้อผิดพลาด เพราะปิดของที่ถอนไปแล้วก็ได้ผลเหมือนกัน
            # แต่คีย์ที่พิมพ์ผิดก็หน้าตาแบบนี้เป๊ะ จึงต้องบอกไว้
            _warn(f"DISABLED_PLUGINS: ไม่มีจุด plug ชื่อ {key!r} อยู่บนดิสก์")
    for point in disabled():
        _warn(f"{point.key}: ปิดอยู่ตามคำสั่ง DISABLED_PLUGINS")
        # **ปิดปัจจัยยืนยันตัวตน = ลดระดับความปลอดภัยของคนที่เปิดใช้ไว้แล้ว**
        # คนที่เคยต้องใส่รหัสสองชั้นจะ login ได้ด้วยรหัสผ่านอย่างเดียวทันที
        # (ข้อมูลของเขายังอยู่ครบ เปิดสวิตช์กลับก็กลับมาเหมือนเดิม) — เรื่องนี้
        # ต้องดังกว่าบรรทัดข้างบน เพราะคีย์ของ plugin แม่กับของส่วนเสริมต่างกัน
        # แค่ `#` เดียว คนที่ตั้งใจปิดแค่ตัววาด QR พิมพ์พลาดเป็นตัวแม่ได้ง่ายมาก
        if point.manifest.get("factor"):
            _warn(
                f"{point.key}: นี่คือปัจจัยยืนยันตัวตน — ผู้ใช้ที่เปิดไว้จะ login "
                "ด้วยรหัสผ่านอย่างเดียวจนกว่าจะเอาคีย์นี้ออกจาก DISABLED_PLUGINS "
                "(ถ้าตั้งใจปิดแค่ส่วนเสริมของมัน คีย์ต้องมี # ต่อท้าย)"
            )


def _check_themes() -> None:
    """ธีมที่ไม่มีไฟล์สีคือธีมที่เลือกแล้วหน้าเว็บกลายเป็นขาวดำ"""
    for plugin in themes().values():
        if not plugin.stylesheet:
            raise PluginError(f"ธีม {plugin.id}: manifest ไม่ได้ระบุ stylesheet")
        if not plugin.file(plugin.stylesheet).is_file():
            raise PluginError(f"ธีม {plugin.id}: ไม่พบไฟล์ {plugin.stylesheet}")


def _check_enhancements() -> None:
    """ส่วนเสริมที่มี manifest แต่ไม่มีโค้ดคือของที่แพ็กมาไม่ครบ — ให้ดังตั้งแต่ start

    ต่างจาก "ไลบรารียังไม่ได้ติดตั้ง" ซึ่งเป็นสถานะปกติที่ตั้งใจให้เงียบ (ADR 0025)
    """
    for plugin in installed():
        for enhancement in enhancements(plugin).values():
            if not (enhancement.directory / f"{PROVIDE_MODULE}.py").is_file():
                raise PluginError(f"{enhancement.key}: ไม่มี {PROVIDE_MODULE}.py")
            if not enhancement.provides:
                raise PluginError(f"{enhancement.key}: manifest ไม่ได้ระบุ `provides`")


def _check_db_backends() -> None:
    """backend ของฐานข้อมูลต้องไม่เป็นเจ้าของตารางใด ๆ (ADR 0026 ข้อ 3)

    schema เดียวกันทุกยี่ห้อเป็น *ข้อกำหนด* ไม่ใช่ผลพลอยได้ — backend ที่มีตาราง
    ของตัวเองแปลว่าการย้ายยี่ห้อกลายเป็นการย้ายข้อมูลที่ไม่มีใครเขียนทางไว้
    และ migration ของ core จะมองไม่เห็นตารางนั้น (`owned_tables()` กรองออก)
    """
    for plugin in installed_on_disk():
        if plugin.type == DB_TYPE and tables_of(plugin):
            raise PluginError(
                f"{plugin.key}: plugin ชนิด {DB_TYPE} ห้ามมีตารางของตัวเอง "
                f"(เจอ {', '.join(sorted(tables_of(plugin)))}) — มันเป็นเจ้าของทางที่ข้อมูล "
                "วิ่งผ่าน ไม่ใช่เจ้าของข้อมูล ดู ADR 0026"
            )


def _check_second_factors() -> None:
    """ปัจจัยที่สองที่ทำสัญญาไม่ครบ = ด่าน login ที่พังตอนมีคนพยายาม login จริง"""
    for plugin in second_factors():
        module = factor_module(plugin)
        missing = [
            name for name in SECOND_FACTOR_CONTRACT if not callable(getattr(module, name, None))
        ]
        if missing:
            raise PluginError(f"{plugin.key}: {FACTOR_MODULE}.py ต้องมีฟังก์ชัน {', '.join(missing)}")


def check_installation() -> None:
    """ตรวจตอนสร้างแอปว่าโครงสร้าง plugin ใช้ได้

    ให้พังตั้งแต่ตอน start ดีกว่าไปพังตอน render หน้าแรก — รายการที่ตรวจอยู่ใน
    `_check_*` ข้างบน ตัวนี้เป็นแค่ลำดับการเรียก **ลำดับสำคัญ**: สวิตช์ก่อน
    (คีย์ผิดต้องบอกก่อนที่อย่างอื่นจะพังตามแบบชี้ผิดที่) แล้วธีมสำรองของ core
    """
    _check_switch()
    core_theme()
    # โหลด model ของ plugin ที่มีข้อมูลของตัวเอง — ให้ prefix ที่ผิดพังตั้งแต่ตอน
    # start ไม่ใช่ตอนที่มีคนกด install แล้วได้ตารางชื่อประหลาดค้างในฐานข้อมูล
    load_models()
    _check_themes()
    _check_enhancements()
    _check_db_backends()
    _check_second_factors()
