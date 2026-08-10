"""app หลัง reverse proxy — ต้องเห็นไอพีของ *client* ไม่ใช่ของ proxy (P5-11)

เทสต์ในไฟล์นี้พิสูจน์สามอย่างที่พังเงียบทั้งหมดถ้าทำผิด:
ไม่เชื่อ header เมื่อไม่ได้สั่งให้เชื่อ · เชื่อแล้วต้องอ่านค่าที่ถูกตัว ·
และผลจริงที่ตามมา คือโควตา rate limit ต้องแยกกันต่อ client ไม่ใช่ก้อนเดียว
"""

from __future__ import annotations

import os

import pytest

from app import create_app, limiter
from tests.conftest import PASSWORD, TestConfig, _app_with_tables, _make_user

# ไอพีที่ werkzeug ตั้งให้ทุกคำขอของ test client — ในสถานการณ์ที่จำลองอยู่นี้
# มันคือ "ไอพีของ proxy" ซึ่งเป็นค่าที่แอปเห็นเหมือนกันหมดถ้าไม่แปลง header
SOCKET_PEER = "127.0.0.1"
CLIENT_IP = "203.0.113.7"


class ProxiedConfig(TestConfig):
    TRUSTED_PROXY_HOPS = 1


class ProxiedRateLimitConfig(ProxiedConfig):
    RATELIMIT_ENABLED = True
    LOGIN_RATE_LIMIT = "2 per minute"
    # โควตาต่อชื่อผู้ใช้ตั้งหลวมไว้ ไม่งั้นมันจะกันก่อนถึงมิติต่อไอพีที่กำลังวัด
    # (เหตุผลเดียวกับ UsernameRateLimitTestConfig ใน conftest แค่กลับด้าน)
    LOGIN_USERNAME_RATE_LIMIT = "1000 per minute"


def _with_echo_route(app):
    """เติม route ที่คืนสิ่งที่แอปเห็นจาก WSGI environ

    ต้องเป็น route จริง ไม่ใช่ `test_request_context` — `ProxyFix` เป็น WSGI
    middleware จึงทำงานก็ต่อเมื่อคำขอเดินผ่านชั้นนั้นจริง ๆ
    """

    @app.route("/whoami")
    def whoami():
        from flask import request

        return f"{request.remote_addr}|{request.scheme}"

    return app


@pytest.fixture
def plain_app():
    for app in _app_with_tables(TestConfig):
        yield _with_echo_route(app)


@pytest.fixture
def proxied_app():
    for app in _app_with_tables(ProxiedConfig):
        yield _with_echo_route(app)


def test_forwarded_headers_are_ignored_when_no_proxy_is_declared(plain_app):
    """ค่าเริ่มต้นต้องไม่เชื่อ `X-Forwarded-For` เลย

    ถ้าเชื่อโดยไม่มีใครล้างค่าให้ก่อน คนยิงจะปลอมไอพีใหม่ทุกคำขอแล้วหลุด
    rate limit ต่อไอพีทั้งหมด — แย่กว่าอาการ "ทุกคนใช้ก้อนเดียวกัน" เสียอีก
    """
    resp = plain_app.test_client().get(
        "/whoami",
        headers={"X-Forwarded-For": CLIENT_IP, "X-Forwarded-Proto": "https"},
    )
    assert resp.get_data(as_text=True) == f"{SOCKET_PEER}|http"


def test_declared_proxy_makes_the_client_ip_visible(proxied_app):
    resp = proxied_app.test_client().get(
        "/whoami",
        headers={"X-Forwarded-For": CLIENT_IP, "X-Forwarded-Proto": "https"},
    )
    # scheme ต้องเป็น https ด้วย ไม่งั้น HTTPS_ENABLED จะสั่ง redirect ไป https
    # ทั้งที่ผู้ใช้มาทาง https อยู่แล้ว = วนไม่รู้จบ (P5-12 พึ่งข้อนี้)
    assert resp.get_data(as_text=True) == f"{CLIENT_IP}|https"


def test_client_cannot_forge_an_ip_by_sending_its_own_forwarded_for(proxied_app):
    """proxy **ต่อท้าย** ค่าที่ตัวเองเห็น ค่าที่ client ปลอมจึงอยู่ทางซ้ายเสมอ

    นี่คือเหตุผลที่ config เป็น *จำนวนชั้น* ไม่ใช่ boolean — อ่านค่าซ้ายสุด
    (หรือประกาศชั้นเกินจำนวน proxy ที่มีจริง) เมื่อไหร่ ก็เท่ากับให้คนยิง
    ตั้งไอพีของตัวเองได้ตามใจ
    """
    resp = proxied_app.test_client().get(
        "/whoami",
        # "9.9.9.9" คือค่าที่ client แนบมาเอง ส่วน CLIENT_IP คือค่าที่ proxy ต่อท้าย
        headers={"X-Forwarded-For": f"9.9.9.9, {CLIENT_IP}"},
    )
    assert resp.get_data(as_text=True) == f"{CLIENT_IP}|http"


