"""สร้าง/รีเฟรชตารางประเมิน ASVS ใน docs/ASVS.md จากมาตรฐานที่ตรึงไว้ใน repo

**สคริปต์นี้ไม่เคยเขียนคำตัดสินให้ใคร** — มันเติมได้แค่ *แถว* ของข้อกำหนดที่ยัง
ไม่มีในเอกสาร (สถานะตั้งต้น "ยังไม่ประเมิน") และคง "สถานะ" กับ "หลักฐาน" ที่คน
เขียนไว้แล้วทุกแถวไม่ให้ถูกทับ · การประเมินเป็นงานของคน สคริปต์แค่กันไม่ให้
ข้อกำหนดตกหล่นตอนขยับเวอร์ชันของมาตรฐาน

ทำไมต้องตรึงมาตรฐานลง repo แทนที่จะดึงสดตอนรันเทสต์:
- ด่านที่ต้องต่อเน็ตคือด่านที่แดงเพราะเน็ต ไม่ใช่เพราะโค้ด
- และมาตรฐานที่เปลี่ยนใต้เท้าเราแปลว่า "ผ่าน" ของเมื่อวานอาจไม่ใช่ของวันนี้
  โดยไม่มี commit ไหนบอก — การขยับเวอร์ชันต้องเป็นการกระทำที่มองเห็นใน git

รัน:
    PYTHONPATH=. pipenv run python scripts/build_asvs_worksheet.py            # รีเฟรชตาราง
    PYTHONPATH=. pipenv run python scripts/build_asvs_worksheet.py --fetch    # ดึงมาตรฐานใหม่
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
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

UNASSESSED = "ยังไม่ประเมิน"
HEADER = "| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |"
DIVIDER = "|---|---|---|---|---|"

# แถวของตาราง: ขึ้นต้นด้วย `| V<เลข>.` เสมอ จึงแยกออกจากตารางอื่นในไฟล์ได้แน่นอน
ROW = re.compile(r"^\|\s*(V\d+\.\d+\.\d+)\s*\|")

PREAMBLE_END = "<!-- ตารางประเมินเริ่มที่นี่ — ทุกอย่างใต้บรรทัดนี้สร้างโดยสคริปต์ -->"


def _fetch() -> list[dict[str, str]]:
    """ดึงมาตรฐานจากต้นทาง แล้วตัดให้เหลือเฉพาะฟิลด์ที่เราใช้"""
    with urllib.request.urlopen(URL, timeout=60) as response:
        payload = json.load(response)
    return [
        {
            "req_id": item["req_id"],
            "chapter_id": item["chapter_id"],
            "chapter_name": item["chapter_name"],
            "section_id": item["section_id"],
            "section_name": item["section_name"],
            "level": item["L"],
            "text": item["req_description"],
        }
        for item in payload["requirements"]
    ]


def _sort_key(requirement: dict[str, str]) -> tuple[int, ...]:
    return tuple(int(part) for part in requirement["req_id"][1:].split("."))


def digest_of(requirements: list[dict[str, str]]) -> str:
    """checksum ของเนื้อหาข้อกำหนด — เปลี่ยนเมื่อ *ข้อกำหนด* เปลี่ยนเท่านั้น"""
    canonical = json.dumps(requirements, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load() -> list[dict[str, str]]:
    """อ่านมาตรฐานที่ตรึงไว้ใน repo"""
    return json.loads(SOURCE.read_text(encoding="utf-8"))["requirements"]


def assessment_part(text: str) -> str:
    """เฉพาะส่วนที่สคริปต์เป็นเจ้าของ — ทุกอย่างใต้เครื่องหมาย

    **ต้องตัดหัวทิ้งก่อนเสมอ** เพราะคำนำมีตาราง backlog ที่แถวขึ้นต้นด้วยเลขข้อ
    เหมือนกันเป๊ะ · รอบแรกที่เขียนสคริปต์นี้ไม่ได้ตัด แล้วมันเขียนทับแถว backlog
    ด้วยรูปแบบของตารางประเมิน — พังเงียบ ๆ เพราะผลลัพธ์ยังเป็นตาราง markdown ที่ถูกต้อง
    """
    return text.split(PREAMBLE_END, 1)[1] if PREAMBLE_END in text else ""


def existing_verdicts(text: str) -> dict[str, tuple[str, str]]:
    """เก็บ (สถานะ, หลักฐาน) ที่คนเขียนไว้แล้ว เพื่อไม่ให้การรีเฟรชทับของเดิม"""
    verdicts = {}
    for line in assessment_part(text).splitlines():
        if not ROW.match(line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 5:
            verdicts[cells[0]] = (cells[3], cells[4])
    return verdicts


def render(requirements: list[dict[str, str]], verdicts: dict[str, tuple[str, str]]) -> str:
    """สร้างตารางทั้งหมด แบ่งตามหมวดและหัวข้อย่อยของมาตรฐาน"""
    lines: list[str] = []
    chapter = section = None
    for requirement in sorted(requirements, key=_sort_key):
        if requirement["level"] not in IN_SCOPE:
            continue
        if requirement["chapter_id"] != chapter:
            chapter = requirement["chapter_id"]
            section = None
            lines += ["", f"## {chapter} — {requirement['chapter_name']}"]
        if requirement["section_id"] != section:
            section = requirement["section_id"]
            lines += ["", f"### {section} {requirement['section_name']}", "", HEADER, DIVIDER]
        status, evidence = verdicts.get(requirement["req_id"], (UNASSESSED, "—"))
        lines.append(
            f"| {requirement['req_id']} | {requirement['level']} | {requirement['text']} "
            f"| {status} | {evidence} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", help="ดึงมาตรฐานจากต้นทางแล้วตรึงใหม่")
    parser.add_argument("--check", action="store_true", help="ตรวจว่าตารางตรงกับมาตรฐาน ไม่เขียนไฟล์")
    args = parser.parse_args()

    if args.fetch:
        requirements = sorted(_fetch(), key=_sort_key)
        SOURCE.write_text(
            json.dumps(
                {"version": VERSION, "source": URL, "requirements": requirements},
                ensure_ascii=False,
                indent=1,
            )
            + "\n",
            encoding="utf-8",
        )
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
    preamble = text.split(PREAMBLE_END)[0] if PREAMBLE_END in text else ""
    rebuilt = preamble + PREAMBLE_END + "\n" + render(requirements, existing_verdicts(text))

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
