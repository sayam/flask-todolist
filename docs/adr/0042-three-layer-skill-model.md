# 0042 — กฎทุกข้อประกาศชั้นของตัวเอง: baseline / business / internal

สถานะ: accepted (2026-08-14) — เปิดเฟส 13 ([ROADMAP-FEATURES.md](../ROADMAP-FEATURES.md))

**บริบท:** การทดลองเฟส 12 (`docs/comparison/`) ให้คำตอบที่ชัดที่สุดว่า
scaffolding คุ้มค่าตรงไหน: **ข้อตกลงเฉพาะโปรเจกต์** (soft delete — ไม่มีแอป
ไหนในแขนทบทวนคิดถึงเองเลย) กับ**ความสม่ำเสมอ** ส่วนกฎที่เดาได้ด้วยสามัญสำนึก
รอบทบทวนเก็บไปเกือบหมดเอง · แต่ `SKILL.md` ปัจจุบันเทกฎทั้งสองชนิดรวมใบเดียว
— ผู้รับที่ไม่ได้ทำ todolist ได้ข้อตกลงของ todolist ติดไปด้วย และข้อกำหนด
พื้นฐานเสี่ยงไปขัด flow/ข้อดีของ framework หรือ domain ของผู้รับ (ข้อ 7
ของรายการ idea)

## คำตัดสิน

gate ทุกตัวใน `gates.yaml` ประกาศ `layer:` หนึ่งค่า:

| layer | นิยาม | เกณฑ์ตัดสิน | ไปอยู่ที่ |
|---|---|---|---|
| `baseline` | วินัยสากล | **แอปไหนเบี่ยงจากข้อนี้ = บกพร่อง** ไม่ใช่ทางเลือก (CSRF, config ต้องล้มเหลวดัง, ความลับไม่ฝังโค้ด) | `SKILL.md` |
| `business` | ข้อตกลงของ*ตัวแอป* (app-type todolist) | แอปอื่นเลือกต่างได้**โดยไม่ถือว่าบกพร่อง** (ลบ = soft delete, ทุกการเขียนลง audit chain) | `SKILL-TODOLIST.md` |
| `internal` | เครื่องมือ/โครงของ repo นี้เอง | ไม่มีความหมายนอก repo นี้ (ตัววัดการทดลอง, job ของ CI stack) | ไม่ export |

**invariant ที่เทสต์บังคับ** (`tests/test_gates.py`):
- ทุก gate มี `layer` และเป็นหนึ่งในสามค่า
- `layer: baseline` ⇒ `portable: true` (สากลแล้วไม่ export คือขัดแย้งในตัว)
- `layer: internal` ⇒ `portable: false`
- `business` เป็นได้ทั้งสอง (กฎ portable ไปยัง todolist implementation อื่น ·
  ชุดเทสต์พฤติกรรมเป็น business ที่ไม่ portable)

**การ render** (`scripts/build_skill.py` — generate ทั้งคู่ ห้ามแก้มือ):
- `SKILL.md` = baseline ∧ portable · `SKILL-TODOLIST.md` = business ∧ portable
- **portable gate ทุกตัวอยู่ในใบเดียวเป๊ะ** (partition — เทสต์บังคับ)
- ban list ชื่อไลบรารี framework ใช้กับ**ทั้งสองใบ** — business ก็สากลข้าม
  framework (soft delete ไม่ผูกกับ Flask)

**ทิศระหว่างชั้น (ข้อ 9 ของรายการ idea — business → overlay → baseline):**
- ใบ business ประกาศในหัวว่า**ต่อยอด baseline** — adopt โดยไม่รับ baseline
  ไม่ได้ (เทสต์ตรวจว่า pointer อยู่จริง)
- `requires:` ใน `gates.yaml` เป็นของ *environment* (mysql, docker-compose)
  อยู่แล้ว — **ไม่ยืมคีย์นี้มาใช้เรื่องชั้น** และไม่สร้างคีย์ dependency ใหม่
  จนกว่าจะมีกรณีจริงที่ต้องใช้ (ทะเบียนที่ไม่มีใครอ่านคือทะเบียนที่ drift)
