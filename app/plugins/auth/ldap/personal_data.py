"""ข้อมูลของผู้ใช้ที่ plugin นี้ถือไว้ — สำหรับคำขอสำเนาของเจ้าของข้อมูล

หลักเดียวกับ plugin อื่น: plugin เป็นเจ้าของตารางของตัวเอง (ADR 0023)
จึงต้องเป็นคนตอบว่าข้างในมีอะไรของใคร ไม่ใช่ให้ core ไปอ่านเอง
"""

from typing import Any

from sqlalchemy import select

from app import db

from .models import DirectoryIdentity


def export_for(user: Any) -> dict[str, Any] | None:
    """สิ่งที่ plugin นี้เก็บเกี่ยวกับผู้ใช้คนนี้ — ไม่มีเลยคืน None

    `external_id` เป็นชั้น C2 เหมือน `subject` ของ OIDC — ระบุตัวบุคคลใน
    ไดเรกทอรีได้ แต่ไม่ใช่ความลับที่ใช้ยืนยันตัว
    """
    rows = list(
        db.session.scalars(
            select(DirectoryIdentity)
            .where(DirectoryIdentity.user_id == user.id)
            .order_by(DirectoryIdentity.id)
        )
    )
    if not rows:
        return None
    return {
        "linked_directories": [
            {
                "directory": row.directory,
                "external_id": row.external_id,
                "linked_at": row.linked_at.isoformat() if row.linked_at else None,
            }
            for row in rows
        ]
    }


def erase_for(user: Any) -> int:
    """ลบการผูกบัญชีกับไดเรกทอรีของผู้ใช้คนนี้ทิ้ง **จริง ๆ ไม่ใช่ soft delete**

    ตารางของ plugin อยู่นอกวงจร purge ของ core (ADR 0023) การซ่อนแถวไว้จึงแปลว่า
    ไม่มีใครมาล้างมันเลยตลอดกาล · คืนจำนวนแถวที่ลบไป เพื่อให้ผู้เรียกรายงานได้
    ว่าเกิดอะไรขึ้นบ้าง แทนที่จะเชื่อว่าทำงานแล้ว
    """
    rows = list(
        db.session.scalars(select(DirectoryIdentity).where(DirectoryIdentity.user_id == user.id))
    )
    for row in rows:
        db.session.delete(row)
    return len(rows)
