"""org todo graph (ADR 0049) — privacy สองทิศ: ที่ประกาศว่าเห็นได้ต้องเห็น
และที่ประกาศว่าไม่ได้ต้อง**พิสูจน์ว่าไม่รั่ว**ผ่านทุกช่องทาง (เว็บ · API ·
สัญญาณ impact · ข้อความแจ้ง)
"""

import dataclasses
from datetime import timedelta

import pytest

from app import db, tz
from app.models import Team, Todo, TodoDependency, TodoShare, User
from app.services import ForbiddenError, NotFoundError, ValidationError
from app.services import dependencies as dependencies_service
from app.services import sharing as sharing_service
from app.services import teams as teams_service
from app.services.errors import ConflictError
from tests.conftest import PASSWORD


def _user(username, role="user"):
    person = User(username=username, role=role)
    person.set_password(PASSWORD)
    db.session.add(person)
    db.session.commit()
    return person


def _todo(owner, title, overdue=False):
    due = tz.now_utc() - timedelta(hours=3) if overdue else tz.now_utc() + timedelta(days=3)
    todo = Todo(title=title, user_id=owner.id, due_date=due)
    db.session.add(todo)
    db.session.commit()
    return todo


@pytest.fixture
def org(app):
    """admin หนึ่ง + สมาชิกวงสอง (somchai, malee) + คนนอกวง (frank) + วง alpha

    คืน id ทั้งหมด (ไม่ใช่ object) — fixture นี้ถูกใช้ยิง HTTP ด้วย จึงต้องปิด
    app context ก่อนคืนตามกับดักข้อ 2 ใน CLAUDE.md
    """
    with app.app_context():
        boss = _user("boss", role="admin")
        somchai = _user("somchai")
        malee = _user("malee")
        frank = _user("frank")
        team = teams_service.create_team(boss, "alpha")
        teams_service.add_member(boss, team.id, "somchai")
        teams_service.add_member(boss, team.id, "malee")
        return {
            "boss": boss.id,
            "somchai": somchai.id,
            "malee": malee.id,
            "frank": frank.id,
            "team": team.id,
        }


def _get(app, user_id):
    return db.session.get(User, user_id)


def _login(app, username):
    client = app.test_client()
    resp = client.post("/login", data={"username": username, "password": PASSWORD})
    assert resp.status_code == 302
    return client


# ---------------------------------------------------------------- วงเป็นของ admin


def test_only_admins_manage_teams(app, org):
    with app.app_context():
        somchai = _get(app, org["somchai"])
        with pytest.raises(ForbiddenError):
            teams_service.create_team(somchai, "shadow")
        with pytest.raises(ForbiddenError):
            teams_service.add_member(somchai, org["team"], "frank")


def test_the_admin_teams_page_needs_the_admin_role(app, org):
    client = _login(app, "somchai")
    assert client.get("/admin/teams").status_code == 403
    assert client.post("/admin/teams/add", data={"name": "shadow"}).status_code == 403


# ---------------------------------------------------------------- สี่ฟิลด์ที่แชร์


def test_the_shared_view_carries_exactly_the_four_allowed_fields(app):
    """โครงของ view คือสัญญา privacy — ฟิลด์ที่เพิ่มเข้ามาภายหลังต้องมาผ่านตาคนอ่าน ADR"""
    fields = {field.name for field in dataclasses.fields(sharing_service.SharedTodoView)}
    assert fields == {"todo_id", "title", "due_date", "is_done", "owner_username"}


def test_a_member_sees_a_shared_task_and_an_outsider_sees_no_team_at_all(app, org):
    with app.app_context():
        somchai = _get(app, org["somchai"])
        todo = _todo(somchai, "prepare quarterly numbers")
        sharing_service.share(somchai, todo.id, org["team"])

    member = _login(app, "malee")
    page = member.get(f"/teams/{org['team']}")
    assert page.status_code == 200
    assert "prepare quarterly numbers" in page.data.decode()

    outsider = _login(app, "frank")
    assert outsider.get(f"/teams/{org['team']}").status_code == 404, (
        "คนนอกวงต้องไม่รู้แม้แต่ว่าวงนี้มีอยู่ (ADR 0004)"
    )


