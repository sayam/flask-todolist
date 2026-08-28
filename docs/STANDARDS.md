# Standards & Tooling — งานวิเคราะห์ความเป็นไปได้

> ตอบคำถาม 3 ข้อ: (1) database มี guideline อะไรให้ follow, (2) Python มี
> programming guideline อะไร, (3) Flask มีเครื่องมือแบบ PHPStan ของ Laravel ไหม
> จุดยืนของโปรเจกต์: **ความเป็นไปได้ที่เพิ่มความน่าเชื่อถือมาก่อนความพอดี** —
> รายการนี้จึงจัดเต็มแล้วค่อยคัดออกทีหลัง verdict อยู่ท้ายเอกสาร (ข้อ 4)
>
> วันที่สำรวจ: 2026-08 ณ commit `cf15794` · **ทบทวนล่าสุด 2026-08-15 หลังปิด
> เฟส 13–18** — คำตัดสินเดิมไม่มีข้อไหนถูกกลับ มีแต่ของเพิ่มและของที่ตัดออก
> อย่างเปิดเผย (ดูท้ายข้อ 4)

---

## 1. Database

### 1.1 Table prefix (แบบ `wp_` ของ WordPress / `mdl_` ของ Moodle)

**ที่มาของธรรมเนียมนี้:** ยุค shared hosting ที่หลายแอปใช้ database เดียวร่วมกัน
และ MySQL ไม่มี schema แยกภายใน database — prefix คือ namespace เดียวที่มี
สำหรับแอปสมัยใหม่ที่มี database ของตัวเอง โดยทั่วไปถือว่า**ไม่จำเป็นแล้ว**

**แต่โปรเจกต์นี้มีเหตุผลเฉพาะ 3 ข้อที่ทำให้ควรใช้:**

1. **Plugin architecture (ทิศทางหลักของแอป)** — plugin ที่ดูแล table ตัวเอง
   ต้องมี namespace กันชนกับ core และกันเอง นี่คือเหตุผลเดียวกับที่ Moodle
   ยังใช้ `mdl_<component>_*` จนวันนี้
2. **Multi-DB (ROADMAP ข้อ 4)** — Postgres มี schema, Oracle ผูก schema กับ user,
   MySQL ไม่มี schema ใน database — prefix เป็นกลไก namespace เดียวที่ทำงาน
   เหมือนกันทุกยี่ห้อ
3. **ฆ่า landmine reserved word ที่สแกนพบแล้ว** — ตาราง `user` เป็น reserved ใน
   PostgreSQL/Oracle/MSSQL แต่ `tdl_user` ไม่ reserved ที่ไหนเลย
   การเปลี่ยนชื่อครั้งเดียวลบปัญหาทั้งชั้นทิ้งถาวร ดีกว่าจำกติกา quote ไปตลอด

**ข้อเสนอ:**
- core: `tdl_` (สั้น, เป็นเอกลักษณ์) → `tdl_user`, `tdl_category`, `tdl_todo`
- plugin: `tdl_<ชนิด>_<ไอดี>_*` เช่น MFA plugin → `tdl_auth_totp_secret`
  (บังคับใน plugin contract — core ตรวจได้ด้วย prefix ว่า table ไหนเป็นของใคร)
  **ทำจริงแล้วใน Phase 4 (ADR 0023)** — registry บังคับ prefix ตอนโหลด และตาราง
  ของ plugin ถูกกันออกจากสาย migration ของ core
- ตาราง version ของ alembic เปลี่ยนเป็น `tdl_alembic_version` (ตั้งได้ผ่าน
  `version_table` ใน env.py)
- **จังหวะ: ด่านแรกของ Phase 2** — ก่อนตาราง audit/temporal เกิด ทุกตารางใหม่
  หลังจากนั้นเกิดมาพร้อม prefix เลย ยิ่งช้าตารางยิ่งเยอะ

### 1.2 SQLAlchemy `naming_convention` — ตัวจริงของงาน schema portability

ปัญหาที่มีอยู่: constraint/index ที่ไม่ได้ตั้งชื่อ จะได้ชื่อ auto ที่ต่างกันตาม
ยี่ห้อ DB → alembic drop/alter constraint ข้ามยี่ห้อไม่ได้ (โดยเฉพาะ MySQL)
ตอนนี้เรามี named constraint แค่ตัวเดียว (`uq_category_user_name`) ที่เหลือ auto

