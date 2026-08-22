# OpenSSF Best Practices Badge — passing 67 ข้อ + silver 55 ข้อ

ใบกรอกสำหรับ <https://www.bestpractices.dev> · **เว็บนั้นเป็นแหล่งจริงหลังส่งแล้ว**
ไฟล์นี้คือใบตอบที่เตรียมไว้ พร้อมหลักฐานว่าแต่ละข้อผ่านด้วยอะไร — เก็บไว้เพราะ
badge ถูกทบทวนเป็นรอบ และคำตอบที่ไม่มีที่มาคือคำตอบที่เขียนใหม่ทุกครั้ง
(หลักเดียวกับ [ASVS.md](ASVS.md))

> **ก่อนออกรุ่นถัดไป มีสามช่องบนเว็บที่ต้องแก้** — ดูหัวข้อ
> "สิ่งที่ต้องกรอกบนเว็บก่อนออกรุ่นถัดไป" ท้ายไฟล์ (ตรวจกับ API แล้ว ไม่ใช่จากความจำ)

**สถานะ: badge อยู่ระดับ SILVER (100% · `achieved_silver_at`
2026-08-16T14:45Z — verify จาก API) · passing คง 100% · gold เริ่มนับ 26%**
— ระดับ passing: 66 ผ่าน · 1 ไม่เกี่ยวข้อง · ระดับ silver: 46 Met · 6 N/A ·
3 Unmet โดยตั้งใจ (ตาราง silver อยู่ท้ายไฟล์) · คำตอบในไฟล์นี้กับบนเว็บ
ตรงกันทั้งสองระดับ (รอบก่อนหน้า 2026-08-14/15 ดูหมายเหตุท้ายไฟล์)

เกณฑ์ทั้งหมด 67 ข้อ: MUST 43 · SHOULD 10 · SUGGESTED 14
**MUST ผ่านครบทั้ง 43 ข้อ** ซึ่งเป็นเงื่อนไขของ badge ระดับ passing

---

## Basics

| เกณฑ์ | ตอบ | หลักฐาน |
|---|---|---|
| `description_good` MUST | ผ่าน | `README.md` ย่อหน้าแรกบอกว่าเป็นอะไรและแก้ปัญหาอะไร · ช่อง About ของ repo เติมแล้ว (อัปเดตตามรุ่น — ล่าสุด v2.2.0) |
| `interact` MUST | ผ่าน | `README.md` มีวิธีติดตั้ง/รัน · `CONTRIBUTING.md` มีวิธีเสนอการเปลี่ยนแปลง · Issues เปิดอยู่ |
| `contribution` MUST | ผ่าน | `CONTRIBUTING.md` — อธิบายว่าใช้ PR, ต้องผ่าน 27 required check (จาก 30 check — scorecard, `posture` และ job ของ workflow release ไม่รันบน PR จึงไม่บังคับ), merge ด้วย rebase, และกติกาลงทะเบียนไฟล์เทสต์ใน `gates.yaml` |
| `contribution_requirements` SHOULD | ผ่าน | `CONTRIBUTING.md` — Conventional Commits (หัว ≤72), ruff/mypy, **กติกา mutation test ของเทสต์ใหม่** |
| `floss_license` MUST | ผ่าน | `LICENSE` (AGPL-3.0-or-later — ADR 0070) · เอกสารอยู่ใต้ CC BY-SA 4.0 ที่ `LICENSE-docs` |
| `floss_license_osi` SUGGESTED | ผ่าน | AGPL-3.0 เป็นสัญญาอนุญาตที่ OSI รับรอง — [ADR 0070](adr/0070-relicense-to-agpl-and-cc-by-sa.md) (เดิม MIT ตาม ADR 0038) |
| `license_location` MUST | ผ่าน | `LICENSE` ที่รากของ repo |
| `documentation_basics` MUST | ผ่าน | `README.md` + `docs/OPERATIONS.md` |
| `documentation_interface` MUST | ผ่าน | `docs/openapi.json` — **generate จากโค้ด** และ job `openapi` ใน CI เทียบว่าตรงกับโค้ดทุก push |
| `sites_https` MUST | ผ่าน | โฮสต์บน GitHub ทั้งหมด |
| `discussion` MUST | ผ่าน | GitHub Issues (ค้นได้ · เธรดได้ · เห็นได้โดยไม่ต้องล็อกอิน) |
| `english` SHOULD | ผ่าน | `README.md` สองภาษา **อังกฤษขึ้นก่อน** · ข้อความในโค้ดเป็นอังกฤษเสมอ (ภาษาไทยอยู่ในไฟล์คำแปล) |
| `maintained` MUST | ผ่าน | มี commit ต่อเนื่องทุกสัปดาห์นับจากเปิด repo · เจ้าของตอบ issue เอง (วันที่แน่นอนอ่านจาก `git log` ไม่ตรึงไว้ที่นี่ — ภาพถ่ายของวันที่คือของที่ล้าสมัยเองเสมอ) |

## Change Control

