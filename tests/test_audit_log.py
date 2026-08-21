"""ทะเบียนรอบ audit ต้องตรงกับความจริงสองทิศ — และเลขที่โฆษณาต้องมาจากมัน

เลข "audit N รอบ" อยู่ในช่อง About ของ repo และในใบตอบ badge มานาน โดย
**ไม่มีทะเบียนให้ใครนับตาม** — คนอ่านต้องเชื่อคำพูด ซึ่งเป็นสิ่งเดียวกับที่
ทั้งโปรเจกต์นี้พยายามเลิกทำ · ตอนไปไล่ดูจริงพบว่าเลขที่เขียนไว้ (20) ต่ำกว่า
จำนวนรอบที่เกิดขึ้นจริง และไม่มีใครรู้ เพราะไม่มีอะไรนับได้

สี่ทิศที่บังคับ:
- **รูปของทะเบียน**: รอบเรียงต่อเนื่องจาก 1 ไม่ข้ามไม่ซ้ำ · ทุกแถวมีคำถาม ผล
  และหลักฐานอย่างน้อยหนึ่งชิ้น
- **หลักฐานต้องมีอยู่จริง**: `gate:<id>` มีใน `gates.yaml` · `ADR NNNN` มีไฟล์ ·
  path ของเอกสารมีไฟล์
- **หลักฐานต้องพูดถึงรอบนั้นจริง** — ชื่อที่พิมพ์ไว้เฉย ๆ ไม่นับ (นี่คือทิศที่
  ทำให้ทะเบียนนี้ต่างจากรายการชื่อไฟล์)
- **ทิศกลับ**: รอบที่ถูกอ้างที่ไหนก็ตามในรีโป ต้องมีแถวในทะเบียน — รอบผีที่
  โผล่ในเอกสารแต่ไม่มีในทะเบียน = แดง · และเลขที่โฆษณาต้องเท่ากับจำนวนแถว
"""

import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG = ROOT / "docs" / "AUDIT-LOG.md"
GATES = ROOT / "gates.yaml"

ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$", re.MULTILINE)
EVIDENCE = re.compile(r"`(gate:[a-z0-9-]+|ADR \d{4}|[\w./-]+\.md)`")
# ที่ที่เลขจำนวนรอบถูกโฆษณาออกไปข้างนอก
COUNT_CLAIM = re.compile(r"audit (\d+) รอบ|(\d+) recorded governance audits")
DOCS_CLAIMING_THE_COUNT = ("docs/BEST-PRACTICES.md",)


@pytest.fixture(scope="module")
def rows() -> list[tuple[int, str, str, str]]:
    found = [(int(m[0]), m[1], m[2], m[3]) for m in ROW.findall(LOG.read_text(encoding="utf-8"))]
    assert found, "อ่านตารางใน AUDIT-LOG.md ไม่ได้เลย — regex เพี้ยนหรือรูปตารางเปลี่ยน"
    return found


@pytest.fixture(scope="module")
def gate_ids() -> set[str]:
    return {g["id"] for g in yaml.safe_load(GATES.read_text(encoding="utf-8"))["gates"]}


def _mentions(text: str, round_number: int) -> bool:
    """ข้อความนี้พูดถึงรอบนั้นจริงไหม — รับทุกสำนวนที่ repo นี้ใช้เขียนถึงมัน"""
    probe = re.compile(rf"รอบ (?:ที่ )?{round_number}\b|audit r{round_number}\b|\(r{round_number}\)")
    return bool(probe.search(text))


def test_the_rounds_run_from_one_without_gaps(rows):
    """รอบที่ข้ามไปคือรอบที่หายไปจากบันทึก และไม่มีใครสังเกตได้ถ้าไม่มีตาราง"""
    numbers = [n for n, _, _, _ in rows]
    assert numbers == sorted(numbers), f"รอบไม่ได้เรียงจากน้อยไปมาก: {numbers}"
    assert len(set(numbers)) == len(numbers), "มีรอบซ้ำในทะเบียน"
    assert numbers == list(range(1, len(numbers) + 1)), f"รอบต้องต่อเนื่องจาก 1 — ที่มีคือ {numbers}"


def test_every_row_carries_a_question_a_result_and_evidence(rows):
    """คอลัมน์ที่ว่างคือแถวที่ทำให้ทะเบียนดูใหญ่กว่าที่มันพิสูจน์ได้"""
    thin = [
        n
        for n, question, result, evidence in rows
        if len(question) < 10 or len(result) < 10 or not EVIDENCE.findall(evidence)
    ]
    assert not thin, f"แถวที่ยังไม่ครบ (คำถาม/ผล/หลักฐาน): {thin}"


