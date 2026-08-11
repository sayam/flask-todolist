"""LDAP เป็นปัจจัยหลักแบบ `credential` — รับชื่อกับรหัสผ่านมาตรวจตรง ๆ (ADR 0029)

สัญญาที่ core เรียก (ดู `app/services/sso.py`): `authenticate(username, password)`
คืน `User` ของที่นี่ หรือ `None` ถ้า directory ไม่รู้จักคู่นี้

**core เรียกตัวนี้ก็ต่อเมื่อรหัสผ่านของที่นี่ไม่ผ่านแล้วเท่านั้น** (ADR 0029 ข้อ 2)

สามข้อที่เป็นความปลอดภัยล้วน ๆ และต้องอยู่ในโค้ดนี้ ไม่ใช่หวังว่า directory
ปลายทางจะตั้งค่าไว้ถูก:

1. **รหัสผ่านว่าง = ปฏิเสธทันที** — LDAP หลายตัวตีความ bind ที่รหัสผ่านว่างเป็น
   *anonymous bind* ซึ่ง **สำเร็จ** แปลว่าใครส่งรหัสว่างมาก็ "ยืนยันตัวตนผ่าน"
   ทั้งที่ไม่รู้อะไรเลย
2. **ยืนยันตัวตน = bind สำเร็จด้วย credential ของผู้ใช้เอง** บัญชีบริการมีไว้
   *ค้น* `dn` จากชื่อผู้ใช้เท่านั้น เพราะรูปแบบ `dn` ต่างกันตาม directory —
   ห้ามใช้ผลการค้นหาแทนการ bind
3. **TLS ไม่ใช่ตัวเลือก** รหัสผ่านของผู้ใช้เดินทางไป directory ทุกครั้งที่ login
   `ldap://` เปล่า ๆ คือการส่งรหัสผ่านเป็นข้อความธรรมดา

**ไลบรารีไม่มี = ปิดตัวเอง ไม่ใช่พัง** (ADR 0025) — `import` ที่ล้มเป็นสถานะ
ปกติที่ออกแบบไว้ และ core เช็ค `is_installed()` ก่อนใช้งานอยู่แล้ว
"""

import os
from typing import Any

import ldap3
from flask import current_app
from flask_babel import gettext as _
from sqlalchemy import select

from app import audit, db
from app.models import User
from app.services.errors import ValidationError

from .models import DirectoryIdentity

# ไม่ให้คำขอค้างเพราะ directory ที่ไม่ตอบ — คำขอที่ค้างคือ worker ที่หายไปหนึ่งตัว
CONNECT_TIMEOUT_SECONDS = 5


def _setting(name: str, default: str = "") -> str:
    """อ่านจาก config ของแอปก่อน แล้วค่อยตกไปที่ environment

    เหตุผลเดียวกับ `auth/oidc`: core ไม่ประกาศคีย์ของ plugin ไว้ใน `config.py`
    (ADR 0023) และเทสต์ต้องตั้งค่าได้โดยไม่แตะ environment ของเครื่องที่รัน
    """
    value = current_app.config.get(name)
    if value is None:
        value = os.environ.get(name, default)
    return str(value)


def _require(name: str) -> str:
    value = _setting(name)
    if not value:
        raise ValidationError(
            _("The directory is not configured"), code="ldap_not_configured", field=name
        )
    return value


def _server_url() -> str:
    """URL ของ directory — **ต้องเป็น ldaps:// เว้นแต่จะสั่งเป็นอย่างอื่น**"""
    url = _require("LDAP_URL")
    if not url.startswith("ldaps://"):
        if _setting("LDAP_INSECURE") != "1":
            raise ValidationError(
                _("The directory is not configured"), code="ldap_insecure", field="LDAP_URL"
            )
        # ดังทุกครั้งที่ถูกใช้ ไม่ใช่ครั้งเดียวตอน start — ข้อนี้แปลว่ารหัสผ่าน
        # ของผู้ใช้ทุกคนเดินทางเป็นข้อความธรรมดา (ADR 0029 ข้อ 6)
        current_app.logger.warning(
            "LDAP_URL ไม่ได้ใช้ ldaps:// และ LDAP_INSECURE=1 — "
            "รหัสผ่านของผู้ใช้เดินทางเป็นข้อความธรรมดา (ADR 0029 ข้อ 6)"
        )
    return url


