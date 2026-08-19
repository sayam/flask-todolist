"""หน้าเดียวที่ตอบว่า "ช่วงหลังมีอะไรถูกถอดออกไปบ้าง" — audit รอบ 16 ข้อ 3

บันทึกของการถอด **มีอยู่ครบแล้วใน git history** ไม่มีอะไรหายจริงในเชิงข้อมูล ·
สิ่งที่ไม่มีคือ *ใครสักคนหรืออะไรสักอย่างที่อ่านมัน* — และนี่เป็นครั้งที่สามที่
โปรเจกต์นี้เจอรูปเดียวกัน (รอบ 13: ไม่มีที่*อ่าน* ไม่ใช่ไม่มีที่*เขียน* · รอบ 15:
ด่านที่รันบนเครื่องได้แต่ไม่มีใครเรียกในจังหวะที่ยังมีประโยชน์)

**ปัญหาที่แท้จริงคือแยกไม่ออก**: `git log -p -- docs/SECURITY-CADENCE.md` ให้บรรทัด
ตารางที่ถูกลบ 31 บรรทัดตลอดอายุ repo · ในนั้นแยกไม่ออกด้วยตาเปล่าว่าอันไหนคือ
"แถวที่ถูกถอด" อันไหนคือ "แถวที่ถูกเขียนใหม่" ต้องเปิดอ่านทีละ diff ซึ่งไม่มีใครทำ

**ตัวนี้ไม่ใช่ทะเบียนใหม่** และตั้งใจให้ไม่เป็น: ไม่เก็บสถานะของตัวเองเลย อ่าน
git log อย่างเดียวแล้วพิมพ์ออกมาหน้าเดียว · ทะเบียนใบที่สิบเอ็ดคือสิ่งสุดท้ายที่
ระบบนี้ต้องการ (audit รอบ 13 วัดไว้แล้ว)

**สิ่งที่นับ**: ของที่ *หายไปจากไฟล์แล้วไม่ได้ถูกเพิ่มกลับ* ในช่วงเวลาที่ถาม —
ไม่ใช่ทุกบรรทัดที่ขึ้นต้นด้วย `-` ในทุก diff · การเปลี่ยนชื่อ (ถอดออกแล้วเพิ่ม
ชื่อใหม่ใน commit เดียวกัน) จึงไม่ถูกนับเป็นการถอด ซึ่งตรงกับความจริง: gate สองตัว
ที่หายไปตลอดอายุ repo เป็นการเปลี่ยนชื่อทั้งคู่

ใช้:
    python3 scripts/removals_census.py                 # 30 วันล่าสุด
    python3 scripts/removals_census.py --since 90.days # ช่วงอื่น
"""

from __future__ import annotations

import argparse
import difflib
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# `subprocess.run` ที่ไม่มี `timeout=` รอตลอดกาล (ADR 0067)
GIT_TIMEOUT_SECONDS = 120

# ตัวคั่นระหว่าง commit hash กับหัวข้อ — **ห้ามใช้ null byte** เพราะ argument ของ
# `subprocess` ที่มี `\x00` ส่งไม่ได้เลย (ValueError ตั้งแต่ตอน spawn) · U+241F
# เป็นสัญลักษณ์ที่ไม่มีทางโผล่ในหัว commit จริง
SEP = "\u241f"

# สิ่งที่ถอดแล้วเงียบ — ชื่อกอง → (path ที่ดู, regex ของ "หนึ่งรายการ")
WATCHED: dict[str, tuple[str, re.Pattern[str]]] = {
    "gate": ("gates.yaml", re.compile(r"^  - id: (\S+)")),
    "แถวตรวจตามรอบ": ("docs/SECURITY-CADENCE.md", re.compile(r"^\| \*{0,2}([^|*]{6,60})")),
    "แถวทะเบียนความเสี่ยง": (
        "docs/RISK-ASSESSMENT.md",
        re.compile(r"^\| ([^|]{6,60})\|\s*(?:ต่ำ|กลาง|สูง)"),
    ),
    "ของที่จงใจเลื่อน": ("docs/GOVERNANCE.md", re.compile(r"^\| \[?([^|\]]{6,60})")),
    "ไฟล์เทสต์": ("tests/", re.compile(r"^(tests/test_\w+\.py)$")),
    "ADR": ("docs/adr/", re.compile(r"^(docs/adr/\d{4}-[\w-]+\.md)$")),
}


