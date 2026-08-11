"""สำเนาข้อมูลของเจ้าของข้อมูล (ADR 0034)

เทสต์ที่ตรวจแค่ "ไฟล์มีงานของฉันครบ" **ผ่านได้ทั้งที่มีของคนอื่นปนอยู่**
และผ่านได้ทั้งที่มีความลับหลุดไปด้วย — สองอย่างนั้นจึงเป็นเทสต์แยกที่ตรวจ
*สิ่งที่ต้องไม่มี* ไม่ใช่ผลพลอยได้ของการตรวจว่าครบ
"""

import json

import pytest

from app import audit, db
from app.models import ApiToken, Category, User
from app.services import personal_data
from app.services import todos as todos_service
from tests.conftest import PASSWORD


@pytest.fixture
def owner(app, user_id, other_user_id):
    """ผู้ใช้ที่มีข้อมูลของตัวเองพร้อม และมีข้อมูลของคนอื่นอยู่ในฐานด้วย"""
    with app.app_context():
        user = db.session.get(User, user_id)
        stranger = db.session.get(User, other_user_id)

        mine = Category(name="งานบ้านของฉัน", user_id=user.id)
        theirs = Category(name="ความลับของคนอื่น", user_id=stranger.id)
        db.session.add_all([mine, theirs])
        db.session.commit()

        todos_service.create_todo(user, title="ล้างจานของฉัน", category_id=mine.id)
        todos_service.create_todo(stranger, title="งานของคนอื่น", category_id=theirs.id)
        db.session.add(ApiToken(user_id=user.id, name="กุญแจของฉัน", token_hash="a" * 64))
        db.session.add(ApiToken(user_id=stranger.id, name="กุญแจของคนอื่น", token_hash="b" * 64))
        db.session.commit()
        yield user


def _blob(payload):
    """ไฟล์ทั้งก้อนเป็นข้อความเดียว — ใช้ค้นว่ามีค่าที่ไม่ควรอยู่ปนมาไหม"""
    return json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------- สิ่งที่ต้องมี


def test_export_has_the_owners_own_data(app, owner):
    with app.app_context():
        payload = personal_data.export(owner)
    assert payload["account"]["username"] == "tester"
    assert [c["name"] for c in payload["categories"]] == ["งานบ้านของฉัน"]
    assert [t["title"] for t in payload["todos"]] == ["ล้างจานของฉัน"]
    assert [t["name"] for t in payload["api_tokens"]] == ["กุญแจของฉัน"]


def test_export_says_what_is_not_in_it(app, owner):
    """ข้อจำกัดต้องอยู่ในไฟล์ ไม่ใช่ในเอกสารที่คนได้ไฟล์ไปไม่มีทางเปิด"""
    with app.app_context():
        payload = personal_data.export(owner)
    notice = payload["notice"]
    assert "excluded_operational_logs" in notice, "ต้องบอกว่า log ปฏิบัติการไม่ได้อยู่ในไฟล์"
    assert "excluded_secrets" in notice
    assert "90" in notice["excluded_operational_logs"], "ต้องบอกระยะเก็บรักษาของ log ด้วย"


def test_history_includes_what_the_owner_did(app, client, user_id):
    """สร้างงานผ่านหน้าเว็บจริง เพราะ actor มาจาก request ไม่ใช่จากการเรียก service

    (ห้ามเปิด app context ค้างไว้ตอนยิง HTTP — ดูหัวเรื่องของ tests/test_rbac.py)
    """
    client.post("/add", data={"title": "งานที่ฉันเพิ่งสร้าง"})
    with app.app_context():
        payload = personal_data.export(db.session.get(User, user_id))
    assert any(row["event"] == "todo.insert" for row in payload["history"])
    assert all(row["by"] in ("self", "administrator") for row in payload["history"])


