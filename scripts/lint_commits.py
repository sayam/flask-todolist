"""ตรวจ Conventional Commits + DCO — แทน gitlint ที่ pin click ชนกับ Flask ecosystem

ใช้ได้สองโหมด:
    python scripts/lint_commits.py --msg-file .git/COMMIT_EDITMSG   # hook commit-msg
    python scripts/lint_commits.py --range origin/main..HEAD       # CI

กติกา (ตามที่ประวัติ commit ของ repo นี้ใช้อยู่แล้ว):
    <type>[(scope)][!]: <subject ไม่เกิน 72 ตัว>

และตั้งแต่ ADR 0073 ทุก commit ต้องมีบรรทัด **`Signed-off-by:` (DCO)** — เซ็นด้วย
`git commit -s` · เป็นการรับรองตาม Developer Certificate of Origin 1.1 ว่าผู้ส่ง
มีสิทธิ์ตามกฎหมายที่จะส่งโค้ดชิ้นนั้น · ตรวจสองที่เหมือนกฎหัว commit: hook
`commit-msg` บนเครื่อง และ job `commit-lint` ที่เห็น commit ของ PR จาก fork ด้วย

บทบาท: decider — ตัดสินผ่าน/ไม่ผ่าน — หลักฐานคือเทสต์ที่ฝังความผิดแล้วต้องจับได้ · ของสะอาดต้องไม่ถูกจับ
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
# `Signed-off-by: ชื่อ <อีเมล>` — รูปเดียวกับที่ `git commit -s` เขียนให้ และเป็น
# รูปที่ DCO bot/CLA ของโปรเจกต์อื่นอ่านได้เหมือนกัน · **ต้องมีอีเมลจริง** เพราะ
# ลายเซ็นที่ไม่มีที่อยู่ติดต่อกลับ ไม่ได้รับรองอะไรให้ใครตามไปถามได้
SIGN_OFF = re.compile(r"^Signed-off-by: .+ <[^<>@\s]+@[^<>\s]+>\s*$", re.MULTILINE)


def check_title(title: str) -> list[str]:
    problems = []
    if len(title) > MAX_TITLE:
        problems.append(f"หัว commit ยาว {len(title)} ตัว (เกิน {MAX_TITLE})")
    if not TITLE.match(title):
        problems.append(f"ไม่ตรงรูปแบบ Conventional Commits: {title!r}")
    return problems


def check_sign_off(message: str) -> list[str]:
    """DCO — ทุก commit ต้องรับรองว่าผู้ส่งมีสิทธิ์ตามกฎหมาย (ADR 0073)

    ตรวจ *ทั้งข้อความ* ไม่ใช่แค่หัว เพราะ `git commit -s` เขียนบรรทัดนี้ท้ายเนื้อ
    """
    if SIGN_OFF.search(message):
        return []
    return [
        (
            "ไม่มีบรรทัด `Signed-off-by: ชื่อ <อีเมล>` — เซ็นด้วย `git commit -s` "
            "(DCO 1.1 · ADR 0073) หรือ `git commit --amend -s` ถ้า commit ไปแล้ว"
        )
    ]


# ตัวคั่นของ `git log --format` — **เนื้อ commit มีขึ้นบรรทัดใหม่ได้** ตัวคั่นที่
# เป็นบรรทัดจึงแตก commit ใบเดียวเป็นหลายใบเงียบ ๆ · เก็บไว้เป็นค่าคงที่คู่กับรูป
# ที่ส่งให้ git เพื่อให้สองฝั่งไม่มีทาง drift จากกัน (เทสต์เทียบสองฝั่งอีกชั้น)
RECORD_SEP = "\x1e"
FIELD_SEP = "\x00"
LOG_FORMAT = "%H%x00%s%x00%b%x1e"


def parse_log(out: str) -> list[tuple[str, str, str]]:
    """แปลงผลของ `git log --format=LOG_FORMAT` เป็น (sha สั้น, หัว, เนื้อ) ต่อ commit"""
    return [
        (sha[:9], subject, body)
        for chunk in out.split(RECORD_SEP)
        if chunk.strip()
        for sha, subject, body in [chunk.strip("\n").split(FIELD_SEP, 2)]
    ]


def commits_in_range(rev_range: str) -> list[tuple[str, str, str]]:
    """commit ในช่วงนี้ **ไม่รวม merge commit**

    ข้อความของ merge commit เป็นของที่ GitHub สร้างให้ (`Merge branch 'main'
    into ...`) ไม่ใช่ของที่คนเขียน — บังคับรูปแบบกับมันจึงเท่ากับทำให้ปุ่ม
    "Update branch" บนหน้า PR ทำให้ด่านนี้แดงเสมอ โดยที่ไม่มีใครพิมพ์อะไรผิด
    · และ `required_linear_history` ของ branch protection ก็ไม่ยอมให้ merge
    commit ลง `main` อยู่แล้ว มันจึงเป็นของชั่วคราวบนกิ่งเท่านั้น
    """
    out = subprocess.run(  # noqa: S603 — อินพุตมาจาก CI/ผู้พัฒนาเอง ไม่ใช่ผู้ใช้ภายนอก
        ["git", "log", "--no-merges", f"--format={LOG_FORMAT}", rev_range],  # noqa: S607 - executable is in PATH
        capture_output=True,
        text=True,
        check=True,
        timeout=LOCAL_TIMEOUT_SECONDS,
    ).stdout
    return parse_log(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--msg-file", help="ไฟล์ commit message (โหมด hook)")
    group.add_argument("--range", dest="rev_range", help="ช่วง commit (โหมด CI)")
    args = parser.parse_args()

    failures: list[tuple[str | None, str, str]] = []
    if args.msg_file:
        message = pathlib.Path(args.msg_file).read_text()
        title = message.splitlines()[0]
        failures.extend((None, title, p) for p in check_title(title))
        failures.extend((None, title, p) for p in check_sign_off(message))
    else:
        for sha, subject, body in commits_in_range(args.rev_range):
            failures.extend((sha, subject, p) for p in check_title(subject))
            failures.extend((sha, subject, p) for p in check_sign_off(body))

    for maybe_sha, _title, problem in failures:
        prefix = f"{maybe_sha}: " if maybe_sha else ""
        print(f"FAIL {prefix}{problem}")
    if not failures:
        print("commit message ผ่านทุกตัว")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
