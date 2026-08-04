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


# --- plugin ที่มีข้อมูลของตัวเอง (Phase 4 — ADR 0023) ---

TOTP_KEY = "auth/totp"


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
        (directory / "plugin.json").write_text(json.dumps({"type": "auth", "name": plugin_id}))
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
    (directory / "plugin.json").write_text(json.dumps({"type": "auth", "name": "hosty"}))

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
        assert plugins.requirements(plugins.find(TOTP_KEY)) == ["segno~=1.6"]
        assert plugins.requirements(plugins.find("themes/system")) == []


def test_the_category_name_is_derived_from_the_key(app):
    """ชื่อ category ห้ามให้ manifest ประกาศเอง — ค่าที่ประกาศซ้ำได้คือค่าที่จะไม่ตรงกัน"""
    with app.app_context():
        assert plugins.category_of(plugins.find(TOTP_KEY)) == "plugin-auth-totp"


def test_no_plugin_library_sits_in_the_core_packages(app):
    """**ด่านหลักของ ADR 0025** — ไลบรารีที่ plugin เดียวใช้ต้องไม่อยู่ใน [packages]

    ถ้ามันอยู่ตรงนั้น การลบไดเรกทอรี plugin ทิ้งจะถอดได้แค่โค้ด ส่วนไลบรารียัง
    ถูกติดตั้งทุก deploy ยังอยู่ใน SBOM และยังต้องเฝ้า CVE ต่อไป
    """
    core_packages = {name.lower() for name in _pipfile().get("packages", {})}
    with app.app_context():
        offenders = [
            (plugin.key, requirement)
            for plugin in plugins.installed()
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
        for plugin in plugins.installed():
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
        json.dumps({"type": "auth", "name": "needy", "requires": {"pip": ["ไม่มีแพ็กเกจนี้จริง"]}})
    )
    with app.app_context():
        plugin = plugins.find("auth/needy")
        assert plugins.missing_requirements(plugin) == ["ไม่มีแพ็กเกจนี้จริง"]
        # ของที่ติดตั้งอยู่จริงต้องไม่ถูกรายงานว่าขาด
        assert plugins.missing_requirements(plugins.find(TOTP_KEY)) == []


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
    assert result.output.strip() == "plugin-auth-totp"


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
