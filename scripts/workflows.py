"""อ่าน workflow ของ GitHub Actions — **ตัวอ่านตัวเดียวของทั้ง repo**

`on:` ของ GitHub ถูกต้องสามรูป และสำนวนที่เราเคยใช้รองรับแค่สองรูป:

    on: push                    → str    ใช้ได้
    on: [push, pull_request]    → list   **โยน TypeError**
    on:
      pull_request:             → dict   ใช้ได้

สำนวนเดิมคือ `"pull_request" in (triggers if isinstance(triggers, dict) else {triggers: None})`
ซึ่งเอาค่าไปทำเป็นคีย์ของ dict — ลิสต์เป็นคีย์ไม่ได้ · มันถูกลอกไว้ **ห้าที่**
(`audit_posture` · `red_streak_census` · `schedule_census` · เทสต์อีกสองไฟล์)
และสามที่พังแบบเดียวกันทั้งหมด (audit governance รอบ 18)

บั๊กหลับอยู่เพราะ workflow ทุกไฟล์ของ repo นี้ใช้รูป dict — มันจะตื่นในวันที่มีคน
เพิ่ม workflow ด้วยรูปลิสต์ ซึ่งเป็นรูปที่ตัวอย่างในเอกสารของ GitHub ใช้มากที่สุด
แล้ววันนั้น job `posture` จะแดงด้วยข้อความที่ไม่เกี่ยวกับสิ่งที่มันตรวจเลย

**ทำไมต้องเป็นโมดูลเดียว**: ADR 0039 ห้ามเก็บคำสั่งไว้สองที่ เพราะที่ที่สองจะ drift
ทันทีที่มีคนแก้ฝั่งเดียว — *ตัวแยกวิเคราะห์ก็เป็นคำสั่งชนิดหนึ่ง* และหลักฐานคือ
ห้าสำเนานี้ drift ไปแล้วจริง: `schedule_census` กันตัวเองด้วย `isinstance` ส่วน
อีกสองตัวไม่กัน

บทบาท: helper — ของใช้ร่วม — หลักฐานคือผู้ใช้งานจริงในโค้ด และเทสต์ของผู้ใช้นั้น
"""

from __future__ import annotations

import pathlib

# pyyaml มากับ dev tools และไม่มี stub — เหตุผลเดียวกับ build_gates_crosswalk.py
import yaml  # type: ignore[import-untyped] - library lacks type stubs

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW_DIR = ROOT / ".github" / "workflows"


def load(path: pathlib.Path) -> dict:
    """เนื้อของ workflow หนึ่งไฟล์ — ไฟล์ว่างคืน dict ว่าง ไม่ใช่ None"""
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def all_workflows(directory: pathlib.Path | None = None) -> dict[str, dict]:
    """ชื่อไฟล์ → เนื้อ ของ workflow ทุกไฟล์ (เรียงตามชื่อ)"""
    directory = WORKFLOW_DIR if directory is None else directory
    return {path.name: load(path) for path in sorted(directory.glob("*.y*ml"))}


def triggers(workflow: dict) -> set[str]:
    """ชื่อเหตุการณ์ที่ทำให้ workflow นี้รัน — ครอบทั้งสามรูปของ `on:`

    **คีย์เป็น `True` ได้จริง** เพราะ YAML 1.1 อ่าน `on:` ที่ไม่มีเครื่องหมายคำพูด
    เป็นบูลีน (`yes`/`on`/`true` เป็นค่าเดียวกันในสเปคนั้น) — pyyaml ตามสเปคนั้นอยู่
    """
    declared = workflow.get(True, workflow.get("on"))
    if declared is None:
        return set()
    if isinstance(declared, str):
        return {declared}
    if isinstance(declared, dict):
        return {str(key) for key in declared}
    return {str(item) for item in declared}


def runs_on(workflow: dict, event: str) -> bool:
    """workflow นี้ถูกกระตุ้นด้วยเหตุการณ์นี้ไหม"""
    return event in triggers(workflow)


def event_config(workflow: dict, event: str) -> object:
    """ค่าที่ประกาศไว้ใต้เหตุการณ์นั้น — `None` ถ้าไม่มีหรือประกาศด้วยรูปที่ไม่มี config

    (`on: [schedule]` ประกาศเหตุการณ์ได้ แต่ประกาศ cron ไม่ได้ — GitHub เองก็
    ไม่รับ ดังนั้น "ไม่มี config" คือคำตอบที่ถูก ไม่ใช่การยอมแพ้)
    """
    declared = workflow.get(True, workflow.get("on"))
    return declared.get(event) if isinstance(declared, dict) else None


def schedules(workflow: dict) -> list[str]:
    """cron ทุกบรรทัดที่ workflow นี้ประกาศ — `on.schedule` เป็นลิสต์ของ `{cron: ...}`"""
    declared = event_config(workflow, "schedule")
    if not isinstance(declared, list):
        return []
    return [entry["cron"] for entry in declared if isinstance(entry, dict) and entry.get("cron")]


def jobs(workflow: dict) -> dict[str, dict]:
    """job ทั้งหมดของ workflow นี้"""
    return workflow.get("jobs") or {}
