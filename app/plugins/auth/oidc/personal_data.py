"""ข้อมูลของผู้ใช้ที่ plugin นี้ถือไว้ — สำหรับคำขอสำเนาของเจ้าของข้อมูล

plugin เป็นเจ้าของตารางของตัวเอง (ADR 0023) core จึงถามไม่ได้ว่าข้างในมีอะไร
**plugin ต้องเป็นคนตอบเอง** — ไม่งั้นวันที่ถอด plugin ทิ้ง core จะยังมีโค้ดที่
รู้จักคอลัมน์ของมันค้างอยู่ ซึ่งเป็นสิ่งที่ ADR 0023 ห้ามไว้ตรง ๆ
"""

from typing import Any

from sqlalchemy import select

from app import db

from .models import OidcIdentity


def export_for(user: Any) -> dict[str, Any] | None:
    """สิ่งที่ plugin นี้เก็บเกี่ยวกับผู้ใช้คนนี้ — ไม่มีเลยคืน None

    `subject` เป็นชั้น C2 (ระบุตัวบุคคลในระบบของ IdP) **ไม่ใช่ C1** จึงส่งออกได้
    ตามกติกาของ ADR 0034 — มันไม่ให้สิทธิ์อะไรกับคนที่รู้ค่านี้
    """
    rows = list(
        db.session.scalars(
            select(OidcIdentity).where(OidcIdentity.user_id == user.id).order_by(OidcIdentity.id)
        )
    )
    if not rows:
        return None
    return {
        "linked_accounts": [
            {
                "issuer": row.issuer,
                "subject": row.subject,
                "linked_at": row.linked_at.isoformat() if row.linked_at else None,
            }
            for row in rows
        ]
    }
