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
    assert b"Too many sign-in attempts" in resp.data


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
        attacker.post("/login", data=WRONG, environ_base={"REMOTE_ADDR": "10.0.0.1"}).status_code
        == 429
    )

    victim = ratelimit_app.test_client()
    assert (
        victim.post("/login", data=RIGHT, environ_base={"REMOTE_ADDR": "10.0.0.2"}).status_code
        == 302
    ), "IP อื่นต้องไม่โดนหางเลข"


# ---------------------------------------------------------------- โควตาต่อชื่อผู้ใช้
# ปิดช่องที่ CLAUDE.md บันทึกไว้ตั้งแต่ต้นว่า "ยังไม่กันตาม username" (Phase 4)


def _try_from(app, ip, data):
    return app.test_client().post("/login", data=data, environ_base={"REMOTE_ADDR": ip})


def test_failures_add_up_per_username_across_different_ips(username_ratelimit_app):
    """คนเดารหัสที่เปลี่ยน IP ทุกครั้งต้องถูกกันได้ — โควตาต่อ IP ไม่มีทางจับได้เลย"""
    for attempt in range(3):
        assert _try_from(username_ratelimit_app, f"10.0.1.{attempt}", WRONG).status_code == 401

    assert _try_from(username_ratelimit_app, "10.0.1.99", WRONG).status_code == 429


def test_the_username_quota_does_not_spill_onto_other_accounts(username_ratelimit_app):
    """ยิงบัญชีหนึ่งจนเต็มโควตา ต้องไม่ทำให้อีกบัญชีใช้งานไม่ได้"""
    for attempt in range(4):
        _try_from(username_ratelimit_app, f"10.0.2.{attempt}", WRONG)

    other = {"username": "somchai", "password": PASSWORD}
    assert _try_from(username_ratelimit_app, "10.0.2.50", other).status_code == 302


def test_changing_letter_case_does_not_reset_the_username_quota(username_ratelimit_app):
    """`TESTER` กับ `tester` คือบัญชีเดียวกัน โควตาต้องใช้ถังเดียวกัน"""
    for attempt, name in enumerate(["tester", "TESTER", "Tester"]):
        assert (
            _try_from(
                username_ratelimit_app, f"10.0.3.{attempt}", {**WRONG, "username": name}
            ).status_code
            == 401
        )

    assert _try_from(username_ratelimit_app, "10.0.3.99", WRONG).status_code == 429


def test_a_correct_password_does_not_burn_the_username_quota(username_ratelimit_app):
    for attempt in range(5):
        assert _try_from(username_ratelimit_app, f"10.0.4.{attempt}", RIGHT).status_code == 302


def test_a_blocked_username_stays_blocked_even_with_the_right_password(username_ratelimit_app):
    """ไม่งั้นคนยิงจะรู้ทันทีว่าเจอรหัสที่ใช่ เพราะคำตอบต่างจากครั้งอื่น"""
    for attempt in range(3):
        _try_from(username_ratelimit_app, f"10.0.5.{attempt}", WRONG)
    assert _try_from(username_ratelimit_app, "10.0.5.99", RIGHT).status_code == 429


def test_an_unknown_username_is_throttled_the_same_way(username_ratelimit_app):
    """ต้องกันบัญชีที่ไม่มีอยู่จริงด้วย ไม่งั้นความต่างของคำตอบคือช่องให้ไล่เดาว่ามีใครบ้าง"""
    ghost = {"username": "ไม่มีคนนี้", "password": "อะไรก็ได้"}
    for attempt in range(3):
        assert _try_from(username_ratelimit_app, f"10.0.6.{attempt}", ghost).status_code == 401
    assert _try_from(username_ratelimit_app, "10.0.6.99", ghost).status_code == 429


def test_the_quota_key_never_carries_the_username_itself(app):
    """กุญแจนี้จะไปนอนอยู่ใน storage ของ limiter (วันหนึ่งคือ redis ที่ใช้ร่วมกัน)
    ชื่อผู้ใช้เป็นชั้น C2 จึงต้องถูก hash ก่อนเสมอ"""
    from app.auth import username_bucket

    with app.test_request_context("/login", method="POST", data={"username": "tester"}):
        key = username_bucket()
    assert "tester" not in key
    assert key.startswith("login-user:")