- การขัดกัน*เชิงเนื้อหา*ระหว่างชั้นตรวจด้วยเครื่องไม่ได้ — สิ่งที่บังคับได้และ
  บังคับแล้วคือ partition + ที่มาของทุกข้อ (`born_from`) + ผู้ตัดสินชั้นคือ ADR นี้

**overlay ไม่เปลี่ยน**: `overlays/flask/` ครอบ portable **ทุกชั้น** เหมือนเดิม
— todolist บน framework อื่นใช้ checker ชุดเดียวกัน และเกณฑ์ "ครอบครบสองทิศ"
ใน `tests/test_overlay.py` คงเดิม

## การจัดชั้นรอบแรก (71 gate)

- `business`: `delete-means-soft-delete` · `every-write-audited` (สอง portable
  ที่เป็น*ทางเลือก*ของแอปนี้ — GDPR-erasure แอปอาจลบจริงโดยชอบ · audit แบบ
  hash chain เป็นการลงทุนที่แอปอื่นไม่จำเป็นต้องเอา) · `app-behavior-suite`
  (พฤติกรรมของ todolist เอง — ไม่ portable)
- `internal`: `migration-dialect-lint` · `comparison-instrument-verified` ·
  `ropa-current` · `stack-deploys-and-serves` · `oidc-end-to-end` ·
  `ldap-end-to-end` · `vault-end-to-end` · `scaffold-installs-and-runs` ·
  `openssf-scorecard`
- `baseline`: ที่เหลือ 59

`SKILL.md` จึงลดจาก 61 → 59 ข้อ — **เอกสารการทดลองเฟส 12 ไม่แก้ย้อน**
(บันทึกของสภาพที่วัด ณ วันนั้น ตามกติกาของมันเอง)

## ทางเลือกที่ไม่เอา

- **ใบเดียวมี section** — ผู้รับ import ทั้งไฟล์อยู่ดี การแยกที่อ่านข้ามได้
  ไม่ใช่การแยก
- **layer เป็นของ overlay ไม่ใช่ของ gate** — ชั้นเป็นคุณสมบัติของ*กฎ*
  (soft delete เป็น business ในทุก framework) ไม่ใช่ของตัวบังคับ
- **แตก business ออกเป็น repo แยก** — ยังไม่มีผู้บริโภคจริง · แยกเมื่อมีคนใช้
  (หลักเดียวกับ legal overlay ประเทศที่สอง)

## ผลที่ตามมา / เงื่อนไขทบทวน

- เฟส 14–18 ต้องประกาศ layer ให้ gate ใหม่ทุกตัว — กฎ masking/encryption ที่
  derive จากชั้นข้อมูลเป็น `baseline` · กฎ org-graph เป็น `business`
- ชั้น legal (PDPA — 13-04) เป็น **worksheet ที่อ้างหลักฐาน ไม่ใช่ layer ใน
  gates.yaml** เพราะมันคือ*คำตัดสินของคน*ต่อข้อกฎหมาย (ชนิดเดียวกับ `ASVS.md`
  ตาม ADR 0039) ไม่ใช่กลไกบังคับ
- ถ้าวันหนึ่ง business gate ต้องอ้างถึงกันเป็นลูกโซ่จริง ค่อยเพิ่มคีย์
  dependency พร้อมเทสต์ทิศ — วันนี้ยังไม่มีกรณีจริง

---

**โน้ต (2026-08-16)**: รายชื่อตัวอย่างของแต่ละชั้นข้างบนเป็นภาพ ณ วันเขียน —
ADR 0057 จัดชั้นใหม่ 7 ตัวตามผล recheck ของ audit governance (ยกขึ้น
baseline 2 · business 4 · ยุบ 1) ทะเบียนจริงคือ `gates.yaml` เสมอ
