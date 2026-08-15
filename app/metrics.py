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

import json
import os
import pathlib
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
HELP_MULTIPROC = (
    "เวลาที่ใช้ตอบคำขอ (วินาที) — **รวมทุก worker ของ container นี้** "
    "(โหมด multiproc — ADR 0052) ต่าง replica ยัง scrape แยกตามเดิม"
)

# โหมด multiproc (ADR 0052 — opt-in): แต่ละ worker เขียน snapshot ของตัวเอง
# ลงไฟล์ใน dir ที่ประกาศ แล้วตัวที่รับ scrape เป็นคนรวม — กลไกเดียวกับ
# multiprocess mode ของ prometheus_client แต่เขียนเองด้วย stdlib ตามหลักของ
# โมดูลนี้ (histogram คือ counter — เครื่องจักร mmap ของไลบรารีคือของที่เรา
# ไม่ต้องแบก supply chain เพิ่มเพื่อให้ได้มา) · ไฟล์ของ worker ที่ตายแล้วถูก
# นับต่อโดยตั้งใจ (งานที่เคยเกิดไม่หายไปกับ process — counter สะสมโดยนิยาม)
# dir ต้องตายพร้อม container (tmpfs) — ดู docs/OPERATIONS.md
DUMP_INTERVAL_SECONDS = 1.0


def dump_snapshot(histogram: "Histogram", directory: pathlib.Path, pid: int) -> None:
    """เขียน snapshot ของ worker หนึ่งตัวแบบ atomic (เขียน tmp แล้ว rename)

    ไฟล์ต่อ pid — ไม่มีการเขียนชนกันข้าม worker และผู้อ่านไม่มีวันเห็นไฟล์
    ครึ่งใบ (`os.replace` เป็น atomic บน filesystem เดียวกัน)
    """
    rows = [
        [endpoint, method, status, counts, total, elapsed]
        for (endpoint, method, status), counts, total, elapsed in histogram.snapshot()
    ]
    tmp = directory / f".histogram-{pid}.tmp"
    tmp.write_text(json.dumps(rows), encoding="utf-8")
    tmp.replace(directory / f"histogram-{pid}.json")


def merged_series(
    histogram: "Histogram", directory: pathlib.Path, pid: int
) -> list[tuple[tuple[str, str, str], list[int], int, float]]:
    """รวมค่าของทุก worker: ตัวเอง (สด จากหน่วยความจำ) + ไฟล์ของตัวอื่น

    ไฟล์ของ pid ตัวเองถูกข้าม — ค่าสดในหน่วยความจำใหม่กว่าเสมอ · ไฟล์ที่
    อ่านไม่ได้ (กำลังถูกเขียนบน filesystem ที่ replace ไม่ atomic) ถูกข้าม
    รอบนี้ — รอบ scrape ถัดไปได้ค่าที่โตขึ้นเอง counter ไม่ถอยหลัง
    """
    merged: dict[tuple[str, str, str], list[Any]] = {}

    def _add(key: tuple[str, str, str], counts: list[int], total: int, elapsed: float) -> None:
        entry = merged.setdefault(key, [[0] * len(BUCKETS), 0, 0.0])
        entry[0] = [a + b for a, b in zip(entry[0], counts, strict=True)]
        entry[1] += total
        entry[2] += elapsed

    for key, counts, total, elapsed in histogram.snapshot():
        _add(key, counts, total, elapsed)
    for path in sorted(directory.glob("histogram-*.json")):
        if path.name == f"histogram-{pid}.json":
            continue
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for endpoint, method, status, counts, total, elapsed in rows:
            _add((endpoint, method, status), counts, total, elapsed)
    return [(key, entry[0], entry[1], entry[2]) for key, entry in merged.items()]


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
    """แปลงค่าของ process เดียวเป็น exposition text (โหมดเดิม — ค่าเริ่มต้น)"""
    return render_series(histogram.snapshot(), HELP)


