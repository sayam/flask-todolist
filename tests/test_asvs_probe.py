"""ตัววัดของการทดลองเฟส 12 ต้องถูกวัดก่อน — สองทิศ ต่อข้อ ไม่ใช่ต่อชุด

บทเรียนข้อ 3 ของ Phase 7: **เครื่องมือที่เราสร้างเองเพื่อพิสูจน์ว่าถูก ก็โกหกได้**
ถ้า `scripts/asvs_probe.py` ตอบ "ผ่าน" ให้ทุกแอปเสมอ ผลของการทดลองจะเป็น
"skill ไม่ช่วยอะไร" ซึ่งเป็นข้อสรุปที่ผิดโดยที่ไม่มีอะไรฟ้อง

ที่นี่จึงกาง**แอปคู่หนึ่ง**ในไดเรกทอรีชั่วคราว: ตัวหนึ่งละเมิดทั้ง 10 ข้อ
อีกตัวทำครบทั้ง 10 ข้อ แล้วบังคับว่า **ทุกข้อต้องแยกสองตัวนี้ออกจากกันได้**
— ข้อที่ตอบเหมือนกันทั้งสองฝั่งคือข้อที่ไม่ได้วัดอะไรเลย
"""

import json
import pathlib

import pytest

from scripts.asvs_probe import CHECKS, probe

INSECURE_APP = {
    "run.py": "from app import create_app\n\napp = create_app()\napp.run(debug=True)\n",
    "app/__init__.py": (
        "from flask import Flask\n\n\n"
        "def create_app():\n"
        "    app = Flask(__name__)\n"
        '    app.config["SECRET_KEY"] = "dev-secret"\n'
        "    return app\n"
    ),
    "app/views.py": (
        "from flask import Blueprint, request\n\n"
        "from . import db\n"
        "from .models import Note, User\n\n"
        'main = Blueprint("main", __name__)\n\n\n'
        '@main.route("/register", methods=["POST"])\n'
        "def register():\n"
        '    user = User(password=request.form["password"])\n'
        "    db.session.add(user)\n"
        '    return ""\n\n\n'
        '@main.route("/notes/<int:note_id>")\n'
        "def show(note_id):\n"
        "    note = db.session.get(Note, note_id)\n"
        "    return note.body\n\n\n"
        '@main.route("/api/notes")\n'
        "def api_notes():\n"
        '    q = request.args.get("q", "")\n'
        '    rows = db.session.execute("SELECT * FROM note WHERE body LIKE \'%" + q + "%\'")\n'
        '    return {"notes": [dict(r) for r in rows]}\n'
    ),
    "app/templates/index.html": '<form method="post"><button>ลบ</button></form>\n{{ body|safe }}\n',
}

SECURE_APP = {
    "run.py": "from app import create_app\n\napp = create_app()\n",
    "app/__init__.py": (
        "import os\n\n"
        "from flask import Flask\n"
        "from flask_wtf import CSRFProtect\n\n\n"
        "def create_app():\n"
        "    app = Flask(__name__)\n"
        '    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]\n'
        '    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"\n'
        "    CSRFProtect(app)\n"
        "    return app\n"
    ),
    "app/views.py": (
        "from flask import Blueprint, request\n"
        "from flask_login import current_user, login_required\n"
        "from werkzeug.security import generate_password_hash\n\n"
        "from . import db\n"
        "from .models import Note, User\n\n"
        'main = Blueprint("main", __name__)\n\n\n'
        '@main.route("/register", methods=["POST"])\n'
        "def register():\n"
        '    password = request.form["password"]\n'
        "    if len(password) < 8:\n"
        '        return "สั้นเกินไป", 400\n'
        "    db.session.add(User(password_hash=generate_password_hash(password)))\n"
        '    return ""\n\n\n'
        '@main.route("/notes/<int:note_id>")\n'
        "@login_required\n"
        "def show(note_id):\n"
        "    note = db.session.get(Note, note_id)\n"
        "    if note is None or note.user_id != current_user.id:\n"
        '        return "ไม่พบ", 404\n'
        "    return note.body\n\n\n"
        '@main.route("/api/notes")\n'
        "@login_required\n"
        "def api_notes():\n"
        '    q = request.args.get("q", "")\n'
        "    rows = db.session.query(Note).filter(\n"
        "        Note.user_id == current_user.id, Note.body.ilike(f'%{q}%')\n"
        "    )\n"
        '    return {"notes": [r.body for r in rows]}\n'
    ),
    "app/templates/index.html": (
        '<form method="post">\n'
        '  <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">\n'
        "  <button>ลบ</button>\n</form>\n{{ body }}\n"
    ),
}


