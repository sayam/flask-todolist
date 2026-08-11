"""latency histogram + `/metrics` (Phase 6 · P6-02 — ดู ADR 0031)

สามเรื่องที่ต้องพิสูจน์แยกกัน:

1. **รูปแบบถูกต้องพอที่ Prometheus จะกินได้** — bucket สะสม, มี `+Inf` เท่ากับ
   `_count`, และ `_sum` สมเหตุสมผล · รูปแบบที่ผิดจะถูกปฏิเสธทั้งก้อน ไม่ใช่
   บางบรรทัด แล้ว metric ทั้งหมดหายไปเงียบ ๆ
2. **`/metrics` ไม่มีโหมดเปิดสาธารณะ** (ข้อ 5) และคุกกี้ของเบราว์เซอร์ยกระดับ
   เป็นสิทธิ์ตรงนี้ไม่ได้ ด้วยเหตุผลเดียวกับ `/api/v1` (ADR 0017/0018)
3. **label ไม่ระเบิดตามข้อมูลของผู้ใช้** (ข้อ 6) — `/edit/1` กับ `/edit/2`
   ต้องเป็น series เดียวกัน ไม่งั้นคนนอกยิง path มั่ว ๆ ให้หน่วยความจำหมดได้
"""

import pytest

from app import metrics
from tests.conftest import bearer_client, issue_token


def series_for(text, endpoint):
    """บรรทัดของ endpoint นั้นจากผลลัพธ์ exposition"""
    return [line for line in text.splitlines() if f'endpoint="{endpoint}"' in line]


def value_of(lines, suffix):
    for line in lines:
        name, _, value = line.rpartition(" ")
        if suffix in name:
            return float(value)
    return None


# ------------------------------------------------ 1. รูปแบบที่ Prometheus กินได้


def test_buckets_are_cumulative_and_end_with_inf():
    """`le` ของ Prometheus คือ "น้อยกว่าหรือเท่ากับ" จึงต้องสะสมขึ้นเรื่อย ๆ

    และ `+Inf` ต้องเท่ากับ `_count` เสมอ — histogram ที่ไม่ครบถูกปฏิเสธทั้งก้อน
    """
    histogram = metrics.Histogram()
    for seconds in (0.001, 0.03, 0.03, 2.0):
        histogram.observe(("main.index", "GET", "200"), seconds)

    lines = series_for(metrics.render(histogram), "main.index")
    counts = [float(line.rpartition(" ")[2]) for line in lines if "_bucket{" in line]
    assert counts == sorted(counts), "bucket ต้องไม่ลดลง (สะสม)"

    # **ต้องมีบรรทัด `+Inf` อยู่จริง** ไม่ใช่แค่ค่าสุดท้ายบังเอิญเท่ากับ `_count`
    # (mutation test จับได้ว่าเทสต์รุ่นแรกไม่ได้ตรวจข้อนี้เลย: ลบบรรทัด `+Inf`
    #  ทิ้งแล้วยังเขียว เพราะ bucket 5.0 มีค่าเท่ากันพอดี)
    inf = [line for line in lines if 'le="+Inf"' in line]
    assert len(inf) == 1, "histogram ที่ไม่มี +Inf ถูก Prometheus ปฏิเสธทั้งก้อน"
    assert float(inf[0].rpartition(" ")[2]) == value_of(lines, "_count") == 4
    # 0.001 + 0.03 + 0.03 + 2.0
    assert value_of(lines, "_sum") == pytest.approx(2.061)


def test_a_value_lands_in_every_bucket_at_or_above_it():
    histogram = metrics.Histogram()
    histogram.observe(("main.index", "GET", "200"), 0.02)
    lines = [
        line for line in series_for(metrics.render(histogram), "main.index") if "_bucket{" in line
    ]
    # bucket 0.005 กับ 0.01 ต้องยังเป็น 0 ส่วน 0.025 ขึ้นไปต้องเป็น 1
    assert lines[0].endswith(" 0")
    assert lines[1].endswith(" 0")
    assert all(line.endswith(" 1") for line in lines[2:])


def test_label_values_are_escaped():
    """ค่าที่มีอัญประกาศทำให้บรรทัดนั้นเสียรูปและ Prometheus ทิ้งทั้งก้อน"""
    histogram = metrics.Histogram()
    histogram.observe(('weird"name', "GET", "200"), 0.01)
    assert 'endpoint="weird\\"name"' in metrics.render(histogram)


def test_the_help_line_says_the_numbers_are_per_process():
    """คนที่อ่านตัวเลขมักไม่ได้อ่านเอกสาร — คำเตือนต้องเดินทางไปกับ metric เอง

    (ADR 0031 ข้อ 4: หลาย worker/replica ต้อง scrape แยกแล้วรวมที่ Prometheus)
    """
    rendered = metrics.render(metrics.Histogram())
    assert rendered.startswith("# HELP todolist_request_duration_seconds")
    assert "process" in rendered.splitlines()[0]


# --------------------------------------------------------- 2. ด่านของ /metrics


def test_metrics_needs_a_token(app):
    assert app.test_client().get("/metrics").status_code == 401


def test_a_browser_session_cannot_read_metrics(app, user_id):
    """คุกกี้ยกระดับเป็นสิทธิ์ของเครื่องไม่ได้ (หลักเดียวกับ ADR 0018)"""
    from tests.conftest import PASSWORD

    client = app.test_client()
    client.post("/login", data={"username": "tester", "password": PASSWORD})
    assert client.get("/").status_code == 200, "login แล้วจริง"
    assert client.get("/metrics").status_code == 401


def test_a_token_can_read_metrics(app, user_id):
    client = bearer_client(app, issue_token(app, user_id))
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    assert b"todolist_request_duration_seconds" in response.data


# ------------------------------------------------- 3. label ต้องไม่ระเบิด


def test_paths_that_differ_only_by_id_share_one_series(app, user_id):
    """`/edit/1` กับ `/edit/2` ต้องเป็น series เดียวกัน (ADR 0031 ข้อ 6)

    ถ้า label ใช้ `request.path` จำนวน time series จะโตตามจำนวนงานในระบบ
    และ **คนนอกยิง path มั่ว ๆ ให้หน่วยความจำหมดได้** ซึ่งเป็นช่องโจมตี
    ไม่ใช่แค่ความสิ้นเปลือง
    """
    from tests.conftest import PASSWORD

    client = app.test_client()
    client.post("/login", data={"username": "tester", "password": PASSWORD})
    for todo_id in (1, 2, 3):
        client.get(f"/edit/{todo_id}")

    histogram = app.extensions[metrics.EXTENSION_KEY]
    edit_series = [key for key, *_ in histogram.snapshot() if key[0] == "main.edit"]
    assert len(edit_series) == 1, f"ควรมี series เดียว ได้ {edit_series}"


def test_a_path_that_matches_no_route_does_not_create_a_series_per_path(app):
    """404 จาก path มั่ว ๆ ต้องรวมกันเป็น series เดียว ไม่ใช่หนึ่งอันต่อหนึ่ง path"""
    client = app.test_client()
    for suffix in range(5):
        client.get(f"/ไม่มีหน้านี้-{suffix}")

    histogram = app.extensions[metrics.EXTENSION_KEY]
    unknown = [key for key, *_ in histogram.snapshot() if key[0] == "unknown"]
    assert len(unknown) == 1, f"ควรรวมเป็น series เดียว ได้ {unknown}"
