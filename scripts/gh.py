"""คุยกับ GitHub ผ่าน `gh` — **ตัวจริงอยู่ที่ verifiable-gates แล้ว**

ตัวห่ออยู่ที่ `verifiable_gates.gh` ใน submodule `vendor/verifiable-gates`
(ADR 0077 · ขั้น 3b) · ไฟล์นี้เหลือไว้เพราะ `audit_posture` กับ `sync_counts`
ยังอยู่ที่นี่และ `import gh` ตรง ๆ — ทั้งคู่จะย้ายในขั้น 3d/3e แล้วไฟล์นี้หายตาม

**ห้ามส่งสตริงที่คนอื่นแต่งเข้ามาเป็น argument** ยังใช้เหมือนเดิม — ผู้เรียก
ประกอบ argument เองจากค่าคงที่ในโค้ด

บทบาท: helper — ตัวช่วยของสภาพแวดล้อม ไม่ตัดสินและไม่ถูกอ้างเป็นหลักฐาน
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vendor" / "verifiable-gates" / "src"))

from verifiable_gates.gh import (  # noqa: E402 — ต้องต่อ path ให้ vendor ก่อน import
    NETWORK_TIMEOUT_SECONDS,
    api,
    run,
)

__all__ = ["NETWORK_TIMEOUT_SECONDS", "api", "run"]
