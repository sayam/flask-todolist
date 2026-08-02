"""สร้าง app/sun_data.py — ตารางเวลาดวงอาทิตย์ขึ้น-ตกรายเดือนของแต่ละ timezone

รันตอนจะ regenerate เท่านั้น ไม่ได้ถูกเรียกตอนแอปทำงาน:

    python scripts/generate_sun_table.py

พิกัดของแต่ละโซนมาจาก zone.tab ของ tzdata ที่ติดตั้งในเครื่อง
ชื่อที่ tzdata ไม่ได้ให้พิกัดไว้จะถูกจับคู่กับโซนที่ไฟล์ tzdata เหมือนกันเป๊ะ
และ Etc/GMT±N ที่ไม่มีความหมายทางภูมิศาสตร์ใช้เส้นศูนย์สูตรตาม offset
ผลคือครอบคลุมทุกชื่อที่ zoneinfo รู้จัก — ไม่มีโซนไหนที่โหมด auto ใช้ไม่ได้
ส่วนเวลาขึ้น-ตกคำนวณด้วย "Sunrise/Sunset Algorithm" ของ Almanac
(ตัวเดียวกับที่ NOAA ใช้อธิบาย) ไม่ต้องพึ่ง library ภายนอก

ความแม่นยำระดับไม่กี่นาที ซึ่งเกินพอสำหรับตัดสินว่าจะแสดงธีมสว่างหรือมืด
"""

import math
import pathlib
import sys
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, available_timezones

# zone.tab มาก่อนเพราะแยกพิกัดรายประเทศ (418 โซน) ส่วน zone1970.tab
# รวมโซนที่กฎเวลาเหมือนกันไว้ด้วยกันเหลือ 312 ทำให้หลายเมืองต้องยืมพิกัดคนอื่น
ZONE_TAB_CANDIDATES = (
    "/usr/share/zoneinfo/zone.tab",
    "/usr/share/zoneinfo/zone1970.tab",
)
ZONEINFO_ROOT = pathlib.Path("/usr/share/zoneinfo")
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

    cos_h = (math.cos(math.radians(ZENITH)) - sin_dec * math.sin(math.radians(lat))) / (
        cos_dec * math.cos(math.radians(lat))
    )
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
    moment = datetime.combine(day, datetime.min.time(), tzinfo=UTC) + timedelta(hours=utc_hours)
    local = moment.astimezone(zone)
    return local.hour * 60 + local.minute


def month_row(lat, lon, zone, year, month):
    """(นาทีที่ขึ้น, นาทีที่ตก) ของวันที่ 15 ซึ่งเป็นตัวแทนของเดือนนั้น"""
    day = date(year, month, 15)
    rise = _sun_event_utc_hours(lat, lon, day, rising=True)
    set_ = _sun_event_utc_hours(lat, lon, day, rising=False)

    if rise is None or set_ is None:
        # เขตขั้วโลก — ดูมุมของดวงอาทิตย์ตอนเที่ยงว่าอยู่เหนือหรือใต้ขอบฟ้า
        declination = 23.44 * math.sin(math.radians(360 / 365 * (day.timetuple().tm_yday - 81)))
        noon_altitude = 90 - abs(lat - declination)
        return (ALWAYS_LIGHT, ALWAYS_LIGHT) if noon_altitude > 0 else (ALWAYS_DARK, ALWAYS_DARK)

    return _local_minutes(rise, day, zone), _local_minutes(set_, day, zone)


def _row_for(lat, lon, zone, year):
    values = []
    for month in range(1, 13):
        values.extend(month_row(lat, lon, zone, year, month))
    return values


def _tzfile_bytes(name):
    """เนื้อไฟล์ tzdata ของโซนนั้น — ไฟล์เหมือนกันเป๊ะ = โซนเดียวกันคนละชื่อ"""
    path = ZONEINFO_ROOT / name
    return path.read_bytes() if path.is_file() else None


def _offset_hours(zone, year):
    """UTC offset เป็นชั่วโมง ใช้กับโซนที่ไม่มีความหมายทางภูมิศาสตร์"""
    moment = datetime(year, 1, 15, 12, tzinfo=zone)
    offset = moment.utcoffset()
    return offset.total_seconds() / 3600 if offset is not None else 0.0


