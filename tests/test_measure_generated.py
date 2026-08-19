"""เครื่องมือวัดของการทดลองเฟส 12 ต้องถูกวัดด้วย — audit รอบ 17

`scripts/measure_generated.py` ผลิตตัวเลขใน `docs/comparison/` ซึ่งเป็นหลักฐาน
ของคำถามใหญ่ที่สุดของโปรเจกต์ ("กฎที่ export ออกไปเปลี่ยนโค้ดที่ถูกเขียนจริงไหม")
· รอบ 17 วัดได้ว่ามัน **ไม่มีเทสต์เลยสักตัว · 0% coverage · ไม่ถูกเรียกใน CI**
ขณะที่คู่หูของมัน (`asvs_probe.py`) มีเทสต์ 15 ตัวและ fixture สามสำนวน

ด่านที่มีอยู่ (`tests/test_asvs_probe.py`) พิสูจน์ว่า *รายงานตรงกับไฟล์ผล* —
ไม่ได้พิสูจน์ว่า *ไฟล์ผลตรงกับแอปที่วัด* · ระยะห่างระหว่างสองประโยคนั้นคือช่องว่าง
ที่ไฟล์นี้เริ่มปิด

**ไฟล์นี้เป็นชั้นแรก** (โครงของผลลัพธ์ + กรณีว่าง) · ชั้นที่สองซึ่งฝังคำตอบไว้
ล่วงหน้าแล้ววัดว่าตัวเลขตรง อยู่ใน audit รอบ 17 ข้อ 2
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
        assert set(row["gates"].values()) <= {"ok", "na", "finding"}


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
