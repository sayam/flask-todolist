"""นโยบายรหัสผ่านตาม NIST SP 800-63B (Phase 4 — ดู ADR 0019)

สิ่งที่ไฟล์นี้ต้องพิสูจน์ไม่ใช่แค่ "กฎทำงาน" แต่รวมถึง **กฎที่ตั้งใจไม่มี**ด้วย
(ไม่มี complexity, ไม่ตัดปลาย, ยาวเท่าไหร่ก็ได้จนถึงเพดาน) เพราะถ้าวันหนึ่ง
มีคนเติม "ต้องมีตัวเลขหนึ่งตัว" กลับเข้ามา จะไม่มีอะไรค้านเลยถ้าไม่เขียนไว้

**app context อยู่ที่ fixture ตัวเทสต์ห้ามเปิดซ้อน** ด้วยเหตุผลเดียวกับ
`tests/test_services.py` (session คนละตัว = การเขียนหายเงียบ)
"""

import pytest

from app import db
from app.audit import AuditEntry
from app.models import User
from app.services import ValidationError
from app.services import passwords as passwords_service
from tests.conftest import PASSWORD

# รหัสที่อยู่ในรายการที่หลุดแล้วจริง ๆ (เช็คได้จาก app/password_blocklist.txt)
BREACHED = "password123"
# ยาวพอ ไม่อยู่ในรายการ ไม่มีตัวเลข ไม่มีตัวใหญ่ ไม่มีอักขระพิเศษ —
# ต้องผ่าน เพราะนโยบายนี้ไม่มีกฎ complexity โดยตั้งใจ
PLAIN_BUT_FINE = "quiet mountain evening"
# ภาษาไทยมี สระอำ (U+0E33) ที่ NFKC แตกเป็นสองตัว — ค่าที่เก็บจึงไม่ใช่ไบต์ชุด
# เดียวกับที่ผู้ใช้พิมพ์ ใช้พิสูจน์ว่า normalize เกิดทั้งตอนตั้งและตอนตรวจ
THAI_PASSWORD = "ปลาทองว่ายน้ำในบ่อ"
NEW_PASSWORD = "a-brand-new-passphrase"


@pytest.fixture
def person(app):
    """ผู้ใช้หนึ่งคนที่ context ถูกเปิดค้างไว้ให้ (ดูหัวข้อบนสุดของไฟล์)"""
    with app.app_context():
        user = User(username="somchai")
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
        yield user


# ---------------------------------------------------------------- ตัวกฎ


def test_short_password_is_rejected():
    with pytest.raises(ValidationError) as raised:
        passwords_service.validate("sh0rt")
    assert raised.value.code == "password_too_short"


def test_password_exactly_at_the_minimum_is_accepted():
    """ขอบเขตต้องเป็น >= ไม่ใช่ > — off-by-one ตรงนี้ตัดสิทธิ์คนที่ทำถูกตามป้าย"""
    at_minimum = "wq7hj2vx"  # 8 ตัวพอดี ไม่อยู่ในรายการที่หลุด
    assert len(at_minimum) == passwords_service.MIN_LENGTH
    assert passwords_service.validate(at_minimum) == at_minimum


def test_long_password_is_rejected():
    with pytest.raises(ValidationError) as raised:
        passwords_service.validate("a" * (passwords_service.MAX_LENGTH + 1))
    assert raised.value.code == "password_too_long"


def test_password_at_the_cap_is_accepted():
    """เพดานมีไว้กัน hash ของขนาดมหาศาล ไม่ใช่กัน passphrase ยาว ๆ"""
    at_cap = "a" * passwords_service.MAX_LENGTH
    assert passwords_service.validate(at_cap) == at_cap


def test_cap_leaves_room_for_the_length_nist_requires():
    """NIST บังคับว่า verifier ต้องรับอย่างน้อย 64 ตัว — เพดานต้องไม่ต่ำกว่านั้น"""
    assert passwords_service.MAX_LENGTH >= 64


def test_breached_password_is_rejected():
    with pytest.raises(ValidationError) as raised:
        passwords_service.validate(BREACHED)
    assert raised.value.code == "password_breached"


def test_breach_check_ignores_letter_case():
    """`PassWord123` คือรหัสเดียวกับที่หลุดไปแล้วในสายตาคนที่ไล่เดา"""
    with pytest.raises(ValidationError) as raised:
        passwords_service.validate("PassWord123")
    assert raised.value.code == "password_breached"


