"""เครื่องมือวัดของการทดลองเฟส 12 ต้องถูกวัดด้วย — audit รอบ 17

`scripts/measure_generated.py` ผลิตตัวเลขใน `docs/comparison/` ซึ่งเป็นหลักฐาน
ของคำถามใหญ่ที่สุดของโปรเจกต์ ("กฎที่ export ออกไปเปลี่ยนโค้ดที่ถูกเขียนจริงไหม")
· รอบ 17 วัดได้ว่ามัน **ไม่มีเทสต์เลยสักตัว · 0% coverage · ไม่ถูกเรียกใน CI**
ขณะที่คู่หูของมัน (`asvs_probe.py`) มีเทสต์ 15 ตัวและ fixture สามสำนวน

ด่านที่มีอยู่ (`tests/test_asvs_probe.py`) พิสูจน์ว่า *รายงานตรงกับไฟล์ผล* —
ไม่ได้พิสูจน์ว่า *ไฟล์ผลตรงกับแอปที่วัด* · ระยะห่างระหว่างสองประโยคนั้นคือช่องว่าง
ที่ไฟล์นี้เริ่มปิด

**ชั้นแรก** คือโครงของผลลัพธ์กับกรณีว่าง · **ชั้นที่สอง** (ข้อ 2 ของรอบเดียวกัน)
คือ fixture ที่ **ฝังคำตอบไว้ล่วงหน้า** แล้ววัดว่าตัวเลขที่นับได้ตรงกับที่ฝัง —
ยาชุดเดียวกับที่ `asvs_probe` ได้รับมาตั้งแต่เฟส 12
"""

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "measure_generated.py"


def _run(target: pathlib.Path, output: pathlib.Path) -> subprocess.CompletedProcess:
    """ยิงผ่าน subprocess เหมือนที่คนใช้จริง — ไม่ใช่ import แล้วเรียกฟังก์ชันภายใน"""
    return subprocess.run(  # noqa: S603 — คำสั่งคงที่ + interpreter ของ venv เดียวกัน
        [sys.executable, str(SCRIPT), str(target), "--output", str(output)],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
        cwd=ROOT,
    )


def test_an_empty_root_measures_nothing_and_says_so(tmp_path):
    """ไดเรกทอรีที่ไม่มีแอปเลย ต้องได้ผลว่าง ไม่ใช่ศูนย์ที่ดูเหมือนวัดแล้ว"""
    output = tmp_path / "result.json"
    done = _run(tmp_path, output)

    assert done.returncode == 0, f"ล้มด้วย: {done.stderr[-400:]}"
    assert json.loads(output.read_text(encoding="utf-8")) == []


def test_it_measures_each_app_it_finds_on_both_sides(tmp_path):
    """โครงของผลลัพธ์คือสิ่งที่รายงานทั้งใบตั้งอยู่บน — เปลี่ยนเมื่อไหร่ต้องรู้ตัว"""
    for side in ("ctrl", "skill"):
        app = tmp_path / side / "app1"
        app.mkdir(parents=True)
        (app / "main.py").write_text("print('hello')\n", encoding="utf-8")

    output = tmp_path / "result.json"
    done = _run(tmp_path, output)
    assert done.returncode == 0, f"ล้มด้วย: {done.stderr[-400:]}"

    rows = json.loads(output.read_text(encoding="utf-8"))
    assert {(r["side"], r["app"]) for r in rows} == {("ctrl", "app1"), ("skill", "app1")}
    for row in rows:
        assert row["py_lines"] >= 1, "ไม่ได้นับบรรทัดของไฟล์ python ที่มีอยู่จริง"
        for field in ("gate_findings", "gates_na", "gates", "asvs", "semgrep"):
            assert field in row, f"ผลลัพธ์ขาดช่อง {field} ซึ่งรายงานอ้างถึง"

        # **`na` ต้องแยกจาก `ok` เสมอ** — หัวไฟล์ของสคริปต์ประกาศข้อนี้ไว้เอง:
        # "ไม่มีของให้ตรวจ" ไม่ใช่ "ตรวจแล้วสะอาด" · แอปเปล่า ๆ ที่มีไฟล์เดียว
        # จึงต้องมี gate ที่ตอบ `na` อยู่จริง ไม่ใช่ถูกนับเป็นผ่านทั้งหมด
        assert row["gates_na"], "แอปที่ไม่มี Dockerfile/workflow/ADR เลย แต่ไม่มี gate ไหนตอบ na"
        # ค่าของ gate เป็นสามอย่างเท่านั้น: `ok` · `na` · **จำนวน finding เป็นเลข**
        # (เดิมเขียนเทียบกับสตริง `"finding"` ซึ่งไม่มีอยู่จริง — ผ่านมาได้เพราะ
        # แอปในเทสต์นี้สะอาด · ชั้นที่สองข้างล่างฝัง finding จริงจึงเจอ)
        assert all(v in ("ok", "na") or isinstance(v, int) for v in row["gates"].values())


