"""soft delete — "ลบ" แปลว่าซ่อน ไม่ใช่หายจากฐานข้อมูลทันที

**ตัวกรองทำงานอัตโนมัติทุก ORM query** ผ่าน event `do_orm_execute` ไม่ใช่ให้แต่ละ
จุดเรียกใช้ helper เอง เพราะ helper ที่ต้องเรียกเองคือ helper ที่ลืมเรียกได้
และการลืมครั้งเดียวแปลว่าข้อมูลที่ผู้ใช้สั่งลบโผล่กลับมาให้เห็น

ครอบทุกทาง: `Model.query`, `session.get()`, `select()` และการโหลด relationship
งานที่ต้องเห็นของที่ลบแล้ว (purge job, การกู้คืน) ต้องขอเป็นพิเศษด้วย
`.execution_options(**INCLUDE_DELETED)` — ตั้งใจให้เขียนยากกว่าปกติหนึ่งขั้น

**ข้อจำกัดที่ต้องรู้:** ตัวกรองทำงานตอนมี query จริงเท่านั้น ถ้า object ยังค้าง
อยู่ใน identity map ของ session `session.get()` จะคืนตัวนั้นกลับมาโดยไม่ query
จึงไม่ถูกกรอง — เป็นพฤติกรรมของ `with_loader_criteria` เอง ไม่ใช่บั๊กของเรา
**ไม่กระทบ request จริงเพราะแต่ละ request ได้ session ใหม่** แต่กระทบเทสต์ที่
soft delete แล้วอ่านซ้ำใน context เดียวกัน — ต้อง `expunge_all()` ก่อน
(`expire_all()` ไม่พอ มันแค่บอกให้โหลดค่าใหม่ ไม่ได้เอาออกจาก identity map)

ระยะเวลาก่อนลบจริงและกติกาต่อชั้นข้อมูลอยู่ใน docs/DATA-CLASSIFICATION.md
"""

from datetime import datetime

from sqlalchemy import DateTime, event
from sqlalchemy.orm import (
    Mapped,
    ORMExecuteState,
    Session,
    mapped_column,
    with_loader_criteria,
)

from app import tz

# ส่งเข้า execution_options เพื่อ "ขอเห็นของที่ถูกลบด้วย"
INCLUDE_DELETED = {"include_deleted": True}


class SoftDeleteMixin:
    """model ที่สืบทอดตัวนี้จะถูกซ่อนอัตโนมัติเมื่อ `deleted_at` ไม่เป็น NULL"""

    # NULL = ยังอยู่ / มีค่า = ถูกลบเมื่อไหร่ (UTC naive เหมือน timestamp อื่นทั้งระบบ)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """ทำเครื่องหมายว่าถูกลบ — เขียนเวลาเฉพาะครั้งแรก

        เรียกซ้ำต้องไม่ขยับเวลา ไม่งั้นการลบซ้ำจะเลื่อนกำหนด purge ออกไปเรื่อย ๆ
        และของที่ควรถูกล้างไปแล้วจะค้างอยู่ตลอดกาล
        """
        if self.deleted_at is None:
            self.deleted_at = tz.now_utc()


@event.listens_for(Session, "do_orm_execute")
def _hide_soft_deleted(execute_state: ORMExecuteState) -> None:
    """เติมเงื่อนไข `deleted_at IS NULL` ให้ทุก SELECT ที่ไม่ได้ขอยกเว้น"""
    if not execute_state.is_select:
        return
    if execute_state.execution_options.get("include_deleted", False):
        return
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            SoftDeleteMixin,
            lambda cls: cls.deleted_at.is_(None),
            # ครอบ alias ด้วย ไม่งั้น join/subquery จะหลุดตัวกรอง
            include_aliases=True,
        )
    )
