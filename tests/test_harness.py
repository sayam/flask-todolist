"""fail-fix harness ต้องรายงานตรงความจริงทั้งสามสถานะ — และนับรอบไม่หลง

harness ที่รายงาน "ผ่าน" ตอนที่เทสต์แดง คืออุปกรณ์ที่ป้อนความมั่นใจผิด ๆ ให้
loop ที่เชื่อมันสนิท — ที่นี่พิสูจน์ด้วย gates file สังเคราะห์ใน tmp:
gate ที่ต้องผ่าน · gate ที่ต้องแดง (พร้อมสาเหตุที่ชี้ที่) · gate ที่ต้องถูกข้าม
พร้อมเหตุผล — ยิงผ่าน subprocess เหมือนที่ loop ใช้จริง

การพิสูจน์กับช่องโหว่จริง (11-03) ทำใน worktree แยกและบันทึกผลไว้ที่
`docs/GATE-LOG.md` — เทสต์นี้คุมกลไก ไม่ใช่คุมเหตุการณ์นั้น
"""

import json
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
HARNESS = ROOT / "scripts" / "run_gates.py"


def _gates_file(tmp: pathlib.Path) -> pathlib.Path:
    (tmp / "test_green.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (tmp / "test_red.py").write_text(
        "def test_broken():\n    assert 1 == 2, 'ตั้งใจพัง'\n", encoding="utf-8"
    )
    gates = {
        "version": 1,
        "gates": [
            {
                "id": "green-gate",
                "kind": "test",
                "enforced_by": {"job": "test", "tests": ["test_green.py"]},
            },
            {
                "id": "red-gate",
                "kind": "test",
                "enforced_by": {"job": "test", "tests": ["test_red.py"]},
                "born_from": "กับดักตัวอย่าง",
            },
            {
                "id": "ci-only-gate",
                "kind": "job",
                "enforced_by": {"job": "stack"},
                "requires": ["docker-compose"],
            },
        ],
    }
    path = tmp / "gates.yaml"
    path.write_text(json.dumps(gates), encoding="utf-8")  # JSON เป็น subset ของ YAML
    return path


def _run(tmp: pathlib.Path, *extra: str) -> tuple[subprocess.CompletedProcess, list[dict]]:
    report = tmp / "report.json"
    result = subprocess.run(  # noqa: S603 — ยิง harness เหมือนที่ loop ใช้จริง
        [
            sys.executable,
            str(HARNESS),
            "--gates-file",
            str(_gates_file(tmp)),
            "--root",
            str(tmp),
            "--output",
            str(report),
            *extra,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    results = json.loads(report.read_text(encoding="utf-8"))["results"] if report.exists() else []
    return result, results


def test_all_three_statuses_are_reported_truthfully(tmp_path):
    result, results = _run(tmp_path)
    by_id = {r["gate"]: r for r in results}

    assert by_id["green-gate"]["status"] == "pass"
    assert by_id["red-gate"]["status"] == "fail"
    assert "ตั้งใจพัง" in by_id["red-gate"]["cause"], "สาเหตุต้องพาไปถึง assertion ที่พัง"
    assert by_id["red-gate"]["hint"] == "กับดักตัวอย่าง", "hint ต้องมาจาก born_from"
    assert by_id["ci-only-gate"]["status"] == "skip"
    assert "docker-compose" in by_id["ci-only-gate"]["cause"], "ข้ามต้องบอกว่าขาดอะไร"
    assert result.returncode == 1, "มี gate แดงแล้ว exit ต้องไม่เป็นศูนย์"


def test_the_only_filter_narrows_the_run(tmp_path):
    result, results = _run(tmp_path, "--only", "green-gate")
    assert [r["gate"] for r in results] == ["green-gate"]
    assert result.returncode == 0


def test_an_unknown_gate_id_is_a_usage_error_not_a_silent_pass(tmp_path):
    result, _ = _run(tmp_path, "--only", "no-such-gate")
    assert result.returncode == 2
    assert "no-such-gate" in result.stderr


def test_rounds_accumulate_in_the_log(tmp_path):
    _run(tmp_path)
    _run(tmp_path)
    lines = (tmp_path / ".gate-rounds.jsonl").read_text(encoding="utf-8").splitlines()
    rounds = [json.loads(line) for line in lines]
    assert [r["round"] for r in rounds] == [1, 2], "เลขรอบต้องนับต่อ ไม่รีเซ็ต"
    assert rounds[0]["failed"] == ["red-gate"], "log ต้องจดว่า gate ไหนแดง เพื่อหาตัวที่แดงบ่อย"


@pytest.mark.parametrize("flag", ["--gates-file", "--root", "--only", "--output"])
def test_the_flags_the_loop_depends_on_still_exist(flag):
    """สัญญาของ CLI — loop ภายนอกเรียกด้วย flag พวกนี้ เปลี่ยนชื่อคือ break สัญญา"""
    helptext = subprocess.run(  # noqa: S603 - trusted executable and input
        [sys.executable, str(HARNESS), "--help"], capture_output=True, text=True, check=False
    ).stdout
    assert flag in helptext
