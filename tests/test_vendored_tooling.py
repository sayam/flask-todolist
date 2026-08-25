"""เครื่องมือที่ย้ายไป vendor แล้ว ต้องยังทำงานให้ repo นี้จริง — ADR 0077

`scripts/run_gates.py` กับ `scripts/preflight.py` เหลือเป็น adapter บาง ๆ ที่ชี้
ทะเบียนกับรากของ repo นี้ให้ของใน `vendor/verifiable-gates` · **ตัวตรรกะถูกเทสต์
ที่ต้นทางแล้ว** (repo นั้นมีชุดเทสต์ของตัวเองและ CI ของมันบังคับก่อน pin SHA)
สิ่งที่ยังไม่มีใครตรวจคือ *รอยต่อ* — และรอยต่อคือที่ที่ของพังเงียบที่สุด:
adapter ที่ชี้ path ผิดจะรายงาน "ไม่มี gate ให้รัน" ซึ่งอ่านเหมือนผ่าน

สามข้ออ้างที่เทสต์นี้ถือไว้ให้ ตรงกับ gate `fail-fix-harness-honest`:

- harness **เห็นทะเบียนของ repo นี้จริง** (ไม่ใช่ทะเบียนว่าง) และรายงาน gate ที่
  แดงว่าแดง
- gate ที่ harness ตัดสินไม่ได้ **ถูกรายงานว่าข้ามพร้อมเหตุผล** ไม่ใช่ถูกนับว่าผ่าน
- preflight **อ่านคำสั่งจาก workflow จริงของ repo นี้** ไม่ใช่จากสำเนาที่สอง
"""

from __future__ import annotations

import json
import pathlib
from typing import TYPE_CHECKING

from scripts import preflight, run_gates

