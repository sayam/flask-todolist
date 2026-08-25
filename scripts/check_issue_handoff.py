"""issue ที่ติดป้าย `good first issue` ต้องไม่ถูกปิดเงียบ ๆ — **ตัวจริงอยู่ที่ vg แล้ว**

ตัวตัดสินคือ `verifiable_gates.check_issue_handoff` ใน submodule
`vendor/verifiable-gates` (ADR 0077 · ขั้น 3a) · ไฟล์นี้เหลือหน้าที่เดียวคือเป็น
ที่อยู่ที่ job `lint` เรียกถึงได้ แล้วส่ง argument ต่อไป

เหตุที่ทำให้กฎนี้เกิดยังอยู่ครบใน docstring ของตัวจริง (เหตุการณ์ 2026-08-20)
· กติกาฝั่งคนเขียนอยู่ใน `CONTRIBUTING.md` เหมือนเดิม

บทบาท: decider — ตัดสินผ่าน/ไม่ผ่าน — หลักฐานคือเทสต์ที่ฝังความผิดแล้วต้องจับได้ · ของสะอาดต้องไม่ถูกจับ
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vendor" / "verifiable-gates" / "src"))

from verifiable_gates import check_issue_handoff  # noqa: E402 — ต่อ path ให้ vendor ก่อน

LABEL = check_issue_handoff.LABEL
problems = check_issue_handoff.problems


def main(argv: list[str] | None = None) -> int:
    return check_issue_handoff.main(list(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    raise SystemExit(main())
