"""ระบบ plugin — core ไม่รู้จัก plugin ตัวไหนเป็นการเฉพาะ

**สัญญาของสถาปัตยกรรมนี้**

* core รู้แค่ *วิธีค้นหา* plugin ไม่ได้ hardcode ชื่อ plugin ไว้ที่ไหนเลย
* plugin หนึ่งตัว = หนึ่งไดเรกทอรีใต้ `app/plugins/<ชนิด>/<ไอดี>/`
  ชื่อไดเรกทอรีคือไอดีของ plugin
* เพิ่ม plugin = วางไดเรกทอรีลงไป **ไม่ต้องแก้โค้ด core แม้แต่บรรทัดเดียว**
* ลบ plugin = ลบไดเรกทอรีทิ้ง ระบบต้องยังทำงานได้ ผู้ใช้ที่เลือก plugin นั้นไว้
  จะตกกลับไปใช้ตัว core อัตโนมัติ
* plugin ที่ต้องเก็บข้อมูลเพิ่มต้องดูแล table ของตัวเอง ห้ามแก้ table ของ core
  (ยังไม่มี plugin ชนิดนั้นในตอนนี้ — ดู "ยังไม่ได้ทำ" ใน CLAUDE.md)

ตอนนี้รองรับชนิดเดียวคือ `theme` แต่ตัว registry ออกแบบให้เพิ่มชนิดอื่นได้
โดยไม่ต้องรื้อ
"""

import json
import pathlib

PLUGIN_ROOT = pathlib.Path(__file__).resolve().parent
MANIFEST_NAME = "plugin.json"

THEME_TYPE = "themes"

# ไอดีของ plugin ที่ core ต้องมีเสมอ ใช้เป็นตัวสำรองเวลา plugin อื่นหายไป
# ตัวนี้ลบไม่ได้ — ถ้าหายแอปจะไม่ start (ดู load_all)
CORE_THEME = "system"


class PluginError(RuntimeError):
    """manifest เสียหรือโครงสร้าง plugin ไม่ถูกต้อง"""


class Plugin:
    """ข้อมูลของ plugin หนึ่งตัวที่อ่านมาจาก manifest"""

    def __init__(self, plugin_type, plugin_id, directory, manifest):
        self.type = plugin_type
        self.id = plugin_id
        self.directory = directory
        self.manifest = manifest

    @property
    def name(self):
        """ชื่อที่เอาไปแสดง — ไม่ผ่าน gettext เพราะเป็นข้อมูลของ plugin
        ไม่ใช่ข้อความของ core (plugin จะแปลเองต้องมี lang pack ของตัวเอง)"""
        return self.manifest.get("name", self.id)

    @property
    def version(self):
        return self.manifest.get("version", "0")

    @property
    def is_core(self):
        """plugin ที่มากับระบบ ลบไม่ได้"""
        return bool(self.manifest.get("core", False))

    @property
    def stylesheet(self):
        return self.manifest.get("stylesheet")

    def file(self, filename):
        """path ของไฟล์ใน plugin — กันไม่ให้หลุดออกนอกไดเรกทอรีตัวเอง"""
        target = (self.directory / filename).resolve()
        if not target.is_relative_to(self.directory):
            raise PluginError(f"{self.id}: ไฟล์อยู่นอกไดเรกทอรีของ plugin")
        return target

    def __repr__(self):
        return f"<Plugin {self.type}/{self.id} v{self.version}>"


def _read_manifest(directory):
    path = directory / MANIFEST_NAME
    try:
        manifest = json.loads(path.read_text())
    except FileNotFoundError:
        return None  # ไม่ใช่ไดเรกทอรีของ plugin ข้ามไป
    except json.JSONDecodeError as exc:
        raise PluginError(f"{directory.name}: {MANIFEST_NAME} อ่านไม่ได้ — {exc}")
    if not isinstance(manifest, dict):
        raise PluginError(f"{directory.name}: {MANIFEST_NAME} ต้องเป็น object")
    return manifest


def discover(plugin_type):
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
        found[directory.name] = Plugin(
            plugin_type, directory.name, directory.resolve(), manifest
        )
    return found


def themes():
    return discover(THEME_TYPE)


def get_theme(theme_id):
    """คืน plugin ธีมตามไอดี — ไม่มีก็คืน None (ปล่อยให้ผู้เรียกตัดสินใจ)"""
    return themes().get(theme_id)


def core_theme():
    """ธีมสำรองที่ต้องมีเสมอ"""
    found = get_theme(CORE_THEME)
    if found is None:
        raise PluginError(
            f"ไม่พบธีม core '{CORE_THEME}' — ต้องมีไดเรกทอรี "
            f"app/plugins/{THEME_TYPE}/{CORE_THEME}/ เสมอ"
        )
    return found


def check_installation():
    """ตรวจตอนสร้างแอปว่าโครงสร้าง plugin ใช้ได้

    ให้พังตั้งแต่ตอน start ดีกว่าไปพังตอน render หน้าแรก
    """
    core_theme()
    for plugin in themes().values():
        if not plugin.stylesheet:
            raise PluginError(f"ธีม {plugin.id}: manifest ไม่ได้ระบุ stylesheet")
        if not plugin.file(plugin.stylesheet).is_file():
            raise PluginError(
                f"ธีม {plugin.id}: ไม่พบไฟล์ {plugin.stylesheet}"
            )
