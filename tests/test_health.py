"""liveness / readiness (ADR 0048) — สองทิศ: พร้อมเมื่อควรพร้อม พังเมื่อควรพัง"""

from app import db


def test_healthz_answers_without_login_and_without_a_database(app):
    """liveness ห้ามแตะ DB — ตัดการเชื่อมต่อทิ้งแล้วต้องยังตอบ 200 ได้"""
    client = app.test_client()
    assert client.get("/healthz").status_code == 200

    with app.app_context():
        db.session.remove()
        db.engine.dispose()
        # ทำให้ engine ต่อไม่ได้จริง ๆ — ชี้ไปไฟล์ในไดเรกทอรีที่ไม่มีอยู่
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:////nonexistent-dir/x.db"
    resp = app.test_client().get("/healthz")
    assert resp.status_code == 200, "liveness ที่ล้มตาม DB จะสั่ง restart ทุก replica พร้อมกัน"
    assert resp.data == b"ok", "body ต้องไม่มีข้อมูลภายใน"


def test_readyz_reports_ready_only_when_the_database_answers(app, monkeypatch):
    client = app.test_client()
    ready = client.get("/readyz")
    assert ready.status_code == 200
    assert ready.data == b"ok"

    # ทิศที่สอง: ฐานข้อมูลไม่ตอบ = 503 ไม่ใช่ 200 และไม่ใช่ 500 พร้อม traceback
    def _boom(*args, **kwargs):
        raise RuntimeError("database is gone")

    monkeypatch.setattr(db.session, "execute", _boom)
    broken = client.get("/readyz")
    assert broken.status_code == 503, "readiness ที่ตอบพร้อมทั้งที่ DB ล่ม คือ proxy ที่ส่งงานลงเหว"
    assert broken.data == b"not ready", "body ต้องไม่เล่าสาเหตุ — สาเหตุอยู่ใน log"


def test_health_endpoints_need_no_token_and_no_session(app):
    """ของ orchestrator — ด่าน token ของ /metrics ต้องไม่ลามมาถึงนี่ (ADR 0048)"""
    client = app.test_client()
    for path in ("/healthz", "/readyz"):
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} ต้องตอบได้โดยไม่มีตัวตนใด ๆ"
        assert resp.headers["Cache-Control"] == "no-store"


def test_health_requests_do_not_flood_the_request_log(app):
    """คำขอ health มาทุกไม่กี่วินาที — ต้องไม่ลง log รายคำขอ (แต่คำขออื่นยังลงครบ)"""
    import logging

    lines: list[str] = []

    class Grab(logging.Handler):
        def emit(self, record):
            if getattr(record, "event", "") == "http_request":
                lines.append(getattr(record, "path", ""))

    handler = Grab(level=logging.INFO)
    app.logger.addHandler(handler)
    try:
        client = app.test_client()
        client.get("/healthz")
        client.get("/readyz")
        client.get("/login")
    finally:
        app.logger.removeHandler(handler)
    assert "/healthz" not in lines
    assert "/readyz" not in lines
    assert "/login" in lines, "คำขอปกติต้องยังลง log ครบ — ไม่งั้นการข้ามกว้างเกินไป"


def test_health_still_returns_the_request_id_header(app):
    """ข้าม log ได้ แต่ header `X-Request-Id` ต้องยังอยู่ — เผื่อ orchestrator อ้างอิง"""
    resp = app.test_client().get("/healthz")
    assert resp.headers.get("X-Request-Id")
