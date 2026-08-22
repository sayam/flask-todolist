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


def _run(script: str, tree: dict[str, str], tmp: pathlib.Path) -> subprocess.CompletedProcess:
    (tmp / "scaffold.json").write_text("{}", encoding="utf-8")
    for name, content in tree.items():
        path = tmp / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return subprocess.run(  # noqa: S603 — ยิง checker เหมือนที่ปลายทางรันจริง
        [sys.executable, str(OVERLAY / "checks" / script), str(tmp)],
        capture_output=True,
        text=True,
        check=False,
    )


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
    install = subprocess.run(  # noqa: S603 - trusted executable and input
        [sys.executable, str(OVERLAY / "install.py"), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert install.returncode == 0, install.stderr

    doctor = target / "tools" / "gates_doctor.py"
    ok = subprocess.run(  # noqa: S603 - trusted executable and input
        [sys.executable, str(doctor), "--installed"], capture_output=True, check=False
    )
    assert ok.returncode == 0

    (target / "tools" / "checks" / "scan_adr_index.py").unlink()
    broken = subprocess.run(  # noqa: S603 - trusted executable and input
        [sys.executable, str(doctor), "--installed"], capture_output=True, text=True, check=False
    )
    assert broken.returncode == 1, "ไฟล์หายแล้ว doctor ยังบอกว่าติดตั้งครบ"


def test_a_gutted_overlay_refuses_to_install(tmp_path):
    """ลบไฟล์ออกจาก overlay หนึ่งตัว install ต้องล้มดัง ๆ ไม่ใช่ติดตั้งครึ่งเดียว"""
    import shutil

    clone = tmp_path / "overlay"
    shutil.copytree(OVERLAY, clone)
    (clone / "checks" / "scan_service_layer.py").unlink()

    result = subprocess.run(  # noqa: S603 - trusted executable and input
        [sys.executable, str(clone / "install.py"), str(tmp_path / "t")],
        capture_output=True,
        text=True,
        check=False,
    )
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
    install = subprocess.run(  # noqa: S603 - trusted executable and input
        [sys.executable, str(OVERLAY / "install.py"), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert install.returncode == 0, install.stderr

    result = subprocess.run(  # noqa: S603 — รันแบบเดียวกับที่ปลายทางรัน
        [sys.executable, str(target / "tools" / "preflight.py"), "--root", str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        f"preflight ของปลายทางแดงตั้งแต่ครั้งแรก: {result.stdout}{result.stderr}"
    )
    assert "gates_doctor.py" in result.stdout, result.stdout
