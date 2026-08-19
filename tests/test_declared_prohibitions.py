"""ข้อห้ามที่เครื่องตรวจได้ ต้องมีเครื่องตรวจ — audit รอบ 14 ข้อ 2

`CLAUDE.md` มีบรรทัดที่ใช้คำว่า "ห้าม" 62 บรรทัด · แยกเป็นข้อห้ามที่ต่างกันได้
61 ข้อ · ในนั้น **10 ข้อเป็นวิจารณญาณของคนแก้** (เช่น "ห้ามลด assert เหลือแค่
อ่าน pragma") ซึ่งเครื่องตัดสินแทนไม่ได้และไม่ควรตัดสิน · เหลือ **51 ข้อที่
เครื่องตรวจได้ — และ 19 ข้อในนั้นมีแค่ประโยค** ไม่มีเทสต์ ไม่มี gate

สิ่งที่ทำให้เรื่องนี้เร่งด่วนกว่าที่ตัวเลขบอก: **ทั้ง 19 ข้อยังไม่ถูกละเมิดเลย**
กติกาของ repo นี้จึงถูกปฏิบัติตามด้วย *วินัย* ไม่ใช่ด้วยกลไก — ซึ่งพอสำหรับคนที่
เขียนกฎเอง แต่ไม่พอสำหรับคนถัดไป และไม่พอสำหรับตัวเราในอีกหกเดือน · **ด่านที่
เขียนตอนของยังถูกอยู่คือตาข่ายกันถอยหลัง** ส่วนด่านที่เขียนตอนของพังไปแล้วต้อง
แลกกับการซ่อมก่อน และมักถูกลดเงื่อนไขลงเพื่อให้ผ่าน

## ทำไมเป็นไฟล์เดียว ไม่ใช่ทะเบียนใบใหม่

audit รอบ 13 วัดได้ว่าปัญหาของระบบนี้คือ **ไม่มีที่*อ่าน* ไม่ใช่ไม่มีที่*เขียน***
(ตอนนั้นต้องเปิด 8 ที่เพื่อตอบว่าอะไรค้าง) · ทะเบียนใบที่สิบเอ็ดจึงเป็นคำตอบที่ผิด
ตั้งแต่ต้น · ที่นี่เก็บทั้งกฎและตัวตรวจไว้ด้วยกัน แล้วผูกกลับไปที่ `CLAUDE.md`
ด้วยข้อความจริง

## สองทิศ

- เจอการละเมิด = แดง
- **แถวที่อ้างข้อความซึ่งไม่มีอยู่ใน `CLAUDE.md` แล้ว = แดงเหมือนกัน** — กฎถูกถอน
  ด่านต้องถูกถอนตาม ไม่ใช่ค้างอยู่เป็นกฎผีที่ไม่มีใครตัดสินใจให้ (หลักเดียวกับ
  ทะเบียนข้อยกเว้นทุกใบของ repo นี้ตั้งแต่ audit รอบ 9)

## ที่นี่ไม่ครอบอะไร

ข้อห้ามที่ต้องอ่าน*เจตนา*ของคนแก้ (`ห้ามแก้เทสต์ให้เงียบ`) และข้อที่ถ้อยคำยัง
กว้างเกินจะบังคับ (`ห้ามเขียนไทยลงโค้ดตรง ๆ` — literal ไทย 164 จุดเป็น description
ของ OpenAPI ที่ตั้งใจให้เป็นไทย) · **ข้อหลังต้องแคบถ้อยคำก่อน แล้วค่อยมาเพิ่ม**
ไม่ใช่เขียนด่านที่จับของที่เราตั้งใจให้มี
"""

import ast
import pathlib
import re
from collections.abc import Callable
from dataclasses import dataclass

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
INSTRUCTIONS = ROOT / "CLAUDE.md"
APP = ROOT / "app"
TESTS = ROOT / "tests"
SCRIPTS = ROOT / "scripts"


