"""เขียน `docs/openapi.json` ใหม่จากโค้ดจริง (Phase 3 — ดู ADR 0018)

ไฟล์ที่ commit ไว้เป็น **ภาพถ่าย**ของสัญญาที่โค้ดประกาศ ไม่ใช่ต้นฉบับ
ต้นฉบับคือ schema กับ view ใน `app/api/` — แก้ที่นั่นแล้วรันตัวนี้เพื่อ
ให้ภาพถ่ายตรงกับของจริง

    pipenv run python scripts/generate_openapi.py

`tests/test_openapi.py` และ job `openapi` ใน CI เทียบสองอย่างนี้ทุกครั้ง
ลืมรันแล้วจะแดง ไม่ใช่ปล่อยให้เอกสารค้างอยู่คนละเวอร์ชันกับ API เงียบ ๆ

ไม่ต้องมีฐานข้อมูล ไม่ต้องมี .env จริง — spec มาจากการประกาศของโค้ดล้วน ๆ
จึงตั้ง SECRET_KEY ปลอมให้ `create_app()` ผ่านไปได้

บทบาท: generator — สร้างไฟล์ที่ commit ไว้ — หลักฐานคือผลลัพธ์ต้องตรงกับที่ commit (coverage ไม่ใช่ตัววัดของชนิดนี้)
"""

import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "docs" / "openapi.json"

# `create_app()` ปฏิเสธที่จะ start ถ้าไม่มี SECRET_KEY ที่ยาวพอ ตัวนี้ใช้แค่ตอน
# generate เอกสาร ไม่ได้เซ็นอะไรที่ออกไปนอกเครื่อง
DUMMY_SECRET = "openapi-generator-only-not-a-real-secret-key"  # noqa: S105


def build_spec() -> dict:
    """spec ที่แอปประกาศ ณ ตอนนี้"""
    from app import create_app
    from app.api import spec_dict
    from config import Config

    class SpecConfig(Config):
        SECRET_KEY = DUMMY_SECRET
        # ไม่แตะฐานข้อมูลเลย แต่ตัว config ต้องมีค่า — ชี้ไปหน่วยความจำไว้ก่อน
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

    return spec_dict(create_app(SpecConfig))


def render(spec: dict) -> str:
    """JSON ที่เขียนลงไฟล์ — เรียงคีย์และจบด้วยบรรทัดใหม่ให้ diff อ่านง่าย

    `ensure_ascii=False` เพราะคำอธิบายเป็นภาษาไทย การหนีเป็น `\\uXXXX`
    ทำให้ diff อ่านไม่ออกและไฟล์ใหญ่ขึ้นสามเท่าโดยไม่ได้อะไรกลับมา
    """
    return json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    sys.path.insert(0, str(REPO_ROOT))
    SPEC_PATH.write_text(render(build_spec()), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
