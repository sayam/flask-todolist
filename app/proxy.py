"""เชื่อ header ของ reverse proxy — **เฉพาะเมื่อบอกว่ามีกี่ชั้น** (Phase 5 · P5-11)

พอ app อยู่หลัง proxy (ซึ่งเป็นเงื่อนไขของการมีหลาย replica) สิ่งที่ WSGI เห็น
จะเป็นของ *proxy* ไม่ใช่ของ client: `REMOTE_ADDR` เป็นไอพีของ proxy ทุกคำขอ
และ scheme เป็น `http` แม้ผู้ใช้จะเข้ามาทาง https

สองอย่างนั้นพังคนละแบบ และทั้งคู่พังเงียบ:

- **`remote_addr` เป็นไอพีเดียวกันหมด** → กุญแจของ rate limit ต่อไอพีกลายเป็น
  ก้อนเดียวสำหรับคนทั้งโลก คนที่ไล่เดารหัสผ่านจะกิน quota ของคนอื่นจนหมด
  (มิติต่อชื่อผู้ใช้ตาม ADR 0021 ยังทำงานอยู่ จึงเป็น "แย่ลง" ไม่ใช่ "เปิดโล่ง")
  และ `remote_addr` ใน log ก็เลิกตอบคำถามว่าใครยิงมา
- **scheme เป็น `http`** → `HTTPS_ENABLED=1` จะสั่ง redirect ไป https ทุกคำขอ
  ทั้งที่ผู้ใช้มาทาง https อยู่แล้ว = วนไม่รู้จบจน login ไม่ได้ (P5-12 จะใช้ตรงนี้)

**ค่าเริ่มต้นคือไม่เชื่อเลย** และนั่นไม่ใช่ความขี้เกียจ — `X-Forwarded-For` เป็น
header ธรรมดาที่ client ตั้งเองได้ ถ้าเชื่อโดยไม่มีใครล้างค่าให้ก่อน คนยิงจะ
ปลอมไอพีใหม่ทุกคำขอแล้ว **หลุด rate limit ต่อไอพีทั้งหมด** ซึ่งแย่กว่าสภาพ
"ทุกคนใช้ก้อนเดียวกัน" ที่เรากำลังจะแก้เสียอีก

**ค่าที่ตั้งเป็นจำนวนชั้น ไม่ใช่ boolean** เพราะ ProxyFix อ่านค่าที่ N จากขวา
ค่าที่ client แนบมาเองจะอยู่ซ้ายสุดเสมอ (proxy แต่ละชั้น *ต่อท้าย*) การนับให้ตรง
กับจำนวน proxy ที่เรารันจริงจึงเป็นสิ่งเดียวที่แยก "ไอพีของ client" ออกจาก
"ค่าที่ client อยากให้เราเชื่อ" — ตั้งเกินจริงเมื่อไหร่ ก็เท่ากับเชื่อค่าปลอม
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from werkzeug.middleware.proxy_fix import ProxyFix

if TYPE_CHECKING:
    from flask import Flask


def init_proxy_fix(app: Flask) -> None:
    """ผูก `ProxyFix` ตามจำนวนชั้นที่ config บอก (0 = ไม่ผูกอะไรเลย)"""
    hops = int(app.config.get("TRUSTED_PROXY_HOPS", 0) or 0)
    if hops < 0:
        raise ValueError("TRUSTED_PROXY_HOPS ต้องไม่ติดลบ")
    if hops == 0:
        return

    # ผูกเฉพาะสามอย่างที่เราใช้จริง — `x_for` (rate limit + log),
    # `x_proto` (Talisman/HSTS ตอน TLS จบที่ proxy) และ `x_host` (url_for แบบเต็ม)
    # ไม่เปิด `x_port`/`x_prefix` เพราะไม่มีอะไรในแอปนี้พึ่งมัน และทุก header
    # ที่เราประกาศว่าเชื่อ คือหนึ่งค่าที่ proxy ต้องรับผิดชอบล้างให้
    app.wsgi_app = ProxyFix(  # type: ignore[method-assign]
        app.wsgi_app, x_for=hops, x_proto=hops, x_host=hops
    )
    app.logger.info("trusting reverse proxy headers", extra={"trusted_proxy_hops": hops})
