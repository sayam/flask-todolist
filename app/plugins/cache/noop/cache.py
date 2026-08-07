"""ไม่เก็บอะไรเลย — **นี่คือค่าเริ่มต้นและเป็นเส้นทางที่ถูกต้อง ไม่ใช่ของชั่วคราว**

ROADMAP ข้อ 4.3 ตั้งกติกาไว้ว่า cache เป็น optimization ห้ามเป็น correctness
วิธีเดียวที่จะรู้ว่ากติกานี้ยังจริงอยู่ คือมีเส้นทาง "ไม่มี cache" ที่ทุกคนเดินผ่าน
เป็นปกติทุกวัน ไม่ใช่เส้นทางสำรองที่ไม่มีใครรัน (หลักเดียวกับ job `bare` ของ ADR 0025)

**ทำไมไม่ทำเป็น dict ใน process**: แอปนี้จะรันหลาย worker (Phase 5 ข้อ ≥2 replica)
cache ที่ไม่แชร์กันทำให้คำขอสองอันที่เหมือนกันได้คำตอบต่างกันตาม worker ที่รับ
ซึ่งจากภายนอกแยกไม่ออกจากบั๊ก — **cache ที่ผิดเงียบ ๆ แย่กว่าไม่มี cache**
ใครต้องการความเร็วจริงให้ตั้ง `CACHE_URL` ไปที่ backend ที่แชร์ได้
"""

from typing import Any


def connect(_url: str) -> None:
    """ไม่ต้องต่ออะไร"""
    return


def get(_handle: None, _key: str) -> Any:
    """ไม่เคยมีค่าเก็บไว้ — ผู้เรียกต้องคำนวณเองเสมอ"""
    return None


def set(_handle: None, _key: str, _value: Any, _ttl: int | None) -> None:  # noqa: A001
    """ทิ้งค่าไปเฉย ๆ ไม่ใช่การลืม แต่เป็นสัญญาของ backend ตัวนี้"""
    return


def invalidate(_handle: None, _key: str) -> None:
    """ไม่มีอะไรให้ลบ"""
    return
