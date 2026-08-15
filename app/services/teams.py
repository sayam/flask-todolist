"""วงแบ่งปันงาน (ADR 0049) — สร้าง/จัดการโดย admin เท่านั้น (คำตัดสินข้อ 2)

สมาชิกภาพคือ**สิทธิ์การมองเห็น**งานที่ถูกแชร์เข้าวงนั้น — การถอดสมาชิกจึงต้อง
ตัด dependency ที่คนนั้นมองเห็นผ่านวงนี้ด้วย (ทำใน `app/services/sharing.py`
ผ่าน `sever_invisible_dependencies` — กติกาเดียวกับการเลิกแชร์)

การลบทุกอย่างในไฟล์นี้คือ soft delete (วินัย ADR 0014) และการเพิ่มซ้ำคือการ
คืนชีพแถวเดิม — unique constraint ครอบแถวที่ถูกซ่อนอยู่ด้วย จะ insert ใหม่ไม่ได้
"""

from flask_babel import gettext as _
from sqlalchemy import select

from app import db
from app.models import Team, TeamMember, User
from app.services.errors import ConflictError, NotFoundError, ValidationError
from app.services.lookup import by_id
from app.services.roles import require_admin
from app.soft_delete import INCLUDE_DELETED


def get_team(actor: User, team_id: int) -> Team:
    """วงสำหรับงานของผู้ดูแล — ไม่มี = 404 (ของ*สมาชิก*ใช้ `visible_team()`)"""
    require_admin(actor)
    team = by_id(Team, team_id)
    if team is None:
        raise NotFoundError(_("Team not found"), code="team_not_found")
    return team


def visible_team(user: User, team_id: int) -> Team:
    """วงในสายตาสมาชิก — ไม่ได้เป็นสมาชิก = ไม่มีวงนี้อยู่ (ADR 0004)"""
    team = by_id(Team, team_id)
    if team is None or not is_member(user, team.id):
        raise NotFoundError(_("Team not found"), code="team_not_found")
    return team


def list_teams(actor: User) -> list[Team]:
    require_admin(actor)
    return list(db.session.scalars(select(Team).order_by(Team.name)))


def teams_of(user: User) -> list[Team]:
    """วงที่ผู้ใช้เป็นสมาชิก — ตัวเลือกตอนแชร์งานและขอบเขตการมองเห็นทั้งหมด"""
    return list(
        db.session.scalars(
            select(Team)
            .join(TeamMember, TeamMember.team_id == Team.id)
            .where(TeamMember.user_id == user.id)
            .order_by(Team.name)
        )
    )


def is_member(user: User, team_id: int) -> bool:
    row = db.session.scalars(
        select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == user.id)
    ).first()
    return row is not None


def create_team(actor: User, name: str) -> Team:
    require_admin(actor)
    cleaned = str(name or "").strip()
    if not cleaned:
        raise ValidationError(_("Team name is required"), code="team_name_required", field="name")
    # ชื่อมี unique constraint ที่ครอบแถวที่ถูกซ่อน — เจอแถวเดิมให้คืนชีพ
    existing = db.session.scalars(
        select(Team).where(Team.name == cleaned).execution_options(**INCLUDE_DELETED)
    ).first()
    if existing is not None:
        if not existing.is_deleted:
            raise ConflictError(_("A team with that name already exists"), code="team_name_taken")
        existing.deleted_at = None
        db.session.commit()
        return existing
    team = Team(name=cleaned)
    db.session.add(team)
    db.session.commit()
    return team


def delete_team(actor: User, team_id: int) -> Team:
    """ลบวง = ซ่อนวงพร้อมสมาชิกภาพ/การแชร์/dependency ที่พึ่งการมองเห็นผ่านวงนี้"""
    from app.services import sharing

    team = get_team(actor, team_id)
    for member in db.session.scalars(select(TeamMember).where(TeamMember.team_id == team.id)):
        member.soft_delete()
    db.session.flush()
    sharing.retire_team_shares(team)
    team.soft_delete()
    db.session.commit()
    return team


def add_member(actor: User, team_id: int, username: str) -> TeamMember:
    team = get_team(actor, team_id)
    person = db.session.scalars(
        select(User).where(User.username == str(username or "").strip())
    ).first()
    if person is None:
        raise NotFoundError(_("No user with that name"), code="user_not_found")
    existing = db.session.scalars(
        select(TeamMember)
        .where(TeamMember.team_id == team.id, TeamMember.user_id == person.id)
        .execution_options(**INCLUDE_DELETED)
    ).first()
    if existing is not None:
        if not existing.is_deleted:
            raise ConflictError(_("Already a member of this team"), code="already_member")
        existing.deleted_at = None
        db.session.commit()
        return existing
    member = TeamMember(team_id=team.id, user_id=person.id)
    db.session.add(member)
    db.session.commit()
    return member


