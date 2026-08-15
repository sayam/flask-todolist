"""โหมด multiproc ของ /metrics (ADR 0052 — G5): รวมข้าม worker ถูก · ครึ่ง ๆ = ไม่ start

สามคำสัญญาของ ADR: (ก) ตัวเลขรวมทุก worker ของ container ถูกต้อง —
พิสูจน์ด้วย worker จำลองที่เขียนไฟล์ snapshot ด้วยกลไกจริงตัวเดียวกัน
(ข) `WEB_CONCURRENCY > 1` โดยไม่มี dir = refuse ตอน start พร้อมบอกทาง
(ค) โหมดเดิม (worker เดียว ไม่มี dir) พฤติกรรมเดิมทุกประการ — ไม่มีไฟล์
ถูกเขียน และ HELP ยังประกาศว่าเป็นของ process เดียว
"""

import json
import os

import pytest

from app import create_app
from app.metrics import (
    EXTENSION_KEY,
    HELP_MULTIPROC,
    Histogram,
    dump_snapshot,
    merged_series,
    render,
)
from tests.conftest import TestConfig, bearer_client, issue_token


def _multiproc_config(tmp_path, workers=2):
    class MultiprocConfig(TestConfig):
        WEB_CONCURRENCY = workers
        METRICS_MULTIPROC_DIR = str(tmp_path / "metrics")

    return MultiprocConfig


# ----------------------------------------------------- (ข) fail-loud ตอน start


def test_two_workers_without_a_dir_refuse_to_start():
    class HalfConfig(TestConfig):
        WEB_CONCURRENCY = 2
        METRICS_MULTIPROC_DIR = None

    with pytest.raises(RuntimeError, match="METRICS_MULTIPROC_DIR"):
        create_app(HalfConfig)


def test_an_unwritable_dir_refuses_to_start(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("", encoding="utf-8")  # เป็นไฟล์ — mkdir ใต้มันย่อมพัง

    class BadDirConfig(TestConfig):
        WEB_CONCURRENCY = 2
        METRICS_MULTIPROC_DIR = str(blocker / "metrics")

    with pytest.raises(RuntimeError, match="เขียนไม่ได้"):
        create_app(BadDirConfig)


# ------------------------------------------------- (ก) รวมข้าม worker ถูกต้อง


def test_metrics_aggregate_across_workers(tmp_path):
    app = create_app(_multiproc_config(tmp_path))
    from app import db

    with app.app_context():
        db.create_all()
        from app.models import User

        user = User(username="scraper")
        user.set_password("Multiproc-Scrape-1!")
        db.session.add(user)
        db.session.commit()
        uid = user.id
        db.session.remove()

    # worker จำลอง: เขียนไฟล์ด้วย dump_snapshot ตัวจริง (pid ที่ไม่มีวันชนกับเรา)
    other = Histogram()
    other.observe(("main.index", "GET", "200"), 0.02)
    other.observe(("main.index", "GET", "200"), 0.02)
    directory = tmp_path / "metrics"
    dump_snapshot(other, directory, pid=99999999)

    # worker จริง (ตัวที่รับ scrape) มีของตัวเองหนึ่งครั้ง
    client = bearer_client(app, issue_token(app, uid))
    response = client.get("/metrics")
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert HELP_MULTIPROC.split(" — ")[1] in text  # ประกาศโหมดรวมบนตัว metric เอง

    # แถวของ worker จำลองต้องถูกนับรวม: 2 ครั้งของ main.index GET 200
    count_line = next(
        line
        for line in text.splitlines()
        if line.startswith("todolist_request_duration_seconds_count")
        and 'endpoint="main.index"' in line
    )
    assert count_line.endswith(" 2"), f"ค่าที่รวมข้าม worker หาย: {count_line}"


def test_dead_worker_counters_survive(tmp_path):
    """ไฟล์ของ worker ที่ตายแล้วยังถูกนับ — งานที่เคยเกิดไม่หายไปกับ process"""
    live = Histogram()
    live.observe(("a", "GET", "200"), 0.01)
    dead = Histogram()
    dead.observe(("a", "GET", "200"), 0.01)
    directory = tmp_path / "m"
    directory.mkdir()
    dump_snapshot(dead, directory, pid=12345)  # ตายไปแล้ว ไม่มีใครลบไฟล์
    merged = merged_series(live, directory, pid=os.getpid())
    assert merged[0][2] == 2, "ค่าจากไฟล์ของ pid ที่ตายแล้วต้องยังถูกรวม"


def test_a_torn_file_is_skipped_not_fatal(tmp_path):
    live = Histogram()
    live.observe(("a", "GET", "200"), 0.01)
    directory = tmp_path / "m"
    directory.mkdir()
    (directory / "histogram-777.json").write_text("{torn", encoding="utf-8")
    merged = merged_series(live, directory, pid=os.getpid())
    assert merged[0][2] == 1, "ไฟล์ขาดกลางต้องถูกข้ามรอบนี้ ไม่ใช่ทำ scrape ทั้งรอบพัง"


def test_dump_is_atomic_and_valid_json(tmp_path):
    histogram = Histogram()
    histogram.observe(("a", "GET", "200"), 0.01)
    directory = tmp_path / "m"
    directory.mkdir()
    dump_snapshot(histogram, directory, pid=1)
    files = list(directory.iterdir())
    assert [f.name for f in files] == ["histogram-1.json"], "ไฟล์ tmp ต้องไม่เหลือค้าง"
    rows = json.loads(files[0].read_text(encoding="utf-8"))
    assert rows[0][0] == "a"
    assert rows[0][4] == 1


# --------------------------------------------- (ค) โหมดเดิมไม่เปลี่ยนสักนิด


def test_single_worker_mode_writes_no_files_and_keeps_the_old_help(app, tmp_path):
    histogram = app.extensions[EXTENSION_KEY]
    assert "ของ process นี้คนเดียว" in render(histogram)
    assert not list(tmp_path.iterdir()), "โหมดเดิมต้องไม่แตะดิสก์เลย"
