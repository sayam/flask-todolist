"""หน้าของผู้ดูแลระบบ — package ของ core ที่เสียบ panel ได้ (ADR 0044)

ทุก view ในนี้ทำงานกับข้อมูลของ **คนอื่น** (ต่างจาก `app/routes.py` ที่ทำงาน
กับข้อมูลของเจ้าของ session) — สองกติกาที่ห้ามผิด:

1. ด่านสิทธิ์อยู่ใน service (`require_admin` — ADR 0022) ที่นี่แค่แปลงเป็น 403
2. **ข้อมูลผู้ใช้ทุกชิ้นที่ออกจอ ต้องผ่าน `app/services/masking.py`**
   (ADR 0045) — ไม่มีข้อยกเว้นสำหรับ panel ที่มาทีหลัง

panel ใหม่ลงทะเบียนตัวเองด้วย `register_panel()` ตอน import — nav ของ admin
วนจาก registry ไม่ hardcode รายชื่อหน้า
"""

from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required

bp = Blueprint("admin", __name__, url_prefix="/admin")

#: (endpoint, ชื่อที่แปลได้, หมวดที่แปลได้) ตามลำดับการลงทะเบียน — หน้า
#: Site administration จัดกลุ่มตามหมวด (Change Req #1 ข้อ 3 — แบบ Moodle)
#: ส่วนแถบ nav ของหน้า admin ยัง render เรียงตามลำดับเดิม
PANELS: list[tuple[str, object, object]] = []


def register_panel(endpoint: str, title: object, category: object) -> None:
    """ลงทะเบียนหน้าเข้า registry ของ admin — เรียกตอน import ของ module หน้า

    `category` เป็นหมวดบนหน้า Site administration — หน้าใหม่เลือกหมวดเดิม
    ที่มีอยู่ก่อนเสมอ ตั้งหมวดใหม่เมื่อไม่มีหมวดไหนตรงจริง ๆ เท่านั้น
    (หมวดที่มีสมาชิกใบเดียวหลายหมวดคือรายการแบนที่แต่งตัวเป็นกลุ่ม)
    """
    PANELS.append((endpoint, title, category))


def panels_by_category() -> list[tuple[object, list[tuple[str, object]]]]:
    """จัดกลุ่มตามหมวด คงลำดับการลงทะเบียนทั้งระดับหมวดและในหมวด"""
    grouped: dict[object, list[tuple[str, object]]] = {}
    for endpoint, title, category in PANELS:
        grouped.setdefault(category, []).append((endpoint, title))
    return list(grouped.items())


@bp.app_context_processor
def _expose_panels() -> dict:
    """ให้ template เห็นรายการ panel โดยไม่ต้อง import อะไร"""
    return {"admin_panels": PANELS}


@bp.route("")
@login_required
def index():
    """หน้า Site administration — ทางเข้าเดียวของงานผู้ดูแล จัดหมวดแบบ Moodle

    ด่านสิทธิ์คือ `require_admin` ของ service (ADR 0022) เหมือน panel ทุกหน้า
    """
    from app.services import ForbiddenError
    from app.services.roles import require_admin

    try:
        require_admin(current_user)
    except ForbiddenError:
        abort(403)
    return render_template("admin_index.html", groups=panels_by_category())


from app.admin import system, teams, users  # noqa: E402,F401 - import order required here · ลงทะเบียน view + panel ตอน import
