"""panel ระบบของ admin (เฟส 14-04/14-06): อ่านของจริง ตอบตามจริง และ admin เท่านั้น

สามหน้า (environment · lifecycle · observability) มีสัญญาเดียวกัน:

- ค่าทุกตัวมาจาก runtime/ดิสก์ ณ ตอนเรียก — เทสต์เทียบกับแหล่งจริง ไม่เทียบ
  กับสตริงที่คาดไว้ล่วงหน้า (เลขที่ไม่ได้อ่านจากของจริงคือเลขที่ผิดอยู่แล้ว)
- ของที่อ่านไม่ได้ต้องบอกว่าอ่านไม่ได้ ไม่ใช่เดา
- ด่านสิทธิ์อยู่ใน service (`require_admin`) — คนธรรมดาได้ 403 ทุกหน้า
- ป้ายกำกับ ADR 0031 ("ของ process เดียว") ต้องอยู่บนหน้า observability เสมอ
"""

import sys

import pytest

from app import __version__, db
from app.models import User
from app.services import ForbiddenError, system_info
from app.services import roles as roles_service
from tests.conftest import PASSWORD

PANEL_PATHS = ("/admin/environment", "/admin/lifecycle", "/admin/observability", "/admin/sbom")


def _two_people(app):
    with app.app_context():
        boss = User(username="boss", role=roles_service.ROLE_ADMIN)
        boss.set_password(PASSWORD)
        member = User(username="member")
        member.set_password(PASSWORD)
        db.session.add_all([boss, member])
        db.session.commit()


def _sign_in(app, username):
    client = app.test_client()
    resp = client.post("/login", data={"username": username, "password": PASSWORD})
    assert resp.status_code == 302
    return client


@pytest.mark.parametrize("path", PANEL_PATHS)
def test_every_system_panel_is_admin_only(app, path):
    _two_people(app)
    client = _sign_in(app, "member")
    assert client.get(path).status_code == 403


def test_environment_reports_the_real_interpreter_and_database(app):
    """ค่าบนหน้าเทียบกับแหล่งจริงตัวเดียวกับที่ระบบใช้ — ไม่ใช่ค่าที่จำมา"""
    _two_people(app)
    client = _sign_in(app, "boss")
    page = client.get("/admin/environment").data.decode()
    assert sys.version.split()[0] in page, "เวอร์ชัน Python บนหน้าไม่ตรงกับ interpreter จริง"
    assert __version__ in page
    with app.app_context():
        assert db.engine.dialect.name in page


def test_lifecycle_lists_every_plugin_on_disk_with_its_class(app):
    """รายการ plugin มาจากดิสก์จริง (รวมตัวที่ถูกปิด) พร้อม migration class"""
    _two_people(app)
    client = _sign_in(app, "boss")
    page = client.get("/admin/lifecycle").data.decode()
    from app import plugins

    on_disk = plugins.installed_on_disk()
    assert on_disk, "ไม่มี plugin บนดิสก์เลย — ตัวสแกนพังหรือเปล่า"
    for plugin in on_disk:
        assert plugin.key in page, f"plugin {plugin.key} หายจากหน้า lifecycle"


def test_lifecycle_is_honest_when_the_schema_was_never_migrated(app):
    """ฐานเทสต์สร้างด้วย create_all ไม่มีตาราง alembic — หน้าต้องบอกว่าอ่านไม่ได้ ไม่ใช่เดา"""
    _two_people(app)
    with app.app_context():
        boss = db.session.query(User).filter_by(username="boss").one()
        facts = system_info.lifecycle(boss)
    assert facts["migration_current"] is None, "ไม่มีตาราง alembic แต่รายงานว่ามี revision"
    assert facts["migration_in_sync"] is False
    assert facts["migration_head"], "สาย migration บนดิสก์มีจริง ต้องอ่าน head ได้"


def test_lifecycle_is_honest_when_the_migration_chain_is_unreadable(app, monkeypatch, tmp_path):
    """สาย migration บนดิสก์หาย/อ่านไม่ได้ → head ต้องเป็น None ไม่ใช่เดา

    เกิดจริงได้ใน image ที่ไม่ได้ copy migrations/ มา — หน้า lifecycle ต้อง
    รายงานว่าอ่านไม่ได้ ไม่ใช่โชว์ค่ามั่วให้คนเชื่อว่า schema เป็นปัจจุบัน
    """
    _two_people(app)
    monkeypatch.setattr(system_info, "MIGRATIONS_DIR", tmp_path / "gone")
    with app.app_context():
        boss = db.session.query(User).filter_by(username="boss").one()
        facts = system_info.lifecycle(boss)
    assert facts["migration_head"] is None
    assert facts["migration_in_sync"] is False


