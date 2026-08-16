# Roadmap — ยกระดับ todolist ให้ถึงเกณฑ์ ISO/IEC 25010:2023 + Audit/Data Governance

> เอกสารนี้คือแผนแม่บทของโปรเจกต์ ใช้ ISO/IEC 25010:2023 เป็นโครง (ตัด Functional
> Suitability ออก) บวก 2 กลุ่มที่มาตรฐานไม่ครอบคลุมเต็มที่: Audit Trail และ
> Data Retention — จัดเป็นเฟสที่ **เรียงตามหลักลด rework** ไม่ใช่เรียงตามหมวดมาตรฐาน
>
> **ขอบเขตของไฟล์นี้คือ Phase 0–7 ของ *ตัวแอป* ซึ่งปิดครบแล้ว (2026-08-12)**
> · งานเฟส 8–12 เป็นเรื่องของ *scaffolding ที่ export ออกไปได้* และอยู่ใน
> [`ROADMAP-INFRA.md`](ROADMAP-INFRA.md) คนละไฟล์โดยตั้งใจ — คนละคำถาม
> (แอปนี้ดีพอหรือยัง กับ วินัยนี้ย้ายไปที่อื่นได้ไหม) และคนละเกณฑ์ตัดสิน
> · ส่วนเฟส 13–18 (ชั้นฟีเจอร์ของ v1.1.0 — ปิดครบ 2026-08-15) อยู่ใน
> [`ROADMAP-FEATURES.md`](ROADMAP-FEATURES.md) · และแผน G (governance ตาม
> ธรรมนูญ ADR 0051 — ปิดครบทั้งใบ 2026-08-16) อยู่ใน
> [`ROADMAP-GOVERNANCE.md`](ROADMAP-GOVERNANCE.md)
>
> หมวดที่ตัดออกโดยเจตนา (บันทึกไว้ แต่ไม่ทำใน app นี้):
> - **Reliability & Availability** — SLA/RTO/RPO/backup 3-2-1 ผูกกับ infra จริง
>   ถ้ากลับมาทำ ให้แทรกหลัง Phase 5 (ต้องมี container/IaC ก่อนถึงจะพูดเรื่อง DR ได้จริง)
> - **Safety** — น้ำหนักต่ำสำหรับ business/admin app ที่ไม่ trigger ผลทางกายภาพ

---

## 1. หลักการจัดลำดับ (ทำไมเฟสถึงเรียงแบบนี้)

เรียงตาม "ต้นทุนการย้อนแก้โตตามอะไร":

1. **งานที่ทุกบรรทัดใหม่ต้องสืบทอด มาก่อนสุด** — pattern ของ template, รูปแบบ log,
   ความหมายของการลบข้อมูล ฯลฯ ยิ่งทำช้า โค้ดที่ต้องย้อนแก้ยิ่งงอกตามฟีเจอร์ที่เพิ่ม
2. **งานที่เปลี่ยน "ความหมายของข้อมูล" ต้องมาก่อนการประกาศ contract** —
   OpenAPI v1 คือการ freeze ความหมาย ถ้าเปลี่ยน semantics (เช่น hard delete →
   soft delete) หลังประกาศ v1 จะกลายเป็น breaking change ทันที
3. **สร้าง seam ก่อนแล้วค่อยเพิ่ม consumer** — service layer ต้องมาก่อน API และ SSO
   ไม่งั้นของพวกนั้นจะเกาะ routes แล้วต้องรื้อสองรอบ
4. **infra wrapper (container, IaC) เป็น additive** — วางกลางแผนได้โดยไม่แตะโค้ดแอป
5. **การวัดและพิสูจน์อยู่ท้ายสุด** — load test, pentest, ASVS assessment
   ต้องมีของจริงครบก่อนถึงจะวัดได้อย่างสัตย์จริง ไม่ใช่วัดของครึ่งทาง

## 2. ตัวคูณ rework ที่พบในโค้ดปัจจุบัน (สแกนจริง ณ commit `3f17b3b`)

| หนี้ | ชนกับ | ขนาดตอนนี้ | โตตามอะไร |
|---|---|---|---|
| inline JS/style ใน template (8 จุด, 4 ไฟล์) | CSP strict (security headers) | เล็ก | ทุก template ใหม่ |
| hard delete (4 จุด: todo, clear-completed, category, delete-user) | temporal modeling / retention / PDPA | กลาง | ทุก route ที่แตะข้อมูล |
| business logic ฝังใน `routes.py` (431 บรรทัด, 37 functions) | API contract + SSO | กลาง | ทุก route ใหม่ |
| SQLite ไม่บังคับ FK (`pragma foreign_keys=0`) | data integrity | จุดเดียว | คงที่ (แต่เสี่ยงสะสม) |
| rate limiter `memory://` ต่อ process | horizontal scale | จุดเดียว | คงที่ |

## 3. ทุนที่มีแล้ว (ไม่ต้องทำซ้ำ นับเป็นข้อได้เปรียบ)

- CSRF ทั้งแอป + เทสต์แยกที่เปิดใช้จริง / rate limit หน้า login (ต่อ IP, deduct on 401)
- `SECRET_KEY` จาก env เท่านั้น ไม่มี default, ยาวขั้นต่ำ 32 — fail closed ตั้งแต่ start
- รหัสผ่าน scrypt / ownership check ตอบ 404 / ไม่มี `?next=` (กัน open redirect)
- i18n en/th ผ่าน gettext จริง + เทสต์ดัก fuzzy/untranslated
- เวลาเก็บ UTC ทั้งระบบ แปลงตาม timezone ผู้ใช้ + ตารางดวงอาทิตย์ 598 โซน
- **สถาปัตยกรรม plugin (theme) ที่พิสูจน์แล้วว่า purge ได้โดยไม่แตะ core** —
  เป็นฐานของ auth plugin (MFA) ใน Phase 4 จริงตามที่วางไว้ และของ SSO ใน Phase 5
- เทสต์ 211 ตัว + วัฒนธรรม mutation testing + migration ที่ทดสอบ round trip

## 4. กลยุทธ์ data layer แบบ plugin

ทิศทางที่กำหนด: backend ของฐานข้อมูลเป็น plugin โดย **built-in = SQLite 3,
MySQL 8+, MariaDB 11+** ส่วนยี่ห้ออื่นเพิ่มทีหลังเป็น plugin
เลขเวอร์ชันทั้งหมดเป็น floor ตาม security baseline — เกณฑ์จริงคือ
"vendor ยัง support และได้รับ security patch" ณ เวลา deploy ไม่ใช่ตัวเลขตายตัว

การวิเคราะห์แยกเป็น 3 ชั้นที่ธรรมชาติต่างกัน (สำคัญ — อย่าออกแบบรวมเป็นชั้นเดียว):

### 4.1 Relational backends — สับเปลี่ยนกันได้จริง
MySQL/MariaDB/PostgreSQL/Oracle/SQL Server ใช้ schema + migration ชุดเดียวกันผ่าน
SQLAlchemy ตัว plugin ต่อยี่ห้อจึงบาง: driver + dialect quirk handler +
compose service + healthcheck + preset ค่า connection

- **Cloud-compatible ไม่ใช่ plugin แยก** — Amazon RDS/Aurora MySQL, Azure Database
  for MySQL, Cloud SQL for MySQL คือ MySQL wire-compatible → อยู่ใน plugin
  ตระกูล mysql ด้วย config preset (ฝั่ง PostgreSQL ก็แบบเดียวกัน) ไม่งั้นจะมี
  plugin ซ้ำซ้อนหลายตัวที่ต่างกันแค่ connection string
- **Purge semantics ต่างจาก theme โดยพื้นฐาน:** theme ถอนแล้ว fallback ได้
  แต่ DB backend ที่ active ถอนไม่ได้ (ข้อมูลอยู่ในนั้น) — สัญญาของ db plugin คือ
  ห้าม purge ตัวที่ active และต้องมี export/migrate path ก่อนถอนเสมอ
  (หลัก no-lock-in ใช้กับ plugin ภายในของเราเองด้วย)

### 4.2 Document/Graph (MongoDB, Neo4j) — ไม่ใช่บ้านทางเลือกของ core data
ประเด็นที่ต้องตรงไปตรงมา: document/graph DB รัน SQLAlchemy model ชุดเดียวกับ
relational ไม่ได้ ถ้าจะให้เป็น "ทางเลือกของ core data" ต้องรื้อทั้ง data access
เป็น repository pattern ซึ่งทิ้งการลงทุนใน SQLAlchemy/Alembic ทั้งหมด — ไม่คุ้ม

การจัดวางที่เข้ากับสัญญา plugin ที่มีอยู่พอดีคือ: **feature plugin ที่มี store
ของตัวเอง** เช่น "task relationship graph" เป็น plugin ที่ใช้ Neo4j ของตัวเอง
core data ยังอยู่ relational — ตรงกับสัญญาเดิมเป๊ะ: plugin ดูแลข้อมูลตัวเองล้วน ๆ
purge แล้ว store ของมันหายไปด้วยโดย core ไม่กระทบ (กลไก plugin-owns-its-own-data
**ออกแบบและทำจริงแล้วใน Phase 4 สำหรับ MFA — ADR 0023** ใช้ซ้ำกับชั้นนี้ได้เลย
โดยส่วนที่ต้องเพิ่มคือ store ที่ไม่ใช่ตาราง SQL ในฐานข้อมูลเดียวกัน)

### 4.3 Cache (Redis/memcache) — interface ใน core, backend เป็น plugin
core ประกาศ cache interface (get/set/invalidate) โดย default เป็น no-op
(ไม่มี cache ระบบต้องยังถูกต้อง แค่ช้ากว่า — cache เป็น optimization ห้ามเป็น
correctness) backend จริงเป็น plugin และ rate-limiter storage ใช้ backend
เดียวกันนี้แทนที่จะถือ Redis connection แยกเอง

### 4.4 Landmines ด้าน dialect ที่มีอยู่แล้วในโค้ด (สแกนจริง)

