# 0008 — table prefix `tdl_` + SQLAlchemy naming_convention

สถานะ: accepted (2026-08-03) — implement จริงเป็นด่านแรกของ Phase 2

**บริบท:** (1) plugin จะมี table ของตัวเอง ต้องมี namespace (2) รองรับหลาย DB
prefix เป็นกลไกเดียวที่ portable ทุกยี่ห้อ (3) ตาราง `user` เป็น reserved word
ใน PostgreSQL/Oracle/MSSQL — landmine ที่สแกนพบจริง
**คำตัดสิน:** core = `tdl_*` / plugin = `tdl_<ชนิด>_<ไอดี>_*` /
alembic version table = `tdl_alembic_version` / ใส่ `naming_convention`
มาตรฐานของ SQLAlchemy ให้ constraint ทุกตัวมีชื่อ deterministic /
พ่วง `done` → `is_done` ในรอบเดียวกัน
**ผล:** landmine `user` ตายถาวร / จ่าย batch-recreate ของ SQLite หนึ่งครั้ง
