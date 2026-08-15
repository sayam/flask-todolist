"""เอกสารที่คนนอกอ่านก่อนแตะโค้ด ต้องยังพูดตรงกับของจริง

`README.md` · `CONTRIBUTING.md` · `SECURITY.md` · `CODE_OF_CONDUCT.md` เป็นหน้า
แรกที่คนนอกเจอ **และเป็นเอกสารที่ไม่มีใครรันจึงเน่าเงียบที่สุด** — ลิงก์ที่ชี้ไป
หาไฟล์ที่ถูกเปลี่ยนชื่อไปแล้ว หรือคำสั่งที่ก๊อปไปวางแล้วไม่ทำงาน ทำให้คนที่ตั้งใจ
จะช่วยเลิกกลางทางโดยที่เจ้าของ repo ไม่มีทางรู้

เจอจริงตอนเขียนชุดนี้: เอกสารสามที่บอกว่า CI มี "21 job" ขณะที่ไฟล์ workflow
นิยามไว้ 20 ตัว — เลข 21 คือจำนวน *check* เพราะ `dialects` เป็น matrix สองยี่ห้อ
ไม่มีใครโกหก แต่ก็ไม่มีใครตรวจ และตัวเลขนั้นอยู่ในเอกสารมาตั้งแต่ปิด Phase 7
"""

import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW_DIR = ROOT / ".github" / "workflows"

PUBLIC_DOCS = (
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "CHANGELOG.md",
    # เอกสารใน docs/ ที่ทำหน้าที่เดียวกับหน้า contributor — ลิงก์ตายไม่ได้เท่ากัน
    "docs/DEVELOPMENT.md",
)

# `[ข้อความ](เป้าหมาย)` ทุกแบบ · ใช้ยืนยันว่าตัวดึงลิงก์ยังทำงานอยู่
ANY_LINK = re.compile(r"\[[^\]]+\]\(([^)\s]+)\)")
# เฉพาะเป้าหมายที่เป็น path ในโปรเจกต์ (ไม่ใช่ http/mailto/anchor)
LINK = re.compile(r"\[[^\]]+\]\((?!https?:|mailto:|#)([^)\s]+)\)")

# `20 jobs (21 checks)` และ `20 job (21 check)`
JOB_CLAIM = re.compile(r"(\d+)\s+jobs?\s*\((\d+)\s+checks?\)")

DOCS_CLAIMING_JOB_COUNTS = ("CONTRIBUTING.md", "CLAUDE.md")


@pytest.fixture(scope="module")
def ci_jobs():
    """(จำนวนนิยาม job, จำนวน check ที่จะขึ้นบน GitHub) — matrix นับตามจำนวนรอบ

    อ่าน **ทุกไฟล์ workflow** ไม่ใช่แค่ `ci.yml` — วันที่มีใครแยก job ออกไป
    ไฟล์ใหม่ ตัวเลขที่โฆษณาไว้จะกลายเป็นเลขที่ต่ำกว่าความจริงโดยไม่มีอะไรฟ้อง
    """
    files = sorted(WORKFLOW_DIR.glob("*.y*ml"))
    assert files, "ไม่เจอไฟล์ workflow สักไฟล์"

    defined, checks = 0, 0
    for path in files:
        jobs = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("jobs") or {}
        defined += len(jobs)
        for job in jobs.values():
            matrix = (job.get("strategy") or {}).get("matrix") or {}
            axes = [value for value in matrix.values() if isinstance(value, list)]
            runs = 1
            for values in axes:
                runs *= len(values)
            checks += runs
    return defined, checks


@pytest.mark.parametrize("name", PUBLIC_DOCS)
def test_every_relative_link_resolves(name):
    """ลิงก์ที่ตายอยู่ในหน้าแรกที่คนนอกอ่าน = คนอ่านสรุปว่าโปรเจกต์ถูกทิ้งแล้ว"""
    path = ROOT / name
    assert path.is_file(), f"ไม่มี {name} ที่รากของ repo"

    text = path.read_text(encoding="utf-8")

    # กันการ "ผ่านเพราะดึงลิงก์ไม่ออกเลย" — ไฟล์ที่ไม่มีลิงก์ภายในเป็นเรื่องปกติ
    # (CODE_OF_CONDUCT ชี้ออกนอกทั้งหมด) แต่ไฟล์ที่ไม่มีลิงก์*เลย*แปลว่า regex พัง
    assert ANY_LINK.findall(text), f"ดึงลิงก์จาก {name} ไม่ได้สักอัน — ตัวดึงลิงก์พังหรือเปล่า"

    # ลิงก์ relative ต้องแตกจากไดเรกทอรีของไฟล์นั้น ไม่ใช่จากรากเสมอ —
    # ไฟล์ใน docs/ เขียน (ROADMAP.md) ซึ่งแปลว่า docs/ROADMAP.md
    base = path.parent
    targets = set(LINK.findall(text))
    broken = sorted(t for t in targets if not (base / t.split("#")[0]).resolve().exists())
    assert not broken, f"{name} ชี้ไปหาไฟล์ที่ไม่มีอยู่: {broken}"


@pytest.mark.parametrize("name", DOCS_CLAIMING_JOB_COUNTS)
def test_the_ci_job_count_we_advertise_is_the_real_one(name, ci_jobs):
    """เลขที่โฆษณาไว้ต้องมาจากไฟล์ workflow ไม่ใช่จากความจำของครั้งล่าสุด"""
    defined, checks = ci_jobs
    claims = JOB_CLAIM.findall((ROOT / name).read_text(encoding="utf-8"))
    assert claims, (
        f"{name} ไม่ได้บอกจำนวน job ในรูปแบบ `N jobs (M checks)` — "
        "ถ้าตั้งใจถอดออกให้เอาชื่อไฟล์ออกจาก DOCS_CLAIMING_JOB_COUNTS ด้วย"
    )

    wrong = [
        f"บอกว่า {claimed_jobs} job / {claimed_checks} check"
        for claimed_jobs, claimed_checks in claims
        if (int(claimed_jobs), int(claimed_checks)) != (defined, checks)
    ]
    assert not wrong, f"{name} {wrong} แต่ ci.yml มี {defined} job / {checks} check"


