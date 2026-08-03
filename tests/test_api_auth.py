"""ด่านของ `/api/v1` — ใครเข้าได้ ใครเข้าไม่ได้ (Phase 3, ADR 0017/0018)

ข้อที่อันตรายที่สุดของไฟล์นี้คือ **cookie ต้องเข้า API ไม่ได้**

API ถูกยกเว้น CSRF (ถูกต้อง เพราะ bearer token ไม่ถูกเบราว์เซอร์แนบเอง)
ถ้าด่านของ API ยอมรับตัวตนที่มาจาก session cookie ด้วย เว็บของคนอื่นจะสั่ง
เบราว์เซอร์ที่ login ค้างอยู่ให้ยิง POST มาลบงานได้ทันที — CSRF ที่ปิดไว้
ตั้งแต่ Phase 1 จะเปิดกลับมาโดยไม่มีอะไรฟ้อง เทสต์ในนี้ยิงด้วย cookie จริง
ที่ login สำเร็จแล้วเพื่อพิสูจน์ว่ายังโดนปฏิเสธ

อีกข้อคือ **ไม่มี endpoint ไหนหลุดด่าน** — ไล่จาก `url_map` จริง ไม่ใช่จาก
รายชื่อที่เขียนมือ เพราะ endpoint ที่เพิ่งเพิ่มเข้ามาคือตัวที่คนลืมง่ายที่สุด
"""

import pytest

from app import create_app, db
from app.api.base import API_PREFIX
from app.models import User
from app.services import tokens as tokens_service
from tests.conftest import (
    PASSWORD,
    CsrfTestConfig,
    bearer_client,
    issue_token,
)

UNAUTHORIZED = 401
OK = 200
CREATED = 201

# เสิร์ฟตัวสัญญาเอง ไม่ได้ให้ข้อมูลของใคร จึงเปิดอ่านได้โดยไม่ต้องมี token
PUBLIC_PATHS = {f"{API_PREFIX}/openapi.json"}


def _api_rules(app):
    """ทุก rule ที่อยู่ใต้ `/api/v1` พร้อม method ที่มันรับ (ข้ามของสาธารณะ)"""
    for rule in app.url_map.iter_rules():
        if not rule.rule.startswith(API_PREFIX) or rule.rule in PUBLIC_PATHS:
            continue
        for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
            # ใส่เลขให้ path parameter — ด่านต้องตัดก่อนถึงจะไปหาแถวอยู่แล้ว
            yield (
                method,
                rule.rule.replace("<int:todo_id>", "1")
                .replace("<int:category_id>", "1")
                .replace("<int:token_id>", "1"),
            )


def test_the_sweep_actually_finds_endpoints(app):
    """กันเทสต์ข้างล่างเขียวเพราะไม่เจอ endpoint ไหนเลย"""
    found = set(_api_rules(app))
    assert len(found) >= 10, found
    assert ("GET", f"{API_PREFIX}/todos") in found
    assert ("DELETE", f"{API_PREFIX}/tokens/1") in found


def test_every_api_endpoint_refuses_an_anonymous_request(app, anon_client):
    open_doors = [
        f"{method} {path}"
        for method, path in _api_rules(app)
        if anon_client.open(path, method=method).status_code != UNAUTHORIZED
    ]
    assert not open_doors, "endpoint ที่เข้าได้โดยไม่มี token:\n" + "\n".join(open_doors)


def test_every_api_endpoint_refuses_a_browser_session(app, client):
    """cookie ที่ login แล้วต้องยังเข้าไม่ได้ — ไม่งั้นเท่ากับเปิดรู CSRF"""
    still_open = [
        f"{method} {path}"
        for method, path in _api_rules(app)
        if client.open(path, method=method).status_code != UNAUTHORIZED
    ]
    assert not still_open, "endpoint ที่ยอมรับ session cookie:\n" + "\n".join(still_open)


def test_a_valid_token_gets_in(api_client):
    assert api_client.get(f"{API_PREFIX}/todos").status_code == OK


def test_the_refusal_says_which_scheme_to_use(anon_client):
    """401 ต้องมี WWW-Authenticate ตาม RFC 6750 ไม่งั้น client ต้องเดาเอง"""
    resp = anon_client.get(f"{API_PREFIX}/todos")
    assert resp.headers["WWW-Authenticate"].startswith("Bearer")
    assert resp.get_json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize(
    "header",
    [
        pytest.param("", id="ว่าง"),
        pytest.param("Bearer", id="ไม่มีค่าตามหลัง"),
        pytest.param("Bearer   ", id="ค่าเป็นช่องว่าง"),
        pytest.param("Basic dGVzdGVyOnB3", id="scheme ผิด"),
        pytest.param("Bearer tdl_1_ไม่ใช่ความลับจริง", id="ความลับผิด"),
        pytest.param("tdl_1_abc", id="ไม่มีชื่อ scheme"),
    ],
)
def test_a_malformed_authorization_header_is_refused(app, header):
    client = app.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = header
    assert client.get(f"{API_PREFIX}/todos").status_code == UNAUTHORIZED


