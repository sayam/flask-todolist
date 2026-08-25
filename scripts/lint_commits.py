"""ตรวจ Conventional Commits + DCO — **ตัวจริงอยู่ที่ verifiable-gates แล้ว**

ตัวตัดสินคือ `verifiable_gates.lint_commits` ใน submodule `vendor/verifiable-gates`
(ADR 0077 · ขั้น 3a) · ไฟล์นี้เหลือหน้าที่เดียวคือเป็นที่อยู่ที่ hook `commit-msg`
กับ job `commit-lint` เรียกถึงได้ แล้วส่ง argument ต่อไปทั้งดุ้น

กติกาไม่เปลี่ยน: `<type>[(scope)][!]: <หัวไม่เกิน 72 ตัว>` และทุก commit ต้องมี
`Signed-off-by:` (DCO 1.1 — ADR 0073) · **`TYPES` ยัง export จากที่นี่**
เพราะ `tests/test_dependabot.py` อ่านชนิดที่ยอมรับได้จากตัวจริง ไม่ใช่จากสำเนา

ใช้สองโหมดเหมือนเดิม:
    python scripts/lint_commits.py --msg-file .git/COMMIT_EDITMSG   # hook
    python scripts/lint_commits.py --range origin/main..HEAD        # CI

บทบาท: decider — ตัดสินผ่าน/ไม่ผ่าน — หลักฐานคือเทสต์ที่ฝังความผิดแล้วต้องจับได้ · ของสะอาดต้องไม่ถูกจับ
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vendor" / "verifiable-gates" / "src"))

from verifiable_gates import lint_commits  # noqa: E402 — ต้องต่อ path ให้ vendor ก่อน import

# ผู้เรียกเดิมอ่านค่าเหล่านี้จากที่นี่ — ชี้ไปที่ตัวจริง ไม่ใช่ลอกค่ามาไว้
TYPES = lint_commits.TYPES
MAX_TITLE = lint_commits.MAX_TITLE
check_title = lint_commits.check_title
check_sign_off = lint_commits.check_sign_off


def main(argv: list[str] | None = None) -> int:
    return lint_commits.main(list(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    sys.exit(main())
