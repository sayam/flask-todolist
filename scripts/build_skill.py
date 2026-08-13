"""สร้าง `SKILL.md` — กฎสากลของ scaffolding ที่ import ไป project อื่นได้

`SKILL.md` ที่เขียนมือคือทะเบียนที่สามที่ drift จาก `gates.yaml` ได้ทันทีที่มี
คนแก้ฝั่งเดียว — ที่นี่จึง **generate ทั้งใบ** จาก gate ที่ `portable: true`:
กฎคือ `title` บทเรียนคือ `born_from` ตัวบังคับคือ `enforced_by` ซึ่งทุกช่อง
มีเทสต์คุมอยู่แล้วใน `tests/test_gates.py` (สองทิศ + partition + corroboration)

ส่วนที่เป็นของคนอยู่ที่เดียวคือ **หลักปฏิบัติกลาง** ใน PREAMBLE ข้างล่าง —
วินัยที่ไม่ใช่ gate ตัวไหนตัวเดียวแต่เป็นวิธีที่ gate ทุกตัวถูกสร้าง

ใช้: `pipenv run python scripts/build_skill.py` · `tests/test_skill.py`
เทียบไฟล์ที่ commit กับผล generate ทุกครั้งที่รันเทสต์
"""

from __future__ import annotations

import pathlib
import re
import sys

# pyyaml มากับ dev tools และไม่มี stub — เหตุผลเดียวกับ build_gates_crosswalk.py
import yaml  # type: ignore[import-untyped]

ROOT = pathlib.Path(__file__).resolve().parent.parent
GATES = ROOT / "gates.yaml"
OUT = ROOT / "SKILL.md"

PREAMBLE = """# SKILL — กฎสากลของ scaffolding นี้

**ไฟล์นี้ generate มา ห้ามแก้ด้วยมือ** — สร้างใหม่ด้วย
`python scripts/build_skill.py` · แหล่งจริงคือ gate ที่
`portable: true` ใน `gates.yaml` (`tests/test_skill.py` เทียบทุกครั้งที่รันเทสต์)

กฎในไฟล์นี้**ไม่ผูกกับ framework** — ตัวบังคับของแต่ละกฎเป็นของ framework
(อยู่ใน `overlays/<framework>/` ซึ่งอ้างกฎด้วย gate id) · โครงสามชั้นนี้
คือคำตอบของคำถาม "ทำไมไม่ทำ abstraction ข้าม framework ที่ runtime" —
ดู `docs/adr/0040-scaffolding-scope-cuts.md`

## หลักปฏิบัติกลาง — วิธีที่กฎทุกข้อข้างล่างถูกสร้างและถูกรักษา

1. **เทสต์ใหม่ทุกตัวต้องผ่าน mutation test ก่อนถือว่าเสร็จ** — พังโค้ด
   ที่มันอ้างว่าคุ้มทีละจุด เทสต์ต้องแดง แล้วคืนโค้ด · พังแล้วยังเขียว = เทสต์
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


def portable_gates() -> list[dict]:
    """gate ที่ประกาศว่าเป็นกฎสากล — ตามลำดับในไฟล์ (เรียงตามหมวดอยู่แล้ว)"""
    gates = yaml.safe_load(GATES.read_text(encoding="utf-8"))["gates"]
    return [g for g in gates if g.get("portable")]


def _enforcement(gate: dict) -> str:
    """บรรทัดตัวบังคับ — ชี้ไปหาของจริงใน repo นี้ ไม่เขียนคำสั่งซ้ำ (ADR 0039)"""
    enforced = gate["enforced_by"]
    if gate["kind"] == "test":
        return " · ".join(f"`{t}`" for t in enforced["tests"])
    if gate["kind"] == "step":
        return f'job `{enforced["job"]}` step "{enforced["step"]}"'
    return f"job `{enforced['job']}`"


def render() -> str:
    """ประกอบทั้งใบ — ลำดับตาม gates.yaml ผล generate จึงซ้ำได้ไบต์ต่อไบต์"""
    lines = [PREAMBLE]
    for gate in portable_gates():
        born = re.sub(r"\s+", " ", gate["born_from"]).strip()
        lines.append(f"### `{gate['id']}`\n")
        lines.append(f"**กฎ:** {gate['title']}\n")
        lines.append(f"**เกิดจาก:** {born}\n")
        lines.append(f"**ตัวบังคับใน reference:** {_enforcement(gate)}\n")
    return "\n".join(lines)


def main() -> int:
    """เขียน SKILL.md ทับไฟล์เดิม แล้วบอกว่ามีอะไรเปลี่ยนไหม"""
    fresh = render()
    changed = not OUT.exists() or OUT.read_text(encoding="utf-8") != fresh
    OUT.write_text(fresh, encoding="utf-8")
    print(f"{'เขียนใหม่' if changed else 'ไม่มีอะไรเปลี่ยน'}: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
