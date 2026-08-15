# OpenSSF Best Practices Badge — คำตอบของทั้ง 67 เกณฑ์ (ระดับ passing)

ใบกรอกสำหรับ <https://www.bestpractices.dev> · **เว็บนั้นเป็นแหล่งจริงหลังส่งแล้ว**
ไฟล์นี้คือใบตอบที่เตรียมไว้ พร้อมหลักฐานว่าแต่ละข้อผ่านด้วยอะไร — เก็บไว้เพราะ
badge ถูกทบทวนเป็นรอบ และคำตอบที่ไม่มีที่มาคือคำตอบที่เขียนใหม่ทุกครั้ง
(หลักเดียวกับ [ASVS.md](ASVS.md))

**สถานะ: 66 ผ่าน · 1 ไม่เกี่ยวข้อง · 0 ยังไม่ผ่าน** (ทบทวน 2026-08-15 หลัง
v1.2.0 ออก — ไม่มีข้อไหนเปลี่ยนสถานะ มีแต่หลักฐานที่หนักขึ้น: แถว version
ครอบสาม tag แล้ว · รอบก่อนหน้า 2026-08-14 ดูหมายเหตุท้ายไฟล์)

เกณฑ์ทั้งหมด 67 ข้อ: MUST 43 · SHOULD 10 · SUGGESTED 14
**MUST ผ่านครบทั้ง 43 ข้อ** ซึ่งเป็นเงื่อนไขของ badge ระดับ passing

---

## Basics

| เกณฑ์ | ตอบ | หลักฐาน |
|---|---|---|
| `description_good` MUST | ผ่าน | `README.md` ย่อหน้าแรกบอกว่าเป็นอะไรและแก้ปัญหาอะไร · **ต้องเติมช่อง About ของ repo ด้วย — ตอนนี้ว่าง** |
| `interact` MUST | ผ่าน | `README.md` มีวิธีติดตั้ง/รัน · `CONTRIBUTING.md` มีวิธีเสนอการเปลี่ยนแปลง · Issues เปิดอยู่ |
| `contribution` MUST | ผ่าน | `CONTRIBUTING.md` — อธิบายว่าใช้ PR, ต้องผ่าน 26 required check (จาก 27 check — scorecard ไม่บังคับ), merge ด้วย rebase, และกติกาลงทะเบียนไฟล์เทสต์ใน `gates.yaml` |
| `contribution_requirements` SHOULD | ผ่าน | `CONTRIBUTING.md` — Conventional Commits (หัว ≤72), ruff/mypy, **กติกา mutation test ของเทสต์ใหม่** |
| `floss_license` MUST | ผ่าน | `LICENSE` (MIT) · GitHub ตรวจพบเป็น `MIT` แล้ว |
| `floss_license_osi` SUGGESTED | ผ่าน | MIT เป็นสัญญาอนุญาตที่ OSI รับรอง — [ADR 0038](adr/0038-mit-license.md) |
| `license_location` MUST | ผ่าน | `LICENSE` ที่รากของ repo |
| `documentation_basics` MUST | ผ่าน | `README.md` + `docs/OPERATIONS.md` |
| `documentation_interface` MUST | ผ่าน | `docs/openapi.json` — **generate จากโค้ด** และ job `openapi` ใน CI เทียบว่าตรงกับโค้ดทุก push |
| `sites_https` MUST | ผ่าน | โฮสต์บน GitHub ทั้งหมด |
| `discussion` MUST | ผ่าน | GitHub Issues (ค้นได้ · เธรดได้ · เห็นได้โดยไม่ต้องล็อกอิน) |
| `english` SHOULD | ผ่าน | `README.md` สองภาษา **อังกฤษขึ้นก่อน** · ข้อความในโค้ดเป็นอังกฤษเสมอ (ภาษาไทยอยู่ในไฟล์คำแปล) |
| `maintained` MUST | ผ่าน | commit ล่าสุด 2026-08-15 · เจ้าของตอบ issue เอง |

## Change Control

