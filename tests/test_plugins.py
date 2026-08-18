"""เทสต์สถาปัตยกรรม plugin

หัวใจของเทสต์ชุดนี้คือ **core ต้องไม่รู้จัก plugin ตัวไหนเป็นการเฉพาะ**
เทสต์ส่วนใหญ่จึงสร้าง/ลบธีมชั่วคราวจริง ๆ บนดิสก์ แล้วดูว่าระบบตอบสนองถูกต้อง
โดยไม่มีการแก้โค้ด core เลย
"""

import ast
import functools
import importlib.metadata
import json
import pathlib
import re
import shutil
import sys

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
                    "migration": "live",  # ADR 0041 — manifest ที่ไม่ประกาศ = ไม่ start
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


# --- plugin ที่มีข้อมูลของตัวเอง (Phase 4 — ADR 0023) ---

TOTP_KEY = "auth/totp"
QR_KEY = "auth/totp#qr-segno"


@pytest.fixture
def data_plugin():
    """plugin ชั่วคราวที่ประกาศตารางของตัวเอง แล้วเก็บกวาด metadata ให้ด้วย

    ต้องถอนตารางออกจาก `db.metadata` เองหลังเทสต์จบ ไม่งั้นมันจะค้างอยู่ตลอด
    อายุ process แล้วไปโผล่ใน `db.create_all()` ของเทสต์ตัวถัดไป
    """
    created = []

    def make(plugin_id, table_name):
        directory = plugins.PLUGIN_ROOT / "auth" / plugin_id
        directory.mkdir(parents=True)
        created.append((directory, table_name))
        (directory / "plugin.json").write_text(
            json.dumps({"type": "auth", "name": plugin_id, "migration": "warm"})
        )
        (directory / "models.py").write_text(
            "from sqlalchemy.orm import Mapped, mapped_column\n"
            "from app import db\n\n\n"
            f"class Temp(db.Model):\n"
            f'    __tablename__ = "{table_name}"\n'
            "    id: Mapped[int] = mapped_column(primary_key=True)\n"
        )
        plugins.forget_models()
        return directory

    yield make

    for directory, table_name in created:
        shutil.rmtree(directory, ignore_errors=True)
        table = db.metadata.tables.get(table_name)
        if table is not None:
            db.metadata.remove(table)
    plugins.forget_models()


def test_a_plugin_owns_the_tables_it_declares(app):
    with app.app_context():
        plugin = plugins.find(TOTP_KEY)
        assert plugins.tables_of(plugin) == {"tdl_auth_totp_secret"}


def test_core_tables_are_not_owned_by_any_plugin(app):
    """ตารางของ core ต้องไม่หลุดเข้าไปในรายการของ plugin (ไม่งั้น migration จะเมินมัน)"""
    with app.app_context():
        assert "tdl_user" not in plugins.owned_tables()
        assert "tdl_todo" not in plugins.owned_tables()


def test_installing_and_uninstalling_creates_and_drops_the_table(app):
    """ถอน plugin แล้วข้อมูลของมันหายไปจริง ไม่ใช่ค้างอยู่โดยไม่มีใครดูแล"""
    from sqlalchemy import inspect

    with app.app_context():
        plugin = plugins.find(TOTP_KEY)
        plugins.uninstall(plugin)
        assert "tdl_auth_totp_secret" not in inspect(db.engine).get_table_names()

        plugins.install(plugin)
        assert "tdl_auth_totp_secret" in inspect(db.engine).get_table_names()


def test_a_table_without_the_right_prefix_is_refused(app, data_plugin):
    """ชื่อที่ไม่มี prefix ของ plugin = แยกไม่ออกว่าเป็นของใครตอนถอน"""
    data_plugin("badname", "tdl_something_else")
    with app.app_context(), pytest.raises(plugins.PluginError, match="ขึ้นต้นด้วย"):
        plugins.load_models()


def test_dropping_in_a_plugin_with_tables_needs_no_core_change(app, data_plugin):
    data_plugin("extra", "tdl_auth_extra_thing")
    with app.app_context():
        assert plugins.tables_of(plugins.find("auth/extra")) == {"tdl_auth_extra_thing"}
        assert "tdl_auth_extra_thing" in plugins.owned_tables()


# --- ส่วนเสริมของ plugin (Phase 4.5 — ADR 0025) ---
# กติกาเดิม ("ไดเรกทอรีที่มี plugin.json = จุด plug") ใช้ซ้อนอีกชั้น
# สิ่งที่ต้องพิสูจน์: ถอดส่วนเสริมออกแล้ว plugin แม่ยังทำงาน และเมื่อกำกวมต้องปิดไว้ก่อน


@pytest.fixture
def host_plugin():
    """plugin แม่ชั่วคราวหนึ่งตัว พร้อมฟังก์ชันสร้างส่วนเสริมให้มัน"""
    directory = plugins.PLUGIN_ROOT / "auth" / "hosty"
    (directory / "enhancements").mkdir(parents=True)
    (directory / "plugin.json").write_text(
        json.dumps({"type": "auth", "name": "hosty", "migration": "warm"})
    )

    def add(enhancement_id, manifest=None, body="VALUE = 'ok'\n"):
        target = directory / "enhancements" / enhancement_id
        target.mkdir(parents=True)
        (target / "plugin.json").write_text(
            json.dumps(
                manifest if manifest is not None else {"name": enhancement_id, "provides": "thing"}
            )
        )
        if body is not None:
            (target / "provide.py").write_text(body)
        return target

    yield add
    shutil.rmtree(directory, ignore_errors=True)
    plugins.forget_models()


def test_an_enhancement_is_found_under_its_host(app, host_plugin):
    host_plugin("basic")
    with app.app_context():
        host = plugins.find("auth/hosty")
        found = plugins.enhancements(host)
        assert list(found) == ["basic"]
        assert found["basic"].key == "auth/hosty#basic"
        assert found["basic"].host is host
        assert plugins.category_of(found["basic"]) == "plugin-auth-hosty-basic"


def test_the_host_asks_for_a_capability_not_for_an_id(app, host_plugin):
    host_plugin("basic", body="def render():\n    return 'จากส่วนเสริม'\n")
    with app.app_context():
        module = plugins.capability(plugins.find("auth/hosty"), "thing")
        assert module is not None
        assert module.render() == "จากส่วนเสริม"


def test_removing_the_directory_removes_the_capability(app, host_plugin):
    """หัวใจของทั้งเฟส: ถอดไดเรกทอรีทิ้งแล้ว host ต้องไม่พัง แค่ไม่มีความสามารถนั้น"""
    directory = host_plugin("basic")
    with app.app_context():
        assert plugins.capability(plugins.find("auth/hosty"), "thing") is not None

    shutil.rmtree(directory)
    with app.app_context():
        assert plugins.capability(plugins.find("auth/hosty"), "thing") is None


def test_an_enhancement_without_its_library_is_skipped(app, host_plugin):
    host_plugin("needy", manifest={"provides": "thing", "requires": {"pip": ["ไม่มีจริง"]}})
    with app.app_context():
        host = plugins.find("auth/hosty")
        assert plugins.enhancements(host)  # ยังค้นเจอ
        assert plugins.usable_enhancements(host) == []  # แต่ใช้ไม่ได้
        assert plugins.capability(host, "thing") is None


def test_an_import_error_disables_the_enhancement_instead_of_raising(app, host_plugin):
    """ไลบรารีหายตอน import = ปิดตัวเอง (ด่านสำรองของการเช็ค requires)"""
    host_plugin("broken", body="import ไม่มีโมดูลนี้จริง\n")
    with app.app_context():
        assert plugins.capability(plugins.find("auth/hosty"), "thing") is None


def test_other_errors_in_an_enhancement_are_loud(app, host_plugin):
    """บั๊กของ plugin (ไม่ใช่ไลบรารีขาด) ต้องดังให้ได้ยิน ไม่ใช่ถูกกลืน"""
    host_plugin("bad", body="raise ValueError('พังตั้งแต่ import')\n")
    with app.app_context(), pytest.raises(ValueError, match="พังตั้งแต่ import"):
        plugins.capability(plugins.find("auth/hosty"), "thing")


def test_two_providers_without_a_pick_are_both_disabled(app, host_plugin):
    """กำกวม = ปิดไว้ก่อน — การเดาให้แปลว่าวางไดเรกทอรีเพิ่มแล้วพฤติกรรมเปลี่ยนเอง"""
    host_plugin("one")
    host_plugin("two")
    with app.app_context():
        assert plugins.capability(plugins.find("auth/hosty"), "thing") is None


