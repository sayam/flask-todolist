"""คำสัญญาของผู้เฝ้าต้องสั้นกว่าหน้าต่างเงียบของแพลตฟอร์ม — audit รอบ 26 ข้อ 1

**ปัญหาที่รอบ 26 วัดได้**: gate ที่บล็อกไม่ได้ทั้งห้าตัวของ repo นี้ ถูกบังคับด้วย
job ที่ไม่รันบน `pull_request` — ทางเดียวที่มันได้รันโดยไม่มีใครลงมือคือ `on.schedule`
· และ GitHub เขียนไว้ตรง ๆ ว่า *"In a public repository, scheduled workflows are
automatically disabled when no repository activity has occurred in 60 days."*

ผลคือ `schedules-still-fire` ซึ่งถูกสร้างมาเพื่อจับ **กฎ 60 วันข้อนี้โดยเฉพาะ**
(อ่าน `born_from` ของมันได้) รันอยู่ใน `scorecard.yml` ซึ่งเป็น cron ตัวที่ถูกปิด —
ตัวเฝ้าอยู่ใต้สิ่งที่มันเฝ้า และมันตายในวินาทีเดียวกับที่มีเรื่องให้รายงาน ·
คำสัญญาของมันตอนนั้นคือ **90 วัน** ซึ่งยาวกว่าหน้าต่างที่สร้างความล้มเหลว: ผู้เฝ้า
มาถึงช้ากว่าของที่เฝ้าอย่างน้อยหนึ่งเดือน **โดยไม่ผิดสัญญาสักข้อ**

สิ่งที่ไฟล์นี้บังคับคือข้อเดียว: **ในบรรดา workflow ที่รอดได้ด้วย cron อย่างเดียว
ต้องมีคำสัญญาอย่างน้อยหนึ่งข้อที่สั้นกว่า 60 วัน** — ไม่ต้องทุกข้อ เพราะการลงมือ
หนึ่งครั้งรีเซ็ตนาฬิกาของแพลตฟอร์มให้ทั้ง repo พร้อมกัน คำสัญญาที่สั้นที่สุดจึงเป็น
ตัวที่ค้ำตัวอื่นไว้ทั้งหมด (หลักเดียวกับ `promised_days()` ของ `red_streak_census.py`
ที่หยิบค่าน้อยที่สุดต่อไฟล์ด้วยเหตุผลเดียวกัน)

**ตัวเลข 60 เป็นของ GitHub ไม่ใช่ของเรา** — เทสต์จึงบังคับด้วยว่าเอกสารที่คนอ่าน
ต้องบอกที่มาของมัน ไม่ใช่ปล่อยให้เป็นค่าคงที่ลอย ๆ ในโค้ดที่คนแก้ได้โดยไม่รู้ว่า
กำลังแก้อะไร (ADR 0074)
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

from scripts import workflows

ROOT = pathlib.Path(__file__).resolve().parent.parent
GATES = ROOT / "gates.yaml"
WORKFLOWS = ROOT / ".github" / "workflows"
CADENCE_DOC = ROOT / "docs" / "SECURITY-CADENCE.md"

# **ค่าของ GitHub ไม่ใช่ของเรา** — docs.github.com, หัวข้อ `schedule`:
# "In a public repository, scheduled workflows are automatically disabled when
# no repository activity has occurred in 60 days."
PLATFORM_SILENCE_DAYS = 60


@pytest.fixture(scope="module")
def gates() -> list[dict]:
    return list(yaml.safe_load(GATES.read_text(encoding="utf-8"))["gates"])


def _cron_only_jobs() -> dict[str, str]:
    """job → ไฟล์ workflow ของมัน เฉพาะไฟล์ที่ **รอดได้ด้วย cron อย่างเดียว**

    เกณฑ์คือ "ประกาศ `schedule` และไม่รันบน `pull_request`" — ไฟล์ที่รันบน PR มี
    คนกดอยู่แล้วทุกใบ ส่วน `push` ก็ต้องมีคนลงมือเหมือนกัน · เหลือ `schedule`
    เป็นทริกเกอร์เดียวที่เดินเองได้ ซึ่งเป็นทริกเกอร์ตัวที่แพลตฟอร์มปิดให้
    """
    owner: dict[str, str] = {}
    for path in sorted(WORKFLOWS.glob("*.y*ml")):
        workflow = workflows.load(path)
        if not workflows.runs_on(workflow, "schedule"):
            continue
        if workflows.runs_on(workflow, "pull_request"):
            continue
        for job in workflows.jobs(workflow):
            owner[job] = path.name
    return owner


def test_the_repo_still_has_a_watcher_that_only_a_cron_keeps_alive(gates):
    """ทิศกลับ — กฎนี้ต้องไม่กลายเป็นกฎเปล่าโดยไม่มีใครรู้

    ถ้าวันหนึ่งไม่มี workflow ไหนพึ่ง cron แล้ว กฎข้างล่างจะผ่านฟรีตลอดกาลและ
    ไม่มีอะไรบอก · เทสต์นี้ทำให้การหายไปของสมมติฐานเป็นความแดง ไม่ใช่ความเงียบ
    (บทเรียนเดียวกับ audit รอบ 16: ของที่ถูกถอดออกต้องมีคนเห็น)
    """
    owner = _cron_only_jobs()
    assert owner, (
        "ไม่มี workflow ไหนที่พึ่ง `on.schedule` อย่างเดียวแล้ว — "
        "ถ้าตั้งใจถอด ให้ถอดไฟล์นี้กับ gate `watcher-windows-fit-platform-silence` ออกด้วย "
        "ไม่งั้นมันจะเขียวโดยไม่ได้ตรวจอะไร"
    )
    watched = [g for g in gates if (g.get("enforced_by") or {}).get("job") in owner]
    assert watched, (
        f"มี workflow ที่พึ่ง cron ({sorted(set(owner.values()))}) แต่ไม่มี gate ไหนอ้าง job ในนั้นเลย — "
        "ดัชนีกับความจริงหลุดจากกันแล้ว (`tests/test_gates.py` ควรจับได้ก่อนถึงตรงนี้)"
    )


def test_at_least_one_promise_is_shorter_than_the_platform_silence_window(gates):
    """คำสัญญาที่สั้นที่สุดของ workflow ที่พึ่ง cron ต้อง < 60 วัน

    ไม่ได้บังคับทุกข้อให้สั้น เพราะการลงมือครั้งเดียวรีเซ็ตนาฬิกาของแพลตฟอร์มให้
    ทั้ง repo — พอมีข้อหนึ่งที่พาคนกลับมาทันเวลา cron ก็ไม่ถูกปิด แล้วคำสัญญา
    ที่ยาวกว่าของข้ออื่นก็ยังทำได้จริงตามเดิม · **แต่ถ้าไม่มีข้อสั้นสักข้อ ทุกข้อ
    กลายเป็นสัญญาที่ทำไม่ได้พร้อมกัน** เพราะเครื่องที่จะรายงานถูกปิดไปก่อน

    **นับรวมทั้ง repo ไม่ใช่ต่อไฟล์ (แก้ 2026-08-27)** — เดิมจัดกลุ่มตามไฟล์ ซึ่ง
    ให้คำตอบเดียวกันตราบใดที่มีไฟล์ที่พึ่ง cron อยู่ไฟล์เดียว · วันที่ `posture`
    ถูกแยกออกจาก `scorecard.yml` ความต่างก็โผล่ทันที: `scorecard.yml` เหลือคำสัญญา
    365 วันตัวเดียวแล้วแดง ทั้งที่ไม่มีอะไรแย่ลงเลย · **ADR 0074 ตัดสินไว้เองแล้ว**
    ในหัวข้อ "ทางที่ไม่ได้เลือก" ว่า *"นาฬิกาที่กำลังพูดถึงเป็นนาฬิกาเดียวของทั้ง
    repo ไม่ใช่นาฬิกาต่อ gate"* และ *"กฎ 60 วันของ GitHub ปิด schedule **ทุกไฟล์**
    ใน repo นั้นพร้อมกัน ไม่ใช่ทีละไฟล์"* — การจัดกลุ่มต่อไฟล์จึงเป็นการถามคำถาม
    ที่แพลตฟอร์มไม่ได้ถาม และให้ความแดงที่แก้ไม่ได้ด้วยอะไรที่มีความหมาย
    """
    owner = _cron_only_jobs()
    promises = [
        (gate["id"], int(gate["watched_by"]["within_days"]))
        for gate in gates
        if gate.get("watched_by") and (gate.get("enforced_by") or {}).get("job") in owner
    ]
    assert promises, (
        f"มี workflow ที่พึ่ง cron ({sorted(set(owner.values()))}) แต่ไม่มี gate ไหน "
        "ทั้งอ้าง job ในนั้นและมี `watched_by` — ไม่มีคำสัญญาให้วัดแล้ว"
    )

    gate_id, shortest = min(promises, key=lambda row: row[1])
    assert shortest < PLATFORM_SILENCE_DAYS, (
        f"คำสัญญาที่สั้นที่สุดของ repo คือ {shortest} วัน ({gate_id}) แต่ GitHub ปิด "
        f"schedule ให้ repo ที่เงียบครบ {PLATFORM_SILENCE_DAYS} วัน — "
        "ผู้เฝ้าจะมาถึงหลังจากเครื่องที่มันเฝ้าถูกปิดไปแล้ว\n"
        "แก้ที่ `watched_by.within_days` พร้อมกับแถวใน docs/SECURITY-CADENCE.md "
        "ที่มันอ้าง — ตัวเลขที่สั้นลงโดยไม่มีแถวรองรับ `tests/test_gates.py` จับได้ (ADR 0074)"
    )


def test_the_window_says_where_the_number_came_from():
    """เอกสารที่คนอ่านต้องบอกว่า 60 เป็นตัวเลขของใคร

    ค่าคงที่ที่ไม่มีที่มาคือค่าที่ถูกขยับทุกครั้งที่มันขวางทาง — และตัวนี้ขยับไม่ได้
    เพราะมันไม่ใช่ของเรา · เทสต์นี้ผูกตัวเลขในโค้ดกับประโยคที่คนอ่านจะเจอก่อน
    """
    text = CADENCE_DOC.read_text(encoding="utf-8")
    assert f"{PLATFORM_SILENCE_DAYS} วัน" in text, (
        f"docs/SECURITY-CADENCE.md ไม่ได้เอ่ยถึงหน้าต่าง {PLATFORM_SILENCE_DAYS} วันของ GitHub เลย — "
        "แถวรักษาชีพต้องบอกว่าทำไมรอบถึงสั้นขนาดนั้น ไม่งั้นคนถัดไปจะขยายมันคืน"
    )
