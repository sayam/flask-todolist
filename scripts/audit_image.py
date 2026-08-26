"""ตัดสินผลสแกน OS layer ของ image — และบังคับให้รายการยกเว้นไม่เน่า

pip-audit ครอบไลบรารี python ทุกชั้นแล้ว (core · deploy · plugin · pins)
แต่ image ที่ ship จริงมีอีกครึ่งหนึ่งคือ **แพ็กเกจ OS ของ base image**
ซึ่ง SBOM บันทึกไว้เฉย ๆ โดยไม่มีใครอ่าน — มี SBOM ไม่เท่ากับมีคนสแกน
(ผล audit governance 2026-08-16 — ADR 0054)

**กลไกอยู่ที่ verifiable-gates แล้ว** (ADR 0077 · ขั้น 4) — `verifiable_gates.advisories`
อ่านรายงานและตัดสินสองทิศ · ที่นี่เหลือทะเบียนกับถ้อยคำ

สคริปต์นี้อ่าน**รายงาน JSON ของ trivy** (job `image` เป็นคนรันตัวสแกน
เพราะ image อยู่ที่นั่น — เครื่อง dev ไม่มี container runtime ตาม P5-09)
แล้วตัดสินแบบเดียวกับ `audit_pins.py` ทุกประการ:

- **เจอ CVE ที่ไม่ได้อยู่ในรายการยกเว้น = แดง**
- **ยกเว้น CVE ที่ไม่โผล่แล้ว = แดงเหมือนกัน** — ฐานข้อมูลช่องโหว่ขยับและ
  Dependabot (ecosystem `docker`) พา digest ใหม่มาเรื่อย ๆ รายการที่ไม่มี
  ใครถอดจะกลายเป็นตัวปิดของจริงในวันหนึ่ง

ขอบเขตที่ตัดสินไว้ (เหตุผลเต็มใน ADR 0054):
- เฉพาะ severity **HIGH / CRITICAL** — กรอบเวลาแก้ของ cadence เริ่มนับที่
  ระดับนี้ ส่วน MEDIUM/LOW ของ Debian มาก-ไปเร็วเกินกว่า acceptance list
  จะเล่าเรื่องอะไรได้
- เฉพาะที่ **มี fix แล้ว** (`--ignore-unfixed` ฝั่ง trivy) — ของที่ Debian
  ยังไม่ปล่อย patch คือของที่การกระทำเดียวที่ทำได้คือรอ และตัวพาของใหม่
  มาคือ Dependabot ไม่ใช่ความแดงของด่าน

รันเองบนเครื่อง (ต้องมีรายงานมาก่อน): `python3 scripts/audit_image.py <trivy.json>`

บทบาท: decider — ตัดสินผ่าน/ไม่ผ่าน — หลักฐานคือเทสต์ที่ฝังความผิดแล้วต้องจับได้ · ของสะอาดต้องไม่ถูกจับ
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vendor" / "verifiable-gates" / "src"))

from verifiable_gates import advisories  # noqa: E402 — ต้องต่อ path ให้ vendor ก่อน import

ACCEPTED = ROOT / "deploy" / "accepted-image-advisories.txt"


def accepted_advisories() -> set[str]:
    """ID ที่ประเมินแล้วว่ารับไว้ — บรรทัดว่างและคอมเมนต์ไม่นับ"""
    return set(advisories.accepted(ACCEPTED))


def findings(report: dict) -> dict[str, str]:
    """CVE ที่ trivy รายงาน → คำอธิบายสั้น ๆ สำหรับคนอ่าน log

    ขอบเขต severity/fixed ถูกตัดตั้งแต่ตอนเรียก trivy (ADR 0054) — ที่นี่
    อ่านทุกแถวที่อยู่ในรายงานโดยไม่กรองซ้ำ เพราะตัวกรองสองที่คือตัวกรอง
    ที่วันหนึ่งจะไม่ตรงกันเอง (หลักเดียวกับขอบเขต semgrep ที่ประกาศที่เดียว)
    """
    return advisories.from_trivy(report)


def main() -> int:
    if len(sys.argv) != 2:
        print("ใช้: python3 scripts/audit_image.py <trivy-report.json>")
        return 2

    report_path = pathlib.Path(sys.argv[1])
    report = json.loads(report_path.read_text(encoding="utf-8"))

    found = findings(report)
    accepted = accepted_advisories()

    for vid, detail in sorted(found.items()):
        mark = "[ยกเว้นไว้]" if vid in accepted else "[ใหม่ — ยังไม่มีใครตัดสิน]"
        print(f"   {vid}  {detail}  {mark}")

    fresh = sorted(set(found) - accepted)
    stale = sorted(accepted - set(found))

    failed = False
    if fresh:
        failed = True
        print(f"\nเจอ CVE ใน OS layer ที่ยังไม่มีใครตัดสิน: {', '.join(fresh)}")
        print("ทางออกเรียงตามที่ควรลอง: (1) Dependabot มี PR ขยับ digest ค้างอยู่ไหม")
        print("(2) regenerate digest เอง (3) ประเมินแล้วรับไว้ — เพิ่ม ID ลง")
        print(f"{ACCEPTED.relative_to(ROOT)} พร้อมเหตุผลใน docs/SECURITY-CADENCE.md")
    if stale:
        failed = True
        print(f"\nยกเว้นไว้แต่ไม่โผล่ในผลสแกนแล้ว: {', '.join(stale)}")
        print("แปลว่า fix มาถึงแล้วหรือแพ็กเกจหายไป — ถอด ID ออกจากรายการ")
        print("และถอดเหตุผลใน docs/SECURITY-CADENCE.md ในคอมมิตเดียวกัน")

    if not failed:
        kept = len(found)
        print(f"\nไม่มีอะไรใหม่ — ยกเว้นไว้ {kept} ข้อ และยังตรงกับความจริงทุกข้อ")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