| จุด | ระเบิดกับ | แก้ที่ไหน |
|---|---|---|
| ~~raw SQL `UPDATE user SET ...` ใน migration `296ab616c11b` — `user` เป็น reserved word~~ **ปิดแล้ว** | PostgreSQL/Oracle/MSSQL (fresh install ที่ replay migration) — **MySQL/MariaDB รอด** | Phase 2: rename เป็น `tdl_user` (หมดปัญหาถาวร) + **P5-02: ยุบสายเดิม 13 ตัวเป็น baseline `5ffefa218ed7` ✅ raw SQL หายไปทั้งหมด** |
| ~~MySQL `DATETIME` default ตัด microsecond แต่โค้ดเก็บ `datetime.now()` เต็ม precision~~ **ปิดฝั่งประกาศแล้ว** | MySQL/MariaDB (silent truncation กระทบ ordering tie และ audit hash) | **P5-03: `UTCDateTime` ใน `app/db_types.py` ประกาศ variant `DATETIME(6)` ครอบทั้ง mysql/mariadb ✅ ทุกคอลัมน์เวลารวมของ plugin** — เหลือพิสูจน์ค่าจริงที่วิ่งไปกลับใน CI matrix (P5-04) |
| ~~`batch_alter_table` + data fix เฉพาะ SQLite ใน migration เก่า~~ **ปิดแล้ว** | ไม่ระเบิด (no-op บนยี่ห้ออื่น) แต่รก | **P5-02: หายไปพร้อมการยุบสาย ✅ baseline ไม่มี `batch_alter_table` เลยสักจุด** |
| ชื่อคอลัมน์ String ระบุความยาวครบทุกตัวแล้ว | — | ทุนที่มีแล้ว (MySQL บังคับ) |

**Baseline squash (Phase 5):** ณ จุดที่รองรับหลาย DB จะสร้าง migration ตั้งต้น
ใหม่จาก model ปัจจุบันสำหรับ fresh install (สาย migration เก่าเก็บไว้ให้ DB
ที่มีอยู่ upgrade ตามปกติ) — ตัดปัญหา raw SQL เก่าทั้งหมดในคราวเดียว

### 4.5 วินัย dialect มีผลตั้งแต่วันนี้ (ต้นทุน ≈ 0 ถ้าเริ่มตอนนี้)
migration และโค้ดใหม่ทุกตัวจากนี้ต้อง:
1. raw SQL ใน migration ต้องอ้างตารางแบบ quoted (`"user"`) หรือใช้ SQLAlchemy
   construct — โดยเฉพาะตาราง `user`
2. ห้าม assume microsecond precision — อย่าเทียบ DATETIME แบบ exact ข้าม insert
   และของที่ต้อง hash (audit) ให้ serialize เวลาเป็น ISO string ฝั่งแอปก่อน
3. คอลัมน์ String ระบุความยาวเสมอ / ห้ามใช้ type เฉพาะ dialect โดยไม่มี variant

---

## เฟสทั้งหมด (ภาพรวม)

| เฟส | ชื่อ | ขนาด | ตอบหมวด |
|---|---|---|---|
| 0 ✅ | Process backbone | S | Maintainability |
| 1 ✅ | Cross-cutting inheritance | M | Security(headers), Interaction, Maintainability |
| 2 ✅ | Data governance core | L | Audit Trail, Data Retention, PDPA |
| 3 ✅ | Service layer + API v1 | M–L | Compatibility, Maintainability |
| 4 ✅ | Identity & AuthN/AuthZ | L | Security(authn), Compatibility(SSO) |
| 4.5 ✅ | Supply-chain isolation ของจุด plug | M | Security(supply chain), Modularity |
| 5 ✅ | Deployment parity + DB/cache plugins **+ SSO** | M–L | Flexibility, Security(TLS/secrets), Compatibility |
| 6 ✅ | Performance validation | M | Performance Efficiency |
| 7 ✅ | Verification & compliance closure | M–L | Security(ASVS/pentest/PDPA), Interaction(WCAG), Audit(SIEM) |

งานต่อเนื่องทุกเฟส: ADR ทุกการตัดสินใจสำคัญ, SCA รายสัปดาห์, SBOM ทุก release,
coverage gate ใน CI

---

## Phase 0 — Process backbone ✅ (เสร็จ 2026-08-03)

**เป้าหมาย:** ทุกเฟสถัดไปถูกคุ้มกันด้วย gate อัตโนมัติ ก่อนจะเริ่มเขียนโค้ดเพิ่ม

- CI pipeline (GitHub Actions) — ชุดเครื่องมือตัดสินแล้วใน `docs/STANDARDS.md` ข้อ 4:
  pytest + coverage (branch mode + threshold + diff-cover), ruff `select=ALL`
  + ruff format, mypy strict แบบ gradual (เริ่มที่ module ที่ pure), semgrep `p/flask`,
  xenon (complexity gate), interrogate (docstring), gitlint (Conventional Commits),
  `pip-audit` (SCA), secret scanning, pre-commit ฝั่งเครื่อง dev
- SBOM: `cyclonedx-py` generate ทุก release เก็บเป็น artifact
- ไดเรกทอรี `docs/adr/` + backfill ADR ของการตัดสินใจที่ทำไปแล้ว
  (UTC storage, msgid ภาษาอังกฤษ, CSRF ก่อน login_required, plugin architecture,
  404 แทน 403, ตารางดวงอาทิตย์ฝังในแอป)
- นโยบาย: ไม่มี manual deploy ข้าม pipeline (ตอนนี้ = push เข้า main ต้องเขียวก่อน)
- migration lint อย่างง่ายใน CI: จับ raw SQL ที่อ้างตาราง `user` แบบไม่ quote
  (บังคับวินัย dialect ข้อ 4.5 ตั้งแต่ migration ตัวถัดไป)

**ทำไมต้องก่อน:** ไม่แตะโค้ดแอปเลย (rework = 0) แต่ทุกบรรทัดหลังจากนี้ถูกตรวจฟรี
ยิ่งช้า โค้ดที่ไม่เคยผ่าน gate ยิ่งสะสม
**DoD:** push ที่ทำให้เทสต์แดง/coverage ตก/มี CVE ใหม่ ถูกบล็อกอัตโนมัติ

## Phase 1 — Cross-cutting inheritance ✅ (เสร็จ 2026-08-03)

**เป้าหมาย:** เก็บหนี้ที่ "ทุก template และทุก request ใหม่ต้องสืบทอด" ให้หมดตอนที่ codebase ยังเล็ก

- **CSP-ready** (ADR 0010): ย้าย inline handler และ `style=` ออกจาก template จนหมด
  → `app/static/app.js` ตัวเดียวแบบ event delegation คุยผ่าน `data-*`
  เปิด security header จริงด้วย Flask-Talisman: CSP `'self'` ล้วน **ไม่มี
  `unsafe-inline`/`unsafe-eval`**, `base-uri`/`object-src`/`frame-ancestors` = `'none'`,
  `X-Content-Type-Options`, `Referrer-Policy`, cookie `HttpOnly`+`SameSite=Lax`
  ของที่ผูก TLS (HSTS/บังคับ https/cookie `Secure`) รวมไว้ที่ `HTTPS_ENABLED` ตัวเดียว
  รอเปิดพร้อมกันใน Phase 5
- **WCAG 2.2 AA baseline** (ADR 0012): gate สองชั้น — `tests/test_a11y.py` ตรวจโครงสร้าง
  (รันทุกครั้ง ไม่ต้องมี browser) + job `a11y` ใน CI รัน pa11y-ci 4.1.1 (`htmlcs`+`axe`)
  บน Chromium จริง 11 หน้า ครอบโหมดมืด ธีม ocean และภาษาไทย
  **จับได้จริงตอนตั้ง:** ฟอร์มติ๊กงานเสร็จไม่มีปุ่ม submit เลย — พึ่ง JS ล้วน
  แก้ด้วย progressive enhancement (`.js-hidden`)
- **Structured logging + correlation ID** (ADR 0011): JSON บรรทัดละ event ออก stdout
  ทุก request มี `request_id` (รับต่อจาก `X-Request-Id` เฉพาะที่เป็น UUID จริง)
  `actor` เก็บ username ไม่ใช่ชื่อจริง OpenTelemetry ยังไม่ใส่ — ยังเป็น monolith เดียว
- **แถม:** แก้ต้นเหตุที่ `TestConfig` ไม่สืบทอด `Config` (พังซ้ำมาแล้ว 4 ครั้ง)

**ทำไมตรงนี้:** สามอย่างนี้ต้นทุน retrofit โตเป็นเส้นตรงตามจำนวน template/route
ตอนนี้มี 6 template — ถูกสุดที่จะจ่ายวันนี้
**DoD:** ✅ CSP ไม่มี `unsafe-inline`/`unsafe-eval` ✅ a11y gate เขียวใน CI (11/11)
✅ ทุก request มี request_id ใน log — เทสต์ 292 ผ่าน coverage 93.20% (ratchet 92→93)

## Phase 2 — Data governance core ✅ (เสร็จ 2026-08-03) ★ เฟสที่แพงสุดถ้าทำช้า

**เป้าหมาย:** เปลี่ยนความหมายของ "ลบ" และให้ทุก write ถูกบันทึก **ก่อน** ที่จะมี
ฟีเจอร์/สัญญาใหม่มาทับ

- **ด่านแรก — "schema identity" (migration เดียวจบ, ดู STANDARDS ข้อ 1):**
  เปลี่ยนชื่อตารางเป็น `tdl_*` (core) + กติกา `tdl_<ชนิด>_<ไอดี>_*` สำหรับ plugin,
  ใส่ SQLAlchemy `naming_convention`, `done` → `is_done`,
  rewrite model เป็น SQLAlchemy 2.0 typed style (`Mapped[]`) เปิดทาง mypy strict
  → ผลพลอยได้: ฆ่า landmine reserved word `user` ถาวร ก่อนตาราง audit จะเกิด
- **Data classification ✅ (อนุมัติ 2026-08-03):** `docs/DATA-CLASSIFICATION.md`
  แบ่ง 6 ชั้น C1 ความลับ / C2 PII / C3 เนื้อหาผู้ใช้ / C4 การตั้งค่า /
  C5 audit / C6 log ปฏิบัติการ — retention แยกต่อชั้น: soft delete 30 วัน,
  audit 1 ปี, log 90 วัน, credential ล้างทันทีที่ปิดบัญชี
  มี `tests/test_data_classification.py` บังคับว่าคอลัมน์ใหม่ต้องถูกจำแนก
