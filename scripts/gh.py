"""คุยกับ GitHub ผ่าน `gh` — **ตัวห่อตัวเดียวของทั้ง repo**

ADR 0039 ห้ามเก็บคำสั่งไว้สองที่ เพราะที่ที่สองจะ drift ทันทีที่มีคนแก้ฝั่งเดียว ·
audit รอบ 18 พิสูจน์ว่ากฎข้อนั้นใช้กับ *ตัวแยกวิเคราะห์* ด้วย ไม่ใช่แค่กับคำสั่ง
ที่คนพิมพ์ — สำนวนอ่าน `on:` ของ workflow ถูกลอกไว้ห้าที่และพังสามที่แบบเดียวกัน
ซึ่งเป็นที่มาของ `scripts/workflows.py`

**ตัวห่อ `gh` เป็นเคสที่สองของคลาสเดียวกัน** — ตอน audit รอบ 26 นับได้ว่ามันถูก
ลอกไว้ **ห้าที่** และสองในนั้นเหมือนกันทุกตัวอักษร (`schedule_census` กับ
`red_streak_census`) · ทุกใบพกคำสั่งปิด `S603` ของตัวเองมาด้วย จึงเป็นห้าข้อยกเว้น
สำหรับคำสั่งเดียว

ตอนนี้ย้ายมาแล้วสามใบ (`schedule_census` · `red_streak_census` · `sync_counts`)
· **ที่ยังเหลือสองใบ และเหลือด้วยเหตุผล**:

- `audit_posture._request` ยืม token คนละใบต่อคำถาม (`GH_TOKEN_ALERTS`) ซึ่งเป็น
  พฤติกรรมที่ตัวนี้ยังไม่มี — ย้ายเมื่อไหร่ต้องยกเรื่อง token มาด้วยทั้งก้อน
- `rerun_census._gh_json` ใช้ `check=True` จึงโยน `CalledProcessError` ไม่ใช่
  `PermissionError` — เทสต์ของมันผูกกับรูปนั้น การย้ายคือการเปลี่ยนสัญญาของ error

**ห้ามส่งสตริงที่คนอื่นแต่งเข้ามาเป็น argument** — ทุกที่ที่เรียกตัวนี้ประกอบ
argument เองจากค่าคงที่ในโค้ด ซึ่งเป็นเหตุผลเดียวที่ `S603` ยกเว้นได้

บทบาท: helper — ตัวช่วยของสภาพแวดล้อม ไม่ตัดสินและไม่ถูกอ้างเป็นหลักฐาน
"""

from __future__ import annotations

import json
import shutil
import subprocess
import typing

# **เพดานเวลาของคำสั่งที่เรายิงออกไป** (ADR 0067 · audit รอบ 11) — `subprocess.run`
# ที่ไม่มี `timeout=` รอตลอดกาล และเครื่องมือพวกนี้รันอยู่ใน job ของ CI ผลคือ
# `gh` ที่ไม่ตอบกลายเป็น job ที่กินเพดานของ job ไปทั้งก้อนโดยไม่ทำอะไรเลย
NETWORK_TIMEOUT_SECONDS = 60


def run(args: list[str]) -> str:
    """เรียก `gh <args>` แล้วคืน stdout ที่ตัดช่องว่างหัวท้ายแล้ว

    ล้มเหลว = `PermissionError` เสมอ เพราะสาเหตุที่พบจริงเกือบทุกครั้งคือสิทธิ์
    ไม่พอหรือ token หมดอายุ — และข้อความของ `gh` ถูกแนบไปด้วยทั้งก้อน
    """
    binary = shutil.which("gh")
    if not binary:
        raise RuntimeError("ไม่มี gh บนเครื่องนี้ — เครื่องมือนี้ต้องคุยกับ GitHub ผ่านมัน")
    done = subprocess.run(  # noqa: S603 — path มาจาก shutil.which และ argument เป็นของเราเอง
        [binary, *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=NETWORK_TIMEOUT_SECONDS,
    )
    if done.returncode != 0:
        raise PermissionError(f"`gh {' '.join(args)}` ล้มเหลว: {done.stderr.strip()}")
    return done.stdout.strip()


def api(path: str) -> typing.Any:
    """ถาม GitHub API แล้วคืน JSON ที่ย่อยแล้ว"""
    return json.loads(run(["api", path]))
