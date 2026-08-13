"""gate: csp-no-inline — template ห้ามมี inline handler/style/script

CSP ที่เป็น 'self' ล้วนจะทำให้ browser บล็อกของพวกนี้**เงียบ ๆ** ไม่มี error
ฝั่ง server — ด่านจึงต้องตรวจไฟล์ตรง ๆ ไม่ใช่รอดูอาการ

exit 0 = สะอาด/NA · 1 = พบ · 2 = เรียกผิด
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

PATTERNS = (
    (re.compile(r"\son\w+\s*="), "inline handler (on*=)"),
    (re.compile(r"\sstyle\s*="), "inline style="),
    (re.compile(r"<script(?![^>]*\bsrc\s*=)[^>]*>", re.IGNORECASE), "inline <script>"),
    (re.compile(r"javascript:", re.IGNORECASE), "javascript: URI"),
)


def main(root: pathlib.Path) -> int:
    config = json.loads((root / "scaffold.json").read_text(encoding="utf-8"))
    templates = root / config.get("templates_path", "app/templates")
    if not templates.is_dir():
        print(f"NA: ไม่มี {templates.relative_to(root)} — ยังไม่มีอะไรให้ตรวจ")
        return 0

    findings: list[str] = []
    for path in sorted(templates.rglob("*.html")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            findings += [
                f"{path.relative_to(root)}:{lineno} {label}"
                for pattern, label in PATTERNS
                if pattern.search(line)
            ]

    for finding in findings:
        print(f"csp-no-inline: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("ใช้: scan_templates_inline.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
