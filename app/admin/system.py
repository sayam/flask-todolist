"""panel ข้อเท็จจริงของระบบ: environment · lifecycle · observability (เฟส 14)

ทั้งสามหน้าเป็น adapter บาง ๆ เหนือ `app/services/system_info.py` — ด่านสิทธิ์
อยู่ในนั้น (require_admin) ที่นี่แค่แปลง ForbiddenError เป็น 403 ตามแบบแผนของ
package นี้ · ไม่มีข้อมูลผู้ใช้บนหน้าเหล่านี้ แต่กติกา ADR 0045 ยังคุม: ถ้า
วันหนึ่งมีของผู้ใช้โผล่ ต้องผ่าน `app/services/masking.py` เท่านั้น
"""

from flask import abort, render_template
from flask_babel import lazy_gettext as _l
from flask_login import current_user, login_required

from app.admin import bp, register_panel
from app.services import ForbiddenError, system_info


@bp.route("/environment")
@login_required
def environment():
    """interpreter · แพลตฟอร์ม · ฐานข้อมูลที่ใช้อยู่จริง — อ่านสด ไม่เขียนมือ"""
    try:
        facts = system_info.environment(current_user)
    except ForbiddenError:
        abort(403)
    return render_template("admin_environment.html", facts=facts)


@bp.route("/lifecycle")
@login_required
def lifecycle():
    """เวอร์ชันแอป · สถานะ migration · สถานะ plugin จากดิสก์"""
    try:
        facts = system_info.lifecycle(current_user)
    except ForbiddenError:
        abort(403)
    return render_template("admin_lifecycle.html", facts=facts)


@bp.route("/observability")
@login_required
def observability():
    """histogram ของ process ตัวเอง — ป้ายกำกับ ADR 0031 ต้องอยู่บนหน้าเสมอ"""
    try:
        facts = system_info.observability(current_user)
    except ForbiddenError:
        abort(403)
    return render_template("admin_observability.html", facts=facts)


@bp.route("/sbom")
@login_required
def sbom():
    """SBOM ฉบับ runtime — ของที่ติดตั้งจริงเทียบกับที่ lock ประกาศ + เจ้าของต่อ package"""
    try:
        facts = system_info.sbom(current_user)
    except ForbiddenError:
        abort(403)
    return render_template("admin_sbom.html", facts=facts)


register_panel("admin.environment", _l("Environment"), _l("Server"))
register_panel("admin.lifecycle", _l("Lifecycle"), _l("Server"))
register_panel("admin.sbom", _l("Supply chain"), _l("Server"))
register_panel("admin.observability", _l("Observability"), _l("Reports"))