def render_series(
    series: list[tuple[tuple[str, str, str], list[int], int, float]], help_text: str
) -> str:
    """แปลงเป็นข้อความตามรูปแบบ exposition ของ Prometheus

    **bucket เป็นแบบสะสม** (`le` = น้อยกว่าหรือเท่ากับ) และต้องมี `+Inf` ปิดท้าย
    เสมอ ซึ่งต้องมีค่าเท่ากับ `_count` — Prometheus ปฏิเสธ histogram ที่ไม่ครบ
    """
    lines = [
        f"# HELP todolist_request_duration_seconds {help_text}",
        "# TYPE todolist_request_duration_seconds histogram",
    ]
    for (endpoint, method, status), counts, total, elapsed in sorted(series):
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


def _multiproc_dir(app: Any) -> pathlib.Path | None:
    """ตรวจ config ของโหมด multiproc — ครึ่ง ๆ กลาง ๆ = ไม่ start (ADR 0052)

    หลาย worker โดยไม่มี dir คือสภาพที่ตัวเลข `/metrics` สลับตัวนับต่อ scrape
    — ความผิดไม่ใช่การรันหลาย worker แต่คือการไม่รู้ว่าตัวเลขมั่ว จึง refuse
    ดัง ๆ พร้อมบอกทาง (หลักเดียวกับ scheme ของ DATABASE_URL ที่ไม่รู้จัก)
    """
    workers = int(app.config.get("WEB_CONCURRENCY", 1) or 1)
    configured = app.config.get("METRICS_MULTIPROC_DIR")
    if workers > 1 and not configured:
        raise RuntimeError(
            f"WEB_CONCURRENCY={workers} แต่ไม่มี METRICS_MULTIPROC_DIR — "
            "หลาย worker ทำให้ /metrics สลับตัวนับต่อ scrape (ADR 0031) "
            "ตั้ง METRICS_MULTIPROC_DIR ชี้ tmpfs ของ container (ADR 0052) "
            "หรือกลับไปใช้ worker เดียวแล้ว scale ด้วย replica"
        )
    if not configured:
        return None
    directory = pathlib.Path(configured)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / f".probe-{os.getpid()}"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        raise RuntimeError(
            f"METRICS_MULTIPROC_DIR={configured} เขียนไม่ได้ ({exc}) — "
            "โหมด multiproc ที่เขียนไฟล์ไม่ได้คือโหมดที่ตัวเลขหายเงียบ ๆ"
        ) from exc
    return directory


def init_metrics(app: Any) -> Histogram:
    """ผูกตัวนับเข้ากับทุกคำขอ และเปิด `/metrics` (ต้องมี token — ADR 0031 ข้อ 5)"""
    histogram = Histogram()
    app.extensions[EXTENSION_KEY] = histogram
    multiproc = _multiproc_dir(app)
    last_dump = [0.0]

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
            if multiproc is not None:
                # dump แบบผ่อน — ความสดของไฟล์มีเพดานที่ DUMP_INTERVAL_SECONDS
                # และตัวที่รับ scrape ใช้ค่าสดของตัวเองเสมอ counter จึงไม่ถอยหลัง
                now = time.monotonic()
                if now - last_dump[0] >= DUMP_INTERVAL_SECONDS:
                    last_dump[0] = now
                    dump_snapshot(histogram, multiproc, os.getpid())
        return response

    @app.route(METRICS_PATH)
    def metrics() -> Response:
        """ตัวเลขสำหรับ Prometheus — **ไม่มีโหมดเปิดสาธารณะ** (ADR 0031 ข้อ 5)"""
        from app.api.auth import require_api_token

        require_api_token()
        if multiproc is not None:
            pid = os.getpid()
            dump_snapshot(histogram, multiproc, pid)
            body = render_series(merged_series(histogram, multiproc, pid), HELP_MULTIPROC)
        else:
            body = render(histogram)
        return Response(
            body,
            mimetype="text/plain; version=0.0.4; charset=utf-8",
        )

    return histogram
