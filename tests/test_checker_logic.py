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
import typing

import pytest
import yaml

from scripts import (
    audit_image,
    audit_pins,
    audit_plugin_deps,
    audit_posture,
    check_issue_handoff,
    check_ratchets,
    check_semgrep,
    lint_commits,
    red_streak_census,
    removals_census,
    rerun_census,
    schedule_census,
    skeleton,
    whats_pending,
    workflows,
)


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
}
ON_PR = {"lint", "test"}


def test_posture_passes_when_the_platform_matches_what_we_declared():
    """ทิศ "ผ่านเมื่อควรผ่าน" — ท่าทีที่ตรงทุกข้อต้องไม่มีเสียงบ่น"""
    assert audit_posture.compare(HEALTHY, ON_PR, 2, (2, 2)) == []


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
        ({"required_checks": ["lint"]}, "job ที่รันบน PR หลุดจากรายการบังคับ"),
        ({"required_checks": ["lint", "test", "ผี"]}, "บังคับ check ที่ไม่มีใครสร้างได้"),
    ],
)
def test_posture_catches_every_way_the_platform_can_drift(change, why):
    """ทุกทางที่ท่าทีจะเลื่อนต้องแดง — ไม่ใช่แค่กรณีที่นึกถึงตอนเขียน"""
    assert audit_posture.compare({**HEALTHY, **change}, ON_PR, 2, None), why


def test_posture_tells_off_apart_from_invisible(capsys):
    """**ปิดอยู่** กับ **มองไม่เห็น** ต่างกันคนละขั้ว — รายงานผิดฝั่งคือการโกหก

    `allow_auto_merge` ถูกคืนมาเฉพาะกับ token ที่มี `contents:write` (เอกสารของ
    GitHub ระบุไว้ตรง ๆ) · `POSTURE_TOKEN` เป็น token อ่านอย่างเดียวโดยตั้งใจ
    ฟิลด์นี้จึงมาเป็น `None` ไม่ใช่ `False` — ฉบับแรกอ่านว่า "ไม่เป็น True แปลว่า
    ปิด" แล้วรายงานว่า auto-merge ปิดอยู่ ทั้งที่มันเปิดและ**ใช้งานอยู่ทุก PR**
    (run 32108560896 · การรันจริงครั้งแรกของด่านนี้)
    """
    invisible = {**HEALTHY, "allow_auto_merge": None}

    assert audit_posture.compare(invisible, ON_PR, 2, None) == [], (
        "ฟิลด์ที่ token อ่านไม่ได้ ต้องไม่ถูกนับเป็นท่าทีที่ผิด"
    )
    assert audit_posture.unreadable(invisible), "แต่ต้องรายงานว่ามองไม่เห็น ไม่ใช่เงียบ"
    assert audit_posture.unreadable(HEALTHY) == [], "อ่านได้แล้วต้องไม่มีหมายเหตุค้าง"


def test_posture_catches_a_document_that_advertises_the_wrong_count():
    """เลข "required NN จาก MM" ในเอกสารต้องตรงกับของจริง ไม่ใช่กับตอนที่เขียน"""
    assert audit_posture.compare(HEALTHY, ON_PR, 2, (26, 29))


def test_posture_lets_the_declared_exemptions_through():
    """job ที่ไม่รันบน PR ต้องไม่ถูกนับว่าหลุด — แต่ต้องประกาศพร้อมเหตุผลที่เดียว"""
    assert "release-sign" in audit_posture.EXEMPT
    assert audit_posture.compare(HEALTHY, ON_PR | {"release-sign"}, 3, None) == []


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

    assert audit_posture.unrequired_problems(produced, {"lint", "test"}) == []


def test_an_undeclared_unrequired_check_is_red():
    """job ใหม่ที่ไม่ถูกบังคับและไม่มีใครประกาศ = ด่านที่ล้มเงียบได้ทั้งวัน"""
    produced = {"lint", "test", "job-ใหม่"} | set(audit_posture.EXEMPT)

    problems = audit_posture.unrequired_problems(produced, {"lint", "test"})

    assert problems, "job ใหม่ที่ไม่มีใครประกาศต้องถูกจับ"
    assert "job-ใหม่" in problems[0], "ข้อความต้องบอกว่าตัวไหน ไม่ใช่แค่ว่ามีปัญหา"


def test_a_declared_exemption_that_names_nothing_is_red():
    """ทิศที่เงียบเสมอ — ยกเว้น job ที่ถูกลบไปแล้ว ไม่มีอะไรฟ้องถ้าไม่ตรวจทิศนี้"""
    assert audit_posture.unrequired_problems({"lint"}, {"lint"}), (
        "EXEMPT ทั้งชุดไม่ตรงกับ job ไหนเลย แต่ตัวตรวจเงียบ"
    )


def test_matrix_checks_are_matched_by_their_job_name():
    """`dialect (mysql-8)` ต้องนับเป็น job `dialect` ไม่ใช่ชื่อแปลกที่ไม่มีในทะเบียน"""
    produced = {"dialect (mysql-8)", "dialect (mariadb-11)"} | set(audit_posture.EXEMPT)

    assert audit_posture.unrequired_problems(produced, {"dialect (mysql-8)"}), (
        "แถว matrix ที่หลุดจากรายการบังคับต้องถูกจับ"
    )


