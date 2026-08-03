"""ยืนยันตัวตนของ API ด้วย bearer token เท่านั้น (ดู ADR 0017 และ 0018)

**กติกาที่ห้ามผิด: cookie ของเบราว์เซอร์ยกระดับเป็นสิทธิ์ API ไม่ได้**

`/api/v1` ถูกยกเว้น CSRF (ถูกต้องแล้ว เพราะ bearer token ไม่ถูกเบราว์เซอร์แนบเอง)
แต่ถ้าด่านของ API ตรวจแค่ `current_user.is_authenticated` เบราว์เซอร์ที่ login
ค้างอยู่จะกลายเป็นตัวยิงให้เว็บของคนอื่นทันที — เท่ากับเปิดรู CSRF ที่ปิดไว้
ตั้งแต่ Phase 1 กลับมาโดยไม่มีใครสังเกต

ด่านจึงตรวจ `g.api_token` ซึ่งถูกตั้งได้ทางเดียวคือผ่าน header `Authorization`
ที่ตรวจผ่านแล้วเท่านั้น (`tests/test_api_auth.py` ยิงด้วย session cookie จริง
เพื่อพิสูจน์ว่ายังโดนปฏิเสธ)

ในทางกลับกัน token **ต้อง** ทำให้ `current_user` ใช้งานได้ ไม่งั้น `actor_id`
ใน audit จะว่างเปล่าและเราจะไม่รู้ว่าใครเป็นคนแก้ข้อมูล
"""

from typing import Any

from flask import Request, g
from flask_login import current_user
from flask_smorest import abort

from app import login_manager
from app.models import User
from app.services import tokens as tokens_service

# ชื่อ scheme ตาม RFC 6750 — เทียบแบบไม่สนตัวพิมพ์
BEARER = "bearer"
API_PREFIX = "/api/"
UNAUTHORIZED = 401

# ส่งกลับใน 401 ตาม RFC 6750 ให้ client รู้ว่าต้องใช้ scheme ไหน
CHALLENGE = {"WWW-Authenticate": 'Bearer realm="api"'}


def bearer_token(source: Request) -> str | None:
    """ค่าใน `Authorization: Bearer <token>` — None ถ้าไม่มีหรือ scheme ไม่ตรง"""
    scheme, _, value = source.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != BEARER:
        return None
    return value.strip() or None


@login_manager.request_loader
def load_user_from_api_token(source: Request) -> User | None:
    """ยกระดับ bearer token เป็น `current_user` — **เฉพาะคำขอที่ยิงมาที่ `/api/`**

    Flask-Login เรียก loader ตัวนี้ทุกคำขอที่ไม่มี session จำกัดขอบเขตด้วย path
    เพื่อไม่ให้หน้าเว็บ HTML รับ token จาก header ได้ด้วย — หน้าเว็บมีด่าน CSRF
    ที่คิดมาบนสมมติฐานว่าตัวตนมาจาก cookie เท่านั้น
    """
    if not source.path.startswith(API_PREFIX):
        return None
    raw = bearer_token(source)
    if raw is None:
        return None
    token = tokens_service.authenticate(raw)
    if token is None:
        return None
    # เก็บใบที่ใช้ไว้ให้ด่านตรวจซ้ำได้ว่า "ตัวตนนี้มาจาก token จริง ๆ"
    g.api_token = token
    return token.user


def require_api_token() -> None:
    """ด่านของทุก endpoint ใน `/api/v1` — ผูกไว้ที่ `before_request` ของ blueprint

    ผูกที่ระดับ blueprint ไม่ใช่ decorator ต่อ view เพราะ decorator ที่ต้องจำ
    ไปแปะเองคือ decorator ที่วันหนึ่งจะลืมแปะ แล้ว endpoint นั้นจะเปิดโล่ง
    (`tests/test_api_auth.py` ไล่ทุก rule ใน url_map ซ้ำอีกชั้น)
    """
    # แตะ `current_user` ก่อนหนึ่งครั้งเพื่อ "ปลุก" loader — Flask-Login เรียก
    # `request_loader` แบบ lazy ตอนมีคนอ่านค่าครั้งแรกเท่านั้น ถ้าไม่แตะตรงนี้
    # `g.api_token` จะยังว่างอยู่เสมอตอน before_request แล้วทุกคำขอจะได้ 401
    # (เคยเป็นมาแล้วตอนเขียนครั้งแรก — token ถูกต้องแต่ถูกปฏิเสธทั้งหมด)
    if not current_user.is_authenticated or getattr(g, "api_token", None) is None:
        abort(
            UNAUTHORIZED,
            message="Send a personal access token as: Authorization: Bearer <token>",
            headers=CHALLENGE,
        )


def current_api_token() -> Any:
    """ใบที่ใช้ยืนยันตัวตนของคำขอนี้ — มีค่าเสมอหลังผ่าน `require_api_token()`"""
    return g.api_token


def token_owner() -> User:
    """เจ้าของ token ของคำขอนี้ — ใช้แทน `current_user` เพื่อไม่ต้องแกะ proxy

    ค่าเดียวกับ `current_user` ทุกประการ (loader ข้างบนเป็นคนตั้งให้) แต่เป็น
    `User` จริง ไม่ใช่ `LocalProxy` ซึ่งทำให้ mypy ตรวจให้ได้ว่าส่งของถูกชนิด
    เข้า service
    """
    owner: User = current_api_token().user
    return owner
