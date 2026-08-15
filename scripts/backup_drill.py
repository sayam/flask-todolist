"""ซ้อม backup → เสียหาย → restore → ตรวจ ของฐานข้อมูล SQLite — บนสำเนา ไม่แตะต้นฉบับ

ปิดช่องว่าง `A.5.30`/`A.8.13` ของ docs/ISO27001.md: restore ที่ไม่เคยซ้อม
คือความหวัง ไม่ใช่แผน — สคริปต์นี้ถูกเรียกโดย `tests/test_backup_drill.py`
**ทุก push** (การซ้อมต่อเนื่อง ไม่ใช่พิธีปีละครั้ง) และรันมือกับฐานจริงได้:

    pipenv run python scripts/backup_drill.py instance/todolist.db

ขั้นตอน: online backup ด้วย API ของ sqlite (ปลอดภัยแม้มีคนเขียนอยู่) →
จำลองความเสียหาย (ลบไฟล์ "ที่ใช้งาน" ใน workdir — ต้นฉบับไม่ถูกแตะ) →
restore จาก backup → ตรวจ integrity + เทียบตาราง/จำนวนแถวกับต้นฉบับ
วิธี backup/restore ฉบับเต็ม (รวม MySQL/MariaDB และคีย์ encrypt) อยู่ใน
docs/RUNBOOK-BACKUP.md
"""

from __future__ import annotations

import pathlib
import shutil
import sqlite3
import sys
import tempfile


def _row_counts(db: pathlib.Path) -> dict[str, int]:
    """ตาราง → จำนวนแถว (เฉพาะตารางผู้ใช้ ไม่รวมของภายใน sqlite)"""
    with sqlite3.connect(db) as conn:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        # ชื่อตารางมาจาก sqlite_master ของไฟล์เอง ไม่ใช่ input ภายนอก — parametrize ชื่อตารางไม่ได้
        return {
            t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]  # noqa: S608
            for t in tables
        }


def drill(source: pathlib.Path, workdir: pathlib.Path) -> list[str]:
    """รันการซ้อมเต็มวง คืน list ของปัญหา (ว่าง = ผ่าน) — อ่านต้นฉบับอย่างเดียว"""
    try:
        return _drill(source, workdir)
    except sqlite3.DatabaseError as exc:
        # ไฟล์เสีย/ไม่ใช่ sqlite = ผลการซ้อมที่ต้องรายงาน ไม่ใช่ traceback
        return [f"ฐานข้อมูลอ่านไม่ได้ระหว่างซ้อม: {exc}"]


def _drill(source: pathlib.Path, workdir: pathlib.Path) -> list[str]:
    workdir.mkdir(parents=True, exist_ok=True)
    problems: list[str] = []
    expected = _row_counts(source)
    if not expected:
        return [f"{source} ไม่มีตารางเลย — ฐานเปล่าซ้อม restore ไม่ได้ความหมาย"]

    backup = workdir / "backup.db"
    live = workdir / "live.db"

    # 1) backup แบบ online — สำเนาที่สอดคล้องแม้ต้นฉบับกำลังถูกเขียน
    with sqlite3.connect(source) as src, sqlite3.connect(backup) as dst:
        src.backup(dst)

    # 2) จำลองการใช้งานแล้วเสียหาย: สำเนา "ที่ใช้งาน" ถูกทำลาย
    shutil.copy(backup, live)
    live.unlink()

    # 3) restore จาก backup
    shutil.copy(backup, live)

    # 4) ตรวจ: integrity ต้องสะอาด และตาราง/จำนวนแถวต้องตรงต้นฉบับ
    with sqlite3.connect(live) as conn:
        verdict = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if verdict != "ok":
        problems.append(f"integrity_check ได้ {verdict!r} ไม่ใช่ 'ok'")
    restored = _row_counts(live)
    if restored != expected:
        problems.append(f"ข้อมูลหลัง restore ไม่ตรงต้นฉบับ: {restored} != {expected}")
    if "tdl_alembic_version" in expected and restored.get("tdl_alembic_version", 0) < 1:
        problems.append("ตารางเวอร์ชันของ alembic หายหลัง restore — ฐานนี้ upgrade ต่อไม่ได้")
    return problems


def main() -> int:
    if len(sys.argv) != 2:
        print("ใช้: python scripts/backup_drill.py <ไฟล์ฐานข้อมูล sqlite>")
        return 2
    source = pathlib.Path(sys.argv[1])
    if not source.is_file():
        print(f"ไม่มีไฟล์ {source}")
        return 2
    with tempfile.TemporaryDirectory(prefix="backup-drill-") as tmp:
        problems = drill(source, pathlib.Path(tmp))
    if problems:
        print("การซ้อมล้มเหลว:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print(f"การซ้อมผ่าน: backup → เสียหาย → restore → ตรวจครบ ({source})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