| เกณฑ์ | ตอบ | หลักฐาน |
|---|---|---|
| `repo_public` MUST | ผ่าน | <https://github.com/sayam/flask-todolist> |
| `repo_track` MUST | ผ่าน | git |
| `repo_interim` MUST | ผ่าน | commit ระหว่างทางอยู่ครบบน `main` ไม่ใช่แค่ของที่ release |
| `repo_distributed` SUGGESTED | ผ่าน | git |
| `version_unique` MUST | ผ่าน | ทุกรุ่นมี tag ไม่ซ้ำ — v1.0.0 ถึง v2.2.0 |
| `version_semver` SUGGESTED | ผ่าน | SemVer · นิยามของ 1.0.0 บันทึกไว้ใน `docs/ROADMAP.md` |
| `version_tags` SUGGESTED | ผ่าน | git tag ทุกรุ่น (v1.0.0 ถึง v2.2.0) |
| `release_notes` MUST | ผ่าน | `CHANGELOG.md` (Keep a Changelog) ผูกกับ `app.__version__` และมีเทสต์คุม |
| `release_notes_vulns` MUST | ผ่าน | **v1.5.0 คือรุ่นแรกที่แก้ CVE และ notes ระบุครบทั้งเจ็ด** (cryptography 45.0.7→50.0.0) — ตามที่นโยบายใน `docs/SECURITY-CADENCE.md` สัญญาไว้ |

## Reporting

| เกณฑ์ | ตอบ | หลักฐาน |
|---|---|---|
| `report_process` MUST | ผ่าน | GitHub Issues · `CONTRIBUTING.md` |
| `report_tracker` SHOULD | ผ่าน | GitHub Issues |
| `report_responses` MUST | ผ่าน | **ยังไม่มีรายงานจากคนนอกเลย** (repo เพิ่งเป็นสาธารณะ 2026-08-12) เจ้าของเฝ้า Issues เอง |
| `enhancement_responses` SHOULD | ผ่าน | เช่นเดียวกับข้อบน |
| `report_archive` MUST | ผ่าน | Issues ของ GitHub เปิดอ่านสาธารณะและค้นได้ |
| `vulnerability_report_process` MUST | ผ่าน | `SECURITY.md` |
| `vulnerability_report_private` MUST | ผ่าน | GitHub Private Vulnerability Reporting (**เปิดใช้แล้ว** ยืนยันจาก API) · `SECURITY.md` ไม่มีอีเมลอยู่ในไฟล์โดยตั้งใจ |
| `vulnerability_report_response` MUST | ผ่าน | ยังไม่เคยได้รับรายงาน · นโยบายคือ **ตอบรับภายใน 7 วัน** (`SECURITY.md` · มีเทสต์บังคับว่าตัวเลขในสามที่ตรงกัน) |

## Quality

| เกณฑ์ | ตอบ | หลักฐาน |
|---|---|---|
| `build` MUST | ผ่าน | `Dockerfile` (multi-stage) · job `image` ใน CI **build จริงแล้วยิงใส่มันทุก push** ไม่ใช่แค่ตรวจ syntax |
| `build_common_tools` SUGGESTED | ผ่าน | Docker + pipenv |
| `build_floss_tools` SHOULD | ผ่าน | ทุกตัวเป็น FLOSS |
| `test` MUST | ผ่าน | pytest ทั้งชุดเป็น required check ทุก push (job `test`) · coverage floor `fail_under = 97` แบบ ratchet · `diff-cover` บังคับบรรทัดที่แก้ 100% · **ไม่ตรึงจำนวนเทสต์ไว้ที่นี่** เพราะทุก PR เพิ่มเทสต์ เลขภาพถ่ายจึงผิดตั้งแต่ commit ถัดไป — นับสดด้วย `pipenv run pytest --collect-only -q` |
| `test_invocation` SHOULD | ผ่าน | `pipenv run pytest` |
| `test_most` SUGGESTED | ผ่าน | coverage gate `fail_under = 97` (**ratchet: ขยับขึ้นได้อย่างเดียว**) + `diff-cover` บังคับบรรทัดที่แก้ 100% |
| `test_continuous_integration` SUGGESTED | ผ่าน | 30 check (27 บังคับ) — รวมสามยี่ห้อฐานข้อมูล, stack จริง, SSO, LDAP, DAST |
| `test_policy` MUST | ผ่าน | `CONTRIBUTING.md` + `CLAUDE.md`: **เทสต์ใหม่ทุกตัวต้องถูกพิสูจน์ด้วย mutation test ว่าจับของจริงได้ก่อนถือว่าเสร็จ** และ `diff-cover` บังคับที่ CI · ตั้งแต่เฟส 8 มี `gates.yaml` บังคับอีกชั้นว่า **ไฟล์เทสต์ทุกไฟล์ต้องถูกตัดสินว่าเป็นของ gate ไหน** (`tests/test_gates.py`) |
| `tests_are_added` MUST | ผ่าน | PR ล่าสุดมีเทสต์มาด้วยทุกใบ — และ `gates.yaml` ทำให้ "ลืมเพิ่มเทสต์" กลายเป็น CI แดง ไม่ใช่เรื่องที่ต้องมีคนสังเกต (`tests/test_gates.py`, `test_overlay.py`, `test_harness.py`, `test_asvs_probe.py`) |
| `tests_documented_added` SUGGESTED | ผ่าน | `CONTRIBUTING.md` |
| `warnings` MUST | ผ่าน | ruff (รวมกฎแนว bandit) · mypy โหมด strict · xenon (ความซับซ้อน) · interrogate (docstring) |
| `warnings_fixed` MUST | ผ่าน | job `lint` บล็อก merge — และเป็น required check |
| `warnings_strict` SUGGESTED | ผ่าน | threshold ทุกตัวเป็น **ratchet ขยับขึ้นได้อย่างเดียว** · รายชื่อ module ที่ mypy strict **ขยายได้ ห้ามหด** |

## Security

