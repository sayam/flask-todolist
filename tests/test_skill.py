"""`SKILL.md` ต้องเป็นเงาของ portable gate — และห้ามเอ่ยชื่อไลบรารีของ Flask

สองอันตรายของเอกสาร skill ที่ export ไปใช้ที่อื่น:

1. **drift** — เขียนมือแล้วมีคนแก้ gates.yaml ฝั่งเดียว กฎที่ส่งออกไปจะเป็น
   รุ่นเก่าโดยไม่มีอะไรฟ้อง → generate ทั้งใบ แล้วที่นี่เทียบไบต์ต่อไบต์
2. **framework รั่วเข้าไปในชั้นที่ประกาศว่าสากล** — กฎที่เอ่ยชื่อไลบรารีของ
   Flask คือกฎที่ import ไป framework อื่นแล้วอ่านไม่รู้เรื่อง · เทคนิคเดียวกับ
   ที่ `tests/test_plugins.py` ห้าม core เอ่ยชื่อ plugin: grep แล้วแดง
   — ban list ตรวจที่*ผล render สด* ไม่ใช่แค่ไฟล์ จึงจับได้ตั้งแต่ตอนคำต้องห้าม
   ถูกพิมพ์ลง gates.yaml ไม่ใช่ตอน regenerate
"""

import pathlib
import re

import pytest

from scripts import build_skill
from scripts.build_skill import OUT, OUT_BUSINESS, portable_gates, render

ROOT = pathlib.Path(__file__).resolve().parent.parent

# ไลบรารีของ ecosystem Flask/Python-web ที่กฎสากลห้ามพึ่งชื่อ — ชั้นที่ผูกได้
# คือ overlay เท่านั้น · คำกลาง ๆ อย่าง redis/mysql เป็นชื่อ *ระบบภายนอก*
# ไม่ใช่ไลบรารีของ framework จึงไม่อยู่ในรายการนี้
BANNED = (
    "flask",
    "werkzeug",
    "jinja",
    "sqlalchemy",
    "alembic",
    "talisman",
    "wtform",
    "marshmallow",
    "smorest",
    "gunicorn",
    "pipenv",
)


@pytest.mark.parametrize(("path", "layer"), [(OUT, "baseline"), (OUT_BUSINESS, "business")])
def test_each_skill_sheet_is_a_render_of_the_registry_not_a_second_copy(path, layer):
    """แก้ gates.yaml แล้วไม่ regenerate = แดง · แก้ไฟล์ skill มือ = แดง — ทั้งสองใบ"""
    assert path.is_file(), f"ไม่มี {path.name} — รัน scripts/build_skill.py"
    assert path.read_text(encoding="utf-8") == render(layer), (
        f"{path.name} ไม่ตรงกับผล generate จาก gates.yaml — "
        "รัน pipenv run python scripts/build_skill.py แล้ว commit มาด้วยกัน"
    )


def _ids_in(path):
    return set(re.findall(r"^### `([a-z0-9-]+)`$", path.read_text(encoding="utf-8"), re.MULTILINE))


def test_the_two_sheets_partition_every_portable_gate():
    """portable gate ทุกตัวอยู่ในใบเดียวเป๊ะ — ขาด ซ้ำ หรือเกิน คือเงาที่โกหก

    partition แบบเดียวกับที่ไฟล์เทสต์ถูกตัดสินใน gates.yaml (ADR 0042):
    baseline อยู่ SKILL.md · business อยู่ SKILL-TODOLIST.md · ห้ามทับกัน
    และรวมกันต้องเท่ากับเซต portable ทั้งหมด
    """
    in_baseline = _ids_in(OUT)
    in_business = _ids_in(OUT_BUSINESS)
    overlap = in_baseline & in_business
    assert not overlap, f"gate ที่โผล่สองใบ: {sorted(overlap)}"
    expected = {g["id"] for g in portable_gates()}
    union = in_baseline | in_business
    assert union == expected, f"ขาด: {sorted(expected - union)} · เกิน: {sorted(union - expected)}"
    assert in_baseline == {g["id"] for g in portable_gates("baseline")}
    assert in_business == {g["id"] for g in portable_gates("business")}


def test_no_flask_library_name_leaks_into_the_universal_layer():
    """ตรวจผล render สด — จับคำต้องห้ามตั้งแต่ตอนมันถูกพิมพ์ลง gates.yaml

    ยกเว้นบรรทัด "ตัวบังคับใน reference" ซึ่งชี้ไฟล์/job ของ repo นี้โดยตั้งใจ
    (นั่นคือส่วน reference ไม่ใช่ส่วนกฎ) — กฎกับบทเรียนต้องสะอาด
    """
    leaked = []
    for line in render("baseline").splitlines() + render("business").splitlines():
        if line.startswith("**ตัวบังคับใน reference:**"):
            continue
        lowered = line.lower()
        leaked += [f"{word!r} ใน: {line.strip()[:80]}" for word in BANNED if word in lowered]
    assert not leaked, "\n  ".join(["ชื่อไลบรารีของ framework หลุดเข้าชั้นสากล:", *leaked])


@pytest.mark.parametrize(("path", "layer"), [(OUT, "baseline"), (OUT_BUSINESS, "business")])
def test_every_rule_still_carries_its_origin(path, layer):
    """ทุกข้อในไฟล์ต้องมีทั้งกฎและบทเรียน — โครงที่หายไปเงียบ ๆ คือ generator พัง"""
    text = path.read_text(encoding="utf-8")
    rules = text.count("**กฎ:**")
    origins = text.count("**เกิดจาก:**")
    total = len(portable_gates(layer))
    assert rules == origins == total, f"{path.name}: กฎ {rules} · เกิดจาก {origins} · gate {total}"


