"""บันทึกเวลาของสายวิทยานิพนธ์ต้องมีแถวทุกวันที่มีงานจริง — ADR 0075

ข้ออ้างหลักของวิทยานิพนธ์คือ "AI-assisted ทำให้ต้นทุนของ compliance ย้ายที่/ลดลง"
· วันที่ 2026-08-24 พบว่า repo นี้ **ไม่มีตัวเลขเวลาแม้แต่ตัวเดียว** — 434 commit
ใน 22 วันบอกได้แค่ขอบบนของปฏิทิน ไม่ใช่ชั่วโมงที่ใช้ · และเวลาเป็นสิ่งเดียวที่
เก็บย้อนหลังไม่ได้ จึงต้องเริ่มเก็บก่อนทำอย่างอื่น

ไฟล์ `docs/comparison/effort-log.csv` เป็นทะเบียนที่**คนเขียน** (ประมาณการท้าย
session) — เทสต์นี้ไม่ตัดสินว่าตัวเลขถูก แต่บังคับสองทิศว่า:

- **ทุกวันที่มี commit บน main ตั้งแต่วันเริ่มเก็บ ต้องมีแถวของวันนั้น** — งานที่
  เกิดโดยไม่มีบันทึกเวลา คือข้อมูลที่หายไปถาวรและทำให้ชุดข้อมูลทั้งชุดเอียง
  (วันที่ลืมจดคือวันที่ทำเยอะเสมอ)
- แถวทุกแถวมีรูปที่เครื่องอ่านได้ (วันที่ไม่อยู่ในอนาคต · นาที > 0 · track/kind
  จากชุดที่ประกาศ) เพราะไฟล์นี้จะถูกวิเคราะห์ ไม่ใช่แค่เก็บ

วันที่ไม่มี commit แต่มีแถว (วันคิด วันเขียนเล่ม) ถูกต้องเสมอ — ทิศนั้นไม่บังคับ
"""

from __future__ import annotations

import csv
import datetime as dt
import pathlib

import pytest

from scripts.removals_census import _git

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOG = ROOT / "docs" / "comparison" / "effort-log.csv"

# วันแรกที่เริ่มเก็บ — ก่อนหน้านี้ไม่มีข้อมูล และไม่แต่งย้อนหลัง (ADR 0075)
START = dt.date(2026, 8, 24)
COLUMNS = ["date", "minutes", "track", "kind", "note"]
TRACKS = frozenset({"thesis", "product"})
KINDS = frozenset({"governance", "feature", "experiment", "writing", "review"})


def rows() -> list[dict[str, str]]:
    with LOG.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == COLUMNS, f"หัวคอลัมน์ต้องเป็น {COLUMNS} ได้ {reader.fieldnames}"
        return list(reader)


def commit_dates_since(start: dt.date) -> set[dt.date]:
    """วันที่ (author date, local) ของ commit ทั้งหมดในสายปัจจุบันตั้งแต่ `start`"""
    out = _git("log", f"--since={start.isoformat()}", "--format=%ad", "--date=short").split()
    return {dt.date.fromisoformat(day) for day in out}


@pytest.fixture(scope="module")
def log_rows():
    return rows()


def latest_possible_today() -> dt.date:
    """วันที่ "วันนี้" ในโซนเวลาที่ล้ำสุดของโลก (UTC+14) — ไม่ใช่ของเครื่องที่รันเทสต์

    แถวถูกเขียนตามวันของคนเขียน (ไทย UTC+7) แต่ CI รันที่ UTC ซึ่งยังเป็นเมื่อวาน
    · เทสต์ที่ใช้ `date.today()` ของเครื่องจึงเขียวบนเครื่อง dev แดงบน CI —
    คลาสเดียวกับ `test_pseudo_zones_are_never_offered` ใน CLAUDE.md
    """
    return (dt.datetime.now(dt.UTC) + dt.timedelta(hours=14)).date()


def test_every_row_is_machine_readable(log_rows):
    today = latest_possible_today()
    problems = []
    for index, row in enumerate(log_rows, start=2):
        day = dt.date.fromisoformat(row["date"])
        if day < START or day > today:
            problems.append(f"บรรทัด {index}: วันที่ {day} อยู่นอกช่วง {START}..{today}")
        if not row["minutes"].isdigit() or int(row["minutes"]) <= 0:
            problems.append(f"บรรทัด {index}: minutes ต้องเป็นจำนวนเต็มบวก ได้ {row['minutes']!r}")
        if row["track"] not in TRACKS:
            problems.append(f"บรรทัด {index}: track {row['track']!r} ไม่อยู่ใน {sorted(TRACKS)}")
        if row["kind"] not in KINDS:
            problems.append(f"บรรทัด {index}: kind {row['kind']!r} ไม่อยู่ใน {sorted(KINDS)}")
        if not row["note"].strip():
            problems.append(f"บรรทัด {index}: note ว่าง — ตัวเลขที่ไม่มีบริบทวิเคราะห์ไม่ได้")
    assert not problems, "\n".join(problems)


def test_rows_are_appended_in_date_order(log_rows):
    days = [row["date"] for row in log_rows]
    assert days == sorted(days), "แถวต้องเรียงตามวันที่ — ไฟล์นี้ต่อท้ายอย่างเดียว ไม่แทรกกลาง"


def test_every_day_with_a_commit_has_a_row(log_rows):
    logged = {dt.date.fromisoformat(row["date"]) for row in log_rows}
    worked = {day for day in commit_dates_since(START) if day >= START}
    missing = sorted(worked - logged)
    assert not missing, (
        f"มี commit ในวันที่ {[d.isoformat() for d in missing]} แต่ไม่มีแถวใน {LOG.relative_to(ROOT)} — "
        "เติมแถวของวันนั้น (ประมาณการได้ แต่ห้ามเว้น) ก่อน merge"
    )
