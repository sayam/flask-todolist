"""หน้าเดียวที่ตอบว่า "อะไรค้างอยู่" — audit รอบ 13 ข้อ 4

หลัง audit สิบสองรอบ คำถามง่าย ๆ ว่า *"หายไปหกเดือนแล้วกลับมา ต้องดูอะไรบ้าง"*
ต้องเปิด **8 ที่**: แถวตรวจตามรอบ · ทะเบียนข้อยกเว้น · รายการ `UNPROVEN` ·
ทะเบียนของที่จงใจเลื่อน · ADR ที่มีเงื่อนไขหมดอายุ · หน้า Security · รายการ
"ยังไม่ได้ทำ" · ROADMAP — และไม่มีหน้าไหนรวมให้

ขนาดของสองกองแรก ณ วันนี้: **แถวตรวจตามรอบ 34 แถว ·
ทะเบียนข้อยกเว้น 8 แฟ้ม** — สองเลขนี้มีเทสต์อ่านคู่กับของจริง
(`tests/test_checker_logic.py`) เพราะ **หน้าที่สร้างมาเพื่อให้เลิกนับด้วยมือ
เคยมีเลขที่นับด้วยมือและผิดทั้งสองตัวอยู่ในหัวไฟล์ของตัวเอง** — ตอนที่ audit
รอบ 21 มาอ่าน มันบอกว่า 24 แถวกับ 7 แฟ้ม ขณะที่ของจริงคือ 26 กับ 8

**ตัวนี้ไม่ใช่ทะเบียนใหม่** และตั้งใจให้ไม่เป็น: มันไม่เก็บสถานะของตัวเองเลย
อ่านจากแหล่งที่มีอยู่แล้วทั้งหมด แล้วพิมพ์ออกมาหน้าเดียว · ทะเบียนที่สิบเอ็ด
คือสิ่งสุดท้ายที่ระบบนี้ต้องการ — ปัญหาคือไม่มีที่*อ่าน* ไม่ใช่ไม่มีที่*เขียน*

**ออฟไลน์ล้วนโดยตั้งใจ** — พื้นผิวที่ต้องต่อเน็ต (alert บนหน้า Security · ตารางเวลา
ที่หยุดยิง) มีตัวตรวจของตัวเองที่รันทุก push อยู่แล้ว (`ci:posture`) การดึงซ้ำที่นี่
จะได้ตัวเลขที่ล้าสมัยกว่าและช้ากว่าโดยไม่ได้อะไรเพิ่ม

ใช้:
    python3 scripts/whats_pending.py
    python3 scripts/whats_pending.py --within 30   # แถวที่จะครบกำหนดใน 30 วัน

บทบาท: reader — อ่านแล้วรายงาน — หลักฐานคือตัวเลขที่พิมพ์ต้องตรงกับแหล่ง · ห้ามตัดของทิ้งเงียบ
"""

from __future__ import annotations

import argparse
import datetime
import pathlib
import re
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent
CADENCE = ROOT / "docs" / "SECURITY-CADENCE.md"
GOVERNANCE = ROOT / "docs" / "GOVERNANCE.md"
EVIDENCE = ROOT / "tests" / "test_gate_evidence.py"
INSTRUCTIONS = ROOT / "CLAUDE.md"
ADR_DIR = ROOT / "docs" / "adr"

REGISTERS = (
    ".zap/rules.tsv",
    ".hadolint.yaml",
    ".gitleaksignore",
    ".semgrepignore",
    "pins/accepted-advisories.txt",
    "deploy/accepted-image-advisories.txt",
    ".github/accepted-code-scanning-alerts.txt",
    "app/plugins/accepted-advisories.txt",
)

# ทะเบียนที่อยู่ **ในโค้ด** ไม่ใช่ไฟล์ข้อความ — นับด้วยตัวเลขของมันเองที่อื่น
# ในหน้านี้ แต่ต้องถูกเอ่ยชื่อคู่กับกองข้างบนเสมอ ไม่งั้นรายการของ "ทะเบียน
# ข้อยกเว้นทั้งหมด" จะมีสองฉบับที่ไม่ตรงกัน (audit รอบ 25 ข้อ 1)
IN_CODE_REGISTERS = ("ALLOWED_LINES", "UNPROVEN")

PYPROJECT = ROOT / "pyproject.toml"

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EXPIRY_MARK = "เงื่อนไขที่ทำให้คำตัดสิน"


def cadence_rows() -> list[tuple[str, str, str]]:
    """(ชื่อการตรวจ, รอบ, ครบกำหนด) ของทุกแถวในตาราง "ต้องมีคนลงมือ" """
    return [(title, period, due) for title, period, _, due in _cadence_cells()]


