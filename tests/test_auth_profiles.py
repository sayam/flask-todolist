"""auth หลาย profile ต่อ plugin เดียว (ADR 0047) — สองทิศทุกข้อที่ ADR สัญญา

- ลำดับใน `AUTH_PROFILES` คือลำดับที่ลอง และ**คำตอบใด ๆ เป็นที่สิ้นสุด**:
  "ปฏิเสธ/ไม่รู้จัก" หยุดทันที (กันโควตาเดารหัส × จำนวนวง และกันบัญชีชื่อซ้ำ
  login ข้ามวง) — fallback เกิดเฉพาะ "ติดต่อไม่ได้" (`UnreachableError`)
- ค่าของ profile มาจากคีย์ที่มี prefix เท่านั้น ไม่ตกกลับคีย์เปล่า
- ปิดทีละ profile ได้ด้วยคีย์ `auth/<id>:<ชื่อ>` โดยตัวอื่นไม่กระทบ
- config ที่ชี้ของที่ไม่มี = แอปไม่ start (หลัก ADR 0026)
"""

import pytest

from app import db, plugins
from app.services import sso
from tests.conftest import TestConfig, _app_with_tables

CORP_ISSUER = "https://corp-idp.example.test"
PARTNER_ISSUER = "https://partner-idp.example.test"


class TwoIdpConfig(TestConfig):
    AUTH_PROFILES = ("oidc:corp", "oidc:partner")
    OIDC_CORP_ISSUER = CORP_ISSUER
    OIDC_CORP_CLIENT_ID = "todolist-corp"
    OIDC_CORP_CLIENT_SECRET = "corp-secret-not-a-real-one"
    OIDC_PARTNER_ISSUER = PARTNER_ISSUER
    OIDC_PARTNER_CLIENT_ID = "todolist-partner"
    OIDC_PARTNER_CLIENT_SECRET = "partner-secret-not-a-real-one"
    EXTERNAL_URL = "https://todolist.example.test"


def _fake_fetch(url, data=None):
    """IdP ปลอมสองเจ้า — discovery ตอบ endpoint ใต้ issuer ของตัวเอง"""
    issuer = url.split("/.well-known")[0]
    return {
        "issuer": issuer,
        "authorization_endpoint": f"{issuer}/authorize",
        "token_endpoint": f"{issuer}/token",
    }


def _oidc_module():
    return plugins.factor_module(plugins.find("auth/oidc"))


@pytest.fixture
def two_idp_app(monkeypatch):
    for app in _app_with_tables(TwoIdpConfig):
        monkeypatch.setattr(_oidc_module(), "_fetch", _fake_fetch)
        yield app


# ---------------------------------------------------------------- ปุ่มบนหน้า login


def test_each_declared_profile_gets_its_own_button(two_idp_app):
    page = two_idp_app.test_client().get("/login").data.decode()
    assert "auth/oidc:corp" in page
    assert "auth/oidc:partner" in page


def test_the_default_labels_are_distinct_per_profile(two_idp_app):
    """ปุ่มสองใบชื่อเหมือนกันเป๊ะ = ผู้ใช้เดาเอาว่าใบไหนของวงไหน"""
    with two_idp_app.app_context():
        labels = [provider.label for provider in sso.available()]
    assert len(labels) == len(set(labels)), f"ป้ายปุ่มซ้ำกัน: {labels}"
    assert any("corp" in label for label in labels)


def test_a_label_can_be_set_per_profile(monkeypatch):
    class Labeled(TwoIdpConfig):
        OIDC_CORP_LABEL = "Corp single sign-on"

    for app in _app_with_tables(Labeled):
        monkeypatch.setattr(_oidc_module(), "_fetch", _fake_fetch)
        page = app.test_client().get("/login").data.decode()
        assert "Corp single sign-on" in page


