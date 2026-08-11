"""audit trail — บันทึกครบ, ไม่มี PII, แก้ย้อนหลังไม่ได้

สามข้ออ้างของฟีเจอร์นี้ที่ต้องพิสูจน์ให้ได้ทีละข้อ:
1. **ครบ** — ทุก write ถูกบันทึกเอง ไม่ว่ามาจาก route หรือ CLI
2. **สะอาด** — ไม่มีค่าของชั้น C1/C2/C3 หลุดลงตาราง audit เลยสักตัว
3. **แก้ไม่ได้** — แก้แถวเก่าแล้ว `verify_chain()` ต้องจับได้

ข้อ 2 เป็นข้อที่พังเงียบที่สุด เพราะเพิ่มคอลัมน์ใหม่แล้วลืมจัดชั้นก็รั่วได้
โดยไม่มีอะไรแดง — `test_every_column_has_an_audit_policy` จึงบังคับไว้อีกชั้น
"""

import hashlib
import json
import os
from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import audit, db, purge, tz
from app.audit import AuditEntry, AuditImmutableError
from app.models import Category, Todo, User
from tests.conftest import PASSWORD


def _events(app, name=None):
    """แถว audit เรียงจากเก่าไปใหม่ (ลำดับเดียวกับสาย hash)"""
    with app.app_context():
        rows = db.session.query(AuditEntry).order_by(AuditEntry.id).all()
        return [row for row in rows if name is None or row.event == name]


def _all_audit_text(app):
    """ข้อความทั้งหมดที่ตาราง audit เก็บไว้ รวมเป็นก้อนเดียวเพื่อค้นหาของที่ไม่ควรอยู่"""
    with app.app_context():
        rows = db.session.query(AuditEntry).all()
        return "\n".join(f"{row.event} {row.source} {row.table_name} {row.changes}" for row in rows)


# ---------------------------------------------------------------- นโยบายต่อคอลัมน์


def test_every_column_has_an_audit_policy(app):
    """คอลัมน์ใหม่ต้องถูกระบุว่าเก็บค่าจริง/HMAC/ไม่เก็บ — ห้ามตกหล่นเงียบ ๆ

    ค่าเริ่มต้นตอนรันคือ HMAC (ปลอดภัยไว้ก่อน) แต่ปล่อยให้พึ่งค่าเริ่มต้นไม่ได้
    เพราะคอลัมน์ชั้น C4 ที่ลืมประกาศจะถูกปิดบังโดยไม่มีใครตั้งใจ ทำให้ audit
    อ่านไม่รู้เรื่องแทนที่จะรั่ว — ผิดคนละทางแต่ก็ยังผิด
    """
    with app.app_context():
        # คอลัมน์ของ core ประกาศใน app/audit.py ส่วนของ plugin ประกาศใน
        # `models.py` ของตัวเอง (ADR 0023) — ทั้งสองทางรวมกันต้องครอบทุกคอลัมน์
        known = (
            audit.PLAIN_COLUMNS
            | audit.SECRET_COLUMNS
            | audit.HASHED_COLUMNS
            | set(audit.plugin_column_policies())
        )
        missing = [
            f"{table.name}.{column.name}"
            for table in db.metadata.sorted_tables
            if table.name != AuditEntry.__tablename__
            for column in table.columns
            if column.name not in known
        ]
    assert not missing, (
        "คอลัมน์ที่ยังไม่มีนโยบาย audit:\n"
        + "\n".join(missing)
        + "\nของ core ประกาศใน app/audit.py ของ plugin ประกาศใน models.py ของ plugin นั้น"
        + "\nดูชั้นของมันใน docs/DATA-CLASSIFICATION.md ก่อนตัดสินใจ"
    )


def test_the_three_policies_do_not_overlap():
    """คอลัมน์เดียวอยู่สองนโยบายไม่ได้ ไม่งั้นผลลัพธ์ขึ้นกับลำดับการเช็ค"""
    assert not (audit.PLAIN_COLUMNS & audit.SECRET_COLUMNS)
    assert not (audit.PLAIN_COLUMNS & audit.HASHED_COLUMNS)
    assert not (audit.SECRET_COLUMNS & audit.HASHED_COLUMNS)


