"""SQLAlchemy models — 2.0 typed style (`Mapped[]` + `mapped_column`)

**ชื่อตารางขึ้นต้น `tdl_` ทุกตัว** (ดู docs/STANDARDS.md ข้อ 1.1) เพื่อให้
core กับ plugin แยกกันได้ในฐานข้อมูลเดียว และเพื่อให้ `user` ไม่ชนกับ
reserved word ของ PostgreSQL/Oracle/MSSQL อีกต่อไป

ชื่อ constraint ทั้งหมดมาจาก `NAMING_CONVENTION` ใน `app/__init__.py`
ไม่ใช่ชื่อ auto ของ DB แต่ละยี่ห้อ
"""

from datetime import UTC, datetime

from flask_login import UserMixin
from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, tz
from app.db_types import UTCDateTime
from app.soft_delete import SoftDeleteMixin

# ค่าที่ใส่แทน hash เมื่อปิดบัญชีหรือเพิกถอน token — ไม่ใช่รูปแบบ hash ที่ถูกต้อง
# จึงเทียบกับความลับใดก็ไม่ผ่าน (ธรรมเนียมเดียวกับ /etc/shadow ของ unix)
DISABLED_SECRET = "!"  # noqa: S105  ไม่ใช่ความลับ แต่เป็นค่าที่แปลว่า "ใช้ไม่ได้"


def _utcnow() -> datetime:
    return datetime.now(UTC)


