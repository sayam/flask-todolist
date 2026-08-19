"""CVE ในไลบรารีของ plugin ต้องถูก *ตัดสิน* ไม่ใช่แค่ถูกเห็น — audit รอบ 13 ข้อ 2

ADR 0025 ตัดสินไว้ว่า CVE ของไลบรารีที่ **ถอดได้** ไม่ควรทำให้ pipeline ของ core
แดง เพราะคำตอบที่เร็วที่สุดคือ "ถอดก่อน" (`DISABLED_PLUGINS` ใช้ได้ทันทีโดยไม่ต้อง
deploy) — **เจตนานั้นยังถูก** และใบนี้ไม่ได้กลับคำตัดสินนั้น

สิ่งที่ audit รอบ 13 พบคือ *ครึ่งหลัง* ของประโยคเดียวกันไม่เป็นจริง: ADR 0025 เขียนว่า
"แต่ต้องดังพอให้เห็น" ส่วนความจริงที่วัดได้คือ **สัญญาณนั้นดังใส่ annotation ของ job
ที่เขียวอยู่** ซึ่งไม่มีใครเปิดอ่าน · เมื่อรอบ 12 ให้ตัวรับสัญญาณประกาศกรอบเวลาตาม
กลไกจริง มันได้ **90 วัน** ขณะที่ `docs/SECURITY-CADENCE.md` ประกาศว่า CVE ระดับ
critical ต้องแก้ภายใน **7 วันนับจากวันที่รู้** — สองข้อนี้พร้อมกันไม่ได้

ทางออกที่เลือก: **ไม่ใช่ "ห้ามมี CVE" แต่คือ "ต้องมีคนตัดสิน"** · advisory ที่ยังไม่มี
บรรทัดใน `app/plugins/accepted-advisories.txt` ทำให้ job แดง และการปลดมีสามทาง
ซึ่งทั้งสามเป็นการตัดสินใจที่ใช้เวลาไม่กี่นาที:

1. อัปเกรดไลบรารี (ถ้ามี fix)
2. ถอด plugin ตัวนั้น — คำตอบที่ ADR 0025 บอกว่าเร็วที่สุด
3. เขียนบรรทัดในทะเบียนพร้อมเหตุผล — คือการรับความเสี่ยงอย่างเปิดเผย

ตรวจ **สองทิศ** เหมือนทะเบียนอื่นทุกใบ: เจอของที่ไม่อยู่ในทะเบียน = แดง ·
ID ที่อยู่ในทะเบียนแต่ไม่โผล่แล้ว = แดงเหมือนกัน (การยกเว้นเงียบเสมอเมื่อของที่
ยกเว้นหายไป — และรายการที่ไม่มีใครถอดจะกลายเป็นตัวปิดของจริงในวันหนึ่ง)

ใช้:
    pip-audit --no-deps -r req-<category>.txt --format=json --output found-<category>.json
    python3 scripts/audit_plugin_deps.py found-*.json

บทบาท: decider — ตัดสินผ่าน/ไม่ผ่าน — หลักฐานคือเทสต์ที่ฝังความผิดแล้วต้องจับได้ · ของสะอาดต้องไม่ถูกจับ
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ACCEPTED = ROOT / "app" / "plugins" / "accepted-advisories.txt"


def accepted_advisories() -> set[str]:
    """ID ที่ประเมินแล้วว่ารับไว้ — เหตุผลอยู่ใน `docs/SECURITY-CADENCE.md`"""
    if not ACCEPTED.is_file():
        return set()
    return {
        line.split("#", 1)[0].strip()
        for line in ACCEPTED.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def advisories(reports: list[dict]) -> dict[str, str]:
    """ID → ชื่อ package ที่มันอยู่ · อ่านจากผล `pip-audit --format=json`"""
    found: dict[str, str] = {}
    for report in reports:
        for dependency in report.get("dependencies", []):
            for vuln in dependency.get("vulns", []):
                if vuln.get("id"):
                    found[str(vuln["id"])] = str(dependency.get("name", "?"))
    return found


def problems(found: dict[str, str], accepted: set[str]) -> list[str]:
    """สองทิศ — ของใหม่ที่ยังไม่มีใครตัดสิน และการยกเว้นที่หมดอายุไปแล้ว"""
    lines = [
        f"{advisory} (ใน {package}) ยังไม่ถูกตัดสิน — อัปเกรด · ถอด plugin ด้วย "
        "DISABLED_PLUGINS (ADR 0025 บอกว่านี่คือคำตอบที่เร็วที่สุด) · หรือเขียน "
        "บรรทัดใน app/plugins/accepted-advisories.txt พร้อมเหตุผล"
        for advisory, package in sorted(found.items())
        if advisory not in accepted
    ]
    lines += [
        f"{advisory} อยู่ในทะเบียนแต่ไม่โผล่ในผลอีกแล้ว — ถอดบรรทัดออก (การยกเว้นเงียบเสมอเมื่อของที่ยกเว้นหายไป)"
        for advisory in sorted(accepted - set(found))
    ]
    return lines


def main(argv: list[str] | None = None) -> int:
    """อ่านผลของ pip-audit ทุก category → เทียบกับทะเบียนสองทิศ · คืน 1 เมื่อไม่ตรง"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="*", help="ไฟล์ JSON ของ pip-audit ต่อ category")
    args = parser.parse_args(argv)

    reports = []
    for name in args.reports:
        path = pathlib.Path(name)
        if not path.is_file():
            print(f"อ่าน {name} ไม่ได้ — pip-audit ไม่ได้เขียนไฟล์นี้ไว้", file=sys.stderr)
            return 2
        reports.append(json.loads(path.read_text(encoding="utf-8")))

    found = advisories(reports)
    accepted = accepted_advisories()
    for advisory, package in sorted(found.items()):
        state = "รับไว้แล้ว" if advisory in accepted else "**ยังไม่ถูกตัดสิน**"
        print(f"  {advisory} · {package} · {state}")

    trouble = problems(found, accepted)
    if trouble:
        print("CVE ในไลบรารีของ plugin ที่ยังไม่ถูกตัดสิน:", file=sys.stderr)
        for line in trouble:
            print(f"  - {line}", file=sys.stderr)
        return 1

    print(f"ทุก advisory ถูกตัดสินแล้ว ({len(found)} รายการ · ทะเบียน {len(accepted)} บรรทัด)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