def test_unknown_columns_are_hidden_by_default(app):
    """คอลัมน์ที่ไม่รู้จักต้องถูก HMAC ไม่ใช่เก็บค่าดิบ"""
    with app.app_context():
        change = audit._column_change("คอลัมน์ที่ยังไม่มีใครจัดชั้น", "ค่าลับ", "ค่าลับใหม่")
    assert "ค่าลับ" not in json.dumps(change, ensure_ascii=False)
    assert set(change) == {"from_hash", "to_hash"}


# ---------------------------------------------------------------- ครบทุก write


def test_creating_a_task_is_audited(client, app, user_id):
    client.post("/add", data={"title": "ซื้อนม"})
    rows = _events(app, "todo.insert")
    assert len(rows) == 1
    assert rows[0].table_name == "tdl_todo"
    assert rows[0].actor_id == user_id
    assert rows[0].source == "web"


def test_insert_records_columns_that_came_from_defaults(client, app):
    """คอลัมน์ที่ได้ค่าจาก `default=` ต้องถูกบันทึกด้วย

    เคยเขียนโดยอ่านจาก history อย่างเดียว แล้ว `is_done`/`created_at` หายไป
    เพราะ SQLAlchemy เติมค่าให้ตอน flush โดยไม่ทิ้ง history ไว้
    """
    client.post("/add", data={"title": "ซื้อนม"})
    changes = _events(app, "todo.insert")[0].payload
    assert changes["is_done"] == {"from": None, "to": False}
    assert changes["created_at"]["to"] is not None


def test_editing_a_task_records_only_what_changed(client, app):
    client.post("/add", data={"title": "ซื้อนม"})
    with app.app_context():
        todo_id = db.session.query(Todo).one().id
    client.post(
        f"/edit/{todo_id}",
        data={"title": "ซื้อนมสด", "category_id": "", "start_date": "", "due_date": ""},
    )
    changes = _events(app, "todo.update")[-1].payload
    assert set(changes) == {"title"}


def test_soft_delete_is_recorded_as_delete_not_update(client, app):
    """ "ลบ" ในระบบนี้เป็น UPDATE ในระดับ SQL — audit ต้องเรียกตามความหมาย ไม่ใช่ตามคำสั่ง"""
    client.post("/add", data={"title": "ซื้อนม"})
    with app.app_context():
        todo_id = db.session.query(Todo).one().id
    client.post(f"/delete/{todo_id}")
    assert [row.event for row in _events(app)][-1] == "todo.delete"
    assert not _events(app, "todo.update")


def test_restore_is_recorded_separately(app, user_id):
    with app.app_context():
        todo = Todo(title="ซื้อนม", user_id=user_id)
        db.session.add(todo)
        db.session.commit()
        todo.soft_delete()
        db.session.commit()
        todo.deleted_at = None
        db.session.commit()
    assert [row.event for row in _events(app)][-1] == "todo.restore"


def test_purge_is_recorded_as_purge(app, user_id):
    with app.app_context():
        todo = Todo(title="ซื้อนม", user_id=user_id)
        db.session.add(todo)
        todo.soft_delete()
        db.session.commit()
        purge.purge_expired(days=0)
    assert "todo.purge" in [row.event for row in _events(app)]


def test_cli_writes_are_audited_as_cli(app):
    """CLI ไม่ผ่าน route แต่ต้องถูกบันทึกเหมือนกัน เพราะดักที่ ORM ไม่ใช่ที่ HTTP"""
    app.test_cli_runner().invoke(args=["create-user", "somchai"], input=f"{PASSWORD}\n{PASSWORD}\n")
    rows = _events(app, "user.insert")
    assert len(rows) == 1
    assert rows[0].source == "cli"
    assert rows[0].actor_id is None
    assert len(_events(app, "category.insert")) == 2


def test_login_and_logout_are_audited(client, app, user_id):
    client.post("/logout")
    events = [row.event for row in _events(app)]
    assert "auth.login" in events
    assert "auth.logout" in events
    logout_row = _events(app, "auth.logout")[0]
    assert logout_row.actor_id == user_id, "ต้องบันทึกก่อน logout_user() ไม่งั้น actor หาย"


def test_failed_login_is_audited(anon_client, app, user_id):
    anon_client.post("/login", data={"username": "tester", "password": "ผิด"})
    rows = _events(app, "auth.login_failed")
    assert len(rows) == 1
    assert rows[0].row_id == user_id
    assert rows[0].actor_id is None


def test_audit_links_to_the_log_by_request_id(client, app):
    client.post("/add", data={"title": "ซื้อนม"})
    row = _events(app, "todo.insert")[0]
    assert row.request_id, "ต้องมี request_id ไว้ไปค้นต่อใน log"


