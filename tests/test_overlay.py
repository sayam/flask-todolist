"""overlay ของ Flask ต้องครอบ portable gate ครบ และ checker ทุกตัวพิสูจน์สองทิศ

สามชั้นของความจริงที่ต้องตรงกัน:
1. `overlay.json` ↔ portable gate ใน `gates.yaml` — สองทิศ ขาดหรือเกินคือ
   overlay ที่โกหกว่าครอบ (เงื่อนไขสำเร็จของเฟส 9: เพิ่ม portable gate โดยไม่มี
   enforcement ใน overlay = แดง)
2. checker ทุกตัว**แดงเมื่อควรแดงและผ่านเมื่อควรผ่าน** — fixture คู่ต่อตัว
   (ของที่ฝังช่องโหว่ vs ของสะอาด) ยิงผ่าน subprocess ด้วย interpreter เปล่า
   เหมือนที่โปรเจกต์ปลายทางจะรันจริง
3. install → doctor ต้องจับของหาย — ลบไฟล์ที่ติดตั้งแล้ว doctor ต้องไม่เขียว

เคสของ entrypoint-clean มาจาก dogfood จริง: `run.py` ของ repo นี้*เล่า*ใน
docstring ว่าเคยถอด `debug=True` ออก — checker รุ่น regex อ่านร้อยแก้วเป็นโค้ด
"""

import json
import pathlib
import subprocess
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
OVERLAY = ROOT / "overlays" / "flask"
MANIFEST = OVERLAY / "overlay.json"
GATES = ROOT / "gates.yaml"

SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"
DIGEST = "sha256:" + "a" * 64
# job ที่ต่อท้าย workflow ตั้งต้นเพื่อพิสูจน์ทิศกลับของดัชนี
EXTRA_JOB = "\n  extra:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo hi\n"

# (ชื่อ checker, ไฟล์ที่วางใน repo จำลอง: เคสฝังช่องโหว่, เคสสะอาด)
CASES = {
    "scan_service_layer.py": (
        {"app/services/x.py": "from flask import request\n"},
        {"app/services/x.py": "from flask import current_app\n"},
    ),
    "scan_write_discipline.py": (
        {"app/routes.py": "db.session.delete(row)\n"},
        {"app/purge.py": "db.session.delete(row)\n"},
    ),
    "scan_templates_inline.py": (
        {"app/templates/a.html": '<button onclick="go()">x</button>\n'},
        {"app/templates/a.html": '<script src="/static/app.js"></script>\n'},
    ),
    "scan_entrypoint_debug.py": (
        {"run.py": "app.run(debug=True)\n"},
        {"run.py": '"""เคยมี app.run(debug=True) แต่ถอดออกแล้ว"""\napp.run()\n'},
    ),
    "scan_workflow_pinning.py": (
        {".github/workflows/ci.yml": "steps:\n  - uses: actions/checkout@v4\n"},
        {".github/workflows/ci.yml": f"steps:\n  - uses: actions/checkout@{SHA}\n"},
    ),
    "scan_dockerfile_digest.py": (
        {"Dockerfile": "FROM python:3.13-slim\n"},
        {"Dockerfile": f"FROM python:3.13-slim@{DIGEST} AS builder\nFROM builder\n"},
    ),
    "scan_install_pinning.py": (
        {".github/workflows/ci.yml": "run: pip install pipenv && npm install x\n"},
        {".github/workflows/ci.yml": "run: pip install --require-hashes -r pins/t.txt && npm ci\n"},
    ),
    "scan_gates_registry.py": (
        {
            "gates.yaml": "version: 1\ngates:\n"
            "  - id: g\n    title: t\n    kind: job\n    enforced_by: {job: nowhere}\n",
            ".github/workflows/ci.yml": "jobs:\n  real:\n    steps:\n      - run: x\n",
        },
        {
            "gates.yaml": "version: 1\ngates:\n"
            "  - id: g\n    title: t\n    kind: job\n    enforced_by: {job: real}\n",
            ".github/workflows/ci.yml": "jobs:\n  real:\n    steps:\n      - run: x\n",
        },
    ),
    "scan_adr_index.py": (
        {"docs/adr/0001-first.md": "# x\n", "docs/adr/README.md": "ว่าง\n"},
        {"docs/adr/0001-first.md": "# x\n", "docs/adr/README.md": "[0001](0001-first.md)\n"},
    ),
}


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def portable_ids() -> set[str]:
    gates = yaml.safe_load(GATES.read_text(encoding="utf-8"))["gates"]
    return {g["id"] for g in gates if g.get("portable")}


