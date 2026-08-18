"""แฟ้มที่ **ปิดเสียงด่าน** ต้องมีเหตุผลทุกบรรทัด และต้องมีคนตรวจ (audit r9 · ข้อ 2)

`pins/accepted-advisories.txt` กับ `deploy/accepted-image-advisories.txt` มีเทสต์
สองทิศคุมมาตั้งแต่ต้น — แต่แฟ้มอีกสองใบที่ทำหน้าที่เดียวกัน (ปิดเสียงสิ่งที่
เครื่องมือความปลอดภัยรายงาน) **ไม่มีเทสต์ไฟล์ไหนอ่านเลย** ทั้งที่ CLAUDE.md
ประกาศกฎไว้ทั้งคู่ว่า "ทุกบรรทัดต้องมีเหตุผล" (`.zap/rules.tsv`) และ "ข้อยกเว้น
ต้องมีเหตุผลกำกับที่นี่ที่เดียว" (`.hadolint.yaml`)

**ความเสี่ยงไม่ใช่เก้าบรรทัดที่มีอยู่วันนี้ — ทุกบรรทัดมีเหตุผลครบ** ความเสี่ยง
คือบรรทัดที่สิบ ที่ใครสักคนเติมตอนรีบแล้วไม่มีอะไรฟ้อง · กฎที่มีแต่ในเอกสาร
คือกฎที่ครบเฉพาะบนกระดาษ (หลักเดียวกับ `tests/test_route_authz.py` ที่เกิดจาก
รายการยกเว้นซึ่งไม่มีใครตรวจแล้วไม่ครบจริง)

ที่นี่ตรวจสามอย่างที่ตรวจได้โดยไม่ต้องรัน ZAP หรือ hadolint:

1. **รูปแบบและเหตุผล** — ทุกบรรทัดครบสามคอลัมน์ · action เป็นค่าที่รู้จัก ·
   id ไม่ซ้ำ · และ**มีข้อความเหตุผลยาวพอจะตัดสินได้**
2. **ตาข่ายกันถอยหลังไม่หด** — จำนวนกฎที่ตั้งเป็น `FAIL` มีเพดานล่าง การเปลี่ยน
   `FAIL` เป็น `WARN` คือการปิดเสียงที่ diff อ่านผ่านได้ง่ายที่สุด (แก้คำเดียว)
   ถ้าไม่มีเลขคุมไว้ก็ไม่มีอะไรทำให้คนสังเกต
3. **แฟ้มถูกใช้จริง** — `.zap/rules.tsv` ต้องถูกอ้างใน `scripts/dast_scan.sh`
   และ `.hadolint.yaml` ต้องถูกอ้างใน job `lint` **โดยไม่มีการตั้ง
   `failure-threshold`** ซึ่งจะยกเลิกเกณฑ์ "ทุกระดับรวม info" ของ ADR 0055
   เงียบ ๆ — แฟ้มข้อยกเว้นที่ไม่มีใครอ่าน กับด่านที่ถูกผ่อนเกณฑ์ ให้ผลเหมือนกัน
"""

import pathlib

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
ZAP_RULES = ROOT / ".zap" / "rules.tsv"
HADOLINT = ROOT / ".hadolint.yaml"
DAST_SCRIPT = ROOT / "scripts" / "dast_scan.sh"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

ZAP_ACTIONS = frozenset({"FAIL", "WARN", "IGNORE", "OUTOFSCOPE"})

# เหตุผลที่สั้นกว่านี้คือชื่อกฎที่พิมพ์ซ้ำ ไม่ใช่เหตุผล
MIN_REASON = 20

# **ตาข่ายกันถอยหลัง** — ลดได้ต้องมาแก้เลขนี้พร้อมเหตุผลใน PR เดียวกัน
FAIL_FLOOR = 18


@pytest.fixture(scope="module")
def zap_rows() -> list[tuple[str, str, str]]:
    rows = []
    for line in ZAP_RULES.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        rows.append(tuple(cell.strip() for cell in line.split("\t")))
    assert rows, "อ่าน .zap/rules.tsv ไม่ได้เลย — รูปแบบไฟล์เปลี่ยนไปแล้ว"
    return rows


