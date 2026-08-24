"""หน้าเดียวที่รวม "อะไรค้างอยู่" ต้องเห็นทุกกอง และรายการทะเบียนต้องมีฉบับเดียว

audit รอบ 25 ถามคำถามที่ยี่สิบสี่รอบก่อนไม่เคยถาม: **ทะเบียนที่ audit สร้างขึ้นเอง
มีกี่ใบ ใครอ่านมันบ้าง และมันเก็บภาษีเท่าไหร่ต่อการเปลี่ยนแปลงหนึ่งครั้ง** —
รอบก่อน ๆ ถามแต่ฝั่ง *ความครอบคลุม* (มีอะไรที่ยังไม่มีด่านคุม) ไม่เคยถามฝั่ง *ต้นทุน*

สามอย่างที่วัดได้ในรอบนั้น และเป็นที่มาของไฟล์นี้:

1. **รายการของ "ทะเบียนข้อยกเว้นทั้งหมด" มีสามฉบับที่ไม่ตรงกัน** — แถวรอบตรวจ
   เอ่ย 7 · `whats_pending.REGISTERS` นับ 8 · `tests/test_exception_registers.py`
   บังคับ 2 · union จริงคือ 10 และไม่มีฉบับไหนครบ
2. **หน้าเดียวที่สร้างมาเพื่อให้เลิกเปิดหลายที่ ไม่เห็นกองที่รอบหลัง ๆ สร้างเอง** —
   เพดานสามตัวใน `[tool.todolist.ceilings]` (audit รอบ 21 และ 24) ไม่เคยถูกทวง
   ให้มาโผล่ที่นี่ · หน้าที่ไม่ครบก็ยังต้องเปิดที่อื่นอยู่ดี
3. **ภาษีของการเพิ่มของหนึ่งชิ้น วัดได้ด้วยการทดลอง** — เพิ่ม ADR หนึ่งใบใน
   worktree แยกแล้วดูว่าอะไรแดง: ต้องไล่แก้สี่ที่ · เพิ่ม gate หนึ่งตัว: สองที่
   · และ **25 จาก 200 commit ล่าสุด (12.5%) เป็นการซิงก์ตัวเลขล้วน ๆ**
   → `scripts/sync_counts.py` รับงานพิมพ์ไปทำแทน **โดยที่เทสต์ยังเป็นคนตัดสิน**
"""

import datetime
import pathlib

import pytest
import yaml

from scripts import sync_counts, whats_pending

#
# รอบ 13 สร้างหน้านี้เพราะต้องเปิด 8 ที่ถึงจะรู้ว่าอะไรค้าง · รอบ 21 พบว่าหัวไฟล์
# ของมันเองเป็นเลขที่นับด้วยมือและผิด · **รอบ 25 พบชั้นที่สาม**: กองที่รอบหลัง ๆ
# สร้างขึ้นเอง (เพดานใน `pyproject.toml` · แถวผิวนอกที่ยังไม่มีเจ้าของ) ไม่เคย
# ถูกทวงให้มาโผล่ที่นี่ — หน้าที่สร้างมาเพื่อให้เลิกเปิดหลายที่ จึงยังต้องเปิด
# ที่อื่นอยู่ดี · และรายการ "ทะเบียนข้อยกเว้นทั้งหมด" มีสามฉบับที่ไม่ตรงกัน


CADENCE_FILE = pathlib.Path(__file__).resolve().parent.parent / "docs" / "SECURITY-CADENCE.md"


def _pending_page() -> str:
    return whats_pending.report(datetime.date(2026, 8, 22), within=60)


def test_every_ceiling_shows_up_on_the_page():
    """เพดานคือกองที่ *มีคนต้องไปทำให้เล็กลง* — ไม่ใช่แค่ห้ามโต

    **กองผิวนอกที่ยังไม่มีเจ้าของก็อยู่ในนี้** (`external_surface_unowned`) — และ
    จงใจไม่นับซ้ำในหน้านี้: ตัวนับที่สองจะทำให้เทสต์ที่เทียบกับตัวมันเองผ่านฟรี
    ซึ่งจับได้ตอน mutation ของรอบ 25 พอดี (ทิศที่ห้าเขียวทั้งที่ตัวนับอ่านผิด)
    """
    page = _pending_page()
    limits = whats_pending.ceilings()

    assert limits, "อ่านเพดานจาก pyproject ไม่ได้เลย — ตารางว่างแล้วเทสต์นี้จะผ่านฟรี"
    missing = [name for name in limits if name not in page]

    assert not missing, (
        f"เพดานที่ไม่โผล่บนหน้ารวมของค้าง: {missing} — "
        "เพิ่มเพดานใน pyproject แล้วต้องมาโผล่ที่นี่ด้วย ไม่งั้นไม่มีใครรู้ว่ามันมี"
    )


