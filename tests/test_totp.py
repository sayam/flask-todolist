"""ปัจจัยที่สอง: TOTP เป็น plugin ที่มีตารางของตัวเอง (Phase 4 — ADR 0023/0024)

สองเรื่องที่ต้องพิสูจน์แยกกัน:

1. **อัลกอริทึมถูกต้องจริง** — เทียบกับ test vector ใน RFC 6238 ตรง ๆ
   (โค้ดที่ "ดูเหมือนถูก" แต่ตัดตัวเลขผิดตำแหน่งจะให้รหัสที่ใช้กับ Google
   Authenticator ไม่ได้ และไม่มีเทสต์ภายในตัวไหนจับได้เลย)
2. **core ไม่รู้จักชื่อ `totp`** — เส้นทาง login/หน้า settings ทำงานผ่าน
   registry ล้วน ๆ ถอนไดเรกทอรีทิ้งแล้วต้องกลับไปเป็น login ปกติ

**app context อยู่ที่ fixture ตัวเทสต์ห้ามเปิดซ้อน และเทสต์ที่ยิง HTTP ต้อง
ไม่มี context ค้าง** (ดู `tests/test_rbac.py` และ CLAUDE.md)
"""

import base64
import io
import logging
import sys
import time

import pytest

from app import db, plugins
from app.models import User
from app.services import mfa
from tests.conftest import PASSWORD

TOTP_KEY = "auth/totp"
# ความลับตัวอย่างใน RFC 6238 คือ ASCII "12345678901234567890"
# **เข้ารหัส base32 ตรงนี้แทนที่จะเขียนค่าที่เข้ารหัสแล้วลงไป** สองเหตุผล:
# อ่านแล้วตรงกับที่ RFC เขียนไว้จริง ๆ และไม่มีสตริง base32 32 ตัวลอยอยู่ในซอร์ส
# ให้เครื่องมือสแกน secret เข้าใจผิดว่าเป็นความลับที่หลุด (gitleaks จับมาแล้ว)
RFC_SECRET = base64.b32encode(b"12345678901234567890").decode("ascii")
# (เวลา, รหัสแปดหลักตาม RFC) — ของเราใช้หกหลัก ซึ่งคือหกหลักท้ายของค่าเดียวกัน
RFC_VECTORS = [
    (59, "94287082"),
    (1111111109, "07081804"),
    (1111111111, "14050471"),
    (1234567890, "89005924"),
    (2000000000, "69279037"),
    (20000000000, "65353130"),
]


def factor():
    """โมดูลของ plugin — โหลดผ่าน registry เหมือนที่ core ทำ ไม่ import ตรง ๆ"""
    plugin = plugins.find(TOTP_KEY)
    assert plugin is not None, "ไม่พบ plugin auth/totp"
    return plugins.factor_module(plugin)


@pytest.fixture
def person(app):
    """ผู้ใช้หนึ่งคนพร้อม context ที่เปิดค้างไว้ (สำหรับเทสต์ที่เรียก service ตรง ๆ)"""
    with app.app_context():
        user = User(username="somchai")
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
        yield user


@pytest.fixture
def enrolled_user(app):
    """ผู้ใช้ที่เปิด TOTP เรียบร้อยแล้ว คืน (id, ความลับ) แล้ว **ปิด context**"""
    with app.app_context():
        user = User(username="mfauser")
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
        secret = factor().start_enrollment(user)
        # ยืนยันด้วยรหัสของ **ช่วงก่อนหน้า** เพราะการยืนยันนับว่ารหัสนั้นถูกใช้ไปแล้ว
        # ถ้ายืนยันด้วยรหัสของช่วงปัจจุบัน การ login ทันทีหลังจากนั้นจะถูกปฏิเสธ
        # ว่าใช้รหัสซ้ำ (ซึ่งถูกต้อง แต่ไม่ใช่สถานการณ์ที่อยากทดสอบตรงนี้)
        earlier = time.time() - factor().PERIOD
        assert factor().confirm(user, current_code(secret, earlier), at=earlier)
        return user.id, secret