# --------------------------------- ตารางเวลาที่หยุดยิง (ADR 0064 ชั้นถัดไป · audit r10)
#
# "ไม่มี run เลย" หน้าตาเหมือน "ไม่มี run ไหนแดง" เป๊ะในทุกเครื่องมือที่เรามี —
# `rerun_census.py` นับจากสิ่งที่ *เกิดขึ้น* ไม่ใช่สิ่งที่ *ควรเกิด*

WEEKLY = {"scorecard.yml": schedule_census.WEEK}
NOW = "2026-08-18T09:00:00+00:00"


@pytest.mark.parametrize(
    ("cron", "hours", "why"),
    [
        ("27 5 * * 1", schedule_census.WEEK, "ตรึงวันในสัปดาห์ = ทุกสัปดาห์"),
        ("0 3 1 * *", schedule_census.MONTH, "ตรึงวันที่ = ทุกเดือน"),
        ("17 3 * * *", schedule_census.DAY, "ตรึงชั่วโมง = ทุกวัน"),
        ("*/5 * * * *", schedule_census.HOUR, "ไม่ตรึงอะไรหยาบกว่านาที = ทุกชั่วโมง"),
    ],
)
def test_the_period_of_a_cron_line_is_read_from_its_coarsest_field(cron, hours, why):
    """รอบต้องอ่านจาก cron จริง ไม่ใช่เดาจากชื่อ workflow"""
    assert schedule_census.period_hours(cron) == hours, why


def test_a_schedule_that_still_fires_on_time_is_quiet():
    """ทิศ "ผ่านเมื่อควรผ่าน" — ยิงเมื่อวานแล้วต้องไม่มีเสียงบ่น"""
    last = {"scorecard.yml": "2026-08-17T05:41:19+00:00"}

    assert schedule_census.problems(WEEKLY, last, NOW, 2) == []


def test_a_schedule_that_never_fired_is_red():
    """ประกาศ cron แล้วไม่เคยยิงเลย = workflow ที่ถูกปฏิเสธทั้งไฟล์ (เกิดจริงมาแล้ว)"""
    found = schedule_census.problems(WEEKLY, {"scorecard.yml": None}, NOW, 2)

    assert found, "cron ที่ไม่เคยยิงเลยต้องแดง"
    assert "ไม่เคยมี run" in found[0]


def test_a_schedule_that_stopped_firing_is_red():
    """หยุดยิงกลางทางคือความเงียบที่หน้าตาเหมือนความสำเร็จ"""
    stale = {"scorecard.yml": "2026-07-01T05:41:19+00:00"}

    assert schedule_census.problems(WEEKLY, stale, NOW, 2), "เงียบมา 48 วันแต่ตัวตรวจไม่ว่าอะไร"


def test_the_tolerance_is_a_multiple_of_the_declared_period():
    """cron รายสัปดาห์ที่ยิงเมื่อ 10 วันก่อน ยังอยู่ในเกณฑ์ 2 เท่า แต่ตกเกณฑ์ 1 เท่า"""
    last = {"scorecard.yml": "2026-08-08T05:41:19+00:00"}

    assert schedule_census.problems(WEEKLY, last, NOW, 2) == []
    assert schedule_census.problems(WEEKLY, last, NOW, 1), "เกณฑ์ที่แคบลงต้องจับได้"


def test_the_declared_schedules_on_disk_are_readable():
    """อ่านจาก workflow จริงได้ — ไม่ใช่แค่ fixture ในเทสต์ที่อ่านได้"""
    declared = schedule_census.declared_schedules()

    assert declared, "ไม่เห็น cron สักตัวใน .github/workflows — ตัวดึงพังหรือ workflow เปลี่ยนรูป"
    assert all(hours > 0 for hours in declared.values())


def test_dependabot_is_reported_as_something_no_machine_can_check():
    """ของที่ตรวจด้วยเครื่องไม่ได้ ต้องถูกเรียกว่าอย่างนั้น ไม่ใช่ถูกเดาไปข้างใดข้างหนึ่ง"""
    ecosystems = schedule_census.dependabot_ecosystems()

    assert ecosystems, "dependabot.yml ประกาศรอบไว้แต่ตัวรายงานไม่เห็น"
    assert all("weekly" in line or "daily" in line or "monthly" in line for line in ecosystems)


# ------------------------- `within_days` ทำได้จริงไหม (ADR 0066 → วัดได้ในรอบ 11)
#
# รอบ 10 ให้ทุก gate ที่บล็อกไม่ได้ประกาศว่า "ใครเห็นภายในกี่วัน" แต่สิ่งเดียวที่
# ตรวจมันคือ *รูปแบบ* · ตัวนี้วัดขอบบนของเวลาที่ใช้รับรู้+แก้ จากความยาวของช่วง
# ที่ workflow อยู่ในสถานะแดงบน main — ไม่ใช่ MTTA แท้ ๆ และต้องเรียกให้ถูก


