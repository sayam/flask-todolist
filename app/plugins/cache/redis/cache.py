"""เก็บใน redis — แชร์ข้ามโปรเซสและข้าม replica ได้จริง

**ถอดไดเรกทอรีนี้ทิ้ง = ตกกลับไปไม่มี cache** ซึ่งระบบยังถูกต้อง แค่ช้าลง
และ `redis` หลุดจาก supply chain ไปด้วยเพราะอยู่ใน category ของตัวเอง (ADR 0025)

**ค่าเก็บเป็น bytes ตามที่ redis คืนมา ไม่ถอดรหัสให้** — ผู้เรียกเป็นคนรู้ว่า
ตัวเองเก็บอะไรลงไป การเดา encoding แทนเขาคือการเพิ่มพฤติกรรมที่ต่างจาก backend
ตัวอื่นโดยไม่มีใครขอ (`decode_responses` ที่เปิดไว้จะทำให้ค่า binary พัง)
"""

from typing import Any

# import ระดับบนสุดโดยตั้งใจ: ไม่มีไลบรารี = ImportError = แอปไม่ start พร้อมบอกว่า
# ขาดอะไร ต่างจากส่วนเสริมของ ADR 0025 ที่ปิดตัวเองเงียบ ๆ เพราะที่นี่ผู้ดูแล
# **ตั้งใจ** ชี้ CACHE_URL มาที่ redis การเงียบแล้วไม่ cache ให้คือการโกหก
import redis


def connect(url: str) -> Any:
    """client หนึ่งตัวใช้ตลอดอายุแอป — ตัว redis-py จัดการ connection pool ให้เอง"""
    return redis.Redis.from_url(url)


def get(handle: Any, key: str) -> Any:
    return handle.get(key)


def set(handle: Any, key: str, value: Any, ttl: int | None) -> None:  # noqa: A001 - documented suppression
    handle.set(key, value, ex=ttl)


def invalidate(handle: Any, key: str) -> None:
    handle.delete(key)
