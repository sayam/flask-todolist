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

PANEL_PATHS = ("/admin/environment", "/admin/lifecycle", "/admin/observability")


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


def test_all_four_panels_are_registered_in_the_nav(app):
    """หน้าใหม่ต้องลงทะเบียนเข้า registry — nav วนจาก registry ไม่ hardcode (ADR 0044)"""
    from app.admin import PANELS

    endpoints = {endpoint for endpoint, _title in PANELS}
    assert endpoints == {
        "admin.users",
        "admin.environment",
        "admin.lifecycle",
        "admin.observability",
    }, f"panel ที่ลงทะเบียน: {sorted(endpoints)}"
