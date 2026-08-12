"""docs/ROPA.md กับ docs/RUNBOOK-BREACH.md ต้องตรงกับของจริง

**ROPA ที่ลอกมาจากแม่แบบคือเอกสารที่ทำให้เชื่อว่ารู้ว่าข้อมูลอยู่ที่ไหน**
ซึ่งอันตรายกว่าไม่มี เพราะตอนเกิดเหตุจริงมันจะถูกใช้ตัดสินใจ

สามอย่างที่เน่าได้ และถูกตรวจที่นี่:

1. **ตารางใหม่ไม่ถูกบันทึก** — เพิ่มตารางแล้วลืมกลับมาเขียนว่าใครเป็นเจ้าของ
   ข้อมูลในนั้น (หลักเดียวกับ `tests/test_data_classification.py`)
2. **ระยะเก็บรักษาในเอกสารกับในโค้ดไม่ตรงกัน** — เอกสารบอก 30 วัน โค้ดลบที่ 60
   แล้วไม่มีใครรู้จนกว่าจะมีคนถาม · ตัวเลขในเอกสารถูกเทียบกับค่าคงที่ที่ purge
   job ใช้จริง ไม่ใช่กับความทรงจำ
3. **runbook อ้างคำสั่งที่ไม่มีแล้ว** — คำสั่งที่พิมพ์ผิดหรือถูกเปลี่ยนชื่อจะ
   ถูกค้นพบตอนตีสาม ซึ่งเป็นเวลาที่แย่ที่สุดที่จะค้นพบมัน
"""

import pathlib
import re

import pytest

from app import db
from app.models import Category, Todo, User  # noqa: F401  ต้อง import ให้ metadata ครบ
from app.purge import AUDIT_RETAIN_DAYS, PURGE_AFTER_DAYS

DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs"
ROPA = DOCS / "ROPA.md"
RUNBOOK = DOCS / "RUNBOOK-BREACH.md"

# คำสั่ง flask ที่ runbook อ้างถึง — ต้องมีอยู่จริงใน CLI
FLASK_COMMAND = re.compile(r"flask ([a-z][a-z-]+)")
LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


@pytest.fixture(scope="module")
def ropa():
    return ROPA.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def runbook():
    return RUNBOOK.read_text(encoding="utf-8")


def test_every_table_is_accounted_for(app, ropa):
    """ทุกตารางต้องถูกบันทึกว่าอยู่ในกิจกรรมไหน — ตารางใหม่ตกหล่นไม่ได้"""
    with app.app_context():
        tables = {table.name for table in db.metadata.sorted_tables}
    # ตารางเวอร์ชันของ alembic ไม่ใช่ข้อมูลของใคร และไม่ได้อยู่ใน metadata ของแอป
    missing = sorted(name for name in tables if f"`{name}`" not in ropa)
    assert not missing, (
        "ตารางที่ยังไม่ถูกบันทึกใน docs/ROPA.md:\n"
        + "\n".join(missing)
        + "\nเพิ่มตารางแล้วต้องตอบให้ได้ว่าข้อมูลในนั้นถูกประมวลผลเพื่ออะไร"
    )


def test_retention_in_the_document_matches_the_code(ropa):
    """ตัวเลขในเอกสารต้องเป็นตัวเลขเดียวกับที่ purge job ใช้จริง"""
    assert f"**{PURGE_AFTER_DAYS} วัน**" in ropa, (
        f"เอกสารต้องบอกระยะ soft delete เป็น {PURGE_AFTER_DAYS} วัน ให้ตรงกับ PURGE_AFTER_DAYS"
    )
    assert f"**{AUDIT_RETAIN_DAYS} วัน**" in ropa, (
        f"เอกสารต้องบอกระยะของ audit เป็น {AUDIT_RETAIN_DAYS} วัน ให้ตรงกับ AUDIT_RETAIN_DAYS"
    )


def test_the_log_inventory_answers_the_four_questions(ropa):
    """บัญชีรายการ log ต้องตอบครบ: เขียนอะไร ไปไหน ใครอ่านได้ เก็บนานเท่าไร (ASVS V16.1.1)"""
    section = ropa.split("## 3. บัญชีรายการของ log", 1)
    assert len(section) == 2, "เอกสารขาดหัวข้อบัญชีรายการของ log"
    inventory = section[1].split("\n## ", 1)[0]
    for question in ("เขียนอะไร", "ไปไหน", "ใครอ่านได้", "เก็บนานเท่าไร"):
        assert question in inventory, f"บัญชีรายการ log ไม่ได้ตอบว่า{question}"
    assert "stdout" in inventory, "ต้องบอกปลายทางจริงของ log ไม่ใช่ปลายทางที่ตั้งใจจะมี"


def test_every_outward_destination_is_listed(ropa):
    """ปลายทางที่ระบบคุยด้วยต้องอยู่ในเอกสารครบ (ASVS V13.1.1)"""
    for key in ("DATABASE_URL", "CACHE_URL", "SECRETS_URL", "OIDC_ISSUER", "LDAP_URL"):
        assert f"`{key}`" in ropa, f"ยังไม่ได้บันทึกปลายทางที่ตั้งด้วย {key}"


def test_the_runbook_only_names_commands_that_exist(app, runbook):
    """คำสั่งที่ runbook บอกให้พิมพ์ ต้องมีอยู่จริง — จะรู้ตอนตีสามนั้นสายไป"""
    registered = set(app.cli.commands)
    named = set(FLASK_COMMAND.findall(runbook))
    missing = sorted(named - registered)
    assert not missing, f"runbook อ้างคำสั่งที่ไม่มีใน CLI: {missing}\nที่มีจริง: {sorted(registered)}"


def test_the_runbook_states_the_deadline_that_the_law_sets(runbook):
    """กรอบ 72 ชั่วโมงต้องอยู่ในเอกสาร พร้อมจุดเริ่มนับที่ถูกต้อง"""
    assert "72" in runbook, "ต้องบอกกรอบเวลาแจ้งเหตุ"
    assert "นับจากที่รู้" in runbook or "นับจากเวลาที่รู้" in runbook, (
        "ต้องบอกด้วยว่านับจาก *เวลาที่รู้* ไม่ใช่เวลาที่เกิดเหตุ — เป็นจุดที่ตีความผิดกันบ่อยที่สุด"
    )


def test_the_runbook_says_to_collect_evidence_before_restarting(runbook):
    """log อยู่ที่ stdout — restart ก่อนคัดลอกคือการทำลายหลักฐานของตัวเอง"""
    collect = runbook.index("## 2. เก็บหลักฐาน")
    stop = runbook.index("## 1. หยุดเลือด")
    assert stop < collect, "ลำดับต้องเป็นหยุดเลือดก่อน แล้วค่อยเก็บหลักฐาน"
    section = runbook[collect:]
    assert "restart" in section, "ต้องเตือนว่า restart ทำให้ log หายก่อนได้คัดลอก"


@pytest.mark.parametrize("document", [ROPA, RUNBOOK])
def test_links_resolve(document):
    """เอกสารที่อ้างของซึ่งหายไปแล้วเน่าแบบเดียวกับ checklist ที่ไม่มีใครตรวจ"""
    text = document.read_text(encoding="utf-8")
    missing = [
        target
        for target in LINK.findall(text)
        if not target.startswith(("http://", "https://", "#"))
        and not (document.parent / target.split("#", 1)[0]).exists()
    ]
    assert not missing, f"{document.name} มีลิงก์ที่ชี้ไปหาไฟล์ที่ไม่มีอยู่: {missing}"
