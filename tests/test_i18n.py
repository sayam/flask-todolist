"""เทสต์การเลือกภาษาและคำแปล

ข้อความในโค้ดเป็นภาษาอังกฤษ (เป็น msgid) ส่วนภาษาไทยมาจาก catalog
ถ้าเทสต์ไทยแดงขึ้นมาให้เช็คก่อนว่าลืมรัน `pybabel compile` หรือเปล่า
"""

import pathlib
import subprocess

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
    resp = anon_client.post("/login", data={"username": "tester", "password": "ผิดแน่นอน"})
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


def _entries(text):
    """แยก .po เป็นรายการ (flags, msgid, msgstr) — **ต่อบรรทัดที่ถูกตัดให้ด้วย**

    ข้อความยาวถูก pybabel ตัดเป็นหลายบรรทัดในรูป `msgid ""` แล้วตามด้วย
    `"..."` ทีละท่อน · การอ่านด้วย regex บรรทัดเดียวจึงมองไม่เห็นมันเลย
    (เจอจริงตอน P7-06: ข้อความสองประโยคที่ยังไม่ได้แปลผ่านด่านนี้ไปได้)
    """
    for block in text.split("\n\n"):
        flags, field, parts = "", None, {"msgid": "", "msgstr": "", "skip": ""}
        for line in block.splitlines():
            if line.startswith("#,"):
                flags = line
                continue
            name, _, value = line.partition(" ")
            if name.startswith("msgstr"):
                # **รายการพหูพจน์ใช้ `msgstr[0]`, `msgstr[1]`** — ไทยมี nplurals=1
                # จึงมีแค่ [0] · การอ่านเฉพาะ `msgstr` เปล่า ๆ ทำให้รายการพหูพจน์
                # ทุกตัวดูเหมือน "ยังไม่แปล" ทั้งที่แปลแล้ว
                field = "msgstr"
            elif name == "msgid":
                field = "msgid"
            elif name == "msgid_plural":
                # รูปพหูพจน์ของภาษาต้นทาง ไม่ใช่ช่องที่ต้องมีคำแปลของตัวเอง
                field = "skip"
            elif line.startswith('"') and field:
                parts[field] += line.strip().strip('"')
                continue
            else:
                continue
            parts[field] += value.strip().strip('"')
        if parts["msgid"]:
            yield flags, parts["msgid"], parts["msgstr"]


def test_thai_catalog_has_no_untranslated_or_fuzzy_entries():
    """กัน 2 กรณีที่ทำให้ผู้ใช้เห็นภาษาอังกฤษทั้งที่เลือกไทยไว้:

    1. msgstr ว่าง = ลืมแปล
    2. #, fuzzy = pybabel เดาคำแปลให้จากข้อความที่คล้ายกัน ซึ่งมักผิดความหมาย
       และ compile จะข้ามไป ทำให้ตกกลับเป็น msgid เงียบ ๆ

    (catalog en ไม่ต้องมีคำแปล เพราะ msgid เป็นภาษาอังกฤษอยู่แล้ว)
    """
    po = pathlib.Path(__file__).resolve().parent.parent / (
        "app/translations/th/LC_MESSAGES/messages.po"
    )
    entries = list(_entries(po.read_text()))
    assert entries, "อ่าน catalog ไม่ได้เลย — รูปแบบไฟล์เปลี่ยนไปแล้ว"

    fuzzy = [msgid for flags, msgid, _ in entries if "fuzzy" in flags]
    assert not fuzzy, f"มี msgid ที่ยัง fuzzy อยู่: {fuzzy}"

    empty = [msgid for _, msgid, msgstr in entries if not msgstr]
    assert not empty, f"มี msgid ที่ยังไม่ได้แปล: {empty}"


# --- catalog ต้องครอบข้อความที่มีอยู่ในโค้ดจริง ---

# ต้องตรงกับคำสั่งใน CLAUDE.md เป๊ะ:
#   pybabel extract -F babel.cfg -k _l -k _ -k ngettext:1,2 -o messages.pot .
# ถ้าสองอย่างนี้ต่างกัน ด่านนี้จะตรวจของคนละชุดกับที่คนรันจริง
EXTRA_KEYWORDS = {"_l": None, "_": None, "ngettext": (1, 2)}
METHOD_MAP = [("**.py", "python"), ("**/templates/**.html", "jinja2")]


