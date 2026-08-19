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

import json
import pathlib
import typing

import pytest

from scripts import (
    audit_image,
    audit_pins,
    audit_plugin_deps,
    audit_posture,
    check_ratchets,
    check_semgrep,
    red_streak_census,
    removals_census,
    rerun_census,
    schedule_census,
    whats_pending,
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