def _run(path, stamp, conclusion, name="ชื่ออะไรก็ได้"):
    return {"path": path, "created_at": stamp, "conclusion": conclusion, "name": name}


WATCHED = ".github/workflows/scorecard.yml"


def test_a_red_streak_is_measured_from_first_failure_to_next_success():
    runs = [
        _run(WATCHED, "2026-08-17T16:30:00+00:00", "failure"),
        _run(WATCHED, "2026-08-17T23:00:00+00:00", "failure"),
        _run(WATCHED, "2026-08-18T06:49:00+00:00", "success"),
    ]

    assert red_streak_census.longest_red_hours(runs)[WATCHED] == pytest.approx(14.3, abs=0.1)


def test_runs_are_grouped_by_path_not_by_name():
    """run ที่ GitHub ปฏิเสธทั้งไฟล์ถูกตั้งชื่อด้วย *path* — รวมด้วยชื่อจะตัดประวัติเป็นสองก้อน

    ฉบับแรกของการวัดนี้พลาดตรงนี้จริง: ได้ 2.2 ชม. แทนที่จะเป็น 14.6
    """
    runs = [
        _run(WATCHED, "2026-08-17T16:30:00+00:00", "failure", name=WATCHED),
        _run(WATCHED, "2026-08-18T06:49:00+00:00", "success", name="scorecard"),
    ]

    measured = red_streak_census.longest_red_hours(runs)

    assert list(measured) == [WATCHED], "ชื่อที่ต่างกันต้องไม่ทำให้กลายเป็นสอง workflow"
    assert measured[WATCHED] > 14


def test_a_streak_that_has_not_ended_yet_still_counts():
    """ความแดงที่ยังไม่จบคือความแดงที่ยาวที่สุดเสมอเมื่อมองจากตอนนี้"""
    runs = [
        _run(WATCHED, "2026-08-10T00:00:00+00:00", "failure"),
        _run(WATCHED, "2026-08-18T00:00:00+00:00", "failure"),
    ]

    assert red_streak_census.longest_red_hours(runs)[WATCHED] == pytest.approx(192.0, abs=0.1)


def test_a_promise_that_reality_beats_is_quiet():
    """ทิศ "ผ่านเมื่อควรผ่าน" — แดง 14 ชม. ใต้คำสัญญา 7 วัน ต้องไม่มีเสียงบ่น"""
    assert red_streak_census.problems({WATCHED: 7}, {WATCHED: 14.6}) == []


def test_a_promise_reality_cannot_keep_is_red():
    """สัญญาว่าเห็นภายใน 1 วัน แต่ความแดงยืนอยู่ 3 วัน = สัญญาเกินกว่าที่ทำได้"""
    found = red_streak_census.problems({WATCHED: 1}, {WATCHED: 72.0})

    assert found, "คำสัญญาที่ทำไม่ได้ต้องแดง"
    assert "เลิกสัญญาเกินจริง" in found[0]


def test_workflows_that_also_block_are_left_out_of_the_comparison():
    """`ci.yml` มี job ที่บล็อกปนอยู่ — ผลของ run เป็นของทั้งไฟล์ จึงวัดตัวที่ถูกเฝ้าไม่ได้

    เขียวที่ไม่ได้แปลว่าอะไร แย่กว่าไม่วัด
    """
    promised = red_streak_census.promised_days()

    assert ".github/workflows/ci.yml" not in promised
    assert ".github/workflows/scorecard.yml" in promised, "ไฟล์ที่ทุก job ถูกเฝ้าต้องถูกวัด"


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
    """นับจากทะเบียนจริงใน `tests/test_declared_prohibitions.py` ไม่ใช่จากเอกสาร"""
    assert check_ratchets.enforced_prohibitions() >= 8


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
    """อ่านรูปที่ `pip-audit --format=json` คืนมาจริง ไม่ใช่รูปที่เราคิดเอง"""
    found = audit_plugin_deps.advisories([REPORT, {"dependencies": []}])

    assert found == {"GHSA-aaaa": "cryptography"}


def test_the_register_on_disk_is_readable():
    """ทะเบียนจริงต้องย่อยได้ — ปกติมันควรว่าง เพราะคำตอบที่เร็วที่สุดคือถอด"""
    assert audit_plugin_deps.accepted_advisories() == set()


# ------------- อ่านว่ามีอะไรถูกถอดไปบ้าง (audit r16 · ข้อ 3)
#
# บันทึกมีครบใน git อยู่แล้ว · ที่ไม่มีคือใครสักคนที่อ่านมัน — และปัญหาที่แท้จริง
# คือ **แยกไม่ออกว่าบรรทัดที่หายไปคือ "ถูกถอด" หรือ "ถูกเขียนใหม่"** ต้องเปิดอ่าน
# ทีละ diff ซึ่งไม่มีใครทำ


RENAMED_IN_ONE_COMMIT = """abc1234\u241frefactor: เปลี่ยนชื่อ gate
-  - id: old-name
+  - id: new-name
"""

EDITED_ROW = """def5678\u241fdocs: แก้ถ้อยคำของแถวเดิม
-| ทบทวนทะเบียนข้อยกเว้นทุกแฟ้ม | 6 เดือน |
+| ทบทวนทะเบียนข้อยกเว้นทุกแฟ้ม (รวม pins) | 6 เดือน |
"""

