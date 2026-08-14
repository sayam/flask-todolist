"""ตรวจข้อ ASVS ที่ *ตรวจอัตโนมัติได้* บนแอป Flask เล็ก ๆ ที่ถูก generate มา

ใช้ในการทดลองเฟส 12 เท่านั้น — **ไม่ใช่การประเมิน ASVS เต็มรูป** (ของจริงอยู่ใน
`docs/ASVS.md` 253 ข้อ ประเมินด้วยคน) ที่นี่คือ 10 ข้อที่พิสูจน์ได้จากตัวไฟล์
โดยไม่ต้องรันแอป เลือกจากข้อที่ **ผิดแล้วเป็นช่องโหว่จริง** ไม่ใช่ข้อที่วัดง่าย

สามค่าเท่านั้น ต่อหนึ่งข้อ:

- `True` — เจอหลักฐานว่าทำ
- `False` — มีของให้ตรวจ แต่ไม่เจอหลักฐาน (หรือเจอหลักฐานว่าทำผิด)
- `None` — **ไม่เกี่ยวข้อง** เพราะแอปไม่มีส่วนนั้นเลย · ไม่นับเป็นผ่านและ
  ไม่นับเป็นไม่ผ่าน — เหมือน `NA:` ของ scan ใน overlay (ADR 0039)

**ข้อจำกัดที่ต้องพูดพร้อมตัวเลขเสมอ**: นี่คือ heuristic บนข้อความ+AST มันตอบ
"มีร่องรอยของการป้องกันไหม" ไม่ใช่ "การป้องกันนั้นทำงานจริงไหม" — ตัวมันเอง
ถูกตรวจสองทิศด้วย fixture คู่ใน `tests/test_asvs_probe.py` (สกปรกต้องตก
สะอาดต้องผ่าน) ตามวินัยเดียวกับด่านอื่นของ repo นี้
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pathlib

# ข้อที่ตรวจ → คำอธิบายสั้น (ใช้พิมพ์ในรายงาน)
CHECKS = {
    "V6.2.2-password-hashing": "รหัสผ่านถูก hash ด้วยฟังก์ชันที่ออกแบบมาเพื่อรหัสผ่าน",
    "V2.1.1-password-min-length": "บังคับความยาวขั้นต่ำของรหัสผ่านตอนสมัคร",
    "V3.4.1-cookie-flags": "คุกกี้ session ประกาศ SameSite/Secure/HttpOnly เอง",
    "V4.2.2-csrf": "คำขอที่เปลี่ยนสถานะมีด่าน CSRF",
    "V4.1.1-ownership-filter": "การหาแถวตาม id ถูกจำกัดด้วยเจ้าของเสมอ",
    "V5.3.3-output-escaping": "ไม่มีการปิด escape ของ template",
    "V5.3.4-no-sql-string-building": "ไม่มี SQL ที่ต่อสตริงจาก input",
    "V6.4.1-secret-not-hardcoded": "SECRET_KEY ไม่ได้ฝังค่าไว้ในโค้ด",
    "V13.2.1-api-requires-auth": "endpoint ของ API บังคับตัวตน",
    "V14.1.3-no-debug-console": "ไม่มีทางเปิด debug console",
}

HASHERS = ("generate_password_hash", "bcrypt", "argon2", "scrypt", "pbkdf2")


def _is_test(path: pathlib.Path) -> bool:
    """ไฟล์เทสต์ไม่ใช่โค้ดที่รันในโปรดักชัน

    ต้องตัดออก ไม่งั้นข้อ "ความลับห้ามฝังในโค้ด" จะลงโทษฝั่งที่เขียนเทสต์
    (fixture ตั้ง `SECRET_KEY = "x" * 48` เป็นเรื่องปกติและถูกต้อง) — เจอจริง
    ตอนวัดรอบแรก: ฝั่งที่มีชุดเทสต์ตกข้อนี้ทั้งที่ config ของแอปไม่มี default เลย
    """
    return path.name.startswith("test_") or path.name == "conftest.py" or "tests" in path.parts


def _python_files(root: pathlib.Path) -> list[pathlib.Path]:
    """โค้ดของแอปเท่านั้น — ไม่รวมไฟล์เทสต์และของที่ build มา"""
    return [
        p for p in sorted(root.rglob("*.py")) if "__pycache__" not in p.parts and not _is_test(p)
    ]


def _templates(root: pathlib.Path) -> list[pathlib.Path]:
    """เทมเพลตทุกไฟล์ (ที่ไหนก็ได้ในโปรเจกต์ — โครงต่างกันได้)"""
    return sorted(root.rglob("*.html"))


def _read(paths: list[pathlib.Path]) -> str:
    """ต่อเนื้อไฟล์ทั้งหมดเป็นก้อนเดียวสำหรับข้อที่ตรวจแบบข้อความ"""
    return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in paths)


def _functions(code: str) -> list[ast.FunctionDef]:
    """ฟังก์ชันทุกตัวในไฟล์ — syntax พังก็ข้ามไป ไม่ใช่ล้มทั้งการวัด"""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    return [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]


#: การหาแถวจากฐานข้อมูลด้วย id — **ไม่รวม `session.get(...)` เปล่า ๆ**
#: ซึ่งคือการอ่าน session ของ Flask คนละเรื่องกันโดยสิ้นเชิง (probe รอบแรก
#: จับผิดตัวนี้แล้วรายงานว่าทุกแอปที่มี session timeout ลืมตรวจความเป็นเจ้าของ)
DB_LOOKUP = re.compile(r"db\.session\.get\(|\.query\.get\(|get_or_404\(")

OWNER_WORDS = ("user_id", "current_user", "owner")


def _mentions_owner(body: str) -> bool:
    """โค้ดก้อนนี้พูดถึงความเป็นเจ้าของไหม (ไม่ตัดสินว่าใช้ถูกหรือไม่)"""
    return any(word in body for word in OWNER_WORDS)


def _ownership(py_files: list[pathlib.Path]) -> bool | None:
    """การหาแถวตาม id ต้องมีการตรวจเจ้าของ — ในฟังก์ชันนั้น หรือที่ผู้เรียกทุกราย

    ไม่พยายามพิสูจน์ว่ากรองถูก — พิสูจน์แค่ว่า *ไม่ได้ลืมนึกถึง*

    **helper กลางต้องไม่ถูกลงโทษ**: `lookup.by_id(model, raw_id)` ที่รับ model
    เป็นพารามิเตอร์ ไม่มีทางรู้จักเจ้าของได้ตามนิยาม — ความเป็นเจ้าของถูกตรวจที่
    ผู้เรียก (`note.user_id != user_id`) ซึ่งเป็นโครงที่ *ดีกว่า* การหาแถวกระจาย
    ทั่วโค้ด · ถ้า probe นับว่าตก มันจะให้คะแนนสำนวนที่แย่กว่าสูงกว่า
    """
    helpers: set[str] = set()
    offenders: list[str] = []
    seen_any = False

    for path in py_files:
        code = path.read_text(encoding="utf-8", errors="replace")
        for func in _functions(code):
            body = ast.get_source_segment(code, func) or ""
            if not DB_LOOKUP.search(body):
                continue
            seen_any = True
            if _mentions_owner(body):
                continue
            parameters = {arg.arg for arg in func.args.args}
            generic = any(
                isinstance(node, ast.Call)
                and node.args
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id in parameters
                for node in ast.walk(func)
            )
            if generic:
                helpers.add(func.name)
            else:
                offenders.append(func.name)

    if offenders:
        return False
    if not seen_any:
        return None
    return all(_helper_callers_check_ownership(name, py_files) for name in helpers)


def _helper_callers_check_ownership(helper: str, py_files: list[pathlib.Path]) -> bool:
    """ผู้เรียก helper ทุกรายต้องตรวจเจ้าของ — ไม่มีผู้เรียกเลยก็ถือว่าไม่ผ่าน"""
    callers = 0
    for path in py_files:
        code = path.read_text(encoding="utf-8", errors="replace")
        for func in _functions(code):
            # นิยามของ helper เองไม่ใช่ผู้เรียก — บรรทัด `def by_id(...)` เข้าเงื่อนไข
            # ของ regex ด้วย ถ้าไม่ตัดออก helper จะถูกนับว่าเรียกตัวเองโดยไม่ตรวจเจ้าของ
            if func.name == helper:
                continue
            body = ast.get_source_segment(code, func) or ""
            if not re.search(rf"\b{re.escape(helper)}\(", body):
                continue
            callers += 1
            if not _mentions_owner(body):
                return False
    return callers > 0


def _password_length(py_files: list[pathlib.Path]) -> bool:
    """สามสำนวนที่พบจริง: เทียบตรง ๆ · เทียบกับค่าคงที่ · validator ของฟอร์ม

    `Length(min=...)` ต้องอยู่ใน**ไฟล์เดียวกัน**กับคำว่า password และห่างไม่เกิน
    ไม่กี่บรรทัด ไม่งั้นข้อนี้จะผ่านเพราะแอปบังคับความยาว *ชื่อผู้ใช้* ซึ่งเป็นคนละ
    เรื่องกับ ASVS V2.1.1 (ดูฟิลด์ที่กางหลายบรรทัด — validator อยู่ห่างจากชื่อฟิลด์)
    """
    for path in py_files:
        code = path.read_text(encoding="utf-8", errors="replace")
        # ชื่อตัวแปรไม่จำเป็นต้องมีคำว่า password — โมดูลที่ชื่อ passwords.py
        # เขียน `len(candidate) < MIN_LENGTH` ซึ่งเป็นการบังคับความยาวเต็มตัว
        about_passwords = "password" in path.name.lower() or "password" in code.lower()
        if about_passwords and re.search(r"len\(\s*\w+\s*\)\s*[<>]=?\s*\w+", code):
            return True
        lines = code.splitlines()
        for number, line in enumerate(lines):
            if not re.search(r"Length\(\s*min\s*=\s*\d+", line):
                continue
            window = "\n".join(lines[max(0, number - 6) : number + 3]).lower()
            if "password" in window:
                return True
    return False


#: วิธีวาง token ที่ถูกต้องเท่ากันหมด — token ดิบ, macro ของโปรเจกต์, หรือ
#: `hidden_tag()` ของ Flask-WTF · probe ที่รู้จักสำนวนเดียวจะบอกว่าแอปที่ใช้
#: macro "ไม่มี CSRF" ทั้งที่ทุกฟอร์มมีครบ (เจอจริงตอนวัดรอบแรก)
CSRF_IN_TEMPLATE = ("csrf_token", "csrf_field(", "hidden_tag(")


def _csrf(py_text: str, template_text: str) -> bool | None:
    """ไม่มีฟอร์ม POST เลย = ไม่เกี่ยวข้อง · มีแล้วต้องมีด่าน ไม่ใช่แค่ import"""
    if 'method="post"' not in template_text.lower():
        return None
    protected = "CSRFProtect(" in py_text or "csrf.init_app" in py_text
    return protected and any(mark in template_text for mark in CSRF_IN_TEMPLATE)


def _decorator_names(func: ast.FunctionDef) -> set[str]:
    """ชื่อ decorator ทั้งหมดของฟังก์ชัน

    ต้องอ่านจาก AST เพราะ `ast.get_source_segment()` ของ FunctionDef
    **ไม่รวมบรรทัด decorator** — view ที่ป้องกันด้วย `@login_required` แล้วส่ง
    งานต่อให้ helper (จึงไม่มีคำว่า `current_user` ในตัวมันเอง) จะถูกตัดสินว่า
    "ไม่มีด่าน" ทั้งที่มีด่านอยู่บรรทัดบน — เป็นการลงโทษการแยกหน้าที่อีกครั้ง
    """
    names = set()
    for decorator in func.decorator_list:
        node = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def _route_paths(func: ast.FunctionDef) -> list[str]:
    """path ที่ decorator ของ view ตัวนี้ประกาศไว้ (อ่านจาก AST ไม่ใช่จากข้อความ)"""
    return [
        arg.value
        for decorator in func.decorator_list
        if isinstance(decorator, ast.Call)
        for arg in decorator.args
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
    ]


def _api_auth(py_files: list[pathlib.Path]) -> bool | None:
    """view ที่ผูกกับ path `/api/` ต้องมี login_required หรือเช็ค current_user เอง

    ไม่มี view ของ API เลย = ไม่เกี่ยวข้อง · มีตัวไหนไม่มีด่านเลย = ตกทั้งข้อ
    (ด่านที่ครอบแค่บาง endpoint ไม่ใช่ด่าน)

    **path ของ view เดี่ยว ๆ ไม่พอ** — สำนวนที่พบบ่อยกว่าคือ blueprint ที่ตั้ง
    `url_prefix="/api"` แล้ว route ข้างในเขียนแค่ `/notes` · probe รอบแรกจึง
    รายงาน "ไม่เกี่ยวข้อง" ให้แอปที่มี API ครบทุกตัว (จุดบอดของตัววัด ไม่ใช่ของแอป)
    """
    result: bool | None = None
    for path in py_files:
        code = path.read_text(encoding="utf-8", errors="replace")
        prefixed = bool(re.search(r"""Blueprint\([^)]*url_prefix\s*=\s*["']/api""", code))
        for func in _functions(code):
            paths = _route_paths(func)
            is_api = any(p.startswith("/api") for p in paths) or (prefixed and paths)
            if not is_api:
                continue
            body = ast.get_source_segment(code, func) or ""
            guarded = (
                "login_required" in _decorator_names(func)
                or "login_required" in body
                or "current_user" in body
            )
            if not guarded:
                return False
            result = True
    return result


