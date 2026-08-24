"""`docs/SUPPLY-CHAIN.md` (G3 — ADR 0051) ต้องตรงกับแกนที่ประกาศใน gates.yaml สองทิศ

สมาชิกของแกนประกาศที่ gate ด้วย `axis: supply-chain` — ดัชนีที่ไม่ถูกบังคับ
ให้ตรงกับความจริงคือดัชนีที่โกหกเงียบ ๆ (บทเรียนเดียวกับ semgrep scope):
ด่าน supply chain ใหม่ที่ไม่ถูกจัดเข้าดัชนี = มองไม่เห็นจากแกน · แถวในดัชนี
ที่ไม่มี gate จริงหนุน = คำขวัญ
"""

import pathlib
import re

import pytest
import yaml  # type: ignore[import-untyped] - library lacks type stubs

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "SUPPLY-CHAIN.md"
WORKFLOWS = ROOT / ".github" / "workflows"

# ชั้นที่ 6 — ทะเบียนผู้ให้บริการภายนอก (audit รอบ 7)
REGISTER = "### 6."
USES = re.compile(r"uses:\s*([^\s#@]+)")
IMAGE = re.compile(r"^\s*image:\s*([^\s#]+)", re.MULTILINE)
FROM = re.compile(r"^FROM\s+(\S+?)(?:@|:)", re.MULTILINE)
JOB_REF = re.compile(r"job `([a-z0-9-]+)`")

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


@pytest.fixture(scope="module")
def register(text) -> str:
    """เฉพาะชั้นที่ 6 — ทะเบียนผู้ให้บริการภายนอกและกลไกรับรู้"""
    start = text.index(REGISTER)
    return text[start : text.index("\n## ", start)]


def _pulled_from_outside() -> set[str]:
    """ของภายนอกที่เรา *ดึงเข้ามาจริง* — อนุมานจากไฟล์ ไม่ใช่จากความจำ"""
    pulled = set()
    for path in WORKFLOWS.glob("*.y*ml"):
        # `github/codeql-action/init` กับ `.../analyze` เป็นสัญญาเดียวกัน — หน่วยที่
        # มีสัญญาคือ owner/repo ไม่ใช่ path ย่อยของแต่ละ action
        used = USES.findall(path.read_text(encoding="utf-8"))
        pulled |= {"/".join(ref.split("/")[:2]) for ref in used}
    for path in [*ROOT.glob("compose*.yaml"), *(ROOT / "deploy").glob("*.y*ml")]:
        pulled |= {ref.split(":")[0] for ref in IMAGE.findall(path.read_text(encoding="utf-8"))}
    pulled |= set(FROM.findall((ROOT / "Dockerfile").read_text(encoding="utf-8")))
    return pulled


def test_the_register_names_everything_we_pull_from_outside(register):
    """ทิศกลับ: ของภายนอกทุกชิ้นที่ CI/stack ดึงจริง ต้องมีเจ้าของอยู่ในทะเบียน

    เพิ่ม action หรือ image ใหม่โดยไม่บอกว่า "ถ้าเจ้านี้เปลี่ยนสัญญาอะไรจะแดง"
    คือการเพิ่มการพึ่งพาที่ไม่มีใครตัดสินใจ — กับดักเดียวกับ Bitnami ที่ย้าย
    image ไป org ใหม่แล้วเรารู้เพราะของพัง
    """
    missing = sorted(ref for ref in _pulled_from_outside() if ref.split("@")[0] not in register)
    assert not missing, (
        f"ของภายนอกที่ยังไม่มีในทะเบียนชั้นที่ 6: {missing}\n"
        "เพิ่มแถว (หรือเติมชื่อในแถวที่ครอบอยู่แล้ว) พร้อมคำตอบว่าอะไรจะแดงถ้าเจ้านี้เปลี่ยน"
    )


def test_every_supplier_row_says_what_would_go_red(register):
    """ทุกแถวต้องตอบครบสามช่อง และ "ไม่มีเครื่องตรวจ" ต้องมีตัวทวงกำกับ"""
    rows = [
        [cell.strip() for cell in line.strip().strip("|").split("|")]
        for line in register.splitlines()
        if line.startswith("| ") and "---" not in line
    ][1:]
    assert len(rows) >= 5, f"ทะเบียนมีแค่ {len(rows)} แถว — ตัวดึงตารางพังหรือเปล่า"

    for row in rows:
        assert len(row) == 3, f"แถวต้องมีสามช่อง: {row}"
        assert all(row), f"แถวที่มีช่องว่าง: {row}"
        if "ไม่มีเครื่องตรวจ" in row[2]:
            assert "SECURITY-CADENCE" in row[2], (
                f"{row[0]}: ไม่มีด่านแล้วต้องมีแถวทวงใน SECURITY-CADENCE กำกับ ไม่ใช่ปล่อยว่าง"
            )


def test_the_jobs_the_register_leans_on_exist(register):
    """job ที่ทะเบียนอ้างว่าจะแดง ต้องมีอยู่จริงใน workflow — ไม่งั้นคือคำมั่นลอย ๆ"""
    defined = set()
    for path in WORKFLOWS.glob("*.y*ml"):
        defined |= set(yaml.safe_load(path.read_text(encoding="utf-8")).get("jobs", {}))

    ghosts = sorted(set(JOB_REF.findall(register)) - defined)
    assert not ghosts, f"ทะเบียนอ้าง job ที่ไม่มีจริง: {ghosts}"