def test_a_private_task_never_reaches_the_team_page(app, org):
    with app.app_context():
        somchai = _get(app, org["somchai"])
        shared = _todo(somchai, "the shared one")
        _todo(somchai, "the secret one")
        sharing_service.share(somchai, shared.id, org["team"])

    page = _login(app, "malee").get(f"/teams/{org['team']}").data.decode()
    assert "the shared one" in page
    assert "the secret one" not in page, "งาน private รั่วขึ้นหน้าวง"


def test_depending_on_an_unshared_task_answers_404_not_403(app, org):
    """probe ด้วย id มั่ว/ id งาน private ต้องแยกไม่ออกจาก id ที่ไม่มีจริง"""
    with app.app_context():
        somchai = _get(app, org["somchai"])
        malee = _get(app, org["malee"])
        mine = _todo(malee, "my own work")
        private = _todo(somchai, "private target")
        with pytest.raises(NotFoundError):
            dependencies_service.invite(malee, mine.id, private.id)
        with pytest.raises(NotFoundError):
            dependencies_service.invite(malee, mine.id, 999_999)


# ---------------------------------------------------------------- เชิญ → ยอมรับ


@pytest.fixture
def linked(app, org):
    """somchai แชร์งาน (เลยกำหนดแล้ว) · malee ขอพึ่ง · somchai ยอมรับ"""
    with app.app_context():
        somchai = _get(app, org["somchai"])
        malee = _get(app, org["malee"])
        target = _todo(somchai, "upstream deliverable", overdue=True)
        mine = _todo(malee, "downstream report")
        sharing_service.share(somchai, target.id, org["team"])
        dependency = dependencies_service.invite(malee, mine.id, target.id)
        dependencies_service.accept(somchai, dependency.id)
        return {**org, "target": target.id, "mine": mine.id, "dependency": dependency.id}


def test_an_invited_dependency_has_no_effect_until_accepted(app, org):
    with app.app_context():
        somchai = _get(app, org["somchai"])
        malee = _get(app, org["malee"])
        target = _todo(somchai, "late upstream", overdue=True)
        mine = _todo(malee, "waiting work")
        sharing_service.share(somchai, target.id, org["team"])
        dependencies_service.invite(malee, mine.id, target.id)
        assert dependencies_service.at_risk_todo_ids(malee) == set(), (
            "คำเชิญที่ยังไม่ถูกยอมรับส่งผลต่อ impact แล้ว — unilateral โดยพฤตินัย"
        )


def test_only_the_target_owner_can_accept(app, linked, org):
    with app.app_context():
        malee = _get(app, org["malee"])
        somchai = _get(app, org["somchai"])
        target = _todo(somchai, "another upstream", overdue=False)
        mine2 = _todo(malee, "another mine")
        sharing_service.share(somchai, target.id, org["team"])
        row = dependencies_service.invite(malee, mine2.id, target.id)
        with pytest.raises(NotFoundError):
            dependencies_service.accept(malee, row.id)  # คนขอเองยอมรับแทนไม่ได้
        with pytest.raises(NotFoundError):
            dependencies_service.accept(_get(app, org["frank"]), row.id)


def test_an_accepted_overdue_dependency_marks_my_todo_at_risk(app, linked):
    with app.app_context():
        malee = _get(app, linked["malee"])
        assert dependencies_service.at_risk_todo_ids(malee) == {linked["mine"]}

    page = _login(app, "malee").get("/").data.decode()
    assert "เสี่ยงจากงานที่พึ่ง" not in page  # ภาษา en เป็นค่าเริ่มต้น
    assert "At risk via dependencies" in page


def test_the_risk_badge_never_names_the_upstream_task(app, linked):
    """ป้าย impact บอกว่า "เสี่ยง" ได้ แต่ห้ามพกรายละเอียดของโซ่มาที่หน้า list"""
    page = _login(app, "malee").get("/").data.decode()
    assert "upstream deliverable" not in page


