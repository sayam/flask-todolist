# Todolist (Flask)

## Stack
- Flask + Flask-SQLAlchemy, SQLite (dev), pipenv จัดการ env
- Flask-Migrate (alembic) จัดการ schema, Flask-Login จัดการ session
- Python 3.13

## Commands
- รัน dev server: `pipenv run flask run --debug`
- รัน test: `pipenv run pytest -v`
- เพิ่ม dependency: `pipenv install <pkg>` (ห้ามใช้ `pip install` ตรง ๆ — Pipfile/Pipfile.lock จะไม่ sync)
- สร้าง user: `pipenv run flask create-user <ชื่อ>` (ไม่มีหน้าสมัครสมาชิก โดยตั้งใจ)
- ดู user: `pipenv run flask list-users`
- เปลี่ยน schema: `pipenv run flask db migrate -m "..."` แล้ว `pipenv run flask db upgrade`

## Structure
- `app/__init__.py` — app factory (`create_app`), init db/migrate/login_manager
- `app/models.py` — SQLAlchemy models (`User`, `Category`, `Todo`)
- `app/routes.py` — view functions ของงาน/หมวด ผูกกับ blueprint `main`
- `app/auth.py` — login/logout ผูกกับ blueprint `auth`
- `app/cli.py` — custom flask CLI commands
- `app/templates/` — Jinja2 templates (ทุกหน้า extend `base.html`)
- `migrations/` — alembic migration scripts (commit ลง git ด้วย)
- `tests/` — pytest, fixture จาก `conftest.py`

## Conventions
- Route คืน `render_template`/`redirect` เท่านั้น ไม่คืน raw string
- Query model นอก request ต้องอยู่ใน `with app.app_context():`
- **ทุก route ต้องมี `@login_required`** และ query ต้อง filter ด้วย `user_id=current_user.id` เสมอ
- ห้ามใช้ `db.get_or_404()` กับข้อมูลที่มีเจ้าของ — ใช้ `_owned_todo()`/`_owned_category()` ใน `routes.py`
  ซึ่งตอบ 404 (ไม่ใช่ 403) เมื่อเป็นของคนอื่น เพื่อไม่ให้รู้ว่า id นั้นมีจริง
- `create_app` **ไม่เรียก** `db.create_all()` แล้ว — schema มาจาก migration เท่านั้น
  (เทสต์สร้างตารางเองใน fixture `app`)
- แทรกค่าลง JS ใน template ต้องใช้ `|tojson` ไม่ใช่ `{{ }}` เปล่า ๆ เช่นใน `onsubmit="return confirm(...)"`

## ยังไม่ได้ทำ
- CSRF protection (Flask-WTF) — form ทั้งหมดยังไม่มี token
- หน้า login ไม่รองรับ `?next=` โดยตั้งใจ (กัน open redirect) login เสร็จเด้งไปหน้าแรกเสมอ
