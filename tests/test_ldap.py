"""ปัจจัยหลักแบบ `credential`: LDAP เป็น plugin (Phase 5 · P5-14 — ดู ADR 0029)

สามเรื่องที่ต้องพิสูจน์แยกกัน:

1. **ด่านที่กันของที่ directory ปลายทางอาจไม่ได้กันให้** — รหัสผ่านว่าง,
   การ bind ด้วย `dn` ของผู้ใช้เอง, และการบังคับ TLS
2. **ลำดับ**: รหัสผ่านของที่นี่มาก่อน directory ภายนอกเสมอ (ADR 0029 ข้อ 2)
3. **ถอดแล้วไม่พัง** ทั้งกรณีถอนไดเรกทอรีและกรณีไลบรารีหาย

**ไม่ยิง directory จริงในไฟล์นี้** — ปลอมชั้น `ldap3.Connection` ไว้ เพราะที่นี่
ตรวจ *ตรรกะของเรา* ส่วนการ bind กับ OpenLDAP จริงเป็นงานของด่านใน CI (P5-14d)
ซึ่งตอบคนละคำถาม · เทสต์ที่ import ไลบรารีต้องมาร์ค `plugin_deps` ให้ job `bare`
ข้ามได้ (**ห้ามใช้ `importorskip`** — job `test` จะข้ามเงียบ ๆ ตอนไลบรารีหาย
ซึ่งคือกรณีที่เราต้องการให้มันแดงที่สุด)
"""

import pytest

from app import db, plugins
from app.services import sso
from tests.conftest import PASSWORD, TestConfig, _app_with_tables, _make_user

pytestmark = pytest.mark.plugin_deps

LDAP_KEY = "auth/ldap"
DIRECTORY = "ldaps://directory.example.test"
SERVICE_DN = "cn=service,dc=example,dc=test"
SERVICE_PASSWORD = "service-account-password"
USER_DN = "uid=somchai,ou=people,dc=example,dc=test"
USER_PASSWORD = "directory-password-not-a-real-one"
ADMIN_GROUP = "cn=todolist-admins,ou=groups,dc=example,dc=test"


class LdapConfig(TestConfig):
    LDAP_URL = DIRECTORY
    LDAP_BIND_DN = SERVICE_DN
    LDAP_BIND_PASSWORD = SERVICE_PASSWORD
    LDAP_BASE_DN = "dc=example,dc=test"
    LDAP_USER_FILTER = "(uid=%s)"


def factor():
    return plugins.factor_module(plugins.find(LDAP_KEY))


class _Attribute:
    def __init__(self, values):
        self.values = list(values)
        self.value = values[0] if values else None


class _Entry:
    """entry ปลอมที่ตอบเฉพาะสองแบบที่โค้ดของเราใช้จริง"""

    def __init__(self, dn, attributes):
        self.entry_dn = dn
        self._attributes = attributes

    def __contains__(self, name):
        return name in self._attributes

    def __getitem__(self, name):
        return _Attribute(self._attributes[name])


class _Connection:
    """`ldap3.Connection` ปลอม — bind สำเร็จเฉพาะคู่ที่ directory รู้จักจริง

    `search()` ตอบสองแบบตามตัวกรองที่ได้รับ เหมือน directory จริง: ค้นผู้ใช้
    ด้วย `(uid=...)` และ **ค้นกลุ่มที่มีผู้ใช้คนนั้นเป็นสมาชิก** ด้วย `(member=...)`
    (อย่างหลังคือกลไกที่ใช้จริง — `memberOf` ไม่ได้มีในทุก directory)
    """

    known = {SERVICE_DN: SERVICE_PASSWORD, USER_DN: USER_PASSWORD}
    entry_attributes: dict = {"entryUUID": ["uuid-of-somchai"]}
    groups: list = [ADMIN_GROUP]
    found = True

    # ต้องรับพารามิเตอร์ให้ตรงกับ `ldap3.Connection` แม้จะไม่ได้ใช้ทุกตัว
    def __init__(self, server, user=None, password=None, **kwargs):  # noqa: ARG002
        self.server = server
        self.user = user
        self.password = password
        self.entries = []

    def bind(self):
        # **รหัสผ่านว่างสำเร็จเสมอ** — นี่คือพฤติกรรมจริงที่ทำให้ต้องมีด่านใน
        # โค้ดของเรา: RFC 4513 เรียก dn ที่มากับรหัสผ่านว่างว่า *unauthenticated
        # bind* และ server จำนวนมากตอบสำเร็จ ส่วน user ที่เป็น None คือ
        # *anonymous bind* ซึ่งสำเร็จเช่นกัน
        #
        # ตอนแรกเขียนไว้แค่กรณี `user is None` แล้ว **mutation test จับได้ว่า
        # ถอดด่านรหัสผ่านว่างออกก็ยังเขียว** เพราะ fake ตัวเก่าปฏิเสธรหัสว่างเอง
        # — fake ที่ใจดีกว่าของจริงทำให้เทสต์พิสูจน์สิ่งที่ไม่มีอยู่
        if self.user is None or not self.password:
            return True
        return self.known.get(self.user) == self.password

    def search(self, base, search_filter, attributes=None):  # noqa: ARG002
        if search_filter.startswith("(member="):
            self.entries = [_Entry(dn, {}) for dn in self.groups]
            return True
        self.entries = [_Entry(USER_DN, dict(self.entry_attributes))] if self.found else []
        return self.found

    def unbind(self):
        return True


