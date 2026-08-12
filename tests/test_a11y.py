"""a11y ชั้นโครงสร้าง — WCAG 2.2 AA baseline ที่ตรวจจาก HTML ได้ตรง ๆ

ชั้นนี้เร็วและรันได้ทุกที่ (ไม่ต้องมี browser) หน้าที่ของมันคือ **กันการถดถอย
ของ pattern ที่ตั้งไว้** ไม่ใช่แทน audit เต็มรูปแบบ
ของที่ต้องมี browser จริง (contrast จริงหลัง CSS, focus order, screen reader)
อยู่ในงาน audit ของ Phase 7 และ job pa11y ใน CI

อ้างอิงเกณฑ์: WCAG 2.2 AA (= ISO/IEC 40500:2025)
"""

import pathlib
import re

import pytest

PAGES = ["/login", "/", "/categories", "/settings", "/edit"]

CONTROL = r"<(?:input|select|textarea)\b[^>]*>"
# <label>…<input>…</label> — การผูกแบบ implicit ถูกต้องตาม HTML/WCAG พอ ๆ กับ for=
WRAPPING_LABEL = re.compile(r"<label\b(?![^>]*\sfor=)[^>]*>(.*?)</label>", re.DOTALL)


def _named_by_wrapping_label(html):
    """คืน set ของ control ที่อยู่ใน <label> ซึ่งไม่มี for= (ได้ชื่อจากการห่อ)"""
    return {tag for block in WRAPPING_LABEL.findall(html) for tag in re.findall(CONTROL, block)}


@pytest.fixture
def page(client, anon_client):
    """ดึง HTML ของหน้าใดก็ได้ — เลือก client ให้เหมาะกับหน้านั้นเอง

    `/edit` ต้องมีงานอยู่จริงก่อน จึงสร้างงานให้แล้วต่อ id เข้าไปเอง
    """

    def get(path):
        source = anon_client if path == "/login" else client
        if path == "/edit":
            client.post("/add", data={"title": "งานสำหรับตรวจ a11y"}, follow_redirects=True)
            todo_id = re.search(r"/edit/(\d+)", client.get("/").data.decode())
            assert todo_id, "ไม่พบลิงก์แก้ไขงานในหน้าแรก"
            path = todo_id.group(0)
        resp = source.get(path)
        assert resp.status_code == 200, f"{path} ตอบ {resp.status_code}"
        return resp.data.decode()

    return get


# --- 3.1.1 Language of Page ---


@pytest.mark.parametrize("path", PAGES)
def test_page_declares_its_language(page, path):
    """screen reader ต้องรู้ว่าจะออกเสียงภาษาอะไร"""
    assert re.search(r'<html[^>]*\slang="(en|th)"', page(path)), f"{path} ไม่ประกาศ lang"


def test_language_attribute_follows_the_chosen_locale(anon_client):
    assert 'lang="th"' in anon_client.get("/login?lang=th").data.decode()


# --- 2.4.2 Page Titled ---


@pytest.mark.parametrize("path", PAGES)
def test_page_has_a_non_empty_title(page, path):
    match = re.search(r"<title>(.*?)</title>", page(path), re.DOTALL)
    assert match, f"{path} ไม่มี <title>"
    assert match.group(1).strip(), f"{path} มี <title> แต่ว่าง"


# --- 1.1.1 Non-text Content ---


@pytest.mark.parametrize("path", PAGES)
def test_every_image_has_an_alt_attribute(page, path):
    """alt="" (decorative) ผ่าน แต่ "ไม่มี alt เลย" ไม่ผ่าน"""
    missing = [tag for tag in re.findall(r"<img\b[^>]*>", page(path)) if "alt=" not in tag]
    assert not missing, f"{path} มี <img> ที่ไม่มี alt: {missing}"


# --- 1.3.1 Info and Relationships / 4.1.2 Name, Role, Value ---


@pytest.mark.parametrize("path", PAGES)
def test_every_form_control_has_an_accessible_name(page, path):
    """ทุก input/select ต้องมีชื่อ — จาก <label for>, <label> ห่อ, aria-label
    หรือ aria-labelledby (ทั้งสี่ทางถูกต้องตาม WCAG เท่ากัน)"""
    html = page(path)
    labelled_ids = set(re.findall(r'<label[^>]*\sfor="([^"]+)"', html))
    wrapped = _named_by_wrapping_label(html)

    unnamed = []
    for tag in re.findall(CONTROL, html):
        if re.search(r'type="(hidden|submit|button)"', tag):
            continue
        has_aria = "aria-label=" in tag or "aria-labelledby=" in tag
        tag_id = re.search(r'\sid="([^"]+)"', tag)
        has_label = tag_id and tag_id.group(1) in labelled_ids
        if not (has_aria or has_label or tag in wrapped):
            unnamed.append(tag.strip())
    assert not unnamed, f"{path} มี control ที่ไม่มีชื่อให้ screen reader อ่าน:\n" + "\n".join(unnamed)