def test_the_overlay_covers_every_portable_gate_and_nothing_else(manifest, portable_ids):
    """สองทิศ — กฎสากลที่ไม่มี enforcement ใน overlay คือคำขวัญ ไม่ใช่กฎ"""
    covered = set(manifest["gates"])
    assert covered == portable_ids, (
        f"ขาด: {sorted(portable_ids - covered)} · เกิน: {sorted(covered - portable_ids)}"
    )


def test_everything_the_manifest_ships_exists(manifest):
    """install อ่านจาก manifest — รายการที่ชี้ไฟล์ที่ไม่มีคือการติดตั้งที่พังกลางทาง"""
    missing = [name for name in manifest["ship"] if not (OVERLAY / name).is_file()]
    assert not missing, f"ship ชี้ไฟล์ที่ไม่มี: {missing}"

    scripts = {e["script"] for e in manifest["gates"].values() if e["kind"] == "scan"}
    unshipped = sorted(scripts - set(manifest["ship"]))
    assert not unshipped, f"scan ที่ไม่อยู่ในรายการ ship: {unshipped}"


def _spawn(*command: str) -> subprocess.CompletedProcess:
    """ยิงเครื่องมือด้วย interpreter เปล่า เหมือนที่โปรเจกต์ปลายทางรันจริง

    การเรียก subprocess ของไฟล์นี้ผ่านที่นี่ที่เดียว — คำสั่งประกอบจาก path ที่
    เทสต์สร้างเอง ไม่มีอะไรมาจากภายนอก จึงปิด S603 ได้จุดเดียวพร้อมเหตุผล
    แทนที่จะโรยไว้ทุกจุดที่เรียก
    """
    return subprocess.run(  # noqa: S603 — คำสั่งประกอบจาก path ของเทสต์เอง ไม่มี input ภายนอก
        [sys.executable, *command], capture_output=True, text=True, check=False
    )


def _run(script: str, tree: dict[str, str], tmp: pathlib.Path) -> subprocess.CompletedProcess:
    (tmp / "scaffold.json").write_text("{}", encoding="utf-8")
    for name, content in tree.items():
        path = tmp / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return _spawn(str(OVERLAY / "checks" / script), str(tmp))


@pytest.mark.parametrize("script", sorted(CASES), ids=lambda s: s.removesuffix(".py"))
def test_each_checker_flags_the_planted_violation(script, tmp_path):
    bad, _ = CASES[script]
    result = _run(script, bad, tmp_path)
    assert result.returncode == 1, f"ควรพบแต่ไม่พบ — stdout: {result.stdout}"
    assert result.stdout.strip(), "พบแต่ไม่บอกว่าเจออะไรที่ไหน — รายงานว่างช่วยใครไม่ได้"


@pytest.mark.parametrize("script", sorted(CASES), ids=lambda s: s.removesuffix(".py"))
def test_each_checker_stays_quiet_on_clean_input(script, tmp_path):
    _, clean = CASES[script]
    result = _run(script, clean, tmp_path)
    assert result.returncode == 0, f"เตือนลวงบนของสะอาด: {result.stdout}"


def test_install_then_doctor_and_the_doctor_notices_missing_pieces(tmp_path):
    """ติดตั้งแล้วต้อง --installed เขียว · ถอดไฟล์ที่ติดตั้งแล้วต้องแดง"""
    target = tmp_path / "target"
    install = _spawn(str(OVERLAY / "install.py"), str(target))
    assert install.returncode == 0, install.stderr

    doctor = target / "tools" / "gates_doctor.py"
    ok = _spawn(str(doctor), "--installed")
    assert ok.returncode == 0

    (target / "tools" / "checks" / "scan_adr_index.py").unlink()
    broken = _spawn(str(doctor), "--installed")
    assert broken.returncode == 1, "ไฟล์หายแล้ว doctor ยังบอกว่าติดตั้งครบ"


def test_a_gutted_overlay_refuses_to_install(tmp_path):
    """ลบไฟล์ออกจาก overlay หนึ่งตัว install ต้องล้มดัง ๆ ไม่ใช่ติดตั้งครึ่งเดียว"""
    import shutil

    clone = tmp_path / "overlay"
    shutil.copytree(OVERLAY, clone)
    (clone / "checks" / "scan_service_layer.py").unlink()

    result = _spawn(str(clone / "install.py"), str(tmp_path / "t"))
    assert result.returncode == 1
    assert "ไม่ครบ" in result.stderr


