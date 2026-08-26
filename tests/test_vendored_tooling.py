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


# ---------------------------------------------------- ตัวอ่านที่ย้ายไปขั้น 3b
#
# ห้าโมดูลย้ายไป `verifiable-gates` แล้วและถูกทดสอบสองทิศที่นั่น (มิวเทชัน 24 จุด)
# · ที่นี่พิสูจน์ **รอยต่อ** — adapter ชี้รากของ repo นี้จริงไหม
#
# `gh` กับ `workflows` ยังมี adapter อยู่เพราะ `audit_posture` (3e) และ
# `sync_counts` (3d) ยัง `import` มันตรง ๆ · สองไฟล์นั้นย้ายเมื่อไหร่ adapter หายตาม


def test_the_skeleton_adapter_reads_this_repos_files(capsys):
    """ทางที่คนกับ agent เรียกจริง — ชี้ไฟล์ของ repo นี้แล้วต้องได้พื้นผิวจริง"""
    from scripts import skeleton as adapter

    assert adapter.main(["app/theme.py"]) == 0
    out = capsys.readouterr().out
    assert "def resolve_mode" in out, "อ่านไฟล์ของ repo นี้ไม่เจอพื้นผิวที่มีอยู่จริง"


def test_the_schedule_census_adapter_points_at_this_repos_root(tmp_path, capsys):
    """adapter ที่ชี้รากผิดจะรายงานว่าไม่มีตารางเวลาเลย ซึ่งอ่านเหมือน 'ไม่มีอะไรต้องเฝ้า'

    ป้อนประวัติเปล่าเข้าไป ตัวสำมะโนจึงต้องรายงานว่าทุกตารางไม่เคยยิง — ซึ่ง
    *พิสูจน์ว่ามันอ่าน workflow ของ repo นี้เจอจริง* · สิ่งที่รอยต่อต้องพิสูจน์
    คือมันมองเห็นของที่นี่ ไม่ใช่คำตัดสิน (คำตัดสินถูกทดสอบสองทิศที่ vg แล้ว)
    """
    from scripts import schedule_census as adapter

    state = tmp_path / "state.json"
    state.write_text('{"last_scheduled_run": {}}', encoding="utf-8")

    code = adapter.main(["--input", str(state)])
    captured = capsys.readouterr()

    assert code == 1, "ประวัติเปล่าแล้วยังผ่าน — แปลว่ามันไม่เห็น workflow ของที่นี่เลย"
    assert "nothing to watch" not in captured.out, "adapter มองไม่เห็น workflow ของ repo นี้"
    assert "dependabot" in captured.out, "ไม่ได้อ่าน .github/dependabot.yml ของ repo นี้"
    assert ".yml:" in captured.err, "แดงแล้วแต่ไม่ได้บอกว่า workflow ไหน"


def test_the_red_streak_adapter_points_at_this_repos_registry(tmp_path, capsys):
    """ตัววัดต้องเห็น `gates.yaml` ของที่นี่ ไม่งั้นจะไม่มีคำสัญญาไหนถูกวัดเลย"""
    from scripts import red_streak_census as adapter

    runs = tmp_path / "runs.json"
    runs.write_text("[]", encoding="utf-8")

    assert adapter.main(["--input", str(runs)]) == 0
    out = capsys.readouterr().out
    assert "0 watched workflows" not in out, "adapter มองไม่เห็นทะเบียนของ repo นี้"


def test_the_helper_adapters_still_serve_the_scripts_that_have_not_moved():
    """`audit_posture` กับ `sync_counts` ยัง import สองตัวนี้ตรง ๆ — ต้องใช้ได้เหมือนเดิม"""
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import gh
    import workflows
    from verifiable_gates import gh as real_gh

    assert gh.api is real_gh.api
    assert workflows.WORKFLOW_DIR == ROOT / ".github" / "workflows"
    assert "ci.yml" in workflows.all_workflows(), "ตัวห่อไม่ได้ชี้ workflow ของ repo นี้"


def test_the_probe_adapter_reaches_the_real_instrument(tmp_path, capsys) -> None:
    """ตัววัดของการทดลองย้ายไป vg แล้ว — ที่นี่พิสูจน์ว่า *พาธเดิมยังเดินไปถึงตัวจริง*

    คำตัดสินทั้งสิบข้อถูกทดสอบสองทิศที่ vg (แอปที่ละเมิดครบ / ทำครบ ต้องแยก
    ออกจากกันได้ทุกข้อ) · รอยต่อที่ยังไม่มีใครตรวจคือ adapter ที่ export ชื่อ
    ผิดตัว ซึ่งอ่านเหมือนใช้ได้จนกว่าจะมีคนเรียกจริง
    """
    from scripts import asvs_probe as adapter

    real = adapter.asvs_probe
    assert (ROOT / "vendor") in pathlib.Path(real.__file__ or "").parents
    assert adapter.probe is real.probe
    assert adapter.CHECKS is real.CHECKS, "adapter ถือรายการข้อคนละชุดกับตัวจริง"

    (tmp_path / "app").mkdir()
    (tmp_path / "run.py").write_text("from app import create_app\n", encoding="utf-8")
    (tmp_path / "app" / "__init__.py").write_text(
        'SECRET_KEY = "hardcoded-secret-value"\n', encoding="utf-8"
    )

    answers = adapter.probe(tmp_path)

    assert set(answers) == set(adapter.CHECKS), "ตอบไม่ครบทุกข้อที่ประกาศไว้"
    assert answers["V6.4.1-secret-not-hardcoded"] is False, "เดินไปไม่ถึงตัวตัดสินจริง"
    assert capsys.readouterr().out == "", "ตัววัดไม่ควรพิมพ์อะไรตอนถูกเรียกเป็นไลบรารี"


