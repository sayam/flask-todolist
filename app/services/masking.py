"""คำตัดสินการแสดงข้อมูลผู้ใช้ในหน้า admin — ต่อคอลัมน์ ที่เดียว (ADR 0045)

ค่าเริ่มต้น derive จากชั้นข้อมูลใน `docs/DATA-CLASSIFICATION.md`:
C1/C3 → `hidden` · C2 → `masked` · C4–C6 → `visible` — ตารางข้างล่างประกาศ
คำตัดสินจริงต่อคอลัมน์ และ `tests/test_masking.py` บังคับสองทิศ:
ทุกคอลัมน์ใน metadata ต้องถูกตัดสิน และคำตัดสินหลวมกว่าชั้นของมันไม่ได้
เว้นแต่อยู่ใน `EXCEPTIONS` พร้อมเหตุผล

การเปิดดูค่าเต็ม (unmask) เป็นการกระทำที่ลง audit — ดู `app/admin/`
"""

from __future__ import annotations

import fnmatch

HIDDEN = "hidden"
MASKED = "masked"
VISIBLE = "visible"

#: คำตัดสินต่อคอลัมน์ของตารางที่ถือข้อมูลผู้ใช้ — คีย์คือ "ตาราง.คอลัมน์"
#: (คอลัมน์โครงระบบที่ไม่ใช่ของผู้ใช้ ใช้ pattern ท้ายไฟล์)
DECISIONS: dict[str, str] = {
    # tdl_user
    "tdl_user.id": VISIBLE,
    "tdl_user.username": VISIBLE,  # ข้อยกเว้น — ดู EXCEPTIONS
    "tdl_user.password_hash": HIDDEN,  # C1
    "tdl_user.first_name": MASKED,  # C2
    "tdl_user.last_name": MASKED,  # C2
    "tdl_user.role": VISIBLE,
    "tdl_user.locale": VISIBLE,
    "tdl_user.theme": VISIBLE,
    "tdl_user.mode": VISIBLE,
    "tdl_user.timezone_name": VISIBLE,
    "tdl_user.created_at": VISIBLE,
    "tdl_user.updated_at": VISIBLE,
    "tdl_user.deleted_at": VISIBLE,
    "tdl_user.purged_at": VISIBLE,
    "tdl_user.suspended_at": VISIBLE,
    # tdl_todo — เนื้อหาของผู้ใช้ (C3) ทั้งแถวไม่ใช่ธุระของผู้ดูแล
    "tdl_todo.title": HIDDEN,
    "tdl_todo.start_date": HIDDEN,
    "tdl_todo.due_date": HIDDEN,
    "tdl_todo.is_done": HIDDEN,
    # tdl_category
    "tdl_category.name": HIDDEN,  # C3
    # tdl_api_token
    "tdl_api_token.token_hash": HIDDEN,  # C1
    "tdl_api_token.name": HIDDEN,  # C3 — ชื่อที่ผู้ใช้ตั้งบอกว่าเครื่องไหนใช้
    "tdl_api_token.expires_at": VISIBLE,
    "tdl_api_token.revoked_at": VISIBLE,
}

#: pattern สำหรับคอลัมน์โครงระบบ (C4–C6) ที่ชื่อซ้ำกันทุกตาราง — ตรวจท้ายสุด
PATTERN_DECISIONS: dict[str, str] = {
    "*.id": VISIBLE,
    "*.user_id": VISIBLE,
    "*.category_id": VISIBLE,
    "*.created_at": VISIBLE,
    "*.updated_at": VISIBLE,
    "*.deleted_at": VISIBLE,
    "*.purged_at": VISIBLE,
    # audit (C5) และตารางของ plugin — หลักฐาน/ค่าที่ถูกจัดชั้นแล้วว่าโชว์ได้
    "tdl_audit.*": VISIBLE,
    "tdl_audit_lock.*": VISIBLE,
}

#: คอลัมน์ที่คำตัดสิน*หลวมกว่า*ค่าเริ่มต้นของชั้น — ต้องมีเหตุผลรายตัว
EXCEPTIONS: dict[str, str] = {
    "tdl_user.username": (
        "C2 แต่ visible: เป็นตัวระบุที่งานบริหารทุกงานอ้าง (เปลี่ยนบทบาท · "
        "set-password · export-user รับ username) และ log/audit ใช้เป็น actor "
        "อยู่แล้วตาม ADR 0011 — mask แล้วงานบริหารทำไม่ได้เลย"
    ),
}


def decision_for(table: str, column: str) -> str | None:
    """คำตัดสินของคอลัมน์หนึ่ง — core ตรงตัว → ของ plugin → pattern · ไม่รู้จัก = None

    คอลัมน์ของ plugin มาจาก `MASKING_DECISIONS` ใน models.py ของ plugin เอง
    (หลักเดียวกับ AUDIT_POLICIES — ADR 0023: ชื่อคอลัมน์ของ plugin ห้ามโผล่
    ในโค้ด core) · คืน None แทนการเดา — ผู้เรียกและเทสต์ partition ต้องเห็นว่า
    คอลัมน์ไหนยังไม่ถูกตัดสิน ไม่ใช่ได้ค่า default เงียบ ๆ
    """
    from app import plugins

    exact = DECISIONS.get(f"{table}.{column}")
    if exact is not None:
        return exact
    declared = plugins.masking_decisions()
    for key in (f"{table}.{column}", column):
        if key in declared:
            return declared[key]
    for pattern, decision in PATTERN_DECISIONS.items():
        if fnmatch.fnmatch(f"{table}.{column}", pattern):
            return decision
    return None


def masked(value: str | None) -> str:
    """ค่าแบบ mask: อักษรแรก + ••• — ว่าง/None ได้ขีดกลาง

    ไม่รักษาความยาว (ADR 0045: ความยาวชื่อไม่ใช่ความลับที่คุกคามจริงในบริบทนี้
    แต่ก็ไม่มีเหตุให้แจกฟรี)
    """
    if not value:
        return "—"
    return f"{value[0]}•••"


def display(table: str, column: str, value: str | None, *, unmasked: bool = False) -> str | None:
    """ค่าที่หน้า admin ได้เห็น — จุดตัดสินเดียวของทุก panel (ADR 0044)

    `unmasked=True` ใช้ได้เฉพาะเส้นทางที่ลง audit แล้วเท่านั้น และเปิดได้แค่
    ระดับ `masked` — ของ `hidden` ไม่มีทางออกจอไม่ว่าทางไหน
    """
    decision = decision_for(table, column)
    if decision == VISIBLE:
        return value
    if decision == MASKED:
        return value if unmasked else masked(value)
    return None
