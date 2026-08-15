"""gate: delete-means-soft-delete — `.delete(` นอกโมดูล purge ที่ประกาศไว้ = พบ

ลบจริงต้องอยู่ในที่ที่ประกาศ (`purge_paths` — รับ glob) — ที่อื่นทั้งหมดต้องเป็น
soft delete · จับ `session.delete(` ของ ORM ไม่ใช่ `.delete(` ทุกตัว เพราะ
`.delete(key)` ของ cache client ไม่ใช่การลบข้อมูลผู้ใช้ (dogfood กับ reference
จับ false positive นี้ได้) · ด่านลึกกว่า (bulk/Core/raw SQL) เป็นของ suite
ของโปรเจกต์ — scan นี้คือชั้นแรก ไม่ใช่ชั้นเดียว

exit 0 = สะอาด/NA · 1 = พบ · 2 = เรียกผิด
"""

from __future__ import annotations

import fnmatch
import json
import pathlib
import re
import sys

DELETE_CALL = re.compile(r"\bsession\.delete\s*\(|synchronize_session")


def main(root: pathlib.Path) -> int:
    config = json.loads((root / "scaffold.json").read_text(encoding="utf-8"))
    src = root / config.get("src_path", "app")
    if not src.is_dir():
        print(f"NA: ไม่มี {src.relative_to(root)} — ยังไม่มีอะไรให้ตรวจ")
        return 0
    patterns = config.get("purge_paths", ["app/purge.py"])

    findings: list[str] = []
    for path in sorted(src.rglob("*.py")):
        relative = path.relative_to(root)
        if any(fnmatch.fnmatch(str(relative), pattern) for pattern in patterns):
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if DELETE_CALL.search(line) and not line.lstrip().startswith("#"):
                findings.append(f"{path.relative_to(root)}:{lineno} {line.strip()[:70]}")

    for finding in findings:
        print(f"delete-means-soft-delete: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("ใช้: scan_write_discipline.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
