"""security headers ผ่าน Flask-Talisman

**CSP ไม่มี `unsafe-inline` โดยตั้งใจ** — พฤติกรรมฝั่ง client อยู่ใน
`static/app.js` ทั้งหมด และสไตล์อยู่ใน `base.css` + theme plugin
ถ้ามีใครใส่ `onclick=` หรือ `style=` กลับเข้า template browser จะบล็อกเงียบ ๆ
โดยไม่มี error ฝั่ง server — `tests/test_security_headers.py` จึงตรวจ template
ตรง ๆ อีกชั้นหนึ่ง

ส่วนที่ผูกกับ TLS (HSTS, บังคับ https, cookie `Secure`) ปิดไว้ก่อนและเปิด
พร้อมกันด้วย `HTTPS_ENABLED=1` ตอนมี reverse proxy จริงใน Phase 5 —
ถ้าเปิดตอนยังรัน http อยู่จะ redirect วนจน login ไม่ได้
"""

from flask_talisman import Talisman

talisman = Talisman()

# ทุกอย่างมาจาก origin เดียวกันหมด แอปไม่โหลด CDN ใด ๆ เลย
CONTENT_SECURITY_POLICY = {
    "default-src": "'self'",
    "script-src": "'self'",
    "style-src": "'self'",
    "img-src": "'self'",
    "font-src": "'self'",
    # ไม่มี XHR/websocket — ปิดไว้ก่อน เปิดเมื่อ API ฝั่ง browser มาจริง (Phase 3)
    "connect-src": "'self'",
    "form-action": "'self'",
    "base-uri": "'none'",
    "object-src": "'none'",
    "frame-ancestors": "'none'",
}


def init_security_headers(app):
    """ผูก Talisman เข้ากับแอป — ระดับความเข้มขึ้นกับว่ามี TLS แล้วหรือยัง"""
    https_enabled = app.config["HTTPS_ENABLED"]

    # ตั้งตรง ๆ ไม่พึ่ง Talisman ที่ตั้งให้ตอน before_request ของ request แรก —
    # config ควรบอกความจริงตั้งแต่ตอน start ไม่ใช่หลังมีคนเข้าเว็บแล้ว
    app.config["SESSION_COOKIE_SECURE"] = https_enabled
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    # Lax: cookie ไม่ถูกส่งไปกับ cross-site POST (กัน CSRF อีกชั้นนอกจาก token)
    # แต่ยังส่งตอนคลิกลิงก์เข้าเว็บเราตามปกติ
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    talisman.init_app(
        app,
        content_security_policy=CONTENT_SECURITY_POLICY,
        # ไม่ใช้ nonce เพราะไม่มี inline script เลย
        content_security_policy_nonce_in=None,
        force_https=https_enabled,
        strict_transport_security=https_enabled,
        session_cookie_secure=https_enabled,
        session_cookie_http_only=True,
        referrer_policy="strict-origin-when-cross-origin",
        # frame-ancestors ใน CSP ครอบงานนี้แล้ว X-Frame-Options เป็นของเก่า
        frame_options=None,
    )
