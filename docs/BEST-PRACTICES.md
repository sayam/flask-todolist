# OpenSSF Best Practices Badge — passing 67 ข้อ + silver 55 ข้อ

ใบกรอกสำหรับ <https://www.bestpractices.dev> · **เว็บนั้นเป็นแหล่งจริงหลังส่งแล้ว**
ไฟล์นี้คือใบตอบที่เตรียมไว้ พร้อมหลักฐานว่าแต่ละข้อผ่านด้วยอะไร — เก็บไว้เพราะ
badge ถูกทบทวนเป็นรอบ และคำตอบที่ไม่มีที่มาคือคำตอบที่เขียนใหม่ทุกครั้ง
(หลักเดียวกับ [ASVS.md](ASVS.md))

> **เหลือช่องเดียวบนเว็บที่ยังค้าง** (`governance_justification` — 72 ADR ขณะที่
> ของจริงคือ 78) ดูหัวข้อ "ค่าที่เก็บอยู่บนเว็บจริง" (ตรวจกับ API แล้ว ไม่ใช่จากความจำ)

**สถานะ: badge อยู่ระดับ SILVER (100% · `achieved_silver_at`
2026-08-16T14:45Z — verify จาก API)**
— ระดับ passing: 66 ผ่าน · 1 ไม่เกี่ยวข้อง · ระดับ silver: 47 Met · 6 N/A ·
2 Unmet โดยตั้งใจ (ตาราง silver อยู่ท้ายไฟล์) · คำตอบในไฟล์นี้กับบนเว็บ
ตรงกันทั้งสองระดับ (รอบก่อนหน้า 2026-08-14/15 ดูหมายเหตุท้ายไฟล์)

## เปอร์เซ็นต์ที่เว็บตอบ — ตารางนี้มีเครื่องอ่านคู่

**อ่านสดจาก `https://www.bestpractices.dev/projects/14085.json` ทุกครั้งที่ job
`posture` รัน** (audit รอบ 27 ข้อ 3) · ก่อนหน้านี้ทั้งไฟล์พึ่งแถวทบทวนรอบ 12 เดือน
อย่างเดียว ซึ่งแปลว่าเลขที่ค้างจะค้างได้นานสุดหนึ่งปี — และตอนตั้งตารางนี้ก็พบว่า
บรรทัดสถานะข้างบนเขียน `gold เริ่มนับ 26%` อยู่จริง ขณะที่เว็บตอบ **57%** มาตั้งแต่
v2.1.0 · **นี่คือแถวสุดท้ายในทะเบียนผู้ให้บริการที่ยังไม่มีเครื่องอ่านคู่**

**เกณฑ์ของเขาเปลี่ยนได้โดยที่เราไม่ได้ทำอะไร** — คำตอบที่เคยผ่านกลายเป็นไม่ผ่าน
แล้ว badge ลดระดับเงียบ ๆ · ตารางนี้ทำให้การลดระดับนั้นเป็นความแดง ไม่ใช่ความเงียบ

| ชุด | ฟิลด์ใน API | เปอร์เซ็นต์ |
|---|---|---|
| passing | `badge_percentage_0` | 100% |
| silver | `badge_percentage_1` | 100% |
| gold | `badge_percentage_2` | 61% |
| baseline-1 | `badge_percentage_baseline_1` | 100% |
| baseline-2 | `badge_percentage_baseline_2` | 100% |
| baseline-3 | `badge_percentage_baseline_3` | 95% |

`OSPS-BR-01.02` ที่เว็บแสดงเป็น Unmet ถูก retire ตั้งแต่ v2026.02.19 จึงไม่นับใน
เปอร์เซ็นต์ของ baseline-3 (20/21 = 95.2%)

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

## ระดับ gold — ตอบครบแล้ว (ตรวจกับ API 2026-08-26)

เกณฑ์ gold มี 23 ข้อ · **ตอบครบทั้ง 23 แล้ว** (Met 17 · Unmet 6) · ไม่เหลือช่องว่าง
· ตัวเลขบนเว็บคือ **61%** (26% ตอนตั้งหัวข้อนี้ 2026-08-20 → 57% → 61%)

**gold ยังไปไม่ถึงแน่นอน** เพราะติดข้อที่โครงสร้างของโปรเจกต์เป็นตัวกำหนด
(คนเดียว) — แต่การตอบข้อที่ตอบได้ยังคุ้ม เพราะทะเบียนที่ว่างไว้แปลว่า
"ยังไม่ได้ดู" ซึ่งคนละเรื่องกับ "ดูแล้วยังไม่ผ่าน"

### ตอบ Met ได้ทันที — หลักฐานมีอยู่แล้ว

| เกณฑ์ | ชนิด | หลักฐานที่ใช้ตอบ |
|---|---|---|
| `test_statement_coverage90` | MUST | **วัดแล้ว 97.18%** (`fail_under = 97` ใน `pyproject.toml` เป็นพื้นที่ขยับขึ้นทางเดียว · job `test` บังคับทุก push) |
| `test_branch_coverage80` | MUST | **วัดแล้ว 93.98%** (1,062 จาก 1,130 สาขา · `[tool.coverage.run] branch = true`) |
| `code_review_standards` | MUST (ต้องมี URL) | `CONTRIBUTING.md` — PR-only, Conventional Commits, กติกา mutation test, การลงทะเบียนไฟล์เทสต์ใน `gates.yaml` · คำตัดสินอยู่ใน ADR 0053 |
| `security_review` | MUST | `docs/ASVS.md` (ประเมิน ASVS 5.0 L2 ครบ 253 ข้อ) · `docs/ISO27001.md` (116 ข้อ) · `docs/RISK-ASSESSMENT.md` · และรอบ audit 27 รอบที่มีทะเบียนใน [AUDIT-LOG.md](AUDIT-LOG.md) |
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

