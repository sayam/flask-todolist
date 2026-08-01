# Todolist (Flask)

## Stack
- Flask + Flask-SQLAlchemy, SQLite (dev), pipenv จัดการ env
- Python 3.13

## Commands
- รัน dev server: `pipenv run flask run --debug`
- รัน test: `pipenv run pytest -v`
- เพิ่ม dependency: `pipenv install <pkg>` (ห้ามใช้ `pip install` ตรง ๆ — Pipfile/Pipfile.lock จะไม่ sync)

## Structure
- `app/__init__.py` — app factory (`create_app`)
- `app/models.py` — SQLAlchemy models
- `app/routes.py` — view functions, ผูกกับ blueprint `main`
- `app/templates/` — Jinja2 templates
- `tests/` — pytest, ใช้ fixture `client`/`app` จาก `conftest.py`

## Conventions
- Route คืน `render_template`/`redirect` เท่านั้น ไม่คืน raw string
- Query `Todo` model นอก request ต้องอยู่ใน `with app.app_context():`
- ยังไม่มี migration tool (Flask-Migrate) — เปลี่ยน schema ช่วง dev ให้ลบ `instance/todolist.db` แล้วปล่อยให้ `db.create_all()` สร้างใหม่
