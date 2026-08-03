# Todolist (Flask)

## Stack
- Flask + Flask-SQLAlchemy, SQLite (dev), pipenv จัดการ env
- Flask-Migrate (alembic) จัดการ schema, Flask-Login จัดการ session, Flask-WTF จัดการ CSRF,
  Flask-Limiter จำกัดจำนวนครั้งที่หน้า login
- Python 3.13

## Commands
- รัน dev server: `pipenv run flask run --debug`
- รัน test: `pipenv run pytest -v` (coverage gate: `pipenv run pytest --cov`)
- lint/format: `pipenv run ruff check .` / `pipenv run ruff format .`
- type check: `pipenv run mypy app scripts` (strict list ใน pyproject — ขยาย ห้ามหด)
- ครั้งแรกหลัง clone: `pipenv run pre-commit install --hook-type pre-commit --hook-type commit-msg`
- เพิ่ม dependency: `pipenv install <pkg>` (ห้ามใช้ `pip install` ตรง ๆ — Pipfile/Pipfile.lock จะไม่ sync)
- สร้าง user: `pipenv run flask create-user <ชื่อ>` (ไม่มีหน้าสมัครสมาชิก โดยตั้งใจ)
- ดู user: `pipenv run flask list-users`
- ล้างข้อมูลที่พ้นระยะ: `pipenv run flask purge-expired` (ดูก่อนด้วย `--dry-run`)
- ตรวจ audit: `pipenv run flask audit-verify` / อ่าน audit: `pipenv run flask audit-log`
- เปลี่ยน schema: `pipenv run flask db migrate -m "..."` แล้ว `pipenv run flask db upgrade`

## Structure
- `app/__init__.py` — app factory (`create_app`), init db/migrate/csrf/limiter/login_manager
  และ errorhandler ของ 429
- `app/models.py` — SQLAlchemy models (`User`, `Category`, `Todo`) แบบ 2.0 typed (`Mapped[]`)
- `app/routes.py` — view functions ของงาน/หมวด/ตั้งค่า ผูกกับ blueprint `main`
- `app/auth.py` — login/logout ผูกกับ blueprint `auth`
- `app/cli.py` — custom flask CLI commands
- `app/tz.py` — แปลงเวลา UTC ↔ เวลาท้องถิ่นของผู้ใช้
- `app/theme.py` — เลือกชุดสีและโหมด, `app/sun_data.py` — ตารางดวงอาทิตย์ (generate)
- `app/plugins/` — registry ของ plugin + ตัว plugin เอง (ดูหัวข้อ "สถาปัตยกรรม plugin")
- `app/security_headers.py` — CSP + security header (Talisman), `app/logging_setup.py` — JSON log + request id
- `app/db_engine.py` — ค่าระดับ connection (เปิดบังคับ foreign key ของ SQLite)
- `app/soft_delete.py` — ตัวกรอง `deleted_at IS NULL` อัตโนมัติ, `app/purge.py` — จุดเดียวที่ลบจริง
- `app/audit.py` — audit trail แบบเติมได้อย่างเดียว + hash chain (ดูหัวข้อ Audit trail)
- `app/static/base.css` — เลย์เอาต์ของ core **ห้ามมีสีดิบ** สีมาจากธีมทั้งหมด
- `app/static/app.js` — พฤติกรรมฝั่ง client **ทั้งหมด** (ห้ามมี inline handler ที่อื่น)
- `.pa11yci.json` — รายการหน้าที่ job `a11y` ใน CI สแกน (รวมโหมดมืด/ธีม ocean/ภาษาไทย)
- `scripts/` — สคริปต์ที่รันมือ ไม่ได้ถูกเรียกตอนแอปทำงาน
- `app/templates/` — Jinja2 templates (ทุกหน้า extend `base.html`)
- `app/static/` — `logo.svg` (120px ใช้หน้า login) และ `logo-small.svg` (32px ใช้บน header + favicon)
  ตัวเล็กไม่ใช่ตัวใหญ่ย่อลงมา แต่ตัดรายละเอียดออกให้เหลือแค่เครื่องหมายถูก
- `migrations/` — alembic migration scripts (commit ลง git ด้วย)
  `env.py` ตั้ง `version_table` เป็น `tdl_alembic_version` และเปลี่ยนชื่อตารางเวอร์ชันเก่าให้เอง
- `tests/` — pytest, fixture จาก `conftest.py`
- `pyproject.toml` — config กลางของ ruff/mypy/coverage/interrogate/pytest
  (pytest.ini ถูกยุบเข้ามาแล้ว) threshold เป็น ratchet: ขยับขึ้นได้อย่างเดียว
- `docs/adr/` — การตัดสินใจสำคัญทุกเรื่อง ตัดสินใจใหม่ต้องมี ADR
- commit message เป็น Conventional Commits หัวไม่เกิน 72 ตัว (hook + CI บังคับ)

## Conventions
- Route คืน `render_template`/`redirect` เท่านั้น ไม่คืน raw string
- Query model นอก request ต้องอยู่ใน `with app.app_context():`
- **ทุก route ต้องมี `@login_required`** และ query ต้อง filter ด้วย `user_id=current_user.id` เสมอ
- **แถวในลิสต์งานอ่านอย่างเดียว** การแก้อยู่ที่หน้า `/edit/<id>` แยกต่างหาก
  เพราะมีทั้งชื่อ หมวด วันเริ่ม และกำหนดส่ง ใส่ในแถวเดียวแล้วอ่านไม่ออก
- checkbox "แสดงวันเริ่ม" จำไว้ใน session ต้องมี hidden `filters_submitted`
  ในฟอร์มด้วย เพราะ checkbox ที่ไม่ติ๊กจะไม่ถูกส่งมาเลย แยกไม่ออกจากการกดลิงก์อื่น
