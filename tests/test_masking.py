"""masking ของหน้า admin — ทุกคอลัมน์ถูกตัดสิน และหลวมกว่าชั้นข้อมูลไม่ได้ (ADR 0045)

สามชั้นที่ตรวจ:

1. **partition** — ทุกคอลัมน์ใน metadata มีคำตัดสิน (แบบแผน `NOT_EXPORTED`
   ของ ADR 0034: เพิ่มคอลัมน์แล้วต้องกลับมาตอบ ไม่ใช่หลุดเงียบ ๆ)
2. **ทิศเดียวกับชั้นข้อมูล** — เทียบกับชั้นที่ parse จาก
   `docs/DATA-CLASSIFICATION.md`: เข้มกว่าได้ หลวมกว่าต้องอยู่ใน `EXCEPTIONS`
   พร้อมเหตุผล (เอกสารเป็นแหล่งของ*ชั้น* โค้ดเป็นแหล่งของ*คำตัดสิน* เทสต์นี้
   บังคับให้สองอย่างสอดคล้อง — ทะเบียนสองที่ที่ถูกบังคับ ไม่ใช่เขียนคู่ขนาน)
3. **พฤติกรรมจริงบนหน้า** — ชื่อจริงไม่โผล่เต็มจนกว่าจะ unmask · unmask ลง
   audit · คนที่ไม่ใช่ admin ทำไม่ได้ · template ไม่แตะค่าดิบเอง
"""

import pathlib
import re

from app import db
from app.audit import AuditEntry
from app.models import Category, Todo, User  # noqa: F401  ต้อง import ให้ metadata ครบ
from app.services import masking
from app.services import roles as roles_service
from tests.conftest import PASSWORD

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "DATA-CLASSIFICATION.md"

#: ชั้น → คำตัดสินที่หลวมที่สุดที่ยอมได้ (ADR 0045) · ลำดับความเข้ม
STRICTNESS = {masking.HIDDEN: 2, masking.MASKED: 1, masking.VISIBLE: 0}
FLOOR_BY_CLASS = {"C1": masking.HIDDEN, "C2": masking.MASKED, "C3": masking.HIDDEN}


def _fields_of_class(label):
    """ชื่อใน backtick ของแถวชั้นนั้นในตารางชั้นข้อมูล — เอกสารคือแหล่งของชั้น"""
    text = DOC.read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.startswith(f"| **{label}**"))
    return set(re.findall(r"`([^`]+)`", row))


def _class_of(table, column):
    """ชั้นของคอลัมน์ตามเอกสาร — C1 ก่อน (เข้มสุด) · ไม่เจอ = ไม่ใช่ชั้นอ่อนไหว"""
    qualified = f"{table}.{column}"
    for label in ("C1", "C2", "C3"):
        fields = _fields_of_class(label)
        if qualified in fields or column in fields:
            return label
    return None


def test_every_column_has_a_masking_decision(app):
    """partition เต็ม — คอลัมน์ที่ยังไม่ถูกตัดสินคือคอลัมน์ที่จะโผล่บนจอโดยไม่มีใครคิด"""
    with app.app_context():
        undecided = [
            f"{table.name}.{column.name}"
            for table in db.metadata.sorted_tables
            for column in table.columns
            if masking.decision_for(table.name, column.name) is None
        ]
    assert not undecided, (
        "คอลัมน์ที่ยังไม่มีคำตัดสิน masking (เพิ่มใน app/services/masking.py):\n" + "\n".join(undecided)
    )


def test_no_decision_is_looser_than_the_data_class(app):
    """C1/C3 ต้องอย่างน้อย hidden · C2 อย่างน้อย masked — หลวมกว่าต้องมีเหตุผลใน EXCEPTIONS"""
    with app.app_context():
        offending = []
        for table in db.metadata.sorted_tables:
            for column in table.columns:
                label = _class_of(table.name, column.name)
                if label is None:
                    continue
                decision = masking.decision_for(table.name, column.name)
                floor = FLOOR_BY_CLASS[label]
                key = f"{table.name}.{column.name}"
                if STRICTNESS[decision] < STRICTNESS[floor] and key not in masking.EXCEPTIONS:
                    offending.append(f"{key}: ชั้น {label} แต่ตัดสิน {decision!r}")
    assert not offending, "\n  ".join(["คำตัดสินที่หลวมกว่าชั้นข้อมูลโดยไม่มีเหตุผล:", *offending])