def test_audit_never_stores_the_client_ip(client, app):
    """IP อยู่ใน log (90 วัน) ไม่ใช่ใน audit (1 ปี) — ก๊อปมาเก็บยาวโดยไม่ตั้งใจไม่ได้"""
    client.post("/add", data={"title": "ซื้อนม"})
    assert "127.0.0.1" not in _all_audit_text(app)
    assert "remote_addr" not in {column.name for column in AuditEntry.__table__.columns}


# ---------------------------------------------------------------- ไม่มี PII หลุด


def test_task_titles_are_hashed_not_stored(client, app):
    client.post("/add", data={"title": "โทรหาหมอฟัน 081-2345678"})
    assert "โทรหาหมอฟัน" not in _all_audit_text(app)
    assert "081-2345678" not in _all_audit_text(app)
    changes = _events(app, "todo.insert")[0].payload
    assert set(changes["title"]) == {"from_hash", "to_hash"}
    assert changes["title"]["to_hash"]


def test_usernames_are_hashed_not_stored(app):
    app.test_cli_runner().invoke(args=["create-user", "สมชาย"], input=f"{PASSWORD}\n{PASSWORD}\n")
    assert "สมชาย" not in _all_audit_text(app)


def test_failed_login_does_not_store_the_username_that_was_tried(anon_client, app):
    """ชื่อที่คนนอกกรอกมาก็เป็นชั้น C2 และไม่ใช่ของเราด้วยซ้ำ ห้ามเก็บ"""
    anon_client.post("/login", data={"username": "สมหญิง", "password": "เดา"})
    assert "สมหญิง" not in _all_audit_text(app)
    assert _events(app, "auth.login_failed")[0].payload == {}


def test_password_hash_never_reaches_the_audit_table(app):
    """ชั้น C1 ห้ามออกจากระบบทุกกรณี แม้แต่ในรูป hash (ADR 0014)"""
    app.test_cli_runner().invoke(args=["create-user", "somchai"], input=f"{PASSWORD}\n{PASSWORD}\n")
    with app.app_context():
        stored_hash = db.session.query(User).filter_by(username="somchai").one().password_hash
    text_dump = _all_audit_text(app)
    assert stored_hash not in text_dump
    assert PASSWORD not in text_dump
    assert _events(app, "user.insert")[0].payload["password_hash"] == {"changed": True}


def test_settings_values_are_stored_plainly(client, app):
    """ชั้น C4 เก็บค่าจริงได้ ไม่งั้น audit อ่านไม่รู้เรื่อง"""
    client.post(
        "/settings/preferences",
        data={"locale": "th", "theme": "system", "mode": "dark", "timezone": "Asia/Bangkok"},
    )
    changes = _events(app, "user.update")[-1].payload
    assert changes["mode"] == {"from": None, "to": "dark"}
    assert changes["locale"] == {"from": None, "to": "th"}


def test_names_are_hashed_even_though_the_row_is_the_users_own(client, app):
    client.post("/settings/profile", data={"first_name": "สยาม", "last_name": "ศรีสุข"})
    assert "สยาม" not in _all_audit_text(app)
    changes = _events(app, "user.update")[-1].payload
    assert set(changes["first_name"]) == {"from_hash", "to_hash"}


def test_hashing_uses_hmac_not_a_bare_digest(app):
    """hash เปล่าถูกไล่เดาด้วย dictionary ได้ ค่าอย่างชื่อคนสั้นเกินกว่าจะรอด"""
    with app.app_context():
        hashed = audit._hmac("สมชาย")
    bare = hashlib.sha256(json.dumps("สมชาย", ensure_ascii=False).encode()).hexdigest()
    assert hashed != bare


def test_equal_values_hash_equal_and_different_values_differ(app):
    """ต้องตอบได้ว่า "ค่าเปลี่ยนไหม" ไม่งั้น HMAC ไม่มีประโยชน์อะไรเลย"""
    with app.app_context():
        assert audit._hmac("ซื้อนม") == audit._hmac("ซื้อนม")
        assert audit._hmac("ซื้อนม") != audit._hmac("ซื้อขนม")
        assert audit._hmac(None) is None


