"""panel รายชื่อผู้ใช้ — งานบริหารบทบาท + การเปิดดูข้อมูลที่ mask ไว้ (ADR 0045)"""

from flask import abort, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_babel import lazy_gettext as _l
from flask_login import current_user, login_required

from app import db
from app.admin import bp, register_panel
from app.audit import record
from app.services import ForbiddenError, NotFoundError, ServiceError, masking, suspension
from app.services import roles as roles_service


def _rows(people, unmasked_id=None):
    """แปลงผู้ใช้เป็นแถวที่ผ่านชั้น masking แล้ว — template ห้ามแตะค่าดิบเอง

    ชื่อจริงเป็น C2: ค่าเริ่มต้นคือ mask และเปิดเต็มได้เฉพาะแถวที่เพิ่งถูก
    unmask (ซึ่งลง audit ไปแล้ว) — ค่าที่ template ได้จึงตัดสินเสร็จแล้วทั้งหมด
    """
    rows = []
    for person in people:
        unmasked = person.id == unmasked_id
        first = masking.display("tdl_user", "first_name", person.first_name, unmasked=unmasked)
        last = masking.display("tdl_user", "last_name", person.last_name, unmasked=unmasked)
        shown = " ".join(part for part in (first, last) if part) or "—"
        rows.append({"person": person, "name": shown, "unmasked": unmasked})
    return rows


@bp.route("/users")
@login_required
def users():
    """รายชื่อผู้ใช้ทั้งหมดพร้อมบทบาท — ชื่อจริงถูก mask โดยค่าเริ่มต้น"""
    try:
        people = roles_service.list_users(current_user)
    except ForbiddenError:
        abort(403)
    return render_template("admin_users.html", rows=_rows(people), roles=roles_service.ROLES)


@bp.route("/users/<int:user_id>/unmask", methods=["POST"])
@login_required
def unmask(user_id):
    """เปิดดูค่าที่ mask ของผู้ใช้หนึ่งคน — เป็นการกระทำที่ลง audit เสมอ

    ไม่มีสถานะค้าง: ค่าเต็มโผล่เฉพาะ response นี้ (ADR 0045) และ audit บันทึก
    *ว่าดูของใคร* ไม่บันทึกค่าที่เห็น (กติกา audit ห้ามเก็บค่าของ C1/C2/C3)
    """
    try:
        people = roles_service.list_users(current_user)
    except ForbiddenError:
        abort(403)
    if all(person.id != user_id for person in people):
        abort(404)

    record("admin.unmask", table_name="tdl_user", row_id=user_id)
    db.session.commit()
    return render_template(
        "admin_users.html", rows=_rows(people, unmasked_id=user_id), roles=roles_service.ROLES
    )


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


@bp.route("/users/<int:user_id>/suspend", methods=["POST"])
@login_required
def suspend(user_id):
    """ระงับการใช้บัญชี (PDPA ม.34) — ย้อนกลับได้เสมอด้วยปุ่มเดียวกัน"""
    return _toggle_suspension(suspension.suspend, user_id, _("%(name)s is now suspended"))


@bp.route("/users/<int:user_id>/unsuspend", methods=["POST"])
@login_required
def unsuspend(user_id):
    """เลิกระงับ — สถานะกลับเป็นปกติทั้งใบ"""
    return _toggle_suspension(suspension.unsuspend, user_id, _("%(name)s is active again"))


def _toggle_suspension(action, user_id, message):
    """ทางร่วมของ suspend/unsuspend — แปลง exception เป็นคำตอบแบบเดียวกับ change_role"""
    try:
        person = action(current_user, user_id)
    except ForbiddenError:
        abort(403)
    except NotFoundError:
        abort(404)
    except ServiceError as error:
        flash(error.message)
        return redirect(url_for("admin.users"))
    flash(message % {"name": person.username})
    return redirect(url_for("admin.users"))


register_panel("admin.users", _l("Users"))
