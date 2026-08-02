"""เทสต์สถาปัตยกรรม plugin

หัวใจของเทสต์ชุดนี้คือ **core ต้องไม่รู้จัก plugin ตัวไหนเป็นการเฉพาะ**
เทสต์ส่วนใหญ่จึงสร้าง/ลบธีมชั่วคราวจริง ๆ บนดิสก์ แล้วดูว่าระบบตอบสนองถูกต้อง
โดยไม่มีการแก้โค้ด core เลย
"""

import json
import pathlib
import re
import shutil

import pytest

from app import db, plugins
from app.models import User
from tests.conftest import PASSWORD

THEMES_DIR = plugins.PLUGIN_ROOT / plugins.THEME_TYPE
BASE_CSS = pathlib.Path(__file__).resolve().parent.parent / "app" / "static" / "base.css"

PALETTE_BLOCKS = (":root", ':root[data-theme="dark"]')


@pytest.fixture
def temp_theme():
    """สร้างธีมชั่วคราวบนดิสก์แล้วเก็บกวาดให้หลังเทสต์จบ

    จำลองการ "วางไดเรกทอรีลงไป" กับ "ลบทิ้ง" ซึ่งเป็นวิธีเพิ่ม/ถอน plugin จริง
    """
    created = []

    def make(theme_id, manifest=None, css=None):
        directory = THEMES_DIR / theme_id
        directory.mkdir(parents=True)
        created.append(directory)
        (directory / "plugin.json").write_text(
            json.dumps(
                manifest
                if manifest is not None
                else {
                    "type": "theme",
                    "name": theme_id.title(),
                    "version": "1.0.0",
                    "stylesheet": "theme.css",
                }
            )
        )
        if css is not False:
            (directory / "theme.css").write_text(css or ":root { --bg: #123456; }\n")
        return directory

    yield make
    for directory in created:
        shutil.rmtree(directory, ignore_errors=True)


# --- การค้นหา plugin ---


def test_core_theme_is_installed():
    assert plugins.core_theme().id == plugins.CORE_THEME


def test_core_theme_is_marked_undeletable():
    assert plugins.core_theme().is_core is True


def test_extra_theme_ships_with_the_app():
    """ต้องมีอย่างน้อยสองธีมถึงจะ toggle ได้จริง"""
    assert len(plugins.themes()) >= 2


def test_added_theme_is_found_without_touching_core(temp_theme):
    """วางไดเรกทอรีลงไปแล้วต้องเจอทันที ไม่ต้องแก้ config หรือ restart"""
    assert "sunset" not in plugins.themes()
    temp_theme("sunset")
    assert "sunset" in plugins.themes()
    assert plugins.themes()["sunset"].name == "Sunset"


def test_removed_theme_disappears(temp_theme):
    directory = temp_theme("sunset")
    assert "sunset" in plugins.themes()
    shutil.rmtree(directory)
    assert "sunset" not in plugins.themes()


def test_directory_without_manifest_is_ignored():
    (THEMES_DIR / "__pycache__").mkdir(exist_ok=True)
    try:
        assert "__pycache__" not in plugins.themes()
    finally:
        shutil.rmtree(THEMES_DIR / "__pycache__", ignore_errors=True)


def test_broken_manifest_raises(temp_theme):
    directory = THEMES_DIR / "broken"
    directory.mkdir()
    try:
        (directory / "plugin.json").write_text("{ นี่ไม่ใช่ json")
        with pytest.raises(plugins.PluginError):
            plugins.themes()
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_installation_check_catches_missing_stylesheet(temp_theme):
    temp_theme("sunset", css=False)
    with pytest.raises(plugins.PluginError, match="ไม่พบไฟล์"):
        plugins.check_installation()


def test_plugin_cannot_reach_outside_its_directory():
    theme = plugins.core_theme()
    with pytest.raises(plugins.PluginError):
        theme.file("../../../etc/passwd")


# --- core ไม่ hardcode ชื่อธีม ---


def test_core_config_does_not_list_themes():
    """ถ้า config ยังประกาศธีมไว้ แปลว่าเพิ่มธีมต้องแก้ core"""
    config_source = (pathlib.Path(__file__).resolve().parent.parent / "config.py").read_text()
    assert "THEMES = {" not in config_source


def test_core_python_does_not_name_the_extra_theme():
    """ชื่อธีมที่ไม่ใช่ core ต้องไม่โผล่ในโค้ด core เลย"""
    app_dir = pathlib.Path(__file__).resolve().parent.parent / "app"
    offenders = []
    for path in app_dir.rglob("*.py"):
        if plugins.PLUGIN_ROOT in path.parents or path == plugins.PLUGIN_ROOT / "__init__.py":
            continue
        if "ocean" in path.read_text().lower():
            offenders.append(str(path))
    assert not offenders, f"core อ้างชื่อธีมเฉพาะตัว: {offenders}"


