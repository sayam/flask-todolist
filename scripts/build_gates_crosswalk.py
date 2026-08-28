"""สร้าง `docs/GATES-ASVS.md` — crosswalk ระหว่าง gate กับข้อ ASVS ที่มัน**หนุนจริง**

**กลไกอยู่ที่ verifiable-gates แล้ว** (ADR 0077 · ขั้น 5 ส่วนสุดท้าย) —
`verifiable_gates.gates_crosswalk` derive ทางเดียวจากหลักฐานในตารางประเมิน ผ่าน
partition ของ `gates.yaml` (ADR 0039 — ทุกไฟล์เทสต์เป็นของ gate ตัวเดียว การ map
จึงไม่กำกวม) · ไฟล์นี้เหลือ**ถ้อยคำภาษาไทย**ของเอกสาร กับพาธของสามไฟล์

ผลพลอยได้ที่ตั้งใจ: เห็นชัดว่าแถวไหน **ผ่านด้วยด่านที่รันทุก push** และแถวไหน
**ผ่านด้วยเหตุผล/เอกสาร** (หลักฐานเป็น ADR หรือไฟล์โค้ด ไม่มีด่านรัน) —
สองอย่างนี้เป็นความเชื่อมั่นคนละระดับ และผู้ตรวจควรเห็นความต่างโดยไม่ต้องไล่อ่านเอง

ใช้: `pipenv run python scripts/build_gates_crosswalk.py` (เขียนไฟล์)
`tests/test_gates.py` เทียบไฟล์ที่ commit กับผล generate ทุกครั้งที่รันเทสต์

บทบาท: generator — สร้างไฟล์ที่ commit ไว้ — หลักฐานคือผลลัพธ์ต้องตรงกับที่ commit (coverage ไม่ใช่ตัววัดของชนิดนี้)
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vendor" / "verifiable-gates" / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import build_asvs_worksheet  # noqa: E402 — เครื่องหมายแบ่งตารางเป็นของ worksheet ตัวเดียว (ต่อ path ให้ scripts/ ก่อน)
from verifiable_gates import (  # noqa: E402 — ต้องต่อ path ให้ vendor ก่อน import
    gates_crosswalk,
    registry,
)

GATES = ROOT / "gates.yaml"
ASVS = ROOT / "docs" / "ASVS.md"
OUT = ROOT / "docs" / "GATES-ASVS.md"

# เครื่องหมายเดียวกับที่ tests/test_asvs.py และ build_asvs_worksheet.py ใช้ — ถือไว้ที่เดียว
ASSESSMENT_MARKER = build_asvs_worksheet.PREAMBLE_END
PASSED = "ผ่าน"

# regex ของหลักฐาน — เป็นสัญญาของ worksheet ทุกใบ จึงอยู่ที่ vg · ชื่อเดิมยังอ้างได้จากที่นี่
TEST_REF = gates_crosswalk.TEST_REF
JOB_REF = gates_crosswalk.JOB_REF

WORDS = gates_crosswalk.Words(
    header="""# Crosswalk: gate ↔ ASVS

**ไฟล์นี้ generate มา ห้ามแก้ด้วยมือ** — สร้างใหม่ด้วย
`pipenv run python scripts/build_gates_crosswalk.py`
(`tests/test_gates.py` เทียบกับผล generate ทุกครั้งที่รันเทสต์)

derive จากหลักฐานในตาราง `docs/ASVS.md`: แถวที่อ้างไฟล์เทสต์หรือ `ci:job`
ถูก map กลับไปหา gate ผ่าน partition ของ `gates.yaml` — ไม่มีการเขียน mapping
มือ จึงไม่มีที่ที่สามให้ drift (ADR 0039)
""",
    summary=(
        'สรุป: แถวที่ประเมินว่า "ผ่าน" {rows} ข้อ · '
        "มี gate หนุน {backed} · "
        "ผ่านด้วยเหตุผล/เอกสาร (ไม่มีด่านรัน) {unbacked}\n"
    ),
    backed_title="## gate → ข้อ ASVS ที่หลักฐานของข้อนั้นชี้มาหา gate นี้\n",
    table_head="| gate | ข้อ ASVS |",
    unbacked_title="## ข้อที่ผ่านด้วยเหตุผล/เอกสาร — ไม่มีด่านรันหนุน\n",
    unbacked_note=(
        "ความเชื่อมั่นคนละระดับกับข้างบน: หลักฐานเป็น ADR/ไฟล์โค้ด/คำอธิบาย "
        "ซึ่งไม่ถูกรันซ้ำทุก push — รายการนี้คือที่ที่ควรมองหา gate ตัวถัดไป\n"
    ),
)


def passed_rows() -> dict[str, str]:
    """แถวที่ประเมินว่า "ผ่าน" → ช่องหลักฐานดิบของแถวนั้น"""
    try:
        return gates_crosswalk.passed_rows(
            ASVS.read_text(encoding="utf-8"), marker=ASSESSMENT_MARKER, passed=PASSED
        )
    except ValueError as problem:
        if "marker" in str(problem):
            raise SystemExit(
                "docs/ASVS.md ไม่มีเครื่องหมายแบ่งตารางประเมิน — โครงเอกสารเปลี่ยนไปแล้ว"
            ) from problem
        raise SystemExit("ไม่เจอแถวที่ผ่านเลย — ตัวอ่านพังหรือเปล่า") from problem


def gate_lookups() -> tuple[dict[str, str], dict[str, list[str]]]:
    """(ไฟล์เทสต์ → gate id, job → gate id ของ kind job/step บน job นั้น)"""
    return gates_crosswalk.gate_lookups(registry.load(GATES))


def crosswalk() -> str:
    """ประกอบเอกสารทั้งใบในถ้อยคำของที่นี่ — ทุกลิสต์เรียงแล้ว ผล generate จึงซ้ำได้ไบต์ต่อไบต์"""
    by_file, by_job = gate_lookups()
    return gates_crosswalk.crosswalk(passed_rows(), by_file, by_job, words=WORDS)


def main() -> int:
    """เขียน crosswalk ทับไฟล์เดิม แล้วบอกว่ามีอะไรเปลี่ยนไหม"""
    fresh = crosswalk()
    changed = not OUT.exists() or OUT.read_text(encoding="utf-8") != fresh
    OUT.write_text(fresh, encoding="utf-8")
    print(f"{'เขียนใหม่' if changed else 'ไม่มีอะไรเปลี่ยน'}: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