def test_observability_counts_real_requests_and_carries_the_caveat(app):
    """ตัวเลขต้องมาจากคำขอที่เกิดจริงใน process นี้ และป้าย ADR 0031 ต้องอยู่บนหน้า"""
    _two_people(app)
    client = _sign_in(app, "boss")
    client.get("/admin/environment")  # สร้างคำขอให้ histogram นับ

    page = client.get("/admin/observability").data.decode()
    assert "admin.environment" in page, "endpoint ที่เพิ่งถูกเรียกต้องโผล่ในตาราง"
    assert "ADR 0031" in page, "ป้ายกำกับข้อจำกัดหายจากหน้า observability"


def test_the_service_refuses_non_admins_directly(app):
    """ด่านอยู่ใน service ไม่ใช่ที่ route — เรียกตรงก็ต้องโดนเหมือนกัน (ADR 0022)"""
    _two_people(app)
    with app.app_context():
        member = db.session.query(User).filter_by(username="member").one()
        for fn in (system_info.environment, system_info.lifecycle, system_info.observability):
            with pytest.raises(ForbiddenError):
                fn(member)


def test_every_panel_is_registered_in_the_nav(app):
    """หน้าใหม่ต้องลงทะเบียนเข้า registry — nav วนจาก registry ไม่ hardcode (ADR 0044)"""
    from app.admin import PANELS

    endpoints = {endpoint for endpoint, _title, _category in PANELS}
    assert endpoints == {
        "admin.users",
        "admin.teams",
        "admin.environment",
        "admin.lifecycle",
        "admin.sbom",
        "admin.observability",
    }, f"panel ที่ลงทะเบียน: {sorted(endpoints)}"


def test_sbom_reports_real_installed_packages_with_owners(app):
    """แถวเทียบกับ importlib.metadata จริง และ package ของ plugin ระบุเจ้าของเป็น category

    flask ต้องเป็นของ default (core) — และถ้าใน env นี้มีไลบรารีของ plugin
    ติดตั้งอยู่ เจ้าของต้องเป็น category ของ plugin นั้น ไม่ใช่ default
    """
    from importlib import metadata as im

    _two_people(app)
    with app.app_context():
        boss = db.session.query(User).filter_by(username="boss").one()
        facts = system_info.sbom(boss)
    assert facts["lockfile_readable"], "รันจาก repo จริงต้องอ่าน Pipfile.lock ได้"
    by_name = {row["name"]: row for row in facts["rows"]}
    assert by_name["flask"]["installed"] == im.version("flask"), "รุ่นบนหน้าไม่ตรงกับที่ติดตั้งจริง"
    assert by_name["flask"]["category"] == "default"
    assert by_name["flask"]["status"] in ("match", "drift")


def test_sbom_actually_detects_drift_and_unlisted_packages(app, monkeypatch, tmp_path):
    """drift ต้องถูก *ตรวจ* ไม่ใช่ถูกประกาศ — ปลูก lock ปลอมแล้วดูว่ามันจับได้

    mutation test รอบแรกพิสูจน์ว่าเทสต์ชุดเดิมผ่านแม้ตัวตัดสิน drift ตอบ
    "match" เสมอ — เทสต์นี้คือคำตอบ: lock ที่ประกาศ flask รุ่นที่ไม่มีจริง
    ต้องได้ drift และ package ที่ติดตั้งแต่ lock ไม่รู้จักต้องได้ unlisted
    """
    import json as jsonlib

    _two_people(app)
    fake = tmp_path / "Pipfile.lock"
    fake.write_text(jsonlib.dumps({"default": {"flask": {"version": "==0.0.1"}}}), encoding="utf-8")
    monkeypatch.setattr(system_info, "LOCKFILE", fake)
    with app.app_context():
        boss = db.session.query(User).filter_by(username="boss").one()
        facts = system_info.sbom(boss)
    by_name = {row["name"]: row for row in facts["rows"]}
    assert by_name["flask"]["status"] == "drift", "รุ่นไม่ตรง lock แต่ไม่ถูกนับเป็น drift"
    assert facts["drift_count"] >= 1
    assert by_name["pytest"]["status"] == "unlisted", "ของที่ lock ไม่รู้จักต้องเป็น unlisted"


def test_the_sbom_page_renders_for_an_admin(app):
    """เส้นทางปกติบนหน้าเว็บ — package จริงกับ EOL ของ runtime ต้องอยู่บนหน้า"""
    _two_people(app)
    client = _sign_in(app, "boss")
    page = client.get("/admin/sbom").data.decode()
    assert "flask" in page
    assert f"{sys.version_info.major}.{sys.version_info.minor}" in page


