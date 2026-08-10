"""ตารางของ plugin `auth/oidc` — **เป็นของ plugin ตัวนี้ล้วน ๆ** (ADR 0023)

เก็บแค่ **คู่ที่ผูก `(issuer, sub)` ของ IdP เข้ากับ `tdl_user.id` ของที่นี่**
ไม่เก็บชื่อ ไม่เก็บอีเมล ไม่เก็บ token ใด ๆ (ADR 0028 ข้อ 1) — ทุกอย่างที่แอป
ใช้ตัดสินใจยังอยู่ในตารางของ core ตัวเดิม

ผลที่ตั้งใจ: **ถอน plugin = ตารางผูกหายไป ผู้ใช้ยังอยู่ครบ** กลับไป login
ด้วยรหัสผ่านซึ่งผู้ดูแลตั้งให้ใหม่ได้ด้วย `flask set-password`

ไม่ใช้ `SoftDeleteMixin` ด้วยเหตุผลเดียวกับ `auth/totp`: การยกเลิกการผูกบัญชี
ต้องเป็นการลบจริง ไม่ใช่ซ่อนไว้ 30 วัน (แถวที่ซ่อนอยู่ยังกันไม่ให้ `sub` เดิม
ไปผูกกับคนใหม่ได้ ซึ่งไม่ใช่สิ่งที่คนสั่งยกเลิกตั้งใจ) และ purge job ของ core
ไม่รู้จักตารางนี้อยู่แล้ว
"""

from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app import db
from app.db_types import UTCDateTime

# ชั้นของคอลัมน์สำหรับ audit — **plugin ประกาศเอง** (ADR 0023)
# `issuer` กับ `subject` เป็นตัวระบุบุคคลจาก IdP: ไม่ใช่ความลับ แต่ไม่ใช่ของ
# สาธารณะ จึงเก็บเป็น HMAC ไม่ใช่ค่าดิบ (ดู docs/DATA-CLASSIFICATION.md)
AUDIT_POLICIES = {
    "issuer": "plain",
    "subject": "hashed",
    "linked_at": "plain",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


class OidcIdentity(db.Model):  # type: ignore[name-defined]  # ดู pyproject: db.Model เป็น attribute แบบ dynamic
    """บัญชีที่ IdP หนึ่งเจ้ารู้จัก ผูกกับผู้ใช้หนึ่งคนของที่นี่"""

    __tablename__ = "tdl_auth_oidc_identity"
    __table_args__ = (
        # **คู่ (issuer, subject) ต้องไม่ซ้ำ** — `sub` รับประกันว่าไม่ซ้ำ
        # *ภายใน issuer เดียวกัน* เท่านั้น ไม่ใช่ทั้งจักรวาล การไม่ใส่ issuer
        # ลงในกุญแจแปลว่าวันที่มี IdP เจ้าที่สอง ผู้ใช้ของเจ้านั้นอาจสวมรอย
        # เป็นผู้ใช้ของเจ้าแรกได้ด้วย `sub` ที่บังเอิญตรงกัน
        UniqueConstraint("issuer", "subject", name="uq_tdl_auth_oidc_identity_issuer_subject"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tdl_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # ความยาวระบุเสมอ (MySQL บังคับ) — URL ของ issuer ยาวได้ตามสมควร
    issuer: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    linked_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_utcnow, nullable=False)