def test_an_unconfigured_profile_has_no_button(monkeypatch):
    """profile ที่ config ไม่ครบต้องหายไปจากหน้า login ไม่ใช่กดแล้วพัง"""

    class HalfConfigured(TwoIdpConfig):
        OIDC_PARTNER_ISSUER = None
        OIDC_PARTNER_CLIENT_ID = None

    for app in _app_with_tables(HalfConfigured):
        monkeypatch.setattr(_oidc_module(), "_fetch", _fake_fetch)
        page = app.test_client().get("/login").data.decode()
        assert "auth/oidc:corp" in page
        assert "auth/oidc:partner" not in page


def test_profile_settings_never_fall_back_to_the_bare_key(monkeypatch):
    """คีย์เปล่า `OIDC_ISSUER` ต้องไม่ถูก "ยืม" โดย profile — ADR 0047 ห้ามตรง ๆ

    ถ้ากิ่ง fallback ถูกเผลอเขียนกลับเข้ามา profile ที่ไม่มีคีย์ของตัวเอง
    จะโผล่เป็นปุ่มทั้งที่ไม่มีใครตั้งค่าให้มัน — เทสต์นี้ต้องแดงทันที
    """

    class BareKeyOnly(TestConfig):
        AUTH_PROFILES = ("oidc:corp",)
        OIDC_ISSUER = CORP_ISSUER
        OIDC_CLIENT_ID = "todolist"
        EXTERNAL_URL = "https://todolist.example.test"

    for app in _app_with_tables(BareKeyOnly):
        monkeypatch.setattr(_oidc_module(), "_fetch", _fake_fetch)
        with app.app_context():
            assert sso.available() == [], "profile corp ยืมค่าจากคีย์เปล่าได้ — ห้ามเกิด"


def test_sso_begin_uses_that_profiles_issuer(two_idp_app):
    """คนกดปุ่ม corp ต้องถูกส่งไป IdP ของ corp — ไม่ใช่ของ partner"""
    client = two_idp_app.test_client()
    corp = client.get("/login/sso/auth/oidc:corp")
    partner = client.get("/login/sso/auth/oidc:partner")
    assert corp.status_code == 302
    assert corp.headers["Location"].startswith(CORP_ISSUER)
    assert partner.status_code == 302
    assert partner.headers["Location"].startswith(PARTNER_ISSUER)
    assert "client_id=todolist-corp" in corp.headers["Location"]
    assert "client_id=todolist-partner" in partner.headers["Location"]


def test_the_active_profile_never_leaks_out_of_the_call(two_idp_app):
    with two_idp_app.app_context():
        provider = sso.find("auth/oidc:corp")
        sso.begin(provider, "https://todolist.example.test/cb")
        assert plugins.active_profile() is None, "contextvar ต้องถูก reset เสมอ"


def test_disabling_one_profile_leaves_the_other_alone(monkeypatch):
    class CorpDisabled(TwoIdpConfig):
        DISABLED_PLUGINS = frozenset({"auth/oidc:corp"})

    for app in _app_with_tables(CorpDisabled):
        monkeypatch.setattr(_oidc_module(), "_fetch", _fake_fetch)
        page = app.test_client().get("/login").data.decode()
        assert "auth/oidc:partner" in page
        assert "auth/oidc:corp" not in page
        with app.app_context():
            from app.services.errors import ValidationError

            with pytest.raises(ValidationError):
                sso.find("auth/oidc:corp")


# ---------------------------------------------------------------- config ที่ผิดต้องดัง


def test_a_profile_pointing_at_a_missing_plugin_stops_the_app(monkeypatch):
    class Ghost(TestConfig):
        AUTH_PROFILES = ("ghostly:corp",)

    boot = _app_with_tables(Ghost)
    with pytest.raises(plugins.PluginError, match="ghostly"):
        next(boot)


def test_a_malformed_profile_entry_stops_the_app():
    class Malformed(TestConfig):
        AUTH_PROFILES = ("oidc-corp",)

    boot = _app_with_tables(Malformed)
    with pytest.raises(plugins.PluginError, match="oidc-corp"):
        next(boot)


def test_a_duplicate_profile_stops_the_app():
    class Doubled(TestConfig):
        AUTH_PROFILES = ("oidc:corp", "oidc:corp")

    boot = _app_with_tables(Doubled)
    with pytest.raises(plugins.PluginError, match="ซ้ำ"):
        next(boot)


