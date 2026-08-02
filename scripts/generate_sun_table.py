"""สร้าง app/sun_data.py — ตารางเวลาดวงอาทิตย์ขึ้น-ตกรายเดือนของแต่ละ timezone

รันตอนจะ regenerate เท่านั้น ไม่ได้ถูกเรียกตอนแอปทำงาน:

    python scripts/generate_sun_table.py

พิกัดของแต่ละโซนมาจาก zone1970.tab ของ tzdata ที่ติดตั้งในเครื่อง
ส่วนเวลาขึ้น-ตกคำนวณด้วย "Sunrise/Sunset Algorithm" ของ Almanac
(ตัวเดียวกับที่ NOAA ใช้อธิบาย) ไม่ต้องพึ่ง library ภายนอก

ความแม่นยำระดับไม่กี่นาที ซึ่งเกินพอสำหรับตัดสินว่าจะแสดงธีมสว่างหรือมืด
"""

import math
import pathlib
import sys
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, available_timezones

ZONE_TAB_CANDIDATES = (
    "/usr/share/zoneinfo/zone1970.tab",
    "/usr/share/zoneinfo/zone.tab",
)
OUTPUT = pathlib.Path(__file__).resolve().parent.parent / "app" / "sun_data.py"

# ค่าพิเศษแทนบริเวณขั้วโลกที่ดวงอาทิตย์ไม่ขึ้นหรือไม่ตกทั้งเดือน
ALWAYS_DARK = -1
ALWAYS_LIGHT = -2

ZENITH = 90.833  # ขอบบนดวงอาทิตย์แตะขอบฟ้า รวมการหักเหของแสงแล้ว


def _parse_coord(text):
    """แปลงพิกัดของ zone.tab เป็นองศาทศนิยม

    มีสองรูปแบบเท่านั้น: ±DDMM±DDDMM (11 ตัว) และ ±DDMMSS±DDDMMSS (15 ตัว)
    รูปแบบอื่นให้ raise ทันที — เคยเขียนแบบเดาความยาวแล้วมันคืนค่ามั่วเงียบ ๆ
    ทำให้ลองจิจูดของครึ่งโลกผิดโดยไม่มีอะไรฟ้อง
    """
    if len(text) == 11:
        lat, lon = text[:5], text[5:]
    elif len(text) == 15:
        lat, lon = text[:7], text[7:]
    else:
        raise ValueError(f"รูปแบบพิกัดไม่รู้จัก: {text!r} (ยาว {len(text)})")

    def to_deg(part, deg_digits):
        sign = -1 if part[0] == "-" else 1
        digits = part[1:]
        deg = int(digits[:deg_digits])
        minutes = int(digits[deg_digits : deg_digits + 2])
        seconds = int(digits[deg_digits + 2 : deg_digits + 4] or 0)
        return sign * (deg + minutes / 60 + seconds / 3600)

    lat_deg = to_deg(lat, 2)
    lon_deg = to_deg(lon, 3)
    if not (-90 <= lat_deg <= 90 and -180 <= lon_deg <= 180):
        raise ValueError(f"พิกัดนอกช่วง: {text!r} -> {lat_deg}, {lon_deg}")
    return lat_deg, lon_deg


def load_zone_coordinates():
    for path in ZONE_TAB_CANDIDATES:
        p = pathlib.Path(path)
        if not p.is_file():
            continue
        coords = {}
        for line in p.read_text().splitlines():
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            coords[parts[2]] = _parse_coord(parts[1])
        if coords:
            return coords, path
    raise SystemExit("ไม่พบ zone1970.tab หรือ zone.tab — ต้องมี tzdata ติดตั้งอยู่")


