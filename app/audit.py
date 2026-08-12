"""audit trail — บันทึกว่า **ใครทำอะไรกับแถวไหนเมื่อไหร่** แบบเติมได้อย่างเดียว

**ไม่ใช่ log** — log (`app/logging_setup.py`) ตอบว่าระบบทำงานยังไง เก็บ 90 วัน
ส่วนตารางนี้เป็นหลักฐาน เก็บ 1 ปี และแก้ย้อนหลังไม่ได้ (ดู ADR 0014/0015)

## หลักที่ห้ามผิด

1. **ดักที่ ORM ไม่ใช่ที่ route** — ผูก event `after_flush` ของ Session ทุก write
   จึงถูกบันทึกเอง ไม่ว่าจะมาจาก route, CLI หรือสคริปต์ คนเขียนฟีเจอร์ใหม่
   ไม่ต้องจำว่าต้องเรียกอะไร (วิธีที่ต้องจำ = วิธีที่ลืมได้ เหมือน soft delete)
2. **ไม่เขียน PII ลงตารางนี้ตั้งแต่แรก** — actor เก็บเป็นเลข `actor_id`
   ค่าของคอลัมน์ชั้น C2/C3 เก็บเป็น HMAC ส่วน C1 ไม่เก็บแม้แต่ในรูป hash
   คำขอลบข้อมูลจึงทำได้ครบโดยไม่ต้องแตะแถว audit เลย (นั่นคือเหตุผลทั้งหมด
   ที่ chain ไม่มีวันต้องถูก re-chain — ดู ADR 0014)
3. **"ที่ไหน" ตอบด้วย `request_id` ไม่ใช่ IP** — IP อยู่ใน log ซึ่งมีอายุ 90 วัน
   ตามชั้น C6 ถ้าก๊อป IP มาไว้ที่นี่ด้วยมันจะอยู่ยาว 1 ปีโดยไม่มีใครตั้งใจ
   ต้องการ IP ให้เอา `request_id` ไปค้นใน log ระหว่างที่ log ยังไม่หมดอายุ

## hash chain

แต่ละแถวเก็บ `prev_hash` ของแถวก่อนหน้า และ `row_hash` ของตัวเอง แก้แถวเก่า
แถวเดียวทำให้ทุกแถวถัดไปตรวจไม่ผ่าน — `flask audit-verify` เดินสายทั้งเส้น

**`prev_hash` ถูกบังคับ unique** เพื่อให้ chain แตกเป็นสองสายไม่ได้เลยในระดับ DB
และ **การต่อสายถูก serialize ด้วยการล็อกแถวท้ายสาย** (`FOR UPDATE` ใน
`_last_hash` — ADR 0032) ผู้เขียนรายที่สองจึงรอ ไม่ใช่ชนแล้วตกไป

ประวัติที่ควรรู้: เดิมยอมให้ชนแล้ว transaction ตกไป โดยให้เหตุผลว่า "ดังกว่า
chain ที่พังเงียบ" และว่า SQLite serialize การเขียนอยู่แล้ว — **เงื่อนไขนั้น
หมดอายุตอน Phase 5 ทำให้ ≥2 replica เป็นของจริง** และ load test ของ Phase 6
วัดราคาออกมาเป็น 500 ที่ผู้ใช้เห็น 0.36–9.5% ของการเขียน

**เวลาถูกตัดเศษวินาทีทิ้งก่อนทั้งเก็บและ hash** เพราะ MySQL `DATETIME` ปัดทิ้ง
microsecond ให้เอง ถ้า hash ค่าที่ละเอียดกว่าที่ DB เก็บได้ อ่านกลับมาคำนวณใหม่
จะไม่ตรงทันทีที่ย้ายยี่ห้อ DB (ดู ROADMAP ข้อ 4.5)
"""

import hashlib
import hmac
import json
from datetime import datetime
from typing import Any

from flask import current_app, has_request_context
from flask_login import current_user
from sqlalchemy import Integer, String, Text, UniqueConstraint, event, inspect, select
from sqlalchemy.orm import Mapped, Session, mapped_column, scoped_session

from app import db, tz
from app.db_types import UTCDateTime
from app.logging_setup import current_request_id

