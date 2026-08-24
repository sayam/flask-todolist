"""ทุกอย่างที่ *รอ* ต้องประกาศเพดานเวลา — ADR 0067 (audit governance รอบ 11)

ค่าเริ่มต้นของ GitHub Actions คือ **6 ชั่วโมง** ซึ่งไม่ใช่เพดานที่ใครเลือก มันคือ
เลขที่แปลว่า "ไม่มีเพดาน" ในทางปฏิบัติ · ผลที่ตามมาไม่ใช่เรื่องเวลาเครื่อง แต่เป็น
เรื่องของการตัดสินใจ: **job ที่ค้างจริง กับ job ที่แค่ช้ากว่าปกติ หน้าตาเหมือนกัน**
จนกว่าจะมีใครเขียนไว้ว่ามันควรจบเมื่อไหร่

เกิดขึ้นแล้วจริง 2026-08-18 — `dialect (mysql-8)` ใช้เวลา 30+ นาที (ปกติ 10) แล้ว
ถูกยกเลิกทิ้งทั้งที่เดินอยู่ที่ 92% เพราะคนอ่านแยกสองอย่างนี้ไม่ออก

ที่นี่ตรวจสามอย่าง:

1. **ทุก job ประกาศ `timeout-minutes`** — job ใหม่ที่ลืม = แดง
2. **ค่าอยู่ในช่วงที่ตัดสินได้** — ต่ำกว่า `MIN` คือเพดานที่จะแดงเพราะ runner ช้า
   ไม่ใช่เพราะของเสีย · สูงกว่า `MAX` คือการเขียนคำว่า "ไม่มีเพดาน" ด้วยตัวเลข
3. **เพดานของ job ที่แพงที่สุดต้องไม่ต่ำกว่าที่วัดได้จริง** — กันการตั้งเลขสวย
   ที่ทำให้ด่านแดงเป็นนิสัย ซึ่งจบลงด้วยการที่ทุกคนกด rerun โดยไม่อ่าน

**ทำไมไม่ตรวจว่าเลขตรงกับเวลาที่ job ใช้จริงในแต่ละ run**: เวลาที่วัดได้ขึ้นกับ
runner ที่ได้มาในวันนั้น (วัดจริง: ยี่ห้อเดียวกัน 10 นาที กับ 33 นาที ในวันเดียวกัน)
ด่านที่ผูกกับตัวเลขนั้นจะแดงด้วยเรื่องที่เราแก้ไม่ได้ — สิ่งที่บังคับได้คือ
**มีการตัดสินใจเขียนไว้ไหม** ไม่ใช่ว่าการตัดสินใจนั้นแม่นแค่ไหน
"""

import ast
import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW_DIR = ROOT / ".github" / "workflows"
SCRIPTS_DIR = ROOT / "scripts"

# ต่ำกว่านี้คือเพดานที่จะแดงเพราะวันที่ runner ช้า ไม่ใช่เพราะของเสีย
# (วัดจริง 2026-08-18: job เดียวกันใช้ 10 นาทีกับ 33 นาทีในวันเดียวกัน)
MIN_MINUTES = 10
# สูงกว่านี้คือการเขียนคำว่า "ไม่มีเพดาน" ด้วยตัวเลข — ครึ่งวันของ GitHub คือ 360
MAX_MINUTES = 60

# job ที่แพงที่สุด กับเวลาที่ **วัดได้จริง** ของมัน (นาที) — เพดานต้องเผื่อจากตรงนี้
# ไม่ใช่ต่ำกว่า · อัปเดตเลขนี้เมื่อวัดใหม่แล้วเปลี่ยนจริง พร้อมเหตุผลใน PR เดียวกัน
MEASURED = {"dialects": 33, "test": 6, "bare": 4}


def _workflows() -> dict[str, dict]:
    return {
        path.name: yaml.safe_load(path.read_text(encoding="utf-8"))
        for path in sorted(WORKFLOW_DIR.glob("*.y*ml"))
    }


@pytest.fixture(scope="module")
def jobs() -> dict[str, dict]:
    found = {}
    for name, workflow in _workflows().items():
        for job, body in (workflow.get("jobs") or {}).items():
            found[f"{name}:{job}"] = body
    assert found, "อ่าน job จาก workflow ไม่ได้เลย — ตัวดึงพังหรือเปล่า"
    return found


