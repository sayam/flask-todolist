"""ตัวตัดสินต้องถูกตัดสิน — เทสต์สองทิศของสคริปต์ที่บอกว่า CI ผ่านหรือไม่ผ่าน

audit governance รอบ 4 ชี้ช่องว่างที่สามรอบแรกมองไม่เห็น: `audit_pins.py` ·
`audit_image.py` · `check_semgrep.py` เป็นคนตัดสินว่า supply chain เขียวหรือแดง
แต่เทสต์ที่มีอยู่ตรวจแค่ **"รายการยกเว้นตรงกับเอกสารไหม"** กับ **"job เรียก
สคริปต์ไหม"** — ไม่มีตัวไหนรัน*ตรรกะการตัดสิน*เลย · กลับเงื่อนไข set arithmetic
สักบรรทัดแล้วชุดเทสต์ทั้งชุดยังเขียว และ CI จะรายงาน "ไม่มีอะไรใหม่" ตลอดไป
ทั้งที่ไม่ได้ตัดสินอะไร — ด่านที่เขียวเปล่าชนิดที่แพงที่สุด เพราะมันคือด่าน
ที่ทุกด่านอื่นของแกน supply chain พิงอยู่

รูปที่ใช้ที่นี่คือรูปเดียวกับ `tests/test_overlay.py` ที่ใช้กับ checker 8 ตัว
ของ overlay มาตลอด: **planted violation ต้องแดง · clean input ต้องเขียว** ·
กฎที่ export ให้คนอื่นถูกทดสอบเข้มกว่าตัวตัดสินที่เราใช้เองไม่ได้

**เดินผ่าน `main()` ตัวจริงที่ CI เรียก** ไม่ใช่ฟังก์ชันที่แยกออกมาให้เทสต์ง่าย
— ปลอมเฉพาะจุดที่ต้องต่อเน็ต/ต้องมี container (pip-audit · npm audit · trivy)
แล้วปล่อยตรรกะตัดสินกับ exit code เดินจริงทั้งเส้น (บทเรียน Phase 7: repro ที่
ไม่เหมือนรูปของคำขอจริง รายงานผ่านในจังหวะที่เราอยากได้ยินที่สุด)
"""

import ast
import json
import pathlib
import re
import shutil
import subprocess
import typing

import pytest
import yaml

from scripts import (
    audit_image,
    audit_pins,
    audit_plugin_deps,
    audit_posture,
    check_ratchets,
    check_semgrep,
    removals_census,
    rerun_census,
    whats_pending,
    workflows,
)
from scripts import workflows as gha


class Case(typing.NamedTuple):
    """หนึ่งกรณีของการตัดสิน — รวมเป็นตัวเดียวเพื่อให้ชื่อพารามิเตอร์อ่านออกในผลเทสต์"""

    found: object
    accepted: list[str]
    expected: int
    why: str


CVE = "CVE-2026-9999"
OTHER_CVE = "CVE-2026-1111"


def _accepted_file(tmp_path: pathlib.Path, ids: list[str]) -> pathlib.Path:
    """ไฟล์รายการยกเว้นปลอม — มีคอมเมนต์ด้วย เพราะตัวอ่านต้องข้ามมันให้ถูก"""
    path = tmp_path / "accepted.txt"
    path.write_text("# เหตุผลอยู่ในเอกสาร ไม่ใช่ที่นี่\n" + "\n".join(ids) + "\n", encoding="utf-8")
    return path


def _trivy_report(tmp_path: pathlib.Path, ids: list[str]) -> pathlib.Path:
    """รายงาน trivy สังเคราะห์ — รูปเดียวกับที่ job `image` เขียนออกมาจริง"""
    vulns = [
        {"VulnerabilityID": i, "PkgName": "libfake", "FixedVersion": "1.2.3", "Severity": "HIGH"}
        for i in ids
    ]
    path = tmp_path / "trivy.json"
    path.write_text(json.dumps({"Results": [{"Vulnerabilities": vulns}]}), encoding="utf-8")
    return path


# --------------------------------------------------------------- audit_image


@pytest.mark.parametrize(
    "case",
    [
        Case([], [], 0, "ไม่เจออะไรและไม่ได้ยกเว้นอะไร = สถานะปกติที่ควรเขียว"),
        Case([CVE], [CVE], 0, "เจอเท่ากับที่ประเมินไว้แล้ว = เขียว"),
        Case([CVE], [], 1, "เจอของที่ยังไม่มีใครตัดสิน = ต้องแดง"),
        Case([], [CVE], 1, "ยกเว้นไว้แต่ไม่โผล่แล้ว = ต้องแดงเหมือนกัน (ทิศที่คนลืม)"),
        Case([CVE, OTHER_CVE], [CVE], 1, "เจอเพิ่มหนึ่งตัวจากที่ยกเว้นไว้ = แดง"),
    ],
)
def test_image_judge_decides_both_ways(tmp_path, monkeypatch, case):
    """สองทิศของ `audit_image.py` — เจอของใหม่แดง และยกเว้นที่ไม่โผล่แล้วก็แดง"""
    monkeypatch.setattr(audit_image, "ROOT", tmp_path)
    monkeypatch.setattr(audit_image, "ACCEPTED", _accepted_file(tmp_path, case.accepted))
    monkeypatch.setattr("sys.argv", ["audit_image.py", str(_trivy_report(tmp_path, case.found))])

    assert audit_image.main() == case.expected, case.why


