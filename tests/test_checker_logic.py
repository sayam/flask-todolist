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

from scripts import audit_image, audit_pins, check_semgrep


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