def test_the_measurement_adapter_still_runs_from_the_path_people_type(tmp_path) -> None:
    """ตัวสั่งงาน battery ถูกเรียกด้วยพาธนี้ในเอกสารและใน session ของ agent

    ป้อนรากที่ไม่มีแอปเลย: ต้องได้ผลว่างพร้อมบอกว่าไม่มีอะไรให้วัด — ซึ่งพิสูจน์ว่า
    มันเดินถึงตัวจริงและเขียนไฟล์ผลออกมาได้ · **ตัวเลขที่มันนับถูกทดสอบที่ vg**
    """
    import json as json_module
    import subprocess
    import sys

    script = ROOT / "scripts" / "measure_generated.py"
    output = tmp_path / "result.json"
    done = subprocess.run(  # noqa: S603 — คำสั่งคงที่ + interpreter ของ venv เดียวกัน
        [sys.executable, str(script), str(tmp_path), "--output", str(output)],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
        cwd=ROOT,
    )

    assert done.returncode == 0, f"ล้มด้วย: {done.stderr[-400:]}"
    assert json_module.loads(output.read_text(encoding="utf-8")) == []


# ----------------------------------------------- สำมะโนของที่ถูก rerun (ขั้น 5 · ตัวสุดท้าย)
#
# คำตัดสินทั้งชุด (ใครพัง · อะไรถูก rerun จนหาย · ชื่อ check ที่ต้องแปลงกลับ) ถูก
# ทดสอบสองทิศที่ vg แล้ว · รอยต่อที่เหลือให้พิสูจน์ที่นี่มีสองอย่าง: **ถ้อยคำ**
# (adapter ที่ลืมส่ง `MESSAGES` จะพิมพ์อังกฤษโดยไม่มีอะไรแดง) และ **ราก**
# (adapter ที่ชี้ผิดจะรายงานว่าไม่มี job ไหนเคยแดง ซึ่งอ่านเหมือน "ไม่มีอะไรพัง")


def _runs(tmp_path: pathlib.Path, records: list[dict]) -> str:
    path = tmp_path / "runs.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return str(path)


def test_the_rerun_census_adapter_reports_in_this_repos_language(tmp_path, capsys) -> None:
    """ตัวเลขที่ถูกต้องในภาษาที่คนอ่านไม่ออก คือรายงานที่ไม่มีใครอ่าน"""
    from scripts import rerun_census as adapter

    hidden = [
        {
            "id": 1,
            "attempt": 2,
            "failures": [{"attempt": 1, "job": "dast", "step": "ZAP", "message": "FAIL-NEW"}],
        }
    ]

    assert adapter.main(["--input", _runs(tmp_path, hidden), "--max-hidden", "0"]) == 1

    printed = capsys.readouterr()
    assert "ล้มแล้วถูก rerun จนหายไป    : 1" in printed.out, printed.out
    assert "ซ่อน 1" in printed.out, "ของที่ซ่อนอยู่ต้องเด่นกว่าของที่ทุกคนเห็นอยู่แล้ว"
    assert "ของเรา" in printed.out, "ชื่อชั้นยังเป็นค่าเครื่อง — ไม่ได้ถูกแปลตอนพิมพ์"
    assert "เพดาน 0" in printed.err, printed.err


def test_the_rerun_census_adapter_reads_this_repos_workflows(tmp_path, capsys) -> None:
    """หน้าต่างเปล่าแปลว่าทุก job ของ repo นี้ต้องโผล่ในรายการที่ไม่เคยแดง"""
    from scripts import rerun_census as adapter

    assert adapter.main(["--input", _runs(tmp_path, []), "--never-red"]) == 0
    out = capsys.readouterr().out

    # สามชื่อจากสามไฟล์ — adapter ต้อง glob ทั้งไดเรกทอรี ไม่ใช่อ่านไฟล์เดียว
    # (job `posture` ย้ายจาก `scorecard.yml` ไป `posture.yml` เมื่อ 2026-08-27
    # ตัวที่อ่านไฟล์เดียวจึงเคยเขียวได้ทั้งที่มองไม่เห็นครึ่งหนึ่งของ repo)
    assert "dialects" in out, "adapter มองไม่เห็น ci.yml ของ repo นี้"
    assert "posture" in out, "adapter มองไม่เห็น posture.yml ของ repo นี้"
    assert "scorecard" in out, "adapter มองไม่เห็น scorecard.yml ของ repo นี้"


def test_the_rerun_census_adapter_maps_a_matrix_name_back(tmp_path, capsys) -> None:
    """`dialect (mysql-8)` ต้องถูกนับเป็น `dialects` — ไม่งั้นรายงานฉบับเดียวขัดกันเอง

    ฝั่งที่นับความล้มเหลวอ่าน *ชื่อ check* จาก API ส่วนฝั่ง "ไม่เคยแดง" อ่าน *ไอดี*
    จากไฟล์ workflow ของที่นี่ — สองฝั่งนี้จะแมตช์กันได้ก็ต่อเมื่อ adapter ชี้ราก
    ที่มี `ci.yml` ตัวจริงอยู่
    """
    from scripts import rerun_census as adapter

    matrix = [
        {
            "id": 2,
            "attempt": 1,
            "failures": [
                {"attempt": 1, "job": "dialect (mysql-8)", "step": "pytest", "message": "assert"}
            ],
        }
    ]

    assert adapter.main(["--input", _runs(tmp_path, matrix), "--never-red"]) == 0
    out = capsys.readouterr().out

    assert "    dialects: 1" in out, out
    assert "dialects" not in out.split("ไม่แดงเลยในหน้าต่างนี้")[1], "job ที่เพิ่งล้มยังถูกรายงานว่าไม่เคยแดง"
