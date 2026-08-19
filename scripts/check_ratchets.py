"""เกณฑ์แบบ ratchet ต้องไม่ลอยเหนือของจริง — audit รอบ 12 ข้อ 1

`pyproject.toml` เขียนกำกับไว้ทั้งสองที่ว่า "ขยับขึ้นได้อย่างเดียว" — ทิศถูกแล้ว
แต่**ไม่มีอะไรทำให้มันขยับ** · ผลที่วัดได้ 2026-08-18 (หกวันหลังตั้งเลข):
coverage จริง 97.11% ขณะที่พื้นยังเป็น 96 ที่ตั้งไว้ตอนวัดได้ 96.31% —
ที่ว่าง 1.11 จุดแปลว่า **โค้ดที่มีเทสต์คุมอยู่ราว 54 บรรทัดหายไปได้โดยไม่มีอะไรแดง**

กลไกที่ใช้ตรงนี้เป็นตัวเดียวกับที่ ADR 0065 ใช้กับเพดานของ `CLAUDE.md` อยู่แล้ว
(`LINE_SLACK`) — เพดาน/พื้นที่ห่างจากของจริงเกินระยะที่ประกาศ คือเกณฑ์ที่ไม่ได้ตั้ง
· ที่นี่แค่เอาไปใช้กับ ratchet ตัวอื่นที่ยังไม่มี

**ทำไมระยะถึงเป็น 1 จุด**: กว้างพอให้ความผันผวนปกติของการรันผ่าน (บรรทัดที่
`# pragma: no cover` ครอบเพิ่ม/ลดหนึ่งจุด) แต่แคบพอที่การปรับปรุงจริงจะถูกเก็บไว้
· ไม่ตั้งเป็น 0 เพราะเกณฑ์ที่ต้องขยับทุกครั้งที่ตัวเลขขยับ คือเกณฑ์ที่คนจะเลิกอ่าน

**audit รอบ 14 เพิ่มทิศที่สองและ ratchet ตัวที่สาม**: ตัวตรวจรุ่นแรกอ่านเฉพาะพื้น
ที่เป็น *ตัวเลข* ใน config ของเครื่องมือ — ratchet ที่เขียนเป็น *ประโยค* จึงรอดมาได้
ทั้งใบ · strict list ของ mypy บอกว่า "ขยาย ห้ามหด" มาตั้งแต่ Phase 2 โดยไม่มีอะไร
บังคับสักทาง และเป้าที่เขียนกำกับ ("ทั้งแอปภายใน Phase 2") หมดอายุไปสิบหกเฟส

ratchet ที่นับเป็น *จำนวน* ต่างจากที่นับเป็น *เปอร์เซ็นต์* ตรงระยะที่ให้ลอยได้:
เปอร์เซ็นต์ผันผวนเองได้จากบรรทัด `# pragma: no cover` ที่ขยับ แต่จำนวนโมดูล
เปลี่ยนก็ต่อเมื่อมีคนแก้ลิสต์ — **ระยะจึงเป็น 0 และตรวจสองทิศ** (หดแล้วแดง
เพราะไม่มีเครื่องมือตัวไหนบังคับทิศนั้นให้ · ขยายแล้วไม่ขยับพื้นก็แดง)

ใช้ (ต้องรัน `pytest --cov` มาก่อนเพื่อให้มีข้อมูล coverage):
    python3 scripts/check_ratchets.py
"""

from __future__ import annotations

import fnmatch
import pathlib
import re
import shutil
import subprocess
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"

# **เพดานเวลาของคำสั่งที่เรายิงออกไป** (ADR 0067) — `subprocess.run` ที่ไม่มี
# `timeout=` รอตลอดกาล ซึ่งกลายเป็น job ที่ไม่มีวันจบเมื่อรันใน CI
TOOL_TIMEOUT_SECONDS = 300

