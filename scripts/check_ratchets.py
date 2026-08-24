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

**audit รอบ 17 เพิ่ม `scripts_coverage`** — โค้ดที่บังคับกฎทั้ง 83 gate อยู่นอก
`source` ของ coverage มาตลอด (`source = ["app"]`) จึงเป็นโค้ดชุดเดียวในโปรเจกต์
ที่ไม่มีเกณฑ์บังคับตัวเอง ทั้งที่มันคือสิ่งที่บังคับทุกอย่างที่เหลือ · วัดแยกไฟล์
ข้อมูลโดยตั้งใจ: ยัด `scripts` เข้า `source` เมื่อไหร่ ตัวเลขรวมจะตกต่ำกว่า 97
แล้วพื้นของแอปจะถูกลดด้วยผลข้างเคียง

**audit รอบ 16 เพิ่มกองที่สอง: กันการ *ถอด*** (`[tool.todolist.removals]`) ·
รอบนั้นวัดด้วยการลบของจริง 11 ครั้ง แล้วพบเส้นแบ่งที่คมกว่าที่คิด — ทะเบียนที่ถูก
ตรวจกับ *ความจริง* (คอลัมน์ · route · ไฟล์ · job) ลบไม่ได้เงียบ ส่วนทะเบียนที่ถูก
ตรวจกับ *กระดาษอีกใบ* ลบได้เงียบสนิท เพราะ **การลบทั้งสองข้างพร้อมกันยังนับว่า
"ตรงกัน" อยู่ดี** · ที่วัดได้: ถอด gate ทิ้งแล้ว CI เขียวครบถ้าเก็บกวาด 6 ที่ ·
37 แถวในสามทะเบียนกระดาษลบทิ้งได้โดยไม่มีอะไรฟ้อง

กองนี้ต่างจาก ratchet ตรงทิศที่บังคับ: **โตได้อิสระ หดต้องมาแก้เลข** — การเพิ่ม
ถูกเฝ้าด้วยด่านอื่นครบอยู่แล้ว (ลงทะเบียนไฟล์เทสต์ · overlay · หลักฐาน) ที่ขาดคือ
การถอด · ผลคือการถอดกลายเป็นคำตัดสินที่มีคนเซ็นชื่อ แทนที่จะเป็นผลข้างเคียงของ
การเก็บกวาดให้ CI เขียว

ใช้ (ต้องรัน `pytest --cov` มาก่อนเพื่อให้มีข้อมูล coverage):
    python3 scripts/check_ratchets.py