def test_a_pick_chooses_between_two_providers(app, host_plugin):
    host_plugin("one", body="WHICH = 'one'\n")
    host_plugin("two", body="WHICH = 'two'\n")
    with app.app_context():
        app.config["PLUGIN_PICKS"] = {"auth/hosty#thing": "two"}
        module = plugins.capability(plugins.find("auth/hosty"), "thing")
        assert module is not None
        assert module.WHICH == "two"


def test_a_pick_that_names_nothing_real_is_still_fail_closed(app, host_plugin):
    host_plugin("one")
    host_plugin("two")
    with app.app_context():
        app.config["PLUGIN_PICKS"] = {"auth/hosty#thing": "ไม่มีตัวนี้"}
        assert plugins.capability(plugins.find("auth/hosty"), "thing") is None


def test_the_one_left_standing_does_not_get_promoted_over_a_pick(app, host_plugin):
    """ตัวที่ผู้ดูแล **ไม่ได้เลือก** ต้องไม่ถูกเลื่อนขึ้นมาแทนเงียบ ๆ

    เกิดได้จริงตอนที่ตัวที่ถูกเลือกไว้ถูกปิดเพราะ CVE หรือไลบรารีหายไป
    ถ้าเหลือตัวเดียวแล้วใช้เลย = การปิดตัวหนึ่งกลายเป็นการ **เปิด** อีกตัวหนึ่ง
    ซึ่งไม่มีใครสั่ง (นี่คือสิ่งเดียวกับที่กฎ fail closed มีไว้ป้องกัน)
    """
    host_plugin("chosen")
    host_plugin("other", body="WHICH = 'other'\n")
    with app.app_context():
        app.config["PLUGIN_PICKS"] = {"auth/hosty#thing": "chosen"}
        app.config["DISABLED_PLUGINS"] = frozenset({"auth/hosty#chosen"})
        assert plugins.capability(plugins.find("auth/hosty"), "thing") is None


def test_a_pick_still_applies_when_only_one_provider_is_installed(app, host_plugin):
    host_plugin("chosen", body="WHICH = 'chosen'\n")
    with app.app_context():
        app.config["PLUGIN_PICKS"] = {"auth/hosty#thing": "chosen"}
        module = plugins.capability(plugins.find("auth/hosty"), "thing")
        assert module is not None
        assert module.WHICH == "chosen"


def test_an_enhancement_that_fails_to_load_stays_broken(app, host_plugin):
    """โมดูลที่ exec ไม่จบต้องไม่ค้างใน sys.modules ให้ครั้งถัดไปได้ของครึ่ง ๆ

    เส้นทางนี้เป็นเรื่องปกติของส่วนเสริม เพราะ `ImportError` ถูกกลืนไว้เป็น
    การปิดตัวเอง — ถ้าไม่ถอนออก ครั้งแรกได้ None ครั้งที่สองได้โมดูลเปล่า
    ที่ไม่มีฟังก์ชันอะไรเลย แล้ว host จะพังตอนเรียกใช้
    """
    host_plugin("broken", body="import ไม่มีโมดูลนี้จริง\n\ndef render(text):\n    return text\n")
    with app.app_context():
        host = plugins.find("auth/hosty")
        assert plugins.capability(host, "thing") is None
        assert plugins.capability(host, "thing") is None, "ครั้งที่สองต้องยังปิดอยู่"


def test_an_enhancement_may_not_own_data(app, host_plugin):
    """ส่วนเสริมที่มีข้อมูลของตัวเอง = สลับ implementation กลายเป็นย้ายข้อมูล"""
    directory = host_plugin("greedy")
    (directory / "models.py").write_text("# ห้ามมีไฟล์นี้\n")
    with app.app_context(), pytest.raises(plugins.PluginError, match="ส่วนเสริมห้ามมี"):
        plugins.enhancements(plugins.find("auth/hosty"))


def test_find_reaches_an_enhancement_by_key(app, host_plugin):
    host_plugin("basic")
    with app.app_context():
        assert plugins.find("auth/hosty#basic") is not None
        assert plugins.find("auth/hosty#ไม่มี") is None


def test_a_plugin_can_point_at_itself_without_naming_itself(app, host_plugin):
    """โค้ดของ plugin ต้องอ้างถึงตัวเองได้โดยไม่เขียนไอดีของตัวเองเป็นสตริง

    ไอดีที่เขียนไว้ในโค้ดจะกลายเป็นค่าที่ผิดเงียบ ๆ วันที่มีคนเปลี่ยนชื่อไดเรกทอรี
    (ความสามารถหายไปโดยไม่มีอะไรฟ้อง)
    """
    enhancement = host_plugin("basic")
    directory = plugins.PLUGIN_ROOT / "auth" / "hosty"
    with app.app_context():
        assert plugins.plugin_of(str(directory / "factor.py")).key == "auth/hosty"
        # ส่วนเสริมก็ต้องหาตัวเองเจอ ไม่งั้นมันเรียก `plugin_of(__file__)` ไม่ได้
        assert plugins.plugin_of(str(enhancement / "provide.py")).key == "auth/hosty#basic"
        assert plugins.plugin_of(str(plugins.PLUGIN_ROOT / "nowhere" / "x.py")) is None


@pytest.mark.plugin_deps
def test_the_shipped_qr_is_plugged_in_as_an_enhancement(app):
    """ของจริง: QR ต้องมาจากส่วนเสริม ไม่ได้อยู่ในตัว plugin แล้ว

    ต้องมีไลบรารีของส่วนเสริมติดตั้งอยู่ถึงจะจริง — ไม่มีไลบรารี = ส่วนเสริม
    ปิดตัวเอง ซึ่งเป็นสถานะที่ถูกต้อง (job `bare` เป็นคนพิสูจน์ฝั่งนั้น)
    """
    with app.app_context():
        totp = plugins.find(TOTP_KEY)
        assert plugins.capability(totp, "qr") is not None
        assert callable(plugins.capability(totp, "qr").render)
        # และตัว plugin เองต้องไม่ import ไลบรารีของส่วนเสริมอีกแล้ว
        source = (totp.directory / "factor.py").read_text(encoding="utf-8")
        assert "segno" not in source


def test_plug_points_covers_every_level(app, host_plugin):
    host_plugin("basic")
    with app.app_context():
        keys = {point.key for point in plugins.plug_points()}
    assert {"auth/totp", "auth/hosty", "auth/hosty#basic"} <= keys


# --- dependency ของ plugin (Phase 4.5 — ADR 0025) ---
# สิ่งที่ต้องพิสูจน์คือคำว่า ถอด plugin แล้ว supply chain ของมันหายไปด้วย
# ซึ่งจะจริงก็ต่อเมื่อไลบรารีของ plugin **ไม่ได้อยู่ใน `[packages]` ของ core**

PIPFILE = pathlib.Path(__file__).resolve().parent.parent / "Pipfile"


def _pipfile():
    import tomllib

    return tomllib.loads(PIPFILE.read_text(encoding="utf-8"))


def test_a_plugin_declares_the_libraries_it_needs(app):
    with app.app_context():
        # ตั้งแต่ ADR 0046 ตัว plugin พึ่ง cryptography เอง (encrypt ความลับ at rest)
        # — ก่อนหน้านั้นของที่พึ่งมีแต่ในส่วนเสริม
        assert plugins.requirements(plugins.find(TOTP_KEY)) == ["cryptography~=50.0"]
        assert plugins.requirements(plugins.find(QR_KEY)) == ["segno~=1.6"]
        assert plugins.requirements(plugins.find("themes/system")) == []


def test_the_category_name_is_derived_from_the_key(app):
    """ชื่อ category ห้ามให้ manifest ประกาศเอง — ค่าที่ประกาศซ้ำได้คือค่าที่จะไม่ตรงกัน"""
    with app.app_context():
        assert plugins.category_of(plugins.find(TOTP_KEY)) == "plugin-auth-totp"
        assert plugins.category_of(plugins.find(QR_KEY)) == "plugin-auth-totp-qr-segno"