def _sun_event_utc_hours(lat, lon, day, rising):
    """ชั่วโมง UTC ที่ดวงอาทิตย์ขึ้น (rising=True) หรือตก คืน None ถ้าไม่เกิดขึ้นเลย"""
    n = day.timetuple().tm_yday
    lng_hour = lon / 15
    t = n + ((6 if rising else 18) - lng_hour) / 24

    mean_anomaly = 0.9856 * t - 3.289
    true_long = (
        mean_anomaly
        + 1.916 * math.sin(math.radians(mean_anomaly))
        + 0.020 * math.sin(math.radians(2 * mean_anomaly))
        + 282.634
    ) % 360

    right_asc = math.degrees(math.atan(0.91764 * math.tan(math.radians(true_long)))) % 360
    # ต้องดึง right ascension ให้อยู่ควอดแรนต์เดียวกับ true longitude
    right_asc += (true_long // 90) * 90 - (right_asc // 90) * 90
    right_asc /= 15

    sin_dec = 0.39782 * math.sin(math.radians(true_long))
    cos_dec = math.cos(math.asin(sin_dec))

    cos_h = (
        math.cos(math.radians(ZENITH)) - sin_dec * math.sin(math.radians(lat))
    ) / (cos_dec * math.cos(math.radians(lat)))
    if cos_h > 1:
        return None  # ดวงอาทิตย์ไม่ขึ้นเลยในวันนั้น
    if cos_h < -1:
        return None  # ดวงอาทิตย์ไม่ตกเลยในวันนั้น

    h = math.degrees(math.acos(cos_h))
    if rising:
        h = 360 - h
    h /= 15

    return (h + right_asc - 0.06571 * t - 6.622 - lng_hour) % 24


def _local_minutes(utc_hours, day, zone):
    """ชั่วโมง UTC -> นาทีนับจากเที่ยงคืนตามเวลาท้องถิ่นของโซนนั้น"""
    moment = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc) + timedelta(
        hours=utc_hours
    )
    local = moment.astimezone(zone)
    return local.hour * 60 + local.minute


def month_row(lat, lon, zone, year, month):
    """(นาทีที่ขึ้น, นาทีที่ตก) ของวันที่ 15 ซึ่งเป็นตัวแทนของเดือนนั้น"""
    day = date(year, month, 15)
    rise = _sun_event_utc_hours(lat, lon, day, rising=True)
    set_ = _sun_event_utc_hours(lat, lon, day, rising=False)

    if rise is None or set_ is None:
        # ขั้วโลก: ดูมุมของดวงอาทิตย์ตอนเที่ยงว่าอยู่เหนือหรือใต้ขอบฟ้า
        declination = 23.44 * math.sin(math.radians(360 / 365 * (day.timetuple().tm_yday - 81)))
        noon_altitude = 90 - abs(lat - declination)
        return (ALWAYS_LIGHT, ALWAYS_LIGHT) if noon_altitude > 0 else (ALWAYS_DARK, ALWAYS_DARK)

    return _local_minutes(rise, day, zone), _local_minutes(set_, day, zone)


def main():
    coords, source = load_zone_coordinates()
    known = available_timezones()
    year = 2026  # ปีอ้างอิง เวลาขึ้น-ตกแทบไม่ต่างกันระหว่างปี

    rows = {}
    skipped = []
    for name, (lat, lon) in sorted(coords.items()):
        if name not in known:
            skipped.append(name)
            continue
        zone = ZoneInfo(name)
        values = []
        for month in range(1, 13):
            values.extend(month_row(lat, lon, zone, year, month))
        rows[name] = values

    lines = [
        '"""ตารางเวลาดวงอาทิตย์ขึ้น-ตกรายเดือนของแต่ละ timezone (สร้างอัตโนมัติ)',
        "",
        "**อย่าแก้ไฟล์นี้ด้วยมือ** — สร้างใหม่ด้วย:",
        "    python scripts/generate_sun_table.py",
        "",
        f"ที่มาของพิกัด: {source}",
        f"ปีอ้างอิง: {year} คำนวณจากวันที่ 15 ของแต่ละเดือน",
        "",
        "แต่ละโซนเก็บเป็น tuple 24 ค่า = (ขึ้น, ตก) ของเดือน 1..12",
        "หน่วยเป็นนาทีนับจากเที่ยงคืนตามเวลาท้องถิ่นของโซนนั้น",
        f"{ALWAYS_DARK} = ทั้งเดือนดวงอาทิตย์ไม่ขึ้น, {ALWAYS_LIGHT} = ทั้งเดือนไม่ตก",
        '"""',
        "",
        f"ALWAYS_DARK = {ALWAYS_DARK}",
        f"ALWAYS_LIGHT = {ALWAYS_LIGHT}",
        "",
        "SUN_TIMES = {",
    ]
    for name, values in rows.items():
        packed = ", ".join(str(v) for v in values)
        lines.append(f'    "{name}": ({packed}),')
    lines.append("}")
    lines.append("")

    OUTPUT.write_text("\n".join(lines))
    print(f"เขียน {OUTPUT} — {len(rows)} โซน")
    if skipped:
        print(f"ข้าม {len(skipped)} โซนที่ zoneinfo ไม่รู้จัก: {skipped[:5]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
