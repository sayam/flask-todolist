"""ตรวจสุขภาพของ *ข้อมูลที่นอนอยู่ในฐานตอนนี้* — อ่านอย่างเดียว ไม่แก้อะไร

**สิบแปดรอบของ audit ตรวจทุกอย่างยกเว้นข้อมูล** (audit รอบ 19) — โค้ด · config ·
เอกสาร · CI · ทะเบียน · แม้แต่เครื่องมือที่ตรวจเครื่องมือ ทั้งหมดอยู่ใน git และ
ตรวจซ้ำได้ด้วยการอ่านไฟล์ · **ข้อมูลเป็นสิ่งเดียวในระบบที่ไม่อยู่ใน git และเป็น
สิ่งเดียวที่ผู้ใช้เห็น**

วัดตอนตั้งของนี้: CLI มี 26 คำสั่ง ที่ *ถาม* ข้อมูลว่ายังดีอยู่ไหมมี 1 (`audit-verify`)
และคำว่า `foreign_key_check` ไม่ปรากฏที่ไหนใน repo แม้แต่ครั้งเดียว · แถวกำพร้า
ที่ปลูกไว้ผ่านทุกคำสั่ง ทุก healthcheck และทุก job

## สี่คำถามที่ตอบได้ด้วยการอ่านฐานอย่างเดียว

1. มีแถวที่ชี้ไปหาแถวที่ไม่มีอยู่แล้วไหม (referential integrity)
2. สาย audit ยังต่อครบและหางยังตรงกับสมอไหม
3. มีชื่อผู้ใช้ที่ชนกันแบบ casefold ไหม (audit รอบ 19 ข้อ 2)
4. มีข้อมูลที่พ้นระยะเก็บรักษาแล้วแต่ยังอยู่ไหม (นโยบายเป็นจริงก็ต่อเมื่อมีคนรัน purge)

## ทำไมอ่านอย่างเดียว

เครื่องมือที่ซ่อมเองคือเครื่องมือที่ไม่มีใครกล้ารันบนฐานจริง — และวันที่มันซ่อมผิด
จะไม่มีใครรู้ว่าเดิมเป็นอย่างไร · ที่นี่รายงานอย่างเดียว ส่วนการแก้เป็นการตัดสินใจ
ของคน (หลักเดียวกับ `preview_expired()` ที่แยกจาก `purge_expired()` คนละฟังก์ชัน)

**ไม่ใช้ `PRAGMA foreign_key_check`** เพราะเป็นของ SQLite ยี่ห้อเดียว — ระบบนี้
รันบนสามยี่ห้อ (ADR 0026) ตัวตรวจจึงต้องอ่านความสัมพันธ์จาก metadata ของ
SQLAlchemy แล้วถามด้วย SQL ธรรมดาที่ทุกยี่ห้อตอบเหมือนกัน
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, inspect, select

import app.services.usernames as usernames_service
from app import audit, db, purge


@dataclass
class Finding:
    """ปัญหาหนึ่งข้อที่เจอ — `where` คือที่ที่คนต้องไปดูต่อ"""

    kind: str
    where: str
    detail: str


@dataclass
class Report:
    """ผลการตรวจทั้งใบ — `findings` ว่าง = ฐานนี้ตอบทุกคำถามได้ถูกต้อง"""

    findings: list[Finding] = field(default_factory=list)
    checks: int = 0

    @property
    def healthy(self) -> bool:
        return not self.findings


def _orphans(report: Report) -> None:
    """แถวที่ค่า foreign key ชี้ไปหาแถวที่ไม่มีอยู่

    FK ถูกบังคับตอน *เขียน* อยู่แล้ว (ADR: listener ของ sqlite เปิด `foreign_keys`
    และยี่ห้ออื่นบังคับให้เองอยู่แล้ว) — สิ่งที่ตัวนี้จับคือของที่เข้ามาทางอื่น:
    การกู้คืนที่ไม่ครบ · การย้ายฐาน · คนแก้ด้วย SQL ตรง ๆ · หรือช่วงที่ listener
    หลุดไปโดยไม่มีใครเห็น (ซึ่ง `tests/test_db_integrity.py` มีไว้กันแต่กันได้
    เฉพาะฐานของเทสต์ที่สร้างใหม่ทุกครั้งและสะอาดโดยนิยาม)
    """
    # **ตารางของ plugin ที่ยังไม่ถูกติดตั้ง ไม่มีอยู่จริงในฐาน** — models ของมัน
    # เข้ามาใน metadata ตอน import (ADR 0023) แต่ตารางเกิดตอน `plugin-install`
    # เท่านั้น · ถามหาข้อมูลในตารางที่ยังไม่มี = ล้มทั้งคำสั่ง ทั้งที่คำตอบที่ถูก
    # คือ "ไม่มีข้อมูลให้ตรวจ" (หลักเดียวกับที่ core เช็ค `is_installed()` ก่อนใช้)
    present = set(inspect(db.engine).get_table_names())
    for table in db.metadata.sorted_tables:
        if table.name not in present:
            continue
        for constraint in table.foreign_key_constraints:
            for element in constraint.elements:
                # ปลายทางของ FK เป็นตารางของ core เสมอ (ของ plugin ชี้ออกไปหา
                # `tdl_user` ไม่มีใครชี้เข้ามา) — ถ้าลูกมีอยู่ พ่อแม่ก็มีอยู่ด้วย
                child, parent = element.parent, element.column
                report.checks += 1
                missing = db.session.scalar(
                    select(func.count())
                    .select_from(table.outerjoin(parent.table, child == parent))
                    .where(child.is_not(None), parent.is_(None))
                )
                if missing:
                    report.findings.append(
                        Finding(
                            kind="orphan-row",
                            where=f"{table.name}.{child.name}",
                            detail=(
                                f"{missing} แถวชี้ไปที่ {parent.table.name}.{parent.name} ที่ไม่มีอยู่แล้ว"
                            ),
                        )
                    )


def _audit_chain(report: Report) -> None:
    """สายยังต่อครบ และหางยังตรงกับสมอ (audit รอบ 19 ข้อ 1)"""
    report.checks += 1
    try:
        audit.verify_chain()
    except audit.ChainError as broken:
        report.findings.append(
            Finding(
                kind="audit-chain", where=f"tdl_audit id={broken.entry_id}", detail=broken.reason
            )
        )
    except audit.AnchorError as broken:
        report.findings.append(
            Finding(kind="audit-anchor", where="tdl_audit_lock", detail=str(broken))
        )


def _username_collisions(report: Report) -> None:
    """ชื่อที่ต่างกันแค่ตัวพิมพ์ = บัญชีเดียวกันในสายตาโควตากันเดารหัสผ่าน"""
    report.checks += 1
    for group in usernames_service.collisions():
        report.findings.append(
            Finding(
                kind="username-collision",
                where="tdl_user.username",
                detail=f"{group} ชนกันแบบ casefold — คนยิงชื่อหนึ่งจะล็อกอีกชื่อออกจากระบบ",
            )
        )


def _retention(report: Report) -> None:
    """ของที่พ้นระยะเก็บรักษาแล้วแต่ยังอยู่ — แปลว่าไม่มีอะไรรัน `purge-expired` ตามรอบ"""
    report.checks += 1
    due = purge.preview_expired()
    overdue = {
        "tasks": due.todos,
        "categories": due.categories,
        "tokens": due.api_tokens,
        "users": due.users_purged,
        "graph rows": due.graph_rows,
        "audit entries": due.audit_entries,
    }
    stuck = {name: count for name, count in overdue.items() if count}
    if stuck:
        report.findings.append(
            Finding(
                kind="retention-overdue",
                where="purge-expired",
                detail=(
                    "ข้อมูลที่พ้นระยะแล้วแต่ยังอยู่: "
                    + " · ".join(f"{name} {count}" for name, count in stuck.items())
                ),
            )
        )


def examine() -> Report:
    """ตรวจทุกข้อ แล้วคืนรายงาน — **ไม่เขียนอะไรลงฐานเลย**"""
    report = Report()
    _orphans(report)
    _audit_chain(report)
    _username_collisions(report)
    _retention(report)
    return report
