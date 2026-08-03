"""`/api/v1/todos` — สัญญาที่ client ยึดถือได้ (Phase 3)

ตรรกะของโดเมนถูกทดสอบไปแล้วที่ `tests/test_services.py` ไฟล์นี้ทดสอบ **สิ่งที่
เป็นของชั้น HTTP เท่านั้น**: status code, รูปร่าง JSON, การแยก "ไม่ได้ส่งฟิลด์
มา" ออกจาก "ส่ง null มา", และเวลาที่ต้องเป็นเวลาท้องถิ่นทั้งขาเข้าและขาออก

เวลาเป็นจุดที่พังเงียบที่สุด — ส่งเข้าไปเป็นเวลาท้องถิ่นแต่ได้ UTC กลับมา
แล้วไม่มีใครสังเกตจนกว่างานจะเตือนผิดเวลา 7 ชั่วโมง
"""

from datetime import datetime

import pytest

from app import db
from app.audit import AuditEntry
from app.models import Todo
from app.services import todos as todos_service

TODOS = "/api/v1/todos"
OK, CREATED, NO_CONTENT = 200, 201, 204
BAD_REQUEST, NOT_FOUND, UNPROCESSABLE = 400, 404, 422


def _make(api_client, **fields):
    resp = api_client.post(TODOS, json={"title": "งาน", **fields})
    assert resp.status_code == CREATED, resp.get_json()
    return resp.get_json()


# ---------------------------------------------------------------- อ่าน


def test_an_empty_list_is_an_empty_array(api_client):
    """ไม่มีงานต้องได้ `[]` ไม่ใช่ 404 หรือ null"""
    resp = api_client.get(TODOS)
    assert resp.status_code == OK
    assert resp.get_json() == []


def test_a_created_task_comes_back_with_every_documented_field(api_client):
    body = _make(api_client, due_date="2026-09-01T16:00")
    assert set(body) == {
        "id",
        "title",
        "is_done",
        "category_id",
        "start_date",
        "due_date",
        "is_overdue",
        "is_due_today",
        "created_at",
        "updated_at",
    }


def test_the_list_shows_the_soonest_due_first(api_client):
    _make(api_client, title="ทีหลัง", due_date="2026-09-10T09:00")
    _make(api_client, title="ก่อน", due_date="2026-09-01T09:00")
    _make(api_client, title="ไม่มีกำหนด")
    assert [row["title"] for row in api_client.get(TODOS).get_json()] == [
        "ก่อน",
        "ทีหลัง",
        "ไม่มีกำหนด",
    ]


def test_one_task_can_be_read_on_its_own(api_client):
    todo_id = _make(api_client)["id"]
    assert api_client.get(f"{TODOS}/{todo_id}").get_json()["id"] == todo_id


def test_a_deleted_task_is_gone_from_both_the_list_and_the_item(api_client):
    todo_id = _make(api_client)["id"]
    assert api_client.delete(f"{TODOS}/{todo_id}").status_code == NO_CONTENT
    assert api_client.get(TODOS).get_json() == []
    assert api_client.get(f"{TODOS}/{todo_id}").status_code == NOT_FOUND


# ---------------------------------------------------------------- เวลา


def test_dates_go_in_and_come_back_as_the_owners_local_time(app, api_client):
    """ส่ง 16:00 ตามเวลาที่ผู้ใช้ตั้งไว้ ต้องได้ 16:00 กลับมา ไม่ใช่ 09:00 UTC"""
    todo_id = _make(api_client, due_date="2026-09-01T16:00")["id"]
    assert api_client.get(f"{TODOS}/{todo_id}").get_json()["due_date"] == "2026-09-01T16:00:00"
    with app.app_context():
        # ในฐานข้อมูลต้องเป็น UTC — กรุงเทพ +07:00 จึงเป็น 09:00
        assert db.session.get(Todo, todo_id).due_date == datetime(2026, 9, 1, 9, 0)


def test_a_date_without_a_time_means_midnight(api_client):
    todo_id = _make(api_client, due_date="2026-09-01")["id"]
    assert api_client.get(f"{TODOS}/{todo_id}").get_json()["due_date"] == "2026-09-01T00:00:00"