def test_missing_semgrep_is_reported_as_skipped_not_as_zero(tmp_path):
    """**ศูนย์ที่แปลว่า "ไม่ได้วัด" คือตัวเลขที่โกหกเงียบที่สุดในไฟล์นี้**

    หัวไฟล์ของสคริปต์ประกาศข้อนี้ไว้เอง ("ไม่ตั้ง = รายงานว่าข้าม ไม่ใช่ 0")
    แต่ไม่มีอะไรบังคับจนถึงรอบ 17
    """
    app = tmp_path / "ctrl" / "app1"
    app.mkdir(parents=True)
    (app / "main.py").write_text("x = 1\n", encoding="utf-8")

    output = tmp_path / "result.json"
    done = _run(tmp_path, output)
    assert done.returncode == 0

    rows = json.loads(output.read_text(encoding="utf-8"))
    assert rows[0]["semgrep"] != 0, "ไม่มี semgrep แล้วรายงาน 0 — อ่านไม่ออกว่าสะอาดหรือไม่ได้วัด"


# =========================================================================
# ชั้นที่สอง — **ฝังคำตอบไว้ก่อน แล้ววัดว่าตัวเลขตรง** (audit รอบ 17 ข้อ 2)
#
# ชั้นแรกพิสูจน์ว่า "มีช่องนั้นในผลลัพธ์" ซึ่งยังเข้ากันได้กับตัวนับที่นับผิด
# ทั้งใบ · ข้างล่างนี้สร้างแอปที่**รู้คำตอบล่วงหน้า** แล้วเทียบตัวเลขตรง ๆ


def _app(root: pathlib.Path, side: str, name: str) -> pathlib.Path:
    """แอปเปล่าใต้ `<root>/<side>/<name>` — ผู้เรียกเติมของที่อยากให้ถูกนับเอง"""
    app = root / side / name
    (app / "app").mkdir(parents=True)
    return app


def test_the_number_of_findings_is_the_number_that_was_planted(tmp_path):
    """ฝัง finding ที่นับได้ด้วยมือ 2 + 3 → ตัวเลขต้องเป็น 2 · 3 · และรวม 5

    เป็นข้อที่รายงานทั้งใบตั้งอยู่บน (`docs/comparison/` เทียบ "gate ที่พบ"
    ของสองฝั่ง) — ตัวนับที่นับเกินหรือขาดไปทั้งแถว จะทำให้ข้อสรุปกลับด้านได้
    โดยไม่มีอะไรฟ้อง เพราะไม่มีใครรู้คำตอบที่ถูกอยู่ก่อน
    """
    app = _app(tmp_path, "ctrl", "app1")
    (app / "main.py").write_text(
        "import flask\napp = flask.Flask(__name__)\napp.run(debug=True)\napp.run(debug=True)\n",
        encoding="utf-8",
    )
    (app / "app" / "store.py").write_text(
        "def a(s, x):\n    session.delete(x)\n\n"
        "def b(s, x):\n    session.delete(x)\n\n"
        "def c(s, x):\n    session.delete(x)\n",
        encoding="utf-8",
    )

    output = tmp_path / "result.json"
    done = _run(tmp_path, output)
    assert done.returncode == 0, f"ล้มด้วย: {done.stderr[-400:]}"

    (row,) = json.loads(output.read_text(encoding="utf-8"))
    assert row["gates"]["entrypoint_debug"] == 2, row["gates"]
    assert row["gates"]["write_discipline"] == 3, row["gates"]
    assert row["gate_findings"] == 5, row["gates"]


def test_a_gate_with_material_to_judge_says_ok_not_na(tmp_path):
    """`na` ต้องมาจาก "ไม่มีของให้ตรวจ" เท่านั้น — ของสะอาดต้องนับเป็น `ok`

    ทิศกลับของเทสต์ `na` ในชั้นแรก · ถ้าสองสถานะนี้ยุบเข้าหากันเมื่อไหร่
    แอปที่ไม่มีอะไรเลยจะดูเท่ากับแอปที่ผ่านทุกด่าน ซึ่งเป็นข้อสรุปที่กลับด้าน
    """
    app = _app(tmp_path, "ctrl", "clean")
    (app / "main.py").write_text("import flask\napp = flask.Flask(__name__)\n", encoding="utf-8")
    (app / "app" / "store.py").write_text("def keep(x):\n    return x\n", encoding="utf-8")

    output = tmp_path / "result.json"
    assert _run(tmp_path, output).returncode == 0

    (row,) = json.loads(output.read_text(encoding="utf-8"))
    assert row["gates"]["entrypoint_debug"] == "ok", "มี entrypoint ให้ตรวจ แต่ตอบ na"
    assert row["gates"]["write_discipline"] == "ok", "มีซอร์สให้ตรวจ แต่ตอบ na"
    assert "entrypoint_debug" not in row["gates_na"]
    assert row["gate_findings"] == 0


