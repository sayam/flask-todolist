"""วัดแอปที่ถูก generate ในการทดลอง — battery เดียวกันทั้งสามแขน

**ตัวจริงอยู่ที่ verifiable-gates แล้ว** (ADR 0077 · ขั้น 5) —
`verifiable_gates.measure_apps` · ไฟล์นี้เหลือเป็นที่อยู่ที่คนเรียกถึงได้เหมือนเดิม

การทดลองทั้งชุด (spec · รายงาน · ข้อมูลดิบ) ย้ายไป `docs/comparison/` ของ vg
เพราะมันเป็นหลักฐานของข้ออ้างที่ vg เป็นคนอ้าง — ที่นี่เหลือบันทึกการพัฒนา

ใช้: `pipenv run python scripts/measure_generated.py <apps-root> [--output x.json]`
· ตัวสแกนภายนอกส่งด้วย `--scanner` **ไม่ใช่ตัวแปรแวดล้อม**

บทบาท: reader — อ่านแล้วรายงาน — หลักฐานคือตัวเลขที่พิมพ์ต้องตรงกับแหล่ง · ห้ามตัดของทิ้งเงียบ
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vendor" / "verifiable-gates" / "src"))

from verifiable_gates import measure_apps  # noqa: E402 — ต้องต่อ path ให้ vendor ก่อน import

Battery = measure_apps.Battery
measure = measure_apps.measure
run_scans = measure_apps.run_scans
staged = measure_apps.staged


def main(argv: list[str] | None = None) -> int:
    """วัดทุกแอปใต้ root แล้วพิมพ์ตาราง + เขียน JSON"""
    return measure_apps.main(list(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    sys.exit(main())