def test_a_date_with_an_offset_is_refused(api_client):
    """`+07:00` ที่ส่งมาโดยคนที่ตั้ง timezone เป็นโตเกียวแปลว่าอะไรไม่มีใครตอบได้"""
    resp = api_client.post(TODOS, json={"title": "งาน", "due_date": "2026-09-01T16:00+07:00"})
    assert resp.status_code == UNPROCESSABLE
    assert resp.get_json()["error"]["code"] == "validation_error"


def test_a_date_that_is_not_a_date_is_refused(api_client):
    assert api_client.post(TODOS, json={"title": "งาน", "due_date": "เมื่อวาน"}).status_code == (
        UNPROCESSABLE
    )


# ---------------------------------------------------------------- เขียน


def test_creating_without_a_title_is_refused(api_client):
    resp = api_client.post(TODOS, json={})
    assert resp.status_code == UNPROCESSABLE
    assert "title" in resp.get_json()["error"]["errors"]["json"]


def test_a_blank_title_is_refused_by_the_service(api_client):
    """schema ปล่อยผ่านเพราะเป็นสตริง — กติกา "ห้ามว่าง" อยู่ที่ service ชั้นเดียว"""
    resp = api_client.post(TODOS, json={"title": "   "})
    assert resp.status_code == BAD_REQUEST
    assert resp.get_json()["error"] == {
        "code": "title_required",
        "message": "Please enter a task name",
        "field": "title",
    }


def test_patching_one_field_leaves_the_others_alone(api_client):
    todo_id = _make(api_client, title="เดิม", due_date="2026-09-01T16:00")["id"]
    body = api_client.patch(f"{TODOS}/{todo_id}", json={"title": "ใหม่"}).get_json()
    assert body["title"] == "ใหม่"
    assert body["due_date"] == "2026-09-01T16:00:00", "กำหนดส่งหายทั้งที่ไม่ได้ส่งมาแก้"


def test_sending_null_clears_the_field(api_client):
    """`null` ที่ส่งมาจริงแปลว่า "ล้างค่า" — ต่างจากการไม่ส่งฟิลด์นั้นมาเลย"""
    todo_id = _make(api_client, due_date="2026-09-01T16:00")["id"]
    assert api_client.patch(f"{TODOS}/{todo_id}", json={"due_date": None}).get_json()[
        "due_date"
    ] is (None)


def test_marking_done_through_patch(api_client):
    todo_id = _make(api_client)["id"]
    assert api_client.patch(f"{TODOS}/{todo_id}", json={"is_done": True}).get_json()["is_done"]


def test_an_unknown_field_is_refused(api_client):
    """client ที่พิมพ์ `done` แทน `is_done` ต้องรู้ตัวทันที ไม่ใช่คิดว่าบันทึกแล้ว"""
    todo_id = _make(api_client)["id"]
    resp = api_client.patch(f"{TODOS}/{todo_id}", json={"done": True})
    assert resp.status_code == UNPROCESSABLE
    assert "done" in resp.get_json()["error"]["errors"]["json"]


def test_an_empty_patch_changes_nothing(api_client):
    todo_id = _make(api_client, title="เดิม")["id"]
    assert api_client.patch(f"{TODOS}/{todo_id}", json={}).get_json()["title"] == "เดิม"


# ---------------------------------------------------------------- ตัวกรอง


def test_filtering_by_status(api_client):
    done_id = _make(api_client, title="เสร็จแล้ว")["id"]
    _make(api_client, title="ยังอยู่")
    api_client.patch(f"{TODOS}/{done_id}", json={"is_done": True})

    assert [row["title"] for row in api_client.get(f"{TODOS}?status=active").get_json()] == ["ยังอยู่"]
    assert [row["title"] for row in api_client.get(f"{TODOS}?status=completed").get_json()] == [
        "เสร็จแล้ว"
    ]


def test_an_unknown_filter_value_falls_back_instead_of_failing(api_client):
    """ค่าที่ไม่รู้จักตกกลับเป็นค่าเริ่มต้นเงียบ ๆ เหมือนฝั่งเว็บ"""
    _make(api_client, title="งาน")
    assert len(api_client.get(f"{TODOS}?status=มั่ว").get_json()) == 1


