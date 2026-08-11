"""ข้อมูลของผู้ใช้ที่ plugin นี้ถือไว้ — สำหรับคำขอสำเนาของเจ้าของข้อมูล

**ความลับ TOTP เป็นชั้น C1 จึงไม่ออกจากระบบเลย แม้แต่ในรูป hash** (ADR 0014)
ที่ส่งออกได้คือ *ข้อเท็จจริงว่าเปิดใช้อยู่* กับเวลา ซึ่งเป็น C4 —
เจ้าของข้อมูลมีสิทธิ์รู้ว่าบัญชีตัวเองมีปัจจัยที่สองผูกอยู่ตั้งแต่เมื่อไหร่
แต่การส่งเมล็ดออกไปคือการส่งกุญแจออกไปทั้งดอก

`last_counter` ก็ไม่ส่งออก — มันบอกได้ว่าเจ้าตัว login ครั้งล่าสุดช่วงไหน
ซึ่งเป็นข้อมูลของเขาเองก็จริง แต่ค่าที่ส่งออกไปแล้วช่วยคนที่ขโมยเมล็ดไปได้
ในการเลี่ยงตัวกันใช้รหัสซ้ำ · คำถาม "login ครั้งล่าสุดเมื่อไหร่" ตอบจาก
ประวัติในไฟล์ส่งออกได้อยู่แล้ว (เหตุการณ์ auth.login)
"""

from typing import Any

from sqlalchemy import select

from app import db

from .models import TotpSecret


def export_for(user: Any) -> dict[str, Any] | None:
    """สิ่งที่ plugin นี้เก็บเกี่ยวกับผู้ใช้คนนี้ — ไม่มีเลยคืน None"""
    row = db.session.scalars(select(TotpSecret).where(TotpSecret.user_id == user.id)).first()
    if row is None:
        return None
    return {
        "enrolled": row.confirmed_at is not None,
        "started_at": row.created_at.isoformat() if row.created_at else None,
        "confirmed_at": row.confirmed_at.isoformat() if row.confirmed_at else None,
    }
