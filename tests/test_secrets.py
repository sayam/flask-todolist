"""ความลับมาจากแหล่งที่ประกาศไว้ (Phase 5 · P5-15 — ดู ADR 0030)

สามเรื่องที่ต้องพิสูจน์แยกกัน:

1. **ค่าเริ่มต้นไม่เปลี่ยนอะไรเลย** — คนที่รันด้วย env อยู่แล้วต้องไม่ต้องตั้งอะไรเพิ่ม
2. **สองสถานะที่ต้องแยกให้ขาด**: "ไม่มีชื่อนั้นในแหล่ง" ตกกลับไป env ได้ ส่วน
   "ถามแหล่งไม่ได้เลย" ต้องทำให้แอปไม่ start (ข้อ 4 กับข้อ 6 ของ ADR)
3. **ความลับที่มาจากแหล่งต้องมีผลจริง** ไม่ใช่แค่ถูกอ่านมาแล้ววางทิ้งไว้
"""

import pytest

from app import create_app, plugins, secrets
from tests.conftest import TestConfig, _app_with_tables

LONG_ENOUGH_KEY = "a-secret-key-that-came-from-a-file-not-from-env"


@pytest.fixture
def secrets_dir(tmp_path):
    """ไดเรกทอรีแบบเดียวกับที่ docker/kubernetes mount ให้"""
    directory = tmp_path / "run-secrets"
    directory.mkdir()
    return directory


def config_using(directory, **extra):
    class FileSecretsConfig(TestConfig):
        SECRETS_URL = f"file://{directory}"

    for name, value in extra.items():
        setattr(FileSecretsConfig, name, value)
    return FileSecretsConfig


# ------------------------------------------------- 1. ค่าเริ่มต้นต้องไม่เปลี่ยนอะไร


def test_the_default_source_changes_nothing(app):
    """`env://` ต้องให้ผลเหมือนเดิมทุกประการ — ไม่งั้นทุกคนที่ clone มาต้องมาตั้งค่าเพิ่ม"""
    with app.app_context():
        assert secrets.active().key == "secrets/env"
    assert app.config["SECRET_KEY"] == TestConfig.SECRET_KEY


def test_an_unknown_scheme_refuses_to_start(monkeypatch):
    """scheme ที่พิมพ์ผิดคือ config ที่ผิด **ไม่ใช่คำสั่งให้ใช้ค่าเริ่มต้น**

    ตกกลับ env เงียบ ๆ แปลว่าวันที่ตั้ง URL ผิด ระบบจะรันต่อด้วยความลับชุดเก่า
    ที่ยังค้างอยู่ใน env โดยไม่มีใครรู้ (ADR 0030 ข้อ 6 · หลักเดียวกับ ADR 0026)
    """

    class Broken(TestConfig):
        SECRETS_URL = "vaultt://typo"

    with pytest.raises(plugins.PluginError, match="vaultt"):
        create_app(Broken)


# --------------------------------------- 2. "ไม่มีค่า" กับ "ถามไม่ได้" คนละเรื่อง


def test_a_source_directory_that_is_missing_refuses_to_start(tmp_path):
    """path ที่พิมพ์ผิดกับ path ที่ยังไม่ได้ mount ให้ผลเหมือนกันเป๊ะ

    ถ้าปล่อยผ่านเป็น "ไม่มีความลับสักตัว" ระบบจะรันด้วยค่าจาก environment
    ทั้งที่ผู้ดูแลตั้งใจย้ายไปไฟล์แล้ว — ซึ่งคือความล้มเหลวที่เงียบที่สุดแบบหนึ่ง
    """
    with pytest.raises(plugins.PluginError, match="ไม่มีไดเรกทอรี"):
        create_app(config_using(tmp_path / "never-mounted"))


def test_a_name_the_source_does_not_have_falls_back_to_the_environment(secrets_dir):
    """แหล่งที่ไม่มีชื่อนั้น = ตกกลับไป env ได้ (ADR 0030 ข้อ 4)

    ไก่กับไข่ที่แก้ไม่ได้: แหล่งความลับเองต้องมี credential จากที่อื่น
    สิ่งที่ทำได้คือทำให้ของที่ยังอยู่ใน env เหลือน้อยที่สุด ไม่ใช่ศูนย์
    """
    for app in _app_with_tables(config_using(secrets_dir)):
        with app.app_context():
            # ไม่มีไฟล์ชื่อนี้ในไดเรกทอรี → ต้องได้ค่าจาก environment
            assert secrets.get("PATH") == __import__("os").environ["PATH"]
            assert secrets.get("ไม่มีชื่อนี้แน่ ๆ", "ค่าสำรอง") == "ค่าสำรอง"


# ------------------------------------------- 3. ความลับจากแหล่งต้องมีผลจริง


