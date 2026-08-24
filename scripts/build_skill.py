"""สร้าง `SKILL.md` (baseline) และ `SKILL-TODOLIST.md` (business) — ADR 0042

`SKILL.md` ที่เขียนมือคือทะเบียนที่สามที่ drift จาก `gates.yaml` ได้ทันทีที่มี
คนแก้ฝั่งเดียว — ที่นี่จึง **generate ทั้งใบ** จาก gate ที่ `portable: true`:
กฎคือ `title` บทเรียนคือ `born_from` ตัวบังคับคือ `enforced_by` ซึ่งทุกช่อง
มีเทสต์คุมอยู่แล้วใน `tests/test_gates.py` (สองทิศ + partition + corroboration)

ส่วนที่เป็นของคนอยู่ที่เดียวคือ **หลักปฏิบัติกลาง** ใน PREAMBLE ข้างล่าง —
วินัยที่ไม่ใช่ gate ตัวไหนตัวเดียวแต่เป็นวิธีที่ gate ทุกตัวถูกสร้าง

ใช้: `pipenv run python scripts/build_skill.py` · `tests/test_skill.py`
เทียบไฟล์ที่ commit กับผล generate ทุกครั้งที่รันเทสต์

บทบาท: generator — สร้างไฟล์ที่ commit ไว้ — หลักฐานคือผลลัพธ์ต้องตรงกับที่ commit (coverage ไม่ใช่ตัววัดของชนิดนี้)
"""

from __future__ import annotations

import pathlib
import re
import sys

# pyyaml มากับ dev tools และไม่มี stub — เหตุผลเดียวกับ build_gates_crosswalk.py
import yaml  # type: ignore[import-untyped] - library lacks type stubs

ROOT = pathlib.Path(__file__).resolve().parent.parent
GATES = ROOT / "gates.yaml"
OUT = ROOT / "SKILL.md"
OUT_BUSINESS = ROOT / "SKILL-TODOLIST.md"

PREAMBLE = """# SKILL — กฎสากลของ scaffolding นี้

**ไฟล์นี้ generate มา ห้ามแก้ด้วยมือ** — สร้างใหม่ด้วย
`python scripts/build_skill.py` · แหล่งจริงคือ gate ที่
`portable: true` ใน `gates.yaml` (`tests/test_skill.py` เทียบทุกครั้งที่รันเทสต์)

กฎในไฟล์นี้**ไม่ผูกกับ framework** — ตัวบังคับของแต่ละกฎเป็นของ framework
(อยู่ใน `overlays/<framework>/` ซึ่งอ้างกฎด้วย gate id) · โครงสามชั้นนี้
คือคำตอบของคำถาม "ทำไมไม่ทำ abstraction ข้าม framework ที่ runtime" —
ดู `docs/adr/0040-scaffolding-scope-cuts.md`

ใบนี้คือชั้น **baseline** — กฎที่แอปไหนเบี่ยงก็ถือว่าบกพร่อง ไม่ใช่ทางเลือก ·
ข้อตกลงระดับ*ตัวแอป* (ที่เลือกต่างได้โดยชอบ เช่น soft delete) แยกอยู่
`SKILL-TODOLIST.md` ตามชั้นใน `gates.yaml` (ADR 0042)

## หลักปฏิบัติกลาง — วิธีที่กฎทุกข้อข้างล่างถูกสร้างและถูกรักษา

1. **เทสต์ใหม่ทุกตัวต้องผ่าน mutation test ก่อนถือว่าเสร็จ** — ทำให้โค้ด
   ที่มันอ้างว่าคุ้มผิดทีละจุด เทสต์ต้องแดง แล้วคืนโค้ด · ผิดแล้วยังเขียว = เทสต์
   ไม่ได้ทดสอบอะไร ให้แก้เทสต์ ไม่ใช่ปล่อยผ่าน
2. **ด่านต้องพิสูจน์สองทิศ** — แดงเมื่อควรแดง และผ่านเมื่อควรผ่าน · ด่านที่
   "ผ่าน" หน้าตาเหมือนด่านที่ "ไม่ได้ตรวจ" เสมอ จนกว่าจะวัดว่ามันตรวจอะไรจริง
3. **threshold เป็น ratchet ขยับขึ้นได้ทางเดียว** — coverage, ความเข้มของ
   type checker, จำนวนข้อที่ยังไม่ประเมิน ล้วนห้ามถอยโดยไม่มีใครเห็น
4. **การตัดสินใจสำคัญทุกเรื่องมี ADR** — รวมสิ่งที่*ตัดออก*โดยตั้งใจ พร้อม
   เงื่อนไขที่ทำให้คำตัดสินหมดอายุ
5. **ทะเบียนต้องถูกบังคับให้ตรงกับความจริง ไม่ใช่เขียนคู่ขนาน** — ของที่ derive
   ได้ให้ generate ของที่เป็นคำตัดสินของคนให้ตรวจอ้างอิงสองทิศ

## กฎ

แต่ละข้อ: **กฎ** (สากล) · **เกิดจาก** (กับดักจริงที่ให้กำเนิด — ไม่ใช่ทฤษฎี) ·
**ตัวบังคับใน reference** (ของ repo นี้ · overlay ของ framework อื่นอ้างด้วย id)
"""


