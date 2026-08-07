"""cache เป็น optimization ห้ามเป็น correctness (Phase 5 · ROADMAP ข้อ 4.3)

**ข้อที่สำคัญที่สุดคือ `test_the_default_really_stores_nothing`** — ค่าเริ่มต้น
ต้องไม่เก็บอะไรเลยจริง ๆ ไม่ใช่ dict ใน process ที่ "เกือบใช้ได้" เพราะถ้ามันเก็บ
ชุดเทสต์ทั้งชุดจะเดินผ่านเส้นทาง "มี cache" โดยไม่มีใครรู้ แล้วเส้นทาง "ไม่มี cache"
ซึ่งเป็นค่าเริ่มต้นของทุก deploy จะไม่เคยถูกทดสอบเลย (หลักเดียวกับ job `bare`)

ตัวที่ต่อ redis จริงจะรันก็ต่อเมื่อมี `TEST_REDIS_URL` — ตั้งเองในเครื่องได้:
`TEST_REDIS_URL=redis://<host>:6379/0 pipenv run pytest tests/test_cache.py`
"""

import json
import os
import shutil

import pytest

from app import cache, plugins
from tests.conftest import TestConfig

NOOP_KEY = "cache/noop"
REDIS_KEY = "cache/redis"

REDIS_URL = os.environ.get("TEST_REDIS_URL")
needs_redis = pytest.mark.skipif(not REDIS_URL, reason="ตั้ง TEST_REDIS_URL ก่อนถึงจะยิง redis จริงได้")


@pytest.fixture
def temp_cache_backend():
    """วาง backend ชั่วคราวลงดิสก์จริงแล้วเก็บกวาดให้"""
    created = []

    def make(backend_id, manifest=None, module=None):
        directory = plugins.PLUGIN_ROOT / cache.CACHE_TYPE / backend_id
        directory.mkdir(parents=True)
        created.append(directory)
        (directory / "plugin.json").write_text(
            json.dumps(
                manifest
                if manifest is not None
                else {"type": "cache", "name": backend_id, "schemes": [backend_id]}
            )
        )
        if module is not None:
            (directory / "cache.py").write_text(module)
        return directory

    yield make
    for directory in created:
        shutil.rmtree(directory, ignore_errors=True)


# --- ค่าเริ่มต้นต้องไม่เก็บอะไรจริง ๆ ---


def test_the_default_backend_is_the_one_that_stores_nothing(app):
    with app.app_context():
        assert cache.current().plugin.key == NOOP_KEY
        assert cache.current().is_shared is False


def test_the_default_really_stores_nothing(app):
    """**เขียนแล้วอ่านต้องไม่เจอ** — ไม่ใช่ "เจอบ้างไม่เจอบ้าง"

    ถ้าวันหนึ่งมีคนเปลี่ยนค่าเริ่มต้นเป็น dict ใน process ชุดเทสต์ทั้งชุดจะเดินผ่าน
    เส้นทาง "มี cache" เงียบ ๆ แล้วเส้นทางที่ทุก deploy ใช้จริงจะไม่เคยถูกทดสอบ
    (และ dict ต่อ process ยังทำให้หลาย worker ตอบไม่ตรงกันด้วย)
    """
    with app.app_context():
        current = cache.current()
        current.set("k", "v")
        assert current.get("k") is None
        current.invalidate("k")  # ต้องไม่ระเบิดถึงจะเรียกของที่ไม่มี


# --- เลือก backend จาก scheme ---


def test_the_url_scheme_picks_the_backend(app):
    with app.app_context():
        assert cache.active("memory://").key == NOOP_KEY
        assert cache.active("redis://h:6379/0").key == REDIS_KEY
        assert cache.active("rediss://h:6379/0").key == REDIS_KEY


def test_an_unknown_scheme_refuses_to_start(app):
    """ไม่ตกกลับไป no-op เงียบ ๆ — คนที่ตั้ง CACHE_URL ตั้งใจจะได้ cache ที่แชร์ได้

    การเงียบแล้วให้ no-op แปลว่าเขาจะเชื่อว่ามี cache อยู่ทั้งที่ไม่มี แล้วไปหา
    สาเหตุที่ประสิทธิภาพผิดคาดในที่ที่ไม่มีอะไรผิด
    """
    with app.app_context(), pytest.raises(plugins.PluginError, match="memcached"):
        cache.active("memcached://h:11211")


def test_adding_a_backend_touches_no_core_code(app, temp_cache_backend):
    temp_cache_backend("fake", manifest={"type": "cache", "name": "f", "schemes": ["fakestore"]})
    with app.app_context():
        assert cache.active("fakestore://x").key == "cache/fake"


# --- สัญญาเป็นเรื่องของ host ไม่ใช่ registry (ADR 0025) ---


def test_a_backend_missing_part_of_the_contract_is_loud(app, temp_cache_backend):
    """แพ็กมาไม่ครบต้องดังตอน start ไม่ใช่ตอนมีคนเรียก `invalidate` ครั้งแรก"""
    temp_cache_backend(
        "halfdone",
        manifest={"type": "cache", "name": "h", "schemes": ["halfdone"]},
        module="def connect(url):\n    return None\n\n\ndef get(h, k):\n    return None\n",
    )
    with app.app_context(), pytest.raises(plugins.PluginError, match="set, invalidate"):
        cache.module_of(cache.active("halfdone://x"))


def test_a_backend_without_code_is_loud(app, temp_cache_backend):
    temp_cache_backend("empty", manifest={"type": "cache", "name": "e", "schemes": ["empty"]})
    with app.app_context(), pytest.raises(plugins.PluginError, match=r"ไม่มี cache\.py"):
        cache.module_of(cache.active("empty://x"))


def test_the_active_backend_cannot_be_switched_off(app):
    with app.app_context():
        in_use = cache.active(TestConfig.CACHE_URL).key
        app.config["DISABLED_PLUGINS"] = frozenset({in_use})
        with pytest.raises(plugins.PluginError, match="CACHE_URL"):
            cache.active(TestConfig.CACHE_URL)


# --- ของจริง (ต้องมี server) ---


@needs_redis
@pytest.mark.plugin_deps
def test_redis_really_stores_and_forgets(app):
    """ยิง redis จริง — set/get/invalidate ต้องทำงานครบวง

    **ไม่ใช้ mock** เพราะ mock จะพิสูจน์ได้แค่ว่าเราเรียกฟังก์ชันชื่อถูก
    ไม่ได้พิสูจน์ว่าค่าเดินทางไปถึงและกลับมาได้จริง ซึ่งคือทั้งหมดของ backend นี้
    """
    with app.app_context():
        shared = cache.Cache(REDIS_URL)
        assert shared.is_shared is True
        shared.invalidate("pytest-probe")
        assert shared.get("pytest-probe") is None

        shared.set("pytest-probe", "ค่าจริง", ttl=60)
        # คืนเป็น bytes ตามที่ backend ประกาศไว้ว่าไม่ถอดรหัสให้ผู้เรียก
        assert shared.get("pytest-probe") == "ค่าจริง".encode()

        shared.invalidate("pytest-probe")
        assert shared.get("pytest-probe") is None