def test_a_secret_from_a_file_wins_over_the_environment(secrets_dir, monkeypatch):
    """ค่าที่อยู่ในแหล่งต้องชนะ env ไม่งั้นการย้ายไปไฟล์ไม่มีความหมาย"""
    monkeypatch.setenv("SECRET_KEY", "this-is-the-old-value-from-environment")
    (secrets_dir / "secret_key").write_text(LONG_ENOUGH_KEY)
    for app in _app_with_tables(config_using(secrets_dir)):
        assert app.config["SECRET_KEY"] == LONG_ENOUGH_KEY


def test_a_trailing_newline_in_the_file_is_ignored(secrets_dir):
    """editor เติม `\\n` ให้เอง — ความลับที่มีมันต่อท้ายจะทำให้ HMAC ไม่ตรง
    โดยไม่มีใครเห็นสาเหตุ"""
    (secrets_dir / "secret_key").write_text(LONG_ENOUGH_KEY + "\n")
    for app in _app_with_tables(config_using(secrets_dir)):
        assert app.config["SECRET_KEY"] == LONG_ENOUGH_KEY


# **สองตัวนี้ต้องมาร์ค `plugin_deps`** เพราะการตั้ง `CACHE_URL` เป็น `redis://`
# ทำให้ `create_app()` ต้องโหลด backend ของ redis จริง ซึ่งไม่มีในโหมด `bare`
# — เลือก scheme ที่ไม่ต้องมีไลบรารีไม่ได้ เพราะค่าเริ่มต้น (`memory://`) คือค่า
# ที่เราต้องพิสูจน์ว่ามัน *เปลี่ยน* ไปแล้ว (เจอตอน job `bare` แดง — P5-15)
@pytest.mark.plugin_deps
def test_the_rate_limit_store_follows_a_cache_url_that_came_from_a_file(secrets_dir):
    """**`RATELIMIT_STORAGE_URI` ตามหลัง `CACHE_URL` (P5-07)**

    ความสัมพันธ์นั้นถูกคำนวณตอนสร้างคลาส `Config` ซึ่งเกิดก่อนที่แหล่งความลับ
    จะถูกอ่าน — ถ้าไม่ตามมาแก้ การย้าย `CACHE_URL` ไปไว้ในไฟล์จะทำให้โควตา
    rate limit เงียบ ๆ ย้อนกลับไปนับแยกต่อ process ซึ่งคือหนี้ที่ P5-07 เพิ่งปิด
    """
    (secrets_dir / "cache_url").write_text("redis://cache.example.test:6379/0")
    for app in _app_with_tables(config_using(secrets_dir)):
        assert app.config["CACHE_URL"] == "redis://cache.example.test:6379/0"
        assert app.config["RATELIMIT_STORAGE_URI"] == "redis://cache.example.test:6379/0"


@pytest.mark.plugin_deps
def test_an_explicit_rate_limit_store_is_not_overwritten(secrets_dir, monkeypatch):
    """ตั้งแยกไว้เองแล้วต้องไม่ถูกกลืน — P5-07 เขียนไว้ว่าตั้งแยกได้ถ้าตั้งใจ"""
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://counters.example.test:6379/1")
    (secrets_dir / "cache_url").write_text("redis://cache.example.test:6379/0")

    class Explicit(config_using(secrets_dir)):
        RATELIMIT_STORAGE_URI = "redis://counters.example.test:6379/1"

    for app in _app_with_tables(Explicit):
        assert app.config["RATELIMIT_STORAGE_URI"] == "redis://counters.example.test:6379/1"


def test_the_source_is_per_app_not_global(secrets_dir):
    """แอปสองตัวในโปรเซสเดียวต้องมีแหล่งของตัวเอง

    ถ้าเก็บไว้เป็นตัวแปรระดับโมดูล แหล่งของเทสต์หนึ่งจะรั่วไปให้อีกเทสต์
    แล้วผลจะขึ้นกับลำดับการรัน ซึ่งเป็นบั๊กที่หายากที่สุดชนิดหนึ่ง
    """
    (secrets_dir / "secret_key").write_text(LONG_ENOUGH_KEY)
    for from_file in _app_with_tables(config_using(secrets_dir)):
        from_env = create_app(TestConfig)
        with from_file.app_context():
            assert secrets.active().key == "secrets/file"
        with from_env.app_context():
            assert secrets.active().key == "secrets/env"
        assert from_env.config["SECRET_KEY"] == TestConfig.SECRET_KEY


def test_a_secret_key_that_exists_only_in_the_source_is_enough_to_start(secrets_dir):
    """**นี่คือเหตุผลที่ `init_secrets()` ต้องมาก่อน `check_secret_key()`**

    config ไม่มี `SECRET_KEY` เลย มีแต่ในไฟล์ — ถ้าลำดับสลับกัน แอปจะปฏิเสธ
    ที่จะ start ทั้งที่ค่ามีอยู่ ซึ่งเป็นอาการที่อ่านแล้วนึกว่าตั้งค่าผิด
    """
    (secrets_dir / "secret_key").write_text(LONG_ENOUGH_KEY)

    class NoKeyInConfig(config_using(secrets_dir)):
        SECRET_KEY = None

    for app in _app_with_tables(NoKeyInConfig):
        assert app.config["SECRET_KEY"] == LONG_ENOUGH_KEY


