# 0013 — schema identity: prefix `tdl_`, naming convention, typed models

สถานะ: accepted (2026-08-03)

**บริบท:** Phase 2 กำลังจะเพิ่มตาราง audit trail และคอลัมน์ soft-delete
ทุกตาราง ถ้าเปลี่ยนชื่อตารางทีหลังต้องแก้ทั้ง audit log ที่อ้างชื่อตารางไว้แล้ว
จึงต้องจัดการ "ตัวตนของ schema" ให้จบก่อน (ดู docs/STANDARDS.md ข้อ 1)

**คำตัดสิน:** ทำทั้งสี่เรื่องใน **migration เดียว** (`a1f0c2d47b93`)
เพราะแต่ละเรื่องบังคับให้ SQLite สร้างตารางใหม่อยู่แล้ว — จ่ายครั้งเดียวจบ

1. **prefix `tdl_` ทุกตาราง** — `tdl_user`, `tdl_category`, `tdl_todo`,
   `tdl_alembic_version` และ plugin ใช้ `tdl_<ชนิด>_<ไอดี>_*`
   ทำให้ core กับ plugin อยู่ในฐานข้อมูลเดียวกันได้โดยรู้ว่าตารางไหนของใคร
   **ผลพลอยได้ที่สำคัญ: ไม่มีตารางชื่อ `user` อีกแล้ว** ซึ่งเป็น reserved word
   ของ PostgreSQL/Oracle/MSSQL — landmine ที่ค้างมาตั้งแต่ต้นตายถาวรตรงนี้
   ไม่ต้องรอ baseline squash ใน Phase 5
2. **`naming_convention` ที่ `MetaData`** — constraint ที่ไม่ได้ตั้งชื่อจะได้ชื่อ
   auto ที่ต่างกันตามยี่ห้อ DB ทำให้ alembic drop/alter ข้ามยี่ห้อไม่ได้
3. **`done` → `is_done`** — กติกา boolean ขึ้นต้น `is_`/`has_` มีตัวเดียวที่ผิด
4. **model เป็น SQLAlchemy 2.0 typed style** (`Mapped[]` + `mapped_column`)
   เปิดทางให้ `app.models` เข้า mypy strict list ได้ใน Phase 2

**วิธี migrate:** สร้างตารางใหม่ → `INSERT ... SELECT` ที่ระบุคอลัมน์ชัดเจน →
drop ของเก่าตามลำดับ dependency **ไม่ใช้ `batch_alter_table`** เพราะ batch mode
บน SQLite คัดลอกด้วย `CAST(col AS <type>)` ซึ่งเคยทำ DATETIME เกิดปัญหามาแล้ว
(ADR/migration `89cd0c572bf9`) ที่นี่ชนิดคอลัมน์ไม่เปลี่ยน การคัดลอกจึงเป็นค่าดิบ

**ตารางเวอร์ชันของ alembic:** เปลี่ยนชื่อด้วย ทำให้ `flask db upgrade` บนฐานข้อมูล
เดิมจะหาไม่เจอแล้วคิดว่าฐานข้อมูลว่าง → ไล่รัน migration ตั้งแต่ตัวแรก → ล้มเหลว
แก้ด้วย `_adopt_legacy_version_table()` ใน `env.py` ที่เปลี่ยนชื่อให้อัตโนมัติครั้งเดียว

**บทเรียนที่ต้องไม่ลืม:** ตอนแรกเขียนฟังก์ชันนั้นให้ใช้ connection ตัวเดียวกับที่
ส่งให้ `context.configure()` ผลคือ **migration ทั้งชุดถูก rollback เงียบ ๆ**
log ขึ้น "Running upgrade" ครบทุกตัว exit code เป็น 0 แต่ฐานข้อมูลไม่เปลี่ยนเลย
ไม่มี gate ตัวไหนจับได้เพราะเทสต์ทั้งหมดใช้ `db.create_all()` ไม่เคยรัน migration จริง
→ เพิ่ม `tests/test_migrations.py` ที่รัน `upgrade()` จริงกับไฟล์ SQLite ชั่วคราว
และ assert ว่า **ตารางเวอร์ชันถูก stamp จริง** (ว่าง = ไม่ได้ commit)
mutation test ยืนยันแล้วว่าจำลองบั๊กเดิมกลับมาแล้วเทสต์แดง 5 ตัว

**ผล:** ตรวจแล้วด้วยฐานข้อมูลจริง 3 เส้นทาง — replay จากศูนย์, upgrade จากสำเนา
ฐานข้อมูลจริงที่มีข้อมูล (ค่าตรงทุกตัวรวม microsecond และ NULL), และ
downgrade→upgrade ไป-กลับได้ค่าเดิมเป๊ะ

ข้อจำกัดที่ยอมรับ: migration เก่า 3 จุดยังมี raw SQL ที่อ้าง `user` แบบไม่ quote
ปล่อยไว้ตามเดิม (`tests/test_migration_lint.py` มี allowlist ดักไม่ให้เพิ่มจุดใหม่)
จะหายไปพร้อม baseline squash ใน Phase 5
