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

DOCS_CLAIMING_JOB_COUNTS = (
    "CONTRIBUTING.md",
    "CLAUDE.md",
    "docs/DEVELOPMENT.md",
    "docs/ROADMAP.md",
)

# ใบตอบ badge เป็นเอกสารที่คนนอกอ่าน (ลิงก์จาก README) และเต็มไปด้วยตัวเลข
# ที่ไม่มีใครรัน — เน่าไปแล้วสามจุดก่อนจะมีเทสต์ชุดนี้
BADGE_WORKSHEET = "docs/BEST-PRACTICES.md"
# DOI ที่ README พิมพ์ออกมา — ทั้งในร้อยแก้วและใน URL ของ badge
DOI_IN_TEXT = re.compile(r"10\.\d{4,9}/[-._;()/:a-zA-Z0-9]*zenodo[.\d]+")
CITATION = ROOT / "CITATION.cff"
# โฮสต์ของรูป badge ที่ **วัดแล้ว** ว่า camo ของ GitHub ดึงไหวสม่ำเสมอ
# (ยิงผ่าน camo สามครั้งต่อใบ — ดูเหตุผลใน docstring ของเทสต์ข้างล่าง)
BADGE_HOSTS = {
    "https://img.shields.io/": "ทุกใบที่ใช้อยู่ 200 ทุกครั้ง",
    "https://www.bestpractices.dev/": "badge ของ OpenSSF เอง · 200 ทุกครั้ง",
}
VERSION_SOURCE = (ROOT / "app" / "__init__.py").read_text(encoding="utf-8")


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


def test_the_badge_worksheet_tracks_the_current_version():
    """ใบตอบ badge อ้างเลขรุ่นสามที่ — ต้องเป็นรุ่นปัจจุบัน ไม่ใช่รุ่นที่กรอกครั้งล่าสุด

    เจอจริง 2026-08-17: ไฟล์ยังเขียน v1.5.0 อยู่สามจุดหลังออก v1.6.0 ไปแล้ว
    ทั้งที่ `docs/RELEASE.md` มีขั้นตอน "อัปเดต BEST-PRACTICES ให้ตรงกับที่กรอก
    จริง" อยู่แล้ว — ขั้นตอนที่ไม่มีเทสต์อ่านคู่ก็เน่าเหมือนเลขที่ไม่มีเทสต์อ่านคู่
    (ช่อง `release_notes_vulns` อ้างรุ่นเก่าได้โดยชอบ เพราะมันเล่าว่า *รุ่นไหน*
    แก้ CVE — เทสต์นี้จึงจับเฉพาะสองสำนวนที่แปลว่า "รุ่นล่าสุด")
    """
    version = re.search(r'^__version__\s*=\s*"([\d.]+)"', VERSION_SOURCE, re.MULTILINE)
    assert version, "อ่าน __version__ จาก app/__init__.py ไม่ได้"

    text = (ROOT / BADGE_WORKSHEET).read_text(encoding="utf-8")
    claims = re.findall(r"ล่าสุด v([\d.]+)", text) + re.findall(r"v1\.0\.0 ถึง v([\d.]+)", text)
    assert claims, f"{BADGE_WORKSHEET} ไม่ได้อ้างรุ่นล่าสุดในรูปแบบที่เทสต์อ่านได้"

    wrong = sorted({claimed for claimed in claims if claimed != version.group(1)})
    assert not wrong, (
        f"{BADGE_WORKSHEET} อ้างว่ารุ่นล่าสุดคือ {wrong} แต่ __version__ คือ {version.group(1)} — "
        "ตอนออกรุ่นต้องอัปเดตไฟล์นี้พร้อมฟอร์มบน bestpractices.dev (docs/RELEASE.md ขั้น 7)"
    )


def test_the_badge_worksheet_counts_the_real_supply_chain_gates():
    """จำนวน gate ของแกน supply chain ในใบตอบ ต้องนับจาก `gates.yaml` จริง"""
    gates = yaml.safe_load((ROOT / "gates.yaml").read_text(encoding="utf-8"))["gates"]
    actual = sum(1 for gate in gates if gate.get("axis") == "supply-chain")

    text = (ROOT / BADGE_WORKSHEET).read_text(encoding="utf-8")
    claims = re.findall(r"SUPPLY-CHAIN\.md`?\s*\((\d+) gate\)", text)
    assert claims, f"{BADGE_WORKSHEET} ไม่ได้บอกจำนวน gate ของแกน supply chain"

    wrong = sorted({claimed for claimed in claims if int(claimed) != actual})
    assert not wrong, f"{BADGE_WORKSHEET} บอกว่ามี {wrong} gate แต่ gates.yaml มี {actual}"


