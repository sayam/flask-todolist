"""เทสต์กำหนดส่ง (due_date) และตัวกรองรายการ"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app import db
from app.models import Todo

# TestConfig ตั้ง BABEL_DEFAULT_TIMEZONE เป็น Asia/Bangkok และ user ในเทสต์
# ไม่ได้ตั้ง timezone เอง เวลาท้องถิ่นของเขาจึงเป็นโซนนี้
# คำนวณจากโซนนี้ตรง ๆ เทสต์จะได้ไม่ผูกกับ timezone ของเครื่องที่รัน
TEST_TZ = ZoneInfo("Asia/Bangkok")
NOW = datetime.now(TEST_TZ).replace(tzinfo=None)
TODAY = NOW.date()
# ใช้เที่ยงวันเป็นฐานเพื่อไม่ให้เทสต์พังตอนรันใกล้เที่ยงคืน
NOON_TODAY = datetime.combine(TODAY, datetime.min.time()) + timedelta(hours=12)
EARLIER_TODAY = NOW - timedelta(minutes=30)
LATER_TODAY = NOW + timedelta(minutes=30)
YESTERDAY = NOW - timedelta(days=1)
TOMORROW = NOW + timedelta(days=1)
NEXT_WEEK = NOW + timedelta(days=7)


def _form_value(dt):
    """รูปแบบเดียวกับที่ <input type="datetime-local"> ส่งมา (ไม่มีวินาที)"""
    return dt.strftime("%Y-%m-%dT%H:%M")


def _expected(dt):
    """ค่าที่ควรถูกเก็บ — วินาทีและไมโครวินาทีถูกตัดทิ้งเพราะ form ไม่ได้ส่งมา"""
    return dt.replace(second=0, microsecond=0)


def _add(client, title, due=None, category_id=None):
    data = {"title": title}
    if due is not None:
        data["due_date"] = _form_value(due) if hasattr(due, "strftime") else due
    if category_id is not None:
        data["category_id"] = str(category_id)
    return client.post("/add", data=data, follow_redirects=True)


def _get(app, title):
    with app.app_context():
        return Todo.query.filter_by(title=title).first()


def _prop(app, title, name):
    """อ่าน property ของ todo ภายใน app context

    property อย่าง due_local/is_overdue แตะ todo.user ซึ่ง lazy-load ไม่ได้
    ถ้าออกนอก context ไปแล้ว
    """
    with app.app_context():
        return getattr(Todo.query.filter_by(title=title).first(), name)


def _titles_in_order(resp, titles):
    """คืนลำดับที่ชื่อแต่ละงานปรากฏใน HTML"""
    body = resp.data
    return sorted(titles, key=lambda t: body.index(t.encode()))


# --- due_date ---

def test_add_with_due_date(app, client):
    _add(client, "ส่งรายงาน", due=TOMORROW)
    assert _prop(app, "ส่งรายงาน", "due_local") == _expected(TOMORROW)


def test_time_is_stored_not_just_date(app, client):
    """จุดสำคัญของฟีเจอร์นี้ — เวลาต้องไม่ถูกปัดทิ้ง"""
    due = NOON_TODAY.replace(hour=14, minute=45)
    _add(client, "ประชุมบ่าย", due=due)
    stored = _prop(app, "ประชุมบ่าย", "due_local")
    assert (stored.hour, stored.minute) == (14, 45)


def test_accepts_date_only_as_midnight(app, client):
    """คนยิง API ที่ยังส่งแค่วัน ให้ถือว่าเป็นเที่ยงคืนของวันนั้น"""
    _add(client, "ส่งแค่วัน", due="2026-12-31")
    stored = _prop(app, "ส่งแค่วัน", "due_local")
    assert stored == datetime(2026, 12, 31, 0, 0)


def test_add_without_due_date(app, client):
    _add(client, "งานไม่มีกำหนด")
    assert _prop(app, "งานไม่มีกำหนด", "due_date") is None


def test_add_rejects_malformed_due_date(app, client):
    resp = client.post(
        "/add",
        data={"title": "งานวันที่พัง", "due_date": "31/12/2026"},
        follow_redirects=True,
    )
    assert b"Invalid date format" in resp.data
    with app.app_context():
        assert Todo.query.filter_by(title="งานวันที่พัง").count() == 0


def test_edit_sets_and_clears_due_date(app, client):
    _add(client, "งาน", due=TOMORROW)
    todo_id = _get(app, "งาน").id

    client.post(
        f"/edit/{todo_id}",
        data={"title": "งาน", "due_date": _form_value(NEXT_WEEK)},
        follow_redirects=True,
    )
    with app.app_context():
        assert db.session.get(Todo, todo_id).due_local == _expected(NEXT_WEEK)

    # ส่งค่าว่างมา = ลบกำหนดส่งทิ้ง
    client.post(
        f"/edit/{todo_id}", data={"title": "งาน", "due_date": ""}, follow_redirects=True
    )
    with app.app_context():
        assert db.session.get(Todo, todo_id).due_date is None


# --- is_overdue ---

def test_overdue_true_for_past_date(app, client):
    _add(client, "งานเลยกำหนด", due=YESTERDAY)
    assert _prop(app, "งานเลยกำหนด", "is_overdue") is True


def test_overdue_true_for_earlier_today(app, client):
    """พอมีเวลาแล้ว งานที่เลยเวลาไปเมื่อเช้าถือว่าเลยกำหนดทันที
    ไม่ต้องรอข้ามวันเหมือนตอนที่เก็บแค่วัน"""
    _add(client, "งานเมื่อเช้า", due=EARLIER_TODAY)
    assert _prop(app, "งานเมื่อเช้า", "is_overdue") is True


def test_overdue_false_for_later_today(app, client):
    _add(client, "งานอีกเดี๋ยว", due=LATER_TODAY)
    assert _prop(app, "งานอีกเดี๋ยว", "is_overdue") is False


def test_is_due_today_for_later_today(app, client):
    _add(client, "งานอีกเดี๋ยว", due=LATER_TODAY)
    assert _prop(app, "งานอีกเดี๋ยว", "is_due_today") is True


def test_is_due_today_false_for_tomorrow(app, client):
    _add(client, "งานพรุ่งนี้", due=TOMORROW)
    assert _prop(app, "งานพรุ่งนี้", "is_due_today") is False


def test_is_due_today_false_when_already_overdue(app, client):
    """เลยเวลาไปแล้วให้ขึ้นว่า 'เลยกำหนด' อย่างเดียว ไม่ซ้อนกับ 'ครบกำหนดวันนี้'"""
    _add(client, "งานเมื่อเช้า", due=EARLIER_TODAY)
    assert _prop(app, "งานเมื่อเช้า", "is_due_today") is False


def test_overdue_false_for_future(app, client):
    _add(client, "งานอนาคต", due=TOMORROW)
    assert _prop(app, "งานอนาคต", "is_overdue") is False


def test_overdue_false_without_due_date(app, client):
    _add(client, "งานไร้กำหนด")
    assert _prop(app, "งานไร้กำหนด", "is_overdue") is False


def test_done_task_is_not_overdue(app, client):
    """ทำเสร็จแล้วไม่ต้องมาทวงว่าเลยกำหนด"""
    _add(client, "เสร็จแล้วแต่ช้า", due=YESTERDAY)
    todo_id = _get(app, "เสร็จแล้วแต่ช้า").id
    client.post(f"/toggle/{todo_id}", follow_redirects=True)
    with app.app_context():
        assert db.session.get(Todo, todo_id).is_overdue is False


def test_overdue_shown_in_page(client):
    _add(client, "งานค้าง", due=YESTERDAY)
    resp = client.get("/")
    assert b"Overdue" in resp.data


# --- เรียงลำดับ ---

def test_due_soonest_first_then_undated(client):
    """เพิ่มโดยเรียงกลับด้านกับผลที่คาดไว้ เพื่อไม่ให้เทสต์ผ่านได้
    ด้วยการเรียงตาม created_at เฉย ๆ"""
    _add(client, "พรุ่งนี้", due=TOMORROW)
    _add(client, "อีกอาทิตย์", due=NEXT_WEEK)
    _add(client, "ไม่มีกำหนด")

    order = _titles_in_order(
        client.get("/"), ["พรุ่งนี้", "อีกอาทิตย์", "ไม่มีกำหนด"]
    )
    assert order == ["พรุ่งนี้", "อีกอาทิตย์", "ไม่มีกำหนด"]


# --- ตัวกรองสถานะ ---

def test_filter_active_hides_done(app, client):
    _add(client, "ล้างรถ")
    _add(client, "ตัดผม")
    client.post(f"/toggle/{_get(app, 'ตัดผม').id}", follow_redirects=True)

    resp = client.get("/?status=active")
    assert "ล้างรถ".encode() in resp.data
    assert "ตัดผม".encode() not in resp.data


def test_filter_completed_hides_active(app, client):
    _add(client, "ล้างรถ")
    _add(client, "ตัดผม")
    client.post(f"/toggle/{_get(app, 'ตัดผม').id}", follow_redirects=True)

    resp = client.get("/?status=completed")
    assert "ตัดผม".encode() in resp.data
    assert "ล้างรถ".encode() not in resp.data


def test_filter_all_shows_both(app, client):
    _add(client, "ล้างรถ")
    _add(client, "ตัดผม")
    client.post(f"/toggle/{_get(app, 'ตัดผม').id}", follow_redirects=True)

    resp = client.get("/?status=all")
    assert "ล้างรถ".encode() in resp.data
    assert "ตัดผม".encode() in resp.data


def test_unknown_status_falls_back_to_all(app, client):
    _add(client, "งานเดียว")
    resp = client.get("/?status=มั่ว")
    assert resp.status_code == 200
    assert "งานเดียว".encode() in resp.data


# --- ตัวกรองหมวด ---

def test_filter_by_category(app, client, category_id):
    _add(client, "งานในหมวด", category_id=category_id)
    _add(client, "งานนอกหมวด")

    resp = client.get(f"/?category={category_id}")
    assert "งานในหมวด".encode() in resp.data
    assert "งานนอกหมวด".encode() not in resp.data


def test_filter_no_category(app, client, category_id):
    _add(client, "งานในหมวด", category_id=category_id)
    _add(client, "งานนอกหมวด")

    resp = client.get("/?category=none")
    assert "งานนอกหมวด".encode() in resp.data
    assert "งานในหมวด".encode() not in resp.data


def test_filter_by_other_users_category_is_404(client, other_client, category_id):
    """กรองด้วยหมวดของคนอื่นไม่ได้ ไม่งั้นจะเดาได้ว่าหมวด id ไหนมีอยู่"""
    assert other_client.get(f"/?category={category_id}").status_code == 404


def test_status_and_category_filters_combine(app, client, category_id):
    _add(client, "ในหมวดยังไม่เสร็จ", category_id=category_id)
    _add(client, "ในหมวดเสร็จแล้ว", category_id=category_id)
    _add(client, "นอกหมวดยังไม่เสร็จ")
    client.post(f"/toggle/{_get(app, 'ในหมวดเสร็จแล้ว').id}", follow_redirects=True)

    resp = client.get(f"/?status=active&category={category_id}")
    assert "ในหมวดยังไม่เสร็จ".encode() in resp.data
    assert "ในหมวดเสร็จแล้ว".encode() not in resp.data
    assert "นอกหมวดยังไม่เสร็จ".encode() not in resp.data
