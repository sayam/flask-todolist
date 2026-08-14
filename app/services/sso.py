"""ปัจจัยหลักที่ไม่ใช่รหัสผ่าน — **core ไม่รู้จักชื่อ plugin ตัวไหนเลย**

ไฟล์นี้คือทั้งหมดที่ core รู้เรื่อง SSO: ถามทุก plugin ชนิด `auth` ที่ประกาศ
ตัวเองเป็น `"factor": "primary"` และไม่ใช่ของ core ว่า "ส่งผู้ใช้ไปที่ไหน"
และ "คนที่กลับมาคือใคร"

หลักและรูปร่างเหมือน `app/services/mfa.py` ทุกอย่างโดยตั้งใจ — ปัจจัยหลัก
ตัวที่สองไม่ใช่กลไกใหม่ มันคือจุด plug ชนิดเดียวกันที่ถูกถามคนละคำถาม
(ดู ADR 0028 · สัญญาของความสามารถเป็นเรื่องของ host ตาม ADR 0025)

ผลที่ตามมาที่ตั้งใจ: **ถอนไดเรกทอรีของ plugin ทิ้ง หน้า login กลับไปเป็น
รหัสผ่านอย่างเดียวทันที** ไม่มีโค้ดตรงไหนของ core ที่พังเพราะหาไม่เจอ
"""

from typing import Any, NamedTuple

from flask import current_app
from flask_babel import gettext as _

from app import plugins
from app.services.errors import ServiceError, UnreachableError, ValidationError

# ฟังก์ชันที่ปัจจัยหลักต้องมีครบ **ต่อรูปแบบ** — host เป็นคนตรวจ ไม่ใช่ registry
# (registry ไม่รู้ว่าความสามารถแต่ละอย่างต้องมีอะไร — ADR 0025/0029)
CONTRACT = ("begin", "finish")
CREDENTIAL_CONTRACT = ("authenticate",)


def _module(plugin: plugins.Plugin, contract: tuple[str, ...] = CONTRACT) -> Any:
    module = plugins.factor_module(plugin)
    missing = [name for name in contract if not hasattr(module, name)]
    if missing:
        # บอกว่า *ใคร* ผิดสัญญา *ข้อไหน* — ข้อความที่บอกแค่ "plugin พัง"
        # ทำให้คนเขียน plugin ต้องเดาว่าตกอะไร
        raise plugins.PluginError(f"{plugin.key}: ปัจจัยหลักต้องมี {', '.join(missing)}")
    return module


def _usable(plugin: plugins.Plugin, contract: tuple[str, ...]) -> Any | None:
    """โมดูลของปัจจัยนั้น หรือ `None` ถ้ามันปิดตัวเองอยู่

    **ไลบรารีที่ขาดไป = ปิดตัวเอง ไม่ใช่พัง** (ADR 0025) — `ImportError` เป็น
    สถานะปกติที่ออกแบบไว้ หลักเดียวกับตารางที่ยังไม่ถูกสร้าง ส่วนข้อผิดพลาด
    อื่น (syntax ผิด, ตัวแปรไม่มี) **ต้องดัง** เพราะเป็นบั๊กของ plugin ไม่ใช่
    สถานะปกติ · ไม่ cache ผลของความล้มเหลวไว้ ไม่งั้นการติดตั้งไลบรารีเพิ่ม
    จะไม่มีผลจนกว่าจะ restart
    """
    try:
        return _module(plugin, contract)
    except ImportError:
        current_app.logger.info("ปัจจัยหลักปิดตัวเองเพราะไลบรารีไม่ครบ", extra={"plugin": plugin.key})
        return None


class Provider(NamedTuple):
    """ปัจจัยหลักหนึ่ง **profile** — plugin เดียวโผล่ได้หลายรายการตาม ADR 0047

    `profile=None` คือชุดค่าเดี่ยวไม่มี prefix (พฤติกรรมก่อนมี profile)
    `key` คือสิ่งที่อยู่ใน URL และ `DISABLED_PLUGINS` · `label` คือป้ายบนปุ่ม
    """

    plugin: plugins.Plugin
    profile: str | None
    key: str
    label: str


