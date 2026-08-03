"""`/api/v1/tokens` — ดูและเพิกถอนกุญแจของตัวเอง

**ไม่มี POST โดยตั้งใจ** — ออกใบใหม่ทำได้จาก CLI เท่านั้น (`flask token-create`)

ถ้า token ออก token ได้ ใบที่หลุดออกไปจะแตกลูกเป็นใบใหม่ที่อายุยาวกว่าเดิมได้
ทันที การเพิกถอนใบที่หลุดจึงไม่ได้ปิดประตูจริง เพราะประตูบานที่สองถูกสร้างไป
ก่อนแล้ว (GitHub ก็ห้ามด้วยเหตุผลเดียวกัน) การออกใบต้องเริ่มจากตัวตนที่แรงกว่า
เสมอ — ตอนนี้คือ CLI บนเครื่อง ทีหลังคือหน้าเว็บที่ยืนยันรหัสผ่านซ้ำ

ส่วนการ**เพิกถอน**เปิดให้ทำผ่าน API ได้ เพราะเป็นการลดสิทธิ์ ไม่ใช่เพิ่ม —
สคริปต์ที่รู้ตัวว่าโดนเจาะควรฆ่ากุญแจตัวเองได้ทันทีโดยไม่ต้องรอคนมา ssh
"""

from typing import Any

from flask.views import MethodView

from app.api.auth import token_owner
from app.api.base import api_blueprint
from app.api.errors import ErrorSchema
from app.api.schemas import TokenSchema
from app.services import tokens as tokens_service

blp = api_blueprint("tokens", "/tokens", "personal access token ของผู้ใช้เอง")

NO_CONTENT = 204


@blp.route("")
class TokenCollection(MethodView):
    @blp.response(200, TokenSchema(many=True))
    def get(self) -> list[Any]:
        """ใบที่ยังไม่ถูกเพิกถอนของผู้ใช้ ใหม่สุดก่อน — **ไม่มีตัวความลับในคำตอบ**"""
        return tokens_service.list_tokens(token_owner())


@blp.route("/<int:token_id>")
class TokenItem(MethodView):
    @blp.response(200, TokenSchema)
    @blp.alt_response(404, schema=ErrorSchema, description="ไม่มีใบนี้ หรือไม่ใช่ของผู้ใช้คนนี้")
    def get(self, token_id: int) -> Any:
        """ใบหนึ่งใบ"""
        return tokens_service.get_token(token_owner(), token_id)

    @blp.response(NO_CONTENT)
    @blp.alt_response(404, schema=ErrorSchema, description="ไม่มีใบนี้ หรือไม่ใช่ของผู้ใช้คนนี้")
    def delete(self, token_id: int) -> None:
        """เพิกถอนใบนั้นทันที (ล้าง hash ทิ้งด้วย ไม่ใช่แค่ซ่อน)

        เพิกถอนใบที่กำลังใช้ยิงคำขอนี้อยู่ก็ได้ — คำขอนี้สำเร็จ แต่คำขอถัดไป
        ที่ใช้ใบเดิมจะได้ 401
        """
        tokens_service.revoke(token_owner(), token_id)
