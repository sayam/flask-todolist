"""แปลงเวลาไปมาระหว่าง UTC (ที่เก็บใน DB) กับเวลาท้องถิ่นของผู้ใช้

**กติกาของโปรเจกต์: `Todo.due_date` ใน DB เป็น UTC แบบ naive เสมอ**
เวลาที่ผู้ใช้กรอกเข้ามาจาก `<input type="datetime-local">` เป็นเวลาท้องถิ่น
ของเขา ต้องผ่าน `to_utc()` ก่อนเก็บ และผ่าน `to_local()` ก่อนแสดง

เก็บเป็น naive (ไม่ใช่ aware) เพราะ SQLite ไม่มีชนิดข้อมูลที่เก็บ offset ได้
การเก็บ UTC ล้วนจึงเป็นวิธีเดียวที่ไม่กำกวม
"""

from datetime import UTC, datetime
from functools import lru_cache
from typing import overload
from zoneinfo import ZoneInfo, available_timezones

from flask import current_app

FALLBACK = "UTC"


@lru_cache(maxsize=1)
def all_timezones() -> tuple[str, ...]:
    """รายชื่อ timezone ทั้งหมดของระบบ เรียงแล้ว (cache ไว้ เพราะสแกนดิสก์)"""
    return tuple(sorted(available_timezones()))


def is_supported(name: str | None) -> bool:
    return bool(name) and name in set(all_timezones())


def default_name() -> str:
    return str(current_app.config.get("BABEL_DEFAULT_TIMEZONE", FALLBACK))


def resolve(name: str | None) -> ZoneInfo:
    """ZoneInfo จากชื่อ — ชื่อที่ไม่รู้จักหรือไม่ได้ตั้งให้ตกไปใช้ค่าเริ่มต้นของแอป"""
    if is_supported(name):
        return ZoneInfo(name)  # type: ignore[arg-type]  # is_supported การันตี str แล้ว
    fallback = default_name()
    return ZoneInfo(fallback if is_supported(fallback) else FALLBACK)


# overload: บอก mypy ว่า None เข้า None ออก / datetime เข้า datetime ออก
# ผู้เรียกที่ส่งค่า non-None จึงไม่ต้อง assert ซ้ำ


@overload
def to_utc(naive_local: datetime, tz_name: str | None) -> datetime: ...
@overload
def to_utc(naive_local: None, tz_name: str | None) -> None: ...


def to_utc(naive_local: datetime | None, tz_name: str | None) -> datetime | None:
    """เวลาที่ผู้ใช้กรอก (naive ตาม tz ของเขา) -> naive UTC สำหรับเก็บลง DB"""
    if naive_local is None:
        return None
    aware = naive_local.replace(tzinfo=resolve(tz_name))
    return aware.astimezone(UTC).replace(tzinfo=None)


@overload
def to_local(naive_utc: datetime, tz_name: str | None) -> datetime: ...
@overload
def to_local(naive_utc: None, tz_name: str | None) -> None: ...


def to_local(naive_utc: datetime | None, tz_name: str | None) -> datetime | None:
    """naive UTC จาก DB -> naive ตาม tz ของผู้ใช้ สำหรับเอาไปแสดง"""
    if naive_utc is None:
        return None
    aware = naive_utc.replace(tzinfo=UTC)
    return aware.astimezone(resolve(tz_name)).replace(tzinfo=None)


def now_utc() -> datetime:
    """เวลาปัจจุบันเป็น naive UTC — เทียบกับค่าใน DB ได้ตรง ๆ"""
    return datetime.now(UTC).replace(tzinfo=None)