- **ADR ข้อขัดแย้ง PDPA vs retention ✅ (ADR 0014):** แผนเดิมที่ว่า
  "pseudonymize PII ใน audit ทีหลัง" **ทำไม่ได้จริงเมื่อ audit เป็น hash chain**
  เพราะแก้แถวเก่า = chain ทั้งสายใช้ไม่ได้ → เปลี่ยนเป็น **ไม่เขียน PII ลง audit
  ตั้งแต่แรก** (actor เป็นเลข, ค่าของ C2/C3 เก็บเป็น HMAC) คำขอลบจึงทำได้ครบ
  โดยไม่ต้องแตะ audit สักแถว / purge audit ใช้แถว checkpoint กัน chain ขาด
- **Temporal/soft-delete ✅ (2026-08-03):** `deleted_at` ครบทั้งสามตาราง + `purged_at`
  ของ user / hard delete หมดไปทั้ง 4 จุด (todo, clear-completed, category, delete-user)
  **ตัวกรองไม่ได้ทำเป็น helper ให้เรียกเอง แต่เติมอัตโนมัติทุก ORM query** ผ่าน event
  `do_orm_execute` (`app/soft_delete.py`) เพราะ helper ที่ต้องเรียกเองคือ helper ที่ลืมได้
  purge job อยู่ที่ `app/purge.py` เป็นจุดเดียวในระบบที่ลบจริง มี `flask purge-expired`
  พร้อม `--dry-run` ที่เป็นฟังก์ชันอ่านอย่างเดียวคนละตัวกับของจริง
- **Audit trail ✅ (2026-08-03 — ดู ADR 0015):** ตาราง `tdl_audit` append-only
  แยกจาก data ปกติ (ไม่มี FK ผูก) บันทึกผ่าน event `after_flush` ของ Session
  **ครอบทุก write อัตโนมัติรวม CLI** — actor เป็น `actor_id` (เลข) ไม่ใช่ username
  ตามที่ ADR 0014 กำหนด และ "ที่ไหน" เก็บ `request_id` ไม่เก็บ IP
  (IP มีอายุ 90 วันตามชั้น C6 ก๊อปมาไว้ 1 ปีไม่ได้)
  tamper-evident ด้วย hash chain + `prev_hash` unique ที่ระดับ DB (สายแตกสองสายไม่ได้)
  คำสั่ง `flask audit-verify` / `flask audit-log` ไม่มี route ไหนแตะตารางนี้เลย
  ห้ามแก้/ลบผ่าน ORM (ด่านที่ `before_flush`) purge ตัดได้จากหัวสายเท่านั้นแล้วเขียน
  checkpoint ก่อนลบ เวลาในตารางตัดเศษวินาทีทิ้งให้ผล hash ไม่ขึ้นกับยี่ห้อ DB (ดู 4.5)
  **ข้อจำกัดที่รู้ตัว:** bulk/raw SQL ไม่ถูกดัก, ตัดหางสายหรือลบทั้งตารางแล้วสร้างใหม่
  ยังตรวจไม่ได้ — ต้องส่ง hash ออกไป anchor ที่อื่น ยกไป Phase 7 พร้อมงาน SIEM
- เปิด `PRAGMA foreign_keys=ON` ต่อ connection (ปิดช่อง integrity ของ SQLite)

**ทำไมตรงนี้:** (1) เปลี่ยน semantics ของข้อมูล — ต้องเสร็จก่อน API v1 freeze สัญญา
(2) audit ผ่าน event hooks แปลว่าฟีเจอร์ทุกตัวหลังจากนี้ถูก audit ฟรี
(3) ทุก route ที่เพิ่มก่อนเฟสนี้คือจุด hard-delete ที่ต้องย้อนแก้เพิ่ม
**DoD:** ✅ ไม่มี `session.delete`/bulk delete บนข้อมูลผู้ใช้นอก purge job
✅ mutation test ยืนยันว่า write ที่ไม่ลง audit ถูกจับได้ ✅ verify chain ผ่าน
— เทสต์ 387 ผ่าน coverage 94.88% (ratchet 93→94), audit 97% / purge, soft_delete 100%

**ข้อ DoD แรกเป็นสถานะ ไม่ใช่เหตุการณ์** — จริงวันนี้แล้วเท็จพรุ่งนี้ได้ถ้ามีคนเพิ่ม
route ใหม่ จึงมี `tests/test_write_discipline.py` สแกนโค้ดบังคับไว้ ไม่ปล่อยให้ขึ้นกับ
ความจำ (mutation test 6 แบบ: hard delete, bulk delete, raw SQL, `text()`,
Core DML, `synchronize_session` — จับได้ทั้งหมด)

**ของที่ยกไปเฟสอื่นอย่างตั้งใจ:** ติดตั้งตารางเวลา purge บน host จริง → Phase 5
(สคริปต์พร้อมแล้ว ดู [OPERATIONS.md](OPERATIONS.md)) / anchor hash ออกนอกระบบเพื่อ
จับการตัดหางสายหรือลบทั้งตาราง → Phase 7 พร้อมงาน SIEM (ดู ADR 0015)

## Phase 3 — Service layer + API v1 (contract-first) ✅ (เสร็จ 2026-08-03)

**เป้าหมาย:** แยก business logic ออกจาก HTTP แล้วประกาศสัญญาที่ freeze ได้จริง

- **Service layer ✅ (ADR 0016):** `app/services/` (todos, categories, settings,
  tokens) ไม่รู้จัก HTTP เลย — `app/routes.py` เหลือ adapter ที่อ่าน request
  เรียก service แล้วเลือกคำตอบ ตัวกรองยุบเป็น `FilterSpec` ชุดเดียวที่ทั้งฟอร์ม
  HTML และ query string ของ API แปลงเข้า (ปิดหนี้ `apply_when()` 7 อาร์กิวเมนต์)
  บังคับด้วย `tests/test_service_layer.py` ทั้งสแกน import และรันจริงโดยไม่มี request
- **Personal access token ✅ (ADR 0017):** ตาราง `tdl_api_token` เก็บ sha256 ของ
  ความลับสุ่ม 256 บิต (ไม่ใช่ scrypt — ค่าสุ่มไม่มี dictionary ให้ไล่ ส่วน scrypt
  ต่อ request คือช่องยิงถล่ม) แสดงความลับครั้งเดียวตอนออกใบ เพิกถอนแล้วล้าง hash
  ทันทีไม่รอ grace ออกใบผ่าน CLI เท่านั้น — **token ออก token ไม่ได้** ไม่งั้นใบที่
  หลุดจะแตกลูกที่อายุยาวกว่าเดิมแล้วการเพิกถอนก็ไม่ปิดประตูจริง
- **`/api/v1` ✅ (ADR 0018):** todos + categories + tokens ผ่าน flask-smorest +
  marshmallow view เป็น adapter บาง ๆ เหนือ service เดิม — งานที่สร้างผ่าน API
  โผล่บนหน้าเว็บทันทีและถูก audit ให้เองโดยไม่ต้องเขียนอะไรเพิ่ม (ผลตอบแทนของ
  ADR 0015 ที่จ่ายไปแล้วใน Phase 2) เวอร์ชันอยู่ที่ path, ซอง error รูปเดียว
  ที่ `code` มาจาก service ตรง ๆ, เวลาเป็นเวลาท้องถิ่นของเจ้าของข้อมูลทั้งขาเข้าออก
- **สัญญาไม่มีทางหลุด sync ✅:** `docs/openapi.json` generate จากโค้ดด้วย
  `scripts/generate_openapi.py` มีสองด่านเทียบ (`tests/test_openapi.py` + job
  `openapi` ใน CI ที่ `git diff --exit-code`) **CI ไม่ commit ไฟล์ให้เอง** เพราะ
  commit ของ bot จะกลบการเปลี่ยนสัญญาที่ไม่ตั้งใจแทนที่จะเอามาวางตรงหน้าคนรีวิว

**ทำไมตรงนี้:** หลัง Phase 2 เพื่อให้ v1 เกิดบน semantics สุดท้าย (soft delete แล้ว)
และ API ถูก audit ฟรีผ่าน hooks — ก่อน Phase 4 เพื่อให้ SSO/MFA ลงบน seam ที่นิ่ง
**DoD:** ✅ OpenAPI spec ตรวจใน CI ว่า sync กับโค้ด ✅ เทสต์ API แยกชุด
(`test_api_auth` / `test_api_todos` / `test_api_categories` / `test_api_tokens` /
`test_openapi` / `test_api_fuzz`) ✅ ADR versioning (0018) — เทสต์ 548 ผ่าน
coverage 96.50% (ratchet 94→96, interrogate 65→73), `app/api/*` 100% ทุกไฟล์

**schemathesis เข้ามาตามที่ STANDARDS วางไว้** (`tests/test_api_fuzz.py`) สร้างคำขอ
จาก `openapi.json` เองแล้วตรวจว่าคำตอบตรงกับสัญญา — รอบแรกจับได้สามอย่างที่เทสต์
ซึ่งคนเขียนเองมองข้าม และ**ทั้งสามกระทบหน้าเว็บด้วย ไม่ใช่แค่ API**: ตัวกรองวันที่
ที่ย่อยไม่ได้ทำให้ `ValueError` หลุดเป็น 500, id ที่เกิน 64 บิตทำให้ไดรเวอร์ DB
โยน `OverflowError` เป็น 500 (แก้ที่ `app/services/lookup.py` จึงได้ทั้งสองทาง),
และคำขอที่ตกตั้งแต่ชั้น routing ได้ HTML กลับไปพร้อม 405 ที่ไม่มี header `Allow`

**ด่านที่ต้องอยู่ตลอดไป ไม่ใช่เหตุการณ์ที่ผ่านไปแล้ว:** ตัวตนของ API ต้องมาจาก
token เท่านั้น — API ยกเว้น CSRF ไว้ ถ้าวันหนึ่งด่านยอมรับ session cookie ด้วย
เท่ากับเปิดรู CSRF ที่ปิดไว้ตั้งแต่ Phase 1 กลับมาโดยไม่มีอะไรฟ้อง จึงบังคับ
สามชั้น: ด่านผูกที่ `before_request` ของ blueprint (ลืมแปะไม่ได้เพราะไม่ใช่
decorator), เทสต์ยิงด้วย cookie จริงที่ login สำเร็จแล้ว, และเทสต์ที่ไล่ทุก rule
ใน `url_map` (mutation test 18 แบบ — ตายทั้งหมด)

