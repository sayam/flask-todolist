"""ความลับ TOTP ต้องเป็น ciphertext บนดิสก์ (ADR 0046) — สองทิศ ทุกกิ่ง

- แถวใหม่: ดิสก์ต้องไม่มี base32 ดิบ (อ่านด้วย raw SQL พิสูจน์)
- แถว legacy (plaintext ก่อนเฟส 15): ยัง verify ได้ และถูกยกเป็น ciphertext
  ตอน verify สำเร็จ (encrypt-on-use — ตารางของ plugin ไม่มีสาย alembic)
- คีย์หาย = ดังพร้อมทางแก้ · คีย์ผิด = DecryptionFailedError ไม่ใช่ขยะเงียบ ๆ
"""

import base64

import pytest
from sqlalchemy import text

from app import db, plugins
from app.models import User

# crypto import ชื่อจริงได้ปลอดภัย (ไม่มี model — กับดักตารางซ้ำไม่เกิด) และ**ต้อง**
# ใช้ชื่อเดียวกับที่ models.py ใช้ ไม่งั้น exception class เป็นคนละตัวกับที่ถูก raise
# (โมดูลเดียวโหลดสองชื่อ = สองสำเนา — เจอจริงตอนเขียนไฟล์นี้)
from app.plugins.auth.totp import crypto
from tests.conftest import PASSWORD

pytestmark = pytest.mark.plugin_deps  # ใช้ cryptography ซึ่งอยู่ใน category ของ plugin

TOTP_KEY = "auth/totp"


def _totp():
    """โมดูล factor ผ่าน registry — absolute import จะนิยามตารางซ้ำ (กับดักใน CLAUDE.md)"""
    plugin = next(p for p in plugins.installed_on_disk() if p.key == TOTP_KEY)
    return plugins.factor_module(plugin)


def _enrolled_user(app):
    with app.app_context():
        user = User(username="somchai")
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
        secret = _totp().start_enrollment(user)
        code = _totp().code_at(secret, _totp()._counter(1_000_000.0))
        assert _totp().confirm(user, code, at=1_000_000.0)
        return user.id, secret


def _raw_stored(app, user_id):
    with app.app_context():
        return db.session.execute(
            text("SELECT totp_secret FROM tdl_auth_totp_secret WHERE user_id = :uid"),
            {"uid": user_id},
        ).scalar()


def test_a_new_secret_lands_on_disk_as_ciphertext(app):
    """ใจของ at rest: dump ฐานข้อมูลใบเดียวต้องไม่ได้ความลับไป"""
    user_id, secret = _enrolled_user(app)
    stored = _raw_stored(app, user_id)
    assert stored.startswith(crypto.PREFIX), f"บนดิสก์ไม่ใช่ ciphertext: {stored[:20]}"
    assert secret not in stored, "base32 ดิบโผล่อยู่ในค่าที่เก็บ"


def test_the_model_reads_back_the_original_secret(app):
    user_id, secret = _enrolled_user(app)
    with app.app_context():
        stored = _totp().secret_of(db.session.get(User, user_id))
        assert stored == secret, "decrypt แล้วต้องได้ค่าเดิมเป๊ะ"


def test_a_legacy_plaintext_row_still_verifies_then_gets_encrypted(app):
    """ของเดิมก่อนเฟส 15 ต้องไม่ถูก lock ออก — และถูกยกเป็น ciphertext ตอนใช้"""
    user_id, secret = _enrolled_user(app)
    with app.app_context():
        # จำลองแถวยุคก่อน encrypt: เขียน plaintext ทับตรง ๆ ที่ชั้นดิสก์
        db.session.execute(
            text("UPDATE tdl_auth_totp_secret SET totp_secret = :s WHERE user_id = :uid"),
            {"s": secret, "uid": user_id},
        )
        db.session.commit()
        db.session.expunge_all()
    assert not crypto.is_encrypted(_raw_stored(app, user_id))

    with app.app_context():
        user = db.session.get(User, user_id)
        code = _totp().code_at(secret, _totp()._counter(2_000_000.0))
        assert _totp().verify(user, code, at=2_000_000.0), "แถว legacy ต้องยัง verify ได้"

    stored = _raw_stored(app, user_id)
    assert crypto.is_encrypted(stored), "verify สำเร็จแล้วแถว legacy ต้องถูก encrypt"