@pytest.mark.parametrize("path", PAGES)
def test_labels_point_at_controls_that_exist(page, path):
    """label ที่ชี้ไป id ที่ไม่มีอยู่ = ไม่มี label จริง แต่ดูเหมือนมี"""
    html = page(path)
    control_ids = set(re.findall(r'<(?:input|select|textarea)\b[^>]*\sid="([^"]+)"', html))
    dangling = [
        target
        for target in re.findall(r'<label[^>]*\sfor="([^"]+)"', html)
        if target not in control_ids
    ]
    assert not dangling, f"{path} มี label ชี้ไป id ที่ไม่มี: {dangling}"


def test_task_row_controls_are_named(client):
    """แถวรายการใช้ aria-label แทน label ที่มองเห็น — ต้องไม่หลุด"""
    client.post("/add", data={"title": "งานสำหรับตรวจ a11y"}, follow_redirects=True)
    html = client.get("/").data.decode()
    # เล็งเฉพาะ checkbox ติ๊กเสร็จในแถวงาน (ตัวที่ submit เอง) ไม่ใช่ตัวกรองด้านบน
    checkbox = re.search(r"<input[^>]*\bdata-auto-submit\b[^>]*>", html, re.DOTALL)
    assert checkbox, "ไม่พบ checkbox ของแถวงาน"
    assert "aria-label=" in checkbox.group(0)


# --- 2.1.1 Keyboard / ฟอร์มต้อง submit ได้โดยไม่ต้องพึ่ง JS ---

FORM = re.compile(r"(<form\b[^>]*>)(.*?)</form>", re.DOTALL | re.IGNORECASE)
SUBMIT = re.compile(
    r'<button\b(?![^>]*\stype="(?:button|reset)")[^>]*>|<input\b[^>]*\stype="(?:submit|image)"',
    re.IGNORECASE,
)


@pytest.mark.parametrize("path", PAGES)
def test_every_form_can_be_submitted_without_js(page, path):
    """ฟอร์มที่ไม่มีปุ่ม submit ใช้งานไม่ได้เลยเมื่อ JS ไม่ทำงาน
    (เคยหลุดมาแล้วกับฟอร์มติ๊กงานเสร็จ ที่พึ่ง data-auto-submit อย่างเดียว)"""
    orphans = [
        opening.strip() for opening, body in FORM.findall(page(path)) if not SUBMIT.search(body)
    ]
    assert not orphans, f"{path} มีฟอร์มที่ไม่มีปุ่ม submit:\n" + "\n".join(orphans)


def test_js_fallback_button_hides_only_when_js_runs(client):
    """ปุ่มสำรองต้องถูกซ่อนด้วยคลาส `js` ที่สคริปต์ติดให้ ไม่ใช่ซ่อนตายตัว —
    ไม่งั้นซ่อนแม้ตอน JS ใช้ไม่ได้ กลายเป็นฟอร์มที่ submit ไม่ได้"""
    css = client.get("/static/base.css").data.decode()
    assert ".js .js-hidden" in css, "ต้องซ่อนแบบมีเงื่อนไข ไม่ใช่ .js-hidden เปล่า ๆ"
    assert not re.search(r"(?<!\.js )\.js-hidden\s*\{[^}]*display:\s*none", css)

    js = client.get("/static/app.js").data.decode()
    assert 'classList.add("js")' in js, "app.js ต้องติดคลาส js ให้ <html>"


def test_script_is_not_deferred(client):
    """defer = คลาส `js` มาหลัง body render ปุ่มสำรองจะโผล่แวบหนึ่งแล้วหาย"""
    head = client.get("/").data.decode().split("</head>")[0]
    tag = re.search(r"<script[^>]*app\.js[^>]*>", head)
    assert tag, "app.js ต้องโหลดใน <head>"
    assert "defer" not in tag.group(0)
    assert "async" not in tag.group(0)


# --- 2.4.4 Link Purpose ---


