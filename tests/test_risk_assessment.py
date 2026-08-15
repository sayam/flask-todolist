"""`docs/RISK-ASSESSMENT.md` ต้องมีโครงครบ ระดับตรงสูตร และหลักฐานชี้ของจริง

ปิดข้อ 6.1/8.2 ของ ISO 27001: วิธีที่ประกาศต้องตรวจได้ — ระดับความเสี่ยง
คำนวณจากสูตรที่เขียนไว้ (ผลคูณ) ไม่ใช่ความรู้สึกต่อแถว · แถวระดับ `สูง`
ต้องมีกลไกจริงใน backtick ตามเกณฑ์รับความเสี่ยงของไฟล์เอง · และรอบทบทวน
ต้องมีแถวจริงใน SECURITY-CADENCE (เทสต์ cadence เป็นคนทวงกำหนด)
"""

import pathlib
import re

import pytest
import yaml  # type: ignore[import-untyped]

from tests.test_asvs import _unresolved

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "RISK-ASSESSMENT.md"

SCORE = {"ต่ำ": 1, "กลาง": 2, "สูง": 3}
ROW = re.compile(
    r"^\|([^|]+)\|\s*(ต่ำ|กลาง|สูง)\s*\|\s*(ต่ำ|กลาง|สูง)\s*\|\s*(ต่ำ|กลาง|สูง)\s*\|([^|]*)\|([^|]*)\|\s*$",
    re.MULTILINE,
)

REQUIRED_HEADINGS = (
    "## วิธี (methodology)",
    "## เกณฑ์รับความเสี่ยง (acceptance)",
    "## ทะเบียนความเสี่ยง",
    "## รอบทบทวน",
)


@pytest.fixture(scope="module")
def text():
    return DOC.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def rows(text):
    return ROW.findall(text)


def _expected_level(likelihood, impact):
    product = SCORE[likelihood] * SCORE[impact]
    if product >= 6:
        return "สูง"
    return "กลาง" if product >= 3 else "ต่ำ"


def test_the_method_sections_exist(text):
    missing = [h for h in REQUIRED_HEADINGS if h not in text]
    assert not missing, f"หัวข้อที่วิธีประเมินขาดไม่ได้หายไป: {missing}"


def test_the_register_is_not_empty(rows):
    assert len(rows) >= 5, f"ทะเบียนมีแค่ {len(rows)} แถว — การประเมินรอบแรกครอบทั้งระบบไม่น่าต่ำกว่านี้"


def test_every_level_follows_the_declared_formula(rows):
    wrong = [
        (name.strip(), likelihood, impact, level, _expected_level(likelihood, impact))
        for name, likelihood, impact, level, _t, _r in rows
        if level != _expected_level(likelihood, impact)
    ]
    assert not wrong, (
        "ระดับไม่ตรงสูตรผลคูณที่ไฟล์ประกาศเอง (ชื่อ, โอกาส, ผลกระทบ, ที่เขียน, ที่ควรเป็น):\n"
        + "\n".join(map(str, wrong))
    )


def test_high_risks_carry_a_real_mechanism(rows):
    bare = [
        name.strip()
        for name, _l, _i, level, treatment, _r in rows
        if level == "สูง" and not re.search(r"`[^`]+`", treatment)
    ]
    assert not bare, f"ความเสี่ยงระดับสูงที่ไม่มีกลไกจริงใน backtick (เกณฑ์ของไฟล์เอง): {bare}"


def test_every_treatment_reference_resolves(rows):
    ci_jobs = set()
    for path in (ROOT / ".github" / "workflows").glob("*.y*ml"):
        ci_jobs |= set((yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("jobs") or {})
    gate_ids = {
        g["id"] for g in yaml.safe_load((ROOT / "gates.yaml").read_text(encoding="utf-8"))["gates"]
    }
    dead = []
    for name, _l, _i, _level, treatment, residual in rows:
        for ref in re.findall(r"`([^`]+)`", treatment + residual):
            gate = re.fullmatch(r"gate ([a-z0-9-]+)", ref)
            if gate:
                if gate.group(1) not in gate_ids:
                    dead.append(f"{name.strip()}: ไม่มี gate {gate.group(1)!r}")
                continue
            if ref == "DATA_ENCRYPTION_KEY":
                continue
            reason = _unresolved(ref, ci_jobs)
            if reason:
                dead.append(f"{name.strip()}: `{ref}` — {reason}")
    assert not dead, "กลไกที่อ้างแต่ไม่มีจริง:\n  " + "\n  ".join(dead)


def test_the_full_review_has_a_cadence_row():
    cadence = (ROOT / "docs" / "SECURITY-CADENCE.md").read_text(encoding="utf-8")
    assert "ประเมินความเสี่ยงเต็มรอบ" in cadence, (
        "SECURITY-CADENCE ไม่มีแถวประเมินความเสี่ยงเต็มรอบ — รอบที่ไม่มีใครทวงคือรอบที่ไม่เกิด"
    )
