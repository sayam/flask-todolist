"""โปรไฟล์และค่าที่ผู้ใช้ตั้งไว้ (ภาษา ธีม โหมด timezone)

**`session` ไม่ได้อยู่ในนี้โดยตั้งใจ** — service เขียนลงโปรไฟล์อย่างเดียว
ส่วนการอัปเดต session เป็นงานของ adapter ฝั่งเว็บ เพราะ session ชนะโปรไฟล์
ในลำดับการเลือกภาษา/ธีม (ดู `app/i18n.py`, `app/theme.py`) และ API ที่ยืนยัน
ตัวตนด้วย token ไม่มี session ให้อัปเดตตั้งแต่แรก

username แก้ไม่ได้ที่นี่ เพราะเป็นตัวระบุตอน login (ช่องบนหน้าเว็บก็ disabled ไว้)
"""

from flask_babel import gettext as _

from app import db, tz
from app.i18n import is_supported as locale_is_supported
from app.models import User
from app.services.errors import ValidationError
from app.theme import mode_is_supported, theme_is_supported


def save_profile(user: User, first_name: str | None, last_name: str | None) -> User:
    """บันทึกชื่อ-นามสกุล — ช่องที่เว้นว่างเก็บเป็น NULL ไม่ใช่สตริงว่าง

    ไม่งั้น `full_name` จะได้ช่องว่างเกินมาเวลาเอาสองช่องมาต่อกัน
    """
    user.first_name = (first_name or "").strip() or None
    user.last_name = (last_name or "").strip() or None
    db.session.commit()
    return user


def save_locale(user: User, locale: str | None) -> User:
    """บันทึกภาษาที่เพิ่งกดสลับลงโปรไฟล์ — การกดสลับคือความตั้งใจล่าสุดของผู้ใช้"""
    if not locale_is_supported(locale):
        raise ValidationError(_("Unsupported language"), code="locale_invalid", field="locale")
    user.locale = locale
    db.session.commit()
    return user


def save_mode(user: User, mode: str | None) -> User:
    """บันทึกโหมดสว่าง/มืดที่เพิ่งกดสลับลงโปรไฟล์

    `auto` เก็บเป็นสตริง `'auto'` ไม่ใช่ NULL — มันเป็นตัวเลือกจริงที่ผู้ใช้ตั้งใจเลือก
    ต่างจาก `locale`/`timezone_name` ที่ NULL แปลว่ายังไม่เคยเลือก
    """
    if not mode_is_supported(mode):
        raise ValidationError(_("Unsupported mode"), code="mode_invalid", field="mode")
    user.mode = mode
    db.session.commit()
    return user


def save_preferences(
    user: User,
    *,
    locale: str | None,
    theme: str | None,
    mode: str | None,
    timezone_name: str | None,
) -> User:
    """บันทึกค่าที่ผู้ใช้ตั้งไว้ทั้งชุด — ค่าไหนไม่รองรับก็ไม่บันทึกอะไรเลยสักตัว

    ตรวจให้ครบก่อนเขียน เพื่อไม่ให้เหลือสถานะครึ่ง ๆ กลาง ๆ ที่ภาษาถูกบันทึกแล้ว
    แต่ธีมไม่ถูกบันทึกเพราะค่าถัดไปไม่ผ่าน
    """
    if not locale_is_supported(locale):
        raise ValidationError(_("Unsupported language"), code="locale_invalid", field="locale")
    if not theme_is_supported(theme):
        raise ValidationError(_("Unsupported theme"), code="theme_invalid", field="theme")
    if not mode_is_supported(mode):
        raise ValidationError(_("Unsupported mode"), code="mode_invalid", field="mode")
    if not tz.is_supported(timezone_name):
        raise ValidationError(_("Unsupported timezone"), code="timezone_invalid", field="timezone")

    user.locale = locale
    user.theme = theme
    user.mode = mode
    user.timezone_name = timezone_name
    db.session.commit()
    return user