def test_risk_travels_through_a_chain_and_survives_cycles(app, org):
    """somchai พึ่ง malee ที่เลยกำหนด · boss พึ่ง somchai → boss เสี่ยงผ่านโซ่
    และวงวน dependency ต้องไม่ทำให้คำนวณค้าง"""
    with app.app_context():
        boss = _get(app, org["boss"])
        somchai = _get(app, org["somchai"])
        malee = _get(app, org["malee"])
        teams_service.add_member(boss, org["team"], "boss")

        late = _todo(malee, "late leaf", overdue=True)
        middle = _todo(somchai, "middle piece")
        top = _todo(boss, "final assembly")
        sharing_service.share(malee, late.id, org["team"])
        sharing_service.share(somchai, middle.id, org["team"])
        sharing_service.share(boss, top.id, org["team"])

        dependencies_service.accept(
            malee, dependencies_service.invite(somchai, middle.id, late.id).id
        )
        dependencies_service.accept(
            somchai, dependencies_service.invite(boss, top.id, middle.id).id
        )
        # ปิดวง: malee พึ่งงานของ boss — กราฟกลายเป็นวงกลม
        dependencies_service.accept(boss, dependencies_service.invite(malee, late.id, top.id).id)

        assert top.id in dependencies_service.at_risk_todo_ids(boss), "โซ่สองชั้นต้องส่งผล"


# ---------------------------------------------------------------- การตัดตามการมองเห็น


def test_unsharing_cuts_dependencies_that_lose_sight(app, linked):
    with app.app_context():
        somchai = _get(app, linked["somchai"])
        malee = _get(app, linked["malee"])
        sharing_service.unshare(somchai, linked["target"], linked["team"])
        assert dependencies_service.dependencies_of(malee, linked["mine"]) == []
        assert dependencies_service.at_risk_todo_ids(malee) == set()
        assert sharing_service.severed_recently(malee) == 1


def test_a_second_team_keeps_the_dependency_alive(app, linked):
    with app.app_context():
        boss = _get(app, linked["boss"])
        somchai = _get(app, linked["somchai"])
        malee = _get(app, linked["malee"])
        second = teams_service.create_team(boss, "beta")
        teams_service.add_member(boss, second.id, "somchai")
        teams_service.add_member(boss, second.id, "malee")
        sharing_service.share(somchai, linked["target"], second.id)

        sharing_service.unshare(somchai, linked["target"], linked["team"])
        assert len(dependencies_service.dependencies_of(malee, linked["mine"])) == 1, (
            "ยังมองเห็นผ่านวงที่สอง — dependency ต้องไม่ถูกตัด"
        )


def test_removing_a_member_severs_their_dependencies(app, linked):
    with app.app_context():
        boss = _get(app, linked["boss"])
        malee = _get(app, linked["malee"])
        teams_service.remove_member(boss, linked["team"], linked["malee"])
        assert dependencies_service.dependencies_of(malee, linked["mine"]) == []


def test_the_severed_notice_counts_without_naming_anything(app, linked):
    with app.app_context():
        somchai = _get(app, linked["somchai"])
        sharing_service.unshare(somchai, linked["target"], linked["team"])

    page = _login(app, "malee").get("/teams").data.decode()
    assert "unshared recently" in page
    assert "upstream deliverable" not in page, "ชื่องานที่เลิกแชร์แล้วห้ามโผล่ — สิทธิ์การมองเห็นจบไปพร้อมการแชร์"


def test_closing_the_account_cuts_both_directions(app, linked):
    from app.services import personal_data

    with app.app_context():
        somchai = _get(app, linked["somchai"])
        malee = _get(app, linked["malee"])
        personal_data.close_account(somchai, actor=somchai)
        assert dependencies_service.dependencies_of(malee, linked["mine"]) == [], (
            "เจ้าของงานปลายทางปิดบัญชี — dependency ที่ชี้มาต้องถูกตัด"
        )


