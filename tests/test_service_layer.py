"""ขอบเขตของ service layer — **เป็นสถานะ ไม่ใช่เหตุการณ์** (Phase 3, ADR 0016)

หลัง Phase 3 ตรรกะทั้งหมดอยู่ใน `app/services/` และถูกเรียกจากสองทาง
(หน้าเว็บ HTML กับ `/api/v1`) กติกาที่ทำให้ "สองทาง" ไม่กลายเป็น "โค้ดสองชุด"
คือ service ต้องไม่รู้จัก request ของใครเลย

กติกานี้พังได้เงียบ ๆ ด้วย `from flask import request` บรรทัดเดียวใน service
วันที่รีบ ๆ แล้วมันจะยัง "ทำงานได้" ฝั่ง HTML แต่ฝั่ง API จะพังหรือได้ค่าผิด
ไฟล์นี้จึงบังคับทั้งสองชั้น: สแกนโค้ดว่าไม่ import ของต้องห้าม และพิสูจน์ด้วย
การรันจริงว่าเรียกได้โดยไม่มี request context เลย
"""

import ast
import pathlib

import pytest

from app import db
from app.filters import FilterSpec
from app.models import User
from app.services import categories as categories_service
from app.services import todos as todos_service

SERVICES = pathlib.Path(__file__).resolve().parent.parent / "app" / "services"

# ของที่ผูกกับ "คำขอที่กำลังทำอยู่" — service ต้องรับค่าพวกนี้เป็น argument แทน
# `current_app` **ไม่อยู่ในรายการ** เพราะผูกกับแอป ไม่ใช่กับ request (config อ่านได้)
FORBIDDEN_FLASK_NAMES = frozenset(
    {
        "request",
        "session",
        "g",
        "flash",
        "abort",
        "redirect",
        "render_template",
        "url_for",
        "jsonify",
        "make_response",
    }
)

# ทิศทางของ dependency: adapter รู้จัก service ได้ แต่ service ห้ามรู้จัก adapter
FORBIDDEN_MODULES = ("flask_login", "app.routes", "app.auth", "app.api")


def _service_files():
    return sorted(SERVICES.glob("*.py"))


def _violations(path):
    """import ที่ผิดกติกาในไฟล์เดียว — คืนเป็นข้อความอ่านออกพร้อมเลขบรรทัด"""
    found = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(
                f"{path.name}:{node.lineno} import {alias.name}"
                for alias in node.names
                if alias.name == "flask" or alias.name.startswith(FORBIDDEN_MODULES)
            )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(FORBIDDEN_MODULES):
                found.append(f"{path.name}:{node.lineno} from {module}")
            elif module == "flask":
                found.extend(
                    f"{path.name}:{node.lineno} from flask import {alias.name}"
                    for alias in node.names
                    if alias.name in FORBIDDEN_FLASK_NAMES
                )
    return found


def test_services_never_import_request_bound_helpers():
    offenders = [problem for path in _service_files() for problem in _violations(path)]
    assert not offenders, (
        "service แตะของที่ผูกกับ request:\n"
        + "\n".join(offenders)
        + "\n\nรับค่าที่ต้องใช้เป็น argument แทน แล้วให้ adapter (route/API view) เป็นคนอ่าน request"
    )


def test_the_scanner_actually_reads_the_service_files():
    """กันเทสต์ข้างบนเขียวเพราะหาไฟล์ไม่เจอ ไม่ใช่เพราะโค้ดสะอาด"""
    names = {path.name for path in _service_files()}
    assert {"todos.py", "categories.py", "settings.py"} <= names, names


def test_the_scanner_catches_a_planted_import(tmp_path):
    """พิสูจน์ว่าตัวสแกนจับของจริงได้ ไม่ใช่ regex ที่ไม่เคยตรงกับอะไรเลย"""
    planted = tmp_path / "planted.py"
    planted.write_text("from flask import request\n", encoding="utf-8")
    assert _violations(planted)


@pytest.fixture
def user(app):
    """User ตัวจริงในฐานข้อมูล — service รับ object นี้ ไม่ใช่ current_user"""
    with app.app_context():
        person = User(username="servicetester", timezone_name="Asia/Bangkok")
        person.set_password("password123")
        db.session.add(person)
        db.session.commit()
        yield person


def test_services_run_without_any_request(app, user):
    """ตรรกะทั้งเส้นต้องทำงานได้ใน app context เปล่า ๆ — ไม่มี request ให้แตะ

    นี่คือข้อพิสูจน์จริงของ ADR 0016 ตัวสแกน import เป็นแค่ด่านที่ถูกกว่า
    (CLI และ script ก็เดินทางเส้นนี้ ไม่ใช่แค่ API)
    """
    with app.app_context():
        category = categories_service.create_category(user, "งานบ้าน")
        todo = todos_service.create_todo(user, title="ล้างจาน", category_id=category.id)
        assert todo.id is not None

        listed = todos_service.list_todos(user, FilterSpec(category=str(category.id)))
        assert [item.title for item in listed] == ["ล้างจาน"]

        todos_service.toggle_todo(user, todo.id)
        assert todos_service.clear_completed(user) == 1
        assert todos_service.list_todos(user, FilterSpec()) == []