def test_the_asvs_answers_are_the_ones_that_were_planted(tmp_path):
    """ฝังข้อที่ต้อง "ไม่ผ่าน" สองข้อ → ต้องโผล่ใน `asvs_fail` ทั้งคู่"""
    app = _app(tmp_path, "skill", "leaky")
    (app / "main.py").write_text(
        'import flask\napp = flask.Flask(__name__)\napp.config["SECRET_KEY"] = "hardcoded-secret"\n'
        "app.run(debug=True)\n",
        encoding="utf-8",
    )

    output = tmp_path / "result.json"
    assert _run(tmp_path, output).returncode == 0

    (row,) = json.loads(output.read_text(encoding="utf-8"))
    assert "V14.1.3-no-debug-console" in row["asvs_fail"], row["asvs"]
    assert "V6.4.1-secret-not-hardcoded" in row["asvs_fail"], row["asvs"]
    assert row["asvs_pass"] == sum(1 for v in row["asvs"].values() if v is True)


def test_what_the_overlay_installed_is_not_counted_as_the_agents_work(tmp_path):
    """**ผู้วัดมีส่วนได้เสียกับผล** — ของที่ `install.py` วางให้ ต้องไม่ถูกนับ

    `tools/` คือ checker ของเราเอง หลายร้อยบรรทัด · นับเข้าไปเท่ากับเอาของเรา
    ไปบวกแต้มให้ฝั่ง skill ฝ่ายเดียว แล้วตัวเลข "บรรทัด .py" ในรายงานเปรียบเทียบ
    จะเชียร์ฝั่งที่เราอยากให้ชนะ
    """
    app = _app(tmp_path, "skill", "app1")
    (app / "main.py").write_text("x = 1\n", encoding="utf-8")
    (app / "tools").mkdir()
    (app / "tools" / "overlay.json").write_text("{}", encoding="utf-8")
    (app / "tools" / "scan_something.py").write_text("y = 2\n" * 500, encoding="utf-8")
    (app / "scaffold.json").write_text("{}", encoding="utf-8")

    output = tmp_path / "result.json"
    assert _run(tmp_path, output).returncode == 0

    (row,) = json.loads(output.read_text(encoding="utf-8"))
    assert row["overlay_installed"] is True, "ไม่รู้ด้วยซ้ำว่าแอปนี้ติดตั้ง overlay ไว้"
    assert row["py_lines"] == 1, f"นับของที่ overlay วางให้เป็นผลงานของ agent: {row['py_lines']}"
    assert row["py_files"] == 1


def test_an_app_that_never_installed_the_overlay_keeps_all_of_its_own_files(tmp_path):
    """ทิศกลับ — การตัดต้องผูกกับเครื่องหมายของ overlay ไม่ใช่กับชื่อไดเรกทอรี

    ฝั่ง ctrl ที่บังเอิญมีไดเรกทอรีชื่อ `tools/` ของตัวเอง ต้องไม่ถูกหักบรรทัดทิ้ง
    ไม่งั้นการตัดที่ตั้งใจให้ "เข้มกับฝั่ง skill" กลายเป็นการลงโทษอีกฝั่งแทน
    """
    app = _app(tmp_path, "ctrl", "app1")
    (app / "main.py").write_text("x = 1\n", encoding="utf-8")
    (app / "tools").mkdir()
    (app / "tools" / "helper.py").write_text("y = 2\n" * 9, encoding="utf-8")

    output = tmp_path / "result.json"
    assert _run(tmp_path, output).returncode == 0

    (row,) = json.loads(output.read_text(encoding="utf-8"))
    assert row["overlay_installed"] is False
    assert row["py_lines"] == 10, f"หักบรรทัดของแอปที่ไม่ได้ติดตั้ง overlay: {row['py_lines']}"


def _fake_semgrep(tmp_path: pathlib.Path, body: str) -> pathlib.Path:
    """semgrep ปลอมที่รู้คำตอบล่วงหน้า — ตัวจริงต้องต่อเน็ตและช้าเกินกว่าจะเป็นด่าน"""
    binary = tmp_path / "semgrep-ปลอม"
    binary.write_text(f"#!{sys.executable}\nimport sys\n{body}\n", encoding="utf-8")
    binary.chmod(0o755)
    return binary


