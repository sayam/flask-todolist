"""panel จัดการวงแบ่งปันงาน (ADR 0049 — คำตัดสินข้อ 2: admin เท่านั้น)

adapter บาง ๆ เหนือ `app/services/teams.py` ตามวินัย service layer —
ด่านสิทธิ์จริงอยู่ที่ `require_admin()` ใน service ไม่ใช่ที่นี่
"""

from flask import abort, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_babel import lazy_gettext as _l
from flask_login import current_user, login_required

from app.admin import bp, register_panel
from app.services import ForbiddenError, NotFoundError, ServiceError
from app.services import teams as teams_service


@bp.route("/teams")
@login_required
def teams():
    """รายการวงทั้งหมดพร้อมสมาชิก — ที่เดียวจบ ไม่มีหน้าลูก"""
    try:
        rows = teams_service.list_teams(current_user)
    except ForbiddenError:
        abort(403)
    return render_template("admin_teams.html", teams=rows)


@bp.route("/teams/add", methods=["POST"])
@login_required
def add_team():
    try:
        team = teams_service.create_team(current_user, request.form.get("name", ""))
        flash(_("Team “%(name)s” created", name=team.name))
    except ForbiddenError:
        abort(403)
    except ServiceError as error:
        flash(error.message)
    return redirect(url_for("admin.teams"))


@bp.route("/teams/<int:team_id>/rename", methods=["POST"])
@login_required
def rename_team(team_id):
    """เปลี่ยน display name ของวง (CR#3) — ต้องกรอกเหตุผล และลงบันทึกให้สมาชิกอ่าน"""
    try:
        team = teams_service.rename(
            current_user, team_id, request.form.get("name", ""), request.form.get("reason", "")
        )
        flash(_("Team renamed to “%(name)s”", name=team.name))
    except ForbiddenError:
        abort(403)
    except NotFoundError:
        abort(404)
    except ServiceError as error:
        flash(error.message)
    return redirect(url_for("admin.teams"))


@bp.route("/teams/<int:team_id>/delete", methods=["POST"])
@login_required
def delete_team(team_id):
    try:
        teams_service.delete_team(current_user, team_id)
        flash(_("Team deleted"))
    except ForbiddenError:
        abort(403)
    except NotFoundError:
        abort(404)
    return redirect(url_for("admin.teams"))


@bp.route("/teams/<int:team_id>/members", methods=["POST"])
@login_required
def add_member(team_id):
    try:
        teams_service.add_member(current_user, team_id, request.form.get("username", ""))
    except ForbiddenError:
        abort(403)
    except NotFoundError as error:
        # วงไม่มี = 404 · แต่ "ไม่มีผู้ใช้ชื่อนั้น" คือความผิดของฟอร์ม ไม่ใช่ URL
        if error.code == "team_not_found":
            abort(404)
        flash(error.message)
    except ServiceError as error:
        flash(error.message)
    return redirect(url_for("admin.teams"))


@bp.route("/teams/<int:team_id>/members/<int:user_id>/remove", methods=["POST"])
@login_required
def remove_member(team_id, user_id):
    try:
        teams_service.remove_member(current_user, team_id, user_id)
    except ForbiddenError:
        abort(403)
    except NotFoundError:
        abort(404)
    return redirect(url_for("admin.teams"))


register_panel("admin.teams", _l("Teams"), _l("Users & teams"))
