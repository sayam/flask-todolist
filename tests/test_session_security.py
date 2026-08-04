"""อายุและการต่ออายุของ session (Phase 4 — ดู ADR 0020)

session อยู่ในคุกกี้ที่เซ็นไว้ ไม่มีสำเนาฝั่ง server เทสต์จึงเข้าไปแก้ค่าในนั้น
ตรง ๆ ด้วย `client.session_transaction()` แทนที่จะรอเวลาจริงผ่านไปครึ่งชั่วโมง
— เทสต์ที่ต้องรอเวลาจริงคือเทสต์ที่ไม่มีใครรัน
"""

import time

from app.session_security import AUTH_AT_KEY, SEEN_AT_KEY
from tests.conftest import PASSWORD, issue_token

NEW_PASSWORD = "another-good-passphrase"


def _expire_idle(client):
    """ทำให้ session อยู่ในสภาพ 'ไม่มีความเคลื่อนไหวมานานมาก'"""
    with client.session_transaction() as stored:
        stored[SEEN_AT_KEY] = time.time() - 10 * 24 * 3600


def _expire_absolute(client):
    """เพิ่งใช้งานเมื่อครู่ แต่ login มาตั้งแต่สัปดาห์ที่แล้ว"""
    with client.session_transaction() as stored:
        stored[AUTH_AT_KEY] = time.time() - 10 * 24 * 3600
        stored[SEEN_AT_KEY] = time.time()


# ---------------------------------------------------------------- ตอน login


def test_login_throws_away_whatever_was_in_the_session_before(app, user_id):
    """session fixation: ค่าที่ถูกวางไว้ก่อน login ต้องไม่รอดมาเป็นของ session ที่ยืนยันแล้ว"""
    client = app.test_client()
    with client.session_transaction() as stored:
        stored["planted"] = "ของที่คนอื่นวางไว้"

    client.post("/login", data={"username": "tester", "password": PASSWORD})

    with client.session_transaction() as stored:
        assert "planted" not in stored
        assert stored["_user_id"] == str(user_id)


def test_login_keeps_the_language_picked_on_the_login_page(app, user_id):
    """ล้าง session แล้วต้องไม่ล้างสิ่งที่ผู้ใช้เพิ่งเลือกไปเมื่อกี้ด้วย"""
    client = app.test_client()
    client.get("/lang/th")
    client.post("/login", data={"username": "tester", "password": PASSWORD})

    with client.session_transaction() as stored:
        assert stored["lang"] == "th"


def test_login_stamps_both_clocks(client):
    with client.session_transaction() as stored:
        assert stored[AUTH_AT_KEY] > 0
        assert stored[SEEN_AT_KEY] > 0


# ---------------------------------------------------------------- การหมดอายุ


def test_idle_timeout_signs_the_user_out(client):
    _expire_idle(client)
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]

    with client.session_transaction() as stored:
        assert "_user_id" not in stored, "คุกกี้ต้องถูกล้าง ไม่ใช่แค่เด้งไปหน้า login"


def test_absolute_timeout_signs_out_even_when_still_active(client):
    """ใช้งานอยู่ตลอดก็ต้องหมดอายุ ไม่งั้นคุกกี้ที่ถูกขโมยไปใช้ได้ตลอดกาล"""
    _expire_absolute(client)
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_a_session_without_timestamps_counts_as_expired(client):
    """คุกกี้ที่ออกก่อนมีฟีเจอร์นี้ (หรือถูกแก้จนค่าหาย) ต้อง fail closed"""
    with client.session_transaction() as stored:
        del stored[AUTH_AT_KEY]
        del stored[SEEN_AT_KEY]
    assert client.get("/").status_code == 302


def test_activity_pushes_the_idle_clock_forward(client):
    """ทุก request ที่ผ่านต้องนับเป็นความเคลื่อนไหว ไม่งั้น idle timeout จะตัดคนที่ยังใช้งานอยู่"""
    stale = time.time() - 60
    with client.session_transaction() as stored:
        stored[SEEN_AT_KEY] = stale

    assert client.get("/").status_code == 200
    with client.session_transaction() as stored:
        assert stored[SEEN_AT_KEY] > stale


def test_the_absolute_clock_does_not_move_with_activity(client):
    """ถ้า absolute ถูกเลื่อนตามการใช้งานด้วย มันก็คือ idle timeout ตัวที่สอง"""
    with client.session_transaction() as stored:
        started_at = stored[AUTH_AT_KEY]

    client.get("/")
    with client.session_transaction() as stored:
        assert stored[AUTH_AT_KEY] == started_at