# แถวแรกสุดของสายไม่มีแถวก่อนหน้าให้ชี้ — ใช้ค่าคงที่แทน
GENESIS_HASH = "0" * 64
HASH_LENGTH = 64

# แถวเดียวของ tdl_audit_lock — คีย์คงที่เพราะมันมีแถวเดียวตลอดอายุระบบ
LOCK_ROW_ID = 1

# ชนิดเหตุการณ์ที่ purge job เขียนแทนช่วงที่ถูกลบไป (ดู ADR 0014 หัวข้อที่สอง)
CHECKPOINT_EVENT = "audit.checkpoint"

# db.session เป็น scoped_session ไม่ใช่ Session ตรง ๆ — รับทั้งสองแบบเพื่อให้
# เรียกจากทั้ง event handler (ได้ Session) และจากโค้ดแอป (ได้ db.session) ได้
type SessionLike = Session | scoped_session[Any]

SOURCE_WEB = "web"
SOURCE_CLI = "cli"

# ---------------------------------------------------------------- นโยบายต่อคอลัมน์
# ที่มาของการแบ่งคือ docs/DATA-CLASSIFICATION.md — เปลี่ยนที่นั่นต้องมาเปลี่ยนที่นี่
# `tests/test_audit.py` บังคับว่าทุกคอลัมน์ต้องถูกระบุไว้ในสามชุดนี้ชุดใดชุดหนึ่ง

# ชั้น C4 — เก็บค่าจริงได้ เพราะเป็นการตั้งค่า/metadata ไม่ระบุตัวบุคคล
PLAIN_COLUMNS = frozenset(
    {
        "id",
        "user_id",
        "category_id",
        "is_done",
        "locale",
        "theme",
        "mode",
        # บทบาทเป็นชั้น C4 และเป็นค่าที่ **ต้องอ่านออกจาก audit ได้จริง** —
        # "ใครยกระดับใครเป็น admin เมื่อไหร่" เป็นคำถามแรก ๆ ตอนสืบเหตุ
        "role",
        "timezone_name",
        "created_at",
        "updated_at",
        "deleted_at",
        "purged_at",
        "expires_at",
    }
)

# ชั้น C1 — ห้ามออกจากระบบทุกกรณี บันทึกได้แค่ว่า "มีการเปลี่ยน"
SECRET_COLUMNS = frozenset({"password_hash", "token_hash"})

# ชั้น C2/C3 — เก็บชื่อคอลัมน์ + HMAC ของค่าเก่า/ใหม่
HASHED_COLUMNS = frozenset(
    {
        "username",
        "first_name",
        "last_name",
        "title",
        "name",
        "start_date",
        "due_date",
    }
)

# ชื่อของสามนโยบายข้างบน — ใช้เป็นค่าที่ **plugin ประกาศเอง** ได้ด้วย (ADR 0023)
PLAIN = "plain"
SECRET = "secret"  # noqa: S105  ชื่อของนโยบาย ไม่ใช่ความลับ
HASHED = "hashed"


def plugin_column_policies() -> dict[str, str]:
    """ชั้นของคอลัมน์ที่ plugin ประกาศไว้ใน `models.py` ของตัวเอง

    **core ไม่รู้จักชื่อคอลัมน์ของ plugin ตัวไหนเลย** ถามเอาตอนใช้งานจริง
    ไม่ใช่เขียนรายชื่อไว้ในไฟล์นี้ — ชื่อที่เขียนไว้จะกลายเป็นขยะค้างอยู่ในโค้ด
    core ทันทีที่มีคนถอน plugin ทิ้ง (และ `tests/test_plugins.py` ก็ห้ามไว้ด้วย)
    """
    from app import plugins

    return plugins.audit_policies()


def column_policy(column: str) -> str:
    """คอลัมน์นี้ถูกบันทึกลง audit ยังไง — **ไม่รู้จักก็ปิดบังไว้ก่อน (HMAC)**"""
    if column in SECRET_COLUMNS:
        return SECRET
    if column in PLAIN_COLUMNS:
        return PLAIN
    if column in HASHED_COLUMNS:
        return HASHED
    return plugin_column_policies().get(column, HASHED)


