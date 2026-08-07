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


# --- โควตา rate limit ต้องไม่ถูกนับแยกต่อ process (P5-07) ---
# หนี้เดิม: `RATELIMIT_STORAGE_URI` ตายตัวเป็น `memory://` วันที่ใครรันหลาย worker
# เพดานจริงกลายเป็น N เท่าของที่ตั้งไว้ **โดยไม่มีอะไรฟ้อง** — ไม่มี error ไม่มี log
# มีแต่คนไล่เดารหัสผ่านที่ได้โควตามากกว่าที่เราคิด


def test_the_counter_store_follows_the_cache_by_default():
    """ตั้ง store ที่แชร์ได้ครั้งเดียว แล้วโควตาย้ายตามเอง — ไม่มีทางลืมตั้งตัวใดตัวหนึ่ง"""
    from config import Config

    assert Config.RATELIMIT_STORAGE_URI == Config.CACHE_URL


def test_an_explicit_setting_still_wins(monkeypatch):
    """ตั้งแยกได้ถ้าตั้งใจให้ counter อยู่คนละที่กับ cache (เช่นคนละ redis db)"""
    import importlib

    import config

    monkeypatch.setenv("CACHE_URL", "redis://cache:6379/0")
    monkeypatch.setenv("RATELIMIT_STORAGE_URI", "redis://counters:6379/1")
    importlib.reload(config)
    try:
        assert config.Config.RATELIMIT_STORAGE_URI == "redis://counters:6379/1"
        assert config.Config.CACHE_URL == "redis://cache:6379/0"
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_a_store_that_is_not_shared_says_so_on_every_start(app, warnings_of):
    """**นี่คือส่วนที่ปิดหนี้จริง ๆ** — ระบบพูดออกมาแทนที่จะให้เป็นความรู้ในหัวคน

    ไม่ refuse to start เพราะ `memory://` ถูกต้องสมบูรณ์สำหรับ dev/single worker
    ซึ่งเป็นวิธีรันที่พบบ่อยที่สุด — สิ่งที่ผิดคือการ *ไม่รู้* ว่าตัวเองอยู่สภาพไหน
    """
    app.config["RATELIMIT_STORAGE_URI"] = "memory://"
    cache.warn_if_counters_are_not_shared(app)
    assert [line for line in warnings_of if "นับแยกต่อ process" in line]


def test_a_shared_store_says_nothing(app, warnings_of):
    """คำเตือนที่ขึ้นทุกครั้งไม่ว่าอะไรจะเกิดขึ้น คือคำเตือนที่คนเลิกอ่าน"""
    app.config["RATELIMIT_STORAGE_URI"] = "redis://anywhere:6379/0"
    cache.warn_if_counters_are_not_shared(app)
    assert not [line for line in warnings_of if "นับแยกต่อ process" in line]


def test_a_store_we_do_not_know_gets_no_false_claim(app, warnings_of):
    """`limits` รองรับ store ที่เราไม่มี plugin ให้ (memcached, mongodb)

    พวกนั้นแชร์ได้จริงแต่เราตอบแทนไม่ได้ — การเดาว่า "ไม่แชร์" จะกลายเป็นคำเตือน
    ที่ผิด ซึ่งแพงกว่าการไม่เตือน เพราะมันสอนให้คนเลิกเชื่อคำเตือนอื่นด้วย
    """
    assert cache.is_shared_uri("memcached://host:11211") is None
    app.config["RATELIMIT_STORAGE_URI"] = "memcached://host:11211"
    cache.warn_if_counters_are_not_shared(app)
    assert not [line for line in warnings_of if "นับแยกต่อ process" in line]


@needs_redis
@pytest.mark.plugin_deps
def test_two_workers_share_one_quota(monkeypatch):
    """**ข้อพิสูจน์จริงของ P5-07** — สองแอปที่ชี้ store เดียวกันต้องนับโควตารวมกัน

    จำลอง worker สองตัวด้วย `Limiter` คนละตัว (ไม่ใช่ singleton ของแอป) ที่ชี้ไป
    redis เดียวกัน — ถ้าโควตายังถูกนับแยก ตัวที่สองจะยังยิงได้ทั้งที่ตัวแรกใช้หมดแล้ว
    ซึ่งคือหน้าตาของหนี้ที่ commit นี้ปิด: เพดานจริงเป็น N เท่าตามจำนวน worker

    เทสต์นี้ไม่พึ่ง fixture `ratelimit_app` เพราะตัวนั้นใช้ limiter ตัวเดียวกับแอป
    ซึ่งพิสูจน์ "แชร์ข้ามโปรเซส" ไม่ได้ตามนิยาม
    """
    import uuid

    from flask import Flask
    from flask_limiter import Limiter

    # กุญแจใหม่ทุกครั้ง ไม่งั้นเทสต์ที่รันซ้ำจะเริ่มด้วยโควตาที่ถูกใช้ไปแล้ว
    who = f"pytest-{uuid.uuid4()}"

    def worker():
        app = Flask(__name__)
        app.config["RATELIMIT_STORAGE_URI"] = REDIS_URL
        app.config["RATELIMIT_ENABLED"] = True
        limits = Limiter(key_func=lambda: who, app=app, default_limits=["2 per minute"])

        @app.route("/probe")
        def probe():
            return "ok"

        assert limits  # ผูกกับแอปแล้ว
        return app.test_client()

    first, second = worker(), worker()

    assert first.get("/probe").status_code == 200
    assert first.get("/probe").status_code == 200
    # โควตาหมดแล้วที่ worker ตัวแรก — ตัวที่สองต้องเห็นด้วย ไม่ใช่เริ่มนับใหม่
    assert second.get("/probe").status_code == 429, (
        "worker ตัวที่สองยังยิงได้ = โควตาถูกนับแยกต่อ process (เพดานจริง N เท่า)"
    )
