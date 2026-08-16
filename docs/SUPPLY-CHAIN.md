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
| `gate plugin-deps-cve-visible` | CVE ของ plugin ดังพอให้เห็น (คำตอบคือถอด — ไม่บล็อก) |
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
