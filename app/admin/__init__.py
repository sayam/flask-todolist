"""หน้าของผู้ดูแลระบบ — package ของ core ที่เสียบ panel ได้ (ADR 0044)

ทุก view ในนี้ทำงานกับข้อมูลของ **คนอื่น** (ต่างจาก `app/routes.py` ที่ทำงาน
กับข้อมูลของเจ้าของ session) — สองกติกาที่ห้ามผิด:

1. ด่านสิทธิ์อยู่ใน service (`require_admin` — ADR 0022) ที่นี่แค่แปลงเป็น 403
2. **ข้อมูลผู้ใช้ทุกชิ้นที่ออกจอ ต้องผ่าน `app/services/masking.py`**
   (ADR 0045) — ไม่มีข้อยกเว้นสำหรับ panel ที่มาทีหลัง

panel ใหม่ลงทะเบียนตัวเองด้วย `register_panel()` ตอน import — nav ของ admin
วนจาก registry ไม่ hardcode รายชื่อหน้า
"""

from flask import Blueprint

bp = Blueprint("admin", __name__, url_prefix="/admin")

#: (endpoint, ชื่อที่แปลได้) ตามลำดับการลงทะเบียน — ใช้ render แถบ panel
PANELS: list[tuple[str, object]] = []


def register_panel(endpoint: str, title: object) -> None:
    """ลงทะเบียนหน้าเข้าแถบ panel ของ admin — เรียกตอน import ของ module หน้า"""
    PANELS.append((endpoint, title))


@bp.app_context_processor
def _expose_panels() -> dict:
    """ให้ template เห็นรายการ panel โดยไม่ต้อง import อะไร"""
    return {"admin_panels": PANELS}


from app.admin import system, users  # noqa: E402,F401 — ลงทะเบียน view + panel ตอน import
