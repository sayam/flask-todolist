"""นโยบายรหัสผ่านตาม NIST SP 800-63B (Phase 4 — ดู ADR 0019)

**สิ่งที่ *ไม่* ทำ สำคัญพอ ๆ กับสิ่งที่ทำ** มาตรฐานฉบับนี้เลิกแนะนำของที่เคย
เป็นธรรมเนียมมาก่อน เพราะวัดแล้วว่ามันผลักคนไปหาพฤติกรรมที่แย่กว่าเดิม:

* **ไม่มีกฎ complexity** (ต้องมีตัวใหญ่/ตัวเลข/อักขระพิเศษ) — คนจะได้
  `Password1!` ซึ่งอยู่ในรายการที่หลุดแล้วทุกฉบับ ความยาวได้ผลกว่ามาก
* **ไม่บังคับเปลี่ยนตามรอบ** — บังคับแล้วคนจะเติมเลขต่อท้ายไปเรื่อย ๆ
  เปลี่ยนเมื่อมีเหตุ (สงสัยว่าหลุด) เท่านั้น
* **ไม่ตัดปลายรหัสผ่าน** และรับอักขระทุกตัวรวมช่องว่าง — ตัดทิ้งเงียบ ๆ
  แปลว่าความยาวที่ผู้ใช้ตั้งใจให้ไม่ได้ถูกใช้จริง

สิ่งที่ทำแทน: ความยาวขั้นต่ำ, เพดานความยาว (กันคนยิงคำขอที่ต้อง hash ของ
ขนาดมหาศาล), เทียบกับ **รายการรหัสที่หลุดแล้วแบบ offline**
(`app/password_blocklist.txt` — ดู `scripts/build_password_blocklist.py`)
และกันรหัสที่ประกอบจาก username ของตัวเอง

**ทำไม offline ไม่ใช่ HIBP k-anonymity:** การตั้งรหัสผ่านจะพึ่งบริการภายนอก
ไม่ได้ ถ้าเน็ตล่มแล้วต้อง "ปล่อยผ่านไปก่อน" เท่ากับนโยบายมีผลเฉพาะตอนเน็ตดี
ซึ่งไม่ใช่นโยบาย ส่วนการ fail closed ก็แปลว่าเน็ตล่มแล้วตั้งรหัสไม่ได้เลย
รายการ bundled ตัดสินใจได้เองเสมอและตอบเร็วเท่ากันทุกครั้ง

**การ normalize อยู่ที่ `User.set_password`/`check_password` ไม่ใช่ที่นี่**
เพื่อไม่ให้มีทางลืมเรียก: ถ้า normalize เฉพาะตอนตั้งรหัสแล้วตอน login
ไม่ normalize คนที่ใช้อักขระ unicode จะ login ไม่ได้ทั้งที่พิมพ์เหมือนเดิมเป๊ะ
"""

import pathlib
import unicodedata
from typing import TYPE_CHECKING

from flask_babel import gettext as _

from app import db
from app.services.errors import ValidationError

if TYPE_CHECKING:  # pragma: no cover — ตัดวงจร import: models เรียก normalize() ตัวนี้
    from app.models import User

# NIST SP 800-63B: verifier ต้องรับความยาวอย่างน้อย 8 (SHALL)
MIN_LENGTH = 8
# และต้องรับได้อย่างน้อย 64 (SHALL) — ตั้งเพดานสูงกว่านั้นไว้เพื่อกันคนส่ง
# ข้อความขนาดเมกะไบต์มาให้ scrypt ทำงาน ไม่ใช่เพื่อจำกัดคนที่ใช้ passphrase
MAX_LENGTH = 128

# username ที่สั้นกว่านี้ห้ามเอาไปเทียบแบบ substring — "abc" จะไปโดนรหัสผ่านดี ๆ
# ที่บังเอิญมีสามตัวนี้เรียงกัน ซึ่งเป็นการปฏิเสธที่อธิบายกับผู้ใช้ไม่ได้
MIN_USERNAME_MATCH = 3

BLOCKLIST_PATH = pathlib.Path(__file__).resolve().parent.parent / "password_blocklist.txt"

# อ่านจากดิสก์ครั้งเดียวต่ออายุ process — ไฟล์เป็นของที่ deploy มาพร้อมโค้ด
# ไม่ใช่ของที่แก้ระหว่างรัน (ต่างจาก plugin ที่ตั้งใจให้เห็นผลทันที)
_blocklist_cache: frozenset[str] | None = None


def normalize(password: str) -> str:
    """รูปแบบมาตรฐานของรหัสผ่านหนึ่งตัว — ใช้ทั้งตอนตั้ง ตอนตรวจ และตอนเทียบ blocklist

    NFKC ตามที่ NIST กำหนด: อักขระที่หน้าตาเหมือนกันแต่เข้ารหัสคนละแบบ
    (เช่น ตัวเต็มความกว้างกับตัวปกติ) ต้องนับเป็นรหัสผ่านเดียวกัน ไม่งั้นผู้ใช้
    ที่เปลี่ยน input method แล้ว login ไม่ได้จะหาสาเหตุไม่เจอเลย

    casefold ใช้เฉพาะตอนเทียบ blocklist **ไม่ใช่ตอนเก็บ** — รหัสผ่านยัง
    case-sensitive อยู่ ตัวนี้แค่ทำให้ `PASSWORD123` ถูกจับได้เหมือน `password123`
    """
    return unicodedata.normalize("NFKC", password)