def current_code(secret, at=None):
    now = time.time() if at is None else at
    return factor().code_at(secret, int(now // factor().PERIOD))


# ---------------------------------------------------------------- อัลกอริทึม


def test_matches_the_rfc_6238_test_vectors(app):
    """หกหลักของเราต้องเป็นหกหลักท้ายของรหัสแปดหลักใน RFC เป๊ะทุกตัว"""
    with app.app_context():
        for moment, expected in RFC_VECTORS:
            counter = moment // factor().PERIOD
            assert factor().code_at(RFC_SECRET, counter) == expected[-6:], f"ผิดที่ t={moment}"


def test_a_fresh_secret_is_random_and_long_enough(app):
    with app.app_context():
        secrets_seen = {factor().new_secret() for _ in range(20)}
        assert len(secrets_seen) == 20, "ความลับซ้ำกัน = การสุ่มพัง"
        # base32 ของ 20 ไบต์ = 32 ตัวอักษร (ตัด padding แล้ว)
        assert all(len(value) == 32 for value in secrets_seen)


def test_codes_from_the_neighbouring_windows_are_accepted(app):
    """นาฬิกาของโทรศัพท์ไม่เคยตรงกับ server เป๊ะ — ต้องเผื่อหนึ่งช่วงทั้งสองทาง"""
    with app.app_context():
        now = 1_700_000_000
        for shift in (-factor().PERIOD, 0, factor().PERIOD):
            code = current_code(RFC_SECRET, now + shift)
            assert factor().matching_counter(RFC_SECRET, code, now) is not None


def test_codes_from_further_away_are_rejected(app):
    with app.app_context():
        now = 1_700_000_000
        far = current_code(RFC_SECRET, now + 5 * factor().PERIOD)
        assert factor().matching_counter(RFC_SECRET, far, now) is None


def test_the_provisioning_uri_carries_what_the_app_needs(app):
    with app.app_context():
        uri = factor().provisioning_uri(RFC_SECRET, "somchai")
        assert uri.startswith("otpauth://totp/")
        assert f"secret={RFC_SECRET}" in uri
        assert "period=30" in uri


# ---------------------------------------------------------------- สถานะของผู้ใช้


def test_enrollment_is_not_on_until_it_is_confirmed(person):
    """คนที่สแกนไม่ทันต้องไม่ถูกล็อกออกจากบัญชีตัวเองทันทีที่กดเปิด"""
    secret = factor().start_enrollment(person)
    assert factor().is_pending(person)
    assert not factor().is_enrolled(person)
    assert not mfa.is_required(person)

    assert factor().confirm(person, current_code(secret))
    assert factor().is_enrolled(person)
    assert mfa.is_required(person)


def test_a_wrong_code_does_not_confirm_anything(person):
    factor().start_enrollment(person)
    assert not factor().confirm(person, "000000")
    assert not factor().is_enrolled(person)


def test_verify_refuses_a_secret_that_was_never_confirmed(person):
    """ใบที่ยังไม่ยืนยันต้องใช้ผ่านขั้นที่สองไม่ได้

    ถ้ายอมรับ คนที่กดเปิดแล้วปิดหน้าจอทิ้งไว้จะมีปัจจัยที่สองที่ "ใช้ได้" อยู่
    ทั้งที่ระบบไม่ได้นับว่าเขาเปิดใช้ — สองสถานะที่ขัดกันเองในบัญชีเดียว
    """
    secret = factor().start_enrollment(person)
    assert not factor().verify(person, current_code(secret))


def test_a_used_code_cannot_be_used_again(person):
    """คนที่แอบเห็นรหัสบนจอต้องเอาไปใช้ต่อไม่ได้ แม้ยังไม่ครบ 30 วินาที"""
    secret = factor().start_enrollment(person)
    code = current_code(secret)
    factor().confirm(person, code)

    assert not factor().verify(person, code), "รหัสเดิมต้องใช้ซ้ำไม่ได้"


def test_confirming_again_cannot_rewind_the_replay_guard(person):
    """ยืนยันซ้ำใบที่เปิดใช้แล้วต้องไม่ผ่าน

    `confirm()` ไม่ได้เช็คการใช้รหัสซ้ำเหมือน `verify()` ถ้ายอมให้ยืนยันซ้ำได้
    การยิงรหัสของช่วงที่ผ่านมาเข้ามาจะถอย `last_counter` กลับไปข้างหลัง
    แล้วรหัสที่ใช้ไปแล้วในช่วงระหว่างนั้นกลับมาใช้ได้อีก
    """
    secret = factor().start_enrollment(person)
    now = 1_700_000_000
    factor().confirm(person, current_code(secret, now), at=now)
    factor().verify(person, current_code(secret, now + factor().PERIOD), at=now + factor().PERIOD)

    older = now - factor().PERIOD
    assert not factor().confirm(person, current_code(secret, older), at=older)
    # นาฬิกาถอยหลังไม่ได้ รหัสของช่วงที่ใช้ไปแล้วจึงต้องยังใช้ไม่ได้
    assert not factor().verify(
        person, current_code(secret, now + factor().PERIOD), at=now + factor().PERIOD
    )


def test_the_next_window_still_works_after_a_used_code(person):
    secret = factor().start_enrollment(person)
    now = 1_700_000_000
    factor().confirm(person, current_code(secret, now), at=now)

    later = now + factor().PERIOD
    assert factor().verify(person, current_code(secret, later), at=later)


def test_the_secret_is_hidden_once_it_is_confirmed(person):
    """ใบที่เปิดใช้แล้วต้องไม่มีทางดูความลับซ้ำได้จากหน้าเว็บ"""
    secret = factor().start_enrollment(person)
    assert factor().setup_details(person), "ระหว่างลงทะเบียนต้องแสดงให้เจ้าตัวดูได้"

    factor().confirm(person, current_code(secret))
    assert factor().setup_details(person) == []


def test_starting_over_is_refused_while_it_is_on(person):
    """ไม่งั้น session ที่ถูกยึดจะออกความลับใบใหม่ให้ตัวเองแล้วยึดบัญชีถาวร"""
    secret = factor().start_enrollment(person)
    factor().confirm(person, current_code(secret))

    with pytest.raises(ValueError, match="ปิดก่อน"):
        factor().start_enrollment(person)


def test_disabling_removes_the_secret_for_real(app, person):
    """ชั้น C1 — ปิดแล้วต้องไม่เหลือความลับค้างในฐานข้อมูล (ไม่ใช่แค่ซ่อน)"""
    user_id = person.id
    secret = factor().start_enrollment(person)
    factor().confirm(person, current_code(secret))
    assert factor().disable(person)
    db.session.remove()

    reloaded = db.session.get(User, user_id)
    assert factor().secret_of(reloaded) is None, "แถวต้องหายไปจริง"
    assert not factor().is_enrolled(reloaded)


# ---------------------------------------------------------------- QR ของการลงทะเบียน
# ข้ออ้างที่ต้องพิสูจน์ ไม่ใช่แค่เขียนไว้ในคอมเมนต์:
# 1. ไม่มีความลับอยู่ใน URL (ไม่งั้นมันไปโผล่ใน log/ประวัติ/Referer)
# 2. ไม่ต้องผ่อน CSP (`img-src 'self'` เดิมต้องยังเป็น 'self' ล้วน)
# 3. เห็นได้เฉพาะเจ้าของ และเฉพาะตอนที่ยังไม่ยืนยัน


def test_the_qr_encodes_exactly_the_same_uri_as_the_text(app, user_id):
    """รูปกับข้อความต้องเป็นความลับเดียวกัน ไม่งั้นสแกนแล้วรหัสไม่ตรง

    เทียบด้วยการ encode ซ้ำจาก URI ที่รู้ค่า แทนการอ่าน QR กลับ (ซึ่งต้องมี
    ตัวถอดรหัสอีกตัว) — ถ้า payload ต่างกันแม้แต่บิตเดียว SVG จะไม่เหมือนกัน
    """
    import segno

    client = _sign_in(app, "tester")
    client.post("/settings/mfa/start", data={"factor": TOTP_KEY})

    with app.app_context():
        user = db.session.get(User, user_id)
        expected_uri = factor().provisioning_uri(factor().secret_of(user), user.username)

    resp = client.get(f"/settings/mfa/{TOTP_KEY}/image")
    assert resp.status_code == 200
    assert resp.mimetype == "image/svg+xml"

    # ตัวเลือกการวาดต้องตรงกับใน factor.py — เปลี่ยนที่นั่นแล้วเทสต์นี้จะแดง
    # ให้รู้ตัว (เจตนา: รูปที่เสิร์ฟออกไปคือ QR ของ URI ตัวนี้เป๊ะ ไม่ใช่ของอื่น)
    buffer = io.BytesIO()
    segno.make(expected_uri, error="m").save(
        buffer, kind="svg", scale=5, border=2, dark="#000000", light="#ffffff"
    )
    assert resp.data == buffer.getvalue()

    # และต้องไม่ตรงกับ QR ของ URI อื่น (กันเทสต์ที่เขียวเพราะเทียบของว่างกับของว่าง)
    other = io.BytesIO()
    segno.make(expected_uri + "x", error="m").save(
        other, kind="svg", scale=5, border=2, dark="#000000", light="#ffffff"
    )
    assert resp.data != other.getvalue()


def test_the_qr_carries_its_own_light_background(app, user_id):
    """โหมดมืด: QR ที่พื้นหลังโปร่งใสจะกลายเป็นดำบนดำ = สแกนไม่ได้

    ตัวสแกนต้องการโมดูลเข้มบนพื้นอ่อนเสมอ สีจึงฝังอยู่ในตัว SVG ไม่ได้ขึ้นกับธีม
    (เป็นข้อกำหนดของตัวสแกน ไม่ใช่การตัดสินใจเรื่องสไตล์)
    """
    client = _sign_in(app, "tester")
    client.post("/settings/mfa/start", data={"factor": TOTP_KEY})

    svg = client.get(f"/settings/mfa/{TOTP_KEY}/image").get_data(as_text=True).lower()
    # segno ย่อ #ffffff เป็น #fff ให้เอง — เทียบทั้งสองรูปแบบ
    assert 'fill="#fff"' in svg or 'fill="#ffffff"' in svg, "QR ไม่มีพื้นหลังอ่อนฝังมาด้วย"
    assert 'stroke="#000"' in svg or 'stroke="#000000"' in svg


def test_without_its_library_the_qr_disappears_instead_of_breaking(app, user_id, monkeypatch):
    """ไลบรารีของ plugin อยู่นอก `[packages]` ของ core (ADR 0025) — คนที่รัน
    `pipenv sync --dev` เฉย ๆ จะไม่มี segno และต้องได้หน้าลงทะเบียนแบบข้อความ
    ล้วน ไม่ใช่ 500

    ใส่ `None` ลง sys.modules ทำให้ `import segno` โยน ImportError ได้จริง
    (จำลองสภาพแวดล้อมที่ยังไม่ได้ติดตั้ง category ของ plugin ตัวนี้)
    """
    monkeypatch.setitem(sys.modules, "segno", None)

    client = _sign_in(app, "tester")
    client.post("/settings/mfa/start", data={"factor": TOTP_KEY})

    assert client.get(f"/settings/mfa/{TOTP_KEY}/image").status_code == 404

    body = client.get("/settings").get_data(as_text=True)
    assert "setup-qr" not in body, "ห้ามวาง <img> ที่ชี้ไปยัง URL ที่ตอบ 404"
    assert "Secret key" in body, "ทางข้อความต้องยังใช้ตั้งค่าได้ตามปกติ"

    # และการลงทะเบียนต้องยังจบได้ทั้งเส้น
    with app.app_context():
        secret = factor().secret_of(db.session.get(User, user_id))
    client.post("/settings/mfa/confirm", data={"factor": TOTP_KEY, "code": current_code(secret)})
    with app.app_context():
        assert factor().is_enrolled(db.session.get(User, user_id))


def test_the_qr_url_never_carries_the_secret(app, user_id, caplog):
    """ความลับใน URL = ความลับใน log ของเรา (ชั้น C6 อายุ 90 วัน), ใน log ของ
    reverse proxy, ในประวัติเบราว์เซอร์ และใน header `Referer` ของหน้าถัดไป"""
    client = _sign_in(app, "tester")
    client.post("/settings/mfa/start", data={"factor": TOTP_KEY})

    with app.app_context():
        secret = factor().secret_of(db.session.get(User, user_id))

    url = f"/settings/mfa/{TOTP_KEY}/image"
    assert secret not in url

    with caplog.at_level(logging.INFO):
        assert client.get(url).status_code == 200
    assert secret not in caplog.text, "ความลับหลุดลง log"

    # และหน้า settings ต้องไม่ฝังรูปเป็น data: URI (ซึ่งจะต้องผ่อน CSP)
    body = client.get("/settings").get_data(as_text=True)
    assert "data:image" not in body
    assert url in body


def test_serving_the_qr_does_not_loosen_the_csp(app, user_id):
    """`img-src 'self'` ต้องยังเป็น 'self' ล้วน — ทั้งหน้า settings และตัวรูปเอง"""
    client = _sign_in(app, "tester")
    client.post("/settings/mfa/start", data={"factor": TOTP_KEY})

    for path in ("/settings", f"/settings/mfa/{TOTP_KEY}/image"):
        csp = client.get(path).headers["Content-Security-Policy"]
        assert "img-src 'self'" in csp, path
        assert "data:" not in csp, f"{path}: CSP ถูกผ่อนให้รับ data URI"


def test_the_qr_is_not_cached_anywhere(app, user_id):
    client = _sign_in(app, "tester")
    client.post("/settings/mfa/start", data={"factor": TOTP_KEY})

    resp = client.get(f"/settings/mfa/{TOTP_KEY}/image")
    assert "no-store" in resp.headers["Cache-Control"]


def test_the_qr_is_gone_once_the_factor_is_confirmed(app, user_id):
    """ใบที่เปิดใช้แล้วต้องไม่มีทางดูความลับซ้ำได้ ไม่ว่าจะรูปหรือข้อความ"""
    client = _sign_in(app, "tester")
    client.post("/settings/mfa/start", data={"factor": TOTP_KEY})
    with app.app_context():
        secret = factor().secret_of(db.session.get(User, user_id))
    client.post("/settings/mfa/confirm", data={"factor": TOTP_KEY, "code": current_code(secret)})

    assert client.get(f"/settings/mfa/{TOTP_KEY}/image").status_code == 404


def test_there_is_no_qr_before_enrollment_starts(app, user_id):
    assert _sign_in(app, "tester").get(f"/settings/mfa/{TOTP_KEY}/image").status_code == 404


def test_the_qr_belongs_to_whoever_is_signed_in(app, user_id, other_user_id):
    """คนอื่นเรียก URL เดียวกันต้องไม่ได้ QR ของเรา — ตัวตนมาจาก session เท่านั้น"""
    owner = _sign_in(app, "tester")
    owner.post("/settings/mfa/start", data={"factor": TOTP_KEY})

    intruder = _sign_in(app, "intruder")
    assert intruder.get(f"/settings/mfa/{TOTP_KEY}/image").status_code == 404


def test_the_qr_needs_a_signed_in_user(app, anon_client):
    resp = anon_client.get(f"/settings/mfa/{TOTP_KEY}/image")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_an_unknown_factor_has_no_image(app, user_id):
    assert _sign_in(app, "tester").get("/settings/mfa/auth/nope/image").status_code == 404


# ---------------------------------------------------------------- ทางเข้าเว็บ


def test_signing_in_stops_halfway_when_a_second_factor_is_on(app, enrolled_user):
    """**สำคัญที่สุดของไฟล์นี้**: รหัสผ่านถูกอย่างเดียวต้องยังเข้าไม่ได้"""
    _user_id, _secret = enrolled_user
    client = app.test_client()

    resp = client.post("/login", data={"username": "mfauser", "password": PASSWORD})
    assert resp.status_code == 302
    assert "/login/verify" in resp.headers["Location"]

    # ยังไม่ใช่ session ที่ login แล้ว — เข้าหน้าอื่นไม่ได้
    assert "/login" in client.get("/", follow_redirects=False).headers["Location"]
    with client.session_transaction() as stored:
        assert "_user_id" not in stored


def test_the_right_code_finishes_the_sign_in(app, enrolled_user):
    user_id, secret = enrolled_user
    client = app.test_client()
    client.post("/login", data={"username": "mfauser", "password": PASSWORD})

    resp = client.post("/login/verify", data={"code": current_code(secret)})
    assert resp.status_code == 302
    assert client.get("/").status_code == 200
    with client.session_transaction() as stored:
        assert stored["_user_id"] == str(user_id)


def test_a_wrong_code_does_not_finish_the_sign_in(app, enrolled_user):
    client = app.test_client()
    client.post("/login", data={"username": "mfauser", "password": PASSWORD})

    resp = client.post("/login/verify", data={"code": "000000"})
    assert resp.status_code == 401
    with client.session_transaction() as stored:
        assert "_user_id" not in stored


def test_the_verify_page_is_useless_without_the_password_step(app, enrolled_user):
    """เข้ามาที่ /login/verify ตรง ๆ ต้องไม่มีอะไรให้ทำ"""
    anon = app.test_client()
    assert "/login" in anon.get("/login/verify").headers["Location"]
    assert "/login" in anon.post("/login/verify", data={"code": "000000"}).headers["Location"]


def test_the_halfway_state_expires(app, enrolled_user):
    """สถานะ 'ผ่านรหัสผ่านแล้ว' ปล่อยค้างไว้นานไม่ได้ (ADR 0024)"""
    _user_id, secret = enrolled_user
    client = app.test_client()
    client.post("/login", data={"username": "mfauser", "password": PASSWORD})

    with client.session_transaction() as stored:
        stored["mfa_at"] = time.time() - 10 * 24 * 3600

    resp = client.post("/login/verify", data={"code": current_code(secret)})
    assert "/login" in resp.headers["Location"], "หมดเวลาแล้วต้องกลับไปเริ่มใหม่"


def test_a_plugin_that_was_never_installed_does_not_break_login(app, user_id):
    """วางไดเรกทอรีไว้แต่ยังไม่ `flask plugin-install` = ข้ามไป ไม่ใช่พังทั้งระบบ

    เจอจริงตอน Phase 4: job `a11y` ใน CI ล้มทั้ง job เพราะที่นั่นรันแค่
    `flask db upgrade` (ซึ่งไม่สร้างตารางของ plugin **ตามดีไซน์** — ADR 0023)
    แล้วทุกหน้าที่แตะปัจจัยที่สองพังด้วย "no such table" รวมถึงหน้า login
    """
    from app import plugins

    with app.app_context():
        plugins.uninstall(plugins.find(TOTP_KEY))
        assert not plugins.is_installed(plugins.find(TOTP_KEY))
        assert mfa.available() == []

    client = app.test_client()
    assert (
        client.post("/login", data={"username": "tester", "password": PASSWORD}).status_code == 302
    )
    assert client.get("/settings").status_code == 200

    with app.app_context():
        plugins.install(plugins.find(TOTP_KEY))  # คืนสภาพให้เทสต์ตัวถัดไป


def test_someone_without_mfa_signs_in_as_before(app, user_id):
    client = app.test_client()
    resp = client.post("/login", data={"username": "tester", "password": PASSWORD})
    assert resp.status_code == 302
    assert "/login/verify" not in resp.headers["Location"]


# ---------------------------------------------------------------- หน้า settings


def _sign_in(app, username):
    client = app.test_client()
    resp = client.post("/login", data={"username": username, "password": PASSWORD})
    assert resp.status_code == 302
    return client


def test_the_settings_page_offers_the_factor_by_name_from_the_manifest(app, user_id):
    body = _sign_in(app, "tester").get("/settings").get_data(as_text=True)
    assert "Authenticator app" in body, "ชื่อต้องมาจาก manifest ของ plugin"
    assert 'value="auth/totp"' in body


def test_turning_it_on_and_off_from_the_web(app, user_id):
    client = _sign_in(app, "tester")

    client.post("/settings/mfa/start", data={"factor": TOTP_KEY})
    with app.app_context():
        user = db.session.get(User, user_id)
        secret = factor().secret_of(user)
        assert secret

    client.post("/settings/mfa/confirm", data={"factor": TOTP_KEY, "code": current_code(secret)})
    with app.app_context():
        assert factor().is_enrolled(db.session.get(User, user_id))

    # กดปิดโดยกรอกรหัสผ่านผิดต้องไม่มีอะไรเกิดขึ้น
    client.post("/settings/mfa/disable", data={"factor": TOTP_KEY, "password": "ผิด"})
    with app.app_context():
        assert factor().is_enrolled(db.session.get(User, user_id)), (
            "session ที่ถูกยึดต้องปิด MFA ไม่ได้ถ้าไม่รู้รหัสผ่าน"
        )

    client.post("/settings/mfa/disable", data={"factor": TOTP_KEY, "password": PASSWORD})
    with app.app_context():
        assert not factor().is_enrolled(db.session.get(User, user_id))


def test_an_unknown_factor_name_is_a_404(app, user_id):
    """ค่าที่มาจากฟอร์มต้องถูกเทียบกับรายการที่ค้นเจอจริงเสมอ ไม่เอาไปประกอบ path"""
    client = _sign_in(app, "tester")
    for path in ("start", "confirm", "disable"):
        resp = client.post(
            f"/settings/mfa/{path}",
            data={"factor": "auth/../../etc", "code": "000000", "password": PASSWORD},
        )
        assert resp.status_code == 404, path


def test_starting_over_from_the_web_is_refused_while_it_is_on(app, user_id):
    """ข้อความจาก service ต้องถึงผู้ใช้ ไม่ใช่กลายเป็น 500"""
    client = _sign_in(app, "tester")
    client.post("/settings/mfa/start", data={"factor": TOTP_KEY})
    with app.app_context():
        secret = factor().secret_of(db.session.get(User, user_id))
    client.post("/settings/mfa/confirm", data={"factor": TOTP_KEY, "code": current_code(secret)})

    resp = client.post("/settings/mfa/start", data={"factor": TOTP_KEY}, follow_redirects=True)
    assert "ปิดการยืนยันสองขั้นก่อน" in resp.get_data(as_text=True) or "Turn off" in resp.get_data(
        as_text=True
    )


def test_a_wrong_code_on_the_settings_page_says_so(app, user_id):
    client = _sign_in(app, "tester")
    client.post("/settings/mfa/start", data={"factor": TOTP_KEY})

    resp = client.post(
        "/settings/mfa/confirm",
        data={"factor": TOTP_KEY, "code": "000000"},
        follow_redirects=True,
    )
    assert "That code is not valid" in resp.get_data(as_text=True)
    with app.app_context():
        assert not factor().is_enrolled(db.session.get(User, user_id))
