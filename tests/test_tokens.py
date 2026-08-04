"""personal access token — กุญแจของเครื่อง (Phase 3, ADR 0017)

token เป็นความลับที่อายุยาวกว่า session cookie มาก และถูกแปะไว้ในสคริปต์กับ
ตัวแปรแวดล้อมของคนอื่น ข้ออ้างที่ต้องพิสูจน์จึงมีสี่ข้อ:

1. **ความลับจริงไม่ถูกเก็บ** — ฐานข้อมูลมีแต่ hash ค่าที่หลุดออกไปเอาไปใช้ต่อไม่ได้
2. **เพิกถอนแล้วตายทันที** ไม่ใช่แค่ถูกซ่อนจากหน้าจอ
3. **ใบของคนอื่นเท่ากับไม่มีอยู่** — ไม่บอกด้วยซ้ำว่ามีใบนั้นจริง (ADR 0004)
4. **ปฏิเสธแล้วไม่บอกเหตุผล** ทุกกรณีที่ไม่ผ่านให้ผลลัพธ์เดียวกันหมด

ข้อ 1 กับ 2 พังเงียบที่สุด เพราะระบบยัง "ทำงานได้" ทั้งที่ความลับรั่วหรือ
ใบที่เพิกถอนแล้วยังเปิดประตูได้

app context อยู่ที่ fixture ตัวเทสต์ห้ามเปิดซ้อน (เหตุผลเต็มอยู่ใน
`tests/test_services.py`) — session ที่ต่างกันทำให้การแก้ค่าบน `owner` หายเงียบ
"""

import hashlib
import re
from datetime import timedelta

import pytest

from app import db, tz
from app.audit import AuditEntry
from app.models import ApiToken, User
from app.purge import purge_expired
from app.services import NotFoundError, ValidationError
from app.services import tokens as tokens_service
from app.soft_delete import INCLUDE_DELETED
from tests.conftest import PASSWORD, bearer_client, issue_token


@pytest.fixture
def owner(app):
    with app.app_context():
        person = User(username="tokenowner")
        person.set_password(PASSWORD)
        db.session.add(person)
        db.session.commit()
        yield person


@pytest.fixture
def stranger(app, owner):
    """คนอื่นที่ใช้ session เดียวกับ `owner` — ต้องมาหลัง owner เพื่อไม่เปิด context ซ้อน"""
    person = User(username="tokenstranger")
    person.set_password(PASSWORD)
    db.session.add(person)
    db.session.commit()
    return person


def _id_of(raw):
    """เลขแถวที่ฝังอยู่ในตัว token"""
    return int(raw.split("_")[1])


def _secret_of(raw):
    return raw.split("_", 2)[2]


def _row(token_id):
    """อ่านแถวโดยไม่สนตัวกรอง soft delete — ใช้ตรวจของที่เพิ่งเพิกถอนไป"""
    return (
        db.session.query(ApiToken)
        .execution_options(**INCLUDE_DELETED)
        .filter(ApiToken.id == token_id)
        .one_or_none()
    )


# ---------------------------------------------------------------- รูปแบบและการเก็บ


def test_the_secret_is_never_stored(owner):
    """ฐานข้อมูลต้องไม่มีชิ้นส่วนใดของความลับเลย มีแค่ hash ของมัน"""
    raw = tokens_service.issue(owner, "laptop")
    secret = _secret_of(raw)
    db.session.remove()

    stored = db.session.get(ApiToken, _id_of(raw))
    assert stored.token_hash != secret
    assert secret not in stored.token_hash
    assert stored.token_hash == hashlib.sha256(secret.encode()).hexdigest()


def test_the_token_carries_its_row_id(owner):
    """`tdl_<id>_<ความลับ>` — id ทำให้หาแถวได้ตรง ๆ ไม่ต้องไล่เทียบทั้งตาราง"""
    raw = tokens_service.issue(owner, "laptop")
    prefix, token_id, secret = raw.split("_", 2)
    assert prefix == tokens_service.TOKEN_PREFIX
    assert db.session.get(ApiToken, int(token_id)) is not None
    # 32 ไบต์ที่ผ่าน base64url ยาวกว่า 40 ตัวเสมอ — กันการลดขนาดความลับโดยไม่ตั้งใจ
    assert len(secret) > 40


def test_two_tokens_never_share_a_secret(owner):
    first = tokens_service.issue(owner, "laptop")
    second = tokens_service.issue(owner, "phone")
    assert _secret_of(first) != _secret_of(second)


