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

import importlib.util
import json
import pathlib
import sys
from types import ModuleType
from typing import Any

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent
MANIFEST_NAME = "plugin.json"

THEME_TYPE = "themes"

# ไอดีของ plugin ที่ core ต้องมีเสมอ ใช้เป็นตัวสำรองเวลา plugin อื่นหายไป
# ตัวนี้ลบไม่ได้ — ถ้าหายแอปจะไม่ start (ดู load_all)
CORE_THEME = "system"


class PluginError(RuntimeError):
    """manifest เสียหรือโครงสร้าง plugin ไม่ถูกต้อง"""


AUTH_TYPE = "auth"

# ชื่อโมดูลที่ plugin ใช้ประกาศ model ของตัวเอง (ไม่มีก็ได้ = ไม่มีข้อมูลของตัวเอง)
MODELS_MODULE = "models"
# โมดูลที่ plugin ชนิด auth ต้องมี ถ้าประกาศตัวเองเป็นปัจจัยที่สอง
FACTOR_MODULE = "factor"
# ฟังก์ชันที่ปัจจัยที่สองต้องมีครบ — core เรียกแค่สองตัวนี้ ไม่รู้อะไรมากกว่านี้
SECOND_FACTOR_CONTRACT = ("is_enrolled", "verify")


class Plugin:
    """ข้อมูลของ plugin หนึ่งตัวที่อ่านมาจาก manifest"""

    def __init__(
        self, plugin_type: str, plugin_id: str, directory: pathlib.Path, manifest: dict[str, Any]
    ) -> None:
        self.type = plugin_type
        self.id = plugin_id
        self.directory = directory
        self.manifest = manifest

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
        """ชื่อเต็มที่ใช้อ้างถึง plugin ตัวนี้จากบรรทัดคำสั่ง เช่น `auth/totp`"""
        return f"{self.type}/{self.id}"

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


def discover(plugin_type: str) -> dict[str, Plugin]:
    """หา plugin ทุกตัวของชนิดนั้น เรียงตามไอดี

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


def types() -> list[str]:
    """ชนิดของ plugin ที่มีไดเรกทอรีอยู่จริง — core ไม่ได้ประกาศรายชื่อไว้ที่ไหน"""
    return sorted(
        directory.name
        for directory in PLUGIN_ROOT.iterdir()
        if directory.is_dir() and not directory.name.startswith(("_", "."))
    )


def installed() -> list[Plugin]:
    """plugin ทุกตัวทุกชนิดที่ค้นเจอบนดิสก์ ณ ตอนนี้"""
    return [plugin for plugin_type in types() for plugin in discover(plugin_type).values()]


def find(key: str) -> Plugin | None:
    """หา plugin จากชื่อเต็ม `<ชนิด>/<ไอดี>` — ไม่มีก็คืน None"""
    plugin_type, _, plugin_id = key.partition("/")
    return discover(plugin_type).get(plugin_id) if plugin_id else None


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
    name = f"app.plugins.{plugin.type}.{plugin.id.replace('-', '_')}.{module_name}"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover — ไฟล์มีอยู่แล้ว
        raise PluginError(f"{plugin.key}: โหลด {path.name} ไม่ได้")
    module = importlib.util.module_from_spec(spec)
    # ใส่เข้า sys.modules ก่อน exec เพื่อให้ import ซ้อนภายในโมดูลทำงานได้
    sys.modules[name] = module
    spec.loader.exec_module(module)
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
    for plugin in installed():
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


def check_installation() -> None:
    """ตรวจตอนสร้างแอปว่าโครงสร้าง plugin ใช้ได้

    ให้พังตั้งแต่ตอน start ดีกว่าไปพังตอน render หน้าแรก
    """
    core_theme()
    # โหลด model ของ plugin ที่มีข้อมูลของตัวเอง — ให้ prefix ที่ผิดพังตั้งแต่ตอน
    # start ไม่ใช่ตอนที่มีคนกด install แล้วได้ตารางชื่อประหลาดค้างในฐานข้อมูล
    load_models()
    for plugin in themes().values():
        if not plugin.stylesheet:
            raise PluginError(f"ธีม {plugin.id}: manifest ไม่ได้ระบุ stylesheet")
        if not plugin.file(plugin.stylesheet).is_file():
            raise PluginError(f"ธีม {plugin.id}: ไม่พบไฟล์ {plugin.stylesheet}")
    # ปัจจัยที่สองที่ทำสัญญาไม่ครบ = ด่าน login ที่พังตอนมีคนพยายาม login จริง
    # ให้พังตั้งแต่ตอน start ดีกว่า
    for plugin in second_factors():
        module = factor_module(plugin)
        missing = [
            name for name in SECOND_FACTOR_CONTRACT if not callable(getattr(module, name, None))
        ]
        if missing:
            raise PluginError(f"{plugin.key}: {FACTOR_MODULE}.py ต้องมีฟังก์ชัน {', '.join(missing)}")
