"""โรงงานสร้าง blueprint ของ API — ทุกตัวได้ด่านและซองข้อความผิดพลาดชุดเดียวกัน

blueprint ที่สร้างเองทีละตัวแล้วค่อยไล่ผูก `before_request` / error handler
เองคือ blueprint ที่วันหนึ่งจะมีตัวที่ลืมผูก — และตัวที่ลืมจะเป็นตัวที่เปิดโล่ง
โดยไม่มีอะไรฟ้อง จึงบังคับให้ทางเดียวที่สร้าง blueprint ของ API ได้คือทางนี้
"""

from flask import current_app, g
from flask_limiter.util import get_remote_address
from flask_login import current_user
from flask_smorest import Blueprint
from werkzeug.exceptions import HTTPException

from app import limiter
from app.api.auth import require_api_token
from app.api.errors import http_error_response, service_error_response
from app.services import ServiceError

API_PREFIX = "/api/v1"


def _quota_key() -> str:
    """กุญแจของโควตา — **ต่อใบ token ไม่ใช่ต่อ IP** (P5-08)

    client ของ API เป็นเครื่อง ซึ่งมักออกเน็ตผ่าน IP เดียวกันทั้งองค์กร (NAT,
    egress ของ cloud) การนับต่อ IP จึงลงโทษผิดคน: client ที่ยิงถี่ตัวเดียวกิน
    โควตาของทุกคนที่อยู่หลัง gateway เดียวกัน ส่วนคนที่มี IP เยอะเดินผ่านสบาย
    ใบ token คือตัวตนที่ตรงกับ *ผู้ใช้จริง* ของ API มากที่สุดที่เรามี

    **ตกกลับไปนับต่อ IP เมื่อยังไม่มี token ที่ใช้ได้** ไม่งั้นคำขอที่จะได้ 401
    อยู่แล้วจะยิงได้ไม่จำกัด — ด่าน 401 ถูกกว่าการทำงานจริงก็จริง แต่ไม่ฟรี

    หมายเหตุเรื่องลำดับ: ตัวนี้ถูกเรียกจาก `before_request` ระดับแอปของ
    Flask-Limiter ซึ่งทำงาน **ก่อน** `require_api_token` ของ blueprint
    การแตะ `current_user` ตรงนี้จึงเป็นตัวปลุก `request_loader` ให้ตั้ง
    `g.api_token` เอง (หลักเดียวกับที่ `require_api_token` ต้องทำ)
    """
    if current_user.is_authenticated and getattr(g, "api_token", None) is not None:
        return f"token:{g.api_token.id}"
    return f"ip:{get_remote_address()}"


def _quota() -> str:
    """อ่านโควตาตอนมีคำขอ ไม่ใช่ตอน import — เทสต์จึงตั้งค่าต่อแอปได้"""
    limit: str = current_app.config["API_RATE_LIMIT"]
    return limit


def api_blueprint(name: str, path: str, description: str) -> Blueprint:
    """blueprint ของ API หนึ่งกลุ่ม — ต้องมี token ถึงจะเข้าถึงได้ทุก endpoint"""
    blueprint = Blueprint(
        name,
        __name__.rsplit(".", 1)[0] + "." + name,
        url_prefix=f"{API_PREFIX}{path}",
        description=description,
    )
    blueprint.before_request(require_api_token)
    # ผูกโควตาที่ blueprint ทั้งอัน ไม่ใช่ทีละ view — ด้วยเหตุผลเดียวกับด่าน token
    # ข้างบน: decorator ที่ต้องจำไปแปะเองคือ decorator ที่วันหนึ่งจะลืมแปะ
    # แล้ว endpoint นั้นจะไม่มีเพดานโดยไม่มีอะไรฟ้อง
    limiter.limit(_quota, key_func=_quota_key)(blueprint)

    # ผูกที่ blueprint ไม่ใช่ที่แอป — หน้า HTML ต้องได้หน้า error แบบเดิมของมัน
    # ไม่ใช่ JSON (flask-smorest ปกติจะยึด handler ระดับแอป ดู app/api/__init__.py)
    blueprint.register_error_handler(ServiceError, service_error_response)
    blueprint.register_error_handler(HTTPException, http_error_response)
    return blueprint
