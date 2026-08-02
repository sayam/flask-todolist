# Todolist

แอปจดงานส่วนตัวเขียนด้วย Flask — มีระบบ login, จัดหมวดงาน และแก้ไขงานได้

## ความสามารถ

- เพิ่ม / แก้ไข / ติ๊กว่าเสร็จ / ลบงาน
- ลบงานที่เสร็จแล้วทั้งหมดในคลิกเดียว
- จัดหมวดงานเองได้ (เพิ่ม/แก้/ลบ)
- ระบุวันเริ่มและกำหนดส่งได้ถึงระดับเวลา เรียงงานที่ใกล้ครบกำหนดขึ้นก่อน
- กรองตามวันครบกำหนด — ใกล้ถึงกำหนด (15/30/45 นาที หรือ 8 ชม.), วันนี้, พรุ่งนี้ หรือเลือกช่วงเอง
- กรองตามสถานะ (ทั้งหมด / ยังไม่เสร็จ / เสร็จแล้ว) และตามหมวด ใช้ร่วมกันได้
- ข้อมูลแยกตาม user ใครเห็นแต่ของตัวเอง
- รองรับ 2 ภาษา — English (ค่าเริ่มต้น) และไทย สลับได้จากเมนู จำภาษาที่เลือกไว้ให้
- โหมดสว่าง/มืด/อัตโนมัติ — อัตโนมัติสลับตามเวลาดวงอาทิตย์ขึ้น-ตกของเขตเวลาที่ตั้งไว้
  (ตารางเวลาครบทุกเขตเวลาฝังมากับแอป ไม่ต้องต่อเน็ตหรือใช้ JS)
- หน้า Settings รวมโปรไฟล์ (ชื่อ-นามสกุล), ภาษา, ธีม, โหมด และเขตเวลาไว้ที่เดียว
- ลบหมวดได้เฉพาะตอนไม่มีงานอยู่ในหมวดนั้นแล้ว
- กำหนดส่งเก็บเป็น UTC แล้วแสดงตามเขตเวลาที่ผู้ใช้ตั้งไว้

## Stack

- Python 3.13, Flask, Flask-SQLAlchemy, SQLite
- Flask-Migrate (alembic) — จัดการ schema
- Flask-Login — session
- Flask-WTF — CSRF
- Flask-Limiter — จำกัดจำนวนครั้งที่หน้า login
- Flask-Babel — แปลภาษา (gettext)
- pipenv — จัดการ dependency

## ติดตั้ง

```bash
git clone git@github.com:sayam/flask-todolist.git
cd flask-todolist
pipenv install
```

ตั้งค่า `SECRET_KEY` (ไม่มีค่า default โดยตั้งใจ — ไม่ตั้งแล้วแอปจะไม่ start):

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(32))"
# เอาค่าที่ได้ไปใส่หลัง SECRET_KEY= ใน .env
```

สร้างฐานข้อมูลและ user แรก:

```bash
pipenv run flask db upgrade
pipenv run flask create-user <ชื่อผู้ใช้>
```

คำสั่ง `create-user` จะถามรหัสผ่าน (ยาวอย่างน้อย 8 ตัว) และสร้างหมวดตั้งต้นให้ 2 หมวด
ใส่ `--no-categories` ถ้าไม่ต้องการ

> ต้องรันในเทอร์มินัลจริง เพราะคำสั่งนี้ถามรหัสผ่านแบบซ่อนจอ

## รัน

```bash
pipenv run flask run --debug
```

เปิด http://127.0.0.1:5000 แล้วล็อกอิน

## เทสต์

```bash
pipenv run pytest -v
```

192 tests ครอบคลุมงาน/หมวด, การแยกข้อมูลระหว่าง user, CSRF, rate limit,
การตรวจ `SECRET_KEY`, การเลือกภาษา, ธีม/โหมด, เขตเวลา, settings และ CLI

## คำสั่ง CLI

| คำสั่ง | ทำอะไร |
|---|---|
| `flask create-user <ชื่อ> [--lang en\|th]` | สร้าง user ใหม่ พร้อมหมวดตั้งต้นตามภาษา |
| `flask list-users` | ดูรายชื่อ user |
| `flask delete-user <ชื่อ>` | ลบ user พร้อมหมวดและงานทั้งหมด |
| `flask db migrate -m "..."` | สร้าง migration หลังแก้ model |
| `flask db upgrade` | อัปเดต schema |

## ความปลอดภัย

- **ไม่มีหน้าสมัครสมาชิก** โดยตั้งใจ — สร้าง user ผ่าน CLI เท่านั้น
- รหัสผ่าน hash ด้วย scrypt (werkzeug)
- ทุก route ต้อง login และ query filter ด้วย `user_id` เสมอ
  แตะข้อมูลของคนอื่นได้ 404 (ไม่ใช่ 403) เพื่อไม่ให้รู้ว่า id นั้นมีจริง
- CSRF token ครบทุก form
- หน้า login จำกัด 5 ครั้ง/นาที และ 20 ครั้ง/ชม. ต่อ IP นับเฉพาะครั้งที่ล็อกอินพลาด
- `SECRET_KEY` ต้องมาจาก env และยาว ≥ 32 ตัว ไม่มี fallback

ข้อจำกัดที่รู้อยู่:

- rate limit เก็บสถานะใน memory ของ process เดียว ถ้ารันหลาย worker ต้องเปลี่ยนไปใช้ Redis
- ยังไม่กัน brute force ตาม username คนที่เปลี่ยน IP ไปเรื่อย ๆ ยังไล่เดาได้
- ใช้ Flask dev server ถ้าจะเอาขึ้นจริงต้องมี WSGI server (gunicorn ฯลฯ)

## แปลภาษา

ข้อความในโค้ดเป็นภาษาอังกฤษ ส่วนคำแปลอยู่ใน `app/translations/`
แก้คำแปลแล้วต้อง compile ใหม่:

```bash
pipenv run pybabel compile -d app/translations
```

เพิ่มข้อความใหม่ในโค้ด แล้วอัปเดต catalog:

```bash
pipenv run pybabel extract -F babel.cfg -k _l -k _ -k ngettext:1,2 -o messages.pot .
pipenv run pybabel update -i messages.pot -d app/translations
```

## โครงสร้าง

```
app/
  __init__.py    app factory + init extension ทั้งหมด
  models.py      User, Category, Todo
  routes.py      งานและหมวด (blueprint `main`)
  auth.py        login/logout (blueprint `auth`)
  cli.py         คำสั่ง flask CLI
  templates/     Jinja2 (ทุกหน้า extend base.html)
  static/        โลโก้ SVG 2 ขนาด + style.css
  translations/  คำแปล gettext (en, th)
  i18n.py        ตรรกะเลือกภาษาของแต่ละ request
  theme.py       ตรรกะเลือกชุดสีและโหมดของแต่ละ request
  sun_data.py    ตารางเวลาดวงอาทิตย์ (สร้างจาก scripts/)
  tz.py          แปลงเวลา UTC ↔ เวลาท้องถิ่นของผู้ใช้
migrations/      alembic
tests/
```

รายละเอียดสำหรับคนที่จะแก้โค้ดต่ออยู่ใน [CLAUDE.md](CLAUDE.md)
