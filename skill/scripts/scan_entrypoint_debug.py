"""gate: no-debug-entrypoint — entrypoint ห้ามเปิด debug console ได้แม้รันผิดตัว

debug console ของ dev server รันโค้ดจากหน้าเว็บได้ — และไฟล์ entrypoint
มักถูกก๊อปเข้า image · ตรวจด้วย **AST ไม่ใช่ regex** เพราะไฟล์พวกนี้ชอบเล่า
ในคอมเมนต์/docstring ว่าทำไมถึง*ไม่มี* `debug=True` — ตัวอักษรเดียวกัน
คนละความหมาย (dogfood กับ reference จับ false positive นี้ได้ตั้งแต่วันแรก)

exit 0 = สะอาด/NA · 1 = พบ · 2 = เรียกผิด
"""

from __future__ import annotations

import ast
import json
import pathlib
import sys


def _debug_run_calls(tree: ast.AST) -> list[int]:
    """บรรทัดของ `<อะไรก็ตาม>.run(..., debug=True, ...)` — ค่าคงที่จริงเท่านั้น"""
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "run"
        and any(
            keyword.arg == "debug"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is True
            for keyword in node.keywords
        )
    ]


def main(root: pathlib.Path) -> int:
    config = json.loads((root / "scaffold.json").read_text(encoding="utf-8"))
    names = config.get("entrypoints", ["run.py", "wsgi.py", "app.py", "main.py"])
    present = [root / n for n in names if (root / n).is_file()]
    if not present:
        print("NA: ไม่มีไฟล์ entrypoint ที่ประกาศไว้ — ยังไม่มีอะไรให้ตรวจ")
        return 0

    findings: list[str] = []
    for path in present:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        findings += [
            f"{path.relative_to(root)}:{line} .run(debug=True)" for line in _debug_run_calls(tree)
        ]
    for finding in findings:
        print(f"no-debug-entrypoint: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("ใช้: scan_entrypoint_debug.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