def test_there_is_no_complexity_rule():
    """ไม่มีตัวเลข ไม่มีตัวใหญ่ ไม่มีอักขระพิเศษ แต่ยาวและไม่เคยหลุด → ต้องผ่าน"""
    assert passwords_service.validate(PLAIN_BUT_FINE) == PLAIN_BUT_FINE


def test_password_containing_the_username_is_rejected():
    with pytest.raises(ValidationError) as raised:
        passwords_service.validate("somchai-loves-cats", username="somchai")
    assert raised.value.code == "password_has_username"


def test_username_match_ignores_letter_case():
    with pytest.raises(ValidationError) as raised:
        passwords_service.validate("xxSOMCHAIxx-longer", username="somchai")
    assert raised.value.code == "password_has_username"


def test_a_very_short_username_is_not_matched_as_a_substring():
    """username สองตัวอักษรที่ไปโผล่กลางรหัสผ่านดี ๆ ไม่ควรทำให้ถูกปฏิเสธ"""
    assert passwords_service.validate("quiet-mountain-air", username="ai")


def test_spaces_are_kept_not_trimmed():
    """ตัดช่องว่างท้ายทิ้งเงียบ ๆ = ความยาวที่ผู้ใช้ตั้งใจไม่ได้ถูกใช้จริง"""
    with_space = "  a quiet passphrase  "
    assert passwords_service.validate(with_space) == with_space


def test_a_password_that_normalization_rewrites_still_signs_in(person):
    """สระอำ ถูก NFKC แตกเป็นสองตัว ค่าที่เก็บจึงต่างจากที่ผู้ใช้พิมพ์

    ถ้า normalize เกิดแค่ฝั่งใดฝั่งหนึ่ง คนที่ตั้งรหัสเป็นภาษาไทยจะ login ไม่ได้
    ทั้งที่พิมพ์เหมือนเดิมเป๊ะ — และจะไม่มีใครหาสาเหตุเจอเลย
    """
    assert passwords_service.normalize(THAI_PASSWORD) != THAI_PASSWORD
    person.set_password(THAI_PASSWORD)
    assert person.check_password(THAI_PASSWORD)


def test_unicode_forms_that_look_alike_are_the_same_password():
    """NFKC: ตัวเต็มความกว้างกับตัวปกติต้องนับเป็นรหัสเดียวกัน"""
    fullwidth = "ｐａｓｓｗｏｒｄ１２３"
    assert passwords_service.normalize(fullwidth) == BREACHED
    with pytest.raises(ValidationError) as raised:
        passwords_service.validate(fullwidth)
    assert raised.value.code == "password_breached"


# ---------------------------------------------------------------- ตัวรายการที่หลุด


def test_the_blocklist_is_actually_loaded():
    entries = passwords_service.blocklist()
    assert len(entries) > 10_000, "รายการเล็กผิดปกติ — ไฟล์ถูก generate มาครบไหม"
    assert BREACHED in entries


def test_the_blocklist_holds_only_comparable_entries():
    """ทุกบรรทัดต้องอยู่ในรูปที่ `blocklist_key()` ผลิต ไม่งั้นเทียบไม่เจอเงียบ ๆ

    บรรทัดที่ยังมีตัวใหญ่ค้างอยู่คือรายการที่ไม่มีวันถูก match เลยสักครั้ง
    """
    for entry in passwords_service.blocklist():
        assert entry == passwords_service.blocklist_key(entry)
        assert len(entry) >= passwords_service.MIN_LENGTH


# ---------------------------------------------------------------- เปลี่ยนรหัสผ่าน


def test_change_password_needs_the_current_one(person):
    with pytest.raises(ValidationError) as raised:
        passwords_service.change_password(
            person, current_password="not-the-right-one", new_password=NEW_PASSWORD
        )
    assert raised.value.code == "password_incorrect"
    assert person.check_password(PASSWORD), "รหัสเดิมต้องยังใช้ได้เมื่อการเปลี่ยนไม่ผ่าน"


def test_change_password_applies_the_policy_to_the_new_password(person):
    with pytest.raises(ValidationError) as raised:
        passwords_service.change_password(person, current_password=PASSWORD, new_password=BREACHED)
    assert raised.value.code == "password_breached"


def test_change_password_is_written_to_the_database(app, person):
    """พิสูจน์ว่า commit จริง ไม่ใช่แค่ค่าในหน่วยความจำเปลี่ยน (ดูหัวข้อบนสุด)"""
    user_id = person.id
    passwords_service.change_password(person, current_password=PASSWORD, new_password=NEW_PASSWORD)
    db.session.remove()

    reloaded = db.session.get(User, user_id)
    assert reloaded.check_password(NEW_PASSWORD)
    assert not reloaded.check_password(PASSWORD)


