"""structured logging + correlation ID

รูปแบบ log ถูกตัดสินครั้งเดียวที่นี่เพื่อให้ Phase 7 ต่อ SIEM ได้โดยไม่ต้อง
ไล่แก้จุดที่เขียน log — เทสต์ชุดนี้จึงล็อก contract ของ field ไว้
"""

import json
import logging
import pathlib
import sys
import time
import uuid

import pytest

from app.logging_setup import REQUEST_ID_HEADER, JsonFormatter


@pytest.fixture
def logged(app, caplog):
    """จับ log record แล้วคืนเป็น dict ที่ผ่าน formatter จริง"""

    def parse():
        formatter = JsonFormatter()
        return [
            json.loads(formatter.format(record))
            for record in caplog.records
            if getattr(record, "event", None) == "http_request"
        ]

    caplog.set_level(logging.INFO)
    return parse


# --- รูปแบบ JSON ---


def test_log_line_is_valid_json(app, anon_client, logged):
    anon_client.get("/login")
    lines = logged()
    assert lines, "ทุก request ต้องมี log อย่างน้อยหนึ่งบรรทัด"


def test_log_has_the_agreed_fields(app, anon_client, logged):
    anon_client.get("/login")
    entry = logged()[0]
    for field in (
        "timestamp",
        "level",
        "logger",
        "message",
        "event",
        "request_id",
        "method",
        "path",
        "status",
        "duration_ms",
    ):
        assert field in entry, f"log ขาด field {field}"


def test_log_records_the_status_and_path(app, anon_client, logged):
    anon_client.get("/login")
    entry = logged()[0]
    assert entry["path"] == "/login"
    assert entry["status"] == 200
    assert entry["method"] == "GET"


def test_timestamp_is_utc_not_local_time(monkeypatch):
    """เวลาใน log ต้องเป็น UTC เสมอ ไม่ว่าเครื่องที่รันตั้งโซนอะไรไว้ (ASVS V16.2.2)

    เครื่องที่ตั้งโซนต่างกันแล้วเขียนเวลาท้องถิ่นลง log **โดยไม่มี offset**
    ทำให้การเรียงลำดับเหตุการณ์ข้ามเครื่องผิดโดยไม่มีอะไรฟ้อง — และเดือนที่มี
    การเปลี่ยน DST จะมีชั่วโมงที่ปรากฏสองครั้ง ตอนสืบเหตุการณ์จริงจึงแยกไม่ออก
    ว่าอันไหนเกิดก่อน · ตัว `Z` ท้ายสตริงคือส่วนหนึ่งของสัญญา ไม่ใช่การตกแต่ง
    """
    monkeypatch.setenv("TZ", "Asia/Bangkok")  # UTC+7 — ต่างจาก UTC แน่นอน
    time.tzset()
    try:
        created = 1_754_000_000.0  # จุดเวลาคงที่ จะได้เทียบกับค่าที่คำนวณเองได้
        record = logging.LogRecord("t", logging.INFO, "", 0, "hello", None, None)
        record.created, record.msecs = created, 0
        entry = json.loads(JsonFormatter().format(record))
    finally:
        monkeypatch.delenv("TZ")
        time.tzset()

    expected = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(created)) + ".000Z"
    assert entry["timestamp"] == expected
    assert entry["timestamp"].endswith("Z"), "ต้องบอกให้ชัดว่าเป็น UTC ไม่ใช่ปล่อยให้เดา"


def test_thai_text_is_not_escaped():
    """ensure_ascii=False — ไม่งั้น log ไทยอ่านไม่ออกใน SIEM"""
    record = logging.LogRecord("t", logging.INFO, "", 0, "งานทดสอบ", None, None)
    assert "งานทดสอบ" in JsonFormatter().format(record)


def _boom():
    raise ValueError("พังโดยตั้งใจ")


def test_exception_is_serialised():
    """traceback ต้องลงไปใน log ไม่งั้นตอนเกิดเหตุจริงจะเหลือแค่ 'boom'"""
    try:
        _boom()
    except ValueError:
        record = logging.LogRecord("t", logging.ERROR, "", 0, "boom", None, sys.exc_info())
    entry = json.loads(JsonFormatter().format(record))
    assert "ValueError" in entry["exception"]
    assert "พังโดยตั้งใจ" in entry["exception"]


# --- correlation ID ---