def test_a_new_token_expires_by_default(owner):
    """ค่าเริ่มต้นต้องมีวันหมดอายุ — ใบที่ไม่มีวันหมดต้องขอเป็นพิเศษ"""
    token = tokens_service.get_token(owner, _id_of(tokens_service.issue(owner, "laptop")))
    assert token.expires_at is not None
    expected = tz.now_utc() + timedelta(days=tokens_service.DEFAULT_EXPIRY_DAYS)
    assert abs((token.expires_at - expected).total_seconds()) < 60


def test_zero_days_means_never_expires(owner):
    token = tokens_service.get_token(
        owner, _id_of(tokens_service.issue(owner, "s", expires_days=0))
    )
    assert token.expires_at is None
    assert not token.is_expired


# ---------------------------------------------------------------- การตรวจสอบ


def test_a_fresh_token_authenticates(owner):
    raw = tokens_service.issue(owner, "laptop")
    db.session.remove()

    token = tokens_service.authenticate(raw)
    assert token is not None
    assert token.user.username == "tokenowner"


@pytest.mark.parametrize(
    "mangle",
    [
        pytest.param(lambda raw: raw[:-1] + ("A" if raw[-1] != "A" else "B"), id="แก้ตัวสุดท้าย"),
        pytest.param(lambda raw: raw.replace("tdl_", "xyz_", 1), id="prefix-ผิด"),
        pytest.param(_secret_of, id="ไม่มี-prefix-กับ-id"),
        pytest.param(lambda raw: f"tdl_abc_{_secret_of(raw)}", id="id-ไม่ใช่ตัวเลข"),
        pytest.param(lambda raw: f"tdl_999999_{_secret_of(raw)}", id="id-ที่ไม่มีอยู่"),
        pytest.param(lambda raw: f"tdl_{_id_of(raw)}", id="ไม่มีส่วนความลับ"),
        pytest.param(lambda _: "", id="สตริงว่าง"),
        pytest.param(lambda _: None, id="ไม่ได้ส่งมา"),
    ],
)
def test_a_bad_token_is_refused(owner, mangle):
    """ทุกกรณีที่ผิดต้องได้ None เหมือนกันหมด ไม่มีข้อความบอกว่าผิดตรงไหน"""
    raw = tokens_service.issue(owner, "laptop")
    db.session.remove()

    assert tokens_service.authenticate(mangle(raw)) is None


def test_a_secret_from_one_row_does_not_open_another(owner):
    """ประกอบ id ของใบหนึ่งเข้ากับความลับของอีกใบต้องไม่ผ่าน"""
    first = tokens_service.issue(owner, "laptop")
    second = tokens_service.issue(owner, "phone")
    db.session.remove()

    assert tokens_service.authenticate(f"tdl_{_id_of(first)}_{_secret_of(second)}") is None


def test_an_expired_token_is_refused(owner):
    raw = tokens_service.issue(owner, "laptop")
    db.session.get(ApiToken, _id_of(raw)).expires_at = tz.now_utc() - timedelta(seconds=1)
    db.session.commit()
    db.session.remove()

    assert tokens_service.authenticate(raw) is None


def test_a_token_that_expires_later_today_still_works(owner):
    """เส้นแบ่งอยู่ที่ "เลยเวลาแล้ว" ไม่ใช่ "มีวันหมดอายุ" """
    raw = tokens_service.issue(owner, "laptop")
    db.session.get(ApiToken, _id_of(raw)).expires_at = tz.now_utc() + timedelta(seconds=30)
    db.session.commit()
    db.session.remove()

    assert tokens_service.authenticate(raw) is not None


def test_a_revoked_token_is_refused(owner):
    raw = tokens_service.issue(owner, "laptop")
    tokens_service.revoke(owner, _id_of(raw))
    db.session.remove()

    assert tokens_service.authenticate(raw) is None


def test_revoking_wipes_the_hash_not_just_hides_the_row(owner):
    """กู้แถวคืนมาแล้วต้องยังใช้ไม่ได้ — เพิกถอนคือ "ตาย" ไม่ใช่ "ซ่อน" """
    raw = tokens_service.issue(owner, "laptop")
    tokens_service.revoke(owner, _id_of(raw))
    db.session.remove()

    restored = _row(_id_of(raw))
    assert restored.token_hash != hashlib.sha256(_secret_of(raw).encode()).hexdigest()
    restored.deleted_at = None  # แกล้งกู้คืนแถวที่ถูกซ่อนไว้
    db.session.commit()
    assert tokens_service.authenticate(raw) is None


