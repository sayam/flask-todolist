"""การเลือกธีมของแต่ละ request

ลำดับเดียวกับภาษา (ดู `app/i18n.py`):
`?theme=` → session → `User.theme` → ตามระบบ

ค่าที่เป็นไปได้คือ 'light', 'dark' และ AUTO
AUTO ไม่ใส่ `data-theme` ลง `<html>` เลย ปล่อยให้ CSS `prefers-color-scheme`
ตัดสินตามค่าที่ OS ตั้งไว้ — จึงเป็นค่าเริ่มต้นที่ถูกต้องกว่าการบังคับ light
"""

from flask import has_request_context, request, session
from flask_login import current_user

SESSION_KEY = "theme"
AUTO = "auto"
THEMES = ("light", "dark")
CHOICES = (AUTO,) + THEMES


def is_supported(value):
    return value in CHOICES


def select_theme():
    """คืนค่าที่ผู้ใช้เลือก — AUTO แปลว่าไม่บังคับ ให้ CSS ตัดสินเอง"""
    if not has_request_context():
        return AUTO

    if is_supported(request.args.get(SESSION_KEY)):
        return request.args[SESSION_KEY]

    if is_supported(session.get(SESSION_KEY)):
        return session[SESSION_KEY]

    if current_user.is_authenticated and current_user.theme in THEMES:
        return current_user.theme

    return AUTO
