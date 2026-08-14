"""ตารางของ plugin `auth/ldap` — **เป็นของ plugin ตัวนี้ล้วน ๆ** (ADR 0023)

เก็บแค่คู่ที่ผูก **ตัวระบุของ directory** เข้ากับ `tdl_user.id` ของที่นี่
รูปเดียวกับ `auth/oidc` ทุกอย่างโดยตั้งใจ (ADR 0029 ข้อ 3) — กติกาการผูกบัญชี
เป็นเรื่องของที่นี่ ไม่ใช่ของโพรโทคอล ถ้าสองแหล่งผูกคนละแบบ คำถามว่า
"ผู้ใช้คนนี้มาจากไหนและมีสิทธิ์อะไร" จะมีคำตอบสองชุดที่ต้องเทียบกันทุกครั้ง

**ไม่เก็บรหัสผ่านของ directory** และไม่เก็บ attribute อื่นเลย — สิ่งเดียวที่
ระบบนี้ต้องรู้คือ "ตัวระบุนี้คือผู้ใช้คนไหนของเรา"
"""

from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app import db
from app.db_types import UTCDateTime

# ชั้นของคอลัมน์สำหรับ audit — **plugin ประกาศเอง** (ADR 0023)
# `external_id` เป็น `dn` หรือ uuid ของผู้ใช้ใน directory: ระบุตัวบุคคลได้
# จึงเป็น C2 เท่าชื่อผู้ใช้ (เก็บเป็น HMAC ใน audit ไม่ใช่ค่าจริง)
AUDIT_POLICIES = {
    "directory": "plain",
    "external_id": "hashed",
    "linked_at": "plain",
}

# คำตัดสิน masking บนหน้า admin (ADR 0045) — plugin ประกาศเอง เหตุผลเดียวกับข้างบน
MASKING_DECISIONS = {
    "external_id": "masked",  # C2 — ตัวระบุจาก directory ภายนอก
    "directory": "visible",
    "linked_at": "visible",
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


class DirectoryIdentity(db.Model):  # type: ignore[name-defined]  # ดู pyproject: db.Model เป็น attribute แบบ dynamic
    """บัญชีใน directory หนึ่งเจ้า ผูกกับผู้ใช้หนึ่งคนของที่นี่"""

    __tablename__ = "tdl_auth_ldap_identity"
    __table_args__ = (
        # **คู่ (directory, external_id) ต้องไม่ซ้ำ** — ตัวระบุไม่ซ้ำภายใน
        # directory เดียวกันเท่านั้น ไม่ใช่ทั้งจักรวาล (เหตุผลเดียวกับ
        # `(issuer, subject)` ของ auth/oidc)
        UniqueConstraint(
            "directory", "external_id", name="uq_tdl_auth_ldap_identity_directory_external_id"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tdl_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # URL ของ directory ที่ผูกไว้ — ความยาวระบุเสมอ (MySQL บังคับ)
    # **191 ไม่ใช่ 255** เพราะคอลัมน์นี้อยู่ในดัชนี unique ร่วมกับ `external_id`
    # และ InnoDB จำกัดดัชนีไว้ที่ 3072 ไบต์ ซึ่ง utf8mb4 คิด 4 ไบต์ต่ออักขระ
    # (191+512)×4 = 2812 พอดี ส่วน 255+512 จะเฉียด 3072 จนไม่เหลือที่
    directory: Mapped[str] = mapped_column(String(191), nullable=False)
    # `dn` ยาวได้มากในระบบจริง (OU ซ้อนกันหลายชั้น) จึงเผื่อไว้กว่าตัวอื่น
    external_id: Mapped[str] = mapped_column(String(512), nullable=False)
    linked_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_utcnow, nullable=False)
