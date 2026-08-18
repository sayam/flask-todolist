"""เทสต์ว่าแอปไม่ยอม start ถ้า SECRET_KEY ไม่ปลอดภัย

จุดสำคัญคือ "พังตั้งแต่ตอน start" ไม่ใช่ "รันได้แต่ไม่ปลอดภัย"
เพราะ session และ CSRF token เซ็นด้วยคีย์นี้ทั้งคู่
"""

import pytest

from app import create_app
from config import MIN_SECRET_KEY_LENGTH, Config
from tests.conftest import TestConfig


def _config_with(secret_key):
    return type("Cfg", (TestConfig,), {"SECRET_KEY": secret_key})


def test_missing_secret_key_refuses_to_start():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(_config_with(None))


def test_empty_secret_key_refuses_to_start():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(_config_with(""))


def test_short_secret_key_refuses_to_start():
    with pytest.raises(RuntimeError, match="สั้นเกินไป"):
        create_app(_config_with("a" * (MIN_SECRET_KEY_LENGTH - 1)))


def test_long_enough_secret_key_starts():
    app = create_app(_config_with("b" * MIN_SECRET_KEY_LENGTH))
    assert app.config["SECRET_KEY"] == "b" * MIN_SECRET_KEY_LENGTH


def test_config_has_no_hardcoded_fallback():
    """กันการเผลอใส่ default กลับเข้าไป"""
    import config

    source = __import__("pathlib").Path(config.__file__).read_text()
    assert "dev-secret-change-me" not in source
    assert 'os.environ.get("SECRET_KEY")' in source, "SECRET_KEY ต้องอ่านจาก env ล้วน ๆ ห้ามมี default"


def test_dead_pooled_connections_are_checked_before_they_are_handed_out():
    """สายที่ตายในพูลต้องถูกจับตอนหยิบ ไม่ใช่ตอนที่คำขอของผู้ใช้ไปเจอ

    (audit รอบ 11 · ADR 0067) — proxy/firewall ตัด connection ที่นอนอยู่ได้เงียบ ๆ
    แล้วคำขอใบถัดไปที่หยิบมันไปใช้จะพังด้วยข้อความที่ชี้ไปผิดที่
    ("MySQL server has gone away") หรือค้างรอจนถูกฆ่า
    """
    options = Config.SQLALCHEMY_ENGINE_OPTIONS

    assert options.get("pool_pre_ping") is True, "ถอด pool_pre_ping ออกแล้วสายที่ตายจะถูกส่งให้คำขอของผู้ใช้"
