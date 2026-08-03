"""`/api/v1/categories` — adapter บาง ๆ เหนือ `app/services/categories.py`"""

from typing import Any

from flask.views import MethodView

from app.api.auth import token_owner
from app.api.base import api_blueprint
from app.api.errors import ErrorSchema
from app.api.schemas import CategorySchema, CategoryWriteSchema
from app.services import categories as categories_service

blp = api_blueprint("categories", "/categories", "หมวดของงาน")

NO_CONTENT = 204


@blp.route("")
class CategoryCollection(MethodView):
    @blp.response(200, CategorySchema(many=True))
    def get(self) -> list[Any]:
        """หมวดทั้งหมดของผู้ใช้ เรียงตามชื่อ"""
        return categories_service.list_categories(token_owner())

    @blp.arguments(CategoryWriteSchema)
    @blp.response(201, CategorySchema)
    @blp.alt_response(400, schema=ErrorSchema, description="ชื่อหมวดว่าง")
    @blp.alt_response(409, schema=ErrorSchema, description="ชื่อนี้มีอยู่แล้ว")
    def post(self, data: dict[str, Any]) -> Any:
        """สร้างหมวดใหม่ — ชื่อห้ามซ้ำกับหมวดอื่นของคนเดียวกัน"""
        return categories_service.create_category(token_owner(), data["name"])


@blp.route("/<int:category_id>")
class CategoryItem(MethodView):
    @blp.response(200, CategorySchema)
    @blp.alt_response(404, schema=ErrorSchema, description="ไม่มีหมวดนี้ หรือไม่ใช่ของผู้ใช้คนนี้")
    def get(self, category_id: int) -> Any:
        """หมวดหนึ่งรายการ"""
        return categories_service.get_category(token_owner(), category_id)

    @blp.arguments(CategoryWriteSchema)
    @blp.response(200, CategorySchema)
    @blp.alt_response(400, schema=ErrorSchema, description="ชื่อหมวดว่าง")
    @blp.alt_response(404, schema=ErrorSchema, description="ไม่มีหมวดนี้ หรือไม่ใช่ของผู้ใช้คนนี้")
    @blp.alt_response(409, schema=ErrorSchema, description="ชื่อนี้มีอยู่แล้ว")
    def patch(self, data: dict[str, Any], category_id: int) -> Any:
        """เปลี่ยนชื่อหมวด"""
        return categories_service.rename_category(token_owner(), category_id, data["name"])

    @blp.response(NO_CONTENT)
    @blp.alt_response(404, schema=ErrorSchema, description="ไม่มีหมวดนี้ หรือไม่ใช่ของผู้ใช้คนนี้")
    @blp.alt_response(409, schema=ErrorSchema, description="ยังมีงานอยู่ในหมวดนี้")
    def delete(self, category_id: int) -> None:
        """ลบหมวด — **ทำได้เฉพาะตอนไม่มีงานอยู่เลย** งานที่ทำเสร็จแล้วก็ยังนับ"""
        categories_service.delete_category(token_owner(), category_id)
