"""`docs/SUPPLY-CHAIN.md` (G3 — ADR 0051) ต้องตรงกับแกนที่ประกาศใน gates.yaml สองทิศ

สมาชิกของแกนประกาศที่ gate ด้วย `axis: supply-chain` — ดัชนีที่ไม่ถูกบังคับ
ให้ตรงกับความจริงคือดัชนีที่โกหกเงียบ ๆ (บทเรียนเดียวกับ semgrep scope):
ด่าน supply chain ใหม่ที่ไม่ถูกจัดเข้าดัชนี = มองไม่เห็นจากแกน · แถวในดัชนี
ที่ไม่มี gate จริงหนุน = คำขวัญ
"""

import pathlib
import re

import pytest
import yaml  # type: ignore[import-untyped]

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "SUPPLY-CHAIN.md"

GATE_REF = re.compile(r"`gate ([a-z0-9-]+)`")


@pytest.fixture(scope="module")
def gates():
    return yaml.safe_load((ROOT / "gates.yaml").read_text(encoding="utf-8"))["gates"]


@pytest.fixture(scope="module")
def text():
    return DOC.read_text(encoding="utf-8")


def test_axis_values_are_known(gates):
    unknown = [(g["id"], g["axis"]) for g in gates if "axis" in g and g["axis"] != "supply-chain"]
    assert not unknown, f"ค่า axis ที่ไม่รู้จัก: {unknown} — ตอนนี้แกนเดียวที่นิยามคือ supply-chain"


def test_every_axis_gate_is_indexed_and_vice_versa(gates, text):
    tagged = {g["id"] for g in gates if g.get("axis") == "supply-chain"}
    listed = set(GATE_REF.findall(text))
    assert tagged, "ไม่มี gate ไหนติดธง axis: supply-chain เลย — ธงหายทั้งชุดหรือเปล่า"
    missing = sorted(tagged - listed)
    ghosts = sorted(listed - tagged)
    assert not missing, f"gate ของแกนที่ยังไม่มีแถวใน docs/SUPPLY-CHAIN.md: {missing}"
    assert not ghosts, (
        f"ดัชนีอ้าง gate ที่ไม่ได้ติดธง axis (หรือไม่มีจริง): {ghosts} — ติดธงที่ gates.yaml หรือถอดแถวออก"
    )


def test_every_backtick_path_resolves(text):
    dead = []
    for ref in re.findall(r"`([^`]+)`", text):
        if ref.startswith("gate ") or re.fullmatch(r"ADR \d{4}", ref):
            continue
        if re.fullmatch(r"(?:A\.)?\d+\.\d+", ref) or ref in {"Pipfile.lock", "[packages]"}:
            continue
        pathlike = "/" in ref or ref.endswith((".md", ".json", ".yaml", ".txt"))
        if pathlike and not (ROOT / ref).exists():
            dead.append(ref)
    assert not dead, f"ดัชนีชี้ไฟล์ที่ไม่มีจริง: {dead}"