- **ลบหมวดได้เฉพาะตอนไม่มีงานอยู่เลย** งานที่ทำเสร็จแล้วก็ยังนับ
  (มันยังโผล่ในตัวกรอง "เสร็จแล้ว") ปุ่มบนหน้าเว็บถูก disabled ไว้ด้วย
  แต่การกันจริงอยู่ที่ route — อย่าเชื่อแค่ปุ่ม
- ห้ามใช้ `db.get_or_404()` กับข้อมูลที่มีเจ้าของ — ใช้ `_owned_todo()`/`_owned_category()` ใน `routes.py`
  ซึ่งตอบ 404 (ไม่ใช่ 403) เมื่อเป็นของคนอื่น เพื่อไม่ให้รู้ว่า id นั้นมีจริง
- `create_app` **ไม่เรียก** `db.create_all()` แล้ว — schema มาจาก migration เท่านั้น
  (เทสต์สร้างตารางเองใน fixture `app`)
- **`TestConfig` ใน `tests/conftest.py` ต้อง `class TestConfig(Config)` เสมอ**
  ห้ามเขียนใหม่แบบ standalone — ลืม copy ค่าใหม่จาก `Config` มาแล้ว 4 ครั้ง
  (LANGUAGES, RATELIMIT_STORAGE_URI, THEMES, LOG_LEVEL) เทสต์จะพังแบบงง ๆ
  เพราะ config ขาดไปเฉย ๆ ไม่ใช่เพราะโค้ดผิด — สืบทอดแล้ว override เฉพาะที่ต่าง
- ส่งข้อความจาก template ไปให้ JS ใช้ `data-*` attribute (Jinja escape ให้เอง)
  ไม่ต้อง `|tojson` แล้วเพราะไม่มี inline script เหลือ — ดูหัวข้อ CSP ด้านล่าง
- **ตั้งชื่องาน/หมวดในเทสต์อย่าให้ตรงกับข้อความบน UI** เช่น "ยังไม่เสร็จ"/"เสร็จแล้ว"
  เป็น label ของลิงก์ตัวกรองที่อยู่ในหน้าเสมอ `assert ... not in resp.data` จะพังทันที
- **ทุก `<form method="post">` ต้องมี `{{ csrf_field() }}` หรือ hidden input `csrf_token`**
  `CSRFProtect` คุมทั้งแอป ลืมใส่แล้ว form นั้นจะได้ 400 ทันที
- เทสต์ทั่วไปปิด CSRF (`WTF_CSRF_ENABLED = False` ใน `TestConfig`) ตัว CSRF มีเทสต์แยกใน
  `tests/test_csrf.py` ที่เปิดใช้จริงผ่าน fixture `csrf_app` — ห้ามลบไฟล์นั้นทิ้ง
  ไม่งั้นจะไม่มีอะไรจับได้เวลา `csrf.init_app()` หลุด

## Mutation test — บังคับ ไม่ใช่ทางเลือก

**เทสต์ใหม่ทุกตัวต้องถูกพิสูจน์ว่าจับของจริงได้ ก่อนถือว่าเสร็จ**
วิธี: พังโค้ดที่เทสต์นั้นอ้างว่าคุ้มอยู่ทีละจุด → เทสต์ต้องแดง → คืนโค้ดกลับ
ถ้าพังแล้วยังเขียว แปลว่าเทสต์นั้นไม่ได้ทดสอบอะไรเลย ให้แก้เทสต์ ไม่ใช่ปล่อยผ่าน

ต้องพังให้ตรงกับสิ่งที่เทสต์อ้าง — ลบ `aria-label` ออกจริง ๆ ไม่ใช่แค่แก้ตัวแปร
ข้าง ๆ และคืนโค้ดกลับด้วย `cp` จากสำเนา ไม่ใช่แก้มือย้อน (พลาดง่าย)
ตรวจว่าคืนครบด้วย `git diff` หรือ `diff -r` ทุกครั้ง

ที่จับได้มาแล้วเพราะทำขั้นนี้:
- เทสต์ลำดับการเรียงที่ผ่านทั้งที่ถอด `order_by` ออก (แก้: ใส่งานสลับลำดับที่คาดไว้)
- เทสต์บันทึก preferences ที่ผ่านทั้งที่ไม่ได้เขียน session (แก้: seed session ค้างไว้ก่อน)
- `resolve_mode()` ที่ผ่านทั้งที่เป็น stub (แก้: เทสต์ end-to-end หาโซนที่ตอนนี้เป็นกลางคืน)
- regex จับ `#, fuzzy` ที่พลาด `#, fuzzy, python-format`

**เทสต์ที่ผลลัพธ์ขึ้นกับเครื่อง ต้องปลอม input เอง** อย่าพึ่งว่าเครื่องที่รันมีอะไร
(`available_timezones()` มี `localtime` บน Ubuntu แต่ไม่มีบน Gentoo →
เขียวบนเครื่อง dev แดงบน CI ดู `test_pseudo_zones_are_never_offered`)

## ลำดับด่านของ request (สำคัญตอนอ่าน status code)

`CSRFProtect` ทำงานใน `before_request` จึง**ตัดก่อน** `@login_required` เสมอ
POST ที่ทั้งไม่มี token และไม่ได้ login จะได้ **400 (CSRF) ไม่ใช่ 302 (ไป login)**

| สถานะคำขอ | ผลลัพธ์ |
|---|---|
| ไม่มี token + ไม่ได้ login | 400 |
| มี token ถูกต้อง + ไม่ได้ login | 302 → `/login` |
| มี token + login แล้ว + ของคนอื่น | 404 |
| POST `/login` ผิดรหัสเกินโควตา | 429 |

