"""ธีมและโหมดของแต่ละ request

แยกเป็นสองแกน:

* **theme** — ชื่อชุดสี ตอนนี้มีชุดเดียวชื่อ `system` เผื่อเพิ่มทีหลัง
* **mode**  — ระดับความสว่าง: `light`, `dark`, `auto`

`auto` ตัดสินจากเวลาดวงอาทิตย์ขึ้น-ตกของ timezone ที่ผู้ใช้ตั้งไว้
โดยอ่านจากตารางใน `app/sun_data.py` ที่ generate ไว้ล่วงหน้า
ไม่เรียก API ภายนอกและไม่ต้องพึ่ง JS

ลำดับความสำคัญเหมือนภาษา: `?mode=` → session → `User.mode` → ค่าเริ่มต้น
"""

from datetime import datetime

from flask import has_request_context, request, session
from flask_login import current_user

from app import plugins, tz
from app.sun_data import ALWAYS_DARK, ALWAYS_LIGHT, SUN_TIMES

THEME_SESSION_KEY = "theme"
MODE_SESSION_KEY = "mode"

DEFAULT_THEME = plugins.CORE_THEME
AUTO = "auto"
LIGHT = "light"
DARK = "dark"
MODES = (LIGHT, DARK, AUTO)
DEFAULT_MODE = AUTO


def themes() -> dict[str, plugins.Plugin]:
    """ชุดสีที่ติดตั้งอยู่: ไอดี -> Plugin — มาจากการค้นหาไดเรกทอรี ไม่ใช่ config"""
    return plugins.themes()


def theme_is_supported(value: str | None) -> bool:
    return bool(value) and value in themes()


def mode_is_supported(value: str | None) -> bool:
    return value in MODES


def select_theme() -> str:
    if not has_request_context():
        return DEFAULT_THEME
    if theme_is_supported(request.args.get(THEME_SESSION_KEY)):
        return str(request.args[THEME_SESSION_KEY])
    if theme_is_supported(session.get(THEME_SESSION_KEY)):
        return str(session[THEME_SESSION_KEY])
    if current_user.is_authenticated and theme_is_supported(current_user.theme):
        return str(current_user.theme)
    return DEFAULT_THEME


def select_mode() -> str:
    """โหมดที่ผู้ใช้เลือก — อาจเป็น 'auto' ซึ่งยังไม่ใช่ค่าที่เอาไปแสดงได้"""
    if not has_request_context():
        return DEFAULT_MODE
    if mode_is_supported(request.args.get(MODE_SESSION_KEY)):
        return str(request.args[MODE_SESSION_KEY])
    if mode_is_supported(session.get(MODE_SESSION_KEY)):
        return str(session[MODE_SESSION_KEY])
    if current_user.is_authenticated and mode_is_supported(current_user.mode):
        return str(current_user.mode)
    return DEFAULT_MODE


def sun_mode(tz_name: str | None, now_local: datetime | None = None) -> str:
    """โหมดตามดวงอาทิตย์ของ timezone หนึ่ง ๆ — คืน 'light' หรือ 'dark' เสมอ

    โซนที่ไม่มีในตาราง (เช่นชื่อพ้องที่ tzdata ไม่ได้ให้พิกัดไว้) ให้ 'light'
    ดีกว่าโยน error เพราะนี่เป็นแค่การเลือกสี
    """
    resolved = tz.resolve(tz_name)
    row = SUN_TIMES.get(str(resolved.key))
    if row is None:
        return LIGHT

    if now_local is None:
        now_local = tz.to_local(tz.now_utc(), tz_name)

    sunrise, sunset = row[(now_local.month - 1) * 2], row[(now_local.month - 1) * 2 + 1]
    if sunrise == ALWAYS_DARK:
        return DARK
    if sunrise == ALWAYS_LIGHT:
        return LIGHT

    minutes = now_local.hour * 60 + now_local.minute
    return LIGHT if sunrise <= minutes < sunset else DARK


def resolve_mode() -> str:
    """โหมดที่เอาไปใส่ `data-theme` ได้จริง — 'light' หรือ 'dark' เท่านั้น"""
    mode = select_mode()
    if mode != AUTO:
        return mode

    tz_name: str | None = (
        current_user.timezone_name
        if has_request_context() and current_user.is_authenticated
        else None
    )
    return sun_mode(tz_name)
