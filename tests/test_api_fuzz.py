"""ยิงคำขอที่ "ถูกตามสัญญา" ใส่ API ทุก endpoint แล้วดูว่ามันแตกไหม (Phase 3)

เทสต์ที่คนเขียนเองครอบเฉพาะกรณีที่คนเขียน**นึกออก** ตัวนี้ให้ schemathesis
สร้างคำขอจาก `openapi.json` เอง แล้วตรวจว่าคำตอบตรงกับที่สัญญาประกาศไว้จริง
(status code ที่ไม่ได้ประกาศ, content-type ที่ไม่ตรง, 500, schema ของ response
ไม่ตรงกับที่บอก, header ที่ RFC บังคับแล้วไม่มี)

**ของจริงที่จับได้ตอนเปิดใช้ครั้งแรก** — ทั้งสามอย่างกระทบหน้าเว็บด้วย ไม่ใช่แค่ API:

1. `?date_from=มั่ว` ทำให้ `ValueError` หลุดออกจาก view → 500 (ตอนนี้เป็น 400)
2. id ที่ใหญ่กว่า 64 บิต (`/todos/99999999999999999999`) ทำให้ไดรเวอร์ DB โยน
   `OverflowError` → 500 (ตอนนี้เป็น 404 — ดู `app/services/lookup.py`)
3. คำขอที่ตกตั้งแต่ชั้น routing (path ผิด, method ไม่รองรับ) ได้ HTML กลับไป
   และ 405 ไม่มี header `Allow` ที่ RFC 9110 บังคับ

เป็นเทสต์ที่ **ไม่ deterministic โดยธรรมชาติ** (hypothesis สุ่ม input) จึงตั้ง
`max_examples` ไว้เตี้ย ๆ ให้เร็วพอจะรันทุกครั้ง — งานหนักกว่านี้เป็นของ nightly
"""

import pytest
import schemathesis
from hypothesis import HealthCheck, settings
from schemathesis.core.failures import AcceptedNegativeData, FailureGroup
from schemathesis.generation import GenerationMode
from schemathesis.specs.openapi import checks as openapi_checks

from app import create_app, db
from app.models import User
from app.services import tokens as tokens_service
from tests.conftest import PASSWORD, TestConfig


class FuzzConfig(TestConfig):
    """**ตรึงเป็น SQLite ในหน่วยความจำเสมอ แม้ `TEST_DATABASE_URL` จะชี้ยี่ห้ออื่น**

    แอปของไฟล์นี้มีชีวิตข้ามเทสต์ทั้งไฟล์ (schemathesis ต้องอ่าน schema ตอน
    import ไม่ใช่ตอนรัน) จึงใช้ฐานร่วมกับ fixture ที่ลบตารางทิ้งท้ายเทสต์ไม่ได้ —
    teardown ของเทสต์ตัวอื่นจะลบตารางที่แอปตัวนี้ยังใช้อยู่กลางคัน

    **ไม่เสียความครอบคลุมของ CI matrix** เพราะชุดนี้ตรวจว่า *คำตอบตรงกับ spec ไหม*
    ซึ่งไม่ขึ้นกับยี่ห้อฐานข้อมูล (ของที่มันเคยจับได้คือตัวกรองวันที่ที่ย่อยไม่ได้,
    id เกิน 64 บิต, คำขอที่ตกตั้งแต่ชั้น routing — ทั้งหมดเป็นเรื่องของชั้น HTTP)
    """

    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


# แอปตัวเดียวใช้ทั้งไฟล์ — schemathesis ต้องอ่าน schema ตอน import ไม่ใช่ตอนรัน
_app = create_app(FuzzConfig)
with _app.app_context():
    db.create_all()
    _user = User(username="fuzz", timezone_name="Asia/Bangkok")
    _user.set_password(PASSWORD)
    db.session.add(_user)
    db.session.commit()
    TOKEN = tokens_service.issue(_user, "fuzz")

schema = schemathesis.openapi.from_wsgi("/api/v1/openapi.json", _app)


def _negative_payload_survives_the_wire(case) -> bool:
    """negative ที่อยู่ *นอก* body ไม่รอดการ serialize — ตัดสินจากของที่ถูกส่งจริง

    query string กับ header เป็นสตริงโดยนิยามของ HTTP: ค่าที่ "ผิดชนิด" อย่าง
    `[None]` หรือ property ส่วนเกินที่ชื่อมีอักขระควบคุม จะ**ระเหยหายตอน
    serialize** — สิ่งที่ถึงแอปคือ request ที่ถูก spec ทุกประการ แอปตอบ 200
    อย่างถูกต้อง แต่ `negative_data_rejection` ตัดสินจากข้อมูล*ก่อน* serialize
    จึงกล่าวหาว่าแอป "รับของผิด schema" ทั้งที่ของผิดนั้นไม่เคยถูกส่งไป
    (เจอจริง: `?date_from=` บน CI · reproduce แล้วเห็น query ที่ generate เป็น
    `{'\\n-v·òLØF': [None], ...}` แต่บนสายเหลือแค่พารามิเตอร์ปกติ)

    ส่วน **body เป็น JSON ซึ่งรักษาชนิดข้ามสายได้จริง** — negative ของ body
    ต้องไม่ถูกกรองทิ้งเด็ดขาด · และฝั่ง query ที่*แทนค่าได้จริง* (ชื่อพารามิเตอร์
    แปลกปลอมแบบปกติ) มีเทสต์ deterministic คุมอยู่แล้ว:
    `tests/test_api_todos.py::test_an_unknown_query_parameter_is_refused`
    """
    components = case.meta.components if case.meta else {}
    return any(
        location.value == "body" and info.mode is GenerationMode.NEGATIVE
        for location, info in components.items()
    )


@schema.parametrize()
@settings(max_examples=15, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_the_api_answers_the_way_the_spec_promises(case):
    """ทุก operation ต้องตอบตามสัญญา และห้ามมี 500 ไม่ว่าจะยิงอะไรเข้าไป

    ปิด `positive_data_acceptance` ไว้ตัวเดียว: มันถือว่า "ข้อมูลที่ถูกตาม
    schema ต้องไม่ถูกปฏิเสธ" ซึ่งชนกับดีไซน์ของเราโดยตรง — schema คุมแค่
    **รูปแบบ** (`name` เป็นสตริง) ส่วนกติกา **ความหมาย** ("ห้ามว่าง") อยู่ที่
    service ชั้นเดียวตาม ADR 0016 ชื่อว่าง ๆ จึงถูกตอบ 400 อย่างตั้งใจ และ
    สัญญาก็ประกาศ 400 ไว้ในทุก operation ที่เป็นแบบนี้แล้ว

    `AcceptedNegativeData` ถูกกรองเฉพาะเคสที่ negative อยู่นอก body —
    ดูเหตุผลเต็มที่ `_negative_payload_survives_the_wire`
    """
    response = case.call(headers={"Authorization": f"Bearer {TOKEN}"})
    try:
        case.validate_response(
            response,
            excluded_checks=[openapi_checks.positive_data_acceptance],
            # check ฝั่ง auth ต้องรู้ว่าเรา override Authorization ด้วย token จริง
            # ไม่งั้นมันเห็น "auth ที่ generate มามั่ว ๆ ได้ 200" แล้วฟ้อง IgnoredAuth
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
    except FailureGroup as group:
        real = [
            failure
            for failure in group.exceptions
            if not isinstance(failure, AcceptedNegativeData)
            or _negative_payload_survives_the_wire(case)
        ]
        if real:
            raise
