"""gates doctor — รายงานสถานะ gate ของโปรเจกต์ที่ import scaffolding นี้

ใช้ stdlib ล้วน **โดยตั้งใจ** — โปรเจกต์ปลายทางต้องรันได้ด้วย `python3` เปล่า ๆ
ตั้งแต่ยังไม่มี dependency ตัวแรก (manifest จึงเป็น JSON ไม่ใช่ YAML)

สอง mode ที่วัดคนละอย่าง — อย่าสับสน:
- `--installed`: ทุกอย่างที่ overlay ส่งมอบ**อยู่ครบและรันได้** (config มีจริง,
  scan ทุกตัว compile ผ่าน) — นี่คือ claim ของการ import ไม่ใช่ของโค้ด
- ไม่มี flag: **รัน scan จริง** — exit 1 ถ้า scan ตัวไหนพบ · gate ชนิด `suite`
  รายงานว่า "รอเทสต์ของโปรเจกต์" ตามจริง ไม่ถูกนับผ่านเงียบ ๆ
"""

from __future__ import annotations

import json
import pathlib
import py_compile
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent


def load_manifest() -> dict:
    return json.loads((HERE / "overlay.json").read_text(encoding="utf-8"))


def check_installed(root: pathlib.Path, manifest: dict) -> int:
    """ของครบและรันได้ไหม — ยังไม่ตัดสินโค้ดของโปรเจกต์"""
    problems: list[str] = []
    if not (root / "scaffold.json").is_file():
        problems.append("ไม่มี scaffold.json — install ยังไม่เสร็จ")
    for entry in manifest["gates"].values():
        if entry["kind"] != "scan":
            continue
        script = HERE / entry["script"]
        if not script.is_file():
            problems.append(f"ไม่มี {entry['script']}")
            continue
        try:
            py_compile.compile(str(script), doraise=True)
        except py_compile.PyCompileError as error:  # pragma: no cover - ทางพัง
            problems.append(f"{entry['script']} compile ไม่ผ่าน: {error}")

    scans = sum(1 for e in manifest["gates"].values() if e["kind"] == "scan")
    suites = sum(1 for e in manifest["gates"].values() if e["kind"] == "suite")
    if problems:
        print("** ติดตั้งไม่ครบ:")
        for problem in problems:
            print(f"   {problem}")
        return 1
    total = len(manifest["gates"])
    print(f"ติดตั้งครบ: gate ทั้งหมด {total} (scan {scans} · suite {suites}) — scan ทุกตัวรันได้")
    return 0


def run_scans(root: pathlib.Path, manifest: dict) -> int:
    """รัน scan ทุกตัวกับโปรเจกต์จริง — รายงานทีละ gate ไม่หยุดที่ตัวแรกที่พบ"""
    failed: list[str] = []
    pending = 0
    for gid, entry in sorted(manifest["gates"].items()):
        if entry["kind"] == "suite":
            pending += 1
            continue
        result = subprocess.run(
            [sys.executable, str(HERE / entry["script"]), str(root)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            status = "ผ่าน" if "NA:" not in result.stdout else "NA"
            print(f"[{status:>4}] {gid}")
        else:
            print(f"[ พบ ] {gid}")
            sys.stdout.write(result.stdout)
            failed.append(gid)

    print(f"\nsuite ที่รอเทสต์ของโปรเจกต์: {pending} gate (ดูรายชื่อใน overlay.json)")
    if failed:
        print(f"** scan พบปัญหา {len(failed)} gate: {', '.join(failed)}")
        return 1
    return 0


def main(argv: list[str]) -> int:
    """เลือก mode แล้ววิ่ง — root คือปลายทางที่ติดตั้ง เว้นแต่ส่ง path มาเอง

    ส่ง root มาเองได้ (`gates_doctor.py [--installed] [root]`) เพื่อชี้ doctor
    ที่ติดตั้งไว้ที่หนึ่งไปตรวจโปรเจกต์อีกที่ — job `scaffold` ใช้ทางนี้ dogfood
    reference implementation ด้วย overlay ของตัวเอง
    """
    positional = [a for a in argv if not a.startswith("--")]
    root = pathlib.Path(positional[0]).resolve() if positional else HERE.parent
    manifest = load_manifest()
    if "--installed" in argv:
        return check_installed(root, manifest)
    return run_scans(root, manifest)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
