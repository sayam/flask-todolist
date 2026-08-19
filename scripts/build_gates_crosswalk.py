"""สร้าง `docs/GATES-ASVS.md` — crosswalk ระหว่าง gate กับข้อ ASVS ที่มัน**หนุนจริง**

การเชื่อมสองทะเบียน (`gates.yaml` กับ `docs/ASVS.md`) ด้วยการเขียนมือทั้งสองฝั่ง
คือการสร้างที่ที่สามให้ drift — ที่นี่จึง **derive ทางเดียวจากหลักฐานที่มีอยู่**:
แถว ASVS ที่หลักฐานอ้างไฟล์เทสต์หรือ `ci:job` จะถูก map กลับไปหา gate ที่ถือ
ไฟล์/job นั้น ผ่าน partition ของ `gates.yaml` (ADR 0039 — ทุกไฟล์เทสต์ถูกตัดสิน
ว่าเป็นของ gate ตัวเดียว การ map จึงไม่มีทางกำกวม)

ผลพลอยได้ที่ตั้งใจ: เห็นชัดว่าแถวไหน **ผ่านด้วยด่านที่รันทุก push** และแถวไหน
**ผ่านด้วยเหตุผล/เอกสาร** (หลักฐานเป็น ADR หรือไฟล์โค้ด ไม่มีด่านรัน) —
สองอย่างนี้เป็นความเชื่อมั่นคนละระดับ และผู้ตรวจควรเห็นความต่างโดยไม่ต้องไล่อ่านเอง

ใช้: `pipenv run python scripts/build_gates_crosswalk.py` (เขียนไฟล์)
`tests/test_gates.py` เทียบไฟล์ที่ commit กับผล generate ทุกครั้งที่รันเทสต์

บทบาท: generator — สร้างไฟล์ที่ commit ไว้ — หลักฐานคือผลลัพธ์ต้องตรงกับที่ commit (coverage ไม่ใช่ตัววัดของชนิดนี้)
"""

from __future__ import annotations

import pathlib
import re
import sys

# pyyaml มากับ dev tools และไม่มี stub — ไม่คุ้มเพิ่ม dependency (types-PyYAML)
# เพื่อ type ของ safe_load ที่โครงถูกตรวจโดย tests/test_gates.py อยู่แล้ว
import yaml  # type: ignore[import-untyped]

ROOT = pathlib.Path(__file__).resolve().parent.parent
GATES = ROOT / "gates.yaml"
ASVS = ROOT / "docs" / "ASVS.md"
OUT = ROOT / "docs" / "GATES-ASVS.md"

# ตารางประเมินอยู่ใต้เครื่องหมายนี้เท่านั้น — คำนำมีตาราง backlog ที่หน้าตาเหมือนกัน
# (เครื่องหมายเดียวกับที่ tests/test_asvs.py และ build_asvs_worksheet.py ใช้)
ASSESSMENT_MARKER = "<!-- ตารางประเมินเริ่มที่นี่ — ทุกอย่างใต้บรรทัดนี้สร้างโดยสคริปต์ -->"

ROW = re.compile(r"^\|\s*(V\d+\.\d+\.\d+)\s*\|")
TEST_REF = re.compile(r"`(tests/test_\w+\.py)(?:::\w+)?`")
JOB_REF = re.compile(r"`ci:([a-z0-9-]+)`")
PASSED = "ผ่าน"

HEADER = """# Crosswalk: gate ↔ ASVS

**ไฟล์นี้ generate มา ห้ามแก้ด้วยมือ** — สร้างใหม่ด้วย
`pipenv run python scripts/build_gates_crosswalk.py`
(`tests/test_gates.py` เทียบกับผล generate ทุกครั้งที่รันเทสต์)

derive จากหลักฐานในตาราง `docs/ASVS.md`: แถวที่อ้างไฟล์เทสต์หรือ `ci:job`
ถูก map กลับไปหา gate ผ่าน partition ของ `gates.yaml` — ไม่มีการเขียน mapping
มือ จึงไม่มีที่ที่สามให้ drift (ADR 0039)
"""


