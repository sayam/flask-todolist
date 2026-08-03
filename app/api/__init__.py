"""`/api/v1` — สัญญาที่ freeze แล้ว สร้างจากโค้ด ไม่ได้เขียนมือ (ดู ADR 0018)

spec ของ OpenAPI ถูก generate จาก schema กับ view จริง (flask-smorest +
apispec) ไฟล์ `docs/openapi.json` ที่ commit ไว้เป็นแค่ **ภาพถ่าย**ของสิ่งที่
โค้ดประกาศ และมีเทสต์เทียบว่าตรงกันเสมอ — เอกสาร API ที่เขียนมือจะล้าสมัย
ภายในไม่กี่สัปดาห์เสมอ และไม่มีใครรู้ตัวจนกว่า client จะพัง

**ไม่มี Swagger UI** เพราะมันโหลด JS/CSS จาก CDN ซึ่ง CSP ของเรา (`'self'`
ล้วน ไม่มี `unsafe-inline` — ADR 0010) บล็อกทิ้งอยู่แล้ว จะได้หน้าขาว ๆ
ที่ไม่มี error ให้เห็น เสิร์ฟแค่ตัว JSON ที่ `/api/v1/openapi.json` แล้วให้คน
เอาไปเปิดด้วยเครื่องมือของตัวเอง
"""

from typing import Any

from flask import Flask, request
from flask_smorest import Api
from werkzeug.exceptions import HTTPException

from app import csrf
from app.api import auth, categories, todos, tokens
from app.api.base import API_PREFIX
from app.api.errors import ErrorSchema, http_error_response

# ชื่อ security scheme ใน spec — ที่เดียวกับที่ view อ้างถึง
BEARER_SCHEME = "PersonalAccessToken"


class TodolistApi(Api):
    """Api ของ flask-smorest ที่ **ไม่ยึด error handler ระดับแอป**

    ตัวเดิมทำ `app.register_error_handler(HTTPException, ...)` ตอน init ซึ่ง
    แปลว่าหน้า 404 ของเว็บ HTML จะกลายเป็น JSON ไปด้วยทั้งเว็บ — ผลข้างเคียง
    ที่ไม่มีใครสั่ง เราผูกเองสองชั้นแทน: ที่ระดับ blueprint (`app/api/base.py`)
    และที่ระดับแอปแบบดูจาก path (`_errors_stay_in_their_own_language` ข้างล่าง)
    ขอบเขตจึงอยู่แค่ `/api/` จริง ๆ
    """

    # ใช้ซองของเราเป็นตัวอธิบาย error ใน spec ด้วย ไม่งั้นจะมี schema ชื่อ "Error"
    # สองตัวที่หน้าตาไม่เหมือนกันปนอยู่ในไฟล์เดียว
    ERROR_SCHEMA = ErrorSchema

    def _register_error_handlers(self) -> None:
        return


# คำอธิบายระดับ spec — กติกาที่จริงกับ **ทุก** endpoint เขียนไว้ที่เดียวตรงนี้
# แทนที่จะไปประกาศซ้ำในทุก operation (ซึ่งจะมีตัวที่ตกหล่นแน่นอน)
DESCRIPTION = """
API ของ todolist — เรียกตรรกะชุดเดียวกับหน้าเว็บ (ADR 0016)

**การยืนยันตัวตน:** ทุก endpoint ต้องมี personal access token
(`Authorization: Bearer tdl_<id>_<secret>`) ออกใบด้วย `flask token-create`
session cookie ของเบราว์เซอร์ **ใช้กับ API ไม่ได้** และ token ก็ใช้กับหน้าเว็บ
ไม่ได้เช่นกัน ไม่มี token / token หมดอายุ / ถูกเพิกถอน → `401`

**เวลา:** ทุก datetime เป็นเวลาท้องถิ่นของเจ้าของข้อมูล รูปแบบ ISO 8601
**ไม่มี offset** (เช่น `2026-09-01T16:00`) ค่าที่ส่ง offset มาด้วยถูกปฏิเสธ

**ความผิดพลาด:** ทุกคำตอบที่ไม่สำเร็จมีรูปเดียวกันคือ
`{"error": {"code": ..., "message": ...}}` โดย `code` เป็นส่วนหนึ่งของสัญญา
ส่วน `message` เป็นข้อความสำหรับคนอ่านและเปลี่ยนได้

**เวอร์ชัน:** สัญญาอยู่ที่ path (`/api/v1`) การเปลี่ยนที่ทำให้ client เดิมพัง
ต้องขึ้น `/api/v2` ใหม่ทั้งชุด ไม่ใช่แก้ของเดิม (ADR 0018)
"""


def _errors_stay_in_their_own_language(app: Flask) -> None:
    """คำขอที่ยิงมาที่ `/api/` ต้องได้ JSON เสมอ ส่วนหน้าเว็บต้องได้ HTML เสมอ

    handler ที่ blueprint ครอบได้แค่คำขอที่หา view เจอ — URL ที่พิมพ์ผิดหรือ
    method ที่ไม่รองรับถูกตัดตั้งแต่ชั้น routing ซึ่งยังไม่รู้ว่าเป็นของ blueprint ไหน
    ถ้าไม่ดักตรงนี้ client ที่พิมพ์ path ผิดจะได้หน้า HTML กลับไปแล้ว JSON parser
    พังด้วยข้อความที่ไม่เกี่ยวอะไรกับสาเหตุจริงเลย (schemathesis จับข้อนี้ให้)
    """

    @app.errorhandler(HTTPException)
    def _http_error(error: HTTPException) -> Any:
        if request.path.startswith(auth.API_PREFIX):
            return http_error_response(error)
        # หน้าเว็บ: คืนคำตอบมาตรฐานของ werkzeug ตามเดิม ไม่แตะอะไร
        return error.get_response()


def init_api(app: Flask) -> Api:
    """ผูก `/api/v1` เข้ากับแอป — เรียกจาก `create_app()`"""
    api = TodolistApi(app, spec_kwargs={"description": DESCRIPTION.strip()})
    _errors_stay_in_their_own_language(app)

    api.spec.components.security_scheme(
        BEARER_SCHEME,
        {
            "type": "http",
            "scheme": "bearer",
            "description": (
                "personal access token ที่ออกด้วย `flask token-create` "
                "ส่งมาเป็น `Authorization: Bearer tdl_<id>_<secret>`"
            ),
        },
    )
    # ทุก endpoint ต้องมี token — ประกาศครั้งเดียวที่ระดับ spec ให้ตรงกับด่านจริง
    # ที่ผูกไว้ที่ `before_request` ของทุก blueprint (app/api/base.py)
    api.spec.options["security"] = [{BEARER_SCHEME: []}]

    for blueprint in (todos.blp, categories.blp, tokens.blp):
        # bearer token ไม่ถูกเบราว์เซอร์แนบมาเอง จึงไม่มีอะไรให้ CSRF ป้องกัน
        # (ด่านที่กันเบราว์เซอร์ยิงข้ามเว็บอยู่ที่ `require_api_token` — app/api/auth.py)
        csrf.exempt(blueprint)
        api.register_blueprint(blueprint)

    return api


def spec_dict(app: Flask) -> dict[str, Any]:
    """spec ของแอปนี้เป็น dict — ใช้โดยสคริปต์ generate และเทสต์ที่เทียบว่าตรงกัน"""
    api: Api = app.extensions["flask-smorest"]["apis"][""]["ext_obj"]
    spec: dict[str, Any] = api.spec.to_dict()
    return spec


__all__ = ["API_PREFIX", "BEARER_SCHEME", "auth", "init_api", "spec_dict"]
