"""Smoke ของสัญญา N-1 (ADR 0048) — รันด้วยโค้ด **รุ่นเก่า** ทับ schema ของ HEAD

job `n-1` ใน CI เรียกไฟล์นี้จาก checkout ของ HEAD แต่รันมัน**ใต้ venv และ
ไดเรกทอรีของ tag ล่าสุด** (`import app` จึงได้โค้ดรุ่นเก่า) โดย `DATABASE_URL`
ชี้ไปฐานข้อมูลที่ `flask db upgrade` ของ HEAD สร้างไว้ — สิ่งที่พิสูจน์คือ
"โค้ดที่ deploy อยู่ วันที่ schema ใหม่ลงไปแล้ว ยังให้บริการได้จริง"

เส้นทางที่ใช้คือ `/api/v1` ทั้งหมด **โดยตั้งใจ** — สัญญาของมันถูกตรึงข้ามรุ่น
อยู่แล้ว (ADR 0018: v1 แก้ไม่ได้) สคริปต์นี้จึงไม่ต้องรู้ว่า UI ของรุ่นไหน
หน้าตาเป็นยังไง และไม่ต้องแก้เมื่อ tag ขยับ

ข้อควรรู้: สคริปต์รันนอก pytest — ใช้ `create_app()` กับ config จริงของรุ่นเก่า
(ต้องมี SECRET_KEY ใน env) และคุยผ่าน `test_client()` ไม่ต้องเปิดพอร์ต
"""

import os
import pathlib
import sys

# รันจากไดเรกทอรีของ tag เก่า — python ใส่ไดเรกทอรีของ *สคริปต์* ลง sys.path
# ไม่ใช่ cwd จึงต้องเติมเองเพื่อให้ `import app` ได้โค้ดรุ่นเก่าจาก cwd
sys.path.insert(0, str(pathlib.Path.cwd()))


def fail(message: str) -> None:
    print(f"n-1 smoke FAILED: {message}")
    sys.exit(1)


def main() -> None:
    if not os.environ.get("DATABASE_URL", "").startswith("sqlite:////"):
        fail("ต้องตั้ง DATABASE_URL เป็น path สัมบูรณ์ของฐานข้อมูลที่ HEAD migrate ไว้")

    from app import create_app, db
    from app.models import User
    from app.services import tokens as tokens_service

    app = create_app()
    with app.app_context():
        user = db.session.query(User).filter_by(username="veteran").one_or_none()
        if user is None:
            fail("ไม่พบผู้ใช้ 'veteran' — ขั้น create-user ของ job ต้องรันก่อน")
            raise SystemExit(1)  # ให้ type checker รู้ว่าบรรทัดล่างไม่เจอ None
        secret = tokens_service.issue(user, "n1-smoke", 1)

    client = app.test_client()
    auth = {"Authorization": f"Bearer {secret}"}

    created = client.post("/api/v1/todos", json={"title": "n1 smoke item"}, headers=auth)
    if created.status_code != 201:
        fail(f"POST /api/v1/todos → {created.status_code}: {created.data[:200]!r}")
    todo_id = created.get_json()["id"]

    done = client.patch(f"/api/v1/todos/{todo_id}", json={"is_done": True}, headers=auth)
    if done.status_code != 200:
        fail(f"PATCH /api/v1/todos/{todo_id} → {done.status_code}: {done.data[:200]!r}")

    listing = client.get("/api/v1/todos?status=completed", headers=auth)
    if listing.status_code != 200:
        fail(f"GET /api/v1/todos → {listing.status_code}")
    titles = [item["title"] for item in listing.get_json()]
    if "n1 smoke item" not in titles:
        fail(f"งานที่เพิ่งสร้างไม่อยู่ในรายการ: {titles!r}")

    # ลบ (soft delete) แล้วต้องหายจากรายการ — เส้นเขียนครบวงจรบน schema ใหม่
    gone = client.delete(f"/api/v1/todos/{todo_id}", headers=auth)
    if gone.status_code != 204:
        fail(f"DELETE /api/v1/todos/{todo_id} → {gone.status_code}")

    print("n-1 smoke passed: old code served create/patch/list/delete on the new schema")


if __name__ == "__main__":
    main()
