# 0046 — field-level encryption at rest สำหรับความลับที่ต้องอ่านคืนได้

สถานะ: accepted (2026-08-14 — เจ้าของอนุมัติทั้งสามคำถามท้ายไฟล์ในแชต)

หมายเหตุการ implement: การย้ายข้อมูลเดิมใช้ **encrypt-on-verify** (dual-read +
เขียนกลับตอน verify สำเร็จ) แทนสคริปต์ migration — ตารางของ plugin อยู่นอกสาย
alembic โดยออกแบบ (ADR 0023) · ผู้ deploy บน MySQL ที่ติดตั้ง plugin ไว้ก่อน
เฟส 15 ต้อง `ALTER TABLE tdl_auth_totp_secret MODIFY totp_secret VARCHAR(256)`
ก่อน (SQLite ไม่บังคับความยาวจึงไม่ต้องทำ)

**บริบท:** ชั้นข้อมูล C1 มีสามคอลัมน์ — `password_hash` (scrypt) ·
`token_hash` (sha256 ของค่าสุ่ม 256 บิต) · `totp_secret` (**เก็บค่าจริง**
เพราะ TOTP ต้องคำนวณรหัสเทียบทุกครั้ง — ADR 0023/0024 บันทึกไว้แล้วว่า
ชดเชยด้วยการลบทิ้งทันทีที่ปิด MFA) · dump ของฐานข้อมูลใบเดียววันนี้จึงได้
ความลับ TOTP ไปทั้งหมด

## คำตัดสิน (เสนอ)

### อะไรถูก encrypt — เลือกจาก "ต้องอ่านคืนได้ + เป็นความลับจริง" เท่านั้น

| คอลัมน์ | ทำไหม | เหตุผล |
|---|---|---|
| `tdl_auth_totp_secret.totp_secret` | **ทำ (ตัวแรกและตัวเดียวของรอบนี้)** | ความลับที่ต้องอ่านคืนได้โดยนิยาม — encrypt แล้ว dump DB ใบเดียวไม่พอเปิด MFA |
| `password_hash` / `token_hash` | ไม่ทำ | เป็น one-way อยู่แล้ว — encrypt ซ้ำไม่เพิ่มอะไรนอกจากจุดพังใหม่ |
| เนื้อหางาน (C3: title ฯลฯ) | ไม่ทำในเฟสนี้ | field-encrypt แล้ว `LIKE` ของช่องค้นหาตายทั้งฟีเจอร์ — at-rest ของเนื้อหาเป็นเรื่องของ disk/DB-level encryption ฝั่ง deploy (บันทึกใน OPERATIONS) · **เงื่อนไขทบทวน**: มี requirement จริงที่ยอมแลกการค้นหา |

### กลไก

- คีย์แยกใหม่ `DATA_ENCRYPTION_KEY` (32 ไบต์ base64) อ่านผ่าน **secrets
  source เดิม** (ADR 0030 — env:// เป็นค่าเริ่มต้น, vault:// ได้ทันที)
  · **ไม่ derive จาก SECRET_KEY** — SECRET_KEY หมุนแล้ว session หลุดคือเรื่อง
  ปกติ แต่ข้อมูลถอดไม่ได้คือหายนะ สองอย่างนี้ต้องหมุนแยกกันได้
- AES-256-GCM ผ่านไลบรารี `cryptography` · รูปเก็บ: `enc:v1:<nonce>:<ct>`
  — เลขเวอร์ชันในตัวค่า = หมุนคีย์ได้ทีละแถวด้วยสคริปต์ re-encrypt โดยไม่มี
  flag day (คีย์เก่าถอด v1, คีย์ใหม่เขียน v2)
- **`cryptography` อยู่ใน category ของ plugin auth/totp** ไม่ใช่ `[packages]`
  ของ core (ADR 0025 — ถอน plugin แล้ว supply chain ต้องหายตาม) · ตัวชนิด
  คอลัมน์ `EncryptedSecret` อยู่ใน `models.py` ของ plugin เอง — core ไม่มี
  โค้ด crypto เลย (ตอนนี้ไม่มีคอลัมน์ core ตัวไหนต้องใช้ · ถ้าวันหนึ่งมี
  ค่อยยกขึ้น core พร้อมย้าย dependency — บันทึกไว้เป็นเงื่อนไข)
- **มีคอลัมน์ encrypt แต่ไม่มีคีย์ = ไม่ start** (หลัก config-fails-loud) ·
  คีย์ผิด = ปฏิเสธชัดเจนตอนอ่าน ไม่ใช่คืนขยะเงียบ ๆ
- migration ของข้อมูลเดิม: อ่านค่า plaintext → เขียนกลับแบบ encrypt
  (สำรองก่อนตามวินัย · ทดสอบไป-กลับ)

### สิ่งที่แผนนี้ *ไม่ทำ* (ตัดต่อจาก ADR 0043)

- in-process encryption (ตัดแล้วใน 0043) · KMS ของ cloud (seam พร้อม —
  แหล่งคีย์คือ secrets source ซึ่งเป็น plugin อยู่แล้ว) · encrypt ทั้งฐาน
  (เรื่องของ deploy ไม่ใช่ของแอป)

## ผลที่ตามมา

- ตาราง bench เฟส 10: totp ยังเป็น `live` — encrypt/decrypt ต่อการ verify
  เป็นงาน CPU จิ๋ว แต่**ต้องวัดซ้ำหลังทำ** (วินัย ADR 0031)
- `docs/DATA-CLASSIFICATION.md` เพิ่มหมายเหตุว่า C1 ตัวไหน encrypted at rest
- ASVS หลายแถวในกลุ่ม V11 (cryptography) ขยับจากยังไม่ผ่าน → ผ่าน — ประเมิน
  ตอนปิดเฟส

## คำถามที่ต้องการคำตอบจากเจ้าของก่อนลงมือ

1. ยืนยันขอบเขต "totp_secret ตัวเดียวก่อน" หรืออยากรวมอะไรอีก
2. ยืนยันคีย์แยก `DATA_ENCRYPTION_KEY` ผ่าน secrets source (ไม่ derive จาก SECRET_KEY)
3. ยืนยันให้ `cryptography` อยู่ใน category ของ plugin ไม่ใช่ core
