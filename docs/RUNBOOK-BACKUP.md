# Runbook — backup และ restore

ปิดช่องว่างข้อ `A.5.30`/`A.8.13` ของ [ISO27001.md](ISO27001.md) (backlog
ของ G2) — หลักตั้งของไฟล์นี้: **restore ที่ไม่เคยซ้อมคือความหวัง ไม่ใช่แผน**
การซ้อมของ repo นี้จึงเป็นเทสต์ที่รันจริง**ทุก push** ไม่ใช่พิธีปีละครั้ง
(`tests/test_backup_drill.py` เรียก `scripts/backup_drill.py` เต็มวง:
backup → เสียหาย → restore → ตรวจ)

## ต้อง backup อะไร — สามอย่าง แยกที่เก็บ

1. **ฐานข้อมูล** — งาน หมวด ผู้ใช้ audit trail ทั้งหมด
2. **ความลับ**: `SECRET_KEY` และ **`DATA_ENCRYPTION_KEY`** —
   ⚠️ **คีย์หาย = ความลับ TOTP ที่ encrypt ไว้อ่านไม่ได้ถาวร** (ADR 0046
   — ไม่มีทางกู้ ผู้ใช้ต้อง enroll MFA ใหม่ทุกคน) · และ **ห้ามเก็บคีย์ไว้
   ที่เดียวกับ backup ของฐาน** — ฐาน+คีย์ในที่เดียว = encrypt แล้วเท่ากับ
   ไม่ได้ encrypt สำหรับคนที่ได้ backup ไป
3. **ไฟล์ config ของ deployment** (`.env.example` เป็นแม่แบบว่ามีคีย์อะไรบ้าง)

สิ่งที่**ไม่ต้อง** backup: โค้ด (อยู่ใน git) · ไฟล์ `.mo`/generate ทั้งหลาย
(สร้างใหม่ได้) · ตารางของ plugin ถูก backup ไปพร้อมฐานอยู่แล้ว

## วิธี backup

### SQLite (ค่าเริ่มต้น)

ใช้ online backup ของ sqlite — สอดคล้องแม้แอปกำลังเขียน ห้าม `cp` ไฟล์ดิบ
ระหว่างแอปทำงาน (ได้สำเนากลางคำเขียน):

```bash
sqlite3 instance/todolist.db ".backup 'backup/todolist-$(date +%F).db'"
```

### MySQL / MariaDB

```bash
mysqldump --single-transaction --routines todolist > backup/todolist-$(date +%F).sql
```

`--single-transaction` ให้สำเนาสอดคล้องโดยไม่ล็อกตาราง (InnoDB) ·
การซ้อมอัตโนมัติของ repo ครอบเฉพาะทาง SQLite — ผู้ deploy ยี่ห้ออื่นต้อง
ซ้อม restore ของ dump เองตามรอบ (จดเปิดเผย ไม่แกล้งว่าครอบ)

## วิธี restore

1. หยุดแอปก่อนเสมอ (restore ใต้แอปที่กำลังเขียน = เสียหายซ้ำ)
2. SQLite: วางไฟล์ backup แทนที่ `instance/todolist.db` ·
   MySQL/MariaDB: `mysql todolist < backup/todolist-YYYY-MM-DD.sql`
3. ตรวจสามชั้นก่อนเปิดแอป:
   - SQLite: `sqlite3 instance/todolist.db "PRAGMA integrity_check"` ต้องได้ `ok`
   - `pipenv run flask db check` — schema ตรงกับโค้ดรุ่นที่จะรัน
     (ถ้า backup มาจากรุ่นเก่ากว่า: `flask db upgrade` ก่อน — สัญญา N-1
     ของ `ADR 0048` รับรองระยะหนึ่งรุ่น)
   - `pipenv run flask audit-verify` — สาย audit ต้องยังต่อครบ
4. ตรวจว่า `.env` มี `DATA_ENCRYPTION_KEY` **ตัวเดิม** — ฐานที่ restore มา
   กับคีย์คนละตัว = MFA verify ล้มทั้งระบบ

## การซ้อม (drill) — บันทึกจริง

- **อัตโนมัติทุก push**: `tests/test_backup_drill.py` สร้างฐาน scratch
  ที่มีข้อมูลจริง แล้วรัน `scripts/backup_drill.py` เต็มวง — CI เขียว =
  การซ้อมรอบล่าสุดผ่าน (นี่คือความหมายของ "ซ้อมต่อเนื่อง")
- **รันมือกับฐานจริงได้ทุกเมื่อ** (อ่านต้นฉบับอย่างเดียว ไม่แตะไฟล์จริง):
  `pipenv run python scripts/backup_drill.py instance/todolist.db`
- **บันทึกการซ้อมรอบแรกบนเครื่องจริง**: 2026-08-16 — รันกับฐาน dev ที่
  ผ่าน migration จริง ผลผ่านครบสี่ขั้น (ผลรันอยู่ในบันทึกของ PR ที่เพิ่ม
  ไฟล์นี้) · รอบถัดไปตามแถวใน [SECURITY-CADENCE.md](SECURITY-CADENCE.md)
