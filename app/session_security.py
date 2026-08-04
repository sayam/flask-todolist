"""อายุและการต่ออายุของ session ตาม OWASP Session Management (Phase 4 — ADR 0020)

session ของ Flask **อยู่ในคุกกี้ที่เซ็นไว้ ไม่มีสำเนาฝั่ง server** ข้อเท็จจริงนี้
กำหนดวิธีทำทุกอย่างในไฟล์นี้:

* "หมุน session id" ทำไม่ได้ตรง ๆ เพราะไม่มี id ที่ชี้ไปที่เก็บของฝั่ง server
  สิ่งที่ทำแทนคือ **ล้างของเก่าทิ้งทั้งหมดแล้วเขียนใหม่** ตอน login และตอน
  เปลี่ยนรหัสผ่าน — คุกกี้ใบเก่าที่คนอื่นถืออยู่จึงไม่มีสถานะที่ยังใช้ได้เหลือ
* "ยกเลิก session ฝั่ง server" ก็ทำไม่ได้เช่นกัน การหมดอายุจึงหมายถึง
  **ไม่ยอมรับคุกกี้ใบนั้นอีก** ซึ่งต้องตรวจเองทุก request (ตัว `before_request`
  ข้างล่าง) ไม่ใช่พึ่งวันหมดอายุที่เขียนอยู่บนคุกกี้ เพราะฝั่ง client แก้ได้
* การล้าง session ของ *ตัวเอง* ไม่ได้ทำให้คุกกี้ที่ **คนอื่นถืออยู่** ใช้ไม่ได้
  เพราะใบนั้นยังเซ็นถูกและยังมีข้อมูลครบ ทางแก้คือผูกคุกกี้เข้ากับ credential
  ปัจจุบัน (`AUTH_HASH_KEY` ข้างล่าง — วิธีเดียวกับ `get_session_auth_hash()`
  ของ Django) เปลี่ยนรหัสผ่านแล้วทุกใบที่ออกก่อนหน้าตายพร้อมกันทันที

สอง timeout ต้องมีคู่กัน ตัวเดียวไม่พอ:

* **idle** — เครื่องที่ถูกทิ้งไว้ในห้องสมุด ต้องหมดอายุแม้เจ้าของยังไม่กลับมา
* **absolute** — คุกกี้ที่ถูกขโมยไปถูกใช้ต่อได้เรื่อย ๆ ถ้าคนขโมยขยันพอที่จะ
  ยิงคำขอทุก 29 นาที ตัว idle อย่างเดียวจึงไม่มีวันตัดสายนั้น
"""

import hashlib
import hmac
import time
from typing import Any

from flask import Flask, current_app, flash, redirect, request, session, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_user, logout_user

from app.i18n import SESSION_KEY as LOCALE_KEY
from app.theme import MODE_SESSION_KEY, THEME_SESSION_KEY

# เวลาที่ยืนยันตัวตนสำเร็จ (absolute) กับเวลาที่เห็นความเคลื่อนไหวล่าสุด (idle)
# เก็บเป็นวินาที epoch เพราะ session cookie เก็บได้เฉพาะของที่ serialize เป็น JSON ได้
AUTH_AT_KEY = "auth_at"
SEEN_AT_KEY = "seen_at"
# ลายนิ้วมือของ credential ที่ใช้ตอนออกคุกกี้ใบนี้ (ไม่ใช่ตัว hash รหัสผ่าน)
AUTH_HASH_KEY = "auth_hash"

# สถานะกลางทางของ MFA: ผ่านรหัสผ่านแล้วแต่ยังไม่ผ่านขั้นที่สอง
PENDING_KEY = "mfa_user"
PENDING_AT_KEY = "mfa_at"
PENDING_TTL_KEY = "mfa_ttl"

# ค่าที่ผู้ใช้เลือกไว้ก่อน login (จากหน้า login เอง) ไม่ใช่สถานะการยืนยันตัวตน
# จึงพาข้ามการล้างไปด้วยได้ — ล้างทิ้งแปลว่ากดสลับภาษาแล้วภาษาหายตอน login สำเร็จ
CARRY_OVER_KEYS = (LOCALE_KEY, THEME_SESSION_KEY, MODE_SESSION_KEY)


def _now() -> float:
    return time.time()


