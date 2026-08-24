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
    python3 scripts/sync_counts.py --about --write   # ยิงเลขที่ถูกขึ้นช่อง About จริง

**`--about --write` เป็นทางเดียวในไฟล์นี้ที่คุยกับ GitHub** และมันต้องรันจาก
เครื่องของผู้ดูแลเท่านั้น ไม่ใช่จาก CI — `POSTURE_TOKEN` เป็น token อ่านอย่างเดียว
โดยตั้งใจ (ADR 0061) และการให้ CI มีสิทธิ์ `administration: write` เพื่อแก้ช่อง
โฆษณาหนึ่งช่อง คือการยกอำนาจเขียน *ท่าที* ของ repo ให้ไปป์ไลน์ ซึ่งแพงกว่าที่ได้
มาก · ที่นี่ถูกที่แล้วเพราะ `gh` บนเครื่องผู้ดูแลมีสิทธิ์ครบอยู่แล้ว

**ซิงก์ได้สามเลขกับหนึ่งรุ่น ไม่ใช่ทั้งสี่เลข** — `required checks` มาจาก
branch protection จริง ซึ่งนับจากดิสก์ไม่ได้ · ตัวนั้นปล่อยไว้ให้ `ci:posture`
จับเหมือนเดิม และมันเปลี่ยนเฉพาะตอนมีคนเพิ่ม/ถอด required check ซึ่งเป็นคำตัดสิน
ที่มีคนลงมืออยู่แล้ว ต่างจากเลขที่ขยับเองทุกครั้งที่ merge

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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gh

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


# ---------------------------------------------------------------- ช่อง About
#
# **ช่องนี้อยู่นอก git จึงไม่มี diff ไหนทำให้ใครสังเกตว่ามันเก่า** (ADR 0072) ·
# วัดแล้วสองครั้งใน session เดียวเมื่อ 2026-08-23/24: merge ของที่เพิ่ม gate
# หนึ่งตัว แล้ว `ci:posture` แดงทันทีด้วยเลขที่ต่างกันหนึ่ง — ครั้งแรก 112→115
# ครั้งที่สอง 115→116 · ขั้นตอนที่ต้องจำแล้วพลาดสองครั้งติด ไม่ใช่ความบังเอิญ
#
# `about_text()` รู้คำตอบที่ถูกมาตลอด แต่ไม่มีใครเอาไปยิง — เครื่องมือที่รู้คำตอบ
# แต่ไม่ได้ต่อสายไปปลายทาง คือรูปเดียวกับที่ audit รอบ 26 ทั้งรอบพูดถึง
# วลี → คีย์ของเลขที่นับจากดิสก์ได้ · `required checks` **ไม่อยู่ที่นี่โดยตั้งใจ**
# เพราะมันมาจาก branch protection จริง (ดูหัวไฟล์)
ABOUT_NUMBERS = {
    "machine-checked gates": "gates",
    "ADRs": "adrs",
    "recorded governance audits": "audits",
}


def current_version() -> str:
    """รุ่นที่ `app/__init__.py` ประกาศ — ช่อง About ต้องบอกรุ่นนี้ (ADR 0072)"""
    found = re.search(
        r'__version__ = "([^"]+)"', (ROOT / "app" / "__init__.py").read_text(encoding="utf-8")
    )
    if not found:
        raise ValueError("อ่าน __version__ จาก app/__init__.py ไม่ได้")
    return found.group(1)


def about_drift(description: str) -> list[tuple[str, str, str]]:
    """(อะไร, ที่เขียนไว้, ที่ควรเป็น) — เฉพาะของที่นับจากดิสก์ได้

    วลีที่หายไปจากช่อง About **ถูกรายงาน ไม่ใช่ถูกข้าม** — ตัวซิงก์ที่เงียบตอน
    หาไม่เจอ คือตัวที่บอกว่าตรงกันแล้วในวันที่มันไม่ได้อ่านอะไรเลย
    """
    real, _gates = measured()
    found = []
    version = current_version()
    said = re.search(r"v(\d[\w.+-]*)", description)
    if said is None:
        found.append(("รุ่น", "(หาไม่เจอ)", f"v{version}"))
    elif said.group(1) != version:
        found.append(("รุ่น", f"v{said.group(1)}", f"v{version}"))
    for phrase, key in ABOUT_NUMBERS.items():
        said = re.search(rf"(\d+) {re.escape(phrase)}", description)
        if said is None:
            found.append((phrase, "(หาไม่เจอ)", str(real[key])))
        elif int(said.group(1)) != real[key]:
            found.append((phrase, said.group(1), str(real[key])))
    return found


def about_patched(description: str) -> str:
    """ช่อง About ที่เลขถูกแก้ให้ตรงแล้ว — **ประโยคที่เหลือไม่ถูกแตะ**

    แทนที่ทีละเลขในที่เดิม ไม่ใช่เขียนทั้งช่องใหม่จาก `about_text()` เพราะช่องนั้น
    มีคำโฆษณาอย่างอื่นที่คนเขียนไว้ และการเขียนทับทั้งช่องคือการลบมันทิ้งเงียบ ๆ
    """
    real, _gates = measured()
    patched = re.sub(r"(?<=v)\d[\w.+-]*", current_version(), description, count=1)
    for phrase, key in ABOUT_NUMBERS.items():
        patched = re.sub(rf"\d+(?= {re.escape(phrase)})", str(real[key]), patched, count=1)
    return patched


def about_now() -> str:
    """ช่อง About ที่ GitHub ถืออยู่ตอนนี้"""
    return gh.run(["repo", "view", "--json", "description", "--jq", ".description"])


def about_push(description: str) -> None:
    """เขียนช่อง About กลับไป — ต้องเป็น token ของผู้ดูแล ไม่ใช่ของ CI (ดูหัวไฟล์)"""
    gh.run(["repo", "edit", "--description", description])


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

    if args.about and not args.write:
        print(about_text())
        return 0

    if args.about:
        live = about_now()
        found = about_drift(live)
        if not found:
            print("ช่อง About ตรงกับของจริงแล้ว")
            return 0
        about_push(about_patched(live))
        print(f"ยิงขึ้นช่อง About แล้ว {len(found)} ที่:")
        for what, said, want in found:
            print(f"  - {what}: {said} → {want}")
        print("  `required checks` ไม่ได้ถูกแตะ — นับจากดิสก์ไม่ได้ (ci:posture เฝ้าให้)")
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
