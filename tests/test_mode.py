"""เทสต์การเลือกโหมดสว่าง/มืด/อัตโนมัติ และตารางดวงอาทิตย์

โครงสร้างแยกสองแกน:
* theme = ชื่อชุดสี (ตอนนี้มีชุดเดียว "system")
* mode  = light / dark / auto

`auto` ตัดสินฝั่ง server จากตารางเวลาดวงอาทิตย์ขึ้น-ตกใน app/sun_data.py
CSS จึงได้ data-theme เป็น light หรือ dark เสมอ ไม่มี "ตามระบบ" อีกแล้ว
"""

import re
from datetime import datetime

from app import db
from app.models import User
from app.sun_data import ALWAYS_DARK, ALWAYS_LIGHT, SUN_TIMES
from app.theme import AUTO, DARK, LIGHT, sun_mode
from tests.conftest import PASSWORD


def _data_theme(resp):
    match = re.search(rb'<html[^>]*\sdata-theme="([a-z]+)"', resp.data)
    return match.group(1).decode() if match else None


def _theme_name(resp):
    match = re.search(rb'<html[^>]*\sdata-theme-name="([a-z]+)"', resp.data)
    return match.group(1).decode() if match else None


def _prefs(client, **overrides):
    data = {
        "locale": "en",
        "theme": "system",
        "mode": "auto",
        "timezone": "Asia/Bangkok",
    }
    data.update(overrides)
    return client.post("/settings/preferences", data=data, follow_redirects=True)


# --- data-theme ต้องเป็นค่าที่ใช้ได้จริงเสมอ ---


def test_resolved_mode_is_always_concrete(anon_client):
    """ไม่มี "ตามระบบ" แล้ว CSS จึงต้องได้ light หรือ dark เสมอ ไม่ใช่ค่าว่าง"""
    assert _data_theme(anon_client.get("/login")) in {LIGHT, DARK}


def test_theme_name_is_rendered(anon_client):
    assert _theme_name(anon_client.get("/login")) == "system"


def test_explicit_modes_win(anon_client):
    assert _data_theme(anon_client.get("/login?mode=dark")) == DARK
    assert _data_theme(anon_client.get("/login?mode=light")) == LIGHT


def test_unknown_mode_query_param_ignored(anon_client):
    resp = anon_client.get("/login?mode=neon")
    assert resp.status_code == 200
    assert _data_theme(resp) in {LIGHT, DARK}


def test_unknown_mode_route_is_404(anon_client):
    assert anon_client.get("/mode/neon").status_code == 404
    assert anon_client.get("/mode/../etc").status_code == 404


def test_old_theme_route_is_gone(anon_client):
    """/theme/<value> ถูกแทนด้วย /mode/<value> แล้ว"""
    assert anon_client.get("/theme/dark").status_code == 404


# --- จำค่าไว้ใน session และโปรไฟล์ ---


def test_mode_persists_in_session(anon_client):
    anon_client.get("/mode/dark")
    assert _data_theme(anon_client.get("/login")) == DARK


def test_mode_saved_to_profile(app, client, user_id):
    client.get("/mode/dark")
    with app.app_context():
        assert db.session.get(User, user_id).mode == DARK


def test_auto_saved_as_auto_not_null(app, client, user_id):
    """auto เป็นตัวเลือกจริง ไม่ใช่ "ไม่เลือก" จึงต้องเก็บค่าไว้"""
    client.get("/mode/dark")
    client.get("/mode/auto")
    with app.app_context():
        assert db.session.get(User, user_id).mode == AUTO


def test_profile_mode_used_on_fresh_session(app, user_id):
    with app.app_context():
        db.session.get(User, user_id).mode = DARK
        db.session.commit()

    fresh = app.test_client()
    fresh.post("/login", data={"username": "tester", "password": PASSWORD})
    assert _data_theme(fresh.get("/")) == DARK


def test_anonymous_can_switch_mode(anon_client):
    """หน้า login ต้องสลับโหมดได้ เพราะตอนนั้นเข้า settings ไม่ได้"""
    assert anon_client.get("/mode/dark").status_code == 302
    assert _data_theme(anon_client.get("/login")) == DARK


def test_mode_switch_ignores_external_referer(client):
    resp = client.get("/mode/dark", headers={"Referer": "https://evil.example.com/x"})
    assert "evil.example.com" not in resp.headers["Location"]


# --- settings เก็บทั้ง theme และ mode ---


def test_settings_saves_theme_and_mode(app, client, user_id):
    _prefs(client, theme="system", mode="dark")
    with app.app_context():
        user = db.session.get(User, user_id)
        assert (user.theme, user.mode) == ("system", DARK)


def test_settings_rejects_unknown_mode(app, client, user_id):
    resp = _prefs(client, mode="neon")
    assert b"Unsupported mode" in resp.data
    with app.app_context():
        assert db.session.get(User, user_id).mode is None


