# Architecture Description — ตามโครง ISO/IEC/IEEE 42010

เฟส 13-05 ([ROADMAP-FEATURES.md](ROADMAP-FEATURES.md)) — ส่วนเดียวของกลุ่ม
กรอบมาตรฐานองค์กรที่รับเข้ามา (เหตุผลที่ตัดตัวอื่นอยู่ใน `ADR 0043`):
42010 ว่าด้วย*คำอธิบายสถาปัตยกรรม* ซึ่ง repo นี้มีวัตถุดิบครบอยู่แล้วในรูป
ADR — ไฟล์นี้จึงเป็น**ดัชนีที่จัดเรียงตามมุมมอง** ไม่ใช่เอกสารใหม่ที่เล่าเรื่อง
คู่ขนาน (ที่ที่สาม = ที่ให้ drift) · `tests/test_architecture.py` ตรวจว่า
ทุกการอ้างอิงชี้ไปหาของที่มีจริง

## 1. ระบบและบริบท (context)

แอปจดงานส่วนตัวแบบ multi-user ที่ตั้งใจทำวิศวกรรมรอบตัวมันจนสุดทาง และ
ถูกยกระดับเป็น reference implementation ของ scaffolding ที่ export ได้
(เฟส 8–12) · เป้าการใช้งาน: ส่วนตัว/ครอบครัว — 5 concurrent (`ADR 0031`)
· ขอบเขตที่ตัดโดยตั้งใจอยู่ใน `docs/ROADMAP.md` (หมวดที่ไม่ทำ) และ `ADR 0040`

## 2. ผู้มีส่วนได้เสียและความกังวล (stakeholders & concerns)

| ผู้มีส่วนได้เสีย | ความกังวลหลัก | ตอบที่มุมมอง |
|---|---|---|
| เจ้าของ/ผู้พัฒนา | แก้แล้วไม่พังของเดิม · บทเรียนไม่สูญ | Development · ทุก ADR |
| ผู้ deploy | รันจริงได้ · ข้อมูลไม่หาย · กู้ระบบได้ | Deployment · Data |
| ผู้ใช้ | ข้อมูลของตัวเองปลอดภัยและขอคืน/ลบได้ · งาน private ไม่รั่วแม้แชร์บางใบ | Security · Data |
| ผู้ดูแลระบบ (admin) | จัดการบัญชี/วงได้โดยเห็นข้อมูลส่วนบุคคลน้อยที่สุด (mask + unmask ที่ลง audit) | Security (ADR 0044/0045) |
| ผู้รับ scaffolding (โปรเจกต์อื่น) | เอากฎไปใช้ได้โดยไม่แบกของที่ไม่ใช่ของตัว | Development (ชั้นของกฎ) |
| ผู้ตรวจ (auditor/เครื่องมือ) | เคลมทุกข้อชี้หลักฐานได้ | ทุกมุมมอง — หลักฐานคือเทสต์ |

## 3. มุมมอง (viewpoints) และภาพ (views)

### 3.1 โครงสร้าง (Structure)

core + plugin แบบ Moodle: core รู้แค่*วิธีค้นหา* ไม่รู้จักชื่อ plugin ตัวไหนเลย
(`ADR 0023` · `ADR 0025` · บังคับโดย `tests/test_plugins.py`) · ตรรกะทั้งหมด
อยู่ใน `app/services/` ซึ่งไม่รู้จัก HTTP — route/API/CLI เป็น adapter บาง ๆ
สามทางบน service ชุดเดียว (`ADR 0016` · บังคับโดย `tests/test_service_layer.py`)
· จุด plug ทุกชนิดเลือกด้วย config ตัวเดียว: ฐานข้อมูลเลือกด้วย scheme ของ
DATABASE_URL (`ADR 0026`) · แหล่งความลับด้วย SECRETS_URL (`ADR 0030`) ·
ปัจจัยยืนยันตัวตนผ่านสัญญาแคบ ๆ ของ `app/services/mfa.py` และ
`app/services/sso.py` (`ADR 0024` · `ADR 0028`) — และ auth plugin ภายนอก
หนึ่งตัวรับได้หลายชุด config เป็น *profile* ที่ประกาศลำดับใน AUTH_PROFILES
(`ADR 0047` — คำปฏิเสธเป็นที่สิ้นสุด fallback เฉพาะติดต่อไม่ได้) · หน้า admin
เป็น core package ที่เสียบ panel ได้ ไม่ใช่ plugin — ความสามารถถอดได้ =
วินัยถอดได้ (`ADR 0044`)