| เกณฑ์ | ตอบ | หลักฐาน |
|---|---|---|
| `know_secure_design` MUST | ผ่าน | ประเมินตนเองต่อ **ASVS 5.0 L2 ครบ 253/253 ข้อ** (`docs/ASVS.md`) · การตัดสินใจด้านความปลอดภัยทุกเรื่องมี ADR |
| `know_common_errors` MUST | ผ่าน | `docs/ASVS.md` ครอบ injection/XSS/CSRF/session/access control · CSP ไม่มี `unsafe-inline` ([ADR 0010](adr/0010-csp-without-unsafe-inline.md)) · ความเป็นเจ้าของข้อมูลตอบ 404 ไม่ใช่ 403 ([ADR 0004](adr/0004-ownership-404-not-403.md)) |
| `crypto_published` MUST | ผ่าน | scrypt (รหัสผ่าน) · HMAC-SHA256 (สายของ audit, การผูกคุกกี้) · SHA-256 (API token) · TOTP ตาม RFC 6238 · AES-256-GCM (encryption at rest ของความลับ TOTP — ADR 0046) |
| `crypto_call` SHOULD | ผ่าน | ใช้ `hashlib`/`hmac`/`secrets` ของ Python และ werkzeug — **ไม่มีการเขียนอัลกอริทึมเอง** |
| `crypto_floss` MUST | ผ่าน | ทุกตัวเป็น FLOSS |
| `crypto_keylength` MUST | ผ่าน | ความลับของ token 256 บิต · `SECRET_KEY` บังคับ ≥32 ตัวอักษร · TOTP secret 160 บิต · `DATA_ENCRYPTION_KEY` 256 บิต (ADR 0046) |
| `crypto_working` MUST | ผ่าน | ไม่มี MD5/SHA-1 ที่ไหนเลย **ยกเว้น HMAC-SHA1 ของ TOTP ซึ่ง RFC 6238 กำหนด** และ NIST ยังยอมรับสำหรับการใช้แบบ HMAC — บันทึกเปิดเผยไว้ที่ `docs/ASVS.md` V11.4.1 |
| `crypto_weaknesses` SHOULD | ผ่าน | เช่นเดียวกับข้อบน |
| `crypto_pfs` SHOULD | ผ่าน | `deploy/nginx-tls.conf` จำกัดไว้ที่ ECDHE เท่านั้น · **วัดจริงทั้งก่อนและหลังแก้** — ก่อนแก้ nginx ยอมรับ `AES128-GCM-SHA256` ซึ่งไม่มี PFS · `scripts/check_tls_pfs.sh` ยืนยัน และ job `stack` รันทุก push |
| `crypto_password_storage` MUST | ผ่าน | scrypt + salt ต่อผู้ใช้ (werkzeug) · **`password_hash` ห้ามออกจากระบบทุกกรณี** ([ADR 0014](adr/0014-pdpa-vs-audit-retention.md)) · นโยบายรหัสผ่านอยู่ที่ `app/services/passwords.py` ที่เดียว ([ADR 0019](adr/0019-password-policy-nist-800-63b.md)) |
| `crypto_random` MUST | ผ่าน | `secrets` ของ Python ทุกจุดที่สุ่ม |
| `delivery_mitm` MUST | ผ่าน | ส่งมอบผ่าน GitHub (HTTPS/SSH) เท่านั้น |
| `delivery_unsigned` MUST | ผ่าน | ไม่มีการดึง hash ผ่าน http ที่ไหน · **dependency ทุกชั้นถูกตรึงด้วย hash**: `Pipfile.lock`, `pins/*/requirements.txt` (`--require-hashes`), `pins/pa11y/package-lock.json` (`npm ci`), action เป็น commit SHA, base image เป็น digest |
| `vulnerabilities_fixed_60_days` MUST | ผ่าน | ไม่มีช่องโหว่ค้างใน**ซอฟต์แวร์ที่โครงการผลิต** · advisory ที่รับไว้เหลือ 1 ข้อ (`extract-zip` — ยังไม่มีรุ่น fix) เป็นของ**เครื่องมือ CI** (`pins/`) ซึ่งไม่อยู่ใน image ที่ deploy — สาม advisory ของ `mcp` ปิดแล้วด้วย semgrep 1.173.0 (2026-08-16) — ประเมินและบันทึกไว้ใน `docs/SECURITY-CADENCE.md` พร้อมเงื่อนไขที่ทำให้คำตัดสินหมดอายุ |
| `vulnerabilities_critical_fixed` SHOULD | ผ่าน | กรอบเวลา **critical 7 วัน · high 30 · medium 90** นับจากวันที่รู้ (`docs/SECURITY-CADENCE.md` · `tests/test_cadence.py` บังคับ) |
| `no_leaked_credentials` MUST | ผ่าน | gitleaks สแกน**ทั้งประวัติ** (`scripts/secret_scan_history.sh`) + job `secret-scan` ทุก push + push protection ของ GitHub · `.gitleaksignore` มีข้อยกเว้นเดียวคือค่าทดสอบของ RFC 6238 ซึ่ง decode แล้วเป็น `12345678901234567890` |

## Analysis

