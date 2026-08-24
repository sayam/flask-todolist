"""ปลายทางของชุดเทสต์ต้องเป็นฐานข้อมูลของทิ้ง — ISO/IEC 27001 A.8.31 · A.8.33

**รูที่ปิดด้วยไฟล์นี้**: ทุก fixture ที่สร้างแอปเดินผ่าน `_app_with_tables()` ซึ่ง
เรียก `db.create_all()` แล้ว `db.drop_all()` · ปลายทางมาจาก `TEST_DATABASE_URL`
ซึ่ง `CLAUDE.md` **บอกให้คนตั้งเอง**เวลาอยากยิงยี่ห้ออื่น — พิมพ์ host หรือชื่อฐาน
ผิดครั้งเดียวคือ drop ตารางทั้งฐาน และเป็นความเสียหายที่ย้อนไม่ได้

`docs/ISO27001.md` ประกาศมานานว่า A.8.31 กับ A.8.33 ผ่านเพราะ "fixture ปฏิเสธ
ฐานข้อมูลจริง" · ตัวที่ปฏิเสธจริงคือ `scripts/a11y_fixture.py` ซึ่ง (1) เป็นคนละ
เส้นทางกับชุดเทสต์ (2) เกณฑ์ของมันจับได้เฉพาะรูป sqlite ของ dev และ (3) ประกาศ
บทบาทตัวเองว่า `helper` ซึ่งนิยามใน `tests/test_script_roles.py` คือ **"ไม่ตัดสิน
และไม่ถูกอ้างเป็นหลักฐาน"** — เส้นทางที่อันตรายที่สุดจึงไม่เคยมีอะไรกันเลย

**เกณฑ์เป็น allowlist ไม่ใช่ blocklist** — blocklist ต้องเดาให้ครบว่าฐานจริงหน้าตา
อย่างไร ซึ่งเดาไม่มีวันครบ · allowlist ผิดพลาดไปทางที่ปลอดภัย: ฐานที่ไม่ได้ประกาศ
ตัวว่าเป็นของทิ้ง = ไม่ให้แตะ

ทิศ "ผ่านเมื่อควรผ่าน" **ผูกกับค่าที่ CI ใช้จริง อ่านจาก `ci.yml`** ไม่ใช่ค่าที่
พิมพ์ซ้ำไว้ที่นี่ — ด่านที่เทียบกับสำเนาของตัวเองคือด่านที่ยังเขียวในวันที่ของจริง
เปลี่ยนไปแล้ว (บทเรียนของ audit รอบ 25)
"""

from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys

import pytest
import yaml
from conftest import THROWAWAY_MARK, refuse_a_database_that_is_not_throwaway, throwaway_problem

ROOT = pathlib.Path(__file__).resolve().parent.parent
CI = ROOT / ".github" / "workflows" / "ci.yml"

# เพดานเวลาของคำสั่งที่เรายิงออกไป (ADR 0067) — pytest ที่แค่ collect ใช้ไม่กี่วินาที
COLLECT_TIMEOUT_SECONDS = 120

# `${{ matrix.db.scheme }}` ในไฟล์ workflow — แทนด้วยยี่ห้อจริงตัวหนึ่งเพื่อให้
# ได้ URL ที่ย่อยได้ · **ส่วนที่เทสต์นี้สนใจคือชื่อฐาน ไม่ใช่ scheme**
EXPRESSION = re.compile(r"\$\{\{[^}]+\}\}")


@pytest.mark.parametrize(
    "uri",
    [
        "sqlite:///:memory:",
        "sqlite://",
        "mysql+pymysql://root:x@127.0.0.1:3306/todolist_test",
        "postgresql://u:p@db.internal:5432/TODOLIST_TEST",  # ชื่อฐานไม่สนตัวพิมพ์
        "sqlite:////tmp/todolist_test.db",
    ],
)
def test_a_database_that_says_it_is_throwaway_is_allowed(uri):
    """ของทิ้งที่ประกาศตัวชัดต้องผ่าน — ด่านที่บล็อกงานปกติคือด่านที่ถูกถอด"""
    assert throwaway_problem(uri) is None, f"{uri} ควรผ่านแต่ถูกปฏิเสธ"


@pytest.mark.parametrize(
    "uri",
    [
        "mysql+pymysql://u:p@prod-host/todolist",
        "postgresql://u:p@10.0.0.5:5432/todolist_production",
        "sqlite:///instance/todolist.db",
        "sqlite:////var/lib/todolist/todolist.db",
        # **host ชื่อ test ไม่ได้แปลว่าฐานในนั้นทิ้งได้** — เกณฑ์ที่อ่านทั้ง URL
        # จะปล่อยตัวนี้ผ่าน ซึ่งเป็นรูปที่เจอบ่อยที่สุดของ staging ที่มีข้อมูลจริง
        "mysql+pymysql://u:p@test-db.internal:3306/todolist",
    ],
)
def test_a_database_that_does_not_say_so_is_refused(uri):
    """ฐานที่ไม่ประกาศตัวว่าเป็นของทิ้ง ต้องถูกปฏิเสธ ไม่ใช่ถูกเดาว่าปลอดภัย"""
    problem = throwaway_problem(uri)
    assert problem, f"{uri} ควรถูกปฏิเสธแต่ผ่าน"
    assert THROWAWAY_MARK in problem, "ข้อความต้องบอกวิธีเปิดทางที่ถูก ไม่ใช่แค่ปฏิเสธ"


