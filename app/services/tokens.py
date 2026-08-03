"""personal access token (PAT) — กุญแจของเครื่อง ไม่ใช่ของคน (ADR 0017)

รูปแบบของ token ที่ผู้ใช้ได้ไป: `tdl_<id>_<ความลับ>`
ส่วน `<id>` มีไว้ให้หาแถวได้ตรง ๆ โดยไม่ต้องไล่เทียบ hash ทั้งตาราง
ส่วน `<ความลับ>` เป็น `secrets.token_urlsafe(32)` = สุ่ม 256 บิต

**เก็บลงฐานข้อมูลเป็น sha256 ของความลับ ไม่ใช่ scrypt** ต่างจากรหัสผ่านโดยตั้งใจ
เพราะเหตุผลของ scrypt คือ "รหัสผ่านที่คนตั้งเองมีเอนโทรปีต่ำ ต้องทำให้การไล่เดา
แพง" ซึ่งใช้กับค่าสุ่ม 256 บิตไม่ได้เลย — ไม่มี dictionary ของค่าสุ่ม
ในทางกลับกัน scrypt ต่อหนึ่ง request คือช่องให้ยิงถล่มด้วยการเรียก API รัว ๆ
(คนละสถานการณ์กับหน้า login ที่มี rate limit และเกิดไม่บ่อย)
ไม่ต้องมี salt ด้วยเหตุผลเดียวกัน: salt กัน rainbow table ซึ่งสร้างสำหรับ
ค่าสุ่ม 256 บิตไม่ได้อยู่แล้ว

เทียบ hash ด้วย `hmac.compare_digest` ไม่ใช่ `==` เพื่อไม่ให้เวลาที่ใช้เทียบ
บอกใบ้ว่าตรงกันไปกี่ตัวอักษร
"""

import hashlib
import hmac
import secrets
from datetime import timedelta

from flask_babel import gettext as _
from sqlalchemy import select

from app import db, tz
from app.models import ApiToken, User
from app.services.errors import NotFoundError, ValidationError
from app.services.lookup import by_id

# ขึ้นต้นด้วยคำที่ค้นเจอง่าย เผื่อ token หลุดเข้า git หรือ log — เครื่องมือสแกน
# secret จับ pattern ที่ตายตัวได้ ต่างจากสตริงสุ่มเปล่า ๆ ที่แยกจาก id ไม่ออก
TOKEN_PREFIX = "tdl"  # noqa: S105  ตัวคั่นที่เปิดเผยได้ ไม่ใช่ความลับ
SECRET_BYTES = 32
NAME_MAX_LENGTH = 80

# ค่าเริ่มต้นคือ "มีวันหมดอายุ" — token ที่ไม่มีวันหมดคือของที่ต้องขอเป็นพิเศษ
DEFAULT_EXPIRY_DAYS = 90


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _clean_name(raw: str | None) -> str:
    name = (raw or "").strip()
    if not name:
        raise ValidationError(_("Please enter a token name"), code="name_required", field="name")
    if len(name) > NAME_MAX_LENGTH:
        raise ValidationError(
            _("Token name must be at most %(limit)d characters", limit=NAME_MAX_LENGTH),
            code="name_too_long",
            field="name",
        )
    return name


def issue(user: User, name: str | None, expires_days: int | None = DEFAULT_EXPIRY_DAYS) -> str:
    """ออก token ใบใหม่ คืน **ความลับเต็ม ๆ ที่จะไม่มีวันแสดงอีก**

    `expires_days=None` หรือ `0` = ไม่มีวันหมดอายุ (ต้องระบุมาเองเท่านั้น)
    """
    cleaned = _clean_name(name)
    if expires_days is not None and expires_days < 0:
        raise ValidationError(
            _("Expiry must not be negative"), code="expiry_invalid", field="expires_days"
        )

    secret = secrets.token_urlsafe(SECRET_BYTES)
    token = ApiToken(
        user_id=user.id,
        name=cleaned,
        token_hash=_hash_secret(secret),
        expires_at=(
            tz.now_utc() + timedelta(days=expires_days) if expires_days not in (None, 0) else None
        ),
    )
    db.session.add(token)
    # ต้องได้ id ก่อนถึงจะประกอบสตริงได้ — id เป็นส่วนหนึ่งของตัว token
    db.session.flush()
    full = f"{TOKEN_PREFIX}_{token.id}_{secret}"
    db.session.commit()
    return full


def list_tokens(user: User) -> list[ApiToken]:
    """ใบที่ยังไม่ถูกเพิกถอนของผู้ใช้ ใหม่สุดก่อน (ใบที่เพิกถอนแล้วถูกซ่อนโดยตัวกรอง soft delete)"""
    statement = select(ApiToken).where(ApiToken.user_id == user.id).order_by(ApiToken.id.desc())
    return list(db.session.scalars(statement))


def get_token(user: User, token_id: int) -> ApiToken:
    """ใบของผู้ใช้คนนี้เท่านั้น — ของคนอื่นตอบเหมือนไม่มีอยู่ (ADR 0004)"""
    token = by_id(ApiToken, token_id)
    if token is None or token.user_id != user.id:
        raise NotFoundError(_("Token not found"), code="token_not_found")
    return token


def revoke(user: User, token_id: int) -> ApiToken:
    """เพิกถอนใบนั้นทันที — ซ่อนแถวและล้าง hash ทิ้งพร้อมกัน

    ล้าง hash ทันทีไม่รอ 30 วันตามชั้น C1 เหมือนตอนปิดบัญชี ผลคือถึงจะกู้แถว
    คืนมาก็ใช้ไม่ได้อีก ซึ่งเป็นสิ่งที่คนกดเพิกถอนคาดหวังพอดี
    """
    token = get_token(user, token_id)
    token.soft_delete()
    token.disable()
    db.session.commit()
    return token


def authenticate(raw: str | None) -> ApiToken | None:
    """ตรวจ token ที่ส่งมากับคำขอ — คืนใบที่ใช้ได้ หรือ None ถ้าไม่ผ่าน

    **ไม่บอกว่าไม่ผ่านเพราะอะไร** (รูปแบบผิด / ไม่มีใบนี้ / หมดอายุ / ถูกเพิกถอน /
    เจ้าของถูกปิดบัญชี) เพราะคนที่ยิงเดามาไม่ควรได้ข้อมูลกลับไปคัดกรองต่อ
    """
    parts = (raw or "").split("_", 2)
    expected_parts = 3
    if len(parts) != expected_parts or parts[0] != TOKEN_PREFIX or not parts[1].isdigit():
        return None

    token = by_id(ApiToken, int(parts[1]))
    if token is None or not token.is_usable:
        return None
    if not hmac.compare_digest(token.token_hash, _hash_secret(parts[2])):
        return None
    # เจ้าของที่ถูก soft delete ไปแล้วถูกตัวกรองซ่อนไว้ ความสัมพันธ์จึงว่าง
    if token.user is None:
        return None
    return token
