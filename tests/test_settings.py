"""เทสต์หน้า settings — โปรไฟล์ ภาษา ธีม และ timezone"""

from datetime import datetime
from zoneinfo import ZoneInfo

from app import db
from app.models import Todo, User
from tests.conftest import PASSWORD

BANGKOK = ZoneInfo("Asia/Bangkok")


def _user(app, user_id):
    with app.app_context():
        return db.session.get(User, user_id)


def _prefs(client, **overrides):
    data = {
        "locale": "en",
        "theme": "system",
        "mode": "auto",
        "timezone": "Asia/Bangkok",
    }
    data.update(overrides)
    return client.post("/settings/preferences", data=data, follow_redirects=True)


# --- เข้าถึงหน้า ---


def test_settings_requires_login(anon_client):
    assert anon_client.get("/settings").status_code == 302


def test_settings_page_renders(client):
    resp = client.get("/settings")
    assert resp.status_code == 200
    for label in (b"Profile", b"First name", b"Last name", b"Timezone", b"Theme"):
        assert label in resp.data


def test_settings_link_in_nav(client):
    assert b'href="/settings"' in client.get("/").data


def test_language_and_theme_switchers_moved_out_of_nav(client):
    """ย้ายเข้า settings แล้ว nav ไม่ควรมีลิงก์สลับภาษา/ธีมอีก"""
    body = client.get("/").data
    assert b'href="/lang/' not in body
    assert b'href="/mode/' not in body


def test_login_page_keeps_switchers(anon_client):
    """หน้า login ยังต้องสลับได้ เพราะตอนนั้นเข้า settings ไม่ได้"""
    body = anon_client.get("/login").data
    assert b'href="/lang/' in body
    assert b'href="/mode/' in body


# --- โปรไฟล์ ---


def test_save_first_and_last_name(app, client, user_id):
    client.post(
        "/settings/profile",
        data={"first_name": "สยาม", "last_name": "ศรีผัว"},
        follow_redirects=True,
    )
    user = _user(app, user_id)
    assert (user.first_name, user.last_name) == ("สยาม", "ศรีผัว")


def test_blank_name_stored_as_null_not_empty_string(app, client, user_id):
    """เก็บ '' กับ NULL ปนกันจะทำให้ full_name มีช่องว่างเกิน"""
    client.post(
        "/settings/profile",
        data={"first_name": "  ", "last_name": ""},
        follow_redirects=True,
    )
    user = _user(app, user_id)
    assert user.first_name is None
    assert user.last_name is None


def test_display_name_falls_back_to_username(app, user_id):
    user = _user(app, user_id)
    assert user.display_name == "tester"


def test_display_name_uses_full_name_when_set(app, client, user_id):
    client.post(
        "/settings/profile",
        data={"first_name": "Somchai", "last_name": "Jaidee"},
        follow_redirects=True,
    )
    assert _user(app, user_id).display_name == "Somchai Jaidee"


def test_full_name_with_only_first_name(app, client, user_id):
    client.post("/settings/profile", data={"first_name": "Somchai"}, follow_redirects=True)
    assert _user(app, user_id).display_name == "Somchai"


def test_nav_shows_display_name(client):
    client.post(
        "/settings/profile",
        data={"first_name": "Somchai", "last_name": "Jaidee"},
        follow_redirects=True,
    )
    assert b"Somchai Jaidee" in client.get("/").data


def test_username_is_not_editable(app, client, user_id):
    """ฟอร์มส่ง username มาก็ต้องไม่เปลี่ยน — เป็นตัวระบุตอน login"""
    client.post(
        "/settings/profile",
        data={"username": "hacker", "first_name": "A"},
        follow_redirects=True,
    )
    assert _user(app, user_id).username == "tester"


# --- การตั้งค่าส่วนตัว ---


def test_save_preferences_persists_all_four(app, client, user_id):
    _prefs(client, locale="th", theme="system", mode="dark", timezone="Europe/Berlin")
    user = _user(app, user_id)
    assert (user.locale, user.theme, user.mode, user.timezone_name) == (
        "th",
        "system",
        "dark",
        "Europe/Berlin",
    )


def test_saved_language_overrides_stale_session(client):
    """เคยกดสลับภาษาไว้ที่หน้า login (ค่าค้างใน session) แล้วมาเลือกอีกภาษา
    ใน settings — session ชนะโปรไฟล์ในลำดับการเลือก ถ้าไม่อัปเดต session ด้วย
    ค่าที่เพิ่งกดบันทึกจะไม่มีผลเลย"""
    client.get("/lang/en")  # ค่าค้างใน session
    resp = _prefs(client, locale="th")
    assert "ตั้งค่า".encode() in resp.data, "ยังเป็นภาษาเดิมจาก session"