def test_the_business_sheet_declares_baseline_as_its_prerequisite():
    """ทิศระหว่างชั้น (ADR 0042): ใบ business ต้องประกาศว่าต่อยอด baseline

    การขัดกันเชิงเนื้อหาตรวจด้วยเครื่องไม่ได้ — สิ่งที่บังคับได้คือ pointer นี้
    กับ partition ข้างบน · ถอดประโยค prerequisite ออกจาก PREAMBLE = แดงที่นี่
    """
    text = OUT_BUSINESS.read_text(encoding="utf-8")
    assert "SKILL.md" in text, "SKILL-TODOLIST.md ไม่ได้ชี้ไปหา SKILL.md เลย"
    assert "ต้องรับ baseline ก่อน" in text, "SKILL-TODOLIST.md ไม่ได้ประกาศ baseline เป็น prerequisite"


def test_the_readme_advertises_the_real_rule_counts():
    """เลขที่โฆษณาใน README ต้องมาจากดิสก์ — เลขที่ไม่มีเทสต์อ่านคู่คือเลขที่ผิดอยู่แล้ว

    (บทเรียนรอบตรวจเอกสาร 2026-08-14: เลขทุกตัวที่ไม่มีเทสต์เทียบ ผิดหมด)
    """
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    baseline = len(portable_gates("baseline"))
    for pattern in (
        rf"{baseline} framework-agnostic baseline rules",
        rf"กฎ baseline {baseline} ข้อ",
    ):
        assert re.search(pattern, readme), f"README ไม่มีข้อความ {pattern!r} — เลขจริงคือ {baseline}"


def test_every_doc_that_says_how_many_rules_there_are_now_says_the_real_number():
    """คำว่า "ปัจจุบัน N" ในเอกสารไหนก็ตาม ต้องเป็น N ของวันนี้ ไม่ใช่ของวันที่พิมพ์

    เทสต์ข้างบนคุมเฉพาะ README มาตลอด — และบทเรียนที่เขียนอยู่ใน docstring ของมัน
    เองก็เกิดซ้ำทันทีที่มีคนเขียนเลขเดียวกันไว้อีกไฟล์: `docs/ROADMAP-INFRA.md`
    เขียน "ปัจจุบัน 77" ค้างไว้ขณะที่ของจริงเป็น 79 (รอบตรวจเอกสารก่อนออก v2.2.0)

    ที่นี่ไม่ผูกกับชื่อไฟล์ใดไฟล์หนึ่ง — **สแกนทุกไฟล์ `.md` ที่คนเขียน** แล้วบังคับ
    ว่าสำนวนนี้ต้องตรง เพราะที่ที่เลขจะไปโผล่ครั้งถัดไป เราไม่รู้ล่วงหน้า
    """
    baseline = len(portable_gates("baseline"))
    generated = {"SKILL.md", "SKILL-TODOLIST.md"}
    wrong: list[str] = []
    for path in sorted(ROOT.glob("**/*.md")):
        if ".venv" in path.parts or "node_modules" in path.parts or path.name in generated:
            continue
        wrong += [
            f"{path.relative_to(ROOT)} อ้าง {claimed}"
            for claimed in re.findall(r"ปัจจุบัน (\d+)\)", path.read_text(encoding="utf-8"))
            if int(claimed) != baseline
        ]

    assert not wrong, f"เลขกฎที่ล้าสมัย: {wrong} — ของจริงคือ {baseline}"


@pytest.mark.parametrize("word", ["mutation", "ratchet", "ADR", "สองทิศ"])
def test_the_central_practices_survive_in_the_preamble(word):
    """หลักปฏิบัติกลาง (ของคน อยู่ใน PREAMBLE) ต้องไม่หายตอนมีคนแก้ generator"""
    assert word in OUT.read_text(encoding="utf-8"), f"หลักปฏิบัติเรื่อง {word!r} หายจาก SKILL.md"


# ---------------- ทางที่คนพิมพ์จริง — `--check` คือตัวที่ควรจับ drift (ขั้น 2e)
#
# `render()` ถูกเทสต์ไว้แน่นแล้ว แต่ *ตัวสั่งงาน* ไม่เคยถูกเดินผ่านเลย — ซึ่งเป็น
# ทางเดียวที่คนกับ CI ใช้จริง · ตัวสั่งงานที่ไม่มีใครเรียกในเทสต์ คือตัวที่พังได้
# โดยที่ `render()` ยังเขียวสนิท


def test_check_says_up_to_date_when_the_committed_sheets_match(capsys):
    """ไม่เขียนอะไร แค่บอกว่าตรงไหม — CI ใช้ทางนี้"""
    assert build_skill.build(check=True) == 0
    out = capsys.readouterr().out
    assert out.count("up to date") == 2, "ต้องรายงานทั้งสองใบ ไม่ใช่ใบเดียว"


def test_the_worst_exit_code_wins(monkeypatch, capsys):
    """ใบแรกผ่านแล้วใบที่สองแดง ต้องได้ 1 — ไม่ใช่ 0 ของใบสุดท้ายที่บังเอิญผ่าน"""
    codes = iter([0, 1])
    monkeypatch.setattr(build_skill.skill, "main", lambda _argv: next(codes))
    assert build_skill.build() == 1
    capsys.readouterr()


def test_the_command_line_passes_check_through(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["build_skill.py", "--check"])
    assert build_skill.main() == 0
    assert "up to date" in capsys.readouterr().out