มาตรฐานที่ SQLAlchemy แนะนำเอง — ประกาศครั้งเดียวที่ `MetaData`:

```python
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
```

**จังหวะ: migration เดียวกับ rename prefix (Phase 2 ด่านแรก)** — จ่ายค่า
batch-recreate ของ SQLite ครั้งเดียวจบทั้งสองเรื่อง

### 1.3 กติกาตั้งชื่อ (ประกาศสิ่งที่ทำอยู่แล้วให้เป็นลายลักษณ์อักษร)

| กติกา | สถานะปัจจุบัน |
|---|---|
| snake_case ทุกชื่อ | ✓ ทำอยู่แล้ว |
| ชื่อตาราง**เอกพจน์** (`todo` ไม่ใช่ `todos`) | ✓ สม่ำเสมอแล้ว — เลือกฝั่งนี้เป็นกติกา |
| FK ชื่อ `<entity>_id` | ✓ |
| timestamp ชื่อ `created_at`/`updated_at`/`*_at` | ✓ |
| boolean ขึ้นต้น `is_`/`has_` | ✗ มี `done` หนึ่งตัว — เปลี่ยนเป็น `is_done` ในรอบ rename เดียวกัน |
| ห้าม reserved word | จะหมดปัญหาเมื่อใส่ prefix |

อ้างอิงระดับ enterprise: ISO/IEC 11179 (metadata registries — naming and
identification) ใช้เป็นหลักคิด ไม่ต้อง comply เต็มรูปแบบสำหรับแอปขนาดนี้

### 1.4 SQL style

- **sqlfluff** — linter/formatter ของ SQL (รองรับหลาย dialect) — โปรเจกต์นี้มี
  raw SQL เฉพาะใน migration ไม่กี่จุด มูลค่าต่ำวันนี้แต่จะสูงขึ้นเมื่อมี
  migration ที่ซับซ้อนใน Phase 2 → ใส่ไว้เป็น optional check

---

## 2. Python

### 2.1 มาตรฐานทางการ (PEP ที่ยึด)

- **PEP 8** style / **PEP 257** docstring / **PEP 484 + 561** type hints /
  **PEP 621** pyproject metadata — ทั้งหมด enforce ผ่านเครื่องมือ ไม่ใช่อ่านเอง

### 2.2 คำตอบของ "PHPStan ของเราคืออะไร"

Laravel มี PHPStan/Larastan ตัวเดียวจบ ฝั่ง Python **แยกเป็นสองแกนที่ต้องใช้คู่กัน**:

**แกน lint/style/security-pattern → Ruff** (ตัวเดียวแทน flake8 + isort + pyupgrade
+ pep8-naming + bugbear + bandit-rules(S) + mccabe(C901) + pydocstyle(D) + อีก ~50 ชุด)
- จุดยืนจัดเต็ม: `select = ["ALL"]` แล้ว ignore รายข้อพร้อมเหตุผลใน pyproject —
  กลับด้านจากวิธีปกติ (เลือกเปิดทีละชุด) เพื่อให้ "ของที่ปิด" ต้อง justify ตัวเอง
- `ruff format` แทน black (compatible กัน)

**แกน type checking → นี่คือตัวที่เทียบชั้น PHPStan levels จริง**
- **mypy `--strict`** เป็น CI gate (ไล่ระดับต่อ module — โค้ดปัจจุบัน**ไม่มี
  type annotation เลยสักบรรทัด** จึงต้อง retrofit แบบ gradual: ตั้ง per-module
  override แล้วขยาย allowlist จนครบ ห้าม module ใหม่หลุด strict)
- **Pyright/basedpyright** ใน editor (เร็วกว่า, strict กว่าในบางเรื่อง) —
  ใช้คู่ได้ ไม่ขัดกัน
- **ตัวปลดล็อคสำคัญ: เขียน model เป็น SQLAlchemy 2.0 typed style**
  (`Mapped[int] = mapped_column(...)`) — ตอนนี้ใช้ legacy `db.Column` ซึ่ง type
  checker มองไม่ทะลุ การ rewrite เป็นงาน mechanical แต่ได้ type safety ของ
  query ทั้งระบบ → ทำคู่กับรอบ rename ใน Phase 2