def auth_hash(user: object) -> str:
    """ลายนิ้วมือของ credential ปัจจุบันของผู้ใช้คนนั้น

    เป็น HMAC ของ `password_hash` (ไม่ใช่ตัว hash เอง) โดยกุญแจแยกสายมาจาก
    `SECRET_KEY` — ค่าที่อยู่ในคุกกี้จึงเอาไปย้อนกลับเป็น hash รหัสผ่านไม่ได้
    ต่อให้คุกกี้หลุด (`password_hash` เป็นชั้น C1 ห้ามออกจากระบบทุกรูปแบบ)

    พอรหัสผ่านเปลี่ยน ค่านี้เปลี่ยนตาม **คุกกี้ทุกใบที่ออกก่อนหน้าจึงตายพร้อมกัน**
    รวมถึงใบที่อยู่ในมือคนอื่น ซึ่งเป็นสิ่งเดียวที่ทำให้ "เปลี่ยนรหัสเพราะถูกยึด
    บัญชี" มีความหมายจริงบนระบบที่ session อยู่ในคุกกี้
    """
    key = hashlib.blake2b(
        str(current_app.config["SECRET_KEY"]).encode("utf-8"), person=b"tdl-session"
    ).digest()
    material = str(getattr(user, "password_hash", "")).encode("utf-8")
    return hmac.new(key, material, hashlib.sha256).hexdigest()


def start_session(user: object) -> None:
    """ยืนยันตัวตนสำเร็จ — ล้าง session เก่าทิ้งทั้งใบก่อนเขียนของใหม่

    **การล้างคือหัวใจ ไม่ใช่ขั้นตอนเสริม** ถ้าเขียนทับเฉย ๆ ค่าที่คนอื่นแอบวาง
    ไว้ในคุกกี้ก่อนหน้า (session fixation) จะยังอยู่ครบและกลายเป็นของ session
    ที่ผ่านการยืนยันตัวตนแล้ว
    """
    # ผู้เรียกอาจส่ง `current_user` มา ซึ่งเป็น proxy ที่หาตัวเองจาก session
    # ตอนถูกใช้ — ถ้าไม่คลี่เป็น object จริงก่อนล้าง session มันจะวนหาตัวเอง
    # ในของที่เพิ่งล้างไปจน RecursionError (เจอมาแล้วตอนเขียน renew_session)
    resolved = getattr(user, "_get_current_object", lambda: user)()

    carried = {key: session[key] for key in CARRY_OVER_KEYS if key in session}
    session.clear()
    session.update(carried)
    login_user(resolved)
    # **ห้ามตั้ง `session.permanent = True`** สองเหตุผล:
    # 1. คุกกี้แบบไม่ permanent ตายเมื่อปิดเบราว์เซอร์ ซึ่งเป็นสิ่งที่ควรเกิด
    #    บนเครื่องที่ใช้ร่วมกัน อายุที่แท้จริงคุมด้วย `has_expired()` ฝั่ง server
    #    อยู่แล้ว ไม่ได้พึ่งวันหมดอายุบนคุกกี้ที่ฝั่ง client แก้ได้
    # 2. `session_protection = "strong"` ของ Flask-Login **ไม่ล้าง session ให้
    #    ถ้า session เป็น permanent** (มันแค่ mark ว่าไม่ fresh แล้วปล่อยผ่าน —
    #    ดู `_session_protection_failed`) ตั้ง permanent เมื่อไหร่ การผูกคุกกี้
    #    กับเครื่องก็หายไปเงียบ ๆ ทั้งที่ config ยังเขียนว่า strong
    session[AUTH_AT_KEY] = _now()
    session[SEEN_AT_KEY] = _now()
    session[AUTH_HASH_KEY] = auth_hash(resolved)


def begin_pending(user: object, seconds: float) -> None:
    """ผ่านรหัสผ่านแล้วแต่ยังไม่ผ่านขั้นที่สอง — **ยังไม่ใช่ session ที่ login แล้ว**

    เก็บแค่ "ใครกำลังรอ" กับ "ตั้งแต่เมื่อไหร่" ไม่เรียก `login_user()`
    เพราะระหว่างนี้ยังไม่มีสิทธิ์อะไรเลย (ถ้าเรียก คนที่รู้แค่รหัสผ่านจะเข้า
    ถึงข้อมูลได้ทันทีโดยไม่ต้องกรอกรหัสจากแอปเลย ซึ่งคือการมี MFA แต่ไม่บังคับ)
    """
    carried = {key: session[key] for key in CARRY_OVER_KEYS if key in session}
    session.clear()
    session.update(carried)
    session[PENDING_KEY] = int(getattr(user, "id", 0))
    session[PENDING_AT_KEY] = _now()
    session[PENDING_TTL_KEY] = float(seconds)


def pending_user_id() -> int | None:
    """ใครกำลังรอกรอกรหัสขั้นที่สอง — หมดเวลาแล้วถือว่าไม่มี

    มีอายุสั้น ๆ เพราะสถานะนี้คือ "ผ่านรหัสผ่านไปแล้ว" ซึ่งเป็นครึ่งทางของการ
    ยืนยันตัวตน ปล่อยค้างไว้นานเท่ากับลดค่าของขั้นที่สองลง
    """
    user_id = session.get(PENDING_KEY)
    started = session.get(PENDING_AT_KEY)
    ttl = session.get(PENDING_TTL_KEY)
    if not isinstance(user_id, int) or not isinstance(started, (int, float)):
        return None
    if not isinstance(ttl, (int, float)) or _now() - started > ttl:
        return None
    return user_id


