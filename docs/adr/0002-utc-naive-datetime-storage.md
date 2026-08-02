# 0002 — เก็บเวลาเป็น naive UTC ทั้งระบบ

สถานะ: accepted (backfill — ตัดสินใจจริงช่วง feature timezone)

**บริบท:** `due_date` ต้องรองรับผู้ใช้ต่างเขตเวลา และ SQLite ไม่มีชนิดข้อมูล
ที่เก็บ offset ได้
**ทางเลือก:** (ก) naive เวลาท้องถิ่นของ server (ข) aware ISO string (ค) naive UTC
**คำตัดสิน:** (ค) — ทุกคอลัมน์ DateTime เป็น naive UTC แปลงเข้า/ออกที่ `app/tz.py`
ที่เดียว template ใช้ `*_local` เท่านั้น
**ผล:** เทียบเวลาใน DB ได้ตรง ๆ / ราคาที่จ่าย: หลุดใช้ `due_date` ตรง ๆ ใน template
คือบั๊กเงียบ — คุมด้วยเทสต์และกติกาใน CLAUDE.md