def test_the_semgrep_count_is_the_number_of_results_it_reported(tmp_path):
    """ตัวเลขที่รายงานต้องเป็นจำนวน finding ที่ตัวสแกนคืนมา ไม่ใช่ exit code ของมัน

    semgrep คืน exit 1 เมื่อ**เจอ** finding — ตัวอ่านที่สับสนสองอย่างนี้จะรายงาน
    1 เสมอไม่ว่าเจอกี่ข้อ (และรายงานเปรียบเทียบก็จะเท่ากันทั้งสองฝั่งพอดี)
    """
    app = _app(tmp_path, "ctrl", "app1")
    (app / "main.py").write_text("x = 1\n", encoding="utf-8")
    fake = _fake_semgrep(tmp_path, "print('{\"results\": [1, 2, 3, 4]}')\nsys.exit(1)")

    output = tmp_path / "result.json"
    done = subprocess.run(  # noqa: S603 — คำสั่งคงที่ + interpreter ของ venv เดียวกัน
        [
            sys.executable,
            str(SCRIPT),
            str(tmp_path),
            "--output",
            str(output),
            "--semgrep",
            str(fake),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
        cwd=ROOT,
    )
    assert done.returncode == 0, f"ล้มด้วย: {done.stderr[-400:]}"

    (row,) = json.loads(output.read_text(encoding="utf-8"))
    assert row["semgrep"] == 4, row["semgrep"]
    assert "| 4 |" in done.stdout, "ตารางที่คนอ่านไม่ตรงกับ JSON ที่เครื่องอ่าน"


def test_a_broken_scanner_stops_the_measurement_instead_of_reporting_zero(tmp_path):
    """ตัวสแกนที่ล้ม (exit 2) ต้องทำให้การวัดหยุด ไม่ใช่บันทึกว่า "สะอาด"

    หลักเดียวกับ "ไม่มี semgrep = ข้าม ไม่ใช่ 0" ที่หัวไฟล์ประกาศไว้ —
    ต่างกันแค่ตรงที่ครั้งนี้เรามีตัวสแกน แต่มันตอบไม่ได้
    """
    app = _app(tmp_path, "ctrl", "app1")
    (app / "main.py").write_text("x = 1\n", encoding="utf-8")
    fake = _fake_semgrep(tmp_path, 'print("boom", file=sys.stderr)\nsys.exit(2)')

    output = tmp_path / "result.json"
    done = subprocess.run(  # noqa: S603 — คำสั่งคงที่ + interpreter ของ venv เดียวกัน
        [
            sys.executable,
            str(SCRIPT),
            str(tmp_path),
            "--output",
            str(output),
            "--semgrep",
            str(fake),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
        cwd=ROOT,
    )

    assert done.returncode != 0, "ตัวสแกนล้มแล้วยังรายงานว่าวัดสำเร็จ"
    assert not output.exists(), "เขียนไฟล์ผลทั้งที่วัดไม่ครบ"


def test_an_asvs_item_with_nothing_to_judge_is_not_counted_as_a_failure(tmp_path):
    """ "ไม่เกี่ยวข้อง" ต้องไม่ตกไปอยู่กอง "ไม่ผ่าน" — สามกองต้องแบ่งกันครบพอดี

    เจอตอน mutation ของรอบนี้: เปลี่ยน `v is False` เป็น `v is not True` แล้ว
    ทุกเทสต์ยังเขียว ทั้งที่แอปเล็ก ๆ (ไม่มี API · ไม่มีฟอร์ม POST) จะกลายเป็น
    "ตก ASVS เพิ่มอีกสี่ข้อ" ทันที — **ซึ่งลงโทษแอปที่เล็กกว่า ไม่ใช่แอปที่แย่กว่า**
    และรายงานเปรียบเทียบทั้งใบวางอยู่บนการเทียบสองฝั่งที่ขนาดไม่เท่ากัน
    """
    app = _app(tmp_path, "ctrl", "tiny")
    (app / "main.py").write_text("import flask\napp = flask.Flask(__name__)\n", encoding="utf-8")

    output = tmp_path / "result.json"
    assert _run(tmp_path, output).returncode == 0

    (row,) = json.loads(output.read_text(encoding="utf-8"))
    assert None in row["asvs"].values(), "fixture นี้ไม่มีข้อที่ 'ไม่เกี่ยวข้อง' เลย — วัดไม่ตรงจุด"
    assert not set(row["asvs_na"]) & set(row["asvs_fail"]), "ข้อเดียวอยู่สองกองพร้อมกัน"
    assert row["asvs_pass"] + len(row["asvs_fail"]) + len(row["asvs_na"]) == len(row["asvs"]), (
        "สามกองรวมกันไม่เท่าจำนวนข้อทั้งหมด — มีข้อที่ถูกนับซ้ำหรือหายไป"
    )
