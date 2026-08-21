"""พื้นผิว API ของไฟล์ Python — signature ล้วน ไม่มี body

**ทำไมต้องมี**: คำถามที่คนอ่านโค้ด (และ agent) ถามบ่อยที่สุดคือ *"ไฟล์นี้ให้
อะไรบ้าง"* ซึ่งตอบได้ด้วย signature กับบรรทัดแรกของ docstring — แต่ทางเดียวที่มี
คือเปิดไฟล์ทั้งใบ · `app/services/teams.py` มี 300 กว่าบรรทัด ในนั้นเป็นพื้นผิว
จริงไม่ถึงหนึ่งในสิบ ส่วนที่เหลือคือรายละเอียดการทำงานซึ่งยังไม่มีใครต้องการ
ตอนที่กำลังหาว่า *จะเรียกอะไร*

ไอเดียมาจาก `graft` (nanonets) ที่แยกชั้นโครงสร้างซึ่ง deterministic และไม่เรียก
โมเดลเลย ออกจากชั้นคำอธิบายซึ่งต้องใช้โมเดล · **ที่นี่รับมาเฉพาะชั้นแรก** เพราะ
มันคือชั้นที่ตอบได้ด้วย `ast` ของ stdlib ทั้งหมด ไม่ต้องมี dependency ไม่ต้องมี
cache ให้เฝ้า และไม่มีอะไรให้เน่า — อ่านจากไฟล์จริงทุกครั้งที่ถาม

**ไม่ใช่ index และตั้งใจให้ไม่เป็น** — ไม่เก็บสถานะ ไม่มีขั้นตอน build ไม่มี
คำถามว่าข้อมูลสดหรือยัง ซึ่งเป็นคำถามที่ audit รอบ 21 เพิ่งชี้ว่าเป็นต้นทาง
ของหนี้ที่เงียบที่สุดในระบบ

    python scripts/skeleton.py app/services/todos.py
    python scripts/skeleton.py app/services/            # ทั้งไดเรกทอรี
    python scripts/skeleton.py app/models.py --private  # เอาชื่อขึ้นต้น _ ด้วย

บทบาท: reader — อ่านแล้วรายงาน ไม่ตัดสินผ่าน/ไม่ผ่าน และไม่แก้อะไรเลย
"""

from __future__ import annotations

import argparse
import ast
import pathlib
import sys
from dataclasses import dataclass

INDENT = "    "


@dataclass(frozen=True)
class Symbol:
    """สัญลักษณ์หนึ่งตัวที่โผล่บนพื้นผิว — ชั้นลึกเท่าไหร่ · เขียนว่าอะไร · อธิบายว่าอะไร"""

    depth: int
    signature: str
    summary: str


def _is_private(name: str) -> bool:
    """ชื่อที่ขึ้นต้นด้วย `_` ตัวเดียว = ไม่ใช่พื้นผิว · `__init__` และเพื่อน ๆ ยังนับ"""
    return name.startswith("_") and not name.startswith("__")


Documented = ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef


def _first_line(node: Documented) -> str:
    """บรรทัดแรกของ docstring — ส่วนที่เหลือคือรายละเอียดที่คนถามยังไม่ต้องการ"""
    text = ast.get_docstring(node)
    if not text or not text.strip():
        return ""
    return text.strip().splitlines()[0].strip()


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """`def name(args) -> return` — ประกอบจาก AST ไม่ใช่จากข้อความในไฟล์

    อ่านจากข้อความจะพังกับ signature ที่ขึ้นบรรทัดใหม่ ซึ่งในโปรเจกต์นี้มีเยอะ
    เพราะ ruff จัดรูปให้เมื่อยาวเกิน 100 ตัว
    """
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    return f"{prefix} {node.name}({ast.unparse(node.args)}){returns}"


