"""บทบาทของผู้ใช้ — RBAC ขั้นต่ำ (Phase 4 — ดู ADR 0022)

**หนึ่งคนมีบทบาทเดียว** เก็บเป็นสตริงในคอลัมน์ `tdl_user.role` ไม่ใช่ตาราง
many-to-many เพราะตอนนี้มีบทบาทสองตัวและไม่มี permission ย่อยให้ประกอบ
โครงที่ยืดหยุ่นกว่านี้โดยยังไม่มีใครใช้คือความซับซ้อนที่พิสูจน์ความถูกต้องไม่ได้

**การตรวจสิทธิ์อยู่ใน service ไม่ใช่ที่ route** — ฟังก์ชันที่เป็นงานของผู้ดูแล
เรียก `require_admin()` ของตัวเองเสมอ (รับ "คนที่กำลังทำ" เป็นอาร์กิวเมนต์แรก)
ถ้าปล่อยให้ adapter เป็นคนตรวจ วันที่มี adapter ตัวที่สาม (API, CLI, งาน
เบื้องหลัง) คนเขียนต้องจำเองว่าต้องตรวจอะไรบ้าง ซึ่งคือวิธีที่ลืมได้
"""

from flask_babel import gettext as _
from sqlalchemy import select

from app import db
from app.models import User
from app.services.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.services.lookup import by_id

ROLE_USER = "user"
ROLE_ADMIN = "admin"

# ชุดปิด — ค่านอกรายการนี้ถูกปฏิเสธ ไม่ใช่ถูกเก็บลงไปเงียบ ๆ
ROLES = (ROLE_USER, ROLE_ADMIN)
DEFAULT_ROLE = ROLE_USER


def is_admin(user: User) -> bool:
    """คนนี้เป็นผู้ดูแลระบบไหม — อ่านอย่างเดียว ใช้ตอนตัดสินใจว่าจะโชว์เมนูไหม"""
    return getattr(user, "role", DEFAULT_ROLE) == ROLE_ADMIN


def require_admin(user: User) -> None:
    """ด่านของทุกงานที่เป็นของผู้ดูแล — ไม่ผ่านให้ `ForbiddenError` (403)

    **403 ไม่ใช่ 404 โดยตั้งใจ** ต่างจากกติกาเรื่องข้อมูลของคนอื่น (ADR 0004)
    ที่ตอบ 404 เพื่อไม่ยืนยันว่า id นั้นมีจริง — ตรงนี้ไม่มีความลับให้ปกปิด
    การมีอยู่ของหน้าผู้ดูแลไม่ใช่ข้อมูลลับ (มันอยู่ในซอร์สโค้ด) และการตอบ 404
    ให้ผู้ดูแลที่เพิ่งถูกถอดสิทธิ์จะทำให้เขาไล่หาสาเหตุผิดทาง
    """
    if not is_admin(user):
        raise ForbiddenError(_("This page is for administrators only"), code="admin_required")


def list_users(actor: User) -> list[User]:
    """ผู้ใช้ทั้งหมดในระบบ เรียงตาม id — งานของผู้ดูแลเท่านั้น

    คนที่ถูก soft delete ไม่โผล่ (ตัวกรองอัตโนมัติของ `app/soft_delete.py`)
    """
    require_admin(actor)
    return list(db.session.scalars(select(User).order_by(User.id)))


def get_user(actor: User, user_id: int) -> User:
    """ผู้ใช้หนึ่งคนตาม id — งานของผู้ดูแลเท่านั้น"""
    require_admin(actor)
    user = by_id(User, user_id)
    if user is None:
        raise NotFoundError(_("User not found"), code="user_not_found")
    return user


def assign_role(actor: User, user_id: int, role: str | None) -> User:
    """เปลี่ยนบทบาทของผู้ใช้คนหนึ่ง

    **ห้ามแก้บทบาทของตัวเอง** — ผู้ดูแลคนสุดท้ายที่เผลอถอดสิทธิ์ตัวเองทำให้
    ไม่เหลือใครเข้าหน้าผู้ดูแลได้อีกเลย และต้องไปแก้ผ่าน CLI ที่เครื่อง server
    (กติกานี้ยังกันการยกระดับตัวเองด้วย ถ้าวันหนึ่งมีบทบาทที่สูงกว่า admin)

    `require_admin()` ตรงนี้ **ซ้ำซ้อนโดยตั้งใจ** — `get_user()` ข้างล่างก็ตรวจ
    ให้อีกชั้น การถอดบรรทัดนี้ออกบรรทัดเดียวจึงไม่ทำให้เทสต์ตัวไหนแดง
    (equivalent mutant — ตรวจแล้ว ถอดทั้งสองที่เมื่อไหร่เทสต์แดงทันที บันทึกไว้
    กันสับสนรอบหน้า เหมือน `ApiToken.is_usable`) เก็บไว้เพราะด่านควรอยู่ที่
    ทางเข้าของทุกฟังก์ชัน ไม่ใช่ขึ้นกับว่ามันบังเอิญเรียกอะไรต่อ
    """
    require_admin(actor)
    if role not in ROLES:
        raise ValidationError(_("Unknown role"), code="role_invalid", field="role")

    target = get_user(actor, user_id)
    if target.id == actor.id:
        raise ConflictError(_("You cannot change your own role"), code="role_self_change")

    target.role = role
    db.session.commit()
    return target


def set_role(user: User, role: str) -> User:
    """ตั้งบทบาทโดยไม่ผ่านด่าน — **ทางของ CLI เท่านั้น**

    คนที่รันคำสั่งบนเครื่อง server มีสิทธิ์เหนือทุกอย่างอยู่แล้ว (แก้ฐานข้อมูล
    ตรง ๆ ก็ได้) และนี่คือทางเดียวที่จะตั้งผู้ดูแล **คนแรก** ได้ ในระบบที่ยัง
    ไม่มีผู้ดูแลเลยสักคน
    """
    if role not in ROLES:
        raise ValidationError(_("Unknown role"), code="role_invalid", field="role")
    user.role = role
    db.session.commit()
    return user
