"""หน้า `/privacy` (PDPA ม.23) — อ่านได้โดยไม่ login และตัวเลขตรงกับโค้ดจริง

หลักเดียวกับ `tests/test_ropa.py`: ตัวเลขระยะเก็บรักษาบนหน้า ต้องเป็นตัวเลข
เดียวกับที่ purge job ใช้จริง — เอกสาร (หรือหน้าเว็บ) ที่บอก 30 วันขณะที่โค้ด
ลบที่ 60 คือคำสัญญาต่อผู้ใช้ที่ไม่มีใครรักษา
"""

from app.purge import AUDIT_RETAIN_DAYS, PURGE_AFTER_DAYS


def test_the_privacy_page_needs_no_login(app):
    """privacy notice ต้องอ่านได้ก่อนตัดสินใจใช้ — จึงต้องไม่อยู่หลังด่าน login"""
    client = app.test_client()
    resp = client.get("/privacy")
    assert resp.status_code == 200


def test_retention_numbers_come_from_the_code(app):
    """เลขบนหน้า = เลขที่ purge ใช้จริง — ถอด commit ของค่าคงที่แล้วหน้าต้องเปลี่ยนตาม"""
    page = app.test_client().get("/privacy").data.decode()
    assert str(PURGE_AFTER_DAYS) in page, "ระยะ purge บนหน้าไม่ตรงกับ app/purge.py"
    assert str(AUDIT_RETAIN_DAYS) in page, "ระยะเก็บ audit บนหน้าไม่ตรงกับ app/purge.py"


def test_the_page_states_the_rights_pdpa_cares_about(app):
    """สิทธิ์หลัก (สำเนา · ลบ · แก้) ต้องถูกพูดถึง — นี่คือใจของ ม.23/30/33/35"""
    page = app.test_client().get("/privacy").data.decode()
    for word in ("JSON", "Close your account", "Correct"):
        assert word in page, f"หน้า privacy ไม่พูดถึง: {word}"


def test_the_footer_links_to_the_privacy_page(app):
    """ลิงก์ต้องหาเจอจากหน้าแรกที่คนยังไม่ login เห็น — มีหน้าแต่หาไม่เจอ = ไม่มี"""
    page = app.test_client().get("/login").data.decode()
    assert "/privacy" in page


def _back_href(page_bytes):
    """href ของ*ปุ่มกลับโดยเฉพาะ* — ห้ามเทียบกับทั้งหน้า เพราะโลโก้ก็ href="/"

    (mutation จับได้: เวอร์ชันแรกเทียบทั้งหน้า แล้วผ่านทั้งที่ถอดการเช็ค host
    ออก — assertion ที่กว้างกว่า element ที่ทดสอบคือ assertion ที่ไม่ทดสอบอะไร)
    """
    import re

    match = re.search(r'class="button" href="([^"]*)">&larr;', page_bytes.decode())
    assert match, "ไม่พบปุ่มกลับบนหน้า privacy"
    return match.group(1)


def test_the_back_button_returns_where_you_came_from_safely(app, client):
    """Change Req #1 ข้อ 1 — สองทิศ: referrer ในเว็บถูกใช้ · นอกเว็บ/ชี้ตัวเอง
    ต้องตกไป fallback ไม่ใช่กลายเป็น open redirect"""
    page = client.get("/privacy", headers={"Referer": "http://localhost/settings"})
    assert _back_href(page.data) == "/settings", "referrer ในเว็บต้องถูกใช้เป็นปุ่มกลับ"

    evil = client.get("/privacy", headers={"Referer": "https://evil.example.com/settings"})
    assert _back_href(evil.data) == "/", "referrer นอกเว็บต้องตก fallback เป๊ะ ๆ ไม่ใช่ค่าที่แปลงมา"

    tricky = client.get("/privacy", headers={"Referer": "http://localhost/../../evil"})
    assert _back_href(tricky.data) == "/", "referrer พิลึกต้องตก fallback"

    selfref = client.get("/privacy", headers={"Referer": "http://localhost/privacy"})
    assert _back_href(selfref.data) == "/", "referrer ชี้ตัวเองต้องตก fallback ไม่วนลูป"


def test_the_back_button_falls_back_to_login_for_anonymous_visitors(app):
    page = app.test_client().get("/privacy")
    assert _back_href(page.data) == "/login", "คนยังไม่ login กดกลับควรไปหน้า login"