def passed_rows() -> dict[str, str]:
    """แถวที่ประเมินว่า "ผ่าน" → ช่องหลักฐานดิบของแถวนั้น"""
    text = ASVS.read_text(encoding="utf-8")
    if ASSESSMENT_MARKER not in text:
        raise SystemExit("docs/ASVS.md ไม่มีเครื่องหมายแบ่งตารางประเมิน — โครงเอกสารเปลี่ยนไปแล้ว")

    found: dict[str, str] = {}
    for line in text.split(ASSESSMENT_MARKER, 1)[1].splitlines():
        if not ROW.match(line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 5 and cells[3] == PASSED:
            found[cells[0]] = cells[4]
    if not found:
        raise SystemExit("ไม่เจอแถวที่ผ่านเลย — ตัวอ่านพังหรือเปล่า")
    return found


def gate_lookups() -> tuple[dict[str, str], dict[str, list[str]]]:
    """(ไฟล์เทสต์ → gate id, job → gate id ของ kind job/step บน job นั้น)

    kind `test` ไม่ถูกนับฝั่ง job — ทุก gate ชนิดนั้นเกาะ job `test` การ map
    `ci:test` ไปหาทั้งสี่สิบ gate จะทำให้ crosswalk เป็นสัญญาณรบกวน ไม่ใช่ข้อมูล
    """
    gates = yaml.safe_load(GATES.read_text(encoding="utf-8"))["gates"]
    by_file: dict[str, str] = {}
    by_job: dict[str, list[str]] = {}
    for gate in gates:
        for path in gate["enforced_by"].get("tests") or []:
            by_file[path] = gate["id"]
        if gate["kind"] in ("job", "step"):
            by_job.setdefault(gate["enforced_by"]["job"], []).append(gate["id"])
    return by_file, {job: sorted(ids) for job, ids in by_job.items()}


def crosswalk() -> str:
    """ประกอบเอกสารทั้งใบ — ทุกลิสต์เรียงแล้ว ผล generate จึงซ้ำได้ไบต์ต่อไบต์"""
    rows = passed_rows()
    by_file, by_job = gate_lookups()

    gate_rows: dict[str, set[str]] = {}
    unbacked: list[str] = []
    for vid, evidence in rows.items():
        supported = {by_file[f] for f in TEST_REF.findall(evidence) if f in by_file}
        for job in JOB_REF.findall(evidence):
            supported.update(by_job.get(job, []))
        if supported:
            for gid in supported:
                gate_rows.setdefault(gid, set()).add(vid)
        else:
            unbacked.append(vid)

    def vkey(vid: str) -> tuple[int, ...]:
        return tuple(int(part) for part in vid[1:].split("."))

    lines = [HEADER]
    lines.append(
        f'สรุป: แถวที่ประเมินว่า "ผ่าน" {len(rows)} ข้อ · '
        f"มี gate หนุน {len(rows) - len(unbacked)} · "
        f"ผ่านด้วยเหตุผล/เอกสาร (ไม่มีด่านรัน) {len(unbacked)}\n"
    )
    lines.append("## gate → ข้อ ASVS ที่หลักฐานของข้อนั้นชี้มาหา gate นี้\n")
    lines.append("| gate | ข้อ ASVS |")
    lines.append("|---|---|")
    for gid in sorted(gate_rows):
        rows_text = " · ".join(sorted(gate_rows[gid], key=vkey))
        lines.append(f"| `{gid}` | {rows_text} |")
    lines.append("")
    lines.append("## ข้อที่ผ่านด้วยเหตุผล/เอกสาร — ไม่มีด่านรันหนุน\n")
    lines.append(
        "ความเชื่อมั่นคนละระดับกับข้างบน: หลักฐานเป็น ADR/ไฟล์โค้ด/คำอธิบาย "
        "ซึ่งไม่ถูกรันซ้ำทุก push — รายการนี้คือที่ที่ควรมองหา gate ตัวถัดไป\n"
    )
    lines.append(" · ".join(sorted(unbacked, key=vkey)))
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    """เขียน crosswalk ทับไฟล์เดิม แล้วบอกว่ามีอะไรเปลี่ยนไหม"""
    fresh = crosswalk()
    changed = not OUT.exists() or OUT.read_text(encoding="utf-8") != fresh
    OUT.write_text(fresh, encoding="utf-8")
    print(f"{'เขียนใหม่' if changed else 'ไม่มีอะไรเปลี่ยน'}: {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
