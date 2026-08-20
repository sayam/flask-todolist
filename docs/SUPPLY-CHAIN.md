# แกน supply chain — ดัชนีของความเสี่ยงที่แยกเป็นอิสระ

G3 ของแผน governance ([ROADMAP-GOVERNANCE.md](ROADMAP-GOVERNANCE.md) ·
[ADR 0051](adr/0051-project-constitution-and-intake.md)) — ธรรมนูญประกาศให้
supply chain เป็น**แกนอิสระ**ของชั้น security: ความเสี่ยงจากของที่คนอื่น
เขียนต้องมองเห็นได้ในที่เดียว ไม่กระจายซ่อนอยู่ตามด่านย่อย

ไฟล์นี้เป็น**ดัชนี ไม่ใช่แหล่ง** (หลักเดียวกับ `gates.yaml`) — สมาชิกของแกน
ประกาศที่ gate ด้วย field `axis: supply-chain` และ `tests/test_supply_chain.py`
บังคับสองทิศ: ทุก gate ที่ติดธงต้องมีแถวที่นี่ และทุกแถวที่นี่ต้องเป็น gate
ที่ติดธงจริง — เพิ่มด่าน supply chain ใหม่แล้วไม่มาลงดัชนี = แดง

## ห้าชั้นของห่วงโซ่ และด่านที่คุมแต่ละชั้น

### 1. ของที่เข้ามาอยู่ในแอป (dependencies ของ runtime)

ของของ core อยู่ใน `Pipfile.lock` · ของของ plugin แยก category ต่อ plugin
(`ADR 0025`) — **ถอน plugin = supply chain ของมันหายไปด้วย** ไม่ค้างเป็น
ภาระตลอดกาล และสภาพ "ไม่มีไลบรารี" เป็นสถานะปกติที่วัดทุก push

| gate | คุมอะไร |
|---|---|
| `gate core-deps-cve-audit` | CVE ของ core — ถอดไม่ได้ = หยุด pipeline ได้ |
| `gate deploy-deps-cve-audit` | CVE ของหมวด deploy — server ที่รับคำขอจริง |
| `gate plugin-deps-cve-decided` | CVE ของ plugin ต้องถูกตัดสินแล้วทุกตัว — อัปเกรด · ถอดด้วย `DISABLED_PLUGINS` · หรือรับไว้พร้อมเหตุผลในทะเบียน (ADR 0025 โน้ต 1) |
| `gate bare-clone-still-green` | สภาพหลัง clone ไม่มีไลบรารี plugin ต้องเขียว — "ถอดได้จริง" วัดได้ |
| `gate licensing-no-copyleft` | เงื่อนไข license ของทุก dependency — ภาระทางกฎหมายก็คือ supply chain |

### 2. ของที่ CI ติดตั้งเอง (เครื่องมือ ไม่ใช่แอป)

`pins/` คือ lockfile ของเครื่องมือ — pipenv, pip, semgrep, pa11y-ci —
ทุกการติดตั้งต้อง `--require-hashes` และฝั่ง node ต้อง `npm ci`
(วิธี regenerate อยู่ใน `pins/README.md`)

| gate | คุมอะไร |
|---|---|
| `gate ci-tools-hash-pinned` | เครื่องมือทุกตัวตรึงด้วย hash ทั้ง python และ node |
| `gate ci-tools-cve-audit` | audit ของ `pins/` ครบสองภาษา (pip-audit + npm audit) |
| `gate pins-exceptions-honest` | ข้อยกเว้น advisory ตรวจ**สองทิศ** — ของที่ยกเว้นแล้วหายไปก็แดง เหตุผลอยู่ใน `docs/SECURITY-CADENCE.md` |

### 3. ของที่รันจริงใน production

| gate | คุมอะไร |
|---|---|
| `gate image-digest-pinned` | base image ตรึงด้วย digest ของ manifest index |
| `gate stack-images-pinned-and-moved` | image ของ stack ที่ CI ดึงมารัน (compose · service container · สคริปต์) ตรึงด้วย digest **และ** มี ecosystem `docker-compose` ของ Dependabot ขยับให้ — audit รอบ 15 |
| `gate actions-sha-pinned` | GitHub Action ทุกตัวตรึงด้วย commit SHA |
| `gate dockerfile-linted` | Dockerfile ผ่าน hadolint ทุกระดับรวม info (ADR 0055) — ข้อยกเว้นอยู่ที่ `.hadolint.yaml` ที่เดียวพร้อมเหตุผล |
| `gate image-os-cve-audit` | OS layer ของ image ถูกสแกน CVE (trivy ใน job `image` — ADR 0054) และตัดสินเทียบรายการยกเว้นสองทิศ |
| `gate release-signed-and-attested` | SBOM ของ release: generate ใน CI · เซ็น keyless (cosign bundle) · SLSA provenance (`gh attestation verify`) · verify สองทิศก่อนแนบ (ADR 0058) |
| `gate image-exceptions-honest` | ข้อยกเว้น CVE ของ image ตรวจ**สองทิศ** + ขอบเขตการสแกน (HIGH/CRITICAL · เฉพาะที่มี fix) ต้องยังประกาศอยู่ใน workflow |