def test_the_shipped_preflight_is_the_same_file_we_use_ourselves():
    """สำเนาที่ส่งออกต้องตรงไบต์ต่อไบต์กับตัวที่ repo นี้ใช้เอง — ADR 0063

    เครื่องมือที่ปลายทางได้ ต้องเป็นตัวเดียวกับที่เราเดินทุกวัน ไม่ใช่รุ่นที่แยก
    ไปตายอยู่ใน overlay · ถ้าสองไฟล์ต่างกันเมื่อไหร่ แปลว่ามีคนแก้ฝั่งเดียว
    ซึ่งคือกับดักเดียวกับที่ preflight เองถูกสร้างมาปิด (คำสั่งของ CI ที่ถูกลอกไว้)
    """
    ours = (ROOT / "scripts" / "preflight.py").read_bytes()
    shipped = (OVERLAY / "preflight.py").read_bytes()

    assert ours == shipped, (
        "overlays/flask/preflight.py ไม่ตรงกับ scripts/preflight.py — "
        "แก้ตัวใดตัวหนึ่งแล้ว copy ทับอีกตัว (cp scripts/preflight.py overlays/flask/)"
    )


def test_the_installed_preflight_runs_on_a_fresh_project(tmp_path):
    """ติดตั้งลง repo เปล่าแล้ว preflight ต้องเดิน workflow ตั้งต้นได้จริง

    `ci-template.yml` วาง job ชื่อ `scans` และ `scaffold.json.default` ประกาศ
    `preflight_jobs` ให้ตรงกัน — คู่ที่ไม่ตรงกันแปลว่าปลายทางได้เครื่องมือที่
    รันครั้งแรกก็แดงด้วยเรื่องของตัวมันเอง ซึ่งคือเครื่องมือที่ไม่มีใครใช้ต่อ
    """
    target = tmp_path / "fresh"
    install = _spawn(str(OVERLAY / "install.py"), str(target))
    assert install.returncode == 0, install.stderr

    # รันแบบเดียวกับที่ปลายทางรัน
    result = _spawn(str(target / "tools" / "preflight.py"), "--root", str(target))
    assert result.returncode == 0, (
        f"preflight ของปลายทางแดงตั้งแต่ครั้งแรก: {result.stdout}{result.stderr}"
    )
    assert "gates_doctor.py" in result.stdout, result.stdout


