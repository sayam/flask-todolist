"""`SECURITY.md` ต้องไม่สัญญาคนละอย่างกับที่นโยบายภายในถืออยู่

ไฟล์นี้เป็นคำสัญญาที่ให้กับคนนอก ส่วน `docs/SECURITY-CADENCE.md` เป็นกรอบเวลา
ที่โปรเจกต์ถือกับตัวเอง — **เลขชุดเดียวกันอยู่สามที่** (ตารางอังกฤษใน
`SECURITY.md` · ประโยคไทยในไฟล์เดียวกัน · ตารางใน cadence) วันที่มีคนขยับที่หนึ่ง
แล้วลืมอีกสอง โปรเจกต์จะสัญญากับคนภายนอกคนละแบบกับที่ทำจริง โดยไม่มีอะไรส่งเสียง

อีกข้อที่คุมคือ **ห้ามมีอีเมลในไฟล์นี้** — เป็นการตัดสินใจตอนเปิด public ว่า
ช่องทางเดียวคือ private vulnerability reporting ของ GitHub เพื่อไม่ให้ที่อยู่จริง
ไปนอนใน repo สาธารณะให้ crawler เก็บ · เผลอเติมกลับมาเมื่อไหร่ต้องแดง
"""

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
POLICY = ROOT / "SECURITY.md"
CADENCE = ROOT / "docs" / "SECURITY-CADENCE.md"

SEVERITIES = ("critical", "high", "medium")

# `| critical | **7 วัน** |` และ `| Critical | **7 days** |`
TABLE_ROW = re.compile(
    r"^\|\s*(critical|high|medium)\s*\|\s*\*\*(\d+)\s*(?:days?|วัน)\*\*\s*\|",
    re.IGNORECASE | re.MULTILINE,
)

# ประโยคไทยในนโยบาย: `(critical 7 วัน · high 30 · medium 90)`
THAI_SENTENCE = re.compile(r"critical\s+(\d+)\s*วัน\s*·\s*high\s+(\d+)\s*·\s*medium\s+(\d+)")

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _deadlines(path: pathlib.Path) -> dict[str, int]:
    found = {
        match.group(1).lower(): int(match.group(2))
        for match in TABLE_ROW.finditer(path.read_text(encoding="utf-8"))
    }
    assert set(found) == set(SEVERITIES), (
        f"อ่านตารางกรอบเวลาใน {path.name} ไม่ครบ — ได้ {sorted(found)} "
        f"ต้องการ {sorted(SEVERITIES)} · รูปแบบตารางเปลี่ยนไปแล้วหรือเปล่า"
    )
    return found


@pytest.fixture(scope="module")
def policy_text():
    assert POLICY.is_file(), "ไม่มี SECURITY.md ที่รากของ repo — คนนอกไม่รู้จะแจ้งช่องโหว่ทางไหน"
    return POLICY.read_text(encoding="utf-8")


def test_the_public_promise_matches_the_internal_cadence():
    promised, internal = _deadlines(POLICY), _deadlines(CADENCE)
    assert promised == internal, (
        f"กรอบเวลาที่สัญญากับคนนอก {promised} ไม่ตรงกับที่ถือไว้จริง {internal}\n"
        "ขยับที่หนึ่งต้องขยับทั้งสองที่ ไม่งั้นคำสัญญากับความจริงจะแยกทางกันเงียบ ๆ"
    )


def test_the_thai_half_promises_the_same_numbers_as_the_english_half(policy_text):
    """แปลไม่ครบคือทางที่เลขแตกกันได้ง่ายที่สุด เพราะสองครึ่งไม่ได้อยู่ติดกัน"""
    match = THAI_SENTENCE.search(policy_text)
    assert match, "หาประโยคกรอบเวลาฉบับภาษาไทยใน SECURITY.md ไม่เจอ"

    thai = dict(zip(SEVERITIES, (int(group) for group in match.groups()), strict=True))
    assert thai == _deadlines(POLICY), (
        f"ครึ่งภาษาไทยบอก {thai} แต่ตารางภาษาอังกฤษบอก {_deadlines(POLICY)}"
    )


def test_the_policy_carries_no_email_address(policy_text):
    """ช่องทางเดียวคือ private vulnerability reporting — ที่อยู่จริงห้ามอยู่ในไฟล์สาธารณะ"""
    found = EMAIL.findall(policy_text)
    assert not found, (
        f"เจออีเมลใน SECURITY.md: {found}\n"
        "ตัดสินใจไว้ว่าช่องทางเดียวคือ private vulnerability reporting ของ GitHub"
    )


def test_the_policy_points_at_a_reporting_channel_that_exists(policy_text):
    """ลิงก์ต้องชี้ไปที่ repo นี้จริง ไม่ใช่ที่ก๊อปมาจากตัวอย่าง"""
    assert "security/advisories/new" in policy_text, (
        "ไม่มีลิงก์ไปหน้าแจ้งช่องโหว่แบบส่วนตัว — นโยบายที่ไม่บอกทางส่งคือนโยบายที่ไม่มีใครใช้ได้"
    )
    assert policy_text.count("github.com/sayam/flask-todolist") >= 1, "ลิงก์แจ้งช่องโหว่ไม่ได้ชี้มาที่ repo นี้"


