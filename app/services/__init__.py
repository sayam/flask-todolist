"""service layer — business logic ที่ไม่รู้จัก HTTP (Phase 3 — ดู ADR 0016)

**กติกาเดียวที่ห้ามผิด: ไฟล์ในไดเรกทอรีนี้ห้าม import อะไรที่ผูกกับ request**
(`flask.request`, `flask.session`, `flash`, `abort`, `render_template`,
`url_for`, `flask_login.current_user`) — `tests/test_service_layer.py` สแกนบังคับ

เหตุผลไม่ใช่ความสวยงามของโครงสร้าง แต่เป็นเรื่องที่วัดได้: ตั้งแต่มี `/api/v1`
ตรรกะเดียวกันถูกเรียกจากสองทางที่มี input คนละแบบ (ฟอร์ม HTML กับ JSON)
ตรรกะที่หยิบค่าจาก `request` เองจะใช้ได้ทางเดียวเสมอ และ "ทางที่สอง" จะกลาย
เป็นการก๊อปโค้ดมาแก้ ซึ่งแปลว่าบั๊กต้องแก้สองที่ตลอดไป

สิ่งที่ยังเป็นของ adapter (route/view) ไม่ใช่ของ service:

* การอ่าน request และการเลือก status code / template / envelope ของคำตอบ
* `session` (เช่น การจำว่าให้โชว์วันเริ่มไหม, ค่าที่ชนะโปรไฟล์ตอนเลือกภาษา)
* การตัดสินใจว่าจะ `flash()` หรือจะคืน error ให้เครื่อง

service คุมทรานแซกชันของตัวเอง (commit เอง) และสื่อสารความล้มเหลวด้วย
exception ใน `app.services.errors` ไม่ใช่ด้วย `abort()` หรือค่า None กำกวม
"""

from app.services.errors import (
    ConflictError,
    NotFoundError,
    ServiceError,
    ValidationError,
)

__all__ = [
    "ConflictError",
    "NotFoundError",
    "ServiceError",
    "ValidationError",
]
