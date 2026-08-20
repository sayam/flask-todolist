"""CHANGELOG ต้องพูดตรงกับเวอร์ชันที่โค้ดคิดว่าตัวเองเป็น

**เวอร์ชันเดียวกันอยู่สามที่คนละชนิด**: `app.__version__` (โค้ด) · หัวข้อบนสุด
ของ `CHANGELOG.md` (คำประกาศ) · git tag (สิ่งที่คนดาวน์โหลด) — ที่นี่คุมสองอันแรก
ให้ตรงกันเสมอ ส่วน tag ผูกตอน release เพราะยังไม่มีตอนที่ commit ถูกสร้าง

ที่ **ไม่** คุมโดยตั้งใจ: `API_VERSION` ใน `config.py` ซึ่งเป็นเวอร์ชันของ
*สัญญา API* คนละตัวกับเวอร์ชันของแอป (ADR 0018 — สัญญา v1 แก้ไม่ได้ ส่วนแอป
ออกรุ่นใหม่ได้เรื่อย ๆ) ตอนนี้เลขบังเอิญตรงกันเพราะเริ่มพร้อมกัน **การบังคับให้
สองตัวนี้ตรงกันคือการผูกของที่ตั้งใจให้แยกจากกัน**
"""

import pathlib
import re

import pytest

import app as app_package

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"
ADR_DIR = ROOT / "docs" / "adr"