REALLY_REMOVED = """9876fed\u241fchore: ถอดแถวที่ไม่ต้องทำแล้ว
-| ทบทวน alert ของ CodeQL ที่ถูก dismiss ไว้ | 6 เดือน |
"""


def _entries(monkeypatch, raw, pattern):
    monkeypatch.setattr(removals_census, "_git", lambda *_args: raw)
    return removals_census.removed_entries("x", pattern, "30.days")


def test_a_rename_is_not_a_removal(monkeypatch):
    """ลบ+เพิ่มใน commit เดียว = เปลี่ยนชื่อ · gate สองตัวที่หายไปตลอดอายุ repo เป็นแบบนี้ทั้งคู่"""
    gone, edits = _entries(monkeypatch, RENAMED_IN_ONE_COMMIT, removals_census.WATCHED["gate"][1])

    assert gone == [], f"การเปลี่ยนชื่อไม่ใช่การถอด: {gone}"
    assert edits == 1


def test_an_edited_row_is_not_a_removal(monkeypatch):
    """แถวที่ถูกแก้ถ้อยคำหน้าตาเหมือนการถอดทุกประการใน `git log -p`"""
    pattern = removals_census.WATCHED["แถวตรวจตามรอบ"][1]
    gone, edits = _entries(monkeypatch, EDITED_ROW, pattern)

    assert gone == [], f"การแก้ถ้อยคำไม่ใช่การถอด: {gone}"
    assert edits == 1


def test_a_real_removal_is_reported_with_the_commit_that_did_it(monkeypatch):
    """ทิศที่ต้องจับได้ — และต้องมาพร้อมหัว commit เพราะเหตุผลอยู่ตรงนั้น"""
    pattern = removals_census.WATCHED["แถวตรวจตามรอบ"][1]
    gone, edits = _entries(monkeypatch, REALLY_REMOVED, pattern)

    assert len(gone) == 1, f"ของที่ถูกถอดจริงต้องถูกรายงาน: {gone}"
    commit, subject, item = gone[0]
    assert commit == "9876fed"
    assert "ถอดแถว" in subject, "ต้องพ่วงหัว commit มาด้วย — เหตุผลของการถอดอยู่ตรงนั้น"
    assert "CodeQL" in item
    assert edits == 0


def test_the_report_prints_the_pile_it_chose_not_to_count(monkeypatch):
    """ของที่ถูกตัดออกเงียบ ๆ คือของที่ไม่มีใครทบทวน — ตัวเลขการตีความต้องอยู่ในหน้า"""
    monkeypatch.setattr(removals_census, "_git", lambda *_args: EDITED_ROW)

    text = removals_census.report("30.days")

    assert "การแก้ข้อความ" in text
    assert "ไม่นับเป็นการถอด" in text


# ------------- ตัวตัดสินทุกตัวต้องอยู่ในรายการนี้ (audit r17 · ข้อ 3)
#
# gate `checkers-proven-two-way` (จาก r4) บังคับว่าไฟล์นี้ต้องมีเทสต์ planted
# violation ให้ทุกตัว**ที่อยู่ในนั้น** — แต่ไม่มีอะไรบังคับว่าตัวตัดสินตัวใหม่ต้อง
# เข้ามาอยู่ · ผลคือ `lint_commits.py` ซึ่ง **บล็อกทุก commit (hook `commit-msg`)
# และทุก PR (job `commit-lint`)** อยู่นอกรายการมาตลอด โดยมี coverage 0%
#
# รายการที่ไม่มีการตรวจสมาชิก คือรายการที่ครบเฉพาะวันที่มีคนนึกได้


CLEAN_TITLES = [
    "feat(auth): เพิ่มปัจจัยที่สอง",
    "fix: แก้ตัวกรองวันที่ที่ย่อยไม่ได้",
    "docs(adr): บันทึกคำตัดสินเรื่อง license",
    "refactor(gates)!: ยกชั้นของ gate ใหม่ทั้งชุด",
]

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


@pytest.mark.parametrize("title", CLEAN_TITLES)
def test_a_well_formed_subject_is_not_punished(title):
    """ทิศ "ผ่านเมื่อควรผ่าน" — ตัวตัดสินที่จับของถูกด้วย คือตัวที่คนจะปิดเสียง"""
    assert lint_commits.check_title(title) == [], f"หัวที่ถูกต้องถูกจับ: {title!r}"


@pytest.mark.parametrize(("title", "why"), DIRTY_TITLES)
def test_a_broken_subject_is_caught(title, why):
    """ทิศ "พังเมื่อควรพัง" — ฝังความผิดทีละแบบแล้วต้องจับได้"""
    assert lint_commits.check_title(title), f"ไม่จับ: {why} ({title!r})"