**ของที่ยกไปเฟสอื่นอย่างตั้งใจ:** rate limit เฉพาะของ API → Phase 5 (ต้องมี
storage ที่ไม่ใช่ `memory://` ก่อน ไม่งั้นเพดานจริงเป็น N เท่าตามจำนวน worker) /
หน้าเว็บสำหรับออก token → Phase 4 (ต้องคิดเรื่อง re-authentication ก่อน) /
pagination กับ ETag → เพิ่มแบบ opt-in ได้โดยไม่ต้องขึ้น v2 (ตัดสินใจไว้ใน ADR 0018)

## Phase 4 — Identity & AuthN/AuthZ ✅ (เสร็จ 2026-08-04 — ยกเว้น SSO ที่ย้ายไป Phase 5)

**เป้าหมาย:** ยกระดับ authn ให้ถึง ASVS L2 และเปิดทาง identity กลางของมหาวิทยาลัย

- **Password policy ✅ (ADR 0019):** ตาม NIST SP 800-63B ตรง ๆ — ความยาวขั้นต่ำ 8
  เพดาน 128 (NIST บังคับให้รับอย่างน้อย 64), เทียบกับรายการรหัสที่หลุดแล้ว
  **46,476 รายการแบบ bundled offline** (จากรายการ 100k ของ NCSC กรองเหลือเฉพาะที่
  ยาวพอจะถูกเทียบจริง), กันรหัสที่มี username ของตัวเองอยู่ข้างใน
  **ไม่มี**กฎ complexity, **ไม่**บังคับเปลี่ยนตามรอบ, **ไม่**ตัดปลาย/ช่องว่าง
  normalize NFKC อยู่ที่ `User.set_password/check_password` ไม่ใช่ที่ผู้เรียก
  (เกิดข้างเดียวเมื่อไหร่ คนที่ตั้งรหัสเป็นภาษาไทยจะ login ไม่ได้แบบหาสาเหตุไม่เจอ)
  *ไม่เลือก HIBP k-anonymity* เพราะนโยบายที่ต้องตอบว่า "เน็ตล่มแล้วจะยังไง" มีแต่
  คำตอบที่แย่ทั้งคู่
- **Session ✅ (ADR 0020):** ล้าง session ทั้งใบตอน login (session fixation),
  idle 30 นาที + absolute 12 ชม. **ตรวจที่ server ทุก request** ไม่ใช่พึ่งวันหมดอายุ
  บนคุกกี้, ผูกคุกกี้กับเครื่อง (`session_protection="strong"`) และ**กับ credential
  ปัจจุบันด้วย HMAC ของ `password_hash`** (วิธีเดียวกับ Django) — เปลี่ยนรหัสแล้ว
  คุกกี้ทุกใบที่ออกก่อนหน้า **รวมใบที่อยู่ในมือคนอื่น** ตายพร้อมกัน
  คุกกี้ **ไม่** permanent โดยตั้งใจ (ไม่งั้น strong protection เงียบไปเฉย ๆ)
- **Lockout ต่อ username ✅ (ADR 0021):** โควตาชั้นที่สองที่นับตามบัญชีที่ถูกยิง
  (10 ครั้ง/5 นาที) หน้าต่างสั้นและหลวมกว่าฝั่ง IP เพราะโควตานี้เป็นของ*เหยื่อ*
  กุญแจเป็น hash ของชื่อ ไม่ใช่ชื่อดิบ (จะไปนอนใน redis วันหนึ่ง)
  ปิดช่องที่ CLAUDE.md บันทึกไว้ตั้งแต่ Phase 0
- **RBAC ✅ (ADR 0022):** `tdl_user.role` (admin/user) ตรวจสิทธิ์ **ใน service**
  ไม่ใช่ที่ route (adapter มีสามทางแล้ว — ด่านที่ต้องแปะเองคือด่านที่ลืมแปะ),
  403 ไม่ใช่ 404 (ต่างจาก ADR 0004 โดยตั้งใจ), ห้ามแก้บทบาทตัวเองบนหน้าเว็บ,
  หน้า `/admin/users` + `flask set-role` (ทางเดียวที่ตั้งผู้ดูแลคนแรกได้)
- **Auth เป็น plugin ชนิดที่สอง ✅ (ADR 0023 + 0024):** `password` เป็น core plugin
  และ `totp` เป็นปัจจัยที่สองที่ **มีตารางของตัวเอง**
  กลไก plugin-owns-its-own-table ที่ค้างจาก ADR 0006 ได้คำตอบแล้ว: ตารางของ plugin
  **อยู่นอกสาย migration ของ core** (`include_object` ใน `env.py`) วงจรชีวิตเป็นของ
  plugin เองผ่าน `flask plugin-install` / `plugin-uninstall` และ **ชั้นข้อมูลของ
  คอลัมน์ plugin ก็ประกาศเอง** (core ไม่มีชื่อ `totp` อยู่ในโค้ดเลยแม้แต่ในคอมเมนต์
  — มีเทสต์ grep บังคับ) ส่วน TOTP เขียนเองตาม RFC 6238 (ยืนยันด้วย test vector
  ทางการทั้ง 6 ค่า) ไม่เพิ่ม dependency
- **หน้าเว็บออก API token ✅** (ของค้างจาก ADR 0017): ออกใบใหม่ต้องกรอกรหัสผ่านซ้ำ
  เพิกถอนไม่ต้อง (การเพิกถอนทำให้ปลอดภัยขึ้นเสมอ — ตั้งด่านขวางมีแต่ทำให้คนลังเล)
  ความลับ render ในคำตอบ **ไม่ผ่าน flash** เพราะคุกกี้ session ถูกเซ็นแต่ไม่ได้เข้ารหัส
- **SSO → ย้ายไป Phase 5** (ดูเหตุผลข้างล่าง)

**ทำไมตรงนี้:** ใช้ของสามเฟสก่อนหน้าครบ — plugin registry (มีแล้ว), audit
(บันทึก auth events ฟรี), API token seam (Phase 3) และ RBAC ต้องเสร็จก่อน SSO
**DoD:** ✅ ติดตั้ง/ถอน MFA plugin แล้วตารางหายตามจริง ✅ เทสต์ lockout (ทั้งต่อ IP
และต่อ username) ⏭️ login ผ่าน OIDC — ยกไป Phase 5 พร้อม IdP ทดสอบ
— เทสต์ 673 ผ่าน coverage 96.74% (ratchet 96 คงเดิม), interrogate 73→78

**mutation test ของเฟสนี้** (ตามกติกาใน CLAUDE.md): รหัสผ่าน 10/10, session +
โควตาต่อชื่อผู้ใช้ 16/16, RBAC 10/11, MFA/TOTP 15/15 — ตัวที่รอดของ RBAC เป็น
equivalent mutant (มีด่านซ้อนสองชั้น) พิสูจน์แยกแล้วว่าถอดพร้อมกันทั้งสองที่แล้วแดง
ส่วนของ MFA รอบแรกรอดหนึ่งตัวเพราะ**ยังไม่มีเทสต์ปักพฤติกรรมไว้จริง ๆ** จึงเติมเทสต์
(ยืนยันซ้ำแล้วถอย `last_counter` กลับ = เปิดช่องใช้รหัสซ้ำ) แล้วมันตาย

**สองบั๊กที่ gate ของเฟสก่อน ๆ จับได้ระหว่างปิดเฟส** (ไม่ใช่คนเห็นเอง):
1. `include_object` ใน `env.py` กรองแค่ `type_ == "table"` — **index ของ plugin
   ยังหลุดเข้า migration ของ core** (`tests/test_migrations.py` จับ)
2. `app/audit.py` มีชื่อคอลัมน์ของ plugin (`totp_secret`) อยู่ในโค้ด core ซึ่งผิด
   สัญญาข้อ "core ห้ามรู้จัก plugin ตัวใดตัวหนึ่ง" (`tests/test_plugins.py` จับ)
   → แก้เป็นให้ plugin ประกาศชั้นข้อมูลของคอลัมน์ตัวเองใน `models.py` (ADR 0023)

### ทำไม SSO ถึงย้ายไป Phase 5 (ตัดสิน 2026-08-04)

DoD ของ SSO คือ **"login ผ่าน OIDC ได้จริงกับ IdP ทดสอบ"** ซึ่งต้องมี IdP ให้ยิงจริง
(Keycloak หรือเทียบเท่า) — ของแบบนั้นมาพร้อม container stack ของ Phase 5 พอดี
การทำตอนนี้จะได้ OIDC client ที่ผ่านแค่ IdP จำลองในเทสต์ ซึ่ง **ไม่ใช่สิ่งที่ DoD
ข้อนี้ขอ** และการปล่อยเส้นทาง login ที่ยังไม่เคยยิงกับของจริงคือความเสี่ยงที่ไม่คุ้ม

ที่สำคัญกว่า: **seam พร้อมแล้ว** — registry รองรับ plugin ชนิด `auth` ที่ประกาศ
`"factor": "primary"` ได้ทันที และ RBAC (ADR 0022) ที่ SSO ต้องใช้ map group → role
ก็เสร็จแล้ว งานที่เหลือจึงเป็น "เพิ่ม plugin หนึ่งตัว" ไม่ใช่ "รื้อ core"
(หนี้ที่รู้ตัว: `password` ยังเป็น manifest เปล่า core ยังเรียก `check_password()`
ตรง ๆ — จะยกขึ้นเป็นปัจจัยหลักแบบ plugin จริงตอนมีปัจจัยหลักตัวที่สอง ดู ADR 0024)

## Phase 4.5 — Supply-chain isolation ของจุด plug ✅ (เสร็จ 2026-08-05 — ADR 0025)

**แทรกเข้ามาหลัง Phase 4** เพราะ Phase 5 กำลังจะเพิ่ม redis, driver ของ MySQL/MariaDB
และ authlib (OIDC) — ทำฐานนี้ก่อนแปลว่าของพวกนั้นลงมาบนกติกาที่มีอยู่แล้ว
ไม่ใช่ต้องย้อนมารื้อทีหลัง