@pytest.fixture
def ldap_app(monkeypatch):
    for app in _app_with_tables(LdapConfig):
        monkeypatch.setattr(factor().ldap3, "Connection", _Connection)
        monkeypatch.setattr(_Connection, "found", True)
        monkeypatch.setattr(
            _Connection,
            "entry_attributes",
            {"memberOf": [ADMIN_GROUP], "entryUUID": ["uuid-of-somchai"]},
        )
        yield app


def authenticate(app, username="somchai", password=USER_PASSWORD):
    with app.test_request_context():
        user = factor().authenticate(username, password)
        return None if user is None else (user.id, user.role)


# ------------------------------------------ 1. ด่านที่ต้องอยู่ในโค้ดของเราเอง


def test_an_empty_password_never_reaches_the_directory(ldap_app):
    """รหัสผ่านว่าง = ปฏิเสธทันที (ADR 0029 ข้อ 5)

    `_Connection.bind()` ปลอมของเราตอบสำเร็จให้รหัสผ่านว่างเหมือน directory
    จริงจำนวนมาก — ถ้าด่านนี้หายไป เทสต์จะเห็นทันทีว่ามีคน "ยืนยันตัวตนผ่าน"
    ด้วยการไม่พิมพ์อะไรเลย
    """
    with ldap_app.app_context():
        _make_user("somchai")
    assert authenticate(ldap_app, password="") is None


def test_a_blank_username_is_refused(ldap_app):
    assert authenticate(ldap_app, username="   ") is None


def test_a_wrong_password_is_refused(ldap_app):
    with ldap_app.app_context():
        _make_user("somchai")
    assert authenticate(ldap_app, password="not-the-right-one") is None


def test_a_user_the_directory_does_not_know_is_refused(ldap_app, monkeypatch):
    monkeypatch.setattr(_Connection, "found", False)
    assert authenticate(ldap_app) is None


def test_a_plain_ldap_url_is_refused_unless_opted_in(ldap_app):
    """รหัสผ่านเดินทางไป directory ทุกครั้งที่ login (ADR 0029 ข้อ 6)"""
    ldap_app.config["LDAP_URL"] = "ldap://directory.example.test"
    with ldap_app.test_request_context(), pytest.raises(Exception, match="directory"):
        factor().authenticate("somchai", USER_PASSWORD)


def test_binding_uses_the_dn_not_the_linking_identifier(ldap_app):
    """ตั้ง `LDAP_ID_ATTRIBUTE` แล้วต้องยัง bind ด้วย `dn` อยู่ดี

    ตัวระบุที่ใช้ผูกเป็น uuid ซึ่ง bind ไม่ได้ — ถ้าโค้ดเอาไปใช้แทน `dn`
    การยืนยันตัวตนจะล้มเสมอ หรือแย่กว่านั้นคือกลายเป็น anonymous bind ที่ผ่าน
    """
    ldap_app.config["LDAP_ID_ATTRIBUTE"] = "entryUUID"
    with ldap_app.app_context():
        user_id = _make_user("somchai")
    assert authenticate(ldap_app) == (user_id, "user")


# ---------------------------------------------------------- 2. การผูกบัญชี


def test_first_login_links_by_username_then_uses_the_identifier(ldap_app):
    with ldap_app.app_context():
        user_id = _make_user("somchai")
    assert authenticate(ldap_app)[0] == user_id
    # ครั้งที่สองต้องเจอจากแถวที่ผูกไว้ ไม่ใช่ค้นด้วยชื่ออีกรอบ
    assert authenticate(ldap_app)[0] == user_id


def test_unknown_user_is_refused_when_auto_create_is_off(ldap_app):
    assert authenticate(ldap_app) is None


def test_auto_create_makes_an_account_without_a_password(ldap_app):
    ldap_app.config["LDAP_AUTO_CREATE"] = "1"
    result = authenticate(ldap_app)
    assert result is not None
    with ldap_app.app_context():
        from app.models import User

        created = db.session.get(User, result[0])
        assert created.username == "somchai"
        assert not created.check_password(USER_PASSWORD)


