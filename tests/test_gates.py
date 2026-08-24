"""ดัชนี `gates.yaml` ต้องตรงกับความจริงสองทิศ — ADR 0039

ดัชนีที่ไม่ถูกบังคับให้ตรงกับความจริงคือดัชนีที่โกหกเงียบ ๆ — semgrep เคย
ตรวจแค่ 71/136 ไฟล์เพราะขอบเขตประกาศอยู่คนละที่กับตัวตรวจ ที่นี่จึงบังคับ:

- **ทิศไป**: ทุก gate ชี้ไปหา job/step/ไฟล์เทสต์ที่มีอยู่จริง
- **ทิศกลับ (job)**: ทุก job ใน workflow ต้องมี gate — job ใหม่ที่ไม่มี = แดง
- **ทิศกลับ (เทสต์) — partition**: ไฟล์ `tests/test_*.py` ทุกไฟล์ต้องถูกตัดสิน
  ว่าเป็นของ gate ตัวไหน **ตัวเดียวเท่านั้น** (แบบแผน DATA-CLASSIFICATION:
  ของใหม่ที่ไม่ถูกตัดสิน = แดง ไม่ใช่หลุดจากสายตาเงียบ ๆ)

ข้อความ error ของทิศกลับตั้งใจบอกว่า *ขาดอะไร* — มันทำหน้าที่แทน generator:
เพิ่มไฟล์/job แล้วเทสต์นี้จะบอกเองว่าต้องไปลงทะเบียนอะไรที่ไหน
"""

import pathlib
import re

import pytest
import yaml

from scripts import workflows as gha
from tests.test_asvs import _unresolved

ROOT = pathlib.Path(__file__).resolve().parent.parent
GATES = ROOT / "gates.yaml"
WORKFLOW_DIR = ROOT / ".github" / "workflows"
ASVS = ROOT / "docs" / "ASVS.md"
TESTS_DIR = ROOT / "tests"

GATE_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
STANDARD_ID = re.compile(r"^ASVS-(V\d+\.\d+\.\d+)$")
# แถวของตาราง ASVS: | Vx.y.z | ระดับ | คำอธิบาย | สถานะ | หลักฐาน |
ASVS_ROW = re.compile(
    r"^\|\s*(V\d+\.\d+\.\d+)\s*\|\s*\d\s*\|.*?\|\s*(ผ่าน|ไม่เกี่ยวข้อง|ยังไม่ผ่าน)\s*\|", re.MULTILINE
)

KINDS = {"test", "step", "job"}
LAYERS = {"baseline", "business", "internal"}
PILLARS = {"security", "performance", "manageability", "devx"}
# **สามค่า และต้องตรงกับอำนาจจริง** (ADR 0066) — `blocking` บล็อก merge ได้จริง ·
# `watched` ตรวจจริงล้มได้แต่ไม่บล็อกใคร · `warning` ไม่ล้มโดยตั้งใจ
SEVERITIES = {"blocking", "watched", "warning"}
WATCHER_FIELDS = {"who", "within_days", "how", "cadence"}
# **เพดานคือรอบที่ยาวที่สุดที่มีอยู่จริงในตาราง cadence** (12 เดือน) — ยาวกว่านั้น
# ไม่ใช่กรอบเวลา แต่เป็นการยอมแพ้ · ตัวเลขที่ต่ำกว่านี้ต้องมีกลไกที่เร็วพอรองรับ
# ซึ่ง `test_every_promise_is_backed_by_a_mechanism_that_is_fast_enough` บังคับ
MAX_WITHIN_DAYS = 365
CADENCE_DOC = ROOT / "docs" / "SECURITY-CADENCE.md"
MONTHS = 30  # รอบใน cadence เขียนเป็นเดือน — แปลงหยาบ ๆ พอสำหรับการเทียบขอบเขต


@pytest.fixture(scope="module")
def gates() -> list[dict]:
    loaded = yaml.safe_load(GATES.read_text(encoding="utf-8"))
    assert loaded.get("version") == 1, "gates.yaml ต้องประกาศ version: 1"
    found = loaded.get("gates")
    assert found, "ไม่มี gate สักตัวใน gates.yaml — ไฟล์นี้ไม่ทำอะไรเลย"
    return found


