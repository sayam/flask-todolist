"""`/api/v1/tokens` — ดูและเพิกถอนกุญแจของตัวเอง (Phase 3, ADR 0017)

สองข้อที่ต้องพิสูจน์:

1. **ตัวความลับไม่โผล่ในคำตอบเลย** ทั้งของเดิมและในรูป hash — endpoint ที่ทำ
   หน้าที่ "แสดงรายการกุญแจ" คือที่ที่ความลับรั่วได้ง่ายที่สุด
2. **token ออก token ใหม่ไม่ได้** ใบที่หลุดจึงแตกลูกเป็นใบที่อายุยาวกว่าเดิม
   ไม่ได้ การเพิกถอนใบที่หลุดจึงปิดประตูได้จริง
"""

from app import db
from app.models import ApiToken
from tests.conftest import bearer_client, issue_token

TOKENS = "/api/v1/tokens"
OK, NO_CONTENT = 200, 204
UNAUTHORIZED, NOT_FOUND, METHOD_NOT_ALLOWED = 401, 404, 405


def test_the_list_shows_the_token_being_used(api_client, api_token):
    body = api_client.get(TOKENS).get_json()
    assert [row["id"] for row in body] == [int(api_token.split("_")[1])]
    assert body[0]["name"] == "pytest"
    assert body[0]["is_expired"] is False


def test_no_response_ever_carries_the_secret(app, api_client, api_token):
    """ทั้งความลับดิบและ hash ที่เก็บไว้ต้องไม่โผล่ในตัวอักษรใดของคำตอบ"""
    secret = api_token.split("_", 2)[2]
    with app.app_context():
        stored = db.session.get(ApiToken, int(api_token.split("_")[1])).token_hash

    for path in (TOKENS, f"{TOKENS}/{api_token.split('_')[1]}"):
        text = api_client.get(path).get_data(as_text=True)
        assert secret not in text
        assert stored not in text
        assert "token_hash" not in text


def test_the_documented_fields_are_the_only_ones(api_client, api_token):
    body = api_client.get(f"{TOKENS}/{api_token.split('_')[1]}").get_json()
    assert set(body) == {"id", "name", "created_at", "expires_at", "is_expired"}


def test_the_api_cannot_issue_a_new_token(api_client):
    """ออกใบใหม่ได้จาก CLI เท่านั้น — ไม่งั้นใบที่หลุดจะแตกลูกที่อายุยาวกว่าเดิมได้"""
    assert api_client.post(TOKENS, json={"name": "ใบใหม่"}).status_code == METHOD_NOT_ALLOWED


def test_revoking_a_token_kills_it_for_the_next_request(app, user_id, api_token):
    """สคริปต์ที่รู้ตัวว่าโดนเจาะต้องฆ่ากุญแจตัวเองได้ทันที ไม่ต้องรอคนมา ssh"""
    # ใช้ใบที่สองยิงคำสั่งเพิกถอน เพื่อให้เห็นชัดว่าใบที่ถูกเพิกถอน "ตาย" จริง
    # ไม่ใช่แค่คำขอนั้นล้มเหลวไปพร้อมกับตัวมันเอง
    other = issue_token(app, user_id, name="ใบที่สอง")
    client = bearer_client(app, other)
    victim_id = int(api_token.split("_")[1])

    assert client.delete(f"{TOKENS}/{victim_id}").status_code == NO_CONTENT
    assert bearer_client(app, api_token).get(TOKENS).status_code == UNAUTHORIZED
    assert [row["id"] for row in client.get(TOKENS).get_json()] == [int(other.split("_")[1])]


def test_a_token_can_revoke_itself(api_client, api_token):
    """คำขอนี้สำเร็จ แต่คำขอถัดไปที่ใช้ใบเดิมต้องได้ 401"""
    assert api_client.delete(f"{TOKENS}/{api_token.split('_')[1]}").status_code == NO_CONTENT
    assert api_client.get(TOKENS).status_code == UNAUTHORIZED


def test_someone_elses_token_looks_like_it_does_not_exist(api_client, other_api_client):
    theirs = other_api_client.get(TOKENS).get_json()[0]
    assert api_client.get(f"{TOKENS}/{theirs['id']}").status_code == NOT_FOUND
    assert api_client.delete(f"{TOKENS}/{theirs['id']}").status_code == NOT_FOUND
    assert other_api_client.get(TOKENS).status_code == OK, "ใบของเขาต้องยังใช้ได้อยู่"


def test_the_list_only_shows_your_own_tokens(api_client, other_api_client):
    assert len(api_client.get(TOKENS).get_json()) == 1
    assert len(other_api_client.get(TOKENS).get_json()) == 1