- **ty (Astral) / pyrefly (Meta):** จากการสำรวจ ณ ส.ค. 2026 — ty อยู่ในสถานะ
  beta (conformance ~15%, ตั้งเป้า stable ปลาย 2026), pyrefly ~58% —
  **ยังไม่เหมาะเป็น gate ทั้งคู่ → watch list** รอ stable ค่อยประเมินแทน mypy

**แกน security static analysis (เสริมอีกชั้น)**
- **Semgrep** + ruleset `p/flask`, `p/python` — จับ pattern เฉพาะ framework
  ที่ ruff-S ไม่ครอบ (เช่น `render_template_string` กับ user input)
- **Bandit** standalone — ซ้ำกับ ruff-S เป็นส่วนใหญ่ → ใช้ ruff-S เป็นหลัก
  bandit เป็น optional cross-check
- **CodeQL** — ของแรงสุดในสาย taint analysis แต่ repo นี้ private:
  ต้องจ่าย GitHub Advanced Security → **ตัดออกโดยเหตุผลค่าใช้จ่าย**
  (ถ้าวันหนึ่ง repo เป็น public ค่อยเปิด ฟรีทันที)

### 2.3 คุณภาพเชิงโครงสร้างและเทสต์ (ของที่ทำให้ "vibe code" พิสูจน์ตัวเองได้)

| เครื่องมือ | ทำอะไร | ความเข้ากับโปรเจกต์ |
|---|---|---|
| **hypothesis** | property-based testing | เหมาะมาก — `tz.to_utc/to_local` (roundtrip), `parse_boundary`, ตัวแยกพิกัด sun table เป็น pure function ทั้งนั้น |
| **mutmut** | mutation testing อัตโนมัติ | **โปรเจกต์นี้ทำ mutation testing มือทุกฟีเจอร์อยู่แล้ว** — automate สิ่งที่เป็นวัฒนธรรมอยู่แล้ว (ช้า → รัน nightly ไม่ใช่ทุก push) |
| **coverage.py** branch mode + threshold | ครอบ branch ไม่ใช่แค่ line | ยกระดับจาก line coverage |
| **diff-cover** | บังคับ coverage เฉพาะบรรทัดที่แก้ | กัน coverage เฉลี่ยบังบรรทัดใหม่ที่ไม่มีเทสต์ |
| **radon + xenon** | cyclomatic complexity + gate | ตั้ง gate เช่น xenon --max-absolute B |
| **interrogate** | docstring coverage | โค้ดมี docstring ภาษาไทยดีอยู่แล้ว — วัดให้เป็นตัวเลข |
| **pre-commit** | รันทุกอย่างก่อน commit ฝั่งเครื่อง dev | มาตรฐาน de facto |
| **gitlint** | บังคับ Conventional Commits | โปรเจกต์ใช้ convention นี้อยู่แล้วทุก commit — แค่ enforce |
| **schemathesis** | fuzz จาก OpenAPI spec | ✓ ใช้แล้ว (Phase 3) — `tests/test_api_fuzz.py` |
| **uv** (Astral) | แทน pipenv เร็วกว่ามาก | optional — Pipfile ใช้งานได้ดี ย้ายเมื่อเจ็บจริง ไม่ย้ายตามแฟชั่น |

### 2.4 สิ่งที่โปรเจกต์ทำถูกตามมาตรฐานอยู่แล้ว (ประกาศเป็นกติกา)

Conventional Commits ทุก commit / ADR กำลังจะเริ่ม Phase 0 / เทสต์แยกไฟล์ตาม
ความกังวล / migration ทดสอบ round trip / secrets ไม่เคยเข้า git (สแกนยืนยันแล้ว)

---

## 3. Flask

**คำตอบตรง ๆ: Flask ไม่มี "official analyzer" ผูกกับ framework แบบ PHPStan/Larastan**
สิ่งที่ทดแทนคือ stack ในข้อ 2 (ruff + mypy/pyright + semgrep `p/flask`) ซึ่งรวมกัน
ครอบคลุมกว้างกว่า Larastan ด้วยซ้ำ — แลกกับต้องประกอบเอง

