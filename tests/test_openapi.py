"""สัญญาของ API ต้องตรงกับโค้ดเสมอ (Phase 3 — ดู ADR 0018)

`docs/openapi.json` ที่ commit ไว้เป็นภาพถ่ายของสิ่งที่โค้ดประกาศ ไฟล์นี้คือ
ตัวที่ทำให้ภาพถ่ายกับของจริงไม่มีทางเพี้ยนกันเงียบ ๆ — เอกสาร API ที่ไม่มี
อะไรบังคับให้ตรงจะล้าสมัยภายในไม่กี่สัปดาห์เสมอ และคนที่รู้ก่อนคือ client
ที่พังไปแล้ว

นอกจากเทียบว่าตรงกัน ยังตรวจ **คุณสมบัติที่สัญญาต้องมี** ด้วย (ทุก path
ขึ้นต้น `/api/v1`, ทุก operation อธิบายตัวเองได้, ประกาศ security ไว้จริง)
เพราะไฟล์ที่ตรงกับโค้ดเป๊ะแต่โค้ดเองประกาศไม่ครบก็ยังเป็นสัญญาที่ใช้ไม่ได้
"""

import json
import pathlib
import subprocess
import sys

import pytest

from app.api import BEARER_SCHEME, spec_dict
from app.api.base import API_PREFIX

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC_PATH = REPO_ROOT / "docs" / "openapi.json"
GENERATOR = REPO_ROOT / "scripts" / "generate_openapi.py"

REGENERATE = f"รันใหม่ด้วย: pipenv run python {GENERATOR.relative_to(REPO_ROOT)}"

# path item มีคีย์ที่ไม่ใช่ operation ปนอยู่ด้วย (`parameters` เป็น list ของ
# path parameter) — ไล่เฉพาะ method จริง ไม่งั้นจะไปอ่าน list เป็น dict
HTTP_METHODS = ("get", "post", "put", "patch", "delete")


def _operations(spec):
    """คู่ (path, method, operation) ของทุก endpoint ใน spec"""
    for path, item in spec["paths"].items():
        for method in HTTP_METHODS:
            if method in item:
                yield path, method, item[method]


@pytest.fixture(scope="module")
def committed():
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.fixture
def live(app):
    return spec_dict(app)


def test_the_committed_spec_matches_the_code(committed, live):
    """ข้อเดียวที่สำคัญที่สุดของไฟล์นี้"""
    assert committed == live, f"docs/openapi.json ไม่ตรงกับสิ่งที่โค้ดประกาศ — {REGENERATE}"


def test_the_generator_writes_exactly_what_is_committed():
    """รันสคริปต์จริงแล้วต้องได้ไฟล์เดิมเป๊ะ (รวมการจัดรูปแบบ ไม่ใช่แค่เนื้อ)

    ถ้าเทียบแค่ dict ต่อ dict ไฟล์ที่ commit ไว้อาจถูกจัดรูปแบบคนละแบบกับที่
    สคริปต์เขียน แล้ว CI จะแดงทุกครั้งด้วย diff ที่ไม่มีความหมาย
    """
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.generate_openapi import build_spec, render

    assert render(build_spec()) == SPEC_PATH.read_text(encoding="utf-8"), REGENERATE


# ---------------------------------------------------------------- คุณสมบัติของสัญญา


def test_every_path_lives_under_the_version_prefix(live):
    """เวอร์ชันอยู่ที่ path — endpoint ที่หลุดออกไปนอก prefix คือของที่ไม่มีสัญญาคุม"""
    outside = [path for path in live["paths"] if not path.startswith(API_PREFIX)]
    assert not outside, outside


def test_the_spec_declares_the_bearer_scheme(live):
    assert live["security"] == [{BEARER_SCHEME: []}]
    scheme = live["components"]["securitySchemes"][BEARER_SCHEME]
    assert scheme["type"] == "http"
    assert scheme["scheme"] == "bearer"


def test_every_operation_is_documented(live):
    """operation ที่ไม่มีคำอธิบายคือ endpoint ที่ client ต้องเดาว่าทำอะไร"""
    undocumented = [
        f"{method.upper()} {path}"
        for path, method, operation in _operations(live)
        if not operation.get("summary")
    ]
    assert not undocumented, undocumented


def test_every_operation_can_answer_with_the_error_envelope(live):
    """ทุก operation ต้องมีทางบอกความผิดพลาดในรูปซองเดียวกัน"""
    missing = [
        f"{method.upper()} {path}"
        for path, method, operation in _operations(live)
        if "default" not in operation["responses"]
    ]
    assert not missing, missing


def test_the_error_envelope_is_described_once(live):
    """ซองต้องมีนิยามเดียวในไฟล์ ไม่งั้น client จะเจอสองรูปแบบที่หน้าตาไม่เหมือนกัน"""
    error = live["components"]["schemas"]["Error"]
    assert set(error["properties"]) == {"error"}
    detail = live["components"]["schemas"]["ErrorDetail"]
    assert {"code", "message"} <= set(detail["properties"])


def test_the_tokens_resource_has_no_way_to_create_one(live):
    """ออกใบใหม่ต้องมาจากตัวตนที่แรงกว่า token (ดู ADR 0017) — สัญญาต้องสะท้อนข้อนี้"""
    assert "post" not in live["paths"][f"{API_PREFIX}/tokens"]


def test_the_spec_is_served_for_clients_to_fetch(anon_client):
    """เสิร์ฟตัว JSON ได้โดยไม่ต้องมี token — เป็นสัญญาสาธารณะ ไม่ใช่ข้อมูลของใคร"""
    resp = anon_client.get(f"{API_PREFIX}/openapi.json")
    assert resp.status_code == 200
    assert resp.get_json()["info"]["title"]


def test_the_generator_can_run_as_a_plain_script():
    """CI เรียกมันตรง ๆ ไม่ผ่าน pytest — ต้องรันได้โดยไม่ต้องมี .env หรือฐานข้อมูล"""
    result = subprocess.run(  # noqa: S603  รัน interpreter ของเราเองกับสคริปต์ใน repo
        [sys.executable, str(GENERATOR)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(REPO_ROOT)},
        check=False,
    )
    assert result.returncode == 0, result.stderr
