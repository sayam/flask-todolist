"""สำมะโนการถอดแกน governance ต้องตัดสินทุกไฟล์ในขอบเขต และชี้แต่ไฟล์ที่มีจริง — ADR 0075 ข้อ 6 · ขั้น 0

การย้ายของ 100+ ไฟล์ไปอีก repo คือการ*ถอด*ขนาดใหญ่ที่สุดที่ repo นี้เคยทำ และ
ADR 0069 บอกไว้ว่าการถอดต้องเป็นคำตัดสิน ไม่ใช่ผลข้างเคียง · `extraction.yaml`
คือคำตัดสินนั้นทีละไฟล์ — เทสต์นี้บังคับสองทิศแบบเดียวกับ `gates.yaml`:

- **ทุกไฟล์ในขอบเขตต้องถูกตัดสิน** (move / stay / split) — ไฟล์ที่ไม่ถูกตัดสินคือ
  ไฟล์ที่จะถูกลืมไว้ข้างหลัง หรือถูกลากไปโดยไม่มีใครถาม
- **ทุกรายการต้องชี้ไฟล์ที่มีจริง** — เมื่อขั้น 2–5 ย้ายไฟล์ออก รายการของมันต้องหายจาก
  สำมะโนในขั้นเดียวกัน ไม่งั้นสำมะโนจะบอกว่ายังมีของที่ไม่มีแล้ว
- move/split ต้องบอกขั้น (2–6) · stay ห้ามมีขั้น · ทุกรายการมีเหตุผล

ขอบเขตของ "เทสต์ที่เอ่ยถึงของในขอบเขต" คำนวณจากเนื้อไฟล์ ไม่ใช่รายชื่อที่ลอกไว้ —
เทสต์ใหม่ที่ไป import scripts จะโผล่เข้าขอบเขตเองและต้องถูกตัดสิน
"""

from __future__ import annotations

import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "extraction.yaml"

DECISIONS = frozenset({"move", "stay", "split"})
STAGES = frozenset({2, 3, 4, 5, 6})
# เทสต์ที่เอ่ยถึง scripts / overlays / skill — รูปเดียวกับ grep ที่ใช้ตอนทำสำมะโน
MENTIONS = re.compile(r"scripts[./]|overlays/|skill/|SKILL")
TREES = ("scripts", "overlays", "skill", "docs/comparison")
ROOT_FILES = ("gates.yaml", "scaffold.json", "SKILL.md", "SKILL-TODOLIST.md", "CLA.md")


def in_scope() -> set[str]:
    """ทุกไฟล์ที่สำมะโนต้องตัดสิน — คำนวณจากดิสก์ ไม่ใช่จากสำมะโนเอง"""
    found: set[str] = set()
    for tree in TREES:
        for path in (ROOT / tree).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                found.add(path.relative_to(ROOT).as_posix())
    found.update(name for name in ROOT_FILES if (ROOT / name).is_file())
    for path in (ROOT / "tests").glob("*.py"):
        if MENTIONS.search(path.read_text(encoding="utf-8")):
            found.add(path.relative_to(ROOT).as_posix())
    return found


@pytest.fixture(scope="module")
def entries() -> list[dict]:
    data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))
    assert data.get("version") == 1
    assert data["files"], "สำมะโนว่าง"
    return data["files"]


def test_every_entry_is_wellformed(entries):
    problems = []
    for entry in entries:
        path = entry.get("path", "?")
        if entry.get("decision") not in DECISIONS:
            decision = entry.get("decision")
            problems.append(f"{path}: decision {decision!r} ไม่อยู่ใน {sorted(DECISIONS)}")
        stage = entry.get("stage")
        if entry.get("decision") in ("move", "split") and stage not in STAGES:
            problems.append(f"{path}: move/split ต้องบอก stage ใน {sorted(STAGES)} ได้ {stage!r}")
        if entry.get("decision") == "stay" and stage is not None:
            problems.append(f"{path}: stay ห้ามมี stage — ของที่อยู่ไม่มีวันย้าย")
        if not str(entry.get("reason", "")).strip():
            problems.append(f"{path}: ไม่มีเหตุผล — คำตัดสินที่ไม่มีเหตุผลคือคำตัดสินที่ถูกเถียงซ้ำ")
    assert not problems, "\n".join(problems)


def test_no_path_is_decided_twice(entries):
    seen: dict[str, int] = {}
    for entry in entries:
        seen[entry["path"]] = seen.get(entry["path"], 0) + 1
    twice = sorted(path for path, count in seen.items() if count > 1)
    assert not twice, f"ตัดสินซ้ำ: {twice}"


def test_every_file_in_scope_is_decided(entries):
    decided = {entry["path"] for entry in entries}
    missing = sorted(in_scope() - decided)
    assert not missing, (
        "ไฟล์ในขอบเขตที่ยังไม่ถูกตัดสิน (เติมใน extraction.yaml — move/stay/split พร้อมเหตุผล):\n  "
        + "\n  ".join(missing)
    )


def test_every_decided_path_exists(entries):
    ghosts = sorted(entry["path"] for entry in entries if not (ROOT / entry["path"]).is_file())
    assert not ghosts, "สำมะโนชี้ไฟล์ที่ไม่มีแล้ว — ย้ายออกแล้วต้องลบรายการในขั้นเดียวกัน:\n  " + "\n  ".join(
        ghosts
    )


def test_every_decided_path_is_in_scope(entries):
    """ทิศกลับ — สำมะโนตัดสินได้เฉพาะของในขอบเขต ไม่งั้นมันจะกลายเป็นทะเบียนของทุกอย่าง"""
    outside = sorted({entry["path"] for entry in entries} - in_scope())
    assert not outside, f"รายการนอกขอบเขต: {outside}"
