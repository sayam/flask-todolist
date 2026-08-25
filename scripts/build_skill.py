"""สร้าง `SKILL.md` (baseline) และ `SKILL-TODOLIST.md` (business) — ADR 0042

**ตัวเรนเดอร์ไม่ได้อยู่ที่นี่แล้ว** — มันคือ `verifiable_gates.skill` ใน
submodule `vendor/verifiable-gates` (ADR 0077) · ไฟล์นี้เหลือหน้าที่เดียวคือ
บอกว่า *ของของ repo นี้* อยู่ที่ไหน: ทะเบียนคือ `gates.yaml` คำนำอยู่ใน
`docs/skill/` และหัวข้อฟิลด์เป็นภาษาไทย

ทั้งสามอย่างเคยเป็นค่าคงที่ในตัวเรนเดอร์ ซึ่งแปลว่าโปรเจกต์อื่นที่หยิบไปใช้
จะต้องแบกคำนำของ repo นี้ไปด้วย — คำนำของ rule sheet เป็นร้อยแก้วที่โปรเจกต์
เขียนถึงตัวเอง จึงเป็นข้อมูล ไม่ใช่โค้ด

ใช้: `pipenv run python scripts/build_skill.py` (`--check` = ไม่เขียน แค่บอกว่าตรงไหม)
`tests/test_skill.py` เทียบไฟล์ที่ commit กับผล generate ทุกครั้งที่รันเทสต์

บทบาท: generator — สร้างไฟล์ที่ commit ไว้ — หลักฐานคือผลลัพธ์ต้องตรงกับที่ commit (coverage ไม่ใช่ตัววัดของชนิดนี้)
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
VENDOR = ROOT / "vendor" / "verifiable-gates" / "src"
sys.path.insert(0, str(VENDOR))

from verifiable_gates import registry, skill  # noqa: E402 — ต้องต่อ path ให้ vendor ก่อน import

# หัวข้อของสามช่องในแต่ละข้อ — เป็นภาษาไทยเพราะทั้ง repo นี้เป็นภาษาไทย
LABELS = ("กฎ", "เกิดจาก", "ตัวบังคับใน reference")

GATES = ROOT / "gates.yaml"
OUT = ROOT / "SKILL.md"
OUT_BUSINESS = ROOT / "SKILL-TODOLIST.md"
PREAMBLE_DIR = ROOT / "docs" / "skill"

# แต่ละใบ: ไฟล์ผลลัพธ์ · คำนำของใบนั้น · ชั้นของกฎที่หยิบมาเรนเดอร์
SHEETS = (
    (OUT, PREAMBLE_DIR / "preamble-baseline.md", "baseline"),
    (OUT_BUSINESS, PREAMBLE_DIR / "preamble-business.md", "business"),
)
PREAMBLE_FOR = {layer: preamble for _out, preamble, layer in SHEETS}


def portable_gates(layer: str | None = None) -> list[dict]:
    """gate ที่ export ได้ของ repo นี้ — ห่อของใน vendor ให้ผู้เรียกเดิมใช้ชื่อเดิมได้"""
    return skill.portable_gates(registry.load(GATES), layer)


def render(layer: str = "baseline") -> str:
    """เรนเดอร์หนึ่งใบด้วยคำนำและหัวข้อของ repo นี้ — ผลเดียวกับที่ `build()` เขียนลงไฟล์

    มีไว้ให้เทสต์และ `build_agent_skill.py` เรียกผลสดโดยไม่ต้องแตะดิสก์ —
    ban list ของคำต้องห้ามตรวจที่ผล render ไม่ใช่ที่ไฟล์ จึงจับได้ตั้งแต่ตอนที่
    คำนั้นถูกพิมพ์ลง `gates.yaml` ก่อนจะมีใคร generate
    """
    preamble = PREAMBLE_FOR[layer].read_text(encoding="utf-8")
    return skill.render(registry.load(GATES), preamble, layer, LABELS)


def build(*, check: bool = False) -> int:
    """เรนเดอร์ทั้งสองใบด้วยตัวใน vendor — คืน exit code ที่แย่ที่สุดที่เจอ"""
    worst = 0
    for out, preamble, layer in SHEETS:
        args = [
            "--registry",
            str(ROOT / "gates.yaml"),
            "--preamble",
            str(preamble),
            "--out",
            str(out),
            "--layer",
            layer,
            "--labels",
            "|".join(LABELS),
        ]
        if check:
            args.append("--check")
        worst = max(worst, skill.main(args))
    return worst


def main() -> int:
    parser = argparse.ArgumentParser(description="สร้างใบกฎจาก gates.yaml ด้วยตัวเรนเดอร์ใน vendor")
    parser.add_argument("--check", action="store_true", help="ไม่เขียน — แดงถ้าไฟล์ที่ commit ไม่ตรง")
    return build(check=parser.parse_args().check)


if __name__ == "__main__":
    sys.exit(main())