# ---------------------------------------------------------------- ฝั่ง API แบบ additive


def test_the_api_reports_is_at_risk_for_own_todos(app, linked):
    from app.services import tokens as tokens_service

    with app.app_context():
        malee = _get(app, linked["malee"])
        secret = tokens_service.issue(malee, "graph-test", 1)
    client = app.test_client()
    listing = client.get("/api/v1/todos", headers={"Authorization": f"Bearer {secret}"})
    assert listing.status_code == 200
    by_title = {item["title"]: item for item in listing.get_json()}
    assert by_title["downstream report"]["is_at_risk"] is True


def test_export_lists_sharing_but_only_the_owners_side(app, linked):
    from app.services import personal_data

    with app.app_context():
        malee = _get(app, linked["malee"])
        data = personal_data.export(malee)
        assert data["sharing"]["teams"] == ["alpha"]
        assert data["sharing"]["dependencies"][0]["depends_on_todo_id"] == linked["target"]
        flattened = str(data)
        assert "upstream deliverable" not in flattened, (
            "export ของเราต้องไม่พกชื่องานของคนอื่น (เกินสี่ฟิลด์ที่ประกาศ และนี่ไม่ใช่ช่องดูดข้อมูลวง)"
        )


# ---------------------------------------------------------------- กติกาซ้ำ/สถานะ


def test_double_share_and_double_accept_are_conflicts(app, linked):
    with app.app_context():
        somchai = _get(app, linked["somchai"])
        with pytest.raises(ConflictError):
            sharing_service.share(somchai, linked["target"], linked["team"])
        with pytest.raises(ConflictError):
            dependencies_service.accept(somchai, linked["dependency"])


def test_a_task_cannot_depend_on_the_owners_own_task(app, org):
    with app.app_context():
        somchai = _get(app, org["somchai"])
        one = _todo(somchai, "left hand")
        two = _todo(somchai, "right hand")
        sharing_service.share(somchai, two.id, org["team"])
        with pytest.raises(ValidationError):
            dependencies_service.invite(somchai, one.id, two.id)


def test_reinviting_after_withdrawal_starts_as_invited_again(app, linked):
    with app.app_context():
        malee = _get(app, linked["malee"])
        dependencies_service.withdraw(malee, linked["dependency"])
        row = dependencies_service.invite(malee, linked["mine"], linked["target"])
        assert row.status == "invited", "การยอมรับครั้งก่อนต้องไม่ติดมากับคำเชิญรอบใหม่"
        assert row.accepted_at is None


# ---------------------------------------------------------------- เส้นทางเว็บจริง


def test_the_full_story_through_the_web(app, org):
    """เดินทั้งเรื่องผ่าน HTTP: แชร์ → เห็นในวง → ขอพึ่ง → ยอมรับ → ป้ายเสี่ยง
    → เลิกแชร์ → ป้ายหาย + ประกาศแจ้ง — พฤติกรรมเดียวกับที่ service พิสูจน์แล้ว
    แต่คราวนี้ผ่าน adapter จริงทุกชั้น (ฟอร์ม · redirect · flash)"""
    with app.app_context():
        somchai_id = org["somchai"]
        target = _todo(_get(app, somchai_id), "web upstream", overdue=True)
        target_id = target.id
        mine = _todo(_get(app, org["malee"]), "web downstream")
        mine_id = mine.id

    somchai = _login(app, "somchai")
    resp = somchai.post(f"/share/{target_id}", data={"team_id": org["team"]})
    assert resp.status_code == 302

    malee = _login(app, "malee")
    page = malee.get(f"/teams/{org['team']}").data.decode()
    assert "web upstream" in page

    resp = malee.post(
        "/dependencies/add",
        data={"todo_id": mine_id, "depends_on": target_id, "team_id": org["team"]},
    )
    assert resp.status_code == 302
    assert f"/teams/{org['team']}" in resp.headers["Location"]

    # เจ้าของปลายทางเห็นคำเชิญ: ใครขอ + งานไหน*ของเรา* — ชื่องานของฝั่งขอ
    # เป็น private ของเขา ต้องไม่โผล่บนหน้าเรา (ADR 0049 ข้อ 1)
    teams_page = somchai.get("/teams").data.decode()
    assert "malee" in teams_page
    assert "web upstream" in teams_page
    assert "web downstream" not in teams_page, "ชื่องาน private ของคนขอรั่วมาหน้าเจ้าของปลายทาง"
    with app.app_context():
        dependency_id = db.session.query(TodoDependency).one().id
    assert somchai.post(f"/dependencies/{dependency_id}/accept").status_code == 302

    assert "At risk via dependencies" in malee.get("/").data.decode()

    # เจ้าของเลิกแชร์ — ป้ายต้องหาย และหน้า /teams ของ malee ขึ้นประกาศแจ้ง
    assert somchai.post(f"/unshare/{target_id}", data={"team_id": org["team"]}).status_code == 302
    assert "At risk via dependencies" not in malee.get("/").data.decode()
    assert "unshared recently" in malee.get("/teams").data.decode()