def test_the_cadence_row_names_every_register_the_page_counts():
    """สองทิศ — รายการของสิ่งเดียวกันต้องมีฉบับเดียว (audit รอบ 25 ข้อ 1)

    ก่อนรอบนี้มีสามฉบับ: แถว cadence เอ่ย 7 · `REGISTERS` นับ 8 ·
    `tests/test_exception_registers.py` บังคับ 2 — ไม่มีฉบับไหนครอบ union ครบ
    """
    cadence = CADENCE_FILE.read_text(encoding="utf-8")
    row = next(line for line in cadence.splitlines() if "ทะเบียนข้อยกเว้นทุกแฟ้ม" in line)

    missing = [name for name in whats_pending.REGISTERS if f"`{name}`" not in row]
    assert not missing, f"แถวรอบตรวจไม่ได้เอ่ยถึงทะเบียนที่หน้ารวมนับอยู่: {missing}"

    in_code = [name for name in whats_pending.IN_CODE_REGISTERS if f"`{name}`" not in row]
    assert not in_code, f"ทะเบียนที่อยู่ในโค้ดหายไปจากแถวรอบตรวจ: {in_code}"


def test_a_register_that_appears_on_disk_cannot_stay_unlisted():
    """ทิศที่สำคัญที่สุด — ทะเบียนใบใหม่เกิดมาแล้วต้องเข้ารายการ ไม่ใช่รอให้ audit เจอ"""
    root = pathlib.Path(__file__).resolve().parent.parent
    found = {
        path.relative_to(root).as_posix()
        for path in root.rglob("accepted-*.txt")
        if ".venv" not in path.parts and "node_modules" not in path.parts
    }
    unlisted = sorted(found - set(whats_pending.REGISTERS))

    assert not unlisted, (
        f"แฟ้มข้อยกเว้นที่ไม่มีใครนับ: {unlisted} — "
        "เพิ่มใน whats_pending.REGISTERS และในแถวรอบตรวจ (ADR 0069: การเกิดก็ต้องเป็นคำตัดสิน)"
    )


# ------------- เลขที่โฆษณาไว้ต้องซิงก์ได้ด้วยคำสั่งเดียว (audit รอบ 25 ข้อ 3)
#
# วัดด้วยการทดลองจริง: เพิ่ม ADR หนึ่งใบทำให้ต้องไล่แก้สามไฟล์ · เพิ่ม gate หนึ่ง
# ตัวทำให้ต้องแก้สองเลขในไฟล์เดียว · 25 จาก 200 commit ล่าสุดเป็นการซิงก์เลขล้วน ๆ
# **ด่านไม่ได้อ่อนลง** — เทสต์ยังเป็นคนตัดสิน สคริปต์แค่รับงานพิมพ์ไปทำแทน


def _mini_repo(root: pathlib.Path, adrs: int, gates: int, audits: int, said: int) -> None:
    """สร้างรีโปจิ๋วที่มีของครบทุกอย่างที่ตัวซิงก์อ่าน"""
    (root / "docs" / "adr").mkdir(parents=True)
    for n in range(adrs):
        (root / "docs" / "adr" / f"{n:04d}-x.md").write_text("x", encoding="utf-8")
    (root / "docs" / "adr" / "README.md").write_text(
        "".join(f"({n:04d}-x.md)\n" for n in range(adrs)), encoding="utf-8"
    )
    (root / "gates.yaml").write_text(
        yaml.safe_dump(
            {
                "gates": [
                    {"id": f"g{n}", "pillar": "devx", "portable": True, "layer": "baseline"}
                    for n in range(gates)
                ]
            }
        ),
        encoding="utf-8",
    )
    (root / "docs" / "AUDIT-LOG.md").write_text(
        "".join(f"| {n + 1} | ถาม | ตอบ | `ADR 0001` |\n" for n in range(audits)), encoding="utf-8"
    )
    (root / "README.md").write_text(
        f"| [`docs/adr/`](docs/adr/) | {said} architecture decision records — x\n"
        f"[`docs/adr/`](docs/adr/) {said} ใบ\n"
        f"| [`SKILL.md`](SKILL.md) | {said} framework-agnostic baseline rules, x\n"
        f"- [`SKILL.md`](SKILL.md) — กฎ baseline {said} ข้อ x\n",
        encoding="utf-8",
    )
    (root / "CONTRIBUTING.md").write_text(
        f"the {said} records in [`docs/adr/`](docs/adr/)\n", encoding="utf-8"
    )
    (root / "CHANGELOG.md").write_text(f"lives in the {said} records in x\n", encoding="utf-8")
    (root / "docs" / "ROADMAP-GOVERNANCE.md").write_text(
        f"เป็น security 0 · devx 0 · manageability 0 · performance 0\nรวม {said} gate\n",
        encoding="utf-8",
    )
    (root / "CITATION.cff").write_text(f"{said} recorded audit rounds\n", encoding="utf-8")
    (root / ".zenodo.json").write_text(f"{said} recorded audit rounds\n", encoding="utf-8")
    (root / "docs" / "BEST-PRACTICES.md").write_text(
        f"**{said}** recorded governance audits · audit {said} รอบ\n", encoding="utf-8"
    )
    (root / "docs" / "ROADMAP-INFRA.md").write_text(
        f"portable gate (ตอนนั้น 58 กฎ · ปัจจุบัน {said}) ไม่ใช่เขียนมือ\n", encoding="utf-8"
    )