def _connect(user: str | None = None, password: str | None = None) -> Any:
    """เปิดการเชื่อมต่อแล้ว bind — คืน connection ที่ bind แล้ว หรือ `None` ถ้าไม่ผ่าน

    `raise_exceptions=False` เพราะ "รหัสผ่านไม่ถูก" ไม่ใช่ข้อผิดพลาดของโปรแกรม
    มันเป็นคำตอบที่ถูกต้องคำตอบหนึ่งของฟังก์ชันนี้
    """
    # **`get_info=NONE` ไม่ใช่การปิดการตรวจสอบเพื่อความสะดวก** — ค่าเริ่มต้นทำให้
    # ldap3 ดึง schema มาแล้วปฏิเสธ attribute ที่ไม่ได้ประกาศไว้ ซึ่งรวมถึง
    # **operational attribute อย่าง `memberOf`** ที่ overlay เป็นคนเติมให้ตอน
    # query ผลคือ `invalid attribute type memberOf` ทั้งที่ directory ตอบได้ปกติ
    # (เจอจริงตอนต่อกับ OpenLDAP — P5-14) และยังประหยัด round trip ไปหนึ่งครั้ง
    server = ldap3.Server(
        _server_url(), connect_timeout=CONNECT_TIMEOUT_SECONDS, get_info=ldap3.NONE
    )
    try:
        connection = ldap3.Connection(
            server, user=user, password=password, auto_bind=False, raise_exceptions=False
        )
        if not connection.bind():
            return None
    except ldap3.core.exceptions.LDAPException as error:
        # ต่อไม่ติด/TLS ไม่ผ่าน = **ตอบไม่ได้** ไม่ใช่ตอบว่าไม่ใช่ — แต่ผลลัพธ์
        # ที่ปลอดภัยของความไม่แน่นอนนี้คือ login ไม่ผ่าน (core จะ log ให้เอง)
        raise ValidationError(
            _("Could not reach the directory"), code="ldap_unreachable"
        ) from error
    return connection


def _find_entry(username: str) -> tuple[str, str, list[str]] | None:
    """ค้น `dn`, ตัวระบุที่ใช้ผูก, และกลุ่มของผู้ใช้ด้วยบัญชีบริการ

    **ยังไม่ใช่การยืนยันตัวตน** — และ **คืน `dn` แยกจากตัวระบุที่ใช้ผูกเสมอ**
    เพราะสองอย่างนี้เป็นคนละเรื่องเมื่อตั้ง `LDAP_ID_ATTRIBUTE`: ตัวระบุอาจเป็น
    uuid ที่ bind ไม่ได้ ส่วนสิ่งที่ต้องเอาไป bind คือ `dn` เสมอ
    """
    connection = _connect(_setting("LDAP_BIND_DN") or None, _setting("LDAP_BIND_PASSWORD") or None)
    if connection is None:
        raise ValidationError(
            _("The directory is not configured"), code="ldap_bind_failed", field="LDAP_BIND_DN"
        )
    attribute = _setting("LDAP_ID_ATTRIBUTE")
    wanted = [attribute] if attribute else []
    # `%s` ตัวเดียวในเทมเพลตที่ผู้ดูแลตั้ง — ค่าที่แทนลงไปถูก escape ก่อนเสมอ
    search_filter = _require("LDAP_USER_FILTER") % ldap3.utils.conv.escape_filter_chars(username)
    try:
        connection.search(_require("LDAP_BASE_DN"), search_filter, attributes=wanted)
    except ldap3.core.exceptions.LDAPException as error:
        # **การค้นที่ล้มต้องกลายเป็น "ตอบไม่ได้" ไม่ใช่ 500** — base dn ที่ผิด
        # หรือ attribute ที่ directory ไม่รู้จักเป็นเรื่อง config ของผู้ดูแล
        # ไม่ใช่บั๊กที่ควรทำให้หน้า login ทั้งหน้าพัง (เจอจริงตอนต่อกับ OpenLDAP)
        raise ValidationError(
            _("Could not reach the directory"), code="ldap_search_failed"
        ) from error
    if not connection.entries:
        return None
    entry = connection.entries[0]
    dn = str(entry.entry_dn)
    external_id = str(entry[attribute].value) if attribute else dn
    return dn, external_id, _groups_of(connection, dn)


