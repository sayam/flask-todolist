"""สิทธิ์ของเจ้าของข้อมูล: ขอสำเนา และปิดบัญชี — ADR 0034

**เส้นแบ่งว่าอะไรอยู่ในไฟล์คือชั้นข้อมูล ไม่ใช่ความสะดวก**
(`docs/DATA-CLASSIFICATION.md`) — C1 ไม่ออกจากระบบเลยแม้ในรูป hash,
C5 ออกเฉพาะ "เกิดอะไรขึ้นเมื่อไหร่" ไม่รวมกลไกพิสูจน์ความครบถ้วนของสาย,
C6 ออกไม่ได้เลยเพราะแอปไม่มีทางค้น log ที่ไปอยู่นอกตัวมันตั้งแต่วินาทีแรก

**ข้อมูลของ plugin ให้ plugin ตอบเอง** — core ถามผ่านโมดูล `personal_data.py`
ของ plugin แต่ละตัว (`export_for` / `erase_for`) และไม่รู้จักชื่อใครเลย
(ADR 0023 · ADR 0025) ถอด plugin ทิ้งแล้วส่วนนั้นหายไปเอง ไม่มีโค้ดของมันค้างใน core

**ทางเดียวที่ปิดบัญชีได้คือ `close_account()` ตัวนี้** — ทั้งหน้าเว็บและ CLI
เรียกตัวเดียวกัน เพราะตอนที่ต่างคนต่างไล่ลบ `flask delete-user` ลืมล้างความลับ
ของปัจจัยที่สองไปทั้งดุ้น ทั้งที่คอมเมนต์ในฟังก์ชันนั้นอ้างกติกา C1 อยู่ (ADR 0034 ข้อ 4)
"""

from typing import Any

from flask import current_app
from flask_babel import gettext as _
from sqlalchemy import and_, func, or_, select

from app import db, plugins
from app.audit import AuditEntry
from app.models import ApiToken, Category, Todo, User
from app.services.errors import ConflictError

# ชื่อโมดูลที่ plugin ต้องมีถ้ามันเก็บข้อมูลของผู้ใช้ไว้
CONTRIBUTOR_MODULE = "personal_data"

# รูปแบบของไฟล์ — เพิ่มขึ้นเมื่อโครงสร้างเปลี่ยนจนของเก่าอ่านด้วยกติกาใหม่ไม่ได้
FORMAT_VERSION = 1

# **ข้อจำกัดต้องอยู่ในไฟล์ ไม่ใช่ในเอกสารที่ไม่มีใครเปิด** — คนที่ได้ไฟล์ไป
# ต้องรู้ว่าอะไรไม่ได้อยู่ในนั้นและทำไม ไม่ใช่เข้าใจเอาเองว่าครบ
NOTICE = {
    "included": ("บัญชี การตั้งค่า หมวด งาน ชื่อ API token และประวัติการเปลี่ยนแปลงที่เกี่ยวกับบัญชีนี้"),
    "excluded_secrets": (
        "ความลับทุกชนิด (รหัสผ่าน ค่าของ API token เมล็ดของปัจจัยที่สอง) "
        "ไม่อยู่ในไฟล์นี้แม้แต่ในรูปที่ถูกแฮชแล้ว — มันไม่ออกจากระบบทุกกรณี"
    ),
    "excluded_operational_logs": (
        "log ปฏิบัติการ (เวลาเข้าใช้ ที่อยู่ไอพี หน้าที่เปิด) ไม่อยู่ในไฟล์นี้ "
        "เพราะระบบส่งมันออกไปเก็บนอกตัวแอปตั้งแต่วินาทีที่เกิด แอปจึงค้นมันไม่ได้ "
        "ระยะเก็บรักษาของ log คือ 90 วัน"
    ),
    "excluded_audit_internals": (
        "ประวัติในไฟล์นี้บอกว่าเกิดอะไรขึ้นเมื่อไหร่ แต่ไม่มีค่าก่อน/หลังของ"
        "แต่ละการแก้ไข เพราะระบบเก็บไว้เป็นค่าที่ย้อนกลับไม่ได้เพื่อพิสูจน์ว่า"
        "ประวัติไม่ถูกแก้ ไม่ใช่เพื่อเก็บเนื้อหา"
    ),
}


