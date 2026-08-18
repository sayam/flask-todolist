"""workflow ต้อง **start ได้จริง** ไม่ใช่แค่เป็น YAML ที่ถูกต้อง (audit r9 · ของแถม)

`tests/test_workflow_pinning.py` ตรวจว่า `uses:` ทุกตัวถูกตรึงด้วย SHA และ
`tests/test_ci_pinning.py` ตรวจว่าเครื่องมือถูกตรึงด้วย hash — **แต่ไม่มีตัวไหน
ตรวจว่า GitHub จะยอม start ไฟล์นี้ไหม** · PyYAML ยอมรับทุกคีย์ที่สะกดถูกตาม YAML
ส่วน GitHub ปฏิเสธคีย์ที่ไม่อยู่ใน schema ของมัน แล้ว**ล้มทั้ง run ตั้งแต่ก่อน
สร้าง job** ("This run likely failed because of a workflow file issue")

เกิดขึ้นจริงและอยู่นานข้ามวันโดยไม่มีใครเห็น: `permissions: administration: read`
ใน job `posture` (ADR 0061) ไม่ใช่ scope ที่ `GITHUB_TOKEN` มี — ตั้งแต่ commit
ที่เพิ่ม job นั้น (2026-08-17) **`scorecard.yml` ล้มทุก run รวมบน main** และ
`posture` **ไม่เคยรันเลยสักครั้ง** · มันเงียบได้เพราะ `posture` ไม่ใช่ required
check จึงไม่มีสีแดงบนหน้า PR ใบไหนเลย — **ด่านที่ไม่ได้รัน ให้ผลเหมือนด่านที่
ไม่มีอยู่ ต่างกันแค่เรามีเอกสารที่บอกว่ามันมี**

ที่นี่ตรวจสิ่งที่ตรวจได้โดยไม่ต้องยิง API ของ GitHub:

1. **ทุก scope ใน `permissions:` ต้องอยู่ในรายการที่ GitHub รับ** (ทั้งระดับ
   workflow และระดับ job) · รายการนี้คัดลอกมาจากเอกสารของ GitHub และ**หนึ่ง
   บรรทัดที่สะกดผิดก็ล้มทั้ง workflow** — ราคาของการพลาดสูงกว่าราคาของการตรวจมาก
2. **ทุก job ต้องมี `runs-on` และ `steps`** — job ที่ขาดสองอย่างนี้คือ job ที่
   GitHub ปฏิเสธเหมือนกัน
3. **ทุก workflow ต้องมี `on:`** ที่ไม่ว่าง — ไฟล์ที่ไม่มีทริกเกอร์คือไฟล์ที่
   ไม่มีวันรัน ซึ่งเป็นอีกรูปหนึ่งของด่านที่เขียวเพราะไม่ได้ทำงาน
"""

import pathlib

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.y*ml"))

# scope ที่ `permissions:` ของ GitHub Actions รับได้ (docs: Workflow syntax →
# permissions) · **`administration` ไม่อยู่ในรายการนี้โดยตั้งใจ** — มันเป็นสิทธิ์
# ของ GitHub App/PAT ไม่ใช่ของ GITHUB_TOKEN และเป็นตัวที่ทำให้ scorecard.yml
# ล้มทั้งไฟล์มาแล้ว (run 32097631697 · 22 จาก 30 run ล่าสุดตอนที่จับได้)
PERMISSION_SCOPES = frozenset(
    {
        "actions",
        "attestations",
        "checks",
        "contents",
        "deployments",
        "discussions",
        "id-token",
        "issues",
        "models",
        "packages",
        "pages",
        "pull-requests",
        "repository-projects",
        "security-events",
        "statuses",
    }
)


def _load(path: pathlib.Path) -> dict:
    # `on:` ถูก YAML ตีความเป็น boolean True — เป็นกับดักคลาสสิกของ workflow
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _permission_blocks(workflow: dict) -> list[tuple[str, dict]]:
    blocks = []
    if isinstance(workflow.get("permissions"), dict):
        blocks.append(("(ระดับ workflow)", workflow["permissions"]))
    for name, job in (workflow.get("jobs") or {}).items():
        if isinstance(job.get("permissions"), dict):
            blocks.append((name, job["permissions"]))
    return blocks


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_permission_scope_is_one_github_accepts(path):
    """คีย์เดียวที่ GitHub ไม่รู้จัก = ทั้ง workflow ไม่ start และ job ไม่เกิดสักตัว"""
    for where, block in _permission_blocks(_load(path)):
        unknown = sorted(set(block) - PERMISSION_SCOPES)
        assert not unknown, (
            f"{path.name} · {where}: scope ที่ GitHub ไม่รู้จัก {unknown}\n"
            "ไฟล์จะไม่ start เลย (ไม่ใช่ job เดียวที่แดง) และถ้า workflow นั้นไม่ใช่ "
            "required check ก็จะไม่มีอะไรฟ้องบนหน้า PR — สิทธิ์ที่ GITHUB_TOKEN "
            "ให้ไม่ได้ ต้องมาจาก PAT ใน secret ไม่ใช่จากการประกาศ scope ที่ไม่มีจริง"
        )


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_workflow_declares_a_trigger(path):
    """ไฟล์ที่ไม่มีทริกเกอร์ = ด่านที่ไม่มีวันรัน ซึ่งอ่านจากภายนอกเหมือนด่านที่ผ่าน"""
    workflow = _load(path)
    # PyYAML แปลงคีย์ `on` เป็น True ตาม YAML 1.1
    triggers = workflow.get(True, workflow.get("on"))

    assert triggers, f"{path.name} ไม่มี `on:` — ไม่มีเหตุการณ์ไหนทำให้มันรันได้เลย"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_job_can_actually_run(path):
    """job ที่ขาด `runs-on` หรือ `steps` ถูก GitHub ปฏิเสธทั้งไฟล์เหมือนกัน"""
    for name, job in (_load(path).get("jobs") or {}).items():
        if "uses" in job:  # job ที่เรียก reusable workflow ไม่มี runs-on/steps ของตัวเอง
            continue
        assert job.get("runs-on"), f"{path.name} · job {name} ไม่มี runs-on"
        assert job.get("steps"), f"{path.name} · job {name} ไม่มี steps"
