"""ทุก route ต้องมี `@login_required` — และรายการข้อยกเว้นต้องถูกตรวจ ไม่ใช่แค่ประกาศ

กฎข้อแรกสุดของโปรเจกต์ (CLAUDE.md · Conventions) คือ **ทุก route ต้องมี
`@login_required`** พร้อมรายการข้อยกเว้นที่เขียนไว้ว่า "มีเท่านี้" — audit
governance รอบ 5 พบว่า**ไม่มีใครตรวจรายการนั้นเลย** และมันไม่ครบจริง:
`/plugin/themes/<id>/style.css` ไม่ถูกนับ ทั้งที่เปิดสาธารณะมาตั้งแต่ Phase 4

เทสต์เดิมของ authz ครอบ route ที่*คนเขียนนึกถึง* (RBAC · ownership · CSRF)
ไม่ใช่*ทุก route ที่มีอยู่จริง* — route ใหม่ที่ลืม decorator จึงเงียบสนิท
จนกว่าจะมีคนอ่านเจอ · นี่คือ OWASP A01 (Broken Access Control) ซึ่งอันตราย
ที่สุดตอนที่มันเกิดจาก "ลืม" ไม่ใช่ "ตัดสินใจผิด"

ด่านนี้จึงเป็น **enumeration สองทิศ** แบบเดียวกับ `ALLOWED_LINES` ของ
`tests/test_write_discipline.py` และ partition ของ `docs/DATA-CLASSIFICATION.md`:

1. route ที่ไม่มี `login_required` ต้องอยู่ใน `PUBLIC_ROUTES` พร้อมเหตุผล
2. **ทุกชื่อใน `PUBLIC_ROUTES` ต้องมีอยู่จริง** — รายการที่มีสมาชิกผีคือรายการ
   ที่ยกเว้นของที่ไม่มีอยู่ และวันหนึ่งจะยกเว้นของใหม่ที่บังเอิญชื่อซ้ำ
3. **endpoint ทุกตัวใน `url_map` ต้องมาจาก view ที่ AST เห็น** — กัน route ที่
   ลงทะเบียนด้วย `add_url_rule` ซึ่งการสแกน decorator มองไม่เห็นโดยนิยาม
"""

import ast
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = ROOT / "app"

# ข้อยกเว้นที่ **ตั้งใจ** ให้เปิดสาธารณะ — เหตุผลต่อรายการ ไม่ใช่รายชื่อลอย ๆ
# (ตรงกับรายการใน CLAUDE.md หัวข้อ Conventions — สองที่นี้ต้องตรงกันเสมอ)
PUBLIC_ROUTES = {
    "login": "หน้า login เอง — ต้องเข้าถึงได้ก่อนมีตัวตน",
    "verify": "ขั้นที่สองของ MFA — ยังไม่ถือว่า login (สถานะครึ่งทาง ADR 0024)",
    "sso_begin": "เริ่ม flow ของปัจจัยหลักภายนอก (ADR 0028)",
    "sso_callback": "ปลายทางที่ IdP เรียกกลับ — ยังไม่มี session ของเรา",
    "privacy": "หน้านโยบายความเป็นส่วนตัว — PDPA ม.23 บังคับให้เปิดสาธารณะ",
    "set_language": "สลับภาษาใช้จากหน้า login ได้ (ไม่มีข้อมูลผู้ใช้ในคำตอบ)",
    "set_mode": "สลับโหมดสว่าง/มืด ใช้จากหน้า login ได้",
    "theme_stylesheet": (
        "CSS ของธีม — หน้า login ต้องโหลดได้ · ไอดีถูกตรวจกับรายการ plugin ที่ค้นเจอจริง"
        " จึง traverse ออกนอกไดเรกทอรีไม่ได้ และไฟล์ไม่มีข้อมูลผู้ใช้"
    ),
    "healthz": "liveness ของ orchestrator — ไม่แตะ DB ไม่มีข้อมูลภายใน (ADR 0048)",
    "readyz": "readiness ของ orchestrator — ตอบ 200/503 เท่านั้น (ADR 0048)",
    "metrics": "ด่านคนละชั้น — `require_api_token()` ตัวเดียวกับ /api/v1 (ADR 0031)",
}


def _routes() -> dict[str, bool]:
    """ทุก view ที่ผูก route ในโค้ดของแอป → ชื่อฟังก์ชัน: มี login_required ไหม"""
    found: dict[str, bool] = {}
    for path in sorted(APP.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        if ".route(" not in source:
            continue
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.FunctionDef):
                continue
            decorators = [ast.unparse(d) for d in node.decorator_list]
            if any(".route(" in d for d in decorators):
                found[node.name] = any("login_required" in d for d in decorators)
    return found