def test_a_different_hmac_key_gives_a_different_hash(app):
    with app.app_context():
        first = audit._hmac("ซื้อนม")
        app.config["AUDIT_HMAC_KEY"] = "กุญแจคนละดอก"
        assert audit._hmac("ซื้อนม") != first


# ---------------------------------------------------------------- hash chain


def test_chain_verifies_after_a_normal_session(client, app):
    client.post("/add", data={"title": "ซื้อนม"})
    with app.app_context():
        assert audit.verify_chain() >= 2


def test_the_first_entry_starts_from_genesis(client, app):
    client.post("/add", data={"title": "ซื้อนม"})
    assert _events(app)[0].prev_hash == audit.GENESIS_HASH


def test_editing_an_entrys_content_breaks_the_chain(client, app):
    client.post("/add", data={"title": "ซื้อนม"})
    target = _events(app, "todo.insert")[0].id
    with app.app_context():
        db.session.execute(
            text("UPDATE tdl_audit SET changes = :value WHERE id = :id"),
            {"value": '{"title":{"from_hash":null,"to_hash":null}}', "id": target},
        )
        db.session.commit()
        with pytest.raises(audit.ChainError) as broken:
            audit.verify_chain()
    assert broken.value.entry_id == target


def test_rewriting_the_actor_breaks_the_chain(client, app):
    """เปลี่ยนคนทำเป็นคนอื่นย้อนหลังคือสิ่งที่ chain มีไว้จับ"""
    client.post("/add", data={"title": "ซื้อนม"})
    target = _events(app, "todo.insert")[0].id
    with app.app_context():
        db.session.execute(
            text("UPDATE tdl_audit SET actor_id = 999 WHERE id = :id"), {"id": target}
        )
        db.session.commit()
        with pytest.raises(audit.ChainError):
            audit.verify_chain()


def test_removing_an_entry_from_the_middle_breaks_the_chain(client, app):
    client.post("/add", data={"title": "ซื้อนม"})
    client.post("/add", data={"title": "ซื้อขนม"})
    rows = _events(app)
    assert len(rows) >= 3
    with app.app_context():
        db.session.execute(text("DELETE FROM tdl_audit WHERE id = :id"), {"id": rows[1].id})
        db.session.commit()
        with pytest.raises(audit.ChainError):
            audit.verify_chain()


def test_replacing_an_entry_with_a_self_consistent_forgery_still_breaks(client, app):
    """ปลอมแถวเดียวให้ hash ตัวเองถูกต้องก็ยังไม่พอ เพราะแถวถัดไปชี้มาที่ hash เดิม"""
    client.post("/add", data={"title": "ซื้อนม"})
    client.post("/add", data={"title": "ซื้อขนม"})
    rows = _events(app)
    victim = rows[1]
    with app.app_context():
        forged_changes = '{"title":{"from_hash":null,"to_hash":"ปลอม"}}'
        forged_hash = audit.compute_row_hash(
            created_at=victim.created_at,
            event_name=victim.event,
            actor_id=victim.actor_id,
            source=victim.source,
            request_id=victim.request_id,
            table_name=victim.table_name,
            row_id=victim.row_id,
            changes=forged_changes,
            prev_hash=victim.prev_hash,
        )
        db.session.execute(
            text("UPDATE tdl_audit SET changes = :c, row_hash = :h WHERE id = :id"),
            {"c": forged_changes, "h": forged_hash, "id": victim.id},
        )
        db.session.commit()
        with pytest.raises(audit.ChainError) as broken:
            audit.verify_chain()
    assert broken.value.entry_id == rows[2].id, "แถวถัดไปต่างหากที่ควรฟ้อง"


def test_the_chain_cannot_fork(client, app):
    """สองแถวชี้ไปแถวก่อนหน้าตัวเดียวกันไม่ได้ — DB ปฏิเสธเอง"""
    client.post("/add", data={"title": "ซื้อนม"})
    last = _events(app)[-1]
    forged = text(
        "INSERT INTO tdl_audit "
        "(created_at, event, source, changes, prev_hash, row_hash) "
        "VALUES (:t, 'todo.insert', 'web', '{}', :prev, :hash)"
    )
    # ส่งเวลาเป็นข้อความ ไม่ใช่ datetime — adapter ของ sqlite3 ถูก deprecate แล้ว
    values = {"t": last.created_at.isoformat(sep=" "), "prev": last.prev_hash, "hash": "x" * 64}
    with app.app_context(), pytest.raises(IntegrityError):
        db.session.execute(forged, values)


