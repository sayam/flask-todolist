"""gate: logic-knows-no-http — service layer ห้าม import ของฝั่ง request

สแกน AST ของทุกไฟล์ใต้ `services_path` — import สัญลักษณ์ฝั่ง request จาก
framework หรือ import โมดูล session ผู้ใช้ = ตรรกะรู้จัก HTTP แล้ว
(`current_app` ไม่ห้าม — มันผูกกับแอป ไม่ใช่กับ request)

exit 0 = สะอาด/ไม่มีไดเรกทอรี (NA) · 1 = พบ · 2 = เรียกผิด
"""

from __future__ import annotations

import ast
import json
import pathlib
import sys

FORBIDDEN_FLASK_SYMBOLS = {
    "request",
    "session",
    "g",
    "flash",
    "abort",
    "redirect",
    "render_template",
    "url_for",
    "jsonify",
    "make_response",
}
FORBIDDEN_MODULES = {"flask_login"}


def main(root: pathlib.Path) -> int:
    config = json.loads((root / "scaffold.json").read_text(encoding="utf-8"))
    services = root / config.get("services_path", "app/services")
    if not services.is_dir():
        print(f"NA: ไม่มี {services.relative_to(root)} — ยังไม่มีอะไรให้ตรวจ")
        return 0

    findings: list[str] = []
    for path in sorted(services.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            where = f"{path.relative_to(root)}:{getattr(node, 'lineno', 0)}"
            if isinstance(node, ast.ImportFrom) and node.module == "flask":
                bad = sorted({a.name for a in node.names} & FORBIDDEN_FLASK_SYMBOLS)
                if bad:
                    findings.append(f"{where} from flask import {', '.join(bad)}")
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                else:
                    names = [node.module or ""]
                bad = sorted({n.split(".")[0] for n in names} & FORBIDDEN_MODULES)
                if bad:
                    findings.append(f"{where} import {', '.join(bad)}")

    for finding in findings:
        print(f"logic-knows-no-http: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("ใช้: scan_service_layer.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
