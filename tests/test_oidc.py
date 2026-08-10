"""ปัจจัยหลักตัวที่สอง: OIDC เป็น plugin (Phase 5 · P5-13 — ดู ADR 0028)

สามเรื่องที่ต้องพิสูจน์แยกกัน:

1. **การตรวจ ID token ถูกต้องจริง** — เราเลือกไม่ตรวจลายเซ็นตาม OIDC Core
   §3.1.3.7 ข้อ 6 ซึ่งแปลว่า `iss`/`aud`/`exp`/`nonce` ที่เหลือ **ต้องตรวจครบ
   ทุกตัว** ตัวไหนหลุดคือรูที่ไม่มีลายเซ็นมาปิดให้อีกแล้ว
2. **การผูกบัญชีทำตามที่ ADR ตัดสิน** — `sub` เป็นเจ้าของความจริง, ผูกครั้งแรก
   ด้วยชื่อ, ไม่สร้างบัญชีให้เองถ้าไม่ได้สั่ง, group → role
3. **core ไม่รู้จักชื่อ `oidc`** — ถอนไดเรกทอรีทิ้งแล้วหน้า login ต้องกลับไป
   เป็นรหัสผ่านล้วนทันที

**ไม่ยิง IdP จริงในไฟล์นี้** — ปลอม `_fetch` เอาไว้ เพราะที่นี่ตรวจ *ตรรกะ*
ส่วนการคุยกับ Keycloak จริงเป็นงานของด่านใน CI (P5-13e) ซึ่งตอบคนละคำถาม
"""

import base64
import json
import time
from types import SimpleNamespace

import pytest

from app import db, plugins
from app.models import User
from app.services import sso
from app.services.errors import ServiceError
from tests.conftest import TestConfig, _app_with_tables, _make_user

OIDC_KEY = "auth/oidc"
ISSUER = "https://idp.example.test/realms/todolist"
CLIENT_ID = "todolist-test-client"

DISCOVERY = {
    "authorization_endpoint": f"{ISSUER}/protocol/openid-connect/auth",
    "token_endpoint": f"{ISSUER}/protocol/openid-connect/token",
}


class OidcConfig(TestConfig):
    """config ของ plugin อ่านผ่าน `current_app.config` ก่อน environment

    ตั้งที่นี่จึงไม่ต้องแตะ environment ของเครื่องที่รัน (หลักเดียวกับ
    `TEST_DATABASE_URL` ที่แยกจาก `DATABASE_URL`)
    """

    OIDC_ISSUER = ISSUER
    OIDC_CLIENT_ID = CLIENT_ID
    OIDC_CLIENT_SECRET = "test-client-secret-not-a-real-one"


def factor():
    return plugins.factor_module(plugins.find(OIDC_KEY))


def _fake_fetch_for(app):
    """IdP ปลอมที่ตอบ discovery และ token endpoint ตามที่เทสต์ตั้งไว้

    **รับ `app` เป็นพารามิเตอร์ ไม่ใช่ปิดทับตัวแปรของ fixture** — closure ที่
    จับตัวแปรของลูปไว้เป็นบั๊กที่รอเกิด (ruff B023) ต่อให้ลูปนี้จะวนรอบเดียวก็ตาม
    """

    def fake_fetch(url, data=None):
        if url.endswith("/.well-known/openid-configuration"):
            return dict(DISCOVERY)
        return {"id_token": app.config["_next_id_token"]}

    return fake_fetch


@pytest.fixture
def oidc_app(monkeypatch):
    """แอปที่ตั้ง config ของ IdP ไว้ครบ และ `_fetch` ถูกปลอม

    ปลอมที่ `_fetch` ตัวเดียว ไม่ใช่ที่ `_discovery` — เพราะอยากให้เส้นทาง
    ตรวจ scheme ของปลายทาง (`_checked`) ยังถูกเดินจริงในทุกเทสต์
    """
    for app in _app_with_tables(OidcConfig):
        monkeypatch.setattr(factor(), "_fetch", _fake_fetch_for(app))
        yield app


def id_token(**overrides):
    """ID token ปลอม — **ส่วนลายเซ็นเป็นขยะโดยตั้งใจ**

    เพราะเราไม่ได้ตรวจมัน (ADR 0028 ข้อ 4) ถ้าวันหนึ่งมีคนเพิ่มการตรวจลายเซ็น
    เทสต์ชุดนี้จะแดงทันที ซึ่งเป็นสัญญาณที่ถูกต้อง ไม่ใช่เทสต์ที่เขียนผิด
    """
    claims = {
        "iss": ISSUER,
        "aud": CLIENT_ID,
        "exp": time.time() + 300,
        "nonce": "nonce-value",
        "sub": "subject-abc",
        "preferred_username": "somchai",
    }
    claims.update(overrides)
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"header.{payload}.not-a-real-signature"


def pending(**overrides):
    data = {
        "state": "state-value",
        "nonce": "nonce-value",
        "verifier": "verifier-value",
        "redirect_uri": "https://todolist.example.test/login/sso/auth/oidc/callback",
    }
    data.update(overrides)
    return data