def test_the_readme_advertises_the_real_ci_job_count(ci_jobs):
    """README เขียนเลขแบบร้อยเรียง (`20 CI jobs`) ไม่ใช่รูปแบบเดียวกับ CONTRIBUTING"""
    defined, _ = ci_jobs
    text = (ROOT / "README.md").read_text(encoding="utf-8")

    claims = re.findall(r"(\d+)\s+CI jobs", text) + re.findall(r"CI\s+(\d+)\s+job", text)
    assert claims, "README ไม่ได้บอกจำนวน job ของ CI เลย — ถ้าตั้งใจถอดออก ให้ลบเทสต์นี้ด้วย"

    wrong = sorted({claimed for claimed in claims if int(claimed) != defined})
    assert not wrong, f"README บอกว่ามี {wrong} job แต่ ci.yml นิยามไว้ {defined}"


def test_the_readme_advertises_the_real_number_of_adrs():
    """ทั้งครึ่งอังกฤษและครึ่งไทยพูดถึงจำนวน ADR — ทั้งคู่ต้องตรงกับดิสก์

    ครอบ `CONTRIBUTING.md` ด้วย — รอบตรวจหลังเฟส 18 เจอ "the 38 records" ค้าง
    อยู่ที่นั่นทั้งที่ดิสก์มี 49 เพราะ regex เดิมอ่านแต่ README (เลขที่ไม่มีเทสต์
    อ่านคู่คือเลขที่ผิดอยู่แล้วโดยยังไม่มีใครรู้)
    """
    actual = len([path for path in (ROOT / "docs" / "adr").glob("*.md") if path.name[:4].isdigit()])

    for name in ("README.md", "CONTRIBUTING.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        claims = (
            re.findall(r"(\d+) architecture decision records", text)
            + re.findall(r"the (\d+) records in", text)
            + re.findall(r"\)\s*(\d+)\s*ใบ", text)
        )
        assert claims, f"{name} ไม่ได้บอกจำนวน ADR ในรูปแบบที่เทสต์อ่านได้"
        wrong = sorted({claimed for claimed in claims if int(claimed) != actual})
        assert not wrong, f"{name} บอกว่ามี ADR {wrong} ใบ แต่บนดิสก์มี {actual} ใบ"


def test_the_readme_advertises_the_real_coverage_floor():
    """เลข coverage ที่โฆษณาต้องมาจาก `fail_under` จริง ไม่ใช่จากตอนที่วัดครั้งล่าสุด"""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    floor = re.search(r"^fail_under\s*=\s*(\d+)", pyproject, re.MULTILINE)
    assert floor, "อ่าน `fail_under` จาก pyproject.toml ไม่ได้ — ชื่อคีย์เปลี่ยนไปแล้ว"

    text = (ROOT / "README.md").read_text(encoding="utf-8")
    claims = re.findall(r"\*\*(\d+)%\*\*", text)
    assert claims, "README ไม่ได้บอกพื้น coverage ในรูปแบบ `**NN%**`"

    wrong = sorted({claimed for claimed in claims if int(claimed) != int(floor.group(1))})
    assert not wrong, f"README บอกพื้น coverage {wrong}% แต่ pyproject บังคับ {floor.group(1)}%"


def test_contributing_points_at_gates_that_exist():
    """คำสั่งที่บอกให้ contributor รันต้องมีไฟล์รองรับจริง"""
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")

    for expected in (".pre-commit-config.yaml", "pyproject.toml", "Pipfile"):
        assert (ROOT / expected).is_file(), f"CONTRIBUTING พึ่ง {expected} ที่หายไปแล้ว"

    scripts = set(re.findall(r"scripts/[\w.-]+\.py", text))
    missing = sorted(name for name in scripts if not (ROOT / name).is_file())
    assert not missing, f"CONTRIBUTING บอกให้รันสคริปต์ที่ไม่มีอยู่: {missing}"


def test_contributing_states_the_licence_terms_for_contributions():
    """ไม่มี CLA แปลว่า inbound = outbound ต้องเขียนไว้ ไม่ใช่ปล่อยให้เดา (ADR 0038)"""
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "MIT" in text, "CONTRIBUTING ไม่ได้บอกว่าสิ่งที่ส่งมาถูกเผยแพร่ด้วย license อะไร"
    assert "CLA" in text, "CONTRIBUTING ไม่ได้บอกว่ามี CLA หรือไม่ — คนส่ง PR ต้องรู้ก่อนส่ง"


def test_the_code_of_conduct_names_a_private_reporting_route():
    """CoC ที่บอกให้ 'แจ้งคนดูแล' โดยไม่มีทางส่งจริง ไม่ใช่กระบวนการบังคับใช้"""
    text = (ROOT / "CODE_OF_CONDUCT.md").read_text(encoding="utf-8")
    assert "security/advisories/new" in text, "CoC ไม่ได้บอกช่องทางส่งรายงานแบบส่วนตัว"
    assert "support.github.com" in text, (
        "CoC ไม่ได้บอกทางออกสำหรับกรณีที่เรื่องเป็นเรื่องของคนดูแลเอง — "
        "โปรเจกต์คนเดียวไม่มีใครให้อุทธรณ์ต่อ ต้องเขียนไว้ให้ตรง"
    )
