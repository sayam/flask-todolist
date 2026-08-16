# Crosswalk: gate ↔ ASVS

**ไฟล์นี้ generate มา ห้ามแก้ด้วยมือ** — สร้างใหม่ด้วย
`pipenv run python scripts/build_gates_crosswalk.py`
(`tests/test_gates.py` เทียบกับผล generate ทุกครั้งที่รันเทสต์)

derive จากหลักฐานในตาราง `docs/ASVS.md`: แถวที่อ้างไฟล์เทสต์หรือ `ci:job`
ถูก map กลับไปหา gate ผ่าน partition ของ `gates.yaml` — ไม่มีการเขียน mapping
มือ จึงไม่มีที่ที่สามให้ drift (ADR 0039)

สรุป: แถวที่ประเมินว่า "ผ่าน" 141 ข้อ · มี gate หนุน 119 · ผ่านด้วยเหตุผล/เอกสาร (ไม่มีด่านรัน) 22

## gate → ข้อ ASVS ที่หลักฐานของข้อนั้นชี้มาหา gate นี้

| gate | ข้อ ASVS |
|---|---|
| `alerts-fire-for-real` | V16.4.3 |
| `api-fuzzed-from-spec` | V1.3.3 · V1.4.2 · V2.2.1 · V8.2.2 · V15.3.3 · V16.5.1 |
| `app-behavior-suite` | V1.2.6 · V1.3.4 · V2.2.1 · V2.3.1 · V3.7.2 · V4.1.1 · V4.1.3 · V6.3.4 · V6.5.1 · V6.5.3 · V6.5.5 · V6.8.1 · V7.5.1 · V7.6.2 · V9.2.2 · V9.2.3 · V10.1.1 · V10.1.2 · V10.2.1 · V10.5.1 · V10.5.2 · V10.5.4 · V11.2.3 · V11.4.1 · V11.5.1 · V12.3.2 · V13.4.5 · V14.2.1 · V14.2.2 · V15.3.4 |
| `authz-in-service-layer` | V6.3.2 · V8.2.1 · V8.3.1 |
| `cadence-not-overdue` | V6.3.3 |
| `ci-tools-cve-audit` | V15.2.1 |
| `config-fails-loud` | V7.2.2 · V13.2.3 · V16.5.2 |
| `core-deps-cve-audit` | V15.2.1 |
| `core-never-names-plugins` | V1.3.2 · V5.3.2 |
| `csp-no-inline` | V1.2.1 · V1.2.3 · V3.2.1 · V3.2.2 · V3.3.2 · V3.3.4 · V3.4.1 · V3.4.2 · V3.4.3 · V3.4.4 · V3.4.5 · V3.4.6 · V3.7.1 · V6.2.7 · V14.2.3 · V15.3.6 |
| `csrf-guards-every-form` | V3.5.1 |
| `delete-means-soft-delete` | V1.1.2 · V1.2.4 · V2.3.3 |
| `deploy-deps-cve-audit` | V15.2.1 |
| `dockerfile-linted` | V15.3.5 |
| `every-column-classified` | V14.1.1 · V14.1.2 |
| `every-column-export-decided` | V5.4.1 · V5.4.2 · V7.4.2 |
| `every-write-audited` | V2.3.4 · V11.4.3 · V14.2.4 · V16.3.1 |
| `i18n-catalog-integrity` | V1.3.10 |
| `image-built-and-probed` | V13.4.1 · V15.2.3 |
| `image-os-cve-audit` | V13.4.1 · V15.2.3 |
| `logic-knows-no-http` | V2.2.2 · V2.2.3 · V2.3.3 · V8.2.3 · V8.3.1 · V16.5.3 |
| `login-rate-limited-two-ways` | V6.1.1 · V6.3.1 |
| `logs-carry-no-pii` | V1.2.9 · V14.2.4 · V16.2.1 · V16.2.2 · V16.2.4 · V16.2.5 · V16.3.4 · V16.4.1 |
| `password-policy-nist` | V6.2.1 · V6.2.2 · V6.2.3 · V6.2.4 · V6.2.5 · V6.2.8 · V6.2.9 · V6.2.12 · V6.4.3 · V11.4.2 |
| `plugin-deps-cve-visible` | V15.1.2 · V15.2.1 |
| `purge-timer-real-systemd` | V14.2.4 |
| `push-secret-scan` | V13.3.1 |
| `ropa-current` | V13.1.1 · V16.1.1 · V16.2.3 |
| `sbom-per-category` | V1.4.1 · V15.1.2 |
| `secrets-encrypted-at-rest` | V11.3.2 · V11.3.3 |
| `semgrep-sast` | V15.2.1 |
| `session-hardening` | V7.1.1 · V7.2.1 · V7.2.4 · V7.3.1 · V7.3.2 · V14.3.1 |
| `stack-deploys-and-serves` | V3.4.1 · V12.1.1 · V12.2.1 |
| `static-quality-battery` | V15.3.5 |
| `suite-on-three-brands` | V2.3.4 |
| `tls-forward-secrecy` | V3.4.1 · V12.1.1 · V12.2.1 |
| `tls-modern-protocols-only` | V3.4.1 · V12.1.1 · V12.2.1 |
| `vault-end-to-end` | V13.3.1 |
| `zap-authenticated-scan` | V3.3.2 · V3.3.4 · V3.4.1 · V3.4.3 · V3.4.4 · V3.4.6 · V3.5.1 · V13.4.3 · V14.2.1 · V16.5.1 |

## ข้อที่ผ่านด้วยเหตุผล/เอกสาร — ไม่มีด่านรันหนุน

ความเชื่อมั่นคนละระดับกับข้างบน: หลักฐานเป็น ADR/ไฟล์โค้ด/คำอธิบาย ซึ่งไม่ถูกรันซ้ำทุก push — รายการนี้คือที่ที่ควรมองหา gate ตัวถัดไป

V1.1.1 · V1.2.2 · V1.2.5 · V1.3.7 · V1.4.3 · V1.5.2 · V6.1.3 · V6.2.6 · V6.2.10 · V6.4.2 · V7.4.4 · V8.1.1 · V11.2.1 · V11.3.1 · V11.4.4 · V13.2.2 · V13.4.2 · V13.4.4 · V14.3.3 · V15.1.1 · V15.3.1 · V15.3.7