def remove_member(actor: User, team_id: int, user_id: int) -> TeamMember:
    """ถอดสมาชิก — สิ่งที่เขามองเห็นผ่านวงนี้หายไปด้วย รวมทั้ง dependency
    ของเขาที่ชี้ไปงานซึ่งเหลือมองเห็นผ่านวงนี้ทางเดียว (ADR 0049 ข้อ 2)"""
    from app.services import sharing

    team = get_team(actor, team_id)
    member = db.session.scalars(
        select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.user_id == user_id)
    ).first()
    if member is None:
        raise NotFoundError(_("No such member"), code="member_not_found")
    member.soft_delete()
    # flush ก่อนตัด dependency — เงื่อนไขการมองเห็นเป็น SQL ต้องเห็นสมาชิกภาพที่เพิ่งซ่อน
    db.session.flush()
    person = by_id(User, user_id)
    if person is not None:
        sharing.sever_invisible_dependencies(person)
    db.session.commit()
    return member


def rename(actor: User, team_id: int, new_name: str, reason: str) -> Team:
    """เปลี่ยนชื่อวง (CR#3) — ต้องมีเหตุผลเสมอ และลงบันทึกที่สมาชิกอ่านได้

    วงถูกบริหารโดย admin (ADR 0049 ข้อ 2) การเปลี่ยนที่ไม่บอกกล่าวทำให้สมาชิก
    สับสน — เหตุผลจึงเป็นช่องบังคับ ไม่ใช่ของแต่ง (บันทึกที่ไม่มี "ทำไม"
    ตอบได้แค่ว่าเกิดอะไร ซึ่งสมาชิกเห็นเองอยู่แล้วจากชื่อที่เปลี่ยนไป)
    """
    from app.models import TeamNameChange

    team = get_team(actor, team_id)
    cleaned = str(new_name or "").strip()
    cleaned_reason = str(reason or "").strip()
    if not cleaned:
        raise ValidationError(_("Team name is required"), code="team_name_required", field="name")
    if not cleaned_reason:
        raise ValidationError(
            _("A reason for the rename is required"), code="rename_reason_required", field="reason"
        )
    if cleaned == team.name:
        raise ValidationError(
            _("That is already the team's name"), code="team_name_unchanged", field="name"
        )
    collision = db.session.scalars(
        select(Team)
        .where(Team.name == cleaned, Team.id != team.id)
        .execution_options(**INCLUDE_DELETED)
    ).first()
    if collision is not None:
        raise ConflictError(_("A team with that name already exists"), code="team_name_taken")

    db.session.add(
        TeamNameChange(
            team_id=team.id,
            changed_by_id=actor.id,
            old_name=team.name,
            new_name=cleaned,
            reason=cleaned_reason,
        )
    )
    team.name = cleaned
    db.session.commit()
    return team


def overview_team(viewer: User, team_id: int) -> Team:
    """วงในสายตาคนที่มีสิทธิ์ดูหน้า detail — สมาชิก **หรือ admin** (CR#3)

    admin ไม่จำเป็นต้องเป็นสมาชิกวงที่ตัวเองบริหาร จึงเปิดทางนี้ให้ ·
    คนนอกที่ไม่ใช่ทั้งสองอย่าง = ไม่มีวงนี้อยู่ (ADR 0004)
    """
    from app.services.roles import is_admin

    team = by_id(Team, team_id)
    if team is None or not (is_member(viewer, team.id) or is_admin(viewer)):
        raise NotFoundError(_("Team not found"), code="team_not_found")
    return team


def name_history(viewer: User, team_id: int) -> list:
    """บันทึกการเปลี่ยนชื่อของวง ใหม่สุดก่อน — สิทธิ์เดียวกับหน้า detail"""
    from app.models import TeamNameChange

    team = overview_team(viewer, team_id)
    return list(
        db.session.scalars(
            select(TeamNameChange)
            .where(TeamNameChange.team_id == team.id)
            .order_by(TeamNameChange.changed_at.desc(), TeamNameChange.id.desc())
        )
    )