# `## [1.0.0] — 2026-08-12` (em dash หรือ hyphen ก็ได้) และ `## [Unreleased]`
RELEASE = re.compile(r"^##\s*\[(\d+\.\d+\.\d+)\]\s*[—-]\s*(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)
UNRELEASED = re.compile(r"^##\s*\[Unreleased\]\s*$", re.MULTILINE | re.IGNORECASE)

# `the 38 records in` — จำนวน ADR ที่ CHANGELOG โฆษณาไว้
ADR_CLAIM = re.compile(r"the (\d+) records in")


@pytest.fixture(scope="module")
def text():
    assert CHANGELOG.is_file(), "ไม่มี CHANGELOG.md ที่รากของ repo"
    return CHANGELOG.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def releases(text):
    found = RELEASE.findall(text)
    assert found, "อ่านหัวข้อรุ่นใน CHANGELOG ไม่ได้เลย — รูปแบบ `## [x.y.z] — YYYY-MM-DD` เปลี่ยนไปแล้ว"
    return found


def test_the_newest_entry_matches_the_version_in_the_code(releases):
    """เลขในโค้ดกับเลขที่ประกาศต้องเป็นเลขเดียวกัน ไม่งั้นไม่มีใครรู้ว่ารันรุ่นไหนอยู่"""
    newest = releases[0][0]
    assert newest == app_package.__version__, (
        f"CHANGELOG บอกว่ารุ่นล่าสุดคือ {newest} แต่ `app.__version__` เป็น "
        f"{app_package.__version__} — ออกรุ่นใหม่ต้องขยับทั้งสองที่"
    )


def test_releases_are_listed_newest_first(releases):
    """เรียงผิดแปลว่าคนอ่านสรุปรุ่นล่าสุดผิดตั้งแต่บรรทัดแรก"""
    versions = [tuple(int(part) for part in version.split(".")) for version, _ in releases]
    assert versions == sorted(versions, reverse=True), (
        f"รุ่นใน CHANGELOG ไม่ได้เรียงจากใหม่ไปเก่า: {[v for v, _ in releases]}"
    )

    dates = [date for _, date in releases]
    assert dates == sorted(dates, reverse=True), f"วันที่ของรุ่นไม่ได้เรียงจากใหม่ไปเก่า: {dates}"


def test_every_release_number_is_unique(releases):
    versions = [version for version, _ in releases]
    duplicated = sorted({version for version in versions if versions.count(version) > 1})
    assert not duplicated, f"เลขรุ่นซ้ำใน CHANGELOG: {duplicated}"


def test_there_is_a_place_to_write_the_next_change(text):
    """ไม่มีหัวข้อ Unreleased แปลว่าการเปลี่ยนแปลงถัดไปไม่มีที่ลง แล้วมันจะไม่ถูกจด"""
    assert UNRELEASED.search(text), "CHANGELOG ไม่มีหัวข้อ `## [Unreleased]`"


def test_the_number_of_adrs_we_advertise_is_the_real_one(text):
    """เลขที่โฆษณาต้องนับจากดิสก์ ไม่ใช่จากความจำตอนเขียน"""
    claims = ADR_CLAIM.findall(text)
    assert claims, "CHANGELOG ไม่ได้บอกจำนวน ADR ในรูปแบบที่เทสต์อ่านได้"

    actual = len([path for path in ADR_DIR.glob("*.md") if re.match(r"^\d{4}-", path.name)])
    wrong = [claimed for claimed in claims if int(claimed) != actual]
    assert not wrong, f"CHANGELOG บอกว่ามี ADR {wrong} ใบ แต่บนดิสก์มี {actual} ใบ"


def test_the_link_targets_at_the_bottom_cover_every_release(text, releases):
    """ลิงก์ `[1.0.0]: https://...` ที่ขาดไป ทำให้หัวข้อกลายเป็นวงเล็บเปล่า ๆ ตอน render"""
    defined = set(re.findall(r"^\[([^\]]+)\]:\s*https?://", text, re.MULTILINE))
    needed = {version for version, _ in releases} | {"Unreleased"}

    missing = sorted(needed - defined)
    assert not missing, f"หัวข้อที่ไม่มีปลายทางของลิงก์: {missing}"


# ------------- ที่อื่นที่บอกเวอร์ชันกับโลกภายนอก ต้องพูดตรงกัน (2026-08-20)
#
# หัวไฟล์นี้เขียนไว้ว่า "เวอร์ชันเดียวกันอยู่สามที่คนละชนิด" — ตอนนั้นจริง
# วันนี้มีอีกสองที่ที่**คนนอกอ่าน**และเก่าได้เงียบ ๆ: badge บน `README.md`
# (สิ่งแรกที่คนเห็น) และ `CITATION.cff` (สิ่งที่ Zenodo กับโปรแกรมอ้างอิงอ่าน)
#
# ทั้งคู่ไม่มีอะไรบังคับมาก่อน — และ `CITATION.cff` ยังไม่มีช่อง `version` เลย
# จนถึงวันนี้ ทั้งที่มันคือ *บัตรประจำตัวของงานชิ้นนี้*

README = ROOT / "README.md"
CITATION = ROOT / "CITATION.cff"
BADGE = re.compile(r"badge/version-v(\d+\.\d+\.\d+)-")
CFF_VERSION = re.compile(r"^version:\s*(\d+\.\d+\.\d+)\s*$", re.MULTILINE)


def test_the_badge_people_see_first_says_the_real_version():
    """badge บน README คือสิ่งแรกที่คนเห็น — เก่าแล้วคือคำประกาศที่ผิด"""
    found = BADGE.search(README.read_text(encoding="utf-8"))

    assert found, "README ไม่มี badge เวอร์ชันแล้ว — ถ้าตั้งใจถอด ให้ลบเทสต์นี้ด้วย"
    assert found.group(1) == app_package.__version__, (
        f"badge บอก v{found.group(1)} แต่โค้ดเป็น {app_package.__version__}"
    )


def test_the_citation_record_says_the_real_version():
    """`CITATION.cff` คือบัตรประจำตัวที่ Zenodo และโปรแกรมอ้างอิงอ่าน"""
    found = CFF_VERSION.search(CITATION.read_text(encoding="utf-8"))

    assert found, "CITATION.cff ไม่มีช่อง `version:` — Zenodo จะไม่รู้ว่าอ้างรุ่นไหน"
    assert found.group(1) == app_package.__version__, (
        f"CITATION.cff บอก {found.group(1)} แต่โค้ดเป็น {app_package.__version__}"
    )
