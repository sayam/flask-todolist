# Roadmap — ยกระดับ todolist ให้ถึงเกณฑ์ ISO/IEC 25010:2023 + Audit/Data Governance

> เอกสารนี้คือแผนแม่บทของโปรเจกต์ ใช้ ISO/IEC 25010:2023 เป็นโครง (ตัด Functional
> Suitability ออก) บวก 2 กลุ่มที่มาตรฐานไม่ครอบคลุมเต็มที่: Audit Trail และ
> Data Retention — จัดเป็นเฟสที่ **เรียงตามหลักลด rework** ไม่ใช่เรียงตามหมวดมาตรฐาน
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
  จะเป็นฐานของ auth plugin (MFA/SSO) ใน Phase 4
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
ที่จะออกแบบใน Phase 4 สำหรับ MFA ใช้ซ้ำกับชั้นนี้ได้เลย)

### 4.3 Cache (Redis/memcache) — interface ใน core, backend เป็น plugin
core ประกาศ cache interface (get/set/invalidate) โดย default เป็น no-op
(ไม่มี cache ระบบต้องยังถูกต้อง แค่ช้ากว่า — cache เป็น optimization ห้ามเป็น
correctness) backend จริงเป็น plugin และ rate-limiter storage ใช้ backend
เดียวกันนี้แทนที่จะถือ Redis connection แยกเอง

### 4.4 Landmines ด้าน dialect ที่มีอยู่แล้วในโค้ด (สแกนจริง)

| จุด | ระเบิดกับ | แก้ที่ไหน |
|---|---|---|
| raw SQL `UPDATE user SET ...` ใน migration `296ab616c11b` — `user` เป็น reserved word | PostgreSQL/Oracle/MSSQL (fresh install ที่ replay migration) — **MySQL/MariaDB รอด** | Phase 2: rename เป็น `tdl_user` (หมดปัญหาถาวร) + Phase 5: squash ล้าง raw SQL เก่า |
| MySQL `DATETIME` default ตัด microsecond แต่โค้ดเก็บ `datetime.now()` เต็ม precision | MySQL/MariaDB (silent truncation กระทบ ordering tie และ audit hash) | Phase 5: type variant `DATETIME(6)` + เทสต์ precision ใน CI matrix |
| `batch_alter_table` + data fix เฉพาะ SQLite ใน migration เก่า | ไม่ระเบิด (no-op บนยี่ห้ออื่น) แต่รก | Phase 5: baseline squash ล้างทิ้งพร้อมกัน |
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
| 2 | Data governance core | L | Audit Trail, Data Retention, PDPA |
| 3 | Service layer + API v1 | M–L | Compatibility, Maintainability |
| 4 | Identity & AuthN/AuthZ | L | Security(authn), Compatibility(SSO) |
| 5 | Deployment parity + DB/cache plugins | M–L | Flexibility, Security(TLS/secrets), Compatibility |
| 6 | Performance validation | M | Performance Efficiency |
| 7 | Verification & compliance closure | M–L | Security(ASVS/pentest/PDPA), Interaction(WCAG), Audit(SIEM) |

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

## Phase 2 — Data governance core ★ เฟสที่แพงสุดถ้าทำช้า

**เป้าหมาย:** เปลี่ยนความหมายของ "ลบ" และให้ทุก write ถูกบันทึก **ก่อน** ที่จะมี
ฟีเจอร์/สัญญาใหม่มาทับ

- **ด่านแรก — "schema identity" (migration เดียวจบ, ดู STANDARDS ข้อ 1):**
  เปลี่ยนชื่อตารางเป็น `tdl_*` (core) + กติกา `tdl_<ชนิด>_<ไอดี>_*` สำหรับ plugin,
  ใส่ SQLAlchemy `naming_convention`, `done` → `is_done`,
  rewrite model เป็น SQLAlchemy 2.0 typed style (`Mapped[]`) เปิดทาง mypy strict
  → ผลพลอยได้: ฆ่า landmine reserved word `user` ถาวร ก่อนตาราง audit จะเกิด
- **Data classification (เอกสาร + ADR):** ระบุ PII (username, first/last name),
  transactional (todo/category), audit log — retention period แยกต่อ class
  ไม่ใช้ค่าเดียวทั้งระบบ
