"""โควตาของ `/api/v1` — นับต่อใบ token (Phase 5 · P5-08 · ADR 0018)

ADR 0018 บันทึกไว้ตั้งแต่ Phase 3 ว่ายังไม่มี rate limit ของ API และรอ storage
ที่ไม่ใช่ `memory://` ก่อน (ไม่งั้นเพดานจริงเป็น N เท่าตามจำนวน worker) —
P5-07 ทำให้ storage พร้อมแล้ว ชุดนี้คือด่านที่ตามมา

**กับดักที่ชุดนี้มีไว้จับ**: แอปมี `errorhandler(429)` ที่ render `login.html`
มาตั้งแต่ Phase 1 ถ้า 429 ของ API ไปตกที่ handler นั้น client จะได้ HTML กลับไป
แล้ว JSON parser พังด้วยข้อความที่ไม่เกี่ยวกับสาเหตุจริงเลย — เป็นอาการเดียวกับ
ที่ fuzz เคยจับได้ตอน Phase 3 (คำขอที่ตกตั้งแต่ชั้น routing ได้ HTML)
"""

import pytest

from app import limiter
from app.api.base import API_PREFIX
from tests.conftest import PASSWORD, TestConfig, _app_with_tables, _make_user, bearer_client
from tests.conftest import issue_token as _issue

TOO_MANY = 429
OK = 200


class ApiRateLimitTestConfig(TestConfig):
    """โควตาเล็กพอให้ชนได้ในไม่กี่คำขอ ส่วนโควตาของหน้า login ตั้งหลวมจนไม่มีผล

    ตั้งสองตัวให้ห่างกันมากโดยตั้งใจ — ถ้าตั้งใกล้กันจะแยกไม่ออกว่าที่โดนกัน
    เป็นเพราะโควตาของ API หรือของหน้า login (บทเรียนเดียวกับ
    `UsernameRateLimitTestConfig` ใน conftest)
    """

    RATELIMIT_ENABLED = True
    API_RATE_LIMIT = "3 per minute"
    LOGIN_RATE_LIMIT = "1000 per minute"
    LOGIN_USERNAME_RATE_LIMIT = "1000 per minute"


@pytest.fixture
def api_limited():
    """แอปที่เปิดโควตาของ API จริง พร้อมผู้ใช้สองคนที่มี token คนละใบ"""
    for app in _app_with_tables(ApiRateLimitTestConfig):
        with app.app_context():
            first = _make_user("tester")
            second = _make_user("intruder")
            limiter.reset()
        yield app, _issue(app, first), _issue(app, second)
        with app.app_context():
            limiter.reset()


def _spend_quota(client, times=3):
    for _ in range(times):
        assert client.get(f"{API_PREFIX}/todos").status_code == OK


def test_the_quota_runs_out(api_limited):
    app, token, _ = api_limited
    client = bearer_client(app, token)
    _spend_quota(client)
    assert client.get(f"{API_PREFIX}/todos").status_code == TOO_MANY


def test_running_out_answers_in_json_not_html(api_limited):
    """**กับดักหลักของงานนี้** — แอปมี errorhandler(429) ที่คืนหน้า login เป็น HTML

    ถ้า 429 ของ API ไปตกที่ handler นั้น client จะได้ HTML กลับไปแล้ว parser พัง
    ด้วยข้อความที่ไม่เกี่ยวกับสาเหตุจริง (อาการเดียวกับที่ fuzz จับได้ตอน Phase 3)
    """
    app, token, _ = api_limited
    client = bearer_client(app, token)
    _spend_quota(client)

    resp = client.get(f"{API_PREFIX}/todos")
    assert resp.status_code == TOO_MANY
    assert resp.get_json() is not None, "ได้ HTML กลับมา = ตกไปที่ handler ของหน้าเว็บ"
    assert resp.get_json()["error"]["code"] == "rate_limited"
    assert b"<html" not in resp.data.lower()


def test_the_refusal_says_when_to_come_back(api_limited):
    """`Retry-After` เป็นข้อบังคับของ RFC 9110 สำหรับ 429 — ไม่มีแล้ว client ต้องเดา"""
    app, token, _ = api_limited
    client = bearer_client(app, token)
    _spend_quota(client)
    assert "Retry-After" in client.get(f"{API_PREFIX}/todos").headers


def test_each_token_gets_its_own_quota(api_limited):
    """**นับต่อใบ token ไม่ใช่ต่อ IP** — เทสต์ยิงจาก IP เดียวกันทั้งหมด

    ถ้ากุญแจเป็น IP ใบที่สองจะโดนกันไปด้วยทั้งที่ยังไม่ได้ยิงอะไรเลย ซึ่งคือ
    อาการจริงของ client ที่อยู่หลัง NAT เดียวกัน — คนหนึ่งยิงถี่ อีกคนใช้ไม่ได้
    """
    app, first_token, second_token = api_limited
    _spend_quota(bearer_client(app, first_token))
    assert bearer_client(app, first_token).get(f"{API_PREFIX}/todos").status_code == TOO_MANY

    assert bearer_client(app, second_token).get(f"{API_PREFIX}/todos").status_code == OK


def test_a_request_without_a_token_still_costs_something(api_limited):
    """คำขอที่จะได้ 401 อยู่แล้วต้องไม่ยิงได้ไม่จำกัด

    ด่าน 401 ถูกกว่าการทำงานจริงก็จริง แต่ไม่ฟรี — ปล่อยไว้ก็เป็นช่องให้ยิงถล่ม
    โดยไม่ต้องมี token สักใบ
    """
    app, _, _ = api_limited
    anon = app.test_client()
    for _ in range(4):
        anon.get(f"{API_PREFIX}/todos")
    assert anon.get(f"{API_PREFIX}/todos").status_code == TOO_MANY


def test_the_html_site_keeps_its_own_page(api_limited):
    """หน้าเว็บต้องยังได้หน้า HTML ตามเดิม — โควตาของ API ไม่ใช่ของทั้งแอป"""
    app, _, _ = api_limited
    resp = app.test_client().post("/login", data={"username": "tester", "password": PASSWORD})
    assert resp.status_code != TOO_MANY, "โควตาของ API ไม่ควรไปกินโควตาของหน้า login"