def _git(*args: str) -> str:
    binary = shutil.which("git")
    if not binary:
        raise RuntimeError("ไม่มี git บนเครื่องนี้ — ตัวอ่านนี้อ่านประวัติจาก git อย่างเดียว")
    done = subprocess.run(  # noqa: S603 — คำสั่งคงที่ + path จาก shutil.which
        [binary, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    return done.stdout


def deleted_files(path: str, since: str) -> list[tuple[str, str, str]]:
    """(commit, หัวข้อ, ไฟล์) ของไฟล์ที่ถูกลบใต้ path — ไม่นับไฟล์ที่ถูก rename"""
    raw = _git(
        "log",
        f"--since={since}",
        "--diff-filter=D",
        "--name-only",
        f"--format=%h{SEP}%s",
        "--",
        path,
    )
    found = []
    commit = subject = ""
    for line in raw.splitlines():
        if SEP in line:
            commit, subject = line.split(SEP, 1)
        elif line.strip():
            found.append((commit, subject, line.strip()))
    return found


# ความคล้ายที่ถือว่า "แถวเดิมถูกแก้ข้อความ" ไม่ใช่ "แถวถูกถอด" — ค่านี้เป็นการ
# ตีความ ไม่ใช่ข้อเท็จจริง จึงถูกรายงานแยกให้เห็น ไม่ใช่ตัดทิ้งเงียบ ๆ
EDIT_SIMILARITY = 0.6


def _looks_like_an_edit(gone: str, added: set[str]) -> bool:
    """แถวที่หายไปแล้วมีแถวหน้าตาใกล้เคียงเพิ่มเข้ามาใน commit เดียวกัน = การแก้"""
    return any(
        difflib.SequenceMatcher(None, gone, candidate).ratio() >= EDIT_SIMILARITY
        for candidate in added
    )


def removed_entries(
    path: str, pattern: re.Pattern[str], since: str
) -> tuple[list[tuple[str, str, str]], int]:
    """(รายการที่ถูกถอด, จำนวนที่ตีความว่าเป็นการแก้ข้อความ)

    การเปลี่ยนชื่อและการแก้ถ้อยคำคือ ลบ+เพิ่มใน commit เดียว — ถ้านับแค่บรรทัดที่
    ขึ้นต้นด้วย `-` ทั้งสองอย่างจะกลายเป็น "การถอด" แล้วรายงานจะเต็มไปด้วยของที่
    ไม่ได้หายไปไหน · **นี่คือความต่างที่รายงานของรอบ 16 บอกว่าตาเปล่าแยกไม่ออก**
    """
    raw = _git("log", f"--since={since}", "-p", f"--format=%h{SEP}%s", "--", path)
    found: list[tuple[str, str, str]] = []
    edits = 0
    commit = subject = ""
    gone: list[str] = []
    added: set[str] = set()

    def flush() -> None:
        nonlocal edits
        for item in gone:
            if item in added or _looks_like_an_edit(item, added):
                edits += 1
            else:
                found.append((commit, subject, item))

    for line in raw.splitlines():
        if SEP in line and not line.startswith(("+", "-")):
            flush()
            commit, subject = line.split(SEP, 1)
            gone, added = [], set()
        elif line.startswith("-") and not line.startswith("---"):
            if match := pattern.match(line[1:]):
                gone.append(match.group(1).strip())
        elif line.startswith("+") and not line.startswith("+++"):
            if match := pattern.match(line[1:]):
                added.add(match.group(1).strip())
    flush()
    return found, edits


def census(since: str) -> tuple[dict[str, list[tuple[str, str, str]]], int]:
    """(ทุกกอง → รายการที่ถูกถอด, จำนวนที่ตีความว่าเป็นการแก้ข้อความ)"""
    result: dict[str, list[tuple[str, str, str]]] = {}
    edits = 0
    for name, (path, pattern) in WATCHED.items():
        if path.endswith("/"):
            result[name] = deleted_files(path, since)
        else:
            result[name], counted = removed_entries(path, pattern, since)
            edits += counted
    return result, edits


def report(since: str) -> str:
    """หน้าเดียว — กองไหนว่างก็บอกว่าว่าง ไม่ใช่หายไปจากรายงาน"""
    found, edits = census(since)
    total = sum(len(items) for items in found.values())
    lines = [f"ของที่ถูกถอดออกไป — ตั้งแต่ {since} · รวม {total} รายการ", ""]
    for name, items in found.items():
        lines.append(f"## {name} — {len(items)}")
        rows = [f"  {commit} {item[:56]}  ({subject[:52]})" for commit, subject, item in items]
        lines += rows or ["  (ไม่มี)"]
        lines.append("")
    lines += [
        f"อีก {edits} รายการถูกตีความว่าเป็น **การแก้ข้อความ** (มีของหน้าตาใกล้เคียงเพิ่ม",
        "เข้ามาใน commit เดียวกัน) จึงไม่นับเป็นการถอด — ตัวเลขนี้ถูกพิมพ์ไว้เพราะ",
        "มันคือการตีความ ไม่ใช่ข้อเท็จจริง · ของที่ถูกตัดออกเงียบ ๆ คือของที่ไม่มีใครทบทวน",
        "",
        "การถอดที่ตั้งใจจะมีเหตุผลอยู่ในหัว commit ของมันเอง — แถวที่หัว commit",
        "อ่านแล้วไม่บอกว่าทำไมถึงถอด คือแถวที่ต้องไปถามต่อ",
        "",
        "จำนวนของแต่ละกองถูกประกาศไว้ใน [tool.todolist.removals] ของ pyproject.toml",
        "และ scripts/check_ratchets.py ทำให้การถอดต้องมาแก้เลขนั้น (ADR 0069)",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """พิมพ์รายงาน — คืน 0 เสมอ เพราะนี่คือของอ่าน ไม่ใช่ด่าน"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--since", default="30.days", help="ช่วงเวลาแบบที่ git เข้าใจ (ค่าเริ่มต้น 30.days)"
    )
    args = parser.parse_args(argv)
    print(report(args.since))
    return 0


if __name__ == "__main__":
    sys.exit(main())
