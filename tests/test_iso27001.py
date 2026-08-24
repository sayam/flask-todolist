"""`docs/ISO27001.md` (G2 — ADR 0051) ต้องครบทุกข้อและหลักฐานทุกชิ้นชี้ของจริง

หลักเดียวกับ `test_asvs.py`/`test_pdpa.py`: มาตรฐานตรึงไว้ (โครงรหัสข้อใน
`docs/iso27001-2022-outline.json` + checksum ในไฟล์นี้) · ทุกข้อของ outline
ต้องมีแถวและทุกแถวต้องอยู่ใน outline · สถานะมีสามค่า ไม่มี "ยังไม่ประเมิน"
ตั้งแต่วันแรก · backtick ทุกอันในช่องหลักฐานต้อง resolve — รับเพิ่มสองรูป
ที่ worksheet นี้ใช้: `gate <id>` (เทียบ gates.yaml) และรหัสข้ออ้างข้ามกัน
"""

import hashlib
import json
import pathlib
import re

import pytest
import yaml  # type: ignore[import-untyped] - library lacks type stubs

from tests.test_asvs import _unresolved

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "ISO27001.md"
OUTLINE = ROOT / "docs" / "iso27001-2022-outline.json"

# ตรึงมาตรฐาน: outline เปลี่ยน = ต้องรู้ตัวและประเมินข้อที่ขยับใน commit เดียวกัน
OUTLINE_SHA256 = "b3171030b4426307949fa4796b8b30189b065bd321e83895097cc018560f9ebe"

STATUSES = ("ผ่าน", "ไม่เกี่ยวข้อง", "ยังไม่ผ่าน")
ROW = re.compile(r"^\|\s*`((?:A\.)?\d+\.\d+)`\s*\|([^|]*)\|([^|]*)\|(.*)\|\s*$", re.MULTILINE)
BACKTICK = re.compile(r"`([^`]+)`")


@pytest.fixture(scope="module")
def outline():
    raw = OUTLINE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == OUTLINE_SHA256, (
        "outline ของมาตรฐานถูกแก้ — ถ้าตั้งใจ (แก้พิมพ์ผิด/รุ่นใหม่) ให้ประเมิน"
        "ข้อที่กระทบใน commit เดียวกัน แล้วอัปเดต OUTLINE_SHA256 ในไฟล์นี้"
    )
    data = json.loads(raw)
    return data["clauses"] + data["annex_a"]


@pytest.fixture(scope="module")
def rows():
    return [
        (m.group(1), m.group(3).strip(), m.group(4).strip())
        for m in ROW.finditer(DOC.read_text(encoding="utf-8"))
    ]


@pytest.fixture(scope="module")
def ci_jobs():
    jobs = set()
    for path in (ROOT / ".github" / "workflows").glob("*.y*ml"):
        jobs |= set((yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("jobs") or {})
    return jobs


@pytest.fixture(scope="module")
def gate_ids():
    gates = yaml.safe_load((ROOT / "gates.yaml").read_text(encoding="utf-8"))["gates"]
    return {g["id"] for g in gates}


def _assessment_rows(rows):
    """แถวประเมิน (สถานะเป็นหนึ่งในสามค่า) — แถว backlog ใช้คอลัมน์ต่างออกไป"""
    return [r for r in rows if r[1] in STATUSES]


def test_every_outline_item_is_assessed_exactly_once(rows, outline):
    ids = [r[0] for r in _assessment_rows(rows)]
    assert len(ids) == len(set(ids)), "มีข้อที่ซ้ำในตาราง"
    missing = sorted(set(outline) - set(ids))
    extra = sorted(set(ids) - set(outline))
    assert not missing, f"ข้อที่ยังไม่ถูกประเมิน ({len(missing)}): {missing}"
    assert not extra, f"แถวของข้อที่ไม่มีใน outline: {extra}"


def test_every_status_is_a_known_status(rows, outline):
    unknown = [(r[0], r[1]) for r in rows if r[0] in outline and r[1] not in STATUSES]
    assert not unknown, f"สถานะที่ไม่รู้จัก (รวม 'ยังไม่ประเมิน' ซึ่งห้ามถาวร): {unknown}"


def test_every_backtick_resolves(rows, ci_jobs, gate_ids, outline):
    dead = []
    for control, _status, cell in rows:
        for ref in BACKTICK.findall(cell):
            gate = re.fullmatch(r"gate ([a-z0-9-]+)", ref)
            if gate:
                if gate.group(1) not in gate_ids:
                    dead.append(f"{control}: ไม่มี gate ชื่อ {gate.group(1)!r}")
                continue
            if re.fullmatch(r"(?:A\.)?\d+\.\d+", ref):
                if ref not in outline:
                    dead.append(f"{control}: อ้างข้อ {ref} ที่ไม่มีใน outline")
                continue
            reason = _unresolved(ref, ci_jobs)
            if reason:
                dead.append(f"{control}: `{ref}` — {reason}")
    assert not dead, "หลักฐานที่ชี้ไปหาของที่ไม่มีจริง:\n  " + "\n  ".join(dead)


def test_passing_rows_carry_evidence(rows):
    bare = [r[0] for r in _assessment_rows(rows) if r[1] == "ผ่าน" and not BACKTICK.search(r[2])]
    assert not bare, f"แถวที่ 'ผ่าน' โดยไม่มีหลักฐานใน backtick สักชิ้น: {bare}"


def test_the_advertised_tally_matches_the_table(rows):
    counted = {s: sum(1 for r in _assessment_rows(rows) if r[1] == s) for s in STATUSES}
    text = DOC.read_text(encoding="utf-8")
    m = re.search(r"ผ่าน (\d+) · ไม่เกี่ยวข้อง (\d+) · ยังไม่ผ่าน (\d+)", text)
    assert m, "หัวไฟล์ไม่มีผลรวมในรูปแบบที่เทสต์อ่านได้"
    claimed = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    advertised = dict(zip(STATUSES, claimed, strict=True))
    assert advertised == counted, f"หัวไฟล์บอก {advertised} แต่ตารางนับได้ {counted}"


def test_every_failing_row_is_in_the_backlog_and_vice_versa(rows):
    failing = {r[0] for r in _assessment_rows(rows) if r[1] == "ยังไม่ผ่าน"}
    text = DOC.read_text(encoding="utf-8")
    backlog = text.split("## Backlog", 1)[1]
    covered = set(re.findall(r"`((?:A\.)?\d+\.\d+)`", backlog.split("## รอบทบทวน")[0]))
    assert failing <= covered, f"ข้อที่ยังไม่ผ่านแต่ไม่อยู่ใน backlog: {sorted(failing - covered)}"
    assert covered <= failing, (
        f"backlog อ้างข้อที่ไม่ได้มีสถานะ 'ยังไม่ผ่าน' (การยกเว้นเงียบ): {sorted(covered - failing)}"
    )
