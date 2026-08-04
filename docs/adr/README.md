# Architecture Decision Records

การตัดสินใจสำคัญทุกครั้งบันทึกที่นี่ — ไฟล์ละหนึ่งเรื่อง เรียงเลขไม่ reuse
รูปแบบ: บริบท → ทางเลือก → คำตัดสิน → ผลที่ตามมา (MADR อย่างย่อ)
ADR 0002–0008 เป็นการ backfill การตัดสินใจที่เกิดก่อนเริ่มจด (Phase 0)

| # | เรื่อง | สถานะ |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | ใช้ ADR บันทึกการตัดสินใจ | accepted |
| [0002](0002-utc-naive-datetime-storage.md) | เก็บเวลาเป็น naive UTC ทั้งระบบ | accepted |
| [0003](0003-english-msgid-for-i18n.md) | msgid เป็นภาษาอังกฤษ ไทยอยู่ใน catalog | accepted |
| [0004](0004-ownership-404-not-403.md) | ข้อมูลของคนอื่นตอบ 404 ไม่ใช่ 403 | accepted |
| [0005](0005-csrf-before-login-required.md) | ยอมรับลำดับ CSRF ตัดก่อน login_required | accepted |
| [0006](0006-moodle-style-plugin-architecture.md) | สถาปัตยกรรม plugin แบบ Moodle | accepted |
| [0007](0007-embedded-sun-table.md) | ตารางดวงอาทิตย์ฝังในแอป ไม่เรียก API | accepted |
| [0008](0008-tdl-table-prefix-and-naming.md) | prefix `tdl_` + naming convention | accepted — ทำแล้วใน ADR 0013 |
| [0009](0009-quality-gate-toolchain.md) | ชุดเครื่องมือ quality gate ของ Phase 0 | accepted |
| [0010](0010-csp-without-unsafe-inline.md) | CSP ไม่มี unsafe-inline, JS อยู่ไฟล์เดียว | accepted |
| [0011](0011-structured-json-logging.md) | log JSON + correlation ID ต่อ request | accepted |
| [0012](0012-accessibility-two-tier-gate.md) | a11y gate สองชั้น (โครงสร้าง + pa11y) | accepted |
| [0013](0013-schema-identity-tdl-prefix.md) | prefix `tdl_`, naming convention, typed models | accepted |
| [0014](0014-pdpa-vs-audit-retention.md) | PDPA vs audit: ไม่เขียน PII ลง audit ตั้งแต่แรก | accepted |
| [0015](0015-audit-trail-design.md) | audit trail: ดักที่ ORM, hash chain, checkpoint ตอน purge | accepted |
| [0016](0016-service-layer-boundary.md) | service layer ไม่รู้จัก HTTP, route เป็น adapter | accepted |
| [0017](0017-personal-access-tokens.md) | PAT แยกจาก session cookie, sha256 ไม่ใช่ scrypt | accepted |
| [0018](0018-api-v1-contract-and-versioning.md) | API v1: spec generate จากโค้ด, เวอร์ชันที่ path | accepted |
| [0019](0019-password-policy-nist-800-63b.md) | นโยบายรหัสผ่านตาม NIST 800-63B + blocklist offline | accepted |
| [0020](0020-session-lifetime-and-binding.md) | อายุ session บังคับที่ server + ผูกกับเครื่องและ credential | accepted |
| [0021](0021-per-username-login-throttle.md) | โควตา login ต่อชื่อผู้ใช้ (กันคนเปลี่ยน IP) | accepted |
| [0022](0022-minimal-rbac.md) | RBAC ขั้นต่ำ admin/user ตรวจที่ service | accepted |
| [0023](0023-plugin-owns-its-own-table.md) | plugin ดูแลตารางของตัวเอง นอกสาย migration ของ core | accepted |
| [0024](0024-mfa-as-an-auth-plugin.md) | MFA เป็น plugin ชนิด auth, TOTP เขียนเอง | accepted |