if TYPE_CHECKING:
    import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_the_harness_reads_this_repos_registry(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """adapter ที่ชี้ทะเบียนผิดจะรายงาน 0 gate ซึ่งอ่านเหมือน "ไม่มีอะไรเสีย"."""
    report = tmp_path / "report.json"
    run_gates.main(["--only", "gates-carry-red-evidence", "--output", str(report)])
    capsys.readouterr()

    results = json.loads(report.read_text(encoding="utf-8"))["results"]
    assert [r["gate"] for r in results] == ["gates-carry-red-evidence"]
    assert results[0]["status"] == "pass"


def test_a_gate_the_harness_cannot_decide_is_reported_as_skipped(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """gate ที่บังคับใน CI ต้องไม่ถูกนับว่าผ่านตอนรันบนเครื่อง"""
    report = tmp_path / "report.json"
    run_gates.main(["--only", "suite-on-three-brands", "--output", str(report)])
    capsys.readouterr()

    entry = json.loads(report.read_text(encoding="utf-8"))["results"][0]
    assert entry["status"] == "skip", "gate ที่ตัดสินไม่ได้ถูกนับว่าผ่าน"
    assert "enforced by CI job" in entry["cause"]


def test_the_preflight_adapter_points_at_this_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    """ตรวจที่ *รอยต่อ* ไม่ใช่ที่ฟังก์ชันปลายทาง

    รุ่นแรกของเทสต์นี้เรียก `jobs_on_disk(ROOT)` ตรง ๆ ซึ่งข้าม adapter ไปทั้งตัว —
    ผมทำให้ adapter ชี้รากผิดแล้วมันยังเขียว · เทสต์ที่ไม่เดินผ่านบรรทัดที่ตัวเอง
    อ้างว่าคุ้ม ก็คือเทสต์ที่ไม่ได้คุ้มอะไร
    """
    seen: list[list[str]] = []
    monkeypatch.setattr(preflight.preflight, "main", lambda argv: seen.append(argv) or 0)

    assert preflight.main(["--only", "lint"]) == 0
    assert seen == [["--root", str(ROOT), "--only", "lint"]], (
        "adapter ไม่ได้ส่งรากของ repo นี้ หรือกลืน argument ของผู้เรียก"
    )


def test_the_harness_adapter_points_at_this_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []
    monkeypatch.setattr(run_gates.harness, "main", lambda argv: seen.append(argv) or 0)

    assert run_gates.main(["--only", "x"]) == 0
    assert seen == [["--registry", str(ROOT / "gates.yaml"), "--root", str(ROOT), "--only", "x"]]


def test_preflight_reads_the_commands_from_this_repos_workflow() -> None:
    """คำสั่งต้องมาจาก `.github/workflows/` ของจริง — สำเนาที่สองจะ drift ทันที

    ตรวจที่ *แผน* ไม่ใช่ที่การรัน เพราะการรันชุดเต็มในเทสต์คือการรัน CI ซ้อน CI
    """
    workflow = {"jobs": preflight.preflight.jobs_on_disk(ROOT)}
    assert "lint" in workflow["jobs"], "อ่าน job ของ repo นี้ไม่เจอ"

    entries = preflight.preflight.plan(workflow, ("lint",), "main")
    assert any("ruff check" in e.get("run", "") for e in entries), "ไม่เห็นคำสั่งจริงของ job lint"

    steps = workflow["jobs"]["lint"]["steps"]
    assert len(entries) == len(steps), "แผนทิ้ง step ไป — มั่นใจผิดแบบเดียวกับ harness ที่โกหก"
    assert all("run" in e or "skip" in e for e in entries)


def test_the_vendored_tools_are_the_ones_being_used() -> None:
    """adapter ต้องเรียกของใน vendor ไม่ใช่สำเนาที่หลงเหลือใน repo นี้"""
    for module in (run_gates.harness, preflight.preflight):
        where = pathlib.Path(module.__file__ or "")
        assert (ROOT / "vendor") in where.parents, f"{module.__name__} ไม่ได้มาจาก vendor: {where}"


# ---------------------------------------------------- ตัวตัดสินที่ย้ายไปขั้น 3a
#
# `lint_commits` กับ `check_issue_handoff` ย้ายไป `verifiable-gates` แล้ว (ADR 0077
# ขั้น 3a) และถูกทดสอบสองทิศที่นั่น · ที่เหลือให้พิสูจน์ที่นี่คือ **รอยต่อ** —
# พาธที่ hook กับ workflow เรียกถึง ยังเดินไปถึงตัวจริงไหม
#
# เทสต์ที่เรียกฟังก์ชันปลายทางตรง ๆ พิสูจน์เรื่องนั้นไม่ได้ (บทเรียนของขั้น 2e:
# ฉบับแรกข้าม adapter ไปเลย แล้วยังเขียวตอนชี้รากผิด) — จึงขับผ่าน `main()`
# ของ adapter ด้วย argv จริง


def test_the_commit_linter_adapter_reaches_the_real_decider(tmp_path, monkeypatch, capsys):
    """โหมด `--msg-file` คือทางที่ hook `commit-msg` ใช้ทุกครั้งที่มีคน commit"""
    from scripts import lint_commits as adapter

    message = tmp_path / "COMMIT_EDITMSG"
    message.write_text("feat(x): หัวที่ถูกต้อง\n\nSigned-off-by: A B <a@b.co>\n", encoding="utf-8")

    monkeypatch.setattr("sys.argv", ["lint_commits.py", "--msg-file", str(message)])
    assert adapter.main() == 0
    assert "passes" in capsys.readouterr().out

    message.write_text("แก้บั๊ก\n\nSigned-off-by: A B <a@b.co>\n", encoding="utf-8")
    assert adapter.main() == 1, "adapter ปล่อยหัวที่ผิดรูปผ่าน — hook จะเงียบตอนที่ควรบล็อก"


def test_the_commit_linter_adapter_exports_what_its_callers_read():
    """`tests/test_dependabot.py` อ่าน `TYPES` จากที่นี่ — ค่าต้องมาจากตัวจริง ไม่ใช่สำเนา"""
    from verifiable_gates import lint_commits as real

    from scripts import lint_commits as adapter

    assert adapter.TYPES is real.TYPES
    assert adapter.MAX_TITLE == real.MAX_TITLE


def test_the_issue_handoff_adapter_reaches_the_real_decider(monkeypatch, capsys):
    """job `lint` เรียกพาธนี้โดยไม่ส่ง flag — บริบทมาจาก env ล้วน"""
    from scripts import check_issue_handoff as adapter

    monkeypatch.delenv("PR_NUMBER", raising=False)
    monkeypatch.setattr("sys.argv", ["check_issue_handoff.py"])

    assert adapter.main() == 0
    assert "only means anything" in capsys.readouterr().out


def test_the_issue_handoff_adapter_exports_the_real_label():
    from verifiable_gates import check_issue_handoff as real

    from scripts import check_issue_handoff as adapter

    assert adapter.LABEL == real.LABEL
    assert adapter.problems is real.problems
