"""ชื่อผู้ใช้ที่ชนกันแบบ casefold — ตรวจที่จุดเดียว ใช้ได้ทุกทางเข้า

**ระบบตัดสินชื่อผู้ใช้สองมาตรฐาน** (audit รอบ 19 ข้อ 2):

- *ตัวตน* เทียบตรงตัวพิมพ์ — `app/auth.py` ใช้ `User.username == username`
- *โควตากันเดารหัสผ่าน* เทียบแบบ casefold — `app/auth.py::_username_key()`
  ทำแบบนั้นโดยตั้งใจตาม ADR 0021 ("คนยิงแค่สลับตัวพิมพ์ก็ได้โควตาใหม่ทั้งชุด")

สองข้อนี้ถูกทั้งคู่ในตัวเอง · ที่ผิดคือระบบยอมให้มี `alice` กับ `Alice` อยู่พร้อมกัน
ตั้งแต่แรก — วัดจริงในรอบ 19: `flask create-user Alice` สำเร็จทั้งที่มี `alice` แล้ว
ผลที่ตามมาคือ **คนนอกยิงรหัสผิดใส่ `Alice` ห้าครั้ง แล้ว `alice` เข้าระบบไม่ได้**
ซึ่งเป็นการปฏิเสธบริการข้ามบัญชีโดยไม่ต้องรู้อะไรเกี่ยวกับเป้าเลย

**และมันเกิดได้บนยี่ห้อเดียว** (เจอตอน job `dialects` แดงใน PR ของข้อนี้เอง):
MySQL/MariaDB เทียบ unique index ด้วย collation ที่ไม่สนตัวพิมพ์ ฐานจึงปฏิเสธ
`Alice` ให้ตั้งแต่แรกด้วย `Duplicate entry` · SQLite ใช้ BINARY จึงยอมรับ —
และ SQLite คือค่าเริ่มต้นของ dev · **กฎเดียวกันถูกบังคับด้วยฐานสองยี่ห้อ และ
ไม่ถูกบังคับเลยบนยี่ห้อที่สาม** ตัวตรวจในไฟล์นี้จึงทำให้พฤติกรรมเท่ากันทุกยี่ห้อ
โดยไม่ต้องพึ่ง collation ของใคร

ทางแก้คือกันที่ *การสร้าง* ไม่ใช่เปลี่ยนวิธีเทียบตัวตน — การทำให้ login ไม่สนตัวพิมพ์
เปลี่ยนความหมายของบัญชีที่มีอยู่แล้วทุกใบ ส่วนการห้ามชื่อที่ชนกันไม่เปลี่ยนอะไรเลย
กับของเดิมที่ไม่ได้ชนกัน
"""

from __future__ import annotations

from flask_babel import gettext as _
from sqlalchemy import select

from app import db
from app.models import User
from app.services.errors import ConflictError


def normalize(username: str) -> str:
    """รูปที่ใช้เทียบว่า "ชนกันไหม" — ต้องเป็นรูปเดียวกับที่ ADR 0021 ใช้ทำกุญแจโควตา"""
    return username.strip().casefold()


def taken_by(username: str) -> User | None:
    """ผู้ใช้ที่ชื่อชนกับชื่อนี้แบบ casefold (ถ้ามี) — คนที่ถูก soft delete ถูกกรองออกให้เอง

    **อ่านทั้งคอลัมน์มาเทียบใน python โดยตั้งใจ** — `LOWER()` ของแต่ละยี่ห้อ
    ตัดสิน Unicode ไม่เหมือนกัน (และไม่เหมือน `str.casefold` ของ python)
    ระบบนี้จึงต้องใช้ตัวตัดสินตัวเดียวกับที่ทำกุญแจโควตา ไม่ใช่ตัวที่ฐานข้อมูลมีให้
    · ระดับการใช้งานของโปรเจกต์นี้คือหลักสิบบัญชี ราคาจึงไม่ใช่ประเด็น
    """
    wanted = normalize(username)
    for user in db.session.scalars(select(User)):
        if normalize(user.username) == wanted:
            return user
    return None


def require_available(username: str) -> None:
    """ชื่อนี้ต้องยังว่างอยู่ — ไม่งั้น `ConflictError` พร้อมบอกว่าชนกับใคร"""
    clash = taken_by(username)
    if clash is None:
        return
    if clash.username == username.strip():
        raise ConflictError(
            _("A user named %(name)s already exists.", name=clash.username),
            code="username_taken",
        )
    raise ConflictError(
        _(
            "The name %(wanted)s clashes with the existing user %(existing)s — "
            "they differ only in case, and the login rate limit counts them as one account.",
            wanted=username.strip(),
            existing=clash.username,
        ),
        code="username_collides",
    )


def collisions() -> list[list[str]]:
    """กลุ่มชื่อที่ชนกันอยู่แล้วในฐาน — ว่าง = สะอาด

    มีไว้ให้ตัวตรวจสุขภาพข้อมูลเรียก · ของที่ชนกันก่อนกฎข้อนี้เกิด ต้องมีคนบอก
    ไม่ใช่รอให้เจอตอนมีคนล็อกอินไม่ได้
    """
    seen: dict[str, list[str]] = {}
    for user in db.session.scalars(select(User)):
        seen.setdefault(normalize(user.username), []).append(user.username)
    return [sorted(names) for names in seen.values() if len(names) > 1]