def test_row_hash_leaves_out_the_database_id(app):
    """hash ต้องไม่ผูกกับ id เพราะ id มาจาก DB ตอน insert ซึ่งยังไม่รู้ค่าตอนคำนวณ"""
    with app.app_context():
        moment = tz.now_utc().replace(microsecond=0)
        fields = {
            "created_at": moment,
            "event_name": "todo.insert",
            "actor_id": 1,
            "source": "web",
            "request_id": None,
            "table_name": "tdl_todo",
            "row_id": 5,
            "changes": "{}",
            "prev_hash": audit.GENESIS_HASH,
        }
        assert audit.compute_row_hash(**fields) == audit.compute_row_hash(**fields)


def test_timestamps_are_truncated_to_whole_seconds(client, app):
    """MySQL DATETIME ปัดเศษวินาทีทิ้ง ถ้า hash ค่าที่ละเอียดกว่าที่เก็บได้จะพังตอนย้าย DB"""
    client.post("/add", data={"title": "ซื้อนม"})
    assert all(row.created_at.microsecond == 0 for row in _events(app))


# ---------------------------------------------------------------- แก้ไม่ได้


def test_updating_an_entry_through_the_orm_is_refused(client, app):
    client.post("/add", data={"title": "ซื้อนม"})
    with app.app_context():
        row = db.session.query(AuditEntry).first()
        row.event = "อะไรก็ได้"
        with pytest.raises(AuditImmutableError):
            db.session.commit()


def test_deleting_an_entry_through_the_orm_is_refused(client, app):
    client.post("/add", data={"title": "ซื้อนม"})
    with app.app_context():
        row = db.session.query(AuditEntry).first()
        db.session.delete(row)
        with pytest.raises(AuditImmutableError):
            db.session.commit()


def test_the_purge_permission_is_not_left_open(app, user_id):
    """purge job เปิดสิทธิ์ลบ audit ชั่วคราว ต้องปิดคืนทันที ไม่ค้างทั้ง session"""
    with app.app_context():
        purge.purge_audit(days=0)
        row = db.session.query(AuditEntry).first()
        db.session.delete(row)
        with pytest.raises(AuditImmutableError):
            db.session.commit()


def test_there_is_no_route_that_touches_audit(app):
    """อ่านก็ไม่ได้ แก้ก็ไม่ได้ผ่านเว็บ — เข้าถึงได้ทาง CLI เท่านั้น"""
    paths = [str(rule) for rule in app.url_map.iter_rules()]
    assert not [path for path in paths if "audit" in path]


def test_audit_rows_cannot_be_hidden(app):
    """ไม่มี deleted_at แปลว่า "ซ่อนหลักฐาน" ไม่ใช่ท่าที่ทำได้"""
    assert "deleted_at" not in {column.name for column in AuditEntry.__table__.columns}


# ---------------------------------------------------------------- purge + checkpoint


def _seed_at(app, when, monkeypatch, name):
    """สร้างหมวดหนึ่งอันโดยปลอมนาฬิกาให้เป็นเวลาที่กำหนด

    ต้องปลอมตอน**สร้าง** ไม่ใช่ไปแก้ `created_at` ทีหลัง เพราะการแก้ค่าในแถว
    ทำให้ hash ของแถวนั้นใช้ไม่ได้ทันที — เทสต์จะกลายเป็นการตรวจสายที่พังไปแล้ว
    แทนที่จะตรวจ purge
    """
    monkeypatch.setattr(tz, "now_utc", lambda: when)
    with app.app_context():
        user = db.session.query(User).one()
        db.session.add(Category(name=name, user_id=user.id))
        db.session.commit()
    monkeypatch.undo()


@pytest.fixture
def aged_entries(app, monkeypatch):
    """สาย audit ที่หัวเก่า (400 วันก่อน) และท้ายใหม่ — เรียงตามเวลาจริงเหมือนของจริง"""
    old = tz.now_utc() - timedelta(days=400)
    monkeypatch.setattr(tz, "now_utc", lambda: old)
    with app.app_context():
        user = User(username="tester")
        user.set_password(PASSWORD)
        db.session.add(user)
        db.session.commit()
        db.session.add(Category(name="เก่า", user_id=user.id))
        db.session.commit()
    monkeypatch.undo()
    with app.app_context():
        user = db.session.query(User).one()
        db.session.add(Category(name="ใหม่", user_id=user.id))
        db.session.commit()
    return app