def test_group_becomes_role_in_both_directions(ldap_app, monkeypatch):
    ldap_app.config["LDAP_AUTO_CREATE"] = "1"
    ldap_app.config["LDAP_ADMIN_GROUP"] = ADMIN_GROUP
    assert authenticate(ldap_app)[1] == "admin"

    monkeypatch.setattr(_Connection, "groups", ["cn=everyone,dc=example,dc=test"])
    assert authenticate(ldap_app)[1] == "user"


def test_role_is_untouched_when_no_group_is_configured(ldap_app):
    with ldap_app.app_context():
        from app.models import User

        user_id = _make_user("somchai")
        db.session.get(User, user_id).role = "admin"
        db.session.commit()
    assert authenticate(ldap_app) == (user_id, "admin")


# ------------------------------------- 3. ลำดับ และ "ถอดแล้วไม่พัง"


def test_the_local_password_is_tried_before_the_directory(ldap_app, monkeypatch):
    """รหัสผ่านของที่นี่ถูกต้อง = ไม่ต้องไปรบกวน directory เลย (ADR 0029 ข้อ 2)

    วันที่ directory ล่ม ผู้ดูแลที่มีรหัสผ่านของที่นี่ต้องยังเข้าได้ —
    เทสต์นี้ทำให้ directory "ล่ม" ด้วยการทำให้การเรียกมันระเบิด
    """
    with ldap_app.app_context():
        _make_user("somchai")

    def explode(*args, **kwargs):
        raise AssertionError("ไม่ควรถาม directory เมื่อรหัสผ่านของที่นี่ผ่านแล้ว")

    monkeypatch.setattr("app.auth.sso.authenticate", explode)
    response = ldap_app.test_client().post(
        "/login", data={"username": "somchai", "password": PASSWORD}
    )
    assert response.status_code == 302


def test_the_directory_is_consulted_when_the_local_password_fails(ldap_app):
    with ldap_app.app_context():
        _make_user("somchai")
    response = ldap_app.test_client().post(
        "/login", data={"username": "somchai", "password": USER_PASSWORD}
    )
    assert response.status_code == 302, "รหัสของ directory ต้องใช้ login ได้"


def test_a_directory_that_cannot_answer_does_not_break_the_login_page(ldap_app, monkeypatch):
    """directory ที่ config ผิด = login ไม่ผ่าน ไม่ใช่ 500

    และต้องดังใน log เพราะจากมุมของผู้ใช้มันเหมือนพิมพ์รหัสผิดทุกประการ
    """
    monkeypatch.setitem(ldap_app.config, "LDAP_BASE_DN", "")
    response = ldap_app.test_client().post(
        "/login", data={"username": "somchai", "password": USER_PASSWORD}
    )
    assert response.status_code == 401


def test_a_missing_library_disables_the_factor_instead_of_breaking(ldap_app, monkeypatch):
    """ไลบรารีหาย = ปิดตัวเอง (ADR 0025) — นี่คือสภาพของ job `bare`"""

    def no_library(plugin, module_name):
        raise ImportError("ไม่มี ldap3")

    monkeypatch.setattr(plugins, "load_module", no_library)
    with ldap_app.app_context():
        assert sso.directories() == []
        assert sso.authenticate("somchai", USER_PASSWORD) is None
    assert ldap_app.test_client().get("/login").status_code == 200


def test_the_manifest_decides_the_style_not_the_functions_present(ldap_app):
    """core อ่าน `style` จาก manifest ไม่ใช่เดาจากฟังก์ชันที่มี (ADR 0029 ข้อ 1)"""
    with ldap_app.app_context():
        assert [plugin.key for plugin in sso.directories()] == [LDAP_KEY]
        # ตัวนี้ไม่ใช่แบบ redirect จึงต้องไม่โผล่เป็นปุ่มบนหน้า login
        assert LDAP_KEY not in [plugin.key for plugin in sso.available()]
    assert b"/login/sso/auth/ldap" not in ldap_app.test_client().get("/login").data


def test_a_search_that_blows_up_becomes_a_refusal_not_a_500(ldap_app, monkeypatch):
    """directory ที่ตอบด้วย error ต้องกลายเป็น "login ไม่ผ่าน" ไม่ใช่ 500

    เจอจริงตอนต่อกับ OpenLDAP: ldap3 ปฏิเสธ `memberOf` ตาม schema ที่ดึงมา
    แล้ว exception หลุดขึ้นไปถึง Flask — หน้า login พังทั้งหน้าเพราะ config
    ของ directory ไม่ใช่เพราะโค้ดของเราผิด
    """
    import ldap3

    def explode(self, *args, **kwargs):
        raise ldap3.core.exceptions.LDAPAttributeError("invalid attribute type memberOf")

    monkeypatch.setattr(_Connection, "search", explode)
    with ldap_app.app_context():
        _make_user("somchai")
    response = ldap_app.test_client().post(
        "/login", data={"username": "somchai", "password": USER_PASSWORD}
    )
    assert response.status_code == 401