def _python_files(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def _trees(root: pathlib.Path):
    """(path, source, tree) ของทุกไฟล์ — parse ครั้งเดียวใช้ได้ทุกด่าน"""
    for path in _python_files(root):
        source = path.read_text(encoding="utf-8")
        yield path, source, ast.parse(source)


def _where(path: pathlib.Path, node: ast.AST) -> str:
    return f"{path.relative_to(ROOT)}:{node.lineno}"


def _called(node: ast.AST) -> str:
    """ชื่อที่ถูกเรียก (attribute สุดท้าย) — `db.create_all()` → `create_all`"""
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        if isinstance(node.func, ast.Name):
            return node.func.id
    return ""


# ---------------------------------------------------------------- ตัวตรวจ


def _assigned_to(node: ast.AST) -> list[ast.expr]:
    """ฝั่งซ้ายของการกำหนดค่า — ครอบทั้ง `a = b`, `a: T = b` และ `a += b`"""
    targets = getattr(node, "targets", None)
    if targets is not None:
        return list(targets)
    target = getattr(node, "target", None)
    return [target] if isinstance(target, ast.expr) else []


def _no_permanent_session() -> list[str]:
    """`session.permanent = True` — Flask-Login เลิกล้าง session ให้เงียบ ๆ

    ตรวจด้วย AST ไม่ใช่ grep เพราะ `app/session_security.py` อธิบายกฎนี้ไว้ใน
    คอมเมนต์ของตัวเอง — grep จะจับคำอธิบายของกฎว่าเป็นการละเมิดกฎ
    """
    return [
        _where(path, node)
        for path, _source, tree in _trees(APP)
        for node in ast.walk(tree)
        for target in _assigned_to(node)
        if isinstance(target, ast.Attribute) and target.attr == "permanent"
    ]


def _audit_locks_the_lock_row_not_the_tail() -> list[str]:
    """`with_for_update()` ต้องอยู่บนแถวล็อกเสมอ ไม่ใช่บนหางสาย `tdl_audit`"""
    found = []
    for path, source, tree in _trees(APP):
        for node in ast.walk(tree):
            if _called(node) != "with_for_update":
                continue
            statement = ast.get_source_segment(source, node) or ""
            if "lock" not in statement:
                found.append(f"{_where(path, node)} — {statement[:70]}")
    return found


def _no_importorskip() -> list[str]:
    """`importorskip` ทำให้ job `test` ข้ามเทสต์เงียบ ๆ ตอนไลบรารีหาย"""
    return [
        _where(path, node)
        for path, _source, tree in _trees(TESTS)
        for node in ast.walk(tree)
        if _called(node) == "importorskip"
    ]


def _no_get_or_404() -> list[str]:
    """`db.get_or_404()` บอกคนนอกว่า id นั้นมีจริง (ADR 0004)"""
    return [
        _where(path, node)
        for path, _source, tree in _trees(APP)
        for node in ast.walk(tree)
        if _called(node) == "get_or_404"
    ]


def _no_last_used_column() -> list[str]:
    """คอลัมน์ `last_used_at` = แถว audit หนึ่งแถวต่อหนึ่ง request"""
    from app.models import ApiToken

    return [
        f"app/models.py — ApiToken.{column.name}"
        for column in ApiToken.__table__.columns
        if "last_used" in column.name
    ]


def _test_config_inherits_the_real_config() -> list[str]:
    """`TestConfig` ที่เขียนใหม่แบบ standalone ทำให้ค่าใหม่ของ `Config` หายไป

    **เทียบด้วยชื่อคลาสใน MRO ไม่ใช่ `issubclass`** — ในชุดเทสต์เต็ม `config`
    ถูกโหลดได้มากกว่าหนึ่งครั้ง (คนละ path เดียวกัน คนละ object) แล้ว
    `issubclass` ตอบ False ทั้งที่โค้ดถูก · ด่านที่แดงเพราะเรื่องของ import
    ไม่ใช่เพราะกฎถูกละเมิด คือด่านที่จะถูกปิดเสียงในสัปดาห์ถัดไป
    """
    from tests.conftest import TestConfig

    bases = TestConfig.__mro__[1:]
    if not any(base.__name__ == "Config" for base in bases):
        return [f"tests/conftest.py — TestConfig สืบทอดจาก {[base.__name__ for base in bases]}"]
    return []


SQLITE_URI = re.compile(r"SQLALCHEMY_DATABASE_URI\s*[:=].*sqlite")


def _create_all_only_on_a_private_database() -> list[str]:
    """`db.create_all()` นอก `_app_with_tables()` ได้เฉพาะบนฐานส่วนตัวของไฟล์นั้น

    เหตุผลของกฎคือฐานที่ใช้ร่วมกัน: `sqlite:///:memory:` ตายไปพร้อม engine
    แต่ยี่ห้ออื่นเก็บตารางไว้ข้ามเทสต์ ข้อมูลของตัวก่อนหน้าจึงค้างมาให้ตัวถัดไป
    (เจอจริงตอนเปิด job `dialects`: `Duplicate entry 'tester'`) · ไฟล์ที่ตรึง
    ฐานเป็น sqlite ของตัวเองจึงอยู่นอกอันตรายนี้โดยนิยาม
    """
    found = []
    for path, source, tree in _trees(TESTS):
        if path.name == "conftest.py":
            continue
        calls = [node for node in ast.walk(tree) if _called(node) == "create_all"]
        if calls and not SQLITE_URI.search(source):
            found += [f"{_where(path, node)} — ไฟล์นี้ไม่ได้ตรึงฐานเป็น sqlite ของตัวเอง" for node in calls]
    return found


IF_NOT = re.compile(r"^\s*if\s*!\s")
EXIT_CODE = re.compile(r"=\s*\$\?")


def _shell_scripts_capture_exit_codes_safely() -> list[str]:
    """`if ! cmd; then status=$?` — `$?` ในกิ่งนั้นเป็น 0 เสมอ

    งานตามรอบที่ล้มเหลวจะรายงานว่าสำเร็จ ซึ่งแย่กว่าไม่มีงานนั้นเลย
    """
    found = []
    files = sorted(SCRIPTS.glob("*.sh")) + sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    for path in files:
        lines = path.read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, start=1):
            if line.lstrip().startswith("#") or not IF_NOT.search(line):
                continue
            window = " ".join(lines[number - 1 : number + 3])
            if EXIT_CODE.search(window):
                found.append(f"{path.relative_to(ROOT)}:{number}")
    return found