# สำนวนที่สอง: ป้องกันเรื่องเดียวกันด้วยวิธีที่คนละหน้าตา — blueprint ที่ตั้ง
# `url_prefix="/api"`, ความยาวรหัสผ่านผ่านค่าคงที่ และ validator ของฟอร์ม
# probe รอบแรกตอบ "ไม่เกี่ยวข้อง"/"ไม่ผ่าน" ให้ทั้งสามอย่างนี้ ทั้งที่แอปทำครบ
SECURE_APP_OTHER_IDIOM = {
    "run.py": "from app import create_app\n\napp = create_app()\n",
    "app/__init__.py": SECURE_APP["app/__init__.py"],
    "app/forms.py": (
        "from flask_wtf import FlaskForm\n"
        "from wtforms import PasswordField\n"
        "from wtforms.validators import Length\n\n\n"
        "class RegisterForm(FlaskForm):\n"
        '    password = PasswordField("รหัสผ่าน", validators=[Length(min=8, max=128)])\n'
    ),
    "app/auth.py": (
        "from flask import Blueprint\n"
        "from werkzeug.security import generate_password_hash\n\n"
        "from .forms import RegisterForm\n\n"
        'auth = Blueprint("auth", __name__)\n'
        "MIN_PASSWORD_LENGTH = 8\n\n\n"
        '@auth.route("/register", methods=["POST"])\n'
        "def register():\n"
        "    form = RegisterForm()\n"
        "    if not form.validate_on_submit():\n"
        '        return "ไม่ผ่าน", 400\n'
        "    return generate_password_hash(form.password.data)\n"
    ),
    "app/api.py": (
        "from flask import Blueprint\n"
        "from flask_login import current_user, login_required\n\n"
        "from .models import Note\n\n"
        'api = Blueprint("api", __name__, url_prefix="/api")\n\n\n'
        '@api.route("/notes")\n'
        "@login_required\n"
        "def notes():\n"
        "    rows = Note.query.filter_by(user_id=current_user.id).all()\n"
        '    return {"notes": [r.body for r in rows]}\n'
    ),
    "app/templates/index.html": SECURE_APP["app/templates/index.html"],
}


# สำนวนที่สาม: โครงแบบ service layer — helper กลางหาแถว ส่วนความเป็นเจ้าของ
# ถูกตรวจที่ผู้เรียก · นโยบายรหัสผ่านอยู่ในโมดูลของตัวเองและใช้ค่าคงที่
# · มี session timeout ที่เรียก `session.get(...)` ของ Flask (คนละเรื่องกับการหาแถว)
SECURE_APP_SERVICE_LAYER = {
    "run.py": "from app import create_app\n\napp = create_app()\n",
    "app/__init__.py": SECURE_APP["app/__init__.py"],
    "app/session_security.py": (
        "from flask import session\n\n"
        'STARTED_AT = "started_at"\n\n\n'
        "def expired():\n"
        "    raw = session.get(STARTED_AT)\n"
        "    return raw is None\n"
    ),
    "app/services/lookup.py": (
        "from ..extensions import db\n\n\n"
        "def by_id(model, raw_id):\n"
        "    try:\n"
        "        row_id = int(raw_id)\n"
        "    except (TypeError, ValueError):\n"
        "        return None\n"
        "    return db.session.get(model, row_id)\n"
    ),
    "app/services/passwords.py": (
        "MIN_LENGTH = 8\n\n\n"
        "def validate(candidate):\n"
        '    """นโยบายรหัสผ่านที่เดียวของระบบ"""\n'
        "    if len(candidate) < MIN_LENGTH:\n"
        '        raise ValueError("สั้นเกินไป")\n'
    ),
    "app/services/notes.py": (
        "from ..models import Note\n"
        "from .lookup import by_id\n\n\n"
        "def get_note(user_id, note_id):\n"
        "    note = by_id(Note, note_id)\n"
        "    if note is None or note.user_id != user_id:\n"
        '        raise LookupError("ไม่พบ")\n'
        "    return note\n"
    ),
    "app/api.py": (
        "from flask import Blueprint\n"
        "from flask_login import current_user, login_required\n"
        "from werkzeug.security import generate_password_hash\n\n"
        "from .services.notes import get_note\n\n"
        'api = Blueprint("api", __name__, url_prefix="/api")\n\n\n'
        '@api.route("/notes/<int:note_id>")\n'
        "@login_required\n"
        "def one(note_id):\n"
        "    note = get_note(current_user.id, note_id)\n"
        '    return {"body": note.body, "hash": generate_password_hash(\'x\')}\n'
    ),
    "app/templates/index.html": SECURE_APP["app/templates/index.html"],
    # ไฟล์เทสต์ของโปรเจกต์ปลายทาง — ความลับใน fixture ต้องไม่ถูกนับเป็นความลับที่ฝังในโค้ด
    "tests/conftest.py": 'SECRET_KEY = "x" * 48\n',
}