def test_an_unknown_query_parameter_is_refused(api_client):
    """พิมพ์ชื่อพารามิเตอร์ผิดแล้วได้ผลลัพธ์ที่ไม่ได้กรองคือกับดัก ต้องดังแทน"""
    assert api_client.get(f"{TODOS}?statuss=active").status_code == UNPROCESSABLE


def test_filtering_by_a_category_of_someone_else_is_a_404(api_client, other_api_client):
    theirs = other_api_client.post("/api/v1/categories", json={"name": "ของเขา"}).get_json()
    assert api_client.get(f"{TODOS}?category={theirs['id']}").status_code == NOT_FOUND


# ---------------------------------------------------------------- ความเป็นเจ้าของ


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_someone_elses_task_looks_like_it_does_not_exist(api_client, other_api_client, method):
    theirs = other_api_client.post(TODOS, json={"title": "ความลับ"}).get_json()
    resp = api_client.open(f"{TODOS}/{theirs['id']}", method=method, json={"title": "แก้"})
    assert resp.status_code == NOT_FOUND
    assert resp.get_json()["error"]["code"] == "todo_not_found"


def test_the_list_only_shows_your_own_tasks(api_client, other_api_client):
    other_api_client.post(TODOS, json={"title": "ของเขา"})
    _make(api_client, title="ของเรา")
    assert [row["title"] for row in api_client.get(TODOS).get_json()] == ["ของเรา"]


# ---------------------------------------------------------------- ปลายทางอื่นในระบบ


def test_writes_through_the_api_are_audited_with_the_token_owner(app, api_client, user_id):
    """`actor_id` ต้องเป็นเจ้าของ token ไม่ใช่ค่าว่าง ไม่งั้น audit ตอบไม่ได้ว่าใครแก้"""
    _make(api_client, title="งาน")
    with app.app_context():
        rows = db.session.query(AuditEntry).filter_by(event="todo.insert").all()
        assert [row.actor_id for row in rows] == [user_id]
        assert rows[0].source == "web"


def test_a_task_created_through_the_api_is_visible_on_the_website(app, api_client, user_id):
    """ทั้งสองทางเรียก service ชุดเดียวกัน ข้อมูลจึงเป็นก้อนเดียว (ADR 0016)"""
    _make(api_client, title="ล้างจาน")
    with app.app_context():
        from app.filters import FilterSpec
        from app.models import User

        user = db.session.get(User, user_id)
        assert [t.title for t in todos_service.list_todos(user, FilterSpec())] == ["ล้างจาน"]


def test_a_date_that_is_not_even_a_string_is_refused(api_client):
    """client ที่ส่งตัวเลข epoch มาต้องได้คำตอบที่บอกว่าต้องส่งอะไร ไม่ใช่ 500"""
    resp = api_client.post(TODOS, json={"title": "งาน", "due_date": 1756704000})
    assert resp.status_code == UNPROCESSABLE
    assert "ISO 8601" in str(resp.get_json()["error"]["errors"])


# ---------------------------------------------------------------- ของที่ fuzz จับได้


def test_a_date_filter_that_cannot_be_parsed_is_a_400(api_client):
    """ฝั่งเว็บ flash แล้วแสดงทุกงานแทน แต่ client ที่ยิง API ต้องรู้ว่าตัวกรองไม่ทำงาน

    ก่อนแก้: `ValueError` หลุดออกจาก view กลายเป็น 500 (schemathesis จับได้)
    """
    resp = api_client.get(f"{TODOS}?when=range&date_from=เมื่อวาน")
    assert resp.status_code == BAD_REQUEST
    assert resp.get_json()["error"]["code"] == "date_invalid"


def test_an_id_too_large_for_the_column_is_a_404(api_client):
    """id ที่เกิน 64 บิตแปลว่า "ไม่มีวันมีอยู่จริง" ไม่ใช่ "ระบบพัง"

    ก่อนแก้: ไดรเวอร์ DB โยน OverflowError ตั้งแต่ยังไม่ได้ query → 500
    """
    huge = 10**19
    assert api_client.get(f"{TODOS}/{huge}").status_code == NOT_FOUND
    assert api_client.delete(f"{TODOS}/{huge}").status_code == NOT_FOUND
    assert api_client.patch(f"{TODOS}/{huge}", json={"title": "แก้"}).status_code == NOT_FOUND