ทั้งสองด่านยังอยู่ครบ แค่ CSRF มาก่อน — คนนอกขอ token จากหน้า `/login` ได้ก็จริง
แต่ยิงต่อไปก็ยังติด `@login_required` อยู่ดี

ผลที่ตามมาเวลาแก้บั๊ก:
- เห็น **400** ที่ POST อย่าเพิ่งสรุปว่า "ไม่ได้ login" ให้เช็ค `csrf_token` ใน form ก่อน
- อย่าเขียนเทสต์ที่ assert 302 สำหรับคนที่ยังไม่ login **บนแอปที่เปิด CSRF** โดยไม่แนบ token
  (เทสต์ส่วนใหญ่ปิด CSRF ไว้ จึงได้ 302 ตามปกติ — ต่างกันตรงนี้)

## Environment
- ต้องมี `.env` ที่มี `SECRET_KEY` ไม่งั้นแอปจะไม่ start (ดู `.env.example`)
- `SECRET_KEY` **ไม่มีค่า default โดยตั้งใจ** และต้องยาว ≥ 32 ตัว — ตรวจใน `check_secret_key()`
  ห้ามใส่ default กลับเข้าไปเพื่อความสะดวก มีเทสต์ใน `tests/test_config.py` ดักไว้
- เปลี่ยน `SECRET_KEY` แล้ว session และ CSRF token เดิมใช้ไม่ได้ ทุกคนต้อง login ใหม่
- `.env` ถูก gitignore — `.env.example` เป็นตัวที่ commit
- `LOGIN_RATE_LIMIT` (default `5 per minute; 20 per hour`) และ `RATELIMIT_STORAGE_URI`
  (default `memory://`) ปรับผ่าน env ได้
- **`memory://` นับแยกต่อ process** — ถ้าวันไหนรันหลาย worker (gunicorn ฯลฯ)
  ต้องเปลี่ยนเป็น `redis://` ไม่งั้นเพดานจริงจะกลายเป็น N เท่าของที่ตั้งไว้

## กำหนดส่ง วันเริ่ม และตัวกรอง
- **`Todo.due_date` ใน DB เป็น UTC แบบ naive เสมอ** เหมือน `created_at`/`updated_at`
  ค่าที่ผู้ใช้กรอกจาก `<input type="datetime-local">` เป็นเวลาท้องถิ่นของเขา
  ต้องผ่าน `tz.to_utc()` ก่อนเก็บ และ `tz.to_local()` ก่อนแสดง (ดู `app/tz.py`)
  ใน template ใช้ `todo.due_local` ไม่ใช่ `todo.due_date`
- `Todo.is_overdue` เทียบ UTC กับ UTC จึงไม่ขึ้นกับ timezone ของใคร
  ส่วน `is_due_today` ต้องเทียบวันตามเวลาท้องถิ่นของ **เจ้าของงาน** ไม่ใช่ UTC
  งานที่ `done=True` ไม่นับว่าเลยกำหนด และ `is_due_today` เป็น False ถ้าเลยกำหนดไปแล้ว
  (ไม่ให้ขึ้นป้ายซ้อนกันสองอัน)
- property พวก `due_local`/`is_overdue` แตะ `todo.user` จึงเรียกนอก app context ไม่ได้
  (lazy-load ไม่ได้) เทสต์ต้องอ่านค่าใน `with app.app_context():`
- **`batch_alter_table` บน SQLite ทำข้อมูลพังตอนเปลี่ยนชนิดคอลัมน์เป็น DATETIME**
  alembic คัดลอกข้อมูลด้วย `CAST(col AS DATETIME)` และ DATETIME มี NUMERIC affinity
  `'2026-08-02'` จึงกลายเป็นเลข `2026` — ดูวิธีแก้ใน migration `89cd0c572bf9`
  (อ่านค่าเก็บไว้ก่อน ปล่อยให้ batch alter ทำลาย แล้ว UPDATE เขียนกลับด้วยพารามิเตอร์ข้อความ)
  **ทุกครั้งที่ migration แตะข้อมูลเดิม ให้สำรอง `instance/todolist.db` ก่อนรัน**
- เรียงลำดับ: งานที่มีกำหนดส่งขึ้นก่อน (ใกล้ครบกำหนดสุดก่อน) แล้วค่อยงานไม่มีกำหนด
  เรียงตาม `created_at` ล่าสุดก่อน
- `Todo.start_date` เก็บแบบเดียวกับ `due_date` (UTC naive) มี `start_local` คู่กัน
  เป็นข้อมูลประกอบเท่านั้น **ตัวกรองตามวันดูจาก `due_date` อย่างเดียว**
- ตัวกรองรับผ่าน query string: `?status=all|active|completed`, `?category=<id>|none`
  และ `?when=all|upcoming|today|tomorrow|range` (+ `within` นาที, `date_from`/`date_to`)
  ค่าที่ไม่รู้จักใน `status`/`when`/`within` fallback เป็นค่าเริ่มต้น
  แต่ `category` ที่เป็นของคนอื่นตอบ 404
- **ชื่อพารามิเตอร์ต้องเป็น `date_from`/`date_to` ไม่ใช่ `from`/`to`**
  เพราะ `from` เป็น keyword ของ Python ส่งเข้า `url_for()` ตรง ๆ ไม่ได้
- ตรรกะตัวกรองอยู่ใน `app/filters.py` คำนวณช่วงเป็นเวลาท้องถิ่นก่อน
  แล้วค่อย `tz.to_utc()` ตอนไปเทียบกับ DB — งานที่ไม่มี `due_date` ถูกกรองออก
  เมื่อมีการเลือกช่วง เพราะตอบคำถาม "ครบกำหนดช่วงนี้ไหม" ไม่ได้