def blocklist_key(password: str) -> str:
    """รูปแบบที่ใช้เทียบกับ blocklist — ทั้งตอน generate ไฟล์และตอนตรวจต้องใช้ตัวนี้

    แยกจาก `normalize()` เพราะ casefold ห้ามมีผลกับค่าที่เอาไปเก็บ
    (รหัสผ่านยัง case-sensitive) มีผลเฉพาะตอนเทียบว่าอยู่ในรายการที่หลุดไหม
    """
    return normalize(password).casefold()


def blocklist() -> frozenset[str]:
    """รหัสที่หลุดแล้วทั้งหมด (normalize + casefold มาแล้วจากตอน generate)"""
    global _blocklist_cache  # noqa: PLW0603  cache ระดับ process ตั้งใจให้ใช้ร่วมกันทุก request
    if _blocklist_cache is None:
        lines = BLOCKLIST_PATH.read_text(encoding="utf-8").splitlines()
        _blocklist_cache = frozenset(line for line in lines if line and not line.startswith("#"))
    return _blocklist_cache


def is_breached(password: str) -> bool:
    """เคยโผล่ในข้อมูลที่หลุดแล้วไหม — เทียบแบบไม่สนตัวพิมพ์ใหญ่เล็ก

    การเทียบเป็นแบบตรงตัวเท่านั้น ไม่ได้ลองแปลง leetspeak หรือถอดเลขท้ายออก
    (`p@ssw0rd1` ที่ไม่อยู่ในรายการจะผ่าน) — รายการที่หลุดจริงมีตัวแปลงพวกนั้น
    อยู่ในตัวมันเองแล้วเป็นล้านตัว การเดาเพิ่มเองมีแต่จะปฏิเสธรหัสที่ยังปลอดภัย
    """
    return blocklist_key(password) in blocklist()


def validate(password: str, *, username: str | None = None) -> str:
    """ตรวจรหัสผ่านตามนโยบาย คืนค่าที่ normalize แล้ว — ไม่ผ่านให้ `ValidationError`

    ไม่แตะฐานข้อมูลเลย เรียกได้ทั้งจาก CLI ตอนสร้างผู้ใช้และจาก service
    ตอนเปลี่ยนรหัส ลำดับการตรวจไล่จากถูกที่สุดไปแพงที่สุด
    """
    candidate = normalize(password)

    if len(candidate) < MIN_LENGTH:
        raise ValidationError(
            _("Password must be at least %(count)d characters long", count=MIN_LENGTH),
            code="password_too_short",
            field="password",
        )
    if len(candidate) > MAX_LENGTH:
        raise ValidationError(
            _("Password must be at most %(count)d characters long", count=MAX_LENGTH),
            code="password_too_long",
            field="password",
        )
    if (
        username
        and len(username) >= MIN_USERNAME_MATCH
        and username.casefold() in candidate.casefold()
    ):
        raise ValidationError(
            _("Password must not contain your username"),
            code="password_has_username",
            field="password",
        )
    if is_breached(candidate):
        raise ValidationError(
            _("This password has appeared in a data breach — choose a different one"),
            code="password_breached",
            field="password",
        )
    return candidate


def set_password(user: "User", new_password: str) -> "User":
    """ตั้งรหัสใหม่ให้ผู้ใช้โดยไม่ถามรหัสเดิม — ทางของผู้ดูแลระบบ (CLI) เท่านั้น

    ฝั่งเว็บต้องใช้ `change_password()` ที่ขอรหัสเดิมด้วยเสมอ ไม่งั้น session
    ที่ถูกขโมยไปจะเปลี่ยนรหัสเจ้าของบัญชีทิ้งได้ทันที
    """
    from app import audit

    validated = validate(new_password, username=user.username)
    user.set_password(validated)
    # ชื่อเหตุการณ์ตามความหมาย — แถว `user.update` ที่ hook เขียนให้อัตโนมัติบอกได้
    # แค่ว่า "คอลัมน์ password_hash เปลี่ยน" (ชั้น C1 บันทึกค่าไม่ได้) ซึ่งหาไม่เจอ
    # เวลาไล่หาว่าใครเปลี่ยนรหัสใครเมื่อไหร่
    audit.record("auth.password_reset", table_name="tdl_user", row_id=user.id)
    db.session.commit()
    return user


def change_password(user: "User", *, current_password: str, new_password: str) -> "User":
    """เปลี่ยนรหัสของตัวเอง — ต้องยืนยันรหัสเดิมก่อนเสมอ

    รหัสเดิมผิดตอบ `ValidationError` ไม่ใช่ `NotFoundError` เพราะคนที่ถามคือ
    เจ้าของบัญชีที่ login อยู่แล้ว ไม่มีอะไรให้ปกปิดว่ามีบัญชีนี้อยู่จริงไหม
    """
    from app import audit

    if not user.check_password(current_password):
        # บันทึกความพยายามที่ล้มเหลวด้วย — เป็นสัญญาณของ session ที่ถูกยึด
        audit.record("auth.password_failed", table_name="tdl_user", row_id=user.id)
        db.session.commit()
        raise ValidationError(
            _("Current password is incorrect"),
            code="password_incorrect",
            field="current_password",
        )

    validated = validate(new_password, username=user.username)
    user.set_password(validated)
    audit.record("auth.password_change", table_name="tdl_user", row_id=user.id)
    db.session.commit()
    return user