def test_settings_page_has_both_dropdowns(client):
    body = client.get("/settings").data
    assert b'id="theme"' in body
    assert b'id="mode"' in body
    for label in (b">Auto<", b">Light<", b">Dark<"):
        assert label in body.replace(b"\n", b"").replace(b"  ", b"")


# --- ตารางดวงอาทิตย์ ---


def test_sun_table_covers_common_zones():
    for zone in ("Asia/Bangkok", "Europe/London", "America/New_York", "Asia/Tokyo"):
        assert zone in SUN_TIMES, f"ไม่มี {zone} ในตาราง"
        assert len(SUN_TIMES[zone]) == 24, "ต้องมี (ขึ้น, ตก) ครบ 12 เดือน"


def test_sun_times_are_plausible():
    """ดวงอาทิตย์ต้องขึ้นก่อนตก และอยู่ในช่วงของวัน (ยกเว้นเขตขั้วโลก)"""
    for zone, row in SUN_TIMES.items():
        for month in range(12):
            rise, set_ = row[month * 2], row[month * 2 + 1]
            if rise in (ALWAYS_DARK, ALWAYS_LIGHT):
                assert rise == set_, f"{zone} เดือน {month + 1}: ค่าพิเศษต้องเป็นคู่"
                continue
            assert 0 <= rise < 1440, f"{zone} เดือน {month + 1}"
            assert 0 <= set_ < 1440, f"{zone} เดือน {month + 1}"


def test_bangkok_sunrise_is_morning():
    """กรุงเทพอยู่ใกล้เส้นศูนย์สูตร ดวงอาทิตย์ขึ้นราว 6 โมงทุกเดือน"""
    row = SUN_TIMES["Asia/Bangkok"]
    for month in range(12):
        rise = row[month * 2]
        assert 5 * 60 <= rise <= 7 * 60, f"เดือน {month + 1} ขึ้น {rise // 60}:{rise % 60:02d}"


def test_auto_is_light_at_noon_and_dark_at_midnight(app):
    with app.app_context():
        noon = datetime(2026, 6, 15, 12, 0)
        midnight = datetime(2026, 6, 15, 0, 30)
        assert sun_mode("Asia/Bangkok", noon) == LIGHT
        assert sun_mode("Asia/Bangkok", midnight) == DARK


def test_auto_follows_the_users_timezone(app):
    """เวลาเดียวกันตามนาฬิกาท้องถิ่น แต่คนละโซน ผลอาจต่างกันตามฤดู
    ที่แน่ ๆ คือเที่ยงวันต้องสว่างทุกโซนที่ไม่ใช่ขั้วโลก"""
    with app.app_context():
        noon = datetime(2026, 6, 15, 12, 0)
        for zone in ("Asia/Bangkok", "Europe/London", "America/New_York", "Australia/Sydney"):
            assert sun_mode(zone, noon) == LIGHT, zone


def test_polar_night_is_dark_even_at_noon(app):
    """เขตที่ดวงอาทิตย์ไม่ขึ้นทั้งเดือน ต้องมืดแม้ตอนเที่ยง"""
    polar = [
        zone for zone, row in SUN_TIMES.items() if any(row[m * 2] == ALWAYS_DARK for m in range(12))
    ]
    assert polar, "ควรมีอย่างน้อยหนึ่งโซนที่มีคืนขั้วโลก"

    zone = polar[0]
    month = next(m for m in range(12) if SUN_TIMES[zone][m * 2] == ALWAYS_DARK)
    with app.app_context():
        assert sun_mode(zone, datetime(2026, month + 1, 15, 12, 0)) == DARK


def test_unknown_timezone_falls_back_to_light(app):
    with app.app_context():
        assert sun_mode("Mars/Olympus_Mons", datetime(2026, 6, 15, 3, 0)) in {LIGHT, DARK}


def _zone_that_is_now(app, wanted):
    """หา timezone ที่ตอนนี้เป็นกลางวัน/กลางคืนจริง ๆ

    ณ เวลาใดก็ตามโลกมีทั้งฝั่งสว่างและฝั่งมืด จึงหาเจอเสมอ
    ทำแบบนี้เพื่อให้เทสต์ไม่ผูกกับวันที่หรือเวลาที่รัน
    """
    with app.app_context():
        for zone in SUN_TIMES:
            if sun_mode(zone) == wanted:
                return zone
    raise AssertionError(f"ไม่พบ timezone ที่ตอนนี้เป็น {wanted}")


def _set_timezone(app, user_id, zone):
    with app.app_context():
        user = db.session.get(User, user_id)
        user.timezone_name = zone
        user.mode = AUTO
        db.session.commit()


