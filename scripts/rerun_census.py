"""นับความล้มเหลวของ CI **รวมของที่ถูก rerun จนหายไปจากสถิติ** — audit รอบ 7

**กลไกอยู่ที่ verifiable-gates แล้ว** (ADR 0077 · ขั้น 5 · ตัวสุดท้ายของแผนถอด) —
`verifiable_gates.rerun_census` เป็นคนดึง จำแนก และสรุป · **ที่นี่เหลือถ้อยคำ
ภาษาไทยของรายงาน** กับรากของ repo ที่มันต้องอ่าน

`gh run list --json conclusion` รายงานผลของ **attempt ล่าสุด** เท่านั้น · กด rerun
จนเขียวเมื่อไหร่ ความล้มเหลวเดิมหายจากผลลัพธ์ทันที เหลือร่องรอยอยู่แค่ใน
`/runs/<id>/attempts/<n>/jobs` ที่ไม่มีใครเปิดดู — วัดจริง 2026-08-17: เห็น 11 ใบ
ที่ล้ม **ซ่อนอยู่อีก 3 ใบ** (`dast` สองครั้ง · `codeql` หนึ่งครั้ง)

ทิศของความคลาดเคลื่อนอันตรายกว่าตัวเลข: การ rerun ทำให้ job ที่เคยแดง
**กลับไปเป็น "ไม่เคยแดง"** ได้ — ซึ่งเป็นข้อมูลที่ ADR 0059 (`proved_by`) กับแถว
ทบทวน flake ใน `docs/SECURITY-CADENCE.md` ใช้ตัดสินทั้งคู่

ใช้:
    python3 scripts/rerun_census.py --limit 200          # ดึงสดจาก GitHub ผ่าน gh
    python3 scripts/rerun_census.py --input runs.json    # ตัดสินจากไฟล์ (ออฟไลน์)
    python3 scripts/rerun_census.py --max-hidden 0       # ใช้เป็นด่านตอนทบทวนตามรอบ

บทบาท: reader — อ่านแล้วรายงาน — หลักฐานคือตัวเลขที่พิมพ์ต้องตรงกับแหล่ง · ห้ามตัดของทิ้งเงียบ
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vendor" / "verifiable-gates" / "src"))

from verifiable_gates import rerun_census  # noqa: E402 — ต้องต่อ path ให้ vendor ก่อน import

PLATFORM = rerun_census.PLATFORM
OURS = rerun_census.OURS
UNKNOWN = rerun_census.UNKNOWN
classify = rerun_census.classify
census = rerun_census.census

# **ถ้อยคำเป็นของ repo นี้ กลไกเป็นของห้องสมุด** — ชื่อชั้นที่ `classify()` คืนมา
# เป็นค่าเครื่อง (`ours` · `unclassified`) ส่วนคนที่อ่านรายงานของที่นี่อ่านไทย
# การแปลจึงเกิดที่ขอบของการพิมพ์ ไม่ใช่ด้วยการเปลี่ยนค่าที่โค้ดตัดสินด้วย
MESSAGES = {
    "class_platform": "platform",
    "class_ours": "ของเรา",
    "class_unclassified": "ต้องอ่านเอง",
    "no_jobs": "workflow file issue — run นี้ไม่ได้สร้าง job สักตัว",
    "not_started": "{workflow} — ไม่ได้ start",
    "unknown_workflow": "(ไม่ทราบ workflow)",
    "examined": "ตรวจ {count} run",
    "visible": "  ล้มแบบที่ `gh run list` เห็น : {count}",
    "hidden": "  ล้มแล้วถูก rerun จนหายไป    : {count}",
    "by_class": "  ความล้มเหลวชนิด {kind}: {count}",
    "unread": (
        "  ↳ {count} ครั้งจำแนกด้วยเครื่องไม่ได้ — เปิดอ่านเองก่อนนับเข้าเกณฑ์ flake\n"
        '    (ขั้นตอนตัดสิน "ของเราพัง vs โลกพัง" อยู่ใน docs/OPERATIONS.md)'
    ),
    "hidden_mark": "  (ซ่อน {count})",
    "strange_labels": (
        '\n**ชื่อที่แปลงกลับเป็นไอดี job ไม่ได้** — ตัวเลขของมันจะไม่ถูกนับเข้าฝั่ง "ไม่เคยแดง": {names}'
    ),
    "never_red": "\njob ที่ไม่แดงเลยในหน้าต่างนี้ ({count}): {names}",
    "never_red_note": (
        "  หมายเหตุ: {names} ไม่เคยแดงเอง แต่ workflow ของมันล้มก่อนสร้าง job "
        "{count} ครั้ง — คนละเรื่องกับ 'ไม่มีอะไรพัง'"
    ),
    "never_red_footer": (
        "อ่านคู่กับ `guards:` ใน gates.yaml ก่อนตัดสินว่าด่านไหนควรย้ายไปรันตามรอบ (ADR 0062)"
    ),
    "no_proposals": "\nไม่มี gate ไหนที่ยังไม่มีหลักฐานแล้วแดงจริงในหน้าต่างนี้",
    "proposals": "\ngate ที่แดงจริงในหน้าต่างนี้และยังไม่มีหลักฐาน ({count}):",
    "proposal_date": "        date: <วันที่ของ run นั้น>",
    "proposal_caught": "        caught: <มันจับอะไรได้ — เขียนเอง อย่าลอกชื่อเทสต์มาวาง>",
    "proposals_footer": (
        "\n**อ่าน log ก่อนรับทุกแถว** — เทสต์ที่แดงเพราะ fixture พัง ไม่ได้แปลว่า gate จับของเสียได้"
    ),
    "over_ceiling": (
        "\nความล้มเหลวที่ถูก rerun จนหายไปมี {count} ใบ (เพดาน {ceiling}) — "
        "อ่านว่าอะไรแดงก่อนตัดสินว่าเป็น flake"
    ),
    "cannot_read": (
        "อ่านประวัติ run ไม่ได้: {problem}\n**ห้ามให้กลายเป็นการข้ามเงียบ ๆ** — "
        "สำมะโนที่เงียบตอนมองไม่เห็น จะรายงานว่าหน้าต่างสะอาดในวันที่มันไม่เห็นอะไรเลย"
    ),
}


def main(argv: list[str] | None = None) -> int:
    """พิมพ์รายงานเป็นภาษาไทย — คืน 1 เมื่อของที่ซ่อนเกินเพดานที่ตั้งไว้"""
    given = list(sys.argv[1:] if argv is None else argv)
    return rerun_census.main(["--root", str(ROOT), *given], messages=MESSAGES)


if __name__ == "__main__":
    sys.exit(main())
