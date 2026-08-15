"""gate: actions-sha-pinned — action ทุกตัวใน workflow ต้อง pin ด้วย commit SHA

tag ย้ายได้ commit ย้ายไม่ได้ — และ action รันด้วยสิทธิ์ของ workflow ของโปรเจกต์

exit 0 = สะอาด/NA · 1 = พบ · 2 = เรียกผิด
"""

from __future__ import annotations

import pathlib
import re
import sys

USES = re.compile(r"^\s*-?\s*uses:\s*(\S+)", re.MULTILINE)
PINNED = re.compile(r"@[0-9a-f]{40}$")
LOCAL = ("./", "docker://")


def main(root: pathlib.Path) -> int:
    workflows = sorted((root / ".github" / "workflows").glob("*.y*ml"))
    if not workflows:
        print("NA: ไม่มี workflow — ยังไม่มีอะไรให้ตรวจ")
        return 0

    findings: list[str] = []
    for path in workflows:
        findings += [
            f"{path.relative_to(root)}: {ref}"
            for ref in USES.findall(path.read_text(encoding="utf-8"))
            if not ref.startswith(LOCAL) and not PINNED.search(ref)
        ]

    for finding in findings:
        print(f"actions-sha-pinned: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("ใช้: scan_workflow_pinning.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
