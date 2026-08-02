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
| [0008](0008-tdl-table-prefix-and-naming.md) | prefix `tdl_` + naming convention | accepted — ทำจริง Phase 2 |
| [0009](0009-quality-gate-toolchain.md) | ชุดเครื่องมือ quality gate ของ Phase 0 | accepted |
| [0010](0010-csp-without-unsafe-inline.md) | CSP ไม่มี unsafe-inline, JS อยู่ไฟล์เดียว | accepted |
| [0011](0011-structured-json-logging.md) | log JSON + correlation ID ต่อ request | accepted |
| [0012](0012-accessibility-two-tier-gate.md) | a11y gate สองชั้น (โครงสร้าง + pa11y) | accepted |
| [0013](0013-schema-identity-tdl-prefix.md) | prefix `tdl_`, naming convention, typed models | accepted |
