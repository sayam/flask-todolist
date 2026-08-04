"""ปัจจัยที่สองของการยืนยันตัวตน — **core ไม่รู้จักชื่อ plugin ตัวไหนเลย**

ไฟล์นี้คือทั้งหมดที่ core รู้เรื่อง MFA: ถามทุก plugin ชนิด `auth` ที่ประกาศ
ตัวเองเป็น `"factor": "second"` ว่า "คนนี้เปิดใช้คุณอยู่ไหม" และ "รหัสนี้ผ่านไหม"

ผลที่ตามมาที่ตั้งใจ: **ถอนไดเรกทอรีของ plugin ทิ้ง ระบบกลับไปเป็น login ด้วย
รหัสผ่านอย่างเดียวทันที** ไม่มีโค้ดของ core ตรงไหนที่พังเพราะหา plugin ตัวนั้นไม่เจอ
(สัญญาข้อเดียวกับธีมตั้งแต่ ADR 0006 — ดู ADR 0024)
"""

from typing import Any

from flask_babel import gettext as _

from app import plugins
from app.services.errors import ConflictError

# ฟังก์ชันที่ปัจจัยต้องมีครบถ้าอยากให้ผู้ใช้เปิด/ปิดเองได้จากหน้าเว็บ
# (ไม่มีก็ยังใช้เป็นปัจจัยที่สองได้ แต่ต้องไปเปิดด้วยวิธีอื่น เช่นทาง CLI ของ plugin เอง)
ENROLLMENT_CONTRACT = ("start_enrollment", "setup_details", "confirm", "disable", "is_pending")


def available() -> list[plugins.Plugin]:
    """ปัจจัยที่สองที่ติดตั้งอยู่ตอนนี้ (อ่านดิสก์ใหม่ทุกครั้ง)"""
    return plugins.second_factors()


def enrolled(user: Any) -> list[plugins.Plugin]:
    """ปัจจัยที่ผู้ใช้คนนี้เปิดใช้อยู่จริง"""
    return [plugin for plugin in available() if plugins.factor_module(plugin).is_enrolled(user)]


def is_required(user: Any) -> bool:
    """login ของคนนี้ต้องผ่านขั้นที่สองไหม"""
    return bool(enrolled(user))


def verify(user: Any, code: str) -> bool:
    """รหัสนี้ผ่านปัจจัยตัวใดตัวหนึ่งที่เขาเปิดใช้อยู่ไหม

    **ไม่ break ทันทีที่เจอตัวที่ผ่าน** เพื่อให้ทุกปัจจัยได้บันทึกว่ารหัสถูกใช้ไป
    แล้ว (ปัจจัยที่อิงเวลากันการใช้ซ้ำด้วยการจำช่วงเวลาล่าสุด) และเพื่อให้เวลาที่ใช้
    ไม่ขึ้นกับว่าผ่านที่ตัวไหน
    """
    if not code:
        return False
    results = [plugins.factor_module(plugin).verify(user, code) for plugin in enrolled(user)]
    return any(results)


# ---------------------------------------------------------------- เปิด/ปิดเองจากหน้าเว็บ


def supports_enrollment(plugin: plugins.Plugin) -> bool:
    """ปัจจัยตัวนี้ให้ผู้ใช้เปิด/ปิดเองจากหน้าเว็บได้ไหม"""
    module = plugins.factor_module(plugin)
    return all(callable(getattr(module, name, None)) for name in ENROLLMENT_CONTRACT)


def _module(key: str) -> tuple[plugins.Plugin, Any]:
    """หา plugin จากคีย์ที่ฟอร์มส่งมา — **ต้องเทียบกับรายการที่ค้นเจอจริงเสมอ**

    (หลักเดียวกับ route ที่เสิร์ฟ stylesheet ของธีม: ค่าที่มาจากภายนอกไม่เคย
    ถูกเอาไปประกอบเป็น path หรือชื่อโมดูลตรง ๆ)
    """
    for plugin in available():
        if plugin.key == key:
            return plugin, plugins.factor_module(plugin)
    raise LookupError(key)


def state(user: Any) -> list[dict[str, Any]]:
    """สถานะของทุกปัจจัยสำหรับหน้า settings — core ไม่ต้องรู้ว่าแต่ละตัวคืออะไร

    `details` เป็นคู่ (ป้าย, ค่า) ที่ plugin ส่งมาเอง **ไม่ผ่าน gettext**
    เหมือน `Plugin.name` — plugin ที่อยากแปลต้องมี lang pack ของตัวเอง
    """
    rows = []
    for plugin in available():
        if not supports_enrollment(plugin):
            continue
        module = plugins.factor_module(plugin)
        pending = module.is_pending(user)
        rows.append(
            {
                "key": plugin.key,
                "name": plugin.name,
                "enrolled": module.is_enrolled(user),
                "pending": pending,
                "details": module.setup_details(user) if pending else [],
            }
        )
    return rows


def start(user: Any, key: str) -> None:
    """เริ่มลงทะเบียนปัจจัยตัวนั้น (ยังไม่เปิดใช้จนกว่าจะยืนยัน)

    `ValueError` จาก plugin ถูกแปลงเป็น `ConflictError` ของ core เพราะ core
    ไม่ควรมีคำศัพท์ความผิดพลาดสองชุด (ของตัวเองกับของ plugin) — plugin บอกได้
    แค่ว่า "ทำตอนนี้ไม่ได้" ส่วนถ้อยคำที่ผู้ใช้เห็นเป็นของ core ที่แปลได้
    """
    _plugin, module = _module(key)
    try:
        module.start_enrollment(user)
    except ValueError as refused:
        raise ConflictError(
            _("Turn off two-step verification first"), code="mfa_already_enrolled"
        ) from refused


def confirm(user: Any, key: str, code: str) -> bool:
    """ยืนยันการลงทะเบียนด้วยรหัสจริงหนึ่งครั้ง"""
    _plugin, module = _module(key)
    return bool(module.confirm(user, code))


def disable(user: Any, key: str) -> bool:
    """ปิดปัจจัยตัวนั้น — ผู้เรียกต้องยืนยันรหัสผ่านมาก่อนแล้ว (ดู app/routes.py)"""
    _plugin, module = _module(key)
    return bool(module.disable(user))
