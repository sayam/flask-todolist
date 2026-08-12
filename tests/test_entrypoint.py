"""`run.py` เป็นจุดเข้าของ WSGI server และต้องไม่รันเซิร์ฟเวอร์เอง

เดิมไฟล์นี้ลงท้ายด้วย `if __name__ == "__main__": app.run(debug=True)` ซึ่งเป็น
ปืนที่ขึ้นนกไว้: `python run.py` บนเครื่องที่ไม่ใช่เครื่อง dev เปิด Werkzeug
debugger ซึ่ง **รันโค้ดอะไรก็ได้ผ่านหน้าเว็บ** · ไฟล์นี้ถูกก๊อปเข้า image ด้วย
(`Dockerfile`) จึงอยู่บนเครื่องที่รันจริงทุกเครื่อง

ถอดออกตอนเปิด repo สู่สาธารณะ (CodeQL `py/flask-debug`) และมันไม่เคยจำเป็น
เพราะวิธีรัน dev ที่เอกสารทุกฉบับบอกคือ `flask run --debug` ซึ่งเปิด debugger
เฉพาะเมื่อคนพิมพ์สั่งเอง

ที่นี่ตรวจ **ตัวไฟล์** ไม่ใช่พฤติกรรมตอน import เพราะบล็อก `__main__` ไม่ทำงาน
ตอน import อยู่แล้ว — เทสต์ที่ import แล้วบอกว่า "ไม่เห็นมันรัน" จะเขียวตลอด
ไม่ว่าบล็อกนั้นจะอยู่หรือไม่ (หลักเดียวกับที่ `tests/test_security_headers.py`
อ่านไฟล์ template ตรง ๆ เพื่อหา inline handler)
"""

import ast
import pathlib

ENTRYPOINT = pathlib.Path(__file__).resolve().parent.parent / "run.py"


def _tree() -> ast.Module:
    return ast.parse(ENTRYPOINT.read_text(encoding="utf-8"))


def test_the_entrypoint_exists_and_exposes_app():
    """`gunicorn ... run:app` พังเงียบ ๆ ถ้าชื่อนี้หายไป"""
    assigned = {
        target.id
        for node in _tree().body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assert "app" in assigned, "run.py ต้องมีตัวแปรชื่อ `app` — Dockerfile เรียก `run:app`"


def test_the_entrypoint_never_starts_a_server_itself():
    """`app.run(...)` ในไฟล์นี้แปลว่ามีทางรันเซิร์ฟเวอร์ที่ไม่ได้ผ่าน gunicorn"""
    calls = [
        node
        for node in ast.walk(_tree())
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
    ]
    assert not calls, (
        "run.py เรียก .run() เอง — `python run.py` จะยกเซิร์ฟเวอร์ขึ้นมานอกทางที่ตั้งใจ "
        "และถ้ามี debug=True ด้วยก็เท่ากับเปิด Werkzeug debugger ให้คนนอก"
    )


def test_the_entrypoint_has_no_debug_switch_anywhere():
    """กันทางอ้อม เช่น `app.debug = True` หรือส่ง debug ไปทางอื่น"""
    source = ENTRYPOINT.read_text(encoding="utf-8")
    code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
    # docstring ของไฟล์อธิบายว่าทำไมถึงไม่มี — ตัดออกก่อนค้นหา ไม่งั้นจับคำอธิบายตัวเอง
    body = ast.parse(source).body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        code = code.replace(str(body[0].value.value), "")

    for forbidden in ("debug=True", "debug = True", "DEBUG=True", "use_reloader"):
        assert forbidden not in code, f"run.py มี {forbidden!r} ซึ่งไม่ควรมี"
