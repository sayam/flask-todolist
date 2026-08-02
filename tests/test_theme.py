"""เทสต์ stylesheet และ layout — ส่วนการเลือกโหมดอยู่ใน test_mode.py"""

import pathlib
import re

BASE_CSS = pathlib.Path(__file__).resolve().parent.parent / "app" / "static" / "base.css"


def _data_theme(resp):
    match = re.search(rb'<html[^>]*\sdata-theme="([a-z]+)"', resp.data)
    return match.group(1).decode() if match else None


# --- stylesheet ---


def test_base_stylesheet_is_linked_and_served(anon_client):
    assert b"base.css" in anon_client.get("/login").data
    resp = anon_client.get("/static/base.css")
    assert resp.status_code == 200
    assert b"var(--bg)" in resp.data


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


# --- หน้า login จัดกึ่งกลาง ---


def test_login_form_is_centered(anon_client):
    resp = anon_client.get("/login")
    assert b'class="auth"' in resp.data
    css = BASE_CSS.read_text()
    auth = _block_after(css, ".auth {")
    assert "justify-content: center" in auth
    assert "align-items: center" in auth


def test_quiet_buttons_beat_the_accent_rule():
    """ปุ่มใน nav และในแถวรายการต้องเป็นสีอ่อน

    กฎ button[type="submit"] มี specificity 0,1,1 ส่วน `nav button` มีแค่ 0,0,2
    ถ้าเขียนกฎสีอ่อนโดยไม่ระบุ [type="submit"] ด้วย มันจะแพ้และไม่มีผลอะไรเลย
    โดยไม่มี error ให้เห็น
    """
    css = BASE_CSS.read_text()
    for selector in ('nav button[type="submit"]', 'li button[type="submit"]'):
        assert selector in css, f"ขาด {selector} — จะแพ้ specificity ให้ button[type=submit]"


def test_task_row_is_a_flex_row():
    """แถวรายการต้องคุมการตัดบรรทัดเอง ไม่ปล่อยให้ browser ตัดตรงไหนก็ได้
    จนปุ่ม Delete หลุดไปอยู่บรรทัดของตัวเอง"""
    css = BASE_CSS.read_text()
    task = _block_after(css, ".task {")
    assert "display: flex" in task
    assert "flex-wrap: wrap" in task
    assert "gap:" in task


def test_task_row_markup_uses_layout_classes(client):
    """CSS จะทำงานได้ก็ต่อเมื่อ template ใส่ class ให้ครบ"""
    client.post(
        "/add",
        data={"title": "งานสำหรับตรวจ layout", "due_date": "2026-09-01T09:00"},
        follow_redirects=True,
    )
    body = client.get("/").data
    for css_class in (
        b'class="task"',
        b'class="task-title',
        b'class="task-when"',
        b'class="task-flag',
    ):
        assert css_class in body, f"ไม่พบ {css_class!r} ใน HTML"
