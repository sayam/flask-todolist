"""latency histogram ต่อ endpoint ในรูปแบบ Prometheus (Phase 6 · ADR 0031)

**ตัวนี้มีไว้ *วินิจฉัย* ว่า endpoint ไหนช้า ไม่ใช่เพื่อออกใบผ่านให้เฟส 6**
ตัวเลขที่ DoD ตัดสินมาจากฝั่ง client เพราะเวลาที่ผู้ใช้รอรวมคิวใน gunicorn และ
การรอ connection ของฐานข้อมูล ซึ่งเกิด **ก่อน** โค้ดตรงนี้เริ่มจับเวลา —
ตัวเลขจากที่นี่จึงสวยกว่าความจริงเสมอ โดยเฉพาะตอนระบบเริ่มอิ่มตัว

**ค่าที่นับอยู่เป็นของ process นี้คนเดียว** (ADR 0031 ข้อ 4) หลาย worker หรือ
หลาย replica แปลว่า `/metrics` ถูกตอบโดยตัวที่บังเอิญรับ scrape นั้น —
ข้อความนี้ถูกส่งออกไปกับ metric เองด้วย (`# HELP`) ไม่ใช่ซ่อนไว้ในเอกสาร
เพราะคนที่อ่านตัวเลขมักไม่ได้อ่านเอกสาร

**ไม่ใช้ไลบรารีเพิ่ม** — รูปแบบ exposition ของ Prometheus เป็นข้อความล้วนที่
มีสเปกชัดเจน และ histogram คือ counter ของ bucket แบบสะสม การห่อไลบรารีเพื่อ
สิ่งนี้แพงกว่าการเขียนเอง (หลักเดียวกับ ADR 0007 และ ADR 0024)
"""

import threading
import time
from typing import Any

from flask import Response, g, request

# ขอบของ bucket เป็น **วินาที** ตามธรรมเนียมของ Prometheus
# เลือกให้ถี่ในช่วง 5–250ms เพราะเป้าของเราอยู่แถวนั้น (p95 < 200ms — ADR 0031)
# ช่วงบนมีไว้ให้เห็นหางยาวตอนระบบอิ่มตัว ไม่ได้คาดว่าจะมีอะไรตกไปถึง
BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)
METRICS_PATH = "/metrics"
EXTENSION_KEY = "todolist_metrics"

HELP = (
    "เวลาที่ใช้ตอบคำขอ (วินาที) — **ของ process นี้คนเดียว** "
    "หลาย worker/replica ต้อง scrape แยกแล้วรวมที่ Prometheus (ADR 0031)"
)