def test_the_badge_worksheet_quotes_the_real_coverage_floor():
    """พื้น coverage ในใบตอบมาจาก `fail_under` เหมือนที่ README ถูกบังคับ"""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    floor = re.search(r"^fail_under\s*=\s*(\d+)", pyproject, re.MULTILINE)
    assert floor, "อ่าน `fail_under` จาก pyproject.toml ไม่ได้ — ชื่อคีย์เปลี่ยนไปแล้ว"

    text = (ROOT / BADGE_WORKSHEET).read_text(encoding="utf-8")
    claims = re.findall(r"fail_under\s*=\s*(\d+)", text)
    assert claims, f"{BADGE_WORKSHEET} ไม่ได้อ้างพื้น coverage ในรูปแบบที่เทสต์อ่านได้"

    wrong = sorted({claimed for claimed in claims if claimed != floor.group(1)})
    assert not wrong, f"{BADGE_WORKSHEET} บอกพื้น coverage {wrong} แต่ pyproject บังคับ {floor.group(1)}"


def test_contributing_points_at_gates_that_exist():
    """คำสั่งที่บอกให้ contributor รันต้องมีไฟล์รองรับจริง"""
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")

    for expected in (".pre-commit-config.yaml", "pyproject.toml", "Pipfile"):
        assert (ROOT / expected).is_file(), f"CONTRIBUTING พึ่ง {expected} ที่หายไปแล้ว"

    scripts = set(re.findall(r"scripts/[\w.-]+\.py", text))
    missing = sorted(name for name in scripts if not (ROOT / name).is_file())
    assert not missing, f"CONTRIBUTING บอกให้รันสคริปต์ที่ไม่มีอยู่: {missing}"


def test_contributing_states_the_licence_terms_for_contributions():
    """ไม่มี CLA แปลว่า inbound = outbound ต้องเขียนไว้ ไม่ใช่ปล่อยให้เดา (ADR 0070)

    **อ่านชื่อ license จากไฟล์จริง ไม่ใช่ฝังคำว่า MIT ไว้ในเทสต์** — ตอนเปลี่ยนเป็น
    AGPL เทสต์เดิมแดงเพราะมันตรึงชื่อไว้ ทั้งที่เอกสารถูกอัปเดตครบแล้ว · ด่านที่
    ตรึงคำตอบไว้เอง คือด่านที่ต้องแก้ทุกครั้งที่คำตอบเปลี่ยนอย่างถูกต้อง
    """
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    for name in ("AGPL", "CC BY-SA"):
        assert name in text, f"CONTRIBUTING ไม่ได้บอกว่าสิ่งที่ส่งมาเผยแพร่ด้วย {name}"
    assert "CLA" in text, "CONTRIBUTING ไม่ได้บอกว่ามี CLA หรือไม่ — คนส่ง PR ต้องรู้ก่อนส่ง"


def test_the_code_of_conduct_names_a_private_reporting_route():
    """CoC ที่บอกให้ 'แจ้งคนดูแล' โดยไม่มีทางส่งจริง ไม่ใช่กระบวนการบังคับใช้"""
    text = (ROOT / "CODE_OF_CONDUCT.md").read_text(encoding="utf-8")
    assert "security/advisories/new" in text, "CoC ไม่ได้บอกช่องทางส่งรายงานแบบส่วนตัว"
    assert "support.github.com" in text, (
        "CoC ไม่ได้บอกทางออกสำหรับกรณีที่เรื่องเป็นเรื่องของคนดูแลเอง — "
        "โปรเจกต์คนเดียวไม่มีใครให้อุทธรณ์ต่อ ต้องเขียนไว้ให้ตรง"
    )


# ------------- คำสั่งติดตั้ง hook ต้องครบทุก stage ที่ประกาศไว้ (audit r15 · ข้อ 3)
#
# hook ที่ประกาศใน `.pre-commit-config.yaml` แต่ไม่ถูกติดตั้ง = hook ที่ไม่มีอยู่จริง
# · คนที่ clone มาใหม่แล้วทำตามคำสั่งในเอกสารเป๊ะ ๆ จะได้เครื่องที่ต่างจากที่เรา
# ออกแบบไว้ โดยไม่มีอะไรบอก — คลาสเดียวกับ "ตรึงไว้แล้วไม่มีใครขยับ"


def _declared_stages() -> set[str]:
    """stage ทุกตัวที่ hook ในไฟล์คอนฟิกประกาศไว้ (ไม่ประกาศ = pre-commit)"""
    config = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    stages = set()
    for repo in config["repos"]:
        for hook in repo["hooks"]:
            stages.update(hook.get("stages", ["pre-commit"]))
    return stages


