"""ตารางของ plugin `auth/totp` — **เป็นของ plugin ตัวนี้ล้วน ๆ** (ADR 0023)

ชื่อตารางต้องขึ้นต้นด้วย `tdl_auth_totp_` (registry บังคับตอนโหลด) และตารางนี้
**ไม่อยู่ในสาย migration ของ core** — เกิดตอน `flask plugin-install auth/totp`
และหายไปตอน `flask plugin-uninstall auth/totp`

ไม่ใช้ `SoftDeleteMixin` โดยตั้งใจ: ความลับ TOTP เป็นชั้น C1 เหมือนรหัสผ่าน
"ปิด MFA" จึงแปลว่าลบความลับทิ้งจริง ๆ ไม่ใช่ซ่อนไว้ 30 วัน (หลักเดียวกับ
`ApiToken.disable()` ที่ล้าง hash ทันทีตอนเพิกถอน) — และ purge job ของ core
ไม่รู้จักตารางนี้อยู่แล้ว ถ้าซ่อนไว้ก็จะไม่มีใครมาล้างให้เลย
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import ForeignKey, Integer, String, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column

from app import db
from app.db_types import UTCDateTime


class EncryptedSecret(TypeDecorator):
    """คอลัมน์ความลับที่ encrypt ที่ระดับ field (ADR 0046)

    เขียน = encrypt เสมอ (idempotent — ค่า ``enc:v1:`` อยู่แล้วผ่านตรง) ·
    อ่าน = ถอดถ้าเป็นรูป encrypt, ค่า legacy (plaintext ก่อนเฟส 15) ผ่านตรง
    แล้วรอ encrypt-on-use ตอน verify สำเร็จครั้งถัดไป — ดู `crypto.py`

    import ของ crypto เป็น lazy ในเมธอด: ไฟล์นี้ต้องโหลดได้เสมอแม้ไม่มี
    ไลบรารี (job `bare` โหลด models ทุก plugin ผ่าน registry)
    """

    impl = String(256)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:  # noqa: ARG002 - required by interface
        """ทุกค่าที่ลงดิสก์ต้องเป็น ciphertext — นี่คือใจของ at rest"""
        if value is None:
            return None
        # absolute import ถึงตัวเอง — registry โหลดไฟล์นี้ใต้ชื่อสังเคราะห์
        # (app.plugins.auth_totp.models) ซึ่งไม่มี parent package ให้ `from .`
        # ใช้ · absolute ปลอดภัยที่นี่เพราะ crypto ไม่มี model (กับดัก
        # "Table already defined" เกิดกับไฟล์ที่นิยามตารางเท่านั้น)
        from app.plugins.auth.totp import crypto

        return value if crypto.is_encrypted(value) else crypto.encrypt(str(value))

    def process_result_value(self, value: Any, dialect: Any) -> Any:  # noqa: ARG002 - required by interface
        """ค่า legacy อ่านผ่านตรง — การปฏิเสธของเก่าคือการ lock ผู้ใช้ MFA ทุกคน"""
        if value is None:
            return None
        from app.plugins.auth.totp import crypto

        return crypto.decrypt(str(value))


# ชั้นของคอลัมน์ของเราเองสำหรับ audit — **plugin ประกาศเอง core ไม่รู้จักชื่อพวกนี้**
# (ดู ADR 0023: ชื่อคอลัมน์ของ plugin ที่ไปเขียนไว้ในโค้ด core จะกลายเป็นขยะ
#  ค้างอยู่ที่นั่นทันทีที่มีคนถอน plugin ทิ้ง)
# ค่า: "secret" = บันทึกได้แค่ว่าเปลี่ยน / "plain" = เก็บค่าจริง / "hashed" = HMAC
AUDIT_POLICIES = {
    "totp_secret": "secret",
    "confirmed_at": "plain",
    "last_counter": "plain",
}

# คำตัดสิน masking บนหน้า admin (ADR 0045) — plugin ประกาศเอง เหตุผลเดียวกับข้างบน
MASKING_DECISIONS = {
    "totp_secret": "hidden",  # C1 — ไม่มีงานบริหารไหนต้องเห็น
    "confirmed_at": "visible",
    "last_counter": "visible",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


class TotpSecret(db.Model):  # type: ignore[name-defined]  # ดู pyproject: db.Model เป็น attribute แบบ dynamic
    """ความลับ TOTP ของผู้ใช้หนึ่งคน (คนละหนึ่งใบเท่านั้น)"""

    __tablename__ = "tdl_auth_totp_secret"

    id: Mapped[int] = mapped_column(primary_key=True)
    # หนึ่งคนหนึ่งใบ — unique ที่ระดับ DB ไม่ใช่แค่เช็คในโค้ด
    user_id: Mapped[int] = mapped_column(ForeignKey("tdl_user.id"), unique=True, index=True)
    # base32 ตามที่แอป authenticator ทุกตัวคาดหวัง — **ชั้น C1 · encrypt at rest
    # (ADR 0046)**: บนดิสก์เป็น ``enc:v1:...`` เสมอสำหรับแถวใหม่ · แถว legacy
    # ถูก encrypt ตอน verify สำเร็จครั้งถัดไป (ตารางนี้อยู่นอกสาย alembic)
    totp_secret: Mapped[str] = mapped_column(EncryptedSecret)
    created_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=_utcnow)
    # ค่าว่างแปลว่าออกความลับให้แล้วแต่ยังไม่ได้ยืนยันด้วยรหัสจริงสักครั้ง
    # ใบที่ยังไม่ยืนยัน **ไม่ถูกนับว่าเปิด MFA** ไม่งั้นคนที่สแกน QR ไม่ทันจะ
    # ล็อกตัวเองออกจากบัญชีทันทีที่กดเปิด
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    # ช่วงเวลาล่าสุดที่ใช้รหัสไปแล้ว — กันเอารหัสเดิมมาใช้ซ้ำภายในช่วงเดียวกัน
    last_counter: Mapped[int | None] = mapped_column(Integer, default=None)

    def __repr__(self) -> str:
        return f"<TotpSecret user={self.user_id} confirmed={self.confirmed_at is not None}>"
