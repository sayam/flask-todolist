"""SQLAlchemy models — 2.0 typed style (`Mapped[]` + `mapped_column`)

**ชื่อตารางขึ้นต้น `tdl_` ทุกตัว** (ดู docs/STANDARDS.md ข้อ 1.1) เพื่อให้
core กับ plugin แยกกันได้ในฐานข้อมูลเดียว และเพื่อให้ `user` ไม่ชนกับ
reserved word ของ PostgreSQL/Oracle/MSSQL อีกต่อไป

ชื่อ constraint ทั้งหมดมาจาก `NAMING_CONVENTION` ใน `app/__init__.py`
ไม่ใช่ชื่อ auto ของ DB แต่ละยี่ห้อ
"""

from datetime import UTC, datetime

from flask_login import UserMixin
from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, tz
from app.soft_delete import SoftDeleteMixin

# ค่าที่ใส่แทน hash เมื่อปิดบัญชี — ไม่ใช่รูปแบบ hash ที่ถูกต้อง จึงเทียบกับ
# รหัสผ่านใดก็ไม่ผ่าน (ธรรมเนียมเดียวกับ /etc/shadow ของ unix)
DISABLED_PASSWORD = "!"  # noqa: S105  ไม่ใช่รหัสผ่าน แต่เป็นค่าที่แปลว่า "ใช้ไม่ได้"


def _utcnow() -> datetime:
    return datetime.now(UTC)


class User(UserMixin, SoftDeleteMixin, db.Model):
    """บัญชีผู้ใช้ — ไม่มีหน้าสมัครสมาชิก สร้างผ่าน `flask create-user` เท่านั้น"""

    __tablename__ = "tdl_user"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=_utcnow)
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
    # เวลาที่ PII ถูกล้างจริง (แถวยังอยู่เป็น tombstone ให้ audit อ้างถึงได้)
    # ดู docs/DATA-CLASSIFICATION.md — ต่างจาก deleted_at ที่แปลว่า 'ปิดบัญชีแล้ว'
    purged_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)

    categories: Mapped[list["Category"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    todos: Mapped[list["Todo"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        # เช็คก่อนส่งเข้า werkzeug เพราะค่า sentinel ไม่ใช่ hash ที่ parse ได้
        if self.password_hash == DISABLED_PASSWORD:
            return False
        return check_password_hash(self.password_hash, password)

    def disable_password(self) -> None:
        """ล้าง credential ทิ้ง — ชั้น C1 ไม่มีเหตุผลให้เก็บต่อเมื่อบัญชีถูกปิด

        ทำทันทีที่ soft delete ไม่รอ grace 30 วัน (ดู docs/DATA-CLASSIFICATION.md)
        กู้บัญชีคืนได้ แต่ต้องตั้งรหัสใหม่
        """
        self.password_hash = DISABLED_PASSWORD

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
    created_at: Mapped[datetime | None] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
    # **UTC แบบ naive** เหมือน created_at/updated_at
    # เวลาที่ผู้ใช้กรอกเข้ามาเป็นเวลาท้องถิ่นของเขา ต้องผ่าน tz.to_utc() ก่อนเก็บ
    # และผ่าน tz.to_local() ก่อนแสดง — ดู app/tz.py
    start_date: Mapped[datetime | None] = mapped_column(DateTime)
    due_date: Mapped[datetime | None] = mapped_column(DateTime)
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