def _plant(root: pathlib.Path, files: dict[str, str]) -> pathlib.Path:
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


@pytest.fixture
def insecure(tmp_path):
    return _plant(tmp_path / "insecure", INSECURE_APP)


@pytest.fixture
def secure(tmp_path):
    return _plant(tmp_path / "secure", SECURE_APP)


def test_the_secure_app_passes_every_check(secure):
    """ตัวที่ทำครบต้องไม่มีข้อไหนตก — ไม่งั้น probe จะลงโทษทั้งสองฝั่งเท่ากัน"""
    result = probe(secure)
    failed = sorted(name for name, value in result.items() if value is False)
    assert not failed, f"แอปที่ทำครบกลับตก: {failed}"


def test_the_insecure_app_fails_every_check(insecure):
    """ตัวที่ละเมิดครบต้องตกครบ — ข้อที่ยังผ่านคือข้อที่ไม่ได้ตรวจของจริง"""
    result = probe(insecure)
    passed = sorted(name for name, value in result.items() if value is not False)
    assert not passed, f"แอปที่ละเมิดครบกลับผ่าน: {passed}"


def test_every_declared_check_is_answered(secure, insecure):
    """ชื่อข้อใน CHECKS กับที่ probe ตอบ ต้องเป็นเซตเดียวกันทั้งสองฝั่ง"""
    for app in (secure, insecure):
        assert set(probe(app)) == set(CHECKS)


def test_the_same_protections_written_differently_still_pass(tmp_path):
    """ป้องกันเรื่องเดียวกันคนละสำนวน ต้องได้ผลเดียวกัน

    ถ้า probe ผูกกับสำนวนเดียว มันจะวัด "เขียนเหมือนตัวอย่างที่เราคิดไว้ไหม"
    แทนที่จะวัด "ป้องกันหรือยัง" — ซึ่งเอียงเข้าข้างฝั่งที่อ่าน skill ของเราเอง
    ในการทดลอง (จับได้จริงตอนวัดฝั่งควบคุมรอบแรก: `url_prefix="/api"` ถูกนับ
    เป็น "ไม่มี API" และ `Length(min=8)` ถูกนับเป็น "ไม่บังคับความยาว")
    """
    app = _plant(tmp_path / "other", SECURE_APP_OTHER_IDIOM)
    result = probe(app)
    failed = sorted(name for name, value in result.items() if value is False)
    assert not failed, f"สำนวนที่สองกลับตก: {failed}"
    assert result["V13.2.1-api-requires-auth"] is True, "blueprint url_prefix ต้องถูกนับว่าเป็น API"
    assert result["V2.1.1-password-min-length"] is True


