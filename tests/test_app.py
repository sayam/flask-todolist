from app import db
from app.models import Category, Todo


def _add(client, title, category_id=None):
    data = {"title": title}
    if category_id is not None:
        data["category_id"] = str(category_id)
    return client.post("/add", data=data, follow_redirects=True)


def _first_todo_id(app, title):
    with app.app_context():
        return Todo.query.filter_by(title=title).first().id


def test_index_empty(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "ยังไม่มีงาน".encode() in resp.data


def test_add_todo(client):
    resp = _add(client, "ซื้อกาแฟ")
    assert resp.status_code == 200
    assert "ซื้อกาแฟ".encode() in resp.data


def test_add_rejects_blank_title(app, client):
    resp = client.post("/add", data={"title": "   "}, follow_redirects=True)
    assert resp.status_code == 200
    assert "กรุณาใส่ชื่องาน".encode() in resp.data
    with app.app_context():
        assert Todo.query.count() == 0


def test_toggle_todo(app, client):
    _add(client, "งานทดสอบ")
    todo_id = _first_todo_id(app, "งานทดสอบ")
    assert client.post(f"/toggle/{todo_id}", follow_redirects=True).status_code == 200
    with app.app_context():
        assert db.session.get(Todo, todo_id).done is True


def test_delete_todo(app, client):
    _add(client, "งานที่จะลบ")
    todo_id = _first_todo_id(app, "งานที่จะลบ")
    resp = client.post(f"/delete/{todo_id}", follow_redirects=True)
    assert resp.status_code == 200
    assert "งานที่จะลบ".encode() not in resp.data


def test_clear_completed(app, client):
    _add(client, "ซักผ้า")
    _add(client, "ล้างจาน")
    client.post(f"/toggle/{_first_todo_id(app, 'ซักผ้า')}", follow_redirects=True)

    resp = client.post("/clear-completed", follow_redirects=True)
    assert resp.status_code == 200
    assert "ซักผ้า".encode() not in resp.data
    assert "ล้างจาน".encode() in resp.data

    with app.app_context():
        assert Todo.query.filter_by(done=True).count() == 0
        assert [t.title for t in Todo.query.all()] == ["ล้างจาน"]


# --- แก้ไขงาน ---

def test_edit_todo_title(app, client):
    _add(client, "ชื่อเดิม")
    todo_id = _first_todo_id(app, "ชื่อเดิม")
    resp = client.post(
        f"/edit/{todo_id}", data={"title": "ชื่อใหม่"}, follow_redirects=True
    )
    assert resp.status_code == 200
    assert "ชื่อใหม่".encode() in resp.data
    assert "ชื่อเดิม".encode() not in resp.data


def test_edit_rejects_blank_title(app, client):
    _add(client, "ชื่อเดิม")
    todo_id = _first_todo_id(app, "ชื่อเดิม")
    client.post(f"/edit/{todo_id}", data={"title": "  "}, follow_redirects=True)
    with app.app_context():
        assert db.session.get(Todo, todo_id).title == "ชื่อเดิม"


def test_edit_sets_category(app, client, category_id):
    _add(client, "งานไม่มีหมวด")
    todo_id = _first_todo_id(app, "งานไม่มีหมวด")
    client.post(
        f"/edit/{todo_id}",
        data={"title": "งานไม่มีหมวด", "category_id": str(category_id)},
        follow_redirects=True,
    )
    with app.app_context():
        assert db.session.get(Todo, todo_id).category_id == category_id


# --- หมวดงาน ---

def test_add_category(app, client):
    resp = client.post(
        "/categories/add", data={"name": "งาน delivery"}, follow_redirects=True
    )
    assert resp.status_code == 200
    assert "งาน delivery".encode() in resp.data
    with app.app_context():
        assert Category.query.filter_by(name="งาน delivery").count() == 1


def test_add_duplicate_category_rejected(app, client, category_id):
    client.post(
        "/categories/add", data={"name": "งานส่วนตัว"}, follow_redirects=True
    )
    with app.app_context():
        assert Category.query.filter_by(name="งานส่วนตัว").count() == 1


def test_edit_category(app, client, category_id):
    client.post(
        f"/categories/edit/{category_id}",
        data={"name": "งานบ้าน"},
        follow_redirects=True,
    )
    with app.app_context():
        assert db.session.get(Category, category_id).name == "งานบ้าน"


def test_delete_category_keeps_todos(app, client, category_id):
    _add(client, "งานในหมวด", category_id=category_id)
    todo_id = _first_todo_id(app, "งานในหมวด")

    client.post(f"/categories/delete/{category_id}", follow_redirects=True)

    with app.app_context():
        assert db.session.get(Category, category_id) is None
        todo = db.session.get(Todo, todo_id)
        assert todo is not None, "ลบหมวดแล้วงานต้องไม่หายไปด้วย"
        assert todo.category_id is None


# --- auth ---

def test_index_requires_login(anon_client):
    resp = anon_client.get("/")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_login_with_wrong_password(app, user_id, anon_client):
    resp = anon_client.post(
        "/login", data={"username": "tester", "password": "ผิดแน่นอน"}
    )
    assert resp.status_code == 401


def test_logout(client):
    assert client.post("/logout").status_code == 302
    assert client.get("/").status_code == 302


# --- แยกข้อมูลระหว่าง user ---

def test_cannot_see_other_users_todos(app, client, other_client):
    _add(client, "ความลับของ tester")
    resp = other_client.get("/")
    assert "ความลับของ tester".encode() not in resp.data


def test_cannot_delete_other_users_todo(app, client, other_client):
    _add(client, "งานของ tester")
    todo_id = _first_todo_id(app, "งานของ tester")

    assert other_client.post(f"/delete/{todo_id}").status_code == 404
    with app.app_context():
        assert db.session.get(Todo, todo_id) is not None


def test_cannot_edit_other_users_todo(app, client, other_client):
    _add(client, "งานของ tester")
    todo_id = _first_todo_id(app, "งานของ tester")

    resp = other_client.post(f"/edit/{todo_id}", data={"title": "โดนแก้"})
    assert resp.status_code == 404
    with app.app_context():
        assert db.session.get(Todo, todo_id).title == "งานของ tester"


def test_clear_completed_only_touches_own_todos(app, client, other_client):
    _add(client, "งานเสร็จของ tester")
    done_id = _first_todo_id(app, "งานเสร็จของ tester")
    client.post(f"/toggle/{done_id}", follow_redirects=True)

    _add(other_client, "งานเสร็จของ intruder")
    other_id = _first_todo_id(app, "งานเสร็จของ intruder")
    other_client.post(f"/toggle/{other_id}", follow_redirects=True)

    other_client.post("/clear-completed", follow_redirects=True)

    with app.app_context():
        assert db.session.get(Todo, other_id) is None
        assert db.session.get(Todo, done_id) is not None, (
            "clear-completed ของคนอื่นต้องไม่ลบงานเรา"
        )


def test_cannot_assign_todo_to_other_users_category(app, client, other_client, category_id):
    resp = other_client.post(
        "/add",
        data={"title": "แอบใช้หมวดคนอื่น", "category_id": str(category_id)},
    )
    assert resp.status_code == 404
    with app.app_context():
        assert Todo.query.filter_by(title="แอบใช้หมวดคนอื่น").count() == 0
