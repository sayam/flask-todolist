"""ของที่รันตามเวลา ต้องพิสูจน์ได้ว่ายังยิงอยู่ — **ตัวจริงอยู่ที่ verifiable-gates**

ตัวสำมะโนอยู่ที่ `verifiable_gates.schedule_census` ใน submodule
`vendor/verifiable-gates` (ADR 0077 · ขั้น 3b) · ไฟล์นี้เหลือหน้าที่เดียวคือบอกว่า
รากของ repo นี้อยู่ที่ไหน แล้วส่ง argument ที่เหลือต่อไป

ใช้:
    python3 scripts/schedule_census.py                 # ถาม GitHub ผ่าน gh
    python3 scripts/schedule_census.py --input x.json  # ตัดสินจากไฟล์ (ออฟไลน์)

บทบาท: reader — อ่านแล้วรายงาน — หลักฐานคือตัวเลขที่พิมพ์ต้องตรงกับแหล่ง · ห้ามตัดของทิ้งเงียบ
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vendor" / "verifiable-gates" / "src"))

from verifiable_gates import schedule_census  # noqa: E402 — ต่อ path ให้ vendor ก่อน


def main(argv: list[str] | None = None) -> int:
    """เติมรากของ repo นี้ แล้วปล่อยให้ตัวจริงตัดสิน"""
    given = list(sys.argv[1:] if argv is None else argv)
    return schedule_census.main(["--root", str(ROOT), *given])


if __name__ == "__main__":
    sys.exit(main())
