"""รูปร่างของข้อมูลที่ `/api/v1` รับและส่ง (marshmallow)

**เวลาทุกตัวในสัญญานี้เป็นเวลาท้องถิ่นของเจ้าของข้อมูล แบบไม่มี offset**
เหมือนที่ฟอร์ม HTML ส่งมา (`<input type="datetime-local">`) และเหมือนที่
service รับ — ดู `app/tz.py` ว่าทำไมทั้งระบบตกลงกันแบบนี้ ค่าที่มี offset
ติดมาถูกปฏิเสธ ไม่ใช่แปลงให้ เพราะ `+07:00` ที่ส่งมาโดยคนที่ตั้ง timezone
เป็น Asia/Tokyo แปลว่าอะไรไม่มีใครตอบได้

schema สำหรับ "แก้" (`*UpdateSchema`) **ไม่มี `load_default`** โดยตั้งใจ —
marshmallow จะคืนเฉพาะคีย์ที่ client ส่งมาจริง ทำให้ PATCH แยก "ไม่ได้ส่ง
ฟิลด์นี้มา" ออกจาก "ส่ง null มาเพื่อล้างค่า" ได้ ซึ่งเป็นความต่างที่
`todos_service.update_todo()` ต้องการ
"""

from typing import Any

import marshmallow as ma

from app import tz
from app.filters import (
    DEFAULT_UPCOMING,
    STATUS_FILTERS,
    UPCOMING_CHOICES,
    WHEN_FILTERS,
)
from app.services import categories as categories_service

# ข้อความของชั้นนี้เป็นภาษาอังกฤษตายตัว ไม่ผ่าน gettext — เป็นคำอธิบายเชิงเทคนิค
# ที่ส่งให้คนเขียน client อ่านตอน debug ไม่ใช่ข้อความบน UI ของผู้ใช้ปลายทาง
NOT_A_STRING = "Expected an ISO 8601 date or datetime string."
BAD_DATETIME = "Use local time without a UTC offset, e.g. 2026-09-01T16:00."


class LocalDateTime(ma.fields.Field):
    """เวลาท้องถิ่นของเจ้าของข้อมูล ISO 8601 ไม่มี offset

    ย่อยด้วย `tz.parse_naive()` ตัวเดียวกับที่ฟอร์ม HTML ใช้ ไม่ใช่ตัวย่อยของ
    marshmallow เอง — ทางเข้าข้อมูลสองทางที่ย่อยเวลาคนละแบบคือบั๊กที่รอเกิด
    """

    # ลายเซ็นสองตัวนี้เป็นของ marshmallow ตัดอาร์กิวเมนต์ที่ไม่ได้ใช้ออกไม่ได้
    def _serialize(self, value: Any, attr: str | None, obj: Any, **kwargs: Any) -> str | None:  # noqa: ARG002 - required by interface
        if value is None:
            return None
        return str(value.isoformat())

    def _deserialize(self, value: Any, attr: str | None, data: Any, **kwargs: Any) -> Any:  # noqa: ARG002 - required by interface
        # ไม่ต้องเช็ค None เอง — marshmallow จัดการ `allow_none` ให้ก่อนถึงตรงนี้แล้ว
        if not isinstance(value, str):
            raise ma.ValidationError(NOT_A_STRING)
        try:
            return tz.parse_naive(value)
        except ValueError as bad:
            raise ma.ValidationError(BAD_DATETIME) from bad


# ---------------------------------------------------------------- งาน


class TodoSchema(ma.Schema):
    """งานหนึ่งรายการตามที่ API ส่งออก"""

    id = ma.fields.Integer(dump_only=True)
    title = ma.fields.String(dump_only=True)
    is_done = ma.fields.Boolean(dump_only=True)
    category_id = ma.fields.Integer(dump_only=True, allow_none=True)
    start_date = LocalDateTime(dump_only=True, attribute="start_local", allow_none=True)
    due_date = LocalDateTime(dump_only=True, attribute="due_local", allow_none=True)
    # สองตัวนี้คำนวณจาก due_date ทุกครั้งที่อ่าน ไม่ได้เก็บไว้ — client จึงไม่ต้อง
    # เขียนตรรกะ "เลยกำหนดหรือยัง" ซ้ำ (และไม่ต้องเดาว่าใช้ timezone ไหนเทียบ)
    is_overdue = ma.fields.Boolean(dump_only=True)
    is_due_today = ma.fields.Boolean(dump_only=True)
    # สัญญาณ impact ของ org graph (ADR 0049) — เพิ่มแบบ additive ตาม ADR 0018
    # ค่าจริงถูกติดใส่ instance โดย view (คำนวณเป็นชุดครั้งเดียว ไม่ใช่ต่อแถว)
    is_at_risk = ma.fields.Boolean(dump_only=True, dump_default=False)
    created_at = LocalDateTime(dump_only=True, attribute="created_local")
    updated_at = LocalDateTime(dump_only=True, attribute="updated_local")


