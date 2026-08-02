"""เทสต์ CSRF ทำงานบนแอปที่เปิด WTF_CSRF_ENABLED จริง

ไฟล์อื่นปิด CSRF ไว้เพื่อความสะดวก ถ้าไม่มีไฟล์นี้จะไม่มีอะไรยืนยันว่า
CSRF ทำงาน — และวันไหน csrf.init_app() หลุดไปก็จะไม่มีเทสต์ไหนแดง
"""

import re

import pytest

from app import db
from app.models import Todo
from tests.conftest import PASSWORD

# ทุก route ที่แก้ข้อมูล ต้องถูกปฏิเสธหมดถ้าไม่มี token
MUTATING_ROUTES = [
    "/add",
    "/edit/1",
    "/toggle/1",
    "/delete/1",
    "/clear-completed",
    "/categories/add",
    "/categories/edit/1",
    "/categories/delete/1",
    "/logout",
]


def _token(html):
    match = re.search(rb'name="csrf_token" value="([^"]+)"', html)
    assert match, "ไม่พบ csrf_token ในหน้าที่ render"
    return match.group(1).decode()


def _login(client):
    token = _token(client.get("/login").data)
    resp = client.post(
        "/login",
        data={"username": "tester", "password": PASSWORD, "csrf_token": token},
    )
    assert resp.status_code == 302, "login พร้อม token ที่ถูกต้องต้องผ่าน"
    return client


def test_login_page_renders_token(csrf_app):
    assert _token(csrf_app.test_client().get("/login").data)


def test_login_without_token_rejected(csrf_app):
    resp = csrf_app.test_client().post("/login", data={"username": "tester", "password": PASSWORD})
    assert resp.status_code == 400


def test_login_with_token_succeeds(csrf_app):
    _login(csrf_app.test_client())


@pytest.mark.parametrize("route", MUTATING_ROUTES)
def test_mutating_route_without_token_rejected(csrf_app, route):
    client = _login(csrf_app.test_client())
    assert client.post(route).status_code == 400, f"{route} ต้องปฏิเสธเมื่อไม่มี token"


def test_mutating_route_with_token_succeeds(csrf_app):
    client = _login(csrf_app.test_client())
    token = _token(client.get("/").data)
    resp = client.post("/add", data={"title": "งานที่มี token", "csrf_token": token})
    assert resp.status_code == 302
    with csrf_app.app_context():
        assert Todo.query.filter_by(title="งานที่มี token").count() == 1


def test_stolen_session_without_token_cannot_delete(csrf_app):
    """จำลอง CSRF จริง: ผู้โจมตีมี cookie session แต่ไม่มี token"""
    client = _login(csrf_app.test_client())
    token = _token(client.get("/").data)
    client.post("/add", data={"title": "ห้ามหาย", "csrf_token": token})

    with csrf_app.app_context():
        todo_id = Todo.query.filter_by(title="ห้ามหาย").first().id

    # ยิงด้วย session เดิมแต่ไม่แนบ token — เหมือนเว็บอื่นสั่งให้ browser ยิงมา
    assert client.post(f"/delete/{todo_id}").status_code == 400
    assert client.post("/clear-completed").status_code == 400

    with csrf_app.app_context():
        assert db.session.get(Todo, todo_id) is not None
