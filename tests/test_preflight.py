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

from scripts import preflight
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
    result = subprocess.run(  # noqa: S603 - trusted executable and input
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


# ------------- `env:` ของ step เป็นส่วนหนึ่งของคำสั่ง (audit รอบ 17 · ข้อ 3)
#
# เจอตอนที่ D1 ของรอบนี้เพิ่ม step วัด coverage ของ `scripts/` เข้า job `test`:
# CI ตั้ง `COVERAGE_FILE` ไว้นอก workspace เพราะ `coverage combine` จะกลืนข้อมูล
# ของแอปไปด้วย แต่ preflight ทิ้ง `env:` ทั้งก้อน ผลคือคำสั่งเดียวกันบนเครื่อง
# ทับ `.coverage` ของแอป — **ด่านบนเครื่องกับด่านใน CI ตอบคนละคำถาม**


def test_the_env_of_a_step_reaches_the_command(tmp_path):
    """ทิศ "ผ่านเมื่อควรผ่าน" — ค่าที่ประกาศไว้ต้องไปถึงคำสั่งจริง"""
    result = _run(
        tmp_path,
        [
            {
                "name": "อ่านค่าจาก env",
                "run": '[ "$FROM_WORKFLOW" = "ถึงแล้ว" ]',
                "env": {"FROM_WORKFLOW": "ถึงแล้ว"},
            }
        ],
    )

    assert result.returncode == 0, result.stdout


def test_a_step_without_its_env_is_not_reported_as_passing(tmp_path):
    """ทิศ "แดงเมื่อควรแดง" — ถ้า env ไม่ถูกส่ง คำสั่งที่พึ่งมันต้องแดง ไม่ใช่เขียว

    เป็นการพิสูจน์ว่าเทสต์ข้างบนวัดการส่ง env จริง ไม่ใช่วัดว่า `true` คืน 0
    """
    result = _run(tmp_path, [{"name": "ไม่มี env ให้", "run": '[ -n "$FROM_WORKFLOW" ]'}])

    assert result.returncode == 1, result.stdout


def test_the_temp_dir_of_the_runner_is_substituted_not_left_literal():
    """`${{ runner.temp }}` มีของเทียบเท่าบนเครื่อง — ปล่อยไว้ดิบ ๆ = เขียนลง repo"""
    workflow = {
        "jobs": {
            "x": {"steps": [{"run": "true", "env": {"COVERAGE_FILE": "${{ runner.temp }}/cov"}}]}
        }
    }

    (entry,) = plan(workflow, ("x",), "main", temp="/ที่ทิ้งของ")

    assert entry["env"]["COVERAGE_FILE"] == "/ที่ทิ้งของ/cov", entry


def test_an_env_value_that_cannot_be_resolved_skips_the_step():
    """ค่าที่แทนไม่ได้ต้องทำให้ข้ามพร้อมเหตุผล — ไม่ใช่รันด้วยค่าที่เพี้ยน

    หลักเดียวกับ `run` ที่มี expression: การรันคำสั่งที่ **สภาพแวดล้อมไม่ครบ**
    ให้คำตอบที่ต่างจาก CI โดยไม่มีอะไรบอก
    """
    workflow = {
        "jobs": {"x": {"steps": [{"run": "true", "env": {"TOKEN": "${{ secrets.TOKEN }}"}}]}}
    }

    (entry,) = plan(workflow, ("x",), "main")

    assert "skip" in entry, entry
    assert "secrets.TOKEN" in entry["skip"], entry


# --------------- hook ที่ไม่ได้ติดตั้ง คือ hook ที่ไม่มีอยู่ (audit r22 ข้อ 4)
#
# pull request ของผู้ร่วมพัฒนาภายนอกคนแรกมาถึงพร้อม `I001` กับ `W293` ซึ่งเป็น
# สองอย่างที่ hook ก่อน commit แก้ให้เองอัตโนมัติ — คำสั่งติดตั้งอยู่ในบรรทัดที่สอง
# ของหัวข้อ Setup และมันไม่ได้ถูกทำ


def _fake_repo(root, installed):
    """สร้าง `.git/hooks/` ที่มี hook ตามรายการ — เนื้อไฟล์ต้องมีลายเซ็นของ pre-commit"""
    hooks = root / ".git" / "hooks"
    hooks.mkdir(parents=True)
    for kind in installed:
        (hooks / kind).write_text("#!/bin/sh\n# generated by pre-commit\n", encoding="utf-8")
    return root


def test_every_hook_type_that_is_missing_is_named(tmp_path):
    """บอกว่าขาดชนิดไหน ไม่ใช่บอกแค่ว่า "ยังไม่ได้ติดตั้ง" ซึ่งแก้ไม่ถูก"""
    root = _fake_repo(tmp_path, ["pre-commit"])

    assert preflight.missing_hooks(root) == ["commit-msg", "pre-push"]


def test_a_fully_wired_repo_is_silent(tmp_path):
    """เตือนกับสภาพที่ถูกต้อง = เสียงที่จะถูกปิดภายในสัปดาห์เดียว"""
    root = _fake_repo(tmp_path, ["pre-commit", "commit-msg", "pre-push"])

    assert preflight.missing_hooks(root) == []


def test_a_hook_from_something_else_does_not_count(tmp_path):
    """ไฟล์ชื่อถูกแต่ไม่ใช่ของ pre-commit ไม่นับ — ไม่งั้น hook ของเครื่องมืออื่นจะทำให้เงียบ"""
    root = tmp_path
    hooks = root / ".git" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "pre-commit").write_text("#!/bin/sh\necho ของใครก็ไม่รู้\n", encoding="utf-8")

    assert "pre-commit" in preflight.missing_hooks(root)


def test_a_tree_without_git_says_nothing(tmp_path):
    """worktree ที่ไม่มี `.git/hooks` ไม่ใช่ความผิด — เงียบดีกว่าเตือนผิด"""
    assert preflight.missing_hooks(tmp_path) == []


def test_the_warning_reaches_the_person_running_it(tmp_path, capsys, monkeypatch):
    """เตือนแล้วต้องเห็น และต้องบอกคำสั่งที่แก้ได้ทันที"""
    monkeypatch.setattr(preflight, "jobs_on_disk", lambda _root: {"lint": {"steps": []}})
    monkeypatch.setattr(preflight, "wanted_jobs", lambda _root, _chosen: ("lint",))
    monkeypatch.setattr(preflight, "execute", lambda _entries, _root: 0)

    preflight.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out

    assert "hook ที่ยังไม่ได้ติดตั้ง" not in out, "ไม่มี .git/hooks ต้องไม่เตือน"

    _fake_repo(tmp_path, ["pre-commit"])
    preflight.main(["--root", str(tmp_path)])
    out = capsys.readouterr().out

    assert "commit-msg" in out
    assert "pre-commit install" in out, "เตือนแล้วแต่ไม่ได้บอกวิธีแก้"
