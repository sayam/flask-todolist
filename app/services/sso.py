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

from typing import Any

from flask_babel import gettext as _

from app import plugins
from app.services.errors import ValidationError

# ฟังก์ชันที่ปัจจัยหลักต้องมีครบ — **host เป็นคนตรวจ ไม่ใช่ registry**
# (registry ไม่รู้ว่าความสามารถแต่ละอย่างต้องมีอะไร — ADR 0025)
CONTRACT = ("begin", "finish")


def _module(plugin: plugins.Plugin) -> Any:
    module = plugins.factor_module(plugin)
    missing = [name for name in CONTRACT if not hasattr(module, name)]
    if missing:
        # บอกว่า *ใคร* ผิดสัญญา *ข้อไหน* — ข้อความที่บอกแค่ "plugin พัง"
        # ทำให้คนเขียน plugin ต้องเดาว่าตกอะไร
        raise plugins.PluginError(f"{plugin.key}: ปัจจัยหลักต้องมี {', '.join(missing)}")
    return module


def available() -> list[plugins.Plugin]:
    """ปัจจัยหลักทางเลือกที่ **ติดตั้งครบแล้ว** ตอนนี้ (อ่านดิสก์ใหม่ทุกครั้ง)

    ตัวที่วางไดเรกทอรีไว้แต่ยังไม่ได้ `flask plugin-install` ถูกข้ามไป
    ด้วยเหตุผลเดียวกับปัจจัยที่สอง: ตารางที่ยังไม่ถูกสร้างแปลว่ายังไม่มีใคร
    ผูกบัญชีไว้เลย การข้ามจึงเป็นคำตอบที่ถูก ไม่ใช่การปิดด่านความปลอดภัย
    — และถ้าไม่ข้าม **หน้า login ทั้งหน้าจะพัง** ด้วย "no such table"
    """
    return [plugin for plugin in plugins.primary_factors() if plugins.is_installed(plugin)]


def find(key: str) -> plugins.Plugin:
    """หาปัจจัยหลักจากคีย์ที่มาจาก URL — ไม่เจอ = `ValidationError`

    **ต้องเทียบกับรายการที่ค้นเจอจริง** ไม่ใช่เอาคีย์ไปประกอบเป็น path
    (หลักเดียวกับ route ที่เสิร์ฟ CSS ของธีม)
    """
    for plugin in available():
        if plugin.key == key:
            return plugin
    raise ValidationError(_("Unknown sign-in provider"), code="sso_unknown_provider")


def begin(plugin: plugins.Plugin, redirect_uri: str) -> tuple[str, dict[str, Any]]:
    """เริ่มการ login — คืน URL ที่จะส่ง browser ไป และของที่ต้องจำไว้รอ callback

    ของที่คืนมาก้อนที่สอง core **ไม่ตีความเลย** แค่เก็บใส่ session ไว้แล้วส่ง
    คืนให้ `finish()` ตอนผู้ใช้กลับมา (มันคือ state/nonce/PKCE ของ plugin ซึ่ง
    เป็นรายละเอียดของโพรโทคอลที่ core ไม่ควรรู้)
    """
    target, pending = _module(plugin).begin(redirect_uri)
    return str(target), dict(pending)


def finish(plugin: plugins.Plugin, params: dict[str, str], pending: dict[str, Any]) -> Any:
    """ผู้ใช้กลับมาแล้ว — คืน `User` ของที่นี่ หรือ raise `ServiceError`

    **plugin เป็นคนหาว่าเป็นใคร** เพราะตารางที่ผูก `sub` กับผู้ใช้เป็นของ
    plugin เอง (ADR 0023) core แค่รับ `User` มาแล้วเดินด่านที่เหลือต่อ
    ซึ่งเป็นด่านเดียวกับทางรหัสผ่านเป๊ะ รวมทั้งปัจจัยที่สอง (ADR 0028 ข้อ 6)
    """
    return _module(plugin).finish(params, pending)
