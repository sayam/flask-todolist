"""ด่าน semgrep ต้องพิสูจน์ได้ว่าสแกนอะไรไปบ้าง ไม่ใช่แค่ว่าไม่เจออะไร

`semgrep scan --quiet --error` ที่ผ่าน แปลว่า "ไม่เจอ" ซึ่งหน้าตาเหมือนกันเป๊ะ
กับ "ไม่ได้ตรวจ" · เจอของจริงมาแล้ว: **ค่าเริ่มต้นในตัว semgrep ตัด `tests/`
ทิ้ง** 61 จาก 136 ไฟล์จึงไม่เคยถูกสแกน ขณะที่คำสั่งใน `ci.yml` เขียนว่าตัดแค่
`migrations` กับ `.venv` — ไม่มีใครโกหก แต่ไม่มีใครวัด

`scripts/check_semgrep.py` เป็นตัวตัดสินแทน exit code ของ semgrep · ที่นี่คุม
สิ่งที่ตรวจได้โดยไม่ต้องรัน semgrep จริง (ซึ่งต้องต่อเน็ตและใช้เวลาเป็นนาที)
"""

import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
SEMGREPIGNORE = ROOT / ".semgrepignore"
CHECKER = ROOT / "scripts" / "check_semgrep.py"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


@pytest.fixture(scope="module")
def semgrep_step() -> str:
    """คำสั่งของ step ที่รัน semgrep — อ่านจาก workflow ตัวจริง"""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = [
        step.get("run", "")
        for step in workflow["jobs"]["security"]["steps"]
        if "semgrep" in (step.get("name") or "")
    ]
    assert len(steps) == 1, f"คาดว่ามี step ของ semgrep หนึ่งอัน เจอ {len(steps)}"
    return steps[0]


def test_the_scan_writes_a_report_the_checker_reads(semgrep_step):
    """`--output` ของ semgrep กับอาร์กิวเมนต์ของตัวตรวจ ต้องเป็นไฟล์เดียวกัน

    คนละไฟล์ = ตัวตรวจอ่านของเก่าหรือพังทันที ซึ่งอย่างหลังยังดีกว่า
    """
    written = re.search(r"--output\s+(\S+)", semgrep_step)
    assert written, "step ของ semgrep ไม่ได้เขียนรายงานออกมาเลย"

    read = re.search(r"check_semgrep\.py\s+(\S+)", semgrep_step)
    assert read, "step ของ semgrep ไม่ได้เรียก scripts/check_semgrep.py"

    assert written.group(1) == read.group(1), (
        f"semgrep เขียนไปที่ {written.group(1)} แต่ตัวตรวจอ่าน {read.group(1)}"
    )


def test_the_scan_asks_for_the_fields_the_checker_needs(semgrep_step):
    """`--json` ให้รายชื่อไฟล์ · `--time` ให้รายชื่อกฎที่ถูกใช้จริง

    ขาด `--time` แล้ว `time.rules` จะว่าง ซึ่งตัวตรวจถือว่าแดงอยู่แล้ว —
    เทสต์นี้ทำให้รู้ตั้งแต่ก่อน push แทนที่จะรู้ตอน CI แดงกลาง run
    """
    for flag in ("--json", "--time"):
        assert flag in semgrep_step, f"ขาด {flag} — รายงานจะไม่มีข้อมูลที่ตัวตรวจต้องใช้"


def test_nothing_silences_the_scan_before_the_checker_sees_it(semgrep_step):
    """`--error` ทำให้ semgrep ตายก่อน แล้วตัวตรวจไม่ได้รายงานว่าเจออะไร

    ตัวตัดสินต้องมีตัวเดียว ไม่งั้นเส้นทางที่ล้มจะไม่เคยเดินผ่านตัวที่เราเขียน
    """
    assert "--error" not in semgrep_step, "`--error` ทำให้ step ตายก่อนถึงตัวตรวจ"


def test_the_scan_scope_is_declared_in_the_repo_not_inherited(semgrep_step):
    """ขอบเขตต้องอยู่ในไฟล์ที่ commit ไว้ ไม่ใช่ค่าเริ่มต้นที่มองไม่เห็น"""
    assert SEMGREPIGNORE.is_file(), (
        "ไม่มี .semgrepignore — semgrep จะใช้ค่าเริ่มต้นในตัวซึ่ง**ตัด `tests/` ทิ้ง** โดยไม่มีบรรทัดไหนใน repo บอก"
    )
    assert "--exclude" not in semgrep_step, (
        "ขอบเขตถูกประกาศสองที่ (`--exclude` ใน ci.yml และ .semgrepignore) — "
        "ตัวตรวจอ่านแค่ที่หลัง เซตที่คาดหวังจึงจะผิด"
    )


def test_the_test_suite_itself_is_in_scope():
    """**ข้อที่จับบั๊กจริงได้** — `tests/` เคยหายไปทั้งก้อนโดยไม่มีอะไรฟ้อง

    วัดแล้วว่ารวมเข้ามาได้ 0 finding การไม่สแกนจึงไม่ได้ประหยัดอะไร
    นอกจากทำให้ตัวเลขดูดีกว่าที่เป็น
    """
    lines = SEMGREPIGNORE.read_text(encoding="utf-8").splitlines()
    entries = {
        line.strip().rstrip("/") for line in lines if line.strip() and not line.startswith("#")
    }
    assert "tests" not in entries, "`tests/` ถูกตัดออกจากการสแกนอีกแล้ว"
    assert CHECKER.is_file(), "ไม่มี scripts/check_semgrep.py"
