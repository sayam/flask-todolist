"""ตัวกรองรายการงาน — สถานะ, หมวด, และช่วงวันเวลา

ตัวกรองตามวันดูจาก **`due_date` อย่างเดียว** ให้ตรงกับคำถามที่คนถามจริง ๆ
ว่า "อะไรครบกำหนดเมื่อไหร่" ส่วน `start_date` เป็นข้อมูลประกอบ ไม่ใช่ตัวกรอง

ค่าที่ผู้ใช้กรอก/เห็นเป็นเวลาท้องถิ่นของเขา แต่ใน DB เป็น UTC เสมอ
ทุกช่วงจึงถูกคำนวณในเวลาท้องถิ่นก่อนแล้วค่อยแปลงเป็น UTC ตอนไปเทียบ
"""

from datetime import datetime, time, timedelta

from app import tz

# ตัวกรองสถานะ (เดิม)
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

DAY_START = time(0, 0)
DAY_END = time(23, 59, 59, 999999)


def normalise_status(value):
    return value if value in STATUS_FILTERS else WHEN_ALL


def normalise_when(value):
    return value if value in WHEN_FILTERS else WHEN_ALL


def normalise_within(value):
    """นาทีของช่วง Upcoming — ค่าที่ไม่รู้จักตกไปใช้ค่าเริ่มต้น"""
    try:
        minutes = int(value)
    except (TypeError, ValueError):
        return DEFAULT_UPCOMING
    return minutes if minutes in UPCOMING_CHOICES else DEFAULT_UPCOMING


def parse_boundary(raw, fallback_time):
    """แปลงค่าจากช่องเลือกวัน/เวลาเป็น datetime ท้องถิ่น

    รับทั้ง "YYYY-MM-DDTHH:MM" และ "YYYY-MM-DD" เปล่า ๆ
    แบบหลังจะเติมเวลาให้ตาม fallback_time (ต้นวันหรือท้ายวัน)
    คืน None ถ้าเว้นว่าง และ raise ValueError ถ้ารูปแบบใช้ไม่ได้
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is not None:
        raise ValueError("ไม่รับ timezone offset")
    # ผู้ใช้กรอกแค่วัน (ไม่มีเวลา) fromisoformat จะให้เที่ยงคืนมา
    if len(raw) == 10:
        parsed = datetime.combine(parsed.date(), fallback_time)
    return parsed


def local_bounds(when, within_minutes, range_from, range_to, tz_name):
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


def apply_when(query, model, when, within_minutes, range_from, range_to, tz_name):
    """ใส่เงื่อนไขช่วงวันลงใน query ตาม due_date"""
    start_local, end_local = local_bounds(
        when, within_minutes, range_from, range_to, tz_name
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
