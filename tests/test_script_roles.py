"""สคริปต์ทุกตัวประกาศชนิดของตัวเอง — และหลักฐานที่ถูกต้องต่างกันตามชนิด

audit รอบ 17 ข้อ 4 · `scripts/` มี 27 ไฟล์ที่ทำงานคนละชนิดกันสามแบบ และ
**"หลักฐานที่ถูกต้อง" ของแต่ละชนิดไม่เหมือนกันเลย**:

| ชนิด | หลักฐานที่ถูกต้องคือ |
|---|---|
| `decider` (ตัดสินผ่าน/ไม่ผ่าน) | เทสต์ที่ฝังความผิดแล้วต้องจับได้ · ของสะอาดต้องไม่ถูกจับ |
| `generator` (สร้างไฟล์ที่ commit ไว้) | ผลลัพธ์ต้องตรงกับที่ commit — **coverage ไม่ใช่ตัววัดของชนิดนี้** |
| `reader` (อ่านแล้วรายงาน) | ตัวเลขที่พิมพ์ต้องตรงกับแหล่ง · ห้ามตัดของทิ้งเงียบ |
| `helper` | ไม่ตัดสินและไม่ถูกอ้างเป็นหลักฐาน |

**ทำไมเรื่องนี้ถึงสำคัญกว่าที่ดู**: รอบ 17 วัด coverage ของ `scripts/` ได้ 43.8%
แล้วเห็น 14 ไฟล์ที่ 0% — แต่ในนั้นมี `run_gates.py` ที่ถูกทดสอบ *ผ่าน subprocess*
โดยตั้งใจ (coverage มองไม่เห็น) และ generator หลายตัวที่ถูกตรวจที่ *ผลลัพธ์* ·
**เกณฑ์ที่ถามผิดชนิด คือเกณฑ์ที่คนจะเรียนรู้ที่จะเลี่ยง** — และตัวเลขที่มันให้
ก็ทำให้คนสรุปผิดด้วย

ที่นี่ไม่ตัดสินว่า "หลักฐานดีพอไหม" (นั่นเป็นงานของด่านอื่นทีละใบ) แต่บังคับสองข้อ
ที่เป็นเงื่อนไขก่อนหน้านั้น: **ทุกไฟล์ต้องประกาศชนิด** และ **ทุกไฟล์ต้องมีใครสักคน
แตะมัน** (เทสต์ หรือขั้นตอนใน CI) — สคริปต์ที่ไม่มีทั้งสองอย่างคือโค้ดที่รันแค่
ตอนมีคนจำได้ว่ามันมีอยู่
"""

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
TESTS = ROOT / "tests"
WORKFLOWS = ROOT / ".github" / "workflows"
HOOKS = ROOT / ".pre-commit-config.yaml"

ROLE_LINE = re.compile(r"^บทบาท: (\w+) — .+$", re.MULTILINE)
ROLES = frozenset({"decider", "generator", "reader", "helper"})


def _scripts() -> list[pathlib.Path]:
    return sorted(p for p in SCRIPTS.glob("*.py") if "__pycache__" not in p.parts)


def _role_of(path: pathlib.Path) -> str | None:
    found = ROLE_LINE.search(path.read_text(encoding="utf-8"))
    return found.group(1) if found else None


@pytest.fixture(scope="module")
def roles() -> dict[str, str]:
    return {p.stem: _role_of(p) or "" for p in _scripts()}


def test_every_script_declares_its_role(roles):
    """ชนิดที่ไม่ได้ประกาศ = ชนิดที่คนอ่านต้องเดา แล้วเรียกร้องหลักฐานผิดแบบ"""
    missing = sorted(name for name, role in roles.items() if not role)
    assert not missing, (
        f"สคริปต์ที่ไม่ได้ประกาศบทบาท: {missing}\n"
        "เติมบรรทัด `บทบาท: <decider|generator|reader|helper> — <เหตุผล>` ท้าย docstring"
    )


def test_declared_roles_are_ones_we_defined(roles):
    """ชนิดใหม่ที่โผล่มาเงียบ ๆ แปลว่าไม่มีใครตัดสินว่าหลักฐานของมันหน้าตาอย่างไร"""
    unknown = sorted({role for role in roles.values() if role not in ROLES})
    assert not unknown, f"บทบาทที่ไม่รู้จัก: {unknown} — รู้จักแค่ {sorted(ROLES)}"


