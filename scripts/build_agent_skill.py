"""ประกอบ `skill/` — แพ็กเกจ agent skill ที่ติดตั้งได้ (ADR 0050)

ทุกไบต์ derive จากแหล่งที่มีเทสต์คุมอยู่แล้ว: กฎมาจาก `render()` ของ
`build_skill.py` (ซึ่งอ่าน `gates.yaml`) · checker คัดลอกตาม manifest
`overlays/flask/overlay.json` — ส่วนที่เป็นของคนมีที่เดียวคือซองหุ้ม
(frontmatter + คำนำวิธีใช้ข้างล่าง) ตามหลักเดียวกับ PREAMBLE ของ ADR 0042

ใช้: `PYTHONPATH=. pipenv run python scripts/build_agent_skill.py`
`tests/test_agent_skill.py` เทียบไฟล์ที่ commit กับผล generate ทุกครั้งที่รันเทสต์
— รวมทั้งเซตไฟล์: ของแปลกปลอมใน `skill/` ทำให้เทสต์แดง ไม่ใช่ถูกเมิน

บทบาท: generator — สร้างไฟล์ที่ commit ไว้ — หลักฐานคือผลลัพธ์ต้องตรงกับที่ commit (coverage ไม่ใช่ตัววัดของชนิดนี้)
"""

from __future__ import annotations

import json
import pathlib
import sys

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

# import แบบ top-level (ไม่ใช่ scripts.build_skill) ให้ตรงกับชื่อโมดูลที่
# mypy เห็นตอนสแกน `scripts/` — สองชื่อสำหรับไฟล์เดียว mypy ปฏิเสธ
from build_skill import render  # noqa: E402

SKILL_DIR = ROOT / "skill"
OVERLAY_DIR = ROOT / "overlays" / "flask"
MANIFEST = OVERLAY_DIR / "overlay.json"

DESCRIPTION = (
    "Universal production-discipline rules for web applications, distilled "
    "from a real project's incidents — every rule carries the trap that "
    "created it. Includes stdlib-only checker scripts that enforce part of "
    "the rules mechanically. Rule text is in Thai."
)

# ซองหุ้ม — ส่วนเดียวที่เป็นของคน · ภาษาอังกฤษเพราะเป็น metadata ของแพ็กเกจ
# (ตัวกฎเป็นไทยตามแหล่ง — สำเนาแปลคือไฟล์แรกที่ล้าหลัง ดู ADR 0050)
WRAPPER = f"""\
---
name: webapp-production-discipline
description: {DESCRIPTION}
---

> **How to use this skill** — the rules below are the *baseline* layer:
> a project that deviates from one is defective, not different. Read them
> before writing code, and hold new code to them. Two companions ship in
> this package: `reference/SKILL-TODOLIST.md` (the *business* layer —
> per-app agreements a project may legitimately decide differently, shown
> as one worked example) and `scripts/` (stdlib-only checkers, copied
> verbatim from this skill's source repository overlay; run
> `python scripts/scan_*.py <project-root>` on projects built with the
> matching stack). Generated from `gates.yaml` of the source repository —
> do not edit any file in this package by hand.

"""


def _shipped_checkers() -> list[str]:
    """รายชื่อ checker จาก manifest ของ overlay — ไม่ hardcode ซ้ำที่นี่"""
    ship = json.loads(MANIFEST.read_text(encoding="utf-8"))["ship"]
    return sorted(name for name in ship if name.startswith("checks/scan_"))


def targets() -> dict[str, str]:
    """เนื้อหาทั้งแพ็กเกจ — path (relative กับ skill/) → เนื้อไฟล์"""
    files = {
        "SKILL.md": WRAPPER + render("baseline"),
        "reference/SKILL-TODOLIST.md": render("business"),
    }
    for rel in _shipped_checkers():
        source = OVERLAY_DIR / rel
        files[f"scripts/{source.name}"] = source.read_text(encoding="utf-8")
    return files


def main() -> int:
    fresh = targets()
    changed = []
    for rel, content in fresh.items():
        path = SKILL_DIR / rel
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            changed.append(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    # ไฟล์ที่ไม่อยู่ในเป้า = ของค้างจากรุ่นก่อน ลบทิ้งให้แพ็กเกจตรงกับเป้าเสมอ
    for path in sorted(SKILL_DIR.rglob("*")):
        if path.is_file() and str(path.relative_to(SKILL_DIR)) not in fresh:
            path.unlink()
            changed.append(f"ลบ {path.relative_to(SKILL_DIR)}")
    print(f"skill/: {len(fresh)} ไฟล์ · " + (f"เปลี่ยน {changed}" if changed else "ไม่มีอะไรเปลี่ยน"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
