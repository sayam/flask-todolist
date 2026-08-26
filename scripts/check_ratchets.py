"""เกณฑ์แบบ ratchet ต้องไม่ลอยเหนือของจริง — audit รอบ 12 ข้อ 1

**กลไกอยู่ที่ verifiable-gates แล้ว** (ADR 0077 · ขั้น 3c) — `verifiable_gates.ratchets`
ตัดสิน และ `verifiable_gates.measure` อ่านตัวเลขที่โปรเจกต์ไหนก็มี · **ที่นี่เหลือสิ่งที่
เป็นของ todolist จริง ๆ**: ทะเบียนว่ามี ratchet ตัวไหนบ้าง อ่านของจริงจากไฟล์ไหน
และ**ถ้อยคำที่คนอ่าน** ซึ่งเป็นภาษาไทยและไม่ใช่ของที่พกไปที่อื่นได้

`pyproject.toml` เขียนกำกับไว้ทั้งสองที่ว่า "ขยับขึ้นได้อย่างเดียว" — ทิศถูกแล้ว
แต่**ไม่มีอะไรทำให้มันขยับ** · ผลที่วัดได้ 2026-08-18 (หกวันหลังตั้งเลข):
coverage จริง 97.11% ขณะที่พื้นยังเป็น 96 ที่ตั้งไว้ตอนวัดได้ 96.31% —
ที่ว่าง 1.11 จุดแปลว่า **โค้ดที่มีเทสต์คุมอยู่ราว 54 บรรทัดหายไปได้โดยไม่มีอะไรแดง**

กลไกที่ใช้ตรงนี้เป็นตัวเดียวกับที่ ADR 0065 ใช้กับเพดานของ `CLAUDE.md` อยู่แล้ว
(`LINE_SLACK`) — เพดาน/พื้นที่ห่างจากของจริงเกินระยะที่ประกาศ คือเกณฑ์ที่ไม่ได้ตั้ง

**audit รอบ 14 เพิ่มทิศที่สองและ ratchet ตัวที่สาม**: ตัวตรวจรุ่นแรกอ่านเฉพาะพื้น
ที่เป็น *ตัวเลข* ใน config ของเครื่องมือ — ratchet ที่เขียนเป็น *ประโยค* จึงรอดมาได้
ทั้งใบ · strict list ของ mypy บอกว่า "ขยาย ห้ามหด" มาตั้งแต่ Phase 2 โดยไม่มีอะไร
บังคับสักทาง และเป้าที่เขียนกำกับ ("ทั้งแอปภายใน Phase 2") หมดอายุไปสิบหกเฟส

ratchet ที่นับเป็น *จำนวน* ต่างจากที่นับเป็น *เปอร์เซ็นต์* ตรงระยะที่ให้ลอยได้:
เปอร์เซ็นต์ผันผวนเองได้จากบรรทัดที่ถูกยกเว้นเพิ่ม/ลด แต่จำนวนโมดูลเปลี่ยนก็ต่อเมื่อ
มีคนแก้ลิสต์ — **ระยะจึงเป็น 0 และตรวจสองทิศ**

**audit รอบ 17 เพิ่ม `scripts_coverage`** — โค้ดที่บังคับกฎอยู่นอก `source` ของ
coverage มาตลอด (`source = ["app"]`) จึงเป็นโค้ดชุดเดียวในโปรเจกต์ที่ไม่มีเกณฑ์
บังคับตัวเอง ทั้งที่มันคือสิ่งที่บังคับทุกอย่างที่เหลือ · วัดแยกไฟล์ข้อมูลโดยตั้งใจ:
ยัด `scripts` เข้า `source` เมื่อไหร่ ตัวเลขรวมจะตกต่ำกว่า 97 แล้วพื้นของแอปจะถูก
ลดด้วยผลข้างเคียง

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

import pathlib
import re
import sys
import tomllib

import yaml  # type: ignore[import-untyped]

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vendor" / "verifiable-gates" / "src"))

from verifiable_gates import measure, ratchets  # noqa: E402 — ต้องต่อ path ให้ vendor ก่อน import

PYPROJECT = ROOT / "pyproject.toml"
APP = ROOT / "app"
RISK = ROOT / "docs" / "RISK-ASSESSMENT.md"
# ทะเบียนผิวนอกรีโป (ADR 0072) — แถวที่ยอมรับตรง ๆ ว่ายังไม่มีใครเทียบ
EXTERNAL_SURFACE = ROOT / "docs" / "EXTERNAL-SURFACE.md"
NO_OWNER = "ยังไม่มีใคร"

# ผลวัด coverage ของ `scripts/` — เขียนโดยขั้นตอนแยกใน job `test` (audit รอบ 17)
# **ต้องเป็นไฟล์คนละใบกับของแอป** ไม่งั้นตัวเลขรวมจะลากพื้นของแอปลง
SCRIPTS_COVERAGE = ROOT / ".cov-scripts.json"

# **คัดลอกจากขั้นตอนจริงใน `ci.yml` ไม่ใช่จากความจำ** — รุ่นก่อนหน้าไล่ชื่อไฟล์เทสต์
# ไว้ตรง ๆ สามชื่อ และสองในสามไม่มีอยู่บนดิสก์แล้ว · คำแนะนำที่พาไปสู่คำสั่งที่รันไม่ได้
# แย่กว่าไม่มีคำแนะนำ เพราะคนอ่านจะเชื่อว่าตัวเองทำอะไรผิด
#
# **`COVERAGE_PROCESS_START` ไม่ใช่ของประดับ** — สคริปต์ที่เทสต์ยิงผ่าน subprocess
# (รูปที่ repo นี้บังคับเองว่าดีกว่า) ไม่ถูกนับเลยถ้าไม่มีมัน · รุ่นก่อนหน้าของ
# hint นี้ไม่มี แล้ววันที่มีคนเชื่อมันจริง ๆ ก็วัดได้ 57.96 ขณะที่ด่านซึ่งตัดสิน
# วัดได้ 61.67 — คำสั่งที่ต่างจากด่านหนึ่งตัวแปร คือคำสั่งที่ตอบคนละคำถาม
SCRIPTS_COVERAGE_HINT = (
    " (ดู job `test` ใน ci.yml) · บนเครื่องรัน:\n"
    "  files=$(grep -lE 'from scripts[. ]|^import scripts|/ \"scripts\"' tests/*.py)\n"
    "  COVERAGE_PROCESS_START=.coveragerc-scripts \\\n"
    "  COVERAGE_FILE=/tmp/coverage-scripts pipenv run pytest -q --no-header $files \\\n"
    "    --cov=scripts --cov-config=.coveragerc-scripts \\\n"
    "    --cov-report=json:.cov-scripts.json --cov-fail-under=0\n"
    "**ไฟล์ข้อมูลต้องอยู่นอก repo** ไม่งั้น coverage combine จะกลืนข้อมูลของแอปไปด้วย"
)

# กองที่กันการ *ถอด* — โตได้อิสระ (ไม่มีเพดานบน) แต่หดแล้วแดง
REMOVAL_GUARDS = ("gates_total", "cadence_rows", "risk_rows", "deferred_rows")

# กองที่กันการ *เพิ่ม* — ตรงข้ามกับ ratchet ทั้งหมดข้างบน (audit r21 ข้อ 2)
#
# คำสั่งปิดเครื่องตรวจรายบรรทัดคือการปิดกฎที่บรรทัดนั้น · ruff (`RUF100`) กับ mypy
# (`warn_unused_ignores`) จับให้แล้วว่าอันไหน**ค้าง** จึงไม่ใช่หนี้เงียบแบบล้าสมัย —
# แต่**ไม่มีตัวเลขไหนเห็นมันโต** ขณะที่ repo มี ratchet คุมคุณภาพขึ้นทางเดียว
# และมี `[tool.todolist.removals]` คุมการถอด · วัดตอนตั้งเพดาน (2026-08-21):
# 99 บรรทัด และ 53 ในนั้นไม่มีเหตุผลกำกับ ทั้งที่กติกาเดียวกันถูกบังคับกับ
# 46 บรรทัดในทะเบียนแฟ้มมาตลอด
#
# `gates_ceiling` นับตัวเดียวกับ `removals.gates_total` แต่คนละทิศ — พื้นกันถอด
# เพดานกันโต (ADR 0075 ข้อ 3) · ทั้งคู่ต้องเท่ากับของจริง จึงล็อกจำนวน gate ไว้
# จนกว่าจะมีคำตัดสิน
CEILINGS = (
    "suppressions",
    "suppressions_without_reason",
    "external_surface_unowned",
    "gates_ceiling",
)

SUPPRESSION_SOURCES = ("app/**/*.py", "scripts/*.py", "tests/*.py")
# `app/sun_data.py` generate มา · `migrations/` อยู่นอกขอบเขต ruff อยู่แล้ว
SUPPRESSION_SKIP = ("sun_data.py", "migrations")

# ชั้นที่ไม่ถูกนับเป็นโมดูล strict — **ยังไม่เปลี่ยนตัวเลขวันนี้ และนั่นคือประเด็น**
# `exclude` ของ mypy ตัด `enhancements/` ทิ้งอยู่แล้ว และ pattern ใน strict list
# ตอนนี้ยังไม่มีตัวไหนกวาดถึงมัน · วันที่มีคนเปลี่ยน `app.plugins` เป็น
# `app.plugins.*` พื้นจะเริ่มขยับตาม**การวางไดเรกทอรี** แทนที่จะขยับตามความเข้ม
# ของ type check — วางส่วนเสริมเพิ่มหนึ่งตัวแล้ว ratchet แดง โดยไม่มีใครแตะโค้ด
# ที่ถูกตรวจสักบรรทัด · ประกาศเป็นค่าคงที่เพื่อให้รอยต่อนี้ถูกเทสต์ได้
STRICT_SKIP_PARTS = ("__pycache__", "enhancements")

# ทะเบียน ratchet ของ repo นี้ — ชื่อไหนไม่อยู่ในนี้ถูกตัดสินอย่างพื้นธรรมดา
#
# **ตัวที่นับเป็นจำนวนใช้ระยะ 0** เพราะมันไม่ผันผวนเอง ต้องมีคนแก้ลิสต์เท่านั้น ·
# `coverage` กับ `interrogate` มีเครื่องมือเจ้าของบังคับทิศลงให้อยู่แล้ว
# (`fail_under`) ที่นี่จึงดูแค่ทิศบน ไม่งั้นคนอ่านจะได้ข้อความสองอันที่บอกให้ทำ
# คนละอย่างกับปัญหาเดียว
RATCHETS = {
    "coverage": ratchets.Ratchet("coverage", owned_by_a_tool=True),
    "interrogate": ratchets.Ratchet("interrogate", owned_by_a_tool=True),
    "mypy_strict_modules": ratchets.Ratchet("mypy_strict_modules", slack=0.0),
    "enforced_prohibitions": ratchets.Ratchet("enforced_prohibitions", slack=0.0),
    # **ระยะ 2 จุด ไม่ใช่ 1** — ตัวเลขนี้สั่นตามเครื่องที่วัด: ชุดเดียวกัน 424 เทสต์
    # วัดได้ 61.67 บน runner ของ CI และ 60.70 บนเครื่อง dev ในวันเดียวกัน เพราะ
    # สคริปต์บางตัวเดินเส้นทางที่ขึ้นกับเครื่องมือที่ติดตั้งอยู่ · ระยะ 1 จุดทำให้
    # ต้องเลือกระหว่าง "แดงบน CI" กับ "แดงบนเครื่อง" ซึ่งอย่างหลังคือสิ่งที่ทำให้
    # คนเลิกรันด่านก่อนเปิด PR (วัดเอง 2026-08-26 · ขั้น 3c)
    "scripts_coverage": ratchets.Ratchet("scripts_coverage", slack=2.0),
    **{name: ratchets.Ratchet(name, kind=ratchets.REMOVAL_GUARD) for name in REMOVAL_GUARDS},
    **{name: ratchets.Ratchet(name, kind=ratchets.CEILING) for name in CEILINGS},
}

# ถ้อยคำเป็นของโปรเจกต์ ไม่ใช่ของกลไก — คนที่อ่าน CI ของที่นี่อ่านภาษาไทย
MESSAGES = {
    "ceiling_exceeded": (
        "{name}: เพดาน {declared:.0f} แต่ของจริง {actual:.0f} — **มีข้อยกเว้นเพิ่มขึ้น** · "
        "ถ้าจำเป็นจริง ให้ขยับเพดานใน [tool.todolist.ceilings] ใน PR เดียวกัน "
        "พร้อมเหตุผลใน commit — การปิดเครื่องตรวจต้องเป็นคำตัดสินที่มีคนเซ็นชื่อ"
    ),
    "ceiling_slack": (
        "{name}: เพดาน {declared:.0f} แต่ของจริงเหลือ {actual:.0f} — "
        "ลดเพดานลงไปที่ {actual:.0f} ใน PR เดียวกับที่ทำให้มันดีขึ้น "
        "ไม่งั้นที่ว่างที่เพิ่งได้จะถูกถมกลับโดยไม่มีใครสังเกต"
    ),
    "floor_slack": (
        "{name}: พื้น {declared} แต่ของจริง {actual} — ห่าง {gap:.2f} "
        "(เกิน {slack}) · ขยับพื้นขึ้นไปที่ {actual:.0f} ใน PR เดียวกับที่ทำให้มันดีขึ้น "
        "ไม่งั้นที่ว่างที่เพิ่งได้จะถูกใช้คืนโดยไม่มีใครสังเกต"
    ),
    "removal": (
        "{name}: ประกาศไว้ {declared:.0f} แต่ของจริงเหลือ {actual:.0f} — "
        "**มีของถูกถอดออกไป** · ถ้าตั้งใจถอดจริง ให้ลดตัวเลขใน "
        "[tool.todolist.removals] ใน PR เดียวกันพร้อมเหตุผลใน commit — "
        "การถอดต้องเป็นคำตัดสินที่มีคนเซ็นชื่อ ไม่ใช่ผลข้างเคียงของการเก็บกวาด"
    ),
    "regression": (
        "{name}: ของจริง {actual} ต่ำกว่าพื้นที่ประกาศไว้ {declared} — **นี่คือการถอย** "
        "ratchet ตัวนี้ไม่มีเครื่องมือเจ้าของบังคับทิศลงให้ ตัวตรวจนี้จึงเป็นตัวเดียว "
        "ที่เห็น · ทางที่ถูกคือคืนของที่ถอดออก ไม่ใช่ลดพื้น"
    ),
}

# **ใช้ตัวอ่านตัวเดียวกับที่มีอยู่แล้ว ไม่เขียนตัวที่สอง** (ADR 0039) —
# `whats_pending` อ่านตารางตรวจตามรอบกับทะเบียนของที่เลื่อนอยู่แล้ว การเขียน
# parser ตัวที่สองที่นี่ จะ drift ทันทีที่มีคนแก้รูปตารางฝั่งเดียว
# (เจอกับตัวเองระหว่างเขียน: ตัวนับที่เขียนใหม่ได้ 24 ขณะที่ตัวจริงได้ 23)
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import whats_pending  # noqa: E402

# แถวของทะเบียนความเสี่ยง — รูปเดียวกับที่ `tests/test_risk_assessment.py` ใช้
RISK_ROW = re.compile(
    r"^\|([^|]+)\|\s*(ต่ำ|กลาง|สูง)\s*\|\s*(ต่ำ|กลาง|สูง)\s*\|\s*(ต่ำ|กลาง|สูง)\s*\|([^|]*)\|([^|]*)\|\s*$",
    re.MULTILINE,
)

classify_suppression = measure.classify_suppression


def declared() -> dict[str, float]:
    """พื้นที่ประกาศไว้ใน `pyproject.toml` — อ่านจากไฟล์จริง ไม่ใช่จากคอมเมนต์"""
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return {
        "coverage": float(config["tool"]["coverage"]["report"]["fail_under"]),
        "interrogate": float(config["tool"]["interrogate"]["fail-under"]),
        "mypy_strict_modules": float(config["tool"]["todolist"]["ratchets"]["mypy_strict_modules"]),
        **{name: float(config["tool"]["todolist"]["removals"][name]) for name in REMOVAL_GUARDS},
        **{name: float(config["tool"]["todolist"]["ceilings"][name]) for name in CEILINGS},
        "enforced_prohibitions": float(
            config["tool"]["todolist"]["ratchets"]["enforced_prohibitions"]
        ),
        "scripts_coverage": float(config["tool"]["todolist"]["ratchets"]["scripts_coverage"]),
    }


def removal_counts() -> dict[str, int]:
    """นับของจริงของทุกอย่างที่ถอดได้เงียบ — อ่านจากไฟล์ต้นทาง ไม่ใช่จากเอกสารสรุป"""
    gates = yaml.safe_load((ROOT / "gates.yaml").read_text(encoding="utf-8"))["gates"]
    return {
        "gates_total": len(gates),
        "cadence_rows": len(whats_pending.cadence_rows()),
        "risk_rows": len(RISK_ROW.findall(RISK.read_text(encoding="utf-8"))),
        "deferred_rows": len(whats_pending.deferred()),
    }


def suppression_counts() -> dict[str, int]:
    """นับการปิดเครื่องตรวจรายบรรทัด — ทั้งหมด และที่ไม่มีเหตุผลกำกับ

    "มีเหตุผล" คือมีข้อความต่อท้ายรหัสกฎ · คำสั่งที่มีแต่รหัสเปล่า ๆ บอกว่ากฎไหน
    ถูกปิด แต่ไม่บอกว่าทำไม ซึ่งเป็นคนละคำถามกัน — และเป็นคำถามที่ทะเบียนแฟ้ม
    ทุกใบในโปรเจกต์นี้บังคับให้ตอบมาตลอด
    """
    return measure.suppression_counts(ROOT, SUPPRESSION_SOURCES, SUPPRESSION_SKIP)


def strict_modules() -> int:
    """นับโมดูลใน `app/` ที่ตกอยู่ใต้ strict list จริง ๆ

    **ไม่นับส่วนเสริมของ plugin** เพราะ mypy ตั้งชื่อโมดูลให้มันไม่ได้ (ไอดีมีขีดกลาง)
    และ `exclude` ของ mypy ตัดทิ้งอยู่แล้ว — การนับมันจะทำให้พื้นขยับตามการวาง
    ไดเรกทอรี ซึ่งไม่เกี่ยวกับความเข้มของ type check เลย
    """
    return measure.strict_modules(ROOT, PYPROJECT, APP, skip_parts=STRICT_SKIP_PARTS)


def scripts_coverage() -> float:
    """coverage ของโค้ดที่บังคับกฎ — อ่านจากผลวัดที่ job `test` เขียนไว้

    **ไม่รันเทสต์เอง** เพราะตัวตรวจที่รันชุดเทสต์ซ้ำคือตัวตรวจที่คนจะข้าม ·
    ไม่มีไฟล์ = ขั้นตอนก่อนหน้าไม่ได้รัน ซึ่งต้องดังกว่าการเงียบแล้วผ่าน
    """
    try:
        return measure.coverage_json_percent(SCRIPTS_COVERAGE, hint=SCRIPTS_COVERAGE_HINT)
    except RuntimeError as absent:
        raise RuntimeError(
            f"ไม่มี {SCRIPTS_COVERAGE.name} — ขั้นตอน 'coverage ของโค้ดที่บังคับกฎ' "
            f"ยังไม่ได้รัน{SCRIPTS_COVERAGE_HINT}"
        ) from absent


def enforced_prohibitions() -> int:
    """นับข้อห้ามที่มีเครื่องบังคับจริง — อ่านจากทะเบียนของเทสต์ ไม่ใช่จากเอกสาร

    **import ไม่ได้** เพราะสคริปต์นี้ถูกเรียกจาก job ที่ไม่มี pytest เสมอไป และ
    การ import ไฟล์เทสต์เพื่อจะนับของในนั้น จะลากทั้ง fixture มาด้วย · นับจาก
    โครงของไฟล์แทน ซึ่งเป็นสิ่งที่เปลี่ยนก็ต่อเมื่อมีคนเพิ่ม/ถอดแถวจริง ๆ
    """
    return measure.list_literal_length(ROOT / "tests" / "test_declared_prohibitions.py", "RULES")


def external_surface_unowned() -> int:
    """นับ**แถวในตาราง**เท่านั้น — ร้อยแก้วที่อธิบายคำว่า "ยังไม่มีใคร" ไม่ใช่ผิวที่ไม่มีเจ้าของ

    ผิวนอกรีโปโตได้ทุกครั้งที่ GitHub เพิ่ม setting ใหม่ · เพดานนี้ทำให้การเพิ่ม
    แถวที่ไม่มีเจ้าของเป็นคำตัดสิน และทำให้การหาเจ้าของให้แถวเดิมถูกบันทึก (ADR 0072)
    """
    rows = 0
    for line in EXTERNAL_SURFACE.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) >= 4 and line.startswith("|") and NO_OWNER in cells[-2]:
            rows += 1
    return rows


def measured() -> dict[str, float]:
    """ค่าจริงวันนี้ — รันเครื่องมือเอง เพราะคอมเมนต์ที่เขียนกำกับไว้คือสิ่งที่กำลังตรวจ"""
    counts = removal_counts()
    return {
        "coverage": measure.coverage_total(ROOT),
        "interrogate": measure.docstring_coverage(ROOT, "app"),
        "mypy_strict_modules": float(strict_modules()),
        "enforced_prohibitions": float(enforced_prohibitions()),
        "scripts_coverage": scripts_coverage(),
        "external_surface_unowned": float(external_surface_unowned()),
        "gates_ceiling": float(counts["gates_total"]),
        **{name: float(value) for name, value in counts.items()},
        **{name: float(value) for name, value in suppression_counts().items()},
    }


def problems(floors: dict[str, float], actual: dict[str, float]) -> list[str]:
    """สองทิศ — พื้นที่ลอยเหนือของจริง (ไม่มีใครหมุน) และของจริงที่ตกใต้พื้น (ถอย)"""
    return ratchets.problems(RATCHETS, floors, actual, MESSAGES)


def main() -> int:
    """อ่านพื้นที่ประกาศ → วัดของจริง → คืน 1 เมื่อพื้นลอยต่ำเกินไป"""
    try:
        floors, actual = declared(), measured()
    except RuntimeError as problem:
        print(f"ตรวจ ratchet ไม่ได้: {problem}", file=sys.stderr)
        return 2

    for name in sorted(floors):
        kind = "เพดาน" if name in CEILINGS else "พื้น  "
        print(f"  {name:28s} {kind} {floors[name]:6.1f} · ของจริง {actual[name]:6.2f}")

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