def _mentions(name: str) -> list[str]:
    """ที่ที่เอ่ยชื่อสคริปต์นี้ — เทสต์ · workflow · hook"""
    return [
        str(path.relative_to(ROOT))
        for path in [*TESTS.glob("test_*.py"), *WORKFLOWS.glob("*.yml"), HOOKS]
        if name in path.read_text(encoding="utf-8")
    ]


@pytest.mark.parametrize("script", [p.stem for p in _scripts()])
def test_every_script_is_touched_by_something(script):
    """สคริปต์ที่ไม่มีเทสต์และไม่ถูกเรียกใน CI = โค้ดที่รันตอนมีคนจำได้ว่ามันมีอยู่

    **ไม่ได้บอกว่าหลักฐานดีพอ** — บอกแค่ว่ามีใครสักคนแตะมันบ้าง · ข้อที่แรงกว่านี้
    อยู่ในด่านของแต่ละชนิด (เช่น `checkers-proven-two-way` ของ decider)
    """
    where = _mentions(script)
    assert where, (
        f"`scripts/{script}.py` ไม่ถูกเอ่ยถึงในเทสต์ · workflow · หรือ hook เลยสักที่ — "
        "ถ้ายังจำเป็นให้ผูกเข้ากับอะไรสักอย่าง ถ้าไม่จำเป็นแล้วให้ถอดออก "
        "(ADR 0069 — การถอดต้องเป็นคำตัดสิน)"
    )


# ชื่อค่าคงที่ที่ generator ใช้ชี้ปลายทาง — รับหลายชื่อโดยตั้งใจ เพราะการบังคับให้
# ทุกไฟล์ใช้ชื่อเดียวกันคือการแก้โค้ดที่ถูกอยู่แล้วเพื่อให้ด่านสบายใจ
GENERATOR_OUTPUT = re.compile(
    r"^(?:OUT|OUTPUT|OUTPUT_PATH|TARGET|DEST|SPEC_PATH|WORKSHEET)\w* = (.+)$",
    re.MULTILINE,
)


def test_every_generator_names_the_file_it_writes(roles):
    """generator ที่ไม่บอกว่าเขียนไฟล์ไหน = ของที่ไม่มีใครเทียบผลลัพธ์ได้

    **นี่คือหลักฐานที่ถูกชนิดของ generator** — coverage ของมันไม่มีความหมาย
    เพราะสิ่งที่ต้องถูกต้องคือ *ไฟล์ที่มันผลิต* ไม่ใช่บรรทัดที่ถูกเดินผ่าน ·
    ที่นี่ตรวจแค่ว่ามันประกาศปลายทางไว้ให้คนอื่นเทียบได้ ส่วนการเทียบจริงเป็น
    งานของด่านประจำไฟล์นั้น (`test_skill` · `test_openapi` · `test_mode` …)
    """
    silent = []
    for name, role in sorted(roles.items()):
        if role != "generator":
            continue
        source = (SCRIPTS / f"{name}.py").read_text(encoding="utf-8")
        if not GENERATOR_OUTPUT.search(source):
            silent.append(name)
    assert not silent, (
        f"generator ที่ไม่ได้ประกาศไฟล์ปลายทางเป็นค่าคงที่ระดับโมดูล: {silent}\n"
        "ตั้งชื่อค่าคงที่ว่า OUT/OUTPUT/OUTPUT_PATH แล้วชี้ไปที่ไฟล์ที่มัน commit ไว้"
    )


def test_the_roles_split_the_scripts_into_all_four_kinds(roles):
    """ถ้าเหลือชนิดเดียว แปลว่าการจำแนกไม่ได้ทำงาน — มันควรอธิบายความต่างที่มีจริง"""
    used = set(roles.values())

    assert used == ROLES, f"ชนิดที่ไม่มีใครใช้เลย: {sorted(ROLES - used)}"
    assert len(roles) >= 25, f"อ่านสคริปต์ได้แค่ {len(roles)} ไฟล์ — รูปแบบเปลี่ยนไปแล้ว"