# ---------------------------------------------------------------- ทะเบียน


@dataclass(frozen=True)
class Rule:
    """หนึ่งข้อห้ามที่ประกาศไว้ + เครื่องที่บังคับมัน

    `quote` คือข้อความ **จริง** ใน `CLAUDE.md` — ไม่ใช่คำอธิบายที่เขียนใหม่ที่นี่
    เพราะทิศที่สองของด่านนี้คือ "กฎถูกถอนแล้วด่านต้องถูกถอนตาม"
    """

    quote: str
    check: Callable[[], list[str]]
    hint: str


RULES = (
    Rule(
        quote="**ห้ามตั้ง `session.permanent = True`**",
        check=_no_permanent_session,
        hint="Flask-Login เลิกล้าง session ให้ทันที การผูกคุกกี้กับเครื่องหายเงียบ ๆ",
    ),
    Rule(
        quote="**ห้ามกลับไปใช้ `ORDER BY id DESC LIMIT 1 FOR UPDATE` บน `tdl_audit`**",
        check=_audit_locks_the_lock_row_not_the_tail,
        hint="next-key lock ของ InnoDB พาไปสู่ deadlock — วัดจริง writer 8 ตัว ตาย 128/160",
    ),
    Rule(
        quote="**ห้ามใช้ `importorskip`**",
        check=_no_importorskip,
        hint="job `test` จะข้ามเทสต์นั้นเงียบ ๆ ตอนไลบรารีหาย ซึ่งคือกรณีที่ต้องการให้แดงที่สุด",
    ),
    Rule(
        quote="ห้ามใช้ `db.get_or_404()` กับข้อมูลที่มีเจ้าของ",
        check=_no_get_or_404,
        hint="ตอบ 403 แทน 404 = บอกคนนอกว่า id นั้นมีจริง (ADR 0004)",
    ),
    Rule(
        quote="**ห้ามเพิ่ม `last_used_at`**",
        check=_no_last_used_column,
        hint="เขียนทุก request = แถว audit ต่อ request — กลบสายหลักฐานด้วยเสียงรบกวน",
    ),
    Rule(
        quote="**`TestConfig` ใน `tests/conftest.py` ต้อง `class TestConfig(Config)` เสมอ**",
        check=_test_config_inherits_the_real_config,
        hint="เขียนใหม่แบบ standalone แล้วค่าใหม่ของ Config หายไป — เกิดมาแล้ว 4 ครั้ง",
    ),
    Rule(
        quote="**ทุก fixture ที่สร้างแอปต้องเดินผ่าน `_app_with_tables()`**",
        check=_create_all_only_on_a_private_database,
        hint="ฐานที่ใช้ร่วมกันจะเก็บตารางไว้ข้ามเทสต์ — `Duplicate entry 'tester'` ตอนเปิด job dialects",
    ),
    Rule(
        quote="ในสคริปต์ห้ามรับ exit code แบบ `if ! cmd; then status=$?` เด็ดขาด",
        check=_shell_scripts_capture_exit_codes_safely,
        hint="`$?` ในกิ่งนั้นเป็น 0 เสมอ งานที่ล้มเหลวจะรายงานว่าสำเร็จ",
    ),
)


