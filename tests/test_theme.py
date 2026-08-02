"""เทสต์ธีมสว่าง/มืด

ค่าเริ่มต้นคือ "ตามระบบ" ซึ่งแปลว่า **ไม่ใส่** data-theme ลง <html>
แล้วปล่อยให้ prefers-color-scheme ใน CSS ตัดสิน — ถ้าเผลอใส่ค่าตายตัวลงไป
คนที่ตั้ง dark ไว้ที่ OS จะได้หน้าสว่างแทน
"""

import pathlib
import re

from app import db
from app.models import User
from app.theme import AUTO
from tests.conftest import PASSWORD

CSS_PATH = pathlib.Path(__file__).resolve().parent.parent / "app" / "static" / "style.css"


def _data_theme(resp):
    match = re.search(rb'<html[^>]*\sdata-theme="([a-z]+)"', resp.data)
    return match.group(1).decode() if match else None


# --- ค่าเริ่มต้นและการสลับ ---

def test_default_is_system_theme(anon_client):
    """ไม่มี data-theme = ปล่อยให้ OS ตัดสิน"""
    assert _data_theme(anon_client.get("/login")) is None


def test_query_param_forces_theme(anon_client):
    assert _data_theme(anon_client.get("/login?theme=dark")) == "dark"
    assert _data_theme(anon_client.get("/login?theme=light")) == "light"


def test_switch_persists_in_session(anon_client):
    anon_client.get("/theme/dark")
    assert _data_theme(anon_client.get("/login")) == "dark"


def test_switch_back_to_auto(anon_client):
    anon_client.get("/theme/dark")
    anon_client.get(f"/theme/{AUTO}")
    assert _data_theme(anon_client.get("/login")) is None


def test_unknown_theme_is_404(anon_client):
    assert anon_client.get("/theme/neon").status_code == 404
    assert anon_client.get("/theme/../etc").status_code == 404


def test_unknown_theme_query_param_ignored(anon_client):
    resp = anon_client.get("/login?theme=neon")
    assert resp.status_code == 200
    assert _data_theme(resp) is None


# --- บันทึกลงโปรไฟล์ ---

def test_theme_saved_to_profile(app, client, user_id):
    client.get("/theme/dark")
    with app.app_context():
        assert db.session.get(User, user_id).theme == "dark"


def test_auto_clears_profile_theme(app, client, user_id):
    """'ตามระบบ' ไม่ใช่ชื่อธีม จึงต้องเก็บเป็น NULL ไม่ใช่สตริง 'auto'"""
    client.get("/theme/dark")
    client.get(f"/theme/{AUTO}")
    with app.app_context():
        assert db.session.get(User, user_id).theme is None


def test_profile_theme_used_on_fresh_session(app, user_id):
    with app.app_context():
        db.session.get(User, user_id).theme = "dark"
        db.session.commit()

    fresh = app.test_client()
    fresh.post("/login", data={"username": "tester", "password": PASSWORD})
    assert _data_theme(fresh.get("/")) == "dark"


def test_session_theme_wins_over_profile(app, client, user_id):
    with app.app_context():
        db.session.get(User, user_id).theme = "dark"
        db.session.commit()
    client.get("/theme/light")
    assert _data_theme(client.get("/")) == "light"


def test_anonymous_switch_does_not_crash(anon_client):
    """คนที่ยังไม่ login ต้องสลับธีมได้ ไม่ใช่ 302 ไปหน้า login"""
    assert anon_client.get("/theme/dark").status_code == 302
    assert _data_theme(anon_client.get("/login")) == "dark"


def test_switch_returns_to_previous_page(client):
    resp = client.get("/theme/dark", headers={"Referer": "http://localhost/categories"})
    assert resp.headers["Location"].endswith("/categories")


def test_switch_ignores_external_referer(client):
    resp = client.get("/theme/dark", headers={"Referer": "https://evil.example.com/x"})
    assert "evil.example.com" not in resp.headers["Location"]


# --- stylesheet ---

def test_stylesheet_is_linked_and_served(anon_client):
    assert b"style.css" in anon_client.get("/login").data
    resp = anon_client.get("/static/style.css")
    assert resp.status_code == 200
    assert b"--bg" in resp.data


def _declarations(block):
    return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", block))


def _block_after(css, selector):
    """เนื้อในของบล็อกแรกที่ตรงกับ selector

    ตัด " {" ท้าย selector ทิ้งก่อน ไม่งั้นจะข้ามไปจับ { ของบล็อกถัดไป
    """
    selector = selector.rstrip(" {")
    start = css.index(selector) + len(selector)
    start = css.index("{", start) + 1
    depth, i = 1, start
    while depth:
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
        i += 1
    return css[start : i - 1]


def test_dark_palette_matches_in_both_places():
    """ธีมมืดถูกประกาศสองที่ (media query กับ [data-theme=dark])
    ถ้าแก้ที่เดียวลืมอีกที่ คนกดเลือกเองกับคนใช้ค่า OS จะเห็นสีไม่เหมือนกัน"""
    css = CSS_PATH.read_text()
    from_media = _declarations(_block_after(css, ':root:not([data-theme="light"])'))
    from_attr = _declarations(_block_after(css, ':root[data-theme="dark"]'))

    assert from_media, "ไม่พบบล็อกธีมมืดใน @media prefers-color-scheme"
    assert from_media == from_attr, (
        "ค่าสีธีมมืดสองที่ไม่ตรงกัน — "
        f"ต่างกันที่ {set(from_media.items()) ^ set(from_attr.items())}"
    )


def test_light_and_dark_define_the_same_variables():
    """ธีมมืดต้องกำหนดครบทุกตัวแปรที่ธีมสว่างกำหนด ไม่งั้นจะมีสีตกค้าง"""
    css = CSS_PATH.read_text()
    light = _declarations(_block_after(css, ":root {"))
    dark = _declarations(_block_after(css, ':root[data-theme="dark"]'))
    assert set(light) == set(dark), (
        f"ตัวแปรไม่ครบ: มีแต่ในสว่าง {set(light) - set(dark)}, "
        f"มีแต่ในมืด {set(dark) - set(light)}"
    )


def test_no_raw_colours_outside_theme_blocks():
    """สีดิบต้องอยู่แค่ในบล็อกนิยามธีม ที่เหลือต้องอ้าง var()
    ไม่งั้นสีนั้นจะไม่เปลี่ยนตามธีม"""
    css = CSS_PATH.read_text()
    outside = css
    for sel in (":root", ':root:not([data-theme="light"])', ':root[data-theme="dark"]'):
        outside = outside.replace(_block_after(css, sel), "", 1)
    leaked = re.findall(r"#[0-9a-fA-F]{3,8}\b", outside)
    assert not leaked, f"พบสีดิบนอกบล็อกธีม: {leaked}"


# --- หน้า login จัดกึ่งกลาง ---

def test_login_form_is_centered(anon_client):
    resp = anon_client.get("/login")
    assert b'class="auth"' in resp.data
    css = CSS_PATH.read_text()
    auth = _block_after(css, ".auth {")
    assert "justify-content: center" in auth
    assert "align-items: center" in auth