def test_saved_mode_overrides_stale_session(client):
    client.get("/mode/light")  # ค่าค้างใน session
    resp = _prefs(client, mode="dark")
    assert b'data-theme="dark"' in resp.data, "ยังเป็นโหมดเดิมจาก session"


def test_auto_mode_is_stored_not_null(app, client, user_id):
    """auto เป็นตัวเลือกจริง ไม่ใช่ "ไม่เลือก" """
    _prefs(client, mode="dark")
    _prefs(client, mode="auto")
    assert _user(app, user_id).mode == "auto"


def test_rejects_unsupported_language(app, client, user_id):
    resp = _prefs(client, locale="klingon")
    assert b"Unsupported language" in resp.data
    assert _user(app, user_id).locale is None


def test_rejects_unsupported_theme(app, client, user_id):
    resp = _prefs(client, theme="neon")
    assert b"Unsupported theme" in resp.data
    assert _user(app, user_id).theme is None


def test_rejects_unsupported_timezone(app, client, user_id):
    resp = _prefs(client, timezone="Mars/Olympus_Mons")
    assert b"Unsupported timezone" in resp.data
    assert _user(app, user_id).timezone_name is None


def test_timezone_list_includes_common_zones(client):
    body = client.get("/settings").data
    for zone in (b"Asia/Bangkok", b"Europe/Berlin", b"America/New_York", b"UTC"):
        assert zone in body


# --- timezone มีผลกับ due_date จริง ---


def test_due_date_stored_as_utc(app, client, user_id):
    """กรอก 09:00 ตามเวลากรุงเทพ ต้องเก็บเป็น 02:00 UTC"""
    _prefs(client, timezone="Asia/Bangkok")
    client.post(
        "/add",
        data={"title": "ประชุมเช้า", "due_date": "2026-09-01T09:00"},
        follow_redirects=True,
    )
    with app.app_context():
        todo = Todo.query.filter_by(title="ประชุมเช้า").one()
        assert todo.due_date == datetime(2026, 9, 1, 2, 0)


def test_changing_timezone_shifts_displayed_time(app, client, user_id):
    """เวลาที่เก็บไม่ขยับ แต่เวลาที่แสดงต้องเปลี่ยนตามโซนใหม่"""
    _prefs(client, timezone="Asia/Bangkok")
    client.post(
        "/add",
        data={"title": "ประชุม", "due_date": "2026-09-01T09:00"},
        follow_redirects=True,
    )
    with app.app_context():
        stored = Todo.query.filter_by(title="ประชุม").one().due_date

    _prefs(client, timezone="UTC")
    with app.app_context():
        todo = Todo.query.filter_by(title="ประชุม").one()
        assert todo.due_date == stored, "ค่าใน DB ต้องไม่ขยับตอนเปลี่ยน timezone"
        assert todo.due_local == datetime(2026, 9, 1, 2, 0)


def test_due_time_shown_in_user_timezone(app, client):
    _prefs(client, timezone="Asia/Bangkok")
    client.post(
        "/add",
        data={"title": "ประชุม", "due_date": "2026-09-01T09:00"},
        follow_redirects=True,
    )
    assert b"2026-09-01 09:00" in client.get("/").data

    _prefs(client, timezone="UTC")
    assert b"2026-09-01 02:00" in client.get("/").data


def test_overdue_is_timezone_independent(app, client, user_id):
    """เลยกำหนดหรือยังเทียบใน UTC ทั้งคู่ เปลี่ยนโซนแล้วคำตอบต้องไม่พลิก"""
    past = datetime.now(BANGKOK).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M")
    _prefs(client, timezone="Asia/Bangkok")
    client.post("/add", data={"title": "งานเมื่อกี้", "due_date": past}, follow_redirects=True)

    def overdue():
        with app.app_context():
            return Todo.query.filter_by(title="งานเมื่อกี้").one().is_overdue

    before = overdue()
    _prefs(client, timezone="Pacific/Auckland")
    assert overdue() is before


def test_timezone_used_on_fresh_session(app, user_id):
    with app.app_context():
        db.session.get(User, user_id).timezone_name = "UTC"
        db.session.commit()

    fresh = app.test_client()
    fresh.post("/login", data={"username": "tester", "password": PASSWORD})
    fresh.post(
        "/add",
        data={"title": "งานใหม่", "due_date": "2026-09-01T09:00"},
        follow_redirects=True,
    )
    with app.app_context():
        # user อยู่โซน UTC ค่าที่เก็บจึงเท่ากับที่กรอกพอดี
        assert Todo.query.filter_by(title="งานใหม่").one().due_date == datetime(2026, 9, 1, 9, 0)
