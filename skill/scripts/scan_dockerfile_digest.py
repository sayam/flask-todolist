"""gate: image-digest-pinned — base image ต้อง pin ด้วย digest ไม่ใช่แค่ tag

tag ถูกย้ายทับได้ — image ที่ทดสอบผ่านกับที่ deploy จะไม่ใช่ตัวเดียวกัน
· pin แล้วต้องมีอะไรขยับให้ด้วย (Dependabot docker ecosystem) — ครึ่งนั้น
ตรวจโดยด่าน dependabot ของโปรเจกต์ ไม่ใช่ที่นี่

exit 0 = สะอาด/NA · 1 = พบ · 2 = เรียกผิด
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

FROM_LINE = re.compile(r"^FROM\s+(\S+)", re.MULTILINE)
STAGE = re.compile(r"^FROM\s+\S+\s+AS\s+(\S+)", re.MULTILINE)
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")


def main(root: pathlib.Path) -> int:
    config = json.loads((root / "scaffold.json").read_text(encoding="utf-8"))
    names = config.get("dockerfiles", ["Dockerfile"])
    dockerfiles = [root / n for n in names if (root / n).is_file()]
    if not dockerfiles:
        print("NA: ไม่มี Dockerfile — ยังไม่มีอะไรให้ตรวจ")
        return 0

    findings: list[str] = []
    for path in dockerfiles:
        text = path.read_text(encoding="utf-8")
        stages = set(STAGE.findall(text))
        findings += [
            f"{path.relative_to(root)}: FROM {ref}"
            for ref in FROM_LINE.findall(text)
            if ref not in stages and not DIGEST.search(ref)
        ]

    for finding in findings:
        print(f"image-digest-pinned: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("ใช้: scan_dockerfile_digest.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