| เกณฑ์ | ตอบ | หลักฐาน |
|---|---|---|
| `repo_public` MUST | ผ่าน | <https://github.com/sayam/flask-todolist> |
| `repo_track` MUST | ผ่าน | git |
| `repo_interim` MUST | ผ่าน | commit ระหว่างทางอยู่ครบบน `main` ไม่ใช่แค่ของที่ release |
| `repo_distributed` SUGGESTED | ผ่าน | git |
| `version_unique` MUST | ผ่าน | ทุกรุ่นมี tag ไม่ซ้ำ — `v1.0.0`, `v1.1.0`, `v1.2.0` |
| `version_semver` SUGGESTED | ผ่าน | SemVer · นิยามของ 1.0.0 บันทึกไว้ใน `docs/ROADMAP.md` |
| `version_tags` SUGGESTED | ผ่าน | git tag ทุกรุ่น (`v1.0.0`, `v1.1.0`, `v1.2.0`) |
| `release_notes` MUST | ผ่าน | `CHANGELOG.md` (Keep a Changelog) ผูกกับ `app.__version__` และมีเทสต์คุม |
| `release_notes_vulns` MUST | ผ่าน | ยังไม่มี release ไหนที่แก้ช่องโหว่ซึ่งมี CVE — เมื่อมีจะระบุใน `CHANGELOG.md` ตามกรอบเวลาใน `docs/SECURITY-CADENCE.md` |

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
| `test` MUST | ผ่าน | pytest — **1,239 เทสต์** (นับรอบทบทวน v1.2.0) |
| `test_invocation` SHOULD | ผ่าน | `pipenv run pytest` |
| `test_most` SUGGESTED | ผ่าน | coverage gate `fail_under = 96` (**ratchet: ขยับขึ้นได้อย่างเดียว**) + `diff-cover` บังคับบรรทัดที่แก้ 100% |
| `test_continuous_integration` SUGGESTED | ผ่าน | 27 check ทุก push — รวมสามยี่ห้อฐานข้อมูล, stack จริง, SSO, LDAP, DAST |
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
| `vulnerabilities_fixed_60_days` MUST | ผ่าน | ไม่มีช่องโหว่ค้างใน**ซอฟต์แวร์ที่โครงการผลิต** · 4 advisory ที่ค้างอยู่เป็นของ**เครื่องมือ CI** (`pins/`) ซึ่งไม่อยู่ใน image ที่ deploy — ประเมินและบันทึกไว้ใน `docs/SECURITY-CADENCE.md` พร้อมเงื่อนไขที่ทำให้คำตัดสินหมดอายุ |
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
"ยอมรับชุดชื่อ 0000" แล้วรายงานว่าการแก้ทำ TLS 1.3 พัง ทั้งที่ TLS 1.3 ปกติดี
· **ด่านที่วัดผิดตัวสร้างสัญญาณเตือนลวงได้ ไม่ใช่แค่เงียบตอนควรดัง**
ตัวจริงคือ exit code ของ openssl กับบรรทัดสรุป `New, TLSvX, Cipher is Y`

## ที่ต้องทำก่อนกด submit

1. **เติมช่อง About ของ repo** — ตอนนี้ว่าง (`description: null`) ขณะที่เกณฑ์
   `description_good` และ `interact` พูดถึง "project website" ซึ่งสำหรับที่นี่
   คือหน้า repo · ข้อเสนอ:
   > Flask todolist with a plugin architecture, an audited append-only trail, and CI that proves its own gates.
2. ล็อกอินที่ <https://www.bestpractices.dev> ด้วย GitHub แล้วกด **Add project**
   ใส่ URL ของ repo — ระบบจะเติมข้อที่ตรวจอัตโนมัติได้ให้เอง (license, repo, HTTPS)
3. กรอกที่เหลือจากตารางข้างบน · 8 ข้อที่ต้องแนบ URL คือ `contribution`,
   `contribution_requirements`, `license_location`, `vulnerability_report_process`
   และข้ออื่นที่ระบบขอ — ใช้ลิงก์ตรงไปยังไฟล์บน `main`
4. ได้เลขโครงการมาแล้วเติม badge ลง `README.md`

---

## ทบทวน 2026-08-14 (หลังปิดเฟส 8–12)

ไล่ทั้ง 67 ข้อใหม่เทียบกับสภาพปัจจุบัน — **ไม่มีข้อไหนเปลี่ยนสถานะ** สิ่งที่
เปลี่ยนคือความหนักของหลักฐาน สามข้อ:

- `test_policy` / `tests_are_added` — กติกาเดิมเป็น "คนต้องจำ" ตอนนี้มี
  `gates.yaml` ที่บังคับให้ไฟล์เทสต์ทุกไฟล์ถูกตัดสินว่าเป็นของ gate ไหน
  ลืมแล้ว CI แดงทันที
- `contribution` — required check ขยับมาเรื่อย ๆ ตาม job ใหม่ (ปัจจุบัน 26) (job `scaffold` เข้าเป็น
  ด่านบังคับตอนเฟส 9) และ `CONTRIBUTING.md` มีกติกา `gates.yaml` แล้ว
- `build_reproducible` / `installation_common` — ไม่เปลี่ยน แต่ `overlays/flask/`
  ทำให้มีของที่ *คนอื่น* ติดตั้งได้จริงเป็นครั้งแรก และ job `scaffold` พิสูจน์
  ทุก push ว่าติดตั้งลง repo เปล่าได้

~~ยังไม่ได้ทำ~~ **ทำครบแล้ว (2026-08-15)**: สมัครเป็นโครงการ
**#14085** — <https://www.bestpractices.dev/projects/14085> · badge อยู่ใน
`README.md` ทั้งสองภาษาแล้ว · ช่อง About ของ repo เติมแล้ว (ข้อ
`description_good` ชี้ได้จริง) — **งานที่เหลือ**: ทยอยกรอกคำตอบจากตารางข้างบน
ลงฟอร์ม (ตอนสมัครระบบเติมอัตโนมัติให้ ~19% — หน้าแก้ไข: กด "Show only
incomplete criteria" แล้ววางคำตอบจากตารางนี้ทีละหมวด)
