from datetime import UTC, datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, tz


def _utcnow():
    return datetime.now(UTC)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)
    # ภาษาที่ผู้ใช้เลือกไว้ NULL = ยังไม่เคยเลือก ให้ไปดู Accept-Language แทน
    locale = db.Column(db.String(8), nullable=True)
    # ชื่อชุดสีที่เลือก (ดู config.THEMES) NULL = ใช้ชุดเริ่มต้น
    theme = db.Column(db.String(32), nullable=True)
    # ระดับความสว่าง 'light' / 'dark' / 'auto'
    # NULL = ยังไม่เคยเลือก ให้ใช้ค่าเริ่มต้น (auto)
    mode = db.Column(db.String(8), nullable=True)
    # timezone ของผู้ใช้ (ชื่อ IANA เช่น "Asia/Bangkok")
    # ปล่อย NULL คือใช้ค่าเริ่มต้นของแอป
    timezone_name = db.Column(db.String(64), nullable=True)
    first_name = db.Column(db.String(80), nullable=True)
    last_name = db.Column(db.String(80), nullable=True)

    categories = db.relationship("Category", back_populates="user", cascade="all, delete-orphan")
    todos = db.relationship("Todo", back_populates="user", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        """ชื่อ-นามสกุลเท่าที่กรอกไว้ ไม่ได้กรอกเลยก็คืนค่าว่าง"""
        return " ".join(filter(None, (self.first_name, self.last_name))).strip()

    @property
    def display_name(self):
        """ชื่อที่เอาไปแสดงบนหน้าจอ — ยังไม่กรอกชื่อจริงก็ใช้ username ไปก่อน"""
        return self.full_name or self.username

    def __repr__(self):
        return f"<User {self.id} {self.username!r}>"


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

    user = db.relationship("User", back_populates="categories")
    todos = db.relationship("Todo", back_populates="category")

    # ชื่อหมวดห้ามซ้ำ แต่ซ้ำข้าม user ได้
    __table_args__ = (db.UniqueConstraint("user_id", "name", name="uq_category_user_name"),)

    def __repr__(self):
        return f"<Category {self.id} {self.name!r}>"


class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    done = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)
    # **UTC แบบ naive** เหมือน created_at/updated_at
    # เวลาที่ผู้ใช้กรอกเข้ามาเป็นเวลาท้องถิ่นของเขา ต้องผ่าน tz.to_utc() ก่อนเก็บ
    # และผ่าน tz.to_local() ก่อนแสดง — ดู app/tz.py
    start_date = db.Column(db.DateTime, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    # ลบหมวดแล้ว todo ไม่หาย แค่กลับไปเป็น "ไม่มีหมวด"
    category_id = db.Column(
        db.Integer, db.ForeignKey("category.id", ondelete="SET NULL"), nullable=True
    )

    user = db.relationship("User", back_populates="todos")
    category = db.relationship("Category", back_populates="todos")

    @property
    def _tz_name(self):
        return self.user.timezone_name if self.user else None

    @property
    def due_local(self):
        """กำหนดส่งในเวลาท้องถิ่นของเจ้าของงาน — ใช้ตอนแสดงผลเท่านั้น"""
        return tz.to_local(self.due_date, self._tz_name)

    @property
    def start_local(self):
        """วันเริ่มในเวลาท้องถิ่นของเจ้าของงาน"""
        return tz.to_local(self.start_date, self._tz_name)

    @property
    def is_overdue(self):
        """เลยกำหนดแล้วหรือยัง — งานที่ทำเสร็จแล้วไม่นับว่าเลยกำหนด

        เทียบกันใน UTC ทั้งคู่ ผลลัพธ์จึงไม่ขึ้นกับ timezone ของใครเลย
        """
        if self.done or self.due_date is None:
            return False
        return self.due_date < tz.now_utc()

    @property
    def is_due_today(self):
        """ครบกำหนดภายในวันนี้ (และยังไม่เลยเวลา)

        "วันนี้" ต้องเป็นวันตามเวลาท้องถิ่นของเจ้าของงาน ไม่ใช่ตาม UTC
        ไม่งั้นคนที่อยู่คนละซีกโลกจะเห็นวันเหลื่อมกัน
        """
        if self.done or self.due_date is None or self.is_overdue:
            return False
        today_local = tz.to_local(tz.now_utc(), self._tz_name).date()
        return self.due_local.date() == today_local

    def __repr__(self):
        return f"<Todo {self.id} {self.title!r} done={self.done}>"
