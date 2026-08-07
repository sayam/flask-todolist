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

## หมายเหตุเพิ่มเติม (2026-08-07 · Phase 5 · P5-08)

**log ย้ายจาก stdout ไป stderr** — คำตัดสินเดิมข้างบนเขียนว่า "ออก stdout อย่างเดียว"
โดยอ้าง 12-factor ซึ่งถูกต้องสำหรับแอปที่เป็น *server* อย่างเดียว แต่แอปนี้เป็น
**CLI ด้วย** และ output ของบางคำสั่งถูกเครื่องอ่าน (`flask plugin-deps --categories`
อยู่ใน `$(...)` ของ CI) — สองอย่างนั้นใช้ช่องเดียวกันไม่ได้

สิ่งที่เกิดขึ้นจริงตอน P5-07: เพิ่มคำเตือนที่ดังทุกครั้งที่ start แล้ว CI พังห้า job
เพราะได้ชื่อ category เป็น `'memory://'` (บรรทัด JSON ของ log ถูกอ่านปนมาด้วย)
**เทสต์ที่ตรึงรูปแบบ output ไว้แล้วมองไม่เห็น** เพราะใช้ `CliRunner` ซึ่งรวม
stdout กับ stderr เป็นก้อนเดียว — ด่านใหม่จึงต้องรันเป็น subprocess จริง
(`tests/test_logging.py::test_machine_readable_output_is_not_polluted_by_logs`)

เจตนาของ 12-factor ยังอยู่ครบ: แอปไม่หมุนไฟล์ log เอง ปล่อยให้ runtime จัดการ
ซึ่ง docker/k8s/systemd เก็บทั้ง stdout และ stderr อยู่แล้ว
