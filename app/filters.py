"""ตัวกรองรายการงาน — สถานะ, หมวด, และช่วงวันเวลา

ตัวกรองตามวันดูจาก **`due_date` อย่างเดียว** ให้ตรงกับคำถามที่คนถามจริง ๆ
ว่า "อะไรครบกำหนดเมื่อไหร่" ส่วน `start_date` เป็นข้อมูลประกอบ ไม่ใช่ตัวกรอง

ค่าที่ผู้ใช้กรอก/เห็นเป็นเวลาท้องถิ่นของเขา แต่ใน DB เป็น UTC เสมอ
ทุกช่วงจึงถูกคำนวณในเวลาท้องถิ่นก่อนแล้วค่อยแปลงเป็น UTC ตอนไปเทียบ
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Self

from app import tz

# ตัวกรองสถานะ — ชุดเดิม
STATUS_FILTERS = ("all", "active", "completed")

# ตัวกรองตามวัน
WHEN_ALL = "all"
WHEN_UPCOMING = "upcoming"
WHEN_TODAY = "today"
WHEN_TOMORROW = "tomorrow"
WHEN_RANGE = "range"
WHEN_FILTERS = (WHEN_ALL, WHEN_UPCOMING, WHEN_TODAY, WHEN_TOMORROW, WHEN_RANGE)

# ช่วงเวลาของ "Upcoming" หน่วยเป็นนาที
UPCOMING_CHOICES = (15, 30, 45, 480)
DEFAULT_UPCOMING = 480

# ความยาวสตริง "YYYY-MM-DD" — บอกว่าผู้ใช้ส่งมาแค่วัน ไม่มีเวลา
DATE_ONLY_LEN = 10

DAY_START = time(0, 0)
DAY_END = time(23, 59, 59, 999999)


def normalise_status(value: str | None) -> str:
    return value if value in STATUS_FILTERS else WHEN_ALL


def normalise_when(value: str | None) -> str:
    return value if value in WHEN_FILTERS else WHEN_ALL


def normalise_within(value: str | int | None) -> int:
    """นาทีของช่วง Upcoming — ค่าที่ไม่รู้จักตกไปใช้ค่าเริ่มต้น"""
    if value is None:
        return DEFAULT_UPCOMING
    try:
        minutes = int(value)
    except ValueError:
        return DEFAULT_UPCOMING
    return minutes if minutes in UPCOMING_CHOICES else DEFAULT_UPCOMING


def parse_boundary(raw: str | None, fallback_time: time) -> datetime | None:
    """แปลงค่าจากช่องเลือกวัน/เวลาเป็น datetime ท้องถิ่น

    รับทั้ง "YYYY-MM-DDTHH:MM" และ "YYYY-MM-DD" เปล่า ๆ
    แบบหลังจะเติมเวลาให้ตาม fallback_time (ต้นวันหรือท้ายวัน)
    คืน None ถ้าเว้นว่าง และ raise ValueError ถ้ารูปแบบใช้ไม่ได้
    """
    raw = (raw or "").strip()
    parsed = tz.parse_naive(raw)
    if parsed is None:
        return None
    # ผู้ใช้กรอกแค่วัน (ไม่มีเวลา) fromisoformat จะให้เที่ยงคืนมา
    if len(raw) == DATE_ONLY_LEN:
        parsed = datetime.combine(parsed.date(), fallback_time)
    return parsed


def local_bounds(
    when: str,
    within_minutes: int,
    range_from: datetime | None,
    range_to: datetime | None,
    tz_name: str | None,
) -> tuple[datetime | None, datetime | None]:
    """คืน (เริ่ม, สิ้นสุด) เป็นเวลาท้องถิ่น — None แปลว่าไม่จำกัดด้านนั้น

    `range_from`/`range_to` เป็น datetime ท้องถิ่นที่ผ่าน parse_boundary มาแล้ว
    """
    now_local = tz.to_local(tz.now_utc(), tz_name)
    today = now_local.date()

    if when == WHEN_UPCOMING:
        # นับจากนี้ไปข้างหน้าตามช่วงที่เลือก งานที่เลยกำหนดแล้วไม่ใช่ "upcoming"
        return now_local, now_local + timedelta(minutes=within_minutes)

    if when == WHEN_TODAY:
        return datetime.combine(today, DAY_START), datetime.combine(today, DAY_END)

    if when == WHEN_TOMORROW:
        tomorrow = today + timedelta(days=1)
        return (
            datetime.combine(tomorrow, DAY_START),
            datetime.combine(tomorrow, DAY_END),
        )

    if when == WHEN_RANGE:
        # เลือกวันเดียวก็ได้ — ใส่แค่ช่องเริ่มแล้วปล่อยช่องท้ายว่าง
        if range_from and not range_to:
            range_to = datetime.combine(range_from.date(), DAY_END)
        return range_from, range_to

    return None, None


CATEGORY_NONE = "none"


@dataclass(frozen=True)
class FilterSpec:
    """ตัวกรองหนึ่งชุดที่ normalise แล้ว — ค่าทุกตัวใช้ได้ทันทีโดยไม่ต้องตรวจซ้ำ

    เป็นภาษากลางระหว่าง adapter กับ service (Phase 3 — ดู ADR 0016):
    ฟอร์ม HTML กับ query string ของ API แปลง input ดิบมาเป็นตัวนี้ตัวเดียว
    แล้ว service ก็รับแต่ตัวนี้ ไม่ต้องรู้ว่าใครเป็นคนส่งมา

    `category` เป็นสตริงตามที่รับมา (`""` = ทุกหมวด, `"none"` = ไม่มีหมวด,
    ตัวเลข = id) เพราะการยืนยันว่า id นั้นเป็นของใครต้องแตะฐานข้อมูล
    ซึ่งเป็นงานของ service ไม่ใช่ของตัว normalise
    """

    status: str = "all"
    category: str = ""
    when: str = WHEN_ALL
    within: int = DEFAULT_UPCOMING
    range_from: datetime | None = None
    range_to: datetime | None = None

    @classmethod
    def from_params(cls, params: Mapping[str, str], *, ignore_dates: bool = False) -> Self:
        """อ่านจาก query string — ค่าที่ไม่รู้จักตกไปใช้ค่าเริ่มต้นเงียบ ๆ

        raise `ValueError` เฉพาะรูปแบบวันที่ที่ย่อยไม่ได้ เพราะเป็นกรณีเดียวที่
        การเงียบแล้วแสดงผลอย่างอื่นแทนจะทำให้ผู้ใช้เข้าใจผิดว่าตัวกรองทำงานอยู่

        `ignore_dates=True` คือทางที่ผู้เรียกใช้ **หลังจาก** รับ `ValueError`
        ไปแล้วและตัดสินใจว่าจะแสดงทุกงานแทน — ไม่ใช่ทางลัดให้ข้ามการตรวจ
        """
        category = (params.get("category") or "").strip()
        if category != CATEGORY_NONE and not category.isdigit():
            category = ""
        when = normalise_when(params.get("when", WHEN_ALL))
        range_from = range_to = None
        if ignore_dates:
            # ไม่มีช่วงวันแล้วก็ไม่มีความหมายที่จะคง when=range ไว้
            when = WHEN_ALL
        else:
            range_from = parse_boundary(params.get("date_from"), DAY_START)
            range_to = parse_boundary(params.get("date_to"), DAY_END)
        return cls(
            status=normalise_status(params.get("status", "all")),
            category=category,
            when=when,
            within=normalise_within(params.get("within")),
            range_from=range_from,
            range_to=range_to,
        )


def apply_when(query: Any, model: Any, spec: FilterSpec, tz_name: str | None) -> Any:
    """ใส่เงื่อนไขช่วงวันลงใน query ตาม due_date"""
    start_local, end_local = local_bounds(
        spec.when, spec.within, spec.range_from, spec.range_to, tz_name
    )
    if start_local is None and end_local is None:
        return query

    # งานที่ไม่มีกำหนดส่งตอบคำถาม "ครบกำหนดช่วงนี้ไหม" ไม่ได้ จึงถูกกรองออก
    query = query.filter(model.due_date.isnot(None))
    if start_local is not None:
        query = query.filter(model.due_date >= tz.to_utc(start_local, tz_name))
    if end_local is not None:
        query = query.filter(model.due_date <= tz.to_utc(end_local, tz_name))
    return query