def test_no_pipenv_category_outlives_the_plug_point_that_needed_it(app):
    """category ที่ไม่มีจุด plug ไหนขอแล้ว = supply chain ที่ยังถูกติดตั้งทุก deploy

    เจอมาแล้วตอนย้าย QR ลงไปเป็นส่วนเสริม: `pipenv lock` **ไม่ลบ** category เก่า
    ที่หายไปจาก Pipfile ออกจาก Pipfile.lock ให้ ต้องลบเอง
    """
    import json

    with app.app_context():
        # เฉพาะจุด plug ที่**ประกาศไลบรารีจริง** — จุดที่ไม่พึ่งอะไรเลยไม่ควรมี
        # หมวดของตัวเองค้างอยู่ (ซึ่งคือกรณีของ auth/totp หลังย้าย QR ออกไป)
        wanted = {
            plugins.category_of(point)
            for point in plugins.plug_points()
            if plugins.requirements(point)
        }
    lock = json.loads((PIPFILE.parent / "Pipfile.lock").read_text(encoding="utf-8"))
    for source, name in ((_pipfile(), "Pipfile"), (lock, "Pipfile.lock")):
        orphans = {key for key in source if key.startswith("plugin-")} - wanted
        assert not orphans, f"{name} มีหมวดที่ไม่มีใครขอแล้ว: {sorted(orphans)}"


def test_no_plugin_library_sits_in_the_core_packages(app):
    """**ด่านหลักของ ADR 0025** — ไลบรารีที่ plugin เดียวใช้ต้องไม่อยู่ใน [packages]

    ถ้ามันอยู่ตรงนั้น การลบไดเรกทอรี plugin ทิ้งจะถอดได้แค่โค้ด ส่วนไลบรารียัง
    ถูกติดตั้งทุก deploy ยังอยู่ใน SBOM และยังต้องเฝ้า CVE ต่อไป
    """
    core_packages = {name.lower() for name in _pipfile().get("packages", {})}
    with app.app_context():
        offenders = [
            (plugin.key, requirement)
            for plugin in plugins.plug_points()
            for requirement in plugins.requirements(plugin)
            if plugins.distribution_name(requirement).lower() in core_packages
        ]
    assert not offenders, f"ไลบรารีของ plugin ไปอยู่ใน [packages] ของ core: {offenders}"


def test_every_declared_library_has_a_matching_pipfile_category(app):
    """สิ่งที่ manifest ประกาศ ต้องตรงกับสิ่งที่ Pipfile ติดตั้งจริง

    สองที่นี้แยกกันอยู่โดยธรรมชาติ (ไฟล์คนละไฟล์ คนละเครื่องมือ) ถ้าไม่มีอะไร
    ผูกไว้ วันหนึ่งจะมี manifest ที่ประกาศของที่ไม่มีใครติดตั้งให้
    """
    pipfile = _pipfile()
    with app.app_context():
        for plugin in plugins.plug_points():
            needed = plugins.requirements(plugin)
            if not needed:
                continue
            category = plugins.category_of(plugin)
            assert category in pipfile, f"Pipfile ไม่มีหมวด [{category}] ของ {plugin.key}"
            listed = {name.lower() for name in pipfile[category]}
            for requirement in needed:
                assert plugins.distribution_name(requirement).lower() in listed, (
                    f"{plugin.key} ประกาศ {requirement} แต่ [{category}] ไม่มี"
                )


def test_a_library_that_is_not_installed_is_reported(app, data_plugin):
    directory = data_plugin("needy", "tdl_auth_needy_thing")
    (directory / "plugin.json").write_text(
        json.dumps(
            {
                "type": "auth",
                "name": "needy",
                "migration": "warm",
                "requires": {"pip": ["ไม่มีแพ็กเกจนี้จริง"]},
            }
        )
    )
    with app.app_context():
        plugin = plugins.find("auth/needy")
        assert plugins.missing_requirements(plugin) == ["ไม่มีแพ็กเกจนี้จริง"]
        # ตัวเทียบ "ครบ" ต้องเป็น plugin ที่ไม่ประกาศไลบรารีเลย — totp ใช้ไม่ได้
        # อีกแล้วตั้งแต่ ADR 0046 เพราะใน job bare มันขาด cryptography จริง ๆ
        assert plugins.missing_requirements(plugins.find("themes/system")) == []


def test_plugin_deps_lists_what_each_plugin_needs(app):
    result = app.test_cli_runner().invoke(args=["plugin-deps"])
    assert result.exit_code == 0, result.output
    assert "segno" in result.output
    assert "plugin-auth-totp" in result.output
    assert "no libraries" in result.output, "plugin ที่ไม่พึ่งอะไรต้องบอกให้ชัดด้วย"


def test_plugin_deps_can_print_categories_for_a_script(app):
    """CI ต้องติดตั้ง category ได้โดยไม่ต้องรู้จักชื่อ plugin ตัวไหนเป็นการเฉพาะ"""
    result = app.test_cli_runner().invoke(args=["plugin-deps", "--categories"])
    assert result.exit_code == 0
    assert result.output.split() == [
        "plugin-auth-ldap",
        "plugin-auth-totp",
        "plugin-auth-totp-qr-segno",
        "plugin-cache-redis",
        "plugin-db-mariadb",
        "plugin-db-mysql",
        "plugin-secrets-vault",
    ], "เรียงแล้ว คั่นด้วยช่องว่าง ต่อท้าย `pipenv sync --categories` ได้เลย"


def test_plugin_deps_rows_are_a_contract_that_ci_reads(app):
    """**รูปแบบบรรทัดนี้เป็นสัญญา ไม่ใช่การจัดหน้าให้คนอ่าน**

    ด่านของ job `bare` นับบรรทัดที่คอลัมน์ที่สามเป็น `ok` เพื่อยืนยันว่า
    *ไม่มี* ไลบรารีของจุด plug ตัวไหนติดตั้งอยู่ ก่อนจะเชื่อผลของชุดเทสต์
    ถ้าชื่อสถานะเปลี่ยน สลับคอลัมน์ หรือเลิกคั่นด้วย tab — `awk` จะนับได้ 0
    เสมอ แล้ว **job `bare` จะเขียวโดยไม่ได้พิสูจน์อะไรเลย** ซึ่งเป็นสิ่งเดียวกับ
    ที่ด่านนั้นถูกเขียนขึ้นมากัน (ไม่มีอะไรฟ้อง เพราะมันคือคำว่า "ผ่าน" เหมือนกัน)

    **ห้ามมาร์ก `plugin_deps`** — เทสต์นี้ต้องเดินได้ทั้งสองโหมด จึงไม่ยืนยันว่า
    สถานะเป็น `ok` หรือ `MISSING` ยืนยันแค่ว่าเป็นคำที่ด่านนั้นอ่านออก
    """
    result = app.test_cli_runner().invoke(args=["plugin-deps"])
    assert result.exit_code == 0, result.output
    rows = [line.split("\t") for line in result.output.splitlines() if line]

    assert {len(row) for row in rows} <= {2, 4}, (
        f"บรรทัดต้องมี 2 ช่อง (ไม่พึ่งไลบรารี) หรือ 4 ช่อง (พึ่ง) เท่านั้น: {rows}"
    )
    declared = [row for row in rows if len(row) == 4]
    assert declared, (
        "ไม่มีจุด plug ไหนประกาศไลบรารีเลย — ด่านของ job `bare` จะไม่มีอะไรให้ตรวจ "
        "และจะผ่านทุกครั้งโดยไม่ได้พิสูจน์อะไร"
    )
    for key, requirement, state, category in declared:
        assert state in {"ok", "MISSING"}, (
            f"{key}: คอลัมน์ที่สามต้องเป็น 'ok' หรือ 'MISSING' ไม่ใช่ {state!r} "
            "— ด่านของ job `bare` ใน .github/workflows/ci.yml อ่านค่านี้ตรง ๆ"
        )
        assert requirement, f"{key}: คอลัมน์ที่สองต้องเป็นชื่อไลบรารี"
        assert category.startswith("[plugin-"), f"{key}: คอลัมน์ที่สี่ต้องเป็นชื่อ category"