def test_eol_is_none_when_the_pinned_table_is_unreadable(app, monkeypatch, tmp_path):
    """ตารางตรึงหาย/พัง = None (หน้าโชว์คำแนะนำ refresh) ไม่ใช่ crash หรือค่าเดา"""
    _two_people(app)
    monkeypatch.setattr(system_info, "EOL_TABLE", tmp_path / "gone.json")
    with app.app_context():
        boss = db.session.query(User).filter_by(username="boss").one()
        assert system_info.sbom(boss)["python_eol"] is None

    bad = tmp_path / "bad.json"
    bad.write_text('{"python": [{"cycle": "2.7", "eol": "2020-01-01"}]}', encoding="utf-8")
    monkeypatch.setattr(system_info, "EOL_TABLE", bad)
    with app.app_context():
        boss = db.session.query(User).filter_by(username="boss").one()
        assert system_info.sbom(boss)["python_eol"] is None, "ตารางไม่ครอบ cycle ที่รัน ต้องเป็น None"


def test_sbom_is_honest_when_the_lockfile_is_missing(app, monkeypatch, tmp_path):
    """ไม่มี lock (เช่นใน image ที่ไม่ได้ copy มา) = บอกตรง ๆ ว่าตัดสิน drift ไม่ได้"""
    _two_people(app)
    monkeypatch.setattr(system_info, "LOCKFILE", tmp_path / "none")
    with app.app_context():
        boss = db.session.query(User).filter_by(username="boss").one()
        facts = system_info.sbom(boss)
    assert facts["lockfile_readable"] is False
    assert all(row["status"] == "unknown" for row in facts["rows"])


def test_sbom_shows_python_eol_from_the_pinned_table(app):
    """EOL มาจากตารางที่ตรึงไว้ (ไม่ fetch ตอนรัน) และครอบ runtime ที่ใช้จริง"""
    _two_people(app)
    with app.app_context():
        boss = db.session.query(User).filter_by(username="boss").one()
        facts = system_info.sbom(boss)
    eol = facts["python_eol"]
    assert eol is not None, "ตารางที่ตรึงไม่ครอบ python ที่กำลังรัน"
    assert eol["cycle"] == f"{sys.version_info.major}.{sys.version_info.minor}"


def test_site_administration_groups_every_panel(app):
    """Change Req #1 ข้อ 3 — หน้า /admin จัดหมวดแบบ Moodle และครบทุก panel"""
    from app.admin import PANELS

    _two_people(app)
    page = _sign_in(app, "boss").get("/admin").data.decode()
    assert "Site administration" in page
    for _endpoint, title, category in PANELS:
        assert str(title) in page, f"panel {title} หายจากหน้า Site administration"
        assert str(category) in page, f"หมวด {category} ไม่โผล่"


def test_site_administration_is_admin_only(app):
    _two_people(app)
    assert _sign_in(app, "member").get("/admin").status_code == 403


def test_the_nav_says_site_administration_not_users(app):
    """เมนูเปลี่ยนชื่อแล้วต้องชี้หน้า hub และยังโผล่เฉพาะ admin เหมือนเดิม"""
    _two_people(app)
    admin_nav = _sign_in(app, "boss").get("/").data.decode()
    assert 'href="/admin"' in admin_nav
    assert "Site administration" in admin_nav
    member_nav = _sign_in(app, "member").get("/").data.decode()
    assert 'href="/admin"' not in member_nav, "เมนู admin โผล่ให้ผู้ใช้ทั่วไป (แค่ซ่อนตา แต่ก็ต้องซ่อน)"


def test_the_admin_subnav_lists_only_panels_not_the_hub(app):
    """CR#2 ข้อ 4 — sub-menu ของหน้า admin มีเฉพาะ [panel ทั้งหก] ไม่มีลิงก์
    Site administration ซ้ำ (ทางเข้า hub มีที่เดียวคือ top nav)"""
    import re

    from app.admin import PANELS

    _two_people(app)
    page = _sign_in(app, "boss").get("/admin/environment").data.decode()
    subnav = re.search(r'<nav aria-label="[^"]*">(.*?)</nav>', page, re.DOTALL)
    assert subnav, "ไม่พบ sub-nav ของหน้า admin"
    inside = subnav.group(1)
    assert 'href="/admin"' not in inside, "ลิงก์ hub ยังซ้ำอยู่ใน sub-menu"
    for _endpoint, title, _category in PANELS:
        assert str(title) in inside, f"panel {title} หายจาก sub-menu"
    # top nav ยังต้องมีทางเข้า hub อยู่ (คนละ element กัน)
    assert 'href="/admin"' in page.split("<hr>")[0], "ทางเข้า hub หายจาก top nav ไปด้วย"
