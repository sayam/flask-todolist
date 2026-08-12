"""จุดเข้าของ WSGI server — `gunicorn ... run:app` (ดู Dockerfile)

**ไม่มี `if __name__ == "__main__": app.run(debug=True)` โดยตั้งใจ**
บล็อกนั้นเคยอยู่ตรงนี้และถูกถอดออกตอนเปิด repo สู่สาธารณะ (CodeQL `py/flask-debug`)
เพราะมันเป็นปืนที่ขึ้นนกไว้: `python run.py` บนเครื่องที่ไม่ใช่เครื่อง dev เปิด
Werkzeug debugger ซึ่งรันโค้ดอะไรก็ได้ผ่านหน้าเว็บ · มันไม่เคยจำเป็นด้วย เพราะ
วิธีรัน dev ที่เอกสารทุกฉบับบอกคือ `pipenv run flask run --debug` ซึ่งเปิด
debugger เฉพาะเมื่อ**คนพิมพ์สั่งเอง** ไม่ใช่เพราะเผลอเรียกไฟล์ผิดตัว
"""

from app import create_app

app = create_app()
