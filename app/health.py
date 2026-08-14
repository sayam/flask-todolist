"""liveness / readiness (ADR 0048) — ของ orchestrator ไม่ใช่ของคน

สองเส้นทาง สองคำถาม **ห้ามยุบเป็นเส้นเดียว**:

- `GET /healthz` (liveness) — โปรเซสยังหายใจไหม · **ไม่แตะฐานข้อมูลโดยตั้งใจ**
  liveness ที่แตะ DB คือ liveness ที่สั่ง restart ทุก replica พร้อมกันตอน DB
  สะดุด — แปลงเหตุขัดข้องชั้นเดียวให้กลายเป็นสองชั้น
- `GET /readyz` (readiness) — พร้อมรับงานไหม: ต้องคุยกับฐานข้อมูลได้จริง
  proxy/orchestrator ใช้ตัวนี้ตัดสินว่าจะส่งงานให้ไหม

ทั้งคู่**ไม่มี token และไม่มีข้อมูลภายในใน body** (แค่ `ok`/`not ready`) —
ต่างจาก `/metrics` ที่มีข้อมูลจริงจึงต้องมี token เสมอ (ADR 0031) · และ
**ไม่ลง log รายคำขอ** (`app/logging_setup.py` ข้าม path พวกนี้) เพราะมันมา
ทุกไม่กี่วินาทีโดยไม่มีสาระ — log ที่มีแต่เสียงเดิมซ้ำ ๆ คือ log ที่ไม่มีใครอ่าน
ความล้มเหลวของ readiness ยัง log เสมอ (นั่นคือตอนที่มีสาระ)
"""

from flask import Blueprint, current_app
from sqlalchemy import text

from app import db

bp = Blueprint("health", __name__)

# ให้ logging_setup ใช้ตัดสินว่า path ไหนไม่ต้องลง log รายคำขอ
HEALTH_PATHS = frozenset({"/healthz", "/readyz"})
_PLAIN = {"Content-Type": "text/plain; charset=utf-8", "Cache-Control": "no-store"}


@bp.route("/healthz")
def healthz():
    """โปรเซสยังตอบ HTTP ได้ = ยังมีชีวิต — แค่นั้นจริง ๆ"""
    return "ok", 200, _PLAIN


@bp.route("/readyz")
def readyz():
    """พร้อมรับงานเมื่อคุยกับฐานข้อมูลได้จริง — ไม่พร้อมตอบ 503 พร้อม log"""
    try:
        db.session.execute(text("SELECT 1"))
        db.session.rollback()
    except Exception:
        # log เฉพาะตอนไม่พร้อม — สาเหตุอยู่ใน log ส่วน body บอกแค่สถานะ
        current_app.logger.warning("readyz: ฐานข้อมูลไม่ตอบ", exc_info=True)
        return "not ready", 503, _PLAIN
    return "ok", 200, _PLAIN
