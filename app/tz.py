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

# ชื่อที่ `available_timezones()` คืนมาแต่ **ไม่ใช่โซนจริง** — เป็นของที่ tzdata
# บางดิสโทรวางไว้ในไดเรกทอรีเดียวกัน ต่างดิสโทรมีไม่เท่ากัน (Ubuntu มี `localtime`
# แต่ Gentoo ไม่มี) ถ้าไม่กรองออกจะโผล่ใน dropdown ให้ผู้ใช้เลือกทั้งที่
# ไม่มีความหมาย และไม่มีข้อมูลในตารางดวงอาทิตย์ → โหมด auto จะเป็น light ตลอด
#
#   localtime  — symlink ไปโซนของเครื่องนั้น ซ้ำกับโซนจริงที่มีอยู่แล้ว
#   posixrules — ของตกค้างจาก tzdata รุ่นเก่า ถูกถอดออกตั้งแต่ 2020b
#   Factory    — โซนหลอกที่มีข้อความว่า "ต้องตั้งค่า timezone ก่อน"
NOT_REAL_ZONES = frozenset({"localtime", "posixrules", "Factory"})


@lru_cache(maxsize=1)
def all_timezones() -> tuple[str, ...]:
    """รายชื่อ timezone ที่ให้ผู้ใช้เลือกได้ เรียงแล้ว (cache ไว้ เพราะสแกนดิสก์)

    กรองชื่อที่ไม่ใช่โซนจริงออก — ดู `NOT_REAL_ZONES` ว่าทำไม
    """
    return tuple(sorted(available_timezones() - NOT_REAL_ZONES))


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


def parse_naive(raw: str | None) -> datetime | None:
    """ข้อความ ISO ("YYYY-MM-DDTHH:MM" หรือ "YYYY-MM-DD") -> datetime naive

    คืน None ถ้าเว้นว่าง และ raise `ValueError` ถ้ารูปแบบใช้ไม่ได้

    **ปฏิเสธค่าที่มี offset ติดมาด้วย** เพราะทั้งระบบตกลงกันว่าเวลาที่รับเข้ามา
    คือเวลาท้องถิ่นของผู้ใช้ ค่าที่มี offset จะกำกวมทันทีว่าให้เชื่ออันไหน
    (`+07:00` ที่ส่งมาโดยคนที่ตั้ง timezone เป็น Asia/Tokyo หมายถึงอะไร)

    รับ "YYYY-MM-DD" เปล่า ๆ ด้วยโดยถือว่าเป็นเที่ยงคืนของวันนั้น — client ที่
    ยิง API ตรง ๆ อาจส่งมาแค่วัน
    """
    text = (raw or "").strip()
    if not text:
        return None
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is not None:
        raise ValueError("ไม่รับ timezone offset — ใช้เวลาท้องถิ่นเท่านั้น")
    return parsed


def now_utc() -> datetime:
    """เวลาปัจจุบันเป็น naive UTC — เทียบกับค่าใน DB ได้ตรง ๆ"""
    return datetime.now(UTC).replace(tzinfo=None)