def test_every_job_declares_a_time_budget(jobs):
    """job ที่ไม่ประกาศเวลา = job ที่ค้างได้หกชั่วโมงโดยดูเหมือนกำลังทำงาน"""
    missing = sorted(key for key, body in jobs.items() if body.get("timeout-minutes") is None)
    assert not missing, (
        f"job ที่ไม่ได้ประกาศ timeout-minutes: {missing}\n"
        "ค่าเริ่มต้นของ GitHub คือ 6 ชั่วโมง ซึ่งไม่ใช่เพดานที่ใครเลือก — "
        "และมันทำให้ 'ค้าง' กับ 'ช้า' แยกจากกันไม่ได้ (ADR 0067)"
    )


def test_every_budget_is_a_number_someone_could_defend(jobs):
    """เพดานที่แคบเกินไปแดงด้วยเรื่องที่เราแก้ไม่ได้ · ที่กว้างเกินไปไม่ใช่เพดาน"""
    for key, body in sorted(jobs.items()):
        budget = body.get("timeout-minutes")
        if budget is None:
            continue  # เทสต์ข้างบนเป็นคนบ่นเรื่องนี้
        assert isinstance(budget, int), f"{key}: timeout-minutes ต้องเป็นจำนวนเต็ม"
        assert MIN_MINUTES <= budget <= MAX_MINUTES, (
            f"{key}: timeout-minutes = {budget} — ต้องอยู่ระหว่าง "
            f"{MIN_MINUTES}–{MAX_MINUTES} นาที (ADR 0067)"
        )


def test_the_expensive_jobs_leave_room_for_a_slow_runner(jobs):
    """เพดานที่ต่ำกว่าที่เคยวัดได้จริง = ด่านที่แดงเป็นนิสัย แล้วไม่มีใครอ่านมันอีก"""
    tight = []
    for job, measured in MEASURED.items():
        budgets = [
            body.get("timeout-minutes") for key, body in jobs.items() if key.endswith(f":{job}")
        ]
        assert budgets, f"ไม่เจอ job {job!r} — เปลี่ยนชื่อแล้วต้องมาแก้ MEASURED ด้วย"
        tight += [f"{job}: เพดาน {b} แต่เคยวัดได้ {measured}" for b in budgets if b and b <= measured]
    assert not tight, "เพดานที่ไม่เผื่อจากของที่วัดได้จริง:\n  " + "\n  ".join(tight)


# ------------------------------------------- คำสั่งที่เครื่องมือของเรายิงออกไป
#
# `subprocess.run` ที่ไม่มี `timeout=` **รอตลอดกาล** · เครื่องมือพวกนี้รันอยู่ใน job
# ของ CI ซึ่งเพิ่งได้เพดานของตัวเองจาก ADR 0067 — แต่เพดานของ job จะถูกกินทั้งก้อน
# โดยคำสั่งเดียวที่ไม่ตอบ แล้วรายงานว่า "job หมดเวลา" ซึ่งชี้ผิดที่