def test_every_exception_carries_a_reason_and_a_real_column(app):
    """EXCEPTIONS ที่ไม่มีเหตุผล หรือชี้คอลัมน์ที่ไม่มีจริง = ช่องหลบที่ไม่มีใครเห็น"""
    with app.app_context():
        real = {
            f"{table.name}.{column.name}"
            for table in db.metadata.sorted_tables
            for column in table.columns
        }
    for key, reason in masking.EXCEPTIONS.items():
        assert key in real, f"EXCEPTIONS ชี้คอลัมน์ที่ไม่มีจริง: {key}"
        assert len(reason.strip()) >= 20, f"{key}: เหตุผลสั้นจนไม่ใช่เหตุผล"


def test_masked_value_shows_only_the_first_character():
    assert masking.masked("Somchai") == "S•••"
    assert masking.masked("") == "—"
    assert masking.masked(None) == "—"


def test_hidden_never_leaves_even_when_unmasked():
    """`hidden` ไม่มีทางออกจอ — unmask เปิดได้แค่ระดับ `masked` (ADR 0045)"""
    assert masking.display("tdl_user", "password_hash", "x", unmasked=True) is None
    assert masking.display("tdl_todo", "title", "ความลับ", unmasked=True) is None
    assert masking.display("tdl_user", "first_name", "Somchai", unmasked=True) == "Somchai"
    assert masking.display("tdl_user", "first_name", "Somchai") == "S•••"


def test_admin_templates_never_touch_raw_masked_columns():
    """template ห้ามอ้างค่าดิบของคอลัมน์ที่ไม่ visible — จุดตัดสินต้องอยู่ใน service"""
    banned = ("person.first_name", "person.last_name", "person.full_name")
    for path in (ROOT / "app" / "templates").glob("admin_*.html"):
        text = path.read_text(encoding="utf-8")
        leaked = [word for word in banned if word in text]
        assert not leaked, f"{path.name} อ้างค่าดิบ: {leaked}"


# ---------------------------------------------------------------- พฤติกรรมบนหน้า


def _two_people(app):
    with app.app_context():
        boss = User(username="boss", role=roles_service.ROLE_ADMIN)
        boss.set_password(PASSWORD)
        member = User(username="member", first_name="Somchai", last_name="Jaidee")
        member.set_password(PASSWORD)
        db.session.add_all([boss, member])
        db.session.commit()
        return boss.id, member.id


def _sign_in(app, username):
    client = app.test_client()
    resp = client.post("/login", data={"username": username, "password": PASSWORD})
    assert resp.status_code == 302
    return client


def test_the_users_page_masks_real_names_by_default(app):
    _two_people(app)
    client = _sign_in(app, "boss")
    page = client.get("/admin/users").data.decode()
    assert "S•••" in page, "ชื่อจริงต้องถูก mask"
    assert "Somchai" not in page, "ชื่อจริงเต็มหลุดออกมาโดยไม่ unmask"


def test_unmask_reveals_once_and_is_audited(app):
    _, member_id = _two_people(app)
    client = _sign_in(app, "boss")
    page = client.post(f"/admin/users/{member_id}/unmask").data.decode()
    assert "Somchai Jaidee" in page, "unmask แล้วต้องเห็นค่าเต็ม"

    with app.app_context():
        events = list(db.session.query(AuditEntry).filter(AuditEntry.event == "admin.unmask"))
        assert len(events) == 1, "unmask ต้องลง audit หนึ่งแถวเป๊ะ"
        assert events[0].row_id == member_id, "audit ต้องบอกว่าดูของใคร"

    # ไม่มีสถานะค้าง — โหลดหน้าใหม่ต้องกลับมา mask
    again = client.get("/admin/users").data.decode()
    assert "Somchai" not in again


def test_a_regular_user_cannot_unmask_anyone(app):
    boss_id, _ = _two_people(app)
    client = _sign_in(app, "member")
    assert client.post(f"/admin/users/{boss_id}/unmask").status_code == 403


def test_unmasking_a_missing_user_is_404(app):
    _two_people(app)
    client = _sign_in(app, "boss")
    assert client.post("/admin/users/99999/unmask").status_code == 404
