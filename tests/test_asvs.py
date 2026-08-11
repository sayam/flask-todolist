"""docs/ASVS.md ต้องตรงกับมาตรฐานที่ตรึงไว้ และหลักฐานที่อ้างต้องมีอยู่จริง

**checklist ที่เน่าแย่กว่าไม่มี checklist** เพราะมันทำให้เชื่อว่าตรวจแล้วทั้งที่
สิ่งที่อ้างว่าตรวจหายไปนานแล้ว · เอกสารประเมินตัวเองมีจุดตายอยู่สองที่:

1. **มาตรฐานเปลี่ยนใต้เท้า** — ข้อกำหนดใหม่โผล่มาแล้วไม่มีใครรู้ว่าตกหล่น
   → ตรึงมาตรฐานไว้ใน repo แล้วเทียบว่าทุกข้อในขอบเขตมีแถวของตัวเอง
   และ **ข้อความของข้อกำหนดต้องตรงเป๊ะ** ไม่งั้นแก้ข้อความให้ง่ายลงแล้วผ่านได้
2. **หลักฐานหายไป** — เทสต์ถูกเปลี่ยนชื่อ ไฟล์ถูกลบ job ถูกถอด แต่ตารางยัง
   เขียนว่า "ผ่าน" อยู่ → ทุกอย่างใน backtick ถูกตรวจว่าชี้ไปหาของที่มีจริง

ที่นี่ **ไม่ตัดสินว่าประเมินถูกไหม** — นั่นเป็นงานของคน (หลักเดียวกับ
`tests/test_data_classification.py`) ตรวจแค่ว่าไม่มีข้อไหนหลุดการพิจารณา
และไม่มีคำว่า "ผ่าน" ที่ชี้ไปหาความว่างเปล่า
"""

import ast
import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKSHEET = ROOT / "docs" / "ASVS.md"
SOURCE = ROOT / "docs" / "asvs-5.0.0.json"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

IN_SCOPE = ("1", "2")
PASSED = "ผ่าน"
NOT_APPLICABLE = "ไม่เกี่ยวข้อง"
GAP = "ยังไม่ผ่าน"
UNASSESSED = "ยังไม่ประเมิน"
STATUSES = {PASSED, NOT_APPLICABLE, GAP, UNASSESSED}

# ช่องหลักฐานที่ยังไม่มีอะไร — ใช้ขีดยาวตัวเดียว ไม่ใช่ช่องว่าง เพราะช่องว่าง
# ในตาราง markdown แยกไม่ออกจากการพิมพ์ตกหล่น
EMPTY = "—"

BACKLOG_HEADING = "## ช่องที่ยังไม่ผ่าน (backlog)"

# **ตารางประเมินคือทุกอย่างใต้บรรทัดนี้เท่านั้น** — คำนำมีตาราง backlog ที่แถว
# ขึ้นต้นด้วยเลขข้อเหมือนกัน ถ้าไม่ตัดหัวทิ้งก่อน แถว backlog จะถูกนับเป็นแถว
# ประเมิน แล้วเทสต์ "ห้ามซ้ำ" จะแดงด้วยเหตุผลที่ไม่ใช่ความจริง
ASSESSMENT_MARKER = "<!-- ตารางประเมินเริ่มที่นี่ — ทุกอย่างใต้บรรทัดนี้สร้างโดยสคริปต์ -->"

ROW = re.compile(r"^\|\s*(V\d+\.\d+\.\d+)\s*\|")
REFERENCE = re.compile(r"`([^`]+)`")
ADR_REFERENCE = re.compile(r"^ADR (\d{4})$")

# **เพดานที่ขยับลงได้อย่างเดียว** — จำนวนข้อที่ยังไม่มีใครดู
# ลดลงได้ ขึ้นไม่ได้ (หลักเดียวกับ coverage) วันที่ถึง 0 ให้ตั้งเป็น 0 ค้างไว้
# แล้วสถานะ "ยังไม่ประเมิน" จะกลายเป็นข้อห้ามถาวรโดยไม่ต้องเขียนโค้ดเพิ่ม
UNASSESSED_CEILING = 0  # P7-02: ประเมินครบทั้ง 253 ข้อแล้ว — 0 คือข้อห้ามถาวร


