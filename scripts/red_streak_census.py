"""`within_days` ที่สัญญาไว้ ทำได้จริงไหม — **ตัวจริงอยู่ที่ verifiable-gates**

ตัววัดอยู่ที่ `verifiable_gates.red_streak_census` ใน submodule
`vendor/verifiable-gates` (ADR 0077 · ขั้น 3b) · ไฟล์นี้เหลือหน้าที่เดียวคือบอกว่า
รากกับทะเบียนของ repo นี้อยู่ที่ไหน

**เรียกให้ถูก: สิ่งที่วัดคือ *ขอบบน* ของเวลารับรู้+แก้ ไม่ใช่ MTTA** — มันไม่รู้ว่า
คนเห็นตอนไหน รู้แค่ว่าสภาพแดงยืนอยู่นานแค่ไหน

ใช้:
    python3 scripts/red_streak_census.py                 # ดึงสดผ่าน gh
    python3 scripts/red_streak_census.py --input x.json  # ตัดสินจากไฟล์ (ออฟไลน์)

บทบาท: reader — อ่านแล้วรายงาน — หลักฐานคือตัวเลขที่พิมพ์ต้องตรงกับแหล่ง · ห้ามตัดของทิ้งเงียบ
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vendor" / "verifiable-gates" / "src"))

from verifiable_gates import red_streak_census  # noqa: E402 — ต่อ path ให้ vendor ก่อน


def main(argv: list[str] | None = None) -> int:
    """เติมรากกับทะเบียนของ repo นี้ แล้วปล่อยให้ตัวจริงวัด"""
    given = list(sys.argv[1:] if argv is None else argv)
    return red_streak_census.main(
        ["--root", str(ROOT), "--registry", str(ROOT / "gates.yaml"), *given]
    )


if __name__ == "__main__":
    sys.exit(main())