def test_every_zap_rule_is_wellformed_and_carries_a_reason(zap_rows):
    """ทุกบรรทัดต้องบอกได้ว่ากฎไหน ทำอย่างไร และ**ทำไม**"""
    for row in zap_rows:
        assert len(row) == 3, f"บรรทัดนี้ไม่ครบสามคอลัมน์ (id/action/เหตุผล): {row}"
        rule_id, action, reason = row
        assert rule_id.isdigit(), f"id ของกฎต้องเป็นตัวเลขที่ ZAP พิมพ์ออกมา: {rule_id!r}"
        assert action in ZAP_ACTIONS, f"action {action!r} ไม่ใช่ค่าที่ ZAP รู้จัก (กฎ {rule_id})"
        assert len(reason) >= MIN_REASON, (
            f"กฎ {rule_id} ({action}) มีเหตุผลสั้นเกินกว่าจะตัดสินได้: {reason!r}\n"
            "การปิดเสียงที่ไม่มีเหตุผลกำกับ คือการปิดเสียงที่ไม่มีใครรู้ว่าจะเปิดคืนได้เมื่อไหร่"
        )

    ids = [row[0] for row in zap_rows]
    duplicated = sorted({i for i in ids if ids.count(i) > 1})
    assert not duplicated, (
        f"กฎซ้ำใน .zap/rules.tsv: {duplicated} — ZAP อ่านบรรทัดหลังทับบรรทัดแรก "
        "เหตุผลที่เขียนไว้ข้างบนจึงกลายเป็นเหตุผลของสิ่งที่ไม่มีผล"
    )


def test_the_zap_safety_net_does_not_shrink_quietly(zap_rows):
    """เปลี่ยน FAIL เป็น WARN คือการปิดเสียงที่แก้คำเดียวและ diff อ่านผ่านได้ง่ายที่สุด"""
    failing = [row[0] for row in zap_rows if row[1] == "FAIL"]

    assert len(failing) >= FAIL_FLOOR, (
        f"กฎที่ตั้งเป็น FAIL เหลือ {len(failing)} ตัว (เพดานล่าง {FAIL_FLOOR}) — "
        "ถ้าตั้งใจผ่อนจริง ให้ลด FAIL_FLOOR พร้อมเหตุผลใน PR เดียวกัน "
        "ข้อที่ตั้งเป็น FAIL ทั้งหมดผ่านอยู่แล้ว มันเป็นตาข่ายกันถอยหลัง ไม่ใช่ตัวหาของใหม่"
    )


def test_the_zap_rule_file_is_actually_used(zap_rows):
    """แฟ้มข้อยกเว้นที่ไม่มีใครอ่าน คือไฟล์ข้อความ"""
    assert DAST_SCRIPT.is_file(), "ไม่มี scripts/dast_scan.sh"
    assert ".zap/rules.tsv" in DAST_SCRIPT.read_text(encoding="utf-8"), (
        "scripts/dast_scan.sh ไม่ได้ส่ง .zap/rules.tsv ให้ ZAP — กติกาต่อกฎทั้งไฟล์จึงไม่มีผลกับการสแกนจริง"
    )


@pytest.fixture(scope="module")
def hadolint_step() -> dict:
    jobs = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]
    steps = [
        step
        for job in jobs.values()
        for step in job.get("steps", [])
        if step.get("uses", "").startswith("hadolint/hadolint-action@")
    ]
    assert steps, "ไม่เจอ step ของ hadolint ใน ci.yml — ADR 0055 บอกว่ามันต้องรันทุก push"
    return steps[0]


def test_every_hadolint_exception_has_a_reason_written_above_it():
    """`ignored:` ที่ไม่มีคอมเมนต์นำหน้า คือข้อยกเว้นที่ไม่มีใครรู้ว่าจะถอดได้เมื่อไหร่"""
    lines = HADOLINT.read_text(encoding="utf-8").splitlines()
    ignored = [i for i, line in enumerate(lines) if line.lstrip().startswith("- ")]
    assert ignored, "ไม่มีรายการใน .hadolint.yaml เลย — ถ้าถอดข้อยกเว้นหมดแล้วให้ลบเทสต์ข้อนี้ทิ้งด้วย"

    for i in ignored:
        above = [line.strip() for line in lines[:i] if line.strip()]
        previous = above[-1] if above else ""
        why = f"{lines[i].strip()} ไม่มีคอมเมนต์เหตุผลอยู่เหนือมัน — ADR 0055 ให้เหตุผลอยู่ที่นี่ที่เดียว"

        assert previous.startswith("#"), why
        assert len(previous) > MIN_REASON, why