def test_plugin_list_prints_profile_keys(two_idp_app):
    """คีย์ที่ไม่เคยถูกพิมพ์ออกมา คือคีย์ที่ไม่มีใครใส่ลง DISABLED_PLUGINS ได้ถูก"""
    result = two_idp_app.test_cli_runner().invoke(args=["plugin-list"])
    assert "auth/oidc:corp" in result.output
    assert "auth/oidc:partner" in result.output


def test_the_key_name_mapping_inserts_the_profile_after_the_first_token(app):
    with app.app_context(), plugins.using_profile("corp"):
        assert plugins.profile_setting_name("OIDC_ISSUER") == "OIDC_CORP_ISSUER"
        assert plugins.profile_setting_name("LDAP_BIND_DN") == "LDAP_CORP_BIND_DN"
        # ชื่อคีย์คำเดียว (ไม่มี _) ต่อชื่อ profile ท้ายคำ — กิ่งที่ลืมง่ายที่สุด
        assert plugins.profile_setting_name("TOKEN") == "TOKEN_CORP"
    with app.app_context():
        assert plugins.profile_setting_name("OIDC_ISSUER") == "OIDC_ISSUER"


def test_a_profile_on_a_second_factor_plugin_stops_the_app():
    """profile มีความหมายกับปัจจัยหลักภายนอกเท่านั้น — ชี้ไปที่ปัจจัยที่สอง
    (auth/totp มีจริงบนดิสก์) ต้องดังตั้งแต่ start ไม่ใช่เงียบแล้วไม่มีผลอะไร"""

    class SecondFactor(TestConfig):
        AUTH_PROFILES = ("totp:corp",)

    boot = _app_with_tables(SecondFactor)
    with pytest.raises(plugins.PluginError, match="ปัจจัยหลัก"):
        next(boot)


def test_disabling_an_undeclared_profile_warns_that_it_does_nothing():
    """คีย์ profile ที่พิมพ์ผิดหน้าตาเหมือนการปิดสำเร็จเป๊ะ — ต้องมีเสียงเตือน
    (จับที่ logger ชื่อ "app" ก่อนสร้างแอป เพราะคำเตือนดังระหว่าง create_app)"""
    import logging

    class Typo(TwoIdpConfig):
        DISABLED_PLUGINS = frozenset({"auth/oidc:nosuch"})

    lines: list[str] = []

    class Grab(logging.Handler):
        def emit(self, record):
            lines.append(record.getMessage())

    handler = Grab(level=logging.WARNING)
    logging.getLogger("app").addHandler(handler)
    try:
        for _app in _app_with_tables(Typo):
            break
    finally:
        logging.getLogger("app").removeHandler(handler)
    assert any("ไม่ได้ปิดอะไรเลย" in line for line in lines), lines


def test_a_plugin_without_the_optional_configured_hook_is_assumed_ready(two_idp_app, monkeypatch):
    """สัญญา `configured()` เป็นของเสริม — plugin ที่เขียนก่อน ADR 0047
    (ไม่มีฟังก์ชันนี้) ต้องยังโผล่ครบ ไม่ใช่หายไปเงียบ ๆ ทั้งตัว"""
    monkeypatch.delattr(_oidc_module(), "configured")
    with two_idp_app.app_context():
        assert len(sso.available()) == 2


# ---------------------------------------------------------------- ฝั่ง credential (LDAP)

HQ_HOST = "hq.example.test"
PARTNER_HOST = "partner.example.test"
PASSWORD_AT_HQ = "hq-password-not-a-real-one"
PASSWORD_AT_PARTNER = "partner-password-not-a-real-one"


class TwoDirectoriesConfig(TestConfig):
    AUTH_PROFILES = ("ldap:hq", "ldap:partner")
    LDAP_HQ_URL = f"ldaps://{HQ_HOST}"
    LDAP_HQ_BASE_DN = "dc=hq,dc=example,dc=test"
    LDAP_HQ_USER_FILTER = "(uid=%s)"
    LDAP_HQ_AUTO_CREATE = "1"
    LDAP_PARTNER_URL = f"ldaps://{PARTNER_HOST}"
    LDAP_PARTNER_BASE_DN = "dc=partner,dc=example,dc=test"
    LDAP_PARTNER_USER_FILTER = "(uid=%s)"
    LDAP_PARTNER_AUTO_CREATE = "1"