def _label(plugin: plugins.Plugin, module: Any, profile: str | None) -> str:
    """ป้ายปุ่มของ profile นี้ — ถาม plugin ก่อน (มันอ่านคีย์ `*_LABEL` ของตัวเองได้)

    core ตั้งค่าเริ่มต้นจาก manifest + ชื่อ profile เพราะหลาย profile ของ plugin
    เดียวจะได้ปุ่มชื่อซ้ำกันหมดถ้าใช้ชื่อจาก manifest ตรง ๆ (ADR 0047)
    """
    if hasattr(module, "label"):
        custom = module.label()
        if custom:
            return str(custom)
    name = str(plugin.manifest.get("name", plugin.id))
    return f"{name} ({profile})" if profile else name


def _configured(module: Any) -> bool:
    """profile นี้มี config ครบพอจะใช้จริงไหม — สัญญาเสริม ไม่มีฟังก์ชัน = ถือว่าครบ

    มีไว้ให้ปุ่มบนหน้า login โผล่เฉพาะ profile ที่ใช้งานได้จริง (ADR 0047 ปิด
    finding เดิมที่ปุ่ม SSO โชว์ทั้งที่ไม่มี config) — core ไม่รู้ว่าคีย์ไหน
    จำเป็น จึงต้องเป็นคำถามที่ plugin ตอบเอง
    """
    if not hasattr(module, "configured"):
        return True
    return bool(module.configured())


def _providers(style: str, contract: tuple[str, ...]) -> list[Provider]:
    """ทุก (plugin, profile) ที่ติดตั้งครบและใช้งานได้ ตามลำดับที่ประกาศ"""
    found: list[Provider] = []
    for plugin in plugins.primary_factors(style):
        if not plugins.is_installed(plugin):
            continue
        module = _usable(plugin, contract)
        if module is None:
            continue
        for entry in plugins.auth_profiles(plugin):
            with plugins.using_profile(entry.name):
                if not _configured(module):
                    current_app.logger.info(
                        "ข้าม auth profile ที่ config ยังไม่ครบ", extra={"provider": entry.key}
                    )
                    continue
                label = _label(plugin, module, entry.name)
                found.append(Provider(plugin, entry.name, entry.key, label))
    return found


def available() -> list[Provider]:
    """ปัจจัยหลักแบบ `redirect` ที่ **ติดตั้งครบแล้ว** ตอนนี้ (อ่านดิสก์ใหม่ทุกครั้ง)

    ตัวที่วางไดเรกทอรีไว้แต่ยังไม่ได้ `flask plugin-install` ถูกข้ามไป
    ด้วยเหตุผลเดียวกับปัจจัยที่สอง: ตารางที่ยังไม่ถูกสร้างแปลว่ายังไม่มีใคร
    ผูกบัญชีไว้เลย การข้ามจึงเป็นคำตอบที่ถูก ไม่ใช่การปิดด่านความปลอดภัย
    — และถ้าไม่ข้าม **หน้า login ทั้งหน้าจะพัง** ด้วย "no such table"
    """
    return _providers(plugins.REDIRECT_STYLE, CONTRACT)


def directories() -> list[Provider]:
    """ปัจจัยหลักแบบ `credential` ที่ติดตั้งแล้ว — ไม่มีปุ่มบนหน้า login

    ต่างจากแบบ `redirect` ตรงที่ผู้ใช้ไม่ต้องเลือกอะไร: กรอกชื่อกับรหัสผ่าน
    ในฟอร์มเดิม แล้วระบบเป็นคนไล่ถามให้เอง (ADR 0029 ข้อ 2)
    """
    return _providers(plugins.CREDENTIAL_STYLE, CREDENTIAL_CONTRACT)


