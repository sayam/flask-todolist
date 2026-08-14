"""ระงับ/เลิกระงับการใช้บัญชี (PDPA ม.34) — ระงับ ≠ ลบ และย้อนกลับได้เสมอ

ความหมายที่ล็อกไว้:

- ระงับ = **หยุดการประมวลผล** ไม่ใช่หยุดการเก็บ — ห้าม login · session เดิม
  ถูกตัดโดย `app/session_security.py` · ข้อมูลไม่ถูกแตะแม้แต่แถวเดียว
- ผู้ระงับคือผู้ดูแล (ผู้ใช้ร้องขอผ่านช่องทางติดต่อของผู้ deploy — หลักเดียวกับ
  การกู้รหัสผ่านที่ไม่มี self-service ตาม ADR 0019)
- การเขียนลง audit อัตโนมัติผ่าน after_flush เหมือนการแก้ user ทุกครั้ง
  (แบบเดียวกับการเปลี่ยนบทบาท — ไม่ต้องเรียกอะไรเพิ่ม)
- **ผู้ดูแลระงับตัวเองไม่ได้** เหตุผลเดียวกับที่แก้บทบาทตัวเองไม่ได้
  (ADR 0022): ผู้ดูแลคนสุดท้ายที่ระงับตัวเอง = ระบบที่ไม่มีใครปลดล็อกได้
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app import db
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.services.lookup import by_id
from app.services.roles import require_admin

if TYPE_CHECKING:
    from app.models import User


def _target(actor: User, user_id: int) -> User:
    """หา user เป้าหมาย — ไม่มี/ถูกลบแล้ว = 404 ตาม ADR 0004"""
    from app.models import User

    require_admin(actor)
    person = by_id(User, user_id)
    if person is None:
        raise NotFoundError("ไม่พบผู้ใช้", code="user_not_found")
    return person


def suspend(actor: User, user_id: int) -> User:
    """ระงับการใช้บัญชีหนึ่งบัญชี — ย้อนกลับได้ด้วย `unsuspend()` เสมอ"""
    person = _target(actor, user_id)
    if person.id == actor.id:
        raise ValidationError("ระงับบัญชีของตัวเองไม่ได้", code="cannot_suspend_self")
    if person.suspended_at is not None:
        raise ConflictError("บัญชีนี้ถูกระงับอยู่แล้ว", code="already_suspended")
    person.suspended_at = datetime.now(UTC).replace(tzinfo=None)
    db.session.commit()
    return person


def unsuspend(actor: User, user_id: int) -> User:
    """เลิกระงับ — สถานะกลับเป็นปกติทั้งใบ ไม่มีร่องรอยครึ่ง ๆ กลาง ๆ"""
    person = _target(actor, user_id)
    if person.suspended_at is None:
        raise ConflictError("บัญชีนี้ไม่ได้ถูกระงับ", code="not_suspended")
    person.suspended_at = None
    db.session.commit()
    return person


def is_suspended(user: User | None) -> bool:
    """จุดตัดสินเดียวที่ auth/session ใช้ — อย่าไปเช็คคอลัมน์เอง"""
    return user is not None and user.suspended_at is not None
