"""โรงงานสร้าง blueprint ของ API — ทุกตัวได้ด่านและซองข้อความผิดพลาดชุดเดียวกัน

blueprint ที่สร้างเองทีละตัวแล้วค่อยไล่ผูก `before_request` / error handler
เองคือ blueprint ที่วันหนึ่งจะมีตัวที่ลืมผูก — และตัวที่ลืมจะเป็นตัวที่เปิดโล่ง
โดยไม่มีอะไรฟ้อง จึงบังคับให้ทางเดียวที่สร้าง blueprint ของ API ได้คือทางนี้
"""

from flask_smorest import Blueprint
from werkzeug.exceptions import HTTPException

from app.api.auth import require_api_token
from app.api.errors import http_error_response, service_error_response
from app.services import ServiceError

API_PREFIX = "/api/v1"


def api_blueprint(name: str, path: str, description: str) -> Blueprint:
    """blueprint ของ API หนึ่งกลุ่ม — ต้องมี token ถึงจะเข้าถึงได้ทุก endpoint"""
    blueprint = Blueprint(
        name,
        __name__.rsplit(".", 1)[0] + "." + name,
        url_prefix=f"{API_PREFIX}{path}",
        description=description,
    )
    blueprint.before_request(require_api_token)

    # ผูกที่ blueprint ไม่ใช่ที่แอป — หน้า HTML ต้องได้หน้า error แบบเดิมของมัน
    # ไม่ใช่ JSON (flask-smorest ปกติจะยึด handler ระดับแอป ดู app/api/__init__.py)
    blueprint.register_error_handler(ServiceError, service_error_response)
    blueprint.register_error_handler(HTTPException, http_error_response)
    return blueprint