class AuditChainLock(db.Model):
    """แถวเดียวที่ทุกคนที่จะต่อสาย audit ต้องล็อกก่อน — **หนึ่งแถวเท่านั้น**

    **ทำไมต้องมีตารางนี้ ทั้งที่ ADR 0032 บอกว่าล็อกแถวท้ายสายก็พอ**: เพราะ
    `SELECT ... ORDER BY id DESC LIMIT 1 FOR UPDATE` บน InnoDB จับ **next-key
    lock ที่รวมช่องว่างท้ายตาราง** ไว้ด้วย และ**ช่องว่างเข้ากันได้กับช่องว่าง** —
    ผู้เขียนหลายรายจึงผ่านบรรทัดนั้นไปพร้อมกันได้ทั้งหมด แล้วไปชนกันตอน INSERT
    ซึ่งต้องขอ insert intention lock ที่ขัดกับช่องว่างของคนอื่น → **deadlock**

    วัดจริงก่อนแก้: writer 8 ตัว × 20 รอบ ได้ deadlock 128 จาก 160 ครั้ง
    การล็อกแบบเดิมจึงไม่ได้ทำให้การเขียนเป็นลำดับ มันแค่เปลี่ยนการชนกุญแจ
    unique ให้กลายเป็น deadlock (ดู ADR 0035)

    การล็อก**แถวที่มีอยู่จริงด้วยคีย์หลัก**เป็น record lock ล้วน ไม่มีช่องว่าง
    ให้ขัดกัน ผู้เขียนจึงต่อคิวกันจริง ๆ
    """

    __tablename__ = "tdl_audit_lock"

    id: Mapped[int] = mapped_column(primary_key=True)


# **แถวต้องมีอยู่ก่อนเสมอ** ไม่งั้นไม่มีอะไรให้ล็อกแล้วทุกคนผ่านไปพร้อมกัน
# ผูกกับการสร้าง **ทั้งชุด** ไม่ใช่กับตารางตัวเดียว — INSERT ที่แทรกกลางลำดับ DDL
# ของ `create_all()` ทำให้ MySQL ค้าง metadata lock แล้วการ reflect ตารางถัดไป
# ล้มด้วย 1684 ("definition is being modified by concurrent DDL statement")
# ซึ่งเป็นอาการที่ไล่กลับมาหาต้นเหตุยากมากถ้าไม่รู้ว่ามันมาจากตรงนี้
@event.listens_for(db.metadata, "after_create")
def _seed_lock_row(_target: Any, connection: Any, tables: Any = (), **_kwargs: Any) -> None:
    lock = AuditChainLock.__table__
    if lock in tuple(tables):
        connection.execute(lock.insert().values(id=LOCK_ROW_ID))


class AuditImmutableError(RuntimeError):
    """ยกขึ้นเมื่อมีใครพยายามแก้หรือลบแถว audit นอก purge job"""


class AuditEntry(db.Model):
    """หนึ่งแถว = หนึ่งเหตุการณ์ **เติมได้อย่างเดียว ห้ามแก้ ห้ามลบ**

    ไม่สืบทอด `SoftDeleteMixin` โดยตั้งใจ — "ซ่อนหลักฐาน" ไม่ใช่สิ่งที่ควรทำได้
    และไม่มี FK ไป `tdl_user` เพราะ audit ต้องอยู่รอดโดยไม่ผูกชะตากับตารางข้อมูล
    `actor_id` จึงอาจชี้ไป tombstone ของคนที่ถูก purge ไปแล้ว (ตั้งใจ)
    """

    __tablename__ = "tdl_audit"

    id: Mapped[int] = mapped_column(primary_key=True)
    # UTC naive ตัดเศษวินาทีทิ้งแล้ว (เหตุผลอยู่ใน docstring ของโมดูล)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    event: Mapped[str] = mapped_column(String(32), index=True)
    # เลขล้วน ไม่เก็บ username — ลบ PII ที่ตาราง user แล้วแถวนี้ไม่ต้องแก้
    actor_id: Mapped[int | None] = mapped_column(Integer, index=True)
    source: Mapped[str] = mapped_column(String(8))
    # กุญแจไปหา log ที่มีรายละเอียดระดับ request (IP, path, status)
    request_id: Mapped[str | None] = mapped_column(String(36))
    table_name: Mapped[str | None] = mapped_column(String(64))
    row_id: Mapped[int | None] = mapped_column(Integer)
    # canonical JSON — เก็บเป็นข้อความและ hash ข้อความตัวนี้ตรง ๆ
    # เพื่อไม่ให้ผลลัพธ์ขึ้นกับลำดับคีย์ของ JSON encoder ตัวไหน
    changes: Mapped[str] = mapped_column(Text)
    prev_hash: Mapped[str] = mapped_column(String(HASH_LENGTH))
    row_hash: Mapped[str] = mapped_column(String(HASH_LENGTH))

    __table_args__ = (
        # chain แตกเป็นสองสายไม่ได้: แถวสองแถวชี้ไปแถวก่อนหน้าตัวเดียวกันไม่ได้
        UniqueConstraint("prev_hash", name="uq_audit_prev_hash"),
        UniqueConstraint("row_hash", name="uq_audit_row_hash"),
    )

    def __repr__(self) -> str:
        return f"<AuditEntry {self.id} {self.event} row={self.table_name}:{self.row_id}>"

    @property
    def payload(self) -> dict[str, Any]:
        """`changes` ที่ย่อยกลับเป็น dict แล้ว — ใช้ตอนอ่าน ไม่ใช่ตอน hash"""
        parsed: dict[str, Any] = json.loads(self.changes)
        return parsed