def clear_pending() -> None:
    """ลบสถานะกลางทางทิ้ง (สำเร็จแล้วหรือเลิกกลางคัน)"""
    for key in (PENDING_KEY, PENDING_AT_KEY, PENDING_TTL_KEY):
        session.pop(key, None)


def end_session() -> None:
    """ออกจากระบบ — ล้างทั้งใบ เหลือไว้แค่ค่าที่ใช้แสดงผลหน้า login

    `logout_user()` ลบเฉพาะคีย์ของ Flask-Login ของอื่นที่ค้างอยู่ใน session
    (เช่นตัวกรองที่จำไว้) จะติดไปให้คนถัดไปที่ใช้เครื่องเดียวกันเห็น
    """
    logout_user()
    carried = {key: session[key] for key in CARRY_OVER_KEYS if key in session}
    session.clear()
    session.update(carried)


def renew_session() -> None:
    """ออกคุกกี้ใบใหม่ให้คนที่ login อยู่แล้ว — ใช้หลังเปลี่ยนรหัสผ่าน

    เหตุผลเดียวกับตอน login: คุกกี้ใบเก่าที่หลุดไปแล้วต้องใช้ต่อไม่ได้
    ไม่งั้นการเปลี่ยนรหัสผ่านเพราะสงสัยว่าถูกยึดบัญชีจะไม่ได้ไล่ใครออกเลย
    """
    if current_user.is_authenticated:
        start_session(current_user)


def _seconds(app: Flask, key: str, per_unit: int) -> float:
    return float(app.config[key]) * per_unit


def has_expired(app: Flask, now: float) -> bool:
    """คุกกี้ใบนี้หมดอายุแล้วหรือยัง — ไม่มีเวลาบันทึกไว้ก็ถือว่าหมด

    คุกกี้ที่ออกก่อนมีฟีเจอร์นี้ (หรือถูกแก้จนค่าหาย) จะไม่มีสองคีย์นี้
    ตัดสินว่า "หมดอายุ" ไว้ก่อนเสมอ — fail closed
    """
    auth_at = session.get(AUTH_AT_KEY)
    seen_at = session.get(SEEN_AT_KEY)
    if not isinstance(auth_at, (int, float)) or not isinstance(seen_at, (int, float)):
        return True
    if now - auth_at > _seconds(app, "SESSION_ABSOLUTE_HOURS", 3600):
        return True
    return now - seen_at > _seconds(app, "SESSION_IDLE_MINUTES", 60)


def init_session_security(app: Flask) -> None:
    """ผูกด่านตรวจอายุ session เข้ากับทุก request ของแอป"""
    from app.api.base import API_PREFIX

    def _is_exempt() -> bool:
        """คำขอที่ด่านนี้ไม่เกี่ยวด้วยเลย

        * ไม่มีตัวตนที่มาจาก session — ไม่มีอะไรให้หมดอายุ
        * **คำขอของ API** ถึงจะมีคุกกี้เก่าติดมาด้วยก็ห้ามแตะ ตัวตนของ API
          มาจาก token ล้วน ๆ (ADR 0018) การเด้งไปหน้า login ตรงนี้จะทำให้
          คำขอที่มี token ถูกต้องพังเพราะคุกกี้ที่ไม่เกี่ยวกันเลย
        * ไฟล์ static ไม่ผูกกับตัวตนและเบราว์เซอร์ยิงมาขนานกับหน้าเว็บ —
          เด้ง CSS ไปหน้า login แปลว่าหน้าที่เด้งไปนั้นไม่มีสไตล์
        """
        return (
            not session.get("_user_id")
            or request.path.startswith(API_PREFIX)
            or request.endpoint == "static"
        )

    @app.before_request
    def enforce_session_lifetime() -> Any:
        if _is_exempt():
            return None

        if has_expired(app, _now()):
            return _sign_out(_("Your session has expired — please sign in again"))

        # ถึงตรงนี้ค่อยแตะ `current_user` (= query หนึ่งครั้ง) เพราะสองด่านบน
        # ตัดสินได้จากในคุกกี้ล้วน ๆ ไม่ต้องแตะฐานข้อมูลเลย
        if not current_user.is_authenticated:
            # session_protection ของ Flask-Login เพิ่งตัดทิ้งไป (IP/user agent ไม่ตรง)
            # หรือแถวผู้ใช้หายไปแล้ว — ทั้งสองกรณีคือ "คุกกี้ใบนี้ใช้ไม่ได้แล้ว"
            return _sign_out(_("Your session has expired — please sign in again"))

        if not hmac.compare_digest(str(session.get(AUTH_HASH_KEY, "")), auth_hash(current_user)):
            return _sign_out(_("Your password was changed — please sign in again"))

        session[SEEN_AT_KEY] = _now()
        return None

    def _sign_out(message: str) -> Any:
        logout_user()
        session.clear()
        flash(message)
        return redirect(url_for("auth.login"))