# ------------------------------------------------------ 4. Vault (ADR 0030)
#
# **ไม่ยิง Vault จริงที่นี่** — ปลอมชั้น `hvac.Client` ไว้ เพราะที่นี่ตรวจ
# *ตรรกะของเรา* (แยก mount กับ path, บังคับ token, ทำ key ให้เป็นตัวพิมพ์เล็ก
# เพื่อให้ย้ายไป-กลับ `file://` ได้) ส่วนการคุยกับ Vault ของจริงเป็นงานของ
# ด่านใน CI ซึ่งตอบคนละคำถาม


VAULT_KEY = "secrets/vault"


def vault_module():
    return plugins.load_module(plugins.find(VAULT_KEY), "source")


class _FakeKv:
    stored = {"SECRET_KEY": LONG_ENOUGH_KEY, "cache_url": "redis://from-vault:6379/0"}
    last: dict = {}

    # รับพารามิเตอร์ให้ตรงกับ hvac แม้จะไม่ได้ใช้ทุกตัว
    def read_secret_version(self, mount_point, path, **kwargs):  # noqa: ARG002 - required by interface
        _FakeKv.last = {"mount_point": mount_point, "path": path}
        return {"data": {"data": dict(self.stored)}}


class _FakeClient:
    def __init__(self, url, token):
        self.url = url
        self.token = token
        self.secrets = type("S", (), {"kv": type("K", (), {"v2": _FakeKv()})()})()


# ทุกตัวที่ใช้ fixture นี้ต้องมี `hvac` เพราะ `source.py` import มันตอนโหลด
# (**ห้ามใช้ `importorskip`** — job `test` จะข้ามเงียบ ๆ ตอนไลบรารีหาย
# ซึ่งคือกรณีที่เราต้องการให้มันแดงที่สุด)
@pytest.fixture
def fake_vault(monkeypatch):
    module = vault_module()
    monkeypatch.setattr(module.hvac, "Client", _FakeClient)
    monkeypatch.setenv("VAULT_TOKEN", "a-token-that-came-from-the-environment")
    return module


@pytest.mark.plugin_deps
def test_vault_splits_the_mount_from_the_path(fake_vault):
    fake_vault.connect("vault://vault.example.test:8200/secret/todolist")
    assert _FakeKv.last == {"mount_point": "secret", "path": "todolist"}


@pytest.mark.plugin_deps
def test_vault_lowercases_keys_so_the_exit_path_works(fake_vault):
    """ชื่อคีย์ต้องเป็นตัวพิมพ์เล็กเหมือน backend `file`

    ไม่งั้นการย้ายจาก Vault กลับไปไฟล์ (exit path — ADR 0030 ข้อ 7) จะต้อง
    เปลี่ยนชื่อทุกตัว ซึ่งเปลี่ยน "แก้ config หนึ่งบรรทัด" เป็นงานย้ายของ
    """
    handle = fake_vault.connect("vault://vault.example.test:8200/secret/todolist")
    assert fake_vault.get(handle, "SECRET_KEY") == LONG_ENOUGH_KEY
    assert fake_vault.get(handle, "CACHE_URL") == "redis://from-vault:6379/0"
    assert fake_vault.get(handle, "ไม่มีคีย์นี้") is None


@pytest.mark.plugin_deps
def test_vault_without_a_token_refuses_to_start(fake_vault, monkeypatch):
    """**ไม่เดาว่าจะอ่านโดยไม่ต้องยืนยันตัวตนได้** — Vault แบบนั้นคือ Vault ที่ตั้งผิด"""
    monkeypatch.delenv("VAULT_TOKEN", raising=False)
    with pytest.raises(plugins.PluginError, match="VAULT_TOKEN"):
        fake_vault.connect("vault://vault.example.test:8200/secret/todolist")


@pytest.mark.parametrize(
    "url",
    ["vault://vault.example.test:8200/secret", "vault:///secret/todolist"],
)
@pytest.mark.plugin_deps
def test_vault_urls_that_are_missing_a_part_refuse_to_start(fake_vault, url):
    with pytest.raises(plugins.PluginError):
        fake_vault.connect(url)


@pytest.mark.plugin_deps
def test_vault_that_cannot_be_read_refuses_to_start(fake_vault, monkeypatch):
    """ถามไม่ได้ = ไม่ start (ADR 0030 ข้อ 6) ไม่ใช่ตกกลับไปใช้ค่าเก่าใน env"""

    def explode(self, mount_point, path, **kwargs):
        raise ConnectionError("vault is sealed")

    monkeypatch.setattr(_FakeKv, "read_secret_version", explode)
    with pytest.raises(plugins.PluginError, match="ConnectionError"):
        fake_vault.connect("vault://vault.example.test:8200/secret/todolist")