def test_the_web_decline_and_withdraw_paths(app, org):
    with app.app_context():
        somchai = _get(app, org["somchai"])
        malee = _get(app, org["malee"])
        target = _todo(somchai, "declinable upstream")
        mine = _todo(malee, "withdrawable downstream")
        sharing_service.share(somchai, target.id, org["team"])
        first = dependencies_service.invite(malee, mine.id, target.id)
        first_id, mine_id, target_id = first.id, mine.id, target.id

    owner = _login(app, "somchai")
    assert owner.post(f"/dependencies/{first_id}/decline").status_code == 302

    with app.app_context():
        malee = _get(app, org["malee"])
        second = dependencies_service.invite(malee, mine_id, target_id)
        second_id = second.id
    depender = _login(app, "malee")
    resp = depender.post(f"/dependencies/{second_id}/withdraw", data={"todo_id": mine_id})
    assert resp.status_code == 302
    assert f"/edit/{mine_id}" in resp.headers["Location"]
    # เมื่อไม่ส่ง todo_id มา ต้องพากลับหน้า teams (กิ่ง fallback ของ redirect)
    resp = depender.post(f"/dependencies/{second_id}/withdraw")
    assert resp.status_code == 404, "แถวถูกถอนไปแล้ว — ถอนซ้ำต้อง 404 ไม่ใช่เงียบ"


def test_the_edit_page_shows_sharing_and_dependency_sections(app, org):
    with app.app_context():
        somchai = _get(app, org["somchai"])
        malee = _get(app, org["malee"])
        target = _todo(somchai, "section upstream")
        mine = _todo(malee, "section downstream")
        sharing_service.share(somchai, target.id, org["team"])
        dependencies_service.invite(malee, mine.id, target.id)
        mine_id = mine.id

    page = _login(app, "malee").get(f"/edit/{mine_id}").data.decode()
    assert "section upstream" in page, "รายการที่งานนี้พึ่งต้องโผล่บนหน้าแก้งาน"
    assert "waiting for acceptance" in page


def test_web_error_paths_flash_instead_of_crashing(app, org):
    client = _login(app, "somchai")
    with app.app_context():
        mine = _todo(_get(app, org["somchai"]), "errand")
        mine_id = mine.id
    # team_id ไม่ใช่เลข → flash ไม่ใช่ 500 · วงที่ไม่ได้อยู่ → 404
    assert client.post(f"/share/{mine_id}", data={"team_id": "x"}).status_code == 302
    assert client.post(f"/share/{mine_id}", data={"team_id": "999"}).status_code == 404
    assert client.post(f"/unshare/{mine_id}", data={"team_id": "999"}).status_code == 404
    assert client.post("/share/999999", data={"team_id": "1"}).status_code == 404
    resp = client.post("/dependencies/add", data={"todo_id": "x", "depends_on": "1"})
    assert resp.status_code == 302, "ค่าที่ย่อยไม่ได้ = flash แล้วพากลับ ไม่ใช่ 500"
    assert client.post("/dependencies/999999/accept").status_code == 404
    assert client.post("/dependencies/999999/decline").status_code == 404


