"""TOTP (RFC 6238) — ปัจจัยที่สองของการยืนยันตัวตน (Phase 4 — ดู ADR 0024)

**เขียนเองไม่ใช้ไลบรารี** ด้วยเหตุผลเดียวกับตารางดวงอาทิตย์ (ADR 0007):
อัลกอริทึมทั้งหมดคือ HMAC-SHA1 + การตัดตัวเลขตามสูตรใน RFC ซึ่งสั้นกว่าโค้ด
ที่ต้องเขียนเพื่อห่อไลบรารีเสียอีก และมี **test vector อย่างเป็นทางการ**
ใน RFC 6238 ให้ยืนยันความถูกต้องได้ตรง ๆ (อยู่ใน `tests/test_totp.py`)
ส่วน dependency ที่เพิ่มมาต้องตามดู CVE ไปตลอดอายุโครงการ

สัญญาที่ core เรียก (ทุก plugin ชนิด `auth` ที่เป็น `"factor": "second"`
ต้องมีครบ — `plugins.check_installation()` ตรวจตอน start):

* `is_enrolled(user)` — เปิดใช้ปัจจัยนี้อยู่ไหม
* `verify(user, code)` — รหัสนี้ใช้ได้ไหม (และ "ใช้ไปแล้ว" หลังจากนี้)

core **ไม่รู้จักชื่อ `totp`** เลย มันรู้แค่ว่ามี plugin ชนิด auth ที่เป็น
ปัจจัยที่สองอยู่กี่ตัว แล้วถามทีละตัว
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

from app import db

from .models import TotpSecret

# ค่ามาตรฐานที่แอป authenticator ทุกตัวใช้ — เปลี่ยนแล้วรหัสจะไม่ตรงกับเครื่องผู้ใช้
DIGITS = 6
PERIOD = 30
# ยอมรับรหัสของช่วงก่อนหน้าและถัดไปอย่างละหนึ่งช่วง เพราะนาฬิกาของโทรศัพท์
# ไม่เคยตรงกับ server เป๊ะ ๆ — กว้างกว่านี้คือการเพิ่มพื้นที่ให้คนเดารหัส
WINDOW = 1
# 20 ไบต์ = 160 บิต ตามที่ RFC 4226 กำหนดเป็นอย่างต่ำสำหรับความลับ HOTP/TOTP
SECRET_BYTES = 20

ISSUER = "Todolist"


def new_secret() -> str:
    """ความลับใหม่ในรูป base32 (ไม่มี padding — แอป authenticator ไม่รับ `=`)"""
    return base64.b32encode(secrets.token_bytes(SECRET_BYTES)).decode("ascii").rstrip("=")


def _counter(at: float) -> int:
    return int(at // PERIOD)


def code_at(secret: str, counter: int) -> str:
    """รหัสของช่วงเวลาที่ระบุ — สูตรตรงตาม RFC 4226 ข้อ 5.3 (dynamic truncation)"""
    # base32 ที่ตัด padding ออกแล้วต้องเติมกลับก่อน decode
    padded = secret.upper() + "=" * (-len(secret) % 8)
    key = base64.b32decode(padded, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    chunk = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(chunk % (10**DIGITS)).zfill(DIGITS)


def matching_counter(secret: str, code: str, at: float | None = None) -> int | None:
    """ช่วงเวลาที่รหัสนี้ตรง — ไม่ตรงเลยคืน None

    เทียบด้วย `compare_digest` ทุกช่วง **และไม่ break ทันทีที่เจอ** เพื่อให้
    เวลาที่ใช้ไม่ขึ้นกับว่าตรงที่ช่วงไหน (ซึ่งบอกใบ้เรื่องนาฬิกาของ server ได้)
    """
    now = time.time() if at is None else at
    current = _counter(now)
    found = None
    for offset in range(-WINDOW, WINDOW + 1):
        counter = current + offset
        if hmac.compare_digest(code_at(secret, counter), code.strip()):
            found = counter
    return found


def provisioning_uri(secret: str, username: str) -> str:
    """`otpauth://` ที่แอป authenticator สแกนหรือวางเข้าไปได้

    ไม่มี QR code ให้สแกนโดยตั้งใจ — การสร้างรูปต้องพึ่งไลบรารีวาดภาพ และ
    CSP ของเรา (`img-src 'self'`) ก็ต้องเปิดทางให้ data URI เพิ่ม
    ผู้ใช้กดคัดลอกข้อความนี้ไปวางในแอปได้เหมือนกัน (ทุกแอปรองรับ)
    """
    label = quote(f"{ISSUER}:{username}", safe="")
    return (
        f"otpauth://totp/{label}?secret={secret}&issuer={quote(ISSUER)}"
        f"&algorithm=SHA1&digits={DIGITS}&period={PERIOD}"
    )


# ---------------------------------------------------------------- สถานะของผู้ใช้


def _utc_naive() -> datetime:
    """UTC แบบ naive เหมือนเวลาทุกตัวในระบบ (ADR 0002)"""
    return datetime.now(UTC).replace(tzinfo=None)


def _row(user: Any) -> TotpSecret | None:
    return db.session.query(TotpSecret).filter_by(user_id=user.id).one_or_none()


def is_enrolled(user: Any) -> bool:
    """เปิดใช้ TOTP แล้วจริง ๆ — ใบที่ยังไม่ยืนยันไม่นับ (ดู models.py)"""
    row = _row(user)
    return row is not None and row.confirmed_at is not None


def is_pending(user: Any) -> bool:
    """ออกความลับให้แล้วแต่ยังไม่ได้ยืนยันด้วยรหัสจริง"""
    row = _row(user)
    return row is not None and row.confirmed_at is None


def secret_of(user: Any) -> str | None:
    """ความลับของผู้ใช้ — **ใช้ตอนแสดงให้เจ้าตัวดูระหว่างลงทะเบียนเท่านั้น**"""
    row = _row(user)
    return row.totp_secret if row else None


def setup_details(user: Any) -> list[tuple[str, str]]:
    """สิ่งที่ต้องแสดงระหว่างลงทะเบียน — core เอาไปวางเป็นคู่ (ป้าย, ค่า) ตรง ๆ

    ป้ายเป็นภาษาอังกฤษตายตัวไม่ผ่าน gettext เหมือน `Plugin.name`
    (plugin ที่อยากแปลต้องมี lang pack ของตัวเอง — ดู app/plugins/__init__.py)

    **แสดงเฉพาะใบที่ยังไม่ยืนยัน** ใบที่เปิดใช้แล้วต้องไม่มีทางดูความลับซ้ำได้
    ไม่งั้น session ที่ถูกยึดจะก๊อปความลับไปใส่เครื่องตัวเองได้เงียบ ๆ
    """
    row = _row(user)
    if row is None or row.confirmed_at is not None:
        return []
    return [
        ("Secret key", row.totp_secret),
        ("Setup link", provisioning_uri(row.totp_secret, user.username)),
    ]


def start_enrollment(user: Any) -> str:
    """ออกความลับใบใหม่ (ทับใบเก่าที่ยังไม่ยืนยัน) คืนค่า base32 ให้เอาไปแสดง

    ใบที่ **ยืนยันแล้ว** ถูกทับไม่ได้ — ต้องปิด MFA ก่อน ซึ่งต้องกรอกรหัสผ่าน
    (ไม่งั้น session ที่ถูกยึดจะออกใบใหม่ให้ตัวเองแล้วยึดบัญชีถาวร)
    """
    row = _row(user)
    if row is not None and row.confirmed_at is not None:
        raise ValueError("มี TOTP ที่ยืนยันแล้วอยู่ ต้องปิดก่อนถึงจะออกใบใหม่ได้")

    secret = new_secret()
    if row is None:
        row = TotpSecret(user_id=user.id, totp_secret=secret)
        db.session.add(row)
    else:
        row.totp_secret = secret
        row.last_counter = None
    db.session.commit()
    return secret


def confirm(user: Any, code: str, at: float | None = None) -> bool:
    """ยืนยันการลงทะเบียนด้วยรหัสจริงหนึ่งครั้ง — ผ่านแล้วถือว่าเปิด MFA

    **ใบที่ยืนยันไปแล้วยืนยันซ้ำไม่ได้** เพราะทางนี้ไม่ได้เช็คการใช้รหัสซ้ำ
    (ต่างจาก `verify()`) — ยิงรหัสของช่วงที่ผ่านมาเข้ามาซ้ำจะ **ถอย
    `last_counter` กลับไปข้างหลัง** แล้วเปิดช่องให้รหัสที่ใช้ไปแล้วในช่วงระหว่างนั้น
    กลับมาใช้ได้อีก ต้องปิดแล้วเปิดใหม่เท่านั้น (ซึ่งต้องกรอกรหัสผ่าน)
    """
    row = _row(user)
    if row is None or row.confirmed_at is not None:
        return False
    counter = matching_counter(row.totp_secret, code, at)
    if counter is None:
        return False
    row.confirmed_at = _utc_naive()
    row.last_counter = counter
    db.session.commit()
    return True


def verify(user: Any, code: str, at: float | None = None) -> bool:
    """ตรวจรหัสตอน login — **รหัสที่ใช้ไปแล้วใช้ซ้ำไม่ได้**

    ถ้าไม่กันการใช้ซ้ำ คนที่แอบเห็นรหัสบนจอ (หรือดักจาก log ของ proxy) เอาไป
    ใช้ได้อีกจนกว่าจะครบ 30 วินาที ซึ่งนานพอสำหรับการยิงจากที่อื่น
    """
    row = _row(user)
    if row is None or row.confirmed_at is None:
        return False
    counter = matching_counter(row.totp_secret, code, at)
    if counter is None:
        return False
    if row.last_counter is not None and counter <= row.last_counter:
        return False
    row.last_counter = counter
    db.session.commit()
    return True


def disable(user: Any) -> bool:
    """ปิด MFA — **ลบความลับทิ้งจริง** ไม่ใช่ซ่อน (ชั้น C1 ดู models.py)"""
    row = _row(user)
    if row is None:
        return False
    # ลบจริง — ได้รับการยกเว้นไว้ใน ALLOWED_LINES ของ tests/test_write_discipline.py
    db.session.delete(row)
    db.session.commit()
    return True
