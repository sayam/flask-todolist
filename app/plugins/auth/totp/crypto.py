"""encrypt/decrypt ความลับ TOTP ที่ระดับ field (ADR 0046) — ของ plugin นี้ล้วน ๆ

รูปเก็บ: ``enc:v1:<nonce b64>:<ciphertext b64>`` — เลขเวอร์ชันอยู่ในตัวค่า
จึงหมุนคีย์ได้ทีละแถวโดยไม่มี flag day · ค่าที่ไม่มี prefix คือของเดิมก่อน
เฟส 15 (plaintext) ซึ่ง**อ่านได้และถูกเขียนกลับแบบ encrypt ตอน verify สำเร็จ
ครั้งถัดไป** — ตารางของ plugin อยู่นอกสาย migration ของ core โดยออกแบบ
(ADR 0023) การย้ายข้อมูลจึงเป็น encrypt-on-use ไม่ใช่ alembic

คีย์คือ ``DATA_ENCRYPTION_KEY`` (base64 ของ 32 ไบต์) — อ่านจาก config ซึ่ง
ถูกเติมจาก secrets source ตาม ADR 0030 · **ไม่ derive จาก SECRET_KEY**
(SECRET_KEY หมุนแล้ว session หลุดคือเรื่องปกติ แต่คีย์ข้อมูลหมุนผิดคือ
ข้อมูลถอดไม่ได้ถาวร — สองอย่างนี้ต้องหมุนแยกกันได้)

`cryptography` อยู่ใน category ของ plugin นี้ (ADR 0025) — import แบบ lazy
เพื่อให้ `models.py` โหลดได้เสมอแม้ในเครื่องที่ไม่ติดตั้ง (job `bare`)
"""

from __future__ import annotations

import base64
import binascii

PREFIX = "enc:v1:"
_KEY_BYTES = 32
_NONCE_BYTES = 12


class EncryptionUnavailableError(RuntimeError):
    """ไลบรารีหรือคีย์ไม่พร้อม — ข้อความต้องบอกทางแก้ ไม่ใช่แค่บอกว่าพัง"""


class DecryptionFailedError(RuntimeError):
    """ciphertext ถอดไม่ได้ (คีย์ผิด/ข้อมูลถูกแก้) — ห้ามคืนขยะเงียบ ๆ เด็ดขาด"""


def _aesgcm():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as error:  # pragma: no cover - เดินจริงเฉพาะเครื่องที่ไม่มีไลบรารี
        raise EncryptionUnavailableError(
            "ไม่มีไลบรารี cryptography — ติดตั้ง category ของ plugin นี้ด้วย "
            'pipenv sync --categories="$(pipenv run flask plugin-deps --categories)"'
        ) from error
    return AESGCM


def load_key() -> bytes:
    """คีย์จาก config (ถูกเติมจาก secrets source แล้ว) — ผิดรูป/ไม่มี = ดังพร้อมทางแก้"""
    from flask import current_app

    raw = str(current_app.config.get("DATA_ENCRYPTION_KEY") or "")
    if not raw:
        raise EncryptionUnavailableError(
            "ไม่มี DATA_ENCRYPTION_KEY — สร้างด้วย "
            'python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())" '
            "แล้วตั้งผ่าน environment หรือ secrets source (ADR 0046)"
        )
    try:
        key = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as error:
        raise EncryptionUnavailableError("DATA_ENCRYPTION_KEY ไม่ใช่ base64 ที่ถูกต้อง") from error
    if len(key) != _KEY_BYTES:
        raise EncryptionUnavailableError(
            f"DATA_ENCRYPTION_KEY ต้องเป็น 32 ไบต์ (ได้ {len(key)}) — สร้างใหม่ตามคำสั่งใน ADR 0046"
        )
    return key


def is_encrypted(value: str | None) -> bool:
    """ค่านี้อยู่ในรูป encrypt แล้วหรือยัง — ตัวแยก legacy ออกจากของใหม่"""
    return bool(value) and str(value).startswith(PREFIX)


def encrypt(plaintext: str) -> str:
    """encrypt หนึ่งค่า — nonce สุ่มใหม่ทุกครั้ง (GCM ห้ามซ้ำ nonce ต่อคีย์)"""
    import os

    aesgcm = _aesgcm()(load_key())
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return (
        PREFIX
        + base64.b64encode(nonce).decode("ascii")
        + ":"
        + base64.b64encode(ciphertext).decode("ascii")
    )


def decrypt(stored: str) -> str:
    """ถอดค่าที่เก็บไว้ — คีย์ผิด/ข้อมูลถูกแก้ = `DecryptionFailedError` ที่บอกสาเหตุ"""
    if not is_encrypted(stored):
        # legacy plaintext จากก่อนเฟส 15 — อ่านตรง ๆ แล้วรอ encrypt-on-use
        return stored
    try:
        nonce_b64, ct_b64 = stored[len(PREFIX) :].split(":", 1)
        nonce = base64.b64decode(nonce_b64, validate=True)
        ciphertext = base64.b64decode(ct_b64, validate=True)
    except (ValueError, binascii.Error) as error:
        raise DecryptionFailedError("รูปแบบ ciphertext ไม่ถูกต้อง — ข้อมูลถูกแก้นอกระบบ?") from error
    # โหลดคีย์/ไลบรารี *นอก* try ข้างล่าง — "คีย์หาย" ต้องดังเป็น
    # EncryptionUnavailableError พร้อมทางแก้ของมันเอง ไม่ใช่ถูกห่อเป็น
    # "คีย์ผิด" (เจอตอนเขียนเทสต์: ข้อความบอกทางแก้ผิดเรื่องทั้งบรรทัด)
    aesgcm = _aesgcm()(load_key())
    try:
        return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
    except Exception as error:  # InvalidTag ของ cryptography — import แบบ lazy จึงจับกว้าง
        raise DecryptionFailedError(
            "ถอดความลับไม่ได้ — DATA_ENCRYPTION_KEY ไม่ใช่คีย์ที่ใช้ตอน encrypt "
            "(คีย์ถูกหมุนโดยไม่ re-encrypt?) หรือข้อมูลถูกแก้"
        ) from error