def _subprocess_calls(path: pathlib.Path) -> list[ast.Call]:
    """ทุกจุดที่เรียก `subprocess.run` ในไฟล์เดียว"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
    ]


def test_every_command_we_shell_out_to_declares_a_timeout():
    """คำสั่งที่ไม่มีเพดาน = job ที่ไม่มีวันจบ แม้ job จะมีเพดานของตัวเองแล้ว"""
    unbounded = [
        f"{path.relative_to(ROOT)}:{call.lineno}"
        for path in sorted(SCRIPTS_DIR.glob("*.py"))
        for call in _subprocess_calls(path)
        if not any(keyword.arg == "timeout" for keyword in call.keywords)
    ]
    assert not unbounded, (
        f"subprocess.run ที่ไม่มี timeout=: {unbounded}\n"
        "ค่าเริ่มต้นคือรอตลอดกาล — และเครื่องมือพวกนี้รันใน CI (ADR 0067)"
    )


def test_the_scan_actually_finds_the_calls_it_claims_to_check():
    """ด่านที่นับได้ศูนย์เพราะตัวสแกนพัง จะเขียวเหมือนด่านที่ทุกอย่างเรียบร้อย"""
    found = sum(len(_subprocess_calls(p)) for p in sorted(SCRIPTS_DIR.glob("*.py")))

    assert found >= 10, f"เจอ subprocess.run แค่ {found} จุด — ตัวสแกนน่าจะพัง เพราะของจริงมีมากกว่านั้น"


# ------------------- เพดานระดับ *step* ของขั้นที่เอื้อมออกไปหาเครือข่าย (2026-08-21)
#
# ADR 0067 ตั้งเพดานให้ทุก job แล้ว — ซึ่งทำงานถูกและช่วยไว้จริง: `dialect
# (mariadb-11)` ค้างที่ `pip install` แล้วถูกตัดที่ 45 นาทีแทนที่จะค้าง 6 ชั่วโมง
# ตามค่าเริ่มต้นของ GitHub
#
# **แต่ราคาที่จ่ายคือทั้ง job** — ขั้นติดตั้งที่ปกติใช้ 10–60 วินาที กินงบทั้งใบ
# แล้วงานที่เหลือทั้งหมดหายไปด้วย · เพดานของขั้นเหล่านี้จึงต้องเป็นของมันเอง
# หลักเดียวกับที่ ADR 0067 ให้เหตุผลไว้ที่ระดับ job: "ค้าง" กับ "ช้า" ต้องแยกกันได้
#
# ขอบเขตคือ **ขั้นที่ดึงของจากอินเทอร์เน็ต** เท่านั้น ไม่ใช่ทุก step — ขั้นที่รัน
# แต่โค้ดของเราถูกคุมด้วยเพดานของ job อยู่แล้ว และการบังคับทุกขั้นจะกลายเป็น
# พิธีกรรมที่คนใส่เลขมั่ว ๆ ให้ผ่าน

NETWORK_INSTALL = re.compile(r"\b(pip install|pipenv sync|npm ci|npm install)\b")
STEP_MAX_MINUTES = 15


def _install_steps() -> list[tuple[str, str, dict]]:
    """(workflow, job, step) ของทุกขั้นที่ติดตั้งของจากเครือข่าย"""
    found = []
    for name, workflow in _workflows().items():
        for job, body in (workflow.get("jobs") or {}).items():
            found.extend(
                (name, job, step)
                for step in body.get("steps") or []
                if NETWORK_INSTALL.search(step.get("run") or "")
            )
    return found


def test_every_network_install_step_declares_its_own_ceiling():
    """ขั้นที่รอปลายทางภายนอก ต้องประกาศเพดานเอง — ไม่ใช่ยืมของ job

    เกิดจริง 2026-08-20: `pip install` ค้างจนกิน `timeout-minutes: 45` ของ job
    `dialects` ทั้งใบ แล้ว PR แดงด้วยเรื่องที่ไม่เกี่ยวกับ PR นั้นเลย
    """
    steps = _install_steps()

    assert steps, "ไม่เจอขั้นติดตั้งเลย — ตัวอ่านพังหรือ workflow เปลี่ยนรูปแล้ว"
    bare = [f"{name}:{job}" for name, job, step in steps if step.get("timeout-minutes") is None]

    assert not bare, (
        f"ขั้นที่ติดตั้งของจากเครือข่ายแต่ไม่มีเพดานของตัวเอง: {bare}\n"
        "ใส่ `timeout-minutes:` ให้ขั้นนั้น — เพดานของ job คุ้มทั้งใบ ค้างที่ขั้นเดียว"
        "จึงกินงบของงานที่เหลือทั้งหมด"
    )


def test_a_step_ceiling_is_a_number_someone_could_defend():
    """เพดานของขั้นต้องเล็กกว่าของ job มาก ไม่งั้นมันไม่ได้กันอะไรเพิ่ม"""
    loose = []
    for name, job, step in _install_steps():
        budget = step.get("timeout-minutes")
        assert isinstance(budget, int), f"{name}:{job}: เพดานของขั้นต้องเป็นจำนวนเต็ม"
        if budget > STEP_MAX_MINUTES:
            loose.append(f"{name}:{job} = {budget}")

    assert not loose, (
        f"เพดานของขั้นติดตั้งที่หลวมเกิน {STEP_MAX_MINUTES} นาที: {loose} — "
        "ขั้นพวกนี้วัดได้ 10–60 วินาที เพดานที่ใหญ่กว่าของ job ไม่กี่เท่าไม่ได้กันอะไร"
    )
