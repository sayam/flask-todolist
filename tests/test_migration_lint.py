"""กติกา dialect ของ migration (ดู CLAUDE.md "วินัย dialect")

migrations/ ถูก exclude จาก ruff — ไฟล์นี้คือตัวคุมแทน
"""

import pathlib
import re

VERSIONS = pathlib.Path(__file__).resolve().parent.parent / "migrations" / "versions"

# migration เก่าที่เขียนก่อนมีกติกา — จะถูกล้างด้วย baseline squash ตอน Phase 5
# ห้ามเพิ่มรายการใหม่ใน allowlist นี้ (การเพิ่ม = ยอมรับหนี้ใหม่ ต้องมี ADR)
LEGACY_ALLOWLIST = {"296ab616c11b_split_theme_into_theme_name_mode.py"}

# ตาราง user เป็น reserved word ใน PostgreSQL/Oracle/MSSQL
# raw SQL ที่อ้างแบบไม่ quote จะพังตอน fresh install บนยี่ห้อพวกนั้น
UNQUOTED_USER = re.compile(
    r"""(FROM|UPDATE|INTO|JOIN|TABLE)\s+user\b(?!["'`])""",
    re.IGNORECASE,
)


def test_no_unquoted_user_table_in_new_migrations():
    offenders = []
    for path in sorted(VERSIONS.glob("*.py")):
        if path.name in LEGACY_ALLOWLIST:
            continue
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if UNQUOTED_USER.search(line):
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
    assert not offenders, (
        "raw SQL อ้างตาราง user แบบไม่ quote — พังบน PostgreSQL/Oracle/MSSQL:\n" + "\n".join(offenders)
    )


def test_legacy_allowlist_matches_reality():
    """allowlist ต้องชี้ไฟล์ที่มีอยู่จริงและยังสกปรกจริง — กัน allowlist ค้างหลัง squash"""
    for name in LEGACY_ALLOWLIST:
        path = VERSIONS / name
        assert path.is_file(), f"{name} หายไปแล้ว — ลบออกจาก allowlist ได้"
        assert UNQUOTED_USER.search(path.read_text()), f"{name} สะอาดแล้ว — ลบออกจาก allowlist ได้"
