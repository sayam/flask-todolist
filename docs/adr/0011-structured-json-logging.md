# 0011 — log เป็น JSON บรรทัดละ event + correlation ID ต่อ request

สถานะ: accepted (2026-08-03)

**บริบท:** Phase 7 จะต่อ audit trail/SIEM และ Phase 5 จะมี reverse proxy
(อาจมีหลาย process) การเลือกฟอร์แมต log ทีหลังแปลว่าต้องไล่แก้ทุกจุดที่เขียน log
จึงตัดสินใจครั้งเดียวตั้งแต่ตอนที่ยังมีจุดเขียน log น้อย

**คำตัดสิน:**
- หนึ่งบรรทัด = หนึ่ง JSON object ผ่าน `JsonFormatter` ใน `app/logging_setup.py`
  ออก **stdout** อย่างเดียว (12-factor — การหมุนไฟล์เป็นงานของ runtime ไม่ใช่ของแอป)
- field คงที่: `timestamp` (UTC, ISO 8601), `level`, `logger`, `message`
  ค่าที่ส่งผ่าน `extra=` ถูกยกขึ้นเป็น field ระดับบนสุด
- ทุก request log `event="http_request"` พร้อม `request_id`, `actor`, `method`,
  `path`, `status`, `duration_ms`, `remote_addr`
- `request_id` รับต่อจาก header `X-Request-Id` ได้ **แต่ต้อง parse เป็น UUID ได้
  เท่านั้น** ค่ามั่วจากภายนอกถูกทิ้งแล้วสร้างใหม่ — ไม่งั้นเป็นช่องปลอมแปลง/
  inject log จากคนนอก ค่าเดียวกันถูกส่งกลับใน response header ผู้ใช้ที่แจ้งปัญหา
  จึงอ้างอิงได้
- `ensure_ascii=False` — ข้อมูลผู้ใช้เป็นภาษาไทย ถ้า escape จะอ่านไม่ออกใน SIEM
- **actor เก็บ `username` ไม่ใช่ชื่อจริง** ลด PII ใน log (ต่อยอดที่ Phase 2)

**เหตุผลที่ไม่เลือกทางอื่น:** ยังไม่ใส่ OpenTelemetry เพราะระบบเป็น monolith
process เดียว ประโยชน์ของ trace ยังไม่คุ้ม dependency — `request_id` ที่รับต่อจาก
proxy ได้ทำหน้าที่ correlate ได้พอในตอนนี้ และไม่ปิดทางต่อ OTel ทีหลัง

**ผล:** `tests/test_logging.py` ล็อก contract ของ field ไว้ ถ้ามีใครเปลี่ยนชื่อ
หรือถอด field ออก เทสต์แดงทันที — ไม่ใช่ไปรู้ตอน dashboard ว่างเปล่า