def _debug_run(py_files: list[pathlib.Path]) -> bool:
    """มี `.run(debug=True)` จริงไหม — **อ่านจาก AST ไม่ใช่จากข้อความ**

    การค้นข้อความจะจับ docstring ที่เขียนอธิบายว่า "ไฟล์นี้ไม่มี `debug=True`"
    แล้วรายงานว่าแอปเปิด debug console อยู่ — คือกลับความจริงทั้งข้อ
    (checker ของ overlay เลือก AST ด้วยเหตุผลเดียวกัน)
    """
    for path in py_files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            called = node.func
            if not (isinstance(called, ast.Attribute) and called.attr == "run"):
                continue
            for keyword in node.keywords:
                if (
                    keyword.arg == "debug"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value is True
                ):
                    return True
    return False


def probe(root: pathlib.Path) -> dict[str, bool | None]:
    """ตรวจทั้ง 10 ข้อกับแอปหนึ่งตัว — คืน True/False/None ต่อข้อ"""
    py_files = _python_files(root)
    py_text = _read(py_files)
    template_text = _read(_templates(root))

    secret_lines = [ln for ln in py_text.splitlines() if "SECRET_KEY" in ln]
    hardcoded = [
        ln
        for ln in secret_lines
        if re.search(r"""SECRET_KEY["']?\]?\s*=\s*["'][^"']+["']""", ln)
        or re.search(r"""environ\.get\([^)]*,\s*["'][^"']+["']\)""", ln)
        or re.search(r"""getenv\([^)]*,\s*["'][^"']+["']\)""", ln)
    ]

    return {
        "V6.2.2-password-hashing": any(h in py_text for h in HASHERS),
        "V2.1.1-password-min-length": _password_length(py_files),
        "V3.4.1-cookie-flags": "SESSION_COOKIE_SAMESITE" in py_text
        or "SESSION_COOKIE_SECURE" in py_text
        or "Talisman(" in py_text,
        "V4.2.2-csrf": _csrf(py_text, template_text),
        "V4.1.1-ownership-filter": _ownership(py_files),
        "V5.3.3-output-escaping": "|safe" not in template_text
        and "autoescape false" not in template_text.lower(),
        "V5.3.4-no-sql-string-building": not re.search(
            r"""(execute|text)\(\s*(f["']|["'][^"']*["']\s*[+%]|["'][^"']*["']\.format)""", py_text
        ),
        "V6.4.1-secret-not-hardcoded": (None if not secret_lines else not hardcoded),
        "V13.2.1-api-requires-auth": _api_auth(py_files),
        "V14.1.3-no-debug-console": not _debug_run(py_files),
    }
