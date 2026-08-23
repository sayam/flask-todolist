"""เลขที่เอกสารโฆษณาไว้ ต้องซิงก์ได้ด้วยคำสั่งเดียว — audit รอบ 25 ข้อ 3

ทุกเลขที่ประกาศออกไปมีเทสต์อ่านคู่กับของจริงแล้ว (นั่นคือของดีและต้องคงไว้) แต่
**การทำให้มันตรงยังเป็นงานมือทุกครั้ง** · วัดด้วยการทดลองจริงในชิ้นงานแยกเมื่อ
2026-08-22: เพิ่ม ADR หนึ่งใบ ทำให้เทสต์แดงสามไฟล์ที่ต้องไล่แก้ทีละที่
(`README.md` สองบรรทัด · `CONTRIBUTING.md` · `CHANGELOG.md`) และเพิ่ม gate หนึ่งตัว
ทำให้ต้องแก้สองเลขใน `docs/ROADMAP-GOVERNANCE.md` — รวมแล้ว **25 จาก 200 commit
ล่าสุด (12.5%) เป็นการซิงก์ตัวเลขล้วน ๆ**

สคริปต์นี้ไม่ได้ทำให้ด่านอ่อนลงแม้แต่ข้อเดียว — มันแค่รับงานมือไปทำแทน:
เทสต์ยังเป็นคนตัดสิน ส่วนตัวนี้เป็นคนพิมพ์

ใช้:
    python3 scripts/sync_counts.py            # บอกว่าที่ไหนยังไม่ตรง (exit 1 ถ้าไม่ตรง)
    python3 scripts/sync_counts.py --write     # แก้ให้ตรงทุกที่
    python3 scripts/sync_counts.py --about     # พิมพ์ข้อความของช่อง About ที่ถูกต้อง

**ที่ไม่ทำให้โดยตั้งใจ**: แถวในดัชนี `docs/adr/README.md` — แถวใหม่ต้องมีคำอธิบาย
ของมันเอง ซึ่งเป็นงานเขียน ไม่ใช่งานนับ · สคริปต์จึงบอกว่ามันขาด แต่ไม่แต่งให้

บทบาท: generator — สร้างไฟล์ที่ commit ไว้ — หลักฐานคือผลลัพธ์ต้องตรงกับที่ commit (coverage ไม่ใช่ตัววัดของชนิดนี้)
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

import yaml  # type: ignore[import-untyped]  # pyyaml มากับ dev tools และไม่มี stub

ROOT = pathlib.Path(__file__).resolve().parent.parent
ADR_DIR = ROOT / "docs" / "adr"
GATES = ROOT / "gates.yaml"
AUDIT_LOG = ROOT / "docs" / "AUDIT-LOG.md"
AUDIT_ROW = re.compile(r"^\|\s*(\d+)\s*\|", re.MULTILINE)

# (ไฟล์ที่สคริปต์นี้เขียน, รูปแบบที่ล้อมเลขไว้) — กลุ่มที่ 1 คือเลข · รายการนี้มาจากการวัดว่าอะไร
# *แดงจริง* ตอนเพิ่มของหนึ่งชิ้น ไม่ใช่จากการเดาว่าน่าจะมีที่ไหนบ้าง
TARGETS = {
    "adrs": [
        ("README.md", r"(?<=\| )(\d+)(?= architecture decision records)"),
        ("README.md", r"(?<=\(docs/adr/\) )(\d+)(?= ใบ)"),
        ("CONTRIBUTING.md", r"(?<=the )(\d+)(?= records in \[`docs/adr/`\])"),
        ("CHANGELOG.md", r"(?<=lives in the )(\d+)(?= records in)"),
    ],
    "gates": [
        ("docs/ROADMAP-GOVERNANCE.md", r"(?<=รวม )(\d+)(?= gate)"),
    ],
    # จำนวนรอบ audit เปลี่ยนทุกครั้งที่ลงทะเบียนรอบใหม่ — และสองใบแรกคือบัตร
    # ประจำตัวที่ Zenodo อ่านไปตีพิมพ์ใต้ DOI ถาวร (ADR 0072 · audit รอบ 24)
    # จำนวนกฎ baseline ที่ส่งออกจริง — เปลี่ยนทุกครั้งที่มี gate ใหม่ที่ `portable`
    # และ `layer: baseline` · **ไม่ได้อยู่ในรายการนี้มาจนถึง audit รอบ 26** จึงต้อง
    # ไล่แก้สามที่ด้วยมือทุกครั้ง ซึ่งเป็นภาษีชนิดเดียวกับที่รอบ 25 สร้างสคริปต์นี้มาลด
    "baseline_rules": [
        ("README.md", r"(\d+)(?= framework-agnostic baseline rules)"),
        ("README.md", r"(?<=กฎ baseline )(\d+)(?= ข้อ)"),
        ("docs/ROADMAP-INFRA.md", r"(?<=ปัจจุบัน )(\d+)(?=\))"),
    ],
    "audits": [
        ("CITATION.cff", r"(\d+)(?= recorded audit rounds)"),
        (".zenodo.json", r"(\d+)(?= recorded audit rounds)"),
        ("docs/BEST-PRACTICES.md", r"(?<=\*\*)(\d+)(?=\*\* recorded governance audits)"),
        ("docs/BEST-PRACTICES.md", r"(?<=audit )(\d+)(?= รอบ)"),
    ],
}


def measured() -> tuple[dict[str, int], list[dict]]:
    """(เลขที่นับได้, ตัว gate ทั้งหมด) — นับจากทะเบียนที่เป็นแหล่งจริง ไม่ใช่จากเอกสารอีกใบ"""
    gates = yaml.safe_load(GATES.read_text(encoding="utf-8"))["gates"]
    counted = {
        "adrs": len([p for p in ADR_DIR.glob("*.md") if p.name[:4].isdigit()]),
        "gates": len(gates),
        "baseline_rules": len(
            [g for g in gates if g.get("portable") and g.get("layer") == "baseline"]
        ),
        "audits": len(AUDIT_ROW.findall(AUDIT_LOG.read_text(encoding="utf-8"))),
    }
    return counted, gates


# ลำดับของ pillar ในบรรทัดที่เอกสารประกาศ — **ตายตัว** เพราะบรรทัดที่สลับลำดับได้
# คือบรรทัดที่ diff อ่านไม่รู้เรื่อง · ชนิดที่ไม่อยู่ในลำดับนี้ต้องดัง ไม่ใช่หายไปเงียบ
PILLARS = ("security", "devx", "manageability", "performance")


def pillar_line(gates: list[dict]) -> str:
    """บรรทัดสัดส่วน pillar ที่ `tests/test_gates.py` อ่านคู่กับ `gates.yaml`"""
    tally: dict[str, int] = {}
    for gate in gates:
        tally[gate["pillar"]] = tally.get(gate["pillar"], 0) + 1

    unknown = sorted(set(tally) - set(PILLARS))
    if unknown:
        raise ValueError(f"pillar ที่ตัวซิงก์ไม่รู้จัก: {unknown} — เติมใน PILLARS ก่อน")
    return " · ".join(f"{name} {tally.get(name, 0)}" for name in PILLARS)


def drift() -> list[tuple[pathlib.Path, str, str, str]]:
    """(ไฟล์, รูปแบบ, ค่าที่เขียนไว้, ค่าที่ควรเป็น) ของทุกที่ที่ยังไม่ตรง"""
    real, gates = measured()
    found = []
    for fact, places in TARGETS.items():
        want = str(real[fact])
        for name, pattern in places:
            path = ROOT / name
            body = path.read_text(encoding="utf-8")
            said = re.search(pattern, body)
            if said is None:
                found.append((path, pattern, "(หาไม่เจอ)", want))
            elif said.group(1) != want:
                found.append((path, pattern, said.group(1), want))

    roadmap = ROOT / "docs" / "ROADMAP-GOVERNANCE.md"
    body = roadmap.read_text(encoding="utf-8")
    want_line = pillar_line(gates)
    said = re.search(r"เป็น (security \d+ · devx \d+ · manageability \d+ · performance \d+)", body)
    if said is None:
        found.append((roadmap, "pillar tally", "(หาไม่เจอ)", want_line))
    elif said.group(1) != want_line:
        found.append((roadmap, "pillar tally", said.group(1), want_line))
    return found


def write(items: list[tuple[pathlib.Path, str, str, str]]) -> None:
    """แก้ทีละที่ — ไม่แตะอย่างอื่นเลย เพราะ diff ที่กว้างกว่าที่จำเป็นคือ diff ที่ไม่มีใครอ่าน"""
    for path, pattern, _said, want in items:
        body = path.read_text(encoding="utf-8")
        if pattern == "pillar tally":
            body = re.sub(
                r"(?<=เป็น )security \d+ · devx \d+ · manageability \d+ · performance \d+",
                want,
                body,
                count=1,
            )
        else:
            body = re.sub(pattern, want, body, count=1)
        path.write_text(body, encoding="utf-8")


def about_text() -> str:
    """ข้อความของช่อง About ที่ `ci:posture` จะยอมรับ (ADR 0072)"""
    real, _gates = measured()
    version = re.search(
        r'__version__ = "([^"]+)"', (ROOT / "app" / "__init__.py").read_text(encoding="utf-8")
    )
    return (
        f"v{version.group(1) if version else '?'} · {real['gates']} machine-checked gates, "
        f"{real['adrs']} ADRs, {real['audits']} recorded governance audits"
    )


def missing_index_rows() -> list[str]:
    """ADR ที่มีไฟล์แต่ยังไม่มีแถวในดัชนี — บอกอย่างเดียว ไม่แต่งให้"""
    index = (ADR_DIR / "README.md").read_text(encoding="utf-8")
    return sorted(
        path.name
        for path in ADR_DIR.glob("*.md")
        if path.name[:4].isdigit() and f"({path.name})" not in index
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="แก้ให้ตรงแทนที่จะรายงานเฉย ๆ")
    parser.add_argument("--about", action="store_true", help="พิมพ์ข้อความของช่อง About")
    args = parser.parse_args(argv)

    if args.about:
        print(about_text())
        return 0

    items = drift()
    orphans = missing_index_rows()
    if args.write and items:
        write(items)
        print(f"ซิงก์แล้ว {len(items)} ที่:")
        for path, _pattern, said, want in items:
            print(f"  - {path.relative_to(ROOT)}: {said} → {want}")
    elif items:
        print("เลขที่โฆษณาไว้ยังไม่ตรงกับของจริง:", file=sys.stderr)
        for path, _pattern, said, want in items:
            print(f"  - {path.relative_to(ROOT)}: เขียนไว้ {said} ควรเป็น {want}", file=sys.stderr)
        print("  แก้ทั้งหมดด้วย: python3 scripts/sync_counts.py --write", file=sys.stderr)
    else:
        print("เลขทุกตัวที่โฆษณาไว้ตรงกับของจริงแล้ว")

    if orphans:
        print(f"ADR ที่ยังไม่มีแถวในดัชนี (ต้องเขียนคำอธิบายเอง): {orphans}", file=sys.stderr)
    return 1 if (items and not args.write) or orphans else 0


if __name__ == "__main__":
    sys.exit(main())
