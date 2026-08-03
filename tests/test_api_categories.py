"""`/api/v1/categories` — สัญญาของหมวด (Phase 3)

กติกาของโดเมนอยู่ที่ `tests/test_services.py` แล้ว ไฟล์นี้ดูว่าชั้น HTTP
แปลมันออกมาถูกไหม — โดยเฉพาะ **409 ไม่ใช่ 400** สำหรับ "ชนกับสถานะปัจจุบัน"
เพราะ client ที่เห็น 400 จะแก้ค่าที่ส่งมาแล้วลองใหม่ ส่วน 409 บอกว่าให้ไปแก้
สถานะก่อน (ย้ายงานออกจากหมวด) ซึ่งเป็นการกระทำคนละอย่างกันโดยสิ้นเชิง
"""

import pytest

CATEGORIES = "/api/v1/categories"
TODOS = "/api/v1/todos"
OK, CREATED, NO_CONTENT = 200, 201, 204
BAD_REQUEST, NOT_FOUND, CONFLICT, UNPROCESSABLE = 400, 404, 409, 422


def _make(api_client, name="งานบ้าน"):
    resp = api_client.post(CATEGORIES, json={"name": name})
    assert resp.status_code == CREATED, resp.get_json()
    return resp.get_json()


def test_a_new_category_has_no_tasks_in_it(api_client):
    assert _make(api_client) == {"id": 1, "name": "งานบ้าน", "task_count": 0}


def test_the_list_is_sorted_by_name(api_client):
    _make(api_client, "ข")
    _make(api_client, "ก")
    assert [row["name"] for row in api_client.get(CATEGORIES).get_json()] == ["ก", "ข"]


def test_the_task_count_follows_reality(api_client):
    """ตอบคำถาม "ลบหมวดนี้ได้ไหม" ได้โดยไม่ต้องลองลบ"""
    category = _make(api_client)
    api_client.post(TODOS, json={"title": "ล้างจาน", "category_id": category["id"]})
    assert api_client.get(f"{CATEGORIES}/{category['id']}").get_json()["task_count"] == 1


def test_renaming_a_category(api_client):
    category = _make(api_client)
    resp = api_client.patch(f"{CATEGORIES}/{category['id']}", json={"name": "งานที่ทำงาน"})
    assert resp.status_code == OK
    assert resp.get_json()["name"] == "งานที่ทำงาน"


def test_a_duplicate_name_is_a_conflict(api_client):
    _make(api_client)
    resp = api_client.post(CATEGORIES, json={"name": "งานบ้าน"})
    assert resp.status_code == CONFLICT
    assert resp.get_json()["error"]["code"] == "category_exists"


def test_a_blank_name_is_refused(api_client):
    resp = api_client.post(CATEGORIES, json={"name": "  "})
    assert resp.status_code == BAD_REQUEST
    assert resp.get_json()["error"]["code"] == "name_required"


def test_a_missing_name_is_refused_by_the_schema(api_client):
    resp = api_client.post(CATEGORIES, json={})
    assert resp.status_code == UNPROCESSABLE
    assert "name" in resp.get_json()["error"]["errors"]["json"]


def test_deleting_an_empty_category(api_client):
    category = _make(api_client)
    assert api_client.delete(f"{CATEGORIES}/{category['id']}").status_code == NO_CONTENT
    assert api_client.get(CATEGORIES).get_json() == []


def test_deleting_a_category_that_still_has_tasks_is_a_conflict(api_client):
    """งานที่ทำเสร็จแล้วก็ยังนับ — กติกาเดียวกับหน้าเว็บ"""
    category = _make(api_client)
    todo = api_client.post(
        TODOS, json={"title": "ล้างจาน", "category_id": category["id"]}
    ).get_json()
    api_client.patch(f"{TODOS}/{todo['id']}", json={"is_done": True})

    resp = api_client.delete(f"{CATEGORIES}/{category['id']}")
    assert resp.status_code == CONFLICT
    assert resp.get_json()["error"]["code"] == "category_in_use"
    assert api_client.get(f"{CATEGORIES}/{category['id']}").status_code == OK


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_someone_elses_category_looks_like_it_does_not_exist(api_client, other_api_client, method):
    theirs = other_api_client.post(CATEGORIES, json={"name": "ของเขา"}).get_json()
    resp = api_client.open(f"{CATEGORIES}/{theirs['id']}", method=method, json={"name": "แก้"})
    assert resp.status_code == NOT_FOUND
    assert resp.get_json()["error"]["code"] == "category_not_found"


def test_the_same_name_is_free_for_a_different_user(api_client, other_api_client):
    _make(api_client)
    assert other_api_client.post(CATEGORIES, json={"name": "งานบ้าน"}).status_code == CREATED


def test_putting_a_task_in_someone_elses_category_is_a_404(api_client, other_api_client):
    theirs = other_api_client.post(CATEGORIES, json={"name": "ของเขา"}).get_json()
    resp = api_client.post(TODOS, json={"title": "งาน", "category_id": theirs["id"]})
    assert resp.status_code == NOT_FOUND