**แนวทาง canonical ของ Flask เอง (จาก official docs + community consensus):**

| Pattern | สถานะโปรเจกต์ |
|---|---|
| Application factory (`create_app`) | ✓ ใช้แล้ว |
| Blueprints แยกส่วน | ✓ `main`/`auth` + `/api/v1` (Phase 3) |
| Config เป็น class + env | ✓ + fail-closed SECRET_KEY |
| ไม่รัน debug server ใน production | ✓ ระบุใน README |
| Extension init แบบ `init_app` | ✓ ทุกตัว |

**เครื่องมือเฉพาะทางที่ควรเพิ่ม:**
- **Flask-Talisman** — security headers (CSP/HSTS/frame-ancestors) เป็น extension
  มาตรฐานของงานนี้ → ใช้เป็นตัว implement ใน Phase 1 แทนเขียน after_request เอง
- **djlint** (Jinja profile) — lint + format template ซึ่งตอนนี้ไม่มีอะไรตรวจเลย
  จับได้ทั้ง style และบางส่วนของ a11y
- **pa11y/axe + html5validator** — อยู่ในแผน Phase 1 แล้ว
- OWASP Cheat Sheets (Session Management, CSRF) — ใช้เป็นเกณฑ์ตรวจใน Phase 4
  (อยู่ในแผนแล้ว)

---

## 4. Verdict — อะไรเข้าเมื่อไหร่

### เข้า Phase 0 (CI gates — ทั้งหมดไม่แตะโค้ดแอป ยกเว้น fix ที่ lint เจอ)
ruff (`select=ALL` + ignore มีเหตุผล) / ruff format / mypy (strict แบบ gradual,
เริ่มจาก module ใหม่ + `app/tz.py`, `app/filters.py`, `app/plugins/`) /
coverage branch + threshold + diff-cover / xenon / interrogate / pre-commit /
gitlint / pip-audit / SBOM / migration lint / semgrep `p/flask`

### เข้า Phase 2 ด่านแรก (รอบ "schema identity" — migration เดียวจบ)
prefix `tdl_*` ทุกตาราง + `tdl_alembic_version` / SQLAlchemy `naming_convention` /
`done` → `is_done` / rewrite model เป็น SQLAlchemy 2.0 typed style
→ **ผลพลอยได้: landmine reserved word `user` หมดไปถาวร** (ดี กว่ารอ squash Phase 5)

### ตามเฟสที่เกี่ยวข้อง
Flask-Talisman + djlint → Phase 1 / hypothesis → เริ่ม Phase 2 (ใช้กับ tz/filters
ก่อน) / mutmut nightly → หลัง Phase 0 เสถียร / schemathesis → Phase 3 /
sqlfluff → เมื่อ migration ซับซ้อนขึ้น (Phase 2)

> **ทบทวน 2026-08-15 (หลังเฟส 13–18):** สี่ตัวในแผนข้างบนไม่เคยถูกนำเข้า
> และตอนนี้**ตัดออกอย่างเปิดเผย**แทนที่จะค้างเป็นนัดที่เลยมานาน —
> **djlint/sqlfluff**: template กับ migration มีด่านพฤติกรรมจริงคุมอยู่แล้ว
> (test_security_headers อ่าน template ตรง ๆ · test_design_doc เทียบหน้ากับ
> ตารางโหมดใน DESIGN.md · job `schema` เดิน migration จริง)
> lint เชิงรูปแบบไม่เพิ่มการจับบั๊กชั้นที่เหลือ · **hypothesis**: ชุด mutation
> discipline + fuzz ของ schemathesis ครอบเส้นที่ property-based จะครอบ ในสเกล
> แอปนี้ · **mutmut nightly**: กติกา mutation ทำมือทุกเทสต์ใหม่ (บังคับใน
> CLAUDE.md) ให้ผลเดียวกันแบบ targeted โดยไม่มี nightly ให้เฝ้า — ทั้งสี่ข้อ
> กลับเข้าแผนได้ถ้าเงื่อนไขเปลี่ยน (แอปโตจนทำมือไม่ไหว)
> · **gitlint ในรายการ Phase 0 คือชื่อแนวคิด ไม่ใช่เครื่องมือที่ลง** — ของจริง
> ที่รันคือ `scripts/lint_commits.py` + job `commit-lint` (เขียนเองเพราะต้องมี
> กติกา `--no-merges` และเทียบ head ของ PR)
> · **ของเพิ่มจากเฟส 15**: `cryptography ~=45.0` เป็น crypto dependency ตัวแรก
> ของ runtime — อยู่ใน category `plugin-auth-totp` ตาม ADR 0025 (ถอด plugin =
> supply chain หายตาม) ไม่ใช่ `[packages]` ของ core

