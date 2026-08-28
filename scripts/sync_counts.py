"""เลขที่เอกสารโฆษณาไว้ ต้องซิงก์ได้ด้วยคำสั่งเดียว — audit รอบ 25 ข้อ 3

**กลไกอยู่ที่ verifiable-gates แล้ว** (ADR 0077 · ขั้น 3d) — `verifiable_gates.advertised`
เป็นคนอ่านและคนแก้ · **ที่นี่เหลือทะเบียนว่าเลขไหนถูกโฆษณาไว้ที่ไหน** กับตัวนับ
ที่นับจากแหล่งจริงของ repo นี้

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

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vendor" / "verifiable-gates" / "src"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import gh  # noqa: E402 — ต้องต่อ path ให้ scripts/ ก่อน import
from verifiable_gates import advertised  # noqa: E402 — ต้องต่อ path ให้ vendor ก่อน import

ADR_DIR = ROOT / "docs" / "adr"
GATES = ROOT / "gates.yaml"
AUDIT_LOG = ROOT / "docs" / "AUDIT-LOG.md"
AUDIT_ROW = re.compile(r"^\|\s*(\d+)\s*\|", re.MULTILINE)

Place = advertised.Place

# **ถ้อยคำเป็นของ repo นี้ ตัว sentinel เป็นของห้องสมุด** — `advertised` รายงาน
# ค่าที่หาไม่เจอด้วยเครื่องหมายภาษาอังกฤษของมันเอง ส่วนคนที่อ่าน CI ของที่นี่
# อ่านไทย · การแปลจึงเกิดที่ขอบของการพิมพ์ ไม่ใช่ด้วยการส่งสตริงเข้าไปเป็น config
MISSING = "(หาไม่เจอ)"


def _said(value: str) -> str:
    """ค่าที่เขียนไว้ — เครื่องหมาย "หาไม่เจอ" ถูกแปลเป็นภาษาที่คนอ่าน"""
    return MISSING if value == advertised.MISSING else value


# (ไฟล์ที่สคริปต์นี้เขียน, รูปแบบที่ล้อมเลขไว้) — **กลุ่มที่ 1 คือค่าที่ต้องตรง**
# รายการนี้มาจากการวัดว่าอะไร *แดงจริง* ตอนเพิ่มของหนึ่งชิ้น ไม่ใช่จากการเดาว่า
# น่าจะมีที่ไหนบ้าง
TARGETS = {
    "adrs": [
        Place("README.md", r"\| (\d+) architecture decision records"),
        Place("README.md", r"\(docs/adr/\) (\d+) ใบ"),
        Place("CONTRIBUTING.md", r"the (\d+) records in \[`docs/adr/`\]"),
        Place("CHANGELOG.md", r"lives in the (\d+) records in"),
    ],
    "gates": [
        Place("docs/ROADMAP-GOVERNANCE.md", r"รวม (\d+) gate"),
    ],
    # จำนวนกฎ baseline ที่ส่งออกจริง — เปลี่ยนทุกครั้งที่มี gate ใหม่ที่ `portable`
    # และ `layer: baseline` · **ไม่ได้อยู่ในรายการนี้มาจนถึง audit รอบ 26** จึงต้อง
    # ไล่แก้สามที่ด้วยมือทุกครั้ง ซึ่งเป็นภาษีชนิดเดียวกับที่รอบ 25 สร้างสคริปต์นี้มาลด
    "baseline_rules": [
        Place("README.md", r"(\d+) framework-agnostic baseline rules"),
        Place("README.md", r"กฎ baseline (\d+) ข้อ"),
        Place("docs/ROADMAP-INFRA.md", r"ปัจจุบัน (\d+)\)"),
    ],
    # จำนวนรอบ audit เปลี่ยนทุกครั้งที่ลงทะเบียนรอบใหม่ — และสองใบแรกคือบัตร
    # ประจำตัวที่ Zenodo อ่านไปตีพิมพ์ใต้ DOI ถาวร (ADR 0072 · audit รอบ 24)
    "audits": [
        Place("CITATION.cff", r"(\d+) recorded audit rounds"),
        Place(".zenodo.json", r"(\d+) recorded audit rounds"),
        Place("docs/BEST-PRACTICES.md", r"audit (\d+) รอบ"),
    ],
    # **เคยมีที่สี่ และมันเป็นเป้าที่ผิด** (ถอด 2026-08-26): วลี
    # `**N** recorded governance audits` ในไฟล์นั้นไม่ได้อยู่ในประโยคของเรา —
    # มันอยู่ใน *เครื่องหมายคำพูดที่ยกข้อความจากเว็บ badge มา* เพื่อบันทึกว่าเขา
    # เก็บอะไรไว้ · ตัวซิงก์จึงกำลังจะ "แก้" หลักฐานของค่าที่ค้างอยู่ข้างนอก ให้
    # กลายเป็นค่าที่ถูกต้องของเรา ซึ่งลบสิ่งเดียวที่แถวนั้นมีไว้บันทึก · ที่ผ่านมา
    # มันเขียวเพราะคนเขียนคำพูดนั้นพิมพ์เลขของเราลงไปโดยไม่ได้ดูของจริง — ด่านที่
    # เขียวเพราะหลักฐานถูกกรอกผิด คือด่านที่เขียวเปล่า ๆ
    # **บรรทัดสัดส่วน pillar เป็นเป้าหมายธรรมดาแล้ว ไม่ใช่กรณีพิเศษ** — ค่าที่ซิงก์
    # เป็นข้อความ ไม่ใช่ตัวเลข กิ่งที่เคยแยกไว้ในทั้ง `drift` และ `write` จึงหายไป
    "pillar_tally": [
        Place(
            "docs/ROADMAP-GOVERNANCE.md",
            r"เป็น (security \d+ · devx \d+ · manageability \d+ · performance \d+)",
        ),
    ],
}

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


def measured() -> tuple[dict[str, str], list[dict]]:
    """(ค่าที่ควรเป็น, ตัว gate ทั้งหมด) — นับจากทะเบียนที่เป็นแหล่งจริง ไม่ใช่จากเอกสารอีกใบ"""
    gates = yaml.safe_load(GATES.read_text(encoding="utf-8"))["gates"]
    counted = {
        "adrs": len([p for p in ADR_DIR.glob("*.md") if p.name[:4].isdigit()]),
        "gates": len(gates),
        "baseline_rules": len(
            [g for g in gates if g.get("portable") and g.get("layer") == "baseline"]
        ),
        "audits": len(AUDIT_ROW.findall(AUDIT_LOG.read_text(encoding="utf-8"))),
    }
    return {
        **{name: str(value) for name, value in counted.items()},
        "pillar_tally": pillar_line(gates),
    }, gates


def drift() -> list[advertised.Drift]:
    """ทุกที่ที่เลขยังไม่ตรงกับของจริง"""
    real, _gates = measured()
    return advertised.drift(ROOT, TARGETS, real)


def write(items: list[advertised.Drift]) -> None:
    """แก้ทีละที่ — ไม่แตะอย่างอื่นเลย เพราะ diff ที่กว้างกว่าที่จำเป็นคือ diff ที่ไม่มีใครอ่าน"""
    advertised.write(ROOT, items)


def current_version() -> str:
    """รุ่นที่ `app/__init__.py` ประกาศ — ช่อง About ต้องบอกรุ่นนี้ (ADR 0072)"""
    found = re.search(
        r'__version__ = "([^"]+)"', (ROOT / "app" / "__init__.py").read_text(encoding="utf-8")
    )
    if not found:
        raise ValueError("อ่าน __version__ จาก app/__init__.py ไม่ได้")
    return found.group(1)


def about_text() -> str:
    """ข้อความของช่อง About ที่ `ci:posture` จะยอมรับ (ADR 0072)"""
    real, _gates = measured()
    return (
        f"v{current_version()} · {real['gates']} machine-checked gates, "
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
# `required checks` **ไม่อยู่ที่นี่โดยตั้งใจ** เพราะมันมาจาก branch protection จริง
ABOUT_NUMBERS = {
    "machine-checked gates": "gates",
    "ADRs": "adrs",
    "recorded governance audits": "audits",
}


def about_expectations(required: int | None = None) -> list[advertised.Expectation]:
    """สิ่งที่ช่อง About ต้องพูดให้ตรง — รุ่นหนึ่งข้อ กับเลขที่นับจากดิสก์ได้

    **นี่คือทะเบียนใบเดียวของสิ่งที่ช่อง About โฆษณา** — `scripts/audit_posture.py`
    (ด่านที่ตัดสินทุก push) กับ `--about` ของไฟล์นี้ (ตัวซิงก์) อ่านรายการเดียวกัน
    · ก่อน 2026-08-28 แต่ละฝั่งถือรายการของตัวเองและนับ ADR คนละวิธี
    (`glob("0*.md")` กับ `name[:4].isdigit()`) — สองใบที่ไม่มีอะไรบังคับให้ตรงกัน
    คือที่ที่สองที่ ADR 0039 ห้าม

    `required` คือจำนวน required check จาก branch protection จริง — นับจากดิสก์
    ไม่ได้ จึงเป็นของด่านเท่านั้น: ตัวซิงก์ไม่ส่งมา และรายการก็ไม่มีข้อนั้น
    (`_sync_about` บอกไว้ตรง ๆ ว่าไม่แตะ)
    """
    real, _gates = measured()
    found = [
        advertised.Expectation("รุ่น", r"v(\d[\w.+-]*)", current_version()),
        *(
            advertised.Expectation(phrase, rf"(\d+) {re.escape(phrase)}", real[key])
            for phrase, key in ABOUT_NUMBERS.items()
        ),
    ]
    if required is not None:
        found.append(
            advertised.Expectation("required checks", r"(\d+) required checks", str(required))
        )
    return found


def about_drift(description: str) -> list[tuple[str, str, str]]:
    """(อะไร, ที่เขียนไว้, ที่ควรเป็น) — เฉพาะของที่นับจากดิสก์ได้

    วลีที่หายไปจากช่อง About **ถูกรายงาน ไม่ใช่ถูกข้าม** — ตัวซิงก์ที่เงียบตอน
    หาไม่เจอ คือตัวที่บอกว่าตรงกันแล้วในวันที่มันไม่ได้อ่านอะไรเลย
    """
    return [
        (what, _said(said), want)
        for what, said, want in advertised.field_drift(description, about_expectations())
    ]


def about_patched(description: str) -> str:
    """ช่อง About ที่เลขถูกแก้ให้ตรงแล้ว — **ประโยคที่เหลือไม่ถูกแตะ**"""
    return advertised.field_patched(description, about_expectations())


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


def _sync_about() -> int:
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="แก้ให้ตรงแทนที่จะรายงานเฉย ๆ")
    parser.add_argument("--about", action="store_true", help="พิมพ์ข้อความของช่อง About")
    args = parser.parse_args(argv)

    if args.about and not args.write:
        print(about_text())
        return 0
    if args.about:
        return _sync_about()

    items = drift()
    orphans = missing_index_rows()
    if args.write and items:
        write(items)
        print(f"ซิงก์แล้ว {len(items)} ที่:")
        for item in items:
            print(f"  - {item.place.path}: {_said(item.said)} → {item.want}")
    elif items:
        print("เลขที่โฆษณาไว้ยังไม่ตรงกับของจริง:", file=sys.stderr)
        for item in items:
            print(
                f"  - {item.place.path}: เขียนไว้ {_said(item.said)} ควรเป็น {item.want}",
                file=sys.stderr,
            )
        print("  แก้ทั้งหมดด้วย: python3 scripts/sync_counts.py --write", file=sys.stderr)
    else:
        print("เลขทุกตัวที่โฆษณาไว้ตรงกับของจริงแล้ว")

    if orphans:
        print(f"ADR ที่ยังไม่มีแถวในดัชนี (ต้องเขียนคำอธิบายเอง): {orphans}", file=sys.stderr)
    return 1 if (items and not args.write) or orphans else 0


if __name__ == "__main__":
    sys.exit(main())