def test_a_service_layer_shape_is_not_punished(tmp_path):
    """helper กลาง + ตรวจเจ้าของที่ผู้เรียก + เทสต์ของโปรเจกต์ ต้องไม่ทำให้ตก

    ทั้งสามอย่างนี้ทำให้ probe รอบแรกตัดสินว่าฝั่งที่เขียนโครงดีกว่า "แย่กว่า":
    `session.get(KEY)` ของ Flask ถูกนับเป็นการหาแถว · `by_id(model, id)` ถูกนับ
    ว่าลืมตรวจเจ้าของทั้งที่ผู้เรียกตรวจให้ · และ `SECRET_KEY` ใน fixture ถูกนับ
    เป็นความลับที่ฝังในโค้ด — **ตัววัดที่ให้คะแนนสำนวนที่แย่กว่าสูงกว่า
    คือตัววัดที่ตอบคำถามคนละข้อกับที่รายงานอ้าง**
    """
    app = _plant(tmp_path / "service-layer", SECURE_APP_SERVICE_LAYER)
    result = probe(app)
    failed = sorted(name for name, value in result.items() if value is False)
    assert not failed, f"โครงแบบ service layer กลับตก: {failed}"
    assert result["V4.1.1-ownership-filter"] is True
    assert result["V2.1.1-password-min-length"] is True
    assert result["V6.4.1-secret-not-hardcoded"] is True


def test_writing_about_a_forbidden_thing_is_not_doing_it(tmp_path):
    """docstring ที่อธิบายว่า "ไฟล์นี้ไม่มี `debug=True`" ต้องไม่ถูกนับว่าเปิด debug

    เป็นกับดักเดียวกับที่ checker ของ overlay เลือกใช้ AST เพื่อเลี่ยง — และเป็น
    กับดักเดียวกับที่ agent ฝั่ง skill เจอตอนคอมเมนต์ในเทมเพลตยกตัวอย่างสิ่ง
    ต้องห้ามมาอธิบาย · การค้นข้อความจะ**กลับความจริงทั้งข้อ**
    """
    files = dict(SECURE_APP_SERVICE_LAYER)
    files["run.py"] = (
        '"""entrypoint — ไม่มี ``debug=True`` และอ่าน debug จาก env ไม่ได้เลย"""\n\n'
        "from app import create_app\n\napp = create_app()\n"
    )
    app = _plant(tmp_path / "docstring", files)
    assert probe(app)["V14.1.3-no-debug-console"] is True


def test_a_csrf_macro_counts_like_a_raw_token(tmp_path):
    """`{{ csrf_field() }}` คือการวาง token — ไม่ใช่การไม่มี CSRF"""
    files = dict(SECURE_APP_SERVICE_LAYER)
    files["app/templates/index.html"] = (
        '<form method="post">\n  {{ csrf_field() }}\n  <button>ลบ</button>\n</form>\n'
    )
    app = _plant(tmp_path / "macro", files)
    assert probe(app)["V4.2.2-csrf"] is True


def test_a_lookup_helper_with_no_owner_check_anywhere_still_fails(tmp_path):
    """ยกเว้นให้ helper ไม่ใช่การยกเว้นให้ทั้งระบบ — ผู้เรียกที่ไม่ตรวจต้องตก"""
    files = dict(SECURE_APP_SERVICE_LAYER)
    files["app/services/notes.py"] = (
        "from ..models import Note\nfrom .lookup import by_id\n\n\n"
        "def get_note(note_id):\n    return by_id(Note, note_id)\n"
    )
    files["app/api.py"] = files["app/api.py"].replace(
        "get_note(current_user.id, note_id)", "get_note(note_id)"
    )
    app = _plant(tmp_path / "leaky-helper", files)
    assert probe(app)["V4.1.1-ownership-filter"] is False


def test_a_length_rule_on_something_else_does_not_count(tmp_path):
    """บังคับความยาว *ชื่อผู้ใช้* ไม่ใช่การบังคับความยาวรหัสผ่าน"""
    files = dict(SECURE_APP_OTHER_IDIOM)
    files["app/forms.py"] = (
        "from flask_wtf import FlaskForm\n"
        "from wtforms import StringField\n"
        "from wtforms.validators import Length\n\n\n"
        "class RegisterForm(FlaskForm):\n"
        '    username = StringField("ชื่อผู้ใช้", validators=[Length(min=3, max=64)])\n'
    )
    files["app/auth.py"] = files["app/auth.py"].replace("MIN_PASSWORD_LENGTH = 8\n", "")
    app = _plant(tmp_path / "username-only", files)
    assert probe(app)["V2.1.1-password-min-length"] is False