def test_missing_key_shouts_with_instructions(app):
    user_id, _ = _enrolled_user(app)
    with app.app_context():
        app.config["DATA_ENCRYPTION_KEY"] = ""
        with pytest.raises(crypto.EncryptionUnavailableError) as caught:
            _totp().secret_of(db.session.get(User, user_id))
        assert "DATA_ENCRYPTION_KEY" in str(caught.value), "ข้อความต้องบอกทางแก้"


def test_the_wrong_key_fails_loud_not_garbage(app):
    user_id, _ = _enrolled_user(app)
    other = base64.b64encode(b"B" * 32).decode()
    with app.app_context():
        app.config["DATA_ENCRYPTION_KEY"] = other
        with pytest.raises(crypto.DecryptionFailedError):
            _totp().secret_of(db.session.get(User, user_id))


def test_a_key_that_is_not_base64_or_wrong_length_names_the_problem(app):
    """คีย์ผิดรูปสองแบบ ("ไม่ใช่ base64" กับ "ความยาวผิด") ต้องได้ข้อความ
    คนละเรื่องกัน — ข้อความที่บอกผิดสาเหตุพาคนไปแก้ผิดที่"""
    user_id, _ = _enrolled_user(app)
    with app.app_context():
        user = db.session.get(User, user_id)

        app.config["DATA_ENCRYPTION_KEY"] = "ไม่ใช่ base64 แน่ ๆ"
        with pytest.raises(crypto.EncryptionUnavailableError) as caught:
            _totp().secret_of(user)
        assert "base64" in str(caught.value)

        app.config["DATA_ENCRYPTION_KEY"] = base64.b64encode(b"short").decode()
        with pytest.raises(crypto.EncryptionUnavailableError) as caught:
            _totp().secret_of(user)
        assert "32 ไบต์" in str(caught.value)


def test_a_mangled_ciphertext_is_reported_as_tampering(app):
    """ค่า `enc:v1:` ที่ข้างในไม่ใช่ base64 = ข้อมูลถูกแก้นอกระบบ — ต้องดัง
    เป็น DecryptionFailedError ก่อนถึงชั้น AES ไม่ใช่ ValueError ดิบ"""
    user_id, _ = _enrolled_user(app)
    with app.app_context():
        db.session.execute(
            text("UPDATE tdl_auth_totp_secret SET totp_secret = :s WHERE user_id = :uid"),
            {"s": crypto.PREFIX + "@@@:@@@", "uid": user_id},
        )
        db.session.commit()
        db.session.expunge_all()
        with pytest.raises(crypto.DecryptionFailedError) as caught:
            _totp().secret_of(db.session.get(User, user_id))
        assert "รูปแบบ" in str(caught.value)


def test_verifying_an_already_encrypted_row_does_not_rewrite_it(app):
    """encrypt-on-use ต้องหยุดเมื่อของบนดิสก์ encrypt แล้ว — ไม่งั้นทุก login
    ที่มี MFA จะเขียนแถว (และแถว audit) ทิ้งเปล่า ๆ หนึ่งใบเสมอ"""
    user_id, secret = _enrolled_user(app)
    before = _raw_stored(app, user_id)
    assert crypto.is_encrypted(before)
    with app.app_context():
        user = db.session.get(User, user_id)
        code = _totp().code_at(secret, _totp()._counter(3_000_000.0))
        assert _totp().verify(user, code, at=3_000_000.0)
    assert _raw_stored(app, user_id) == before, (
        "แถวที่ encrypt แล้วถูกเขียนซ้ำตอน verify — nonce ใหม่ทุกครั้งแปลว่า"
        "ค่าต้องเปลี่ยนถ้ามีการเขียน จับได้จากการเทียบตรงนี้"
    )


def test_a_null_secret_passes_through_the_column_type_untouched(app):
    """กิ่ง None ของ TypeDecorator ทั้งสองทิศ — คอลัมน์ nullable ที่ค่า None
    ถูกส่งเข้า encrypt จะระเบิดด้วย AttributeError แทนที่จะเก็บ NULL เฉย ๆ"""
    with app.app_context():
        # เอา instance จริงจาก metadata — import models แบบ absolute ตรงนี้จะ
        # นิยามตารางซ้ำกับที่ registry โหลดไว้ใต้ชื่อสังเคราะห์ (กับดักใน CLAUDE.md)
        column_type = db.metadata.tables["tdl_auth_totp_secret"].c.totp_secret.type
        assert column_type.process_bind_param(None, None) is None
        assert column_type.process_result_value(None, None) is None