def test_the_scheme_name_is_case_insensitive(app, api_token):
    """RFC 7235 บอกว่าชื่อ scheme ไม่สนตัวพิมพ์ — client บางตัวส่ง `bearer`"""
    client = app.test_client()
    client.environ_base["HTTP_AUTHORIZATION"] = f"bearer {api_token}"
    assert client.get(f"{API_PREFIX}/todos").status_code == OK


def test_a_revoked_token_stops_working(app, api_client, api_token, user_id):
    assert api_client.get(f"{API_PREFIX}/todos").status_code == OK
    with app.app_context():
        user = db.session.get(User, user_id)
        tokens_service.revoke(user, int(api_token.split("_")[1]))
    assert api_client.get(f"{API_PREFIX}/todos").status_code == UNAUTHORIZED


def test_a_token_of_a_deleted_user_stops_working(app, api_client, user_id):
    with app.app_context():
        db.session.get(User, user_id).soft_delete()
        db.session.commit()
    assert api_client.get(f"{API_PREFIX}/todos").status_code == UNAUTHORIZED


# ---------------------------------------------------------------- ขอบเขตของ token


def test_a_token_does_not_open_the_html_site(app, api_token):
    """token ใช้ได้เฉพาะใต้ `/api/` — หน้าเว็บมีด่าน CSRF ที่คิดบนสมมติฐานว่าตัวตนมาจาก cookie"""
    client = bearer_client(app, api_token)
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_html_errors_are_still_html(client):
    """flask-smorest ปกติจะยึด error handler ทั้งแอป — หน้าเว็บต้องไม่กลายเป็น JSON"""
    resp = client.get("/ไม่มีหน้านี้")
    assert resp.status_code == 404
    assert resp.get_json() is None
    assert b"<html" in resp.data.lower()


# ---------------------------------------------------------------- CSRF


@pytest.fixture
def csrf_api():
    """แอปที่เปิด CSRF จริง พร้อม user และ token หนึ่งใบ"""
    app = create_app(CsrfTestConfig)
    with app.app_context():
        db.create_all()
        user = User(username="tester")
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    return app, issue_token(app, user_id)


def test_the_api_does_not_ask_for_a_csrf_token(csrf_api):
    """POST ที่ไม่มี CSRF token ต้องผ่าน — ไม่งั้น client ที่ไม่ใช่เบราว์เซอร์ใช้ API ไม่ได้เลย

    ปลอดภัยเพราะตัวตนของ API มาจาก header ที่เบราว์เซอร์ไม่แนบให้เอง
    (คู่กับเทสต์ข้างบนที่พิสูจน์ว่า cookie อย่างเดียวเข้าไม่ได้)
    """
    app, token = csrf_api
    resp = bearer_client(app, token).post(f"{API_PREFIX}/todos", json={"title": "ล้างจาน"})
    assert resp.status_code == CREATED


def test_the_html_site_still_asks_for_a_csrf_token(csrf_api):
    """กันการยกเว้น CSRF หลุดไปทั้งแอปโดยไม่ตั้งใจ"""
    app, _ = csrf_api
    assert app.test_client().post("/login", data={"username": "tester"}).status_code == 400


# ---------------------------------------------------------------- ของที่ fuzz จับได้


def test_an_unknown_path_under_the_api_answers_in_json(api_client):
    """คำขอที่ตกตั้งแต่ชั้น routing ไม่มี blueprint ให้ handler เกาะ — ต้องดักที่ระดับแอป

    ก่อนแก้: client ที่พิมพ์ path ผิดได้หน้า HTML กลับไปแล้ว JSON parser พัง
    ด้วยข้อความที่ไม่เกี่ยวกับสาเหตุจริงเลย
    """
    resp = api_client.get(f"{API_PREFIX}/ไม่มีทางนี้")
    assert resp.status_code == 404
    assert resp.get_json()["error"]["code"] == "not_found"


def test_a_method_that_is_not_allowed_says_which_ones_are(api_client):
    """405 ต้องมี header `Allow` ตาม RFC 9110 — หายไปตอนเปลี่ยนมาสร้างคำตอบเอง"""
    resp = api_client.open(f"{API_PREFIX}/todos/1", method="TRACE")
    assert resp.status_code == 405
    assert "GET" in resp.headers["Allow"]
    assert resp.get_json()["error"]["code"] == "method_not_allowed"


def test_a_token_id_too_large_for_the_column_is_just_refused(app):
    """id ในตัว token เป็นตัวเลขที่คนนอกพิมพ์มาเองได้ — ต้องไม่ทำให้ระบบพัง 500"""
    client = bearer_client(app, f"tdl_{10**25}_ความลับปลอม")
    assert client.get(f"{API_PREFIX}/todos").status_code == UNAUTHORIZED
