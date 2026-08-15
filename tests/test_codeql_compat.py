"""โค้ดของแอปต้อง parse ได้โดย CodeQL — scanner ที่ย่อยไฟล์ไม่ได้คือไฟล์ที่ไม่ถูกสแกน

CodeQL 2.26.3 ยังอ่าน **PEP 695** ไม่ได้: `type X = ...` ทำให้*ทั้งไฟล์*หลุด
จากการวิเคราะห์ (เจอจริง 2026-08-15 — `app/audit.py` ไม่ถูกสแกนเลยทั้งไฟล์
โดยมีแค่ warning เงียบ ๆ บนหน้า status ที่ไม่มีใครเปิดดู) ส่วน `def f[T](...)`
ทำให้ extractor ตกไปโหมด degrade · ไฟล์ที่หลุดจาก SAST เงียบ ๆ อันตรายกว่า
สำนวน generic รุ่นใหม่ — จนกว่า CodeQL จะอ่านได้ (ทบทวนใน SECURITY-CADENCE
ตอน bump รุ่น CodeQL) โค้ดใต้ `app/` ต้องใช้ TypeVar/การ assign ธรรมดาแทน

ruff จะเถียงกลับด้วย UP040/UP047 — จุดที่จำเป็นต้อง noqa พร้อมเหตุผล
(สองด่านต้องการคนละทาง เอกสารของทั้งคู่ต้องชี้หากัน ไม่ใช่เงียบใส่กัน)
"""

import ast
import pathlib

APP = pathlib.Path(__file__).resolve().parent.parent / "app"


def _pep695_uses(tree: ast.AST) -> list[str]:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.TypeAlias):
            found.append(f"บรรทัด {node.lineno}: `type ... = ...` (TypeAlias statement)")
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and getattr(
            node, "type_params", None
        ):
            found.append(f"บรรทัด {node.lineno}: `{node.name}[...]` (type parameter syntax)")
    return found


def test_no_pep695_syntax_under_app():
    offenders = []
    for path in sorted(APP.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        offenders.extend(f"{path.relative_to(APP.parent)} {use}" for use in _pep695_uses(tree))
    assert not offenders, (
        "PEP 695 ใต้ app/ ทำให้ไฟล์หลุดจากการสแกนของ CodeQL:\n"
        + "\n".join(offenders)
        + "\nใช้ TypeVar/การ assign ธรรมดาแทน (ดู docstring ของไฟล์เทสต์นี้)"
    )