def test_image_judge_reads_every_result_block(tmp_path, monkeypatch):
    """trivy แยกผลเป็นหลาย Results (OS layer · lang) — อ่านก้อนเดียวคือมองไม่เห็นครึ่งหนึ่ง"""
    report = tmp_path / "multi.json"
    report.write_text(
        json.dumps(
            {
                "Results": [
                    {"Vulnerabilities": []},
                    {"Vulnerabilities": [{"VulnerabilityID": CVE, "Severity": "CRITICAL"}]},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(audit_image, "ROOT", tmp_path)
    monkeypatch.setattr(audit_image, "ACCEPTED", _accepted_file(tmp_path, []))
    monkeypatch.setattr("sys.argv", ["audit_image.py", str(report)])

    assert audit_image.main() == 1, "CVE ที่อยู่ใน Results ก้อนที่สองต้องถูกนับด้วย"


# ---------------------------------------------------------------- audit_pins


@pytest.fixture
def pins_dir(tmp_path):
    """ไดเรกทอรี pins ปลอมที่มีล็อกครบทั้งสองภาษา (python + node)"""
    (tmp_path / "toolA").mkdir()
    (tmp_path / "toolA" / "requirements.txt").write_text("fake==1.0\n", encoding="utf-8")
    (tmp_path / "toolB").mkdir()
    (tmp_path / "toolB" / "package-lock.json").write_text("{}", encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    "case",
    [
        Case({}, [], 0, "สะอาดทั้งสองฝั่ง = เขียว"),
        Case({CVE: "fake"}, [CVE], 0, "เจอเท่าที่ประเมินไว้ = เขียว"),
        Case({CVE: "fake"}, [], 1, "advisory ที่ยังไม่มีใครประเมิน = แดง"),
        Case({}, [CVE], 1, "ยกเว้นไว้แต่หายไปแล้ว = แดง (fix มาถึงแล้วต้องรู้)"),
    ],
)
def test_pins_judge_decides_both_ways(pins_dir, tmp_path, monkeypatch, case):
    """สองทิศของ `audit_pins.py` — ปลอมเฉพาะขา pip-audit/npm audit ที่ต้องต่อเน็ต"""
    monkeypatch.setattr(audit_pins, "ROOT", tmp_path)
    monkeypatch.setattr(audit_pins, "PINS", pins_dir)
    monkeypatch.setattr(audit_pins, "ACCEPTED", _accepted_file(tmp_path, case.accepted))
    monkeypatch.setattr(audit_pins, "audit_pip", lambda _lock: dict(case.found))
    monkeypatch.setattr(audit_pins, "audit_npm", lambda _project: {})

    assert audit_pins.main() == case.expected, case.why


def test_pins_judge_refuses_when_a_whole_language_is_missing(tmp_path, monkeypatch):
    """ฝั่งที่หาไฟล์ล็อกไม่เจอจะ "ผ่าน" เงียบ ๆ ทั้งที่ไม่ได้ตรวจอะไร — ต้อง exit 2"""
    only_python = tmp_path / "pins"
    (only_python / "toolA").mkdir(parents=True)
    (only_python / "toolA" / "requirements.txt").write_text("fake==1.0\n", encoding="utf-8")
    monkeypatch.setattr(audit_pins, "ROOT", tmp_path)
    monkeypatch.setattr(audit_pins, "PINS", only_python)
    monkeypatch.setattr(audit_pins, "audit_pip", lambda _lock: {})
    monkeypatch.setattr(audit_pins, "audit_npm", lambda _project: {})

    assert audit_pins.main() == 2, "ไม่มีล็อกฝั่ง node แล้วยังตอบ 0 = ด่านที่ครอบภาษาเดียว"


# ------------------------------------------------------------ check_semgrep


def _semgrep_report(tmp_path: pathlib.Path, **overrides) -> str:
    """รายงาน semgrep ที่ผ่านทุกเกณฑ์ — แล้วให้แต่ละเทสต์ทุบทีละจุด"""
    report = {
        "paths": {"scanned": ["app/a.py", "tests/b.py"]},
        "results": [],
        "errors": [],
        "skipped_rules": [],
        "time": {"rules": [{"id": "rule-1"}, {"id": "rule-2"}]},
    }
    report.update(overrides)
    path = tmp_path / "semgrep.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    return str(path)


def test_semgrep_judge_passes_a_complete_scan(tmp_path, monkeypatch):
    """สแกนครบตามที่ git รู้จัก + ไม่มี finding = เขียว"""
    monkeypatch.setattr(check_semgrep, "expected_files", lambda: {"app/a.py", "tests/b.py"})

    assert check_semgrep.main(_semgrep_report(tmp_path)) == 0


@pytest.mark.parametrize(
    ("expected_set", "overrides", "why"),
    [
        (
            {"app/a.py", "tests/b.py", "app/never_scanned.py"},
            {},
            "ไฟล์ที่ควรถูกสแกนหายไปหนึ่งไฟล์ = แดง (อาการจริงของบั๊กที่ด่านนี้เกิดมาเพื่อจับ)",
        ),
        ({"app/a.py", "tests/b.py"}, {"time": {"rules": []}}, "ไม่มีกฎถูกใช้เลย = แดง"),
        (
            {"app/a.py", "tests/b.py"},
            {"errors": [{"message": "parse error"}]},
            "semgrep รายงาน error = แดง",
        ),
        (
            {"app/a.py", "tests/b.py"},
            {"skipped_rules": [{"rule_id": "x"}]},
            "มีกฎถูกข้าม = แดง",
        ),
        (
            {"app/a.py", "tests/b.py"},
            {
                "results": [
                    {"path": "app/a.py", "start": {"line": 3}, "check_id": "python.lang.bad"}
                ]
            },
            "เจอ finding = แดง",
        ),
    ],
)
def test_semgrep_judge_fails_on_every_kind_of_incomplete_scan(
    tmp_path, monkeypatch, expected_set, overrides, why
):
    """ทุกวิธีที่การสแกนจะ "ไม่ครบ" ต้องแดง — ไม่ใช่แค่กรณีเจอช่องโหว่"""
    monkeypatch.setattr(check_semgrep, "expected_files", lambda: expected_set)

    assert check_semgrep.main(_semgrep_report(tmp_path, **overrides)) == 1, why


def test_semgrep_judge_tolerates_files_git_does_not_know_yet(tmp_path, monkeypatch):
    """สแกนเกินคือความปลอดภัย สแกนขาดคือรูโหว่ — ไฟล์ที่ยังไม่ commit ต้องไม่ทำให้แดง"""
    monkeypatch.setattr(check_semgrep, "expected_files", lambda: {"app/a.py"})

    assert check_semgrep.main(_semgrep_report(tmp_path)) == 0


# ---------------------------------------------------------------- rerun census
#
# audit รอบ 7 — ตัวนับที่อ่านแค่ผลของ attempt สุดท้าย มองไม่เห็นความล้มเหลว
# ที่ถูก rerun จนเขียว · วัดจริงบน repo นี้: เห็น 7 ใบ ซ่อนอยู่อีก 3 ใบ
# (`dast` สองครั้ง · `codeql` หนึ่งครั้ง) และทั้งสอง job อ่านว่า "ไม่เคยแดง"
# จากวิธีเดิม — ซึ่งเป็นข้อมูลที่ `proved_by` กับเกณฑ์ flake ใช้ตัดสินทั้งคู่


def _records(tmp_path, records) -> str:
    """เขียน record ลงไฟล์แล้วคืน path — โหมด --input คือทางที่เทสต์เดินได้ออฟไลน์"""
    path = tmp_path / "runs.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return str(path)


def _fail(job: str, step: str, message: str = "") -> dict:
    """ความล้มเหลวหนึ่งครั้งในรูปที่ `collect()` สร้าง — **มี `message` เสมอตั้งแต่ r8**"""
    return {"attempt": 1, "job": job, "step": step, "message": message}


HIDDEN_RUN = {"id": 1, "attempt": 2, "failures": [_fail("dast", "ZAP", "FAIL-NEW: 1 alert")]}
VISIBLE_RUN = {"id": 2, "attempt": 1, "failures": [_fail("test", "pytest", "assert 1 == 2")]}
PLATFORM_RUN = {
    "id": 3,
    "attempt": 2,
    "failures": [_fail("codeql (javascript)", "Set up job", "")],
}
GREEN_RUN = {"id": 4, "attempt": 1, "failures": []}

# เหตุการณ์จริง 2026-08-17/18 ที่ audit r8 จับได้: `codeql` ล้มสี่ครั้ง **ไม่ใช่ที่
# `Set up job`** แต่ที่ step ของ action เอง ซึ่งข้างในคือ 503 ของ GitHub
OUTAGE_RUN = {
    "id": 6,
    "attempt": 1,
    "failures": [
        _fail(
            "codeql (python)",
            "Run github/codeql-action/init@v3",
            "Server Error: HTTP 503 while contacting api.github.com",
        )
    ],
}


def test_the_census_sees_the_failure_a_rerun_erased(tmp_path, capsys):
    """ทิศ "แดงเมื่อควรแดง" ของตัวนับ: ของที่หายจาก `gh run list` ต้องยังถูกนับ"""
    rerun_census.main(["--input", _records(tmp_path, [HIDDEN_RUN, VISIBLE_RUN, GREEN_RUN])])

    printed = capsys.readouterr().out
    assert "ล้มแล้วถูก rerun จนหายไป    : 1" in printed, printed
    assert "dast" in printed, printed
    assert "ซ่อน 1" in printed, printed


def test_the_census_reports_zero_on_a_clean_stretch(tmp_path, capsys):
    """ทิศ "ผ่านเมื่อควรผ่าน" — ช่วงที่ไม่มีอะไรแดงต้องไม่ถูกรายงานว่ามีของซ่อน"""
    assert rerun_census.main(["--input", _records(tmp_path, [GREEN_RUN, GREEN_RUN])]) == 0
    printed = capsys.readouterr().out
    assert "ล้มแล้วถูก rerun จนหายไป    : 0" in printed, printed


def test_the_census_separates_the_platforms_failures_from_ours(tmp_path):
    """429 ตอนโหลด action ไม่ใช่ flake ของด่านเรา — ปนกันแล้วเกณฑ์ flake ถูกมลพิษ"""
    summary = rerun_census.census([PLATFORM_RUN, HIDDEN_RUN])

    assert summary["failures_by_class"] == {"platform": 1, "ของเรา": 1}


def test_the_census_reads_the_message_not_the_name_of_the_step(tmp_path, capsys):
    """**D1 ของ audit r8** — 503 ของ GitHub ที่ล้มใน action ต้องไม่ถูกอ่านว่าเป็นของเรา

    ฉบับแรกแยกคลาสด้วยชื่อ step อย่างเดียว (`Set up job`) · วันที่ GitHub ล่มจริง
    `codeql` ล้มสี่ครั้งที่ step `Run github/codeql-action/init@…` แล้วถูกนับเป็น
    "ของเรา" ทั้งสี่ — เกณฑ์ flake ของด่านเราจึงสุกงอมด้วยเรื่องที่เราแก้ไม่ได้
    """
    assert rerun_census.classify(OUTAGE_RUN["failures"][0]) == rerun_census.PLATFORM

    summary = rerun_census.census([OUTAGE_RUN])
    assert summary["failures_by_class"] == {"platform": 1}


def test_the_census_refuses_to_guess_that_a_failure_is_ours(tmp_path):
    """ที่จำแนกไม่ได้ต้องออกทาง `ต้องอ่านเอง` — **ห้ามตกไปอยู่ "ของเรา" เงียบ ๆ**

    สองรูปที่ตัดสินด้วยเครื่องไม่ได้: ไม่มี annotation ให้อ่านเลย · และล้มใน action
    ของคนอื่นโดยไม่มีร่องรอยว่าฝั่งไหนพัง (เซิร์ฟเวอร์ของเขา หรือ config ของเรา)
    """
    silent = _fail("stack", "docker compose up", "")
    third_party = _fail("image", "Run docker/build-push-action@v6", "buildx failed")

    assert rerun_census.classify(silent) == rerun_census.UNKNOWN
    assert rerun_census.classify(third_party) == rerun_census.UNKNOWN

    summary = rerun_census.census([{"id": 7, "attempt": 1, "failures": [silent, third_party]}])
    assert summary["failures_by_class"] == {"ต้องอ่านเอง": 2}


def test_the_census_does_not_read_our_own_status_codes_as_an_outage(tmp_path):
    """ทิศตรงข้าม: เลขสถานะที่*เราเอง* assert ไว้ ไม่ใช่หลักฐานว่าโลกพัง

    `/readyz` ของแอปนี้ตอบ 503 โดยตั้งใจ และเทสต์ของมัน assert เลขนั้นตรง ๆ —
    ตัวจำแนกที่จับ "503" ลอย ๆ จะย้ายความล้มเหลวของเราไปอยู่ฝั่งแพลตฟอร์ม
    ซึ่งเป็นความผิดพลาดทิศเดียวกับที่ r8 จับได้ แค่กลับด้าน
    """
    ours = _fail("test", "pipenv run pytest", "assert 200 == 503\nE  where 503 = resp.status_code")

    assert rerun_census.classify(ours) == rerun_census.OURS


def test_the_census_tells_the_reader_what_it_could_not_classify(tmp_path, capsys):
    """ชั้น `ต้องอ่านเอง` ที่ไม่ถูกพิมพ์ออกมา คือชั้นที่ไม่มีใครไปอ่าน"""
    rerun_census.main(
        [
            "--input",
            _records(
                tmp_path,
                [
                    {
                        "id": 8,
                        "attempt": 1,
                        "failures": [
                            _fail("stack", "docker compose up", ""),
                        ],
                    }
                ],
            ),
        ]
    )

    printed = capsys.readouterr().out
    assert "ต้องอ่านเอง" in printed, printed
    assert "OPERATIONS.md" in printed, printed


def test_the_census_fails_when_hidden_failures_pass_the_ceiling(tmp_path):
    """ใช้เป็นด่านตอนทบทวนตามรอบได้ — เพดานที่ไม่มีทางแดงคือเพดานที่ไม่ได้ตั้ง"""
    path = _records(tmp_path, [HIDDEN_RUN, GREEN_RUN])

    assert rerun_census.main(["--input", path, "--max-hidden", "1"]) == 0
    assert rerun_census.main(["--input", path, "--max-hidden", "0"]) == 1


def test_the_census_notices_a_workflow_that_never_started(tmp_path):
    """**จุดบอดของ audit r9** — run ที่ล้มโดยมี 0 job หายไปจากสำมะโนทั้งใบ

    ของจริงที่ซ่อนอยู่ใต้จุดบอดนี้: `scorecard.yml` ล้มทุก run ข้ามวันรวมบน main
    เพราะประกาศ scope ที่ `GITHUB_TOKEN` ไม่มี → job `posture` (ADR 0061) ไม่เคย
    รันเลยสักครั้ง และไม่มีใครเห็นเพราะมันไม่ใช่ required check
    """
    run = {"id": 9, "conclusion": "failure", "run_attempt": 1, "name": "scorecard.yml"}

    made = rerun_census.startup_failure(run, [])

    assert len(made) == 1, "run ที่ล้มโดยไม่มี job ล้ม ต้องถูกบันทึกไว้หนึ่งรายการ"
    assert "scorecard.yml" in made[0]["job"], "ต้องบอกได้ว่า workflow ไหนไม่ได้ start"
    assert rerun_census.classify(made[0]) == rerun_census.OURS
    assert (
        rerun_census.census([{"id": 9, "attempt": 1, "failures": made}])["runs_failed_visible"] == 1
    )


def test_the_census_does_not_invent_failures_that_did_not_happen(tmp_path):
    """ทิศตรงข้าม — run ที่เขียว และ run ที่มี job ล้มอยู่แล้ว ต้องไม่ถูกเติมของปลอม"""
    real = [_fail("test", "pytest", "assert 1 == 2")]

    assert rerun_census.startup_failure({"conclusion": "success"}, []) == []
    assert rerun_census.startup_failure({"conclusion": "failure"}, real) == real


def test_the_census_counts_a_run_once_no_matter_how_many_jobs_failed(tmp_path):
    """หนึ่ง run ที่แดงห้า job คือความล้มเหลวหนึ่งครั้ง — ไม่งั้นสถิติเอียงตามขนาด matrix"""
    crowded = {
        "id": 5,
        "attempt": 1,
        "failures": [
            {"attempt": 1, "job": "stack", "step": "TLS"},
            {"attempt": 1, "job": "siem", "step": "loki"},
            {"attempt": 1, "job": "dast", "step": "ZAP"},
        ],
    }

    assert rerun_census.census([crowded])["runs_failed_visible"] == 1


# ------------------------------------------------- เก็บหลักฐานจากความแดงจริง
#
# audit r9 ข้อ 1 — `UNPROVEN` 76 ตัวนั่งอยู่ที่เพดานพอดีและไม่มีอะไรทวงให้หด
# ขณะที่ CI แดงจริงหลายครั้งต่อสัปดาห์ · ADR 0059 ต้องการหลักฐานว่า gate "เคยแดง
# ตอนของเสียจริง" ซึ่งเกิดขึ้นเองทุกครั้งที่ CI แดงแล้วหายไปกับ log


LOG_WITH_FAILURES = """\
=================================== FAILURES ===================================
tests/test_gates.py:110: AssertionError
=========================== short test summary info ============================
FAILED tests/test_gates.py::test_every_job_has_a_gate - AssertionError: job ...
FAILED tests/test_audit.py::test_chain_survives - assert 1 == 2
1 failed, 1362 passed in 360.37s
"""

GATES_FIXTURE = [
    {"id": "gates-index-two-way", "enforced_by": {"job": "test", "tests": ["tests/test_gates.py"]}},
    {
        "id": "audit-chain",
        "enforced_by": {"job": "test", "tests": ["tests/test_audit.py"]},
        "proved_by": [{"kind": "mutation", "ref": "pr/1"}],
    },
]


def test_the_window_is_as_wide_as_it_was_asked_to_be(monkeypatch):
    """`per_page` ของ GitHub ตันที่ 100 — ขอ 200 แล้วได้ 100 เงียบ ๆ

    แถว cadence สองแถวสั่ง `--limit 200` · ถ้าตัวนับไม่ไล่หน้า หน้าต่างที่วัดจริง
    จะแคบกว่าที่เอกสารบอกครึ่งหนึ่งโดยไม่มีอะไรฟ้อง — ซึ่งคือรูปเดียวกับที่ตัวนับ
    ใบนี้ถูกสร้างมาเพื่อปิด (สถิติที่มองไม่เห็นบางส่วนของความจริง)
    """
    pages: list[str] = []

    def fake(path: str) -> dict:
        pages.append(path)
        page = int(path.split("&page=")[1])
        return {"workflow_runs": [{"id": page * 1000 + i} for i in range(100)] if page <= 2 else []}

    monkeypatch.setattr(rerun_census, "_gh", fake)

    runs = rerun_census._recent_runs(150)

    assert len(runs) == 150, f"ขอ 150 ได้ {len(runs)} — หน้าต่างแคบกว่าที่สั่ง"
    assert len(pages) == 2, f"ต้องไล่สองหน้า ไม่ใช่ {len(pages)}"
    assert "per_page=100&page=1" in pages[0]


def test_the_harvester_reads_which_test_files_went_red(tmp_path):
    """หลักฐานอยู่ใน log ของ job ไม่ใช่ใน annotation — annotation บอกแค่ exit code"""
    found = rerun_census.failing_tests(LOG_WITH_FAILURES)

    assert found == {"tests/test_gates.py", "tests/test_audit.py"}
    assert rerun_census.failing_tests("1362 passed in 360.37s") == set()


def test_the_harvester_proposes_evidence_only_for_gates_that_lack_it(tmp_path):
    """เสนอเฉพาะที่ยังไม่มีหลักฐาน — ที่มีแล้วไม่ต้องการเพิ่ม และเสนอ ไม่ใช่เขียนให้"""
    record = {
        "id": 4242,
        "attempt": 1,
        "failures": [
            {
                **_fail("test", "pipenv run pytest", "Process completed with exit code 1."),
                "tests": ["tests/test_gates.py", "tests/test_audit.py"],
            }
        ],
    }

    proposals = rerun_census.evidence_proposals([record], GATES_FIXTURE)

    assert [p["gate"] for p in proposals] == ["gates-index-two-way"], (
        "gate ที่มี proved_by อยู่แล้วต้องไม่ถูกเสนอซ้ำ และ gate ที่ยังไม่มีต้องถูกเสนอ"
    )
    assert proposals[0]["run"] == 4242, "ต้องชี้ run ที่เป็นหลักฐานได้"


def test_the_harvester_ignores_failures_that_are_not_ours(tmp_path):
    """503 ของ GitHub ไม่ใช่หลักฐานว่าด่านของเราจับอะไรได้ (ADR 0064)"""
    outage = {
        "id": 7,
        "attempt": 1,
        "failures": [
            {
                **_fail("test", "Run github/codeql-action/init@v3", "HTTP 503 from api.github.com"),
                "tests": ["tests/test_gates.py"],
            }
        ],
    }

    assert rerun_census.evidence_proposals([outage], GATES_FIXTURE) == []


# ------------------------------------------------------------- platform posture
#
# audit รอบ 7 ข้อ 2 — ADR 0053 ประกาศว่า main รับของทาง PR เท่านั้นและ
# `enforce_admins` เปิด · ทั้งหมดเป็น setting ฝั่ง GitHub ที่ไม่มีอะไรในเรโปตรวจ
# ตัวควบคุมที่ด่านอื่นทุกตัวพิงอยู่ จึงเป็นตัวเดียวที่ไม่มีใครเฝ้า


# จำนวน required check ที่ใช้ในเทสต์ของช่อง About — เลขอะไรก็ได้ที่คงที่
REQUIRED_NOW = 27

HEALTHY = {
    "required_checks": ["lint", "test"],
    "enforce_admins": True,
    "required_linear_history": True,
    "allow_force_pushes": False,
    "allow_deletions": False,
    "allow_auto_merge": True,
    "delete_branch_on_merge": True,
    "allow_merge_commit": False,
    "allow_rebase_merge": True,
    "allow_squash_merge": False,
    "sha_pinning_required": True,
    "default_workflow_permissions": "read",
    "can_approve_pull_request_reviews": False,
}
ON_PR = {"lint", "test"}


def _audit(state, claim=None):
    """ทุกทิศที่ `main()` เดิน รวมเป็นคำตอบเดียว

    ตัวตัดสินถูกแยกเป็นสองตัวตอนขั้น 3e (ธง/เลขที่โฆษณา กับ required check สามทิศ)
    — คำถามของเทสต์ยังเป็นคำถามเดิม: "ท่าทีที่เลื่อนแบบนี้ถูกจับไหม" จึงต้องถาม
    ทั้งสองตัว ไม่ใช่ตัวใดตัวหนึ่ง
    """
    return audit_posture.compare(state, 2, claim) + audit_posture.check_problems(
        state, ON_PR, ON_PR | set(audit_posture.EXEMPT)
    )


def test_posture_passes_when_the_platform_matches_what_we_declared():
    """ทิศ "ผ่านเมื่อควรผ่าน" — ท่าทีที่ตรงทุกข้อต้องไม่มีเสียงบ่น"""
    assert _audit(HEALTHY, (2, 2)) == []


@pytest.mark.parametrize(
    ("change", "why"),
    [
        ({"enforce_admins": False}, "ผู้ดูแลข้ามด่านได้อีกครั้ง — ข้อที่ ADR 0053 ตั้งใจปิด"),
        ({"required_linear_history": False}, "ประวัติแตกสายได้"),
        ({"allow_force_pushes": True}, "เขียนทับประวัติได้"),
        ({"allow_deletions": True}, "ลบ branch หลักได้"),
        ({"allow_auto_merge": False}, "วิธี merge มาตรฐานของทุก PR หายไป"),
        ({"delete_branch_on_merge": False}, "branch ที่ merge แล้วจะกองค้างอีกครั้ง"),
        ({"allow_merge_commit": True}, "ประวัติแตกสายได้ ทั้งที่ประกาศว่าเส้นเดียว"),
        ({"allow_rebase_merge": False}, "ทางเดียวที่ ADR 0053 รับ ถูกปิด"),
        ({"allow_squash_merge": True}, "ปุ่มที่ CONTRIBUTING ข้อ 7 ห้ามไว้ กลับมาให้กดได้"),
        ({"sha_pinning_required": False}, "แพลตฟอร์มเลิกบังคับสิ่งที่เทสต์เราบังคับอยู่"),
        (
            {"default_workflow_permissions": "write"},
            "GITHUB_TOKEN ของทุก job เริ่มด้วยสิทธิ์เขียน — ชั้นที่รองรับตอนมีใครลืมประกาศหายไป",
        ),
        (
            {"can_approve_pull_request_reviews": True},
            "workflow อนุมัติ PR แทนคนได้ — ทางเข้า main ที่ไม่มีคนดู",
        ),
        ({"required_checks": ["lint"]}, "job ที่รันบน PR หลุดจากรายการบังคับ"),
        ({"required_checks": ["lint", "test", "ผี"]}, "บังคับ check ที่ไม่มีใครสร้างได้"),
    ],
)
def test_posture_catches_every_way_the_platform_can_drift(change, why):
    """ทุกทางที่ท่าทีจะเลื่อนต้องแดง — ไม่ใช่แค่กรณีที่นึกถึงตอนเขียน"""
    assert _audit({**HEALTHY, **change}), why


def test_the_two_check_readers_are_not_swapped():
    """ "ชื่อที่ขึ้นบน PR" กับ "ทุกชื่อที่ repo ผลิตได้" ตอบคนละคำถาม

    สลับกันเมื่อไหร่ ด่านจะเรียกร้องให้บังคับ job ที่ไม่เคยรันบน PR — ซึ่งทำให้
    PR รอ check ที่ไม่มีวันมา · ทั้งสองตัวอ่านจาก workflow จริงของ repo นี้
    จึงพิสูจน์รอยต่อได้โดยไม่ต้องปลอมอะไร
    """
    workflows = gha.all_workflows(audit_posture.WORKFLOWS)
    on_pr = audit_posture.pull_request_checks(workflows)
    everything = audit_posture.all_checks(workflows)

    assert on_pr < everything, "สองตัวนี้ตอบเหมือนกัน = ตัวใดตัวหนึ่งถูกสลับ"
    assert "scorecard" in everything - on_pr, "job ที่รันตามรอบต้องอยู่ในเซตกว้างเท่านั้น"


def test_only_the_settings_declared_unreadable_become_notes():
    """อ่านได้แล้วหาย = แพลตฟอร์มหรือ token เปลี่ยน — ห้ามกลืนเป็นเรื่องปกติ

    ถ้าทุกฟิลด์ถูกส่งเข้าไปเป็น "อ่านไม่ได้" ได้หมด คำตอบที่สามจะกลืนคำตอบที่หนึ่ง
    แล้วธงที่ถูกปิดจริงจะกลายเป็นหมายเหตุที่ไม่มีใครทำอะไรต่อ
    """
    readable = [name for name, s in audit_posture.DECLARED_SETTINGS.items() if s.readable]
    assert readable, "ไม่มีธงที่อ่านได้เลย — เทสต์นี้กัดอะไรไม่ได้"

    notes = audit_posture.unreadable({**HEALTHY, readable[0]: None})

    assert all(readable[0] not in note for note in notes), (
        f"{readable[0]} อ่านได้ตามที่ประกาศ แต่ถูกรายงานเป็นหมายเหตุ"
    )


def test_the_audit_reads_this_repository_s_own_workflows(tmp_path, monkeypatch, capsys):
    """รอยต่อของ `main()` — ไม่อ่าน workflow เลย แปลว่า required check ทุกตัวกลายเป็นผี

    และ "ผี" คืออาการที่ไม่มีอะไรแดง PR แค่ไม่ merge — ด่านที่รายงานอาการนั้น
    ผิด ๆ จะพาคนไปถอด required check ที่ถูกต้องออก
    """
    real = sorted(audit_posture.pull_request_checks(gha.all_workflows(audit_posture.WORKFLOWS)))
    state = tmp_path / "state.json"
    state.write_text(
        json.dumps({"required_checks": real, "alerts": [], "description": ""}), encoding="utf-8"
    )
    monkeypatch.setattr(audit_posture, "best_practices", dict)

    audit_posture.main(["--input", str(state)])

    assert "ไม่มี job ไหนสร้างได้" not in capsys.readouterr().err, (
        "check ที่มี job สร้างได้จริง ถูกรายงานว่าเป็นผี — แปลว่าตัวอ่าน workflow ไม่ได้อ่านอะไร"
    )

    # **ทิศตรงข้ามในเทสต์เดียวกัน** — ข้อความที่หายไปพิสูจน์ได้สองอย่าง: ตัวอ่าน
    # ทำงาน หรือไม่มีใครเรียกตัวตัดสินเลย · ต้องแยกสองอย่างนี้ออกจากกัน
    state.write_text(
        json.dumps({"required_checks": [*real, "ผี"], "alerts": [], "description": ""}),
        encoding="utf-8",
    )
    audit_posture.main(["--input", str(state)])

    assert "ไม่มี job ไหนสร้างได้" in capsys.readouterr().err, (
        "บังคับ check ที่ไม่มีอยู่แล้วเงียบ — ตัวตัดสินสามทิศไม่ได้ถูกเรียกจาก main"
    )


def test_posture_tells_off_apart_from_invisible(capsys):
    """**ปิดอยู่** กับ **มองไม่เห็น** ต่างกันคนละขั้ว — รายงานผิดฝั่งคือการโกหก

    `allow_auto_merge` ถูกคืนมาเฉพาะกับ token ที่มี `contents:write` (เอกสารของ
    GitHub ระบุไว้ตรง ๆ) · `POSTURE_TOKEN` เป็น token อ่านอย่างเดียวโดยตั้งใจ
    ฟิลด์นี้จึงมาเป็น `None` ไม่ใช่ `False` — ฉบับแรกอ่านว่า "ไม่เป็น True แปลว่า
    ปิด" แล้วรายงานว่า auto-merge ปิดอยู่ ทั้งที่มันเปิดและ**ใช้งานอยู่ทุก PR**
    (run 32108560896 · การรันจริงครั้งแรกของด่านนี้)
    """
    invisible = {**HEALTHY, "allow_auto_merge": None}

    assert audit_posture.compare(invisible, 2, None) == [], "ฟิลด์ที่ token อ่านไม่ได้ ต้องไม่ถูกนับเป็นท่าทีที่ผิด"
    assert audit_posture.unreadable(invisible), "แต่ต้องรายงานว่ามองไม่เห็น ไม่ใช่เงียบ"
    assert audit_posture.unreadable(HEALTHY) == [], "อ่านได้แล้วต้องไม่มีหมายเหตุค้าง"


def test_posture_catches_a_document_that_advertises_the_wrong_count():
    """เลข "required NN จาก MM" ในเอกสารต้องตรงกับของจริง ไม่ใช่กับตอนที่เขียน"""
    assert audit_posture.compare(HEALTHY, 2, (26, 29))


def test_posture_lets_the_declared_exemptions_through():
    """job ที่ไม่รันบน PR ต้องไม่ถูกนับว่าหลุด — แต่ต้องประกาศพร้อมเหตุผลที่เดียว"""
    assert "release-sign" in audit_posture.EXEMPT
    produced = ON_PR | set(audit_posture.EXEMPT)

    assert audit_posture.check_problems(HEALTHY, ON_PR, produced) == []


def test_posture_refuses_to_pass_when_it_cannot_read(monkeypatch, capsys):
    """อ่านไม่ได้ = แดง (คืน 2) ไม่ใช่ผ่าน — 403 กับ 5xx ห้ามกลายเป็นการข้าม"""

    def blocked() -> dict:
        raise PermissionError("HTTP 403")

    monkeypatch.setattr(audit_posture, "fetch", blocked)

    assert audit_posture.main([]) == 2
    assert "ห้ามแปลงกรณีนี้เป็นการข้ามเงียบ ๆ" in capsys.readouterr().err


def test_the_census_names_the_jobs_that_never_went_red():
    """ครึ่งแรกของคำถาม "ด่านนี้ยังคุ้มไหม" — job ที่ไม่โผล่ในสถิติเลยต้องถูกเรียกชื่อ

    ADR 0062: ด่าน real-service ที่ไม่เคยแดงจะถูกตัดสินด้วยข้อมูลสองชั้น (ไม่แดง
    + โค้ดที่มันคุ้มไม่ถูกแตะ) ไม่ใช่ด้วยความรู้สึกว่ามันแพง
    """
    summary = rerun_census.census([HIDDEN_RUN, VISIBLE_RUN])
    defined = {"dast", "test", "vault", "sso"}

    assert rerun_census.jobs_never_red(summary, defined) == ["sso", "vault"]


def test_the_census_counts_a_rerun_job_as_having_gone_red():
    """job ที่แดงแล้วถูก rerun **ไม่ใช่** job ที่ไม่เคยแดง — กับดักที่ D1 เพิ่งปิด"""
    summary = rerun_census.census([HIDDEN_RUN])

    assert rerun_census.jobs_never_red(summary, {"dast", "vault"}) == ["vault"]


# ------------------------------------------ alert บนหน้า Security (audit r10 · ข้อ 3)
#
# คำตัดสินอยู่ในเรโปครบแล้ว (pins/accepted-advisories.txt ฯลฯ) แต่พื้นผิวที่คนนอก
# อ่านก่อนเพื่อนคือหน้า Security ซึ่งค้างว่า "high · เปิดอยู่" 4 ใบนาน 5.6 วัน
# โดยไม่มีรอบทบทวนไหนครอบ — แถวที่มีอยู่ครอบเฉพาะใบที่ถูก dismiss ไปแล้ว

ACCEPTED = {"Scorecard/VulnerabilitiesID": "ตัวบังคับจริงคือ job security"}


def _alert(rule, state="open", comment="", tool="Scorecard", number=1):
    return {
        "number": number,
        "state": state,
        "tool": {"name": tool},
        "rule": {"id": rule},
        "dismissed_comment": comment,
    }


def test_alerts_pass_when_every_one_of_them_has_been_decided():
    """ทิศ "ผ่านเมื่อควรผ่าน" — ลงทะเบียนไว้ หรือ dismiss พร้อมเหตุผล ถือว่าตัดสินแล้วทั้งคู่"""
    alerts = [
        _alert("VulnerabilitiesID"),
        _alert("py/x", state="dismissed", comment="เป็น false positive เพราะ …", tool="CodeQL"),
        _alert("py/y", state="fixed", tool="CodeQL"),
    ]

    assert audit_posture.alert_problems(alerts, ACCEPTED) == []


@pytest.mark.parametrize(
    ("alerts", "accepted", "why"),
    [
        ([_alert("NewRuleID")], ACCEPTED, "ของใหม่ที่ยังไม่มีใครตัดสิน ต้องแดง"),
        (
            [_alert("NewRuleID", state="dismissed")],
            ACCEPTED,
            "dismiss เงียบ ๆ โดยไม่เขียนเหตุผล = ปิดเสียงที่ไม่มีใครทวนได้",
        ),
        (
            [_alert("VulnerabilitiesID")],
            {**ACCEPTED, "Scorecard/GhostID": "ยกเว้นไว้นานแล้ว"},
            "บรรทัดที่ไม่ตรงกับ alert ไหนแล้ว ต้องถูกบังคับให้ถอด (ทิศที่เงียบเสมอ)",
        ),
        (
            [_alert("VulnerabilitiesID", state="fixed")],
            ACCEPTED,
            "alert ที่ถูกแก้ไปแล้ว ต้องไม่ค้ำบรรทัดในทะเบียนไว้ต่อ",
        ),
        (None, ACCEPTED, "อ่านไม่ได้ = แดง ไม่ใช่ข้าม (ADR 0061 ข้อ 3)"),
    ],
)
def test_alerts_catch_every_way_a_signal_goes_unowned(alerts, accepted, why):
    """ทุกทางที่ alert จะกลายเป็นของไม่มีเจ้าของต้องแดง"""
    assert audit_posture.alert_problems(alerts, accepted), why


def test_the_alert_register_on_disk_is_readable_and_reasoned():
    """ทะเบียนจริงต้องย่อยได้ด้วยตัวมันเอง — ไม่ใช่แค่ fixture ในเทสต์ที่ย่อยได้"""
    accepted = audit_posture.accepted_alerts()

    assert accepted, "อ่าน .github/accepted-code-scanning-alerts.txt ไม่ได้เลย"
    assert all(why for why in accepted.values()), "มีบรรทัดที่ไม่มีเหตุผลกำกับ"


# ------------------------------- check ที่ไม่ถูกบังคับ ต้องถูกประกาศ (ADR 0066 · audit r10)
#
# ทะเบียน `EXEMPT` มีมาตั้งแต่ ADR 0061 แต่ถูกใช้กรองเซต "job ที่รันบน PR แต่ไม่ถูก
# บังคับ" — ซึ่งสมาชิกของมันไม่มีทางอยู่ในเซตนั้นตั้งแต่ต้น · วัดจริงตอน audit รอบ 10:
# 2 รายการ 0 ครั้งที่ถูกปรึกษา · ทิศนี้ทำให้มันถูกอ่านทุกครั้งที่ตัวตรวจรัน


def test_unrequired_checks_pass_when_every_one_of_them_is_declared():
    """ทิศ "ผ่านเมื่อควรผ่าน" — ของที่ประกาศไว้แล้วต้องไม่มีเสียงบ่น"""
    produced = {"lint", "test"} | set(audit_posture.EXEMPT)
    state = {"required_checks": ["lint", "test"]}

    assert audit_posture.check_problems(state, {"lint", "test"}, produced) == []


def test_an_undeclared_unrequired_check_is_red():
    """job ใหม่ที่ไม่ถูกบังคับและไม่มีใครประกาศ = ด่านที่ล้มเงียบได้ทั้งวัน"""
    produced = {"lint", "test", "job-ใหม่"} | set(audit_posture.EXEMPT)
    state = {"required_checks": ["lint", "test"]}

    problems = audit_posture.check_problems(state, {"lint", "test"}, produced)

    assert problems, "job ใหม่ที่ไม่มีใครประกาศต้องถูกจับ"
    assert "job-ใหม่" in problems[0], "ข้อความต้องบอกว่าตัวไหน ไม่ใช่แค่ว่ามีปัญหา"


def test_a_declared_exemption_that_names_nothing_is_red():
    """ทิศที่เงียบเสมอ — ยกเว้น job ที่ถูกลบไปแล้ว ไม่มีอะไรฟ้องถ้าไม่ตรวจทิศนี้"""
    assert audit_posture.check_problems({"required_checks": ["lint"]}, {"lint"}, {"lint"}), (
        "EXEMPT ทั้งชุดไม่ตรงกับ job ไหนเลย แต่ตัวตรวจเงียบ"
    )


def test_matrix_checks_are_matched_by_their_job_name():
    """`dialect (mysql-8)` ต้องนับเป็น job `dialect` ไม่ใช่ชื่อแปลกที่ไม่มีในทะเบียน"""
    produced = {"dialect (mysql-8)", "dialect (mariadb-11)"} | set(audit_posture.EXEMPT)
    state = {"required_checks": ["dialect (mysql-8)"]}

    assert audit_posture.check_problems(state, produced, produced), (
        "แถว matrix ที่หลุดจากรายการบังคับต้องถูกจับ"
    )


NOW = "2026-08-18T09:00:00+00:00"


# ------------------------- `within_days` ทำได้จริงไหม (ADR 0066 → วัดได้ในรอบ 11)
#
# รอบ 10 ให้ทุก gate ที่บล็อกไม่ได้ประกาศว่า "ใครเห็นภายในกี่วัน" แต่สิ่งเดียวที่
# ตรวจมันคือ *รูปแบบ* · ตัวนี้วัดขอบบนของเวลาที่ใช้รับรู้+แก้ จากความยาวของช่วง
# ที่ workflow อยู่ในสถานะแดงบน main — ไม่ใช่ MTTA แท้ ๆ และต้องเรียกให้ถูก


def _run(path, stamp, conclusion, name="ชื่ออะไรก็ได้"):
    return {"path": path, "created_at": stamp, "conclusion": conclusion, "name": name}


WATCHED = ".github/workflows/scorecard.yml"


# ------------------------------- ratchet ต้องไม่ลอยต่ำกว่าของจริง (ADR 0068 · audit r12)
#
# `pyproject.toml` เขียนกำกับทั้งสองที่ว่า "ขยับขึ้นได้อย่างเดียว" — ทิศถูก แต่ไม่มี
# อะไรทำให้ขยับ · หกวันหลังตั้งเลข coverage จริงไต่ไป 97.11% ขณะที่พื้นยังเป็น 96


def test_a_floor_that_sits_just_below_reality_is_quiet():
    """ทิศ "ผ่านเมื่อควรผ่าน" — ห่างไม่เกินระยะที่ประกาศ ต้องไม่มีเสียงบ่น"""
    assert check_ratchets.problems({"coverage": 97.0}, {"coverage": 97.11}) == []


def test_a_floor_left_behind_by_reality_is_red():
    """ที่ว่าง 1.11 จุด = โค้ดที่มีเทสต์คุมราว 54 บรรทัดหายไปได้เงียบ ๆ"""
    found = check_ratchets.problems({"coverage": 96.0}, {"coverage": 97.11})

    assert found, "พื้นที่ตามของจริงไม่ทันต้องแดง"
    assert "97" in found[0], "ข้อความต้องบอกด้วยว่าควรขยับไปที่เท่าไหร่"


def test_a_floor_above_reality_is_not_this_test_s_problem():
    """พื้นที่สูงกว่าของจริงเป็นเรื่องของด่านหลัก (`fail_under` เอง) ไม่ใช่ของทิศนี้

    แยกกันเพราะสองทิศนี้ล้มด้วยเหตุผลคนละอย่าง และข้อความที่บอกว่าต้องทำอะไรต่อ
    ก็คนละอย่าง — รวมกันเมื่อไหร่ คนอ่านจะได้คำแนะนำที่ผิดครึ่งหนึ่งของเวลา
    """
    assert check_ratchets.problems({"coverage": 99.0}, {"coverage": 97.11}) == []


def test_every_declared_floor_is_read_from_the_file_not_a_comment():
    """อ่านพื้นจาก `pyproject.toml` จริง — คอมเมนต์ที่เขียนกำกับคือสิ่งที่รอบนี้กำลังตรวจ"""
    floors = check_ratchets.declared()

    assert set(floors) == {
        "coverage",
        "interrogate",
        "mypy_strict_modules",
        "enforced_prohibitions",
        "scripts_coverage",
        *check_ratchets.REMOVAL_GUARDS,
        *check_ratchets.CEILINGS,
    }
    assert all(value > 0 for value in floors.values())


# ------------------------- ratchet ที่ไม่ใช่ตัวเลขของเครื่องมือ (audit r14 · ข้อ 3)
#
# ตัวตรวจรุ่นแรกอ่านเฉพาะพื้นที่เป็นตัวเลขใน config ของเครื่องมือ — strict list
# ของ mypy ซึ่งบอกว่า "ขยาย ห้ามหด" มาตั้งแต่ Phase 2 จึงรอดมาทั้งใบ โดยที่เป้า
# ที่เขียนกำกับไว้ ("ทั้งแอปภายใน Phase 2") หมดอายุไปสิบหกเฟส


def test_the_strict_list_is_counted_from_the_files_that_exist():
    """นับจากไฟล์จริงเทียบ pattern ไม่ใช่นับจำนวนบรรทัดในลิสต์

    `app.services.*` บรรทัดเดียวครอบหลายโมดูล — การนับบรรทัดจะบอกว่า 12
    ทั้งที่ของจริงคือ 34 แล้วพื้นจะกลายเป็นตัวเลขที่ไม่ได้วัดอะไรเลย
    """
    modules = [
        path
        for path in (check_ratchets.APP).rglob("*.py")
        if "enhancements" not in path.parts and "__pycache__" not in path.parts
    ]
    counted = check_ratchets.strict_modules()

    assert counted > 12, "นับได้เท่าจำนวนบรรทัดในลิสต์ = นับผิดตัว (`app.services.*` ครอบหลายโมดูล)"
    assert counted < len(modules), "นับได้เท่าจำนวนโมดูลทั้งหมด = pattern ไม่ได้ถูกใช้กรองเลย"


def test_the_enhancements_of_a_plugin_stay_outside_the_count(tmp_path):
    """`exclude` ของ mypy ตัดชั้นนี้ทิ้งอยู่แล้ว — ตัวนับต้องตัดตาม

    **วันนี้การถอดชั้นนี้ออกยังไม่เปลี่ยนตัวเลข** เพราะ pattern ใน strict list
    ตอนนี้เป็น `app.plugins` เฉย ๆ ซึ่งกวาดไม่ถึง · เทสต์ที่วัดจากของจริงจึงเขียว
    ไม่ว่าค่าคงที่จะเป็นอะไร — พิสูจน์ที่ต้นไม้สังเคราะห์แทน โดยใช้ **ค่าคงที่ตัวจริง
    ของ repo นี้** เพื่อให้การพิมพ์ผิดหรือการถอด `enhancements` ออกแดงทันที

    ที่ต้องกันไว้คือวันที่มีคนเปลี่ยนเป็น `app.plugins.*`: พื้นจะเริ่มขยับตาม
    **การวางไดเรกทอรี** แทนความเข้มของ type check — วางส่วนเสริมเพิ่มหนึ่งตัวแล้ว
    ratchet แดง โดยไม่มีใครแตะโค้ดที่ถูกตรวจสักบรรทัด
    """
    assert list(check_ratchets.APP.rglob("enhancements")), (
        "ไม่มีชั้นส่วนเสริมบนดิสก์แล้ว — ถ้าถอดทิ้งจริง ค่าคงที่นี้ต้องถูกถอดตาม"
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.mypy]\n[[tool.mypy.overrides]]\nmodule = ["app.*"]\ndisallow_untyped_defs = true\n',
        encoding="utf-8",
    )
    for name in ("app/tz.py", "app/plugins/auth/totp/enhancements/qr/provide.py"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    counted = check_ratchets.measure.strict_modules(
        tmp_path,
        tmp_path / "pyproject.toml",
        tmp_path / "app",
        skip_parts=check_ratchets.STRICT_SKIP_PARTS,
    )

    assert counted == 1, "ตัวนับเห็นส่วนเสริมด้วย — พื้นจะขยับตามการวางไดเรกทอรี ไม่ใช่ตามความเข้ม"


def test_a_strict_list_that_shrank_is_red():
    """ทิศที่ไม่มีเครื่องมือตัวไหนบังคับให้ — ถอดโมดูลออกจากลิสต์ต้องแดง"""
    found = check_ratchets.problems({"mypy_strict_modules": 34.0}, {"mypy_strict_modules": 33.0})

    assert found, "strict list ที่หดลงต้องแดง — ไม่งั้นคำว่า 'ห้ามหด' เป็นแค่คอมเมนต์"
    assert "ถอย" in found[0]


def test_a_strict_list_that_grew_without_moving_the_floor_is_red():
    """ระยะของตัวที่นับเป็นจำนวนคือ 0 — เพิ่มโมดูลแล้วต้องขยับพื้นใน PR เดียวกัน"""
    found = check_ratchets.problems({"mypy_strict_modules": 34.0}, {"mypy_strict_modules": 35.0})

    assert found, "ลิสต์โตขึ้นแล้วพื้นไม่ตาม = ที่ว่างที่จะถูกใช้คืนเงียบ ๆ"
    assert "35" in found[0]


def test_the_enforcement_code_carries_its_own_floor():
    """โค้ดที่บังคับกฎ ต้องอยู่ใต้เกณฑ์เดียวกับโค้ดที่มันคุ้ม (audit r17 · ข้อ 1)

    `[tool.coverage.run] source` ครอบแค่ `app/` มาตลอด — `scripts/` ซึ่งเป็นที่อยู่
    ของตัวบังคับ 83 จาก 105 gate จึงเป็นโค้ดชุดเดียวที่ไม่มีเกณฑ์ของตัวเอง
    """
    floors = check_ratchets.declared()

    assert floors["scripts_coverage"] > 0, "พื้นของ scripts/ ต้องมีค่าจริง"
    shrank = check_ratchets.problems({"scripts_coverage": 43.0}, {"scripts_coverage": 41.0})
    assert shrank, "coverage ของตัวบังคับที่ตกต่ำกว่าพื้นต้องแดง"


def test_a_missing_scripts_measurement_is_loud(monkeypatch, tmp_path):
    """ไม่มีไฟล์ผลวัด = ขั้นตอนก่อนหน้าไม่ได้รัน — ต้องดังกว่าการเงียบแล้วผ่าน"""
    monkeypatch.setattr(check_ratchets, "SCRIPTS_COVERAGE", tmp_path / "ไม่มีอยู่.json")

    with pytest.raises(RuntimeError, match="ยังไม่ได้รัน"):
        check_ratchets.scripts_coverage()


def test_the_register_of_enforced_prohibitions_only_grows():
    """ถอดด่านของข้อห้ามออก = ถอยกลับไปเป็น "กฎที่มีแต่ประโยค" (audit r15 · ข้อ 4)

    audit รอบ 14 ปิดไป 8 จาก 19 · รอบ 15 ปิดเพิ่ม 3 · **แต่ไม่มีอะไรทำให้กอง
    ที่เหลือหดลงเอง** และไม่มีอะไรกันการถอยกลับ — ADR 0068 เรียกสภาพนี้ว่า
    เพดานที่ไม่มีตัวทวง
    """
    shrank = check_ratchets.problems(
        {"enforced_prohibitions": 11.0}, {"enforced_prohibitions": 10.0}
    )
    assert shrank, "ทะเบียนที่หดลงต้องแดง"
    assert "ถอย" in shrank[0]

    grew = check_ratchets.problems({"enforced_prohibitions": 11.0}, {"enforced_prohibitions": 12.0})
    assert grew, "เพิ่มด่านแล้วไม่ขยับพื้น = ที่ว่างที่จะถูกใช้คืนเงียบ ๆ"


def test_the_prohibition_count_is_read_from_the_register_not_a_number_in_a_doc():
    """นับจากทะเบียนจริงใน `tests/test_declared_prohibitions.py` ไม่ใช่จากเอกสาร

    **เทียบกับทะเบียนตัวจริงที่ import เข้ามา ไม่ใช่กับขอบล่างหลวม ๆ** — เกณฑ์
    แบบ `>= 8` เขียวเท่ากันหมดไม่ว่าตัวอ่านจะคืน 14 หรือคืนค่าคงที่ 99 (ลองแล้ว:
    เปลี่ยนตัวอ่านเป็น `return 99` ชุดเทสต์ยังเขียวทั้งชุด)

    ตัวอ่านจริง**ไม่ import** ไฟล์นั้น (มันถูกเรียกจาก job ที่ไม่มี pytest) ส่วน
    ที่นี่ import ได้ — สองทางที่ไปถึงตัวเลขเดียวกันคือสิ่งที่ทำให้เทสต์นี้พิสูจน์อะไรได้
    """
    from tests.test_declared_prohibitions import RULES

    assert check_ratchets.enforced_prohibitions() == len(RULES)
    assert len(RULES) >= 8, "ทะเบียนหดต่ำกว่าที่ audit รอบ 14–15 ปิดไว้"


# ------------------------ การถอดต้องเป็นคำตัดสิน (ADR 0069 · audit r16 · ข้อ 1–2)
#
# รอบ 16 วัดด้วยการลบของจริง 11 ครั้ง: ทะเบียนที่ถูกตรวจกับ *ความจริง* ลบไม่ได้เงียบ
# ส่วนทะเบียนที่ถูกตรวจกับ *กระดาษอีกใบ* ลบได้เงียบสนิท เพราะการลบทั้งสองข้าง
# พร้อมกันยังนับว่า "ตรงกัน" · ที่วัดได้: ถอด gate ทิ้งแล้ว CI เขียวครบถ้าเก็บกวาด
# 6 ที่ · 37 แถวในสามทะเบียนกระดาษลบทิ้งได้โดยไม่มีอะไรฟ้อง


@pytest.mark.parametrize("name", check_ratchets.REMOVAL_GUARDS)
def test_something_removed_is_red(name):
    """ทิศที่รอบ 16 เปิด — ของหายไปแล้วต้องมีคนรู้"""
    found = check_ratchets.problems({name: 10.0}, {name: 9.0})

    assert found, f"{name}: ของถูกถอดออกแล้วต้องแดง"
    assert "ถูกถอดออกไป" in found[0], "ข้อความต้องบอกว่านี่คือการถอด ไม่ใช่การถอยของเกณฑ์"
    assert "removals" in found[0], "ต้องบอกด้วยว่าถ้าตั้งใจถอดจริง ต้องไปแก้ที่ไหน"


@pytest.mark.parametrize("name", check_ratchets.REMOVAL_GUARDS)
def test_growing_freely_is_not_a_problem(name):
    """**ต่างจาก ratchet ตรงนี้**: การเพิ่มถูกเฝ้าด้วยด่านอื่นครบแล้ว

    ถ้าที่นี่บังคับให้ขยับเลขตอนเพิ่มด้วย ทุก PR ที่เพิ่ม gate จะต้องแก้ไฟล์เพิ่ม
    อีกหนึ่งที่โดยไม่ได้อะไรกลับมา — และต้นทุนแบบนั้นคือสิ่งที่ทำให้คนเลิกอ่านด่าน
    """
    assert check_ratchets.problems({name: 10.0}, {name: 25.0}) == []


def test_the_counts_are_read_from_the_source_files_not_from_a_summary():
    """นับจากไฟล์ต้นทางจริง — และ**ใช้ตัวอ่านตัวเดียวกับที่มีอยู่แล้ว**

    ตัวนับที่เขียนใหม่ที่นี่เคยได้ 24 ขณะที่ตัวอ่านจริงของ `whats_pending` ได้ 23
    ในวันเดียวกัน — parser ตัวที่สองคือที่ที่ drift เกิดขึ้นเสมอ (ADR 0039)
    """
    counts = check_ratchets.removal_counts()

    assert set(counts) == set(check_ratchets.REMOVAL_GUARDS)
    assert counts["gates_total"] > 100, "นับ gate จาก gates.yaml ไม่ได้แล้ว"
    assert counts["cadence_rows"] == len(whats_pending.cadence_rows())
    assert counts["deferred_rows"] == len(whats_pending.deferred())
    assert counts["risk_rows"] >= 5


def test_a_coverage_floor_above_reality_is_still_not_this_test_s_problem():
    """ทิศลงของ coverage เป็นของ `fail_under` — ที่นี่ต้องไม่พูดซ้ำ

    ถ้าที่นี่พูดด้วย คนอ่านจะได้ข้อความสองอันที่บอกให้ทำคนละอย่างกับปัญหาเดียว
    """
    assert check_ratchets.problems({"coverage": 99.0}, {"coverage": 97.11}) == []


# ------------------- รายงานต้องไม่ขัดกับตัวเอง (audit r13 · ข้อ 1)
#
# `dialects` ประกาศ `name: dialect (${{ matrix.db.name }})` — API จึงคืนชื่อ
# `dialect (mysql-8)` ส่วนฝั่ง "ไม่เคยแดง" อ่านไอดีจากไฟล์ workflow (`dialects`)
# ผลคือรายงานฉบับเดียวบอกว่ามันล้ม 10 ครั้ง แล้วบอกว่ามันไม่เคยแดง


MATRIX_FAILURE = {
    "id": 11,
    "attempt": 1,
    "failures": [{"attempt": 1, "job": "dialect (mysql-8)", "step": "pytest", "message": "boom"}],
}


def test_a_check_name_is_resolved_back_to_its_job_id():
    """ชื่อที่ API คืนมา ต้องถูกแปลงกลับเป็นไอดีก่อนนับ"""
    summary = rerun_census.census([MATRIX_FAILURE], {"dialect": "dialects"})

    assert "dialects" in summary["jobs"], "ชื่อ check ไม่ได้ถูกแปลงกลับเป็นไอดี job"
    assert "dialect" not in summary["jobs"]


def test_the_two_halves_of_the_report_cannot_contradict_each_other():
    """job ที่นับความล้มเหลวไว้ ต้องไม่โผล่ในรายการ "ไม่เคยแดง" ของรายงานเดียวกัน"""
    summary = rerun_census.census([MATRIX_FAILURE], {"dialect": "dialects"})
    never = rerun_census.jobs_never_red(summary, {"dialects", "lint"})

    assert "dialects" not in never, "รายงานขัดกับตัวเอง"
    assert never == ["lint"]


def test_without_the_map_the_old_bug_is_visible():
    """ทิศที่พิสูจน์ว่าแม็ปคือสิ่งที่แก้ — ไม่ส่งแม็ปแล้วบั๊กเดิมกลับมาทันที"""
    summary = rerun_census.census([MATRIX_FAILURE])

    assert rerun_census.jobs_never_red(summary, {"dialects"}) == ["dialects"], (
        "ถ้าไม่มีแม็ป job ที่ล้มจริงจะยังถูกรายงานว่าไม่เคยแดง"
    )


def test_a_name_that_cannot_be_resolved_is_reported_loudly():
    """ชื่อที่แปลงกลับไม่ได้ = ชื่อที่จะตกไปฝั่ง "ไม่เคยแดง" เงียบ ๆ"""
    summary = rerun_census.census(
        [
            {
                "id": 12,
                "attempt": 1,
                "failures": [{"attempt": 1, "job": "job-ที่ไม่รู้จัก", "step": "s", "message": "m"}],
            }
        ]
    )

    assert rerun_census.unresolved_labels(summary, {"lint"}) == ["job-ที่ไม่รู้จัก"]


def test_a_workflow_that_never_started_is_not_counted_as_a_strange_name():
    """run ที่ไม่ได้ start ถูกตั้งชื่อด้วย path โดยตั้งใจ — ไม่ใช่ชื่อที่แปลงพลาด"""
    summary = rerun_census.census(
        [
            {
                "id": 13,
                "attempt": 1,
                "failures": [
                    {
                        "attempt": 1,
                        "job": ".github/workflows/scorecard.yml — ไม่ได้ start",
                        "step": "",
                        "message": "workflow file issue",
                    }
                ],
            }
        ]
    )

    assert rerun_census.unresolved_labels(summary, {"lint"}) == []


def test_the_identity_map_reads_the_real_workflows():
    """แม็ปต้องอ่านจากไฟล์จริง — matrix ที่เปลี่ยนชื่อ `name:` ต้องยังตามได้"""
    ids, by_name, by_path = rerun_census.job_identity()

    assert "dialects" in ids
    assert by_name.get("dialect") == "dialects", "job ที่ตั้ง name: ต่างจากไอดี ต้องถูกแม็ป"
    assert "posture" in by_path[".github/workflows/scorecard.yml"]


# --------------------- หน้าเดียวที่ตอบว่า "อะไรค้าง" (audit r13 · ข้อ 4)
#
# ตัวนี้เป็น *ของอ่าน* ไม่ใช่ด่าน — มันไม่เก็บสถานะของตัวเองเลย · เทสต์จึงพิสูจน์
# สองอย่าง: มันอ่านแหล่งจริงได้ และมันไม่ทำให้กองดูใหญ่หรือเล็กกว่าความจริง

TODAY = __import__("datetime").date(2026, 8, 19)
CADENCE_ROWS = [
    ("ทบทวนอะไรสักอย่าง", "3 เดือน", "2026-08-01"),
    ("ทบทวนอีกอย่าง", "6 เดือน", "2027-02-18"),
    ("pentest ด้วยมือ", "ทุก major release", "เมื่อมีผู้ใช้ภายนอกจริง"),
]


def test_an_overdue_row_says_so():
    """แถวที่เลยกำหนดต้องอ่านออกทันที ไม่ใช่ต้องคำนวณเอง"""
    soon = whats_pending.due_soon(CADENCE_ROWS, TODAY, within=7)

    assert len(soon) == 1
    assert "เลยกำหนดแล้ว" in soon[0]


def test_rows_far_in_the_future_are_left_out_until_asked_for():
    """หน้าที่แสดงทุกแถวเสมอ คือหน้าที่ไม่มีใครอ่านจนจบ"""
    assert whats_pending.due_soon(CADENCE_ROWS, TODAY, within=7) != whats_pending.due_soon(
        CADENCE_ROWS, TODAY, within=400
    )


def test_conditional_rows_are_counted_separately():
    """แถวที่รอเงื่อนไขไม่มีวันครบกำหนดเอง — ปนกับแถวที่มีวันที่แล้วจะหายไปในกอง"""
    waiting = whats_pending.conditional_rows(CADENCE_ROWS)

    assert len(waiting) == 1
    assert "pentest" in waiting[0]


def test_closed_items_do_not_inflate_the_pile():
    """ข้อที่ขีดฆ่าแล้วใน CLAUDE.md คือของที่ปิดแล้ว ไม่ใช่ของค้าง"""
    pending = whats_pending.undone()

    assert pending, "อ่านรายการ 'ยังไม่ได้ทำ' จาก CLAUDE.md ไม่ได้เลย"
    assert not any(item.startswith("~~") for item in pending)


def test_the_reader_stops_at_the_next_heading(tmp_path, monkeypatch):
    """ตัวอ่านต้องมีขอบเขตของตัวเอง — audit รอบ 14 ข้อ 4

    รุ่นแรกอ่านยาวจนจบไฟล์ · ตัวเลขที่ได้ถูกโดยบังเอิญ เพราะหัวข้อถัด ๆ ไปไม่มี
    bullet ระดับบนสุด — **ตัวอ่านที่อ่านเลยหัวข้อของตัวเอง ห่างจากการรายงานผิด
    อยู่หัวข้อเดียว** และมันจะผิดในวันที่ไม่มีใครกำลังดูมันอยู่
    """
    fake = tmp_path / "CLAUDE.md"
    fake.write_text(
        "## ยังไม่ได้ทำ\n"
        "- ของที่ค้างจริง\n"
        "\n### ไม่ได้ค้าง — ตัดสินแล้วว่าไม่ทำ\n"
        "- ของที่ตัดสินแล้วว่าไม่ทำ\n"
        "\n## หัวข้ออื่นของไฟล์\n"
        "- bullet ของหัวข้ออื่นที่ไม่เกี่ยวอะไรเลย\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(whats_pending, "INSTRUCTIONS", fake)

    pending = whats_pending.undone()

    assert pending == ["ของที่ค้างจริง"], f"อ่านเลยขอบเขตของตัวเอง: {pending}"


def test_decided_and_finished_items_are_not_counted_as_pending():
    """ของที่ปิดแล้วซึ่งนอนอยู่ใต้หัวข้อ "ยังไม่ได้ทำ" ทำให้กองดูใหญ่กว่าความจริง

    วัดจริงตอน audit รอบ 14: 3 จาก 8 ข้อไม่ใช่ของค้าง — `?next=` เป็นคำตัดสิน
    ที่ปิดแล้ว · "ปัจจัยหลักมีสองรูปแบบ" เป็นคำอธิบายของสิ่งที่มีอยู่ · และ
    "OIDC เสร็จแล้วตั้งแต่ P5-13" เป็นของที่ทำเสร็จไปแล้ว
    """
    pending = whats_pending.undone()

    for closed in ("OIDC เสร็จแล้ว", "?next=", "ปัจจัยหลักมีสองรูปแบบ"):
        assert not any(closed in item for item in pending), (
            f"ของที่ปิดแล้วถูกนับเป็นของค้าง: {closed} — ย้ายไปใต้หัวข้อย่อย 'ไม่ได้ค้าง' ของ CLAUDE.md"
        )


def test_the_report_reads_every_source_it_claims_to():
    """รายงานที่หัวข้อครบแต่เนื้อว่าง คือรายงานที่อ่านแหล่งไม่ได้แล้วเงียบ"""
    text = whats_pending.report(TODAY, within=400)

    for heading in ("ตรวจตามรอบที่ถึงคิว", "รอเงื่อนไข", "ตัดสินแล้วว่ายังไม่ทำ", "กองที่ต้องอ่าน"):
        assert heading in text
    assert "(ไม่มี)" not in text.split("## กองที่ต้องอ่าน")[0], "มีหัวข้อที่อ่านแหล่งไม่ได้"
    assert all(value >= 0 for value in whats_pending.counts().values())


# ------------- CVE ของ plugin ต้องถูกตัดสิน (ADR 0025 โน้ต 1 · audit r13 ข้อ 2)
#
# เดิม job นี้เตือนแล้วผ่าน — เวลาที่จะ*รู้*จึงเป็น 90 วัน ขณะที่กรอบแก้ของ critical
# คือ 7 วันนับจากวันที่รู้ · สองนโยบายของเราเองพร้อมกันไม่ได้

REPORT = {"dependencies": [{"name": "cryptography", "vulns": [{"id": "GHSA-aaaa"}]}]}


def test_an_advisory_nobody_decided_is_red():
    """ของใหม่ที่ไม่มีบรรทัดในทะเบียน = ยังไม่มีใครตัดสิน"""
    found = audit_plugin_deps.advisories([REPORT])

    trouble = audit_plugin_deps.problems(found, set())

    assert trouble, "ของใหม่ที่ไม่มีใครตัดสินต้องแดง"
    assert "GHSA-aaaa" in trouble[0]
    assert "DISABLED_PLUGINS" in trouble[0], "ข้อความต้องบอกทางที่เร็วที่สุดด้วย"


def test_an_advisory_that_was_decided_is_quiet():
    """ทิศ "ผ่านเมื่อควรผ่าน" — รับไว้แล้วต้องไม่มีเสียงบ่น"""
    found = audit_plugin_deps.advisories([REPORT])

    assert audit_plugin_deps.problems(found, {"GHSA-aaaa"}) == []


def test_a_register_line_that_no_longer_matches_is_red():
    """ทิศที่เงียบเสมอ — ยกเว้นไว้แล้วของหายไป ต้องบังคับให้ถอดบรรทัด"""
    trouble = audit_plugin_deps.problems({}, {"GHSA-เก่า"})

    assert trouble, "บรรทัดที่ไม่ตรงกับอะไรแล้วต้องแดง"
    assert "ถอดบรรทัดออก" in trouble[0]


def test_the_reader_understands_pip_audit_output():
    """อ่านรูปที่ `pip-audit --format=json` คืนมาจริง ไม่ใช่รูปที่เราคิดเอง

    **ID คือกุญแจของทะเบียน ส่วนคำอธิบายเป็นบรรทัดให้คนอ่าน** — ยืนยัน ID แบบเป๊ะ
    และยืนยันว่าคำอธิบายบอกชื่อ package · รายงานที่ขาดฟิลด์รายละเอียดต้องไม่ทำให้
    ด่านที่จะจับ advisory นั้นล้มไปทั้งใบ (เจอจริงตอนขั้น 4: ตัวอ่านของ vg เข้ม
    กับ `version` จนรายงานที่ไม่มีฟิลด์นั้นทำให้ทั้งตัวตรวจพัง)
    """
    found = audit_plugin_deps.advisories([REPORT, {"dependencies": []}])

    assert set(found) == {"GHSA-aaaa"}
    assert "cryptography" in found["GHSA-aaaa"]


def test_the_register_on_disk_is_readable():
    """ทะเบียนจริงต้องย่อยได้ — ปกติมันควรว่าง เพราะคำตอบที่เร็วที่สุดคือถอด"""
    assert audit_plugin_deps.accepted_advisories() == set()


# ------------- อ่านว่ามีอะไรถูกถอดไปบ้าง (audit r16 · ข้อ 3)
#
# บันทึกมีครบใน git อยู่แล้ว · ที่ไม่มีคือใครสักคนที่อ่านมัน — และปัญหาที่แท้จริง
# คือ **แยกไม่ออกว่าบรรทัดที่หายไปคือ "ถูกถอด" หรือ "ถูกเขียนใหม่"** ต้องเปิดอ่าน
# ทีละ diff ซึ่งไม่มีใครทำ


# **ตรรกะย้ายไป verifiable-gates แล้ว** (ADR 0077 · ขั้น 3d — 8 มิวเทชันแดงที่นั่น
# รวมข้อที่นับการเปลี่ยนชื่อเป็นการถอด) · ที่เหลือให้พิสูจน์ที่นี่คือ **ทะเบียน**:
# แต่ละกองยังชี้ไปยังไฟล์ที่มีอยู่จริง และ regex ของมันยังจับของในไฟล์นั้นได้
# — regex ที่เลิกแมตช์เพราะรูปของไฟล์เปลี่ยน ทำให้สำมะโนรายงาน "ไม่มีอะไรถูกถอด"
# ตลอดไปโดยไม่มีอะไรฟ้อง ซึ่งเป็นคำตอบที่ทุกคนอยากได้พอดี


@pytest.mark.parametrize("name", sorted(removals_census.WATCHED))
def test_every_watched_pile_still_matches_the_file_it_names(name):
    """กองที่ regex เลิกจับของ = กองที่รายงานว่าว่างตลอดกาล"""
    root = pathlib.Path(__file__).resolve().parent.parent
    pile = removals_census.WATCHED[name]

    if pile.is_a_directory:
        here = root / pile.path
        assert here.is_dir(), f"{name}: ชี้ไปไดเรกทอรีที่ไม่มีอยู่ ({pile.path})"
        hits = [path for path in here.rglob("*") if pile.pattern.match(str(path.relative_to(root)))]
    else:
        target = root / pile.path
        assert target.is_file(), f"{name}: ชี้ไปไฟล์ที่ไม่มีอยู่ ({pile.path})"
        hits = [
            line
            for line in target.read_text(encoding="utf-8").splitlines()
            if pile.pattern.match(line)
        ]

    assert hits, f"{name}: regex ไม่จับอะไรใน {pile.path} เลย — สำมะโนจะว่างตลอดกาล"


def test_the_census_reads_the_root_and_the_manifest_it_was_given(tmp_path, monkeypatch):
    """รอยต่อ — `ROOT` กับ `WATCHED` ของที่นี่ต้องเดินไปถึงตัวอ่านจริง

    **ปลอมประวัติเอง ไม่อ่านประวัติจริง** — รุ่นแรกของเทสต์นี้ยืนยันว่า gate ที่ถูก
    ถอดตอนปิดขั้น 6 ต้องโผล่ในสำมะโน ซึ่งเขียวบนเครื่องและ**แดงบน CI** เพราะ
    checkout ของ CI ตื้น ประวัติจึงไปไม่ถึง commit นั้น · เทสต์ที่ผลขึ้นกับสิ่งที่
    เครื่องบังเอิญมี ต้องปลอม input เอง (กติกาใน CLAUDE.md)
    """

    binary = shutil.which("git")
    assert binary, "เทสต์นี้อ่านประวัติจริงจึงต้องมี git"

    def git(*args: str) -> None:
        """คำสั่ง git ของเทสต์นี้ผ่านที่เดียว — ไม่ใช่ห้าบรรทัดที่ปิดกฎเดียวกันห้าครั้ง"""
        subprocess.run(  # noqa: S603 — path จาก shutil.which · argv คงที่ · ปลายทางคือ tmp_path
            [binary, *args], cwd=tmp_path, check=True, timeout=60
        )

    git("init", "-q", "-b", "main")
    git("config", "user.email", "nobody@example.invalid")
    git("config", "user.name", "Nobody")

    rows = "gates:\n  - id: alpha\n  - id: beta\n"
    for body, subject in (
        (rows, "feat: two gates"),
        (rows.replace("  - id: beta\n", ""), "chore: drop beta"),
    ):
        (tmp_path / "gates.yaml").write_text(body, encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", subject)

    monkeypatch.setattr(removals_census, "ROOT", tmp_path)
    found, _edits = removals_census.census("1.year")

    assert set(found) == set(removals_census.WATCHED), "ทุกกองที่ประกาศต้องอยู่ในคำตอบ"
    assert [item for _c, _s, item in found["gate"]] == ["beta"]


def test_the_report_carries_this_project_s_own_closing_note(capsys):
    """หมายเหตุท้ายหน้าเป็นของ repo นี้ — มันบอกว่าต้องไปแก้เลขที่ไหนต่อ"""
    removals_census.main(["--since", "1.year"])

    assert "[tool.todolist.removals]" in capsys.readouterr().out


DIRTY_TITLES = [
    ("แก้บั๊ก", "ไม่มี type นำหน้า"),
    ("feat เพิ่มของ", "ไม่มีเครื่องหมาย :"),
    ("wip: ลองดู", "type ที่ไม่อยู่ในรายการ"),
    ("feat: ", "หัวเรื่องว่าง"),
    # **ต้องผ่าน regex ให้ได้ก่อน** ไม่งั้นรูปแบบเป็นตัวจับ แล้วการตรวจความยาว
    # จะถูกถอดออกได้โดยไม่มีเทสต์ไหนแดง (เจอตอน mutation ของรอบนี้เอง)
    ("feat: " + "ก" * 71, "ยาวเกิน 72 ตัว ทั้งที่รูปแบบถูก"),
    ("feat: " + "ก" * 80, "ยาวเกินและรูปแบบก็ไม่ผ่าน"),
]


# ตัวตัดสินที่พิสูจน์ไว้ที่อื่นแล้ว — **ต้องบอกว่าที่ไหน และด้วยวิธีอะไร** ·
# ตรวจสองทิศเหมือนทะเบียนข้อยกเว้นทุกใบ คือไฟล์ที่อ้างต้องมีจริง
# และต้องเอ่ยถึงสคริปต์นั้นจริง
PROVEN_ELSEWHERE = {
    "run_gates": (
        "tests/test_vendored_tooling.py",
        (
            "ตรรกะย้ายไป `verifiable-gates` แล้วและถูกทดสอบที่นั่น (ADR 0077) — "
            "ที่เหลือให้พิสูจน์คือ *รอยต่อ*: adapter ชี้ทะเบียนกับรากของ repo นี้จริง "
            "ไหม · ทำให้มันชี้ผิดแล้วเทสต์ต้องแดง"
        ),
    ),
    "preflight": (
        "tests/test_vendored_tooling.py",
        (
            "เหมือน `run_gates` — ตรรกะอยู่ใน vendor ส่วนที่นี่พิสูจน์ว่า adapter "
            "ส่ง `--root` ของ repo นี้ และแผนที่ได้อ่านคำสั่งจาก workflow จริง "
            "ไม่ใช่จากสำเนาที่สอง"
        ),
    ),
    "lint_commits": (
        "tests/test_vendored_tooling.py",
        (
            "ตรรกะย้ายไป `verifiable-gates` ขั้น 3a และถูกทดสอบสองทิศที่นั่น "
            "(6 มิวเทชันแดง รวมข้อที่นับความยาวหัวเป็นไบต์) — ที่นี่พิสูจน์ *รอยต่อ*: "
            "พาธที่ hook `commit-msg` เรียก ยังเดินไปถึงตัวจริงและยังบล็อกของผิดได้"
        ),
    ),
    "check_issue_handoff": (
        "tests/test_vendored_tooling.py",
        (
            "เหมือน `lint_commits` — ตรรกะอยู่ใน vendor (5 มิวเทชันแดง) ส่วนที่นี่ "
            "พิสูจน์ว่า job `lint` เรียกพาธนี้แล้วถึงตัวจริง และบริบทจาก env "
            "ยังถูกอ่านเหมือนเดิม"
        ),
    ),
    "schedule_census": (
        "tests/test_vendored_tooling.py",
        (
            "ตรรกะย้ายไป `verifiable-gates` ขั้น 3b และถูกทดสอบสองทิศที่นั่น "
            "(5 มิวเทชันแดง) — ที่นี่พิสูจน์ *รอยต่อ*: ป้อนประวัติเปล่าแล้วต้องแดง "
            "ซึ่งพิสูจน์ว่า adapter อ่าน workflow กับ dependabot.yml ของที่นี่เจอจริง"
        ),
    ),
    "red_streak_census": (
        "tests/test_vendored_tooling.py",
        (
            "เหมือน `schedule_census` — ตรรกะอยู่ใน vendor (5 มิวเทชันแดง) ส่วนที่นี่ "
            "พิสูจน์ว่า adapter ชี้ทั้งรากและ `gates.yaml` ของ repo นี้ ไม่งั้นจะไม่มี "
            "คำสัญญาไหนถูกวัดเลยแล้วรายงานว่าผ่าน"
        ),
    ),
    "n1_smoke": (
        ".github/workflows/ci.yml",
        (
            "job `n-1` รันมันด้วยโค้ดของ tag ล่าสุดทับ schema ของ HEAD ทุก push — "
            "การพิสูจน์คือสัญญา N-1 ที่ยิงกับของจริงสองรุ่น ไม่ใช่ตรรกะที่ mock ได้"
        ),
    ),
}


@pytest.mark.parametrize(("script", "where"), sorted(PROVEN_ELSEWHERE.items()))
def test_a_decider_proven_elsewhere_really_is(script, where):
    """ทิศกลับของข้อยกเว้น — ที่ที่อ้างต้องมีอยู่จริงและต้องพูดถึงสคริปต์นั้นจริง"""
    path, reason = where
    target = pathlib.Path(__file__).resolve().parent.parent / path

    assert target.is_file(), f"{script}: อ้าง {path} ที่ไม่มีอยู่"
    assert script in target.read_text(encoding="utf-8"), f"{script}: {path} ไม่ได้เอ่ยถึงมันแล้ว"
    assert len(reason) > 40, f"{script}: เหตุผลสั้นเกินกว่าจะตัดสินได้"


def test_every_deciding_script_is_in_this_file():
    """**การตรวจสมาชิก** — ตัวตัดสินตัวใหม่ต้องเข้ามาอยู่ ไม่ใช่รอให้มีคนนึกได้

    หลักเดียวกับ "ทุกไฟล์ใต้ `tests/` ต้องเป็นของ gate เดียว" ที่ `gates.yaml`
    ใช้อยู่แล้ว — partition เต็ม ไม่ใช่รายการที่ใครนึกได้ก็ใส่
    """
    here = pathlib.Path(__file__).read_text(encoding="utf-8")
    scripts_dir = pathlib.Path(__file__).resolve().parent.parent / "scripts"

    missing = []
    for path in sorted(scripts_dir.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "บทบาท: decider" not in source:
            continue
        # ตัวที่มีไฟล์เทสต์ของตัวเองอยู่แล้ว ถือว่าพิสูจน์ที่นั่น
        own = (scripts_dir.parent / "tests" / f"test_{path.stem}.py").is_file()
        if own or f"    {path.stem},\n" in here or path.stem in PROVEN_ELSEWHERE:
            continue
        missing.append(path.stem)

    assert not missing, (
        f"สคริปต์ชนิด decider ที่ไม่มีเทสต์ตรรกะที่ไหนเลย: {missing}\n"
        "เพิ่มเข้า import ของไฟล์นี้พร้อมเทสต์ planted violation + clean input "
        "หรือสร้าง tests/test_<ชื่อ>.py ของตัวเอง"
    )


# ------------- รายการไฟล์ที่วัด coverage ของ `scripts/` ต้อง derive มา (รอบ 17 · ข้อ 2)
#
# ตอนตั้งด่านนี้ (ข้อ 1) รายการเป็นชื่อไฟล์สี่ชื่อที่พิมพ์มือลงใน `ci.yml` —
# ซึ่งเป็นโรคเดียวกับที่ข้อ 3 ของรอบเดียวกันไปรักษาที่อื่น · เทสต์ที่เพิ่มเข้ามา
# ใหม่จะไม่ถูกนับ แล้วตัวเลขที่ ratchet เฝ้าอยู่ก็ต่ำกว่าความจริงไปเรื่อย ๆ
#
# ตอนนี้ workflow คัดไฟล์ด้วย `grep` · เทสต์นี้คัดด้วย **AST** แล้วเทียบกัน —
# สองวิธีที่พังคนละแบบ ตรวจทะเบียนใบเดียวกัน

CI_WORKFLOW = pathlib.Path(__file__).resolve().parent.parent / ".github" / "workflows" / "ci.yml"
TESTS_DIR = pathlib.Path(__file__).resolve().parent


def _coverage_step() -> str:
    """คำสั่งของ step ที่วัด coverage ของ `scripts/` — หาไม่เจอ = ด่านหายไปแล้ว"""
    workflow = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    for step in workflow["jobs"]["test"]["steps"]:
        if "scripts/" in str(step.get("name", "")) and "coverage" in str(step.get("name", "")):
            return str(step["run"])
    raise AssertionError("ไม่มี step ที่วัด coverage ของ scripts/ ใน job test แล้ว")


def _imports_a_script(path: pathlib.Path) -> bool:
    """ไฟล์นี้ import โมดูลจาก `scripts` ไหม — อ่านจาก AST ไม่ใช่จากข้อความ"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "scripts":
            return True
        if isinstance(node, ast.Import) and any(
            alias.name.split(".")[0] == "scripts" for alias in node.names
        ):
            return True
    return False


def test_the_coverage_step_does_not_hardcode_the_files_it_measures():
    """ชื่อไฟล์เทสต์ที่พิมพ์ไว้ตรง ๆ ใน workflow = ทะเบียนที่ไม่มีใครตรวจสมาชิก"""
    step = _coverage_step()

    typed = [word for word in step.split() if word.startswith("tests/") and word.endswith(".py")]

    assert not typed, f"step วัด coverage พิมพ์ชื่อไฟล์ไว้เอง: {typed}"


def test_every_test_that_imports_a_script_is_inside_the_measurement(tmp_path):
    """สองวิธีคัดไฟล์ต้องได้ผลเดียวกัน — grep ของ workflow กับ AST ของเทสต์นี้

    ทิศที่สำคัญคือ **AST ⊆ grep**: ไฟล์ที่ import สคริปต์จริงแต่ grep ไม่เจอ
    แปลว่ามันรันอยู่นอกการวัด และโค้ดที่มันคุ้มถูกนับเป็น "ไม่มีใครทดสอบ"
    """
    step = _coverage_step()
    pattern = re.search(r"grep -lE '([^']+)'", step)
    assert pattern, f"อ่านตัวคัดไฟล์จาก step ไม่ออก:\n{step}"

    selected = {
        path.name
        for path in sorted(TESTS_DIR.glob("test_*.py"))
        if re.search(pattern.group(1), path.read_text(encoding="utf-8"), re.MULTILINE)
    }
    importers = {
        path.name for path in sorted(TESTS_DIR.glob("test_*.py")) if _imports_a_script(path)
    }

    missed = sorted(importers - selected)
    assert not missed, (
        f"ไฟล์ที่ import สคริปต์แต่ตัวคัดของ workflow ไม่เจอ: {missed}\n"
        "แก้ regex ใน step 'coverage ของโค้ดที่บังคับกฎ' ของ ci.yml"
    )
    assert len(selected) >= 15, f"ตัวคัดเลือกได้แค่ {len(selected)} ไฟล์ — น้อยผิดปกติ"


def test_subprocess_children_are_counted_or_the_number_punishes_the_better_test(tmp_path):
    """`COVERAGE_PROCESS_START` ต้องถูกตั้ง ไม่งั้นเทสต์ที่ยิงผ่าน subprocess ได้ 0%

    repo นี้บังคับเองว่าการยิงสคริปต์ **ผ่าน subprocess** ดีกว่าการ import แล้ว
    เรียกฟังก์ชัน (`tests/test_measure_generated.py` ทำแบบนั้น) · ถ้าตัววัดไม่นับลูก
    เกณฑ์จะสูงขึ้นเมื่อเขียนเทสต์ให้**แย่ลง** ซึ่งเป็นแรงจูงใจที่กลับด้าน
    """
    workflow = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    (step,) = [
        s
        for s in workflow["jobs"]["test"]["steps"]
        if "scripts/" in str(s.get("name", "")) and "coverage" in str(s.get("name", ""))
    ]

    assert (step.get("env") or {}).get("COVERAGE_PROCESS_START"), (
        "step วัด coverage ไม่ได้ตั้ง COVERAGE_PROCESS_START — "
        "สคริปต์ที่ถูกยิงผ่าน subprocess จะถูกนับเป็น 0% ทุกตัว"
    )
    config = pathlib.Path(__file__).resolve().parent.parent / str(
        step["env"]["COVERAGE_PROCESS_START"]
    )
    assert config.is_file(), f"ชี้ไปไฟล์ config ที่ไม่มีอยู่: {config}"
    assert "scripts" in config.read_text(encoding="utf-8"), "config ของลูกไม่ได้วัด scripts/"


# ------------- ตัวอ่าน workflow ตัวเดียวของ repo (audit รอบ 18 · ข้อ 2)
#
# `on:` ถูกต้องสามรูป · สำนวนเดิม (`{triggers: None}`) รองรับสองรูปที่ hashable
# แล้ว **ระเบิดกับรูปลิสต์** ซึ่งเป็นรูปที่ตัวอย่างในเอกสารของ GitHub ใช้มากที่สุด
# · สำนวนนั้นถูกลอกไว้ห้าที่ และสามที่พังแบบเดียวกัน
#
# บั๊กหลับอยู่เพราะ workflow ทุกไฟล์ของ repo นี้ใช้รูป dict — ด่านที่ไม่เคยเจอ
# อินพุตรูปอื่น คือด่านที่เราไม่รู้ว่ามันตอบอะไรกับอินพุตรูปอื่น

TRIGGER_FORMS = [
    ("on: push\njobs: {}\n", {"push"}),
    ("on: [push, pull_request]\njobs: {}\n", {"push", "pull_request"}),
    ("on:\n  pull_request:\n    branches: [main]\njobs: {}\n", {"pull_request"}),
    ("on:\n  push: null\n  schedule:\n    - cron: '0 3 * * 1'\njobs: {}\n", {"push", "schedule"}),
    ("jobs: {}\n", set()),
]


@pytest.mark.parametrize(("text", "expected"), TRIGGER_FORMS)
def test_every_legal_shape_of_on_is_understood(text, expected):
    """สามรูปของ `on:` ต้องอ่านได้เท่ากัน — ไม่ใช่รูปที่เราบังเอิญใช้อยู่รูปเดียว"""
    assert workflows.triggers(yaml.safe_load(text)) == expected


@pytest.mark.parametrize(("text", "expected"), TRIGGER_FORMS)
def test_asking_about_an_event_never_raises(text, expected):
    """`runs_on()` ต้องตอบ ไม่ใช่โยน — ตัวตัดสินที่ระเบิดคือตัวที่ไม่ได้ตัดสิน"""
    workflow = yaml.safe_load(text)

    assert workflows.runs_on(workflow, "pull_request") == ("pull_request" in expected)


def test_the_list_shape_is_the_one_that_used_to_crash():
    """ทิศที่บั๊กเคยอยู่ — เขียนแยกไว้เพื่อให้ชื่อเทสต์บอกว่าทำไมมันถึงมี"""
    workflow = yaml.safe_load("on: [push, pull_request]\njobs:\n  a: {}\n")

    assert workflows.runs_on(workflow, "pull_request") is True
    assert set(workflows.jobs(workflow)) == {"a"}


def test_cron_lines_are_read_from_the_shape_github_actually_uses():
    """`on.schedule` เป็น **ลิสต์ของ dict** — อ่านผิดรูปแล้วตารางเวลาหายไปเงียบ ๆ"""
    workflow = yaml.safe_load(
        "on:\n  schedule:\n    - cron: '0 3 * * 1'\n    - cron: '30 4 1 * *'\njobs: {}\n"
    )

    assert workflows.schedules(workflow) == ["0 3 * * 1", "30 4 1 * *"]
    assert workflows.schedules(yaml.safe_load("on: [schedule]\njobs: {}\n")) == []


def test_nobody_parses_the_trigger_shape_on_their_own_anymore():
    """**การตรวจสมาชิก** — สำนวนที่พังต้องไม่กลับมาเกิดใหม่ที่ไหนอีก

    หลักเดียวกับ ADR 0039 (ห้ามเก็บคำสั่งไว้สองที่): ตัวแยกวิเคราะห์ก็เป็นคำสั่ง
    ชนิดหนึ่ง · หลักฐานว่าสำเนา drift จริงคือ ตอนเจอบั๊กมีสามสำเนาที่ไม่กันตัวเอง
    และหนึ่งสำเนาที่กันด้วย `isinstance` — คนละพฤติกรรมจากโค้ดที่ลอกกันมา
    """
    root = pathlib.Path(__file__).resolve().parent.parent
    guilty = []
    for path in [*sorted((root / "scripts").glob("*.py")), *sorted((root / "tests").glob("*.py"))]:
        if path.name in {"workflows.py", pathlib.Path(__file__).name}:
            continue
        source = path.read_text(encoding="utf-8")
        if "get(True)" in source or "get(True," in source:
            guilty.append(str(path.relative_to(root)))

    assert not guilty, (
        f"ไฟล์ที่ยังแกะรูปของ `on:` เอง: {guilty}\n"
        "ใช้ scripts/workflows.py (triggers · runs_on · schedules · jobs) แทน"
    )


# ------------- มาร์ก `governance` ต้องตรงกับความจริง (audit รอบ 18 · ข้อ 4)
#
# job `bare` และ `dialect` รันด้วย `-m "not governance"` — การตัดจึงต้องพิสูจน์
# ได้ว่าไม่ได้ตัดสัญญาณทิ้ง · **ถ้ามาร์กติดผิดตัวเดียว ด่านนั้นจะหยุดเดินบนยี่ห้อ
# อื่นโดยไม่มีอะไรฟ้อง** ซึ่งเป็นการปิดตาที่แก้ได้ด้วยการเติมมาร์ก

TESTS_ROOT = pathlib.Path(__file__).resolve().parent


def _conftest():
    """โมดูล conftest ที่ถือกฎการติดมาร์กไว้ — โหลดตรง ๆ ไม่ผ่าน pytest"""
    import conftest

    return conftest


@pytest.mark.parametrize(
    "name",
    ["test_api_todos.py", "test_route_authz.py", "test_services.py", "test_dialect_parity.py"],
)
def test_a_test_that_needs_the_app_is_never_marked_governance(name):
    """ทิศที่อันตราย — เทสต์ที่แตะแอปต้องเดินครบทุก job เสมอ

    `test_dialect_parity.py` อยู่ในรายการนี้โดยตั้งใจ: มันหน้าตาเหมือนเทสต์ชั้น
    กติกา (อ่าน model แล้วตรวจชนิดคอลัมน์) แต่มันสร้างแอปจริงเพื่ออ่าน metadata
    — ตัดออกจาก job `dialect` เมื่อไหร่ คือการถอดด่านที่ job นั้นมีไว้เพื่อมันโดยตรง
    """
    source = (TESTS_ROOT / name).read_text(encoding="utf-8")

    assert _conftest().touches_the_app(source), f"{name} จะถูกตัดออกจาก job dialect/bare"


@pytest.mark.parametrize("name", ["test_gates.py", "test_asvs.py", "test_checker_logic.py"])
def test_a_file_reading_test_is_marked_governance(name):
    """ทิศ "ผ่านเมื่อควรผ่าน" — ถ้าไม่มีอะไรถูกมาร์กเลย การตัดก็ไม่ได้ประหยัดอะไร"""
    source = (TESTS_ROOT / name).read_text(encoding="utf-8")

    assert not _conftest().touches_the_app(source), f"{name} ไม่ถูกนับเป็นชั้นกติกา"


def test_the_jobs_that_ask_other_questions_actually_skip_it():
    """`ci.yml` ต้องกรองจริง — มาร์กที่ไม่มีใครกรอง คือมาร์กที่ไม่ได้ทำอะไรเลย"""
    workflow = yaml.safe_load(CI_WORKFLOW.read_text(encoding="utf-8"))
    commands = {
        job: " ".join(str(step.get("run") or "") for step in workflow["jobs"][job]["steps"])
        for job in ("bare", "dialects", "test")
    }

    assert "not governance" in commands["bare"], "job bare ยังเดินเทสต์ชั้นกติกาซ้ำ"
    assert "not governance" in commands["dialects"], "job dialects ยังเดินเทสต์ชั้นกติกาซ้ำ"
    assert "not governance" not in commands["test"], (
        "job test ต้องเดินทั้งชุด — ไม่งั้นเทสต์ชั้นกติกาจะไม่ถูกรันที่ไหนเลย"
    )


def test_no_gate_watched_by_those_jobs_depends_on_a_governance_file():
    """gate ที่ประกาศว่า job `bare`/`dialects` เป็นคนบังคับ ต้องไม่ถูกตัดออกไปด้วย"""
    gates = yaml.safe_load((TESTS_ROOT.parent / "gates.yaml").read_text(encoding="utf-8"))["gates"]
    conftest = _conftest()

    stranded = []
    for gate in gates:
        enforced = gate["enforced_by"]
        if enforced.get("job") not in {"bare", "dialects"}:
            continue
        for name in enforced.get("tests", []):
            source = (TESTS_ROOT.parent / name).read_text(encoding="utf-8")
            if not conftest.touches_the_app(source):
                stranded.append(f"{gate['id']} → {name}")

    assert not stranded, f"gate ที่ job ของมันจะไม่รันเทสต์นั้นอีกแล้ว: {stranded}"


# ------------- คำโฆษณาบนช่อง About ของ repo (2026-08-20)
#
# ช่องนั้น **ไม่ได้อยู่ใน git** — ไม่มี diff ไหนทำให้ใครสังเกตว่ามันเก่า ·
# วัดเมื่อ 2026-08-20: เขียนว่า v2.0.0 · 105 gate · 16 รอบ audit ขณะที่ของจริง
# คือ v2.0.2 · 107 · 20 · เป็นคำโฆษณาบรรทัดแรกที่คนเห็นก่อนกดเข้ามา
#
# ตัวตัดสินตรวจ **เลขรุ่นอย่างเดียว** โดยตั้งใจ — เลขอื่นเปลี่ยนบ่อยและไม่มี
# สัญญาว่าจะอยู่ในรูปไหน การบังคับทุกเลขจะกลายเป็นด่านที่แดงเพราะถ้อยคำ


def _about(**counts: int) -> str:
    """ประโยคโฆษณาที่ *ถูกทุกตัว* แล้วให้ผู้เรียกทำให้ผิดทีละตัว (audit รอบ 24)"""
    source = (pathlib.Path(__file__).resolve().parent.parent / "app" / "__init__.py").read_text(
        encoding="utf-8"
    )
    current = re.search(r'__version__ = "([^"]+)"', source).group(1)
    real = {**audit_posture.advertised_counts(REQUIRED_NOW), **counts}
    said = " · ".join(f"{value} {phrase}" for phrase, value in real.items())
    return f"… v{current} (AGPL-3.0): {said}"


def test_a_stale_version_in_the_about_box_is_caught():
    """ทิศ "แดงเมื่อควรแดง" — คำโฆษณาที่ค้างรุ่นเก่าต้องถูกจับ"""
    stale = audit_posture.description_problems(
        "… v1.6.0 (AGPL-3.0): 105 machine-checked gates …", REQUIRED_NOW
    )

    assert stale, "คำโฆษณาที่บอกรุ่นเก่ากลับผ่าน"


@pytest.mark.parametrize(
    "phrase",
    ["machine-checked gates", "ADRs", "recorded governance audits", "required checks"],
)
def test_every_number_the_about_box_advertises_is_counted(phrase):
    """เลขที่นับได้แต่ไม่มีใครนับ คือเลขที่ค้างจนกว่าจะมีคนบังเอิญสังเกต (audit รอบ 24)

    ตอน v2.2.0 มันค้างพร้อมกันสามที่ — และตัวตรวจนี้ถือสตริงนั้นอยู่ในมือแล้ว
    ตั้งแต่วันแรก โดยอ่านเฉพาะเลขรุ่น
    """
    wrong = audit_posture.description_problems(_about(**{phrase: 9_999}), REQUIRED_NOW)

    assert wrong, f"เลข {phrase!r} ผิดแล้วยังผ่าน"
    assert any(phrase in line for line in wrong), "แดงแล้วแต่ไม่ได้บอกว่าเลขไหนผิด"


def test_dropping_a_number_from_the_about_box_is_not_silent():
    """ทิศที่คนลืมเสมอ — วลีที่หายไปทั้งวลี ต้องไม่กลายเป็น "ไม่มีอะไรให้ตรวจ" """
    trimmed = re.sub(r"\d+ ADRs · ", "", _about())

    assert audit_posture.description_problems(trimmed, REQUIRED_NOW), (
        "ถอดวลีออกจากช่อง About แล้วด่านเงียบ — แฟ้มที่ไม่มีใครอ่านคือไฟล์ข้อความ"
    )


# ---------------------------------- ใบตอบ badge (audit รอบ 27 ข้อ 3)
#
# `docs/SUPPLY-CHAIN.md` มีแถวเดียวที่ตอบว่า "ไม่มีเครื่องตรวจ" คือ bestpractices.dev
# — และนาฬิกาของแถวนั้นเป็นของเขาล้วน ๆ: **เขาแก้เกณฑ์ได้โดยที่เราไม่ได้ทำอะไร**
# แล้ว badge ลดระดับเงียบ ๆ · ตัวทวงที่มีคือแถวรอบ 12 เดือน ซึ่งแปลว่าเลขที่ค้าง
# จะค้างได้นานสุดหนึ่งปี · ตอนตั้งด่านนี้ก็พบของค้างจริง (เอกสารเขียน gold 26%
# ขณะที่เว็บตอบ 57% มาตั้งแต่ v2.1.0)
#
# **เทสต์ที่นี่ไม่แตะเครือข่าย** — ปลอมใบตอบเอา ส่วนการอ่านจริงพิสูจน์ตอนเขียน

ADVERTISED = {
    "passing": ("badge_percentage_0", 100),
    "gold": ("badge_percentage_2", 57),
}


def test_badge_numbers_that_match_the_site_are_silent():
    """ทิศ "ผ่านเมื่อควรผ่าน" — ตรงกันแล้วต้องไม่บ่น"""
    answer = {"badge_percentage_0": 100, "badge_percentage_2": 57}

    assert audit_posture.badge_problems(answer, ADVERTISED) == []


def test_a_badge_that_was_downgraded_is_reported():
    """เขาลดระดับให้เราโดยที่เราไม่ได้ทำอะไร — ต้องดัง ไม่ใช่รอแถวรอบ 12 เดือน"""
    answer = {"badge_percentage_0": 100, "badge_percentage_2": 41}

    problems = audit_posture.badge_problems(answer, ADVERTISED)

    assert len(problems) == 1, problems
    assert "gold" in problems[0], problems
    assert "57" in problems[0], "ไม่ได้บอกเลขที่เอกสารประกาศ"
    assert "41" in problems[0], "ไม่ได้บอกเลขที่เว็บตอบจริง"


def test_a_field_the_site_stopped_returning_is_reported_not_skipped():
    """เกณฑ์ของเขาเปลี่ยนรูปจนฟิลด์หาย = ต้องดัง ไม่ใช่เงียบเพราะไม่มีอะไรให้เทียบ"""
    problems = audit_posture.badge_problems({"badge_percentage_0": 100}, ADVERTISED)

    assert any("badge_percentage_2" in line for line in problems), problems


def test_a_site_we_cannot_read_is_a_problem_not_a_pass():
    """อ่านไม่ได้ = แดง — ด่านที่ข้ามตอนอ่านไม่ได้ รายงานว่าเลขตรงในวันที่ไม่เคยอ่าน"""
    assert audit_posture.badge_problems(None, ADVERTISED)


def test_removing_the_table_from_the_doc_is_reported():
    """ทิศกลับ — ถอดตารางออกแล้วด่านต้องดัง ไม่ใช่ผ่านฟรีเพราะไม่มีอะไรให้เทียบ"""
    assert audit_posture.badge_problems({"badge_percentage_0": 100}, {})


def test_the_table_in_the_repo_is_the_one_the_checker_reads():
    """ตารางจริงในเอกสารต้องย่อยได้ครบหกชุด — regex ที่อ่านไม่เจอคือด่านที่เขียวเปล่า"""
    advertised = audit_posture.advertised_badges()

    assert set(advertised) == {
        "passing",
        "silver",
        "gold",
        "baseline-1",
        "baseline-2",
        "baseline-3",
    }, advertised


def test_an_about_box_that_names_the_current_version_passes():
    """ทิศ "ผ่านเมื่อควรผ่าน" — ต้องอ่าน `__version__` จริง ไม่ใช่เลขที่ฝังไว้

    อ่านเลขรุ่นจาก *ไฟล์* ไม่ใช่ `import app` — ไฟล์นี้เป็นเทสต์ชั้นกติกาที่
    job `bare`/`dialect` ตัดออก (audit รอบ 18) การ import แอปจะทำให้มันหลุด
    ออกจากกลุ่มนั้นทันที และด่านของรอบ 18 ก็จับได้จริงตอนเขียนเทสต์นี้
    """
    assert audit_posture.description_problems(_about(), REQUIRED_NOW) == []


def test_no_answer_from_the_api_is_not_treated_as_a_failure():
    """`None` = ไม่ได้ถามหรือถามไม่ได้ — คนละเรื่องกับ "ตอบแล้วผิด"

    หลักเดียวกับที่ `--input` ของสคริปต์นี้ทำให้รันโดยไม่ต่อเน็ตได้
    """
    assert audit_posture.description_problems(None, REQUIRED_NOW) == []


def test_every_merge_setting_declares_a_value_and_a_reason():
    """**ทะเบียนที่บอกแค่ว่า "อ่านไม่ได้" คือทะเบียนที่ไม่มีเจ้าของ** (5-Why 2026-08-21)

    `delete_branch_on_merge` หลุดจากแผนที่ไปทั้งใบเพราะมันอยู่ในคลาสที่ token
    สิทธิ์ต่ำสุดอ่านไม่ได้ — ของเดิมบันทึกว่าเครื่องมองไม่เห็นอะไร แต่ไม่มีที่ไหน
    บันทึกว่าค่าที่ควรเป็นคืออะไร · ผลคือกติกาถูกบังคับด้วยความจำ แล้ว branch
    ที่ merge แล้วกองค้าง 64 ใบโดยไม่มีอะไรทัก
    """
    assert audit_posture.MERGE_SETTINGS, "ทะเบียน merge setting ว่าง"

    for flag, declared in audit_posture.MERGE_SETTINGS.items():
        assert isinstance(declared.want, bool), f"{flag} ไม่ได้ประกาศค่าที่ควรเป็น"
        assert len(declared.why) > 20, f"{flag} มีค่าแต่ไม่มีเหตุผลที่ตัดสินได้: {declared.why!r}"
        assert not declared.readable, f"{flag} ถูกประกาศว่าอ่านได้ — แล้วมันจะไม่มีหมายเหตุ"


def test_the_note_for_an_unreadable_setting_says_what_it_should_be():
    """รายงานที่บอกแค่ "อ่านไม่ได้" ทำให้คนอ่านไม่รู้ว่าต้องไปตั้งค่าอะไร"""
    invisible = {**HEALTHY, "delete_branch_on_merge": None}

    notes = audit_posture.unreadable(invisible)

    assert any("delete_branch_on_merge" in note for note in notes), "ไม่ได้รายงานว่ามองไม่เห็น"
    assert any("True" in note for note in notes), "รายงานแล้วแต่ไม่ได้บอกว่าค่าที่ควรเป็นคืออะไร"


def test_a_readable_merge_setting_that_drifted_is_a_problem_not_a_note():
    """อ่านได้แล้วผิด = ปัญหา · อ่านไม่ได้ = หมายเหตุ — สองอย่างนี้ห้ามสลับกัน"""
    drifted = {**HEALTHY, "delete_branch_on_merge": False}

    assert audit_posture.compare(drifted, 2, None), "อ่านได้แล้วผิด ต้องเป็นปัญหา"
    assert audit_posture.unreadable(drifted) == [], "อ่านได้แล้วต้องไม่มีหมายเหตุค้าง"


# ------------------------------- เพดานของการปิดเครื่องตรวจรายบรรทัด (audit r21 ข้อ 2)
#
# ทุก ratchet ในไฟล์นี้เดินขึ้น · กองนี้เดินลง และนั่นคือเหตุผลที่มันต้องมีตรรกะ
# ของตัวเอง: "ของจริงต่ำกว่าที่ประกาศ" เป็น**ข่าวดี**ที่ต้องบันทึก ไม่ใช่การถอย
#
# **ตรรกะสองทิศอยู่ที่ verifiable-gates แล้ว** (ADR 0077 · ขั้น 3c — 7 มิวเทชันแดง)
# ที่เหลือให้พิสูจน์ที่นี่คือ *ทะเบียนกับถ้อยคำ*: ชื่อพวกนี้ถูกประกาศเป็นเพดานจริงไหม
# และข้อความที่ออกมาบอกที่ที่ต้องไปแก้ของ repo นี้ถูกไหม


@pytest.mark.parametrize("name", check_ratchets.CEILINGS)
def test_a_new_suppression_is_a_decision_not_a_side_effect(name):
    """เกินเพดาน = แดง พร้อมบอกว่าต้องไปขยับที่ไหน — ทุกชื่อในกองนี้"""
    found = check_ratchets.problems({name: 99.0}, {name: 100.0})

    assert found, f"{name}: เพิ่มข้อยกเว้นแล้วต้องแดง"
    assert "ceilings" in found[0], "แดงแล้วแต่ไม่ได้บอกว่าต้องไปแก้ที่ไหน"


@pytest.mark.parametrize("name", check_ratchets.CEILINGS)
def test_a_freed_slot_must_be_recorded_not_left_open(name):
    """ลดลงแล้วไม่ลดเพดานตาม = ที่ว่างถูกถมกลับเงียบ ๆ (ทิศที่คนลืมเสมอ)"""
    found = check_ratchets.problems({name: 99.0}, {name: 90.0})

    assert found, f"{name}: ของจริงลดลงแล้วเพดานต้องตามลงมา"
    assert "90" in found[0], "ต้องบอกตัวเลขใหม่ที่ควรเป็น"


@pytest.mark.parametrize("name", check_ratchets.CEILINGS)
def test_a_ceiling_that_matches_reality_is_silent(name):
    """ทิศ "ผ่านเมื่อควรผ่าน" — ตัวตรวจที่ดังกับของปกติจะถูกปิดเสียง"""
    assert check_ratchets.problems({name: 99.0}, {name: 99.0}) == []


def test_the_counter_reads_real_files():
    """อ่านของจริง ไม่ใช่ค่าคงที่"""
    counts = check_ratchets.suppression_counts()

    assert counts["suppressions"] > 0, "นับไม่เจอเลย — ตัวอ่านพังหรือขอบเขตผิด"
    assert counts["suppressions_without_reason"] <= counts["suppressions"]


# ตัวอย่างต้องประกอบขึ้นตอนรัน **ห้ามเขียนเป็นข้อความตรง ๆ** — ไฟล์นี้อยู่ในขอบเขต
# ที่ตัวนับสแกน ตัวอย่างที่เขียนตรง ๆ จะถูกนับเป็นข้อยกเว้นจริงแล้วดันเพดานขึ้น
# (เกิดขึ้นจริงตอนเขียน: ตัวอย่างใน docstring ของตัวนับเองทำให้เพดานเด้งเป็น 100)
HASH = "#"


def test_the_scan_covers_this_repository_s_own_layers():
    """ขอบเขตที่สแกนเป็นของ repo นี้ — ตัวจำแนกรายบรรทัดพิสูจน์แล้วที่ vg

    ที่นี่พิสูจน์ว่า**ขอบเขตถูก**: ทั้งสามชั้นที่ประกาศไว้ต้องมีของถูกนับจริง
    ขอบเขตที่พิมพ์ผิดชั้นใดชั้นหนึ่งจะยังคืนเลขบวก แล้วเพดานจะเฝ้าของน้อยกว่าที่คิด
    โดยไม่มีอะไรฟ้อง

    เรียกตัวอ่านผ่าน `check_ratchets.measure` ไม่ใช่ import ตรง — ไฟล์นี้จึงไม่
    ต้องพึ่งว่า path ของ vendor ถูกต่อไว้แล้วตอนมันถูก import เอง
    """
    for pattern in check_ratchets.SUPPRESSION_SOURCES:
        counts = check_ratchets.measure.suppression_counts(
            check_ratchets.ROOT, (pattern,), check_ratchets.SUPPRESSION_SKIP
        )
        assert counts["suppressions"] > 0, f"{pattern}: ไม่มีอะไรถูกนับเลย — ขอบเขตนี้ตายแล้ว"


def test_the_generated_file_stays_out_of_the_count():
    """`app/sun_data.py` generate มา — บรรทัดในนั้นไม่ใช่คำตัดสินของใคร"""
    with_it = check_ratchets.measure.suppression_counts(
        check_ratchets.ROOT, check_ratchets.SUPPRESSION_SOURCES
    )
    without_it = check_ratchets.suppression_counts()

    assert without_it["suppressions"] <= with_it["suppressions"]
    assert "sun_data.py" in check_ratchets.SUPPRESSION_SKIP


# ------------- หน้าที่สร้างมาให้เลิกนับด้วยมือ ต้องไม่มีเลขที่นับด้วยมือ (audit r21 ข้อ 3)

PAGE_CLAIM = re.compile(r"แถวตรวจตามรอบ (\d+) แถว ·\s*\n?ทะเบียนข้อยกเว้น (\d+) แฟ้ม")


def test_the_single_pending_page_agrees_with_what_it_reads():
    """เลขในหัวไฟล์ต้องตรงกับของจริงที่ตัวมันเองอ่านได้

    r13 สร้างหน้านี้เพราะต้องเปิด 8 ที่ถึงจะรู้ว่าอะไรค้าง · r14 พบว่ามันรายงาน
    ของที่ไม่ได้ค้าง 3 จาก 8 · r21 พบว่า **หัวไฟล์ของมันเองเป็นเลขที่นับด้วยมือ
    และผิดทั้งสองตัว** (บอก 24 แถว / 7 แฟ้ม ขณะที่ของจริงคือ 26 / 8)
    """
    page = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "whats_pending.py"
    source = page.read_text(encoding="utf-8")
    claim = PAGE_CLAIM.search(source)

    assert claim, "หัวไฟล์ whats_pending.py ไม่ได้ประกาศขนาดของสองกองแรกแล้ว"
    assert (int(claim.group(1)), int(claim.group(2))) == (
        len(whats_pending.cadence_rows()),
        len(whats_pending.REGISTERS),
    ), "เลขที่หัวไฟล์ประกาศ ไม่ตรงกับที่ตัวมันเองอ่านได้"


# ------------- issue ที่เปิดให้คนใหม่ ต้องไม่ถูกปิดเงียบ ๆ (เหตุจริง 2026-08-20)
#
# ตรรกะทั้งหมดแยกจากการเรียก GitHub โดยตั้งใจ — ด่านที่ทดสอบได้เฉพาะตอนต่อเน็ต
# คือด่านที่ไม่มีใครทดสอบ

GOOD_FIRST = {"good first issue", "help wanted"}
TAKEN = [{"number": 171, "title": "data-doctor check"}]


# --------------------------------- พื้นผิว API ของไฟล์ Python (`scripts/skeleton.py`)
#
# ไอเดียมาจาก `graft` — แต่รับมาเฉพาะชั้นที่ deterministic · ไม่มี index ไม่มี
# ขั้นตอน build จึงไม่มีคำถามว่าข้อมูลสดหรือยัง ซึ่งเป็นคำถามที่ audit r21 ชี้ว่า
# เป็นต้นทางของหนี้ที่เงียบที่สุด

SAMPLE = '''"""โมดูลตัวอย่าง — บรรทัดแรกเท่านั้นที่ถูกหยิบ

ส่วนนี้ไม่ควรโผล่บนพื้นผิว
"""


def open_one(name: str, count: int = 3) -> bool:
    """ทำอะไรสักอย่าง"""
    helper = 1
    return bool(helper)


def _hidden() -> None:
    """ไม่ใช่พื้นผิว"""


class Thing(Base):
    """ของชิ้นหนึ่ง"""

    @property
    def label(self) -> str:
        """ป้ายของมัน"""
        return "x"

    def _inner(self) -> None:
        """ไม่ใช่พื้นผิว"""


async def fetch(url: str) -> str:
    """ดึงของ"""
    return url
'''


# ------------- คีย์ซ้ำใน workflow: Python ยอมรับ GitHub ปฏิเสธ (ขั้น 2e · ADR 0077)


def _duplicate_keys(text: str) -> list[tuple[str, int]]:
    """คีย์ที่ปรากฏสองครั้งใน mapping เดียวกัน — `yaml.safe_load` เอาตัวหลังเงียบ ๆ"""

    class Loud(yaml.SafeLoader):
        pass

    found: list[tuple[str, int]] = []

    def mapping(loader, node, deep=False):  # ลายเซ็นที่ pyyaml เรียก
        seen = set()
        for key_node, _ in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in seen:
                found.append((str(key), key_node.start_mark.line + 1))
            seen.add(key)
        return yaml.SafeLoader.construct_mapping(loader, node, deep)

    Loud.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    yaml.load(text, Loud)  # noqa: S506 — Loud สืบทอด SafeLoader ทั้งดุ้น
    return found


@pytest.mark.parametrize("path", sorted(CI_WORKFLOW.parent.glob("*.yml")), ids=lambda p: p.name)
def test_no_workflow_has_a_key_written_twice(path):
    """**workflow ที่ GitHub อ่านไม่ได้ ให้ผลเป็น "ไม่มี check เลย" ไม่ใช่ check สีแดง**

    `yaml.safe_load` รับคีย์ซ้ำแล้วเอาตัวหลัง — เทสต์ทุกตัวใน repo นี้ที่อ่าน
    workflow จึงเขียวสนิทกับไฟล์ที่ GitHub ปฏิเสธทั้งใบ · และเมื่อมันถูกปฏิเสธ
    run ที่ได้มี 0 job แล้วหน้า PR ขึ้นว่า "no checks reported" ซึ่งอ่านเหมือน
    ยังไม่รัน ไม่ใช่เหมือนพัง

    เกิดจริงตอนขั้น 2e: ตัวแปลงที่เติม `submodules: true` ให้ทุก checkout ไปเติม
    ซ้ำในบล็อก `with:` ที่มีคีย์นั้นอยู่แล้ว · การตรวจด้วย `yaml.safe_load` ก่อน
    push บอกว่าผ่าน แล้ว push ไปได้เงียบ ๆ
    """
    duplicates = _duplicate_keys(path.read_text(encoding="utf-8"))
    assert not duplicates, (
        f"{path.name} มีคีย์ที่เขียนซ้ำในบล็อกเดียวกัน: {duplicates}\n"
        "GitHub จะปฏิเสธทั้งไฟล์ แล้ว PR จะขึ้นว่าไม่มี check แทนที่จะแดง"
    )
