"""เทสต์การเลือกภาษาและคำแปล

ข้อความในโค้ดเป็นภาษาอังกฤษ (เป็น msgid) ส่วนภาษาไทยมาจาก catalog
ถ้าเทสต์ไทยแดงขึ้นมาให้เช็คก่อนว่าลืมรัน `pybabel compile` หรือเปล่า
"""

from app import db
from app.models import User
from tests.conftest import PASSWORD

THAI_SIGN_IN = "เข้าสู่ระบบ"
THAI_NO_TASKS = "ยังไม่มีงาน"


def test_default_language_is_english(anon_client):
    resp = anon_client.get("/login")
    assert b"Sign in" in resp.data
    assert b'<html lang="en"' in resp.data


def test_thai_catalog_is_compiled(anon_client):
    """ถ้าอันนี้แดง แปลว่า .mo ยังไม่ถูก compile หรือคำแปลหาย"""
    resp = anon_client.get("/login?lang=th")
    assert THAI_SIGN_IN.encode() in resp.data
    assert b'<html lang="th"' in resp.data


def test_switching_language_persists_in_session(anon_client):
    anon_client.get("/lang/th")
    # คำขอถัดไปไม่ได้ส่ง ?lang= มาแล้ว แต่ยังต้องเป็นไทย
    assert THAI_SIGN_IN.encode() in anon_client.get("/login").data


def test_switch_back_to_english(anon_client):
    anon_client.get("/lang/th")
    anon_client.get("/lang/en")
    assert b"Sign in" in anon_client.get("/login").data


def test_unknown_language_is_404(anon_client):
    assert anon_client.get("/lang/xx").status_code == 404
    assert anon_client.get("/lang/../etc").status_code == 404


def test_unknown_lang_query_param_ignored(anon_client):
    """ค่ามั่วใน ?lang= ต้องตกกลับเป็นภาษาเริ่มต้น ไม่ใช่พัง"""
    resp = anon_client.get("/login?lang=klingon")
    assert resp.status_code == 200
    assert b"Sign in" in resp.data


def test_language_switch_saved_to_profile(app, client, user_id):
    client.get("/lang/th")
    with app.app_context():
        assert db.session.get(User, user_id).locale == "th"


def test_profile_language_used_on_fresh_session(app, user_id):
    """เก็บภาษาไว้ในโปรไฟล์แล้ว พอ login ใหม่จาก session เปล่าต้องได้ภาษานั้น"""
    with app.app_context():
        db.session.get(User, user_id).locale = "th"
        db.session.commit()

    fresh = app.test_client()
    fresh.post("/login", data={"username": "tester", "password": PASSWORD})
    assert THAI_NO_TASKS.encode() in fresh.get("/").data


def test_session_language_wins_over_profile(app, client, user_id):
    """กดสลับภาษาแล้วต้องมีผลทันที ไม่ต้องรอแก้โปรไฟล์"""
    with app.app_context():
        db.session.get(User, user_id).locale = "th"
        db.session.commit()
    client.get("/lang/en")
    assert b"No tasks yet" in client.get("/").data


def test_language_chosen_before_login_is_saved(app, anon_client, user_id):
    anon_client.get("/lang/th")
    anon_client.post("/login", data={"username": "tester", "password": PASSWORD})
    with app.app_context():
        assert db.session.get(User, user_id).locale == "th"


def test_accept_language_header_used_when_nothing_chosen(anon_client):
    resp = anon_client.get("/login", headers={"Accept-Language": "th-TH,th;q=0.9"})
    assert THAI_SIGN_IN.encode() in resp.data


def test_accept_language_unsupported_falls_back_to_english(anon_client):
    resp = anon_client.get("/login", headers={"Accept-Language": "ja-JP,ja;q=0.9"})
    assert b"Sign in" in resp.data


def test_flash_message_is_translated(client):
    client.get("/lang/th")
    resp = client.post("/add", data={"title": "  "}, follow_redirects=True)
    assert "กรุณาใส่ชื่องาน".encode() in resp.data


def test_login_error_is_translated(app, user_id, anon_client):
    anon_client.get("/lang/th")
    resp = anon_client.post(
        "/login", data={"username": "tester", "password": "ผิดแน่นอน"}
    )
    assert "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง".encode() in resp.data


def test_language_switch_returns_to_previous_page(client):
    resp = client.get("/lang/th", headers={"Referer": "http://localhost/categories"})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/categories")


def test_language_switch_ignores_external_referer(client):
    """referer ที่ชี้ออกนอกเว็บต้องไม่ถูกใช้ ไม่งั้นเป็น open redirect"""
    resp = client.get("/lang/th", headers={"Referer": "https://evil.example.com/x"})
    assert resp.status_code == 302
    assert "evil.example.com" not in resp.headers["Location"]


def test_every_supported_language_renders(anon_client, app):
    """ทุกภาษาใน LANGUAGES ต้องเปิดหน้าได้ ไม่ใช่แค่ที่มี catalog"""
    for code in app.config["LANGUAGES"]:
        assert anon_client.get(f"/login?lang={code}").status_code == 200


def test_translation_outside_request_does_not_crash(app):
    """เรียกแปลนอก request (เช่นจาก flask CLI) ต้องได้ภาษาเริ่มต้น ไม่ใช่ระเบิด
    เพราะตัวเลือกภาษาอ่านจาก request ซึ่งตอนนั้นไม่มี"""
    from flask_babel import gettext

    with app.app_context():
        assert gettext("Sign in") == "Sign in"


def test_locale_selector_outside_request_returns_default(app):
    from app.i18n import select_locale

    with app.app_context():
        assert select_locale() == app.config["BABEL_DEFAULT_LOCALE"]


def test_thai_catalog_has_no_untranslated_or_fuzzy_entries():
    """กัน 2 กรณีที่ทำให้ผู้ใช้เห็นภาษาอังกฤษทั้งที่เลือกไทยไว้:

    1. msgstr ว่าง = ลืมแปล
    2. #, fuzzy = pybabel เดาคำแปลให้จากข้อความที่คล้ายกัน ซึ่งมักผิดความหมาย
       และ compile จะข้ามไป ทำให้ตกกลับเป็น msgid เงียบ ๆ

    (catalog en ไม่ต้องมีคำแปล เพราะ msgid เป็นภาษาอังกฤษอยู่แล้ว)
    """
    import pathlib
    import re

    po = pathlib.Path(__file__).resolve().parent.parent / (
        "app/translations/th/LC_MESSAGES/messages.po"
    )
    text = po.read_text()

    fuzzy = re.findall(r'#, fuzzy\nmsgid "([^"]+)"', text)
    assert not fuzzy, f"มี msgid ที่ยัง fuzzy อยู่: {fuzzy}"

    empty = re.findall(r'\nmsgid "([^"]+)"\nmsgstr ""\n', text)
    assert not empty, f"มี msgid ที่ยังไม่ได้แปล: {empty}"