def test_the_nav_shows_teams_only_to_members(app, org):
    member_page = _login(app, "somchai").get("/").data.decode()
    outsider_page = _login(app, "frank").get("/").data.decode()
    assert "/teams" in member_page
    assert "/teams" not in outsider_page, "คนที่ไม่อยู่วงไหนเลยไม่ควรเห็นเมนูเปล่า"


# ---------------------------------------------------------------- หน้า admin จริง


def test_the_admin_manages_teams_through_the_page(app, org):
    boss = _login(app, "boss")
    assert boss.get("/admin/teams").status_code == 200

    resp = boss.post("/admin/teams/add", data={"name": "beta"}, follow_redirects=True)
    assert "beta" in resp.data.decode()
    with app.app_context():
        beta_id = db.session.query(Team).filter_by(name="beta").one().id

    assert (
        boss.post(f"/admin/teams/{beta_id}/members", data={"username": "frank"}).status_code == 302
    )
    # ชื่อที่ไม่มีจริง = flash ไม่ใช่ 404 (ความผิดของฟอร์ม ไม่ใช่ URL) · วงผี = 404
    resp = boss.post(
        f"/admin/teams/{beta_id}/members", data={"username": "nobody"}, follow_redirects=True
    )
    assert resp.status_code == 200
    assert boss.post("/admin/teams/99999/members", data={"username": "frank"}).status_code == 404

    assert boss.post(f"/admin/teams/{beta_id}/members/{org['frank']}/remove").status_code == 302
    assert boss.post(f"/admin/teams/{beta_id}/members/{org['frank']}/remove").status_code == 404

    assert boss.post(f"/admin/teams/{beta_id}/delete").status_code == 302
    assert boss.post(f"/admin/teams/{beta_id}/delete").status_code == 404


def test_team_names_and_memberships_revive_instead_of_colliding(app, org):
    """unique constraint ครอบแถวที่ซ่อนอยู่ — สร้าง/เพิ่มซ้ำหลังลบต้องคืนชีพ ไม่ระเบิด"""
    with app.app_context():
        boss = _get(app, org["boss"])
        with pytest.raises(ConflictError):
            teams_service.create_team(boss, "alpha")
        with pytest.raises(ValidationError):
            teams_service.create_team(boss, "   ")
        teams_service.delete_team(boss, org["team"])
        revived = teams_service.create_team(boss, "alpha")
        assert revived.id == org["team"], "ชื่อเดิมหลังลบต้องคืนชีพแถวเดิม"

        member = teams_service.add_member(boss, revived.id, "somchai")
        with pytest.raises(ConflictError):
            teams_service.add_member(boss, revived.id, "somchai")
        teams_service.remove_member(boss, revived.id, member.user_id)
        again = teams_service.add_member(boss, revived.id, "somchai")
        assert again.id == member.id

        assert [team.name for team in teams_service.list_teams(boss)] == ["alpha"]
        with pytest.raises(NotFoundError):
            teams_service.get_team(boss, 99999)
        with pytest.raises(NotFoundError):
            teams_service.remove_member(boss, revived.id, org["frank"])


def test_sharing_revives_and_deleting_a_team_severs_everything(app, linked):
    with app.app_context():
        boss = _get(app, linked["boss"])
        somchai = _get(app, linked["somchai"])
        malee = _get(app, linked["malee"])

        # เมื่อแชร์ซ้ำหลังเลิกแชร์ แถวเดิมต้องถูกคืนชีพ
        sharing_service.unshare(somchai, linked["target"], linked["team"])
        revived = sharing_service.share(somchai, linked["target"], linked["team"])
        with pytest.raises(NotFoundError):
            sharing_service.unshare(somchai, linked["target"], 99999)

        # ต่อ dependency ใหม่ แล้วลบทั้งวง — ทุกอย่างต้องถูกตัด
        row = dependencies_service.invite(malee, linked["mine"], linked["target"])
        dependencies_service.accept(somchai, row.id)
        teams_service.delete_team(boss, linked["team"])
        assert dependencies_service.dependencies_of(malee, linked["mine"]) == []
        assert revived.is_deleted


