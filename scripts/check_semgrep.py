"""ตรวจ *รายงาน* ของ semgrep ไม่ใช่แค่ exit code ของมัน

`semgrep scan --quiet --error` ที่ผ่าน แปลว่า "ไม่เจออะไร" เท่านั้น — ซึ่ง
เหมือนกันเป๊ะกับ "ไม่ได้ตรวจอะไร" · การสแกนที่ตกไปทั้งไดเรกทอรีเพราะ pattern
ของ `--exclude` เปลี่ยน หรือเพราะ cwd ไม่ใช่ที่ที่คิด จะเขียวเงียบ ๆ ตลอดไป
และ**ไม่มีอะไรในผลลัพธ์ให้ดูต่างจากวันที่มันทำงานถูก**

**เกิดขึ้นจริงแล้วครั้งหนึ่ง**: ค่าเริ่มต้นในตัว semgrep ตัด `tests/` ทิ้ง
61 จาก 136 ไฟล์จึงไม่เคยถูกสแกนเลย ขณะที่ `ci.yml` เขียนว่าตัดแค่ `migrations`
กับ `.venv` — ไม่มีใครโกหก แต่ไม่มีใครวัด

ที่นี่จึงเทียบ **เซตของไฟล์ที่สแกนจริง กับเซตที่ควรถูกสแกน** ไม่ใช่ตัวเลขขั้นต่ำ
ที่ตั้งไว้ลอย ๆ — เพราะเลขขั้นต่ำจับ "หายไปทั้งก้อน" ได้ แต่จับ "หายไปหนึ่ง
ไดเรกทอรี" ไม่ได้ ซึ่งเป็นอาการของบั๊กจริงที่เจอ

ใช้: `semgrep scan ... --json --time --output รายงาน.json` แล้ว
`pipenv run python scripts/check_semgrep.py รายงาน.json`
**ต้องมี `--time`** ไม่งั้น `time.rules` ว่าง แล้วด่านนี้จะแดง (ตั้งใจ —
รายงานที่ไม่บอกว่าใช้กฎกี่ข้อ พิสูจน์ไม่ได้ว่ากฎถูกโหลด)
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

# **เพดานเวลาของคำสั่งที่เรายิงออกไป** (audit รอบ 11 · ADR 0067) — `subprocess.run`
# ที่ไม่มี `timeout=` รอตลอดกาล ซึ่งกลายเป็น job ที่ไม่มีวันจบเมื่อรันใน CI
GIT_TIMEOUT_SECONDS = 60  # `git ls-files` บนเครื่อง
SEMGREPIGNORE = ROOT / ".semgrepignore"


def ignored_prefixes() -> list[str]:
    """ไดเรกทอรีที่ประกาศไว้ว่าไม่ต้องสแกน — อ่านจาก `.semgrepignore` ตัวจริง

    **รองรับเฉพาะรูปแบบง่าย ๆ (ชื่อไดเรกทอรี)** ซึ่งเป็นทั้งหมดที่ไฟล์นั้นมี
    ถ้าวันหนึ่งมีคนใส่ glob ลงไป ตัวนี้จะคำนวณเซตที่คาดหวังผิด — เขียนกำกับไว้
    ในไฟล์นั้นแล้วว่าให้คงรูปแบบง่ายไว้
    """
    lines = SEMGREPIGNORE.read_text(encoding="utf-8").splitlines()
    return [line.strip().rstrip("/") for line in lines if line.strip() and not line.startswith("#")]


def expected_files() -> set[str]:
    """ไฟล์ `.py` ที่ git รู้จัก ลบด้วยของที่ประกาศว่าไม่ต้องสแกน

    ใช้ `git ls-files` เพราะมันตอบคำถามว่า "โค้ดของเรามีอะไรบ้าง" ได้ตรงกว่า
    การเดินดิสก์ — ของที่ไม่ได้ commit ไม่ใช่โค้ดที่ CI ควรรับผิดชอบ
    """
    listed = subprocess.run(
        ["git", "ls-files", "*.py"],  # noqa: S607 — git จาก PATH เหมือน scripts/lint_commits.py
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=GIT_TIMEOUT_SECONDS,
    ).stdout.split()
    prefixes = tuple(f"{prefix}/" for prefix in ignored_prefixes())
    return {path for path in listed if not path.startswith(prefixes)}


def main(report_path: str) -> int:
    """เทียบรายงานกับสิ่งที่ควรเป็น แล้วพิมพ์ตัวเลขที่ใช้ตัดสินออกมาเสมอ

    **พิมพ์ออกมาแม้ตอนผ่าน** — ด่านที่เงียบตอนผ่านคือด่านที่ไม่มีใครสังเกตได้ว่า
    วันหนึ่งมันเริ่มตรวจน้อยลง
    """
    report = json.loads(pathlib.Path(report_path).read_text(encoding="utf-8"))

    rules = report.get("time", {}).get("rules", [])
    scanned = {path.lstrip("./") for path in report["paths"]["scanned"] if path.endswith(".py")}
    expected = expected_files()

    # ของที่ git ยังไม่รู้จักถูกสแกนด้วยตอนรันบนเครื่อง — **ไม่ใช่ความผิดพลาด**
    # สแกนเกินคือความปลอดภัย สแกนขาดคือรูโหว่ ด่านนี้จึงสนใจแค่ทิศเดียว
    extra = sorted(scanned - expected)

    print(f"กฎที่ใช้จริง: {len(rules)}")
    print(
        f"ไฟล์ที่สแกน: {len(scanned)} — ครบตามที่ git รู้จัก {len(expected)} ไฟล์"
        + (f" + อีก {len(extra)} ที่ยังไม่ commit" if extra else "")
    )
    print(f"finding: {len(report['results'])} · error: {len(report['errors'])}")

    problems: list[str] = []
    if not rules:
        problems.append("ไม่มีกฎถูกใช้เลย — ลืม `--time` หรือ config โหลดไม่ขึ้น")
    if report["errors"]:
        problems.append(f"semgrep รายงาน error {len(report['errors'])} ข้อ: {report['errors'][:3]}")
    if report.get("skipped_rules"):
        problems.append(f"มีกฎถูกข้าม {len(report['skipped_rules'])} ข้อ")

    missed = sorted(expected - scanned)
    if missed:
        problems.append(
            f"ไฟล์ที่ควรถูกสแกนแต่ไม่ถูกสแกน {len(missed)} ไฟล์: {missed[:10]}\n"
            "   ถ้าตั้งใจไม่สแกน ให้ประกาศใน .semgrepignore — ไม่ใช่ปล่อยให้หายเงียบ ๆ"
        )

    for finding in report["results"]:
        start = finding["start"]["line"]
        problems.append(f"{finding['path']}:{start} {finding['check_id']}")

    if problems:
        print("\n** semgrep ไม่ผ่าน:", file=sys.stderr)
        for problem in problems:
            print(f"   {problem}", file=sys.stderr)
        return 1

    print("ผ่าน — และสแกนครบทุกไฟล์ที่ประกาศไว้ว่าต้องสแกน")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("ใช้: python scripts/check_semgrep.py <รายงาน.json>", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