- `Upcoming` นับจาก **ตอนนี้** ไปข้างหน้าตามช่วงที่เลือก งานที่เลยกำหนดแล้วไม่นับ
  ถ้าช่วงคร่อมเที่ยงคืนก็จะรวมงานของวันถัดไปด้วย (ตั้งใจ — "ภายใน 8 ชม." คือ 8 ชม. จริง)
- เลือกช่วงเองโดยใส่แค่ `date_from` = ครอบทั้งวันนั้น (00:00–23:59)
- `_parse_due_date()` raise `ValueError` ถ้ารูปแบบผิด — route ต้อง catch แล้ว flash
  (browser ส่งมาถูกเสมอ แต่คนยิง POST ตรง ๆ ส่งอะไรมาก็ได้)

## หลายภาษา (i18n)
- ใช้ Flask-Babel (gettext) ภาษาที่รองรับประกาศใน `config.LANGUAGES` ค่าเริ่มต้นคือ `en`
- **ข้อความในโค้ดต้องเป็นภาษาอังกฤษเสมอ** เพราะ msgid คือภาษาอังกฤษ
  ภาษาไทยอยู่ใน `app/translations/th/LC_MESSAGES/messages.po` — ห้ามเขียนไทยลงโค้ดตรง ๆ
- ใช้ `gettext as _` ในไฟล์ `.py` และ `{{ _('...') }}` ใน template
  ใช้ `lazy_gettext` เฉพาะข้อความที่ประกาศตอน import (ยังไม่มี request) เช่น `login_message`
- นับจำนวนใช้ `ngettext` — ไทยมี `nplurals=1` มี `msgstr[0]` อย่างเดียว
- ส่งค่าเข้าข้อความใช้ named placeholder `%(name)s` ไม่ใช่ f-string
  ไม่งั้น pybabel ดึง msgid ไม่ได้และผู้แปลสลับลำดับคำไม่ได้

### workflow เวลาเพิ่ม/แก้ข้อความ
```
pipenv run pybabel extract -F babel.cfg -k _l -k _ -k ngettext:1,2 -o messages.pot .
pipenv run pybabel update -i messages.pot -d app/translations
# แก้คำแปลใน app/translations/*/LC_MESSAGES/messages.po
pipenv run pybabel compile -d app/translations
```
- **ไฟล์ `.mo` ถูก commit ลง git ด้วย** เพื่อให้ clone แล้วรันได้เลย
  แก้ `.po` แล้วต้อง compile ใหม่ ไม่งั้นคำแปลจะไม่เปลี่ยน — `tests/test_i18n.py` ดักไว้
- **ระวัง `#, fuzzy`** — `pybabel update` จะเดาคำแปลให้จากข้อความที่คล้ายกัน
  (เคยเดา "First name" เป็น "ชื่องาน" มาแล้ว) และ `compile` จะข้ามรายการ fuzzy ไป
  ทำให้ตกกลับเป็นภาษาอังกฤษเงียบ ๆ ต้องแก้คำแปลแล้วลบบรรทัด `#, fuzzy` ออก
  ตรวจแค่ `msgstr ""` ไม่พอ — มีเทสต์เช็คทั้งสองอย่าง
- เพิ่มภาษาใหม่: เติมใน `config.LANGUAGES` แล้ว `pybabel init -i messages.pot -d app/translations -l <รหัส>`

### ลำดับการเลือกภาษา (ดู `app/i18n.py`)
`?lang=` → session → `User.locale` → `Accept-Language` → `en`
session มาก่อนโปรไฟล์เพื่อให้กดสลับแล้วเห็นผลทันที และการกดสลับจะบันทึกลงโปรไฟล์ให้ด้วย

### สิ่งที่ไม่ได้แปล
- ชื่องานและชื่อหมวดเป็นข้อมูลของผู้ใช้ ไม่ผ่าน gettext
- หมวดตั้งต้นสร้างตาม `--lang` ของ `flask create-user` แล้วคงที่ ไม่เปลี่ยนตามภาษาที่เลือกทีหลัง
- **ข้อความของ CLI เป็นภาษาอังกฤษตายตัว ไม่ผ่าน gettext** เพราะ CLI รันนอก request context
  จึงไม่มีข้อมูลว่าจะใช้ภาษาไหน — `select_locale()` กันไว้ด้วย `has_request_context()`
  ถ้าเรียกแปลนอก request จะได้ภาษาเริ่มต้นแทนที่จะ RuntimeError (`tests/test_i18n.py` ดักไว้)

## สถาปัตยกรรม plugin

เป้าหมายระยะยาวคือให้ todolist เป็น core + plugin แบบ Moodle ตอนนี้ทำแล้ว
เฉพาะชนิด `theme` แต่ registry ออกแบบให้เพิ่มชนิดอื่นได้โดยไม่ต้องรื้อ

**สัญญาที่ห้ามผิด**
- core **ห้าม hardcode ชื่อ plugin ตัวใดตัวหนึ่ง** — รู้แค่วิธีค้นหา
  (`tests/test_plugins.py` grep หาชื่อธีมที่ไม่ใช่ core ในโค้ด core ทั้งหมด)
- plugin หนึ่งตัว = หนึ่งไดเรกทอรีใต้ `app/plugins/<ชนิด>/<ไอดี>/` + `plugin.json`
  ชื่อไดเรกทอรีคือไอดี
- **เพิ่ม plugin = วางไดเรกทอรี ลบ plugin = ลบไดเรกทอรี** ไม่ต้องแก้ core
  และไม่ต้อง restart (registry อ่านดิสก์ทุกครั้ง แอปเล็กพอที่จะไม่ต้อง cache)
