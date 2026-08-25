"""`docs/COMPLIANCE.md` (G4 — ADR 0051) ต้องตรงกับ gate ชั้น legal สองทิศ

convention: gate ของ worksheet กฎหมายรายประเทศใช้ id ขึ้นต้น `legal-` —
ประเทศใหม่ที่มีด่านแต่ไม่ลงดัชนี = มองไม่เห็นจากชั้น legal · แถวที่ชี้ gate
หรือ worksheet ที่ไม่มีจริง = ดัชนีที่โกหก (หลักเดียวกับแกน supply chain)
"""

import pathlib
import re

import pytest
import yaml  # type: ignore[import-untyped] - library lacks type stubs

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "COMPLIANCE.md"

# แถวของตารางประเทศ: | ชื่อ | กฎหมาย | `docs/X.md` | `gate legal-...` |
COUNTRY_ROW = re.compile(
    r"^\|[^|]+\|[^|]+\|\s*`([^`]+)`\s*\|\s*`gate (legal-[a-z0-9-]+)`\s*\|", re.MULTILINE
)


@pytest.fixture(scope="module")
def gates():
    return yaml.safe_load((ROOT / "gates.yaml").read_text(encoding="utf-8"))["gates"]


@pytest.fixture(scope="module")
def country_rows(text):
    return COUNTRY_ROW.findall(text)


@pytest.fixture(scope="module")
def text():
    return DOC.read_text(encoding="utf-8")


def test_every_legal_gate_is_indexed_and_vice_versa(gates, country_rows):
    legal = {g["id"] for g in gates if g["id"].startswith("legal-")}
    listed = {gate_id for _sheet, gate_id in country_rows}
    assert legal, "ไม่มี gate ชั้น legal เลย — convention ชื่อ legal-* หายหรือเปล่า"
    missing = sorted(legal - listed)
    ghosts = sorted(listed - legal)
    assert not missing, f"gate ชั้น legal ที่ไม่มีแถวใน docs/COMPLIANCE.md: {missing}"
    assert not ghosts, f"ดัชนีอ้าง gate ชั้น legal ที่ไม่มีจริง: {ghosts}"


def test_every_worksheet_in_the_index_exists(country_rows):
    dead = sorted({sheet for sheet, _g in country_rows if not (ROOT / sheet).is_file()})
    assert country_rows, "ดึงแถวประเทศจากตารางไม่ได้เลย — regex หรือโครงตารางพังหรือเปล่า"
    assert not dead, f"ดัชนีชี้ worksheet ที่ไม่มีจริง: {dead}"


def test_legal_gates_sit_in_the_security_pillar(gates):
    wrong = [
        (g["id"], g.get("pillar"))
        for g in gates
        if g["id"].startswith("legal-") and g.get("pillar") != "security"
    ]
    assert not wrong, (
        f"gate ชั้น legal ต้องอยู่ pillar security ตามธรรมนูญ (กฎหมาย = แกนของชั้น 1): {wrong}"
    )
