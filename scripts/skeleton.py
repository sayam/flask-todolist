"""พื้นผิว API ของไฟล์ Python — **ตัวจริงอยู่ที่ verifiable-gates แล้ว**

ตัวอ่านอยู่ที่ `verifiable_gates.skeleton` ใน submodule `vendor/verifiable-gates`
(ADR 0077 · ขั้น 3b) · ไฟล์นี้เหลือเป็นที่อยู่ที่คนกับ agent เรียกถึงได้เหมือนเดิม

ใช้:
    python scripts/skeleton.py app/models.py
    python scripts/skeleton.py app/services
    python scripts/skeleton.py app/models.py --private

บทบาท: reader — อ่านแล้วรายงาน ไม่ตัดสินผ่าน/ไม่ผ่าน และไม่แก้อะไรเลย
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vendor" / "verifiable-gates" / "src"))

from verifiable_gates import skeleton  # noqa: E402 — ต้องต่อ path ให้ vendor ก่อน import

Symbol = skeleton.Symbol
symbols = skeleton.symbols
surface = skeleton.surface
render = skeleton.render


def main(argv: list[str] | None = None) -> int:
    return skeleton.main(list(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    raise SystemExit(main())
