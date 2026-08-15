"""purge — **จุดเดียวในระบบที่ลบข้อมูลจริง**

ทุกที่อื่นทำได้แค่ soft delete (ตั้ง `deleted_at`) ของที่ถูกซ่อนไว้จะถูกล้างจริง
ก็ต่อเมื่อพ้นระยะที่ตกลงไว้ใน docs/DATA-CLASSIFICATION.md เท่านั้น

การรวมไว้ที่เดียวทำให้ตอบคำถาม "ข้อมูลหายไปได้ทางไหนบ้าง" ได้ด้วยการอ่าน
ไฟล์เดียว และทำให้ audit ใน Phase 2 ข้อ 4 มีจุดเดียวที่ต้องดักเหตุการณ์ลบจริง

**ลำดับการล้างสำคัญ** — งานก่อนหมวด เพราะการลบหมวดจะทำให้ `category_id`
ของงานที่ยังเหลือกลายเป็น NULL ตาม `ondelete="SET NULL"` (FK ถูกบังคับจริงแล้ว
ตั้งแต่ Phase 2 ข้อ 1) ล้างงานก่อนจึงไม่มีงานให้เสียหมวดไปโดยเปล่าประโยชน์
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TypeVar

from sqlalchemy import func

from app import audit, db, tz
from app.audit import AuditEntry
from app.models import ApiToken, Category, Team, TeamMember, Todo, TodoDependency, TodoShare, User
from app.soft_delete import INCLUDE_DELETED, SoftDeleteMixin

# ระยะที่อนุมัติไว้ (ADR 0014) — เปลี่ยนต้องแก้เอกสารจำแนกชั้นข้อมูลด้วย
PURGE_AFTER_DAYS = 30
# audit เก็บนานกว่าข้อมูลปฏิบัติการมาก เพราะเป็นหลักฐาน ไม่ใช่ข้อมูลของ subject
AUDIT_RETAIN_DAYS = 365


@dataclass
class PurgeResult:
    """จำนวนแถวที่ถูกล้างจริงในแต่ละชนิด — ใช้รายงานและใช้เทสต์"""

    todos: int = 0
    categories: int = 0
    api_tokens: int = 0
    users_purged: int = 0
    graph_rows: int = 0
    audit_entries: int = 0

    @property
    def total(self) -> int:
        return (
            self.todos
            + self.categories
            + self.api_tokens
            + self.users_purged
            + self.graph_rows
            + self.audit_entries
        )


def _cutoff(days: int) -> datetime:
    return tz.now_utc() - timedelta(days=days)


# **จงใจใช้สำนวนก่อน PEP 695** (TypeVar/การ assign ธรรมดา ไม่ใช่ `type X = ...`
# หรือ `def f[T](...)`) — parser ของ CodeQL (2.26.3) ยังย่อย PEP 695 ไม่ได้
# แล้วไฟล์*ทั้งไฟล์*จะหลุดจากการสแกนความปลอดภัยเงียบ ๆ (เจอจริง: audit.py
# ไม่ถูกวิเคราะห์เลยทั้งไฟล์) · `tests/test_codeql_compat.py` กันการเผลอใช้ซ้ำ
T = TypeVar("T", bound=SoftDeleteMixin)


def _expired(model: type[T], cutoff: datetime) -> list[T]:  # noqa: UP047 — CodeQL ยังอ่าน PEP 695 ไม่ได้
    """แถวที่ถูก soft delete ไว้นานเกินกำหนด — ต้องขอเห็นของที่ถูกลบเป็นพิเศษ

    `is_not(None)` **ซ้ำซ้อนโดยตั้งใจ** — ใน SQL `NULL < cutoff` ให้ UNKNOWN
    แถวที่ยังไม่ถูกลบจึงหลุดตัวกรองอยู่แล้วโดยไม่ต้องเขียน แต่เขียนไว้ให้คนอ่าน
    เห็นเงื่อนไขครบว่า "ถูกลบแล้ว **และ** เก่าพอ" ไม่ใช่ "เก่าพอ" เฉย ๆ
    (mutation test ถอดบรรทัดนี้ออกแล้วเทสต์ยังเขียว — เป็น equivalent mutant
    ไม่ใช่ช่องโหว่ของเทสต์ บันทึกไว้กันสับสนรอบหน้า)
    """
    return (
        db.session.query(model)
        .execution_options(**INCLUDE_DELETED)
        .filter(model.deleted_at.is_not(None), model.deleted_at < cutoff)
        .all()
    )


def _collect(
    days: int,
) -> tuple[list[Todo], list[Category], list[ApiToken], list[User], list[SoftDeleteMixin]]:
    """หาแถวที่ถึงกำหนดล้าง — ใช้ร่วมกันทั้ง preview และของจริง

    แยกการ "หา" ออกจากการ "ลบ" เพื่อให้ทั้งสองทางมองเห็นชุดเดียวกันเสมอ
    ถ้าเขียนแยกกันสองที่ วันหนึ่งเงื่อนไขจะเพี้ยนกันแล้ว preview จะโกหก
    """
    cutoff = _cutoff(days)
    graph_rows: list[SoftDeleteMixin] = [
        # แถวของ org graph (ADR 0049) — สมาชิกภาพ/การแชร์/dependency ที่ถูกถอน
        # แล้วพ้นระยะ ลบทิ้งจริงได้ทั้งแถว (ไม่มี tombstone — ไม่มี audit ตัวไหน
        # อ้างแถวพวกนี้ด้วย id ข้ามตาราง) · Team อยู่ท้ายเพราะแถวลูกอ้างถึงมัน
        *_expired(TodoDependency, cutoff),
        *_expired(TodoShare, cutoff),
        *_expired(TeamMember, cutoff),
        *_expired(Team, cutoff),
    ]
    return (
        _expired(Todo, cutoff),
        _expired(Category, cutoff),
        _expired(ApiToken, cutoff),
        [u for u in _expired(User, cutoff) if u.purged_at is None],
        graph_rows,
    )


def _expired_audit(days: int) -> list[AuditEntry]:
    """แถว audit ที่พ้นระยะแล้ว **เฉพาะที่เป็นคำนำหน้าของสายเท่านั้น**

    audit เป็นสาย hash จึงตัดได้จากหัวอย่างเดียว การลบแถวกลางสายทำให้แถวถัดไป
    ชี้ไปแถวที่ไม่มีอยู่ และ checkpoint ก็ช่วยไม่ได้เพราะมันรับรองได้แค่ช่องว่าง
    ที่อยู่ต้นสาย ถ้าเขียนเป็น `WHERE created_at < cutoff` เฉย ๆ วันที่นาฬิกา
    เครื่องถูกปรับย้อนหลัง (NTP) จะมีแถวเก่าไปแทรกอยู่กลางสาย แล้ว purge
    ครั้งถัดไปจะเจาะรูตรงกลางทำให้ verify ไม่ผ่านตลอดกาล

    จึงหยุดที่แถวแรกที่ยังไม่หมดอายุ — แถวเก่าที่ตกค้างอยู่หลังจากนั้นถูกเก็บต่อ
    อีกพักหนึ่งจนกว่าคำนำหน้าจะไล่มาถึง (ยอมเก็บเกินดีกว่าทำหลักฐานพัง)
    """
    cutoff = _cutoff(days)
    query = db.session.query(AuditEntry).order_by(AuditEntry.id)
    first_kept = (
        db.session.query(func.min(AuditEntry.id)).filter(AuditEntry.created_at >= cutoff).scalar()
    )
    if first_kept is None:
        return query.all()
    return query.filter(AuditEntry.id < first_kept).all()


def purge_audit(days: int = AUDIT_RETAIN_DAYS) -> int:
    """ล้าง audit ที่พ้น 1 ปี พร้อมเขียน checkpoint ไม่ให้ hash chain ขาด

    **เขียน checkpoint ก่อนลบ** เพราะตอนนั้น chain ยังต่อกันครบ แถว checkpoint
    จึงเกาะปลายสายเดิมได้ตามธรรมชาติ ไม่ต้องไปยัดค่า hash เข้าไปเอง
    (ถ้าลบก่อนแล้วค่อยเขียน จะไม่มีอะไรให้เกาะเมื่อลบหมดทั้งตาราง)

    checkpoint เก็บ hash ของแถวสุดท้ายที่ถูกลบไว้ให้ `verify_chain()` ใช้เป็น
    จุดยึดแทนแถวที่หายไป — พิสูจน์ได้แค่ว่าแถวที่เหลือไม่ถูกแก้ ไม่ได้พิสูจน์ว่า
    แถวที่ถูกลบมีอะไร (ADR 0014 บันทึกข้อจำกัดนี้ไว้แล้ว)
    """
    rows = _expired_audit(days)
    if not rows:
        return 0

    audit.record(
        audit.CHECKPOINT_EVENT,
        changes={
            "purged_rows": len(rows),
            "last_purged_hash": rows[-1].row_hash,
            "covers_from": rows[0].created_at.isoformat(),
            "covers_to": rows[-1].created_at.isoformat(),
        },
    )
    audit.allow_purge(db.session)
    try:
        for row in rows:
            db.session.delete(row)
        db.session.commit()
    finally:
        # ปิดสิทธิ์คืนทันที ไม่ปล่อยค้างไว้ให้โค้ดถัดไปลบ audit ได้ฟรี ๆ
        audit.finish_purge(db.session)
    return len(rows)


def preview_expired(
    days: int = PURGE_AFTER_DAYS, audit_days: int = AUDIT_RETAIN_DAYS
) -> PurgeResult:
    """นับว่าจะกระทบอะไรบ้าง **โดยไม่แตะข้อมูลเลย**

    เป็นฟังก์ชันคนละตัวกับ `purge_expired()` โดยตั้งใจ — เคยเขียนเป็น flag
    `dry_run` ที่ใช้ savepoint แล้ว rollback ทีหลัง ซึ่ง**ลบข้อมูลจริง**
    เพราะตัว purge commit ไปก่อนแล้ว savepoint จึงถูกปิดไปแล้วตอน rollback
    ทางที่ปลอดภัยคือทางที่ไม่มีคำสั่งลบอยู่ในนั้นเลย ไม่ใช่ทางที่ตั้งใจจะย้อน
    """
    todos, categories, api_tokens, users, graph_rows = _collect(days)
    return PurgeResult(
        todos=len(todos),
        categories=len(categories),
        api_tokens=len(api_tokens),
        graph_rows=len(graph_rows),
        users_purged=len(users),
        audit_entries=len(_expired_audit(audit_days)),
    )


def purge_expired(days: int = PURGE_AFTER_DAYS, audit_days: int = AUDIT_RETAIN_DAYS) -> PurgeResult:
    """ล้างของที่พ้นระยะแล้วออกจากฐานข้อมูลจริง

    ผู้ใช้ **ไม่ถูกลบแถวทิ้ง** แต่ถูกล้าง PII แล้วเหลือไว้เป็น tombstone
    เพื่อให้ audit ที่อ้าง `actor_id` ยังแสดงผลได้ว่าเป็นใคร (ดู ADR 0014)

    ล้าง audit **หลัง** ล้างข้อมูล เพราะการล้างข้อมูลเองก็สร้างแถว audit
    (เหตุการณ์ `*.purge`) ซึ่งเป็นแถวใหม่เอี่ยม ไม่มีทางพ้นระยะอยู่แล้ว
    """
    todos, categories, api_tokens, users, graph_rows = _collect(days)

    for row in graph_rows:
        db.session.delete(row)
    for todo in todos:
        db.session.delete(todo)
    for category in categories:
        db.session.delete(category)
    for token in api_tokens:
        db.session.delete(token)
    for user in users:
        # เขียนทับ username ให้ชื่อเดิมถูกปล่อยคืนให้คนอื่นสมัครซ้ำได้
        # ไม่กำกวมย้อนหลังเพราะ audit อ้าง actor_id ที่เป็นเลข ไม่ใช่ชื่อ
        user.username = f"#deleted-{user.id}"
        user.first_name = None
        user.last_name = None
        user.disable_password()
        user.purged_at = tz.now_utc()

    db.session.commit()
    return PurgeResult(
        todos=len(todos),
        categories=len(categories),
        api_tokens=len(api_tokens),
        users_purged=len(users),
        graph_rows=len(graph_rows),
        audit_entries=purge_audit(audit_days),
    )