def test_expired_entries_are_purged_and_recent_ones_stay(aged_entries, app):
    before = len(_events(app))
    with app.app_context():
        removed = purge.purge_audit(days=365)
    assert removed >= 1
    remaining = _events(app)
    # ลบของเก่าไปแล้วเพิ่ม checkpoint หนึ่งแถว
    assert len(remaining) == before - removed + 1
    assert remaining[-1].event == audit.CHECKPOINT_EVENT


def test_the_chain_still_verifies_after_a_purge(aged_entries, app):
    with app.app_context():
        purge.purge_audit(days=365)
        assert audit.verify_chain() >= 1


def test_the_checkpoint_records_what_it_replaced(aged_entries, app):
    with app.app_context():
        expiring = purge._expired_audit(365)
        last_hash = expiring[-1].row_hash
        first_time = expiring[0].created_at.isoformat()
        removed = purge.purge_audit(days=365)
    checkpoint = _events(app, audit.CHECKPOINT_EVENT)[0]
    assert checkpoint.payload["purged_rows"] == removed
    # ต้องเป็น hash ของแถวสุดท้ายที่ถูกลบจริง ๆ ไม่งั้น verify หาจุดยึดไม่เจอ
    assert checkpoint.payload["last_purged_hash"] == last_hash
    assert checkpoint.payload["covers_from"] == first_time
    assert checkpoint.payload["covers_from"] <= checkpoint.payload["covers_to"]


def test_purge_only_removes_a_prefix_of_the_chain(app, user_id, monkeypatch):
    """แถวเก่าที่ตกค้างอยู่กลางสาย (นาฬิกาเครื่องถูกปรับย้อน) ต้องไม่ถูกเจาะทิ้ง

    ยอมเก็บเกินระยะไปก่อน ดีกว่าตัดกลางสายแล้ว verify ไม่ผ่านไปตลอดกาล
    """
    _seed_at(app, tz.now_utc() - timedelta(days=400), monkeypatch, "ย้อนเวลา")
    with app.app_context():
        # แถวเก่าอยู่ท้ายสาย (id มากสุด) เพราะ user.insert เกิดก่อนตามเวลาจริง
        assert purge._expired_audit(365) == []
        assert purge.purge_audit(days=365) == 0
        assert audit.verify_chain() == len(_events(app))


def test_the_checkpoint_is_chained_onto_what_it_replaced(client, app):
    """checkpoint ต้อง**ต่อจาก**แถวสุดท้ายที่ถูกลบ ไม่ใช่เริ่มสายใหม่

    ถ้าเขียน checkpoint หลังลบ (แทนที่จะก่อน) ตอนที่ล้างทั้งตาราง มันจะหาแถว
    ก่อนหน้าไม่เจอแล้วตั้งต้นที่ genesis — สายยังตรวจ "ผ่าน" แต่ไม่ผูกกับประวัติ
    ที่มันอ้างว่าแทนอีกต่อไป กลายเป็นแค่คำกล่าวอ้างในช่อง payload
    """
    client.post("/add", data={"title": "ซื้อนม"})
    with app.app_context():
        last_before = purge._expired_audit(0)[-1].row_hash
        purge.purge_audit(days=0)
        checkpoint = db.session.query(AuditEntry).one()
    assert checkpoint.prev_hash == last_before
    assert checkpoint.prev_hash != audit.GENESIS_HASH


def test_purging_every_entry_still_leaves_a_verifiable_chain(client, app):
    """ล้างทั้งตารางแล้ว checkpoint ต้องยังเกาะปลายสายเดิมได้"""
    client.post("/add", data={"title": "ซื้อนม"})
    with app.app_context():
        purge.purge_audit(days=0)
        rows = db.session.query(AuditEntry).all()
        assert len(rows) == 1
        assert rows[0].event == audit.CHECKPOINT_EVENT
        assert audit.verify_chain() == 1


def test_the_chain_keeps_verifying_after_writes_that_follow_a_purge(client, app):
    client.post("/add", data={"title": "ซื้อนม"})
    with app.app_context():
        purge.purge_audit(days=0)
    client.post("/add", data={"title": "ซื้อขนม"})
    with app.app_context():
        assert audit.verify_chain() >= 2


