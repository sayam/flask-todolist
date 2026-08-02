"""purge — **จุดเดียวในระบบที่ลบข้อมูลจริง**

ทุกที่อื่นทำได้แค่ soft delete (ตั้ง `deleted_at`) ของที่ถูกซ่อนไว้จะถูกล้างจริง
ก็ต่อเมื่อพ้นระยะที่ตกลงไว้ใน docs/DATA-CLASSIFICATION.md เท่านั้น

การรวมไว้ที่เดียวทำให้ตอบคำถาม "ข้อมูลหายไปได้ทางไหนบ้าง" ได้ด้วยการอ่าน
ไฟล์เดียว และทำให้ audit ใน Phase 2 ข้อ 4 มีจุดเดียวที่ต้องดักเหตุการณ์ลบจริง

**ลำดับการล้างสำคัญ** — งานก่อนหมวด เพราะการลบหมวดจะทำให้ `category_id`
ของงานที่ยังเหลือกลายเป็น NULL ตาม `ondelete="SET NULL"` (FK ถูกบังคับจริงแล้ว
ตั้งแต่ Phase 2 ข้อ 1) ล้างงานก่อนจึงไม่มีงานให้เสียหมวดไปโดยเปล่าประโยชน์
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from app import db, tz
from app.models import Category, Todo, User
from app.soft_delete import INCLUDE_DELETED, SoftDeleteMixin

# ระยะที่อนุมัติไว้ (ADR 0014) — เปลี่ยนต้องแก้เอกสารจำแนกชั้นข้อมูลด้วย
PURGE_AFTER_DAYS = 30


@dataclass
class PurgeResult:
    """จำนวนแถวที่ถูกล้างจริงในแต่ละชนิด — ใช้รายงานและใช้เทสต์"""

    todos: int = 0
    categories: int = 0
    users_purged: int = 0

    @property
    def total(self) -> int:
        return self.todos + self.categories + self.users_purged


def _cutoff(days: int) -> datetime:
    return tz.now_utc() - timedelta(days=days)


def _expired[T: SoftDeleteMixin](model: type[T], cutoff: datetime) -> list[T]:
    """แถวที่ถูก soft delete ไว้นานเกินกำหนด — ต้องขอเห็นของที่ถูกลบเป็นพิเศษ

    `is_not(None)` **ซ้ำซ้อนโดยตั้งใจ** — ใน SQL `NULL < cutoff` ให้ UNKNOWN
    แถวที่ยังไม่ถูกลบจึงหลุดตัวกรองอยู่แล้วโดยไม่ต้องเขียน แต่เขียนไว้ให้คนอ่าน
    เห็นเงื่อนไขครบว่า "ถูกลบแล้ว **และ** เก่าพอ" ไม่ใช่ "เก่าพอ" เฉย ๆ
    (mutation test ถอดบรรทัดนี้ออกแล้วเทสต์ยังเขียว — เป็น equivalent mutant
    ไม่ใช่ช่องโหว่ของเทสต์ บันทึกไว้กันสับสนรอบหน้า)
    """
    return (
        db.session.query(model)
        .execution_options(**INCLUDE_DELETED)
        .filter(model.deleted_at.is_not(None), model.deleted_at < cutoff)
        .all()
    )


def _collect(
    days: int,
) -> tuple[list[Todo], list[Category], list[User]]:
    """หาแถวที่ถึงกำหนดล้าง — ใช้ร่วมกันทั้ง preview และของจริง

    แยกการ "หา" ออกจากการ "ลบ" เพื่อให้ทั้งสองทางมองเห็นชุดเดียวกันเสมอ
    ถ้าเขียนแยกกันสองที่ วันหนึ่งเงื่อนไขจะเพี้ยนกันแล้ว preview จะโกหก
    """
    cutoff = _cutoff(days)
    return (
        _expired(Todo, cutoff),
        _expired(Category, cutoff),
        [u for u in _expired(User, cutoff) if u.purged_at is None],
    )


def preview_expired(days: int = PURGE_AFTER_DAYS) -> PurgeResult:
    """นับว่าจะกระทบอะไรบ้าง **โดยไม่แตะข้อมูลเลย**

    เป็นฟังก์ชันคนละตัวกับ `purge_expired()` โดยตั้งใจ — เคยเขียนเป็น flag
    `dry_run` ที่ใช้ savepoint แล้ว rollback ทีหลัง ซึ่ง**ลบข้อมูลจริง**
    เพราะตัว purge commit ไปก่อนแล้ว savepoint จึงถูกปิดไปแล้วตอน rollback
    ทางที่ปลอดภัยคือทางที่ไม่มีคำสั่งลบอยู่ในนั้นเลย ไม่ใช่ทางที่ตั้งใจจะย้อน
    """
    todos, categories, users = _collect(days)
    return PurgeResult(todos=len(todos), categories=len(categories), users_purged=len(users))


def purge_expired(days: int = PURGE_AFTER_DAYS) -> PurgeResult:
    """ล้างของที่พ้นระยะแล้วออกจากฐานข้อมูลจริง

    ผู้ใช้ **ไม่ถูกลบแถวทิ้ง** แต่ถูกล้าง PII แล้วเหลือไว้เป็น tombstone
    เพื่อให้ audit ที่อ้าง `actor_id` ยังแสดงผลได้ว่าเป็นใคร (ดู ADR 0014)
    """
    todos, categories, users = _collect(days)

    for todo in todos:
        db.session.delete(todo)
    for category in categories:
        db.session.delete(category)
    for user in users:
        # เขียนทับ username ให้ชื่อเดิมถูกปล่อยคืนให้คนอื่นสมัครซ้ำได้
        # ไม่กำกวมย้อนหลังเพราะ audit อ้าง actor_id ที่เป็นเลข ไม่ใช่ชื่อ
        user.username = f"#deleted-{user.id}"
        user.first_name = None
        user.last_name = None
        user.disable_password()
        user.purged_at = tz.now_utc()

    db.session.commit()
    return PurgeResult(todos=len(todos), categories=len(categories), users_purged=len(users))