def test_csrf_needs_both_the_guard_and_the_token(tmp_path):
    """เรียก `CSRFProtect` แล้วแต่ฟอร์มไม่มี token = ยังตก

    เขียนแยกเพราะ fixture คู่หลักจับไม่ได้: ตัวที่ละเมิดไม่ได้เรียก `CSRFProtect`
    อยู่แล้ว การถอดเงื่อนไข "ต้องมี token ใน template" จึงไม่ทำให้มันผ่าน —
    ด่านที่จับได้เฉพาะกรณีสุดโต่งสองข้างคือด่านที่ปล่อยของครึ่ง ๆ กลาง ๆ ผ่าน
    (พิสูจน์ด้วย mutation test: ถอด `and "csrf_token" in template_text` แล้ว
    เทสต์นี้ต้องแดง)
    """
    half = _plant(tmp_path / "half", {**SECURE_APP})
    (half / "app" / "templates" / "index.html").write_text(
        '<form method="post"><button>ลบ</button></form>\n', encoding="utf-8"
    )
    assert probe(half)["V4.2.2-csrf"] is False


# ------------------------------------------------ รายงานต้องตรงกับข้อมูลดิบที่วัดได้

COMPARISON = pathlib.Path(__file__).resolve().parent.parent / "docs" / "comparison"
REPORT = COMPARISON / "results-2026-08-14.md"
RAW = COMPARISON / "results-2026-08-14.json"
TABLE_START = "<!-- ตารางผลเริ่ม — tests/test_asvs_probe.py อ่านตารางนี้เทียบกับ JSON -->"
TABLE_END = "<!-- ตารางผลจบ -->"


def _report_rows() -> dict[tuple[str, str], tuple[int, int, int]]:
    """(ฝั่ง, แอป) → (บรรทัด, finding ของ gate, semgrep) จากตารางในรายงาน"""
    text = REPORT.read_text(encoding="utf-8")
    block = text.split(TABLE_START, 1)[1].split(TABLE_END, 1)[0]
    rows = {}
    for line in block.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 6 and cells[0] in ("ctrl", "skill"):
            rows[(cells[0], cells[1])] = (int(cells[2]), int(cells[3]), int(cells[5]))
    return rows


def test_the_report_matches_the_raw_measurement():
    """ตัวเลขในรายงานต้องมาจากไฟล์ผลวัด ไม่ใช่จากความจำของคนเขียน"""
    raw = {(r["side"], r["app"]): r for r in json.loads(RAW.read_text(encoding="utf-8"))}
    report = _report_rows()
    assert set(report) == set(raw), "รายชื่อแอปในรายงานกับในข้อมูลดิบไม่ตรงกัน"
    for key, (lines, findings, semgrep) in report.items():
        row = raw[key]
        assert (lines, findings, row["semgrep"]) == (row["py_lines"], row["gate_findings"], semgrep)


def test_the_report_records_the_conditions_it_was_measured_under():
    """ผลที่ไม่มีโมเดล/วันที่/spec กำกับ เอาไปเทียบกับรอบหน้าไม่ได้เลย"""
    text = REPORT.read_text(encoding="utf-8")
    for required in ("claude-opus-5", "2026-08-14", "spec-notes-app.md", "N |"):
        assert required in text, f"รายงานไม่ได้บันทึก: {required}"


def test_an_empty_directory_answers_not_applicable(tmp_path):
    """ไม่มีอะไรให้ตรวจ = `None` ไม่ใช่ผ่าน — กันการนับแอปที่ล้มกลางคันว่าดี"""
    result = probe(tmp_path)
    assert result["V4.1.1-ownership-filter"] is None
    assert result["V4.2.2-csrf"] is None
    assert result["V13.2.1-api-requires-auth"] is None
    assert result["V6.4.1-secret-not-hardcoded"] is None
