"""fail-fix harness — รัน gate จาก `gates.yaml` แล้วคืนผลเป็นของที่เครื่องอ่านได้

**ตัวจริงไม่ได้อยู่ที่นี่แล้ว** — มันคือ `verifiable_gates.harness` ใน submodule
`vendor/verifiable-gates` (ADR 0077) · ไฟล์นี้เหลือหน้าที่เดียวคือชี้ว่าทะเบียน
กับรากของ tree ของ repo นี้อยู่ที่ไหน แล้วส่งต่อ argument ที่เหลือให้มัน

ขอบเขตยังเหมือนเดิมและยังประกาศตรง ๆ: harness รันเฉพาะ gate ชนิด `test` ·
ชนิด `job`/`step` รายงานว่า **ข้ามพร้อมเหตุผล** ไม่ใช่เงียบ เพราะคำสั่งของมัน
อยู่ใน workflow และการลอกมารันคือการสร้างที่ที่สอง (ADR 0039)

ใช้: `pipenv run python scripts/run_gates.py [--only <gate>] [--output <ไฟล์>]`

บทบาท: decider — ตัดสินผ่าน/ไม่ผ่าน — หลักฐานคือเทสต์ที่ฝังความผิดแล้วต้องจับได้ · ของสะอาดต้องไม่ถูกจับ
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vendor" / "verifiable-gates" / "src"))

from verifiable_gates import harness  # noqa: E402 — ต้องต่อ path ให้ vendor ก่อน import


def main(argv: list[str] | None = None) -> int:
    """เติมทะเบียนกับรากของ repo นี้ แล้วปล่อยให้ harness ใน vendor ตัดสิน"""
    given = list(sys.argv[1:] if argv is None else argv)
    return harness.main(["--registry", str(ROOT / "gates.yaml"), "--root", str(ROOT), *given])


if __name__ == "__main__":
    sys.exit(main())
