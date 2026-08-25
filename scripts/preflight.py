"""preflight — เดินด่านของ CI บนเครื่องตัวเอง โดยอ่านคำสั่งจาก workflow

**ตัวจริงไม่ได้อยู่ที่นี่แล้ว** — มันคือ `verifiable_gates.preflight` ใน submodule
`vendor/verifiable-gates` (ADR 0077) · ไฟล์นี้เหลือหน้าที่เดียวคือชี้รากของ tree
แล้วส่งต่อ argument ที่เหลือ · job ที่จะเดินยังมาจาก `scaffold.json` คีย์
`preflight_jobs` เหมือนเดิม และคำสั่งยังถูกอ่านจาก workflow จริง ไม่ได้ลอกมาเก็บ

ใช้:
    pipenv run python scripts/preflight.py                 # ทุก job ที่ประกาศไว้
    pipenv run python scripts/preflight.py --only lint     # เฉพาะ job นั้น (ซ้ำได้)
    pipenv run python scripts/preflight.py --base main     # ฐานของ diff-cover

บทบาท: decider — ตัดสินผ่าน/ไม่ผ่าน — หลักฐานคือเทสต์ที่ฝังความผิดแล้วต้องจับได้ · ของสะอาดต้องไม่ถูกจับ
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vendor" / "verifiable-gates" / "src"))

from verifiable_gates import preflight  # noqa: E402 — ต้องต่อ path ให้ vendor ก่อน import


def main(argv: list[str] | None = None) -> int:
    """เติมรากของ repo นี้ แล้วปล่อยให้ preflight ใน vendor เดินด่าน"""
    given = list(sys.argv[1:] if argv is None else argv)
    return preflight.main(["--root", str(ROOT), *given])


if __name__ == "__main__":
    sys.exit(main())