def test_visible_shared_todo_rejects_owner_and_stranger_views(app, linked):
    with app.app_context():
        somchai = _get(app, linked["somchai"])
        malee = _get(app, linked["malee"])
        frank = _get(app, linked["frank"])
        view = sharing_service.visible_shared_todo(malee, linked["target"])
        assert view.title == "upstream deliverable"
        with pytest.raises(NotFoundError):
            sharing_service.visible_shared_todo(frank, linked["target"])
        with pytest.raises(NotFoundError):
            # เจ้าของใช้เส้นทางของเจ้าของ (get_todo) ไม่ใช่ view ของวง
            sharing_service.visible_shared_todo(somchai, linked["target"])
        with pytest.raises(ConflictError):
            dependencies_service.invite(malee, linked["mine"], linked["target"])


def test_purge_erases_soft_deleted_graph_rows_for_real(app, linked):
    from app.purge import preview_expired, purge_expired

    with app.app_context():
        somchai = _get(app, linked["somchai"])
        sharing_service.unshare(somchai, linked["target"], linked["team"])
        # ย้อนเวลาให้พ้นระยะ 30 วัน
        for row in (
            db.session.query(TodoShare)
            .execution_options(include_deleted=True)
            .filter(TodoShare.deleted_at.is_not(None))
            .all()
        ):
            row.deleted_at = tz.now_utc() - timedelta(days=45)
        for row in (
            db.session.query(TodoDependency)
            .execution_options(include_deleted=True)
            .filter(TodoDependency.deleted_at.is_not(None))
            .all()
        ):
            row.deleted_at = tz.now_utc() - timedelta(days=45)
        db.session.commit()

        assert preview_expired().graph_rows == 2
        result = purge_expired()
        assert result.graph_rows == 2
        leftovers = (
            db.session.query(TodoShare).execution_options(include_deleted=True).count()
            + db.session.query(TodoDependency).execution_options(include_deleted=True).count()
        )
        assert leftovers == 0, "แถว graph ที่พ้นระยะต้องถูกลบจริง ไม่ใช่ซ่อนต่อ"


def test_the_leftover_corners(app, linked):
    """กิ่งเล็กที่เหลือ: repr ของวง · can_see ของเจ้าของ/ของที่ไม่มี · วงวนล้วน
    ที่ไม่มีใครเลยกำหนด · เป้าหมายที่ถูกลบทิ้งระหว่างมี dependency ค้าง"""
    with app.app_context():
        somchai = _get(app, linked["somchai"])
        malee = _get(app, linked["malee"])

        assert "alpha" in repr(db.session.get(Team, linked["team"]))
        assert sharing_service.can_see_todo(somchai, linked["target"]) is True  # เจ้าของ
        assert sharing_service.can_see_todo(somchai, 999_999) is False

        # วงวนที่ไม่มีใครเลยกำหนดเลย — ต้องจบและไม่เสี่ยง (กิ่ง trail-return)
        a = _todo(somchai, "cycle a")
        b = _todo(malee, "cycle b")
        sharing_service.share(somchai, a.id, linked["team"])
        sharing_service.share(malee, b.id, linked["team"])
        dependencies_service.accept(somchai, dependencies_service.invite(malee, b.id, a.id).id)
        dependencies_service.accept(malee, dependencies_service.invite(somchai, a.id, b.id).id)
        assert a.id not in dependencies_service.at_risk_todo_ids(somchai)
        assert b.id not in dependencies_service.at_risk_todo_ids(malee)

        # เจ้าของลบงานปลายทางทิ้ง (soft delete) ทั้งที่ dependency ยังอยู่ —
        # โซ่ต้องมองว่าปลายทางหายไป ไม่ใช่ crash และไม่ใช่ยังเสี่ยงต่อ
        from app.services import todos as todos_service

        todos_service.delete_todo(somchai, linked["target"])
        assert dependencies_service.at_risk_todo_ids(malee) == set()