- ถอน plugin ที่มีคนใช้อยู่แล้วระบบต้องไม่พัง — ค่าที่เก็บไว้ใน `User.theme`
  ไม่ถูกลบ แค่ไม่ผ่าน `theme_is_supported()` จึงตกกลับไปใช้ธีม core
- ธีม `system` เป็น core (`"core": true` ใน manifest) **ต้องมีเสมอ**
  ถ้าหายแอปจะไม่ start (`plugins.check_installation()` เรียกใน `create_app`)
- plugin ที่ต้องเก็บข้อมูลเพิ่มต้องดูแล table ของตัวเอง ห้ามแก้ table ของ core

### ธีมเป็น plugin
- สีทั้งหมดอยู่ใน `app/plugins/themes/<id>/theme.css` ส่วนเลย์เอาต์อยู่ใน
  `app/static/base.css` ของ core ซึ่งอ้าง `var(--...)` อย่างเดียว
  **เพิ่มธีมใหม่ = ก๊อป `theme.css` ไปเปลี่ยนค่าสี ไม่ต้องเขียน CSS เลย์เอาต์ซ้ำ**
- ทุกธีมต้องกำหนดตัวแปรชุดเดียวกันครบทั้งโหมดสว่างและมืด ไม่งั้นจะมีสีตกค้าง
  จากธีมก่อนหน้า — มีเทสต์เทียบตัวแปรข้ามธีม
- หน้าเว็บโหลด `base.css` ก่อนแล้วค่อยโหลดธีม ลำดับนี้สำคัญ ธีมถึงจะทับสีได้
- `/plugin/themes/<id>/style.css` เป็น route ของ core ที่เสิร์ฟไฟล์ของ plugin
  ตรวจไอดีกับรายการที่ค้นเจอจริงก่อนเสมอ จึง traverse ออกนอกไดเรกทอรีไม่ได้

## ธีมกับโหมด (สว่าง/มืด/อัตโนมัติ)

แยกสองแกน อย่าเอามาปนกัน:
- **theme** = ชุดสี มาจาก plugin (ดูข้างบน) ค่าเริ่มต้นคือ `system`
- **mode** = ระดับความสว่าง `light` / `dark` / `auto` ค่าเริ่มต้นคือ `auto`

- `User.theme` เก็บไอดีธีม ส่วน `User.mode` เก็บระดับความสว่าง
  **`auto` เก็บเป็นสตริง `'auto'` ไม่ใช่ NULL** (ต่างจาก `locale`/`timezone_name`
  ที่ NULL แปลว่ายังไม่เลือก) เพราะ auto เป็นตัวเลือกจริงที่ผู้ใช้ตั้งใจเลือก
- ลำดับเหมือนภาษา: `?mode=` → session → `User.mode` → `auto` (ดู `app/theme.py`)
- **โหมด "ตามระบบ" (`prefers-color-scheme`) ถูกตัดทิ้งแล้ว** server ตัดสินโหมด
  มาให้เสมอและส่งเป็น `data-theme="light|dark"` บน `<html>`

### ตารางดวงอาทิตย์ (โหมด auto)
- `app/sun_data.py` เก็บเวลาขึ้น-ตกรายเดือนของ **ทุกชื่อที่ zoneinfo รู้จัก (598)**
  **เป็นไฟล์ที่ generate มา ห้ามแก้ด้วยมือ** สร้างใหม่ด้วย
  `python scripts/generate_sun_table.py`
- พิกัดมาจาก `zone.tab` ของ tzdata คำนวณด้วยสูตรดาราศาสตร์ในสคริปต์เอง
  ไม่มี dependency เพิ่มและไม่เรียก API ครอบคลุมสามชั้น:
  418 โซนมีพิกัดเอง, 135 ชื่อพ้องยืมจากโซนที่ไฟล์ tzdata เหมือนกันเป๊ะ,
  45 โซนแบบ `Etc/GMT±N` ใช้เส้นศูนย์สูตรตาม offset (ขึ้น ~06:00 ตก ~18:00)
- **ตารางต้องครอบคลุมทุกชื่อใน `tz.all_timezones()`** ไม่งั้นโซนที่ขาด
  จะได้ `light` ตลอดเวลาเงียบ ๆ — เคยหลุดมาแล้วตอนสร้างจาก `zone1970.tab`
  (312 โซน) ขณะที่ dropdown มี 598 ชื่อ `tests/test_mode.py` ดักไว้แล้ว
- หน่วยเป็นนาทีนับจากเที่ยงคืน **ตามเวลาท้องถิ่นของโซนนั้น**
  ค่า `-1` = ทั้งเดือนดวงอาทิตย์ไม่ขึ้น (คืนขั้วโลก), `-2` = ไม่ตกเลย
- ความแม่นยำระดับไม่กี่นาที เพียงพอสำหรับสลับสี ไม่ได้ทำมาให้ดูฤกษ์
- **ตัวแยกพิกัดของ zone.tab เคยพังเงียบ ๆ มาแล้ว** — มีสองรูปแบบคือ 11 ตัว
  (`±DDMM±DDDMM`) กับ 15 ตัว (`±DDMMSS±DDDMMSS`) ถ้าเดาความยาวผิดจะได้
  ลองจิจูดมั่วโดยไม่มี error ตอนนี้ raise ทันทีถ้ารูปแบบไม่ตรง

## หน้า Settings
- `/settings` รวม โปรไฟล์ + ภาษา + ธีม + โหมด + timezone ไว้ที่เดียว
  nav มีแค่ลิงก์ Settings ส่วนหน้า login มีตัวสลับภาษา/โหมดของตัวเอง
  (route `/lang/<code>` และ `/mode/<value>` ใช้จากหน้า login ไม่ต้อง login)