@pytest.mark.parametrize("doc", ["CLAUDE.md", "CONTRIBUTING.md"])
def test_the_install_command_covers_every_declared_stage(doc):
    text = (ROOT / doc).read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if "pre-commit install" in line]
    assert lines, f"{doc} ไม่มีคำสั่งติดตั้ง hook เลย"
    for line in lines:
        missing = sorted(
            stage for stage in _declared_stages() if f"--hook-type {stage}" not in line
        )
        assert not missing, (
            f"{doc}: คำสั่งติดตั้งไม่ครอบ stage {missing}\n  {line.strip()}\n"
            "hook ที่ประกาศไว้แต่ไม่ถูกติดตั้ง คือ hook ที่ไม่มีอยู่จริงสำหรับคนที่ clone ใหม่"
        )


# --------------- เลข "required N จาก M" ที่ถูกประกาศไว้หลายที่ (audit r21 ข้อค้าง)
#
# วัดเมื่อ 2026-08-21: คู่เลขนี้ถูกเขียนไว้ **11 ที่ใน 6 ไฟล์** ด้วยถ้อยคำเจ็ดแบบ
# และมีเครื่องอ่านคู่กับความจริงอยู่ **ที่เดียว** (`ci:posture` อ่านของ
# `docs/SECURITY-CADENCE.md`) · สิบที่ที่เหลือจึงเน่าได้เงียบ ๆ ทุกครั้งที่เพิ่ม job
#
# **แบ่งหน้าที่กันสองชั้น ไม่ใช่ให้ทุกที่ต่อเน็ต**: ที่นี่บังคับว่าทุกที่พูดเลข
# *ชุดเดียวกัน* (ออฟไลน์ · เร็ว · รันทุก push) ส่วน `ci:posture` บังคับว่าชุดนั้น
# ตรงกับแพลตฟอร์มจริง — ยืนยันที่เดียวจึงยืนยันครบ เพราะที่เหลือถูกบังคับให้ตรงกับมัน

# `required check **27 จาก 30**` — ต้นทางเดียวที่ `ci:posture` อ่าน
REQUIRED_SOURCE = re.compile(r"required check \*\*(\d+) จาก (\d+)\*\*")

# ถ้อยคำอื่นที่พูดเรื่องเดียวกัน — เพิ่มรูปใหม่ต้องมาเพิ่มที่นี่ ไม่งั้นมันรอด
REQUIRED_CLAIMS = (
    # `\*{0,2}` ไม่ใช่ `\*\*?` — อันหลังบังคับให้ต้องมีดอกจันอย่างน้อยหนึ่งตัว
    # จึงพลาดรูปที่เขียนโดยไม่ทำตัวหนา (ISO27001 เขียนแบบนั้น · จับได้ตอน mutation)
    re.compile(r"required checks? \*{0,2}(\d+) จาก (\d+)\*{0,2}"),
    re.compile(r"\((\d+) จาก (\d+)\)"),
    re.compile(r"(\d+) จาก (\d+) check"),
)
REQUIRED_ALONE = re.compile(r"(\d+) required check")
CHECKS_THEN_REQUIRED = re.compile(r"(\d+) check \((\d+) บังคับ\)")

DOCS_CLAIMING_REQUIRED_COUNTS = (
    "docs/SECURITY-CADENCE.md",
    "docs/BEST-PRACTICES.md",
    "docs/ISO27001.md",
)


@pytest.fixture(scope="module")
def declared_pair() -> tuple[int, int]:
    """(required, checks) จากต้นทางเดียวที่ถูกตรวจกับแพลตฟอร์มจริง"""
    text = (ROOT / "docs" / "SECURITY-CADENCE.md").read_text(encoding="utf-8")
    found = REQUIRED_SOURCE.search(text)

    assert found, "อ่านคู่เลข required จาก SECURITY-CADENCE ไม่ได้ — รูปประโยคเปลี่ยนไปแล้ว"
    return int(found.group(1)), int(found.group(2))


def test_the_advertised_check_total_matches_the_workflows(declared_pair, ci_jobs):
    """ตัวหลัง (จำนวน check ทั้งหมด) ตรวจออฟไลน์ได้ — ไม่ต้องรอ `ci:posture`"""
    _required, claimed_checks = declared_pair
    _defined, real_checks = ci_jobs

    assert claimed_checks == real_checks, (
        f"เอกสารบอกว่ามี {claimed_checks} check แต่ workflow สร้างจริง {real_checks}"
    )