def _decorators(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> list[str]:
    """decorator มีความหมายต่อผู้เรียกเสมอ (`@property` · `@login_required`) จึงอยู่บนพื้นผิว"""
    return [f"@{ast.unparse(item)}" for item in node.decorator_list]


def symbols(source: str, *, private: bool = False) -> list[Symbol]:
    """พื้นผิวของโมดูลหนึ่ง — ระดับบนสุด และ method ชั้นเดียวใต้ class

    ลึกกว่านั้นไม่เอา: ฟังก์ชันซ้อนในฟังก์ชันเป็นรายละเอียดการทำงาน ไม่ใช่สิ่งที่
    ผู้เรียกจากข้างนอกเรียกได้
    """
    tree = ast.parse(source)
    found: list[Symbol] = []

    def take(node: ast.AST, depth: int) -> None:
        """เก็บสัญลักษณ์หนึ่งตัวถ้ามันอยู่บนพื้นผิว"""
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            return
        if not private and _is_private(node.name):
            return
        found.extend(Symbol(depth, line, "") for line in _decorators(node))
        if isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(base) for base in node.bases)
            found.append(
                Symbol(
                    depth,
                    f"class {node.name}({bases})" if bases else f"class {node.name}",
                    _first_line(node),
                )
            )
            for child in node.body:
                take(child, depth + 1)
            return
        found.append(Symbol(depth, _signature(node), _first_line(node)))

    for node in tree.body:
        take(node, 0)
    return found


def render(path: pathlib.Path, source: str, *, private: bool = False) -> str:
    """พื้นผิวของไฟล์เดียว พร้อมบรรทัดสุดท้ายที่บอกว่าย่อไปเท่าไหร่

    ตัวเลขที่ท้ายไม่ใช่ของแถม — มันคือเหตุผลที่เครื่องมือนี้มีอยู่ และเป็นสิ่งเดียว
    ที่บอกได้ว่าไฟล์ไหนคุ้มที่จะถามด้วยวิธีนี้ ไฟล์ไหนอ่านทั้งใบไปเลยเร็วกว่า
    """
    found = symbols(source, private=private)
    header = _first_line(ast.parse(source))
    lines = [f"{path} — {header}" if header else str(path)]
    lines.extend(f"{INDENT * (item.depth + 1)}{item.signature}" for item in found)
    if not found:
        lines.append(f"{INDENT}(ไม่มีสัญลักษณ์บนพื้นผิว)")
    whole = source.count("\n") + 1
    shown = len(lines) + 1  # +1 คือบรรทัดสรุปนี้เอง — ตัวเลขต้องตรงกับที่พิมพ์จริง
    share = shown * 100 // whole if whole else 0
    lines.append(f"{INDENT}— {len(found)} สัญลักษณ์ · {shown} จาก {whole} บรรทัด ({share}%)")
    return "\n".join(lines)


def _targets(raw: str) -> list[pathlib.Path]:
    """ไฟล์เดียวหรือทั้งไดเรกทอรี — เรียงเสมอเพื่อให้ผลลัพธ์ซ้ำได้"""
    path = pathlib.Path(raw)
    if path.is_dir():
        return sorted(item for item in path.rglob("*.py") if "__pycache__" not in item.parts)
    return [path]


def main(argv: list[str] | None = None) -> int:
    """อ่าน → พิมพ์ · คืน 1 เฉพาะตอนที่อ่านไฟล์ไม่ได้จริง ๆ"""
    parser = argparse.ArgumentParser(description="พื้นผิว API ของไฟล์ Python (signature ล้วน)")
    parser.add_argument("path", help="ไฟล์ .py หรือไดเรกทอรี")
    parser.add_argument("--private", action="store_true", help="เอาชื่อที่ขึ้นต้นด้วย _ ด้วย")
    args = parser.parse_args(argv)

    targets = _targets(args.path)
    if not targets:
        print(f"ไม่มีไฟล์ .py ใต้ {args.path}", file=sys.stderr)
        return 1

    blocks = []
    for path in targets:
        try:
            source = path.read_text(encoding="utf-8")
        except OSError as problem:
            print(f"อ่าน {path} ไม่ได้: {problem}", file=sys.stderr)
            return 1
        try:
            blocks.append(render(path, source, private=args.private))
        except SyntaxError as problem:
            print(f"{path} — แยกวิเคราะห์ไม่ได้: {problem}", file=sys.stderr)
            return 1
    print("\n\n".join(blocks))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