class TodoCreateSchema(ma.Schema):
    """ข้อมูลสำหรับสร้างงานใหม่ — ต้องมีชื่อ ที่เหลือไม่ใส่ก็ได้"""

    title = ma.fields.String(required=True)
    category_id = ma.fields.Integer(load_default=None, allow_none=True)
    start_date = LocalDateTime(load_default=None, allow_none=True)
    due_date = LocalDateTime(load_default=None, allow_none=True)


class TodoUpdateSchema(ma.Schema):
    """แก้เฉพาะฟิลด์ที่ส่งมา — ฟิลด์ที่ไม่ส่งมาไม่ถูกแตะ (ดู docstring ของโมดูล)"""

    title = ma.fields.String()
    category_id = ma.fields.Integer(allow_none=True)
    start_date = LocalDateTime(allow_none=True)
    due_date = LocalDateTime(allow_none=True)
    is_done = ma.fields.Boolean()


class TodoQuerySchema(ma.Schema):
    """ตัวกรองใน query string — ชื่อและความหมายตรงกับของหน้าเว็บทุกตัว

    ค่าที่ไม่รู้จักใน `status`/`when`/`within` **ตกกลับเป็นค่าเริ่มต้นเงียบ ๆ**
    เหมือนฝั่ง HTML (`FilterSpec.from_params`) จึงประกาศเป็น String/Integer
    เปล่า ๆ ไม่ใส่ validator — ให้ตัว normalise ที่เดียวเป็นคนตัดสิน ไม่งั้น
    กติกาจะมีสองชุดที่ต้องคอยทำให้ตรงกัน
    """

    status = ma.fields.String(
        load_default="all", metadata={"description": f"หนึ่งใน {list(STATUS_FILTERS)}"}
    )
    category = ma.fields.String(
        load_default="", metadata={"description": "id ของหมวด หรือ 'none' = งานที่ไม่มีหมวด"}
    )
    when = ma.fields.String(
        load_default="all", metadata={"description": f"หนึ่งใน {list(WHEN_FILTERS)}"}
    )
    within = ma.fields.Integer(
        load_default=DEFAULT_UPCOMING,
        metadata={"description": f"นาทีของช่วง upcoming หนึ่งใน {list(UPCOMING_CHOICES)}"},
    )
    date_from = ma.fields.String(load_default="", metadata={"description": "ใช้กับ when=range"})
    date_to = ma.fields.String(load_default="", metadata={"description": "ใช้กับ when=range"})


# ---------------------------------------------------------------- หมวด


class CategorySchema(ma.Schema):
    id = ma.fields.Integer(dump_only=True)
    name = ma.fields.String(dump_only=True)
    # จำนวนงานที่ยังอยู่ในหมวด — ตอบคำถาม "ลบหมวดนี้ได้ไหม" ได้โดยไม่ต้องลองลบ
    # (นับด้วย query ต่อหนึ่งหมวด ยอมรับได้เพราะหมวดของคนเดียวมีไม่กี่อัน)
    task_count = ma.fields.Method(
        "_task_count",
        metadata={"type": "integer", "description": "จำนวนงานที่ยังอยู่ในหมวดนี้"},
    )

    def _task_count(self, category: Any) -> int:
        return categories_service.task_count(category)


class CategoryWriteSchema(ma.Schema):
    """หมวดมีแค่ชื่อ สร้างกับเปลี่ยนชื่อจึงใช้รูปเดียวกัน"""

    name = ma.fields.String(required=True)


# ---------------------------------------------------------------- token


class TokenSchema(ma.Schema):
    """ใบที่ออกไปแล้ว — **ไม่มีตัวความลับ** ทั้งในรูปเดิมและรูป hash"""

    id = ma.fields.Integer(dump_only=True)
    name = ma.fields.String(dump_only=True)
    created_at = LocalDateTime(dump_only=True, attribute="created_local", allow_none=True)
    expires_at = LocalDateTime(dump_only=True, attribute="expires_local", allow_none=True)
    is_expired = ma.fields.Boolean(dump_only=True)