def _groups_of(connection: Any, dn: str) -> list[str]:
    """กลุ่มของผู้ใช้ — **ค้นจากฝั่งกลุ่ม ไม่ใช่อ่าน `memberOf` จากฝั่งผู้ใช้**

    `memberOf` เป็น attribute ที่ **ไม่ได้มีในทุก directory**: Active Directory
    มีให้ในตัว ส่วน OpenLDAP ต้องเปิด overlay และ **overlay นั้นไม่เติมย้อนหลัง
    ให้สมาชิกที่มีอยู่ก่อนเปิด** ผลคือ group → role เงียบ ๆ ไม่ทำงานโดยไม่มี
    error อะไรให้เห็น (เจอจริงตอนต่อกับ OpenLDAP — P5-14: login ผ่านแต่ทุกคน
    เป็น `user` หมด)

    การค้นจากฝั่งกลุ่มด้วย `(member=<dn>)` ใช้ได้กับทุก directory เพราะสมาชิก
    ถูกเก็บไว้ที่กลุ่มเสมอตามนิยามของ `groupOfNames` — แลกกับการค้นเพิ่มหนึ่งครั้ง
    ต่อการ login หนึ่งครั้ง **และทำก็ต่อเมื่อมีคนตั้งกลุ่มของ admin ไว้จริง ๆ**
    """
    if not _setting("LDAP_ADMIN_GROUP"):
        return []
    group_filter = _setting("LDAP_GROUP_FILTER", "(member=%s)") % (
        ldap3.utils.conv.escape_filter_chars(dn)
    )
    try:
        connection.search(_require("LDAP_BASE_DN"), group_filter)
    except ldap3.core.exceptions.LDAPException as error:
        raise ValidationError(
            _("Could not reach the directory"), code="ldap_search_failed"
        ) from error
    return [str(entry.entry_dn) for entry in connection.entries]


def _apply_role(user: User, groups: list[str]) -> None:
    """map กลุ่มของ directory เป็นบทบาทของที่นี่ (ADR 0029 ข้อ 3 → ADR 0028 ข้อ 5)

    **ไม่ได้ตั้งกลุ่มไว้ = ไม่แตะ `role` เลย** ไม่ใช่ตั้งเป็น `user`
    """
    admin_group = _setting("LDAP_ADMIN_GROUP")
    if not admin_group:
        return
    # เทียบแบบไม่สนตัวพิมพ์ เพราะ `dn` ของกลุ่มใน directory ส่วนใหญ่ไม่สนอยู่แล้ว
    wanted = admin_group.casefold()
    user.role = "admin" if any(group.casefold() == wanted for group in groups) else "user"


def _user_for(username: str, external_id: str) -> User | None:
    """หาผู้ใช้ของที่นี่ที่ตรงกับตัวระบุนั้น — ผูกครั้งแรกด้วยชื่อ (ADR 0029 ข้อ 4)"""
    directory = _server_url()
    identity = db.session.scalars(
        select(DirectoryIdentity).where(
            DirectoryIdentity.directory == directory,
            DirectoryIdentity.external_id == external_id,
        )
    ).first()
    if identity is not None:
        # ผู้ใช้ที่ถูกลบไปแล้ว (soft delete) หาไม่เจอ → ปฏิเสธ ไม่ใช่สร้างใหม่ให้
        # ไม่งั้นการลบบัญชีจะกลายเป็นการคืนบัญชีตอน login ครั้งถัดไป
        return db.session.get(User, identity.user_id)

    user = db.session.scalars(select(User).where(User.username == username)).first()
    if user is None:
        if _setting("LDAP_AUTO_CREATE") != "1":
            return None
        user = User(username=username)
        # บัญชีที่เกิดจาก directory ไม่มีรหัสผ่านของที่นี่จนกว่าผู้ดูแลจะตั้งให้
        user.disable_password()
        db.session.add(user)
        db.session.flush()

    db.session.add(DirectoryIdentity(user_id=user.id, directory=directory, external_id=external_id))
    audit.record("auth.directory_linked", table_name="tdl_user", row_id=user.id)
    return user


def authenticate(username: str, password: str) -> User | None:
    """directory รู้จักคู่นี้ไหม — คืน `User` ของที่นี่ หรือ `None`"""
    if not password:
        # **ข้อนี้ต้องมาก่อนทุกอย่าง** — bind ด้วยรหัสผ่านว่างคือ anonymous bind
        # ซึ่งสำเร็จในหลาย directory (ADR 0029 ข้อ 5)
        return None
    if not username.strip():
        return None

    found = _find_entry(username)
    if found is None:
        return None
    dn, external_id, groups = found

    # **การยืนยันตัวตนเกิดที่บรรทัดนี้บรรทัดเดียว** — bind ด้วย `dn` ของผู้ใช้
    # กับรหัสผ่านที่เขาพิมพ์มา ผลการค้นหาข้างบนเป็นแค่การหาว่าจะ bind ด้วย dn ไหน
    # **ต้องเป็น `dn` ไม่ใช่ `external_id`** — ตอนตั้ง `LDAP_ID_ATTRIBUTE` ตัวระบุ
    # เป็น uuid ซึ่ง bind ไม่ได้ และการส่ง `None` ไปแทนคือ anonymous bind ที่
    # **สำเร็จ** ในหลาย directory = ใครก็ผ่านด่านนี้ได้ (ADR 0029 ข้อ 5)
    verified = _connect(dn, password)
    if verified is None:
        return None
    verified.unbind()

    user = _user_for(username, external_id)
    if user is None:
        return None
    _apply_role(user, groups)
    db.session.commit()
    return user