@pytest.fixture(scope="module")
def instructions() -> str:
    return INSTRUCTIONS.read_text(encoding="utf-8")


@pytest.mark.parametrize("rule", RULES, ids=lambda rule: rule.check.__name__)
def test_the_declared_prohibition_is_not_violated(rule: Rule):
    """ทิศแรก — กฎที่ประกาศไว้ ต้องเป็นจริงในโค้ดจริง"""
    violations = rule.check()
    assert not violations, (
        f"ละเมิดกฎที่ `CLAUDE.md` ประกาศไว้: {rule.quote}\n"
        f"  ทำไมถึงห้าม: {rule.hint}\n  ที่พบ:\n    " + "\n    ".join(violations)
    )


@pytest.mark.parametrize("rule", RULES, ids=lambda rule: rule.check.__name__)
def test_every_check_still_quotes_a_rule_that_exists(rule: Rule, instructions: str):
    """ทิศกลับ — กฎถูกถอน ด่านต้องถูกถอนตาม

    ด่านที่บังคับกฎซึ่งไม่มีใครประกาศแล้ว คือกฎที่ไม่มีใครตัดสินใจให้ —
    มันจะยืนอยู่ได้เพราะไม่มีใครกล้าลบ ไม่ใช่เพราะยังมีเหตุผล
    """
    assert rule.quote in instructions, (
        f"ด่านนี้อ้างข้อความที่ไม่มีใน CLAUDE.md แล้ว: {rule.quote!r}\n"
        "ถ้ากฎถูกถอนจริง ให้ลบแถวนี้ทิ้ง · ถ้าแค่แก้ถ้อยคำ ให้อัปเดต quote ให้ตรง"
    )


def test_the_register_has_no_duplicate_rules():
    """คนละด่านที่อ้างกฎเดียวกัน = ด่านหนึ่งตัวถูกลืมไปโดยไม่มีใครสังเกต"""
    quotes = [rule.quote for rule in RULES]
    assert len(quotes) == len(set(quotes)), "มีกฎซ้ำในทะเบียน"