| เกณฑ์ | ตอบ | หลักฐาน |
|---|---|---|
| `static_analysis` MUST | ผ่าน | CodeQL ชุด `security-extended` (python + javascript) · semgrep `p/flask` `p/python` · ruff กฎแนว bandit |
| `static_analysis_common_vulnerabilities` SUGGESTED | ผ่าน | ทั้ง CodeQL `security-extended` และ semgrep ครอบ CWE ที่พบบ่อย |
| `static_analysis_fixed` MUST | ผ่าน | CodeQL **เปิดค้าง 0 ข้อ** · รอบแรกเจอของจริงสองอย่างและแก้แล้ว (Werkzeug debugger ที่ติดไปกับ image · log ที่พิมพ์ URL ของ store ดิบ ๆ) · การปิด alert ต้องมีเหตุผลที่ชี้ไปหาหลักฐานได้ และมีรอบทบทวนทุก 6 เดือน |
| `static_analysis_often` SUGGESTED | ผ่าน | ทุก push |
| `dynamic_analysis` SUGGESTED | ผ่าน | ZAP baseline ยิงใส่ stack ที่รันจริง (TLS + 2 replica) **แบบที่ login แล้ว** ทุก push · `tests/test_api_fuzz.py` สร้างคำขอจาก `docs/openapi.json` เอง · k6 load test |
| `dynamic_analysis_unsafe` SUGGESTED | ไม่เกี่ยวข้อง | ไม่มีโค้ดในภาษาที่จัดการหน่วยความจำเอง (Python ล้วน) |
| `dynamic_analysis_enable_assertions` SUGGESTED | ผ่าน | เทสต์ทั้งชุดเป็น assertion · `tests/test_db_integrity.py` วัด**ผล**ของการบังคับ FK ไม่ใช่แค่อ่านค่า pragma |
| `dynamic_analysis_fixed` MUST | ผ่าน | ZAP: ข้อที่ตั้งเป็น FAIL ผ่านหมด · fuzz ของ API รอบแรกเจอสามอย่างและแก้แล้ว |

---

## `crypto_pfs` — แก้แล้ว และวัดจริงทั้งสองทิศ (2026-08-13)

เดิม `deploy/nginx-tls.conf` เปิด TLS 1.2 ไว้โดยไม่จำกัดชุดรหัสลับ

**วัดก่อนแก้** (nginx:1.27-alpine ตัวเดียวกับที่ compose ใช้): การต่อรองตามปกติ
ได้ `ECDHE-RSA-AES256-GCM-SHA384` ซึ่งดูปลอดภัยดี **แต่ไคลเอนต์ที่ขอ
`AES128-GCM-SHA256` มาตรง ๆ ก็ได้รับ** — แปลว่าใครที่เก็บทราฟฟิกไว้วันนี้
แล้ววันหนึ่งได้กุญแจส่วนตัวของเซิร์ฟเวอร์ไป จะถอดรหัสย้อนหลังได้ทั้งหมด
**ด่านที่ดูแค่ "ต่อรองแล้วได้อะไร" จะรายงานว่าผ่าน**

**วัดหลังแก้**: ชุดที่ไม่มี PFS ถูกปฏิเสธ (alert 40) · การต่อรองปกติยังได้ ECDHE
· TLS 1.3 ยังทำงาน · และแอปยังตอบผ่านขา TLS ตามปกติ

**พิสูจน์ตัววัดเองด้วย** — `scripts/check_tls_pfs.sh` ต้องแดงกับ config เดิม
(แดงจริง พร้อมบอกชื่อชุดที่ถูกยอมรับ) และต้องตอบ "ยังไม่ได้ทดสอบอะไร" ไม่ใช่
"ผ่าน" เมื่อยิงไปที่พอร์ตที่ไม่มีใครฟัง — กับดักที่ `docs/SECURITY-CADENCE.md`
บันทึกไว้เองว่า `openssl s_client` ล้มเหลวเหมือนกันหมดทั้งสองกรณี

**รอบแรกสคริปต์อ่านสัญญาณผิด**: ไปอ่านบรรทัด `Cipher :` ในบล็อก session ซึ่ง
พิมพ์ `0000` ตอนจับมือไม่สำเร็จ — ค่า *ไม่ว่าง* มันจึงแปล "ถูกปฏิเสธ" เป็น
"ยอมรับชุดชื่อ 0000" แล้วรายงานว่าการแก้ทำให้ TLS 1.3 ใช้การไม่ได้ ทั้งที่ TLS 1.3 ปกติดี
· **ด่านที่วัดผิดตัวสร้างสัญญาณเตือนลวงได้ ไม่ใช่แค่เงียบตอนควรดัง**
ตัวจริงคือ exit code ของ openssl กับบรรทัดสรุป `New, TLSvX, Cipher is Y`

## ขั้นตอน submit (ทำครบแล้ว 2026-08-15/16 — เก็บไว้เป็นบันทึก)

ทุกข้อในลิสต์เดิมเสร็จแล้ว: ช่อง About เติมแล้ว (อัปเดตเป็น v1.4.0) ·
โครงการคือ **#14085** ได้ **passing (100%)** · badge อยู่ใน `README.md`
ทั้งสองภาษา · คำตอบ 67 ข้อบนฟอร์มตรงกับตารางข้างบน (verify จาก API
2026-08-16 — ทุกช่อง version อ้าง v1.4.0)

---

---

## ระดับ Silver — 55 เกณฑ์ (100% · achieved 2026-08-16)