def authenticate(username: str, password: str) -> Any:
    """ถาม directory ภายนอกทีละตัวว่ารู้จักคู่นี้ไหม — คืน `User` หรือ `None`

    **เรียกหลังรหัสผ่านของที่นี่ไม่ผ่านเท่านั้น** (ADR 0029 ข้อ 2) — วันที่
    directory ล่ม ผู้ดูแลที่มีรหัสผ่านของที่นี่ต้องยังเข้าได้

    ลำดับคือลำดับที่ประกาศใน `AUTH_PROFILES` และ fallback ข้าม profile เกิด
    เฉพาะกรณี "ติดต่อไม่ได้" (`UnreachableError`) — **คำตอบใด ๆ ที่ไม่ใช่
    "ตอบไม่ได้" เป็นที่สิ้นสุด** (ADR 0047): ทั้งการปฏิเสธ (คืน `None`) และ
    ความล้มเหลวอื่นหยุดการไล่ถามทันที ไม่งั้นคนไล่รหัสได้โควตาคูณด้วยจำนวน
    profile และบัญชีชื่อซ้ำสองวงจะ login ข้ามวงกันได้
    """
    for provider in directories():
        try:
            with plugins.using_profile(provider.profile):
                user = _module(provider.plugin, CREDENTIAL_CONTRACT).authenticate(
                    username, password
                )
        except UnreachableError as error:
            # ตอบไม่ได้ ≠ ตอบว่าไม่ใช่ — ลองแหล่งถัดไปได้ แต่**ต้องดังใน log**
            # เพราะจากมุมผู้ใช้มันเงียบสนิท (เห็นแค่ "รหัสผ่านไม่ถูกต้อง")
            current_app.logger.warning(
                "directory ภายนอกติดต่อไม่ได้ — ลองตัวถัดไป",
                extra={"provider": provider.key, "reason": error.code},
            )
            continue
        except ServiceError as error:
            current_app.logger.warning(
                "ถาม directory ภายนอกไม่สำเร็จ — หยุดการไล่ถาม (ADR 0047)",
                extra={"provider": provider.key, "reason": error.code},
            )
            return None
        # คำตอบของ directory เป็นที่สิ้นสุด — `None` คือ "ไม่ใช่" ไม่ใช่ "ถามต่อ"
        return user
    return None


def find(key: str) -> Provider:
    """หาปัจจัยหลักจากคีย์ที่มาจาก URL — ไม่เจอ = `ValidationError`

    **ต้องเทียบกับรายการที่ค้นเจอจริง** ไม่ใช่เอาคีย์ไปประกอบเป็น path
    (หลักเดียวกับ route ที่เสิร์ฟ CSS ของธีม) — คีย์รวมชื่อ profile แล้ว
    (`auth/oidc:corp`) profile ที่ถูกปิด/ไม่ได้ประกาศจึงตอบเหมือนไม่มีอยู่
    """
    for provider in available():
        if provider.key == key:
            return provider
    raise ValidationError(_("Unknown sign-in provider"), code="sso_unknown_provider")


def begin(provider: Provider, redirect_uri: str) -> tuple[str, dict[str, Any]]:
    """เริ่มการ login — คืน URL ที่จะส่ง browser ไป และของที่ต้องจำไว้รอ callback

    ของที่คืนมาก้อนที่สอง core **ไม่ตีความเลย** แค่เก็บใส่ session ไว้แล้วส่ง
    คืนให้ `finish()` ตอนผู้ใช้กลับมา (มันคือ state/nonce/PKCE ของ plugin ซึ่ง
    เป็นรายละเอียดของโพรโทคอลที่ core ไม่ควรรู้)
    """
    with plugins.using_profile(provider.profile):
        target, pending = _module(provider.plugin).begin(redirect_uri)
    return str(target), dict(pending)


def finish(provider: Provider, params: dict[str, str], pending: dict[str, Any]) -> Any:
    """ผู้ใช้กลับมาแล้ว — คืน `User` ของที่นี่ หรือ raise `ServiceError`

    **plugin เป็นคนหาว่าเป็นใคร** เพราะตารางที่ผูก `sub` กับผู้ใช้เป็นของ
    plugin เอง (ADR 0023) core แค่รับ `User` มาแล้วเดินด่านที่เหลือต่อ
    ซึ่งเป็นด่านเดียวกับทางรหัสผ่านเป๊ะ รวมทั้งปัจจัยที่สอง (ADR 0028 ข้อ 6)
    """
    with plugins.using_profile(provider.profile):
        return _module(provider.plugin).finish(params, pending)