def test_a_token_of_a_deleted_user_is_refused(owner):
    """ปิดบัญชีแล้วกุญแจที่แจกไว้ต้องเปิดประตูไม่ได้อีก"""
    raw = tokens_service.issue(owner, "laptop")
    owner.soft_delete()
    db.session.commit()
    db.session.remove()

    assert tokens_service.authenticate(raw) is None


# ---------------------------------------------------------------- ความเป็นเจ้าของ


def test_listing_shows_only_your_own_tokens(owner, stranger):
    tokens_service.issue(owner, "laptop")
    tokens_service.issue(stranger, "their laptop")
    assert [t.name for t in tokens_service.list_tokens(owner)] == ["laptop"]


def test_listing_hides_revoked_tokens(owner):
    tokens_service.issue(owner, "keep")
    drop = tokens_service.issue(owner, "drop")
    tokens_service.revoke(owner, _id_of(drop))
    assert [t.name for t in tokens_service.list_tokens(owner)] == ["keep"]


def test_listing_puts_the_newest_first(owner):
    tokens_service.issue(owner, "แรก")
    tokens_service.issue(owner, "หลัง")
    assert [t.name for t in tokens_service.list_tokens(owner)] == ["หลัง", "แรก"]


def test_someone_elses_token_looks_like_it_does_not_exist(owner, stranger):
    """ตอบ NotFound ไม่ใช่ Forbidden — ไม่ให้รู้ว่า id นั้นมีจริง (ADR 0004)"""
    raw = tokens_service.issue(stranger, "their laptop")
    with pytest.raises(NotFoundError):
        tokens_service.get_token(owner, _id_of(raw))
    with pytest.raises(NotFoundError):
        tokens_service.revoke(owner, _id_of(raw))


def test_revoking_someone_elses_token_leaves_it_working(owner, stranger):
    raw = tokens_service.issue(stranger, "their laptop")
    with pytest.raises(NotFoundError):
        tokens_service.revoke(owner, _id_of(raw))
    db.session.remove()

    assert tokens_service.authenticate(raw) is not None


# ---------------------------------------------------------------- การตรวจค่าที่รับมา


@pytest.mark.parametrize("name", ["", "   ", None])
def test_a_token_needs_a_name(owner, name):
    with pytest.raises(ValidationError) as error:
        tokens_service.issue(owner, name)
    assert error.value.code == "name_required"


def test_a_name_that_is_too_long_is_refused(owner):
    """ยาวเกินคอลัมน์ต้องถูกปฏิเสธก่อน ไม่ใช่ปล่อยให้ DB ตัดทิ้งเงียบ ๆ"""
    with pytest.raises(ValidationError) as error:
        tokens_service.issue(owner, "ก" * (tokens_service.NAME_MAX_LENGTH + 1))
    assert error.value.code == "name_too_long"


def test_a_name_of_exactly_the_limit_is_accepted(owner):
    name = "ก" * tokens_service.NAME_MAX_LENGTH
    assert tokens_service.get_token(owner, _id_of(tokens_service.issue(owner, name))).name == name


def test_a_name_is_trimmed(owner):
    raw = tokens_service.issue(owner, "  laptop  ")
    assert tokens_service.get_token(owner, _id_of(raw)).name == "laptop"


def test_a_negative_expiry_is_refused(owner):
    with pytest.raises(ValidationError) as error:
        tokens_service.issue(owner, "laptop", expires_days=-1)
    assert error.value.code == "expiry_invalid"


def test_a_refused_token_is_not_written(owner):
    """ตรวจค่าให้เสร็จก่อนแตะฐานข้อมูล — ไม่ทิ้งแถวขยะไว้เมื่อ validation ไม่ผ่าน"""
    with pytest.raises(ValidationError):
        tokens_service.issue(owner, "")
    db.session.remove()

    assert db.session.query(ApiToken).execution_options(**INCLUDE_DELETED).count() == 0


# ---------------------------------------------------------------- ปลายทางอื่นในระบบ


def test_deleting_a_user_kills_their_tokens(app, owner):
    """`delete-user` ต้องปิดกุญแจด้วย ไม่ใช่แค่ซ่อนบัญชี"""
    raw = tokens_service.issue(owner, "laptop")
    app.test_cli_runner().invoke(args=["delete-user", "tokenowner", "--yes"])
    db.session.remove()

    assert tokens_service.authenticate(raw) is None
    assert _row(_id_of(raw)).token_hash != hashlib.sha256(_secret_of(raw).encode()).hexdigest()