def _cadence_cells() -> list[tuple[str, str, str, str]]:
    """(ชื่อ, รอบ, ครั้งล่าสุด, ครบกำหนด) — ช่อง "ครั้งล่าสุด" บอกด้วยว่าเคยทำซ้ำหรือยัง"""
    text = CADENCE.read_text(encoding="utf-8")
    start = text.index("## ส่วนที่ต้องมีคนลงมือ")
    end = text.index("## กรอบเวลาแก้ช่องโหว่", start)
    rows = []
    for line in text[start:end].splitlines():
        if not line.startswith("|") or "---" in line or "ครบกำหนด" in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 5:
            rows.append((cells[0].replace("**", ""), cells[1], cells[2], cells[3]))
    return rows


def never_recurred() -> tuple[int, int]:
    """(จำนวนแถวที่ยังไม่เคยถูกทำซ้ำ, จำนวนแถวที่มีวันที่ทั้งหมด)

    **แถวที่ยังไม่เคยครบรอบ กับแถวที่ทำตามรอบแล้ว ให้ผลเหมือนกันทุกอย่างในตาราง
    เดิม** (audit รอบ 20) — ตัวเลขนี้คือความต่างที่มองเห็นได้ และมันลดลงเองตามเวลา
    """
    dated = [row for row in _cadence_cells() if DATE.match(row[3])]
    return sum(1 for row in dated if "ตั้งต้น" in row[2]), len(dated)


def due_soon(rows: list[tuple[str, str, str]], today: datetime.date, within: int) -> list[str]:
    """แถวที่ครบกำหนดแล้วหรือกำลังจะครบ · แถวที่ผูกกับเงื่อนไขแยกไปอีกกอง"""
    soon = []
    for title, period, due in rows:
        if not DATE.match(due):
            continue
        left = (datetime.date.fromisoformat(due) - today).days
        if left <= within:
            state = "เลยกำหนดแล้ว" if left < 0 else f"อีก {left} วัน"
            soon.append(f"{due} ({state}) · ทุก {period} · {title[:58]}")
    return sorted(soon)


def conditional_rows(rows: list[tuple[str, str, str]]) -> list[str]:
    """แถวที่รอเงื่อนไข ไม่ใช่รอวันที่ — ของพวกนี้ไม่มีวันครบกำหนดเอง"""
    return sorted(
        f"{title[:52]} — {due[:60]}" for title, _period, due in rows if not DATE.match(due)
    )


def human_judged(rows: list[tuple[str, str, str]]) -> tuple[int, int]:
    """(แถวเงื่อนไขที่คนต้องดูเอง, แถวเงื่อนไขทั้งหมด)

    **เงื่อนไขที่เครื่องประเมินได้ ไม่ควรถูกปล่อยให้คนดูโดยบังเอิญ** (audit รอบ 20)
    — ตัวเลขคู่นี้ทำให้ความต่างมองเห็นได้ แทนที่จะต้องไล่อ่านทีละแถว
    """
    conditional = [due for _title, _period, due in rows if not DATE.match(due)]
    return sum(1 for due in conditional if "คนตัดสิน" in due), len(conditional)


def deferred() -> list[str]:
    """แถวในทะเบียนของที่จงใจเลื่อน (docs/GOVERNANCE.md)"""
    text = GOVERNANCE.read_text(encoding="utf-8")
    body = text[text.index("## การตัดสินใจที่จงใจเลื่อน") :]
    rows = []
    for line in body.splitlines():
        if not line.startswith("|") or "---" in line or "ทำไมถึงยังไม่ทำ" in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 3:
            rows.append(f"{cells[0][:58]} → กลับมาทำเมื่อ: {cells[2][:58]}")
    return rows


def undone() -> list[str]:
    """หัวข้อของรายการ "ยังไม่ได้ทำ" ใน CLAUDE.md — บรรทัดแรกของแต่ละข้อ

    **หยุดที่หัวข้อถัดไปเสมอ** (audit รอบ 14 ข้อ 4) — รุ่นแรกอ่านยาวจนจบไฟล์
    โดยไม่มีขอบเขต ซึ่งบังเอิญให้ตัวเลขที่ถูกเพราะหัวข้อถัด ๆ ไปไม่มี bullet
    ระดับบนสุด · **ตัวอ่านที่อ่านเลยหัวข้อของตัวเอง ห่างจากการรายงานผิดอยู่
    หัวข้อเดียว** และมันจะผิดในวันที่ไม่มีใครกำลังดูมันอยู่
    """
    text = INSTRUCTIONS.read_text(encoding="utf-8")
    body = text[text.index("## ยังไม่ได้ทำ") :]
    items = []
    for line in body.splitlines()[1:]:
        if line.startswith("#"):  # หัวข้อถัดไป (รวมหัวข้อย่อยของที่ปิดแล้ว) = จบกอง
            break
        # ข้อที่ถูกขีดฆ่า (`~~...~~`) คือของที่ปิดไปแล้วแต่เก็บไว้ให้อ่านประวัติ —
        # นับมันเป็น "ค้างอยู่" คือการทำให้กองดูใหญ่กว่าความจริง
        if line.startswith("- ") and not line[2:].lstrip().startswith("~~"):
            items.append(line[2:].strip().replace("**", "")[:70])
    return items


