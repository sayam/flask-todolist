"""ติดตั้ง scaffolding ลงโปรเจกต์ปลายทาง — copy ตาม manifest ห้ามเดา

`python3 overlays/flask/install.py <ไดเรกทอรีปลายทาง>`

ผลลัพธ์ในปลายทาง:
- `tools/gates_doctor.py` + `tools/checks/` + `tools/overlay.json` — ตัวตรวจ
- `tools/preflight.py` — เดินด่านของ CI บนเครื่องก่อนเปิด PR โดยอ่านคำสั่งจาก
  workflow จริงของโปรเจกต์ (ADR 0060/0063 ของ repo แม่) · job ที่จะเดินประกาศใน
  `scaffold.json` คีย์ `preflight_jobs`
- `scaffold.json` — config (ไม่ทับของที่มีอยู่)
- `.github/workflows/gates.yml` — workflow ตั้งต้น (ไม่ทับของที่มีอยู่)

**อ่านรายชื่อไฟล์จาก manifest เท่านั้น** — ไฟล์ที่หายไปจาก overlay ทำให้
install **ล้มดัง ๆ** ไม่ใช่ติดตั้งไปครึ่งเดียว (เงื่อนไขสำเร็จของเฟส 9:
ลบไฟล์ overlay หนึ่งตัวแล้ว job scaffold ต้องแดง)
"""

from __future__ import annotations

import json
import pathlib
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent


def main(dest_arg: str) -> int:
    dest = pathlib.Path(dest_arg).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((HERE / "overlay.json").read_text(encoding="utf-8"))

    tools = dest / "tools"
    (tools / "checks").mkdir(parents=True, exist_ok=True)

    for name in [*manifest["ship"], "overlay.json"]:
        source = HERE / name
        if not source.is_file():
            print(f"** overlay ไม่ครบ: ไม่มี {name} — ติดตั้งไม่ได้", file=sys.stderr)
            return 1
        if name == "scaffold.json.default":
            target = dest / "scaffold.json"
            if target.exists():
                print(f"คงไว้: {target.name} (มีอยู่แล้ว)")
                continue
        elif name == "ci-template.yml":
            target = dest / ".github" / "workflows" / "gates.yml"
            if target.exists():
                print("คงไว้: .github/workflows/gates.yml (มีอยู่แล้ว)")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
        else:
            target = tools / name
        shutil.copy2(source, target)

    total = len(manifest["gates"])
    scans = sum(1 for e in manifest["gates"].values() if e["kind"] == "scan")
    print(f"ติดตั้งแล้วที่ {dest} — gate {total} (scan {scans}) · ตรวจด้วย: python3 tools/gates_doctor.py")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("ใช้: install.py <ไดเรกทอรีปลายทาง>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
