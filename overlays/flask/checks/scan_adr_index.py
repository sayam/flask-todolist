"""gate: adr-index-complete — ดัชนี ADR ครอบทุกใบ เลขไม่ซ้ำไม่มีรู

ดัชนีที่ค้างแย่กว่าไม่มีดัชนี — คนอ่านเชื่อว่าเห็นครบทั้งที่การตัดสินใจล่าสุด
ไม่อยู่ในนั้น (reference เคยค้าง 7 ใบจากเฟสที่ตัดสินเรื่องใหญ่ที่สุด)

exit 0 = สะอาด/NA · 1 = พบ · 2 = เรียกผิด
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

FILENAME = re.compile(r"^(\d{4})-[a-z0-9-]+\.md$")
INDEX_LINK = re.compile(r"\[(\d{4})\]\(([^)]+)\)")


def main(root: pathlib.Path) -> int:
    config = json.loads((root / "scaffold.json").read_text(encoding="utf-8"))
    adr_dir = root / config.get("adr_path", "docs/adr")
    if not adr_dir.is_dir():
        print(f"NA: ไม่มี {adr_dir.relative_to(root)} — ยังไม่มีอะไรให้ตรวจ")
        return 0

    on_disk = {m.group(1): p.name for p in adr_dir.glob("*.md") if (m := FILENAME.match(p.name))}
    index = adr_dir / "README.md"
    listed = dict(INDEX_LINK.findall(index.read_text(encoding="utf-8"))) if index.is_file() else {}

    findings: list[str] = []
    if on_disk and not index.is_file():
        findings.append("มี ADR แต่ไม่มีดัชนี README.md")
    findings += [f"ไม่อยู่ในดัชนี: {on_disk[n]}" for n in sorted(on_disk.keys() - listed.keys())]
    findings += [f"ดัชนีชี้ไฟล์ที่ไม่มี: {listed[n]}" for n in sorted(listed.keys() - on_disk.keys())]

    numbers = sorted(int(n) for n in on_disk)
    if numbers and numbers != list(range(numbers[0], numbers[0] + len(numbers))):
        findings.append(f"เลขมีรู: {numbers}")

    for finding in findings:
        print(f"adr-index-complete: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("ใช้: scan_adr_index.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