def test_the_length_limit_is_measured_in_characters_not_bytes():
    """หัวเรื่องภาษาไทยยาว 3 ไบต์ต่อตัว — นับไบต์เมื่อไหร่ commit ปกติจะถูกปฏิเสธ

    เป็นกับดักที่ repo นี้เสี่ยงที่สุดเพราะ commit ทุกใบเป็นภาษาไทย
    """
    thai = "feat: " + "ก" * 60  # 66 ตัวอักษร · 186 ไบต์

    assert len(thai) <= lint_commits.MAX_TITLE
    assert lint_commits.check_title(thai) == [], "นับเป็นไบต์แทนตัวอักษร"


# ตัวตัดสินที่พิสูจน์ไว้ที่อื่นแล้ว — **ต้องบอกว่าที่ไหน และด้วยวิธีอะไร** ·
# ตรวจสองทิศเหมือนทะเบียนข้อยกเว้นทุกใบ คือไฟล์ที่อ้างต้องมีจริง
# และต้องเอ่ยถึงสคริปต์นั้นจริง
PROVEN_ELSEWHERE = {
    "run_gates": (
        "tests/test_harness.py",
        (
            "ยิงผ่าน subprocess พร้อม fixture ที่พังจริงและที่สะอาดจริง — เหมือนที่ "
            "loop ของ agent ใช้ ซึ่งเป็นรูปที่ import แล้วเรียกฟังก์ชันพิสูจน์ไม่ได้"
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
    เรียกฟังก์ชัน (`tests/test_harness.py` · `tests/test_preflight.py` ·
    `tests/test_measure_generated.py` ทำแบบนั้นทั้งหมด) · ถ้าตัววัดไม่นับลูก
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


def test_a_stale_version_in_the_about_box_is_caught():
    """ทิศ "แดงเมื่อควรแดง" — คำโฆษณาที่ค้างรุ่นเก่าต้องถูกจับ"""
    stale = audit_posture.description_problems("… v1.6.0 (AGPL-3.0): 105 machine-checked gates …")

    assert stale, "คำโฆษณาที่บอกรุ่นเก่ากลับผ่าน"


def test_an_about_box_that_names_the_current_version_passes():
    """ทิศ "ผ่านเมื่อควรผ่าน" — ต้องอ่าน `__version__` จริง ไม่ใช่เลขที่ฝังไว้

    อ่านเลขรุ่นจาก *ไฟล์* ไม่ใช่ `import app` — ไฟล์นี้เป็นเทสต์ชั้นกติกาที่
    job `bare`/`dialect` ตัดออก (audit รอบ 18) การ import แอปจะทำให้มันหลุด
    ออกจากกลุ่มนั้นทันที และด่านของรอบ 18 ก็จับได้จริงตอนเขียนเทสต์นี้
    """
    source = (pathlib.Path(__file__).resolve().parent.parent / "app" / "__init__.py").read_text(
        encoding="utf-8"
    )
    current = re.search(r'__version__ = "([^"]+)"', source).group(1)

    assert audit_posture.description_problems(f"… v{current} (AGPL-3.0) …") == []


def test_no_answer_from_the_api_is_not_treated_as_a_failure():
    """`None` = ไม่ได้ถามหรือถามไม่ได้ — คนละเรื่องกับ "ตอบแล้วผิด"

    หลักเดียวกับที่ `--input` ของสคริปต์นี้ทำให้รันโดยไม่ต่อเน็ตได้
    """
    assert audit_posture.description_problems(None) == []


def test_every_merge_setting_declares_a_value_and_a_reason():
    """**ทะเบียนที่บอกแค่ว่า "อ่านไม่ได้" คือทะเบียนที่ไม่มีเจ้าของ** (5-Why 2026-08-21)

    `delete_branch_on_merge` หลุดจากแผนที่ไปทั้งใบเพราะมันอยู่ในคลาสที่ token
    สิทธิ์ต่ำสุดอ่านไม่ได้ — ของเดิมบันทึกว่าเครื่องมองไม่เห็นอะไร แต่ไม่มีที่ไหน
    บันทึกว่าค่าที่ควรเป็นคืออะไร · ผลคือกติกาถูกบังคับด้วยความจำ แล้ว branch
    ที่ merge แล้วกองค้าง 64 ใบโดยไม่มีอะไรทัก
    """
    assert audit_posture.MERGE_SETTINGS, "ทะเบียน merge setting ว่าง"

    for flag, declared in audit_posture.MERGE_SETTINGS.items():
        want, why = declared
        assert isinstance(want, bool), f"{flag} ไม่ได้ประกาศค่าที่ควรเป็น"
        assert len(why) > 20, f"{flag} มีค่าแต่ไม่มีเหตุผลที่อ่านแล้วตัดสินได้: {why!r}"


def test_the_note_for_an_unreadable_setting_says_what_it_should_be():
    """รายงานที่บอกแค่ "อ่านไม่ได้" ทำให้คนอ่านไม่รู้ว่าต้องไปตั้งค่าอะไร"""
    invisible = {**HEALTHY, "delete_branch_on_merge": None}

    notes = audit_posture.unreadable(invisible)

    assert any("delete_branch_on_merge" in note for note in notes), "ไม่ได้รายงานว่ามองไม่เห็น"
    assert any("True" in note for note in notes), "รายงานแล้วแต่ไม่ได้บอกว่าค่าที่ควรเป็นคืออะไร"


def test_a_readable_merge_setting_that_drifted_is_a_problem_not_a_note():
    """อ่านได้แล้วผิด = ปัญหา · อ่านไม่ได้ = หมายเหตุ — สองอย่างนี้ห้ามสลับกัน"""
    drifted = {**HEALTHY, "delete_branch_on_merge": False}

    assert audit_posture.compare(drifted, ON_PR, 2, None), "อ่านได้แล้วผิด ต้องเป็นปัญหา"
    assert audit_posture.unreadable(drifted) == [], "อ่านได้แล้วต้องไม่มีหมายเหตุค้าง"


# ------------------------------- เพดานของการปิดเครื่องตรวจรายบรรทัด (audit r21 ข้อ 2)
#
# ทุก ratchet ในไฟล์นี้เดินขึ้น · กองนี้เดินลง และนั่นคือเหตุผลที่มันต้องมีตรรกะ
# ของตัวเอง: "ของจริงต่ำกว่าที่ประกาศ" เป็น**ข่าวดี**ที่ต้องบันทึก ไม่ใช่การถอย


def test_a_new_suppression_is_a_decision_not_a_side_effect():
    """เกินเพดาน = แดง พร้อมบอกว่าต้องไปขยับที่ไหน"""
    found = check_ratchets._ceiling_problems("suppressions", 99, 100)

    assert found, "เพิ่มข้อยกเว้นแล้วต้องแดง"
    assert "ceilings" in found[0], "แดงแล้วแต่ไม่ได้บอกว่าต้องไปแก้ที่ไหน"


def test_a_freed_slot_must_be_recorded_not_left_open():
    """ลดลงแล้วไม่ลดเพดานตาม = ที่ว่างถูกถมกลับเงียบ ๆ (ทิศที่คนลืมเสมอ)"""
    found = check_ratchets._ceiling_problems("suppressions", 99, 90)

    assert found, "ของจริงลดลงแล้วเพดานต้องตามลงมา"
    assert "90" in found[0], "ต้องบอกตัวเลขใหม่ที่ควรเป็น"


def test_a_ceiling_that_matches_reality_is_silent():
    """ทิศ "ผ่านเมื่อควรผ่าน" — ตัวตรวจที่ดังกับของปกติจะถูกปิดเสียง"""
    assert check_ratchets._ceiling_problems("suppressions", 99, 99) == []


def test_the_counter_reads_real_files():
    """อ่านของจริง ไม่ใช่ค่าคงที่"""
    counts = check_ratchets.suppression_counts()

    assert counts["suppressions"] > 0, "นับไม่เจอเลย — ตัวอ่านพังหรือขอบเขตผิด"
    assert counts["suppressions_without_reason"] <= counts["suppressions"]


# ตัวอย่างต้องประกอบขึ้นตอนรัน **ห้ามเขียนเป็นข้อความตรง ๆ** — ไฟล์นี้อยู่ในขอบเขต
# ที่ตัวนับสแกน ตัวอย่างที่เขียนตรง ๆ จะถูกนับเป็นข้อยกเว้นจริงแล้วดันเพดานขึ้น
# (เกิดขึ้นจริงตอนเขียน: ตัวอย่างใน docstring ของตัวนับเองทำให้เพดานเด้งเป็น 100)
HASH = "#"


@pytest.mark.parametrize(
    ("line", "is_suppression", "has_reason"),
    [
        (f"x = 1  {HASH} noqa: F401", True, False),
        (f"x = 1  {HASH} noqa: F401 นำเข้าเพื่อผูก event ไม่ได้ใช้ชื่อ", True, True),
        (f"x = 1  {HASH} type: ignore[arg-type]", True, False),
        (f"x = 1  {HASH} type: ignore[arg-type] ไลบรารีไม่มี stub", True, True),
        (f"x = 1  {HASH} คอมเมนต์ธรรมดา", False, False),
        ("x = 1", False, False),
    ],
)
def test_the_reason_is_judged_apart_from_the_rule_code(line, is_suppression, has_reason):
    """ "ปิดกฎไหน" กับ "ทำไม" เป็นคนละคำถาม — ยอดรวมพิสูจน์ข้อนี้ไม่ได้"""
    assert check_ratchets.classify_suppression(line) == (is_suppression, has_reason)


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


def test_closing_an_invitation_that_is_still_open_is_a_problem():
    found = check_issue_handoff.problems(TAKEN, {171: GOOD_FIRST}, body="ทำเอง")

    assert found, "ปิด issue ที่ยังติดป้ายอยู่ ต้องแดง"
    assert "171" in found[0]


def test_an_issue_without_the_label_is_not_a_problem():
    """ป้ายอื่นไม่เกี่ยว — ด่านที่ดังกับทุก PR จะถูกปิดเสียงภายในสัปดาห์เดียว"""
    assert check_issue_handoff.problems(TAKEN, {171: {"bug"}}, body="") == []


def test_a_pr_that_closes_nothing_is_not_a_problem():
    assert check_issue_handoff.problems([], {}, body="") == []


def test_a_declared_takeback_passes():
    """ไม่ได้ห้ามผู้ดูแลทำเอง — ห้ามทำเงียบ ๆ"""
    body = "good-first-issue-taken-back: ต้องใช้ในงาน audit วันนี้ รอไม่ได้"

    assert check_issue_handoff.problems(TAKEN, {171: GOOD_FIRST}, body=body) == []


def test_a_takeback_without_a_reason_does_not_pass():
    """คำสั่งเปล่า ๆ ไม่ใช่การประกาศ — หลักเดียวกับทุกทะเบียนข้อยกเว้นในโปรเจกต์นี้"""
    found = check_issue_handoff.problems(
        TAKEN, {171: GOOD_FIRST}, body="good-first-issue-taken-back:"
    )

    assert found, "ประกาศโดยไม่มีเหตุผล ต้องไม่ผ่าน"


def test_the_message_names_both_ways_out():
    """ข้อความตอนแดงต้องบอกทางออก **ทั้งสองทาง** ไม่ใช่แค่บอกว่าผิด

    รุ่นแรกของเทสต์นี้หาแค่คำว่า "ปลดป้าย" ในข้อความทั้งก้อน — ซึ่งโผล่ในประโยค
    ที่บอก*อาการ*อยู่แล้ว มันจึงยังเขียวตอนที่ถอดบรรทัดทางออกข้อ 1 ออกไปทั้งบรรทัด
    (จับได้ตอน mutation) · ตอนนี้จึงนับ *บรรทัด* ที่เป็นทางออกจริง
    """
    message = check_issue_handoff.report(["#171 ยังติดป้ายอยู่"])
    ways = [line.strip() for line in message.splitlines() if line.strip()[:2] in {"1.", "2."}]

    assert len(ways) == 2, f"ต้องมีทางออกสองทาง ได้ {ways}"
    assert "ปลดป้าย" in ways[0], "ทางที่หนึ่งต้องคือการปลดป้าย"
    assert "good-first-issue-taken-back:" in message, "ไม่ได้บอกรูปของการประกาศ"


# ตัวที่คุยกับ GitHub — ทดสอบโดยปลอม `_gh` ไม่ใช่โดยต่อเน็ต · **เกณฑ์ coverage
# ของ `scripts/` จับได้เองว่าครึ่งนี้ไม่มีเทสต์** ตอนที่ด่านนี้ถูกเพิ่มเข้ามา
# (พื้นตก 62.14 → 61.80) ซึ่งเป็นเหตุผลที่เกณฑ์นั้นมีอยู่


@pytest.fixture
def fake_gh(monkeypatch):
    """แทน `gh` ด้วยตารางคำตอบ — คืน list ของ argument ที่ถูกเรียกจริงด้วย"""
    calls = []

    def answer(*args):
        calls.append(args)
        if args[0] == "pr":
            return json.dumps({"closingIssuesReferences": answer.closing})
        return json.dumps({"labels": [{"name": name} for name in answer.labels]})

    answer.closing = []
    answer.labels = []
    monkeypatch.setattr(check_issue_handoff, "_gh", answer)
    return answer, calls


def test_closing_issues_reads_what_github_would_actually_close(fake_gh):
    """อ่านจาก `closingIssuesReferences` ไม่ใช่จากการ grep คำว่า Closes ในเนื้อ PR"""
    answer, calls = fake_gh
    answer.closing = [{"number": 171, "title": "x"}]

    assert check_issue_handoff.closing_issues("9") == [{"number": 171, "title": "x"}]
    assert "closingIssuesReferences" in calls[0]


def test_labels_of_returns_the_names(fake_gh):
    answer, _calls = fake_gh
    answer.labels = ["good first issue", "bug"]

    assert check_issue_handoff.labels_of(171) == {"good first issue", "bug"}


def test_without_a_pull_request_number_the_check_is_silent(capsys):
    """ด่านนี้มีความหมายเฉพาะบน pull_request — บน push ต้องผ่านเงียบ ๆ"""
    assert check_issue_handoff.main(["--pr", "", "--body", ""]) == 0


def test_a_pull_request_closing_nothing_passes(fake_gh):
    assert check_issue_handoff.main(["--pr", "9", "--body", ""]) == 0


def test_closing_a_labelled_issue_fails_the_build(fake_gh):
    answer, _calls = fake_gh
    answer.closing = [{"number": 171, "title": "data-doctor check"}]
    answer.labels = ["good first issue"]

    assert check_issue_handoff.main(["--pr", "9", "--body", "ทำเอง"]) == 1


def test_a_declared_takeback_lets_the_build_through(fake_gh):
    answer, _calls = fake_gh
    answer.closing = [{"number": 171, "title": "data-doctor check"}]
    answer.labels = ["good first issue"]
    body = "good-first-issue-taken-back: จำเป็นต้องใช้ผลในวันเดียวกัน"

    assert check_issue_handoff.main(["--pr", "9", "--body", body]) == 0


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


def test_the_surface_is_signatures_not_bodies():
    """สิ่งที่ผู้เรียกต้องรู้คือ signature — body คือรายละเอียดที่ยังไม่ต้องการ"""
    found = [item.signature for item in skeleton.symbols(SAMPLE)]

    assert "def open_one(name: str, count: int=3) -> bool" in found
    assert "class Thing(Base)" in found
    assert "async def fetch(url: str) -> str" in found
    assert not any("helper" in line for line in found), "body หลุดขึ้นมาบนพื้นผิว"


def test_private_names_are_off_the_surface_unless_asked():
    """`_hidden` ไม่ใช่สิ่งที่ผู้เรียกจากข้างนอกเรียกได้ — แต่บางครั้งก็อยากเห็น"""
    public = [item.signature for item in skeleton.symbols(SAMPLE)]
    everything = [item.signature for item in skeleton.symbols(SAMPLE, private=True)]

    assert not any("_hidden" in line for line in public)
    assert any("_hidden" in line for line in everything)
    assert any("_inner" in line for line in everything), "method ส่วนตัวก็ต้องโผล่ด้วย"


def test_decorators_are_part_of_the_surface():
    """`@property` เปลี่ยนวิธีเรียกของผู้เรียก จึงเป็นพื้นผิว ไม่ใช่รายละเอียด"""
    found = [item.signature for item in skeleton.symbols(SAMPLE)]

    assert "@property" in found


def test_methods_sit_one_level_under_their_class():
    """ความลึกคือข้อมูล — `label` เป็นของ `Thing` ไม่ใช่ของโมดูล"""
    found = {item.signature: item.depth for item in skeleton.symbols(SAMPLE)}

    assert found["class Thing(Base)"] == 0
    assert found["def label(self) -> str"] == 1


def test_the_summary_is_the_first_line_only():
    """ที่เหลือของ docstring คือรายละเอียดที่คนถาม *จะเรียกอะไร* ยังไม่ต้องการ"""
    found = {item.signature: item.summary for item in skeleton.symbols(SAMPLE)}

    assert found["def open_one(name: str, count: int=3) -> bool"] == "ทำอะไรสักอย่าง"


def test_the_report_says_how_much_it_saved(tmp_path):
    """ตัวเลขท้ายไม่ใช่ของแถม — มันคือเหตุผลที่เครื่องมือนี้มีอยู่"""
    path = tmp_path / "sample.py"
    text = skeleton.render(path, SAMPLE)

    assert str(path) in text
    assert "โมดูลตัวอย่าง — บรรทัดแรกเท่านั้นที่ถูกหยิบ" in text
    assert "ส่วนนี้ไม่ควรโผล่บนพื้นผิว" not in text, "docstring ทั้งก้อนหลุดขึ้นมา"
    assert "สัญลักษณ์" in text
    assert "บรรทัด" in text


def test_the_line_count_matches_what_is_printed(tmp_path):
    """เลขที่รายงานต้องเท่ากับบรรทัดที่พิมพ์จริง ไม่งั้นมันเป็นเลขโฆษณา"""
    text = skeleton.render(tmp_path / "sample.py", SAMPLE)
    claimed = int(re.search(r"· (\d+) จาก", text).group(1))

    assert claimed == len(text.splitlines())


def test_a_file_with_no_surface_says_so(tmp_path):
    """ไฟล์ที่มีแต่ค่าคงที่ ต้องบอกว่าไม่มีอะไร ไม่ใช่พิมพ์หัวเปล่า ๆ"""
    text = skeleton.render(tmp_path / "empty.py", "VALUE = 1\n")

    assert "ไม่มีสัญลักษณ์บนพื้นผิว" in text


def test_the_command_reads_a_real_file(tmp_path, capsys):
    """เส้นทางที่คนใช้จริง — รับ path แล้วพิมพ์ออก stdout"""
    path = tmp_path / "sample.py"
    path.write_text(SAMPLE, encoding="utf-8")

    assert skeleton.main([str(path)]) == 0
    assert "def open_one" in capsys.readouterr().out


def test_a_directory_is_read_in_a_stable_order(tmp_path, capsys):
    """ผลลัพธ์ต้องซ้ำได้ ไม่งั้นเอาไป diff อะไรไม่ได้เลย"""
    for name in ("b.py", "a.py"):
        (tmp_path / name).write_text(SAMPLE, encoding="utf-8")

    assert skeleton.main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert out.index("a.py") < out.index("b.py")


def test_a_file_that_cannot_be_parsed_fails_loudly(tmp_path, capsys):
    """แยกวิเคราะห์ไม่ได้ = บอกว่าไฟล์ไหน ไม่ใช่พิมพ์ traceback ใส่หน้าคนใช้"""
    path = tmp_path / "broken.py"
    path.write_text("def (", encoding="utf-8")

    assert skeleton.main([str(path)]) == 1
    assert "แยกวิเคราะห์ไม่ได้" in capsys.readouterr().err


def test_a_missing_file_is_reported_not_crashed(tmp_path, capsys):
    assert skeleton.main([str(tmp_path / "ไม่มีอยู่.py")]) == 1
    assert "อ่าน" in capsys.readouterr().err


def test_an_empty_directory_is_reported(tmp_path, capsys):
    assert skeleton.main([str(tmp_path)]) == 1
    assert "ไม่มีไฟล์" in capsys.readouterr().err