@pytest.fixture(scope="module")
def routes() -> dict[str, bool]:
    discovered = _routes()
    assert len(discovered) > 30, f"เจอ route แค่ {len(discovered)} ตัว — ตัวสแกนน่าจะพัง ไม่ใช่แอปหด"
    return discovered


def test_every_route_requires_login_unless_it_is_a_declared_exception(routes):
    """route ใหม่ที่ลืม `@login_required` ต้องแดง — ไม่ใช่รอให้คนอ่านเจอ"""
    unprotected = sorted(name for name, guarded in routes.items() if not guarded)
    undeclared = [name for name in unprotected if name not in PUBLIC_ROUTES]

    assert not undeclared, (
        f"route ที่เปิดสาธารณะโดยไม่ได้ประกาศ: {undeclared}\n"
        "ถ้าตั้งใจให้เปิด ให้เพิ่มใน PUBLIC_ROUTES พร้อมเหตุผล **และ**แก้รายการใน "
        "CLAUDE.md ด้วย — ถ้าไม่ได้ตั้งใจ นี่คือ OWASP A01 ที่เพิ่งถูกจับได้"
    )


def test_the_exception_list_has_no_ghosts(routes):
    """รายการยกเว้นที่มีสมาชิกไม่มีอยู่จริง = ยกเว้นล่วงหน้าให้ชื่อที่ใครก็มาใช้ซ้ำได้"""
    ghosts = sorted(name for name in PUBLIC_ROUTES if name not in routes)

    assert not ghosts, (
        f"PUBLIC_ROUTES ยกเว้นชื่อที่ไม่มี route จริงแล้ว: {ghosts}\n"
        "ถอดออก — รายการยกเว้นต้องสะท้อนของที่มีอยู่ ณ วันนี้เท่านั้น"
    )


def test_declared_exceptions_are_still_actually_public(routes):
    """ทิศกลับ: ถ้ามีคนใส่ `login_required` ให้ route ที่เคยยกเว้น ให้ถอดออกจากรายการ

    รายการยกเว้นที่ยาวกว่าความจริงทำให้คนอ่านคิดว่าผิวสาธารณะกว้างกว่าที่เป็น
    — และเป็นที่ซ่อนของรายการที่ไม่มีใครทบทวน (หลักเดียวกับ accepted-advisories)
    """
    now_protected = sorted(name for name in PUBLIC_ROUTES if routes.get(name) is True)

    assert not now_protected, f"route เหล่านี้มี login_required แล้วแต่ยังอยู่ในรายการยกเว้น: {now_protected}"


def test_the_documented_exception_list_matches_this_one():
    """CLAUDE.md ประกาศรายการนี้กับคนอ่าน — สองที่ต้องตรงกัน ไม่ใช่ใกล้เคียง"""
    notes = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    marker = "ข้อยกเว้นที่ตั้งใจมีเท่านี้"
    assert marker in notes, "CLAUDE.md ไม่มีรายการข้อยกเว้นแล้ว — กฎหลักหายไปจากบันทึกการทำงาน"

    section = notes.split(marker, 1)[1][:600]
    fragments = ("/login", "/lang/", "/mode/", "/privacy", "/healthz", "/readyz", "/metrics")
    for path_fragment in fragments:
        assert path_fragment in section, f"รายการใน CLAUDE.md ไม่ได้พูดถึง {path_fragment}"
    assert "style.css" in section or "themes" in section, (
        "รายการใน CLAUDE.md ยังไม่นับ route ของ CSS ธีม ทั้งที่มันเปิดสาธารณะจริง (ช่องว่างที่ audit รอบ 5 จับได้)"
    )


def test_no_route_hides_from_the_decorator_scan(app):
    """`add_url_rule` ลงทะเบียน route ได้โดยไม่มี decorator — ด่านนี้ต้องมองเห็นด้วย

    ถ้าวันหนึ่งมีคนเพิ่ม endpoint แบบนั้น การสแกน decorator จะบอกว่า "ครบแล้ว"
    ทั้งที่มองไม่เห็นมันเลย — เทียบกับ `url_map` จริงคือทางเดียวที่รู้ตัว
    """
    scanned = set(_routes())
    registered = {
        rule.endpoint.split(".")[-1]
        for rule in app.url_map.iter_rules()
        if rule.endpoint != "static" and not rule.rule.startswith("/api/")
    }

    invisible = sorted(registered - scanned)
    assert not invisible, (
        f"endpoint ที่อยู่ใน url_map แต่ตัวสแกน decorator มองไม่เห็น: {invisible}\n"
        "น่าจะถูกลงทะเบียนด้วย add_url_rule — ด่านนี้ต้องถูกขยายให้ครอบก่อน merge"
    )
