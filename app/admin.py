"""หน้าของผู้ดูแลระบบ — adapter บาง ๆ เหนือ `app/services/roles.py` (ADR 0022)

แยกออกมาจาก `app/routes.py` เพราะขอบเขตต่างกันชัด: ทุก view ในไฟล์นี้ทำงาน
กับข้อมูลของ **คนอื่น** ส่วนไฟล์นั้นทำงานกับข้อมูลของเจ้าของ session เท่านั้น
การปนกันทำให้กติกา "query ต้อง filter ด้วย user_id เสมอ" อ่านแล้วสับสน

**ด่านสิทธิ์ไม่ได้อยู่ที่นี่** — service เป็นคนตรวจเอง (`require_admin`)
ตรงนี้แค่แปลง `ForbiddenError` เป็น 403 เท่านั้น
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required

from app.services import ForbiddenError, NotFoundError, ServiceError
from app.services import roles as roles_service

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/users")
@login_required
def users():
    """รายชื่อผู้ใช้ทั้งหมดพร้อมบทบาท"""
    try:
        people = roles_service.list_users(current_user)
    except ForbiddenError:
        abort(403)
    return render_template("admin_users.html", people=people, roles=roles_service.ROLES)


@bp.route("/users/<int:user_id>/role", methods=["POST"])
@login_required
def change_role(user_id):
    """เปลี่ยนบทบาทของผู้ใช้หนึ่งคน"""
    try:
        person = roles_service.assign_role(current_user, user_id, request.form.get("role"))
    except ForbiddenError:
        abort(403)
    except NotFoundError:
        abort(404)
    except ServiceError as error:
        flash(error.message)
        return redirect(url_for("admin.users"))

    flash(_("Role of %(name)s is now %(role)s", name=person.username, role=person.role))
    return redirect(url_for("admin.users"))
