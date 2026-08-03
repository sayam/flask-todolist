"""`/api/v1/todos` — adapter บาง ๆ เหนือ `app/services/todos.py`

ไม่มีตรรกะของโดเมนในไฟล์นี้เลยโดยตั้งใจ (ADR 0016) หน้าที่มีแค่ย่อย request
ให้เป็นชนิดที่ service รับ แล้วแปลงผลลัพธ์เป็น status code
"""

from typing import Any

import marshmallow as ma
from flask.views import MethodView

from app.api.auth import token_owner
from app.api.base import api_blueprint
from app.api.errors import ErrorSchema
from app.api.schemas import (
    TodoCreateSchema,
    TodoQuerySchema,
    TodoSchema,
    TodoUpdateSchema,
)
from app.filters import FilterSpec
from app.services import todos as todos_service

blp = api_blueprint("todos", "/todos", "งานของผู้ใช้ที่ยืนยันตัวตนด้วย token")

NO_CONTENT = 204


@blp.route("")
class TodoCollection(MethodView):
    # `unknown=RAISE` ต้องระบุเอง — webargs ตั้งค่าเริ่มต้นของ query string เป็น
    # EXCLUDE คือ "เมินพารามิเตอร์ที่ไม่รู้จัก" ซึ่งแปลว่าพิมพ์ชื่อตัวกรองผิด
    # แล้วจะได้ผลลัพธ์ที่ไม่ได้กรองกลับไปเงียบ ๆ (กติกาเดียวกับฟิลด์ใน PATCH)
    @blp.arguments(TodoQuerySchema, location="query", unknown=ma.RAISE)
    @blp.response(200, TodoSchema(many=True))
    @blp.alt_response(404, schema=ErrorSchema, description="หมวดที่กรองไม่ใช่ของผู้ใช้คนนี้")
    def get(self, args: dict[str, Any]) -> list[Any]:
        """รายการงานตามตัวกรอง

        ตัวกรองชุดเดียวกับหน้าเว็บทุกตัว ค่าที่ไม่รู้จักตกกลับเป็นค่าเริ่มต้น
        """
        spec = FilterSpec.from_params({key: str(value) for key, value in args.items()})
        return todos_service.list_todos(token_owner(), spec)

    @blp.arguments(TodoCreateSchema)
    @blp.response(201, TodoSchema)
    @blp.alt_response(400, schema=ErrorSchema, description="ชื่องานว่างหรือค่าที่ส่งมาใช้ไม่ได้")
    @blp.alt_response(404, schema=ErrorSchema, description="หมวดที่อ้างถึงไม่ใช่ของผู้ใช้คนนี้")
    def post(self, data: dict[str, Any]) -> Any:
        """สร้างงานใหม่"""
        return todos_service.create_todo(token_owner(), **data)


@blp.route("/<int:todo_id>")
class TodoItem(MethodView):
    @blp.response(200, TodoSchema)
    @blp.alt_response(404, schema=ErrorSchema, description="ไม่มีงานนี้ หรือไม่ใช่ของผู้ใช้คนนี้")
    def get(self, todo_id: int) -> Any:
        """งานหนึ่งรายการ"""
        return todos_service.get_todo(token_owner(), todo_id)

    @blp.arguments(TodoUpdateSchema)
    @blp.response(200, TodoSchema)
    @blp.alt_response(400, schema=ErrorSchema, description="ค่าที่ส่งมาใช้ไม่ได้")
    @blp.alt_response(404, schema=ErrorSchema, description="ไม่มีงานนี้ หรือไม่ใช่ของผู้ใช้คนนี้")
    def patch(self, changes: dict[str, Any], todo_id: int) -> Any:
        """แก้เฉพาะฟิลด์ที่ส่งมา

        ฟิลด์ที่ไม่ได้ส่งมาไม่ถูกแตะ ส่วนการส่ง `null` มาแปลว่า "ล้างค่านั้น"
        """
        return todos_service.update_todo(token_owner(), todo_id, changes)

    @blp.response(NO_CONTENT)
    @blp.alt_response(404, schema=ErrorSchema, description="ไม่มีงานนี้ หรือไม่ใช่ของผู้ใช้คนนี้")
    def delete(self, todo_id: int) -> None:
        """ลบงาน (ซ่อนไว้ก่อน ของจริงถูกล้างโดย purge job เมื่อพ้นระยะ)"""
        todos_service.delete_todo(token_owner(), todo_id)