@pytest.mark.parametrize("path", PAGES)
def test_links_have_discernible_text(page, path):
    """ลิงก์ที่ว่างเปล่า screen reader อ่านได้แค่ URL"""
    empty = [
        anchor
        for anchor, text in re.findall(r"(<a\b[^>]*>)(.*?)</a>", page(path), re.DOTALL)
        if not re.sub(r"<[^>]+>", "", text).strip()
        and "aria-label=" not in anchor
        and "<img" not in text
    ]
    assert not empty, f"{path} มีลิงก์ที่ไม่มีข้อความ: {empty}"


# --- 3.3.2 Labels or Instructions ---


def test_required_fields_are_marked_up(anon_client):
    """ช่องบังคับต้องบอกทั้งคนและ browser ผ่าน attribute required"""
    html = anon_client.get("/login").data.decode()
    for field in ("username", "password"):
        tag = re.search(rf'<input[^>]*\sid="{field}"[^>]*>', html)
        assert tag, f"ไม่พบช่อง {field}"
        assert "required" in tag.group(0), f"ช่อง {field} ไม่ได้ระบุ required"


# --- 1.4.x Contrast: ตรวจได้แค่ว่าตัวแปรครบ ค่าจริงต้องวัดด้วย browser ---


def test_disabled_control_is_not_the_only_signal(client):
    """ช่อง disabled ต้องมีข้อความอธิบายด้วย ไม่ใช่สื่อด้วยสีจาง ๆ อย่างเดียว
    (1.4.1 Use of Color)"""
    html = client.get("/settings").data.decode()
    assert "disabled" in html
    assert "cannot be changed" in html or "เปลี่ยนที่นี่ไม่ได้" in html


# --- สิ่งที่การตรวจด้วยมือของ P7-09 หาเจอ (ดู docs/ACCESSIBILITY-AUDIT.md) ---


def test_every_page_marks_where_the_main_content_starts(client, anon_client):
    """ต้องมี landmark ของเนื้อหาหลัก ไม่งั้นไม่มีทางข้าม nav ที่ซ้ำทุกหน้า

    WCAG 2.4.1 รับได้ทั้ง skip link และ landmark — เราเลือก landmark เพราะมัน
    ไม่เพิ่มอะไรบนจอ และคนที่ไม่ได้ใช้ screen reader จะไม่เจอลิงก์ที่งงว่าคืออะไร
    """
    for label, browser, path in (
        ("หน้าที่ login แล้ว", client, "/"),
        ("หน้า login", anon_client, "/login"),
    ):
        body = browser.get(path).data.decode()
        assert "<main>" in body, f"{label} ไม่มี landmark ของเนื้อหาหลัก"


def test_name_fields_say_what_they_are_for(client):
    """WCAG 1.3.5 — browser และตัวช่วยกรอกต้องรู้ว่าช่องนี้คืออะไรของผู้ใช้"""
    body = client.get("/settings").data.decode()
    for field, purpose in (("first_name", "given-name"), ("last_name", "family-name")):
        pattern = re.compile(rf'id="{field}"[^>]*autocomplete="{purpose}"')
        assert pattern.search(body), f"ช่อง {field} ยังไม่ได้บอกว่ามันคือ {purpose}"


def test_the_task_checkbox_is_big_enough_to_hit(app):
    """WCAG 2.5.8 — เป้าที่กดต้องไม่เล็กกว่า 24px

    checkbox ของ browser ไม่โตตามขนาดตัวอักษร (ราว 13px) จึงต้องกำหนดขนาดเอง
    ตรวจที่ CSS เพราะขนาดจริงบนจอวัดได้ต้องมี browser — และ `ci:a11y` ที่รัน
    Chromium จริงเป็นคนตรวจ contrast กับสิ่งที่วัดจากการ render (ดูสองชั้นใน ADR 0012)
    """
    css = (pathlib.Path(app.root_path) / "static" / "base.css").read_text(encoding="utf-8")
    block = re.search(r'\.task-toggle input\[type="checkbox"\]\s*\{([^}]*)\}', css)
    assert block, "ไม่เจอกฎที่กำหนดขนาดของ checkbox ในแถวงาน"
    for axis in ("width", "height"):
        found = re.search(rf"{axis}:\s*([\d.]+)rem", block.group(1))
        assert found, f"ไม่ได้กำหนด {axis} ของ checkbox"
        pixels = float(found.group(1)) * 16
        assert pixels >= 24, f"{axis} ของ checkbox = {pixels}px ซึ่งเล็กกว่าเกณฑ์ 24px"
