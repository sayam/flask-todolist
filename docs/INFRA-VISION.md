# INFRA-VISION — Verifiable Secure-by-Default Scaffolding

> เอกสารทิศทางสำหรับการปรับปรุง infrastructure รอบถัดไปของ repo นี้
> ผู้อ่านหลักคือ Claude Code: ใช้เอกสารนี้เป็น input ในการ**วางแผน phase**
> (ดู "สิ่งที่ต้องส่งมอบจากเอกสารนี้" ท้ายไฟล์) ก่อนลงมือแก้โค้ดใด ๆ

## 1. เป้าหมาย

เปลี่ยน repo นี้จาก "แอปที่ทำวิศวกรรมครบ" ให้กลายเป็น **ต้นแบบ (reference
implementation) ของ scaffolding ที่ import เข้า project อื่นได้** โดยมี claim
หลักข้อเดียว:

> ไม่การันตีว่า "ปลอดภัย" — การันตีว่า **conformance พิสูจน์ซ้ำได้ด้วยเครื่อง**
> ต่อ gate ที่นิยามไว้อย่างชัดเจน (OWASP ASVS 5.0 L2 + scanner battery)

คำว่า "ปลอดภัย" เป็น claim ที่พิสูจน์ไม่ได้และ auditor ไม่รับ ส่วน
"ผ่าน gate ชุดนี้ ทุก push, reproduce ได้" เป็น claim ที่พิสูจน์ได้ —
ทุกการตัดสินใจในเอกสารนี้ไล่มาจากหลักข้อนี้

## 2. สถาปัตยกรรมเป้าหมาย: 3 ชั้น

| ชั้น | คืออะไร | ผูกกับ framework? |
| :--- | :--- | :--- |
| **Policy** | นิยาม gate ทั้งหมดเป็น machine-readable ไฟล์เดียว: gate id → มาตรฐานอ้างอิง (ข้อ ASVS) → คำสั่งตรวจ → เกณฑ์ผ่าน | ไม่ — portable 100% |
| **Skill / Overlay** | SKILL.md แกนกลาง (กฎสากล) + overlay ต่อ framework ที่มี enforcement script และ CI template ของภาษาตัวเอง | overlay ผูก, แกนกลางไม่ผูก |
| **Reference implementation** | repo นี้ — หลักฐานว่า gate ทั้งหมดผ่านได้จริงบนแอปจริง พร้อมตัวเลขวัดจริง | ผูก (Flask) โดยตั้งใจ |

หลักการแบ่งชั้น: **abstraction อยู่ที่ชั้น policy ไม่ใช่ชั้น runtime**
กฎอย่าง "logic ห้ามรู้จัก HTTP" เป็นสากล แต่ตัวบังคับ (AST scan) เป็นของ
Python/Flask — overlay ของ framework อื่นเขียน enforcement ของตัวเอง
โดยอ้างกฎข้อเดียวกัน

## 3. งานที่ต้องทำ (เรียงตามลำดับพึ่งพา)

### 3.1 แยก policy ออกจากโค้ด — `gates.yaml`

สกัดกฎที่ปัจจุบันฝังกระจายอยู่ในเทสต์และ CI 22 jobs ออกมาเป็นไฟล์นิยามเดียว
โครงต่อ gate อย่างน้อย: `id`, `standard` (เช่น ASVS V.x.y), `check`
(คำสั่งที่รันได้จริง), `pass_criteria`, `severity`

**เงื่อนไขสำเร็จ:** CI jobs ถูก generate จาก `gates.yaml` (หรืออย่างน้อย
มีเทสต์พิสูจน์ว่า CI กับ gates.yaml ตรงกัน ไม่มีการเขียนมือคู่ขนานสองที่)
และ `docs/ASVS.md` regenerate โดยอ้าง gate id ได้

> งานนี้คือหัวใจของความ portable — ทุกข้อถัดไปพึ่งไฟล์นี้ ต้องทำก่อน

### 3.2 Restructure `CLAUDE.md` → skill ที่ import ได้

`CLAUDE.md` ปัจจุบันคือ proto-skill อยู่แล้ว (บันทึกกับดักทุกอันที่เคยตกไป)
แตกเป็น:

- `SKILL.md` แกนกลาง: กฎสากล (logic ไม่รู้จัก protocol, delete = soft-delete
  เท่านั้น, ทุก write ถูก audit, เทสต์ใหม่ต้องพิสูจน์ว่าจับของจริงได้,
  plugin dependency แยก category) — เขียนโดย**ไม่เอ่ยชื่อ library ของ Flask**
- `overlays/flask/`: enforcement เฉพาะทาง — AST scan, pipenv category rule,
  Talisman/Flask-Limiter config, CI template — ทุกอันอ้าง gate id จาก
  `gates.yaml`

**เงื่อนไขสำเร็จ:** repo เปล่า (ไม่ใช่ repo นี้) import skill + overlay แล้ว
ได้ gate ชุดเดียวกันโดยไม่ต้อง copy โค้ดจาก repo นี้

### 3.3 Migration class ใน plugin contract + วัด downtime จริง

plugin contract ทุก type ต้องประกาศ **migration class** ของตัวเอง:

| Class | ความหมาย | Port ที่คาดว่าอยู่ class นี้ |
| :--- | :--- | :--- |
| `live` | สลับได้โดย request ไม่หลุด | theme, 2FA method, cache, secret source (dual-read) |
| `warm` | session เดิมอยู่ต่อ ผู้ใช้ใหม่ไปทางใหม่ | primary auth / IdP (OIDC↔LDAP) |
| `cold` | ต้องหยุดเขียนช่วงสั้น ๆ (swap-at-deploy) | database brand |