def _msgids_in_code():
    """ข้อความทุกตัวที่ตัว extract ของ babel มองเห็นในโค้ด

    เรียก API ของ babel ตรง ๆ แทนการ shell out — ผลต้องเท่ากับที่ CLI ให้
    (มีเทสต์ข้างล่างเทียบกับ .pot ที่ CLI สร้าง เพื่อไม่ให้สองทางนี้เพี้ยนจากกัน)
    """
    from babel.messages.extract import DEFAULT_KEYWORDS, extract_from_dir

    root = pathlib.Path(__file__).resolve().parent.parent
    keywords = {**DEFAULT_KEYWORDS, **EXTRA_KEYWORDS}
    found = set()
    for _filename, _lineno, message, _comments, _context in extract_from_dir(
        str(root), METHOD_MAP, keywords=keywords
    ):
        # ngettext คืน tuple (เอกพจน์, พหูพจน์) — catalog เก็บด้วย msgid เอกพจน์
        found.add(message[0] if isinstance(message, tuple) else message)
    return {message for message in found if message}


def test_the_catalog_covers_every_message_in_the_code():
    """**ข้อความใหม่ที่ไม่เคยถูก extract จะตกกลับเป็นภาษาอังกฤษเงียบ ๆ**

    ด่านเดิมตรวจว่า catalog ไม่มีช่องว่าง แต่ไม่ได้ตรวจว่า catalog *ครอบโค้ดครบ*
    — ข้อความของ SSO/LDAP ทั้งชุดจาก Phase 5 จึงไม่เคยเข้า catalog เลย และ
    ผู้ใช้ภาษาไทยเห็นภาษาอังกฤษมาตลอดโดยไม่มีอะไรฟ้อง (เจอตอน P7-03)

    หลักเดียวกับ `docs/openapi.json`: ของที่ต้อง generate แล้วไม่มีอะไรเทียบกับ
    ต้นทาง ย่อมค้างอยู่กับสภาพของวันที่มีคนนึกขึ้นได้ครั้งสุดท้าย
    """
    po = pathlib.Path(__file__).resolve().parent.parent / (
        "app/translations/th/LC_MESSAGES/messages.po"
    )
    catalog = {msgid for _flags, msgid, _msgstr in _entries(po.read_text())}
    missing = sorted(_msgids_in_code() - catalog)
    assert not missing, (
        f"ข้อความที่อยู่ในโค้ดแต่ไม่มีใน catalog ({len(missing)} ข้อความ):\n"
        + "\n".join(missing[:10])
        + "\nรัน pybabel extract/update/compile ตามขั้นตอนใน CLAUDE.md แล้วแปลให้ครบ"
    )


def test_the_gate_reads_the_same_messages_as_the_command_people_run():
    """ด่านที่อ่านคนละชุดกับคำสั่งจริง คือด่านที่เขียวโดยไม่ได้ตรวจของที่ใช้อยู่

    รัน pybabel ของจริงแล้วเทียบ — ถ้าวันหนึ่ง babel.cfg หรือ keyword เปลี่ยน
    แล้วมีคนลืมแก้ที่นี่ ตัวนี้จะเป็นคนบอก
    """
    root = pathlib.Path(__file__).resolve().parent.parent
    pot = root / "messages.pot"
    before = pot.read_text() if pot.exists() else None
    try:
        # S603/S607: อาร์กิวเมนต์ทุกตัวเป็นค่าคงที่ในไฟล์นี้ ไม่มีอะไรมาจากภายนอก
        # และเจตนาคือเรียก `pybabel` ตัวเดียวกับที่คนพิมพ์เอง จึงต้องหาจาก PATH
        subprocess.run(  # noqa: S603 - trusted executable and input
            [  # noqa: S607 - executable is in PATH
                "pybabel",
                "extract",
                "-F",
                "babel.cfg",
                "-k",
                "_l",
                "-k",
                "_",
                "-k",
                "ngettext:1,2",
                "-o",
                str(pot),
                ".",
            ],
            cwd=root,
            check=True,
            capture_output=True,
        )
        from_command = {msgid for _flags, msgid, _msgstr in _entries(pot.read_text())}
    finally:
        if before is None:
            pot.unlink(missing_ok=True)
        else:
            pot.write_text(before)

    assert from_command == _msgids_in_code(), (
        "ชุดข้อความที่ด่านนี้อ่าน ไม่ตรงกับที่คำสั่งใน CLAUDE.md ให้ผล — "
        "แก้ METHOD_MAP/EXTRA_KEYWORDS ให้ตรงกับคำสั่งนั้น"
    )
