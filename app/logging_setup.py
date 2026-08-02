"""log แบบ structured (JSON) + correlation ID ต่อ request

ตัดสินใจรูปแบบครั้งเดียวที่นี่ เพื่อให้ Phase 7 ต่อท่อเข้า SIEM ได้เลย
โดยไม่ต้องไล่แก้จุดที่เขียน log

**ทุกบรรทัดมี `request_id`** — สร้างใหม่ต่อ request หรือรับต่อจาก header
`X-Request-Id` ที่ reverse proxy ใส่มา (Phase 5) เพื่อให้ trace ข้ามชั้นได้
ค่าเดียวกันถูกส่งกลับใน response header ด้วย ผู้ใช้ที่แจ้งปัญหาจึงอ้างอิงได้

ยังไม่ใส่ OpenTelemetry — ระบบยังเป็น monolith เดียว (ดู ROADMAP Phase 1)
"""

import json
import logging
import sys
import time
import uuid

from flask import g, request
from flask_login import current_user

REQUEST_ID_HEADER = "X-Request-Id"

# field มาตรฐานของ LogRecord ที่ไม่ต้องเอาลง JSON ซ้ำ
_RESERVED = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """หนึ่งบรรทัด = หนึ่ง JSON object — SIEM ทุกตัวย่อยได้โดยไม่ต้องเขียน parser"""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # ค่าที่ส่งมาทาง extra= ถูกยกขึ้นเป็น field ระดับบนสุด
        payload.update(
            {k: v for k, v in vars(record).items() if k not in _RESERVED and not k.startswith("_")}
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def current_request_id() -> str | None:
    """request id ของ request ปัจจุบัน — None เมื่ออยู่นอก request"""
    return getattr(g, "request_id", None)


def _actor() -> str | None:
    """username ของคนที่ยิง request — ใช้ username ไม่ใช่ชื่อจริง (ลด PII ใน log)"""
    try:
        if current_user.is_authenticated:
            return str(current_user.username)
    except RuntimeError:  # นอก request context
        return None
    return None


def init_logging(app):
    """ตั้ง JSON log ออก stdout + ผูก request id เข้าทุก request"""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(app.config["LOG_LEVEL"])
    # ไม่ให้ Flask เขียนซ้ำผ่าน handler ของตัวเอง
    app.logger.handlers = []
    app.logger.propagate = True

    @app.before_request
    def _start_request() -> None:
        incoming = request.headers.get(REQUEST_ID_HEADER, "")
        # รับต่อจาก proxy ได้ แต่ต้องเป็น uuid จริง ไม่งั้นเป็นช่องให้ inject log
        try:
            g.request_id = str(uuid.UUID(incoming))
        except ValueError:
            g.request_id = str(uuid.uuid4())
        g.request_started_at = time.perf_counter()

    @app.after_request
    def _log_request(response):
        duration_ms = round((time.perf_counter() - g.get("request_started_at", 0)) * 1000, 2)
        app.logger.info(
            "request",
            extra={
                "event": "http_request",
                "request_id": g.get("request_id"),
                "actor": _actor(),
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "remote_addr": request.remote_addr,
            },
        )
        response.headers[REQUEST_ID_HEADER] = g.get("request_id", "")
        return response