- **ADR ข้อขัดแย้ง PDPA vs retention (ตัดสินใจล่วงหน้า):** เสนอ default —
  คำขอลบของ data subject ลบ/pseudonymize ตัว PII ใน user record จริง
  แต่ audit log เก็บครบตาม retention โดยแทนที่ PII ใน log ด้วย pseudonym
  (audit obligation ชนะเรื่องการมีอยู่ของ log, PDPA ชนะเรื่องเนื้อ PII) — รออนุมัติ
- **Temporal/soft-delete:** เพิ่ม `deleted_at` (และ valid-time ที่จำเป็น) กับข้อมูลผู้ใช้
  ทุก route เลิก hard delete (4 จุดที่สแกนพบ) → query กรอง `deleted_at IS NULL`
  ผ่าน helper กลางที่เดียว + purge job ลบจริงเมื่อพ้น retention
- **Audit trail:** ตาราง append-only แยกจาก data ปกติ, บันทึก who-what-when-where
  ผ่าน SQLAlchemy event hooks (after_flush) — **ครอบทุก write อัตโนมัติรวม CLI**
  (actor = username หรือ `cli`), tamper-evident ด้วย hash chain (แต่ละแถวเก็บ
  hash ของแถวก่อนหน้า) + คำสั่ง verify, ไม่มี UI/route แก้ log — อ่านอย่างเดียว
  payload ที่เข้า hash ต้อง serialize ฝั่งแอป (เวลาเป็น ISO string) ให้ผล hash
  ไม่ขึ้นกับ precision ของ DB แต่ละยี่ห้อ (ดู 4.4)
  ซื่อสัตย์กับข้อจำกัด: immutability สมบูรณ์ต้องการ write-once storage ภายนอก
  (บันทึกใน ADR ว่า scale นี้ใช้ hash chain + สิทธิ์ระดับแอป)
- เปิด `PRAGMA foreign_keys=ON` ต่อ connection (ปิดช่อง integrity ของ SQLite)

**ทำไมตรงนี้:** (1) เปลี่ยน semantics ของข้อมูล — ต้องเสร็จก่อน API v1 freeze สัญญา
(2) audit ผ่าน event hooks แปลว่าฟีเจอร์ทุกตัวหลังจากนี้ถูก audit ฟรี
(3) ทุก route ที่เพิ่มก่อนเฟสนี้คือจุด hard-delete ที่ต้องย้อนแก้เพิ่ม
**DoD:** ไม่มี `session.delete`/bulk delete บนข้อมูลผู้ใช้นอก purge job,
mutation test ยืนยันว่า write ที่ไม่ลง audit ถูกจับได้, verify chain ผ่าน

## Phase 3 — Service layer + API v1 (contract-first)

**เป้าหมาย:** แยก business logic ออกจาก HTTP แล้วประกาศสัญญาที่ freeze ได้จริง

- Extract `app/services/` (todo, category, settings) — routes เหลือ thin adapter
  จ่ายต้นทุนรื้อครั้งเดียวตอน route ยังมี ~20 ตัว
- `/api/v1` + OpenAPI spec (flask-smorest หรือเทียบเท่า — spec ต้อง generate
  จากโค้ด ไม่ใช่เขียนมือแล้วหลุด sync), versioning strategy เป็น ADR
- API auth: token (PAT) แยกจาก session cookie — เตรียม seam ให้ OAuth/SSO เกาะ
- HTML routes กับ API เรียก service เดียวกัน — ฟีเจอร์ใหม่เขียนครั้งเดียวได้สองหน้า

**ทำไมตรงนี้:** หลัง Phase 2 เพื่อให้ v1 เกิดบน semantics สุดท้าย (soft delete แล้ว)
และ API ถูก audit ฟรีผ่าน hooks — ก่อน Phase 4 เพื่อให้ SSO/MFA ลงบน seam ที่นิ่ง
**DoD:** OpenAPI spec ตรวจใน CI ว่า sync กับโค้ด, เทสต์ API แยกชุด, ADR versioning

## Phase 4 — Identity & AuthN/AuthZ

**เป้าหมาย:** ยกระดับ authn ให้ถึง ASVS L2 และเปิดทาง identity กลางของมหาวิทยาลัย

- Password policy ตาม NIST SP 800-63B: เน้นความยาว (มีขั้นต่ำ 8 แล้ว — เพิ่มเพดานยาว),
  เช็ค breach list (bundled top-N offline หรือ HIBP k-anonymity), **ไม่มี** กฎ
  complexity/บังคับเปลี่ยนตามรอบ