@pytest.fixture(scope="module")
def jobs() -> dict[str, list[str]]:
    """job → รายชื่อ step ที่มีชื่อ — อ่านจาก workflow ทุกไฟล์"""
    found: dict[str, list[str]] = {}
    for path in sorted(WORKFLOW_DIR.glob("*.y*ml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for name, job in workflow.get("jobs", {}).items():
            assert name not in found, f"job {name!r} ประกาศซ้ำสองไฟล์ workflow"
            found[name] = [s["name"] for s in job.get("steps", []) if s.get("name")]
    assert found, "อ่าน job จาก workflow ไม่ได้เลย — ตัวดึงพังหรือเปล่า"
    return found


@pytest.fixture(scope="module")
def blocking_jobs() -> set[str]:
    """job ที่ **บล็อก merge ได้จริง** — คือ job ในไฟล์ที่มีทริกเกอร์ `pull_request`

    ด่านที่ไม่ได้รันบน PR บังคับใครไม่ได้เลย ต่อให้ดัชนีจะเขียนว่า blocking
    (audit รอบ 10 ข้อ 1: `scorecard` ล้ม 27 run ติดกันบน main ข้ามคืน
    โดยทุก push ผ่านหมด)
    """
    found: set[str] = set()
    for path in sorted(WORKFLOW_DIR.glob("*.y*ml")):
        workflow = gha.load(path)
        if not gha.runs_on(workflow, "pull_request"):
            continue
        found |= set(gha.jobs(workflow))
    assert found, "ไม่มี job ไหนรันบน pull_request เลย — ตัวดึงพังหรือ workflow เปลี่ยนรูป"
    return found


@pytest.fixture(scope="module")
def asvs_status() -> dict[str, str]:
    """ข้อ ASVS → สถานะที่ประเมินไว้ — ต้องครบ 253 ข้อไม่งั้นตัวดึงพังเอง"""
    rows = dict(ASVS_ROW.findall(ASVS.read_text(encoding="utf-8")))
    assert len(rows) == 253, f"อ่านตาราง ASVS ได้ {len(rows)} แถว (ต้อง 253) — regex เพี้ยนหรือเปล่า"
    return rows


def test_every_gate_is_wellformed(gates):
    """id ไม่ซ้ำ · kind/severity อยู่ในชุดที่นิยาม · คีย์ครบ"""
    seen: set[str] = set()
    for gate in gates:
        gid = gate.get("id", "")
        assert GATE_ID.match(gid), f"id ไม่ใช่ kebab-case: {gid!r}"
        assert gid not in seen, f"id ซ้ำ: {gid}"
        seen.add(gid)
        assert gate.get("kind") in KINDS, f"{gid}: kind {gate.get('kind')!r} ไม่รู้จัก"
        assert gate.get("severity") in SEVERITIES, f"{gid}: severity {gate.get('severity')!r} ไม่รู้จัก"
        assert gate.get("title"), f"{gid}: ไม่มี title"
        assert isinstance(gate.get("requires"), list), f"{gid}: requires ต้องเป็น list"


def test_every_gate_points_at_a_real_job(gates, jobs):
    """ทิศไป: job ที่ gate อ้างต้องมีจริงใน workflow"""
    missing = [
        f"{g['id']} → job {g['enforced_by'].get('job')!r}"
        for g in gates
        if g["enforced_by"].get("job") not in jobs
    ]
    assert not missing, "gate ที่ชี้ไปหา job ที่ไม่มีจริง:\n  " + "\n  ".join(missing)


def test_step_gates_name_a_real_step(gates, jobs):
    """kind: step ต้องตรงกับชื่อ step ใน job นั้นเป๊ะ — ไม่เก็บคำสั่งซ้ำ (ADR 0039)

    เปลี่ยนชื่อ step ใน workflow โดยไม่แก้ดัชนี = แดงที่นี่ ไม่ใช่ drift เงียบ ๆ
    """
    broken = []
    for gate in gates:
        if gate["kind"] != "step":
            continue
        job = gate["enforced_by"]["job"]
        step = gate["enforced_by"].get("step")
        if not step or step not in jobs.get(job, []):
            broken.append(f"{gate['id']} → ไม่มี step {step!r} ใน job {job!r}")
    assert not broken, "\n  ".join(["step gate ที่อ้างผิด:", *broken])


def test_test_gates_list_real_files_in_the_suite_job(gates):
    """kind: test อยู่ใน job `test` เสมอ (จุดที่ทั้งชุดถูกรัน) และไฟล์ต้องมีจริง"""
    broken = []
    for gate in gates:
        if gate["kind"] != "test":
            continue
        if gate["enforced_by"].get("job") != "test":
            broken.append(f"{gate['id']}: kind test ต้องผูกกับ job test")
        files = gate["enforced_by"].get("tests") or []
        if not files:
            broken.append(f"{gate['id']}: ไม่มีรายชื่อไฟล์เทสต์")
        broken += [f"{gate['id']}: ไม่มีไฟล์ {f}" for f in files if not (ROOT / f).is_file()]
    assert not broken, "\n  ".join(["test gate ที่อ้างผิด:", *broken])


def test_every_job_is_covered_by_a_gate(gates, jobs):
    """ทิศกลับ (job): job ที่ไม่มี gate คือด่านที่หายจากดัชนีเงียบ ๆ"""
    covered = {g["enforced_by"]["job"] for g in gates}
    uncovered = sorted(set(jobs) - covered)
    assert not uncovered, (
        f"job ที่ไม่มี gate ในดัชนี: {uncovered}\n"
        "เพิ่ม gate ให้มันใน gates.yaml — job ที่ไม่อยู่ในดัชนีคือด่านที่เฟส 9/11 มองไม่เห็น"
    )


def test_every_test_file_is_decided_exactly_once(gates):
    """ทิศกลับ (เทสต์): partition เต็ม — ทุกไฟล์ถูกตัดสิน ไฟล์ละหนึ่ง gate

    แบบแผนเดียวกับ DATA-CLASSIFICATION: ราคาคือหนึ่งบรรทัดต่อไฟล์ใหม่
    แลกกับการที่ไม่มีไฟล์ไหนหลุดจากดัชนีโดยไม่มีใครตัดสิน
    """
    claims: dict[str, list[str]] = {}
    for gate in gates:
        for f in gate["enforced_by"].get("tests") or []:
            claims.setdefault(f, []).append(gate["id"])

    on_disk = {f"tests/{p.name}" for p in TESTS_DIR.glob("test_*.py")}

    unregistered = sorted(on_disk - claims.keys())
    assert not unregistered, (
        f"ไฟล์เทสต์ที่ยังไม่ถูกตัดสินว่าเป็นของ gate ไหน: {unregistered}\n"
        "ลงทะเบียนใน gates.yaml — gate ใหม่ถ้าเป็นด่านนโยบาย หรือแถวใน app-behavior-suite"
    )

    ghosts = sorted(claims.keys() - on_disk)
    assert not ghosts, f"ดัชนีอ้างไฟล์ที่ไม่มีแล้ว: {ghosts}"

    doubled = {f: gs for f, gs in claims.items() if len(gs) > 1}
    assert not doubled, f"ไฟล์ที่ถูกอ้างมากกว่าหนึ่ง gate (partition แตก): {doubled}"


def test_every_gate_declares_a_coherent_layer(gates):
    """ทุก gate ประกาศชั้น และชั้นต้องไม่ขัดกับ portable (ADR 0042)

    `baseline` = สากล จึงต้อง export ได้ · `internal` = ของ repo นี้เอง จึง
    export ไม่ได้ · ชั้นที่ขัดกับ portable คือ gate ที่จะไปโผล่ผิดใบ (หรือหาย
    จากทุกใบ) ตอน generate skill โดยไม่มีอะไรฟ้อง
    """
    for gate in gates:
        gid = gate["id"]
        layer = gate.get("layer")
        assert layer in LAYERS, f"{gid}: layer {layer!r} ไม่รู้จัก (ต้องเป็น {sorted(LAYERS)})"
        if layer == "baseline":
            assert gate.get("portable") is True, (
                f"{gid}: baseline ต้อง portable — สากลแล้วไม่ export คือขัดแย้งในตัว"
            )
        if layer == "internal":
            assert gate.get("portable") is False, (
                f"{gid}: internal ห้าม portable — ของ repo นี้เองไม่มีความหมายข้างนอก"
            )


# คำที่ผูกกับ *สถาปัตยกรรมของ repo นี้* — ต่างจาก `BANNED` ใน `tests/test_skill.py`
# ซึ่งห้ามชื่อ *ไลบรารีของ framework* · ตัวนั้นถามว่า "กฎนี้ผูกกับ Flask ไหม"
# ตัวนี้ถามว่า **"กฎนี้ผูกกับวิธีที่เราออกแบบแอปของเราไหม"** ซึ่งเป็นคนละคำถาม
# และเป็นคำถามที่ไม่มีใครถามมาก่อน (audit r23)
#
# ชั้น `business` ใช้คำพวกนี้ได้เต็มที่ — มันคือชั้นที่มีไว้สำหรับ "ข้อตกลงของแอป
# ชนิดนี้" โดยนิยาม · ที่ห้ามคือชั้น `baseline` ซึ่งประกาศตัวว่าสากล
ARCHITECTURE_BOUND = ("plugin", "tdl_")


def test_baseline_rules_do_not_speak_our_architecture(gates):
    """กฎที่ประกาศตัวว่าสากล ต้องอ่านรู้เรื่องโดยไม่ต้องมีสถาปัตยกรรมของเรา (audit r23)

    ป้ายชั้นเป็นคำประกาศที่ไม่มีอะไรตรวจมาตลอด — เทสต์ข้างบนบังคับ *ความสัมพันธ์*
    ระหว่างชั้นกับ `portable` ครบถ้วน แต่ไม่มีอะไรถามว่า **กฎข้อนี้สากลจริงไหม**
    · ผลคือกฎห้าข้อที่พูดถึง plugin ตรง ๆ ถูกส่งออกในชั้น baseline ไปหาโปรเจกต์
    ที่ไม่มีสถาปัตยกรรมนั้น — ไม่ใช่ "ทำแล้วไม่ผ่าน" แต่เป็น "ไม่มีความหมาย"

    **ตรวจทั้งชื่อกฎและบทเรียน** เพราะทั้งสองอย่างถูก render ลง `SKILL.md`
    ไปด้วยกัน · บรรทัดที่ชี้ไฟล์/job ของ repo นี้ (`enforced_by`) ไม่ถูกตรวจ
    เพราะนั่นคือส่วนอ้างอิง ไม่ใช่ส่วนกฎ — หลักเดียวกับที่ `tests/test_skill.py`
    ยกเว้นบรรทัด "ตัวบังคับใน reference" ไว้
    """
    leaked = []
    for gate in gates:
        if gate.get("layer") != "baseline":
            continue
        prose = f"{gate.get('title', '')} {gate.get('born_from', '')}".lower()
        leaked += [f"{gate['id']}: มีคำว่า {word!r}" for word in ARCHITECTURE_BOUND if word in prose]

    assert not leaked, "\n  ".join(
        [
            "กฎที่ประกาศตัวว่าสากล แต่พูดภาษาสถาปัตยกรรมของเราเอง:",
            *leaked,
            "",
            (
                "เลือกทางใดทางหนึ่ง: ย้ายไปชั้น `business` (ข้อตกลงของแอปชนิดนี้ — "
                "ยัง export ได้ แต่ไปอยู่ใบของมัน) หรือเขียนกฎใหม่ให้อ่านรู้เรื่อง"
                "โดยไม่ต้องมีสถาปัตยกรรมของเรา"
            ),
        ]
    )


def test_every_gate_declares_a_pillar(gates):
    """ทุก gate ประกาศชั้นของปรัชญา (ADR 0051) — partition แบบเดียวกับ layer

    ปรัชญาที่ไม่ถูกเครื่องตรวจคือคำขวัญ: การบังคับให้ทุกด่านบอกว่าตัวเอง
    รับใช้ชั้นไหน (security/performance/manageability/devx) ทำให้ตอบได้
    ทันทีว่าชั้นไหนพูดมากกว่าทำ — และ gate ใหม่ต้องตัดสินใจตั้งแต่เกิด
    """
    for gate in gates:
        pillar = gate.get("pillar")
        assert pillar in PILLARS, (
            f"{gate['id']}: pillar {pillar!r} ไม่รู้จัก (ต้องเป็น {sorted(PILLARS)})"
        )


# ด่านที่แพงและยังไม่เคยจับอะไร ต้องบอกได้ว่ามัน *คุ้มอะไรอยู่* — ADR 0062
GATES_THAT_MUST_DECLARE_WHAT_THEY_GUARD = frozenset(
    {
        "perf-regression-tripwire",
        "oidc-end-to-end",
        "ldap-end-to-end",
        "vault-end-to-end",
        "metrics-scraped-for-real",
        "a11y-real-browser",
    }
)


def test_expensive_gates_declare_what_they_guard(gates):
    """`guards:` คือครึ่งหนึ่งของคำถาม "ยังคุ้มไหม" — อีกครึ่งคือ "เคยแดงไหม"

    ADR 0062: ด่าน real-service หกตัวกินเวลาเครื่อง 15% ต่อ push และยังไม่เคย
    จับอะไรในหน้าต่าง 200 run · การตัดสินว่าจะเก็บไว้หรือย้ายไปรันตามรอบ ต้องดู
    ทั้งสองอย่างคู่กัน — ด่านที่ไม่เคยแดงเพราะไม่มีใครแตะโค้ดที่มันคุ้ม ต่างจาก
    ด่านที่ไม่เคยแดงทั้งที่โค้ดนั้นถูกแก้ทุกสัปดาห์คนละเรื่อง
    """
    declared = {
        g["id"]: g.get("guards")
        for g in gates
        if g["id"] in GATES_THAT_MUST_DECLARE_WHAT_THEY_GUARD
    }

    missing = sorted(gid for gid, paths in declared.items() if not paths)
    assert not missing, f"gate ที่ต้องประกาศ guards แต่ยังไม่มี: {missing}"

    unknown = sorted(GATES_THAT_MUST_DECLARE_WHAT_THEY_GUARD - set(declared))
    assert not unknown, f"รายการอ้าง gate ที่ไม่มีแล้ว: {unknown}"


def test_declared_guards_point_at_paths_that_exist(gates):
    """เส้นทางที่ไม่มีจริง = ตัวทบทวนจะอ่านว่า "ไม่มีใครแตะเลย" ตลอดกาล"""
    dead = [
        f"{g['id']} → {path}"
        for g in gates
        for path in g.get("guards") or []
        if not (ROOT / path).exists()
    ]
    assert not dead, f"guards ที่ชี้ของที่ไม่มีจริง: {dead}"


def test_portable_gates_carry_their_origin(gates):
    """กฎสากลที่เล่าไม่ได้ว่ามาจากกับดักไหน คือกฎที่จะถูกลบวันที่ไม่มีใครจำเหตุผล"""
    missing = [
        g["id"] for g in gates if g.get("portable") and not (g.get("born_from") or "").strip()
    ]
    assert not missing, f"portable gate ที่ไม่มี born_from: {missing}"


def test_the_crosswalk_is_derived_not_written(gates):
    """`docs/GATES-ASVS.md` ต้องตรงกับผล generate ไบต์ต่อไบต์ — 8-05

    mapping ที่เขียนมือคือที่ที่สามให้ drift (นอกจาก gates.yaml กับ ASVS.md)
    จึง derive ทางเดียวจากหลักฐาน แล้วด่านนี้กันไม่ให้ไฟล์ที่ commit ค้างจากแหล่ง
    """
    from scripts.build_gates_crosswalk import OUT, crosswalk

    assert OUT.is_file(), "ไม่มี docs/GATES-ASVS.md — รัน scripts/build_gates_crosswalk.py"
    assert OUT.read_text(encoding="utf-8") == crosswalk(), (
        "docs/GATES-ASVS.md ไม่ตรงกับผล generate — "
        "รัน pipenv run python scripts/build_gates_crosswalk.py แล้ว commit มาด้วยกัน"
    )


def test_standard_claims_are_corroborated_by_the_rows_evidence(gates):
    """gate ที่อ้างข้อ ASVS ต้องถูกหลักฐานของข้อนั้น**ชี้กลับมาหา** — ไม่ใช่แค่มีแถวอยู่

    ตอนเขียนดัชนีรอบแรกพลาดเองสองข้อ: อ้าง V8.2.2 ให้ gate ของ rbac ทั้งที่
    หลักฐานแถวนั้นอ้าง api_fuzz และอ้าง V3.4.1 ให้ job stack ทั้งที่หลักฐาน
    ยังไม่ได้บันทึกว่า stack ตรวจ HSTS — คำอ้างที่ไม่มีหลักฐานหนุนคือของประดับ
    """
    from scripts.build_gates_crosswalk import JOB_REF, TEST_REF, passed_rows

    rows = passed_rows()
    broken = []
    for gate in gates:
        own_files = set(gate["enforced_by"].get("tests") or [])
        own_job = gate["enforced_by"]["job"] if gate["kind"] in ("job", "step") else None
        for ref in gate.get("standard") or []:
            evidence = rows.get(ref.removeprefix("ASVS-"), "")
            cited_files = set(TEST_REF.findall(evidence))
            cited_jobs = set(JOB_REF.findall(evidence))
            if not (own_files & cited_files or (own_job and own_job in cited_jobs)):
                broken.append(f"{gate['id']} อ้าง {ref} แต่หลักฐานของแถวนั้นไม่ได้ชี้มาหา gate นี้")
    assert not broken, "\n  ".join(["คำอ้างที่ไม่มีหลักฐานหนุน:", *broken])


def test_cited_standards_exist_and_match_the_assessment(gates, asvs_status):
    """`standard` อ้างได้เฉพาะข้อที่ประเมินว่า "ผ่าน" — อ้างข้อที่ประเมินว่า
    "ไม่เกี่ยวข้อง"/"ยังไม่ผ่าน" คือดัชนีที่ขัดกับคำตัดสินของผู้ประเมิน
    """
    broken = []
    for gate in gates:
        for ref in gate.get("standard") or []:
            matched = STANDARD_ID.match(ref)
            if not matched:
                broken.append(f"{gate['id']}: รูปแบบผิด {ref!r} (ต้องเป็น ASVS-Vx.y.z)")
                continue
            status = asvs_status.get(matched.group(1))
            if status is None:
                broken.append(f"{gate['id']}: {ref} ไม่มีในตาราง ASVS")
            elif status != "ผ่าน":
                broken.append(f"{gate['id']}: {ref} ถูกประเมินว่า {status!r} — ขัดกับการอ้างเป็นหลักฐาน")
    assert not broken, "\n  ".join(["standard ที่อ้างผิด:", *broken])


# ------------------------------------------------ อำนาจจริงของด่าน (ADR 0066 · audit r10)
#
# `severity` มีมาตั้งแต่ ADR 0039 แต่**ไม่เคยถูกเทียบกับความจริง** — 97 จาก 99 gate
# ประกาศว่า blocking ขณะที่ 3 จาก 30 check ไม่อยู่ในรายการบังคับเลย และสองในนั้น
# ถือ gate ที่ประกาศตัวเองว่า blocking · วัดจริง: workflow `scorecard` ล้ม 27 run
# ติดกัน 14 ชั่วโมง 19 นาที โดยทุก push ลง main ผ่านหมด


def _enforcing_job(gate: dict) -> str:
    return (gate.get("enforced_by") or {}).get("job", "")


def test_blocking_gates_are_enforced_by_a_job_that_can_block(gates, blocking_jobs):
    """ประกาศว่า blocking แล้วต้องบล็อกได้จริง — ไม่งั้นดัชนีโฆษณาอำนาจที่ไม่มี"""
    lying = [
        f"{gate['id']} (job {_enforcing_job(gate)} ไม่ได้รันบน pull_request)"
        for gate in gates
        if gate.get("severity") == "blocking" and _enforcing_job(gate) not in blocking_jobs
    ]
    assert not lying, (
        "gate ที่ประกาศ blocking แต่ job ของมันบล็อกอะไรไม่ได้:\n  "
        + "\n  ".join(lying)
        + "\nใช้ severity: watched แล้วประกาศ watched_by (ADR 0066) — "
        "ด่านที่ไม่บล็อกใครไม่ใช่เรื่องผิด แต่การเขียนว่ามันบล็อกคือการโฆษณาเกินจริง"
    )


def test_gates_that_can_block_do_not_understate_their_authority(gates, blocking_jobs):
    """ทิศกลับ — job ที่รันบน PR ห้ามถูกลดชั้นเป็น watched

    ถ้าเลี่ยงการบล็อกได้ด้วยการเปลี่ยนคำเดียวในดัชนี ตาข่ายทั้งใบก็หดได้เงียบ ๆ
    (หลักเดียวกับ FAIL → WARN ของ .zap/rules.tsv)
    """
    understated = [
        gate["id"]
        for gate in gates
        if gate.get("severity") == "watched" and _enforcing_job(gate) in blocking_jobs
    ]
    assert not understated, (
        f"gate ที่ job ของมันรันบน PR อยู่แล้ว แต่ประกาศว่า watched: {understated} — "
        "ใช้ blocking หรือถ้าตั้งใจให้ไม่ล้มจริง ๆ ใช้ warning พร้อมเหตุผล"
    )


def test_every_gate_that_cannot_block_names_a_watcher(gates):
    """บล็อกไม่ได้ = ต้องบอกว่าใครเห็น และภายในกี่วัน

    เขียนลงไปว่า "ผู้ดูแล ภายใน 7 วัน" เปลี่ยนความเงียบจากสภาพปกติ
    เป็นสิ่งที่ผิดนัดได้ — นั่นคือทั้งหมดที่ฟิลด์นี้ทำ
    """
    for gate in gates:
        watcher = gate.get("watched_by")
        if gate.get("severity") == "blocking":
            assert not watcher, f"{gate['id']}: blocking แล้วไม่ต้องมี watched_by — ผู้รับคือคนเปิด PR"
            continue
        assert watcher, f"{gate['id']}: severity {gate['severity']!r} แต่ไม่บอกว่าใครเห็น"
        assert set(watcher) == WATCHER_FIELDS, (
            f"{gate['id']}: watched_by ต้องมีครบ {sorted(WATCHER_FIELDS)} — ได้ {sorted(watcher)}"
        )
        assert isinstance(watcher["within_days"], int), f"{gate['id']}: within_days ต้องเป็นตัวเลข"
        assert 1 <= watcher["within_days"] <= MAX_WITHIN_DAYS, (
            f"{gate['id']}: within_days = {watcher['within_days']} — "
            f"เกิน {MAX_WITHIN_DAYS} วันไม่ใช่กรอบเวลา แต่เป็นการยอมแพ้"
        )
        assert watcher["who"].strip(), f"{gate['id']}: ไม่ได้บอกว่าใครเป็นผู้รับ"


def test_every_watcher_names_a_mechanism_that_exists(gates, jobs):
    """`how` ต้องอ้างของที่มีจริง — กลไกที่พิมพ์ไว้เฉย ๆ คือความหวัง ไม่ใช่การเฝ้า"""
    dead = []
    for gate in gates:
        watcher = gate.get("watched_by")
        if not watcher:
            continue
        refs = re.findall(r"`([^`]+)`", watcher["how"])
        assert refs, f"{gate['id']}: watched_by.how ไม่ได้อ้างกลไกไหนเลย"
        dead += [
            f"{gate['id']}: `{ref}` — {reason}"
            for ref in refs
            if (reason := _unresolved(ref, set(jobs)))
        ]
    assert not dead, "กลไกที่เฝ้าอ้างแต่ไม่มีจริง:\n  " + "\n  ".join(dead)


# --------------------- คำสัญญาต้องมีกลไกรองรับ (ADR 0066 โน้ต 1 · audit r12 ข้อ 2)
#
# รอบ 10 ให้ทุก gate ที่บล็อกไม่ได้ประกาศว่า "ใครเห็นภายในกี่วัน" · ตัวตรวจที่มีอยู่
# ดูแค่ว่าเป็นเลขและไม่เกินเพดาน และดูว่า `how` อ้างของที่มีอยู่จริง — **ไม่มีอะไร
# ถามว่าของที่อ้างนั้นเร็วพอกับตัวเลขไหม** · วัดตอนตั้งกฎ: สี่ในหกใบสัญญาเร็วกว่า
# กลไกของตัวเอง 3–12 เท่า (7 วัน กับกลไกที่มีรอบ 90 วัน เป็นต้น)


def _cadence_periods() -> dict[str, int]:
    """หัวข้อของแถวใน cadence → รอบเป็นวัน (ข้ามแถวที่ผูกกับเหตุการณ์ ไม่ใช่เวลา)

    **รับทั้ง "N เดือน" และ "N วัน"** — รอบที่สั้นกว่าหนึ่งเดือนเขียนเป็นเดือนไม่ได้
    และถ้าตัวอ่านรู้จักแต่เดือน แถวแบบนั้นจะถูกอ่านเป็น 0 = "ผูกกับเหตุการณ์
    เร็วพอเสมอ" ซึ่งทำให้ด่านที่พึ่งตัวเลขนี้เขียวฟรี (audit รอบ 26 — แถวรักษาชีพ
    เป็นแถวแรกที่มีรอบเป็นวัน เพราะมันต้องสั้นกว่าหน้าต่าง 60 วันของ GitHub)
    """
    text = CADENCE_DOC.read_text(encoding="utf-8")
    start = text.index("## ส่วนที่ต้องมีคนลงมือ")
    end = text.index("## กรอบเวลาแก้ช่องโหว่", start)
    rows = {}
    for line in text[start:end].splitlines():
        if not line.startswith("|") or line.startswith("|---") or "ครบกำหนด" in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 5:
            continue
        months = re.fullmatch(r"(\d+) เดือน", cells[1])
        days = re.fullmatch(r"(\d+) วัน", cells[1])
        period = int(months.group(1)) * MONTHS if months else int(days.group(1)) if days else 0
        rows[cells[0].replace("**", "")] = period
    return rows


def test_every_promise_is_backed_by_a_mechanism_that_is_fast_enough(gates):
    """`within_days` ต้องไม่เล็กกว่ารอบของกลไกที่มันอ้าง

    สัญญาที่เร็วกว่าเครื่องมือที่ตัวเองอ้างถึง คือสัญญาที่ไม่มีใครทำได้ — และมันถูก
    เขียนในรอบเดียวกับที่ประกาศว่า `severity` ต้องตรงกับอำนาจจริง
    **อยากให้ตัวเลขเล็กลง ต้องสร้างกลไกที่เร็วกว่าก่อน ไม่ใช่แก้ตัวเลข**

    รอบที่ผูกกับเหตุการณ์ (`ทุก release`) ถือว่าเร็วพอเสมอ เพราะสัญญาณเกิดตอนที่
    คนกำลังทำงานนั้นอยู่พอดี — แต่แถวนั้นต้องมีอยู่จริงเหมือนแถวอื่น
    """
    periods = _cadence_periods()
    unbacked = []
    for gate in gates:
        watcher = gate.get("watched_by")
        if not watcher:
            continue
        anchor = watcher["cadence"]
        matched = [name for name in periods if anchor in name]
        assert matched, (
            f"{gate['id']}: `cadence: {anchor}` ไม่ตรงกับแถวไหนใน docs/SECURITY-CADENCE.md — "
            "กลไกที่อ้างต้องมีอยู่จริง"
        )
        slowest = max(periods[name] for name in matched)
        if slowest and watcher["within_days"] < slowest:
            unbacked.append(
                f"{gate['id']}: สัญญา {watcher['within_days']} วัน "
                f"แต่กลไกที่อ้าง ({matched[0][:40]}…) มีรอบ {slowest} วัน"
            )
    assert not unbacked, (
        "คำสัญญาที่เร็วกว่ากลไกของตัวเอง:\n  "
        + "\n  ".join(unbacked)
        + "\nสร้างกลไกที่เร็วกว่าก่อน หรือขยับตัวเลขให้ตรงกับความจริง (ADR 0066 โน้ต 1)"
    )


# ------------- ตัวเลขที่โฆษณาไว้ในแผน ต้องตรงกับ gates.yaml (audit รอบ 17)
#
# `ROADMAP-GOVERNANCE.md` เขียนสัดส่วน pillar ไว้เป็นหลักฐานว่าแผน G1 ให้ผลอะไร
# และเขียนกำกับตัวเองว่า "ตัวเลขชุดนี้ไม่มีเทสต์คุม จึงต้องกวาดตอน doc sweep" —
# ซึ่งค้างผิดมาแล้วสองรอบ · ตัวเลขที่ต้องรอให้มีคนกวาด คือตัวเลขที่ผิดอยู่เงียบ ๆ
# ระหว่างรอบ (หลักเดียวกับ ADR 0068: เพดานที่ไม่มีตัวทวง = เพดานที่ไม่ได้ตั้ง)

ROADMAP_GOVERNANCE = ROOT / "docs" / "ROADMAP-GOVERNANCE.md"
# **quantifier ตัวเดียว มีเพดาน และ lazy** — รุ่นแรกเขียนเป็น `(?:\w+ \d+(?: · )?)+`
# ซึ่ง CodeQL จับเป็น `py/redos` (high) ทันทีใน PR แรก: quantifier ซ้อน quantifier
# ทำให้ backtracking โตแบบเอ็กซ์โพเนนเชียล · การแยกคำทำทีหลังด้วย `str.split`
# ปลอดภัยกว่าและอ่านง่ายกว่าการให้ regex ทำ
PILLAR_TALLY = re.compile(r"วันนี้ \(หลัง r\d+\) เป็น (.{0,200}?) รวม (\d+) gate")


def test_the_pillar_tally_in_the_roadmap_matches_reality(gates):
    """สัดส่วน pillar ที่แผนโฆษณาไว้ ต้องเท่ากับที่นับได้จาก `gates.yaml` จริง"""
    text = ROADMAP_GOVERNANCE.read_text(encoding="utf-8")
    found = PILLAR_TALLY.search(text.replace("\n  ", " "))
    assert found, "หาแถวสัดส่วน pillar ใน ROADMAP-GOVERNANCE.md ไม่เจอ — รูปเปลี่ยนไปแล้ว"

    claimed = {
        name: int(count)
        for name, count in (part.split() for part in found.group(1).strip().split(" · "))
    }
    actual: dict[str, int] = {}
    for gate in gates:
        actual[gate["pillar"]] = actual.get(gate["pillar"], 0) + 1

    assert claimed == actual, f"แผนอ้าง {claimed} แต่ของจริงคือ {actual}"
    assert int(found.group(2)) == len(gates), (
        f"แผนอ้างรวม {found.group(2)} gate แต่ของจริง {len(gates)}"
    )