@pytest.mark.parametrize("name", DOCS_CLAIMING_REQUIRED_COUNTS)
def test_every_copy_of_the_required_count_says_the_same_thing(name, declared_pair):
    """สำเนาทุกใบต้องพูดเลขชุดเดียวกับต้นทาง — สิบที่ที่ไม่มีใครอ่านคือสิบที่ที่เน่าได้"""
    required, checks = declared_pair
    text = (ROOT / name).read_text(encoding="utf-8")

    pairs = [(int(a), int(b)) for probe in REQUIRED_CLAIMS for a, b in probe.findall(text)]
    pairs += [(int(b), int(a)) for a, b in CHECKS_THEN_REQUIRED.findall(text)]
    alone = [int(value) for value in REQUIRED_ALONE.findall(text)]

    assert pairs or alone, (
        f"{name} ไม่ได้อ้างจำนวน required check แล้ว — "
        "ถ้าตั้งใจถอดออก ให้เอาชื่อไฟล์ออกจาก DOCS_CLAIMING_REQUIRED_COUNTS ด้วย"
    )
    wrong = [pair for pair in pairs if pair != (required, checks)]
    wrong += [f"{value} required" for value in alone if value != required]

    assert not wrong, f"{name} อ้าง {wrong} แต่ต้นทางประกาศไว้ว่า {required} จาก {checks}"


def test_every_place_the_readme_prints_the_doi_agrees_with_citation_cff():
    """DOI บน README ต้องเป็นตัวเดียวกับที่ `CITATION.cff` ประกาศ — ทุกที่ รวมเป้าของ badge

    DOI ปรากฏบน README สามที่ (ร้อยแก้วสองแห่ง + เป้าลิงก์ของ badge) และ**ไม่มี
    ที่ไหนเลยที่ derive มาจาก `CITATION.cff`** — ทุกที่คือเลขที่คนพิมพ์ · รูปของ
    badge มาจาก `zenodo.org` ตามที่ Zenodo กำหนด และมันชี้ด้วย *เลขที่อยู่ของ
    repo* ไม่ใช่ DOI ดังนั้นรูปที่ถูกจึงขึ้นคู่กับเป้าที่ผิดได้อย่างหน้าตาเฉย
    ซึ่งเป็นความล้มเหลวที่คนอ่านมองไม่เห็นเลย — เห็น badge สวย ๆ แล้วกดไปหาของผิด
    """
    declared = yaml.safe_load(CITATION.read_text(encoding="utf-8"))["doi"]
    printed = set(DOI_IN_TEXT.findall((ROOT / "README.md").read_text(encoding="utf-8")))

    assert printed, "README ไม่ได้พิมพ์ DOI แล้ว — ถ้าตั้งใจถอด ให้ลบเทสต์นี้ด้วย"
    assert printed == {declared}, (
        f"README พิมพ์ DOI {sorted(printed)} แต่ CITATION.cff ประกาศ {declared!r}"
    )


def test_every_badge_comes_from_a_host_that_camo_can_actually_fetch():
    """โฮสต์ของรูป badge ต้องอยู่ในรายการที่**วัดแล้ว** ว่า camo ดึงไหว

    GitHub ไม่ได้ฝังรูปจากปลายทางตรง ๆ — มันดึงผ่าน camo แล้ว proxy ให้ ดังนั้น
    "ยิงจากเครื่องเราแล้ว 200" ไม่ได้แปลว่า badge จะขึ้น · badge ของ Zenodo ขึ้น
    บ้างไม่ขึ้นบ้างอยู่หลายรุ่น และตอนไล่จนถึงตัว camo จริง ๆ คำตอบคือ

        HTTP/2 502 · Invalid upstream response (429)

    คือ **Zenodo rate-limit camo** ไม่ใช่เรื่องรูปแบบ URL อย่างที่เดากันสองรอบ
    (รอบแรกโทษ URL รูปแบบเก่า · รอบสองเปลี่ยนไปใช้รูปที่ Zenodo ให้มาแล้วก็ยัง
    กะพริบเหมือนเดิม) · ยิงผ่าน camo สามครั้งต่อใบเทียบกันแล้วชัด: shields.io กับ
    bestpractices.dev ได้ 200/200/200 ทุกใบ ส่วน zenodo.org ได้ 200/502/200

    เทสต์นี้ไม่ยิงเน็ต (ด่านที่ต้องต่อเน็ตคือด่านที่แดงเพราะเน็ต) — มันบังคับแค่ว่า
    **การเพิ่มโฮสต์ใหม่ต้องเป็นคำตัดสินที่มีคนเซ็นชื่อ** พร้อมเหตุผลใน `BADGE_HOSTS`
    ไม่ใช่การก๊อปวาง markdown จากหน้าเว็บของใครสักคน
    """
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    images = re.findall(r"!\[[^\]]*\]\((https?://[^)\s]+)\)", text)
    assert images, "README ไม่มี badge แล้ว — ถ้าตั้งใจถอด ให้ลบเทสต์นี้ด้วย"

    strangers = sorted(
        {url for url in images if not any(url.startswith(host) for host in BADGE_HOSTS)}
    )
    assert not strangers, (
        f"badge จากโฮสต์ที่ยังไม่ได้วัด: {strangers} — "
        "ยิงผ่าน camo ของ GitHub หลายครั้งก่อน แล้วมาลงทะเบียนใน BADGE_HOSTS พร้อมเหตุผล"
    )
