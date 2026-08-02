# Todolist (Flask)

## Stack
- Flask + Flask-SQLAlchemy, SQLite (dev), pipenv จัดการ env
- Flask-Migrate (alembic) จัดการ schema, Flask-Login จัดการ session, Flask-WTF จัดการ CSRF,
  Flask-Limiter จำกัดจำนวนครั้งที่หน้า login
- Python 3.13

## Commands
- รัน dev server: `pipenv run flask run --debug`
- รัน test: `pipenv run pytest -v`
- เพิ่ม dependency: `pipenv install <pkg>` (ห้ามใช้ `pip install` ตรง ๆ — Pipfile/Pipfile.lock จะไม่ sync)
- สร้าง user: `pipenv run flask create-user <ชื่อ>` (ไม่มีหน้าสมัครสมาชิก โดยตั้งใจ)
- ดู user: `pipenv run flask list-users`
- เปลี่ยน schema: `pipenv run flask db migrate -m "..."` แล้ว `pipenv run flask db upgrade`

## Structure
- `app/__init__.py` — app factory (`create_app`), init db/migrate/csrf/limiter/login_manager
  และ errorhandler ของ 429
- `app/models.py` — SQLAlchemy models (`User`, `Category`, `Todo`)
- `app/routes.py` — view functions ของงาน/หมวด/ตั้งค่า ผูกกับ blueprint `main`
- `app/auth.py` — login/logout ผูกกับ blueprint `auth`
- `app/cli.py` — custom flask CLI commands
- `app/tz.py` — แปลงเวลา UTC ↔ เวลาท้องถิ่นของผู้ใช้
- `app/theme.py` — เลือกชุดสีและโหมด, `app/sun_data.py` — ตารางดวงอาทิตย์ (generate)
- `scripts/` — สคริปต์ที่รันมือ ไม่ได้ถูกเรียกตอนแอปทำงาน
- `app/templates/` — Jinja2 templates (ทุกหน้า extend `base.html`)
- `app/static/` — `logo.svg` (120px ใช้หน้า login) และ `logo-small.svg` (32px ใช้บน header + favicon)
  ตัวเล็กไม่ใช่ตัวใหญ่ย่อลงมา แต่ตัดรายละเอียดออกให้เหลือแค่เครื่องหมายถูก
- `migrations/` — alembic migration scripts (commit ลง git ด้วย)
- `tests/` — pytest, fixture จาก `conftest.py`

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
- แทรกค่าลง JS ใน template ต้องใช้ `|tojson` ไม่ใช่ `{{ }}` เปล่า ๆ เช่นใน `onsubmit="return confirm(...)"`
- **ตั้งชื่องาน/หมวดในเทสต์อย่าให้ตรงกับข้อความบน UI** เช่น "ยังไม่เสร็จ"/"เสร็จแล้ว"
  เป็น label ของลิงก์ตัวกรองที่อยู่ในหน้าเสมอ `assert ... not in resp.data` จะพังทันที
- **ทุก `<form method="post">` ต้องมี `{{ csrf_field() }}` หรือ hidden input `csrf_token`**
  `CSRFProtect` คุมทั้งแอป ลืมใส่แล้ว form นั้นจะได้ 400 ทันที
- เทสต์ทั่วไปปิด CSRF (`WTF_CSRF_ENABLED = False` ใน `TestConfig`) ตัว CSRF มีเทสต์แยกใน
  `tests/test_csrf.py` ที่เปิดใช้จริงผ่าน fixture `csrf_app` — ห้ามลบไฟล์นั้นทิ้ง
  ไม่งั้นจะไม่มีอะไรจับได้เวลา `csrf.init_app()` หลุด

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

## ธีมกับโหมด (สว่าง/มืด/อัตโนมัติ)

แยกสองแกน อย่าเอามาปนกัน:
- **theme** = ชื่อชุดสี ประกาศใน `config.THEMES` ตอนนี้มีชุดเดียวชื่อ `system`
- **mode** = ระดับความสว่าง `light` / `dark` / `auto` ค่าเริ่มต้นคือ `auto`

- `User.theme` เก็บชื่อชุดสี ส่วน `User.mode` เก็บระดับความสว่าง
  **`auto` เก็บเป็นสตริง `'auto'` ไม่ใช่ NULL** (ต่างจาก `locale`/`timezone_name`
  ที่ NULL แปลว่ายังไม่เลือก) เพราะ auto เป็นตัวเลือกจริงที่ผู้ใช้ตั้งใจเลือก
- ลำดับเหมือนภาษา: `?mode=` → session → `User.mode` → `auto` (ดู `app/theme.py`)
- **โหมด "ตามระบบ" (`prefers-color-scheme`) ถูกตัดทิ้งแล้ว** server ตัดสินโหมด
  มาให้เสมอและส่งเป็น `data-theme="light|dark"` บน `<html>`
  CSS จึงมีบล็อกธีมมืดที่เดียว ไม่ต้อง `@media` และไม่มีการประกาศสีซ้ำอีก
- `app/static/style.css` สีทั้งหมดอยู่ใน CSS custom property
  **ห้ามใส่สีดิบนอกบล็อกนิยามธีม** — `tests/test_theme.py` ดักไว้

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

## ยังไม่ได้ทำ
- หน้า login ไม่รองรับ `?next=` โดยตั้งใจ (กัน open redirect) login เสร็จเด้งไปหน้าแรกเสมอ
- ยังไม่กันตาม username — คนเดารหัสที่เปลี่ยน IP ไปเรื่อย ๆ ยังไล่เดาได้
