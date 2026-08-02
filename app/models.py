from datetime import date, datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


def _utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)
    # ภาษาที่ผู้ใช้เลือกไว้ NULL = ยังไม่เคยเลือก ให้ไปดู Accept-Language แทน
    locale = db.Column(db.String(8), nullable=True)
    # ธีมที่ผู้ใช้เลือกไว้ 'light' หรือ 'dark'
    # NULL = ตามระบบ (ปล่อยให้ prefers-color-scheme ตัดสิน)
    theme = db.Column(db.String(8), nullable=True)

    categories = db.relationship(
        "Category", back_populates="user", cascade="all, delete-orphan"
    )
    todos = db.relationship(
        "Todo", back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.id} {self.username!r}>"


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )

    user = db.relationship("User", back_populates="categories")
    todos = db.relationship("Todo", back_populates="category")

    # ชื่อหมวดห้ามซ้ำ แต่ซ้ำข้าม user ได้
    __table_args__ = (
        db.UniqueConstraint("user_id", "name", name="uq_category_user_name"),
    )

    def __repr__(self):
        return f"<Category {self.id} {self.name!r}>"


class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    done = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)
    # เวลาท้องถิ่นแบบ naive — ตรงกับที่ <input type="datetime-local"> ส่งมา
    # ไม่แปลงเป็น UTC เพราะจะทำให้ถูกต้องต้องรู้ timezone ของผู้ใช้แต่ละคน
    # ต่างจาก created_at/updated_at ที่เป็น UTC เพราะเป็นเวลาของระบบ ไม่ใช่ของคน
    due_date = db.Column(db.DateTime, nullable=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )
    # ลบหมวดแล้ว todo ไม่หาย แค่กลับไปเป็น "ไม่มีหมวด"
    category_id = db.Column(
        db.Integer, db.ForeignKey("category.id", ondelete="SET NULL"), nullable=True
    )

    user = db.relationship("User", back_populates="todos")
    category = db.relationship("Category", back_populates="todos")

    @property
    def is_overdue(self):
        """เลยกำหนดแล้วหรือยัง — งานที่ทำเสร็จแล้วไม่นับว่าเลยกำหนด

        เทียบกับเวลาท้องถิ่นของเครื่องที่รัน server (ไม่ใช่ UTC) ให้ตรงกับ
        ค่าที่ผู้ใช้กรอกเข้ามา
        """
        if self.done or self.due_date is None:
            return False
        return self.due_date < datetime.now()

    @property
    def is_due_today(self):
        """ครบกำหนดภายในวันนี้ (และยังไม่เลยเวลา)"""
        if self.done or self.due_date is None or self.is_overdue:
            return False
        return self.due_date.date() == date.today()

    def __repr__(self):
        return f"<Todo {self.id} {self.title!r} done={self.done}>"