ไล่กรอกหลัง v1.5.0 ออก (release แรกที่เซ็น — `signed_releases` คือใบเบิกทาง)
· **MUST ครบทุกข้อ** · Unmet 3 ตัวเป็น SHOULD/SUGGESTED ที่ตอบตรงพร้อม
เหตุผล ซึ่งกติกาของ BadgeApp ไม่ฉุดเปอร์เซ็นต์ · เกณฑ์เงื่อนไข ("ถ้าไม่มี X
ให้ตอบ N/A") ตอบ N/A เสมอแม้ Met จะได้คะแนนเท่ากัน — Met ที่เงื่อนไขไม่เกิด
คือคำตอบที่สื่อความผิด

| เกณฑ์ | ตอบ | หลักฐาน |
|---|---|---|
| `achieve_passing` MUST | Met | passing 100% ตั้งแต่ 2026-08-15 |
| `contribution_requirements` MUST | Met | `CONTRIBUTING.md` — PR-only + 27 required checks + mutation rule + ลงทะเบียน gates.yaml |
| `dco` SHOULD | **Unmet ตั้งใจ** | ไม่มี DCO/CLA — inbound = outbound ([ADR 0038](adr/0038-mit-license.md)) |
| `governance` MUST | Met | ธรรมนูญสี่ชั้น + intake ([ADR 0051](adr/0051-project-constitution-and-intake.md)) · ADR เป็น intake log · PR-only ([ADR 0053](adr/0053-solo-maintainer-sod-compensating-controls.md)) |
| `code_of_conduct` MUST | Met | `CODE_OF_CONDUCT.md` |
| `roles_responsibilities` MUST | Met | บทบาทเดียวถือครบ เขียนเปิดเผยพร้อม compensating controls (ADR 0053 · CONTRIBUTING ข้อ 11) |
| `access_continuity` MUST | Met | หัวข้อ continuity ใน `CONTRIBUTING.md` — ไม่มีของส่วนตัวจำเป็น (keyless · automation ใน repo) fork เดินต่อได้ครบ |
| `bus_factor` SHOULD | **Unmet ตั้งใจ** | bus factor 1 โดยธรรมชาติของโปรเจกต์ส่วนตัว — mitigation อยู่ใน ADR 0053 + หัวข้อ continuity |
| `documentation_roadmap` MUST | Met | `docs/ROADMAP.md` + roadmap ราย axis |
| `documentation_architecture` MUST | Met | `docs/ARCHITECTURE.md` (42010 · เทสต์คุม) |
| `documentation_security` MUST | Met | `docs/ASVS.md` (253/253 · หลักฐานถูกเทสต์ตรวจ) + `SECURITY.md` |
| `documentation_quick_start` MUST | Met | README "Try it" |
| `documentation_current` MUST | Met | รอบตรวจเอกสาร 2026-08-16 + เลขโฆษณามีเทสต์อ่านคู่ |
| `documentation_achievements` MUST | Met | badge บน README (บน + ล่าง) |
| `accessibility_best_practices` SHOULD | Met | WCAG 2.2 AA สองชั้นทุก push + `docs/ACCESSIBILITY-AUDIT.md` |
| `internationalization` SHOULD | Met | gettext en/th + เทสต์ความครบของ catalog |
| `sites_password_security` MUST | N/A | ไม่ได้รัน site ที่เก็บรหัสผ่านเอง (GitHub ดูแล) |
| `maintenance_or_update` MUST | Met | สัญญา N-1 + expand–contract ([ADR 0048](adr/0048-operations-ha-n1.md)) |
| `report_tracker` MUST | Met | GitHub Issues |
| `vulnerability_report_credit` MUST | N/A | ยังไม่มีรายงานจากคนนอกที่ถูกแก้ — นโยบายให้เครดิตอยู่ใน `SECURITY.md` แล้ว |
| `vulnerability_response_process` MUST | Met | `SECURITY.md` — ตอบรับ 7 วัน · ประเมิน 14 · แก้ตามกรอบความรุนแรง (เทสต์คุม cadence) |
| `coding_standards` MUST | Met | `docs/STANDARDS.md` + CONTRIBUTING |
| `coding_standards_enforced` MUST | Met | ruff ทุกกฎ · mypy strict · xenon · interrogate — ratchet ทางเดียว |
| `build_standard_variables` MUST | N/A | Python ไม่มี compiled build |
| `build_preserve_debug` SHOULD | N/A | เดียวกัน |
| `build_non_recursive` MUST | N/A | เดียวกัน |
| `build_repeatable` MUST | Met | lock ทุกชั้นด้วย hash · image จาก digest · SBOM สร้างซ้ำได้ใน CI (ADR 0058) |
| `installation_common` MUST | Met | pipenv / docker compose ตามมาตรฐาน ecosystem |
| `installation_standard_variables` MUST | Met | ไม่มี installer เอง — ใช้ convention ของ pip/docker ตรง ๆ |
| `installation_development_quick` MUST | Met | clone → รันได้ในห้าคำสั่ง |
| `external_dependencies` MUST | Met | Pipfile ราย category + SBOM ทุก release + `docs/SUPPLY-CHAIN.md` (20 gate) |
| `dependency_monitoring` MUST | Met | Dependabot + pip-audit/npm-audit ทุกชั้นสองทิศ |
| `updateable_reused_components` MUST | Met | ทุกอย่างเป็น package มาตรฐานจาก lockfile ไม่มี vendored |
| `interfaces_current` SHOULD | Met | Python 3.13 · SQLAlchemy 2.0 typed · deprecation โผล่ผ่านด่าน lint/type |
| `automated_integration_testing` MUST | Met | dialects จริงสองยี่ห้อ · stack TLS 2 replica · SSO/LDAP จริง · DAST แบบ login ทุก push |
| `regression_tests_added50` MUST | Met | ทุก bugfix มาพร้อมเทสต์ที่พิสูจน์ด้วย mutation |
| `test_statement_coverage80` MUST | Met | 97% (เปิด branch) ratchet + diff-cover 100% |
| `test_policy_mandated` MUST | Met | CONTRIBUTING ข้อ 1 + ข้อ 8 |
| `tests_documented_added` MUST | Met | เดียวกัน — บังคับด้วย gates registry |
| `warnings_strict` MUST | Met | warning = error ใน CI ทุกตัว |
| `implement_secure_design` MUST | Met | least privilege · complete mediation ใน service layer · fail-safe defaults (config ผิด = ไม่ start) |
| `crypto_weaknesses` MUST | Met | ข้อยกเว้นเดียว HMAC-SHA1 ใน TOTP ตาม RFC 6238 (บันทึกใน ASVS V11.4.1) |
| `crypto_algorithm_agility` SHOULD | Met | รูปเก็บมีเวอร์ชัน `enc:v1:` (ADR 0046) · hash รหัสผ่าน self-describing |
| `crypto_credential_agility` MUST | Met | คีย์อยู่นอกโค้ด หมุนแยกกัน (ADR 0030/0046 · OPERATIONS) |
| `crypto_used_network` SHOULD | Met | stack TLS จริงทุก push |
| `crypto_tls12` SHOULD | Met | gate `tls-modern-protocols-only` |
| `crypto_certificate_verification` MUST | Met | client TLS ทุกตัวใช้ verification ค่าเริ่มต้น ไม่มีที่ไหนปิด |
| `crypto_verification_private` MUST | Met | verify ก่อนส่งของลับเสมอ (พฤติกรรมเดียวกัน) |
| `signed_releases` MUST | Met | cosign keyless + SLSA provenance (ADR 0058) · วิธี verify ใน `SECURITY.md` |
| `version_tags_signed` SUGGESTED | **Unmet ตั้งใจ** | ยังไม่เซ็น tag — เงื่อนไขทบทวนใน ADR 0058 |
| `input_validation` MUST | Met | allowlist ทุกชั้น (marshmallow RAISE · service · lookup) + fuzz จาก spec |
| `hardening` SHOULD | Met | CSP ไม่มี inline · Talisman · container read-only ไม่ใช่ root · hadolint/trivy |
| `assurance_case` MUST | Met | `docs/ASVS.md` + crosswalk `docs/GATES-ASVS.md` + `docs/ARCHITECTURE.md` |
| `static_analysis_common_vulnerabilities` MUST | Met | CodeQL security-extended + semgrep p/flask (พิสูจน์ขอบเขตสแกน) |
| `dynamic_analysis_unsafe` MUST | N/A | Python — ไม่มีโค้ดภาษา memory-unsafe |

**กับดักของฟอร์มที่เจอระดับนี้**: `signed_releases` อยู่ silver ไม่ใช่ passing
(ต้องสลับ `criteria_level=1`) · Save ต่อแท็บ — `updated_at` ใน JSON ของ
โปรเจกต์คือตัวจับว่าบันทึกจริง · **Gold (ตอนนี้ 26%) ติดเงื่อนไขโครงสร้าง**:
ต้องมี contributor ที่ไม่เกี่ยวข้องกัน ≥2 — เป็นไปได้เมื่อมีคนที่สองจริง
(เงื่อนไขเดียวกับ required review ของ ADR 0053)
· **รายการว่าที่ตอบได้ตอนนี้อยู่ในหัวข้อ "ระดับ gold — ตอบได้แล้วกี่ข้อ" ด้านล่าง**

## ระดับ gold — ตอบได้แล้วกี่ข้อ ณ 2026-08-20

เกณฑ์ gold มี 23 ข้อ · ตอบไปแล้ว 9 (Met 8 · Unmet 1) · **ยังว่าง 14 ข้อ**
· ตัวเลขบนเว็บคือ 26%

**gold ยังไปไม่ถึงแน่นอน** เพราะติดข้อที่โครงสร้างของโปรเจกต์เป็นตัวกำหนด
(คนเดียว) — แต่การตอบข้อที่ตอบได้ยังคุ้ม เพราะทะเบียนที่ว่างไว้แปลว่า
"ยังไม่ได้ดู" ซึ่งคนละเรื่องกับ "ดูแล้วยังไม่ผ่าน"

### ตอบ Met ได้ทันที — หลักฐานมีอยู่แล้ว

| เกณฑ์ | ชนิด | หลักฐานที่ใช้ตอบ |
|---|---|---|
| `test_statement_coverage90` | MUST | **วัดแล้ว 97.17%** (`fail_under = 97` ใน `pyproject.toml` เป็นพื้นที่ขยับขึ้นทางเดียว · job `test` บังคับทุก push) |
| `test_branch_coverage80` | MUST | **วัดแล้ว 93.96%** (1,058 จาก 1,126 สาขา · `[tool.coverage.run] branch = true`) |
| `code_review_standards` | MUST (ต้องมี URL) | `CONTRIBUTING.md` — PR-only, Conventional Commits, กติกา mutation test, การลงทะเบียนไฟล์เทสต์ใน `gates.yaml` · คำตัดสินอยู่ใน ADR 0053 |
| `security_review` | MUST | `docs/ASVS.md` (ประเมิน ASVS 5.0 L2 ครบ 253 ข้อ) · `docs/ISO27001.md` (116 ข้อ) · `docs/RISK-ASSESSMENT.md` · และรอบ audit 23 รอบที่มีทะเบียนใน [AUDIT-LOG.md](AUDIT-LOG.md) |
| `hardened_site` | MUST (ต้องมี URL) | หน้าโครงการคือ GitHub ซึ่งส่ง header ครบ · ตัวแอปเองบังคับ CSP/HSTS ผ่าน Talisman และมี gate คุม (`tests/test_security_headers.py`) |
| `require_2FA` | MUST | ผู้ดูแลคนเดียวเปิด 2FA ไว้ (ตรวจตามรอบ "hardening ของบัญชีเจ้าของ" — ทบทวนล่าสุด 2026-08-17) · GitHub บังคับ 2FA กับผู้ร่วมพัฒนาตั้งแต่ 2023 |
| `secure_2FA` | SHOULD | ถ้าเป็น TOTP/passkey (ไม่ใช่ SMS) — **เจ้าของยืนยันเองก่อนตอบ** |

### ตอบ Unmet พร้อมเหตุผล — ตรงกว่าปล่อยว่าง

| เกณฑ์ | ชนิด | ทำไมยังไม่ผ่าน |
|---|---|---|
| `contributors_unassociated` | MUST | ผู้ดูแลคนเดียว — เหตุผลเดียวกับ `bus_factor` ที่ตอบ Unmet ไปแล้ว |
| `two_person_review` | MUST | เหตุผลเดียวกัน · ADR 0053 บันทึกไว้ว่า required review ต้องมีคนที่สอง |
| `copyright_per_file` | MUST | **ตัดสินใจไว้แล้วว่าไม่ทำ** — ประกาศสัญญาอนุญาตที่ระดับ repo (`ruff` ปิดกฎ `CPY001` พร้อมเหตุผลใน `pyproject.toml`) |
| `license_per_file` | MUST | เหตุผลเดียวกัน · **ข้อนี้เปลี่ยนใจได้ถูก** — เติม `SPDX-License-Identifier` ต่อไฟล์เป็นงานเชิงกลไกที่มีเครื่องช่วยได้ |

### ยังตอบไม่ได้จนกว่าจะมีของจริง

| เกณฑ์ | ชนิด | ต้องมีอะไรก่อน |
|---|---|---|
| `small_tasks` | MUST (ต้องมี URL) | **ตอบได้แล้ว** — issue [#186](https://github.com/sayam/flask-todolist/issues/186) เปิดอยู่และติดป้าย `good first issue` (ตอนเขียนแถวนี้ครั้งแรก repo มี 0 issue) · ช่องบนเว็บยังเป็น `?` |
| `build_reproducible` | MUST (ต้องมี URL) | ทุกอย่างถูกตรึงแล้ว (`Pipfile.lock` มี hash · `pins/` ใช้ `--require-hashes` · base image ตรึง digest) แต่ **ยังไม่เคยพิสูจน์ว่า build ซ้ำได้ผลไบต์ต่อไบต์** — ตอบ Met โดยไม่วัดคือสิ่งที่โปรเจกต์นี้ห้ามตัวเองมาตลอด |

**ตอบไปแล้ว และผลออกมาตามที่ประเมินไว้** — gold ขยับจาก 26% เป็น **57%**
โดยไม่ได้แก้โค้ดอะไรเลย · ที่เหลือเป็นรายการที่*ตัดสินแล้ว* ไม่ใช่รายการที่ยังไม่ได้ดู
(ดูรายการที่ยังไม่ Met ท้ายหัวข้อถัดไป)

## ค่าที่เก็บอยู่บนเว็บจริง (ดึงจาก API เมื่อ 2026-08-22)

**เว็บเป็นแหล่งจริง ไฟล์นี้เป็นใบตอบ** — รายการนี้จึงไม่ได้มาจากการอ่านไฟล์นี้
แต่มาจากการดึงคำตอบที่เก็บอยู่จริงมาเทียบ:

```sh
curl -s https://www.bestpractices.dev/projects/14085.json > badge.json
```

สถานะ ณ วันที่ตรวจ: `badge_percentage_0` = 100 · `_1` = 100 (silver) · `_2` = **57**
(gold) · `updated_at` = 2026-08-22T00:39Z · `repo_url` ตรงกับของเรา

| ช่องบนเว็บ | ค่าที่เก็บอยู่จริงตอนนี้ | สถานะ |
|---|---|---|
| `license` | `AGPL-3.0-or-later` | **กรอกแล้ว** — ตรงกับ ADR 0070 |
| `homepage_url` | `https://github.com/sayam/flask-todolist` | **กรอกแล้ว** (ช่องเมทาดาทา) · แต่ *เกณฑ์* ชื่อเดียวกันยังเป็น `?` — การเติมช่องไม่ได้ตอบเกณฑ์ให้เอง |
| `version_unique_justification` · `version_tags_justification` | "v1.0.0 through v2.2.0" | **ตรงกับ tag จริง** |
| `maintained_justification` | "latest release v2.2.0 (2026-08-21)" | **ตรงกับรุ่นล่าสุด** |
| `release_notes_vulns_justification` | ชี้ v1.5.0 (CVE เจ็ดใบของ `cryptography`) | **คงไว้ถูกแล้ว** — v2.2.0 ไม่ได้แก้ CVE ของของที่ ship จริง (`util-linux` เป็นการ*รับไว้*) |
| `test_continuous_integration_justification` | "27 checks on every push" | ตรงกับ required check ปัจจุบัน (27 จาก 30) |
| `floss_license_osi_justification` | อ้าง ADR 0070 ที่แทน ADR 0038 | ถูกต้อง — บันทึกไว้กันเข้าใจผิดว่าเป็นของค้าง |
| `crypto_working_justification` · `crypto_weaknesses_justification` | อ้างเลขรุ่นของไลบรารี (1.4.1) | คงไว้ — เป็นเลขรุ่นของ dependency ไม่ใช่ของแอป |
| `description` | "… v2.2.0 … **109** machine-checked gates, 71 ADRs, **23** recorded governance audits …" | **ตรงแล้ว** (2026-08-22) — เทียบทั้งกับ About ของ repo (ตรงกันทุกตัวอักษร) และกับของบนดิสก์ (`gates.yaml` · `docs/adr/` · `AUDIT-LOG.md`) |

**ช่อง `description` เป็นสำเนาที่สามของตัวเลขชุดเดียวกัน** — อยู่ที่ About ของ repo
· ที่นี่ · และในไฟล์นี้ · **ไม่มีที่ไหนในสามที่นั้นที่เทสต์อ่านคู่ได้เลย** เพราะสองที่แรก
อยู่นอก repo · นี่คือเหตุผลที่ `docs/RELEASE.md` ข้อ 7 ต้องระบุทุกเลขพร้อมแหล่ง
ที่ต้องเทียบ แทนที่จะเขียนว่า "อัปเดต About"

**ตอน v2.2.0 ทั้งสามที่ค้างพร้อมกัน แล้วถูกไล่ปิดทีละที่ในสามรอบ** — About ก่อน
· ใบตอบนี้ · แล้วช่องบนเว็บเป็นที่สุดท้าย · แต่ละรอบผ่านไปโดยที่ "ก็อัปเดตแล้วนี่"
เป็นคำตอบที่จริงบางส่วนเสมอ **วิธีเดียวที่จบคือไล่เทียบทีละที่กับของบนดิสก์**
ไม่ใช่เทียบกับความจำว่าแก้ไปแล้วหรือยัง

### เกณฑ์ที่ยังไม่ Met (อ่านจาก API ตรง ๆ ไม่ใช่จากความจำ)

- **`?` (ยังไม่ตอบ)** — `small_tasks` (ตอนนี้ตอบได้แล้ว: issue #186 ติดป้าย
  `good first issue` และเปิดอยู่) · `build_reproducible` · `homepage_url` ·
  `report_url` · และชุด `OSPS-*` ทั้งหมดซึ่งเป็นกรอบคนละใบ
- **`Unmet` (ตัดสินแล้วว่าไม่ผ่าน)** — `bus_factor` · `contributors_unassociated`
  · `two_person_review` · `dco` · `copyright_per_file` · `license_per_file` ·
  `version_tags_signed` · เจ็ดข้อนี้เป็นผลของการเป็นโครงการคนเดียวโดยตรง
  ห้าข้อแรกแก้ด้วยการมีคนที่สองเท่านั้น

**กับดักของฟอร์มที่ยังใช้ได้อยู่**: บันทึกทีละแท็บ และดูว่า `updated_at`
ใน JSON ขยับจริงหลังกด Save — ถ้าไม่ขยับ แปลว่าไม่ได้บันทึก

## ทบทวน 2026-08-14 (หลังปิดเฟส 8–12)

ไล่ทั้ง 67 ข้อใหม่เทียบกับสภาพปัจจุบัน — **ไม่มีข้อไหนเปลี่ยนสถานะ** สิ่งที่
เปลี่ยนคือความหนักของหลักฐาน สามข้อ:

- `test_policy` / `tests_are_added` — กติกาเดิมเป็น "คนต้องจำ" ตอนนี้มี
  `gates.yaml` ที่บังคับให้ไฟล์เทสต์ทุกไฟล์ถูกตัดสินว่าเป็นของ gate ไหน
  ลืมแล้ว CI แดงทันที
- `contribution` — required check ขยับมาเรื่อย ๆ ตาม job ใหม่ (ปัจจุบัน 27 จาก 30 — `perf-smoke` เข้าเมื่อ ADR 0056 · `posture` ของ ADR 0061 ไม่รันบน PR จึงไม่บังคับ) (job `scaffold` เข้าเป็น
  ด่านบังคับตอนเฟส 9) และ `CONTRIBUTING.md` มีกติกา `gates.yaml` แล้ว
- `build_reproducible` / `installation_common` — ไม่เปลี่ยน แต่ `overlays/flask/`
  ทำให้มีของที่ *คนอื่น* ติดตั้งได้จริงเป็นครั้งแรก และ job `scaffold` พิสูจน์
  ทุก push ว่าติดตั้งลง repo เปล่าได้

~~ยังไม่ได้ทำ~~ **จบทั้งวงจรแล้ว (2026-08-16)**: โครงการ **#14085** —
<https://www.bestpractices.dev/projects/14085> · เจ้าของกรอกครบทุกเกณฑ์และ
badge ขึ้น **passing (100%)** — ยืนยันจาก API ว่าเป็น repo นี้จริง ·
ผลนี้ปิดข้อ A.5.35 (การทบทวนโดยอิสระ) ของ `ISO27001.md` ด้วย · บทเรียน
ตอนกรอก: เกณฑ์ที่หัวเขียน **(URL required)** ต้องมี `https://` อยู่ใน
justification ไม่งั้นค้างสถานะ "?" แม้ข้อความครบ