# ระยะที่พื้นห่างจากของจริงได้ — ดูเหตุผลที่หัวไฟล์
# **ตัวที่นับเป็นจำนวนใช้ 0** เพราะมันไม่ผันผวนเอง ต้องมีคนแก้ลิสต์เท่านั้น
SLACK = {"coverage": 1.0, "interrogate": 1.0, "mypy_strict_modules": 0.0}
DEFAULT_SLACK = 1.0

# ratchet ที่ **เครื่องมือเจ้าของบังคับทิศลงให้อยู่แล้ว** (`fail_under` ของ coverage
# กับ interrogate ทำให้ของจริงตกใต้พื้นไม่ได้) — ที่นี่จึงดูแค่ทิศบน · ส่วนตัวที่
# ไม่มีเจ้าของ ตัวตรวจนี้เป็นตัวเดียวที่เห็นการถอย จึงต้องดูทั้งสองทิศ
OWNED_BY_A_TOOL = frozenset({"coverage", "interrogate"})

APP = ROOT / "app"

INTERROGATE_ACTUAL = re.compile(r"actual:\s*([0-9.]+)%")


def _is_number(text: str) -> bool:
    """`--precision=2` คืนค่าเป็นทศนิยม จึงเช็คด้วย float ไม่ใช่ isdigit"""
    try:
        float(text)
    except ValueError:
        return False
    return True


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    binary = shutil.which(command[0])
    if not binary:
        raise RuntimeError(f"ไม่มี {command[0]} บนเครื่องนี้ — ตัวตรวจนี้ต้องรันมันเพื่ออ่านค่าจริง")
    return subprocess.run(  # noqa: S603 — คำสั่งคงที่ + path จาก shutil.which
        [binary, *command[1:]],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=TOOL_TIMEOUT_SECONDS,
    )


def declared() -> dict[str, float]:
    """พื้นที่ประกาศไว้ใน `pyproject.toml` — อ่านจากไฟล์จริง ไม่ใช่จากคอมเมนต์"""
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return {
        "coverage": float(config["tool"]["coverage"]["report"]["fail_under"]),
        "interrogate": float(config["tool"]["interrogate"]["fail-under"]),
        "mypy_strict_modules": float(config["tool"]["todolist"]["ratchets"]["mypy_strict_modules"]),
    }


def _strict_patterns(config: dict) -> list[str]:
    """รายการ module ที่ประกาศ strict ไว้ใน override ของ mypy"""
    for override in config["tool"]["mypy"]["overrides"]:
        if override.get("disallow_untyped_defs"):
            return list(override["module"])
    raise RuntimeError("หา strict list ของ mypy ไม่เจอ — โครงของ pyproject เปลี่ยนไปแล้ว")


def strict_modules() -> int:
    """นับโมดูลใน `app/` ที่ตกอยู่ใต้ strict list จริง ๆ

    **ไม่นับส่วนเสริมของ plugin** เพราะ mypy ตั้งชื่อโมดูลให้มันไม่ได้ (ไอดีมีขีดกลาง)
    และ `exclude` ของ mypy ตัดทิ้งอยู่แล้ว — การนับมันจะทำให้พื้นขยับตามการวาง
    ไดเรกทอรี ซึ่งไม่เกี่ยวกับความเข้มของ type check เลย
    """
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    patterns = _strict_patterns(config)
    modules = [
        str(path.relative_to(ROOT).with_suffix("")).replace("/", ".").removesuffix(".__init__")
        for path in sorted(APP.rglob("*.py"))
        if "enhancements" not in path.parts and "__pycache__" not in path.parts
    ]
    return sum(any(fnmatch.fnmatch(module, pattern) for pattern in patterns) for module in modules)


