# `pins/` — เครื่องมือที่ CI ติดตั้ง ถูกตรึงด้วย hash

ที่นี่เก็บ **ล็อกไฟล์ของเครื่องมือที่ CI ติดตั้งเอง** ไม่ใช่ dependency ของแอป
(ของแอปอยู่ใน `Pipfile.lock` ซึ่งมี hash ครบอยู่แล้ว และ `pipenv sync` ตรวจให้)

| ไดเรกทอรี | ใครใช้ | ติดตั้งเข้าไปไหน |
|---|---|---|
| `pip/` | job `security` | venv ของ pipenv (ก่อนรัน `pip-audit`) |
| `pipenv/` | ทุก job ที่รัน pytest/lint + `Dockerfile` ชั้น build | python ของ runner |
| `semgrep/` | job `security` | venv แยกของตัวเอง |
| `pa11y/` | job `a11y` | `pins/pa11y/node_modules/` |

## ทำไมต้องตรึง

`pip install pipenv` หยิบรุ่นล่าสุด ณ วินาทีที่ job รัน — สอง run ที่ห่างกัน
หนึ่งชั่วโมงจึงใช้เครื่องมือคนละตัวได้โดยไม่มีอะไรใน repo เปลี่ยน และเครื่องมือ
พวกนี้ **รันด้วยสิทธิ์ของ workflow เรา** อ่าน source อ่าน token ที่ job นั้นมี
การที่ใครยึดบัญชี PyPI ของ dependency ชั้นที่สามของ pipenv ได้ จึงเท่ากับยึด CI เรา

ตรึงด้วย **รุ่นอย่างเดียวไม่พอ** — ที่ต้องการคือ "ไฟล์ตัวเดิมไบต์ต่อไบต์"
`--require-hashes` ทำให้ pip ปฏิเสธทันทีถ้า **ตัวไหนก็ตามในต้นไม้** ไม่ตรง hash
และปฏิเสธด้วยถ้ามี dependency ตัวไหน *ไม่ได้ถูกระบุไว้* — ล็อกไฟล์ที่ครอบไม่ครบ
จึงกลายเป็น error ไม่ใช่ช่องโหว่เงียบ ๆ (หลักเดียวกับที่ action ถูก pin ด้วย SHA
และ base image ด้วย digest)

## ราคาที่จ่าย และวิธีที่จ่ายไปแล้ว

**pin โดยไม่มีใครขยับ = แช่ช่องโหว่ไว้ตลอดกาล** — ซึ่งแย่กว่าไม่ pin เลย
จึงเปิด Dependabot ให้ทุกไดเรกทอรีที่นี่ใน `.github/dependabot.yml`
patch จึงยังมาเหมือนเดิม **แค่มาเป็น PR ที่มีคนเห็นและผ่าน check ครบก่อน**

`tests/test_ci_pinning.py` บังคับว่า **สองอย่างนี้ต้องมาคู่กันเสมอ**:
เพิ่มไดเรกทอรีที่นี่แล้วลืมต่อ Dependabot ให้ = แดง

## แล้วใครตรวจว่าของที่ตรึงไว้มี CVE ไหม

`scripts/audit_pins.py` — รันในjob `security` ทุก push (และรันเองได้ด้วย
`pipenv run python scripts/audit_pins.py`) · **แดงได้เหมือน core**

`pins/accepted-advisories.txt` คือรายการที่ **ประเมินแล้วว่ารับไว้** ซึ่งจำเป็น
เพราะบางอย่างขยับไม่ได้ (`semgrep` pin `mcp` ไว้ตายตัว) — ด่านที่แดงตั้งแต่
วันแรกและแดงต่อไปเรื่อย ๆ คือด่านที่ถูกปิดเสียงภายในสองสัปดาห์

**สคริปต์ตรวจสองทิศ ไม่ใช่ทิศเดียว**:
- เจอ advisory ที่ไม่ได้อยู่ในรายการ → แดง (อันนี้ชัดเจน)
- **ID ในรายการที่ไม่โผล่ในผลอีกแล้ว → แดงเหมือนกัน** เพราะ `--ignore-vuln`
  เงียบเสมอเมื่อ ID นั้นหายไป รายการที่ไม่มีใครถอดจึงค่อย ๆ กลายเป็นรายการที่
  ปิดของจริงโดยไม่มีใครรู้ — มี fix มาแล้วต้องรู้ ไม่ใช่ยกเว้นต่อไปเงียบ ๆ

เหตุผลของแต่ละข้ออยู่ใน `docs/SECURITY-CADENCE.md` และ `tests/test_pins_audit.py`
บังคับว่าไฟล์กับเอกสารต้องตรงกันทั้งสองทิศเช่นกัน

**ฝั่ง npm ยังไม่มีด่านที่บล็อก** — pip-audit มองไม่เห็น `package-lock.json`
ตอนนี้พึ่ง Dependabot security updates ซึ่งเห็นผ่าน dependency graph อย่างเดียว

## สร้างใหม่ยังไง

ปกติไม่ต้องทำเอง — Dependabot ขยับให้ ทำเองเมื่อ **เพิ่มเครื่องมือใหม่**
หรือเมื่ออยากคุมรุ่นเอง · **ต้องรันจากรากของ repo** เพราะ path ที่ pip-compile
เขียนไว้ในหัวไฟล์เป็น path จากรากทั้งหมด

```sh
pipx run --spec pip-tools pip-compile --generate-hashes --allow-unsafe \
    --strip-extras --output-file pins/<ชื่อ>/requirements.txt pins/<ชื่อ>/requirements.in
```

```sh
cd pins/pa11y && npm install --package-lock-only    # ไม่ติดตั้งจริง แค่เขียน lock
```

`--allow-unsafe` จำเป็นเพราะ pip-tools ถือว่า `pip`/`setuptools` เป็นของที่
ไม่ควรตรึง (สมมติฐานของยุคที่ requirements ถูกติดตั้งทับ environment ของระบบ)
— ที่นี่ตรงกันข้าม ทุกอย่างลง venv ที่สร้างใหม่ ของที่ไม่ถูกตรึงคือของที่ไม่รู้ว่าคืออะไร

## ที่ไม่ได้อยู่ที่นี่

- **dependency ของแอป** → `Pipfile.lock` (มี hash อยู่แล้ว `pipenv sync` ตรวจให้)
- **GitHub Actions** → pin เป็น commit SHA ในไฟล์ workflow (`tests/test_workflow_pinning.py`)
- **base image ของ Docker** → pin เป็น digest ใน `Dockerfile` (`tests/test_dockerfile_pinning.py`)
- **service container ของ CI** (`redis:7`, `mysql:8`, `mariadb:11`) และ image ใน
  `compose*.yaml` → **ยังเป็น tag โดยตั้งใจ** มันคือของที่เรา *ทดสอบว่าเข้ากันได้*
  ไม่ใช่ของที่เรา *ส่งมอบ* — การตรึงไว้แปลว่าเราจะไม่มีวันรู้ว่า MySQL รุ่นถัดไป
  ทำให้เราพัง จนกว่าจะมีคนขยับเอง ซึ่งเป็นสิ่งที่ job `dialects` มีไว้เพื่อจับ