- `_safe_referrer()` ใน `routes.py` ใช้ร่วมกันทั้งสลับภาษาและสลับโหมด รับเฉพาะ path ในเว็บเรา
- **username แก้ที่หน้านี้ไม่ได้** เพราะเป็นตัวระบุตอน login (ช่องเป็น `disabled`)
- ชื่อ/นามสกุลที่เว้นว่างเก็บเป็น **NULL ไม่ใช่ `''`** ไม่งั้น `full_name` จะมีช่องว่างเกิน
- บันทึก preferences แล้วต้อง **อัปเดต session ด้วย** ไม่ใช่แค่เขียน DB
  เพราะ session ชนะโปรไฟล์ในลำดับการเลือก ถ้าลืมแล้วผู้ใช้เคยกดสลับไว้ที่หน้า login
  ค่าที่เพิ่งบันทึกจะไม่มีผลเลย — `tests/test_settings.py` ดักไว้

## Rate limit
- จำกัดเฉพาะ `POST /login` GET ไม่โดน
- `deduct_when` หักโควตาเฉพาะตอนได้ 401 — login ถูกไม่กินโควตา
- โดนกันแล้วต้องได้ 429 แม้จะใส่รหัสถูก ไม่งั้นคนไล่เดารหัสจะรู้ทันทีว่าเจอรหัสที่ใช่
- เทสต์ทั่วไปปิด rate limit (`RATELIMIT_ENABLED = False`) ตัวจริงเทสต์ใน `tests/test_ratelimit.py`
  ผ่าน fixture `ratelimit_app` ซึ่งต้อง `limiter.reset()` **หลัง** `create_app` เท่านั้น
  (ก่อน `init_app` ยังไม่มี storage จะ assert พัง)

## CSP กับพฤติกรรมฝั่ง client (Phase 1 — ดู ADR 0010)
- CSP เป็น `'self'` ล้วน **ไม่มี `unsafe-inline`** ตั้งที่ `app/security_headers.py`
- **ห้ามมี `onclick=`/`onsubmit=`/`onchange=` หรือ `style=` ใน template เด็ดขาด**
  browser จะบล็อกเงียบ ๆ ไม่มี error ฝั่ง server ให้เห็น — `tests/test_security_headers.py`
  ตรวจไฟล์ template ตรง ๆ อีกชั้น
- พฤติกรรมทั้งหมดอยู่ใน `app/static/app.js` ไฟล์เดียว คุยกับ template ผ่าน `data-*`:
  `data-confirm="ข้อความ"` บน `<form>` = ถามยืนยัน, `data-auto-submit` บน control = submit เอง
- **`app.js` ต้องโหลดแบบ sync ใน `<head>` ห้ามใส่ `defer`/`async`** เพราะต้องติดคลาส
  `js` ให้ `<html>` ก่อน body render ไม่งั้นปุ่มสำรอง `.js-hidden` จะโผล่แวบหนึ่งแล้วหาย
- ของที่ผูกกับ TLS (HSTS/บังคับ https/cookie `Secure`) เปิดด้วย `HTTPS_ENABLED=1`
  ตัวเดียว **อย่าเปิดตอนยังรัน http** จะ redirect วนจน login ไม่ได้

## Accessibility (WCAG 2.2 AA — ดู ADR 0012)
- **ทุก `<form>` ต้องมีปุ่ม submit จริง** ฟอร์มที่พึ่ง `data-auto-submit` อย่างเดียว
  ใช้ไม่ได้เลยเมื่อ JS ไม่ทำงาน — ใส่ `<button type="submit" class="js-hidden">` เป็นทางสำรอง
  (`.js .js-hidden { display: none }` ซ่อนเฉพาะตอน JS ทำงานจริง **ห้ามเปลี่ยนเป็น
  `.js-hidden { display: none }` เปล่า ๆ** จะกลายเป็นฟอร์มที่ submit ไม่ได้)
- ทุก control ต้องมีชื่อ — `<label for>`, `<label>` ห่อ, `aria-label` หรือ `aria-labelledby`
  (ทั้งสี่ทางถูกต้องเท่ากัน) แถวงานใช้ `aria-label` เพราะไม่มีที่วาง label ที่มองเห็น
- ตรวจสองชั้น: `tests/test_a11y.py` (โครงสร้าง รันทุกครั้ง) + job `a11y` ใน CI
  (pa11y-ci + Chromium จริง สแกนโหมดมืด ธีม ocean และภาษาไทยด้วย เพราะ contrast ต่างกัน)
- รัน pa11y เองบนเครื่อง: ตั้ง `DATABASE_URL` ชี้ไฟล์ทิ้ง → `flask db upgrade` →
  `PYTHONPATH=. python scripts/a11y_fixture.py` → `flask run --port 5099` → `pa11y-ci`
  (สคริปต์ fixture ปฏิเสธถ้า `DATABASE_URL` ชี้ไปฐานข้อมูลจริง)

## Log (Phase 1 — ดู ADR 0011)
- log เป็น JSON บรรทัดละ event ออก stdout ตั้งที่ `app/logging_setup.py`
- ทุก request ได้ `request_id` — รับต่อจาก header `X-Request-Id` ได้ **เฉพาะที่เป็น UUID จริง**
  ค่ามั่วถูกทิ้งแล้วสร้างใหม่ (กันคนนอกปลอม/inject log) และส่งกลับใน response header ด้วย
- ส่งค่าเพิ่มเข้า log ผ่าน `extra={...}` มันจะถูกยกเป็น field ระดับบนสุดเอง
- **`actor` เก็บ `username` ไม่ใช่ชื่อจริง** ลด PII — มีเทสต์ดักว่าชื่อจริงต้องไม่หลุดลง log