def main():
    coords, source = load_zone_coordinates()
    known = sorted(available_timezones())
    year = 2026  # ปีอ้างอิง เวลาขึ้น-ตกแทบไม่ต่างกันระหว่างปี

    rows = {}
    by_coordinates = []

    # 1) โซนที่ tzdata ให้พิกัดมาตรง ๆ — แม่นที่สุด
    for name in known:
        if name in coords:
            lat, lon = coords[name]
            rows[name] = _row_for(lat, lon, ZoneInfo(name), year)
            by_coordinates.append(name)

    # 2) ชื่อที่เหลือ: ถ้าไฟล์ tzdata เหมือนโซนที่ทำไปแล้วเป๊ะ ก็คือโซนเดียวกัน
    #    (เช่น Japan = Asia/Tokyo, US/Pacific = America/Los_Angeles)
    index: dict[bytes, str] = {}
    for name in by_coordinates:
        blob = _tzfile_bytes(name)
        if blob is not None:
            index.setdefault(blob, name)

    aliased = []
    for name in known:
        if name in rows:
            continue
        blob = _tzfile_bytes(name)
        twin = index.get(blob) if blob is not None else None
        if twin:
            rows[name] = list(rows[twin])
            aliased.append(name)

    # 3) ที่เหลือไม่มีความหมายทางภูมิศาสตร์ (Etc/GMT±N, UTC ฯลฯ)
    #    สมมติว่าอยู่บนเส้นศูนย์สูตรที่ลองจิจูดตรงกับ offset — ได้ขึ้น ~06:00 ตก ~18:00
    synthetic = []
    for name in known:
        if name in rows:
            continue
        zone = ZoneInfo(name)
        rows[name] = _row_for(0.0, _offset_hours(zone, year) * 15, zone, year)
        synthetic.append(name)

    missing = [n for n in known if n not in rows]
    assert not missing, f"ยังมีโซนที่ไม่มีข้อมูล: {missing[:10]}"

    lines = [
        '"""ตารางเวลาดวงอาทิตย์ขึ้น-ตกรายเดือนของแต่ละ timezone (สร้างอัตโนมัติ)',
        "",
        "**อย่าแก้ไฟล์นี้ด้วยมือ** — สร้างใหม่ด้วย:",
        "    python scripts/generate_sun_table.py",
        "",
        f"ที่มาของพิกัด: {source}",
        f"ปีอ้างอิง: {year} คำนวณจากวันที่ 15 ของแต่ละเดือน",
        "",
        "ครอบคลุมทุกชื่อที่ zoneinfo รู้จัก โดย",
        f"  {len(by_coordinates)} โซนมีพิกัดของตัวเองใน tzdata",
        f"  {len(aliased)} โซนเป็นชื่อพ้องของโซนข้างบน (ไฟล์ tzdata เหมือนกันเป๊ะ)",
        f"  {len(synthetic)} โซนไม่มีความหมายทางภูมิศาสตร์ (Etc/GMT±N ฯลฯ)",
        "    ใช้เส้นศูนย์สูตรที่ลองจิจูดตรงกับ offset จึงได้ขึ้น ~06:00 ตก ~18:00",
        "",
        "แต่ละโซนเก็บเป็น tuple 24 ค่า = (ขึ้น, ตก) ของเดือน 1..12",
        "หน่วยเป็นนาทีนับจากเที่ยงคืนตามเวลาท้องถิ่นของโซนนั้น",
        f"{ALWAYS_DARK} = ทั้งเดือนดวงอาทิตย์ไม่ขึ้น, {ALWAYS_LIGHT} = ทั้งเดือนไม่ตก",
        '"""',
        "",
        f"ALWAYS_DARK = {ALWAYS_DARK}",
        f"ALWAYS_LIGHT = {ALWAYS_LIGHT}",
        "",
        "SUN_TIMES: dict[str, tuple[int, ...]] = {",
    ]
    for name in known:
        packed = ", ".join(str(v) for v in rows[name])
        lines.append(f'    "{name}": ({packed}),')
    lines.append("}")
    lines.append("")

    OUTPUT.write_text("\n".join(lines))
    print(f"เขียน {OUTPUT} — {len(rows)} โซน")
    print(f"  มีพิกัดเอง {len(by_coordinates)} / ชื่อพ้อง {len(aliased)} / สังเคราะห์ {len(synthetic)}")
    if synthetic:
        print(f"  ตัวอย่างที่สังเคราะห์: {synthetic[:6]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