def measured() -> dict[str, float]:
    """ค่าจริงวันนี้ — รันเครื่องมือเอง เพราะคอมเมนต์ที่เขียนกำกับไว้คือสิ่งที่กำลังตรวจ"""
    # `--ignore-errors` เฉพาะที่นี่ — เทสต์บางตัวสร้าง plugin ชั่วคราวแล้วลบทิ้ง
    # ข้อมูล coverage จึงอ้างไฟล์ที่ไม่มีอยู่แล้วตอนอ่านย้อนหลัง · **ด่านหลัก
    # (`fail_under` ตอน pytest) ยังเข้มเหมือนเดิม** เพราะมันอ่านตอนไฟล์ยังอยู่
    # `--precision=2` เพราะค่าที่ปัดเป็นจำนวนเต็มจะกลืนที่ว่างเศษจุดหายไป
    # ซึ่งเป็นที่ว่างที่ตัวตรวจนี้มีหน้าที่มองเห็นพอดี
    total = _run(["coverage", "report", "--format=total", "--precision=2", "--ignore-errors"])
    if total.returncode != 0 or not _is_number(total.stdout.strip()):
        raise RuntimeError(
            "อ่าน coverage ไม่ได้ — ต้องรัน `pytest --cov` ก่อนเพื่อให้มีไฟล์ข้อมูล "
            f"(stderr: {total.stderr.strip()[:120]})"
        )
    docs = _run(["interrogate", "app"])
    found = INTERROGATE_ACTUAL.search(docs.stdout + docs.stderr)
    if not found:
        raise RuntimeError("อ่านผลของ interrogate ไม่ได้ — รูปแบบข้อความเปลี่ยนไปแล้ว")
    return {
        "coverage": float(total.stdout.strip()),
        "interrogate": float(found.group(1)),
        "mypy_strict_modules": float(strict_modules()),
    }


def problems(floors: dict[str, float], actual: dict[str, float]) -> list[str]:
    """สองทิศ — พื้นที่ลอยเหนือของจริง (ไม่มีใครหมุน) และของจริงที่ตกใต้พื้น (ถอย)"""
    found = []
    for name, floor in sorted(floors.items()):
        now = actual[name]
        slack = SLACK.get(name, DEFAULT_SLACK)
        if now - floor > slack:
            found.append(
                f"{name}: พื้น {floor} แต่ของจริง {now} — ห่าง {now - floor:.2f} "
                f"(เกิน {slack}) · ขยับพื้นขึ้นไปที่ {int(now)} ใน PR เดียวกับที่ทำให้มันดีขึ้น "
                "ไม่งั้นที่ว่างที่เพิ่งได้จะถูกใช้คืนโดยไม่มีใครสังเกต"
            )
        if now < floor and name not in OWNED_BY_A_TOOL:
            found.append(
                f"{name}: ของจริง {now} ต่ำกว่าพื้นที่ประกาศไว้ {floor} — **นี่คือการถอย** "
                "ratchet ตัวนี้ไม่มีเครื่องมือเจ้าของบังคับทิศลงให้ ตัวตรวจนี้จึงเป็นตัวเดียว "
                "ที่เห็น · ทางที่ถูกคือคืนของที่ถอดออก ไม่ใช่ลดพื้น"
            )
    return found


def main() -> int:
    """อ่านพื้นที่ประกาศ → วัดของจริง → คืน 1 เมื่อพื้นลอยต่ำเกินไป"""
    try:
        floors, actual = declared(), measured()
    except RuntimeError as problem:
        print(f"ตรวจ ratchet ไม่ได้: {problem}", file=sys.stderr)
        return 2

    for name in sorted(floors):
        print(f"  {name:12s} พื้น {floors[name]:6.1f} · ของจริง {actual[name]:6.2f}")

    found = problems(floors, actual)
    if found:
        print("ratchet ที่ไม่ตรงกับของจริง (ลอยเหนือ หรือถอยลง):", file=sys.stderr)
        for line in found:
            print(f"  - {line}", file=sys.stderr)
        return 1

    print("ทุกพื้นติดกับของจริงตามระยะที่ประกาศไว้")
    return 0


if __name__ == "__main__":
    sys.exit(main())