- Session ตาม OWASP cheat sheet: rotate session ตอน login, idle + absolute timeout,
  cookie flags (`Secure` ผูกกับ TLS ใน Phase 5, `HttpOnly`, `SameSite`)
- ปิดช่องที่ documented ไว้: lockout ต่อ username (กัน brute force แบบเปลี่ยน IP)
  แบบหน่วงเวลา ไม่ใช่ล็อกถาวร (กัน DoS บัญชีคนอื่น)
- RBAC ขั้นต่ำ (admin/user) — ต้องมาก่อน SSO เพราะ SSO ต้อง map group → role
- **Auth เป็น plugin ชนิดที่สอง** บน registry เดิม: `password` เป็น core plugin,
  แล้วเพิ่ม `totp` (MFA) — **จุดที่ต้องออกแบบกลไก plugin-owns-its-own-table**
  (migration แยกต่อ plugin, purge แล้ว table หายตามโดย core ไม่รู้จัก) — เป็น ADR
  สำคัญที่ยังค้างจากงาน plugin เฟสแรก — กลไกเดียวกันนี้รองรับ feature plugin
  ที่มี store ของตัวเอง (task-graph/Neo4j, ดูข้อ 4.2) ในอนาคตด้วย
- SSO: OIDC (identity กลางมหาวิทยาลัย) เป็น plugin, LDAP เป็นอีก plugin —
  ไม่แยก user store ใหม่ map เข้า `User` เดิม

**ทำไมตรงนี้:** ใช้ของสามเฟสก่อนหน้าครบ — plugin registry (มีแล้ว), audit
(บันทึก auth events ฟรี), API token seam (Phase 3) และ RBAC ต้องเสร็จก่อน SSO
**DoD:** ติดตั้ง/ถอน MFA plugin แล้ว purge ได้ตามสัญญา plugin, เทสต์ lockout,
login ผ่าน OIDC ได้จริงกับ IdP ทดสอบ

## Phase 5 — Deployment parity & flexibility

**เป้าหมาย:** dev/staging/prod เหมือนกันจริง, รองรับ DB หลายยี่ห้อตามกลยุทธ์ข้อ 4
และไม่มี lock-in ที่ไม่มีทางออก

- Dockerfile (multi-stage, non-root) + compose: app (gunicorn) + service ของ
  backend ที่เลือก
- **DB backend plugin ชนิดใหม่บน registry เดิม** (ADR contract: ห้าม purge ตัว
  active, ต้องมี export path) — built-in: SQLite, MySQL 8+, MariaDB 11+
  ยี่ห้ออื่น (PostgreSQL, Oracle, MSSQL + cloud preset) เป็น plugin ภายหลัง
- **CI matrix: SQLite + MySQL + MariaDB** — จับ dialect quirk ให้หมด
  (DATETIME(6) variant, เทสต์ precision, batch mode)
- **Baseline squash migration** สำหรับ fresh install (ล้าง landmine ข้อ 4.4)
- Cache plugin interface (ข้อ 4.3): core no-op default + Redis backend plugin
  แล้วชี้ rate-limiter storage ไปที่เดียวกัน (ปิดหนี้ `memory://` ต่อ process)
- TLS 1.2+/1.3 ที่ reverse proxy + เปิด HSTS ที่ค้างจาก Phase 1
- Secrets: env → รองรับ Vault/KMS เป็น option / IaC ตาม infra เป้าหมายจริง
- ADR "exit path" ต่อ managed service ทุกตัวก่อนผูกมัด

**ทำไมตรงนี้:** additive ทั้งหมด ไม่รื้อโค้ดแอป — แต่ต้องเสร็จก่อน Phase 6
เพราะ load test บน SQLite/dev server คือตัวเลขหลอก
**DoD:** `docker compose up` เลือก backend ได้, เทสต์เขียวทั้งสาม DB ใน CI,
app รัน ≥2 replica พฤติกรรมถูกต้อง (rate limit นับรวม, session ข้าม replica)

## Phase 6 — Performance validation

**เป้าหมาย:** ตัวเลขจริง ไม่ใช่คำว่า "เร็วพอ"

- Metrics middleware (Prometheus format): latency histogram ต่อ endpoint → p95/p99
- ตั้งเป้าเป็นตัวเลข (ค่าตั้งต้นเสนอ: p95 < 200ms, p99 < 500ms ที่ N concurrent —
  N มาจากการประเมินผู้ใช้จริง ไม่ใช่เดา แล้วบันทึกเป็น ADR)