def test_purge_removes_tokens_that_are_past_retention(owner):
    raw = tokens_service.issue(owner, "laptop")
    tokens_service.revoke(owner, _id_of(raw))
    _row(_id_of(raw)).deleted_at = tz.now_utc() - timedelta(days=31)
    db.session.commit()

    assert purge_expired().api_tokens == 1
    assert _row(_id_of(raw)) is None


def test_purge_leaves_a_token_that_is_still_within_retention(owner):
    raw = tokens_service.issue(owner, "laptop")
    tokens_service.revoke(owner, _id_of(raw))

    assert purge_expired().api_tokens == 0
    assert _row(_id_of(raw)) is not None


def test_a_token_secret_never_reaches_the_audit_table(owner):
    """`token_hash` เป็นชั้น C1 — แม้แต่ตัว hash ก็ห้ามออกไป (ดู ADR 0014)"""
    raw = tokens_service.issue(owner, "laptop")
    rows = db.session.query(AuditEntry).all()
    changes = "\n".join(row.changes for row in rows)

    assert _secret_of(raw) not in changes
    assert hashlib.sha256(_secret_of(raw).encode()).hexdigest() not in changes
    # ไม่พอที่จะดูว่า "ค่าไม่โผล่" เฉย ๆ เพราะคอลัมน์ที่ตกไปเป็นชั้น C2/C3 จะถูก
    # เก็บเป็น HMAC ซึ่งก็ไม่โผล่เหมือนกัน — ต้องเช็คว่าถูกจัดเป็นความลับจริง
    insert = next(row for row in rows if row.event == "api_token.insert")
    assert insert.payload["token_hash"] == {"changed": True}


def test_revoking_is_audited_as_a_delete(owner):
    """soft delete ต้องถูกบันทึกตามความหมาย ไม่ใช่ตามคำสั่ง SQL ที่ใช้"""
    tokens_service.revoke(owner, _id_of(tokens_service.issue(owner, "laptop")))
    assert "api_token.delete" in [row.event for row in db.session.query(AuditEntry).all()]


# ---------------------------------------------------------------- CLI


def test_token_create_prints_the_secret_once(app, owner):
    result = app.test_cli_runner().invoke(args=["token-create", "tokenowner", "--name", "laptop"])
    assert result.exit_code == 0
    raw = result.output.strip().splitlines()[-1]
    db.session.remove()

    assert tokens_service.authenticate(raw) is not None


def test_token_create_refuses_an_unknown_user(app):
    result = app.test_cli_runner().invoke(args=["token-create", "ไม่มีคนนี้", "--name", "x"])
    assert result.exit_code != 0
    assert "No user named" in result.output


def test_token_create_reports_a_bad_name(app, owner):
    result = app.test_cli_runner().invoke(args=["token-create", "tokenowner", "--name", " "])
    assert result.exit_code != 0
    db.session.remove()

    assert db.session.query(ApiToken).count() == 0


def test_token_list_shows_state_and_expiry(app, owner):
    tokens_service.issue(owner, "laptop", expires_days=0)
    result = app.test_cli_runner().invoke(args=["token-list", "tokenowner"])
    assert "laptop" in result.output
    assert "active" in result.output
    assert "never" in result.output


def test_token_list_on_a_user_without_tokens(app, owner):
    result = app.test_cli_runner().invoke(args=["token-list", "tokenowner"])
    assert result.exit_code == 0
    assert "No tokens" in result.output


def test_token_revoke_kills_the_token(app, owner):
    raw = tokens_service.issue(owner, "laptop")
    result = app.test_cli_runner().invoke(args=["token-revoke", "tokenowner", str(_id_of(raw))])
    assert result.exit_code == 0
    db.session.remove()

    assert tokens_service.authenticate(raw) is None


def test_token_revoke_refuses_someone_elses_token(app, owner, stranger):
    raw = tokens_service.issue(stranger, "their laptop")
    result = app.test_cli_runner().invoke(args=["token-revoke", "tokenowner", str(_id_of(raw))])
    assert result.exit_code != 0
    db.session.remove()

    assert tokens_service.authenticate(raw) is not None