เพิ่ม bench script ที่**วัดจริง**: downtime (วินาที) และ request ที่ fail
ระหว่างสลับแต่ละ port ภายใต้ load เก็บตัวเลขลง `docs/PERFORMANCE.md`
class ที่ประกาศไว้ต้องมีตัวเลขรองรับ — ประกาศ `live` แล้ววัดได้ downtime > 0
ที่มีนัยสำคัญ = เทสต์แดง

**เงื่อนไขสำเร็จ:** ทุก plugin type มี class ประกาศ + ตัวเลขวัดจริงอย่างน้อย
1 คู่สลับต่อ type และตาราง class เป็นส่วนหนึ่งของ contract ที่เทสต์ตรวจ

### 3.4 Fail-fix loop harness

script/workflow ที่ทำงานเป็นวงรอบ:

```
agent output → รัน gate ทั้งหมดจาก gates.yaml
             → คืน failure เป็น machine-readable feedback (gate id, สาเหตุ, hint)
             → agent แก้ → วนใหม่ จนผ่านครบ
             → บันทึกจำนวนรอบและ gate ที่ fail บ่อยลง log
```

นี่คือกลไกที่เปลี่ยน checklist ให้เป็น **enforcement loop** — จุดต่างหลัก
ของงานนี้จากมาตรฐาน/checklist ที่มีอยู่แล้ว (NIST SSDF, OpenSSF Scorecard)
ซึ่งออกแบบมาให้คนอ่าน ไม่ใช่ให้เครื่องบังคับ

**เงื่อนไขสำเร็จ:** รัน harness กับ feature branch ที่ตั้งใจใส่ช่องโหว่
แล้ว loop ตรวจเจอ, feedback พาแก้จนผ่าน, จำนวนรอบถูกบันทึก

### 3.5 Harness เปรียบเทียบ (ทำหลัง 3.4 เสถียร)

spec กลาง 1 ชุด → ให้ agent generate แอป N รอบ แบบมี skill กับไม่มี →
ยิง scanner battery ชุดเดียวกัน → เทียบ vulnerability density,
ASVS pass rate, จำนวนรอบ fail-fix จนผ่าน — ได้ตัวเลขยืนยันว่า scaffolding
นี้เปลี่ยนผลลัพธ์จริง ไม่ใช่แค่พิธีกรรม

## 4. นอก scope (ตัดโดยตั้งใจ — ควรบันทึกเป็น ADR)

- **Database brand live-swap ผ่าน CDC/dual-write** — เป็นงานขนาดหนึ่งโปรเจกต์
  เต็ม ๆ ในตัวเอง swap-at-deploy (`cold`) ที่มีอยู่เพียงพอต่อ claim
  "alternative ทดแทนกันได้" แล้ว
- **Universal cross-framework runtime** (abstraction layer ให้ component
  สลับข้าม framework ที่ระดับ runtime) — ขัดกับมูลค่าของ framework ecosystem
  เอง และ maintenance matrix (framework × plugin type) โตแบบคูณ
  ทางที่เลือกคือ abstract ที่ชั้น policy ตามข้อ 2
- **Overlay ของ framework อื่น (Laravel, Django)** — เป็น phase หลังจาก
  พิสูจน์ครบวงจรบน Flask แล้วเท่านั้น overlay เดียวที่สมบูรณ์พิสูจน์
  สถาปัตยกรรมได้ดีกว่าสามอันที่ครึ่ง ๆ กลาง ๆ

## 5. Deliverable สุดท้าย 3 ชิ้น

1. **Skill + overlay** ที่ import เข้า project อื่นได้ (ข้อ 3.1–3.2, 3.4)
2. **Repo นี้** เป็น reference implementation ที่ผ่าน gate ครบ พร้อมตัวเลข
   migration ที่วัดจริง (ข้อ 3.3)
3. **ผลเปรียบเทียบ** มี/ไม่มี skill (ข้อ 3.5)

ชิ้นแรกคือของที่คนอื่นเอาไปใช้ ชิ้นที่สองคือหลักฐาน ชิ้นที่สามคือบทพิสูจน์

## 6. สิ่งที่ต้องส่งมอบจากเอกสารนี้ (คำสั่งถึง Claude Code)

อ่านเอกสารนี้ประกอบกับสภาพจริงของ codebase แล้วผลิต **แผน phase** ก่อนแก้โค้ด:

1. สำรวจ codebase ยืนยัน/แก้ไขสมมติฐานในเอกสารนี้ (เช่น รายชื่อ plugin type
   จริง, กฎที่ฝังอยู่ใน CI จริงมีกี่ข้อ) — ถ้าพบว่าข้อใดในเอกสารนี้ขัดกับ
   ของจริง ให้ทักก่อน อย่าเงียบ ๆ ทำตาม
2. แตกงานข้อ 3.1–3.5 เป็น phase ที่แต่ละ phase merge ได้โดย CI เขียวตลอด
   (ห้ามมี phase ที่ทิ้ง main ให้แดงข้ามสัปดาห์) ระบุ: ขอบเขต, ไฟล์ที่กระทบ,
   เงื่อนไขสำเร็จที่ตรวจด้วยเครื่องได้, ความเสี่ยง, สิ่งที่ต้องทำก่อน
3. เขียน ADR ร่างสำหรับข้อ 4 (สิ่งที่ตัดออก) และสำหรับการตัดสินใจโครง
   `gates.yaml`
4. กติกาเดิมของ repo คงเดิมทั้งหมด: coverage 96% ขึ้นทางเดียว, เทสต์ใหม่ต้อง
   พิสูจน์ว่าจับของจริงได้, core ห้ามรู้จักชื่อ plugin — งานปรับ infra
   ครั้งนี้ต้องผ่าน gate ของตัวเองด้วย