### 3.2 ข้อมูล (Data)

ทุกตารางขึ้นต้น tdl_ (`ADR 0013`) · schema มาจาก migration เท่านั้น และ
model ต้องตรงกับ migration เป๊ะ (`tests/test_migrations.py`) · "ลบ" ทั้งระบบ
แปลว่าซ่อน — ลบจริงมีที่เดียวคือ `app/purge.py` ตามระยะใน
`docs/DATA-CLASSIFICATION.md` (`ADR 0014`) · ทุกการเขียนลง audit trail
แบบเติมได้อย่างเดียว + hash chain ที่ต่อคิวบนแถวล็อกเดียว (`ADR 0015` ·
`ADR 0035`) · ทุกคอลัมน์ถูกจัดชั้นและถูกตัดสินเรื่อง export
(`tests/test_data_classification.py` · `tests/test_personal_data.py`)
· ความลับปัจจัยที่สอง encrypt at rest ใต้คีย์ที่แยกจาก SECRET_KEY
(`ADR 0046` · `tests/test_totp_encryption.py`) · org graph เพิ่มห้าตาราง
ที่เดินครบวงจรเดิมทุกข้อ (รวมบันทึกเปลี่ยนชื่อวงที่สมาชิกอ่านได้ — CR#3
ตั้งใจแยกจาก audit trail ซึ่งเก็บค่า C3 เป็น HMAC) และการแบ่งปันข้ามผู้ใช้
เผยสี่ฟิลด์ผ่าน view เดียว (`ADR 0049` · `tests/test_org_graph.py`)

### 3.3 ความปลอดภัย (Security)

ประเมินต่อ ASVS 5.0 L2 ครบ 253 ข้อใน `docs/ASVS.md` — หลักฐานทุกชิ้นถูก
เทสต์ตรวจว่ามีจริง และ crosswalk ที่ generate (`docs/GATES-ASVS.md`) บอกว่า
แถวไหนมีด่านรันทุก push หนุน · การตัดสินใจแกน: ของคนอื่นตอบ 404 ไม่ใช่ 403
(`ADR 0004`) · session ผูกกับ credential ปัจจุบัน (`ADR 0020`) · RBAC ตรวจ
ใน service (`ADR 0022`) · CSP ไม่มี inline (`ADR 0010`) · MFA เสนอแต่ไม่
บังคับ พร้อมมาตรการชดเชยที่มีเทสต์คุม (`ADR 0033`) · ข้อมูลผู้ใช้บนหน้า
admin ผ่านชั้น mask ตามชั้นข้อมูล และการเปิดดูเต็มลง audit (`ADR 0045` ·
`tests/test_masking.py`) · ระงับบัญชีแบบย้อนกลับได้ครอบทุกช่องทางเข้า
(`tests/test_suspension.py`) · ชั้น legal เป็น worksheet แยก: `docs/PDPA.md`

### 3.4 การ deploy (Deployment)

stack จริงอยู่ใน `compose.yaml` + overlay ต่อยี่ห้อ/ความสามารถ (เลือกด้วย
ไฟล์ ไม่ใช่ตัวแปร — ไฟล์เดียวเปลี่ยนทั้ง service และ URL จึงขัดกันเองไม่ได้)
· reverse proxy + TLS + ≥2 replica พิสูจน์ทุก push โดย `ci:stack` ·
proxy เชื่อ header ตามจำนวนชั้นที่ประกาศ (`ADR 0027`) · งานลบข้อมูลตามระยะ
เป็น systemd timer จริง (`deploy/systemd/`) · migration class ของ plugin
(live/warm/cold) ประกาศต่อ plugin พร้อมตัวเลขวัดหนุน (`ADR 0041` ·
`docs/PERFORMANCE.md`) · liveness/readiness แยกกันและไม่มี token
(healthz/readyz ใน `app/health.py`) · สัญญา N-1 + วินัย expand–contract
มีด่านรันทุก push (`scripts/n1_smoke.py`) · graceful shutdown เป็นส่วนหนึ่ง
ของสัญญา rolling (`ADR 0048`) · Prometheus ดูด metrics ผ่านด่าน token จริง
(`compose.metrics.yaml` · `deploy/prometheus.yml`)