## Schema identity (Phase 2 ด่านแรก — ดู ADR 0013)
- **ทุกตารางขึ้นต้น `tdl_`** ตาราง core คือ `tdl_user` / `tdl_category` / `tdl_todo`
  ตารางของ alembic คือ `tdl_alembic_version` — plugin ใช้ `tdl_<ชนิด>_<ไอดี>_*`
  ผลพลอยได้: `user` ไม่ใช่ชื่อตารางอีกแล้ว landmine reserved word ตายถาวร
- ชื่อ constraint/index มาจาก `NAMING_CONVENTION` ใน `app/__init__.py` ไม่ใช่ชื่อ auto
  **แก้รูปแบบนี้ต้องมี migration รองรับ** ไม่งั้น alembic จะ drop constraint ที่ชื่อไม่ตรง
- คอลัมน์ boolean ขึ้นต้น `is_`/`has_` — `Todo.is_done` (เดิมชื่อ `done`)
- model เป็น SQLAlchemy 2.0 typed style ทั้งหมด (`Mapped[]` + `mapped_column`)
  คอลัมน์ที่ nullable ต้องเป็น `Mapped[X | None]` ให้ตรงกับ DB จริง

### env.py: ห้ามแตะ connection ก่อน `context.configure()`
เคยพังมาแล้วตอน Phase 2 — โค้ดที่ `inspect()` หรือ execute บน connection ตัวเดียวกับ
ที่ส่งให้ alembic **ทำให้ migration ทั้งชุดถูก rollback เงียบ ๆ**
log ขึ้น "Running upgrade" ครบทุกตัว exit code เป็น 0 แต่ฐานข้อมูลไม่เปลี่ยนเลย
งานที่ต้องแตะ DB ก่อน configure ให้ใช้ `engine.begin()` เปิด connection ของตัวเอง
`tests/test_migrations.py` เป็นที่เดียวที่รัน migration จริง — **ห้ามลบ**
เทสต์อื่นใช้ `db.create_all()` จึงไม่มีทางจับบั๊กชั้นนี้ได้

## Soft delete และ purge (Phase 2 — ดู ADR 0014)
- **"ลบ" ทั้งระบบแปลว่าซ่อน** ตั้ง `deleted_at` ไม่ใช่ลบแถว
  ห้ามใช้ `db.session.delete()` หรือ `.delete()` แบบ bulk ที่ไหนอีกนอก `app/purge.py`
- **ตัวกรองถูกเติมอัตโนมัติทุก ORM query** ผ่าน event `do_orm_execute` ใน
  `app/soft_delete.py` ไม่ต้องใส่เอง และ**ห้ามพึ่งการใส่เอง** เพราะลืมได้
  งานที่ต้องเห็นของที่ลบแล้วต้องขอด้วย `.execution_options(**INCLUDE_DELETED)`
- **ข้อจำกัดที่ต้องรู้:** ถ้า object ยังอยู่ใน identity map `session.get()` จะคืนตัวนั้น
  โดยไม่ query จึงไม่ถูกกรอง — request จริงไม่เจอเพราะได้ session ใหม่ทุกครั้ง
  แต่ **เทสต์ต้อง `expunge_all()` ไม่ใช่ `expire_all()`**
- `purge-expired` เป็นคำสั่งเดียวที่ลบจริง (`--dry-run` ดูก่อนได้)
  **`--dry-run` ต้องเรียก `preview_expired()` เท่านั้น** ห้ามทำเป็น flag ที่เรียก
  ตัวลบจริงแล้วค่อย rollback — เคยเขียนแบบนั้นแล้ว**ลบข้อมูลจริง** เพราะตัว purge
  commit ไปก่อน savepoint จึงถูกปิดไปแล้ว
- ผู้ใช้ที่ถูก purge **ไม่ถูกลบแถวทิ้ง** เหลือเป็น tombstone (`username` → `#deleted-<id>`)
  ให้ audit อ้าง `actor_id` ได้ ส่วน `password_hash` ถูกล้างทันทีที่ soft delete ไม่รอ grace
- ระยะที่อนุมัติ: soft delete 30 วัน / audit 1 ปี / log 90 วัน (ดู docs/DATA-CLASSIFICATION.md)

## Audit trail (Phase 2 ข้อสุดท้าย — ดู ADR 0015)

- ตาราง `tdl_audit` **เติมได้อย่างเดียว** โค้ดอยู่ที่ `app/audit.py` ไฟล์เดียว
- **ไม่ต้องเรียกอะไรเวลาเขียนฟีเจอร์ใหม่** — event `after_flush` ของ Session ดักทุก
  insert/update/delete ให้เอง ครอบทั้ง route, CLI และสคริปต์
  **ข้อจำกัด:** bulk update/delete ระดับ Core และ raw SQL ไม่ถูกดัก
  (ตอนนี้ระบบไม่มีเหลือแล้ว — เพิ่มใหม่ต้องรู้ตัวว่ามันจะไม่ถูกบันทึก)
- เหตุการณ์ที่ไม่ใช่การเขียน DB (login/logout) เรียก `audit.record()` เอง แล้ว commit
- **ชื่อเหตุการณ์ตามความหมาย ไม่ใช่ตามคำสั่ง SQL** — soft delete เป็น `todo.delete`
  (ไม่ใช่ `todo.update`), คืนค่าเป็น `todo.restore`, ลบจริงเป็น `todo.purge`
- **ค่าที่บันทึกได้ขึ้นกับชั้นข้อมูล** ประกาศไว้ที่ `PLAIN_COLUMNS`/`SECRET_COLUMNS`/
  `HASHED_COLUMNS` ใน `app/audit.py` — **เพิ่มคอลัมน์ใหม่ต้องมาจัดชั้นที่นี่ด้วย**
  (`tests/test_audit.py` บังคับ) ค่าเริ่มต้นตอนรันคือ HMAC = ปิดบังไว้ก่อน
