# 0050 — แพ็กเกจ agent skill เป็นช่องทางแจกจ่ายที่สาม

สถานะ: **accepted** (2026-08-15 — เจ้าของอนุมัติ "เห็นด้วยข้อเสนอทั้ง 3"
จากการวิเคราะห์ bmad-method · impeccable · skillsmp แล้วสั่งเริ่มข้อ 3)

**บริบท:** กฎที่ repo นี้ export มีผู้บริโภคสองแบบแล้ว — คนอ่าน `SKILL.md`/
`SKILL-TODOLIST.md` และ*โปรเจกต์*ติดตั้ง `overlays/flask/` — แต่โลกภายนอก
กำลัง consume วินัยการทำงานกันในรูปที่สาม: **agent skill package**
(โฟลเดอร์ `SKILL.md` + reference + scripts ที่ assistant โหลดเข้า context
ได้ตรง ๆ แบบ skill ของ impeccable และ catalog แบบ skillsmp) · ของที่เรามี
เกือบเป็นรูปนั้นอยู่แล้ว ขาดแค่ซองหุ้ม

## ทางเลือกที่พิจารณา

1. **เขียน skill ใหม่ด้วยมือให้เหมาะกับ agent** — ปัดตก: เอกสารเขียนมือคือ
   ทะเบียนที่สาม (เหตุผลเดียวกับที่ `SKILL.md` ถูก generate — ADR 0042)
2. **แปลกฎเป็นภาษาอังกฤษให้ตลาดกว้างขึ้น** — ปัดตก: สำเนาแปลคือไฟล์แรก
   ที่ล้าหลัง (เหตุผลเดียวกับที่ CHANGELOG มีภาษาเดียว) · กฎ 62 ข้อพร้อม
   บทเรียนเป็นไทย แหล่งจริงคือ `gates.yaml` — แปลเมื่อไหร่ก็ drift เมื่อนั้น
3. **generate ซองหุ้มรอบ render เดิม** — เลือกทางนี้

## คำตัดสิน

- `skill/` ที่รากของ repo คือแพ็กเกจ — **ทุกไบต์ derive จากแหล่งเดิม**
  ด้วย `scripts/build_agent_skill.py`:
  - `skill/SKILL.md` = frontmatter (`name` + `description`) + คำนำวิธีใช้
    (ของคน — ที่เดียวในแพ็กเกจ แบบเดียวกับ PREAMBLE ของ ADR 0042) +
    **render ชั้น baseline ตัวเดียวกับ `SKILL.md` ที่ราก** ไบต์ต่อไบต์
  - `skill/reference/SKILL-TODOLIST.md` = render ชั้น business ตัวเดิม
  - `skill/scripts/` = checker `scan_*.py` **คัดลอกตาม manifest
    `overlays/flask/overlay.json`** — ห้ามมีสำเนาที่แก้เอง · เพิ่ม/ถอด
    checker ที่ overlay แล้ว regenerate เท่านั้น
- ชื่อ skill เป็นกลางต่อ framework (`webapp-production-discipline`) เพราะ
  ชั้น baseline ห้ามมีชื่อไลบรารีของ framework อยู่แล้ว (`tests/test_skill.py`)
  — ส่วน `scripts/` เป็นของ overlay ระบุที่มาตรงไปตรงมาในคำนำ
- `tests/test_agent_skill.py` เทียบไฟล์ที่ commit กับผล generate สด
  ทุกไฟล์รวมทั้ง**เซตไฟล์** (ไฟล์แปลกปลอมใน `skill/` = แดง — แบบเดียวกับ
  ปรัชญา "ไม่ครบ = ล้มดัง" ของ `install.py`) · gate:
  `agent-skill-package-derived`

## ผลที่ตามมา

- แก้กฎ = แก้ `gates.yaml` แล้ว regenerate สองที่ (`build_skill.py` +
  `build_agent_skill.py`) — เทสต์ทั้งสองฝั่งกันลืม
- แพ็กเกจพร้อมสำหรับ marketplace/catalog ภายนอกเมื่อเจ้าของต้องการ —
  การ list ที่ไหนเป็นการตัดสินใจแยก ไม่ผูกกับ ADR นี้
- เงื่อนไขทบทวน: ถ้ารูปแบบ skill ของ ecosystem เปลี่ยน (frontmatter คนละ
  โครง) ซองหุ้มเปลี่ยนตาม แต่แหล่งกฎไม่ขยับ