@pytest.fixture
def mini(tmp_path, monkeypatch):
    _mini_repo(tmp_path, adrs=3, gates=2, audits=4, said=99)
    monkeypatch.setattr(sync_counts, "ROOT", tmp_path)
    monkeypatch.setattr(sync_counts, "ADR_DIR", tmp_path / "docs" / "adr")
    monkeypatch.setattr(sync_counts, "GATES", tmp_path / "gates.yaml")
    monkeypatch.setattr(sync_counts, "AUDIT_LOG", tmp_path / "docs" / "AUDIT-LOG.md")
    return tmp_path


def test_the_sync_sees_every_place_a_number_drifted(mini):
    """หกที่ที่การทดลองของรอบ 25 วัดว่าแดงจริง ต้องถูกมองเห็นครบ

    สี่ที่เป็นจำนวน ADR (`README.md` สองบรรทัด · `CONTRIBUTING.md` · `CHANGELOG.md`) ·
    สองที่เป็นจำนวน gate (`รวม N gate` กับบรรทัดสัดส่วน pillar) · สี่ที่เป็นจำนวน
    รอบ audit ซึ่งรวมบัตรประจำตัวสองใบที่ Zenodo อ่านไปตีพิมพ์ (ADR 0072) · และสามที่
    เป็นจำนวนกฎ baseline ที่ส่งออก (`README.md` สองบรรทัด · `ROADMAP-INFRA.md`)
    ซึ่งเพิ่มเข้ามาตอน audit รอบ 26 หลังจากต้องไล่แก้ด้วยมือครบทั้งสามที่
    """
    found = sync_counts.drift()

    assert len(found) == 13, f"ควรเจอครบสิบสามที่ แต่เจอ {[str(f[0].name) for f in found]}"
    assert {path.name for path, *_ in found} == {
        "README.md",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
        "ROADMAP-GOVERNANCE.md",
        "ROADMAP-INFRA.md",
        "CITATION.cff",
        ".zenodo.json",
        "BEST-PRACTICES.md",
    }


def test_writing_makes_every_place_agree_and_then_it_is_silent(mini):
    """ทิศ "ผ่านเมื่อควรผ่าน" — เขียนแล้วต้องเงียบ ไม่ใช่เขียนวนไม่รู้จบ"""
    sync_counts.write(sync_counts.drift())

    assert sync_counts.drift() == []
    assert "3 architecture decision records" in (mini / "README.md").read_text(encoding="utf-8")
    assert "รวม 2 gate" in (mini / "docs" / "ROADMAP-GOVERNANCE.md").read_text(encoding="utf-8")
    assert "2 framework-agnostic baseline rules" in (mini / "README.md").read_text(encoding="utf-8")


def test_a_sentence_that_no_longer_matches_is_reported_not_skipped(mini):
    """ถ้อยคำเปลี่ยนจนรูปแบบหาไม่เจอ = ต้องดัง — การข้ามเงียบคือการรายงานว่าตรงทั้งที่ไม่รู้"""
    (mini / "CONTRIBUTING.md").write_text("ไม่มีเลขอยู่ในประโยคนี้แล้ว\n", encoding="utf-8")

    said = [row for row in sync_counts.drift() if row[0].name == "CONTRIBUTING.md"]

    assert said, "ประโยคที่หารูปแบบไม่เจอกลับเงียบ"
    assert said[0][2] == "(หาไม่เจอ)"


def test_an_adr_without_a_row_in_the_index_is_named_not_invented(mini):
    """แถวใหม่ต้องมีคำอธิบายของมันเอง — สคริปต์บอกว่าขาด แต่ไม่แต่งให้"""
    (mini / "docs" / "adr" / "0009-new.md").write_text("x", encoding="utf-8")

    assert sync_counts.missing_index_rows() == ["0009-new.md"]


def test_this_repo_is_in_sync_right_now():
    """ทิศที่ทำให้ตัวซิงก์เองไม่เน่า — รูปแบบที่มันหา ต้องยังหาเจอในไฟล์จริง"""
    assert sync_counts.drift() == []
    assert sync_counts.missing_index_rows() == []