### 4. ใครขยับ pin — pin ที่ไม่มีใครขยับคือการแช่ช่องโหว่

| gate | คุมอะไร |
|---|---|
| `gate dependabot-fits-the-gates` | Dependabot ครอบทุกไดเรกทอรีที่ pin และ prefix เข้ากับ commit-lint — เพิ่มไดเรกทอรี pin ใหม่ต้องต่อ Dependabot ด้วย ไม่งั้นแดง |

### 5. หลักฐานและท่าที (posture) ที่คนนอกตรวจได้

| gate | คุมอะไร |
|---|---|
| `gate sbom-per-category` | SBOM แยกต่อ category — ตอบได้ว่าถอด plugin แล้ว component ไหนหาย (แนบทุก release) |
| `gate push-secret-scan` | gitleaks ทุก push — ความลับหลุดเข้า git คือ supply chain ของคนที่ clone เรา |
| `gate openssf-scorecard` | Scorecard วัดแนวปฏิบัติของ repo และเผยแพร่ผล |
| `gate checkers-proven-two-way` | **ตัวตัดสินของแกนนี้ถูกตัดสินเอง** — สคริปต์ที่บอกว่าผ่าน/ไม่ผ่านมีเทสต์ planted violation + clean input (audit r4) · ตัวตัดสินที่ไม่มีใครทดสอบ ทำให้ด่านทั้งแกนกลายเป็นเขียวเปล่าได้ในคอมมิตเดียว |

### 6. ผู้ให้บริการภายนอกที่เราพึ่ง — และเราจะรู้เมื่อไหร่ถ้าเขาเปลี่ยนสัญญา

ห้าชั้นข้างบนตอบว่า *ของที่เราดึงเข้ามา* ถูกคุมอย่างไร · ชั้นนี้ตอบคนละคำถาม:
**เราพึ่งใครอยู่บ้าง และถ้าเขาเปลี่ยนกติกา เราจะรู้ตอนไหน** (audit รอบ 7) —
เพราะห่วงโซ่ไม่ได้ขาดเฉพาะตอนมีคนแทรกของ แต่ขาดตอนที่คนกลางเปลี่ยนสัญญาด้วย

**กติกาขั้นต่ำของทุกแถว**: (1) บอกว่าเราพึ่งอะไร (2) บอกว่า**อะไรจะแดง**ถ้าเขา
เปลี่ยน (3) ถ้าคำตอบคือ "ไม่มีอะไรแดง" ต้องมีแถวทวงใน `docs/SECURITY-CADENCE.md`
กำกับ — ความเสี่ยงที่ไม่มีทั้งด่านและตัวทวงคือความเสี่ยงที่เรายังไม่ได้ตัดสินใจ

