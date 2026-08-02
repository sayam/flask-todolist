def test_index_empty(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "ยังไม่มีงาน".encode() in resp.data


def test_add_todo(client):
    resp = client.post("/add", data={"title": "ซื้อกาแฟ"}, follow_redirects=True)
    assert resp.status_code == 200
    assert "ซื้อกาแฟ".encode() in resp.data


def test_toggle_todo(app, client):
    client.post("/add", data={"title": "งานทดสอบ"}, follow_redirects=True)
    from app.models import Todo
    with app.app_context():
        todo_id = Todo.query.first().id
    resp = client.post(f"/toggle/{todo_id}", follow_redirects=True)
    assert resp.status_code == 200


def test_delete_todo(app, client):
    client.post("/add", data={"title": "งานที่จะลบ"}, follow_redirects=True)
    from app.models import Todo
    with app.app_context():
        todo_id = Todo.query.first().id
    resp = client.post(f"/delete/{todo_id}", follow_redirects=True)
    assert resp.status_code == 200
    assert "งานที่จะลบ".encode() not in resp.data


def test_clear_completed(app, client):
    client.post("/add", data={"title": "ซักผ้า"}, follow_redirects=True)
    client.post("/add", data={"title": "ล้างจาน"}, follow_redirects=True)

    from app.models import Todo
    with app.app_context():
        done_id = Todo.query.filter_by(title="ซักผ้า").first().id
    client.post(f"/toggle/{done_id}", follow_redirects=True)

    resp = client.post("/clear-completed", follow_redirects=True)
    assert resp.status_code == 200
    assert "ซักผ้า".encode() not in resp.data
    assert "ล้างจาน".encode() in resp.data

    with app.app_context():
        assert Todo.query.filter_by(done=True).count() == 0
        remaining = Todo.query.all()
        assert [t.title for t in remaining] == ["ล้างจาน"]