**ปัญหาตั้งต้น:** plugin มีไว้ลดความเสี่ยง แต่ตอนเพิ่ม QR ของ MFA ระบบต้องแบก
`segno` ไว้ใน `[packages]` ของ core ตลอดไป — *ถอดโค้ดได้ แต่ถอด supply chain ไม่ได้*
วันที่ CVE ออกโดยยังไม่มี patch คำตอบควรเป็น "ถอดออกก่อน ระบบยังเดินได้"

- **ส่วนเสริมของ plugin ✅** — กติกาเดิมใช้ซ้ำอีกชั้น
  (`<ชนิด>/<ไอดี>/enhancements/<ไอดี>` + `plugin.json` + `provide.py`)
  host ขอด้วย**ชื่อความสามารถ** ไม่ใช่ไอดี · ส่วนเสริมห้ามมี `models.py`
  (ไม่งั้นการสลับ implementation จะกลายเป็นการย้ายข้อมูล) ·
  มีผู้ให้บริการหลายตัวแต่ไม่มี `PLUGIN_PICKS` = **ปิดทั้งหมด (fail closed)**
  และถ้ามี pick อยู่ pick ชนะเสมอ แม้เหลือผู้ให้บริการตัวเดียว
- **ไลบรารีแยกตาม category ของ pipenv ✅** — `auth/totp#qr-segno` →
  `[plugin-auth-totp-qr-segno]` คำนวณจากคีย์ ไม่ได้ประกาศซ้ำ ·
  `pipenv sync --dev` **ไม่ติดตั้งให้** โดยตั้งใจ (ใช้ `flask plugin-deps --categories`)
- **สวิตช์ปิดตอน runtime ✅** — `DISABLED_PLUGINS` ปิดได้ทุกชั้นด้วยคีย์เดียวกับที่
  `flask plugin-list` แสดง ไม่ต้องแก้โค้ด ไม่ต้องรอ deploy · กรองที่ `discover()`/
  `enhancements()` **ที่เดียว** เพื่อให้ "ปิดอยู่" เหมือน "ไม่เคยวางไดเรกทอรี" จริง ·
  **ปิดโค้ดไม่ได้ปิดข้อมูล** (`installed_on_disk()` ไม่สนสวิตช์ ไม่งั้น migrate
  ตัวถัดไปของ core จะ drop ตารางของ plugin ที่ถูกปิดทิ้งเงียบ ๆ)
- **เทสต์สแกน AST ✅** — โค้ดของจุด plug import ได้แค่ stdlib + ของที่ core แบกอยู่แล้ว
  + ที่ manifest **ของตัวเอง** ประกาศ (plugin แม่ประกาศแทนส่วนเสริมไม่ได้)
  บังคับสองทิศ: import ที่ไม่ประกาศ **และ** requirement ที่ไม่มีใคร import
- **job `bare` ใน CI ✅** — รันชุดเทสต์โดย**ไม่ติดตั้ง category ของ plugin เลย**
  ต้องเขียว นี่คือด่านเดียวที่ทำให้ "ถอดแล้วไม่พัง" เป็นข้อเท็จจริงที่วัดได้ทุก push
  แทนที่จะเป็นความตั้งใจในเอกสาร (เทสต์ที่ต้องใช้ไลบรารีจริงมาร์ก `plugin_deps`
  — **ไม่ใช้ `importorskip`** ซึ่งจะทำให้ job `test` ข้ามเงียบ ๆ ตอนไลบรารีหาย)
- **pip-audit/SBOM แยกตาม category ✅** — CVE ของของที่ถอดได้ **ไม่ทำให้ job ของ
  core แดง** แต่ยิง `::warning::` + สรุปของ run · artifact แยก `sbom-core.json`
  กับ `sbom-<category>.json` จึงตอบได้ว่าถอด plugin ตัวนี้แล้ว component ไหนหายไป

**ผลที่วัดได้:** CI 11 job · โหมด bare 730 passed / 5 deselected ·
`segno` ไม่อยู่ใน SBOM ของ core อีกแล้ว (118 components) แต่ยังถูก audit ในสายของมันเอง

**ที่ไม่ได้ทำ (โดยตั้งใจ):** venv/โปรเซสแยกต่อ plugin — เป็น isolation จริงทางเดียว
ในภาษา python แต่ต้องมี IPC และสอง interpreter ในเครื่องเดียว เกินขนาดของแอปนี้
(ต้องกลับมาทบทวนถ้าวันหนึ่งรับ plugin จากคนนอกจริง ๆ) · ยังไม่มี recovery code
ของ MFA — ค้างจาก Phase 4 ทำโทรศัพท์หายต้องให้ผู้ดูแลปิดให้

## Phase 5 — Deployment parity & flexibility

**เป้าหมาย:** dev/staging/prod เหมือนกันจริง, รองรับ DB หลายยี่ห้อตามกลยุทธ์ข้อ 4
และไม่มี lock-in ที่ไม่มีทางออก

- Dockerfile (multi-stage, non-root) + compose: app (gunicorn) + service ของ
  backend ที่เลือก
- **DB backend plugin ชนิดใหม่บน registry เดิม** (ADR contract: ห้าม purge ตัว
  active, ต้องมี export path) — built-in: SQLite, MySQL 8+, MariaDB 11+
  ยี่ห้ออื่น (PostgreSQL, Oracle, MSSQL + cloud preset) เป็น plugin ภายหลัง
- **CI matrix: SQLite + MySQL + MariaDB** ✅ (P5-04 — job `dialects`) จับ dialect quirk ให้หมด
  **ยืนยันแล้วด้วยการรันจริง**: MySQL 8.0.46 และ MariaDB 11.8.6 ผ่านทั้งชุด
  754 passed / 2 skipped (สอง `PRAGMA` ที่เป็นของ SQLite เท่านั้น)
  (DATETIME(6) variant, เทสต์ precision, batch mode)
- **Baseline squash migration** สำหรับ fresh install (ล้าง landmine ข้อ 4.4)
- Cache plugin interface (ข้อ 4.3): core no-op default + Redis backend plugin
  แล้วชี้ rate-limiter storage ไปที่เดียวกัน (ปิดหนี้ `memory://` ต่อ process)
- TLS 1.2+/1.3 ที่ reverse proxy + เปิด HSTS ที่ค้างจาก Phase 1
- **ติดตั้งตารางเวลา `purge-expired` บน host จริง** — สคริปต์ (`scripts/purge_cron.sh`)
  และขั้นตอน (cron/systemd timer) พร้อมแล้วใน [OPERATIONS.md](OPERATIONS.md)
  เหลือแค่เอาไปติดตั้งตอนมี host **ระยะเก็บรักษาที่อนุมัติไว้จะเป็นจริงก็ต่อเมื่อ
  ขั้นตอนนี้เสร็จ** — ก่อนหน้านั้นต้องรันด้วยมือ ไม่งั้นเอกสารอ้างสิ่งที่ไม่เกิดขึ้น
- Secrets: env → รองรับ Vault/KMS เป็น option / IaC ตาม infra เป้าหมายจริง
- ADR "exit path" ต่อ managed service ทุกตัวก่อนผูกมัด
- **SSO ที่ย้ายมาจาก Phase 4:** OIDC เป็น plugin ชนิด `auth` (`"factor": "primary"`)
  LDAP เป็นอีกตัว — ไม่แยก user store ใหม่ map เข้า `User` เดิม และ map group → role
  ที่มีอยู่แล้ว (ADR 0022) **ทำที่นี่เพราะ DoD ต้อง login กับ IdP ทดสอบจริง**
  ซึ่งต้องมี compose stack ของเฟสนี้ (Keycloak หรือเทียบเท่า) — รายละเอียดใน
  หัวข้อ Phase 4 ("ทำไม SSO ถึงย้ายไป Phase 5")
- **rate limit ของ `/api/v1`** (ยกมาจาก Phase 3 ด้วยเหตุผลเดียวกัน: ต้องมี
  storage ที่ไม่ใช่ `memory://` ก่อน ไม่งั้นเพดานจริงเป็น N เท่าตามจำนวน worker)

**ทำไมตรงนี้:** additive ทั้งหมด ไม่รื้อโค้ดแอป — แต่ต้องเสร็จก่อน Phase 6
เพราะ load test บน SQLite/dev server คือตัวเลขหลอก
**DoD:** `docker compose up` เลือก backend ได้, เทสต์เขียวทั้งสาม DB ใน CI,
app รัน ≥2 replica พฤติกรรมถูกต้อง (rate limit นับรวม, session ข้าม replica)

### ✅ ปิดเฟสแล้ว (2026-08-11) — 17/17 ข้อ · CI 18 job

ทวน DoD ทีละข้อกับของจริง ไม่ใช่กับความจำ:

| DoD | พิสูจน์ด้วย |
|---|---|
| `docker compose up` เลือก backend ได้ | `compose.{mysql,mariadb}.yaml` · job `stack` ยิง stack จริงทุก push |
| เทสต์เขียวทั้งสาม DB | job `dialects` (matrix `mysql:8` + `mariadb:11`) + job `test` (SQLite) |
| ≥2 replica · rate limit นับรวม | job `stack`: ยิงรหัสผิดได้ 5 ครั้งแล้ว 429 ไม่ใช่ 10 |
| ≥2 replica · session ข้าม replica | `tests/test_proxy.py` + คุกกี้ใบเดียวได้ 200 จากทั้งสอง replica |
| SSO (OIDC) | job `sso` — login กับ Keycloak จริง + กลุ่ม → บทบาท |
| LDAP | job `ldap` — bind กับ OpenLDAP จริง + รหัสผ่านว่างได้ 401 |
| TLS 1.2+/1.3 + HSTS | job `stack` — 1.0/1.1 ถูกปฏิเสธโดย *server* (ไม่ใช่โดย client) |
| Secrets + exit path | ADR 0030 · job `vault` — และ **Vault ที่ถามไม่ได้ทำให้ไม่ start** |
| ตารางเวลา purge บน host จริง | ติดตั้งบน host ที่มี systemd จริง · job `purge-timer` |
| rate limit ของ `/api/v1` | P5-08 — นับต่อใบ token ไม่ใช่ต่อ IP |