| ผู้ให้บริการ | เราพึ่งอะไร | อะไรจะแดงถ้าเขาเปลี่ยน |
|---|---|---|
| GitHub — branch protection, auto-merge, Actions permissions | กติกาที่ ADR 0053 ประกาศ: PR-only, enforce_admins, required check ครบ | job `posture` (ADR 0061) เทียบ API กับที่ประกาศทุกครั้งที่กฎเปลี่ยน ทุก push บน main และกดรันเองได้ (`workflow_dispatch`) · อ่านด้วย secret `POSTURE_TOKEN` (PAT อ่านอย่างเดียว) · ฟิลด์ที่ token อ่านไม่ได้รายงานว่า **มองไม่เห็น ไม่ใช่ปิดอยู่** และมีแถว cadence ตรวจด้วยมือแทน |
| GitHub Actions — runner และ codeload (actions/checkout, actions/setup-python, actions/setup-node, actions/upload-artifact) | ทุก job ใน CI เริ่มด้วยการโหลด action จากที่นี่ | job นั้นแดงทันที — **ไม่จำเป็นต้องแดงที่ `Set up job`** (เกิดจริง 4 ครั้งวันที่ 2026-08-17/18: `codeql` แดงที่ step ของ action เอง โดยข้างในเป็น HTTP 503) · แยกออกจาก flake ของด่านเราด้วย `scripts/rerun_census.py` ซึ่งอ่าน**ข้อความ**ของความล้มเหลว ไม่ใช่ชื่อ step และส่งของที่จำแนกไม่ได้ไปชั้น `ต้องอ่านเอง` · ขั้นตอนตัดสินก่อนกด rerun อยู่ใน `docs/OPERATIONS.md` |
| GitHub — attestation API และ actions/attest-build-provenance | provenance ของ release ที่ผู้ใช้ verify ได้ | job `release-sign` แดงตอนออกรุ่น (verify สองทิศก่อนแนบ) |
| sigstore — Fulcio/Rekor และ sigstore/cosign-installer | ลายเซ็น keyless ของ SBOM ทุกไฟล์ | job `release-sign` แดงตอนออกรุ่น |
| เครื่องมือสแกนที่เป็น action — aquasecurity/trivy-action, github/codeql-action, gitleaks/gitleaks-action, hadolint/hadolint-action, ossf/scorecard-action, grafana/setup-k6-action | ด่าน image, SAST, secret scan, lint ของ Dockerfile, คะแนน posture, tripwire ของ performance | job `image`, `codeql`, `secret-scan`, `lint`, `scorecard`, `perf-smoke` แดง — และรุ่นที่ตัดสินคือรุ่นใน action ไม่ใช่รุ่นบนเครื่อง (ADR 0055) |
| Debian ผ่าน base image python:3.13-slim | ชั้น OS ของ image ที่ deploy จริง | `gate image-os-cve-audit` (trivy) + Dependabot ecosystem `docker` |
| PyPI และ npm | ไลบรารีทุกชั้น: core, deploy, plugin, เครื่องมือของ CI | `gate core-deps-cve-audit`, `gate ci-tools-cve-audit`, `gate plugin-deps-cve-decided` |
| Docker Hub และ quay.io — image ของ stack ที่ CI ยิงจริง (mysql, mariadb, redis, nginx, prom/prometheus, grafana/grafana, grafana/loki, grafana/alloy, hashicorp/vault, quay.io/keycloak/keycloak, bitnamilegacy/openldap) | stack จริงที่ job หลายตัวยิงใส่ทุก push (11 จาก 25 job) | **ความพร้อมใช้**: job แดงทันทีที่ดึง image ไม่ได้ · **ความสมบูรณ์และความทำซ้ำได้**: ตรึงด้วย digest ทุกตัวตั้งแต่ audit รอบ 15 (`gate stack-images-pinned-and-moved`) — ก่อนหน้านั้นเป็น tag ล้วน และ image ของ ZAP ซึ่งเป็น *ตัวตัดสิน* ผลด้านความปลอดภัย ใช้ tag ลอย (`stable`) ผลเขียวจึงทำซ้ำไม่ได้ |
| bestpractices.dev (OpenSSF Best Practices) | badge สามระดับที่ `README.md` โฆษณา และใบตอบใน `docs/BEST-PRACTICES.md` | **ไม่มีเครื่องตรวจ** — มีแถวทบทวนประจำปีใน `docs/SECURITY-CADENCE.md` (ทบทวนคำตอบทั้ง 122 ช่อง) |

**กรณีที่เกิดขึ้นจริงแล้วหนึ่งครั้ง**: Bitnami ย้าย image ที่เคยเปิดฟรีไป org
`bitnamilegacy` กลางปี 2025 — เรารู้เพราะ **job ที่ใช้มันล้มเหลว** ไม่ใช่เพราะมีใคร
ประกาศให้ฟัง · เหตุผลถูกบันทึกเป็นคอมเมนต์ไว้ที่ `compose.ldap.yaml` ตรงบรรทัด
ที่ใช้จริง ซึ่งเป็นที่ที่คนถัดไปจะอ่าน · บทเรียน: **สำหรับของที่ CI ดึงทุก push
"ของล้มเหลว" คือกลไกรับรู้ที่เร็วพอ** — ส่วนของที่ไม่มี job ไหนแตะ (เช่น badge)
ต้องมีตัวทวงตามรอบแทน

## กติกาของแกนที่ไม่ใช่ gate ตัวไหนตัวเดียว

- **เพิ่ม dependency = `pipenv install`** ห้าม `pip install` ตรง (lock ไม่ sync)
- **ไลบรารีของ plugin ห้ามอยู่ `[packages]` ของ core** — ประกาศใน manifest
  ของ plugin แล้วเข้า category ที่คำนวณจากคีย์ (`ADR 0025` — มีเทสต์บังคับ)
- **กรอบเวลาแก้ CVE**: critical 7 วัน · high 30 · medium 90 นับจากวันที่รู้
  (`docs/SECURITY-CADENCE.md` — เทสต์ทวงเมื่อเลยกำหนด)
- **วันที่ CVE ออกตอนบ่ายสาม**: ปิด plugin ที่โดนได้ทันทีด้วย DISABLED_PLUGINS
  โดยไม่ต้อง deploy (`ADR 0047` ปิดได้ถึงระดับ auth profile รายตัว)
- มาตรฐานภายนอกที่ตรึงใน repo (`docs/asvs-5.0.0.json` ·
  `docs/iso27001-2022-outline.json`) ก็เป็นของนำเข้า — จึงตรึงด้วย checksum
  แบบเดียวกับที่ pin โค้ด

## รอบทบทวน

สมาชิกของแกนทบทวนเมื่อเพิ่ม/ถอดด่าน supply chain (เทสต์บังคับให้มาแก้ไฟล์นี้
อยู่แล้ว) · เหตุผลของข้อยกเว้นรายตัวทบทวนตามรอบใน `docs/SECURITY-CADENCE.md`
· ความครบของแกนเทียบกับมาตรฐานดูที่ `docs/ISO27001.md` (ข้อ `A.5.19`–`A.5.23`)
