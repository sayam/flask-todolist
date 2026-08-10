"""OIDC เป็นปัจจัยหลักตัวที่สอง — authorization code flow + PKCE (ADR 0028)

**ไม่มี `requires.pip` เลย** ใช้ stdlib ล้วน ซึ่งเป็นไปได้เพราะคำตัดสินข้อ 4
ของ ADR 0028: ID token ที่ได้มาจาก token endpoint **โดยตรง** ผ่านช่องทางที่
TLS ยืนยันตัวตนของ server แล้ว ใช้การยืนยันของ TLS แทนการตรวจลายเซ็นได้
(OIDC Core 1.0 §3.1.3.7 ข้อ 6) — **นี่ไม่ใช่การเขียน crypto เอง แต่คือการ
ไม่ต้องมี crypto ตั้งแต่แรก**

ข้อจำกัดที่ต้องรักษาไว้ให้ครบ ไม่งั้นข้อ 4 ตกทั้งข้อ:

* **รับเฉพาะ authorization code flow** — implicit/hybrid ที่ ID token เดินทาง
  ผ่าน browser ต้องตรวจลายเซ็น ไม่มีข้อยกเว้น
* **`issuer` ต้องเป็น https และใบรับรองต้องถูกตรวจจริง** (`OIDC_INSECURE_ISSUER=1`
  มีไว้สำหรับ IdP ทดสอบในเครื่องเท่านั้น และเตือนทุกครั้งที่ถูกใช้)
* ยังตรวจ `iss`/`aud`/`exp`/`nonce` เองครบ — ไม่ตรวจลายเซ็นไม่ได้แปลว่าเชื่อ
  เนื้อในดิบ ๆ

สัญญาที่ core เรียก (ดู `app/services/sso.py`): `begin` / `finish`

**config อ่านจาก environment เอง** — core ไม่ประกาศคีย์ของ plugin ตัวไหนไว้ใน
`config.py` ด้วยเหตุผลเดียวกับที่ชื่อคอลัมน์ของ plugin ห้ามไปอยู่ใน `app/audit.py`
(ADR 0023): มันจะกลายเป็นขยะค้างทันทีที่มีคนถอน plugin ทิ้ง
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from flask import current_app
from flask_babel import gettext as _
from sqlalchemy import select

from app import audit, db
from app.models import User
from app.services.errors import ValidationError

from .models import OidcIdentity

# เวลาที่ยอมให้นาฬิกาของเรากับของ IdP ต่างกันตอนเทียบ `exp`
# ไม่กว้างกว่านี้เพราะทุกวินาทีที่เผื่อคืออายุที่ token ที่หมดแล้วยังใช้ได้
CLOCK_SKEW_SECONDS = 60
# กันตัวเราเองจาก IdP ที่ตอบช้าหรือไม่ตอบ — คำขอที่ค้างคือ worker ที่หายไปหนึ่งตัว
HTTP_TIMEOUT_SECONDS = 10


def _setting(name: str, default: str = "") -> str:
    """อ่านค่าจาก config ของแอปก่อน แล้วค่อยตกไปที่ environment

    ลำดับนี้ทำให้เทสต์ตั้งค่าได้โดยไม่ต้องแตะ environment ของเครื่องที่รัน
    (หลักเดียวกับ `TEST_DATABASE_URL` ที่แยกออกจาก `DATABASE_URL`)
    """
    value = current_app.config.get(name)
    if value is None:
        value = os.environ.get(name, default)
    return str(value)


def _require(name: str) -> str:
    value = _setting(name)
    if not value:
        # **ไม่ตกกลับค่าเริ่มต้นเงียบ ๆ** — ปัจจัยหลักที่ config ไม่ครบต้องบอก
        # ว่าขาดอะไร ไม่ใช่พาผู้ใช้ไปหา IdP ที่ไม่มีอยู่ (หลักเดียวกับ ADR 0026)
        raise ValidationError(
            _("Single sign-on is not configured"), code="sso_not_configured", field=name
        )
    return value


def _issuer() -> str:
    issuer = _require("OIDC_ISSUER").rstrip("/")
    if not issuer.startswith("https://"):
        if _setting("OIDC_INSECURE_ISSUER") != "1":
            raise ValidationError(
                _("Single sign-on is not configured"),
                code="sso_insecure_issuer",
                field="OIDC_ISSUER",
            )
        # ดังทุกครั้งที่ถูกใช้ ไม่ใช่ครั้งเดียวตอน start — ข้อนี้ทำให้คำตัดสิน
        # ข้อ 4 ของ ADR 0028 ตกทั้งข้อ คนที่เผลอเปิดค้างไว้ใน prod ต้องเห็น
        current_app.logger.warning(
            "OIDC issuer ไม่ได้ใช้ https และ OIDC_INSECURE_ISSUER=1 — "
            "ID token ถูกยืนยันด้วย TLS ไม่ได้อีกต่อไป (ADR 0028 ข้อ 4)"
        )
    return issuer


def _allowed_scheme() -> str:
    """scheme เดียวที่ยอมให้ยิงออกไป — `http` ได้เฉพาะตอนเปิดโหมด IdP ทดสอบ"""
    return "http" if _setting("OIDC_INSECURE_ISSUER") == "1" else "https"


def _checked(url: str) -> str:
    """ปฏิเสธ URL ที่ scheme ไม่ถูก **ก่อน** เอาไปเปิด

    **ปลายทางส่วนใหญ่มาจากเอกสาร discovery ของ IdP ไม่ใช่จาก config ของเรา**
    (`authorization_endpoint`, `token_endpoint`) เอกสารนั้นเป็นข้อมูลจาก
    ภายนอก การเชื่อค่าในนั้นดิบ ๆ แปลว่า IdP ที่ถูกยึด (หรือ DNS ที่ถูกหลอก
    ตอนดึงเอกสารครั้งแรก) สั่งให้เราเปิด `file:///etc/passwd` หรือยิงความลับ
    ของ client ไปที่ `http://` ที่ใครก็ดักได้
    """
    scheme = urllib.parse.urlparse(url).scheme
    if scheme != _allowed_scheme():
        raise ValidationError(_("Sign-in failed"), code="sso_bad_endpoint")
    return url


def _fetch(url: str, data: bytes | None = None) -> dict[str, Any]:
    """ยิง HTTP แล้วคาดหวัง JSON กลับมา — ใช้ทั้งกับ discovery และ token endpoint"""
    request = urllib.request.Request(  # noqa: S310 - scheme ถูกตรวจใน _checked() แล้ว
        _checked(url), data=data, method="POST" if data else "GET"
    )
    if data is not None:
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
    request.add_header("Accept", "application/json")
    try:
        # urllib ตรวจใบรับรองให้เองตั้งแต่ Python 3.6 — **การยืนยันตัวตนของ
        # server ตรงนี้คือสิ่งที่มาแทนการตรวจลายเซ็นของ ID token**
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:  # noqa: S310
            return dict(json.loads(response.read()))
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        # **ไม่เอาข้อความของ IdP มาแสดงต่อผู้ใช้** มันอาจมีรายละเอียดภายใน
        # และเราไม่ได้ควบคุมเนื้อหาของมัน — บันทึกไว้ใน log แทน
        current_app.logger.warning("คุยกับ IdP ไม่สำเร็จ", extra={"oidc_error": str(error)})
        raise ValidationError(
            _("Could not reach the sign-in provider"), code="sso_provider_unreachable"
        ) from error


def _discovery() -> dict[str, Any]:
    """เอกสาร metadata ของ IdP

    **ไม่ cache** โดยตั้งใจ: cache ค่าเริ่มต้นของแอปเป็น no-op จริง ๆ (P5-06)
    การเขียนโค้ดที่ถูกต้องก็ต่อเมื่อมี cache คือการทำให้ cache เป็นเรื่องของ
    ความถูกต้อง ซึ่ง ROADMAP ข้อ 4.3 ห้ามไว้ · ราคาคือหนึ่งคำขอต่อการ login
    หนึ่งครั้ง ซึ่งเทียบกับการเดินทางไป IdP แล้วไม่มีนัยสำคัญ
    """
    return _fetch(f"{_issuer()}/.well-known/openid-configuration")


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def begin(redirect_uri: str) -> tuple[str, dict[str, Any]]:
    """สร้าง URL ที่จะส่ง browser ไป และของที่ต้องจำไว้รอ callback

    สามค่าที่สร้างตรงนี้กันคนละเรื่องกัน **ไม่ใช่ของซ้ำซ้อน**:
    * `state` — กัน CSRF ของขากลับ (มีคนหลอกให้ browser ของเราไปเรียก callback)
    * `code_verifier` (PKCE) — กันคนที่ขโมย `code` ระหว่างทางเอาไปแลก token
    * `nonce` — กันการเอา ID token เก่ามาใช้ซ้ำ
    """
    metadata = _discovery()
    verifier = secrets.token_urlsafe(64)
    pending = {
        "state": secrets.token_urlsafe(32),
        "nonce": secrets.token_urlsafe(32),
        "verifier": verifier,
        "redirect_uri": redirect_uri,
    }
    query = urllib.parse.urlencode(
        {
            # **code เท่านั้น** — flow อื่นทำให้ ID token เดินทางผ่าน browser
            # ซึ่งบังคับให้ต้องตรวจลายเซ็น (ADR 0028 ข้อ 4)
            "response_type": "code",
            "client_id": _require("OIDC_CLIENT_ID"),
            "redirect_uri": redirect_uri,
            "scope": _setting("OIDC_SCOPES", "openid profile"),
            "state": pending["state"],
            "nonce": pending["nonce"],
            "code_challenge": _b64url(hashlib.sha256(verifier.encode()).digest()),
            "code_challenge_method": "S256",
        }
    )
    # ปลายทางนี้ไม่ได้ผ่าน `_fetch()` เพราะเราแค่ส่ง browser ไป จึงต้องตรวจเอง
    return f"{_checked(str(metadata['authorization_endpoint']))}?{query}", pending


def _claims_of(id_token: str, nonce: str) -> dict[str, Any]:
    """อ่านและตรวจ ID token — ตรวจทุกอย่างยกเว้นลายเซ็น (ดูหัวไฟล์)"""
    parts = id_token.split(".")
    if len(parts) != 3:  # noqa: PLR2004 - JWT มีสามส่วนตามนิยาม
        raise ValidationError(_("Sign-in failed"), code="sso_bad_token")
    padded = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        claims = dict(json.loads(base64.urlsafe_b64decode(padded)))
    except ValueError as error:
        raise ValidationError(_("Sign-in failed"), code="sso_bad_token") from error

    # `iss` ต้องตรงกับที่เราตั้งใจคุยด้วย — ข้อนี้คือสิ่งที่ผูก token เข้ากับ
    # ช่องทาง TLS ที่เราเพิ่งเปิดไป ถ้าไม่ตรวจ การยืนยันด้วย TLS ก็ไร้ความหมาย
    if claims.get("iss", "").rstrip("/") != _issuer():
        raise ValidationError(_("Sign-in failed"), code="sso_wrong_issuer")

    # `aud` เป็นสตริงเดียวหรือรายการก็ได้ตามสเปก
    audience = claims.get("aud", "")
    audiences = audience if isinstance(audience, list) else [audience]
    if _require("OIDC_CLIENT_ID") not in audiences:
        raise ValidationError(_("Sign-in failed"), code="sso_wrong_audience")

    if float(claims.get("exp", 0)) + CLOCK_SKEW_SECONDS < time.time():
        raise ValidationError(_("Sign-in failed"), code="sso_token_expired")

    # เทียบแบบคงเวลา ไม่ใช่ `==` (หลักเดียวกับ token ของ API — ADR 0017)
    if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
        raise ValidationError(_("Sign-in failed"), code="sso_nonce_mismatch")

    if not claims.get("sub"):
        raise ValidationError(_("Sign-in failed"), code="sso_no_subject")
    return claims


def _apply_role(user: User, claims: dict[str, Any]) -> None:
    """map กลุ่มของ IdP เป็นบทบาทของที่นี่ (ADR 0028 ข้อ 5)

    **ไม่ได้ตั้งกลุ่มไว้ = ไม่แตะ `role` เลย** ไม่ใช่ตั้งเป็น `user` —
    ผู้ดูแลที่ตั้งบทบาทเองด้วย `flask set-role` ต้องไม่ถูกลดสิทธิ์เพราะ
    IdP ไม่ได้ส่ง claim ที่เราไม่ได้ขอ
    """
    admin_group = _setting("OIDC_ADMIN_GROUP")
    if not admin_group:
        return
    groups = claims.get(_setting("OIDC_GROUPS_CLAIM", "groups"), [])
    if not isinstance(groups, list):
        groups = [groups]
    # ตั้งใหม่ทุกครั้งที่ login ทั้งขึ้นและลง — การถอดสิทธิ์ที่ IdP จึงมีผลจริง
    # ซึ่งคือเหตุผลที่องค์กรใช้ SSO ตั้งแต่แรก
    user.role = "admin" if admin_group in groups else "user"


def _user_for(claims: dict[str, Any]) -> User:
    """หาผู้ใช้ของที่นี่ที่ตรงกับ `sub` — ผูกครั้งแรกด้วยชื่อ (ADR 0028 ข้อ 2)"""
    issuer, subject = _issuer(), str(claims["sub"])
    identity = db.session.scalars(
        select(OidcIdentity).where(OidcIdentity.issuer == issuer, OidcIdentity.subject == subject)
    ).first()
    if identity is not None:
        user = db.session.get(User, identity.user_id)
        if user is None:
            # แถวผูกที่ชี้ไปยังผู้ใช้ที่ถูก purge ไปแล้ว — ปฏิเสธ ไม่ใช่สร้างใหม่ให้
            raise ValidationError(_("Sign-in failed"), code="sso_user_missing")
        return user

    username = str(claims.get("preferred_username", "")).strip()
    if not username:
        raise ValidationError(_("Sign-in failed"), code="sso_no_username")
    user = db.session.scalars(select(User).where(User.username == username)).first()
    if user is None:
        if _setting("OIDC_AUTO_CREATE") != "1":
            # ค่าเริ่มต้นคือ "ผู้ดูแลสร้างบัญชีไว้ก่อน" — ADR 0028 ข้อ 3
            raise ValidationError(_("No account here for that sign-in"), code="sso_no_account")
        user = User(username=username)
        # **บัญชีที่เกิดจาก IdP ไม่มีรหัสผ่านของที่นี่** จนกว่าผู้ดูแลจะตั้งให้
        # (`flask set-password`) — ใช้กลไกเดิมที่มีอยู่แล้วสำหรับ "credential
        # ที่ใช้ไม่ได้" ไม่ใช่สุ่มรหัสทิ้งไว้: `check_password()` รู้จัก sentinel
        # ตัวนี้และปฏิเสธก่อนถึง werkzeug อยู่แล้ว
        user.disable_password()
        db.session.add(user)
        db.session.flush()

    db.session.add(OidcIdentity(user_id=user.id, issuer=issuer, subject=subject))
    audit.record("auth.sso_linked", table_name="tdl_user", row_id=user.id)
    return user


def finish(params: dict[str, str], pending: dict[str, Any]) -> User:
    """ผู้ใช้กลับมาจาก IdP แล้ว — คืน `User` ของที่นี่ หรือ raise `ServiceError`"""
    if params.get("error"):
        # IdP ปฏิเสธเอง (ผู้ใช้กด "ไม่อนุญาต" หรือ config ฝั่งนั้นผิด)
        raise ValidationError(_("Sign-in was cancelled"), code="sso_denied")
    if not hmac.compare_digest(params.get("state", ""), str(pending.get("state", ""))):
        raise ValidationError(_("Sign-in failed"), code="sso_state_mismatch")
    code = params.get("code", "")
    if not code:
        raise ValidationError(_("Sign-in failed"), code="sso_no_code")

    metadata = _discovery()
    tokens = _fetch(
        metadata["token_endpoint"],
        urllib.parse.urlencode(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": str(pending["redirect_uri"]),
                "client_id": _require("OIDC_CLIENT_ID"),
                "client_secret": _require("OIDC_CLIENT_SECRET"),
                "code_verifier": str(pending["verifier"]),
            }
        ).encode(),
    )
    if "id_token" not in tokens:
        raise ValidationError(_("Sign-in failed"), code="sso_no_id_token")

    claims = _claims_of(str(tokens["id_token"]), str(pending.get("nonce", "")))
    user = _user_for(claims)
    _apply_role(user, claims)
    # service เป็นคน commit เอง ผู้เรียกไม่ต้องรู้เรื่อง session (ADR 0016)
    db.session.commit()
    return user