def test_response_carries_a_request_id(client):
    value = client.get("/login").headers[REQUEST_ID_HEADER]
    uuid.UUID(value)  # ต้อง parse ได้ ไม่งั้นถือว่าไม่ใช่ id ที่ใช้ correlate ได้


def test_each_request_gets_a_new_id(client):
    first = client.get("/login").headers[REQUEST_ID_HEADER]
    second = client.get("/login").headers[REQUEST_ID_HEADER]
    assert first != second


def test_incoming_request_id_is_reused(client):
    """proxy ใส่ id มาแล้ว ต้องใช้ตัวเดิมเพื่อ trace ข้ามชั้นได้ (Phase 5)"""
    incoming = str(uuid.uuid4())
    resp = client.get("/login", headers={REQUEST_ID_HEADER: incoming})
    assert resp.headers[REQUEST_ID_HEADER] == incoming


def test_bogus_incoming_id_is_replaced(client):
    """ค่ามั่วจากภายนอกต้องไม่หลุดลง log — เป็นช่องให้ inject/ปลอมแปลง"""
    resp = client.get("/login", headers={REQUEST_ID_HEADER: "'; DROP TABLE--"})
    value = resp.headers[REQUEST_ID_HEADER]
    assert value != "'; DROP TABLE--"
    uuid.UUID(value)


def test_log_id_matches_response_header(app, anon_client, logged):
    resp = anon_client.get("/login")
    assert logged()[0]["request_id"] == resp.headers[REQUEST_ID_HEADER]


# --- actor และ PII ---


def test_actor_is_none_when_anonymous(app, anon_client, logged):
    anon_client.get("/login")
    assert logged()[0]["actor"] is None


def test_actor_is_the_username_once_logged_in(app, client, logged):
    client.get("/")
    assert logged()[0]["actor"] == "tester"


def test_log_uses_username_not_real_name(app, client, logged):
    """ลด PII ใน log — ชื่อจริงไม่ควรไหลเข้าไป (ดู ROADMAP Phase 2)"""
    client.post(
        "/settings/profile",
        data={"first_name": "สยาม", "last_name": "ศรีผัว"},
        follow_redirects=True,
    )
    dumped = json.dumps(logged(), ensure_ascii=False)
    assert "สยาม" not in dumped
    assert "ศรีผัว" not in dumped


# --- log ต้องไม่ปนกับ output ที่เครื่องอ่าน (P5-08) ---


def test_machine_readable_output_is_not_polluted_by_logs(tmp_path):
    """`flask plugin-deps --categories` ถูกใส่ใน `$(...)` ของ CI — stdout จึงเป็นสัญญา

    **ต้องรันเป็น subprocess จริง** เพราะ `CliRunner` ของ click จับ stdout กับ
    stderr รวมกันเป็นก้อนเดียว มันจึงไม่มีวันเห็นความต่างที่เทสต์นี้ตรวจอยู่
    (เจอจริงตอน P5-07: เทสต์ที่ตรึงรูปแบบ output ผ่านหมด แต่ CI พังเพราะ log
    บรรทัดหนึ่งไปโผล่ใน `$(...)` แล้ว `pipenv sync` ได้ชื่อ category เป็น
    `'memory://'` — เทสต์ที่ใช้ CliRunner มองไม่เห็นชั้นนั้นเลย)

    ตั้ง `CACHE_URL=memory://` เพื่อ**บังคับให้มีคำเตือนดังแน่ ๆ** ระหว่างที่รัน
    ถ้าคำเตือนนั้นไปออก stdout เทสต์นี้จะจับได้ทันที
    """
    import os
    import subprocess
    import sys

    root = pathlib.Path(__file__).resolve().parent.parent
    env = {
        **os.environ,
        "SECRET_KEY": "test-secret-key-for-pytest-only-not-a-real-key",
        "CACHE_URL": "memory://",
        "DATABASE_URL": f"sqlite:///{tmp_path / 'probe.db'}",
    }
    result = subprocess.run(
        [sys.executable, "-m", "flask", "plugin-deps", "--categories"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip(), "ต้องมีชื่อ category ออกมาจริง ไม่ใช่ว่างเปล่า"
    for line in result.stdout.splitlines():
        assert not line.lstrip().startswith("{"), (
            f"มี log ปนใน stdout: {line[:80]!r} — CI อ่านช่องนี้ด้วย `$(...)`"
        )
    for name in result.stdout.split():
        assert name.startswith("plugin-"), f"stdout มีของที่ไม่ใช่ชื่อ category: {name!r}"