def test_the_remaining_web_fallbacks(app, org):
    with app.app_context():
        somchai = _get(app, org["somchai"])
        malee = _get(app, org["malee"])
        target = _todo(somchai, "fallback upstream")
        mine = _todo(malee, "fallback downstream")
        sharing_service.share(somchai, target.id, org["team"])
        row = dependencies_service.invite(malee, mine.id, target.id)
        dependencies_service.accept(somchai, row.id)
        row_id, mine_id, target_id = row.id, mine.id, target.id

    somchai_client = _login(app, "somchai")
    # unshare ด้วย team_id ที่ย่อยไม่ได้ = flash ไม่ใช่ 500
    assert somchai_client.post(f"/unshare/{target_id}", data={"team_id": "x"}).status_code == 302
    # accept ซ้ำผ่านเว็บ = flash (ConflictError) ไม่ใช่ 500
    resp = somchai_client.post(f"/dependencies/{row_id}/accept", follow_redirects=True)
    assert resp.status_code == 200

    malee_client = _login(app, "malee")
    # ขอพึ่งซ้ำผ่านเว็บโดยไม่ส่ง team_id = flash แล้วกลับหน้า /teams (กิ่ง fallback)
    resp = malee_client.post(
        "/dependencies/add", data={"todo_id": mine_id, "depends_on": target_id}
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/teams")
    # withdraw โดยไม่ส่ง todo_id = กลับหน้า /teams
    resp = malee_client.post(f"/dependencies/{row_id}/withdraw")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/teams")


def test_probing_an_invisible_target_through_the_web_is_404(app, org):
    with app.app_context():
        somchai = _get(app, org["somchai"])
        malee = _get(app, org["malee"])
        _private = _todo(somchai, "web private target")
        mine = _todo(malee, "web probe source")
        private_id, mine_id = _private.id, mine.id
    client = _login(app, "malee")
    resp = client.post("/dependencies/add", data={"todo_id": mine_id, "depends_on": private_id})
    assert resp.status_code == 404, "probe งาน private ผ่านเว็บต้อง 404 (ADR 0004)"


def test_two_dependents_on_the_same_late_target_are_both_at_risk(app, linked):
    """สองงานพึ่งเป้าเดียวกัน — ผลต้องเท่ากันทั้งคู่ (เส้นทาง cache ของโซ่)"""
    with app.app_context():
        somchai = _get(app, linked["somchai"])
        malee = _get(app, linked["malee"])
        second = _todo(malee, "second downstream")
        row = dependencies_service.invite(malee, second.id, linked["target"])
        dependencies_service.accept(somchai, row.id)
        assert dependencies_service.at_risk_todo_ids(malee) == {linked["mine"], second.id}


def test_every_admin_teams_action_rejects_regular_users(app, org):
    """403 ทุกปุ่ม ไม่ใช่แค่หน้า list — การซ่อนเมนูไม่ใช่การกันสิทธิ์"""
    client = _login(app, "malee")
    assert client.post(f"/admin/teams/{org['team']}/delete").status_code == 403
    assert (
        client.post(f"/admin/teams/{org['team']}/members", data={"username": "frank"}).status_code
        == 403
    )
    assert (
        client.post(f"/admin/teams/{org['team']}/members/{org['somchai']}/remove").status_code
        == 403
    )


def test_admin_form_conflicts_flash_instead_of_crashing(app, org):
    boss = _login(app, "boss")
    resp = boss.post("/admin/teams/add", data={"name": "alpha"}, follow_redirects=True)
    assert resp.status_code == 200, "ชื่อวงซ้ำ = flash แล้วกลับหน้าเดิม ไม่ใช่ 500"
    resp = boss.post(
        f"/admin/teams/{org['team']}/members", data={"username": "somchai"}, follow_redirects=True
    )
    assert resp.status_code == 200, "สมาชิกซ้ำ = flash แล้วกลับหน้าเดิม ไม่ใช่ 500"
