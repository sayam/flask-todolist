import os

# คีย์ที่สั้นกว่านี้เดาได้เร็วเกินไป — session และ CSRF token เซ็นด้วยคีย์นี้ทั้งคู่
MIN_SECRET_KEY_LENGTH = 32


class Config:
    # ไม่มีค่า default โดยตั้งใจ — ไม่ตั้งแล้วต้องแอปพังตั้งแต่ตอน start
    # ดีกว่าเผลอรันด้วยคีย์ที่ใคร ๆ ก็รู้
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///todolist.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False


def check_secret_key(secret_key):
    """ตรวจ SECRET_KEY ตอนสร้างแอป ไม่ใช่ตอน import config
    (ถ้า raise ตอน import จะพังแม้แต่ config ที่ตั้งคีย์เองอย่างในเทสต์)"""
    if not secret_key:
        raise RuntimeError(
            "ยังไม่ได้ตั้ง SECRET_KEY — ใส่ลงไฟล์ .env ก่อน (ดูตัวอย่างใน .env.example)\n"
            "สร้างคีย์ใหม่: "
            "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )
    if len(secret_key) < MIN_SECRET_KEY_LENGTH:
        raise RuntimeError(
            f"SECRET_KEY สั้นเกินไป ({len(secret_key)} ตัว) "
            f"ต้องยาวอย่างน้อย {MIN_SECRET_KEY_LENGTH} ตัว"
        )