def _at(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _account(user: "User") -> dict[str, Any]:
    return {
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
        "locale": user.locale,
        "theme": user.theme,
        "mode": user.mode,
        "timezone_name": user.timezone_name,
        "created_at": _at(user.created_at),
        # สถานะระงับ (PDPA ม.34) เป็นข้อเท็จจริงเกี่ยวกับบัญชีของเจ้าตัว — อยู่ในสำเนา
        "suspended_at": _at(user.suspended_at),
    }


def _categories(user: "User") -> list[dict[str, Any]]:
    rows = db.session.scalars(
        select(Category).where(Category.user_id == user.id).order_by(Category.id)
    )
    return [{"id": row.id, "name": row.name} for row in rows]


def _todos(user: "User") -> list[dict[str, Any]]:
    rows = db.session.scalars(select(Todo).where(Todo.user_id == user.id).order_by(Todo.id))
    return [
        {
            "id": row.id,
            "title": row.title,
            "is_done": row.is_done,
            "category_id": row.category_id,
            "start_date": _at(row.start_date),
            "due_date": _at(row.due_date),
            "created_at": _at(row.created_at),
            "updated_at": _at(row.updated_at),
        }
        for row in rows
    ]


def _api_tokens(user: "User") -> list[dict[str, Any]]:
    """**ชื่อกับวันเท่านั้น** — ค่าของ token เป็น C1 และแสดงครั้งเดียวตอนออกใบ"""
    rows = db.session.scalars(
        select(ApiToken).where(ApiToken.user_id == user.id).order_by(ApiToken.id)
    )
    return [
        {
            "id": row.id,
            "name": row.name,
            "created_at": _at(row.created_at),
            "expires_at": _at(row.expires_at),
        }
        for row in rows
    ]


def _history(user: "User") -> list[dict[str, Any]]:
    """เหตุการณ์ที่เกี่ยวกับบัญชีนี้ — **ไม่รวม changes/prev_hash/row_hash**

    สามอย่างนั้นเป็นกลไกพิสูจน์ว่าสายไม่ถูกแก้ ไม่ใช่ข้อมูลส่วนบุคคล
    และค่าใน `changes` เป็น HMAC ที่อ่านไม่ออกอยู่แล้ว (ADR 0014)

    **"ใครทำ" บอกเป็นบทบาท ไม่ใช่เลข** — id ของผู้ดูแลที่มาเปลี่ยนบทบาทให้
    ไม่ใช่ข้อมูลส่วนบุคคลของผู้ขอ (ADR 0034)
    """
    # สองฝั่ง: สิ่งที่เขาทำเอง และสิ่งที่คนอื่นทำกับบัญชีของเขา — ฝั่งหลังคือ
    # เหตุผลที่ต้องมีคำว่า by ในผลลัพธ์ เช่นตอนผู้ดูแลมาเปลี่ยนบทบาทให้
    did_it = AuditEntry.actor_id == user.id
    done_to_them = and_(AuditEntry.table_name == "tdl_user", AuditEntry.row_id == user.id)
    rows = db.session.scalars(
        select(AuditEntry).where(or_(did_it, done_to_them)).order_by(AuditEntry.id)
    )
    return [
        {
            "at": _at(row.created_at),
            "event": row.event,
            "table": row.table_name,
            "row_id": row.row_id,
            "by": "self" if row.actor_id == user.id else "administrator",
        }
        for row in rows
    ]


def _from_plugins(user: "User") -> dict[str, Any]:
    """ถาม plugin ทุกตัวที่ติดตั้งอยู่ว่ามีอะไรของผู้ใช้คนนี้บ้าง

    **core ไม่รู้จักชื่อ plugin ตัวไหนเลย** — วนตามที่ registry ค้นเจอ และตัวที่
    ไม่มีโมดูลนี้แปลว่าไม่ได้เก็บอะไรของผู้ใช้ ซึ่งเป็นคำตอบที่ถูกต้อง ไม่ใช่บั๊ก
    """
    collected: dict[str, Any] = {}
    for plugin in plugins.installed():
        module = plugins.load_module(plugin, CONTRIBUTOR_MODULE)
        contribute = getattr(module, "export_for", None) if module else None
        if not callable(contribute):
            continue
        # **ห้ามให้ plugin ตัวเดียวล้มทั้งคำขอ** — คนที่ขอสำเนาข้อมูลของตัวเอง
        # ต้องได้ส่วนที่เหลือ ไม่ใช่ได้ 500 เพราะ plugin ที่เขาไม่เคยใช้พัง
        try:
            found = contribute(user)
        except Exception:
            current_app.logger.exception(
                "plugin ตอบคำขอสำเนาข้อมูลไม่สำเร็จ", extra={"plugin": plugin.key}
            )
            collected[plugin.key] = {"error": "ดึงข้อมูลส่วนนี้ไม่สำเร็จ — ติดต่อผู้ดูแลระบบ"}
            continue
        if found:
            collected[plugin.key] = found
    return collected


def export(user: "User", *, now: Any = None) -> dict[str, Any]:
    """สำเนาข้อมูลทั้งหมดของผู้ใช้คนนี้ในรูปที่พร้อมเขียนเป็น JSON

    **ไม่ commit อะไร** — เป็นการอ่านล้วน · การบันทึกว่ามีคนขอสำเนาเป็นหน้าที่
    ของผู้เรียก เพราะ audit ของเหตุการณ์ที่ไม่ใช่การเขียน DB ต้องเรียกเอง (ADR 0015)
    """
    from app import tz

    return {
        "format": FORMAT_VERSION,
        "exported_at": _at(now or tz.now_utc()),
        "notice": NOTICE,
        "account": _account(user),
        "categories": _categories(user),
        "todos": _todos(user),
        "api_tokens": _api_tokens(user),
        "history": _history(user),
        "plugins": _from_plugins(user),
    }


def filename_for(user: "User", *, now: Any = None) -> str:
    """ชื่อไฟล์ **สร้างฝั่งเซิร์ฟเวอร์เสมอ** ไม่รับจากผู้ใช้ (ASVS V5.4.1)"""
    from app import tz

    stamp = (now or tz.now_utc()).strftime("%Y%m%d")
    safe = "".join(ch for ch in user.username if ch.isalnum() or ch in "-_") or "user"
    return f"todolist-{safe}-{stamp}.json"


# ---------------------------------------------------------------- ปิดบัญชี


def _erase_from_plugins(user: "User") -> dict[str, int]:
    """สั่ง plugin ทุกตัวลบข้อมูลของผู้ใช้คนนี้ — คืนจำนวนแถวที่แต่ละตัวลบไป

    **ตรงข้ามกับ export: ตัวนี้ปล่อยให้ล้มดังได้** ถ้า plugin ลบไม่สำเร็จแล้ว
    เรากลืน exception ไว้ ผลคือบัญชี "ปิดแล้ว" ในสายตาผู้ใช้ แต่ความลับของเขา
    ยังอยู่ในฐานข้อมูล ซึ่งแย่กว่าการบอกว่าปิดไม่สำเร็จให้ไปลองใหม่
    """
    erased: dict[str, int] = {}
    for plugin in plugins.installed():
        module = plugins.load_module(plugin, CONTRIBUTOR_MODULE)
        erase = getattr(module, "erase_for", None) if module else None
        if callable(erase):
            erased[plugin.key] = int(erase(user))
    return erased


def close_account(user: "User", *, actor: "User | None" = None) -> dict[str, Any]:
    """ปิดบัญชีตามนโยบายที่อนุมัติไว้ (ADR 0034 ข้อ 4)

    ทันที: ล้างรหัสผ่าน · ลบความลับของทุก plugin · เพิกถอน token ทุกใบ
    ตามระยะ: แถวถูก soft delete แล้ว `flask purge-expired` ล้างจริงเมื่อพ้น 30 วัน

    `actor` มีไว้ให้ผู้ดูแลปิดบัญชีของคนอื่นได้ — เมื่อไม่ส่งมาถือว่าเจ้าตัวทำเอง
    """
    from app.services.roles import ROLE_ADMIN

    # **ด่านนี้ใช้กับการปิดบัญชีตัวเองเท่านั้น** — `actor` เป็น None แปลว่าคำสั่ง
    # มาจาก CLI ซึ่งเป็นตัวตนที่แรงกว่า (คนที่เข้าถึงเครื่องได้) และเป็นทางกู้ระบบ
    # ทางเดียวที่เหลือ · หลักเดียวกับ ADR 0022: แก้บทบาทตัวเองบนเว็บไม่ได้ แต่ CLI ได้
    if user.role == ROLE_ADMIN and actor is not None and actor.id == user.id:
        # **ระบบที่ไม่เหลือผู้ดูแลคือระบบที่ไม่มีใครสร้างบัญชีหรือกู้รหัสให้ใครได้อีก**
        # ข้อความต้องบอกทางออก ไม่ใช่บอกแค่ว่าทำไม่ได้ (หลักเดียวกับ ADR 0022)
        remaining = db.session.scalar(
            select(func.count(User.id)).where(User.role == ROLE_ADMIN, User.id != user.id)
        )
        if not remaining:
            raise ConflictError(
                _(
                    "You are the only administrator. Make someone else an "
                    "administrator first, then close your account."
                ),
                code="last_administrator",
            )

    erased = _erase_from_plugins(user)

    # credential เป็นชั้น C1 — ล้างทันที ไม่รอ grace (ADR 0014)
    # ผลพลอยได้ที่ตั้งใจ: คุกกี้ทุกใบตายทันทีเพราะผูกกับ password_hash (ADR 0020)
    user.disable_password()

    # ใบที่ยังไม่หมดอายุคือกุญแจที่ยังเปิดประตูได้ ต้องตายไปพร้อมบัญชี
    tokens = list(db.session.scalars(select(ApiToken).where(ApiToken.user_id == user.id)))
    for token in tokens:
        token.soft_delete()
        token.disable()

    # cascade ของ ORM ผูกกับการลบจริงเท่านั้น ไม่ทำงานกับการตั้ง deleted_at
    todos = list(db.session.scalars(select(Todo).where(Todo.user_id == user.id)))
    categories = list(db.session.scalars(select(Category).where(Category.user_id == user.id)))
    for todo in todos:
        todo.soft_delete()
    for category in categories:
        category.soft_delete()
    user.soft_delete()

    db.session.commit()
    return {
        "todos": len(todos),
        "categories": len(categories),
        "tokens": len(tokens),
        "plugins": erased,
    }