def test_the_out_of_scope_list_still_matches_decisions_we_actually_made(policy_text):
    """ข้อยกเว้นทุกข้อต้องผูกกับการตัดสินใจที่มีเอกสาร ไม่ใช่ข้ออ้างลอย ๆ

    ที่นี่ตรวจแค่ว่า ADR ที่ยกมาอ้างมีไฟล์อยู่จริง — เอกสารที่ชี้ไปหาเหตุผล
    ที่ไม่มีอยู่ แย่กว่าไม่ชี้ไปไหนเลย (หลักเดียวกับ `tests/test_asvs.py`)
    """
    referenced = set(re.findall(r"docs/(adr/[\w./-]+\.md|[\w./-]+\.md)", policy_text))
    assert referenced, "SECURITY.md ไม่ได้อ้างเอกสารประกอบสักฉบับ"

    missing = sorted(name for name in referenced if not (ROOT / "docs" / name).is_file())
    assert not missing, f"SECURITY.md ชี้ไปหาเอกสารที่ไม่มีอยู่: {missing}"


# --------------------------------------------------------------------------
# คำสั่ง verify ที่คนนอกคัดลอกไปรัน — สำเนาที่สองของข้อเท็จจริงเดียวกัน
# (audit governance รอบ 4 ข้อ 2) · workflow เป็นแหล่งจริง เอกสารเป็นสำเนา
# วันที่เปลี่ยนชื่อไฟล์ workflow หรือย้าย repo แล้วลืมแก้เอกสาร ผู้ใช้จะได้
# "verify ไม่ผ่าน" ซึ่งอ่านได้ว่า artifact ปลอม — ความเสียหายอยู่ที่ความเชื่อถือ
# ไม่ใช่ที่ตัวบั๊ก (คลาสเดียวกับเลข ADR/job count ที่ repo ไล่แก้มาแล้ว)
# --------------------------------------------------------------------------

RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
OIDC_ISSUER = "https://token.actions.githubusercontent.com"


@pytest.fixture(scope="module")
def release_workflow_text() -> str:
    assert RELEASE_WORKFLOW.is_file(), "ไม่มี .github/workflows/release.yml — ใครถอดการเซ็นออก?"
    return RELEASE_WORKFLOW.read_text(encoding="utf-8")


def test_the_documented_verify_command_names_the_workflow_that_actually_signs(
    policy_text, release_workflow_text
):
    """regexp ในเอกสารต้องชี้ไฟล์ workflow ตัวที่เซ็นจริง ไม่ใช่ชื่อที่เคยใช้"""
    assert "cosign sign-blob" in release_workflow_text, (
        "workflow ไม่ได้เซ็นอะไรแล้ว — เอกสารที่ยังสอนวิธี verify คือคำสัญญาที่ว่างเปล่า"
    )

    signer = RELEASE_WORKFLOW.name  # แหล่งจริงคือชื่อไฟล์ ไม่ใช่สตริงที่พิมพ์ซ้ำ
    assert f"/.github/workflows/{signer}@" in policy_text, (
        f"คำสั่ง verify ใน SECURITY.md ไม่ได้ชี้ {signer} — "
        "เปลี่ยนชื่อ workflow แล้วเอกสารค้าง ผู้ใช้จะ verify ไม่ผ่านและคิดว่าไฟล์ปลอม"
    )


def test_both_copies_of_the_verify_command_use_the_same_issuer(policy_text, release_workflow_text):
    """issuer ที่ต่างกันคือการ verify คนละสายความเชื่อถือ โดยที่ทั้งคู่ดู 'ถูก'"""
    assert OIDC_ISSUER in release_workflow_text, "workflow ไม่ได้ผูกกับ issuer ของ GitHub Actions"
    assert OIDC_ISSUER in policy_text, "SECURITY.md ต้องบอก issuer เดียวกับที่ workflow ใช้ verify"


def test_the_documented_commands_reference_artifacts_the_workflow_really_uploads(
    policy_text, release_workflow_text
):
    """ชื่อไฟล์ในตัวอย่างต้องเป็นของที่ workflow แนบจริง — ตัวอย่างที่ copy แล้วไม่เจอไฟล์ = เอกสารตาย"""
    assert "sbom-core.json" in release_workflow_text or "sbom-" in release_workflow_text
    assert "sbom-core.json" in policy_text, "ตัวอย่างต้องใช้ชื่อ asset ที่มีจริงในหน้า release"
    assert "sbom-core.json.sigstore.json" in policy_text, (
        "ตัวอย่างต้องอ้าง bundle ลายเซ็นที่ workflow เขียนออกมา (`<ไฟล์>.sigstore.json`)"
    )
    assert "gh attestation verify" in policy_text, (
        "provenance เป็นชั้นที่สองของการ verify — เอกสารต้องสอนทั้งสองชั้น (ADR 0058)"
    )
