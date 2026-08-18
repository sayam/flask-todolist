"""ทุก job ต้องประกาศเวลาที่คาดไว้ — ADR 0067 (audit governance รอบ 11)

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

import pathlib

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW_DIR = ROOT / ".github" / "workflows"

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