**สิ่งที่เฟสนี้สอนซ้ำจนเป็นรูปแบบ**: ด่านที่ "มีอยู่" กับด่านที่ "ครอบชั้นที่พังจริง"
เป็นคนละเรื่อง และความต่างมักอยู่ที่ **สัญญาณที่วัด** ไม่ใช่ตรรกะ —
`openssl s_client` ตอบเหมือนกันไม่ว่า server ปฏิเสธหรือไม่มีใครฟังพอร์ตนั้น ·
`flask --help` คืน 0 แม้โหลดแอปไม่สำเร็จ · `bind()` ปลอมที่ใจดีกว่าของจริง
ทำให้ด่านสำคัญที่สุดผ่านโดยไม่ได้ตรวจอะไร · ทุกครั้งที่เขียนด่านใหม่
**ต้องทดสอบสองทิศ** (พังเมื่อควรพัง และผ่านเมื่อควรผ่าน)

**ของที่ยังไม่ทำและยกไปเฟสถัดไปอย่างรู้ตัว**: single logout / refresh token
ของ OIDC · ~~การผูกหลาย IdP กับผู้ใช้คนเดียว~~ (ปิดแล้วโดย `ADR 0047` —
ผลพลอยได้ของ auth profile ในเฟส 17) · nested group ของ LDAP ·
การหมุนความลับโดยไม่ restart · KMS ของผู้ให้บริการคลาวด์ (รูปสัญญาเดียวกับ
`secrets` ที่มีแล้ว แต่ยังไม่มีใครต้องใช้) · IaC ตาม infra เป้าหมายจริง

## Phase 6 — Performance validation

**เป้าหมาย:** ตัวเลขจริง ไม่ใช่คำว่า "เร็วพอ"

- Metrics middleware (Prometheus format): latency histogram ต่อ endpoint → p95/p99
- ตั้งเป้าเป็นตัวเลข (ค่าตั้งต้นเสนอ: p95 < 200ms, p99 < 500ms ที่ N concurrent —
  N มาจากการประเมินผู้ใช้จริง ไม่ใช่เดา แล้วบันทึกเป็น ADR)
- Load test (k6/locust) บน compose stack จาก Phase 5, ทดสอบที่ 1 และ ≥2 replica
- ทบทวน index/query จากผล (มี index `user_id` แล้ว — ตรวจ query ตัวกรองวันที่เพิ่ม)

**DoD:** รายงาน load test ใน repo, เป้า p95/p99 ผ่านที่ concurrency เป้าหมาย

### ✅ ปิดเฟสแล้ว (2026-08-11) — 6/6 ข้อ · CI 19 job

ทวน DoD ทีละข้อกับของจริง:

| DoD / รายการ | พิสูจน์ด้วย |
|---|---|
| metrics middleware → p95/p99 ต่อ endpoint | `app/metrics.py` + `tests/test_metrics.py` · `/metrics` **ต้องมี token เสมอ** ไม่มีโหมดสาธารณะ (ADR 0031 ข้อ 5) |
| เป้าเป็นตัวเลขที่มีที่มา | [ADR 0031](adr/0031-performance-targets-and-what-they-mean.md) — p95 < 200ms, p99 < 500ms ที่ **N = 5** ซึ่งมาจากขนาดการใช้งานจริง (ส่วนตัว/ครอบครัว) ไม่ใช่เลขกลม |
| รายงาน load test ใน repo | [PERFORMANCE.md](PERFORMANCE.md) + ชุดที่รันซ้ำได้จริง (`loadtest/journey.js`, `scripts/loadtest_curve.sh`) |
| ทดสอบที่ 1 และ ≥2 replica | เส้นโค้ง 1/5/10/25/50/100 VUs ทั้งสองสภาพ ใน PERFORMANCE.md |
| **เป้าผ่านที่ concurrency เป้าหมาย** | รันที่ 5 VUs โดยเปิด threshold **4 รอบติด k6 คืน exit 0 ทุกรอบ** (p95 22–38ms · p99 57–233ms · ล้มเหลว 0%) |
| ทบทวน index/query จากผล | ทบทวนแล้วและ **คำตอบคือไม่แตะ** — throughput ตันที่ ~57–70 req/s แล้ว *ตกลง* ซึ่งเป็นรูปของคิวที่ล้น ไม่ใช่ของ query ที่ช้า การเพิ่ม index คือการแก้สิ่งที่การวัดไม่ได้บอกว่าเสีย |

**สิ่งที่เฟสนี้หาเจอและไม่มีเฟสไหนก่อนหน้าหาเจอได้**: สาย audit ต่อกันขนานข้าม
process ไม่ได้ — ที่ 2 replica คำขอเขียนล้มด้วย 500 ราว 0.36% ที่โหลดเป้าและ 9.5%
ที่โหลดสูง · **`app/audit.py` เขียนข้อจำกัดนี้ไว้เองตั้งแต่ Phase 2** พร้อมเงื่อนไข
ว่า "ถ้าวันหนึ่งต้องเขียนขนานจริง" — Phase 5 ทำให้วันนั้นมาถึงโดยไม่มีใครสังเกต
เพราะ **ด่านของ Phase 5 ที่พิสูจน์ว่า 2 replica ใช้ได้ ทดสอบแค่การอ่านกับ login
ไม่เคยมีใครเขียนพร้อมกัน** แก้แล้วด้วย [ADR 0032](adr/0032-serialising-audit-appends.md)
(ล็อกแถวท้ายสาย) · ยืนยันด้วยเทสต์ที่เขียนขนานจริงบน MySQL/MariaDB ใน job `dialects`

**บทเรียนของเฟสนี้ต่อจาก Phase 5 โดยตรง**: เฟส 5 สอนว่าด่านที่ "มีอยู่" ไม่เท่ากับ
ด่านที่ "ครอบชั้นที่พังจริง" · เฟส 6 เติมอีกข้อว่า **ตัวเลขจากการวัดรอบเดียวไม่ใช่
หลักฐาน** — p99 ของสี่รอบที่เหมือนกันทุกอย่างต่างกันได้ถึงสี่เท่า สิ่งที่ยืนยันได้
คือ "ไม่มีรอบไหนตกเกณฑ์" ไม่ใช่ค่าใดค่าหนึ่ง (หลักเดียวกับ mutation test:
พิสูจน์ด้วยการที่มันแดงเมื่อควรแดง ไม่ใช่ด้วยการที่มันเขียวหนึ่งครั้ง)

**ของที่ยังไม่ทำและรู้ตัว**: retry เมื่อ MySQL deadlock (error 1213 — เจอ 2 ครั้ง
ต่อรอบที่ 25 VUs หลังแก้ ล้วนเป็นสิ่งที่ลองใหม่ได้ตามนิยาม) ·
~~ปรับ `--workers` แล้ววัดใหม่~~ (วัดแล้วในเฟส 16 — ดู PERFORMANCE.md หัวข้อ
"การปรับ `--workers`": คำตัดสินคือคง 1 worker ด้วยเหตุผลเรื่อง /metrics) ·
~~ยังไม่มี Prometheus/Grafana ที่ scrape จริง~~ (ปิดแล้วในเฟส 16 —
`compose.metrics.yaml` + job `scrape` พิสูจน์ทุก push)

## Phase 7 — Verification & compliance closure

**เป้าหมาย:** พิสูจน์ทั้งหมดข้างบนด้วยเกณฑ์ภายนอก แล้วปิดวงจรเป็น cadence

- **ASVS 5.0 L2 self-assessment:** ตาราง requirement → evidence (เทสต์/เอกสาร/config)
  ช่องที่ไม่ผ่าน → backlog พร้อมเหตุผล (L2 เหมาะกับ admin app ของสถาบัน; L3 ไว้ถ้า
  ระบบแตะข้อมูลอ่อนไหวกว่านี้)
- DAST: ZAP baseline ใน CI ทุก PR + pentest มือเป็นรอบ (ทุก major release + ปีละครั้ง)
  เขียน cadence เป็นนโยบาย ไม่ใช่ทำครั้งเดียวตอน launch
- **PDPA subject rights บนฐาน Phase 2:** export ข้อมูลตัวเอง (JSON), ลบบัญชี
  ตามนโยบายข้อขัดแย้งที่อนุมัติแล้ว, breach-notification runbook, ROPA อย่างย่อ
- WCAG 2.2 AA audit เต็มรอบสอง (มือ ไม่ใช่แค่ automated)
- SIEM: ต่อท่อ structured log (Phase 1) เข้า ELK/Graylog + alert rule พื้นฐาน

**DoD:** ASVS checklist มี evidence ครบทุกข้อที่ claim, ZAP เขียวใน CI,
ผู้ใช้ export/ลบข้อมูลตัวเองได้จริงตามนโยบาย

### ✅ ปิดเฟสแล้ว (2026-08-12) — 12/12 ข้อ · CI 21 job

ทวน DoD ทีละข้อกับของจริง:

| DoD / รายการ | พิสูจน์ด้วย |
|---|---|
| **ASVS checklist มี evidence ครบทุกข้อที่ claim** | [ASVS.md](ASVS.md) ประเมินครบ **253/253** ข้อ · `tests/test_asvs.py` บังคับว่าทุกข้อที่ตอบว่า "ผ่าน" ต้องมีหลักฐานที่**ชี้ไปได้จริง** (ไฟล์ · ชื่อเทสต์ · job ใน CI · ADR) เปลี่ยนชื่อเทสต์ที่ถูกอ้างแล้วเอกสารแดงทันที · `UNASSESSED_CEILING = 0` ทำให้ "ยังไม่ประเมิน" เป็นข้อห้ามถาวร |
| **ZAP เขียวใน CI** | job `dast` ยิง ZAP baseline ใส่ stack ที่รันจริง (TLS + 2 replica) **แบบที่ login แล้ว** ทุก push · กติกาต่อรายการอยู่ใน `.zap/rules.tsv` และ 18 ข้อที่ตั้งเป็น FAIL ผ่านอยู่แล้วทั้งหมด (ตาข่ายกันถอยหลัง ไม่ใช่ตัวหาของใหม่) |
| **ผู้ใช้ export/ลบข้อมูลตัวเองได้จริง** | `POST /settings/export` และ `POST /settings/close` — ทั้งคู่ต้องกรอกรหัสผ่านซ้ำ ([ADR 0034](adr/0034-data-subject-rights.md)) · `tests/test_personal_data.py` · `tests/test_close_account.py` |
| pentest มือเป็นรอบ (เขียน cadence เป็นนโยบาย) | [SECURITY-CADENCE.md](SECURITY-CADENCE.md) — **มีเทสต์อ่านตารางจริง** เลยกำหนดเกิน 7 วันแล้ว CI แดง (`tests/test_cadence.py`) |
| PDPA: breach runbook + ROPA | [RUNBOOK-BREACH.md](RUNBOOK-BREACH.md) · [ROPA.md](ROPA.md) — `tests/test_ropa.py` บังคับว่าทุกตารางถูกบันทึก ระยะเก็บตรงกับค่าคงที่ในโค้ด และคำสั่งที่ runbook อ้างมีอยู่จริง |
| WCAG 2.2 AA ตรวจด้วยมือ | [ACCESSIBILITY-AUDIT.md](ACCESSIBILITY-AUDIT.md) — เจอสามข้อที่เครื่องตรวจไม่ได้ แก้ครบพร้อมเทสต์ |
| SIEM: ต่อท่อ log + alert rule | job `siem` — log ถึง Loki จริง กฎประเมินผ่าน และ **ต้องเห็น alert ดังจริง** หลังยิงรหัสผิด ([ADR 0037](adr/0037-where-logs-go-and-what-shouts.md)) |

**ผลการประเมิน ASVS: ผ่าน 141 · ไม่เกี่ยวข้อง 64 · ยังไม่ผ่าน 48 (V11.3 ขยับเป็นผ่านหลัง ADR 0046)**
— ช่องที่เขียนว่ายังไม่ผ่านมีค่ามากกว่าช่องที่เขียนว่าผ่าน และครึ่งหนึ่งของมัน
คือ *เอกสารที่ยังไม่ได้เขียน* ไม่ใช่โค้ดที่ยังไม่มี

### สิ่งที่เฟสนี้หาเจอ และไม่มีเฟสไหนก่อนหน้าหาเจอได้

**job `dast` หาบั๊กที่เทสต์ในเครื่องไม่มีทางเจอสามตัว** — ลบหมวดแล้วสร้างชื่อเดิม
ได้ 500 · สาย audit ต่อขนานไม่ได้จริง · race ของการตั้งชื่อหมวด · สาเหตุร่วมคือ
**ZAP เดินเส้นทางที่คนเขียนเทสต์ไม่คิดจะเดิน และเดินมันพร้อมกันหลายเส้น**

**และการแก้สาย audit ใช้สามรอบกว่าจะถูก** ([ADR 0035](adr/0035-audit-appends-queue-on-one-row.md) ·
[ADR 0036](adr/0036-read-committed-isolation.md)) — วิธีของ ADR 0032 ที่ Phase 6
บันทึกว่า "แก้แล้ว" **ไม่เคยทำให้การเขียนเป็นลำดับเลย** มันแค่เปลี่ยนชนิดของ
ความล้มเหลวจากการชนกุญแจเป็น deadlock

### บทเรียนของเฟสนี้ — ต่อจาก Phase 5 และ 6 อีกขั้น

Phase 5 สอนว่าด่านที่ "มีอยู่" ไม่เท่ากับด่านที่ครอบชั้นที่พังจริง และความต่าง
อยู่ที่ **สัญญาณที่วัด** · Phase 6 เติมว่า **การวัดรอบเดียวไม่ใช่หลักฐาน**

Phase 7 เติมข้อที่สาม และแพงที่สุด: **เครื่องมือวัดที่เราสร้างขึ้นเองเพื่อพิสูจน์
ว่าแก้ถูก ก็โกหกได้** — repro ที่ใช้ยืนยันว่า deadlock หายไปเรียก `audit.record()`
เป็น statement แรกของ transaction ซึ่งไม่มีคำขอจริงใบไหนทำ ทุกใบอ่านก่อนเขียน
มันจึงรายงาน 160/160 ผ่าน ทั้งที่ของจริงผ่าน 21/160 · **เพิ่มการอ่านหนึ่งบรรทัด
ให้เหมือนคำขอจริง ตัวเลขเปลี่ยนจาก "แก้แล้ว" เป็น "ยังพังอยู่ 87%"**

มันอันตรายกว่าด่านที่วัดผิดตัวแบบเดิม เพราะมันตอบว่า "ผ่าน" ในจังหวะที่เรากำลัง
อยากได้ยิน — และถ้าไม่มี `dast` ยิง stack จริงอยู่ บั๊กนั้นจะถูกปิดไปพร้อม ADR
ที่บอกว่าแก้แล้ว

รูปเดียวกันโผล่อีกครั้งที่ระบบเฝ้าระวัง: กฎแจ้งเตือนที่นับแต่ 401 **เงียบสนิท
พอดีตอนที่การโจมตีหนักที่สุด** เพราะโควตาของแอปเองเปลี่ยนคำขอที่เหลือเป็น 429

### ratchet ตอนปิดเฟส

coverage **96.31%** (เพดาน 96) · interrogate **84.9%** (เพดาน 84) — **ไม่ขยับทั้งคู่**
เพราะที่ว่างต่ำกว่านโยบาย ~1 จุด · ตัวเลข coverage ตอนเริ่มทวนอยู่ที่ 96.18%
ซึ่ง**ลดลง**จาก Phase 6 — ไล่ดูแล้วพบว่ากิ่งที่ขาดคือพฤติกรรมที่เฟสนี้อ้างเองว่า
สำคัญ (แถวล็อกของสาย audit หายไปต้องดัง · plugin ตัวเดียวพังต้องไม่ล้มทั้งคำขอ)
**อ้างแล้วไม่เทสต์คือช่องว่างแบบเดียวกับที่เฟสนี้ไล่ปิดมาตลอด** จึงเขียนเทสต์ให้ก่อนปิด

### ของที่ยังไม่ทำและยกไปอย่างรู้ตัว

- **pentest ด้วยมือโดยคนนอกทีม** — เงื่อนไขที่ทำให้ต้องทำอยู่ใน SECURITY-CADENCE.md
  ("เมื่อจะเปิดให้คนนอกเข้าถึงระบบเป็นครั้งแรก")
- **ยังไม่ได้ฟังด้วย screen reader จริง และยังไม่ได้เดินด้วยแป้นพิมพ์บนเบราว์เซอร์จริง**
  — ช่องว่างที่ใหญ่ที่สุดของการตรวจ WCAG รอบนี้
- **log ยังอยู่บนเครื่องเดียวกับแอป** (ASVS V16.4.2) · ยังไม่มี Alertmanager
  และปลายทางที่คนอ่าน
- **48 ข้อของ ASVS ที่ยังไม่ผ่าน** จัดกลุ่มไว้ใน backlog ท้าย ASVS.md แล้ว
  ครึ่งหนึ่งเป็นเอกสารที่ยังไม่ได้เขียน (นโยบายกุญแจ · กฎการตรวจค่า · เพดานเชิงธุรกิจ)
- ~~ยังไม่วัด throughput ใหม่หลังเปลี่ยนวิธีล็อก~~ — วัดแล้วในเฟส 16 (16-05)
  บนโค้ดปัจจุบัน: DoD ที่โหลดเป้า 4/4 รอบ ล้มเหลว 0% (PERFORMANCE.md)

---

## ลำดับพึ่งพา (สรุปว่าทำไมสลับไม่ได้)

```
0 → 1 → 2 → 3 → 4 → 7
         │    └─ API v1 ต้อง freeze หลัง semantics นิ่ง (2)
         └────── audit hooks ทำให้ทุกฟีเจอร์หลังจากนี้ถูกบันทึกฟรี
0 → 5 → 6 ─────────────→ 7
    │   └─ load test ต้องมี parity ก่อน
    └─ SSO ย้ายมาที่นี่: ต้องมี RBAC + seam จาก 4 (มีแล้ว) **และ IdP ทดสอบจาก 5**
```

- Phase 5 ขนานกับ 3–4 ได้ (ไม่แตะโค้ดแอป) ถ้ามีกำลังทำคู่
- การย้อนแก้ที่ "ยอมจ่ายโดยตั้งใจ": Phase 2 แตะทุก route หนึ่งครั้ง (เปลี่ยน delete),
  Phase 3 แตะทุก route อีกหนึ่งครั้ง (extract service) — สองรอบนี้คือราคาที่ถูกที่สุดแล้ว
  เพราะจ่ายตอน route ยังน้อย และ audit hooks จาก Phase 2 เป็น event-based
  จึงไม่ต้องรื้อซ้ำตอน extract

---

## Public readiness / Badge program (ประตูปลายทาง — ไม่ใช่เฟส)

**เงื่อนไขฝั่งเฟสครบแล้ว (2026-08-12)** — Phase 0–7 ปิดครบและผ่าน DoD ทุกข้อ
· **แต่ประตูยังไม่เปิด** เพราะเช็คลิสต์ข้างล่างยังไม่ครบ ซึ่งเป็นคนละเรื่องกัน:
เฟสตอบว่า *ระบบพร้อมไหม* ส่วนเช็คลิสต์ตอบว่า *เปิดให้คนอื่นเข้ามาได้หรือยัง*

**license คือข้อที่ทุกข้อที่เหลือตั้งอยู่บนมัน** — ไม่มี license แปลว่าคนอื่น
ไม่มีสิทธิ์ใช้ตามกฎหมาย · เลือกแล้วเป็น **MIT** ([ADR 0038](adr/0038-mit-license.md))

### เช็คลิสต์ก่อนกด public (ทบทวนจริง 2026-08-12 หลังปิด Phase 7)

