"""เทสต์ start_date, ตัวกรองตามวัน และหน้าแก้งาน

ตัวกรองตามวันดูจาก `due_date` อย่างเดียว (ไม่ใช่ start_date)
และคำนวณในเวลาท้องถิ่นของผู้ใช้ก่อนแปลงเป็น UTC ตอนไปเทียบกับ DB
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app import db
from app.models import Todo

# TestConfig ตั้ง BABEL_DEFAULT_TIMEZONE เป็น Asia/Bangkok และ user ในเทสต์
# ไม่ได้ตั้ง timezone เอง เวลาท้องถิ่นของเขาจึงเป็นโซนนี้
TEST_TZ = ZoneInfo("Asia/Bangkok")


def _now_local():
    return datetime.now(TEST_TZ).replace(tzinfo=None)


def _form(dt):
    return dt.strftime("%Y-%m-%dT%H:%M")


def _add(client, title, due=None, start=None, category_id=None):
    data = {"title": title}
    if due is not None:
        data["due_date"] = _form(due) if hasattr(due, "strftime") else due
    if start is not None:
        data["start_date"] = _form(start) if hasattr(start, "strftime") else start
    if category_id is not None:
        data["category_id"] = str(category_id)
    return client.post("/add", data=data, follow_redirects=True)


def _titles(resp):
    """ชื่องานที่โผล่ในลิสต์ — อ่านจาก span ของแถว ไม่ปนกับตัวกรองด้านบน"""
    import re

    body = resp.data.decode()
    return re.findall(r'<span class="task-title[^"]*">([^<]*)</span>', body)


def _prop(app, title, name):
    with app.app_context():
        return getattr(Todo.query.filter_by(title=title).first(), name)


# --- #1 start_date ---


def test_add_with_start_date(app, client):
    start = _now_local() + timedelta(days=1)
    _add(client, "งานมีวันเริ่ม", start=start)
    assert _prop(app, "งานมีวันเริ่ม", "start_local") == start.replace(second=0, microsecond=0)


def test_start_date_is_optional(app, client):
    _add(client, "งานไม่มีวันเริ่ม")
    assert _prop(app, "งานไม่มีวันเริ่ม", "start_date") is None


def test_start_date_stored_as_utc(app, client):
    """เก็บเป็น UTC เหมือน due_date — กรอก 09:00 กรุงเทพ ต้องได้ 02:00 UTC"""
    _add(client, "งานเช้า", start="2026-09-01T09:00")
    assert _prop(app, "งานเช้า", "start_date") == datetime(2026, 9, 1, 2, 0)


def test_malformed_start_date_rejected(app, client):
    resp = _add(client, "งานวันที่พัง", start="31/12/2026")
    assert b"Invalid date format" in resp.data
    with app.app_context():
        assert Todo.query.filter_by(title="งานวันที่พัง").count() == 0


# --- #3 หน้าแก้งาน ---


def test_edit_page_shows_all_fields(app, client):
    _add(client, "งานเดิม")
    todo_id = _prop(app, "งานเดิม", "id")
    body = client.get(f"/edit/{todo_id}").data
    for field in (b'name="title"', b'name="start_date"', b'name="due_date"', b'name="category_id"'):
        assert field in body


def test_edit_saves_name_start_and_due(app, client):
    _add(client, "งานเดิม")
    todo_id = _prop(app, "งานเดิม", "id")
    start = _now_local() + timedelta(days=1)
    due = _now_local() + timedelta(days=2)

    client.post(
        f"/edit/{todo_id}",
        data={"title": "งานใหม่", "start_date": _form(start), "due_date": _form(due)},
        follow_redirects=True,
    )
    with app.app_context():
        todo = db.session.get(Todo, todo_id)
        assert todo.title == "งานใหม่"
        assert todo.start_local == start.replace(second=0, microsecond=0)
        assert todo.due_local == due.replace(second=0, microsecond=0)


def test_edit_can_clear_dates(app, client):
    _add(client, "งาน", start=_now_local(), due=_now_local())
    todo_id = _prop(app, "งาน", "id")
    client.post(
        f"/edit/{todo_id}",
        data={"title": "งาน", "start_date": "", "due_date": ""},
        follow_redirects=True,
    )
    with app.app_context():
        todo = db.session.get(Todo, todo_id)
        assert todo.start_date is None
        assert todo.due_date is None


def test_edit_page_of_other_users_task_is_404(app, client, other_client):
    _add(client, "งานของ tester")
    todo_id = _prop(app, "งานของ tester", "id")
    assert other_client.get(f"/edit/{todo_id}").status_code == 404


def test_edit_rejects_blank_title(app, client):
    _add(client, "งานเดิม")
    todo_id = _prop(app, "งานเดิม", "id")
    client.post(f"/edit/{todo_id}", data={"title": "  "}, follow_redirects=True)
    with app.app_context():
        assert db.session.get(Todo, todo_id).title == "งานเดิม"


# --- #2 ตัวกรองตามวัน ---


def test_today_filter(app, client):
    _add(client, "วันนี้", due=_now_local().replace(hour=23, minute=0))
    _add(client, "พรุ่งนี้", due=_now_local() + timedelta(days=1))
    _add(client, "ไม่มีกำหนด")

    titles = _titles(client.get("/?when=today"))
    assert "วันนี้" in titles
    assert "พรุ่งนี้" not in titles
    assert "ไม่มีกำหนด" not in titles


def test_tomorrow_filter(app, client):
    _add(client, "วันนี้", due=_now_local().replace(hour=23, minute=0))
    tomorrow = (_now_local() + timedelta(days=1)).replace(hour=10, minute=0)
    _add(client, "พรุ่งนี้", due=tomorrow)

    titles = _titles(client.get("/?when=tomorrow"))
    assert titles == ["พรุ่งนี้"]


def test_upcoming_respects_the_chosen_window(app, client):
    now = _now_local()
    _add(client, "อีก10นาที", due=now + timedelta(minutes=10))
    _add(client, "อีก2ชั่วโมง", due=now + timedelta(hours=2))
    _add(client, "เมื่อกี้", due=now - timedelta(minutes=10))

    within15 = _titles(client.get("/?when=upcoming&within=15"))
    assert within15 == ["อีก10นาที"], "15 นาทีต้องไม่รวมงานอีก 2 ชม."

    within8h = _titles(client.get("/?when=upcoming&within=480"))
    assert "อีก10นาที" in within8h
    assert "อีก2ชั่วโมง" in within8h


def test_upcoming_excludes_overdue(app, client):
    """งานที่เลยกำหนดแล้วไม่ใช่ของที่ "กำลังจะถึง" """
    _add(client, "เลยไปแล้ว", due=_now_local() - timedelta(hours=1))
    assert _titles(client.get("/?when=upcoming&within=480")) == []


def test_unknown_within_falls_back_to_default(app, client):
    _add(client, "อีก2ชั่วโมง", due=_now_local() + timedelta(hours=2))
    # ค่ามั่วต้องตกไปใช้ 8 ชม. ไม่ใช่พังหรือกรองทิ้งหมด
    assert _titles(client.get("/?when=upcoming&within=99999")) == ["อีก2ชั่วโมง"]


def test_range_filter_with_two_dates(app, client):
    base = _now_local().replace(hour=12, minute=0)
    _add(client, "ในช่วง", due=base + timedelta(days=2))
    _add(client, "นอกช่วง", due=base + timedelta(days=9))

    start = (base + timedelta(days=1)).strftime("%Y-%m-%d")
    end = (base + timedelta(days=3)).strftime("%Y-%m-%d")
    titles = _titles(client.get(f"/?when=range&date_from={start}&date_to={end}"))
    assert titles == ["ในช่วง"]


def test_range_with_only_start_means_that_whole_day(app, client):
    """เลือกวันเดียว: ใส่แค่ช่องเริ่ม ต้องครอบทั้งวันนั้น 00:00-23:59"""
    day = (_now_local() + timedelta(days=3)).date()
    _add(client, "เช้าวันนั้น", due=datetime.combine(day, datetime.min.time()).replace(hour=1))
    late_night = datetime.combine(day, datetime.min.time()).replace(hour=23, minute=30)
    _add(client, "ดึกวันนั้น", due=late_night)
    next_day = datetime.combine(day + timedelta(days=1), datetime.min.time()).replace(hour=10)
    _add(client, "วันถัดไป", due=next_day)

    titles = _titles(client.get(f"/?when=range&date_from={day.isoformat()}"))
    assert "เช้าวันนั้น" in titles
    assert "ดึกวันนั้น" in titles
    assert "วันถัดไป" not in titles


def test_range_accepts_times_too(app, client):
    day = (_now_local() + timedelta(days=3)).date()
    early = datetime.combine(day, datetime.min.time()).replace(hour=9)
    late = datetime.combine(day, datetime.min.time()).replace(hour=20)
    _add(client, "เช้า", due=early)
    _add(client, "เย็น", due=late)

    titles = _titles(client.get(f"/?when=range&date_from={day}T08:00&date_to={day}T12:00"))
    assert titles == ["เช้า"]


def test_malformed_range_falls_back_to_all(app, client):
    _add(client, "งานเดียว", due=_now_local() + timedelta(days=1))
    resp = client.get("/?when=range&date_from=31/12/2026")
    assert b"Invalid date format" in resp.data
    assert "งานเดียว" in _titles(resp)


def test_unknown_when_falls_back_to_all(app, client):
    _add(client, "งานเดียว")
    assert _titles(client.get("/?when=มั่ว")) == ["งานเดียว"]


def test_date_filter_combines_with_status(app, client):
    today = _now_local().replace(hour=22, minute=0)
    _add(client, "วันนี้ยังไม่เสร็จ", due=today)
    _add(client, "วันนี้เสร็จแล้ว", due=today)
    with app.app_context():
        done = Todo.query.filter_by(title="วันนี้เสร็จแล้ว").one()
        done.done = True
        db.session.commit()

    titles = _titles(client.get("/?when=today&status=active"))
    assert titles == ["วันนี้ยังไม่เสร็จ"]


def test_filter_uses_due_date_not_start_date(app, client):
    """งานที่เริ่มวันนี้แต่ครบกำหนดอาทิตย์หน้า ต้องไม่โผล่ในตัวกรอง Today"""
    _add(
        client,
        "เริ่มวันนี้ส่งอาทิตย์หน้า",
        start=_now_local(),
        due=_now_local() + timedelta(days=7),
    )
    assert _titles(client.get("/?when=today")) == []


# --- checkbox แสดงวันเริ่ม ---


def test_start_date_hidden_by_default(app, client):
    _add(client, "งาน", start=_now_local())
    assert b"Start:" not in client.get("/").data


def test_show_start_checkbox_reveals_it(app, client):
    _add(client, "งาน", start=_now_local())
    resp = client.get("/?filters_submitted=1&show_start=1")
    assert b"Start:" in resp.data


def test_show_start_is_remembered_across_pages(app, client):
    _add(client, "งาน", start=_now_local())
    client.get("/?filters_submitted=1&show_start=1")
    # กดลิงก์ตัวกรองอื่นซึ่งไม่ได้ส่ง show_start มาด้วย ค่าต้องยังอยู่
    assert b"Start:" in client.get("/?status=active").data


def test_unticking_turns_it_off(app, client):
    _add(client, "งาน", start=_now_local())
    client.get("/?filters_submitted=1&show_start=1")
    client.get("/?filters_submitted=1")  # ส่งฟอร์มโดยไม่ติ๊ก
    assert b"Start:" not in client.get("/").data


# --- ลิงก์ตัวกรองต้องไม่ล้างตัวกรองอื่น ---


def test_status_link_keeps_the_date_filter(app, client):
    resp = client.get("/?when=today&status=all")
    assert b"when=today" in resp.data, "ลิงก์สถานะต้องพา when ไปด้วย"


def test_category_link_keeps_the_date_filter(app, client, category_id):
    resp = client.get("/?when=tomorrow")
    assert b"when=tomorrow" in resp.data