ldap_marker = pytest.mark.plugin_deps  # ฝั่งนี้ต้องมี ldap3 (category ของ plugin)


def _ldap_module():
    return plugins.factor_module(plugins.find("auth/ldap"))


_DIRECTORY_USERS = {
    HQ_HOST: {"uid=alice,ou=people,dc=hq,dc=example,dc=test": PASSWORD_AT_HQ},
    PARTNER_HOST: {
        "uid=alice,ou=people,dc=partner,dc=example,dc=test": PASSWORD_AT_PARTNER,
        "uid=bob,ou=people,dc=partner,dc=example,dc=test": PASSWORD_AT_PARTNER,
    },
}


class _FakeEntry:
    def __init__(self, dn):
        self.entry_dn = dn

    def __contains__(self, name):
        return False


class _FakeDirectories:
    """`ldap3.Connection` ปลอมสองวง — คนละชุดผู้ใช้ คนละรหัสผ่าน

    วงที่อยู่ใน `down` ต่อไม่ติด (โยน exception แบบเดียวกับ socket ที่ล้ม)
    และทุก connection ที่เปิดสำเร็จถูกจดลง `consulted` ให้เทสต์อ่านลำดับได้
    """

    down: frozenset = frozenset()
    consulted: list | None = None

    def __init__(self, server, user=None, password=None, **kwargs):  # noqa: ARG002 - required by interface
        import ldap3

        if server.host in type(self).down:
            raise ldap3.core.exceptions.LDAPSocketOpenError(f"{server.host} down")
        if type(self).consulted is not None:
            type(self).consulted.append(server.host)
        self.host = server.host
        self.user = user
        self.password = password
        self.entries = []

    def bind(self):
        if self.user is None:
            return True  # anonymous bind — บัญชีบริการไม่ได้ตั้งในเทสต์นี้
        if not self.password:
            return True  # unauthenticated bind — ด่านของโค้ดเราต้องกันเอง
        return _DIRECTORY_USERS[self.host].get(self.user) == self.password

    def search(self, base, search_filter, attributes=None):  # noqa: ARG002 - required by interface
        username = search_filter[len("(uid=") : -1]
        matches = [dn for dn in _DIRECTORY_USERS[self.host] if dn.startswith(f"uid={username},")]
        self.entries = [_FakeEntry(dn) for dn in matches]
        return bool(matches)

    def unbind(self):
        return True


def _two_directories(monkeypatch, down=(), consulted=None):
    monkeypatch.setattr(_FakeDirectories, "down", frozenset(down))
    monkeypatch.setattr(_FakeDirectories, "consulted", consulted)
    monkeypatch.setattr(_ldap_module().ldap3, "Connection", _FakeDirectories)


@ldap_marker
def test_a_rejection_stops_the_chain_dead(monkeypatch):
    """bob มีตัวจริงอยู่ที่ partner — แต่ hq ตอบ "ไม่รู้จัก" ก่อน และคำตอบเป็นที่
    สิ้นสุด (ADR 0047): ไม่มีการเลื่อนไปถามวงถัดไป ไม่งั้นบัญชีชื่อซ้ำสองวง
    จะ login ข้ามวงกันได้ และคนเดารหัสได้โควตาคูณสอง"""
    consulted: list[str] = []
    for app in _app_with_tables(TwoDirectoriesConfig):
        _two_directories(monkeypatch, consulted=consulted)
        with app.test_request_context():
            assert sso.authenticate("bob", PASSWORD_AT_PARTNER) is None
        assert PARTNER_HOST not in consulted, "วงที่สองถูกถามทั้งที่วงแรกตอบแล้ว"