**schemathesis เข้าแล้วใน Phase 3** (`tests/test_api_fuzz.py`) — สร้างคำขอจาก
`docs/openapi.json` เองแล้วตรวจว่าคำตอบตรงกับสัญญา รอบแรกที่เปิดใช้จับได้สามอย่าง
ที่เทสต์ที่คนเขียนเองมองข้าม และทั้งสามกระทบหน้าเว็บด้วยไม่ใช่แค่ API:
ตัวกรองวันที่ที่ย่อยไม่ได้ → 500, id ที่เกิน 64 บิต → `OverflowError` → 500,
และคำขอที่ตกตั้งแต่ชั้น routing ได้ HTML กลับไป (405 ไม่มี header `Allow` ด้วย)
ตั้ง `max_examples` ไว้เตี้ยเพื่อให้รันได้ทุกครั้ง — งานหนักกว่านี้เป็นของ nightly

### เข้าเพิ่มหลังเฟส 7 (ทบทวน 2026-08-14)

**CodeQL เข้าแล้ว** — เหตุผลที่เคยตัดออก ("repo private → ต้องจ่าย GHAS")
หมดอายุตอน repo เป็นสาธารณะเมื่อ 2026-08-12 · รันเป็น job ใน `ci.yml`
ไม่ใช่ default setup และรอบแรกเจอของจริงสองอย่าง

**เครื่องมือที่เฟส 8–12 เพิ่มเข้ามา** — ไม่ได้อยู่ในรายการสำรวจเดิมเพราะมันไม่ใช่
เครื่องมือสำเร็จรูป แต่เป็นของที่เขียนเอง: `gates.yaml` (ดัชนี gate ตรวจสองทิศ)
· `verifiable-gates` เป็นเจ้าของคลังกฎและเรนเดอร์แผ่นกฎเอง (ADR 0078) · bundle ส่งออก 16 ไฟล์ (`overlay.json`): scan 9 ตัว stdlib
ล้วน + ดัชนี `gates.yaml` ตั้งต้น สำหรับโปรเจกต์อื่น) · `scripts/run_gates.py` (fail-fix loop) ·
`verifiable_gates.measure_apps` + `verifiable_gates.asvs_probe` (วัดผลของ
scaffolding — **อยู่ที่ vg แล้ว** ตั้งแต่ ADR 0077 ขั้น 5 · ที่นี่เหลือ adapter
ที่พาธเดิมเรียกได้)
· **เหตุผลที่ไม่ใช้เครื่องมือสำเร็จรูปแทน**: กฎที่ต้องบังคับเป็นข้อตกลงเฉพาะ
โปรเจกต์ (soft delete, service layer ไม่รู้จัก HTTP, ตารางขึ้นต้น `tdl_`)
ซึ่งไม่มี linter ไหนรู้จัก · รายละเอียดอยู่ใน [`ROADMAP-INFRA.md`](ROADMAP-INFRA.md)

### Watch list (ยังไม่ใช้ — ตรวจใหม่เมื่อ stable)
ty (beta, conformance ต่ำ), pyrefly (ยังไล่ mypy ไม่ทัน), uv (ย้ายเมื่อคุ้มจริง)

### ตัดออกพร้อมเหตุผล
~~CodeQL (repo private → ต้องจ่าย GHAS)~~ **เข้าแล้ว 2026-08-12 เมื่อ repo
เป็นสาธารณะ** / bandit standalone (ซ้ำ ruff-S) /
prefix ต่อ environment แบบ WordPress multi-site (ไม่ใช่ use case เรา)