# ---------------------------------------------------------------- หน้าเว็บ (Phase 4)
# ADR 0017 เลื่อนหน้านี้ไว้เพราะ "ต้องคิดเรื่อง re-authentication ก่อน"
# คำตอบ: ออกใบใหม่ต้องกรอกรหัสผ่านซ้ำ ส่วนเพิกถอนไม่ต้อง (ทำให้ปลอดภัยขึ้นเสมอ)
#
# เทสต์กลุ่มนี้ยิง HTTP จึง **ห้ามใช้ fixture `owner` ที่เปิด app context ค้างไว้**
# (ดูเหตุผลใน CLAUDE.md — `g` จะถูกใช้ร่วมกันข้าม request)


def _web_client(app, username="tester"):
    client = app.test_client()
    resp = client.post("/login", data={"username": username, "password": PASSWORD})
    assert resp.status_code == 302
    return client


def _secret_from(body):
    """ดึงสตริง token ออกจากหน้าที่แสดงมันครั้งเดียว"""
    match = re.search(r"tdl_\d+_[A-Za-z0-9_-]+", body)
    assert match, "หน้าที่ออกใบต้องแสดงความลับให้เห็น"
    return match.group(0)


def test_the_settings_page_lists_tokens(app, user_id):
    issue_token(app, user_id, name="เครื่องที่ทำงาน")
    body = _web_client(app).get("/settings").get_data(as_text=True)
    assert "เครื่องที่ทำงาน" in body


def test_creating_a_token_needs_the_password_again(app, user_id):
    """session ที่ถูกยึดต้องออกกุญแจใบใหม่ให้ตัวเองไม่ได้"""
    resp = _web_client(app).post(
        "/settings/tokens", data={"name": "ของคนแปลกหน้า", "password": "ผิด"}
    )
    assert resp.status_code == 302

    with app.app_context():
        assert tokens_service.list_tokens(db.session.get(User, user_id)) == []


def test_a_created_token_is_shown_once_and_works(app, user_id):
    client = _web_client(app)
    resp = client.post(
        "/settings/tokens",
        data={"name": "สคริปต์สำรองข้อมูล", "expires_days": "30", "password": PASSWORD},
    )
    assert resp.status_code == 200
    secret = _secret_from(resp.get_data(as_text=True))

    assert bearer_client(app, secret).get("/api/v1/todos").status_code == 200
    # **ห้ามส่งความลับผ่าน flash** — คุกกี้ session ถูกเซ็นแต่ไม่ได้เข้ารหัส
    assert secret not in (client.get_cookie("session").value or "")


def test_an_unreadable_expiry_falls_back_to_the_safer_default(app, user_id):
    """ตกกลับไปทาง "มีวันหมดอายุ" เสมอ — ใบที่ไม่มีวันหมดต้องเป็นสิ่งที่ตั้งใจขอ"""
    _web_client(app).post(
        "/settings/tokens", data={"name": "พิมพ์เลขผิด", "expires_days": "ก", "password": PASSWORD}
    )
    with app.app_context():
        token = tokens_service.list_tokens(db.session.get(User, user_id))[0]
        assert token.expires_at is not None


def test_revoking_from_the_web_kills_the_token(app, user_id):
    secret = issue_token(app, user_id, name="ใบที่จะถูกเพิกถอน")
    api = bearer_client(app, secret)
    assert api.get("/api/v1/todos").status_code == 200

    with app.app_context():
        token_id = tokens_service.list_tokens(db.session.get(User, user_id))[0].id

    assert _web_client(app).post(f"/settings/tokens/{token_id}/revoke").status_code == 302
    assert api.get("/api/v1/todos").status_code == 401


def test_a_rejected_token_name_comes_back_as_a_message(app, user_id):
    """ข้อความจาก service ต้องถึงผู้ใช้ ไม่ใช่กลายเป็น 500"""
    resp = _web_client(app).post(
        "/settings/tokens",
        data={"name": "   ", "password": PASSWORD},
        follow_redirects=True,
    )
    assert "token" in resp.get_data(as_text=True).lower()
    with app.app_context():
        assert tokens_service.list_tokens(db.session.get(User, user_id)) == []


def test_revoking_a_token_that_does_not_exist_is_a_404(app, user_id):
    assert _web_client(app).post("/settings/tokens/999999/revoke").status_code == 404


def test_revoking_someone_elses_token_is_a_404(app, user_id, other_user_id):
    issue_token(app, other_user_id, name="ของคนอื่น")
    with app.app_context():
        victim_token = tokens_service.list_tokens(db.session.get(User, other_user_id))[0].id

    assert _web_client(app).post(f"/settings/tokens/{victim_token}/revoke").status_code == 404