def finish(app, token=None, params=None, stash=None):
    """เรียก `finish()` แล้วคืน **ภาพถ่ายของผู้ใช้** ไม่ใช่ตัว object

    object ที่ผูกกับ session ตายไปพร้อม context ที่สร้างมัน การอ่าน attribute
    ทีหลังจะได้ `DetachedInstanceError` ซึ่งไม่เกี่ยวอะไรกับสิ่งที่เทสต์ตรวจเลย
    (ข้อจำกัดเดียวกับที่ CLAUDE.md บันทึกไว้เรื่อง fixture ที่ yield object)
    """
    app.config["_next_id_token"] = token if token is not None else id_token()
    with app.test_request_context():
        user = factor().finish(
            params or {"state": "state-value", "code": "the-code"}, stash or pending()
        )
        return SimpleNamespace(id=user.id, role=user.role, username=user.username)


# ------------------------------------------------------- 1. การตรวจ ID token


def test_begin_asks_for_the_code_flow_with_pkce(oidc_app):
    with oidc_app.test_request_context():
        target, stash = factor().begin("https://todolist.example.test/cb")
    assert target.startswith(DISCOVERY["authorization_endpoint"])
    assert "response_type=code" in target
    assert "code_challenge_method=S256" in target
    # สามค่านี้ต้องไม่ซ้ำกันเอง — ค่าเดียวใช้สามหน้าที่คือการยกเลิกสองในสาม
    assert len({stash["state"], stash["nonce"], stash["verifier"]}) == 3


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"iss": "https://evil.example.test"}, "sso_wrong_issuer"),
        ({"aud": "someone-elses-client"}, "sso_wrong_audience"),
        ({"exp": time.time() - 3600}, "sso_token_expired"),
        ({"nonce": "a-different-nonce"}, "sso_nonce_mismatch"),
        ({"sub": ""}, "sso_no_subject"),
    ],
)
def test_id_token_claims_are_all_checked(oidc_app, overrides, code):
    """ทุก claim ที่เหลือหลังเลิกตรวจลายเซ็น ต้องถูกตรวจจริง

    ตัวไหนหลุด = รูที่ไม่มีลายเซ็นมาปิดให้อีกแล้ว (ADR 0028 ข้อ 4)
    """
    with pytest.raises(ServiceError) as caught:
        finish(oidc_app, token=id_token(**overrides))
    assert caught.value.code == code


def test_a_token_that_is_not_a_jwt_is_refused(oidc_app):
    with pytest.raises(ServiceError) as caught:
        finish(oidc_app, token="not-a-jwt-at-all")
    assert caught.value.code == "sso_bad_token"


def test_state_that_does_not_match_is_refused(oidc_app):
    with pytest.raises(ServiceError) as caught:
        finish(oidc_app, params={"state": "someone-elses-state", "code": "x"})
    assert caught.value.code == "sso_state_mismatch"


def test_provider_error_is_reported_as_cancelled(oidc_app):
    with pytest.raises(ServiceError) as caught:
        finish(oidc_app, params={"error": "access_denied"})
    assert caught.value.code == "sso_denied"


def test_endpoints_from_the_discovery_document_must_be_https(oidc_app, monkeypatch):
    """ปลายทางมาจาก IdP ไม่ใช่จาก config ของเรา — เชื่อดิบ ๆ ไม่ได้"""

    def evil_fetch(url, data=None):
        if url.endswith("/.well-known/openid-configuration"):
            return {
                "authorization_endpoint": "file:///etc/passwd",
                "token_endpoint": "http://insecure.example.test/token",
            }
        return {"id_token": id_token()}

    monkeypatch.setattr(factor(), "_fetch", evil_fetch)
    with oidc_app.test_request_context(), pytest.raises(ServiceError) as caught:
        factor().begin("https://todolist.example.test/cb")
    assert caught.value.code == "sso_bad_endpoint"


def test_a_plain_http_issuer_is_refused_unless_opted_in(oidc_app):
    oidc_app.config["OIDC_ISSUER"] = "http://idp.example.test"
    with oidc_app.test_request_context(), pytest.raises(ServiceError) as caught:
        factor().begin("https://todolist.example.test/cb")
    assert caught.value.code == "sso_insecure_issuer"


# ------------------------------------------------------------ 2. การผูกบัญชี


def test_first_login_links_by_username_then_uses_sub(oidc_app):
    with oidc_app.app_context():
        user_id = _make_user("somchai")

    user = finish(oidc_app)
    assert user.id == user_id

    # ครั้งที่สอง IdP เปลี่ยนชื่อผู้ใช้ไปแล้ว แต่ `sub` เดิม → ต้องได้คนเดิม
    again = finish(oidc_app, token=id_token(preferred_username="someone-else"))
    assert again.id == user_id


def test_unknown_user_is_refused_when_auto_create_is_off(oidc_app):
    """ค่าเริ่มต้นคือผู้ดูแลสร้างบัญชีไว้ก่อน (ADR 0028 ข้อ 3)"""
    with pytest.raises(ServiceError) as caught:
        finish(oidc_app)
    assert caught.value.code == "sso_no_account"