### 3.5 การพัฒนา (Development)

กฎทุกข้อของ repo อยู่ในดัชนี `gates.yaml` ที่ตรวจสองทิศ (`ADR 0039`) และ
ประกาศชั้นของตัวเอง: baseline → `SKILL.md` · business → `SKILL-TODOLIST.md`
· internal ไม่ export (`ADR 0042`) · ตัวบังคับสำหรับโปรเจกต์อื่นคือ
`overlays/flask/` ซึ่ง dogfood กับ repo นี้เองทุก push · ผลลัพธ์ถูกวัดจริง
ด้วยการทดลองสามแขนใน `docs/comparison/` · วินัยการพัฒนาโดยละเอียดอยู่ใน
`docs/DEVELOPMENT.md` และ `CONTRIBUTING.md`

## 4. กติกาความสอดคล้องข้ามภาพ (correspondence rules)

ทุกคู่ต่อไปนี้มีเทสต์บังคับให้ตรงกัน — ไม่ใช่ขอความร่วมมือ:

| คู่ | ตัวบังคับ |
|---|---|
| model ↔ migration | `tests/test_migrations.py` |
| gates.yaml ↔ CI jobs ↔ ไฟล์เทสต์ | `tests/test_gates.py` |
| gates.yaml ↔ SKILL สองใบ | `tests/test_skill.py` |
| gates.yaml ↔ overlay | `tests/test_overlay.py` |
| ASVS ↔ หลักฐาน ↔ crosswalk | `tests/test_asvs.py` · `tests/test_gates.py` |
| ROPA/runbook ↔ ตาราง/ค่าจริงในโค้ด | `tests/test_ropa.py` |
| ชั้นข้อมูล ↔ คอลัมน์จริง | `tests/test_data_classification.py` |
| คำตัดสิน masking ↔ ชั้นข้อมูล | `tests/test_masking.py` |
| PDPA worksheet ↔ หลักฐานจริง | `tests/test_pdpa.py` |
| คำประกาศ privacy ของ org graph ↔ พฤติกรรมจริงทุกช่องทาง | `tests/test_org_graph.py` |
| เอกสารฉบับนี้ ↔ ไฟล์/เทสต์ที่มันอ้าง | `tests/test_architecture.py` |
| เลขที่โฆษณาในเอกสาร ↔ ดิสก์ | `tests/test_contributor_docs.py` · `tests/test_changelog.py` · `tests/test_skill.py` |

## 5. เหตุผลของการตัดสินใจ (rationale)

ทั้งหมดอยู่ใน `docs/adr/` — ทุกใบบันทึกทางที่*ไม่ได้เลือก*และเงื่อนไขที่ทำให้
คำตัดสินหมดอายุ ดัชนีอยู่ที่ `docs/adr/README.md` (เทสต์บังคับไม่ให้มีรูเลข)

## 6. การเทียบกับข้อกำหนดของ 42010

| ข้อกำหนดของมาตรฐาน | ตอบด้วย |
|---|---|
| ระบุ system-of-interest และบริบท | หัวข้อ 1 |
| ระบุ stakeholders และ concerns | หัวข้อ 2 |
| viewpoint ที่ประกาศและ view ที่สอดคล้อง | หัวข้อ 3 (5 มุมมอง) |
| correspondence rules ระหว่าง view | หัวข้อ 4 — เป็นเทสต์ ไม่ใช่คำอธิบาย |
| architecture decision + rationale | หัวข้อ 5 → `docs/adr/` |
| ความไม่สอดคล้องที่รู้ (known inconsistencies) | ของค้างทั้งหมดประกาศใน `docs/ROADMAP.md` (หมวดของค้าง) และ backlog ของ `docs/ASVS.md` · `docs/PDPA.md` |

## รอบทบทวน

ทบทวนเมื่อเพิ่ม viewpoint/จุด plug ชนิดใหม่ หรือเมื่อ ADR ใหม่พลิกคำตัดสิน
ที่ไฟล์นี้อ้าง — การอ้างอิงเน่าไม่ต้องรอรอบ: เทสต์จับทันทีที่ไฟล์/ADR หาย
