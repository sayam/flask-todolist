"""แหล่งความลับ: HashiCorp Vault (KV v2) — ADR 0030

`SECRETS_URL=vault://vault.example.com:8200/secret/todolist`
โดย `secret` คือ mount ของ KV v2 และ `todolist` คือ path ของความลับชุดนั้น
ใช้ `vault+http://` เมื่อ Vault ทดสอบยังไม่มี TLS (**สำหรับทดสอบเท่านั้น**)

**อ่านครั้งเดียวตอน `connect()` แล้วเก็บไว้ในหน่วยความจำ** (ADR 0030 ข้อ 5) —
ไม่ยิงไป Vault ต่อคำขอ เพราะนั่นจะทำให้แหล่งความลับกลายเป็น dependency ของ
ทุก request ซึ่งเป็นสิ่งเดียวกับที่ ROADMAP ข้อ 4.3 ห้ามไว้เรื่อง cache
**แลกกับ: หมุนความลับแล้วต้อง restart** ซึ่งเขียนไว้ใน ADR ว่าเป็นราคาที่รับได้

**token มาจาก `VAULT_TOKEN` ใน environment** — นี่คือไก่กับไข่ที่ ADR 0030
ข้อ 4 พูดถึงและแก้ไม่ได้: แหล่งความลับเองต้องมี credential จากที่อื่น
สิ่งที่ทำได้คือทำให้ของที่เหลืออยู่ใน env เป็น **กุญแจดอกเดียวที่ไปเอาของ
ที่เหลือ** ไม่ใช่ของทั้งกอง

**ยิงจริงตอน `connect()`** เพื่อให้ Vault ที่ถามไม่ได้ทำให้แอปไม่ start
(ข้อ 6) ไม่ใช่รันต่อด้วยความลับชุดเก่าที่ยังค้างอยู่ใน env โดยไม่มีใครรู้
"""

import os
from typing import Any
from urllib.parse import urlparse

import hvac

from app.plugins import PluginError


def connect(url: str) -> dict[str, str]:
    """อ่านความลับทั้ง path มาเก็บไว้ครั้งเดียว — คืน dict ของ ชื่อ → ค่า"""
    parsed = urlparse(url)
    scheme = "http" if parsed.scheme.endswith("+http") else "https"
    if not parsed.hostname:
        raise PluginError(f"แหล่งความลับ: {url} ไม่มีชื่อโฮสต์ของ Vault")
    # path เป็น `/<mount>/<path ที่เหลือ>` — mount ของ KV แยกจาก path ข้างใน
    mount, _, path = parsed.path.lstrip("/").partition("/")
    if not mount or not path:
        raise PluginError(f"แหล่งความลับ: {url} ต้องเป็น vault://โฮสต์/<mount>/<path>")

    token = os.environ.get("VAULT_TOKEN", "")
    if not token:
        # **ไม่เดาว่าจะอ่านแบบไม่ต้องยืนยันตัวตนได้** — Vault ที่เปิดให้อ่าน
        # โดยไม่มี token คือ Vault ที่ตั้งค่าผิด ไม่ใช่กรณีที่เราควรรองรับ
        raise PluginError("แหล่งความลับ: ต้องตั้ง VAULT_TOKEN")

    port = f":{parsed.port}" if parsed.port else ""
    client = hvac.Client(url=f"{scheme}://{parsed.hostname}{port}", token=token)
    try:
        answer = client.secrets.kv.v2.read_secret_version(
            mount_point=mount, path=path, raise_on_deleted_version=True
        )
    except Exception as error:
        # **ไม่เอาข้อความของ Vault มาแสดงต่อ** มันมีรายละเอียดภายในของระบบนั้น
        # — ชนิดของ error พอให้ผู้ดูแลไล่ต่อได้แล้ว
        raise PluginError(
            f"แหล่งความลับ: อ่าน {mount}/{path} จาก Vault ไม่ได้ ({type(error).__name__})"
        ) from error
    data = answer["data"]["data"]
    # **ชื่อคีย์เป็นตัวพิมพ์เล็ก** เหมือน backend `file` เพื่อให้ย้ายไปมาได้โดย
    # ไม่ต้องเปลี่ยนชื่ออะไร (exit path — ADR 0030 ข้อ 7)
    return {str(key).lower(): str(value) for key, value in data.items()}


def get(handle: Any, name: str) -> str | None:
    """ค่าที่อ่านมาแล้วตอน start — ไม่มีชื่อนั้น = ไม่มีค่า"""
    values: dict[str, str] = handle
    return values.get(name.lower())