def _resolve(token: str, gates_text: dict[str, str]) -> tuple[str, str | None]:
    """(คำอธิบายของสิ่งที่หลักฐานชี้, เนื้อของมัน) — เนื้อเป็น None ถ้าของนั้นไม่มีอยู่"""
    if token.startswith("gate:"):
        gid = token.removeprefix("gate:")
        return f"gate {gid!r}", gates_text.get(gid)
    if token.startswith("ADR "):
        found = list((ROOT / "docs" / "adr").glob(f"{token.removeprefix('ADR ')}-*.md"))
        return token, found[0].read_text(encoding="utf-8") if found else None
    path = ROOT / token
    return token, path.read_text(encoding="utf-8") if path.is_file() else None


def test_every_piece_of_evidence_exists_and_talks_about_that_round(rows, gate_ids):
    """หลักฐานที่ชี้ของที่ไม่มี — หรือของที่มีแต่ไม่ได้พูดถึงรอบนั้น — ไม่ใช่หลักฐาน

    ทิศหลังคือทิศที่แยกทะเบียนนี้ออกจาก "รายการชื่อไฟล์": เปลี่ยน gate ไปชี้ตัว
    ที่มีอยู่จริงแต่ไม่เกี่ยวกับรอบนั้น แล้วยังเขียว = ทะเบียนที่พิสูจน์อะไรไม่ได้
    """
    gates_text = {
        g["id"]: yaml.safe_dump(g, allow_unicode=True)
        for g in yaml.safe_load(GATES.read_text(encoding="utf-8"))["gates"]
    }
    broken: list[str] = []
    for number, _question, _result, evidence in rows:
        for token in EVIDENCE.findall(evidence):
            what, body = _resolve(token, gates_text)
            if body is None:
                broken.append(f"รอบ {number}: ไม่มี {what}")
            elif not _mentions(body, number):
                broken.append(f"รอบ {number}: {what} ไม่ได้พูดถึงรอบนี้")

    assert not broken, "หลักฐานที่อ้างผิด:\n  " + "\n  ".join(broken)


def test_no_round_is_cited_in_the_repo_without_a_row_here(rows):
    """ทิศกลับ: รอบที่โผล่ในเอกสารแต่ไม่มีในทะเบียน = บันทึกที่ไม่ครบโดยไม่มีใครรู้

    ขอบเขตคือเอกสารกับดัชนี ไม่ใช่ทั้ง repo — เลขรอบในโค้ดเทสต์ (เช่นตัวเทสต์นี้)
    เป็นการอ้างถึงกลไก ไม่ใช่การบันทึกรอบ
    """
    highest = max(n for n, _, _, _ in rows)
    sources = [*(ROOT / "docs").rglob("*.md"), GATES, ROOT / "CLAUDE.md", ROOT / "README.md"]
    cited: set[int] = set()
    for path in sources:
        for number in re.findall(
            r"audit (?:governance )?รอบ (?:ที่ )?(\d+)", path.read_text(encoding="utf-8")
        ):
            cited.add(int(number))

    ghosts = sorted(n for n in cited if n > highest)
    assert not ghosts, (
        f"รอบที่ถูกอ้างในเอกสารแต่ยังไม่มีแถวในทะเบียน: {ghosts} — "
        "รอบใหม่ต้องมาลงทะเบียนที่ docs/AUDIT-LOG.md ในคอมมิตเดียวกับที่มันถูกอ้างครั้งแรก"
    )


@pytest.mark.parametrize("name", DOCS_CLAIMING_THE_COUNT)
def test_every_advertised_count_equals_the_number_of_rows(name, rows):
    """เลขที่โฆษณาออกไปข้างนอก ต้องเป็นเลขที่นับจากทะเบียนนี้ได้

    เจอจริงตอนสร้างทะเบียน: ทั้งช่อง About ของ repo และใบตอบ badge เขียนว่า
    20 รอบ ขณะที่รอบที่เกิดขึ้นจริงคือ 23 — ไม่มีใครโกหก แต่ก็ไม่มีอะไรนับ
    (ช่อง About อยู่นอก repo จึงบังคับที่นี่ไม่ได้ — ขั้นตอนอยู่ใน RELEASE.md)
    """
    text = (ROOT / name).read_text(encoding="utf-8")
    claims = [int(a or b) for a, b in COUNT_CLAIM.findall(text)]
    assert claims, f"{name} ไม่ได้อ้างจำนวนรอบ audit ในรูปแบบที่เทสต์อ่านได้"

    wrong = sorted({c for c in claims if c != len(rows)})
    assert not wrong, f"{name} อ้างว่ามี audit {wrong} รอบ แต่ทะเบียนมี {len(rows)} แถว"