@ldap_marker
def test_an_unreachable_directory_falls_through_to_the_next(monkeypatch):
    consulted: list[str] = []
    for app in _app_with_tables(TwoDirectoriesConfig):
        _two_directories(monkeypatch, down={HQ_HOST}, consulted=consulted)
        with app.test_request_context():
            user = sso.authenticate("bob", PASSWORD_AT_PARTNER)
        assert user is not None, "วงแรกล่มต้องตกไปถามวงถัดไป (ADR 0047)"
        # partner โผล่สองครั้ง (ค้นด้วยบัญชีบริการ + bind ด้วยตัวผู้ใช้) — ที่ต้อง
        # ไม่มีเลยคือ hq เพราะมันต่อไม่ติดตั้งแต่เปิด connection
        assert set(consulted) == {PARTNER_HOST}


@ldap_marker
def test_the_declared_order_is_the_order_tried(monkeypatch):
    """alice อยู่ทั้งสองวงด้วยรหัสคนละชุด — วงแรกตามลำดับประกาศเป็นผู้ตัดสิน"""
    for app in _app_with_tables(TwoDirectoriesConfig):
        _two_directories(monkeypatch)
        with app.test_request_context():
            assert sso.authenticate("alice", PASSWORD_AT_HQ) is not None
            db.session.rollback()
            assert sso.authenticate("alice", PASSWORD_AT_PARTNER) is None, (
                "รหัสของ partner ใช้ได้ทั้งที่ hq ตอบปฏิเสธไปแล้ว — ข้ามวงกันแล้ว"
            )


@ldap_marker
def test_disabling_one_directory_profile_skips_it_entirely(monkeypatch):
    class HqDisabled(TwoDirectoriesConfig):
        DISABLED_PLUGINS = frozenset({"auth/ldap:hq"})

    consulted: list[str] = []
    for app in _app_with_tables(HqDisabled):
        _two_directories(monkeypatch, consulted=consulted)
        with app.test_request_context():
            user = sso.authenticate("bob", PASSWORD_AT_PARTNER)
        assert user is not None
        assert HQ_HOST not in consulted, "profile ที่ปิดแล้วต้องเหมือนไม่ถูกประกาศ"


@ldap_marker
def test_two_directories_bind_to_two_separate_identities(monkeypatch):
    """คนของ hq กับคนของ partner ต้องเป็นคนละแถว identity — คอลัมน์ directory
    คือ URL ของ profile นั้น จึงไม่มีทางพันกันแม้ `uid` จะซ้ำกัน"""
    for app in _app_with_tables(TwoDirectoriesConfig):
        _two_directories(monkeypatch)
        with app.test_request_context():
            alice = sso.authenticate("alice", PASSWORD_AT_HQ)
            directory_of = {
                row.directory
                for row in _ldap_module().DirectoryIdentity.query.filter_by(user_id=alice.id)
            }
            assert directory_of == {f"ldaps://{HQ_HOST}"}


@ldap_marker
def test_one_user_can_hold_identities_from_two_directories(monkeypatch):
    """ปิดของค้าง "ผูกหลาย IdP กับผู้ใช้คนเดียว" (ADR 0047 — ผลพลอยได้ของ profile):
    alice login ผ่าน hq หนึ่งครั้ง แล้ววันที่ hq ล่มก็ login ผ่าน partner ได้
    ด้วยบัญชีเดิม — identity สองแถว คนละ directory ชี้ user เดียวกัน"""
    for app in _app_with_tables(TwoDirectoriesConfig):
        _two_directories(monkeypatch)
        with app.test_request_context():
            first = sso.authenticate("alice", PASSWORD_AT_HQ)
            first_id = first.id

        _two_directories(monkeypatch, down={HQ_HOST})
        with app.test_request_context():
            second = sso.authenticate("alice", PASSWORD_AT_PARTNER)
            assert second is not None, "hq ล่มแล้ว partner ต้องรับช่วงได้"
            assert second.id == first_id, "ต้องเป็นบัญชีเดิม ไม่ใช่สร้างคนใหม่ซ้อน"
            directories = {
                row.directory
                for row in _ldap_module().DirectoryIdentity.query.filter_by(user_id=first_id)
            }
            assert directories == {f"ldaps://{HQ_HOST}", f"ldaps://{PARTNER_HOST}"}
