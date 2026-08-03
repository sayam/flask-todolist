"""การเลือกภาษาของแต่ละ request

ลำดับความสำคัญ (ตัวแรกที่เจอชนะ):
1. `?lang=` ใน URL — ใช้ตอนกดปุ่มสลับภาษา
2. ภาษาที่เก็บไว้ใน session (มาจากการกดสลับครั้งก่อน)
3. ภาษาที่บันทึกไว้ในโปรไฟล์ของ user ที่ login อยู่
4. Accept-Language ที่ browser ส่งมา
5. DEFAULT_LANGUAGE (en)

ข้อ 3 อยู่หลังข้อ 2 เพื่อให้การกดสลับภาษามีผลทันทีในเซสชันนั้น
โดยไม่ต้องไปแก้โปรไฟล์
"""

from flask import current_app, has_request_context, request, session
from flask_login import current_user

SESSION_KEY = "lang"


def supported_languages() -> dict[str, str]:
    """รหัสภาษา -> ชื่อที่แสดงในตัวเลือก (ประกาศไว้ใน config.LANGUAGES)"""
    languages: dict[str, str] = current_app.config["LANGUAGES"]
    return languages


def is_supported(code: str | None) -> bool:
    return bool(code) and code in supported_languages()


def select_locale() -> str:
    # นอก request (เช่นใน flask CLI) ไม่มีข้อมูลให้เดาภาษา ใช้ค่าเริ่มต้นไปเลย
    # ถ้าไม่กันไว้ การเรียก gettext จาก CLI จะพังที่ request.args
    if not has_request_context():
        return str(current_app.config["BABEL_DEFAULT_LOCALE"])

    if is_supported(request.args.get(SESSION_KEY)):
        return str(request.args[SESSION_KEY])

    if is_supported(session.get(SESSION_KEY)):
        return str(session[SESSION_KEY])

    # current_user เข้าถึงได้เฉพาะตอนมี request context ที่ผูก login manager แล้ว
    if current_user.is_authenticated and is_supported(current_user.locale):
        return str(current_user.locale)

    best = request.accept_languages.best_match(list(supported_languages()))
    return best or str(current_app.config["BABEL_DEFAULT_LOCALE"])