def test_change_password_leaves_an_audit_event(person):
    passwords_service.change_password(person, current_password=PASSWORD, new_password=NEW_PASSWORD)
    events = [row.event for row in db.session.query(AuditEntry).all()]
    assert "auth.password_change" in events


def test_a_failed_change_is_audited_too(person):
    """รหัสเดิมผิดทั้งที่ login อยู่ = สัญญาณว่า session ถูกยึด ต้องมีหลักฐาน"""
    with pytest.raises(ValidationError):
        passwords_service.change_password(
            person, current_password="wrong", new_password=NEW_PASSWORD
        )
    events = [row.event for row in db.session.query(AuditEntry).all()]
    assert "auth.password_failed" in events


def test_admin_reset_does_not_ask_for_the_old_password_but_still_validates(app, person):
    user_id = person.id
    with pytest.raises(ValidationError) as raised:
        passwords_service.set_password(person, BREACHED)
    assert raised.value.code == "password_breached"

    passwords_service.set_password(person, NEW_PASSWORD)
    db.session.remove()
    assert db.session.get(User, user_id).check_password(NEW_PASSWORD)


def test_audit_never_records_the_password_itself(person):
    passwords_service.change_password(person, current_password=PASSWORD, new_password=NEW_PASSWORD)
    dump = " ".join(row.changes for row in db.session.query(AuditEntry).all())
    assert NEW_PASSWORD not in dump
    assert PASSWORD not in dump


# ---------------------------------------------------------------- ทางฝั่งเว็บ


def test_settings_page_offers_a_password_form(client):
    body = client.get("/settings").get_data(as_text=True)
    assert 'action="/settings/password"' in body
    assert 'name="current_password"' in body


def test_web_change_password_then_sign_in_with_the_new_one(app, client):
    resp = client.post(
        "/settings/password",
        data={
            "current_password": PASSWORD,
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )
    assert resp.status_code == 302

    assert (
        app.test_client()
        .post("/login", data={"username": "tester", "password": NEW_PASSWORD})
        .status_code
        == 302
    )
    # **ต้องเป็น client คนละตัว** — ตัวที่ login สำเร็จไปแล้วจะถูก `/login` เด้ง
    # กลับหน้าแรกด้วย 302 ตั้งแต่ก่อนถึงการตรวจรหัส เทสต์จะเขียวโดยไม่ได้ตรวจอะไร
    assert (
        app.test_client()
        .post("/login", data={"username": "tester", "password": PASSWORD})
        .status_code
        == 401
    ), "รหัสเดิมต้องใช้ไม่ได้แล้ว"


def test_web_change_password_rejects_a_mistyped_confirmation(app, client):
    client.post(
        "/settings/password",
        data={
            "current_password": PASSWORD,
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD + "typo",
        },
    )
    fresh = app.test_client()
    assert (
        fresh.post("/login", data={"username": "tester", "password": PASSWORD}).status_code == 302
    ), "รหัสต้องไม่ถูกเปลี่ยนเมื่อช่องยืนยันไม่ตรง"


def test_web_change_password_rejects_a_wrong_current_password(app, client):
    resp = client.post(
        "/settings/password",
        data={
            "current_password": "not-the-right-one",
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
        follow_redirects=True,
    )
    assert "Current password is incorrect" in resp.get_data(as_text=True)


def test_web_change_password_needs_a_signed_in_user(anon_client):
    resp = anon_client.post(
        "/settings/password",
        data={
            "current_password": PASSWORD,
            "new_password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# ---------------------------------------------------------------- ทาง CLI


def test_create_user_rejects_a_breached_password(app):
    result = app.test_cli_runner().invoke(
        args=["create-user", "newcomer"], input=f"{BREACHED}\n{BREACHED}\n"
    )
    assert result.exit_code != 0
    assert "data breach" in result.output
    with app.app_context():
        assert db.session.query(User).filter_by(username="newcomer").first() is None


def test_set_password_command_changes_the_password(app, user_id):
    result = app.test_cli_runner().invoke(
        args=["set-password", "tester"], input=f"{NEW_PASSWORD}\n{NEW_PASSWORD}\n"
    )
    assert result.exit_code == 0, result.output
    with app.app_context():
        assert db.session.get(User, user_id).check_password(NEW_PASSWORD)


def test_set_password_command_rejects_an_unknown_user(app):
    result = app.test_cli_runner().invoke(args=["set-password", "ไม่มีคนนี้"])
    assert result.exit_code != 0
    assert "No user named" in result.output
