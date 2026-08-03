"""ซองข้อความผิดพลาดของ API — **รูปเดียวทุกกรณี** (ดู ADR 0018)

```json
{"error": {"code": "todo_not_found", "message": "Task not found"}}
```

`code` เป็นภาษาเครื่องและเป็น**ส่วนหนึ่งของสัญญา** — client เขียนเงื่อนไขกับมันได้
ส่วน `message` เป็นภาษาคนไว้ให้มนุษย์อ่านตอน debug เปลี่ยนถ้อยคำเมื่อไหร่ก็ได้
(ข้อความที่มาจาก service ผ่าน gettext จึงเปลี่ยนตาม `Accept-Language` ด้วย
ส่วนข้อความจากชั้น validation ของ marshmallow เป็นภาษาอังกฤษเสมอ)

ที่ต้องบังคับให้เป็นรูปเดียวเพราะ client ที่ต้องเขียนโค้ดแยกสองแบบ ("ถ้ามี
`error` ก็อ่านแบบหนึ่ง ถ้ามี `errors` ก็อ่านอีกแบบ") จะเขียนถูกแค่แบบเดียว
แล้วอีกแบบจะกลายเป็นข้อผิดพลาดที่ถูกกลืนหายไปเงียบ ๆ
"""

from typing import Any

import marshmallow as ma
from flask import Response, jsonify
from werkzeug.exceptions import HTTPException

from app.services import ConflictError, NotFoundError, ServiceError, ValidationError

# ความล้มเหลวของโดเมน → status ที่ตรงความหมาย
# `NotFoundError` เป็น 404 ทั้งกรณี "ไม่มี" และ "ของคนอื่น" ตาม ADR 0004
STATUS_BY_ERROR = {
    NotFoundError: 404,
    ValidationError: 400,
    ConflictError: 409,
}
FALLBACK_STATUS = 400

# ข้อผิดพลาดระดับ HTTP ที่ไม่ได้มาจาก service ก็ต้องมี `code` ให้ client เทียบได้
# ไม่งั้นจะเหลือแค่เลข status ซึ่งบอกไม่ได้ว่า 400 ตัวนี้คือเรื่องอะไร
CODE_BY_STATUS = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    406: "not_acceptable",
    409: "conflict",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
}
UNKNOWN_CODE = "http_error"


class ErrorDetailSchema(ma.Schema):
    """เนื้อในของซอง — มีไว้ให้ spec อธิบายได้ ไม่ได้ใช้ dump จริง"""

    code = ma.fields.String(metadata={"description": "ชื่อความผิดพลาดแบบคงที่ ใช้เทียบในโค้ดได้"})
    message = ma.fields.String(metadata={"description": "คำอธิบายสำหรับคนอ่าน"})
    field = ma.fields.String(allow_none=True, metadata={"description": "ฟิลด์ที่เป็นต้นเหตุ ถ้าระบุได้"})
    errors = ma.fields.Dict(metadata={"description": "ข้อผิดพลาดรายฟิลด์จากชั้น validation"})


class ErrorSchema(ma.Schema):
    """ซองชั้นนอก — ทุกคำตอบที่ไม่สำเร็จหน้าตาแบบนี้เสมอ"""

    error = ma.fields.Nested(ErrorDetailSchema)


def _envelope(
    payload: dict[str, Any], status: int, headers: dict[str, str] | None = None
) -> tuple[Response, int, dict[str, str]]:
    return jsonify({"error": payload}), status, headers or {}


def service_error_response(error: ServiceError) -> tuple[Response, int, dict[str, str]]:
    """`ServiceError` → JSON — service เป็นคนตัดสินว่าอะไรผิด adapter แค่แปลภาษา"""
    payload: dict[str, Any] = {"code": error.code, "message": error.message}
    if error.field:
        payload["field"] = error.field
    return _envelope(payload, STATUS_BY_ERROR.get(type(error), FALLBACK_STATUS))


def http_error_response(error: HTTPException) -> tuple[Response, int, dict[str, str]]:
    """`HTTPException` → JSON ซองเดียวกัน

    `error.data` คือของที่ `abort()` ของ webargs/flask-smorest แนบมา — ข้อความ
    เพิ่มเติม, ข้อผิดพลาดรายฟิลด์ (`messages`) และ header ที่ต้องติดไปด้วย
    (เช่น `WWW-Authenticate` ของ 401)
    """
    status = error.code or 500
    payload: dict[str, Any] = {
        "code": CODE_BY_STATUS.get(status, UNKNOWN_CODE),
        "message": error.description,
    }
    data = getattr(error, "data", None) or {}
    if "message" in data:
        payload["message"] = data["message"]
    # webargs เรียกมันว่า `messages` ส่วน flask-smorest เรียก `errors` — รับทั้งคู่
    # แล้วส่งออกด้วยชื่อเดียว ไม่งั้น client ต้องรู้ว่าใครเป็นคน abort
    field_errors = data.get("errors") or data.get("messages")
    if field_errors:
        payload["errors"] = field_errors
    return _envelope(payload, status, data.get("headers"))