def test_negative_hop_count_is_refused():
    """ตั้งค่าผิดต้องพังตอน start ไม่ใช่เงียบไปแล้วไปโผล่ตอนมีคนยิงเข้ามา"""

    class Broken(TestConfig):
        TRUSTED_PROXY_HOPS = -1

    with pytest.raises(ValueError, match="TRUSTED_PROXY_HOPS"):
        create_app(Broken)


# --------------------------------------------------------------- ผลที่ตามมาจริง


@pytest.fixture
def proxied_ratelimit_app():
    """แอปที่เปิด rate limit จริง และรู้จัก proxy หนึ่งชั้น

    reset ทั้งก่อนและหลังด้วยเหตุผลเดียวกับ `ratelimit_app` ใน conftest
    (limiter เป็น singleton ระดับโมดูล storage จึงค้างข้ามเทสต์)
    """
    for app in _app_with_tables(ProxiedRateLimitConfig):
        with app.app_context():
            _make_user("tester")
            limiter.reset()
        yield app
        with app.app_context():
            limiter.reset()


def _fail_login_from(app, ip):
    return app.test_client().post(
        "/login",
        data={"username": "tester", "password": "รหัสผิด"},
        headers={"X-Forwarded-For": ip},
    )


def test_quota_is_counted_per_client_not_per_proxy(proxied_ratelimit_app):
    """สองเครื่องที่มาทาง proxy เดียวกัน ต้องมีโควตาคนละก้อน

    นี่คือเหตุผลทั้งหมดที่ P5-11 ต้องแตะเรื่อง proxy: ถ้าไม่แปลง header
    ทุกคำขอจะมี `remote_addr` เป็นไอพีของ proxy คนที่ไล่เดารหัสผ่านคนเดียว
    จะกินโควตาของผู้ใช้ทุกคนจนหมด แล้วทั้งระบบ login ไม่ได้
    """
    first = "198.51.100.1"
    second = "198.51.100.2"

    assert _fail_login_from(proxied_ratelimit_app, first).status_code == 401
    assert _fail_login_from(proxied_ratelimit_app, first).status_code == 401
    # เครื่องแรกหมดโควตา (2 per minute) แล้ว
    assert _fail_login_from(proxied_ratelimit_app, first).status_code == 429
    # เครื่องที่สองต้องยังยิงได้ — ถ้ากลายเป็น 429 แปลว่านับรวมเป็นก้อนเดียว
    assert _fail_login_from(proxied_ratelimit_app, second).status_code == 401


@pytest.fixture
def replicas(tmp_path):
    """แอปสองตัวที่ใช้ `SECRET_KEY` และฐานข้อมูลเดียวกัน = สอง replica

    **ฐานข้อมูลต้องเป็นไฟล์ ไม่ใช่ `:memory:`** — sqlite ในหน่วยความจำเป็นของ
    engine ตัวนั้นตัวเดียว แอปที่สองจะได้ฐานเปล่าคนละใบ แล้วเทสต์จะแดงด้วย
    `no such table` ซึ่งไม่เกี่ยวอะไรกับสิ่งที่เรากำลังพิสูจน์เลย
    (ถ้าตั้ง `TEST_DATABASE_URL` ไว้ ก็ใช้ตัวนั้นเพราะมันแชร์ได้อยู่แล้ว)
    """

    class SharedConfig(ProxiedConfig):
        SQLALCHEMY_DATABASE_URI = (
            os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{tmp_path}/shared.db"
        )

    for app in _app_with_tables(SharedConfig):
        with app.app_context():
            _make_user("tester")
        yield app, create_app(SharedConfig)


def test_session_cookie_from_one_replica_works_on_another(replicas):
    """คุกกี้ที่ replica หนึ่งออกให้ ต้องใช้กับอีก replica ได้ (DoD ของ P5-11)

    สถานะของ session อยู่ในคุกกี้ที่เซ็นไว้ทั้งหมด ไม่มีอะไรค้างอยู่ใน
    หน่วยความจำของ process — **ข้อนี้เป็นสิ่งที่ต้องพิสูจน์ ไม่ใช่สิ่งที่รู้อยู่แล้ว**
    วันไหนมีคนใส่ state ระดับ process เข้ามา (cache ของ preference, ตาราง
    session ในหน่วยความจำ) เทสต์นี้คือตัวที่จะจับได้
    """
    replica_a, replica_b = replicas

    client = replica_a.test_client()
    assert (
        client.post("/login", data={"username": "tester", "password": PASSWORD}).status_code == 302
    )
    cookie = client.get_cookie("session")
    assert cookie is not None

    other = replica_b.test_client()
    other.set_cookie("session", cookie.value)
    resp = other.get("/")
    assert resp.status_code == 200, "คุกกี้ของ replica อื่นต้องใช้ได้ ไม่ใช่เด้งไป login"
