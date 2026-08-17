"""preflight ต้องสะท้อน CI จริง ไม่ใช่รายการคำสั่งที่ลอกไว้ — audit governance รอบ 6

สองเรื่องที่ต่างกันและต้องจริงทั้งคู่:

1. **ไม่มี step ไหนหายเงียบ ๆ** — ทุก step ของ job ที่ mirror ไว้ต้องปรากฏพอดี
   หนึ่งครั้ง ในสถานะ "รัน" หรือ "ข้ามพร้อมเหตุผล" (หลักเดียวกับ
   `tests/test_harness.py`: harness ที่รายงานผ่านตอนของแดง คือ harness ที่
   ป้อนความมั่นใจผิด ๆ ให้คนที่เชื่อมัน)
2. **มันครอบด่านที่ hook ตรวจไม่ได้จริง** — xenon · interrogate · diff-cover
   คือคลาสความผิดพลาดที่ทำให้ PR แดงทั้งที่เครื่องเขียว · preflight ที่ไม่ครอบ
   สามตัวนี้คือ preflight ที่แก้ปัญหาคนละข้อกับที่มันถูกสร้างมาแก้
"""

import pathlib
import subprocess
import sys

import pytest
import yaml

from scripts.preflight import CONFIG, WORKFLOW_DIR, jobs_on_disk, plan, wanted_jobs

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "preflight.py"


@pytest.fixture(scope="module")
def real_workflow() -> dict:
    """workflow ทุกไฟล์รวมเป็นก้อนเดียว — job ไม่ซ้ำชื่อข้ามไฟล์อยู่แล้ว"""
    return {"jobs": jobs_on_disk(ROOT)}


@pytest.fixture(scope="module")
def mirrored() -> tuple[str, ...]:
    """job ที่ repo นี้ประกาศให้ preflight เดิน — อ่านจาก scaffold.json จริง"""
    return wanted_jobs(ROOT, [])


def test_every_step_is_either_run_or_skipped_with_a_reason(real_workflow, mirrored):
    """สองทิศของความซื่อสัตย์: ไม่มีของหาย และของที่ข้ามต้องบอกว่าทำไม"""
    entries = plan(real_workflow, mirrored, "main")
    declared = sum(len(real_workflow["jobs"][job]["steps"]) for job in mirrored)
    assert len(entries) == declared, f"step ใน workflow {declared} ตัว แต่แผนมี {len(entries)}"
    for entry in entries:
        assert ("run" in entry) ^ ("skip" in entry), f"สถานะกำกวม: {entry}"
        if "skip" in entry:
            assert entry["skip"].strip(), f"ข้ามโดยไม่บอกเหตุผล: {entry['label']}"


def test_it_covers_the_checks_the_commit_hook_cannot(real_workflow, mirrored):
    """ด่านที่ hook มองไม่เห็น ต้องอยู่ในแผนจริง ๆ ไม่ใช่แค่ในเจตนา"""
    commands = " ".join(e["run"] for e in plan(real_workflow, mirrored, "main") if "run" in e)
    for tool in ("xenon", "interrogate", "diff-cover", "--cov"):
        assert tool in commands, f"preflight ไม่ได้เดิน {tool} — คลาสที่มันถูกสร้างมาดักหลุดไป"


def test_expressions_of_ci_are_resolved_or_the_step_is_skipped():
    """`${{ }}` ที่แทนค่าไม่ได้ ต้องกลายเป็นการข้าม ไม่ใช่คำสั่งที่รันแล้วเพี้ยน"""
    workflow = {
        "jobs": {
            "x": {
                "steps": [
                    {
                        "name": "ฐานที่แทนได้",
                        "run": "diff-cover --compare-branch origin/${{ github.base_ref }}",
                    },
                    {"name": "ของที่แทนไม่ได้", "run": "echo ${{ secrets.TOKEN }}"},
                ]
            }
        }
    }
    resolved, unresolved = plan(workflow, ("x",), "trunk")
    assert resolved["run"].endswith("origin/trunk"), resolved
    assert "secrets.TOKEN" in unresolved["skip"], unresolved