def test_the_value_ci_really_uses_still_passes_this_gate():
    """ทิศ "ผ่านเมื่อควรผ่าน" ผูกกับ `ci.yml` จริง

    ถ้าใครเปลี่ยนชื่อฐานใน matrix เป็นอย่างอื่น job `dialects` จะถูกด่านนี้บล็อก
    ทุกใบ — และเราอยากรู้ตอนแก้ ไม่ใช่ตอนที่ CI แดงด้วยข้อความที่ไม่เกี่ยวกับ PR นั้น
    """
    workflow = yaml.safe_load(CI.read_text(encoding="utf-8"))
    configured = [
        str(step["env"]["TEST_DATABASE_URL"])
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        if isinstance(step, dict) and "TEST_DATABASE_URL" in (step.get("env") or {})
    ]
    assert configured, "ไม่มี step ไหนใน ci.yml ตั้ง TEST_DATABASE_URL แล้ว — เทสต์นี้ตรวจของที่หายไป"
    for raw in configured:
        uri = EXPRESSION.sub("mysql+pymysql", raw.strip())
        assert throwaway_problem(uri) is None, (
            f"ค่าที่ CI ใช้ถูกด่านนี้ปฏิเสธ: {uri} — แก้ที่ ci.yml หรือที่เกณฑ์ อย่างใดอย่างหนึ่ง แต่ปล่อยให้ขัดกันไม่ได้"
        )


def test_the_guard_reads_the_environment_not_just_a_string(monkeypatch):
    """ด่านต้องอ่านตัวแปรจริง — ฟังก์ชันตัดสินที่ไม่มีใครป้อนของจริงให้ คือฟังก์ชันลอย"""
    monkeypatch.setenv("TEST_DATABASE_URL", "mysql+pymysql://u:p@prod-host/todolist")
    with pytest.raises(pytest.UsageError, match="ปฏิเสธ"):
        refuse_a_database_that_is_not_throwaway()

    monkeypatch.setenv("TEST_DATABASE_URL", "mysql+pymysql://u:p@127.0.0.1/todolist_test")
    refuse_a_database_that_is_not_throwaway()  # ต้องไม่ raise

    monkeypatch.delenv("TEST_DATABASE_URL")
    refuse_a_database_that_is_not_throwaway()  # ไม่ตั้ง = ใช้ค่าเริ่มต้นในหน่วยความจำ


def test_the_run_really_stops_before_any_fixture_can_touch_a_schema():
    """**ทิศที่สำคัญที่สุด**: ด่านถูกเรียกตอน import `conftest.py` จริงหรือเปล่า

    สามข้อข้างบนพิสูจน์ว่า*ตรรกะ*ถูก แต่ไม่ได้พิสูจน์ว่ามันถูก*ต่อสาย* — ฟังก์ชัน
    ที่ถูกต้องแต่ไม่มีใครเรียก คือฟังก์ชันที่ปล่อยให้ `drop_all()` เดินต่อไปตามปกติ
    (audit รอบ 10: เทสต์ต้องเดินไปถึงบรรทัดที่กฎถูกอ่าน)

    ใช้ `--collect-only` เพราะแค่ import `conftest.py` ก็พอจะพิสูจน์แล้ว และมันไม่
    แตะฐานข้อมูลไหนเลยแม้ด่านจะพัง — เทสต์ที่พิสูจน์เรื่องนี้ด้วยการรันจริงคือเทสต์
    ที่ทำลายข้อมูลตอนที่ตัวมันเองล้มเหลว
    """
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "."],
        cwd=ROOT / "tests",
        capture_output=True,
        text=True,
        check=False,
        timeout=COLLECT_TIMEOUT_SECONDS,
        env={**_clean_env(), "TEST_DATABASE_URL": "mysql+pymysql://u:p@prod-host/todolist"},
    )
    assert done.returncode != 0, (
        "ชุดเทสต์เริ่มเดินได้ทั้งที่ TEST_DATABASE_URL ชี้ฐานที่ไม่ใช่ของทิ้ง — ด่านมีอยู่แต่ไม่มีใครเรียก"
    )
    assert "ปฏิเสธ" in done.stdout + done.stderr, (
        f"หยุดจริงแต่ด้วยเหตุผลอื่น ซึ่งแปลว่าด่านนี้ไม่ใช่คนหยุด:\n{done.stdout[-2000:]}"
    )


def _clean_env() -> dict[str, str]:
    """env ของลูก — ตัดค่าที่ทำให้ผลของลูกไม่ใช่ผลของด่านนี้"""
    return {k: v for k, v in os.environ.items() if k not in {"COVERAGE_FILE", "COV_CORE_SOURCE"}}
