"""เทสต์ rate limit ที่หน้า login บนแอปที่เปิด RATELIMIT_ENABLED จริง

เทสต์อื่นปิด rate limit ไว้ ถ้าไม่มีไฟล์นี้จะไม่มีอะไรยืนยันว่ามันทำงาน
config ในเทสต์ตั้งไว้ 3 ครั้ง/นาที (ของจริง 5 ครั้ง/นาที)
"""

from tests.conftest import PASSWORD

WRONG = {"username": "tester", "password": "รหัสผิด"}
RIGHT = {"username": "tester", "password": PASSWORD}


def test_repeated_failures_get_blocked(ratelimit_app):
    client = ratelimit_app.test_client()
    # 3 ครั้งแรกยัง "ผิดรหัส" ปกติ
    for attempt in range(3):
        assert client.post("/login", data=WRONG).status_code == 401, (
            f"ครั้งที่ {attempt + 1} ควรเป็น 401 ไม่ใช่ 429"
        )
    # ครั้งที่ 4 โดนกัน
    assert client.post("/login", data=WRONG).status_code == 429


def test_blocked_response_shows_message(ratelimit_app):
    client = ratelimit_app.test_client()
    for _ in range(3):
        client.post("/login", data=WRONG)
    resp = client.post("/login", data=WRONG)
    assert resp.status_code == 429
    assert "ถี่เกินไป".encode() in resp.data


def test_correct_password_does_not_burn_quota(ratelimit_app):
    """login ที่ถูกต้องไม่ควรกินโควตา — คนใช้จริงจะได้ไม่โดนกันเอง"""
    client = ratelimit_app.test_client()
    for _ in range(5):
        assert client.post("/login", data=RIGHT).status_code == 302
        client.post("/logout")


def test_blocked_user_still_cannot_login_with_right_password(ratelimit_app):
    """โดนกันแล้วต้องกันจริง แม้จะพิมพ์รหัสถูกในครั้งถัดมา
    (ไม่งั้นคนเดารหัสจะรู้ทันทีว่ารหัสไหนถูก เพราะได้ 302 แทน 429)"""
    client = ratelimit_app.test_client()
    for _ in range(3):
        client.post("/login", data=WRONG)
    assert client.post("/login", data=RIGHT).status_code == 429


def test_get_login_page_not_limited(ratelimit_app):
    """จำกัดเฉพาะ POST การเปิดหน้า login เฉย ๆ ไม่ควรโดนกัน"""
    client = ratelimit_app.test_client()
    for _ in range(10):
        assert client.get("/login").status_code == 200


def test_limit_is_per_ip(ratelimit_app):
    """คนละ IP นับแยกกัน คนหนึ่งโดนกันไม่ลามไปอีกคน"""
    attacker = ratelimit_app.test_client()
    for _ in range(3):
        attacker.post("/login", data=WRONG, environ_base={"REMOTE_ADDR": "10.0.0.1"})
    assert (
        attacker.post(
            "/login", data=WRONG, environ_base={"REMOTE_ADDR": "10.0.0.1"}
        ).status_code
        == 429
    )

    victim = ratelimit_app.test_client()
    assert (
        victim.post(
            "/login", data=RIGHT, environ_base={"REMOTE_ADDR": "10.0.0.2"}
        ).status_code
        == 302
    ), "IP อื่นต้องไม่โดนหางเลข"