def test_history_includes_what_someone_else_did_to_the_account(app, user_id):
    """เหตุการณ์ที่คนอื่นทำกับบัญชีนี้ต้องอยู่ในสำเนาด้วย ไม่ใช่เฉพาะที่เจ้าตัวทำ

    ใช้ `flask set-role` ซึ่งเป็นทางที่ผู้ดูแลใช้จริง — ไม่ประกอบแถว audit เอง
    เพราะตาราง audit เติมได้อย่างเดียวและ hash ต้องต่อสายให้ถูก (ADR 0015)
    """
    app.test_cli_runner().invoke(args=["set-role", "tester", "admin"])
    with app.app_context():
        payload = personal_data.export(db.session.get(User, user_id))

    by_others = [row for row in payload["history"] if row["by"] == "administrator"]
    assert by_others, "การเปลี่ยนบทบาทโดยคนอื่นต้องโผล่ในประวัติ"
    assert all(row["table"] == "tdl_user" for row in by_others)
    assert all("actor_id" not in row for row in payload["history"]), "ห้ามบอก id ของคนที่ทำ"


# ---------------------------------------------------------------- สิ่งที่ต้องไม่มี


def test_export_never_contains_other_peoples_data(app, owner):
    """ตรวจ *ค่า* ไม่ใช่แค่จำนวนแถว — ของคนอื่นปนมาแบบไม่นับก็ยังรั่ว"""
    with app.app_context():
        payload = personal_data.export(owner)
    blob = _blob(payload)
    for leaked in ("ความลับของคนอื่น", "งานของคนอื่น", "กุญแจของคนอื่น", "intruder"):
        assert leaked not in blob, f"ข้อมูลของคนอื่นหลุดเข้าไปในสำเนา: {leaked}"


def test_export_never_contains_secrets(app, owner):
    """C1 ห้ามออกจากระบบทุกกรณี แม้แต่ในรูปที่ถูกแฮชแล้ว (ADR 0014)"""
    with app.app_context():
        password_hash = owner.password_hash
        token_hash = db.session.scalars(
            db.select(ApiToken.token_hash).where(ApiToken.user_id == owner.id)
        ).first()
        payload = personal_data.export(owner)

    blob = _blob(payload)
    assert password_hash not in blob
    assert token_hash not in blob
    for forbidden in ("password_hash", "token_hash", "totp_secret"):
        assert forbidden not in blob, f"ชื่อฟิลด์ของความลับก็ไม่ควรโผล่: {forbidden}"


def test_history_leaves_out_the_chain_machinery(app, owner):
    """changes/prev_hash/row_hash เป็นกลไกพิสูจน์ความครบถ้วน ไม่ใช่ข้อมูลส่วนบุคคล"""
    with app.app_context():
        payload = personal_data.export(owner)
    for row in payload["history"]:
        assert set(row) == {"at", "event", "table", "row_id", "by"}


# ------------------------------------------------- ทุกคอลัมน์ต้องถูกตัดสินใจ

# **เพิ่มคอลัมน์ใหม่ในตารางที่มีเจ้าของ = ต้องมาตัดสินตรงนี้ว่ามันอยู่ในสำเนาไหม**
# (ADR 0034) รายการนี้คือคำตอบว่า "ทำไมถึงไม่อยู่" ของแต่ละคอลัมน์ที่ไม่ได้ส่งออก
# — เขียนเหตุผลไว้เพื่อให้คนอ่านทีหลังตัดสินได้ว่ายังจริงอยู่ไหม
NOT_EXPORTED = {
    "tdl_user.id": "เลขภายใน ไม่ได้บอกอะไรกับเจ้าตัว",
    "tdl_user.password_hash": "C1 ห้ามออกจากระบบ (ADR 0014)",
    "tdl_user.deleted_at": "สถานะของแถว — คนที่ขอสำเนาได้คือคนที่บัญชียังอยู่",
    "tdl_user.purged_at": "เวลาที่ข้อมูลถูกล้างจริง เป็นสถานะของแถวหลังบัญชีปิดไปแล้ว",
    "tdl_category.user_id": "ชี้กลับมาที่ตัวเอง ไม่มีข้อมูลเพิ่ม",
    "tdl_category.deleted_at": "หมวดที่ถูกลบแล้วไม่อยู่ในสำเนา",
    "tdl_todo.user_id": "ชี้กลับมาที่ตัวเอง ไม่มีข้อมูลเพิ่ม",
    "tdl_todo.deleted_at": "งานที่ถูกลบแล้วไม่อยู่ในสำเนา",
    "tdl_api_token.user_id": "ชี้กลับมาที่ตัวเอง ไม่มีข้อมูลเพิ่ม",
    "tdl_api_token.token_hash": "C1 ห้ามออกจากระบบ (ADR 0017)",
    "tdl_api_token.deleted_at": "ใบที่ถูกเพิกถอนแล้วไม่อยู่ในสำเนา",
}

