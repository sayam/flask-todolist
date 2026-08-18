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
| [0025](0025-plug-points-and-supply-chain-isolation.md) | จุด plug ซ้อนชั้น + แยก dependency ต่อ plugin | accepted |
| [0026](0026-db-backend-as-a-plugin.md) | DB backend เป็น plugin ชนิด `db`, migration เป็นของ core | accepted |
| [0027](0027-trusting-reverse-proxy-headers.md) | เชื่อ header ของ proxy ตามจำนวนชั้นที่ประกาศ | accepted |
| [0028](0028-oidc-as-a-primary-auth-factor.md) | OIDC เป็นปัจจัยหลัก ยืนยัน ID token ด้วย TLS | accepted |
| [0029](0029-credential-style-primary-factors.md) | ปัจจัยหลักมีสองรูปแบบ: redirect กับ credential | accepted |
| [0030](0030-secrets-come-from-a-declared-source.md) | ความลับมาจากแหล่งที่ประกาศด้วย scheme | accepted |
| [0031](0031-performance-targets-and-what-they-mean.md) | เป้าประสิทธิภาพเป็นตัวเลขที่มีที่มา | accepted |
| [0032](0032-serialising-audit-appends.md) | ต่อสาย audit ให้เป็นลำดับด้วยการล็อกแถวท้าย | accepted |
| [0033](0033-mfa-is-offered-not-required.md) | ไม่บังคับ MFA พร้อมเหตุผลและมาตรการชดเชย | accepted |
| [0034](0034-data-subject-rights.md) | เจ้าของข้อมูล export/ลบบัญชีตัวเองได้ | accepted |
| [0035](0035-audit-appends-queue-on-one-row.md) | ต่อคิวสาย audit ที่แถวเดียว ไม่ใช่ที่หางสาย | accepted — แทนที่ ADR 0032 ข้อ 1 |
| [0036](0036-read-committed-isolation.md) | อ่านแบบ READ COMMITTED บนยี่ห้อที่มี MVCC | accepted |
| [0037](0037-where-logs-go-and-what-shouts.md) | log ไปที่ Loki · กฎแจ้งเตือนอยู่ที่ ruler | accepted |
| [0038](0038-mit-license.md) | เผยแพร่ด้วย MIT · core ต้องไม่มีภาระ copyleft | accepted |
| [0039](0039-gates-registry-verified-two-way.md) | `gates.yaml` เป็นดัชนี enforcement ตรวจสองทิศ — ไม่ generate CI ไม่ทับ ASVS.md | accepted |
| [0040](0040-scaffolding-scope-cuts.md) | งาน scaffolding ตัดอะไรออกโดยตั้งใจ (CDC · cross-framework runtime · overlay อื่น) | accepted |
| [0041](0041-migration-class-per-plugin.md) | migration class ประกาศต่อ plugin (`live`/`warm`/`cold`) พร้อมเกณฑ์ตัวเลข — บังคับตอนโหลด | accepted |
| [0042](0042-three-layer-skill-model.md) | กฎทุกข้อประกาศชั้น baseline/business/internal — SKILL แยกสองใบ partition บังคับ | accepted |
| [0043](0043-feature-roadmap-scope-cuts.md) | แผน feature ตัดอะไรออกโดยตั้งใจ (A/B · maturity frameworks · in-process encryption · benchmark runner · fragment cache) | accepted |
| [0044](0044-admin-is-a-core-package-with-panels.md) | admin เป็น package ของ core ที่เสียบ panel ได้ — ไม่ใช่ plugin | accepted |
| [0045](0045-admin-data-masking-by-classification.md) | หน้า admin เห็นข้อมูลแบบ mask ตามชั้นข้อมูล · unmask ลง audit | accepted |
| [0046](0046-field-encryption-at-rest.md) | field-level encryption at rest — totp_secret ก่อน · คีย์แยกผ่าน secrets source · encrypt-on-use | accepted |
| [0047](0047-named-auth-profiles.md) | auth หลาย profile ต่อ plugin เดียว — ลำดับประกาศ · fallback เฉพาะ "ติดต่อไม่ได้" | accepted |
| [0048](0048-n-minus-one-compatibility.md) | สัญญา N-1 + วินัย expand–contract · readiness/liveness ไม่มี token · job `n-1` | accepted |
| [0049](0049-org-todo-graph-privacy-model.md) | privacy model ของ org graph — private ไม่เผยแม้การมีอยู่ · dependency เชิญ→ยอมรับ · impact จากของที่แชร์เท่านั้น | accepted |
| [0050](0050-agent-skill-package-export.md) | แพ็กเกจ agent skill (`skill/`) เป็นช่องทางแจกจ่ายที่สาม — generate ล้วน ห้ามเขียนคู่ขนาน | accepted |
| [0051](0051-project-constitution-and-intake.md) | ธรรมนูญ: ลำดับสี่ชั้น (security > perf > manageability > devx) · intake ของใหม่ · `pillar:` ทุก gate | accepted |
| [0052](0052-performance-layer-g5.md) | ชั้น performance (G5): multiproc `/metrics` แบบ opt-in ไม่ลดด่าน · caching วัดก่อน ไม่ชนะ=จดว่าไม่ทำ | accepted |
| [0053](0053-solo-maintainer-sod-compensating-controls.md) | main รับของทาง PR เท่านั้น (บังคับถึง admin) · มาตรการชดเชย SoD ของ solo maintainer + เงื่อนไขหมดอายุ | accepted |
| [0054](0054-image-os-layer-cve-scanning.md) | สแกน CVE ของ OS layer ใน image (trivy · HIGH/CRITICAL · เฉพาะมี fix) ตัดสินสองทิศเทียบรายการยกเว้น | accepted |
| [0055](0055-dockerfile-lint-hadolint.md) | lint Dockerfile ด้วย hadolint (ทุกระดับรวม info · ข้อยกเว้นมีเหตุผลที่ config เดียว) — IaC ชิ้นแรกที่ถูกสแกน | accepted |
| [0056](0056-perf-smoke-tripwire.md) | ด่านสะดุด performance ต่อ push — k6 journey เกณฑ์หลวม 2×เป้า บน runner (tripwire ไม่ใช่การวัด) | accepted |
| [0057](0057-gate-relayering-batch.md) | จัดชั้น gate ใหม่สองแบตช์ (7 ตัว + โน้ตรอบสามอีก 4): ชั้นตัดสินจากเนื้อกฎไม่ใช่เหตุที่เกิด — ปัจจุบัน 66/10/15 | accepted |
| [0058](0058-signed-releases-and-provenance.md) | เซ็น release แบบ keyless + SLSA provenance (native attestation ไม่ใช่ slsa-generator ที่บังคับ tag-pin) · SBOM generate ใน CI เท่านั้น | accepted |
| [0059](0059-gate-red-evidence.md) | ด่านต้องเก็บหลักฐานว่าเคยแดงตอนของเสียจริง (`proved_by`) — gate ใหม่มาพร้อมหลักฐาน · รายการที่ยังไม่มีหดทางเดียว | accepted |
| [0060](0060-preflight-mirrors-ci.md) | preflight บนเครื่องอ่านคำสั่งจาก workflow จริง ไม่ลอกมาเก็บที่สอง · ข้ามอะไรต้องบอกเหตุผล · ไม่ผูกเข้า hook | accepted |
| [0061](0061-platform-posture-verified.md) | ท่าทีฝั่งแพลตฟอร์ม (branch protection · required check · auto-merge · sha pinning) ถูกเครื่องตรวจ · อ่านไม่ได้ = แดง ไม่ใช่ข้าม | accepted |
| [0062](0062-expiry-for-gates-that-never-fired.md) | เกณฑ์ล่วงหน้าสำหรับด่านที่ยังไม่เคยจับอะไร — ไม่แดง 12 เดือน **และ** โค้ดที่คุ้มไม่ถูกแตะ = ย้ายไปรันตามรอบ (ไม่ใช่ถอด) | accepted |
| [0063](0063-overlay-ships-the-preflight-tool.md) | overlay ส่งออก*เครื่องมือ*ไม่ใช่แค่กฎ — preflight ตัวเดียวกับที่เราใช้เอง (เทียบไบต์) · เลิกผูกกับชื่อ job ของ repo นี้ | accepted |
| [0064](0064-who-broke-it-is-read-from-the-message.md) | "ของเราพัง vs โลกพัง" อ่านจากข้อความของความล้มเหลว ไม่ใช่ชื่อ step · สามคลาส (ที่จำแนกไม่ได้ต้องมีคนอ่าน) · ขั้นตอนก่อนกด rerun | accepted |
| [0065](0065-instruction-file-ceiling.md) | `CLAUDE.md` มีเพดานแบบ ratchet (บรรทัด+คำ) — เต็มแล้วย้ายเนื้อออก ไม่ใช่ขยับเพดาน · เพดานลอยเหนือของจริงไม่ได้ | accepted |
| [0066](0066-severity-must-match-real-authority.md) | `severity` ของ gate ต้องตรงกับอำนาจจริง (blocking ได้เฉพาะ job ที่รันบน PR) · ที่บล็อกไม่ได้ต้องประกาศ `watched_by` ว่าใครเห็นภายในกี่วัน | accepted |
| [0067](0067-every-job-declares-a-time-budget.md) | ทุก job ประกาศ `timeout-minutes` เอง — ค่าเริ่มต้น 6 ชม. ทำให้ "ค้าง" กับ "ช้า" แยกไม่ออก · เลขมาจากที่วัดได้ ไม่ใช่เลขกลม | accepted |