class Histogram:
    """histogram ของ Prometheus ที่นับแยกตาม (endpoint, method, status)

    **ล็อกรอบการนับ** เพราะ gunicorn แบบ thread จะเรียกจากหลาย thread พร้อมกัน
    การเพิ่มค่าใน dict ของ python เป็น atomic อยู่แล้วก็จริง แต่การอ่าน-บวก-เขียน
    ของ bucket หลายตัวติดกันไม่ใช่ — ตัวเลขที่หายไปบางครั้งหาสาเหตุไม่เจอเลย
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # (endpoint, method, status) → [จำนวนในแต่ละ bucket, จำนวนรวม, ผลรวมเวลา]
        self._series: dict[tuple[str, str, str], list[Any]] = {}

    def observe(self, key: tuple[str, str, str], seconds: float) -> None:
        """นับคำขอหนึ่งครั้งลงทุก bucket ที่มันเข้าเกณฑ์

        วนใส่ทุก bucket ที่ `seconds <= edge` **ไม่ใช่ใส่ bucket เดียวแล้วบวก
        สะสมตอน render** เพราะ bucket ของ Prometheus เป็นค่าสะสมโดยนิยาม
        การเก็บแบบสะสมตั้งแต่ต้นทำให้ `render()` ไม่ต้องรู้เรื่องนี้เลย
        """
        with self._lock:
            entry = self._series.get(key)
            if entry is None:
                entry = [[0] * len(BUCKETS), 0, 0.0]
                self._series[key] = entry
            counts, total, elapsed = entry
            for index, edge in enumerate(BUCKETS):
                if seconds <= edge:
                    counts[index] += 1
            entry[1] = total + 1
            entry[2] = elapsed + seconds

    def snapshot(self) -> list[tuple[tuple[str, str, str], list[int], int, float]]:
        """คัดลอกค่าปัจจุบันออกมาทั้งชุด **ในล็อกเดียว**

        คืน `list(counts)` ที่ก๊อปแล้ว ไม่ใช่ตัวจริง — ไม่งั้นผู้เรียกจะถือ list
        ที่ `observe()` ยังแก้อยู่ระหว่างที่กำลัง render แล้วได้ histogram ที่
        `_count` ไม่ตรงกับ bucket ซึ่ง Prometheus ปฏิเสธทั้งก้อน
        """
        with self._lock:
            return [
                (key, list(counts), total, elapsed)
                for key, (counts, total, elapsed) in self._series.items()
            ]


def _escape(value: str) -> str:
    """escape ค่า label ตามสเปกของ exposition format"""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def render(histogram: Histogram) -> str:
    """แปลงเป็นข้อความตามรูปแบบ exposition ของ Prometheus

    **bucket เป็นแบบสะสม** (`le` = น้อยกว่าหรือเท่ากับ) และต้องมี `+Inf` ปิดท้าย
    เสมอ ซึ่งต้องมีค่าเท่ากับ `_count` — Prometheus ปฏิเสธ histogram ที่ไม่ครบ
    """
    lines = [
        f"# HELP todolist_request_duration_seconds {HELP}",
        "# TYPE todolist_request_duration_seconds histogram",
    ]
    for (endpoint, method, status), counts, total, elapsed in sorted(histogram.snapshot()):
        labels = (
            f'endpoint="{_escape(endpoint)}",method="{_escape(method)}",status="{_escape(status)}"'
        )
        cumulative = 0
        for index, edge in enumerate(BUCKETS):
            cumulative = counts[index]
            lines.append(
                f'todolist_request_duration_seconds_bucket{{{labels},le="{edge}"}} {cumulative}'
            )
        lines.append(f'todolist_request_duration_seconds_bucket{{{labels},le="+Inf"}} {total}')
        lines.append(f"todolist_request_duration_seconds_sum{{{labels}}} {elapsed:.6f}")
        lines.append(f"todolist_request_duration_seconds_count{{{labels}}} {total}")
    return "\n".join(lines) + "\n"


def init_metrics(app: Any) -> Histogram:
    """ผูกตัวนับเข้ากับทุกคำขอ และเปิด `/metrics` (ต้องมี token — ADR 0031 ข้อ 5)"""
    histogram = Histogram()
    app.extensions[EXTENSION_KEY] = histogram

    @app.after_request
    def _record(response: Response) -> Response:
        # ใช้เวลาเริ่มต้นตัวเดียวกับที่ `init_logging` ตั้งไว้ — จับเวลาสองที่
        # แปลว่ามีสองตัวเลขที่ต้องตรงกันตลอดไป และวันหนึ่งมันจะไม่ตรง
        started = g.get("request_started_at")
        if started is not None:
            # **label ต้องเป็นชื่อ endpoint ไม่ใช่ `request.path`** ไม่งั้นจำนวน
            # time series โตตามจำนวนงานในระบบ และคนนอกยิง path มั่ว ๆ ให้ระเบิด
            # ได้ด้วย (cardinality explosion — ADR 0031 ข้อ 6)
            endpoint = request.endpoint or "unknown"
            histogram.observe(
                (endpoint, request.method, str(response.status_code)),
                time.perf_counter() - started,
            )
        return response

    @app.route(METRICS_PATH)
    def metrics() -> Response:
        """ตัวเลขสำหรับ Prometheus — **ไม่มีโหมดเปิดสาธารณะ** (ADR 0031 ข้อ 5)"""
        from app.api.auth import require_api_token

        require_api_token()
        return Response(
            render(histogram),
            mimetype="text/plain; version=0.0.4; charset=utf-8",
        )

    return histogram