# job `bare` รันด้วย `-m "not plugin_deps"` ทุกตัวที่ถูกมาร์กจึงเป็นสิ่งที่ **job
# นั้นไม่ได้พิสูจน์** เพดานนี้ทำให้การลดขอบเขตของด่านเป็นการตัดสินใจที่มีคนเห็น
# ไม่ใช่ผลข้างเคียงของการมาร์กเพิ่มทีละตัวจนวันหนึ่ง `bare` เขียวเพราะแทบไม่ได้รันอะไร
# **ratchet: ลดได้อย่างเดียว** เพิ่มต้องอธิบายให้ได้ว่าทำไมเทสต์นั้นถึงต้องมี
# ไลบรารีของจุด plug จริง ๆ (ส่วนใหญ่เขียนใหม่ให้ไม่ต้องมีได้ — ดู `qr_unplugged`
# ใน tests/test_totp.py ที่ทดสอบเส้นทาง "ไม่มีส่วนเสริม" โดยไม่ต้องมีไลบรารีเลย)
# ขยับ 5 → 7 ระหว่าง P5-06/07: เทสต์ที่ยิง redis จริงสองตัว (`test_cache.py`)
# **ตั้งใจไม่ใช้ mock** เพราะ mock พิสูจน์ได้แค่ว่าเราเรียกฟังก์ชันชื่อถูก
# ไม่ได้พิสูจน์ว่าค่าเดินทางไปถึง redis แล้วกลับมา หรือว่า worker สองตัวเห็น
# โควตาเดียวกันจริง ซึ่งคือทั้งหมดของสิ่งที่สองขั้นนั้นอ้างว่าทำได้
#
# **ราคาที่จ่ายแคบกว่าที่ตัวเลขบอก**: สองตัวนี้ job `bare` ไม่ได้รัน แต่ job `test`
# รันจริงทุก push แล้ว (มี service container ของ redis ตั้งแต่ P5-07) — ก่อนหน้านั้น
# มันข้ามตัวเองใน CI ทุกที่ ซึ่งแปลว่าไม่เคยถูกพิสูจน์นอกเครื่องคนเขียนเลย
# วัดจริง 2026-08-11: test_totp 4 + test_plugins 1 + test_cache 2 + test_ldap 17
# + test_secrets 8 (P5-15: 6 ตัวของ Vault ที่ต้องมี `hvac` และอีก 2 ตัวที่ตั้ง
#   `CACHE_URL` เป็น redis:// ซึ่งทำให้ `create_app()` ต้องโหลด backend จริง)
# **ขยับขึ้นเพราะ `auth/ldap` เป็นจุด plug ตัวแรกที่ต้องมีไลบรารีเพื่อ *ยืนยัน
# ตัวตน*** (ADR 0029) — ต่างจาก `auth/oidc` ที่เป็น stdlib ล้วนจึงไม่กินโควตานี้เลย
# ตรรกะของมันทั้งหมดอยู่หลัง `import ldap3` จึงเขียนเทสต์โดยไม่มีไลบรารีไม่ได้
# และด่านที่ต้องพิสูจน์มีเยอะกว่าปกติเพราะเป็นเรื่องความปลอดภัยล้วน ๆ
# (รหัสผ่านว่าง, bind ด้วย dn, TLS, ลำดับกับรหัสผ่านของที่นี่)
#
# **สิ่งที่ job `bare` ยังต้องพิสูจน์ต่อไปคือ "ไม่มีไลบรารี = ปิดตัวเอง ไม่ใช่พัง"**
# ซึ่งเทสต์ตัวนั้นอยู่ในไฟล์ที่มาร์คไว้เหมือนกัน — จึงมีเทสต์ในชุดที่ *ไม่* ถูกมาร์ค
# ครอบเรื่องเดียวกันด้วย (`tests/test_oidc.py` กับหน้า login ที่ไม่มี plugin ไหนเลย)
# ขยับ 32 → 76 ตอนเฟส 15 (ADR 0046): auth/totp มีไลบรารีจริงเป็นครั้งแรก
# (cryptography) — enroll/verify ทุกเส้นเขียนความลับผ่าน EncryptedSecret จึง
# ต้องการไลบรารี ทั้งไฟล์ test_totp ย้ายออกจาก job bare ตามกติกา · ฝั่ง bare
# ยังมีเทสต์ generic คุมว่า plugin ที่ไลบรารีขาด **ปิดตัวเอง** ไม่ใช่พัง
# — ดูเทสต์ generic ชื่อ a_factor_whose_library_is_missing_disables_itself
# ขยับ 76 → 78 ตอน audit รอบ 11 (ADR 0067): เพดานเวลาของการรอปลายทางภายนอก
# ต้องพิสูจน์ที่ **พารามิเตอร์ที่ส่งเข้าไปจริง** ซึ่งอ่านได้เฉพาะเมื่อมีไลบรารีของ
# ยี่ห้อนั้นอยู่ (ldap3 · pymysql) — ค่าคงที่ที่ไม่มีใครส่งต่อคือค่าที่อ่านแล้ว
# เข้าใจผิดว่ามีผล · ฝั่ง bare ยังมีด่านที่ครอบเรื่องเดียวกันแบบไม่ต้องมีไลบรารี:
# `tests/test_job_timeouts.py` ซึ่งสแกน `subprocess.run` ด้วย AST ล้วน
PLUGIN_DEPS_BUDGET = 78

TESTS_DIR = pathlib.Path(__file__).resolve().parent


def _marked_plugin_deps():
    """ชื่อเทสต์ทุกตัวที่ประกาศตัวว่าต้องมีไลบรารีของจุด plug

    ครอบทั้ง decorator ต่อตัวและ `pytestmark` ระดับโมดูล — อย่างหลังมาร์กทั้งไฟล์
    ด้วยบรรทัดเดียว ซึ่งเป็นวิธีที่ขอบเขตของ job `bare` จะหดลงเยอะที่สุดต่อการ
    แก้หนึ่งครั้ง จึงต้องถูกนับให้ครบทุกตัวในไฟล์นั้น ไม่ใช่นับเป็นหนึ่ง
    """
    marked = []
    for path in sorted(TESTS_DIR.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        functions = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
        ]
        module_wide = any(
            isinstance(node, ast.Assign)
            and any(getattr(target, "id", "") == "pytestmark" for target in node.targets)
            and "plugin_deps" in ast.unparse(node.value)
            for node in tree.body
        )
        for node in functions:
            decorated = any(
                ast.unparse(decorator).endswith("pytest.mark.plugin_deps")
                for decorator in node.decorator_list
            )
            if module_wide or decorated:
                marked.append(f"{path.name}::{node.name}")
    return marked


def test_the_bare_job_still_covers_almost_everything():
    """**สิ่งที่ job `bare` ข้าม คือสิ่งที่มันไม่ได้พิสูจน์**

    ด่านนั้นตอบคำถาม "ถอดไลบรารีของ plugin ออกแล้วระบบยังทำงานไหม" ได้ก็ต่อเมื่อ
    ยังรันเกือบทั้งชุดอยู่ ถ้ามีคนมาร์กเพิ่มเรื่อย ๆ (หรือมาร์กทั้งไฟล์ด้วย
    `pytestmark` บรรทัดเดียว) มันจะยังเขียวเหมือนเดิมทุกครั้ง โดยที่ความหมาย
    ของคำว่าเขียวหดลงเงียบ ๆ — ไม่มีอะไรในระบบฟ้องเรื่องนี้นอกจากเพดานนี้
    """
    marked = _marked_plugin_deps()
    assert len(marked) <= PLUGIN_DEPS_BUDGET, (
        f"มีเทสต์ที่ job `bare` ไม่ได้รัน {len(marked)} ตัว เกินเพดาน {PLUGIN_DEPS_BUDGET}:\n"
        + "\n".join(marked)
        + "\n\nเขียนให้ไม่ต้องพึ่งไลบรารีของจุด plug ได้ไหม ถ้าจำเป็นจริง ๆ "
        "ให้ขยับ PLUGIN_DEPS_BUDGET พร้อมเหตุผล (ratchet: ปกติลดได้อย่างเดียว)"
    )


def test_the_marker_scanner_sees_the_real_markers():
    """กันเทสต์ข้างบนเขียวเพราะสแกนไม่เจออะไรเลย ไม่ใช่เพราะไม่มีใครมาร์กเกิน"""
    marked = _marked_plugin_deps()
    assert "test_plugins.py::test_the_shipped_qr_is_plugged_in_as_an_enhancement" in marked
    # ตั้งแต่ ADR 0046 ทั้งไฟล์ totp ถูกมาร์ก (plugin มีไลบรารีจริงแล้ว) —
    # เลขนี้คือจำนวนเทสต์ทั้งไฟล์ ไม่ใช่สี่ตัวที่แตะส่วนเสริมเหมือนก่อน
    assert sum(name.startswith("test_totp.py::") for name in marked) >= 30