### เคยตอบไม่ได้จนกว่าจะมีของจริง — ตอบทั้งคู่แล้ว 2026-08-26

| เกณฑ์ | ชนิด | ต้องมีอะไรก่อน |
|---|---|---|
| `small_tasks` | MUST (ต้องมี URL) | **ตอบได้แล้ว** — issue [#186](https://github.com/sayam/flask-todolist/issues/186) เปิดอยู่และติดป้าย `good first issue` (ตอนเขียนแถวนี้ครั้งแรก repo มี 0 issue) · **ตอบ Met บนเว็บแล้ว 2026-08-26** |
| `build_reproducible` | MUST (ต้องมี URL) | ทุกอย่างถูกตรึงแล้ว (`Pipfile.lock` มี hash · `pins/` ใช้ `--require-hashes` · base image ตรึง digest) แต่ **ยังไม่เคยพิสูจน์ว่า build ซ้ำได้ผลไบต์ต่อไบต์** — ตอบ Met โดยไม่วัดคือสิ่งที่โปรเจกต์นี้ห้ามตัวเองมาตลอด · **ตอบ Unmet บนเว็บแล้ว 2026-08-26** พร้อมเหตุผลนี้ |

**ตอบไปแล้ว และผลออกมาตามที่ประเมินไว้** — gold ขยับจาก 26% เป็น **57%**
โดยไม่ได้แก้โค้ดอะไรเลย แล้วเป็น **61%** เมื่อ 26 ส.ค. ตอน `small_tasks`/
`build_reproducible` ถูกตอบ (และ `dco` ของ silver ขยับเป็น Met) · ที่เหลือเป็นรายการที่*ตัดสินแล้ว* ไม่ใช่รายการที่ยังไม่ได้ดู
(ดูรายการที่ยังไม่ Met ท้ายหัวข้อถัดไป)

## ค่าที่เก็บอยู่บนเว็บจริง (ดึงจาก API เมื่อ 2026-08-26)

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
| `homepage_url` | `https://github.com/sayam/flask-todolist` | **กรอกแล้ว** (ช่องเมทาดาทา) · **ไม่มี *เกณฑ์* ชื่อนี้ให้ตอบ** — `homepage_url_status` เป็นคอลัมน์ legacy ของเขาที่ค้างค่า `?` ไว้เฉย ๆ (ดูท้ายหัวข้อนี้) |
| `version_unique_justification` · `version_tags_justification` | "v1.0.0 through v2.2.0" | **ตรงกับ tag จริง** |
| `maintained_justification` | "latest release v2.2.0 (2026-08-21)" | **ตรงกับรุ่นล่าสุด** |
| `release_notes_vulns_justification` | ชี้ v1.5.0 (CVE เจ็ดใบของ `cryptography`) | **คงไว้ถูกแล้ว** — v2.2.0 ไม่ได้แก้ CVE ของของที่ ship จริง (`util-linux` เป็นการ*รับไว้*) |
| `test_continuous_integration_justification` | "27 checks on every push" | ตรงกับ required check ปัจจุบัน (27 จาก 30) |
| `floss_license_osi_justification` | อ้าง ADR 0070 ที่แทน ADR 0038 | ถูกต้อง — บันทึกไว้กันเข้าใจผิดว่าเป็นของค้าง |
| `crypto_working_justification` · `crypto_weaknesses_justification` | อ้างเลขรุ่นของไลบรารี (1.4.1) | คงไว้ — เป็นเลขรุ่นของ dependency ไม่ใช่ของแอป |
| `contribution_justification` | "…must pass **27** required status checks…" | **แก้แล้ว 2026-08-22 โดยเจ้าของ** — เดิมเขียน 26 ขณะที่ของจริงคือ 27 และช่องอื่นบนเว็บเดียวกัน (`contribution_requirements_justification` · `test_continuous_integration_justification` · `two_person_review_justification`) เขียน 27 ถูกแล้ว ทั้งสามช่อง — ใบเดียวกันขัดกันเองได้เพราะไม่มีอะไรอ่านคู่ |
| `governance_justification` | "…all decisions recorded as ADRs (**72** to date)…" | **ค้างอีกแล้ว** — ของจริงคือ **78** (`ls docs/adr/0*.md \| wc -l`) · เคยค้างที่ 58 แล้วแก้เป็น 72 เมื่อ 2026-08-22 · **ช่องนี้เป็นช่องเดียวที่ยังค้างอยู่บนเว็บ** (ยืนยัน 2026-08-26) |
| `test_most_justification` · `test_statement_coverage80_justification` | "Coverage gate fail_under = **97**" | **แก้แล้ว 2026-08-26 โดยเจ้าของ** — เดิมเขียน 96 ขณะที่ `pyproject.toml` เป็น 97 มาตั้งแต่ ratchet ขยับ · ตรงกับ `test_statement_coverage90_justification` บนเว็บเดียวกันแล้ว |
| `test_statement_coverage90_justification` · `test_branch_coverage80_justification` | 97.17% · 93.96% (1,058/1,126) | **ยังห่างของวันนี้เท่าเดิม** (97.18% · 93.98% — 1,062/1,130 · วัดซ้ำ 2026-08-26) · ช่องพวกนี้เขียนว่า "measured on the current tree" จึงเป็นภาพถ่าย ไม่ใช่คำสัญญา — แก้ตอนรอบ release ถัดไปพอ |
| `description` | "… v2.2.0 … **114** machine-checked gates, **78** ADRs, **27** recorded governance audits …" | **แก้แล้ว 2026-08-26 โดยเจ้าของ** — ตรงกับ `scripts/sync_counts.py --about` เป๊ะทั้งสามเลข · ก่อนหน้านั้นค้างที่ 112 gate · 72 ADR ขณะที่ช่อง About ของ repo ถูกซิงก์ไปแล้ว · เคย **ตรงกันสามที่ (2026-08-23)** — เว็บ badge · ช่อง About ของ repo · และของบนดิสก์ (`gates.yaml` · `docs/adr/` · [AUDIT-LOG.md](AUDIT-LOG.md)) — แล้วห่างอีกครั้งภายในสามวัน ซึ่งเป็นคำตอบของ audit รอบ 24 ที่ชัดที่สุด: ฝั่ง About มี `ci:posture` อ่านคู่ให้ตั้งแต่ ADR 0072 จึง*รู้ตัว* ส่วนฝั่งเว็บ badge ไม่มีใครอ่านคู่เลย |

**สี่แถวบนนี้เพิ่มตอน audit รอบ 24** — คำถามของรอบคือ *ใครเทียบของที่อยู่นอกรีโป
กับของจริง* และคำตอบสำหรับใบตอบ badge คือ **ไม่มีใคร นอกจากรอบตรวจ 12 เดือน** ·
ตัวเลขที่ค้างอยู่ไม่ได้ค้างเพราะใครประมาท แต่เพราะมันอยู่ในที่ที่ `git diff`
มองไม่เห็น: `26` กับ `27` นั่งอยู่บนหน้าเดียวกันคนละช่อง และ `58 ADRs` เขียน
ตอนที่มัน *เคย* เป็น 58 จริง ๆ · ผิวนอกรีโปทั้งกองอยู่ใน
[EXTERNAL-SURFACE.md](EXTERNAL-SURFACE.md) แล้ว (ADR 0072)

**ช่อง `description` เป็นสำเนาที่สามของตัวเลขชุดเดียวกัน** — อยู่ที่ About ของ repo
· ที่นี่ · และในไฟล์นี้ · **ไม่มีที่ไหนในสามที่นั้นที่เทสต์อ่านคู่ได้เลย** เพราะสองที่แรก
อยู่นอก repo · นี่คือเหตุผลที่ `docs/RELEASE.md` ข้อ 7 ต้องระบุทุกเลขพร้อมแหล่ง
ที่ต้องเทียบ แทนที่จะเขียนว่า "อัปเดต About"

**ตอน v2.2.0 ทั้งสามที่ค้างพร้อมกัน แล้วถูกไล่ปิดทีละที่ในสามรอบ** — About ก่อน
· ใบตอบนี้ · แล้วช่องบนเว็บเป็นที่สุดท้าย · แต่ละรอบผ่านไปโดยที่ "ก็อัปเดตแล้วนี่"
เป็นคำตอบที่จริงบางส่วนเสมอ **วิธีเดียวที่จบคือไล่เทียบทีละที่กับของบนดิสก์**
ไม่ใช่เทียบกับความจำว่าแก้ไปแล้วหรือยัง

### เกณฑ์ที่ยังไม่ Met (อ่านจาก API ตรง ๆ ไม่ใช่จากความจำ — 2026-08-26)

- **`?` (ยังไม่ตอบ)** — **ไม่เหลือแล้วในชุด metal** ทั้ง passing/silver/gold
  ตอบครบทุกข้อ · ที่ยังเป็น `?` มีแต่ชุด `OSPS-*` ซึ่งเป็นกรอบคนละใบ
- **`Unmet` (ตัดสินแล้วว่าไม่ผ่าน)** — silver: `bus_factor` · `version_tags_signed`
  · gold: `bus_factor` · `contributors_unassociated` · `two_person_review` ·
  `copyright_per_file` · `license_per_file` · `build_reproducible` ·
  ทุกข้อยกเว้นสองข้อสุดท้ายเป็นผลของการเป็นโครงการคนเดียวโดยตรง แก้ได้ด้วย
  การมีคนที่สองเท่านั้น (`dco` เคยอยู่ในรายการนี้ — ตอบ Met ไปแล้ว)

**`homepage_url` กับ `report_url` ไม่ใช่เกณฑ์ของระดับไหนเลย** — ทั้งคู่ **ไม่มีอยู่ใน
`criteria/criteria.yml`** ของ bestpractices.dev ทั้งสามระดับ และไม่มีในชุด baseline
· `db/schema.rb` ของเขากำกับคอลัมน์ไว้เองว่า *"legacy URL field, not the integer
enum; '?' = unknown/not evaluated"* · ค่า `?` ของสองฟิลด์นี้จึงไม่โผล่บนฟอร์มแท็บไหน
และไม่มีผลกับเปอร์เซ็นต์ใดเลย (passing ตอบ 100% อยู่ทั้งที่ทั้งคู่เป็น `?`) —
**ไฟล์นี้เคยนับมันเป็น "เกณฑ์ที่ยังไม่ตอบ" ซึ่งผิด** · วิธีตรวจ: ฟิลด์ `*_status`
ตัวไหนหาชื่อไม่เจอใน `criteria.yml` = ไม่ใช่เกณฑ์ ไม่ใช่ของค้าง

**กับดักของฟอร์มที่ยังใช้ได้อยู่**: บันทึกทีละแท็บ และดูว่า `updated_at`
ใน JSON ขยับจริงหลังกด Save — ถ้าไม่ขยับ แปลว่าไม่ได้บันทึก

## ชุด baseline — OSPS Baseline v2026.02.19 (**baseline-1 ได้แล้ว 2026-08-22**)

`bestpractices.dev` ออก badge **สองชุดจากโปรเจกต์เดียวกัน** (ID 14085) —
ชุด *metal* (passing → silver → gold) ที่ไฟล์นี้ตอบไว้ข้างบน และชุด
**baseline** (baseline-1 → 2 → 3) ซึ่งเป็น [OSPS Baseline](https://baseline.openssf.org/)
ชุดข้อ **MUST ล้วน** ที่ derive มาจากกรอบกฎหมาย/regulation · รูปของชุดนี้อยู่คนละ
URL: `https://www.bestpractices.dev/projects/14085/baseline`

**สถานะที่ดึงจาก API เมื่อ 2026-08-23**: `badge_percentage_baseline_1 = 100`
(`achieved_baseline_1_at = 2026-08-22T23:19Z`) · baseline-2 และ 3 ยังเป็น 0 ·
จำนวนข้อยืนยันจากไฟล์เกณฑ์ทางการ `criteria/baseline_criteria.yml` ของ
ossf/best-practices-badge: **L1 24 · L2 19 · L3 21 รวม 64** (หน้าสรุปบนเว็บเขียน
21/16/27 ซึ่งไม่ตรงกับไฟล์ที่ระบบใช้จริง)

ตารางข้างล่างคือ**คำตอบที่กรอกไปจริงทั้ง 24 ข้อ** พร้อมหลักฐานในรีโป ·
รูป badge อยู่บน `README.md` แล้วทั้งฉบับอังกฤษและไทย
(`https://www.bestpractices.dev/projects/14085/baseline`)

| เกณฑ์ | ตอบ | ข้อความที่วางลงฟอร์มได้เลย (อังกฤษ — ฟอร์มเป็นอังกฤษทั้งใบ) |
|---|---|---|
| `OSPS-AC-01.01` | Met | The sole maintainer's GitHub account requires 2FA with a passkey as the primary method (phishing-resistant), with TOTP and GitHub Mobile as backups; SMS is deliberately not enabled. Re-verified on a 12-month cadence recorded in docs/SECURITY-CADENCE.md. |
| `OSPS-AC-02.01` | Met | GitHub requires an explicit permission choice when a collaborator is invited, and the repository has a single collaborator (the maintainer). The collaborator count is a tracked row in docs/EXTERNAL-SURFACE.md. |
| `OSPS-AC-03.01` | Met | main accepts changes only through pull requests (ADR 0053) with enforce_admins enabled, so the maintainer cannot bypass it either. The posture CI job compares the live branch-protection settings against what the ADR declares on every push (ADR 0061). |
| `OSPS-AC-03.02` | Met | Branch protection sets allow_deletions=false and allow_force_pushes=false on main; both are verified against the GitHub API by the posture job on every push. |
| `OSPS-BR-01.01` | Met | No workflow interpolates untrusted text into a run block; every job declares its own permissions and the repository default is read-only. OpenSSF Scorecard scores Dangerous-Workflow 10/10 and Token-Permissions 10/10. |
| `OSPS-BR-01.03` | Met | Workflows triggered by fork pull requests receive no secrets, and workflow runs from first-time contributors require manual approval. Release signing uses keyless sigstore OIDC, so there is no long-lived credential for a pipeline to leak. |
| `OSPS-BR-03.01` | Met | Every official channel is HTTPS: the GitHub repository, GitHub Releases, and the DOI at doi.org. No http:// URL appears in project documentation. |
| `OSPS-BR-03.02` | Met | Releases are distributed through GitHub over TLS; every release asset is signed keyless with cosign/sigstore and carries SLSA build provenance that consumers can verify with gh attestation verify (ADR 0058). |
| `OSPS-BR-07.01` | Met | gitleaks runs on every push, GitHub secret scanning and push protection are enabled, .env is gitignored, and the application refuses to start unless SECRET_KEY is supplied at runtime — there is no default in the source. |
| `OSPS-DO-01.01` | Met | README.md documents installation, configuration and daily use in English and Thai; docs/OPERATIONS.md covers deployment and operations; docs/openapi.json, generated from the code, documents the HTTP API. |
| `OSPS-DO-02.01` | Met | CONTRIBUTING.md explains how to report defects, .github/ISSUE_TEMPLATE/bug_report.md provides the form, and SECURITY.md gives the private channel for security defects together with response deadlines. |
| `OSPS-GV-02.01` | Met | GitHub Issues is the public discussion channel — searchable, threaded and archived. Issues aimed at newcomers carry the good first issue and help wanted labels. |
| `OSPS-GV-03.01` | Met | CONTRIBUTING.md documents the contribution process end to end: pull-request-only flow, Conventional Commits with a 72-character subject limit, mutation testing for every new test, and registration of new test files in gates.yaml. |
| `OSPS-LE-02.01` | Met | The source code is licensed AGPL-3.0-or-later, an OSI-approved license (ADR 0070). |
| `OSPS-LE-02.02` | Met | Released assets are built from the same AGPL-3.0-or-later source, and the source archive attached to every tag contains the LICENSE file. |
| `OSPS-LE-03.01` | Met | LICENSE at the repository root holds the AGPL-3.0-or-later text and LICENSE-docs holds CC BY-SA 4.0 for documentation; tests/test_licensing.py fails if either drifts. |
| `OSPS-LE-03.02` | Met | The GitHub-generated source archive for every tag includes LICENSE, so the license travels with the released assets. |
| `OSPS-QA-01.01` | Met | The repository is public and served from a stable URL: https://github.com/sayam/flask-todolist |
| `OSPS-QA-01.02` | Met | The full git history is public on main with an author and timestamp for every commit; history is linear and never squashed (ADR 0053). |
| `OSPS-QA-02.01` | Met | Pipfile and Pipfile.lock pin every direct and transitive Python dependency by hash; CI tooling is pinned separately under pins/ with --require-hashes; an SBOM per dependency category is attached to every release. |
| `OSPS-QA-04.01` | N/A | The project is a single repository; there are no other codebases to list. |
| `OSPS-QA-05.01` | Met | No executable artifact is committed to version control. OpenSSF Scorecard scores Binary-Artifacts 10/10. |
| `OSPS-QA-05.02` | Met | The only binary files in version control are two compiled gettext catalogues (app/translations/{en,th}/LC_MESSAGES/messages.mo). Their reviewable source (.po) sits beside them and tests/test_i18n.py fails if the compiled output does not match, so the binaries cannot contain anything the reviewable source does not. |
| `OSPS-VM-02.01` | Met | SECURITY.md names the reporting channel (GitHub private vulnerability reporting, enabled) and commits to acknowledgement within 7 days, initial assessment within 14, and fixes within 7/30/90 days by severity. |

**ทั้ง 24 ข้ออยู่ในกลุ่มเดียวบนเว็บ** (`General → Controls`) เรียงตามลำดับนี้พอดี


## ชุด baseline — ระดับ baseline-2 (19 ข้อ · ผ่านครบบนดิสก์แล้ว · รอกรอกบนเว็บ)

จำนวนข้อมาจากไฟล์เกณฑ์ทางการ `criteria/baseline_criteria.yml` · อยู่กลุ่มเดียว
(`General → Controls`) เหมือน baseline-1 และเรียงตามลำดับนี้พอดี

**ผ่านครบทั้ง 19 ข้อแล้ว** — ข้อสุดท้ายที่ค้างคือ `OSPS-LE-01.01` (ผู้ส่งโค้ด
ต้องยืนยันสิทธิ์ตามกฎหมายในทุก commit) ปิดด้วย **DCO ตาม
[ADR 0073](adr/0073-dco-sign-off.md)** เมื่อ 2026-08-23 · ทุก commit ต่อจากนี้
ต้องมี `Signed-off-by` ซึ่ง hook `commit-msg` กับ job `commit-lint` บังคับทั้งสองที่

**ปิดทีเดียวได้สองที่** — เกณฑ์ `dco` ของชุด metal ระดับ **silver** เป็น `Unmet`
มาตั้งแต่ต้นด้วยเหตุผลเดียวกัน ตอนกรอกให้เปลี่ยนเป็น `Met` พร้อมข้อความนี้:

> Every commit must carry a Signed-off-by line (Developer Certificate of Origin
> 1.1), added by git commit -s. The commit-msg hook rejects an unsigned commit
> locally and the commit-lint CI job checks every commit a pull request adds,
> including pull requests from forks. ADR 0073 records the rule and the
> deliberate choice not to rewrite history that predates it.

| เกณฑ์ | ตอบ | ข้อความที่วางลงฟอร์มได้เลย (อังกฤษ) |
|---|---|---|
| `OSPS-AC-04.01` | Met | The repository default for GITHUB_TOKEN is read-only (default_workflow_permissions=read, and workflows cannot approve pull requests); every job additionally declares its own permissions block. OpenSSF Scorecard scores Token-Permissions 10/10. |
| `OSPS-BR-02.01` | Met | Every release carries a unique SemVer git tag (v1.0.0 through v2.2.0); the version is also asserted in app/__init__.py and a test fails if the tag, the code and CHANGELOG.md disagree. |
| `OSPS-BR-04.01` | Met | CHANGELOG.md follows Keep a Changelog with a section per release, and release notes repeat it. Releases that fix published CVEs name them explicitly — v1.5.0 lists all seven cryptography advisories. |
| `OSPS-BR-05.01` | Met | Dependencies are ingested with standard tooling only: pipenv with a hash-pinned Pipfile.lock for the application, pip --require-hashes for CI tools under pins/, and npm ci for the JavaScript tooling. A test fails the build if any workflow installs without hashes. |
| `OSPS-BR-06.01` | Met | Every asset attached to a release is signed keyless with cosign/sigstore — each SBOM ships with its .sigstore.json bundle — and the build carries SLSA provenance verified with gh attestation verify before the assets are published (ADR 0058). Note: GitHub's auto-generated source archives and the git tags themselves are not separately signed; ADR 0058 records that decision and the condition for revisiting it. |
| `OSPS-DO-06.01` | Met | docs/SUPPLY-CHAIN.md documents how dependencies are selected, obtained and tracked across every layer (application, CI tooling, container base image, service images), including the pinning rules and the two-way CVE registers. ADR 0025 documents how plugin dependencies are kept separable. |
| `OSPS-DO-07.01` | Met | README.md and CONTRIBUTING.md give the full build path: Python 3.13, pipenv sync --dev, the plugin dependency categories, and the single preflight command that runs what CI runs. docs/OPERATIONS.md covers container and compose builds. |
| `OSPS-GV-01.01` | Met | CONTRIBUTING.md section 'Who holds what' lists every member with access to sensitive resources: a single maintainer (@sayam) who is the only account with write access, administration rights and repository secrets. There are no teams or service accounts with write access. |
| `OSPS-GV-01.02` | Met | The same section describes the roles and their responsibilities, and ADR 0053 records the compensating controls that stand in for separation of duties in a single-maintainer project, together with the condition that ends the arrangement. |
| `OSPS-GV-03.02` | Met | CONTRIBUTING.md states what an acceptable contribution must satisfy: pull-request-only flow, Conventional Commits with a 72-character subject, ruff and mypy clean, mutation proof for every new test, registration of new test files in gates.yaml, and an ADR for any new decision. |
| `OSPS-LE-01.01` | Met | Every commit must carry a Signed-off-by line (Developer Certificate of Origin 1.1), added by git commit -s. The commit-msg hook rejects an unsigned commit on the contributor's machine and the commit-lint CI job checks every commit a pull request adds, including pull requests from forks. ADR 0073 records the decision, including the deliberate choice not to rewrite history that predates the rule. |
| `OSPS-QA-03.01` | Met | main is protected: 27 required status checks must pass before merge and enforce_admins is on, so the maintainer cannot bypass them either. The posture job compares the live settings with ADR 0053 on every push. |
| `OSPS-QA-06.01` | Met | Every pull request runs the full test suite (1,975 tests) plus the same suite against MySQL and MariaDB, an authenticated DAST scan, an accessibility scan and a real compose stack — 27 required checks in total. |
| `OSPS-SA-01.01` | Met | docs/ARCHITECTURE.md is an ISO/IEC 42010 style description: system context, stakeholders and their concerns, viewpoints and views, and correspondence rules between them. docs/DESIGN.md covers the user-facing side, and every decision links back to an ADR. |
| `OSPS-SA-02.01` | Met | docs/openapi.json describes the HTTP API and is generated from the code, with CI failing if it drifts. The CLI surface is documented in CONTRIBUTING.md and docs/OPERATIONS.md, and the plugin interfaces are specified in the ADRs they were introduced by. |
| `OSPS-SA-03.01` | Met | docs/RISK-ASSESSMENT.md holds a risk register with a documented likelihood x impact method and a machine-checked level formula. It sits alongside a full ASVS 5.0 L2 self-assessment (253 requirements) and an ISO/IEC 27001:2022 self-assessment (116 controls). |
| `OSPS-VM-01.01` | Met | SECURITY.md is a coordinated disclosure policy with explicit timeframes: acknowledgement within 7 days, initial assessment within 14, and fixes within 7/30/90 days by severity. A test fails CI when a scheduled security review is overdue. |
| `OSPS-VM-03.01` | Met | GitHub private vulnerability reporting is enabled and SECURITY.md points to it as the primary channel, giving the reporter a private thread with the maintainer. |
| `OSPS-VM-04.01` | Met | Fixed vulnerabilities are published in CHANGELOG.md and in the release notes, naming each advisory; accepted-but-unfixed advisories are published with their reasoning in pins/accepted-advisories.txt, app/plugins/accepted-advisories.txt and deploy/accepted-image-advisories.txt, all of which CI checks in both directions. |


## รูป badge บน README อ่านจาก API ไหน (2026-08-23)

**OpenSSF มี API สองโดเมนและให้คนละคำตอบ** — วัดเมื่อ 2026-08-23:

| แหล่ง | คะแนน | วันที่ของผล | Branch-Protection |
|---|---|---|---|
| `api.securityscorecards.dev` (เดิม) | 7.2 | 22 ส.ค. 14:15 | `-1` (อ่านไม่ได้) |
| `api.scorecard.dev` (ปัจจุบัน) | **6.9** | 23 ส.ค. | **3** |

รูปสำเร็จรูปของ shields (`/ossf-scorecard/...`) อ่านจากโดเมนเดิม ซึ่งค้างอยู่ที่ผล
ก่อนที่ `repo_token` จะทำให้ Scorecard อ่าน branch protection ได้ · README จึงใช้
รูปแบบ `dynamic/json` ที่ชี้ `api.scorecard.dev` ตรง ๆ แทน — **โฮสต์ของรูปยังเป็น
`img.shields.io` เหมือนเดิม** จึงไม่ต้องเพิ่มโฮสต์ใหม่ในรายการที่วัดผ่าน camo แล้ว

**คะแนนลดลงเพราะเราทำให้มันมองเห็นได้** ไม่ใช่เพราะถอยหลัง: `-1` แปลว่า *อ่านไม่ได้*
และถูกตัดออกจากการเฉลี่ย พอมองเห็นได้จริงมันเข้าสูตรที่ 3/10 — สามในสี่คำเตือน
ต้องมีผู้ดูแลคนที่สอง (ADR 0053) ส่วนข้อที่สี่ `up-to-date branches` ปิดไว้โดยตั้งใจ

## ชุด baseline — ระดับ baseline-3 (21 ข้อ · ตอบได้ 18 · ค้าง 3)

**ระดับนี้ยังไปไม่ถึงด้วยเหตุผลเชิงโครงสร้างหนึ่งข้อ** — `OSPS-QA-07.01` ต้องมี
**คนที่ไม่ใช่ผู้เขียนอนุมัติก่อน merge** ซึ่งเป็นไปไม่ได้กับโปรเจกต์ผู้ดูแลคนเดียว ·
[ADR 0053](adr/0053-solo-maintainer-sod-compensating-controls.md) บันทึกมาตรการ
ชดเชยและเงื่อนไขที่ทำให้ข้อนี้เปลี่ยนไว้แล้ว (วันที่มีผู้ร่วมพัฒนาประจำคนที่สอง)

อีกสองข้อเป็น **งานจริงที่ทำได้ ไม่ใช่ข้อจำกัด**:

- `OSPS-SA-03.02` — ยังไม่มี **threat model + attack surface analysis** ของเส้นทาง
  โค้ดสำคัญ (ทะเบียนความเสี่ยงกับ ASVS/ISO ที่มีอยู่เป็นคนละชนิดของงาน)
- `OSPS-VM-04.02` — เหตุผลของ CVE ที่ไม่กระทบเราอยู่ในทะเบียนร้อยแก้วที่ CI ตรวจ
  สองทิศแล้ว แต่**ยังไม่ได้ออกเป็น VEX** ที่เครื่องอ่านได้

ที่เหลือ 18 ข้อตอบได้ทั้งหมด (17 Met · 1 N/A) — ระหว่างเตรียมใบตอบนี้ได้ปิดช่องว่าง
เอกสารสี่ที่ไปด้วย: นโยบายความลับใน [OPERATIONS.md](OPERATIONS.md) · นโยบายทบทวน
ก่อนให้สิทธิ์ที่สูงขึ้นใน `CONTRIBUTING.md` · ตารางรุ่นที่รองรับใน `SECURITY.md`
(ค้างอยู่ที่ v1.x ทั้งที่รุ่นจริงคือ v2.2.0) · และประโยคที่บอกว่าเมื่อไหร่รุ่นหนึ่ง
หยุดได้รับ security update

| เกณฑ์ | ตอบ | ข้อความที่วางลงฟอร์มได้เลย (อังกฤษ) |
|---|---|---|
| `OSPS-AC-04.02` | Met | Every workflow job declares its own permissions block with only what that job needs (for example the scorecard job takes security-events: write and actions: read and nothing else); the repository default is read-only. OpenSSF Scorecard scores Token-Permissions 10/10. |
| `OSPS-BR-01.04` | Met | Untrusted or collaborator-supplied text is never interpolated into a shell command: values such as the pull request body are passed to a Python script through the environment (PR_BODY) rather than into the run block. OpenSSF Scorecard scores Dangerous-Workflow 10/10. |
| `OSPS-BR-02.02` | Met | Every asset is attached to the tagged release itself, which is the association to the release identifier, and each signature bundle is named after the asset it signs (sbom-core.json / sbom-core.json.sigstore.json). The SBOMs record the component versions they describe. |
| `OSPS-BR-07.02` | Met | docs/OPERATIONS.md has a secrets policy that covers all three layers (application runtime secrets behind SECRETS_URL, CI secrets in GitHub Actions, external service tokens), naming for each where it is stored, who can read it, and when it is rotated — with the rotation deadlines carried as rows in docs/SECURITY-CADENCE.md. Storage in version control is blocked by gitleaks on every push plus GitHub secret scanning with push protection. |
| `OSPS-DO-03.01` | Met | SECURITY.md, section 'Release artifacts are signed', gives the exact commands to verify a downloaded asset: cosign verify-blob against the sigstore bundle, and gh attestation verify for the SLSA build provenance. |
| `OSPS-DO-03.02` | Met | The same verification command pins the expected identity of the release process: --certificate-identity-regexp bound to this repository's release.yml workflow and --certificate-oidc-issuer bound to GitHub's OIDC issuer, so a signature made by any other workflow or account fails the check. |
| `OSPS-DO-04.01` | Met | SECURITY.md, section 'Supported versions', states the scope: main and the latest release are supported, earlier releases are superseded, and pre-1.0 releases promised nothing. |
| `OSPS-DO-05.01` | Met | The same section states when security updates stop: a release stops receiving them the moment a newer release exists. There is no long-term support branch; fixes land on main and go out in the next tag, and releases are never patched in place. |
| `OSPS-GV-04.01` | Met | CONTRIBUTING.md, section 'Who holds what', states that escalated access is reviewed before it is granted — the maintainer reviews the person's contribution history and confirms the identity behind the account, and the grant is recorded in that section so the list always names everyone who holds it. |
| `OSPS-QA-02.02` | Met | Every release carries an SBOM per dependency category (core plus one per installable plugin), generated in CI and attached to the release together with its signature. |
| `OSPS-QA-04.02` | N/A | The project is a single repository; there are no subprojects to hold to the same requirements. |
| `OSPS-QA-06.02` | Met | CONTRIBUTING.md documents when and how tests run: one preflight command reproduces CI's lint and test steps locally by reading the workflow itself, the commit hook covers formatting and typing, and every pull request runs 27 required checks including the full suite against three database engines. |
| `OSPS-QA-06.03` | Met | CONTRIBUTING.md rule 1 requires every new test to be proven by mutation before it counts, and diff-cover gates every pull request at 100% coverage of changed lines, so a change that adds behaviour without tests cannot merge. |
| `OSPS-QA-07.01` | Unmet | The project has a single maintainer, so no non-author human approval is possible; required approvals are set to 0. ADR 0053 records the compensating controls (pull-request-only main enforced against admins, 27 required checks, an append-only audit chain, a fully public history) and the condition that ends the arrangement: the day a second regular contributor arrives, required reviews turn on. |
| `OSPS-SA-03.02` | Met | docs/THREAT-MODEL.md is a threat model and attack surface analysis: scope and assumptions, the assets ranked by what their loss costs, actors and the trust boundaries each one cannot cross, an enumeration of every entry point with the threat considered and the control that stands in the way, and a deeper walk through the three paths that hurt most if they break (login to session, appending to the audit chain, loading a plugin). It ends with what is knowingly left unprotected and what the model cannot answer. It is bound to the code rather than left as prose: tests/test_threat_model.py fails if a route that needs no login is added without updating the model, if the model names a route that no longer exists, or if it cites a gate or an ADR that does not exist. |
| `OSPS-VM-04.02` | Met | docs/vex.openvex.json is an OpenVEX document generated from the same advisory registers that CI already checks in both directions (scripts/build_vex.py). Advisories that live in CI tooling are not_affected with justification component_not_present; advisories in the image's OS layer are reported as affected with the action being waited on, because claiming otherwise would be a lie the consumer's own scanner could catch. tests/test_vex.py enforces both directions between the registers and the document, the OpenVEX shape, and that nothing inside the image is claimed to be absent. SECURITY.md points readers to it. |
| `OSPS-VM-05.01` | Met | docs/SECURITY-CADENCE.md defines the remediation thresholds for SCA findings: critical within 7 days, high within 30, medium within 90, counted from the day the project becomes aware; an advisory without a score is treated as high until scored. Licence findings are gated separately by the licensing check, which fails on copyleft conflicts. |
| `OSPS-VM-05.02` | Met | A release cannot be cut while an SCA violation is open: the release path requires the same required checks as any change, and the dependency audits fail the build unless every finding is either fixed or recorded with its reasoning in the accepted-advisories registers, which are themselves checked in both directions. |
| `OSPS-VM-05.03` | Met | Every change is evaluated automatically: pip-audit for the application and for CI tooling, npm audit for the JavaScript tooling, trivy for the container image, and Dependabot for updates. All dependencies are hash-pinned (Pipfile.lock, pins/ with --require-hashes, npm ci), so a substituted or malicious artefact fails installation rather than being trusted. |
| `OSPS-VM-06.01` | Met | SAST findings follow the same documented thresholds as other vulnerabilities in docs/SECURITY-CADENCE.md (critical 7 / high 30 / medium 90 days from awareness), and every alert that stays open must carry its reasoning in .github/accepted-code-scanning-alerts.txt, which CI checks in both directions. |
| `OSPS-VM-06.02` | Met | Every change runs CodeQL (Python and JavaScript), semgrep with a proven scan scope, and gitleaks as required checks; a finding blocks the pull request unless it is declared with its reasoning in .github/accepted-code-scanning-alerts.txt, and a declaration that no longer matches a real alert fails the build too. |

**ที่ยังต้องทำด้วยมือ**: ล็อกอินที่ <https://www.bestpractices.dev/en/projects/14085>
แล้วสลับไปแท็บชุด baseline · กรอกตามตารางนี้ · ครบ 100% เมื่อไหร่ได้ badge
`baseline-1` แล้วค่อยเพิ่มรูปลง `README.md`

## ทบทวน 2026-08-14 (หลังปิดเฟส 8–12)

ไล่ทั้ง 67 ข้อใหม่เทียบกับสภาพปัจจุบัน — **ไม่มีข้อไหนเปลี่ยนสถานะ** สิ่งที่
เปลี่ยนคือความหนักของหลักฐาน สามข้อ:

- `test_policy` / `tests_are_added` — กติกาเดิมเป็น "คนต้องจำ" ตอนนี้มี
  `gates.yaml` ที่บังคับให้ไฟล์เทสต์ทุกไฟล์ถูกตัดสินว่าเป็นของ gate ไหน
  ลืมแล้ว CI แดงทันที
- `contribution` — required check ขยับมาเรื่อย ๆ ตาม job ใหม่ (ปัจจุบัน 27 จาก 30 — `perf-smoke` เข้าเมื่อ ADR 0056 · `posture` ของ ADR 0061 ไม่รันบน PR จึงไม่บังคับ) (job `scaffold` เข้าเป็น
  ด่านบังคับตอนเฟส 9) และ `CONTRIBUTING.md` มีกติกา `gates.yaml` แล้ว
- `build_reproducible` / `installation_common` — ไม่เปลี่ยน แต่ `verifiable-gates`
  ทำให้มีของที่ *คนอื่น* ติดตั้งได้จริงเป็นครั้งแรก และ job `scaffold` พิสูจน์
  ทุก push ว่าติดตั้งลง repo เปล่าได้

~~ยังไม่ได้ทำ~~ **จบทั้งวงจรแล้ว (2026-08-16)**: โครงการ **#14085** —
<https://www.bestpractices.dev/projects/14085> · เจ้าของกรอกครบทุกเกณฑ์และ
badge ขึ้น **passing (100%)** — ยืนยันจาก API ว่าเป็น repo นี้จริง ·
ผลนี้ปิดข้อ A.5.35 (การทบทวนโดยอิสระ) ของ `ISO27001.md` ด้วย · บทเรียน
ตอนกรอก: เกณฑ์ที่หัวเขียน **(URL required)** ต้องมี `https://` อยู่ใน
justification ไม่งั้นค้างสถานะ "?" แม้ข้อความครบ