# --- แต่ละธีมต้องกำหนดสีครบ ---


def _declarations(css, selector):
    start = css.index(selector) + len(selector)
    start = css.index("{", start) + 1
    depth, i = 1, start
    while depth:
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
        i += 1
    return dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", css[start : i - 1]))


def test_every_theme_defines_the_same_variables():
    """ธีมที่กำหนดตัวแปรไม่ครบจะทำให้มีสีตกค้างจากธีมก่อนหน้า"""
    reference = None
    for theme in plugins.themes().values():
        css = theme.file(theme.stylesheet).read_text()
        for selector in PALETTE_BLOCKS:
            names = set(_declarations(css, selector))
            assert names, f"{theme.id}: บล็อก {selector} ว่าง"
            if reference is None:
                reference = names
            assert names == reference, (
                f"{theme.id} บล็อก {selector} ตัวแปรไม่ตรงกับธีมอื่น: {names ^ reference}"
            )


def test_theme_colour_values_are_valid_hex():
    for theme in plugins.themes().values():
        css = theme.file(theme.stylesheet).read_text()
        for selector in PALETTE_BLOCKS:
            for name, raw_value in _declarations(css, selector).items():
                value = raw_value.strip()
                if value.startswith("#"):
                    assert re.fullmatch(r"#[0-9a-fA-F]{3,8}", value), (
                        f"{theme.id} {name} = {value!r}"
                    )


def test_base_css_has_no_raw_colours():
    """สีต้องมาจากธีมทั้งหมด base.css ต้องอ้าง var() อย่างเดียว"""
    leaked = re.findall(r"#[0-9a-fA-F]{3,8}\b", BASE_CSS.read_text())
    assert not leaked, f"พบสีดิบใน base.css: {leaked}"


# --- ใช้งานผ่านเว็บ ---


def test_stylesheet_of_each_theme_is_served(anon_client):
    for theme_id in plugins.themes():
        resp = anon_client.get(f"/plugin/themes/{theme_id}/style.css")
        assert resp.status_code == 200, theme_id
        assert resp.mimetype == "text/css"
        assert b"--bg" in resp.data


def test_unknown_theme_stylesheet_is_404(anon_client):
    assert anon_client.get("/plugin/themes/nope/style.css").status_code == 404


def test_stylesheet_route_blocks_traversal(anon_client):
    assert anon_client.get("/plugin/themes/..%2f..%2fconfig/style.css").status_code == 404


def test_page_links_base_then_theme(anon_client):
    body = anon_client.get("/login").data.decode()
    assert body.index("base.css") < body.index("/plugin/themes/"), (
        "ธีมต้องโหลดหลัง base.css ไม่งั้นทับสีไม่ได้"
    )


def test_settings_lists_every_installed_theme(client, temp_theme):
    temp_theme("sunset")
    body = client.get("/settings").data
    for theme_id in plugins.themes():
        assert f'value="{theme_id}"'.encode() in body


def test_switching_theme_changes_the_stylesheet(app, client, user_id, temp_theme):
    temp_theme("sunset")
    client.post(
        "/settings/preferences",
        data={"locale": "en", "theme": "sunset", "mode": "light", "timezone": "Asia/Bangkok"},
        follow_redirects=True,
    )
    assert b"/plugin/themes/sunset/style.css" in client.get("/").data
    with app.app_context():
        assert db.session.get(User, user_id).theme == "sunset"


def test_removing_a_theme_falls_back_to_core(app, client, user_id, temp_theme):
    """ถอน plugin ทิ้งแล้วระบบต้องไม่พัง คนที่เลือกไว้ตกกลับไปใช้ธีม core"""
    directory = temp_theme("sunset")
    client.post(
        "/settings/preferences",
        data={"locale": "en", "theme": "sunset", "mode": "light", "timezone": "Asia/Bangkok"},
        follow_redirects=True,
    )
    shutil.rmtree(directory)

    fresh = app.test_client()
    fresh.post("/login", data={"username": "tester", "password": PASSWORD})
    resp = fresh.get("/")
    assert resp.status_code == 200
    assert f"/plugin/themes/{plugins.CORE_THEME}/style.css".encode() in resp.data


def test_settings_rejects_a_theme_that_is_not_installed(app, client, user_id):
    resp = client.post(
        "/settings/preferences",
        data={"locale": "en", "theme": "nope", "mode": "light", "timezone": "Asia/Bangkok"},
        follow_redirects=True,
    )
    assert b"Unsupported theme" in resp.data
    with app.app_context():
        assert db.session.get(User, user_id).theme is None
