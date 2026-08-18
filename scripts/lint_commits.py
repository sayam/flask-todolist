"""ตรวจ Conventional Commits — แทน gitlint ที่ pin click ชนกับ Flask ecosystem

ใช้ได้สองโหมด:
    python scripts/lint_commits.py --msg-file .git/COMMIT_EDITMSG   # hook commit-msg
    python scripts/lint_commits.py --range origin/main..HEAD       # CI

กติกา (ตามที่ประวัติ commit ของ repo นี้ใช้อยู่แล้ว):
    <type>[(scope)][!]: <subject ไม่เกิน 72 ตัว>
"""

import argparse
import pathlib
import re
import subprocess
import sys

# **เพดานเวลาของคำสั่งที่เรายิงออกไป** (audit รอบ 11 · ADR 0067) — `subprocess.run`
# ที่ไม่มี `timeout=` รอตลอดกาล และเครื่องมือพวกนี้รันอยู่ใน job ของ CI ผลคือ
# `gh` ที่ไม่ตอบกลายเป็น job ที่กินเพดานของ job ไปทั้งก้อนโดยไม่ทำอะไรเลย
LOCAL_TIMEOUT_SECONDS = 60  # `git log` บนเครื่อง — ช้ากว่านี้แปลว่ามีอย่างอื่นผิด

TYPES = "feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert"
TITLE = re.compile(rf"^({TYPES})(\([\w./-]+\))?!?: \S.{{0,70}}$")
MAX_TITLE = 72


def check_title(title: str) -> list[str]:
    problems = []
    if len(title) > MAX_TITLE:
        problems.append(f"หัว commit ยาว {len(title)} ตัว (เกิน {MAX_TITLE})")
    if not TITLE.match(title):
        problems.append(f"ไม่ตรงรูปแบบ Conventional Commits: {title!r}")
    return problems


def commits_in_range(rev_range: str) -> list[tuple[str, str]]:
    """commit ในช่วงนี้ **ไม่รวม merge commit**

    ข้อความของ merge commit เป็นของที่ GitHub สร้างให้ (`Merge branch 'main'
    into ...`) ไม่ใช่ของที่คนเขียน — บังคับรูปแบบกับมันจึงเท่ากับทำให้ปุ่ม
    "Update branch" บนหน้า PR ทำให้ด่านนี้แดงเสมอ โดยที่ไม่มีใครพิมพ์อะไรผิด
    · และ `required_linear_history` ของ branch protection ก็ไม่ยอมให้ merge
    commit ลง `main` อยู่แล้ว มันจึงเป็นของชั่วคราวบนกิ่งเท่านั้น
    """
    out = subprocess.run(  # noqa: S603 — อินพุตมาจาก CI/ผู้พัฒนาเอง ไม่ใช่ผู้ใช้ภายนอก
        ["git", "log", "--no-merges", "--format=%H%x00%s", rev_range],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
        timeout=LOCAL_TIMEOUT_SECONDS,
    ).stdout
    return [
        (sha[:9], subject)
        for line in out.splitlines()
        if line
        for sha, subject in [line.split("\x00", 1)]
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--msg-file", help="ไฟล์ commit message (โหมด hook)")
    group.add_argument("--range", dest="rev_range", help="ช่วง commit (โหมด CI)")
    args = parser.parse_args()

    failures: list[tuple[str | None, str, str]] = []
    if args.msg_file:
        title = pathlib.Path(args.msg_file).read_text().splitlines()[0]
        failures.extend((None, title, p) for p in check_title(title))
    else:
        for sha, subject in commits_in_range(args.rev_range):
            failures.extend((sha, subject, p) for p in check_title(subject))

    for maybe_sha, _title, problem in failures:
        prefix = f"{maybe_sha}: " if maybe_sha else ""
        print(f"FAIL {prefix}{problem}")
    if not failures:
        print("commit message ผ่านทุกตัว")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