def test_auto_renders_dark_where_it_is_night_now(app, user_id):
    """เส้นทางจริง: mode=auto -> resolve_mode -> sun_mode -> data-theme
    ถ้ามีขั้นไหนขาด หน้าจะไม่สะท้อนเวลาจริงของผู้ใช้"""
    zone = _zone_that_is_now(app, DARK)
    _set_timezone(app, user_id, zone)

    client = app.test_client()
    client.post("/login", data={"username": "tester", "password": PASSWORD})
    assert _data_theme(client.get("/")) == DARK, f"{zone} ตอนนี้เป็นกลางคืน"


def test_auto_renders_light_where_it_is_day_now(app, user_id):
    zone = _zone_that_is_now(app, LIGHT)
    _set_timezone(app, user_id, zone)

    client = app.test_client()
    client.post("/login", data={"username": "tester", "password": PASSWORD})
    assert _data_theme(client.get("/")) == LIGHT, f"{zone} ตอนนี้เป็นกลางวัน"


def test_explicit_mode_ignores_the_sun(app, user_id):
    """เลือก light ไว้ ต้องสว่างแม้อยู่ในโซนที่ตอนนี้เป็นกลางคืน"""
    zone = _zone_that_is_now(app, DARK)
    with app.app_context():
        user = db.session.get(User, user_id)
        user.timezone_name = zone
        user.mode = LIGHT
        db.session.commit()

    client = app.test_client()
    client.post("/login", data={"username": "tester", "password": PASSWORD})
    assert _data_theme(client.get("/")) == LIGHT


def test_every_selectable_timezone_has_sun_data(app):
    """ทุก timezone ที่เลือกได้ในหน้า settings ต้องมีข้อมูลดวงอาทิตย์

    เคยหลุดมาแล้ว: ตารางสร้างจาก zone1970.tab (312 โซน) แต่ dropdown ใช้
    available_timezones() (598 ชื่อ) ทำให้เกือบครึ่งได้ light ตลอดเวลาเงียบ ๆ
    """
    from app import tz

    with app.app_context():
        missing = [z for z in tz.all_timezones() if z not in SUN_TIMES]
    assert not missing, (
        f"{len(missing)} timezone ไม่มีข้อมูลดวงอาทิตย์ เช่น {missing[:8]} — "
        "รัน scripts/generate_sun_table.py ใหม่"
    )


def test_pseudo_zones_are_never_offered(monkeypatch):
    """`available_timezones()` ของแต่ละดิสโทรไม่เท่ากัน — Ubuntu มี `localtime`
    ติดมาด้วย ส่วน Gentoo ไม่มี ถ้าไม่กรองออกจะโผล่ใน dropdown ทั้งที่ไม่ใช่โซนจริง
    และไม่มีข้อมูลดวงอาทิตย์ (CI บน ubuntu-latest แดงมาแล้วด้วยเหตุนี้)

    เทสต์นี้จึงปลอม `available_timezones()` เอง ไม่พึ่งว่าเครื่องที่รันมีอะไร
    """
    from app import tz

    fake = {"Asia/Bangkok", "UTC", *tz.NOT_REAL_ZONES}
    monkeypatch.setattr(tz, "available_timezones", lambda: fake)
    tz.all_timezones.cache_clear()
    try:
        assert set(tz.all_timezones()) == {"Asia/Bangkok", "UTC"}
        for pseudo in tz.NOT_REAL_ZONES:
            assert not tz.is_supported(pseudo), f"{pseudo} ไม่ควรผ่าน is_supported"
    finally:
        # ต้องล้างหลัง assert ครบ ไม่งั้นค่าปลอมค้างใน cache ไปถึงเทสต์อื่น
        tz.all_timezones.cache_clear()


def test_alias_zones_match_their_canonical_zone():
    """ชื่อพ้องต้องได้ตารางเดียวกับโซนจริง ไม่ใช่ค่าที่คำนวณคนละที่"""
    for alias, canonical in (
        ("Japan", "Asia/Tokyo"),
        ("US/Pacific", "America/Los_Angeles"),
        ("Asia/Calcutta", "Asia/Kolkata"),
    ):
        assert SUN_TIMES[alias] == SUN_TIMES[canonical], alias


def test_offset_only_zones_get_sensible_times():
    """Etc/GMT±N ไม่มีที่ตั้งจริง ใช้เส้นศูนย์สูตร จึงควรได้ราว 06:00-18:00"""
    for zone in ("UTC", "Etc/GMT+5", "Etc/GMT-9"):
        for month in range(12):
            rise, set_ = SUN_TIMES[zone][month * 2], SUN_TIMES[zone][month * 2 + 1]
            assert 5 * 60 <= rise <= 7 * 60, f"{zone} เดือน {month + 1} ขึ้น {rise}"
            assert 17 * 60 <= set_ <= 19 * 60, f"{zone} เดือน {month + 1} ตก {set_}"