def test_the_hadolint_scope_is_not_loosened_outside_the_exception_file(hadolint_step):
    """ผ่อน `failure-threshold` ทีเดียว = ยกเว้นทั้ง class โดยไม่ต้องเขียนเหตุผลสักบรรทัด"""
    with_ = hadolint_step.get("with", {})

    assert with_.get("config") == ".hadolint.yaml", (
        "step ของ hadolint ไม่ได้ชี้ .hadolint.yaml — ข้อยกเว้นที่เขียนไว้จะไม่มีผล "
        "และของที่ตั้งใจยกเว้นจะกลับมาแดงโดยไม่มีใครเข้าใจว่าทำไม"
    )
    assert "failure-threshold" not in with_, (
        "มีการตั้ง failure-threshold ใน workflow — เกณฑ์ของ ADR 0055 คือ "
        "**ทุกระดับรวม info ต้องเขียว** และการผ่อนต้องเกิดที่ .hadolint.yaml "
        "ทีละข้อพร้อมเหตุผล ไม่ใช่ปิดทั้งระดับด้วยบรรทัดเดียวใน workflow"
    )


# ------------------------------------------- ทะเบียน alert ฝั่งแพลตฟอร์ม (audit r10 · ข้อ 3)
#
# แฟ้มที่สามในตระกูลเดียวกัน ต่างที่ของที่มันปิดเสียงอยู่**ไม่ได้อยู่ในเรโป** —
# มันอยู่บนหน้า Security ของ GitHub ซึ่งเป็นพื้นผิวที่คนนอกอ่านก่อนเพื่อน
# ตอนตั้งแถวนี้: alert เปิดค้าง 4 ใบ (3 ใบ high) นาน 5.6 วัน โดยรอบทบทวนที่มีอยู่
# ครอบเฉพาะใบที่ถูก dismiss ไปแล้ว — ที่ยัง**เปิดอยู่**ไม่มีแถวไหนครอบเลย

ALERT_REGISTER = ROOT / ".github" / "accepted-code-scanning-alerts.txt"
CADENCE_DOC = ROOT / "docs" / "SECURITY-CADENCE.md"


@pytest.fixture(scope="module")
def alert_rows() -> list[tuple[str, str]]:
    rows = []
    for line in ALERT_REGISTER.read_text(encoding="utf-8").splitlines():
        body = line.strip()
        if not body or body.startswith("#"):
            continue
        name, _, why = body.partition("#")
        rows.append((name.strip(), why.strip()))
    assert rows, "อ่านทะเบียน alert ไม่ได้เลย — รูปแบบไฟล์เปลี่ยนไปแล้ว"
    return rows


def test_every_accepted_alert_carries_a_reason(alert_rows):
    """บรรทัดที่ไม่มีเหตุผล คือการยกเว้นที่ไม่มีใครรู้ว่าจะถอดคืนได้เมื่อไหร่"""
    for name, why in alert_rows:
        assert "/" in name, f"{name}: ต้องเป็นรูป <tool>/<rule id> ให้ตรงกับที่ API คืนมา"
        assert len(why) >= MIN_REASON, (
            f"{name}: เหตุผลสั้นเกินกว่าจะตัดสินได้ — ทะเบียนข้อยกเว้นที่ไม่มีเหตุผลคือรายการที่ไม่มีใครกล้าถอด"
        )


def test_no_duplicate_rows_in_the_alert_register(alert_rows):
    """ชื่อซ้ำ = เหตุผลสองชุดของเรื่องเดียว แล้วไม่มีใครรู้ว่าอันไหนคือคำตัดสิน"""
    names = [name for name, _ in alert_rows]
    assert len(names) == len(set(names)), "มีชื่อ alert ซ้ำในทะเบียน"


def test_every_accepted_alert_is_explained_in_the_cadence_document(alert_rows):
    """ทะเบียนบอกว่า *อะไร* เอกสารบอกว่า *ทำไม* — ขาดข้างใดข้างหนึ่งคือครึ่งเดียว

    หลักเดียวกับ `pins/accepted-advisories.txt` ↔ `docs/SECURITY-CADENCE.md`
    ที่ `tests/test_pins_audit.py` บังคับสองทิศไว้ก่อนแล้ว
    """
    doc = CADENCE_DOC.read_text(encoding="utf-8")
    for name, _ in alert_rows:
        rule = name.split("/", 1)[1]
        assert rule in doc, (
            f"{name}: ไม่มีเหตุผลใน docs/SECURITY-CADENCE.md — "
            "ทะเบียนที่ไม่มีเอกสารหนุน คือคำตัดสินที่อ่านได้เฉพาะคนที่เขียนมันเอง"
        )