class User(UserMixin, SoftDeleteMixin, db.Model):
    """บัญชีผู้ใช้ — ไม่มีหน้าสมัครสมาชิก สร้างผ่าน `flask create-user` เท่านั้น"""

    __tablename__ = "tdl_user"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=_utcnow)
    # ภาษาที่ผู้ใช้เลือกไว้ NULL = ยังไม่เคยเลือก ให้ไปดู Accept-Language แทน
    locale: Mapped[str | None] = mapped_column(String(8))
    # ไอดีของ theme plugin ที่เลือก NULL = ใช้ธีม core
    theme: Mapped[str | None] = mapped_column(String(32))
    # ระดับความสว่าง 'light' / 'dark' / 'auto'
    # NULL = ยังไม่เคยเลือก ให้ใช้ค่าเริ่มต้น (auto)
    mode: Mapped[str | None] = mapped_column(String(8))
    # timezone ของผู้ใช้ (ชื่อ IANA เช่น "Asia/Bangkok")
    # ปล่อย NULL คือใช้ค่าเริ่มต้นของแอป
    timezone_name: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(80))
    last_name: Mapped[str | None] = mapped_column(String(80))
    # บทบาท: 'user' หรือ 'admin' (ชุดปิด ตรวจใน app/services/roles.py — ADR 0022)
    # **ไม่ nullable และมี server_default** เพราะแถวที่มีอยู่ก่อน migration
    # ต้องได้ค่าที่ชัดเจน ไม่ใช่ NULL ที่แปลว่า "ไม่รู้ว่ามีสิทธิ์แค่ไหน"
    role: Mapped[str] = mapped_column(String(16), default="user", server_default="user")
    # เวลาที่ PII ถูกล้างจริง (แถวยังอยู่เป็น tombstone ให้ audit อ้างถึงได้)
    # ดู docs/DATA-CLASSIFICATION.md — ต่างจาก deleted_at ที่แปลว่า 'ปิดบัญชีแล้ว'
    purged_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    # ระงับการใช้ชั่วคราว (PDPA ม.34) — ห้าม login และ session เดิมถูกตัด
    # แต่ข้อมูลไม่ถูกแตะ ต่างจาก deleted_at ตรงที่ตั้งใจให้ย้อนกลับได้เสมอ
    suspended_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    categories: Mapped[list["Category"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    todos: Mapped[list["Todo"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    api_tokens: Mapped[list["ApiToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        """เก็บ hash ของรหัสผ่านที่ normalize แล้ว (ดู `app/services/passwords.py`)

        **การ normalize อยู่ที่นี่ ไม่ใช่ที่ผู้เรียก** เพราะต้องเกิดคู่กับ
        `check_password()` เสมอ ถ้าปล่อยให้ผู้เรียกจำเอง วันที่มีใครลืมสักทาง
        ผู้ใช้ที่ตั้งรหัสด้วยอักขระ unicode จะ login ไม่ได้ทั้งที่พิมพ์เหมือนเดิม
        """
        from app.services.passwords import normalize

        self.password_hash = generate_password_hash(normalize(password))

    def check_password(self, password: str) -> bool:
        from app.services.passwords import normalize

        # เช็คก่อนส่งเข้า werkzeug เพราะค่า sentinel ไม่ใช่ hash ที่ parse ได้
        if self.password_hash == DISABLED_SECRET:
            return False
        return check_password_hash(self.password_hash, normalize(password))

    def disable_password(self) -> None:
        """ล้าง credential ทิ้ง — ชั้น C1 ไม่มีเหตุผลให้เก็บต่อเมื่อบัญชีถูกปิด

        ทำทันทีที่ soft delete ไม่รอ grace 30 วัน (ดู docs/DATA-CLASSIFICATION.md)
        กู้บัญชีคืนได้ แต่ต้องตั้งรหัสใหม่
        """
        self.password_hash = DISABLED_SECRET

    @property
    def is_admin(self) -> bool:
        """ใช้ใน template เพื่อตัดสินว่าจะโชว์เมนูของผู้ดูแลไหม

        **การโชว์/ไม่โชว์เมนูไม่ใช่การกันสิทธิ์** ตัวที่กันจริงคือ
        `roles.require_admin()` ที่อยู่ใน service (หลักเดียวกับปุ่มลบหมวด
        ที่ถูก disable ไว้ แต่การกันจริงอยู่ที่ route)
        """
        from app.services.roles import is_admin

        return is_admin(self)

    @property
    def full_name(self) -> str:
        """ชื่อ-นามสกุลเท่าที่กรอกไว้ ไม่ได้กรอกเลยก็คืนค่าว่าง"""
        return " ".join(filter(None, (self.first_name, self.last_name))).strip()

    @property
    def display_name(self) -> str:
        """ชื่อที่เอาไปแสดงบนหน้าจอ — ยังไม่กรอกชื่อจริงก็ใช้ username ไปก่อน"""
        return self.full_name or self.username

    def __repr__(self) -> str:
        return f"<User {self.id} {self.username!r}>"


class ApiToken(SoftDeleteMixin, db.Model):
    """personal access token สำหรับเรียก `/api/v1` (Phase 3 — ดู ADR 0017)

    **เก็บเฉพาะ hash ของความลับ ตัวความลับจริงแสดงครั้งเดียวตอนสร้าง**
    ทำหายแล้วออกใบใหม่ ไม่มีทาง "ดูอีกครั้ง" — เป็นข้อจำกัดที่ตั้งใจ ไม่ใช่ของที่ยังไม่ได้ทำ

    ไม่มีคอลัมน์ `last_used_at` โดยตั้งใจเช่นกัน: การอัปเดตทุกครั้งที่เรียก API
    แปลว่ามี write หนึ่งครั้งต่อหนึ่ง request ซึ่งจะไปโผล่เป็นแถว audit หนึ่งแถว
    ต่อหนึ่ง request ด้วย (event `after_flush` ดักทุก write) — กลบสายหลักฐาน
    ด้วยเสียงรบกวน คำถาม "token นี้ถูกใช้ครั้งล่าสุดเมื่อไหร่" ตอบจาก log
    ที่มี `token_id` อยู่แล้ว (ชั้น C6 อายุ 90 วัน)
    """

    __tablename__ = "tdl_api_token"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("tdl_user.id"), index=True)
    # ชื่อที่ผู้ใช้ตั้งไว้ให้ตัวเองจำได้ว่าใบไหนอยู่เครื่องไหน
    name: Mapped[str] = mapped_column(String(80))
    # sha256 ของความลับ (hex 64 ตัว) — ดูเหตุผลที่ไม่ใช้ scrypt ใน app/services/tokens.py
    token_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=_utcnow)
    # NULL = ไม่มีวันหมดอายุ (ต้องขอเป็นพิเศษ ค่าเริ่มต้นคือมีอายุ)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    user: Mapped["User"] = relationship(back_populates="api_tokens")

    @property
    def _tz_name(self) -> str | None:
        return self.user.timezone_name if self.user else None

    @property
    def created_local(self) -> datetime | None:
        """เวลาที่ออกใบ ในเวลาท้องถิ่นของเจ้าของ — ใช้ตอนแสดงผลเท่านั้น"""
        return tz.to_local(self.created_at, self._tz_name)

    @property
    def expires_local(self) -> datetime | None:
        """วันหมดอายุในเวลาท้องถิ่นของเจ้าของ"""
        return tz.to_local(self.expires_at, self._tz_name)

    @property
    def is_expired(self) -> bool:
        """หมดอายุแล้วหรือยัง — ใบที่ไม่ได้ตั้งวันหมดอายุไม่มีวันหมด"""
        return self.expires_at is not None and self.expires_at <= tz.now_utc()

    @property
    def is_usable(self) -> bool:
        """ยังใช้ยืนยันตัวตนได้ไหม — ถูกเพิกถอน/หมดอายุแล้วใช้ไม่ได้

        `not self.is_deleted` **ซ้ำซ้อนโดยตั้งใจ** เหมือน `_expired()` ใน purge.py:
        ตัวกรอง soft delete ซ่อนแถวที่ถูกเพิกถอนไปตั้งแต่ตอน query แล้ว และ
        `revoke()` ยังล้าง hash ทิ้งอีกชั้น การถอดเงื่อนไขนี้ออกจึงไม่ทำให้เทสต์ตัวไหน
        แดง (equivalent mutant — ตรวจแล้ว บันทึกไว้กันสับสนรอบหน้า) แต่เก็บไว้
        เพราะผู้เรียกที่หยิบแถวมาด้วย `INCLUDE_DELETED` ต้องได้คำตอบที่ถูกด้วย
        """
        return not self.is_deleted and not self.is_expired

    def disable(self) -> None:
        """ล้าง hash ทิ้งตอนเพิกถอน — ชั้น C1 ไม่มีเหตุผลให้เก็บต่อ

        แถวยังอยู่เพื่อให้ผู้ใช้เห็นว่าเคยมีใบนี้ (และ audit อ้าง `row_id` ได้)
        แต่ค่าที่เหลือเทียบกับความลับใดก็ไม่ผ่าน
        """
        self.token_hash = DISABLED_SECRET

    def __repr__(self) -> str:
        return f"<ApiToken {self.id} {self.name!r} user={self.user_id}>"


class Category(SoftDeleteMixin, db.Model):
    """หมวดของงาน — ลบได้เฉพาะตอนไม่มีงานอยู่เลย (ดู routes)"""

    __tablename__ = "tdl_category"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    user_id: Mapped[int] = mapped_column(ForeignKey("tdl_user.id"), index=True)

    user: Mapped["User"] = relationship(back_populates="categories")
    todos: Mapped[list["Todo"]] = relationship(back_populates="category")

    # ชื่อหมวดห้ามซ้ำ แต่ซ้ำข้าม user ได้
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_category_user_name"),)

    def __repr__(self) -> str:
        return f"<Category {self.id} {self.name!r}>"


class Todo(SoftDeleteMixin, db.Model):
    """งานหนึ่งรายการ — เวลาทั้งหมดเก็บเป็น naive UTC (ดู app/tz.py)"""

    __tablename__ = "tdl_todo"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    is_done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=_utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, default=_utcnow, onupdate=_utcnow
    )
    # **UTC แบบ naive** เหมือน created_at/updated_at
    # เวลาที่ผู้ใช้กรอกเข้ามาเป็นเวลาท้องถิ่นของเขา ต้องผ่าน tz.to_utc() ก่อนเก็บ
    # และผ่าน tz.to_local() ก่อนแสดง — ดู app/tz.py
    start_date: Mapped[datetime | None] = mapped_column(UTCDateTime)
    due_date: Mapped[datetime | None] = mapped_column(UTCDateTime)
    user_id: Mapped[int] = mapped_column(ForeignKey("tdl_user.id"), index=True)
    # ลบหมวดแล้ว todo ไม่หาย แค่กลับไปเป็น "ไม่มีหมวด"
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("tdl_category.id", ondelete="SET NULL")
    )

    user: Mapped["User"] = relationship(back_populates="todos")
    category: Mapped["Category | None"] = relationship(back_populates="todos")

    @property
    def _tz_name(self) -> str | None:
        return self.user.timezone_name if self.user else None

    @property
    def due_local(self) -> datetime | None:
        """กำหนดส่งในเวลาท้องถิ่นของเจ้าของงาน — ใช้ตอนแสดงผลเท่านั้น"""
        return tz.to_local(self.due_date, self._tz_name)

    @property
    def start_local(self) -> datetime | None:
        """วันเริ่มในเวลาท้องถิ่นของเจ้าของงาน"""
        return tz.to_local(self.start_date, self._tz_name)

    @property
    def created_local(self) -> datetime | None:
        """เวลาที่สร้าง ในเวลาท้องถิ่นของเจ้าของงาน (API v1 ส่งเวลาท้องถิ่นทุกตัว)"""
        return tz.to_local(self.created_at, self._tz_name)

    @property
    def updated_local(self) -> datetime | None:
        """เวลาที่แก้ล่าสุด ในเวลาท้องถิ่นของเจ้าของงาน"""
        return tz.to_local(self.updated_at, self._tz_name)

    @property
    def is_overdue(self) -> bool:
        """เลยกำหนดแล้วหรือยัง — งานที่ทำเสร็จแล้วไม่นับว่าเลยกำหนด

        เทียบกันใน UTC ทั้งคู่ ผลลัพธ์จึงไม่ขึ้นกับ timezone ของใครเลย
        """
        if self.is_done or self.due_date is None:
            return False
        return self.due_date < tz.now_utc()

    @property
    def is_due_today(self) -> bool:
        """ครบกำหนดภายในวันนี้ (และยังไม่เลยเวลา)

        "วันนี้" ต้องเป็นวันตามเวลาท้องถิ่นของเจ้าของงาน ไม่ใช่ตาม UTC
        ไม่งั้นคนที่อยู่คนละซีกโลกจะเห็นวันเหลื่อมกัน
        """
        if self.is_done or self.due_date is None or self.is_overdue:
            return False
        today_local = tz.to_local(tz.now_utc(), self._tz_name).date()
        # เรียก to_local กับ due_date ตรง ๆ (ไม่ผ่าน due_local) เพราะเช็ค None
        # ไปแล้วข้างบน overload จึงการันตีว่าได้ datetime ไม่ใช่ datetime | None
        return tz.to_local(self.due_date, self._tz_name).date() == today_local

    def __repr__(self) -> str:
        return f"<Todo {self.id} {self.title!r} is_done={self.is_done}>"