# ---------------------------------------------------------------- serialize + hash


def _canonical(payload: Any) -> str:
    """JSON ที่ให้ผลเหมือนเดิมทุกครั้ง — คีย์เรียง ไม่มีช่องว่างเกิน"""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _plain(value: Any) -> Any:
    """ค่าที่เก็บลง audit ได้ตรง ๆ — เวลาแปลงเป็น ISO ฝั่งแอปก่อนเสมอ

    ถ้าปล่อยให้ DB จัดการรูปแบบเวลา ผล hash จะต่างกันตามยี่ห้อ DB
    """
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _hmac_key() -> bytes:
    """กุญแจ HMAC — ตั้งแยกได้ ไม่ตั้งก็แยกสายมาจาก SECRET_KEY

    แยกสายด้วย blake2b แทนที่จะใช้ SECRET_KEY ตรง ๆ เพื่อไม่ให้คีย์ที่ใช้เซ็น
    session กับคีย์ที่ใช้ปิดบังค่าใน audit เป็นตัวเดียวกัน
    """
    configured = current_app.config.get("AUDIT_HMAC_KEY")
    if configured:
        return str(configured).encode("utf-8")
    secret = str(current_app.config["SECRET_KEY"]).encode("utf-8")
    return hashlib.blake2b(secret, person=b"tdl-audit-hmac").digest()


def _hmac(value: Any) -> str | None:
    """ปิดบังค่าของชั้น C2/C3 — ตอบได้ว่า "เปลี่ยนไหม" แต่ตอบไม่ได้ว่า "คืออะไร"

    ต้องเป็น HMAC ไม่ใช่ hash เปล่า เพราะค่าอย่างชื่อคนสั้นและเดาได้
    `sha256("สยาม")` ถูกไล่เดาด้วย dictionary ได้ในไม่กี่วินาที (ADR 0014)
    """
    if value is None:
        return None
    return hmac.new(
        _hmac_key(), _canonical(_plain(value)).encode("utf-8"), hashlib.sha256
    ).hexdigest()