บทบาท: decider — ตัดสินผ่าน/ไม่ผ่าน — หลักฐานคือเทสต์ที่ฝังความผิดแล้วต้องจับได้ · ของสะอาดต้องไม่ถูกจับ
"""

from __future__ import annotations

import ast
import fnmatch
import json
import math
import pathlib
import re
import shutil
import subprocess
import sys
import tomllib

import yaml  # type: ignore[import-untyped] - library lacks type stubs

ROOT = pathlib.Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"

# **เพดานเวลาของคำสั่งที่เรายิงออกไป** (ADR 0067) — `subprocess.run` ที่ไม่มี
# `timeout=` รอตลอดกาล ซึ่งกลายเป็น job ที่ไม่มีวันจบเมื่อรันใน CI
TOOL_TIMEOUT_SECONDS = 300

# ระยะที่พื้นห่างจากของจริงได้ — ดูเหตุผลที่หัวไฟล์
# **ตัวที่นับเป็นจำนวนใช้ 0** เพราะมันไม่ผันผวนเอง ต้องมีคนแก้ลิสต์เท่านั้น
SLACK = {
    "coverage": 1.0,
    "interrogate": 1.0,
    "mypy_strict_modules": 0.0,
    "enforced_prohibitions": 0.0,
    "scripts_coverage": 1.0,
}
DEFAULT_SLACK = 1.0

# ratchet ที่ **เครื่องมือเจ้าของบังคับทิศลงให้อยู่แล้ว** (`fail_under` ของ coverage
# กับ interrogate ทำให้ของจริงตกใต้พื้นไม่ได้) — ที่นี่จึงดูแค่ทิศบน · ส่วนตัวที่
# ไม่มีเจ้าของ ตัวตรวจนี้เป็นตัวเดียวที่เห็นการถอย จึงต้องดูทั้งสองทิศ
OWNED_BY_A_TOOL = frozenset({"coverage", "interrogate"})

# ผลวัด coverage ของ `scripts/` — เขียนโดยขั้นตอนแยกใน job `test` (audit รอบ 17)
# **ต้องเป็นไฟล์คนละใบกับของแอป** ไม่งั้นตัวเลขรวมจะลากพื้นของแอปลง
SCRIPTS_COVERAGE = ROOT / ".cov-scripts.json"

# กองที่กันการ *ถอด* — โตได้อิสระ (ไม่มีเพดานบน) แต่หดแล้วแดง
REMOVAL_GUARDS = ("gates_total", "cadence_rows", "risk_rows", "deferred_rows")

CADENCE = ROOT / "docs" / "SECURITY-CADENCE.md"
RISK = ROOT / "docs" / "RISK-ASSESSMENT.md"
GOVERNANCE = ROOT / "docs" / "GOVERNANCE.md"

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
        **{name: float(config["tool"]["todolist"]["removals"][name]) for name in REMOVAL_GUARDS},
        "enforced_prohibitions": float(
            config["tool"]["todolist"]["ratchets"]["enforced_prohibitions"]
        ),
        "scripts_coverage": float(config["tool"]["todolist"]["ratchets"]["scripts_coverage"]),
    }


# **ใช้ตัวอ่านตัวเดียวกับที่มีอยู่แล้ว ไม่เขียนตัวที่สอง** (ADR 0039) —
# `whats_pending` อ่านตารางตรวจตามรอบกับทะเบียนของที่เลื่อนอยู่แล้ว การเขียน
# parser ตัวที่สองที่นี่ จะ drift ทันทีที่มีคนแก้รูปตารางฝั่งเดียว
# (เจอกับตัวเองระหว่างเขียน: ตัวนับที่เขียนใหม่ได้ 24 ขณะที่ตัวจริงได้ 23)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import whats_pending  # noqa: E402 - import order required here

# แถวของทะเบียนความเสี่ยง — รูปเดียวกับที่ `tests/test_risk_assessment.py` ใช้
RISK_ROW = re.compile(
    r"^\|([^|]+)\|\s*(ต่ำ|กลาง|สูง)\s*\|\s*(ต่ำ|กลาง|สูง)\s*\|\s*(ต่ำ|กลาง|สูง)\s*\|([^|]*)\|([^|]*)\|\s*$",
    re.MULTILINE,
)


def removal_counts() -> dict[str, int]:
    """นับของจริงของทุกอย่างที่ถอดได้เงียบ — อ่านจากไฟล์ต้นทาง ไม่ใช่จากเอกสารสรุป"""
    gates = yaml.safe_load((ROOT / "gates.yaml").read_text(encoding="utf-8"))["gates"]
    return {
        "gates_total": len(gates),
        "cadence_rows": len(whats_pending.cadence_rows()),
        "risk_rows": len(RISK_ROW.findall(RISK.read_text(encoding="utf-8"))),
        "deferred_rows": len(whats_pending.deferred()),
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


def scripts_coverage() -> float:
    """coverage ของโค้ดที่บังคับกฎ — อ่านจากผลวัดที่ job `test` เขียนไว้

    **ไม่รันเทสต์เอง** เพราะตัวตรวจที่รันชุดเทสต์ซ้ำคือตัวตรวจที่คนจะข้าม ·
    ไม่มีไฟล์ = ขั้นตอนก่อนหน้าไม่ได้รัน ซึ่งต้องดังกว่าการเงียบแล้วผ่าน
    """
    if not SCRIPTS_COVERAGE.is_file():
        raise RuntimeError(
            f"ไม่มี {SCRIPTS_COVERAGE.name} — ขั้นตอน 'coverage ของโค้ดที่บังคับกฎ' "
            "ยังไม่ได้รัน (ดู job `test` ใน ci.yml) · บนเครื่องรัน:\n"
            "  COVERAGE_FILE=/tmp/coverage-scripts pipenv run pytest -q "
            "tests/test_checker_logic.py tests/test_preflight.py tests/test_harness.py "
            "tests/test_asvs_probe.py --cov=scripts "
            "--cov-report=json:.cov-scripts.json --cov-fail-under=0\n"
            "**ไฟล์ข้อมูลต้องอยู่นอก repo** ไม่งั้น coverage combine จะกลืนข้อมูลของแอปไปด้วย"
        )
    data = json.loads(SCRIPTS_COVERAGE.read_text(encoding="utf-8"))
    return float(data["totals"]["percent_covered"])


def enforced_prohibitions() -> int:
    """นับข้อห้ามที่มีเครื่องบังคับจริง — อ่านจากทะเบียนของเทสต์ ไม่ใช่จากเอกสาร

    **import ไม่ได้** เพราะสคริปต์นี้ถูกเรียกจาก job ที่ไม่มี pytest เสมอไป และ
    การ import ไฟล์เทสต์เพื่อจะนับของในนั้น จะลากทั้ง fixture มาด้วย · นับจาก
    โครงของไฟล์แทน ซึ่งเป็นสิ่งที่เปลี่ยนก็ต่อเมื่อมีคนเพิ่ม/ถอดแถวจริง ๆ
    """
    source = (ROOT / "tests" / "test_declared_prohibitions.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "RULES" for t in node.targets
        ):
            return len(node.value.elts)  # type: ignore[attr-defined] - intentionally suppressed
    raise RuntimeError("หาทะเบียน RULES ใน tests/test_declared_prohibitions.py ไม่เจอ")


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
        "enforced_prohibitions": float(enforced_prohibitions()),
        "scripts_coverage": scripts_coverage(),
        **{name: float(value) for name, value in removal_counts().items()},
    }


def problems(floors: dict[str, float], actual: dict[str, float]) -> list[str]:
    """สองทิศ — พื้นที่ลอยเหนือของจริง (ไม่มีใครหมุน) และของจริงที่ตกใต้พื้น (ถอย)"""
    found = []
    for name, floor in sorted(floors.items()):
        now = actual[name]
        # กองกันการถอดโตได้อิสระ — การเพิ่มถูกเฝ้าด้วยด่านอื่นครบแล้ว
        slack = math.inf if name in REMOVAL_GUARDS else SLACK.get(name, DEFAULT_SLACK)
        if now - floor > slack:
            found.append(
                f"{name}: พื้น {floor} แต่ของจริง {now} — ห่าง {now - floor:.2f} "
                f"(เกิน {slack}) · ขยับพื้นขึ้นไปที่ {int(now)} ใน PR เดียวกับที่ทำให้มันดีขึ้น "
                "ไม่งั้นที่ว่างที่เพิ่งได้จะถูกใช้คืนโดยไม่มีใครสังเกต"
            )
        if now < floor and name not in OWNED_BY_A_TOOL:
            if name in REMOVAL_GUARDS:
                found.append(
                    f"{name}: ประกาศไว้ {int(floor)} แต่ของจริงเหลือ {int(now)} — "
                    "**มีของถูกถอดออกไป** · ถ้าตั้งใจถอดจริง ให้ลดตัวเลขใน "
                    "[tool.todolist.removals] ใน PR เดียวกันพร้อมเหตุผลใน commit — "
                    "การถอดต้องเป็นคำตัดสินที่มีคนเซ็นชื่อ ไม่ใช่ผลข้างเคียงของการเก็บกวาด"
                )
            else:
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