def test_environment_steps_are_skipped_by_declaration():
    """step ที่จัดสภาพแวดล้อมต้องไม่ถูกรัน — มันแก้ .venv ของคนที่กดรัน"""
    workflow = {"jobs": {"x": {"steps": [{"run": "pipenv sync --dev"}, {"run": "pip install x"}]}}}
    assert all("skip" in entry for entry in plan(workflow, ("x",), "main"))


def _run(tmp_path: pathlib.Path, steps: list[dict]) -> subprocess.CompletedProcess:
    workflow = tmp_path / WORKFLOW_DIR / "ci.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(yaml.safe_dump({"jobs": {"lint": {"steps": steps}}}), encoding="utf-8")
    return subprocess.run(  # noqa: S603 — ยิงสคริปต์เหมือนที่คนรันจริง
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "--only", "lint"],
        capture_output=True,
        text=True,
        check=False,
    )


def test_a_failing_step_makes_preflight_red(tmp_path):
    """ทิศ "แดงเมื่อควรแดง" — และต้องบอกว่า step ไหน ไม่ใช่แค่ exit code"""
    result = _run(tmp_path, [{"name": "ด่านที่แดง", "run": "exit 3"}])
    assert result.returncode == 1, result.stdout
    assert "ด่านที่แดง" in result.stdout
    assert "1 แดง" in result.stdout


def test_clean_input_stays_green(tmp_path):
    """ทิศ "ผ่านเมื่อควรผ่าน" — เตือนลวงทำให้คนเลิกรัน preflight ภายในสัปดาห์เดียว"""
    result = _run(tmp_path, [{"name": "ด่านที่ผ่าน", "run": "true"}])
    assert result.returncode == 0, result.stdout
    assert "0 แดง" in result.stdout


def test_an_unknown_job_is_an_error_not_a_silent_pass(tmp_path):
    """job ที่ถูกเปลี่ยนชื่อใน workflow ต้องดัง ไม่ใช่ "ไม่มีอะไรให้รัน = ผ่าน" """
    workflow = tmp_path / WORKFLOW_DIR / "ci.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(yaml.safe_dump({"jobs": {"lint": {"steps": []}}}), encoding="utf-8")
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(SCRIPT), "--root", str(tmp_path), "--only", "ghost"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2, result.stdout
    assert "ghost" in result.stderr


def test_the_jobs_to_walk_come_from_config_not_from_this_repos_names(tmp_path):
    """ไฟล์นี้ถูกส่งออกไปกับ overlay — ชื่อ job ของ repo นี้ห้ามฝังอยู่ในตัวมัน

    ลำดับที่ชนะกัน: บรรทัดคำสั่ง > `scaffold.json` > ค่าเริ่มต้น · ปลายทางที่
    ตั้งชื่อ job ต่างจากเรา ต้องได้เครื่องมือที่เดินของเขา ไม่ใช่ของเรา (ADR 0063)
    """
    assert wanted_jobs(tmp_path, ["only-this"]) == ("only-this",)
    assert wanted_jobs(tmp_path, []) == ("lint", "test"), "ไม่มี config ต้องตกที่ค่าเริ่มต้น"

    (tmp_path / CONFIG).write_text('{"preflight_jobs": ["scans"]}', encoding="utf-8")
    assert wanted_jobs(tmp_path, []) == ("scans",), "config ต้องชนะค่าเริ่มต้น"
    assert wanted_jobs(tmp_path, ["cli"]) == ("cli",), "บรรทัดคำสั่งต้องชนะ config"


def test_jobs_are_found_across_every_workflow_file(tmp_path):
    """job อยู่คนละไฟล์กันได้ — ผูกกับ `ci.yml` ตัวเดียวคือการผูกกับ repo นี้"""
    (tmp_path / WORKFLOW_DIR).mkdir(parents=True)
    (tmp_path / WORKFLOW_DIR / "ci.yml").write_text(
        yaml.safe_dump({"jobs": {"lint": {"steps": []}}}), encoding="utf-8"
    )
    (tmp_path / WORKFLOW_DIR / "other.yml").write_text(
        yaml.safe_dump({"jobs": {"posture": {"steps": []}}}), encoding="utf-8"
    )

    assert set(jobs_on_disk(tmp_path)) == {"lint", "posture"}
