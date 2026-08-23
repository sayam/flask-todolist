"""ออกเอกสาร VEX จากทะเบียน advisory ที่เรารับไว้แล้ว — `OSPS-VM-04.02`

โปรเจกต์นี้ตัดสิน CVE ทุกใบอยู่แล้ว และเหตุผลของแต่ละใบถูกบังคับให้อยู่ใน
`docs/SECURITY-CADENCE.md` โดยเทสต์ที่ตรวจสองทิศ — **แต่คำตัดสินนั้นเป็นร้อยแก้ว
ภาษาไทยที่มีแต่คนอ่านได้** · ปลายทางที่ต้องใช้จริง (ผู้ใช้ที่รันสแกนเนอร์ใส่ image
ของเรา แล้วเห็น CVE เดียวกัน) ไม่มีทางรู้ว่าเราตัดสินไปแล้วว่าอย่างไร

ตัวนี้แปลงทะเบียนที่มีอยู่ให้เป็น [OpenVEX](https://openvex.dev) — **ไม่ได้สร้าง
แหล่งความจริงใหม่** ทะเบียนยังเป็นแหล่งเดียว ตัวนี้แค่พิมพ์ออกมาในรูปที่เครื่องอ่านได้

**สถานะมาจากทะเบียนที่ ID นั้นอยู่ ไม่ใช่จากการเดา**:

- `pins/accepted-advisories.txt` — ของเครื่องมือ CI เท่านั้น ไม่เคยอยู่ในของที่
  ปล่อยออกไป → `not_affected` + `component_not_present`
- `app/plugins/accepted-advisories.txt` — ไลบรารีของ plugin ที่ไม่ได้ติดตั้งโดย
  ค่าเริ่มต้น (ADR 0025) → `not_affected` + `vulnerable_code_not_in_execute_path`
- `deploy/accepted-image-advisories.txt` — **อยู่ใน OS layer ของ image จริง** →
  `affected` + `action_statement` · การตอบ `not_affected` กับของที่อยู่ในภาพจริง
  คือการโกหกที่สแกนเนอร์ของผู้ใช้จับได้เอง

ใช้:
    PYTHONPATH=. python3 scripts/build_vex.py            # เขียนไฟล์
    PYTHONPATH=. python3 scripts/build_vex.py --check    # ตรวจว่าไฟล์ที่ commit ตรงกับที่ควรเป็น

บทบาท: generator — สร้างไฟล์ที่ commit ไว้ — หลักฐานคือผลลัพธ์ต้องตรงกับที่ commit (coverage ไม่ใช่ตัววัดของชนิดนี้)
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "vex.openvex.json"
CADENCE = ROOT / "docs" / "SECURITY-CADENCE.md"

CONTEXT = "https://openvex.dev/ns/v0.2.0"
AUTHOR = "Sayam Sriphua (flask-todolist maintainer)"

# ทะเบียน → (สถานะ, เหตุผลเชิงโครงสร้าง, ประโยคที่อธิบายให้ปลายทางอ่าน)
REGISTERS = {
    "pins/accepted-advisories.txt": (
        "not_affected",
        "component_not_present",
        (
            "The affected package is a CI tooling dependency pinned under pins/. "
            "It is never installed into the application image and is not part of any "
            "released artefact, so no released version of this project contains it."
        ),
    ),
    "app/plugins/accepted-advisories.txt": (
        "not_affected",
        "vulnerable_code_not_in_execute_path",
        (
            "The affected package belongs to an optional plugin that is not installed "
            "by default (ADR 0025). A deployment that does not install that plugin "
            "never loads the code, and removing the plugin directory removes the "
            "dependency with it."
        ),
    ),
    "deploy/accepted-image-advisories.txt": (
        "affected",
        None,
        None,
    ),
}
IMAGE_ACTION = (
    "Rebuild the container image once the upstream python:3.13-slim base ships "
    "the patched Debian package. The fix exists in Debian but the base image has "
    "not been rebuilt yet; the deadline for this decision is tracked in "
    "docs/SECURITY-CADENCE.md and the pinned digest is the newest available."
)

# แถวในตารางของ SECURITY-CADENCE ที่บอกว่า advisory ใบนั้นเป็นของแพ็กเกจไหน
PACKAGE = re.compile(r"— ของ `([^`]+)`")
ADVISORY_IN_ROW = re.compile(r"`((?:CVE|GHSA|PYSEC|DSA|DLA)-[\w.-]+)`")
PURL = {"pins": "pkg:npm/{name}", "plugins": "pkg:pypi/{name}", "image": "pkg:deb/debian/{name}"}


def declared() -> list[tuple[str, str]]:
    """(advisory id, ทะเบียนที่มันอยู่) ทุกใบที่รับไว้ — เรียงให้ผลลัพธ์คงที่"""
    found = []
    for name in REGISTERS:
        for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
            body = line.split("#", 1)[0].strip()
            if body:
                found.append((body, name))
    return sorted(found)


def package_of(advisory: str) -> str:
    """แพ็กเกจที่ advisory ใบนั้นพูดถึง — อ่านจากตารางใน `docs/SECURITY-CADENCE.md`

    **หาไม่เจอ = ดัง ไม่ใช่ข้าม** — VEX ที่บอกว่าเราไม่ได้รับผลกระทบโดยไม่บอกว่า
    ของชิ้นไหน คือเอกสารที่ปลายทางเอาไปทำอะไรไม่ได้
    """
    for line in CADENCE.read_text(encoding="utf-8").splitlines():
        if advisory in ADVISORY_IN_ROW.findall(line):
            named = PACKAGE.search(line)
            if named:
                return named.group(1)
            break
    raise ValueError(
        f"{advisory}: หาแพ็กเกจใน docs/SECURITY-CADENCE.md ไม่เจอ — "
        "แถวของ advisory ต้องเขียนว่า `— ของ \\`ชื่อแพ็กเกจ\\``"
    )


def statements() -> list[dict]:
    rows = []
    for advisory, register in declared():
        status, justification, impact = REGISTERS[register]
        kind = "image" if "image" in register else ("plugins" if "plugins" in register else "pins")
        row: dict = {
            "vulnerability": {"name": advisory},
            "products": [
                {
                    "@id": "pkg:github/sayam/flask-todolist",
                    "subcomponents": [{"@id": PURL[kind].format(name=package_of(advisory))}],
                }
            ],
            "status": status,
        }
        if justification:
            row["justification"] = justification
        if impact:
            row["impact_statement"] = impact
        if status == "affected":
            row["action_statement"] = IMAGE_ACTION
        rows.append(row)
    return rows


def document(timestamp: str) -> dict:
    return {
        "@context": CONTEXT,
        "@id": "https://github.com/sayam/flask-todolist/blob/main/docs/vex.openvex.json",
        "author": AUTHOR,
        "timestamp": timestamp,
        "version": 1,
        "tooling": "https://github.com/sayam/flask-todolist/blob/main/scripts/build_vex.py",
        "statements": statements(),
    }


def render() -> str:
    """เนื้อไฟล์ที่ควรเป็น — **เวลาเดิมถูกเก็บไว้ถ้าเนื้อไม่เปลี่ยน**

    ถ้าปั๊มเวลาใหม่ทุกครั้ง ไฟล์จะต่างจากที่ commit ไว้ทุกครั้งที่รัน แล้วด่านที่
    เทียบผลกับของที่ commit จะกลายเป็นด่านที่แดงตลอดโดยไม่มีอะไรเปลี่ยนจริง
    """
    now = datetime.datetime.now(tz=datetime.UTC).isoformat(timespec="seconds")
    if OUT.exists():
        old = json.loads(OUT.read_text(encoding="utf-8"))
        if old.get("statements") == statements():
            now = old["timestamp"]
    return json.dumps(document(now), ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="ตรวจอย่างเดียว ไม่เขียนไฟล์")
    args = parser.parse_args(argv)

    fresh = render()
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != fresh:
            print(
                f"{OUT.relative_to(ROOT)} ไม่ตรงกับทะเบียน — รัน scripts/build_vex.py", file=sys.stderr
            )
            return 1
        print(f"{OUT.relative_to(ROOT)} ตรงกับทะเบียนแล้ว ({len(statements())} statement)")
        return 0

    OUT.write_text(fresh, encoding="utf-8")
    print(f"เขียน {OUT.relative_to(ROOT)} — {len(statements())} statement")
    return 0


if __name__ == "__main__":
    sys.exit(main())
