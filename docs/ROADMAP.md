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

---

## เฟสทั้งหมด (ภาพรวม)

| เฟส | ชื่อ | ขนาด | ตอบหมวด |
|---|---|---|---|
| 0 | Process backbone | S | Maintainability |
| 1 | Cross-cutting inheritance | M | Security(headers), Interaction, Maintainability |
| 2 | Data governance core | L | Audit Trail, Data Retention, PDPA |
| 3 | Service layer + API v1 | M–L | Compatibility, Maintainability |
| 4 | Identity & AuthN/AuthZ | L | Security(authn), Compatibility(SSO) |
| 5 | Deployment parity & flexibility | M | Flexibility, Security(TLS/secrets) |
| 6 | Performance validation | M | Performance Efficiency |
| 7 | Verification & compliance closure | M–L | Security(ASVS/pentest/PDPA), Interaction(WCAG), Audit(SIEM) |

งานต่อเนื่องทุกเฟส: ADR ทุกการตัดสินใจสำคัญ, SCA รายสัปดาห์, SBOM ทุก release,
coverage gate ใน CI

---

## Phase 0 — Process backbone

**เป้าหมาย:** ทุกเฟสถัดไปถูกคุ้มกันด้วย gate อัตโนมัติ ก่อนจะเริ่มเขียนโค้ดเพิ่ม

- CI pipeline (GitHub Actions): pytest + coverage threshold (ตั้งจากค่าปัจจุบันแล้วห้ามต่ำลง),
  ruff (lint + กฎ security-lite), `pip-audit` (SCA), secret scanning
- SBOM: `cyclonedx-py` generate ทุก release เก็บเป็น artifact
- ไดเรกทอรี `docs/adr/` + backfill ADR ของการตัดสินใจที่ทำไปแล้ว
  (UTC storage, msgid ภาษาอังกฤษ, CSRF ก่อน login_required, plugin architecture,
  404 แทน 403, ตารางดวงอาทิตย์ฝังในแอป)
- นโยบาย: ไม่มี manual deploy ข้าม pipeline (ตอนนี้ = push เข้า main ต้องเขียวก่อน)

**ทำไมต้องก่อน:** ไม่แตะโค้ดแอปเลย (rework = 0) แต่ทุกบรรทัดหลังจากนี้ถูกตรวจฟรี
ยิ่งช้า โค้ดที่ไม่เคยผ่าน gate ยิ่งสะสม
**DoD:** push ที่ทำให้เทสต์แดง/coverage ตก/มี CVE ใหม่ ถูกบล็อกอัตโนมัติ

## Phase 1 — Cross-cutting inheritance

**เป้าหมาย:** เก็บหนี้ที่ "ทุก template และทุก request ใหม่ต้องสืบทอด" ให้หมดตอนที่ codebase ยังเล็ก

- **CSP-ready:** ย้าย inline JS ทั้ง 8 จุด (`onchange`/`onsubmit`) ไป `static/app.js`
  แบบ event delegation, inline `style=` ไปเป็น class — แล้วเปิด security headers จริง:
  CSP (ไม่มี `unsafe-inline`), HSTS (เปิดเมื่อมี TLS — Phase 5), `X-Content-Type-Options`,
  `Referrer-Policy`, `frame-ancestors` + เทสต์ header ทุกหน้า
- **WCAG 2.2 AA baseline:** ไล่เก็บ template ปัจจุบัน (มี label/aria แล้วบางส่วน)
  + เพิ่ม automated a11y check (pa11y/axe) เข้า CI — ตั้ง pattern ให้ template ใหม่สืบทอด
- **Structured logging + correlation ID:** log เป็น JSON (timestamp, level, request_id,
  user_id, event) ตัดสินใจ format ครั้งเดียวตรงนี้ — SIEM มาทีหลังแค่ต่อท่อ
  (OpenTelemetry ยังไม่ใส่ — monolith เดียว ใส่เมื่อแตก service ตามเงื่อนไขในโจทย์)

**ทำไมตรงนี้:** สามอย่างนี้ต้นทุน retrofit โตเป็นเส้นตรงตามจำนวน template/route
ตอนนี้มี 6 template — ถูกสุดที่จะจ่ายวันนี้
**DoD:** CSP ไม่มี `unsafe-inline`/`unsafe-eval`, a11y gate เขียวใน CI, ทุก request มี
request_id ใน log

## Phase 2 — Data governance core ★ เฟสที่แพงสุดถ้าทำช้า

**เป้าหมาย:** เปลี่ยนความหมายของ "ลบ" และให้ทุก write ถูกบันทึก **ก่อน** ที่จะมี
ฟีเจอร์/สัญญาใหม่มาทับ

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
  สำคัญที่ยังค้างจากงาน plugin เฟสแรก
- SSO: OIDC (identity กลางมหาวิทยาลัย) เป็น plugin, LDAP เป็นอีก plugin —
  ไม่แยก user store ใหม่ map เข้า `User` เดิม

**ทำไมตรงนี้:** ใช้ของสามเฟสก่อนหน้าครบ — plugin registry (มีแล้ว), audit
(บันทึก auth events ฟรี), API token seam (Phase 3) และ RBAC ต้องเสร็จก่อน SSO
**DoD:** ติดตั้ง/ถอน MFA plugin แล้ว purge ได้ตามสัญญา plugin, เทสต์ lockout,
login ผ่าน OIDC ได้จริงกับ IdP ทดสอบ

## Phase 5 — Deployment parity & flexibility

**เป้าหมาย:** dev/staging/prod เหมือนกันจริง และไม่มี lock-in ที่ไม่มีทางออก

- Dockerfile (multi-stage, non-root) + compose: app (gunicorn), PostgreSQL, Redis
- CI matrix รันเทสต์ทั้ง SQLite และ Postgres — จับ dialect quirk ที่เคยเจอ
  (batch_alter_table, NUMERIC affinity) ให้หมดก่อนใช้จริง
- Rate limiter → `redis://` (ปิดหนี้ `memory://` ต่อ process), ยืนยัน multi-worker
- TLS 1.2+/1.3 ที่ reverse proxy + เปิด HSTS ที่ค้างจาก Phase 1
- Secrets: env → รองรับ Vault/KMS เป็น option (ไม่ hardcode — เป็นอยู่แล้ว)
- IaC ตาม infra เป้าหมายจริงของหน่วยงาน + ADR "exit path" ต่อ managed service ทุกตัว

**ทำไมตรงนี้:** additive ทั้งหมด ไม่รื้อโค้ดแอป — แต่ต้องเสร็จก่อน Phase 6
เพราะ load test บน SQLite/dev server คือตัวเลขหลอก
**DoD:** `docker compose up` ได้ระบบครบ, เทสต์เขียวทั้งสอง DB, app รัน ≥2 replica
โดยพฤติกรรมถูกต้อง (rate limit นับรวม, session ใช้ได้ข้าม replica)

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