OWNED_TABLES = {
    "tdl_user": "account",
    "tdl_category": "categories",
    "tdl_todo": "todos",
    "tdl_api_token": "api_tokens",
}


def test_every_column_of_an_owned_table_was_decided(app, owner):
    """ไม่มีคอลัมน์ไหนหลุดการพิจารณา — หลักเดียวกับ tests/test_data_classification.py"""
    with app.app_context():
        payload = personal_data.export(owner)

    undecided = []
    for table_name, section in OWNED_TABLES.items():
        table = db.metadata.tables[table_name]
        rows = payload[section] if isinstance(payload[section], list) else [payload[section]]
        exported = set(rows[0]) if rows else set()
        for column in table.columns:
            full = f"{table_name}.{column.name}"
            if column.name in exported or full in NOT_EXPORTED:
                continue
            undecided.append(full)

    assert not undecided, (
        "คอลัมน์ที่ยังไม่มีใครตัดสินว่าอยู่ในสำเนาข้อมูลไหม:\n"
        + "\n".join(undecided)
        + "\nเพิ่มลงใน export หรือใส่เหตุผลใน NOT_EXPORTED (ADR 0034)"
    )


# ---------------------------------------------------------------- หน้าเว็บ


def test_the_web_page_needs_the_current_password(app, client, user_id):
    resp = client.post("/settings/export", data={"password": "ไม่ใช่รหัสของฉัน"})
    assert resp.status_code == 302
    assert b"{" not in resp.data, "รหัสผิดแล้วต้องไม่มีข้อมูลหลุดออกไปแม้แต่นิดเดียว"


def test_the_web_page_returns_a_download(app, client, user_id):
    resp = client.post("/settings/export", data={"password": PASSWORD})
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    assert "attachment" in resp.headers["Content-Disposition"]
    assert "todolist-tester-" in resp.headers["Content-Disposition"]
    # ทั้งก้อนเป็นข้อมูลส่วนบุคคล ห้ามค้างในแคชของใคร (ASVS V14.3.2)
    assert resp.headers["Cache-Control"] == "no-store"
    assert json.loads(resp.data)["account"]["username"] == "tester"


def test_asking_for_a_copy_is_recorded(app, client, user_id):
    client.post("/settings/export", data={"password": PASSWORD})
    with app.app_context():
        events = [row.event for row in db.session.scalars(db.select(audit.AuditEntry))]
    assert "user.export" in events


def test_a_stranger_cannot_ask_for_a_copy(anon_client):
    resp = anon_client.post("/settings/export", data={"password": PASSWORD})
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


# ---------------------------------------------------------------- CLI


def test_the_cli_exports_the_same_shape(app, user_id):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["export-user", "tester"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["account"]["username"] == "tester"
    assert payload["format"] == personal_data.FORMAT_VERSION


def test_the_cli_refuses_a_name_that_does_not_exist(app):
    result = app.test_cli_runner().invoke(args=["export-user", "ไม่มีคนนี้"])
    assert result.exit_code != 0
    assert "No user named" in result.output


def test_the_filename_never_comes_from_the_user(app):
    """ชื่อผู้ใช้ที่มีอักขระของ path ต้องไม่กลายเป็นชื่อไฟล์ (ASVS V5.4.1)"""
    with app.app_context():
        nasty = User(username="../../etc/passwd")
        assert "/" not in personal_data.filename_for(nasty)
        assert ".." not in personal_data.filename_for(nasty)