def portable_gates(layer: str | None = None) -> list[dict]:
    """gate ที่ export ได้ — กรองตามชั้นได้ (ADR 0042) · ลำดับตามไฟล์"""
    gates = yaml.safe_load(GATES.read_text(encoding="utf-8"))["gates"]
    return [g for g in gates if g.get("portable") and (layer is None or g.get("layer") == layer)]


def _enforcement(gate: dict) -> str:
    """บรรทัดตัวบังคับ — ชี้ไปหาของจริงใน repo นี้ ไม่เขียนคำสั่งซ้ำ (ADR 0039)"""
    enforced = gate["enforced_by"]
    if gate["kind"] == "test":
        return " · ".join(f"`{t}`" for t in enforced["tests"])
    if gate["kind"] == "step":
        return f'job `{enforced["job"]}` step "{enforced["step"]}"'
    return f"job `{enforced['job']}`"


BUSINESS_PREAMBLE = """# SKILL-TODOLIST — ข้อตกลงของตัวแอป (ชั้น business)

**ไฟล์นี้ generate มา ห้ามแก้ด้วยมือ** — สร้างใหม่ด้วย
`python scripts/build_skill.py` · แหล่งจริงคือ gate ที่ `layer: business`
และ `portable: true` ใน `gates.yaml`

**ใบนี้ต่อยอด `SKILL.md` (baseline) — ต้องรับ baseline ก่อนจึงรับใบนี้ได้**
เพราะข้อตกลงข้างล่างถูกเขียนบนสมมติฐานว่าวินัยพื้นฐาน (mutation test ·
ด่านสองทิศ · ratchet · ADR) มีอยู่แล้ว (ADR 0042)

ต่างจาก baseline ตรงไหน: กฎในใบนี้เป็น**ทางเลือกของแอปชนิด todolist** —
แอปอื่นเลือกต่างได้โดยไม่ถือว่าบกพร่อง (เช่น แอปที่กฎหมายบังคับ erasure จริง
ย่อมไม่ใช้ soft delete) · การทดลองใน `docs/comparison/` ชี้ว่ากฎชั้นนี้แหละ
คือสิ่งที่ scaffolding ให้แล้วการทบทวนเองให้ไม่ได้ — เพราะมันเดาไม่ได้
ถ้าไม่มีใครเขียนไว้

## กฎ

แต่ละข้อ: **กฎ** (ของ app-type นี้ ไม่ผูก framework) · **เกิดจาก** (กับดักจริง)
· **ตัวบังคับใน reference** (ของ repo นี้)
"""


def render(layer: str = "baseline") -> str:
    """ประกอบหนึ่งใบตามชั้น — ลำดับตาม gates.yaml ผล generate ซ้ำได้ไบต์ต่อไบต์"""
    lines = [PREAMBLE if layer == "baseline" else BUSINESS_PREAMBLE]
    for gate in portable_gates(layer):
        born = re.sub(r"\s+", " ", gate["born_from"]).strip()
        lines.append(f"### `{gate['id']}`\n")
        lines.append(f"**กฎ:** {gate['title']}\n")
        lines.append(f"**เกิดจาก:** {born}\n")
        lines.append(f"**ตัวบังคับใน reference:** {_enforcement(gate)}\n")
    return "\n".join(lines)


def main() -> int:
    """เขียนทั้งสองใบทับไฟล์เดิม แล้วบอกว่ามีอะไรเปลี่ยนไหม"""
    for path, layer in ((OUT, "baseline"), (OUT_BUSINESS, "business")):
        fresh = render(layer)
        changed = not path.exists() or path.read_text(encoding="utf-8") != fresh
        path.write_text(fresh, encoding="utf-8")
        print(f"{'เขียนใหม่' if changed else 'ไม่มีอะไรเปลี่ยน'}: {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