- `actor` เก็บ **`actor_id` เป็นเลข ไม่เก็บ username** และ "ที่ไหน" เก็บ `request_id`
  **ไม่เก็บ IP** เพราะ IP มีอายุ 90 วันตามชั้น C6 เอาไปค้นต่อใน log เอา
- **เวลาในตารางนี้ตัดเศษวินาทีทิ้ง** ห้ามเอา microsecond กลับมา — MySQL ปัดทิ้งเอง
  แล้ว hash ที่คำนวณใหม่จะไม่ตรง (ดู ROADMAP ข้อ 4.5)
- ตรวจสาย: `pipenv run flask audit-verify` / อ่าน: `pipenv run flask audit-log`
- **แก้/ลบแถว audit ผ่าน ORM ไม่ได้** ด่านอยู่ที่ `before_flush` — purge job ต้องขอ
  สิทธิ์ด้วย `allow_purge()` แล้วคืนด้วย `finish_purge()` ทันที
- **purge audit ตัดได้จากหัวสายเท่านั้น** (`_expired_audit` หยุดที่แถวแรกที่ยังไม่หมดอายุ)
  ห้ามเปลี่ยนเป็น `WHERE created_at < cutoff` เฉย ๆ — นาฬิกาที่ถูกปรับย้อนหลังจะทำให้
  เจาะรูกลางสายแล้ว verify ไม่ผ่านตลอดกาล
- **checkpoint ต้องเขียนก่อนลบเสมอ** ไม่งั้นตอนล้างทั้งตารางมันจะหาแถวก่อนหน้าไม่เจอ
  แล้วตั้งต้นที่ genesis — สายยัง "ผ่าน" แต่ไม่ผูกกับประวัติที่มันอ้างว่าแทนอีกต่อไป

## Foreign key (Phase 2)
- **SQLite ปิดการบังคับ FK เป็นค่าเริ่มต้น และเป็นค่าต่อ connection** ไม่ใช่ต่อไฟล์
  `app/db_engine.py` ผูก listener ที่คลาส `Engine` เปิดให้ทุก connection
- **`app/__init__.py` ต้อง import `db_engine` ไว้เสมอ** เป็น import เพื่อผลข้างเคียง
  ลบทิ้งแล้ว FK เลิกถูกบังคับโดยไม่มี error อะไรให้เห็น
  ผลคือลบหมวดแล้วงานจะเหลือ `category_id` ชี้ไปแถวที่ไม่มีอยู่ — ข้อมูลเสียแบบเงียบ
- `tests/test_db_integrity.py` วัด **ผล** ของการบังคับ (insert ที่ผิดต้อง IntegrityError,
  `ondelete="SET NULL"` ต้องทำงานจริง) ไม่ใช่แค่ค่า pragma — ห้ามลด assert เหลือแค่อ่าน pragma
- batch migration ของ alembic กับ FK เปิดอยู่ ทดสอบแล้วว่าไป-กลับได้ข้อมูลครบ
  และ `PRAGMA foreign_key_check` สะอาด — แต่ migration ใหม่ที่ย้ายข้อมูลควรตรวจซ้ำทุกครั้ง

## วินัย dialect (มีผลทันที — เตรียมรองรับ DB หลายยี่ห้อ ดู ROADMAP ข้อ 4)
- raw SQL ใน migration ต้อง quote ตารางที่เป็น reserved word — โดยเฉพาะ `"user"`
  (reserved ใน PostgreSQL/Oracle/MSSQL — migration เก่า 3 จุดปล่อยไว้ จะล้างด้วย
  baseline squash ตอน Phase 5 อย่าเพิ่มจุดใหม่)
  **ตารางปัจจุบันไม่มีชื่อนี้แล้ว** หลังใส่ prefix `tdl_` — เหลือแค่ใน migration เก่า
- ห้ามเทียบ DATETIME แบบ exact ข้าม insert — MySQL default ตัด microsecond
- คอลัมน์ String ระบุความยาวเสมอ (MySQL บังคับ) — ตอนนี้ครบทุกคอลัมน์แล้ว

## แผนระยะยาว
- มาตรฐาน/เครื่องมือที่ตัดสินแล้ว (naming, prefix `tdl_`, ruff/mypy/semgrep ฯลฯ)
  อยู่ใน `docs/STANDARDS.md` — verdict ข้อ 4 บอกว่าอะไรเข้าเฟสไหน
- **การจำแนกชั้นข้อมูลและระยะเก็บรักษาอยู่ใน `docs/DATA-CLASSIFICATION.md`**
  เพิ่มคอลัมน์ใหม่ต้องระบุชั้นในเอกสารนั้นด้วย (`tests/test_data_classification.py` บังคับ)
  กติกาที่มีผลกับโค้ด: **audit ห้ามเก็บค่าของ C1/C2/C3** เก็บได้แค่ชื่อคอลัมน์ + HMAC
  และ `password_hash` ห้ามออกจากระบบทุกกรณีแม้แต่ในรูป hash (ดู ADR 0014)
- แผนแม่บท (ISO/IEC 25010:2023 + audit/data governance) อยู่ใน `docs/ROADMAP.md`
  เรียงเป็นเฟสตามหลักลด rework — **ก่อนเริ่มฟีเจอร์ใหม่ให้เช็คว่าอยู่เฟสไหนของแผน**

## ยังไม่ได้ทำ
- หน้า login ไม่รองรับ `?next=` โดยตั้งใจ (กัน open redirect) login เสร็จเด้งไปหน้าแรกเสมอ
- ยังไม่กันตาม username — คนเดารหัสที่เปลี่ยน IP ไปเรื่อย ๆ ยังไล่เดาได้
