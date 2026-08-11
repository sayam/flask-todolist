"""การเขียนฐานข้อมูลต้องผ่านทางที่ถูกดักไว้เท่านั้น (DoD ของ Phase 2)

Phase 2 ตั้งกติกาสองข้อที่ **เป็นสถานะ ไม่ใช่เหตุการณ์** — มันจริงอยู่ตอนนี้
แต่กลายเป็นเท็จได้เงียบ ๆ ทันทีที่มีใครเพิ่ม route ใหม่:

1. **ลบจริงได้ที่ `app/purge.py` ที่เดียว** ที่อื่นทำได้แค่ soft delete
   หลุดเมื่อไหร่ = ข้อมูลที่ผู้ใช้ยังกู้คืนได้ตามระยะ 30 วันหายไปจริง
2. **audit ดักที่ event `after_flush` ของ ORM เท่านั้น** — bulk update/delete
   ระดับ Core และ raw SQL **ไม่ถูกบันทึก** หลุดเมื่อไหร่ = มีการแก้ข้อมูลที่ไม่มี
   ร่องรอย ทั้งที่ทั้งระบบออกแบบมาโดยเชื่อว่า write ทุกครั้งถูกบันทึก

ทั้งสองข้อถูกจดไว้ใน CLAUDE.md/ROADMAP ว่า "รู้ตัว" มาตลอด แต่ไม่มีอะไรบังคับ
กติกาที่พึ่งความจำของคนคือกติกาที่หลุดตอนกลับมาทำต่อคนละวัน ไฟล์นี้คือตัวบังคับ

**ไม่ได้ตรวจว่าโค้ดทำงานถูกไหม** — ตรวจว่าไม่มีใครเปิดทางที่เลี่ยงด่านไปได้
วิธีเดียวกับ `tests/test_migration_lint.py` และ `tests/test_plugins.py`
"""

import pathlib
import re

APP = pathlib.Path(__file__).resolve().parent.parent / "app"

# `app/purge.py` เป็นจุดเดียวที่ได้รับอนุญาตให้ลบจริงตาม ADR 0014 —
# ทั้งไฟล์จึงถูกยกเว้น การย้ายโค้ดลบออกไปไฟล์อื่นคือสิ่งที่เทสต์นี้ต้องจับได้
EXEMPT_FILES = {"purge.py"}

# ข้อยกเว้นรายบรรทัดที่ทบทวนแล้วว่าปลอดภัย — คู่ของ (ไฟล์, ข้อความที่ต้องมีในบรรทัด)
# **เพิ่มรายการที่นี่ = ยอมรับความเสี่ยงใหม่ ต้องอธิบายให้ได้ว่าทำไมถึงไม่เลี่ยงด่าน**
ALLOWED_LINES = {
    # ตั้งค่า connection ตอนเชื่อมต่อ ไม่ได้แตะข้อมูลสักแถว
    # ย้ายจาก `app/db_engine.py` มาอยู่กับยี่ห้อที่มันเป็นของตอน P5-05 (ADR 0026)
    # — ด่านนี้จับการย้ายได้ตอนนั้นพอดี ซึ่งเป็นสิ่งที่ allowlist ควรทำ:
    # ย้ายโค้ดที่ได้รับข้อยกเว้นแล้วต้องมีคนมาทบทวนใหม่ ไม่ใช่ตามไปเงียบ ๆ
    ("backend.py", "PRAGMA foreign_keys=ON"),
    # ปิด MFA = ลบความลับทิ้งจริง ไม่ใช่ซ่อน — ความลับ TOTP เป็นชั้น C1 เหมือน
    # รหัสผ่าน (ไม่มีเหตุผลให้เก็บต่อ) และตารางนี้เป็นของ plugin ซึ่ง purge job
    # ของ core ไม่รู้จัก ถ้า soft delete ก็จะไม่มีใครมาล้างให้เลย (ADR 0023/0024)
    ("factor.py", "db.session.delete(row)"),
    # ปิดบัญชี = ลบข้อมูลที่ plugin ถือไว้ทิ้งจริง ด้วยเหตุผลเดียวกับบรรทัดข้างบน:
    # ตารางของ plugin อยู่นอกวงจร purge ของ core การซ่อนแถวไว้จึงแปลว่าไม่มีใคร
    # มาล้างมันเลยตลอดกาล — และสำหรับความลับชั้น C1 นั่นคือการเก็บกุญแจของบัญชี
    # ที่ปิดไปแล้วไว้ตลอดกาล (ADR 0034 ข้อ 4)
    ("personal_data.py", "db.session.delete(row)"),
}