def ceilings() -> dict[str, int]:
    """เพดานที่เดินทางเดียว — กองที่ *มีคนต้องไปทำให้เล็กลง* ไม่ใช่แค่ห้ามโต

    หน้านี้เกิดขึ้นเพราะการต้องเปิดหลายที่ถึงจะรู้ว่าอะไรค้าง · เพดานพวกนี้เกิด
    ทีหลัง (audit รอบ 21 และ 24) แล้ว **ไม่มีอะไรทวงให้มาโผล่ที่นี่** — ผลคือ
    หน้าเดียวที่สร้างมาเพื่อให้เลิกเปิดหลายที่ ก็ยังต้องเปิดที่อื่นอยู่ดี
    """
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return {name: int(value) for name, value in config["tool"]["todolist"]["ceilings"].items()}


def counts() -> dict[str, int]:
    """ตัวเลขที่บอกขนาดของกองที่ต้องอ่าน — อ่านจากแหล่งจริงทุกตัว"""
    unproven = re.search(r"UNPROVEN_CEILING\s*=\s*(\d+)", EVIDENCE.read_text(encoding="utf-8"))
    registers = 0
    for name in REGISTERS:
        path = ROOT / name
        if not path.is_file():
            continue
        registers += sum(
            1
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    with_expiry = sum(
        1 for path in ADR_DIR.glob("[0-9]*.md") if EXPIRY_MARK in path.read_text(encoding="utf-8")
    )
    return {
        "gate ที่ยังไม่มีหลักฐาน": int(unproven.group(1)) if unproven else -1,
        "บรรทัดในทะเบียนข้อยกเว้น": registers,
        "ADR ที่มีเงื่อนไขหมดอายุ": with_expiry,
    }


def report(today: datetime.date, within: int) -> str:
    """หน้าเดียวที่ตอบว่าอะไรค้าง — ประกอบจากแหล่งที่มีอยู่แล้วล้วน ๆ"""
    rows = cadence_rows()
    lines = [f"อะไรค้างอยู่ — {today.isoformat()}", ""]

    soon = due_soon(rows, today, within)
    lines.append(f"## ตรวจตามรอบที่ถึงคิว (ภายใน {within} วัน) — {len(soon)} จาก {len(rows)} แถว")
    lines += [f"  {item}" for item in soon] or ["  (ไม่มี)"]

    fresh, dated = never_recurred()
    lines.append(f"  · ยังไม่เคยทำซ้ำเลย {fresh} จาก {dated} แถวที่มีวันที่")
    if fresh == dated:
        lines.append("    (ยังไม่มีรอบไหนหมุนครบสักรอบ — 'เลยกำหนด 0' จึงยังไม่ได้แปลว่ากระบวนการเดิน)")

    waiting = conditional_rows(rows)
    manual, conditional = human_judged(rows)
    lines += ["", f"## รอเงื่อนไข ไม่ใช่รอวันที่ — {len(waiting)} แถว"]
    lines.append(f"  · คนตัดสิน {manual} จาก {conditional} แถว (ที่เหลือมีเครื่องตรวจให้)")
    lines += [f"  {item}" for item in waiting] or ["  (ไม่มี)"]

    limits = ceilings()
    lines += ["", f"## กองที่หดได้ทางเดียว (เพดานใน pyproject) — {len(limits)} กอง"]
    lines += [f"  {name}: {value}" for name, value in sorted(limits.items())]
    lines.append("  · เพดานกันไม่ให้โต แต่ไม่มีอะไรทำให้หด — ต้องมีคนไปทำให้เล็กลงเอง")

    postponed = deferred()
    lines += ["", f"## ตัดสินแล้วว่ายังไม่ทำ — {len(postponed)} รายการ"]
    lines += [f"  {item}" for item in postponed] or ["  (ไม่มี)"]

    pending = undone()
    lines += ["", f"## ยังไม่ได้ทำ (ฟีเจอร์ของแอป) — {len(pending)} ข้อ"]
    lines += [f"  {item}" for item in pending] or ["  (ไม่มี)"]

    lines += ["", "## กองที่ต้องอ่านตอนทบทวน"]
    lines += [f"  {name}: {value}" for name, value in counts().items()]
    lines += [
        "",
        "พื้นผิวที่ต้องต่อเน็ต (alert บนหน้า Security · ตารางเวลาที่หยุดยิง) มีตัวตรวจ",
        "ของตัวเองที่รันทุก push แล้ว — ดูผลของ job `posture` ไม่ต้องดึงซ้ำที่นี่",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """พิมพ์รายงาน — คืน 0 เสมอ เพราะนี่คือของอ่าน ไม่ใช่ด่าน"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--within", type=int, default=60, help="ถือว่า 'ถึงคิว' ถ้าเหลือไม่เกินกี่วัน")
    parser.add_argument("--today", help="วันที่อ้างอิงรูป YYYY-MM-DD (สำหรับเทสต์)")
    args = parser.parse_args(argv)

    today = datetime.date.fromisoformat(args.today) if args.today else datetime.date.today()
    print(report(today, args.within))
    return 0


if __name__ == "__main__":
    sys.exit(main())