# --- โค้ดของจุด plug ต้อง import แค่ของที่ประกาศไว้ (Phase 4.5 — ADR 0025 ข้อ 7) ---
# manifest ที่ประกาศไลบรารีไม่ครบทำให้คำสัญญาหลักของเฟสนี้ ("ถอดไดเรกทอรีแล้ว
# supply chain ของมันหายไปด้วย") เป็นจริงแค่บนกระดาษ — `plugin-deps` จะไม่รู้จัก
# ของที่ขาด, `missing_requirements()` จะบอกว่าครบทั้งที่ไม่ครบ, และไลบรารีตัวนั้น
# จะไปนอนอยู่ใน [packages] ของ core แทน (ที่เดียวที่มันจะถูกติดตั้งให้)
#
# **นี่เป็นด่านตอนรีวิว ไม่ใช่กำแพงตอนรัน** — เมื่อไลบรารีถูกติดตั้งแล้ว python
# ยอมให้โค้ดไหน import อะไรก็ได้ (ADR 0025 หัวข้อ "ขอบเขตที่ ADR นี้ไม่ครอบคลุม")

CORE_DIR = pathlib.Path(__file__).resolve().parent.parent / "app"


def _imported_modules(path):
    """ชื่อโมดูลระดับบนสุดที่ไฟล์นี้ import พร้อมเลขบรรทัด

    import แบบญาติ (`from .models import ...`) ไม่นับ เพราะเป็นโค้ดของจุด plug
    เอง ไม่ใช่ของที่มาจากข้างนอก
    """
    found = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((alias.name.split(".")[0], node.lineno) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and not node.level:
            found.append(((node.module or "").split(".")[0], node.lineno))
    return found


@functools.cache
def _core_modules():
    """โมดูลนอก stdlib ที่ **core เอง** import อยู่แล้ว

    อ่านจากโค้ดของ core ตรง ๆ ไม่ได้เขียนเป็นรายชื่อไว้ที่ไหน (หลักเดียวกับ
    `category_of()` ที่คำนวณจากคีย์ — รายชื่อที่ประกาศซ้ำได้คือรายชื่อที่วันหนึ่ง
    จะไม่ตรงกับของจริง) plugin ยืมของพวกนี้ได้โดยไม่ต้องประกาศ เพราะถอด plugin
    ทิ้งก็ถอดมันออกไม่ได้อยู่ดี การประกาศซ้ำจึงไม่ได้ทำให้ถอดอะไรได้เพิ่ม
    (นี่คือเหตุผลที่ `models.py` ของ plugin import `sqlalchemy` ได้ตรง ๆ)
    """
    modules = {"app"}
    for path in sorted(CORE_DIR.rglob("*.py")):
        if path.is_relative_to(plugins.PLUGIN_ROOT):
            continue
        modules.update(name for name, _ in _imported_modules(path))
    return frozenset(name for name in modules if name and name not in sys.stdlib_module_names)


def _canonical(name):
    """ชื่อแพ็กเกจแบบเทียบกันได้ตาม PEP 503 (`Flask-WTF` กับ `flask_wtf` คือตัวเดียวกัน)"""
    return re.sub(r"[-_.]+", "-", name).lower()


@functools.cache
def _modules_of(requirement):
    """ชื่อโมดูลที่ requirement **บรรทัดเดียว** นี้อนุญาตให้ import

    ปกติชื่อแพ็กเกจกับชื่อโมดูลตรงกัน (`segno` → `segno`) แต่ไม่เสมอไป
    (`python-dotenv` → `dotenv`) ถ้าไลบรารีถูกติดตั้งอยู่ก็ถาม metadata เอาตรง ๆ
    ส่วนตอนที่ยังไม่ได้ติดตั้ง (job `bare` ของ CI) ตกกลับไปเดาจากชื่อแพ็กเกจ
    ซึ่งพลาดไปในทาง **เข้มกว่า** ไม่ใช่หลวมกว่า — คือฟ้องของที่จริง ๆ แล้วถูก
    ไม่ใช่ปล่อยของที่ผิดผ่าน

    **ต้องแยกทีละบรรทัด ไม่ใช่ยุบเป็นก้อนเดียวต่อจุด plug** ไม่งั้นการถามว่า
    "ไลบรารีตัวนี้ยังถูกใช้อยู่ไหม" จะตอบว่าใช้อยู่เพราะ*เพื่อนของมัน*ถูกใช้
    """
    distribution = plugins.distribution_name(requirement)
    names = {distribution.replace("-", "_")}
    names.update(
        module
        for module, owners in importlib.metadata.packages_distributions().items()
        if any(_canonical(owner) == _canonical(distribution) for owner in owners)
    )
    return frozenset(names)


def _declared_modules(point):
    """ชื่อโมดูลทั้งหมดที่ manifest ของจุด plug นี้อนุญาตให้ import"""
    return {name for item in plugins.requirements(point) for name in _modules_of(item)}


def _own_files(point, points):
    """ไฟล์ .py ที่เป็นของจุด plug นี้จริง ๆ

    ไฟล์ที่อยู่ในจุด plug ที่ซ้อนอยู่ข้างใน (`enhancements/<ไอดี>/`) ไม่นับ —
    ส่วนเสริมมี manifest ของตัวเอง จึงต้องถูกตัดสินด้วย manifest ของตัวเอง
    ไม่ใช่ของ plugin แม่ ไม่งั้น plugin แม่จะกลายเป็นที่ประกาศไลบรารีของทุกตัว
    ที่เสียบอยู่ข้างใน ซึ่งคือสิ่งที่ ADR 0025 ย้าย QR ออกมาเพื่อเลิกทำ
    """
    inner = [
        other.directory
        for other in points
        if other.directory != point.directory and other.directory.is_relative_to(point.directory)
    ]
    return [
        path
        for path in sorted(point.directory.rglob("*.py"))
        if not any(path.is_relative_to(directory) for directory in inner)
    ]


def _undeclared_imports(points):
    """import ที่ไม่มี manifest ไหนรองรับ — คืนเป็นข้อความอ่านออกพร้อมที่อยู่"""
    core = _core_modules()
    found = []
    for point in points:
        allowed = core | _declared_modules(point)
        for path in _own_files(point, points):
            found.extend(
                f"{point.key}: {path.name}:{lineno} import {name}"
                for name, lineno in _imported_modules(path)
                if name and name not in sys.stdlib_module_names and name not in allowed
            )
    return found


def test_a_plug_point_imports_only_what_it_declares(app):
    """ของจริงทุกตัวบนดิสก์ต้องผ่าน — รวมตัวที่ถูกสวิตช์ปิด

    ใช้ `plug_points_on_disk()` ไม่ใช่ `plug_points()` เพราะนี่เป็นด่านตรวจ
    *โค้ด* ซึ่งต้องให้ผลเดิมไม่ว่า `.env` ของเครื่องที่รันจะปิดอะไรไว้
    """
    with app.app_context():
        offenders = _undeclared_imports(plugins.plug_points_on_disk())
    assert not offenders, (
        "โค้ดของจุด plug import ของที่ manifest ไม่ได้ประกาศ:\n"
        + "\n".join(offenders)
        + "\n\nประกาศใน `requires.pip` ของ manifest ตัวเอง แล้วเพิ่มหมวดใน Pipfile "
        "ไม่งั้นถอนไดเรกทอรีทิ้งแล้วไลบรารีตัวนี้จะยังถูกติดตั้งต่อไปโดยไม่มีใครขอ"
    )


def test_the_scanner_reads_the_real_plugin_code(app):
    """กันเทสต์ข้างบนเขียวเพราะหาไฟล์ไม่เจอ ไม่ใช่เพราะโค้ดสะอาด

    และพิสูจน์การแบ่งเขตด้วย: `provide.py` ของส่วนเสริมต้อง **ไม่** ถูกนับเป็น
    ไฟล์ของ plugin แม่ ไม่งั้น `import segno` จะถูกตัดสินด้วย manifest ที่ไม่ได้
    ประกาศมันไว้ (หรือแย่กว่านั้นคือถูกปล่อยผ่านเพราะแม่ประกาศไว้ให้)
    """
    with app.app_context():
        points = plugins.plug_points_on_disk()
    files = {point.key: {path.name for path in _own_files(point, points)} for point in points}
    assert files[TOTP_KEY] == {"crypto.py", "factor.py", "models.py", "personal_data.py"}
    assert files[QR_KEY] == {"provide.py"}


def test_a_factor_whose_library_is_missing_disables_itself(app):
    """ไลบรารีของ plugin ขาด = หายจากรายการที่ใช้ได้ ไม่ใช่พังตอนผู้ใช้กด (ADR 0046)

    เทสต์นี้ต้องรันได้ใน job `bare` — วาง plugin ปัจจัยที่สอง*จริง*ลงดิสก์
    (registry อ่านดิสก์ใหม่ทุกครั้ง การแก้ object ใน memory จึงไม่ติด) พร้อม
    manifest ที่เรียกหา distribution ซึ่งไม่มีทางติดตั้งอยู่
    """
    import shutil as sh

    from app.services import mfa

    directory = plugins.PLUGIN_ROOT / "auth" / "ghostly"
    directory.mkdir(parents=True)
    (directory / "plugin.json").write_text(
        json.dumps(
            {
                "type": "auth",
                "name": "ghostly",
                "factor": "second",
                "migration": "live",
                "requires": {"pip": ["no-such-distribution-xyz"]},
            }
        )
    )
    (directory / "factor.py").write_text("import no_such_module_xyz\n")
    try:
        with app.app_context():
            target = next(p for p in plugins.second_factors() if p.id == "ghostly")
            assert plugins.requirements_met(target) is False
            assert "auth/ghostly" not in {p.key for p in mfa.available()}, (
                "plugin ที่ไลบรารีขาดต้องหายจาก available ไม่ใช่รอพังตอน enroll"
            )
    finally:
        sh.rmtree(directory, ignore_errors=True)


def test_the_scanner_catches_an_import_that_no_manifest_declares(app, host_plugin):
    """พิสูจน์ว่าตัวสแกนจับของจริงได้ ไม่ใช่ตัวกรองที่ไม่เคยตรงกับอะไรเลย"""
    host_plugin("sneaky", body="import some_library_nobody_declared\n")
    with app.app_context():
        offenders = _undeclared_imports(plugins.plug_points_on_disk())
    assert [item for item in offenders if item.startswith("auth/hosty#sneaky:")] == [
        "auth/hosty#sneaky: provide.py:1 import some_library_nobody_declared"
    ], offenders


def test_declaring_the_library_makes_the_import_legal(app, host_plugin):
    """ประกาศแล้วต้องผ่าน — และชื่อแพ็กเกจที่มีขีดกลางต้องเทียบกับชื่อโมดูลได้"""
    host_plugin(
        "honest",
        manifest={
            "name": "honest",
            "provides": "thing",
            "requires": {"pip": ["some-library-nobody-declared~=1.0"]},
        },
        body="import some_library_nobody_declared\n",
    )
    with app.app_context():
        offenders = _undeclared_imports(plugins.plug_points_on_disk())
    assert not [item for item in offenders if item.startswith("auth/hosty#honest:")], offenders


# ไลบรารีที่ถูกใช้จริงโดยไม่มีบรรทัด `import` ให้เห็น — driver ที่ถูกเรียกตามชื่อ
# ใน connection string เป็นตัวอย่างที่จะมาถึงจริงใน Phase 5 (`pymysql`, `redis`)
# **เพิ่มรายการที่นี่ = ยอมรับว่าจะไม่มีอะไรบอกได้อีกว่าไลบรารีตัวนี้ยังถูกใช้อยู่ไหม**
DECLARED_BUT_NOT_IMPORTED = {
    # (คีย์ของจุด plug, ชื่อแพ็กเกจ) พร้อมเหตุผลว่าใครเป็นคนเรียกมันแทน
    #
    # driver ของฐานข้อมูลถูกเรียกโดย **SQLAlchemy ตามชื่อใน URL** (`mysql+pymysql://`)
    # ไม่มีไฟล์ไหนของ backend เขียน `import pymysql` เลย — และไม่ควรเขียนด้วย
    # เพราะการ import ตรง ๆ จะทำให้ต้องมี driver ติดตั้งอยู่ถึงจะ *โหลดโมดูล* ได้
    # ทั้งที่จริงต้องมีก็ต่อเมื่อจะ *ต่อ* ฐานข้อมูลยี่ห้อนั้น
    ("db/mysql", "pymysql"),
    ("db/mariadb", "pymysql"),
}


def _unused_requirements(points):
    """ไลบรารีที่ manifest ประกาศไว้แต่ไม่มีไฟล์ไหนของจุด plug นั้น import เลย

    ทิศทางกลับของด่านข้างบน และจำเป็นพอ ๆ กัน: การประกาศเกินแปลว่าทุก deploy
    ติดตั้งไลบรารีที่ไม่มีใครใช้ ต้องเฝ้า CVE ของมัน และมันโผล่ใน SBOM ในฐานะ
    ของที่ระบบนี้พึ่งพา — ซึ่งเป็นสิ่งเดียวกับที่ ADR 0025 ตั้งใจจะเลิกทำ
    """
    found = []
    for point in points:
        imported = {
            name for path in _own_files(point, points) for name, _ in _imported_modules(path)
        }
        for requirement in plugins.requirements(point):
            distribution = plugins.distribution_name(requirement)
            if (point.key, distribution) in DECLARED_BUT_NOT_IMPORTED:
                continue
            if not (_modules_of(requirement) & imported):
                found.append(f"{point.key}: ประกาศ {requirement} แต่ไม่มีไฟล์ไหน import")
    return found


def test_a_plug_point_declares_nothing_it_never_imports(app):
    with app.app_context():
        offenders = _unused_requirements(plugins.plug_points_on_disk())
    assert not offenders, (
        "manifest ประกาศไลบรารีที่ไม่มีใครใช้:\n"
        + "\n".join(offenders)
        + "\n\nเอาออกจาก `requires.pip` และจาก Pipfile ด้วย ไม่งั้นมันจะถูกติดตั้ง "
        "ทุก deploy และต้องเฝ้า CVE ต่อไปโดยไม่มีใครได้ประโยชน์"
        "\nถ้าถูกใช้โดยไม่ผ่าน import จริง ๆ ต้องเพิ่มใน DECLARED_BUT_NOT_IMPORTED พร้อมเหตุผล"
    )


def test_the_scanner_catches_a_library_that_nobody_uses(app, host_plugin):
    """พิสูจน์ทิศทางกลับ — ประกาศแล้วไม่ใช้ต้องถูกจับเหมือนกัน"""
    host_plugin(
        "hoarder",
        manifest={
            "name": "hoarder",
            "provides": "thing",
            "requires": {"pip": ["some-library-nobody-declared~=1.0"]},
        },
        body="VALUE = 'ok'\n",
    )
    with app.app_context():
        offenders = _unused_requirements(plugins.plug_points_on_disk())
    assert [item for item in offenders if item.startswith("auth/hosty#hoarder:")], offenders


def test_a_plug_point_may_lean_on_what_core_already_carries(app, host_plugin):
    """ของที่ core แบกอยู่แล้วไม่ต้องประกาศซ้ำ เพราะถอด plugin ทิ้งก็ถอดมันไม่ได้

    ถ้าด่านนี้เข้มกว่านี้ `models.py` ของ plugin จริงจะต้องประกาศ `sqlalchemy`
    ไว้ในหมวดของตัวเอง ทั้งที่ pipenv จะติดตั้งมันให้อยู่แล้วในฐานะ dependency
    ของ core — ได้ SBOM ที่บอกว่าถอด plugin แล้วจะเลิกใช้ sqlalchemy ซึ่งไม่จริง
    """
    host_plugin("leaning", body="import sqlalchemy\nfrom flask import current_app\n")
    with app.app_context():
        offenders = _undeclared_imports(plugins.plug_points_on_disk())
    assert not [item for item in offenders if item.startswith("auth/hosty#leaning:")], offenders


# --- CLI ของวงจรชีวิต plugin (Phase 4) ---


def test_plugin_list_shows_who_owns_what(app):
    result = app.test_cli_runner().invoke(args=["plugin-list"])
    assert result.exit_code == 0, result.output
    # ธีมไม่มีตารางของตัวเอง ส่วน auth/totp มี
    assert "themes/system" in result.output
    assert "no tables" in result.output
    assert "tdl_auth_totp_secret" in result.output


def test_plugin_list_says_when_a_table_is_missing(app):
    from app import plugins

    with app.app_context():
        plugins.uninstall(plugins.find(TOTP_KEY))
    result = app.test_cli_runner().invoke(args=["plugin-list"])
    assert "NOT installed" in result.output


def test_plugin_install_creates_the_table_and_repeats_safely(app):
    from sqlalchemy import inspect

    from app import plugins

    with app.app_context():
        plugins.uninstall(plugins.find(TOTP_KEY))

    runner = app.test_cli_runner()
    assert runner.invoke(args=["plugin-install", TOTP_KEY]).exit_code == 0
    # คำสั่งติดตั้งที่รันซ้ำไม่ได้คือคำสั่งที่ไม่มีใครกล้ารัน จึงต้องรันซ้ำแล้วไม่พัง
    result = runner.invoke(args=["plugin-install", TOTP_KEY])
    assert result.exit_code == 0, result.output

    with app.app_context():
        assert "tdl_auth_totp_secret" in inspect(db.engine).get_table_names()


def test_plugin_uninstall_drops_the_table(app):
    from sqlalchemy import inspect

    from app import plugins

    result = app.test_cli_runner().invoke(args=["plugin-uninstall", TOTP_KEY, "--yes"])
    assert result.exit_code == 0, result.output
    with app.app_context():
        assert "tdl_auth_totp_secret" not in inspect(db.engine).get_table_names()
        plugins.install(plugins.find(TOTP_KEY))  # คืนสภาพให้เทสต์ตัวถัดไป


def test_plugin_uninstall_asks_before_dropping(app):
    from sqlalchemy import inspect

    result = app.test_cli_runner().invoke(args=["plugin-uninstall", TOTP_KEY], input="n\n")
    assert result.exit_code != 0, "ตอบ n แล้วต้องไม่ลบ"
    with app.app_context():
        assert "tdl_auth_totp_secret" in inspect(db.engine).get_table_names()


def test_plugin_commands_on_a_plugin_without_tables(app):
    runner = app.test_cli_runner()
    assert "nothing to do" in runner.invoke(args=["plugin-install", "themes/system"]).output
    assert "nothing to do" in runner.invoke(args=["plugin-uninstall", "themes/system"]).output


def test_plugin_commands_reject_an_unknown_plugin(app):
    runner = app.test_cli_runner()
    for command in ("plugin-install", "plugin-uninstall"):
        result = runner.invoke(args=[command, "auth/ไม่มีตัวนี้"])
        assert result.exit_code != 0
        assert "No plugin named" in result.output


# --- สวิตช์ปิดตอน runtime (Phase 4.5 — ADR 0025) ---
# สิ่งที่ต้องพิสูจน์: ปิดแล้วต้อง "เหมือนไม่เคยมีไดเรกทอรี" ทุกทาง ยกเว้นทางเดียว
# คือข้อมูล ซึ่งต้องยังมีเจ้าของอยู่ ไม่งั้น migration ตัวถัดไปของ core จะ drop ทิ้ง


def _switch(app, *keys):
    app.config["DISABLED_PLUGINS"] = frozenset(keys)


def test_a_switched_off_plugin_looks_like_it_was_never_installed(app, temp_theme):
    temp_theme("switchable")
    with app.app_context():
        assert plugins.find("themes/switchable") is not None
        _switch(app, "themes/switchable")
        assert plugins.find("themes/switchable") is None
        assert "switchable" not in plugins.themes()
        assert "themes/switchable" not in {point.key for point in plugins.plug_points()}
        # ไดเรกทอรียังอยู่ครบ — ต่างจากการถอนทิ้ง
        assert plugins.find_on_disk("themes/switchable") is not None


def test_a_user_on_a_switched_off_theme_falls_back(app, client, user_id, temp_theme):
    """คนที่เลือกธีมนั้นไว้ต้องไม่เจอหน้าพัง — เส้นทางเดียวกับตอนลบไดเรกทอรีทิ้ง"""
    temp_theme("switchable")
    with app.app_context():
        user = db.session.get(User, user_id)
        user.theme = "switchable"
        db.session.commit()

    assert b"/plugin/themes/switchable/style.css" in client.get("/").data
    app.config["DISABLED_PLUGINS"] = frozenset({"themes/switchable"})
    body = client.get("/").data
    assert b"/plugin/themes/switchable/style.css" not in body
    assert b"/plugin/themes/system/style.css" in body


def test_a_switched_off_enhancement_leaves_its_host_working(app, host_plugin):
    host_plugin("basic")
    with app.app_context():
        assert plugins.capability(plugins.find("auth/hosty"), "thing") is not None
        _switch(app, "auth/hosty#basic")
        assert plugins.find("auth/hosty") is not None, "host ต้องไม่ถูกปิดตามไปด้วย"
        assert plugins.capability(plugins.find("auth/hosty"), "thing") is None


def test_switching_off_a_host_takes_its_enhancements_with_it(app, host_plugin):
    host_plugin("basic")
    with app.app_context():
        _switch(app, "auth/hosty")
        assert plugins.find("auth/hosty#basic") is None
        assert "auth/hosty#basic" not in {point.key for point in plugins.plug_points()}


def test_the_list_of_what_is_off_names_every_level(app, host_plugin):
    """ปิด host หนึ่งตัวอาจหมายถึงหลายความสามารถหายไป — รายงานต้องบอกครบ"""
    host_plugin("basic")
    with app.app_context():
        _switch(app, "auth/hosty")
        assert {point.key for point in plugins.disabled()} == {"auth/hosty", "auth/hosty#basic"}


def test_switching_something_off_takes_its_supply_chain_too(app):
    """ปิดแล้ว `pipenv sync` รอบถัดไปต้องไม่ติดตั้งไลบรารีของมันอีก

    นี่คือเหตุผลทั้งหมดที่สวิตช์นี้มีอยู่ — ถ้าไลบรารียังถูกติดตั้งต่อไป
    การปิดก็แค่ซ่อนปุ่ม ไม่ได้ลดพื้นที่ที่ต้องเฝ้า CVE เลย
    """
    runner = app.test_cli_runner()
    before = runner.invoke(args=["plugin-deps", "--categories"]).output.split()
    assert any(name.startswith("plugin-auth-totp") for name in before)

    app.config["DISABLED_PLUGINS"] = frozenset({TOTP_KEY})
    after = runner.invoke(args=["plugin-deps", "--categories"]).output.split()

    assert not any(name.startswith("plugin-auth-totp") for name in after)
    # และต้องหายไปเฉพาะของตัวที่ถูกปิด — ของยี่ห้ออื่นที่ไม่เกี่ยวต้องอยู่ครบ
    assert after == [name for name in before if not name.startswith("plugin-auth-totp")]


def test_a_switched_off_plugin_still_owns_its_tables(app):
    """**สวิตช์ปิดโค้ด ไม่ได้ปิดข้อมูล**

    ถ้าความเป็นเจ้าของตารางหายไปตอนปิด ตารางนั้นจะกลายเป็นตารางไม่มีเจ้าของ
    แล้ว `flask db migrate` ตัวถัดไปของ core จะออก migration ที่ drop มันทิ้ง
    (env.py กรอง "ตารางของ plugin" ออกจาก autogenerate ด้วย `owned_tables()`)
    ข้อมูลของคนที่เปิดการยืนยันสองขั้นไว้จะหายไปเพราะการปิดสวิตช์ชั่วคราว
    """
    with app.app_context():
        _switch(app, TOTP_KEY)
        plugins.forget_models()
        assert "tdl_auth_totp_secret" in plugins.owned_tables()
        assert plugins.tables_of(plugins.find_on_disk(TOTP_KEY)) == {"tdl_auth_totp_secret"}
    plugins.forget_models()


def test_data_commands_still_reach_a_switched_off_plugin(app):
    """ปิดโค้ดเพราะ CVE แล้วยังต้องเก็บกวาดข้อมูลของมันได้"""
    from sqlalchemy import inspect

    app.config["DISABLED_PLUGINS"] = frozenset({TOTP_KEY})
    result = app.test_cli_runner().invoke(args=["plugin-uninstall", TOTP_KEY, "--yes"])
    assert result.exit_code == 0, result.output
    with app.app_context():
        assert "tdl_auth_totp_secret" not in inspect(db.engine).get_table_names()
        plugins.install(plugins.find_on_disk(TOTP_KEY))  # คืนสภาพให้เทสต์ตัวถัดไป


def test_plugin_list_still_shows_what_is_switched_off(app):
    """ปิดไว้ กับ ไดเรกทอรีหายไป เป็นคนละเรื่องกันตอนแก้ปัญหา ต้องแยกออกจากกันได้"""
    app.config["DISABLED_PLUGINS"] = frozenset({TOTP_KEY})
    result = app.test_cli_runner().invoke(args=["plugin-list"])
    assert result.exit_code == 0, result.output
    assert TOTP_KEY in result.output
    assert "DISABLED" in result.output


def test_plugin_list_prints_the_keys_the_switch_needs(app):
    """คีย์ที่ไม่เคยถูกพิมพ์ออกมา คือคีย์ที่ไม่มีใครใส่ลง DISABLED_PLUGINS ได้ถูก

    docs/OPERATIONS.md บอกให้เอาคีย์จากคำสั่งนี้ไปใช้ ถ้ารายการมีแต่ plugin
    ระดับบน คนที่ตั้งใจปิดแค่ส่วนเสริมจะพิมพ์คีย์ของ plugin แม่แทน ซึ่งสำหรับ
    ปัจจัยยืนยันตัวตนแปลว่าปิด MFA ของทุกคนทิ้ง
    """
    result = app.test_cli_runner().invoke(args=["plugin-list"])
    assert result.exit_code == 0, result.output
    assert QR_KEY in result.output
    assert "segno" in result.output, "ต้องบอกด้วยว่าจุดนั้นลากไลบรารีอะไรมา"


def _listed(output, key):
    """บรรทัดของคีย์นั้นใน `plugin-list` (ขึ้นต้นด้วยคีย์แล้วตามด้วย tab)"""
    return next(line for line in output.splitlines() if line.startswith(f"{key}\t"))


def test_plugin_list_says_which_enhancement_is_actually_serving(app, host_plugin):
    """ไดเรกทอรีอยู่ครบ ไลบรารีก็ครบ ไม่ได้ปิดสวิตช์ แต่ความสามารถนั้นหายไป

    เป็นสถานะที่ตั้งใจให้เกิดได้ (fail closed เมื่อมีผู้ให้บริการหลายตัวแต่
    PLUGIN_PICKS ไม่ได้เลือก — ดู `_unpicked`) ถ้ารายการบอกแค่ว่า "ไม่ DISABLED
    และไลบรารีครบ" คนอ่านจะสรุปว่ามันทำงานอยู่ แล้วไปตามหาสาเหตุผิดที่
    """
    runner = app.test_cli_runner()
    host_plugin("basic")
    assert "provides thing (serving)" in _listed(
        runner.invoke(args=["plugin-list"]).output, "auth/hosty#basic"
    )

    # ผู้ให้บริการตัวที่สองของความสามารถเดียวกัน โดยไม่มีใครเลือกไว้ = ปิดทั้งคู่
    host_plugin("other")
    output = runner.invoke(args=["plugin-list"]).output
    assert "provides thing (NOT serving)" in _listed(output, "auth/hosty#basic")
    assert "provides thing (NOT serving)" in _listed(output, "auth/hosty#other")
    # plugin แม่ไม่ได้ให้ความสามารถอะไรผ่านชั้นนี้ จึงต้องไม่มีคอลัมน์นั้นเลย
    assert "provides" not in _listed(output, "auth/hosty")


def test_the_reason_it_is_off_is_logged_once_not_once_per_candidate(app, host_plugin, warnings_of):
    """เหตุผลเป็นของ *ความสามารถ* ไม่ใช่ของผู้สมัครแต่ละราย

    `provider()` เป็นคนอธิบายลง log ว่าทำไมไม่มีตัวไหนได้ให้บริการ ถ้ารายการนี้
    ถามมันทีละส่วนเสริม คนอ่าน log จะเห็นข้อความเดียวกันซ้ำตามจำนวนผู้สมัคร
    แล้วนึกว่าเป็นคนละเหตุการณ์ — ยิ่งมีผู้สมัครเยอะยิ่งดูเหมือนปัญหาใหญ่ขึ้น
    ทั้งที่เป็นเรื่องเดียวที่ถูกถามซ้ำ
    """
    host_plugin("basic")
    host_plugin("other")
    app.test_cli_runner().invoke(args=["plugin-list"])
    ambiguous = [line for line in warnings_of if "PLUGIN_PICKS ไม่ได้ระบุ" in line]
    assert len(ambiguous) == 1, f"ควรเตือนครั้งเดียวต่อความสามารถ แต่ได้ {len(ambiguous)}:\n{ambiguous}"


def test_switching_off_a_second_factor_says_so_in_plain_words(app, warnings_of):
    """ปิดปัจจัยยืนยันตัวตน = คนที่เปิดไว้ login ด้วยรหัสผ่านอย่างเดียวได้ทันที

    คีย์ของ plugin แม่กับของส่วนเสริมต่างกันแค่ `#` เดียว การพิมพ์พลาดจึงเป็น
    การลดระดับความปลอดภัยของทุกคนโดยไม่ตั้งใจ — ต้องมีบรรทัดที่บอกตรง ๆ
    """
    with app.app_context():
        _switch(app, TOTP_KEY)
        plugins.check_installation()
    assert any("รหัสผ่านอย่างเดียว" in line for line in warnings_of)

    # ปิดแค่ส่วนเสริมต้องไม่มีคำเตือนนี้ ไม่งั้นคำเตือนจะกลายเป็นเสียงรบกวน
    warnings_of.clear()
    with app.app_context():
        _switch(app, QR_KEY)
        plugins.check_installation()
    assert not any("รหัสผ่านอย่างเดียว" in line for line in warnings_of)


def test_a_core_plugin_cannot_be_switched_off(app):
    """ปิดของ core = แอปที่ start ไม่ได้ ต้องบอกให้ตรงจุดตั้งแต่ตอน start"""
    with app.app_context():
        _switch(app, f"{plugins.THEME_TYPE}/{plugins.CORE_THEME}")
        with pytest.raises(plugins.PluginError, match="เป็น plugin ของ core"):
            plugins.check_installation()


def test_what_is_switched_off_is_written_to_the_log_on_every_start(app, warnings_of):
    """ต้องมีร่องรอยว่าตอนนั้นระบบเดินอยู่โดยไม่มีความสามารถอะไรบ้าง"""
    with app.app_context():
        _switch(app, TOTP_KEY)
        plugins.check_installation()
    assert any(TOTP_KEY in line and "DISABLED_PLUGINS" in line for line in warnings_of)


def test_a_key_that_matches_nothing_is_reported(app, warnings_of):
    """คีย์ที่พิมพ์ผิดหน้าตาเหมือนการปิดของที่ถอนไปแล้วเป๊ะ จึงต้องเตือนไว้"""
    with app.app_context():
        _switch(app, "auth/พิมพ์ผิด")
        plugins.check_installation()
    assert any("auth/พิมพ์ผิด" in line for line in warnings_of)


def test_the_switch_ignores_blanks_and_spacing():
    from config import _parse_keys

    assert _parse_keys(" auth/totp , , themes/ocean ") == {"auth/totp", "themes/ocean"}
    assert _parse_keys("") == frozenset()


def test_nothing_is_switched_off_by_default(app):
    """ค่าเริ่มต้นต้องเป็น "เปิดทุกอย่าง" — สวิตช์นี้มีไว้ใช้ตอนฉุกเฉิน ไม่ใช่ตอนปกติ"""
    with app.app_context():
        assert plugins.disabled_keys() == frozenset()
        assert plugins.disabled() == []


def test_core_python_does_not_name_the_second_factor_plugin():
    """ชื่อ plugin ของปัจจัยที่สองต้องไม่โผล่ในโค้ด core เลย (สัญญาเดียวกับธีม)"""
    app_dir = pathlib.Path(__file__).resolve().parent.parent / "app"
    offenders = []
    for path in app_dir.rglob("*.py"):
        if plugins.PLUGIN_ROOT in path.parents or path == plugins.PLUGIN_ROOT / "__init__.py":
            continue
        if "totp" in path.read_text().lower():
            offenders.append(str(path))
    assert not offenders, f"core อ้างชื่อ plugin เฉพาะตัว: {offenders}"