FORBIDDEN = {
    "session.delete()": (
        re.compile(r"\bsession\.delete\("),
        "ลบแถวจริง — ที่อื่นนอก purge.py ต้องใช้ soft_delete() แทน",
    ),
    "bulk .delete()": (
        re.compile(r"\.delete\(\s*\)"),
        "bulk delete ระดับ Core ไม่ผ่าน after_flush จึงไม่ถูกบันทึกลง audit",
    ),
    "synchronize_session": (
        re.compile(r"\bsynchronize_session\b"),
        "เป็นสัญญาณของ bulk update/delete ซึ่งไม่ถูกบันทึกลง audit",
    ),
    "text() raw SQL": (
        re.compile(r"\btext\("),
        "raw SQL ไม่ผ่าน ORM จึงไม่ถูกบันทึกลง audit และเลี่ยงตัวกรอง soft delete",
    ),
    "execute() ด้วยสตริงดิบ": (
        re.compile(r"\.execute\(\s*f?[\"']"),
        "raw SQL ไม่ผ่าน ORM จึงไม่ถูกบันทึกลง audit และเลี่ยงตัวกรอง soft delete",
    ),
    "execute() ด้วย Core DML": (
        re.compile(r"\.execute\(\s*(delete|update|insert)\("),
        "DML ระดับ Core ไม่ผ่าน after_flush จึงไม่ถูกบันทึกลง audit",
    ),
}


def _offenders():
    """ทุกบรรทัดใน app/ ที่ตรงกับ pattern ต้องห้ามและไม่ได้อยู่ในข้อยกเว้น"""
    found = []
    for path in sorted(APP.rglob("*.py")):
        if path.name in EXEMPT_FILES:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            # คอมเมนต์อธิบายกติกาไม่ใช่โค้ดที่ทำงาน จึงไม่นับ
            if line.lstrip().startswith("#"):
                continue
            for label, (pattern, reason) in FORBIDDEN.items():
                if not pattern.search(line):
                    continue
                if any(path.name == name and needle in line for name, needle in ALLOWED_LINES):
                    continue
                found.append(f"{path.relative_to(APP.parent)}:{lineno} [{label}] {reason}")
    return found


def test_no_write_bypasses_the_audit_and_soft_delete_gates():
    offenders = _offenders()
    assert not offenders, (
        "เจอการเขียนฐานข้อมูลที่เลี่ยงด่านของ Phase 2:\n"
        + "\n".join(offenders)
        + "\n\nลบจริงได้ที่ app/purge.py ที่เดียว และ write ทุกครั้งต้องผ่าน ORM"
        + "\nถ้าจำเป็นจริง ๆ ต้องเพิ่มใน ALLOWED_LINES พร้อมเหตุผล (ดู docstring)"
    )


def test_the_scanner_actually_reads_files():
    """กันเทสต์ข้างบนเขียวเพราะหาไฟล์ไม่เจอ ไม่ใช่เพราะโค้ดสะอาด

    ถ้า path ผิดหรือ rglob พัง `_offenders()` จะคืนลิสต์ว่างเหมือนตอนผ่านจริง
    แยกสองกรณีนี้ไม่ออกเลยถ้าไม่ยืนยันว่ามันอ่านไฟล์ได้จริง
    """
    scanned = list(APP.rglob("*.py"))
    assert len(scanned) > 10, f"สแกนเจอแค่ {len(scanned)} ไฟล์ — path น่าจะผิด"
    assert any(p.name == "routes.py" for p in scanned)
