# 0057 — จัดชั้น gate ใหม่ 7 ตัวตามผล recheck ของ audit governance

สถานะ: **accepted** (2026-08-16 — ข้อเสนอ D2 ของ audit governance 5 มิติ:
การแบ่งชั้นถูก ~90% ที่เหลือคือ gate ที่กฎสากลหรือเป็นข้อตกลงระดับชนิดแอป
แต่ถูกจดเป็น internal เพราะ*ตอนเกิด*มันเกิดจากงานภายใน)

**หลักที่ใช้ตัดสิน** (ADR 0042 เดิม ไม่เปลี่ยน): กฎที่สากลต่อทุกโปรเจกต์ →
`baseline` (ต้อง portable → `SKILL.md`) · ข้อตกลงระดับชนิดแอป → `business`
(portable → `SKILL-TODOLIST.md`) · ผูกกับ implementation ของ repo นี้ →
`internal` — ชั้นของ gate ตัดสินจาก*เนื้อกฎ* ไม่ใช่จาก*เหตุที่มันเกิด*

## คำตัดสิน

1. **ยกขึ้น `baseline` (สากลแท้ — 2 ตัว)**:
   - `backup-restore-drilled-every-push` — "restore ที่ไม่เคยซ้อมคือความหวัง"
     จริงกับทุกแอปที่มีฐานข้อมูล ไม่มีอะไรผูก Flask
   - `risk-method-and-register-current` — ทะเบียนความเสี่ยง + สูตรที่เครื่อง
     ตรวจได้ เป็นของที่ ISO 6.1/8.2 ถามกับทุกโปรเจกต์
2. **ยกขึ้น `business` (ข้อตกลงของแอปที่ถือข้อมูลส่วนบุคคล — 3 ตัว)**:
   `ropa-current` · `admin-masking-by-classification` ·
   `secrets-encrypted-at-rest` — สามตัวนี้ทำให้ business sheet เล่าเรื่อง
   "แอปที่ถือข้อมูลส่วนบุคคล" ครบวงจร ซึ่งตรงกับบทเรียนเฟส 8–12 ที่ว่า
   สิ่งที่ scaffolding ให้แล้วอย่างอื่นให้ไม่ได้คือข้อตกลงเฉพาะของโปรเจกต์
3. **ยุบ `migration-dialect-lint` เข้า `dialect-discipline`** — กฎ "ชนิดเวลา
   ใน migration ห้ามใช้ตัวที่ยี่ห้ออื่นตัดเศษวินาที" คือวินัย dialect เรื่อง
   เดียวกัน การแยกสอง gate ทำให้เรื่องเดียวมีสองทะเบียน (ไฟล์เทสต์
   `tests/test_migration_lint.py` ย้ายไปอยู่ใต้ gate ปลายทาง ไม่มีเทสต์หาย)
4. **ย้าย `suite-on-three-brands` ลง `business`** — คำถามที่ audit เปิดไว้
   ตัดสินที่นี่: การรองรับหลายยี่ห้อฐานข้อมูลเป็น*ทางเลือกของชนิดแอป* ไม่ใช่
   กฎสากล — แอป SQLite-only ที่ import overlay ไม่ควรเจอ gate ที่ทำตาม
   ไม่ได้โดยนิยาม (ยัง portable — ย้ายจาก `SKILL.md` ไป `SKILL-TODOLIST.md`)
5. **แก้ถ้อยคำ `purge-timer-real-systemd`** — กฎสากลคือ "งานลบข้อมูลพ้นระยะ
   ติดตั้งบน scheduler จริงและความล้มเหลวมองเห็นได้" — systemd คือ *ตัวเลือก
   ของ repo นี้* ไม่ใช่ตัวกฎ (id คงเดิมกัน churn ของ overlay/ดัชนี)

## เงื่อนไขของ ADR 0045 ที่คำตัดสินนี้ทับ

ADR 0045 เขียนไว้ว่า masking จะยกเป็น portable ได้ "ต่อเมื่อเขียน checker
ของ overlay ที่ตรวจเรื่องนี้ในโปรเจกต์อื่นได้จริง" — คำตัดสินนี้**ทับด้วย
เหตุผลที่แบบแผนจริงพิสูจน์แล้ว**: overlay มี coverage สองแบบตั้งแต่แรก
(`scan` สำหรับกฎที่ตรวจสถิตได้ · `suite` สำหรับกฎที่ enforcement ผูกกับ
แอปเสมอ — `every-write-audited` เป็น business+portable ด้วย suite-kind
มาตลอดโดยไม่มีใครถือว่าผิด invariant) กฎ masking เป็นชนิดหลัง: โครง
ตาราง/ชั้นข้อมูลของแต่ละแอปต่างกันโดยธรรมชาติ scan checker กลางจึงเป็น
ไปไม่ได้โดยไม่ fake — invariant "portable ทุกตัวต้องถูก overlay ครอบ"
ยังจริงทุกตัวอักษร

## ทางที่ไม่ได้เลือก

- **ยก `secrets-encrypted-at-rest` ขึ้น baseline** — ปัดตก: แอปที่ไม่ถือ
  ความลับใช้งานได้ (ไม่มี MFA/credential ภายนอก) ไม่มีอะไรให้ encrypt
  กฎนี้จึงเป็นข้อตกลงของชนิดแอป ไม่ใช่สากล
- **ยก `openssf-scorecard` / `codeql-can-parse-the-app`** — คงเดิมตามผล
  audit (เงื่อนไขแวดล้อมแคบ / workaround ผูกรุ่นที่มีเงื่อนไขถอดอยู่แล้ว)
- **เปลี่ยน id `purge-timer-real-systemd` เป็นชื่อกลาง** — ปัดตก: id ถูก
  อ้างใน overlay/ดัชนี/ประวัติ — เปลี่ยนชื่อคือ churn ที่ไม่ซื้ออะไร
  ถ้อยคำที่คนอ่านคือ title ซึ่งแก้แล้ว

## ผลที่ตามมา

- ตัวเลขใหม่: gates **90** (baseline 65 · business 7 · internal 18) ·
  portable **71** · `SKILL.md` 65 กฎ · `SKILL-TODOLIST.md` ได้กฎเพิ่ม 4
  (สามตัวของข้อ 2 + สามยี่ห้อ) · axis supply-chain คง 17
- overlay ได้ suite entry ใหม่ 5 ตัว (สองตัวของข้อ 1 + สามตัวของข้อ 2)
- ADR 0042 (ตัวอย่างชั้น) และ ADR 0045 (เงื่อนไข masking) ติดโน้ตชี้มาที่นี่

---

**โน้ต (2026-08-16 ค่ำ — แบตช์รอบสามตามหลักเดิม · audit r2)**: ยกอีก 4 ตัว —
`release-signed-and-attested` → baseline (ตอนเกิดใน ADR 0058 จดเป็น internal
เพราะยังไม่เคยรันจริง — ตอนนี้ผ่าน run จริงและ verify ฝั่งผู้ใช้แล้ว) ·
`design-doc-matches-the-ui` / `admin-panels-read-real-state` /
`legal-pdpa-worksheet-honest` → business (ข้อตกลงระดับชนิดแอป — สองตัวหลัง
เข้าเซ็ตเดียวกับ masking/ropa ที่ยกไปรอบแรก) · ตัวเลขใหม่: baseline 66 ·
business 10 · internal 15 · portable 75
