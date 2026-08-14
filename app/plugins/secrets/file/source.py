"""แหล่งความลับ: ไฟล์ในไดเรกทอรี (ADR 0030 ข้อ 2)

`SECRETS_URL=file:///run/secrets` แล้วความลับชื่อ `SECRET_KEY` จะถูกอ่านจาก
ไฟล์ `/run/secrets/secret_key` — **ชื่อไฟล์เป็นตัวพิมพ์เล็ก** ตามธรรมเนียมของ
docker compose/swarm และ kubernetes ที่ตั้งชื่อ secret ด้วยตัวพิมพ์เล็กเสมอ

**นี่คือคำตอบสำหรับคนส่วนใหญ่ ไม่ใช่ทางผ่านไป Vault**: มันแก้ข้อเสียหลักของ
environment ได้เกือบทั้งหมด (ไม่ติดไปกับโปรเซสลูก, ไม่โผล่ใน `docker inspect`,
สิทธิ์เป็นของระบบไฟล์ที่มีอยู่แล้ว) โดยไม่ต้องมี dependency ใหม่และไม่มีระบบ
ใหม่ให้ล่ม · และมันคือ **exit path ของแหล่งอื่นทุกตัว** ในตัว

**ไดเรกทอรีที่ไม่มีอยู่ = ไม่ start** ไม่ใช่ "ไม่มีความลับสักตัว" เพราะ path
ที่พิมพ์ผิดกับ path ที่ยังไม่ได้ mount ให้ผลเหมือนกันเป๊ะ แล้วระบบจะรันต่อ
ด้วยค่าจาก environment เงียบ ๆ ซึ่งเป็นสิ่งที่ ADR 0030 ข้อ 6 ห้ามไว้
"""

import pathlib
from typing import Any

from app.plugins import PluginError


def connect(url: str) -> pathlib.Path:
    """แปลง URL เป็นไดเรกทอรี แล้วยืนยันว่ามันมีอยู่จริง"""
    _, _, raw = url.partition("://")
    directory = pathlib.Path(raw or "/run/secrets")
    if not directory.is_dir():
        raise PluginError(f"แหล่งความลับ: ไม่มีไดเรกทอรี {directory}")
    return directory


def get(handle: Any, name: str) -> str | None:
    """อ่านไฟล์ที่ชื่อตรงกับความลับนั้น (ตัวพิมพ์เล็ก) — ไม่มีไฟล์ = ไม่มีค่า

    **ชื่อไฟล์เป็นตัวพิมพ์เล็กเสมอ** ตามธรรมเนียม docker/k8s secrets —
    `SECRET_KEY` อ่านจากไฟล์ชื่อ `secret_key` · bench ของเฟส 10 เคยวางไฟล์
    ชื่อตัวพิมพ์ใหญ่แล้วแหล่งนี้ไม่ถูกอ่านเลยโดยไม่มีอะไรฟ้อง (ตกกลับ env
    ตามออกแบบ) — จดไว้ตรงนี้เพราะคนถัดไปจะทำพลาดแบบเดียวกัน
    """
    directory: pathlib.Path = handle
    path = directory / name.lower()
    try:
        # **ตัดขึ้นบรรทัดใหม่ท้ายไฟล์ทิ้ง** — editor ส่วนใหญ่เติมให้เอง และ
        # ความลับที่มีบรรทัดใหม่ต่อท้ายจะทำให้ bind/HMAC ไม่ตรงโดยไม่มีใครเห็นสาเหตุ
        return path.read_text().rstrip("\n")
    except (FileNotFoundError, IsADirectoryError, PermissionError):
        return None