@pytest.fixture(scope="module")
def rows():
    """ทุกแถวของตารางประเมิน — (ข้อ, ระดับ, ข้อความ, สถานะ, หลักฐาน)"""
    text = WORKSHEET.read_text(encoding="utf-8")
    assert ASSESSMENT_MARKER in text, "เอกสารขาดเครื่องหมายที่แบ่งคำนำออกจากตารางประเมิน"
    parsed = []
    for line in text.split(ASSESSMENT_MARKER, 1)[1].splitlines():
        if not ROW.match(line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        assert len(cells) == 5, f"แถว {cells[0]} มี {len(cells)} ช่อง ต้องมี 5"
        parsed.append(tuple(cells))
    return parsed


@pytest.fixture(scope="module")
def standard():
    """ข้อกำหนดในขอบเขต จากมาตรฐานที่ตรึงไว้ใน repo"""
    payload = json.loads(SOURCE.read_text(encoding="utf-8"))
    return {item["req_id"]: item for item in payload["requirements"] if item["level"] in IN_SCOPE}


@pytest.fixture(scope="module")
def ci_jobs():
    """ชื่อ job ทั้งหมดใน CI

    อ่านด้วยการดูย่อหน้าแทนการ parse YAML เพราะ PyYAML ไม่ได้อยู่ใน Pipfile
    (มันติดมากับเครื่องมืออื่น การพึ่งมันคือการพึ่งของที่ไม่ได้ประกาศ) —
    ถ้าวิธีนี้อ่านพลาด เทสต์จะ**แดง**เพราะหา job ไม่เจอ ไม่ใช่เขียวเงียบ ๆ
    """
    jobs, inside = set(), False
    for line in WORKFLOW.read_text(encoding="utf-8").splitlines():
        if line.startswith("jobs:"):
            inside = True
            continue
        if inside:
            if line and not line.startswith(" "):
                break
            found = re.match(r"^  ([a-z][\w-]*):\s*$", line)
            if found:
                jobs.add(found.group(1))
    assert jobs, "อ่านชื่อ job จาก ci.yml ไม่ได้เลย — รูปแบบไฟล์เปลี่ยนไปแล้ว"
    return jobs


def _test_names(path):
    """ชื่อฟังก์ชันเทสต์ทั้งหมดในไฟล์ (รวมที่อยู่ในคลาส)"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }


def _unresolved_adr(number):
    found = list((ROOT / "docs" / "adr").glob(f"{number}-*.md"))
    return None if found else f"ไม่มี ADR หมายเลข {number}"


def _unresolved_test(reference):
    filename, test_name = reference.split("::", 1)
    path = ROOT / filename
    if not path.is_file():
        return f"ไม่มีไฟล์ {filename}"
    if test_name not in _test_names(path):
        return f"ไม่มีเทสต์ชื่อ {test_name} ใน {filename}"
    return None


def _unresolved(reference, ci_jobs):
    """คืนเหตุผลว่าหลักฐานชิ้นนี้ชี้ไปหาอะไรไม่เจอ หรือ None ถ้าเจอ"""
    adr = ADR_REFERENCE.match(reference)
    if adr:
        return _unresolved_adr(adr.group(1))
    if reference.startswith("ci:"):
        job = reference[len("ci:") :]
        return None if job in ci_jobs else f"ไม่มี job ชื่อ {job!r} ใน ci.yml"
    if "::" in reference:
        return _unresolved_test(reference)
    return None if (ROOT / reference).exists() else f"ไม่มีไฟล์ {reference}"


def test_every_requirement_in_scope_has_a_row(rows, standard):
    """ข้อกำหนด L1/L2 ทุกข้อต้องมีแถวของตัวเอง — ตกหล่นไม่ได้"""
    listed = [row[0] for row in rows]
    assert len(listed) == len(set(listed)), "มีข้อที่ซ้ำกันในตาราง"
    missing = sorted(set(standard) - set(listed))
    extra = sorted(set(listed) - set(standard))
    assert not missing, (
        f"ข้อกำหนดที่ยังไม่มีแถวในตาราง ({len(missing)} ข้อ): {missing[:10]}\n"
        "รัน scripts/build_asvs_worksheet.py เพื่อเติมแถวที่ขาด"
    )
    assert not extra, f"มีแถวของข้อที่ไม่มีในมาตรฐาน: {extra}"


def test_requirement_text_matches_the_standard(rows, standard):
    """ข้อความของข้อกำหนดต้องตรงเป๊ะ — ไม่งั้นแก้ให้ง่ายลงแล้วผ่านได้"""
    altered = [
        row[0]
        for row in rows
        if row[2] != standard[row[0]]["text"] or row[1] != standard[row[0]]["level"]
    ]
    assert not altered, (
        f"ข้อความหรือระดับถูกแก้ให้ไม่ตรงกับมาตรฐาน: {altered}\n"
        "การประเมินต้องเป็นการตอบข้อกำหนดตามที่มันเขียน ไม่ใช่ตามที่เราอยากให้มันเขียน"
    )


def test_every_status_is_one_of_the_four(rows):
    unknown = {row[3] for row in rows} - STATUSES
    assert not unknown, f"สถานะที่ไม่รู้จัก: {unknown} (ใช้ได้แค่ {STATUSES})"


def test_passing_rows_point_at_evidence_that_exists(rows, ci_jobs):
    """ทุกข้อที่บอกว่า "ผ่าน" ต้องมีหลักฐานอย่างน้อยหนึ่งชิ้น และชิ้นนั้นต้องมีอยู่จริง"""
    problems = []
    for req_id, _, _, status, evidence in rows:
        if status != PASSED:
            continue
        references = REFERENCE.findall(evidence)
        if not references:
            problems.append(f"{req_id}: บอกว่าผ่านแต่ไม่มีหลักฐานใน backtick เลย")
            continue
        problems += [
            f"{req_id}: {reason}"
            for reason in (_unresolved(reference, ci_jobs) for reference in references)
            if reason
        ]
    assert not problems, "หลักฐานที่ชี้ไปหาของที่ไม่มีอยู่:\n" + "\n".join(problems)


def test_every_reference_anywhere_resolves(rows, ci_jobs):
    """แม้แถวที่ไม่ได้บอกว่าผ่าน ถ้าอ้างอะไรไว้ ของนั้นก็ต้องมีจริง

    ช่อง "ไม่เกี่ยวข้อง" ที่อ้าง ADR ซึ่งถูกลบไปแล้ว คือเหตุผลที่ไม่มีใครตรวจได้
    """
    problems = [
        f"{row[0]}: {reason}"
        for row in rows
        for reference in REFERENCE.findall(row[4])
        if (reason := _unresolved(reference, ci_jobs))
    ]
    assert not problems, "หลักฐานที่ชี้ไปหาของที่ไม่มีอยู่:\n" + "\n".join(problems)


def test_rows_that_are_not_passing_explain_why(rows):
    """ "ไม่เกี่ยวข้อง" กับ "ยังไม่ผ่าน" ต้องมีเหตุผล ไม่ใช่ปล่อยว่าง"""
    silent = [row[0] for row in rows if row[3] in (NOT_APPLICABLE, GAP) and row[4] in (EMPTY, "")]
    assert not silent, (
        f"ข้อที่ตอบว่าไม่ผ่าน/ไม่เกี่ยวข้องโดยไม่บอกเหตุผล: {silent}\n"
        "เหตุผลคือสิ่งเดียวที่ทำให้คนอ่านทีหลังตัดสินได้ว่ายังจริงอยู่ไหม"
    )


def test_gaps_are_listed_in_the_backlog(rows):
    """ช่องที่ยังไม่ผ่านต้องโผล่ใน backlog — ไม่ใช่ซ่อนอยู่กลางตาราง 253 แถว"""
    text = WORKSHEET.read_text(encoding="utf-8")
    assert BACKLOG_HEADING in text, f"เอกสารขาดหัวข้อ {BACKLOG_HEADING!r}"
    backlog = text.split(BACKLOG_HEADING, 1)[1].split("<!--", 1)[0]
    missing = [row[0] for row in rows if row[3] == GAP and row[0] not in backlog]
    assert not missing, f"ข้อที่ยังไม่ผ่านแต่ไม่อยู่ใน backlog: {missing}\nงานที่ไม่มีใครเห็นคืองานที่ไม่มีใครทำ"


def test_unassessed_count_only_goes_down(rows):
    """ratchet: จำนวนข้อที่ยังไม่ได้ประเมินลดลงได้อย่างเดียว"""
    unassessed = [row[0] for row in rows if row[3] == UNASSESSED]
    assert len(unassessed) <= UNASSESSED_CEILING, (
        f"ข้อที่ยังไม่ประเมินมี {len(unassessed)} ข้อ เกินเพดาน {UNASSESSED_CEILING}"
    )
    assert len(unassessed) >= UNASSESSED_CEILING - 20 or UNASSESSED_CEILING == 0, (
        f"ประเมินเพิ่มไปแล้ว {UNASSESSED_CEILING - len(unassessed)} ข้อ "
        f"— ลด UNASSESSED_CEILING ลงเป็น {len(unassessed)} ด้วย ไม่งั้นเพดานหลวมเปล่า ๆ"
    )
