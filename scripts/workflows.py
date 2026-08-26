"""อ่าน workflow ของ GitHub Actions — **ตัวจริงอยู่ที่ verifiable-gates แล้ว**

ตัวอ่านอยู่ที่ `verifiable_gates.workflows` ใน submodule `vendor/verifiable-gates`
(ADR 0077 · ขั้น 3b) · ไฟล์นี้เหลือไว้เพราะ `audit_posture` กับ `sync_counts`
ยังอยู่ที่นี่และ `import workflows` ตรง ๆ — ทั้งคู่จะย้ายในขั้น 3d/3e

**ต่างจากตัวจริงหนึ่งข้อ**: ที่นั่นรับไดเรกทอรีเป็น argument (bundle ต้องอ่าน
โปรเจกต์ไหนก็ได้) ส่วนที่นี่คง `WORKFLOW_DIR` กับ `all_workflows()` ที่ไม่ต้อง
ใส่อะไร ไว้ให้ผู้เรียกเดิมของ repo นี้เรียกได้เหมือนเดิม

บทบาท: helper — ของใช้ร่วม — หลักฐานคือผู้ใช้งานจริงในโค้ด และเทสต์ของผู้ใช้นั้น
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vendor" / "verifiable-gates" / "src"))

from verifiable_gates import workflows as _real  # noqa: E402 — ต่อ path ให้ vendor ก่อน

WORKFLOW_DIR = _real.workflow_dir(ROOT)

load = _real.load
triggers = _real.triggers
runs_on = _real.runs_on
event_config = _real.event_config
schedules = _real.schedules
jobs = _real.jobs

__all__ = [
    "WORKFLOW_DIR",
    "all_workflows",
    "event_config",
    "jobs",
    "load",
    "runs_on",
    "schedules",
    "triggers",
]


def all_workflows(directory: pathlib.Path | None = None) -> dict[str, dict]:
    """ชื่อไฟล์ → เนื้อ ของ workflow ทุกไฟล์ · ไม่ใส่อะไรคือของ repo นี้"""
    return _real.all_workflows(WORKFLOW_DIR if directory is None else directory)