| รายการ | สถานะ | หมายเหตุ |
|---|---|---|
| `LICENSE` | ✅ | MIT · [ADR 0038](adr/0038-mit-license.md) · `tests/test_licensing.py` |
| `SECURITY.md` (ช่องทางแจ้งช่องโหว่) | ✅ | private vulnerability reporting ของ GitHub · **ไม่มีอีเมลในไฟล์โดยตั้งใจ** · กรอบเวลาผูกกับ [SECURITY-CADENCE.md](SECURITY-CADENCE.md) ด้วยเทสต์ |
| `CONTRIBUTING.md` + Code of Conduct | ✅ | Contributor Covenant 2.1 · ช่องทางรายงานแบบส่วนตัวระบุไว้ชัด รวมทางออกเมื่อเรื่องเป็นของคนดูแลเอง |
| `CHANGELOG.md` | ✅ | Keep a Changelog · เลขรุ่นผูกกับ `app.__version__` ด้วยเทสต์ |
| README ฉบับอังกฤษ | ✅ | สองภาษา · ตัวเลขที่โฆษณาทุกตัวถูกอ่านจากแหล่งจริง (ci.yml, ดิสก์, `fail_under`) |
| ตรวจ PII ใน history | ✅ | เขียนใหม่ทั้ง 134 commit เป็น `976721+sayam@users.noreply.github.com` · **ยืนยันจากฝั่ง GitHub แล้ว** ว่าไม่เหลืออีเมลเดิม · ดูข้อจำกัดข้างล่าง |
| Secret scan ประวัติเต็มรอบสุดท้าย | ✅ 2026-08-12 | `scripts/secret_scan_history.sh` · เจอรายการเดียวคือค่าตัวอย่างของ RFC 6238 ซึ่งบันทึกเป็นข้อยกเว้นพร้อมเหตุผล |
| Branch protection | ✅ 2026-08-13 (แก้ 2026-08-16) | บังคับ PR + **required checks ครบชุด (ปัจจุบัน 27 จาก 28)** + linear history · ห้าม force push และห้ามลบ branch · **`enforce_admins: true` ตั้งแต่ ADR 0053** — กฎมีผลกับเจ้าของด้วย (คำตัดสินเดิมที่ว่า "การบังคับ PR กับตัวเองคือความช้าที่ไม่ซื้ออะไร" ถูกกลับโดย ADR 0053 หลังการ bypass ถูกใช้จริง — ด่าน 27 ตัวต้องอยู่บนเส้นทางบังคับ) · ต้อง approve 0 คน เพราะคนเดียว approve PR ตัวเองไม่ได้ — ตั้ง 1 เมื่อมี contributor คนที่สอง (เงื่อนไขหมดอายุใน ADR) |
| **กด public** | ✅ 2026-08-12 | repo เป็นสาธารณะแล้ว · GitHub ตรวจพบ license เป็น MIT · ยืนยันแบบไม่ล็อกอินแล้วว่าหน้าแรก/release/LICENSE เข้าถึงได้ |
| private vulnerability reporting | ✅ 2026-08-12 | เปิดแล้ว — **ถ้าไม่เปิด ลิงก์ใน `SECURITY.md` และ `CODE_OF_CONDUCT.md` จะพาไปไหนไม่ได้** ทั้งสองไฟล์ชี้มาที่ช่องทางนี้ช่องทางเดียว |

### ของฟรีที่ปลดล็อกพร้อมการเป็น public

| ของ | สถานะ | หมายเหตุ |
|---|---|---|
| **CodeQL** | ✅ 2026-08-12 | SAST ที่ [ADR 0009](adr/0009-quality-gate-toolchain.md) ตัดออกตอน private เพราะต้องจ่าย · เป็น **job ใน `ci.yml` ไม่ใช่ default setup ที่กดใน UI** ด้วยเหตุผลเดียวกับ [ADR 0037](adr/0037-where-logs-go-and-what-shouts.md): ของที่คลิกไว้ใน UI ไม่มีใคร review ได้และหายเงียบ ๆ ได้ · สแกน python **และ javascript** เพราะ `app/static/app.js` ถือพฤติกรรมฝั่ง client ทั้งหมด |
| secret scanning + **push protection** | ✅ 2026-08-12 | push ที่มีความลับถูก**ปฏิเสธก่อนเข้า repo** — ครอบชั้นที่ job `secret-scan` ครอบไม่ถึง เพราะตัวนั้นตรวจหลังของเข้าไปแล้ว |
| Dependabot security updates | ✅ 2026-08-12 | เปิด PR อัตโนมัติเมื่อมี CVE · **มองไม่เห็น category ของ plugin และ `[deploy]`** เพราะ dependency graph อ่านแค่ `[packages]`/`[dev-packages]` — วัดแล้วเห็น 126 package · ช่องนั้นปิดด้วย job `plugin-audit` และ `security` (ดู [SECURITY-CADENCE.md](SECURITY-CADENCE.md)) · **version updates เปิดเฉพาะของที่ถูกตรึงไว้** (actions, base image, `pins/`) เส้นแบ่งคือ "ตรึงอะไรไว้ต้องมีคนขยับให้" ไม่ใช่ชื่อ ecosystem |
| OpenSSF Scorecard | ✅ 2026-08-13 | `.github/workflows/scorecard.yml` · ผลไปโผล่ที่หน้า Security ร่วมกับ CodeQL และเผยแพร่ไป OpenSSF API เพื่อให้มี badge · **ไม่อยู่ในรายการ required check** เพราะไม่รันบน PR และเป็นคะแนนไม่ใช่ผ่าน/ไม่ผ่าน · **ข้อ `Pinned-Dependencies` ต้องปิดสามชั้น ไม่ใช่ชั้นเดียว**: action → SHA (`tests/test_workflow_pinning.py`) · base image → digest (`tests/test_dockerfile_pinning.py`) · เครื่องมือที่ job ติดตั้งเอง → hash ใน `pins/` (`tests/test_ci_pinning.py`) — ชั้นที่สามคือของที่ค้างอยู่ 13 alert หลังทำสองชั้นแรกเสร็จ (2026-08-13) |

**สิ่งที่การเขียนประวัติใหม่ทำไม่ได้ — บันทึกไว้แทนที่จะเข้าใจว่าเรียบร้อยแล้ว:**
`git log` ในเครื่องสะอาดไม่ได้แปลว่า GitHub สะอาด · **object เก่ายังถูกเสิร์ฟ
ตาม SHA ได้** และ run ของ Actions คือป้ายที่ชี้ไปหา SHA เหล่านั้น — ลบ run เก่า
ทิ้งครบ 76 อันแล้ว (2026-08-12) จึงไม่เหลือทางที่คนทั่วไปจะเจอ SHA เดิม
แต่ถ้าใครเคยจดไว้ก็ยังเรียกได้ · การล้างให้หมดจริงต้องขอ GitHub Support GC
ซึ่ง **ยังไม่ได้ทำ** · ประเมินแล้วว่ารับได้เพราะ repo เป็น private มาตลอดและ
สิ่งที่หลุดคืออีเมลสถาบันที่เปิดเผยอยู่แล้ว ไม่ใช่ความลับ

### Versioning

- **SemVer** เริ่มที่ **v1.0.0** — นิยาม 1.0.0 = สัญญา OpenAPI v1 (Phase 3) นิ่ง
  และครบทุกเฟส / ก่อนหน้านั้นถ้าต้อง tag ใช้ 0.x
- ทุก release: git tag + CHANGELOG + แนบ SBOM (มี artifact อยู่แล้วจาก CI)

### Badge program — ของที่ปลดล็อคเมื่อ public

| Badge | เงื่อนไข | หมายเหตุ |
|---|---|---|
| CI status | ได้ทันที | workflow มีแล้ว |
| Coverage | ต่อ Codecov/Coveralls หรือแสดงจาก gate | ตัวเลขจริงมีอยู่แล้ว (ratchet ≥93) |
| **CodeQL** | **ฟรีทันทีเมื่อ public** | ตัด ไว้ใน ADR 0009 เพราะ private ต้องจ่าย — เปิดกลับเป็นอันดับแรก |
| OpenSSF Best Practices (bestpractices.dev) | สมัคร + ตอบ checklist | งานส่วนใหญ่ (เทสต์, SAST, SCA, disclosure policy) ทำครบตามแผนอยู่แล้ว |
| OpenSSF Scorecard | เปิด action เมื่อ public | วัด branch protection, pinned deps, token permission ฯลฯ |
| Accessibility (WCAG 2.2 AA) | ได้ทันที | job `a11y` รัน pa11y-ci จริงทุก push แล้วตั้งแต่ Phase 1 |

> จุดยืนเดิมของโปรเจกต์: badge ต้องสะท้อนของจริงที่ตรวจได้ ไม่ใช่ติดเพื่อประดับ —
> ทุก badge ข้างบนผูกกับ gate ที่รันจริงใน CI ทั้งหมด

---

## ของค้าง (ไม่ผูกกับเฟสใดเฟสหนึ่ง)

รายการเล็ก ๆ ที่รู้แล้วแต่ยังไม่ถึงคิว — เก็บตอนแตะไฟล์นั้นครั้งหน้า

| เรื่อง | สถานะ | เก็บเมื่อไหร่ |
|---|---|---|
| recovery code ของ MFA (ทำโทรศัพท์หายแล้วกู้เอง) | ยังไม่มี — ตอนนี้ต้องให้ผู้ดูแลปิดให้ ซึ่งยังไม่มีคำสั่ง CLI ของ plugin ด้วยซ้ำ | ตอนแตะ `app/plugins/auth/totp/` ครั้งหน้า |
| `password` เป็น plugin ที่มีแต่ manifest (core ยังเรียก `check_password()` ตรง ๆ) | ตั้งใจ — ยกเป็นปัจจัยหลักแบบ plugin ตอนมีตัวที่สอง | Phase 5 พร้อม SSO |
| ~~CI actions ยัง target Node.js 20 ที่ deprecated~~ | ✅ เก็บแล้ว 2026-08-03 — ขยับครบ 5 ตัวเป็น `checkout@v7`, `setup-python@v7`, `setup-node@v7`, `upload-artifact@v7`, `gitleaks-action@v3` ทุกตัวรันบน Node 24 แล้ว (เส้นตาย: GitHub ถอด Node 20 ออกจาก runner 2026-09-16) | — |
| raw SQL 3 จุดใน migration เก่าอ้างตาราง `user` แบบไม่ quote | ยอมค้างไว้ ไม่เพิ่มจุดใหม่ (มี `tests/test_migration_lint.py` ดัก) | baseline squash ตอน Phase 5 |
| WCAG audit ด้วยคน (focus order, ลำดับ heading, ข้อความ error) | automated ครอบได้ ~30–40% ของเกณฑ์เท่านั้น | Phase 7 |
