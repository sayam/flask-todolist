"""security headers + กติกา CSP-ready ของ template

CSP ที่ไม่มี `unsafe-inline` พังแบบเงียบ: browser บล็อก inline handler
โดยไม่มี error ฝั่ง server เทสต์ชุดนี้จึงตรวจสองชั้น — header ที่ส่งออกจริง
และ template ว่าไม่มี inline handler/style หลงเหลือ
"""

import pathlib
import re

import pytest

from app import create_app
from tests.conftest import TestConfig

TEMPLATES = pathlib.Path(__file__).resolve().parent.parent / "app" / "templates"

# ทุกหน้าที่ผู้ใช้เข้าถึงได้ ทั้งก่อนและหลัง login
PAGES = ["/login", "/", "/categories", "/settings"]

INLINE_HANDLER = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
INLINE_STYLE = re.compile(r"\sstyle\s*=", re.IGNORECASE)


class HttpsTestConfig(TestConfig):
    """จำลองสภาพหลังมี TLS จริง (Phase 5)"""

    HTTPS_ENABLED = True


# --- header ที่ส่งออกจริง ---


@pytest.mark.parametrize("path", PAGES)
def test_security_headers_on_every_page(client, path):
    resp = client.get(path)
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in resp.headers


@pytest.mark.parametrize("path", PAGES)
def test_csp_has_no_unsafe_directives(client, path):
    csp = client.get(path).headers["Content-Security-Policy"]
    assert "unsafe-inline" not in csp
    assert "unsafe-eval" not in csp


def test_csp_locks_down_the_dangerous_directives(client):
    csp = client.get("/login").headers["Content-Security-Policy"]
    for directive in ("frame-ancestors 'none'", "object-src 'none'", "base-uri 'none'"):
        assert directive in csp, f"CSP ขาด {directive}"
    assert "default-src 'self'" in csp
    assert "form-action 'self'" in csp


def test_static_assets_are_same_origin(client):
    """CSP เป็น 'self' ล้วน — asset ที่ชี้ออกนอกจะถูกบล็อก"""
    body = client.get("/").data.decode()
    external = re.findall(r'(?:src|href)="(https?://[^"]+)"', body)
    assert not external, f"asset ชี้ออกนอก origin: {external}"


# --- ส่วนที่ผูกกับ TLS: ปิดตอนยังไม่มี เปิดพร้อมกันตอนมี ---


def test_hsts_is_off_until_tls_exists(client):
    """เปิด HSTS ตอนยังรัน http = browser จำแล้วเข้าเว็บไม่ได้อีกเลย"""
    assert "Strict-Transport-Security" not in client.get("/login").headers


def test_https_flag_turns_on_hsts_and_redirect():
    app = create_app(HttpsTestConfig)
    resp = app.test_client().get("/login")
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("https://")

    secure = app.test_client().get("/login", base_url="https://localhost")
    assert "Strict-Transport-Security" in secure.headers


def test_https_flag_marks_session_cookie_secure():
    app = create_app(HttpsTestConfig)
    assert app.config["SESSION_COOKIE_SECURE"] is True


def test_session_cookie_is_http_only(client):
    """cookie อ่านจาก JS ไม่ได้ ลดผลของ XSS ถ้าหลุด"""
    assert client.application.config["SESSION_COOKIE_HTTPONLY"] is True


def test_session_cookie_is_samesite_lax(client):
    """กัน CSRF อีกชั้นนอกจาก token — cross-site POST ไม่ได้ cookie ไปด้วย"""
    assert client.application.config["SESSION_COOKIE_SAMESITE"] == "Lax"


def test_session_cookie_not_secure_without_tls(client):
    """ตั้ง Secure ตอนยังรัน http = cookie ไม่ถูกส่งเลย ล็อกอินไม่ติด"""
    assert client.application.config["SESSION_COOKIE_SECURE"] is False


# --- template ต้องไม่มี inline (ไม่งั้น CSP บล็อกเงียบ ๆ) ---


@pytest.mark.parametrize(
    "template", sorted(p.name for p in TEMPLATES.glob("*.html")), ids=lambda n: n
)
def test_template_has_no_inline_handler_or_style(template):
    text = (TEMPLATES / template).read_text()
    offenders = [
        f"line {n}: {line.strip()}"
        for n, line in enumerate(text.splitlines(), 1)
        if INLINE_HANDLER.search(line) or INLINE_STYLE.search(line)
    ]
    assert not offenders, f"{template} มี inline handler/style — CSP จะบล็อกเงียบ ๆ:\n" + "\n".join(
        offenders
    )


def test_behaviour_uses_data_attributes(client):
    """พฤติกรรมที่ย้ายออกจาก inline ต้องยังอยู่ครบในรูป data attribute"""
    client.post("/add", data={"title": "งานสำหรับตรวจ CSP"}, follow_redirects=True)
    body = client.get("/").data
    assert b"data-auto-submit" in body, "checkbox ติ๊กเสร็จต้อง submit เอง"
    assert b"data-confirm=" in body, "ปุ่มลบต้องถามยืนยัน"
    assert b"app.js" in body, "ต้องโหลดสคริปต์ที่ทำงานแทน inline handler"


def test_app_js_is_served(client):
    resp = client.get("/static/app.js")
    assert resp.status_code == 200
    assert b"data-confirm" in resp.data