def test_an_expired_session_never_hijacks_an_api_request(app, client, user_id):
    """คำขอที่ยิงมาที่ `/api/` ต้องถูกตัดสินด้วยกติกาของ API เท่านั้น

    ด่านอายุ session ห้ามเด้งคำขอของ API ไปหน้า login เด็ดขาด — client ที่รอ
    JSON อยู่จะได้ HTML กลับไปแล้ว parser พังด้วยข้อความที่ไม่เกี่ยวกับสาเหตุจริง
    (บทเรียนเดียวกับที่ schemathesis จับได้ตอน Phase 3)

    คำตอบที่ถูกคือ 401 ตามกติกาของ API เอง: **คำขอที่มีคุกกี้ติดมาด้วยไม่นับว่า
    ยืนยันตัวตนแล้ว** ไม่ว่าคุกกี้ใบนั้นจะหมดอายุหรือยัง (ADR 0018 —
    Flask-Login อ่าน session ก่อน จึงไม่เรียก request_loader ของ token เลย)
    """
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {issue_token(app, user_id)}"
    _expire_idle(client)

    resp = client.get("/api/v1/todos")
    assert resp.status_code == 401
    assert resp.is_json, "ต้องเป็นซอง error ของ API ไม่ใช่ HTML ของหน้า login"
    assert "Location" not in resp.headers


def test_an_expired_session_does_not_redirect_static_files(client):
    _expire_idle(client)
    assert client.get("/static/base.css").status_code == 200


# ---------------------------------------------------------------- ต่ออายุ / จบ


def test_changing_the_password_issues_a_fresh_session(app, client):
    with client.session_transaction() as stored:
        before = stored[AUTH_AT_KEY]
        # ย้อนนาฬิกาให้ห่างพอที่จะเห็นความต่าง แต่ยังไม่หมดอายุ
        stored[AUTH_AT_KEY] = before - 600
        stored[SEEN_AT_KEY] = time.time()

    client.post(
        "/settings/password",
        data={
            "current_password": PASSWORD,
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )

    with client.session_transaction() as stored:
        assert stored[AUTH_AT_KEY] > before - 600, "นาฬิกา absolute ต้องเริ่มนับใหม่"


def test_logout_leaves_nothing_behind(app, client):
    """เครื่องที่ใช้ร่วมกัน: คนถัดไปต้องไม่เห็นอะไรของคนก่อนหน้าเลย"""
    with client.session_transaction() as stored:
        stored["show_start"] = True

    client.post("/logout")

    with client.session_transaction() as stored:
        assert "_user_id" not in stored
        assert "show_start" not in stored
        assert AUTH_AT_KEY not in stored


def test_logout_keeps_the_chosen_language(app, client):
    client.get("/lang/th")
    client.post("/logout")
    with client.session_transaction() as stored:
        assert stored["lang"] == "th"


# ---------------------------------------------------------------- คุกกี้ที่ถูกก๊อปไป


def test_a_cookie_used_from_another_browser_is_rejected(app, user_id):
    """session_protection = strong: ผูกคุกกี้กับ IP + user agent ของเครื่องที่ login"""
    signed_in = app.test_client()
    signed_in.environ_base["HTTP_USER_AGENT"] = "browser-of-the-owner"
    signed_in.post("/login", data={"username": "tester", "password": PASSWORD})
    assert signed_in.get("/").status_code == 200

    stolen = app.test_client()
    stolen.environ_base["HTTP_USER_AGENT"] = "browser-of-the-thief"
    stolen.set_cookie("session", signed_in.get_cookie("session").value)

    assert stolen.get("/").status_code == 302


def test_the_password_change_leaves_the_old_cookie_useless(app, client):
    """คุกกี้ใบเดิมที่หลุดไปแล้วต้องใช้ต่อไม่ได้หลังเจ้าของเปลี่ยนรหัส"""
    stolen_cookie = client.get_cookie("session").value

    client.post(
        "/settings/password",
        data={
            "current_password": PASSWORD,
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )

    thief = app.test_client()
    thief.set_cookie("session", stolen_cookie)
    resp = thief.get("/")
    assert resp.status_code == 302, "คุกกี้ใบเก่าต้องใช้ไม่ได้แล้ว"
