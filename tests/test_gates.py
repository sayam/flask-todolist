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
SEVERITIES = {"blocking", "warning"}


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