def test_auto_create_makes_an_account_without_a_password(oidc_app):
    oidc_app.config["OIDC_AUTO_CREATE"] = "1"
    user = finish(oidc_app)
    with oidc_app.app_context():
        created = db.session.get(User, user.id)
        assert created.username == "somchai"
        # ยังไม่มีรหัสผ่านของที่นี่จนกว่าผู้ดูแลจะตั้งให้ — ใช้กลไก
        # "credential ที่ใช้ไม่ได้" ตัวเดิมของ `disable_password()`
        assert not created.check_password("")
        assert not created.check_password("somchai")


def test_group_becomes_role_in_both_directions(oidc_app):
    oidc_app.config["OIDC_AUTO_CREATE"] = "1"
    oidc_app.config["OIDC_ADMIN_GROUP"] = "todolist-admins"

    promoted = finish(oidc_app, token=id_token(groups=["todolist-admins"]))
    assert promoted.role == "admin"

    # ถอดออกจากกลุ่มที่ IdP แล้วต้องมีผลจริงในรอบถัดไป ไม่ใช่ค้างเป็น admin
    demoted = finish(oidc_app, token=id_token(groups=["everyone"]))
    assert demoted.role == "user"


def test_role_is_untouched_when_no_group_is_configured(oidc_app):
    """ไม่ได้ตั้งกลุ่มไว้ = ไม่แตะ `role` เลย ไม่ใช่ตั้งเป็น `user`

    ผู้ดูแลที่ตั้งบทบาทเองด้วย `flask set-role` ต้องไม่ถูกลดสิทธิ์เพราะ
    IdP ไม่ได้ส่ง claim ที่เราไม่ได้ขอ (ADR 0028 ข้อ 5)
    """
    with oidc_app.app_context():
        user_id = _make_user("somchai")
        db.session.get(User, user_id).role = "admin"
        db.session.commit()

    user = finish(oidc_app)
    assert user.role == "admin"


# --------------------------------------------- 3. core ไม่รู้จักชื่อ plugin นี้


def test_login_page_offers_the_provider_when_it_is_installed(oidc_app):
    with oidc_app.app_context():
        assert [plugin.key for plugin in sso.available()] == [OIDC_KEY]
    page = oidc_app.test_client().get("/login")
    assert b"/login/sso/auth/oidc" in page.data


def test_removing_the_plugin_returns_the_login_page_to_passwords_only(oidc_app):
    """ถอนแล้วต้องกลับไปเป็นรหัสผ่านล้วน ไม่ใช่หน้าที่พัง (สัญญาตั้งแต่ ADR 0006)"""
    with oidc_app.app_context():
        plugins.uninstall(plugins.find(OIDC_KEY))
        assert sso.available() == []
    page = oidc_app.test_client().get("/login")
    assert page.status_code == 200
    assert b"/login/sso/" not in page.data
    # ฟอร์มรหัสผ่านยังอยู่ครบ (ADR 0028 ข้อ 7)
    assert b'name="password"' in page.data


def test_callback_without_a_pending_handshake_is_refused(oidc_app):
    """ยิง callback ตรง ๆ โดยไม่ได้เริ่มจากที่นี่ = ปฏิเสธ"""
    response = oidc_app.test_client().get(
        f"/login/sso/{OIDC_KEY}/callback?state=made-up&code=made-up"
    )
    assert response.status_code == 401


def test_a_pending_handshake_is_spent_even_when_the_attempt_fails(oidc_app):
    """ของฝากใน session ใช้ได้ครั้งเดียว **ไม่ว่าจะสำเร็จหรือไม่**

    ถ้า `pop` เกิดหลังการตรวจ (หรือเป็น `get`) คนที่ยิง callback ผิด ๆ ถูก ๆ
    จะลองใหม่กับ `state` ชุดเดิมได้ไม่จำกัด — ซึ่งคือการยกเลิกประโยชน์ของ
    `state` ทั้งหมด เทสต์นี้จับด้วยการยิงพลาดก่อนแล้วยิงถูกทีหลัง
    """
    # **ต้องมีบัญชีอยู่จริง** ไม่งั้นครั้งที่สองจะล้มด้วย "ไม่มีบัญชีชื่อนี้"
    # แล้วเทสต์เขียวโดยไม่ได้ทดสอบเรื่องของฝากเลย (เจอตอน mutation test:
    # เปลี่ยน `pop` เป็น `get` แล้วยังเขียว จึงต้องมาแก้เทสต์)
    with oidc_app.app_context():
        _make_user("somchai")

    client = oidc_app.test_client()
    with client.session_transaction() as stored:
        stored["_sso_pending"] = pending()
        stored["_sso_provider"] = OIDC_KEY

    wrong = client.get(f"/login/sso/{OIDC_KEY}/callback?state=wrong&code=x")
    assert wrong.status_code == 401

    oidc_app.config["_next_id_token"] = id_token()
    right = client.get(f"/login/sso/{OIDC_KEY}/callback?state=state-value&code=the-code")
    assert right.status_code == 401, "state ชุดเดิมต้องใช้ซ้ำไม่ได้แม้ครั้งก่อนจะล้มเหลว"