def _registry_reader():
    """โหลดตัวอ่าน YAML ที่ checker ส่งไปกับกล่อง — ไฟล์เดี่ยว ไม่ใช่แพ็กเกจ"""
    import importlib.util

    path = OVERLAY / "checks" / "scan_gates_registry.py"
    spec = importlib.util.spec_from_file_location("scan_gates_registry", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_shipped_yaml_reader_agrees_with_pyyaml_on_our_own_files():
    """ตัวอ่านสับเซต (stdlib ล้วน) ต้องอ่านได้ตรงกับ pyyaml บนไฟล์จริงที่ใหญ่ที่สุดที่เรามี

    ปลายทางไม่มี pyyaml ให้พึ่ง checker จึงอ่าน YAML เอง — และตัวอ่านที่เขียนเอง
    คือที่ที่ "เขียวเพราะอ่านไม่ออก" เกิดได้ง่ายที่สุด · เทียบกับของจริงบน
    `gates.yaml` (108 gate) และ workflow ทุกไฟล์ **เฉพาะฟิลด์ที่ checker อ่านจริง**
    — นั่นคือขอบเขตที่มันอ้างว่าอ่านได้ ไม่ใช่ YAML ทั้งภาษา
    """
    reader = _registry_reader()

    text = GATES.read_text(encoding="utf-8")
    fields = ("id", "kind", "title", "enforced_by")
    mine = [{k: g.get(k) for k in fields} for g in reader.load(text)["gates"]]
    theirs = [{k: g.get(k) for k in fields} for g in yaml.safe_load(text)["gates"]]
    assert mine == theirs, "ตัวอ่านของ overlay อ่าน gates.yaml ไม่ตรงกับ pyyaml"

    def steps(document: dict) -> dict[str, list[str]]:
        return {
            job: [s["name"] for s in ((body or {}).get("steps") or []) if s.get("name")]
            for job, body in (document.get("jobs") or {}).items()
        }

    for path in sorted((ROOT / ".github" / "workflows").glob("*.y*ml")):
        raw = path.read_text(encoding="utf-8")
        assert steps(reader.load(raw)) == steps(yaml.safe_load(raw)), (
            f"อ่าน job/step ของ {path.name} ไม่ตรงกับ pyyaml"
        )


def test_the_seed_registry_lists_exactly_the_gates_the_scans_job_enforces(manifest):
    """แม่แบบ `gates.yaml` ต้องตรงกับ scan ที่กล่องส่งไปจริง — สองทิศ

    ดัชนีตั้งต้นที่อ้างด่านที่ไม่ได้ส่งไป (หรือลืมด่านที่ส่งไป) คือดัชนีที่โกหก
    ตั้งแต่นาทีแรกที่ปลายทางเปิดกล่อง ซึ่งเป็นอาการเดียวกับที่ gate นี้มีไว้ปิด
    """
    reader = _registry_reader()
    seeded = {
        g["id"]
        for g in reader.load((OVERLAY / "gates.yaml.default").read_text(encoding="utf-8"))["gates"]
    }
    scans = {gid for gid, entry in manifest["gates"].items() if entry["kind"] == "scan"}
    assert seeded == scans, f"ขาด: {sorted(scans - seeded)} · เกิน: {sorted(seeded - scans)}"


def test_a_fresh_install_starts_with_a_registry_that_is_already_true(tmp_path):
    """เปิดกล่องแล้วต้องมีดัชนีจริงที่ผ่านด่านของตัวเองทันที ไม่ใช่คำสั่งให้ไปสร้างเอง

    กฎ 80 กว่าข้อในกล่องลงท้ายว่า "ลงทะเบียนใน gates.yaml ของโปรเจกต์" — ถ้า
    กล่องไม่มีไฟล์นั้น คำสั่งนั้นก็เป็นร้อยแก้ว (audit r23 ข้อ 3)
    """
    target = tmp_path / "fresh"
    install = _spawn(str(OVERLAY / "install.py"), str(target))
    assert install.returncode == 0, install.stderr
    assert (target / "gates.yaml").is_file(), "ติดตั้งแล้วยังไม่มีดัชนี gate"

    result = _spawn(str(target / "tools" / "checks" / "scan_gates_registry.py"), str(target))
    assert result.returncode == 0, f"ดัชนีตั้งต้นไม่ผ่านด่านของตัวเอง: {result.stdout}"
    assert "NA" not in result.stdout, f"ดัชนีตั้งต้นถูกข้ามแทนที่จะถูกตรวจ: {result.stdout}"


# ความจริงที่งอกขึ้นในปลายทางโดยไม่มีใครลงทะเบียน — คนละทิศกัน ต้องแดงทั้งคู่
DRIFTS = {
    "job-ใหม่": (".github/workflows/gates.yml", EXTRA_JOB, "extra"),
    "ไฟล์เทสต์ใหม่": ("tests/test_new.py", "def test_x(): pass\n", "tests/test_new.py"),
}


@pytest.mark.parametrize("drift", sorted(DRIFTS))
def test_the_registry_gate_sees_what_nobody_registered(drift, tmp_path):
    """ทิศกลับต้องแดงจริงในปลายทาง — ของที่งอกขึ้นแล้วไม่มี gate คือของที่หายจากดัชนี

    เคส planted ข้างบนพิสูจน์ว่า checker แดงเป็น แต่พิสูจน์แค่ทิศเดียว (gate ที่
    ชี้ไป job ผี) · ทิศที่กฎชนิด `suite` อีก 83 ข้อพึ่งอยู่จริงคือ**ทิศกลับ** —
    เขียนเทสต์แล้วลืมลงทะเบียน ต้องดัง · และต้องดังกับ**ของที่ติดตั้งจริง**
    ซึ่งคือรูปที่ปลายทางเจอ (ADR 0071)
    """
    name, addition, expected = DRIFTS[drift]
    target = tmp_path / "fresh"
    _spawn(str(OVERLAY / "install.py"), str(target))
    path = target / name
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    path.write_text(existing + addition, encoding="utf-8")

    result = _spawn(str(target / "tools" / "checks" / "scan_gates_registry.py"), str(target))
    assert result.returncode == 1, f"{drift} ไม่มี gate แต่ด่านยังเขียว: {result.stdout}"
    assert expected in result.stdout, result.stdout
