"""สร้าง/รีเฟรชตารางประเมิน ASVS ใน docs/ASVS.md จากมาตรฐานที่ตรึงไว้ใน repo

**กลไกอยู่ที่ verifiable-gates แล้ว** (ADR 0077 · ขั้น 5 ส่วนสุดท้าย) —
`verifiable_gates.asvs_worksheet` ดึง/ตรึง/เรนเดอร์ และ**ไม่เคยเขียนคำตัดสินให้ใคร**
· ไฟล์นี้เหลือสิ่งที่เป็นของ repo นี้ล้วน ๆ: checksum ของมาตรฐานที่ตรึง · ระดับ
ที่ประกาศว่าจะทำ (L1+L2 — L3 อยู่นอกขอบเขต) · **ถ้อยคำภาษาไทย**ของตาราง
(เครื่องหมายแบ่ง · หัวตาราง · สถานะ "ยังไม่ประเมิน") · และพาธของสองไฟล์

ทำไมต้องตรึงมาตรฐานลง repo แทนที่จะดึงสดตอนรันเทสต์:
- ด่านที่ต้องต่อเน็ตคือด่านที่แดงเพราะเน็ต ไม่ใช่เพราะโค้ด
- และมาตรฐานที่เปลี่ยนใต้เท้าเราแปลว่า "ผ่าน" ของเมื่อวานอาจไม่ใช่ของวันนี้
  โดยไม่มี commit ไหนบอก — การขยับเวอร์ชันต้องเป็นการกระทำที่มองเห็นใน git

รัน:
    PYTHONPATH=. pipenv run python scripts/build_asvs_worksheet.py            # รีเฟรชตาราง
    PYTHONPATH=. pipenv run python scripts/build_asvs_worksheet.py --fetch    # ดึงมาตรฐานใหม่
    PYTHONPATH=. pipenv run python scripts/build_asvs_worksheet.py --check    # ตรวจอย่างเดียว (CI)

บทบาท: generator — สร้างไฟล์ที่ commit ไว้ — หลักฐานคือผลลัพธ์ต้องตรงกับที่ commit (coverage ไม่ใช่ตัววัดของชนิดนี้)
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vendor" / "verifiable-gates" / "src"))

from verifiable_gates import asvs_worksheet  # noqa: E402 — ต้องต่อ path ให้ vendor ก่อน import

SOURCE = ROOT / "docs" / "asvs-5.0.0.json"
WORKSHEET = ROOT / "docs" / "ASVS.md"

VERSION = "5.0.0"
URL = (
    "https://raw.githubusercontent.com/OWASP/ASVS/master/5.0/docs_en/"
    "OWASP_Application_Security_Verification_Standard_5.0.0_en.flat.json"
)
# ตรึงด้วย checksum ของ *เนื้อหาที่เราตัดฟิลด์แล้ว* ไม่ใช่ของไฟล์ที่โหลดมา —
# ไฟล์ต้นทางมีการจัดรูปแบบที่เปลี่ยนได้โดยข้อกำหนดไม่เปลี่ยน
DIGEST = "ac4b50fe0419cad6a6e6dd0ddc6a47276dccc7485a12bb9989305edb6f4bbe1c"

# ระดับที่โปรเจกต์นี้ประกาศว่าจะทำ — L3 อยู่นอกขอบเขต (ดูหัวข้อขอบเขตใน ASVS.md)
IN_SCOPE = ("1", "2")

# ถ้อยคำของตารางเป็นของที่นี่ — กลไกไม่รู้ภาษา · เครื่องหมายแบ่งคือเส้นที่ทุกอย่าง
# ใต้มันเป็นของสคริปต์ และคำนำเหนือมัน (ที่มีตาราง backlog หน้าตาเหมือนกัน) เป็นของคน
WORDS = asvs_worksheet.Words(
    marker="<!-- ตารางประเมินเริ่มที่นี่ — ทุกอย่างใต้บรรทัดนี้สร้างโดยสคริปต์ -->",
    unassessed="ยังไม่ประเมิน",
    header="| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |",
)
PREAMBLE_END = WORDS.marker
UNASSESSED = WORDS.unassessed

# ชื่อเดิมที่ผู้เรียกในที่นี่ยังอ้างถึง — ตัวจริงอยู่ที่ vg
digest_of = asvs_worksheet.digest_of
ROW = asvs_worksheet.ROW


def load() -> list[dict[str, str]]:
    """อ่านมาตรฐานที่ตรึงไว้ใน repo"""
    return asvs_worksheet.load(SOURCE)


def existing_verdicts(text: str) -> dict[str, tuple[str, str]]:
    """(สถานะ, หลักฐาน) ที่คนเขียนไว้แล้ว — การรีเฟรชต้องไม่ทับ"""
    return asvs_worksheet.existing_verdicts(text, WORDS.marker)


def render(requirements: list[dict[str, str]], verdicts: dict[str, tuple[str, str]]) -> str:
    """ตารางทั้งหมดในถ้อยคำและระดับของที่นี่"""
    return asvs_worksheet.render(requirements, verdicts, levels=IN_SCOPE, words=WORDS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", help="ดึงมาตรฐานจากต้นทางแล้วตรึงใหม่")
    parser.add_argument("--check", action="store_true", help="ตรวจว่าตารางตรงกับมาตรฐาน ไม่เขียนไฟล์")
    args = parser.parse_args()

    if args.fetch:
        requirements = asvs_worksheet.fetch(URL)
        asvs_worksheet.pin(SOURCE, requirements, version=VERSION, url=URL)
        print(f"เขียน {SOURCE.relative_to(ROOT)} — {len(requirements)} ข้อ")
        print(f"checksum ของเนื้อหา: {digest_of(requirements)}")
        print("**เอา checksum ไปใส่ DIGEST ในสคริปต์นี้ด้วย** ไม่งั้นการตรึงไม่มีผล")
        return 0

    requirements = load()
    actual = digest_of(requirements)
    if actual != DIGEST:
        print(f"checksum ของมาตรฐานไม่ตรงกับที่ตรึงไว้\n  ตรึงไว้: {DIGEST}\n  ที่เป็นจริง: {actual}")
        return 1

    text = WORKSHEET.read_text(encoding="utf-8") if WORKSHEET.exists() else ""
    rebuilt = asvs_worksheet.rebuild(text, requirements, levels=IN_SCOPE, words=WORDS)

    if args.check:
        if rebuilt != text:
            print("docs/ASVS.md ไม่ตรงกับมาตรฐานที่ตรึงไว้ — รันสคริปต์นี้โดยไม่ใส่ --check")
            return 1
        print("docs/ASVS.md ตรงกับมาตรฐานที่ตรึงไว้")
        return 0

    WORKSHEET.write_text(rebuilt, encoding="utf-8")
    in_scope = sum(1 for item in requirements if item["level"] in IN_SCOPE)
    print(f"เขียน {WORKSHEET.relative_to(ROOT)} — {in_scope} ข้อในขอบเขต")
    return 0


if __name__ == "__main__":
    sys.exit(main())
