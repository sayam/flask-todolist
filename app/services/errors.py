"""ความล้มเหลวที่ service สื่อสารออกมา — **ไม่มี HTTP อยู่ในไฟล์นี้**

แบ่งเป็น 3 ชนิดตาม "ผู้เรียกต้องทำอะไรต่อ" ไม่ใช่ตาม status code:

* `NotFoundError` — ของที่ขอไม่มี **หรือไม่ใช่ของคนที่ขอ** (ตอบเหมือนกันโดยตั้งใจ
  ดู ADR 0004 — ตอบต่างกันคือการยืนยันให้คนนอกรู้ว่า id นั้นมีอยู่จริง)
* `ValidationError` — input ใช้ไม่ได้ แก้ค่าแล้วลองใหม่ได้
* `ConflictError` — input ถูกต้องแต่ชนกับสถานะปัจจุบัน (ชื่อซ้ำ, หมวดยังมีงานอยู่)

แต่ละตัวมี **`code` ที่เป็นภาษาเครื่อง** แยกจาก `message` ที่เป็นภาษาคน:
`message` แปลตามภาษาผู้ใช้และเปลี่ยนถ้อยคำได้ตลอด ส่วน `code` เป็นส่วนหนึ่งของ
สัญญา API v1 (ADR 0017) — client เอาไปแตกกิ่งได้ **เปลี่ยนแล้วคือ breaking change**
"""


class ServiceError(Exception):
    """ฐานของทุกความล้มเหลวที่ตั้งใจให้ผู้เรียกจัดการ ไม่ใช่บั๊ก"""

    def __init__(self, message: str, *, code: str, field: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        # ชื่อฟิลด์ที่เป็นต้นเหตุ ถ้าระบุได้ — ฟอร์มเอาไปชี้จุด, API เอาไปใส่ envelope
        self.field = field


class NotFoundError(ServiceError):
    """ไม่มีของชิ้นนั้น หรือมีแต่เป็นของคนอื่น (แยกไม่ออกโดยตั้งใจ)"""


class ValidationError(ServiceError):
    """ค่าที่ส่งมาใช้ไม่ได้"""


class ConflictError(ServiceError):
    """ค่าถูกต้องแต่ทำตอนนี้ไม่ได้เพราะชนกับสถานะปัจจุบัน"""