def test_a_forged_checkpoint_does_not_rescue_a_broken_chain(client, app):
    """checkpoint ปลอมที่ไม่ตรงกับแถวจริงต้องไม่ทำให้สายที่ขาดผ่านได้"""
    client.post("/add", data={"title": "ซื้อนม"})
    client.post("/add", data={"title": "ซื้อขนม"})
    rows = _events(app)
    with app.app_context():
        db.session.execute(text("DELETE FROM tdl_audit WHERE id = :id"), {"id": rows[0].id})
        db.session.commit()
        with pytest.raises(audit.ChainError):
            audit.verify_chain()


def test_dry_run_counts_audit_entries_without_deleting(client, app):
    client.post("/add", data={"title": "ซื้อนม"})
    before = len(_events(app))
    with app.app_context():
        result = purge.preview_expired(days=0, audit_days=0)
    assert result.audit_entries == before
    assert len(_events(app)) == before, "dry run ต้องไม่แตะอะไรเลย"


# ---------------------------------------------------------------- คำสั่ง CLI


def test_audit_verify_command_reports_ok(client, app):
    client.post("/add", data={"title": "ซื้อนม"})
    result = app.test_cli_runner().invoke(args=["audit-verify"])
    assert result.exit_code == 0
    assert "OK" in result.output


def test_audit_verify_command_fails_when_the_chain_is_broken(client, app):
    client.post("/add", data={"title": "ซื้อนม"})
    target = _events(app)[0].id
    with app.app_context():
        db.session.execute(
            text("UPDATE tdl_audit SET event = 'ของปลอม' WHERE id = :id"), {"id": target}
        )
        db.session.commit()
    result = app.test_cli_runner().invoke(args=["audit-verify"])
    assert result.exit_code != 0
    assert str(target) in result.output


def test_audit_log_command_shows_entries(client, app):
    client.post("/add", data={"title": "ซื้อนม"})
    result = app.test_cli_runner().invoke(args=["audit-log"])
    assert result.exit_code == 0
    assert "todo.insert" in result.output
    assert "ซื้อนม" not in result.output, "คำสั่งอ่าน log ก็ต้องไม่โชว์เนื้อหาของผู้ใช้"


def test_audit_log_command_on_an_empty_table(app):
    result = app.test_cli_runner().invoke(args=["audit-log"])
    assert result.exit_code == 0
    assert "No audit entries" in result.output


# ------------------------------------------- การเขียนขนานข้าม process (ADR 0032)


@pytest.mark.skipif(
    "sqlite" in os.environ.get("TEST_DATABASE_URL", "sqlite"),
    reason="SQLite ล็อกทั้งไฟล์ตอนเขียนอยู่แล้ว ข้อนี้พิสูจน์ได้เฉพาะยี่ห้อที่เขียนขนานได้จริง",
)
def test_two_connections_appending_at_once_do_not_collide(app):
    """**สองสายเขียนพร้อมกันต้องต่อคิว ไม่ใช่ชนกันแล้วตัวหลังตกไป** (ADR 0032)

    ด่านของ Phase 5 ที่ "พิสูจน์ว่า 2 replica ใช้ได้" ทดสอบแค่การอ่านกับ login
    — **ไม่เคยมีใครเขียนพร้อมกันจริง** load test ของ Phase 6 จึงเจอว่าการเขียน
    ล้ม 0.36–9.5% ด้วย 500 · เทสต์นี้คือบทเรียนนั้นที่กลายเป็นด่าน

    ใช้ **สอง connection จริง** ไม่ใช่เรียกฟังก์ชันสองครั้งติดกัน เพราะการเรียก
    ติดกันใน session เดียวไม่มีทางชนกันได้เลยตามนิยาม
    """
    import threading

    from app import db

    errors: list[Exception] = []
    started = threading.Barrier(2)

    def append(index):
        try:
            with app.app_context():
                started.wait(timeout=5)
                audit.record(f"test.concurrent{index}", table_name="tdl_user", row_id=index)
                db.session.commit()
        except Exception as error:  # noqa: BLE001 - เก็บไว้ให้ thread หลักตรวจ
            errors.append(error)

    threads = [threading.Thread(target=append, args=(index,)) for index in (1, 2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    assert not errors, f"การเขียนขนานล้ม: {errors}"
    with app.app_context():
        # `verify_chain()` คืนจำนวนแถวที่ตรวจแล้ว และ raise ถ้าสายขาด
        assert audit.verify_chain() >= 2, "สาย audit ต้องยังต่อกันถูกต้องหลังเขียนขนาน"