def compute_row_hash(  # noqa: PLR0913  ทุกฟิลด์ของแถวต้องเข้า hash ครบ ยุบตัวไหนก็คือช่องโหว่
    *,
    created_at: datetime,
    event_name: str,
    actor_id: int | None,
    source: str,
    request_id: str | None,
    table_name: str | None,
    row_id: int | None,
    changes: str,
    prev_hash: str,
) -> str:
    """hash ของหนึ่งแถว — ทั้งตอนเขียนและตอน verify ต้องผ่านฟังก์ชันนี้ตัวเดียว

    ไม่รวม `id` เข้าไปในการ hash โดยตั้งใจ เพราะ id มาจาก DB ตอน insert
    (ยังไม่รู้ค่าตอนคำนวณ) และลำดับของสายมาจาก `prev_hash` อยู่แล้ว ไม่ใช่จาก id
    """
    material = _canonical(
        {
            "created_at": created_at.isoformat(),
            "event": event_name,
            "actor_id": actor_id,
            "source": source,
            "request_id": request_id,
            "table_name": table_name,
            "row_id": row_id,
            "changes": changes,
            "prev_hash": prev_hash,
        }
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- ใครและมาจากไหน


def _actor_id() -> int | None:
    """เลขประจำตัวของคนที่ทำ — None เมื่อมาจาก CLI หรือยังไม่ได้ login"""
    if not has_request_context():
        return None
    try:
        if current_user.is_authenticated:
            return int(current_user.id)
    except (AttributeError, RuntimeError):
        return None
    return None


def _source() -> str:
    return SOURCE_WEB if has_request_context() else SOURCE_CLI


# ---------------------------------------------------------------- การเขียนลงสาย

_LAST_HASH_KEY = "audit_last_hash"
_PURGE_ALLOWED_KEY = "audit_purge_allowed"


def _last_hash(session: SessionLike) -> str:
    """hash ของแถวล่าสุดในตาราง — cache ไว้ต่อ transaction ไม่ใช่ตลอดอายุ session

    ล้าง cache ทุกครั้งที่ commit/rollback (ดู `_reset_chain_cache`) เพราะถ้า
    process อื่นเขียนแทรกเข้ามา ค่าที่ค้างอยู่จะทำให้เราต่อสายผิดที่

    **การต่อสายเป็นลำดับจริงข้าม process ด้วยการล็อกแถวเดียวของ `tdl_audit_lock`**
    (ADR 0035) ผู้เขียนรายที่สองรอที่บรรทัดนั้นจนรายแรก commit แล้วค่อยอ่านหางสาย
    ที่ถูกต้องไปต่อ · ไม่มีข้อนี้ สอง replica จะอ่านแถวท้ายสายตัวเดียวกันแล้ว
    ต่อด้วย `prev_hash` เดียวกันทั้งคู่ ตัวหลังชน unique constraint แล้ว
    **ผู้ใช้เห็น 500** (Phase 6 วัดได้ 0.36% ที่โหลดเป้าหมาย ถึง 9.5% ที่โหลดสูง)

    **ห้ามกลับไปล็อกแถวท้ายสายเอง** (`ORDER BY id DESC LIMIT 1 FOR UPDATE` ซึ่ง
    เป็นวิธีของ ADR 0032) — InnoDB จับ next-key lock ที่รวมช่องว่างท้ายตาราง
    และช่องว่างเข้ากันได้กับช่องว่าง ผู้เขียนหลายรายจึงผ่านไปพร้อมกันแล้วไปชนกัน
    ตอน INSERT เป็น **deadlock** แทน · วัดจริง: writer 8 ตัว × 20 รอบ
    ได้ deadlock 128 จาก 160 ครั้ง

    SQLAlchemy ตัด `FOR UPDATE` ทิ้งให้เองบน SQLite ซึ่งถูกต้องแล้ว เพราะ
    SQLite ล็อกทั้งไฟล์ตอนเขียนอยู่แล้ว การเขียนจึงเป็นลำดับโดยธรรมชาติ
    """
    cached = session.info.get(_LAST_HASH_KEY)
    if cached is not None:
        return str(cached)

    connection = session.connection()
    lock = AuditChainLock.__table__
    # ล็อก **แถวที่มีอยู่จริงด้วยคีย์หลัก** — record lock ล้วน ไม่มีช่องว่างให้ขัดกัน
    locked = connection.execute(
        select(lock.c.id).where(lock.c.id == LOCK_ROW_ID).with_for_update()
    ).scalar()
    if locked is None:
        # แถวนี้ถูกสร้างพร้อมตาราง (ดู `_seed_lock_row`) — หายไปแปลว่ามีคนลบมันทิ้ง
        # หรือ migration ไม่ได้ถูกรัน · **ห้ามเดินต่อเงียบ ๆ** เพราะการเขียนที่
        # ไม่มีอะไรกั้นจะกลายเป็น 500 ของผู้ใช้ในวันที่มีคนใช้พร้อมกัน
        # ไม่ใช่การละเมิดความไม่เปลี่ยนแปลงของ audit จึงไม่ใช่ `AuditImmutableError`
        # — เป็นเงื่อนไขก่อนเริ่มที่ไม่ครบ ซึ่งต้องอ่านออกจากข้อความได้ทันที
        raise RuntimeError(f"ไม่มีแถวล็อกของสาย audit (id={LOCK_ROW_ID}) — รัน `flask db upgrade` ก่อน")

    table = AuditEntry.__table__
    found = connection.execute(
        select(table.c.row_hash).order_by(table.c.id.desc()).limit(1)
    ).scalar()
    value = str(found) if found else GENESIS_HASH
    session.info[_LAST_HASH_KEY] = value
    return value


def _build_entry(
    session: SessionLike,
    event_name: str,
    table_name: str | None,
    row_id: int | None,
    changes: dict[str, Any],
) -> AuditEntry:
    prev_hash = _last_hash(session)
    # ตัดเศษวินาทีทิ้งเพื่อให้ค่าที่ hash ตรงกับค่าที่ DB เก็บได้จริงทุกยี่ห้อ
    created_at = tz.now_utc().replace(microsecond=0)
    changes_json = _canonical(changes)
    actor_id = _actor_id()
    source = _source()
    request_id = current_request_id()
    row_hash = compute_row_hash(
        created_at=created_at,
        event_name=event_name,
        actor_id=actor_id,
        source=source,
        request_id=request_id,
        table_name=table_name,
        row_id=row_id,
        changes=changes_json,
        prev_hash=prev_hash,
    )
    session.info[_LAST_HASH_KEY] = row_hash
    return AuditEntry(
        created_at=created_at,
        event=event_name,
        actor_id=actor_id,
        source=source,
        request_id=request_id,
        table_name=table_name,
        row_id=row_id,
        changes=changes_json,
        prev_hash=prev_hash,
        row_hash=row_hash,
    )


def record(
    event_name: str,
    *,
    table_name: str | None = None,
    row_id: int | None = None,
    changes: dict[str, Any] | None = None,
) -> AuditEntry:
    """บันทึกเหตุการณ์ที่ไม่ได้เกิดจากการเขียน DB (เช่น login/logout)

    ผู้เรียกเป็นคนสั่ง commit เอง — ฟังก์ชันนี้แค่ add เข้า session
    ค่าที่ส่งเข้า `changes` ต้องผ่านการพิจารณาชั้นข้อมูลมาแล้ว **ห้ามส่ง PII ดิบ**
    """
    entry = _build_entry(db.session, event_name, table_name, row_id, changes or {})
    db.session.add(entry)
    return entry


# ---------------------------------------------------------------- ดักทุก ORM write


def _is_auditable(obj: object) -> bool:
    """ทุก model ยกเว้นตาราง audit เอง (ไม่งั้นการเขียน audit จะเรียกตัวเองไม่จบ)"""
    return isinstance(obj, db.Model) and not isinstance(obj, AuditEntry)


def _column_change(column: str, old: Any, new: Any) -> dict[str, Any]:
    """แปลงค่าเก่า/ใหม่ตามชั้นข้อมูลของคอลัมน์นั้น

    **ค่าเริ่มต้นคือ HMAC** — คอลัมน์ที่ไม่รู้จักถูกปิดบังไว้ก่อน ไม่ใช่เปิดเผยไว้ก่อน
    คอลัมน์ใหม่ที่ลืมจัดชั้นจึงรั่วไม่ได้ (แต่ก็ยังมีเทสต์บังคับให้ไปจัดชั้นอยู่ดี)
    """
    policy = column_policy(column)
    if policy == SECRET:
        return {"changed": True}
    if policy == PLAIN:
        return {"from": _plain(old), "to": _plain(new)}
    return {"from_hash": _hmac(old), "to_hash": _hmac(new)}


def _changes_for(obj: Any, action: str) -> dict[str, Any]:
    """ค่าที่เปลี่ยนของแถวนั้น — insert/delete บันทึกครบทุกคอลัมน์ update บันทึกเฉพาะที่เปลี่ยน

    **insert อ่านค่าจาก object ตรง ๆ ไม่ใช่จาก history** เพราะคอลัมน์ที่ได้ค่าจาก
    `default=` (เช่น `is_done`, `created_at`) ถูกเติมตอน flush โดยไม่ทิ้ง history ไว้
    ถ้าดูแต่ history แถวเกิดใหม่จะบันทึกไม่ครบและไม่มีใครสังเกตเห็น
    """
    state = inspect(obj)
    changes: dict[str, Any] = {}
    for attr in state.mapper.column_attrs:
        name = attr.key
        if action == "insert":
            changes[name] = _column_change(name, None, getattr(obj, name))
            continue
        if action == "delete":
            changes[name] = _column_change(name, getattr(obj, name), None)
            continue
        history = state.attrs[name].history
        if not history.has_changes():
            continue
        old = history.deleted[0] if history.deleted else None
        new = history.added[0] if history.added else None
        changes[name] = _column_change(name, old, new)
    return changes


def _event_name(obj: Any, action: str) -> str:
    """ชื่อเหตุการณ์ตามความหมายของระบบ ไม่ใช่ตามคำสั่ง SQL ที่ใช้

    ในระบบนี้ "ลบ" คือการตั้ง `deleted_at` ซึ่งเป็น UPDATE ในระดับ SQL
    ถ้าเรียกมันว่า `update` คนอ่าน audit จะหาเหตุการณ์ลบไม่เจอ
    ส่วน DELETE จริงเกิดได้ที่เดียวคือ purge job จึงเรียกว่า `purge`
    """
    table = str(getattr(obj, "__tablename__", "")).removeprefix("tdl_")
    if action == "update":
        history = inspect(obj).attrs.get("deleted_at")
        if history is not None and history.history.has_changes():
            return f"{table}.delete" if getattr(obj, "deleted_at", None) else f"{table}.restore"
        return f"{table}.update"
    return f"{table}.purge" if action == "delete" else f"{table}.insert"


def _pending_writes(session: Session) -> list[tuple[Any, str]]:
    """สิ่งที่เพิ่ง flush ไป จับคู่กับชนิดการเขียน — เก็บให้ครบก่อนค่อยเขียน audit

    ต้องอ่านให้ครบก่อน ไม่ใช่ทยอย `session.add()` ระหว่างวน เพราะการเพิ่ม object
    เข้า session ระหว่างที่ยังไล่ `session.new` อยู่คือการแก้ของที่กำลังวนอยู่
    """
    writes: list[tuple[Any, str]] = [(obj, "insert") for obj in session.new if _is_auditable(obj)]
    writes += [
        (obj, "update")
        for obj in session.dirty
        if _is_auditable(obj) and session.is_modified(obj, include_collections=False)
    ]
    writes += [(obj, "delete") for obj in session.deleted if _is_auditable(obj)]
    return writes


@event.listens_for(Session, "after_flush")
def _record_orm_writes(session: Session, _flush_context: object) -> None:
    """เขียนแถว audit ให้ทุก insert/update/delete ที่เพิ่ง flush ไป

    ใช้ `after_flush` เพราะเป็นจุดเดียวที่ได้ทั้ง **ค่า primary key ของแถวใหม่**
    (ต้องใช้เป็น `row_id`) และ **ประวัติค่าเก่าของแถวที่แก้** ครบพร้อมกัน
    ของที่ `session.add()` ตรงนี้ถูกเขียนใน flush รอบถัดไปที่ commit เรียกให้เอง
    """
    pending: list[AuditEntry] = []
    for obj, action in _pending_writes(session):
        changes = _changes_for(obj, action)
        if not changes:
            continue
        pending.append(
            _build_entry(
                session,
                _event_name(obj, action),
                str(obj.__tablename__),
                getattr(obj, "id", None),
                changes,
            )
        )
    for entry in pending:
        session.add(entry)


@event.listens_for(Session, "before_flush")
def _forbid_audit_mutation(session: Session, _flush_context: object, _instances: object) -> None:
    """append-only บังคับที่ระดับโค้ด ไม่ใช่แค่ "ไม่มีหน้าจอให้แก้"

    การไม่มี UI แก้ log เป็นแค่การไม่ได้ทำ ไม่ใช่การกันไว้ — สคริปต์หรือ shell
    เขียนทับได้อยู่ดี ด่านนี้ทำให้ต้องตั้งใจจริง ๆ ถึงจะผ่าน (purge job เท่านั้น)
    """
    for obj in session.dirty:
        if isinstance(obj, AuditEntry) and session.is_modified(obj, include_collections=False):
            raise AuditImmutableError(f"แถว audit แก้ไม่ได้ (id={obj.id})")
    if session.info.get(_PURGE_ALLOWED_KEY):
        return
    for obj in session.deleted:
        if isinstance(obj, AuditEntry):
            raise AuditImmutableError(
                f"แถว audit ลบได้เฉพาะใน purge job ตามระยะเก็บรักษา (id={obj.id})"
            )


@event.listens_for(Session, "after_commit")
@event.listens_for(Session, "after_rollback")
def _reset_chain_cache(session: Session) -> None:
    session.info.pop(_LAST_HASH_KEY, None)


def allow_purge(session: SessionLike) -> None:
    """เปิดให้ session นี้ลบแถว audit ได้ — เรียกจาก `app/purge.py` เท่านั้น"""
    session.info[_PURGE_ALLOWED_KEY] = True


def finish_purge(session: SessionLike) -> None:
    """ปิดสิทธิ์คืนทันทีที่ลบเสร็จ ไม่ปล่อยค้างไว้ทั้ง session"""
    session.info.pop(_PURGE_ALLOWED_KEY, None)


# ---------------------------------------------------------------- การตรวจสาย


def entries(limit: int | None = None) -> list[AuditEntry]:
    """อ่านแถว audit ใหม่สุดก่อน — ไม่มีทางแก้ผ่านทางนี้ อ่านอย่างเดียว"""
    query = db.session.query(AuditEntry).order_by(AuditEntry.id.desc())
    if limit is not None:
        query = query.limit(limit)
    return query.all()


class ChainError(Exception):
    """สายขาดที่แถวไหน เพราะอะไร"""

    def __init__(self, entry_id: int, reason: str) -> None:
        super().__init__(f"audit chain ขาดที่แถว id={entry_id}: {reason}")
        self.entry_id = entry_id
        self.reason = reason


def verify_chain() -> int:
    """เดินสายทั้งเส้น คืนจำนวนแถวที่ตรวจแล้ว — ไม่ผ่านให้ raise `ChainError`

    จุดเริ่มของสายรับได้สองแบบ: แถวปฐมกำเนิด (`prev_hash` เป็นศูนย์ล้วน)
    หรือแถวที่ต่อจากช่วงที่ purge ไปแล้ว ซึ่งมี checkpoint รับรองไว้

    **ความซื่อสัตย์กับข้อจำกัด:** ผ่านแปลว่า "แถวที่ยังอยู่ไม่ถูกแก้" เท่านั้น
    ไม่ได้แปลว่า "ไม่มีใครตัดประวัติทิ้ง" — คนที่คุมทั้ง purge job และฐานข้อมูล
    เขียน checkpoint ปลอมได้ การกันจริงต้องใช้ storage แบบ write-once ภายนอก
    ซึ่งเกินความจำเป็นของ scale นี้ (ADR 0014)
    """
    rows = db.session.query(AuditEntry).order_by(AuditEntry.id).all()
    anchors = {GENESIS_HASH}
    for row in rows:
        if row.event == CHECKPOINT_EVENT:
            last_purged = row.payload.get("last_purged_hash")
            if last_purged:
                anchors.add(str(last_purged))

    expected: str | None = None
    for row in rows:
        if expected is None:
            if row.prev_hash not in anchors:
                raise ChainError(row.id, "แถวแรกที่เหลืออยู่ไม่ต่อกับจุดกำเนิดหรือ checkpoint ใดเลย")
        elif row.prev_hash != expected:
            raise ChainError(row.id, "prev_hash ไม่ตรงกับ hash ของแถวก่อนหน้า")
        recomputed = compute_row_hash(
            created_at=row.created_at,
            event_name=row.event,
            actor_id=row.actor_id,
            source=row.source,
            request_id=row.request_id,
            table_name=row.table_name,
            row_id=row.row_id,
            changes=row.changes,
            prev_hash=row.prev_hash,
        )
        if recomputed != row.row_hash:
            raise ChainError(row.id, "เนื้อหาของแถวถูกแก้ (คำนวณ hash ใหม่แล้วไม่ตรง)")
        expected = row.row_hash
    return len(rows)