- Load test (k6/locust) บน compose stack จาก Phase 5, ทดสอบที่ 1 และ ≥2 replica
- ทบทวน index/query จากผล (มี index `user_id` แล้ว — ตรวจ query ตัวกรองวันที่เพิ่ม)

**DoD:** รายงาน load test ใน repo, เป้า p95/p99 ผ่านที่ concurrency เป้าหมาย

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

---

## ลำดับพึ่งพา (สรุปว่าทำไมสลับไม่ได้)

```
0 → 1 → 2 → 3 → 4 → 7
         │    └─ SSO ต้องมี RBAC + seam จาก 3
         └────── API v1 ต้อง freeze หลัง semantics นิ่ง (2)
0 → 5 → 6 ─────────────→ 7
    └─ load test ต้องมี parity ก่อน
```

- Phase 5 ขนานกับ 3–4 ได้ (ไม่แตะโค้ดแอป) ถ้ามีกำลังทำคู่
- การย้อนแก้ที่ "ยอมจ่ายโดยตั้งใจ": Phase 2 แตะทุก route หนึ่งครั้ง (เปลี่ยน delete),
  Phase 3 แตะทุก route อีกหนึ่งครั้ง (extract service) — สองรอบนี้คือราคาที่ถูกที่สุดแล้ว
  เพราะจ่ายตอน route ยังน้อย และ audit hooks จาก Phase 2 เป็น event-based
  จึงไม่ต้องรื้อซ้ำตอน extract

---

## Public readiness / Badge program (ประตูปลายทาง — ไม่ใช่เฟส)

**สถานะ: ยังไม่ทำ** — เงื่อนไขเปิดประตูคือ **Phase 0–7 ครบและผ่าน DoD ทุกข้อ**
เมื่อถึงจุดนั้นจึงพิจารณาปล่อย public + ระบุ version — ก่อนหน้านั้นโฟกัสอยู่ที่
functional/non-functional ให้ครบตามแผนเท่านั้น

### เช็คลิสต์ก่อนกด public (สำรวจสถานะจริง 2026-08-03)

| รายการ | สถานะตอนนี้ | หมายเหตุ |
|---|---|---|
| `LICENSE` | ❌ ยังไม่มี | **บังคับ** — ไม่มี license = คนอื่นไม่มีสิทธิ์ใช้ตามกฎหมาย ต้องเลือกก่อน public |
| `SECURITY.md` (ช่องทางแจ้งช่องโหว่) | ❌ ยังไม่มี | vulnerability disclosure policy + ช่องทางติดต่อ |
| `CONTRIBUTING.md` + Code of Conduct | ❌ ยังไม่มี | กติกา contribute (gate ทั้งหมดมีอยู่แล้ว แค่เขียนอธิบาย) |
| `CHANGELOG.md` | ❌ ยังไม่มี | generate ได้จาก Conventional Commits ที่ enforce อยู่แล้ว |
| README ฉบับอังกฤษ | ❌ ไทยล้วน | ผู้ชมสากลต้องอ่านได้ — ทำ bilingual |
| ตรวจ PII ใน history | ⚠️ | email จริงอยู่ในทุก commit — ยอมรับหรือ re-author ต้องตัดสินใจก่อน public (rewrite ทีหลังไม่ได้) |
| Secret scan ประวัติเต็มรอบสุดท้าย | มี gitleaks ใน CI | รัน full-history อีกครั้ง ณ วัน public |
| Branch protection | ❌ (solo push ตรง main) | เปิดบังคับเมื่อมีคนนอก (ตาม ADR 0009) |

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
| CI actions ยัง target Node.js 20 ที่ deprecated (`checkout@v4`, `setup-python@v5`, `setup-node@v4`) | ยังไม่พัง — runner บังคับรันบน Node 24 ให้อยู่ แต่จะพังเมื่อ GitHub ถอด fallback | ครั้งหน้าที่แตะ `.github/workflows/ci.yml` |
| raw SQL 3 จุดใน migration เก่าอ้างตาราง `user` แบบไม่ quote | ยอมค้างไว้ ไม่เพิ่มจุดใหม่ (มี `tests/test_migration_lint.py` ดัก) | baseline squash ตอน Phase 5 |
| WCAG audit ด้วยคน (focus order, ลำดับ heading, ข้อความ error) | automated ครอบได้ ~30–40% ของเกณฑ์เท่านั้น | Phase 7 |
