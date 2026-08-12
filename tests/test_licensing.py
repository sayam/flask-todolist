"""license ของโปรเจกต์ และภาระ copyleft ที่ core ห้ามรับไว้ (ADR 0038)

สองเรื่องที่นี่คุม:

1. **ไฟล์ `LICENSE` ต้องมีจริงและเป็น MIT** — ไม่มีไฟล์นี้แปลว่าคนอื่นไม่มีสิทธิ์
   ใช้โค้ดนี้ตามกฎหมาย ไม่ใช่ "ใช้ได้ตามสบาย"
2. **ไลบรารีของ core ต้องไม่มีภาระ copyleft** — วันที่มีคนเติม GPL/LGPL ลง
   `[packages]` เงื่อนไขการแจกจ่ายของทั้งโปรเจกต์เปลี่ยนทันทีโดยไม่มีอะไรส่งเสียง
   ADR 0038 บันทึกไว้ว่าตอนตรวจ (2026-08-12) core สะอาดทั้ง 34 ตัว และตัวเดียว
   ที่มีภาระจริง (`ldap3`, LGPLv3) อยู่ใน category ของ plugin ที่ถอดทิ้งได้

**กับดักที่ต้องกันเป็นพิเศษ:** เทสต์ที่ "อ่าน metadata ไม่ได้เลยจึงไม่พบ copyleft"
จะเขียวสวยงามในสภาพที่แย่ที่สุด — หลักเดียวกับบทเรียนของ Phase 5 เรื่องด่านที่
วัดสัญญาณผิดตัว จึงต้องนับให้ครบว่าตรวจไปกี่ตัว ไม่ใช่แค่ดูว่าเจอ copyleft ไหม
"""

import importlib.metadata as md
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
LICENSE = ROOT / "LICENSE"
LOCK = ROOT / "Pipfile.lock"

# section ของล็อกที่ถือว่าเป็น "ของ core" — ติดตั้งเสมอเมื่อรันแอปจริง
CORE_SECTIONS = ("default", "deploy")

# คำที่บอกว่า license นั้นมีภาระ copyleft · เทียบแบบตัวพิมพ์ใหญ่ทั้งหมด
COPYLEFT_MARKERS = (
    "GPL",  # ครอบ LGPL/AGPL ที่เขียนย่อในชื่อ classifier ด้วย
    "GENERAL PUBLIC LICENSE",
    "MPL",
    "MOZILLA PUBLIC",
    "EUPL",
    "CDDL",
    "COMMON DEVELOPMENT",
    "EPL",
    "ECLIPSE PUBLIC",
    "SSPL",
    "OSL",
    "OPEN SOFTWARE LICENSE",
    "CECILL",
)


def _license_text(distribution_name: str) -> str:
    """ข้อความ license ของแพ็กเกจที่ติดตั้งอยู่ — raise ถ้าอ่านไม่ได้

    ไล่ตามลำดับที่ metadata สมัยใหม่ใช้: `License-Expression` (PEP 639) →
    classifier → ช่อง `License` แบบข้อความอิสระ
    """
    metadata = md.metadata(distribution_name)

    expression = (metadata.get("License-Expression") or "").strip()
    if expression:
        return expression

    classifiers = [
        line for line in (metadata.get_all("Classifier") or []) if line.startswith("License ::")
    ]
    if classifiers:
        return " / ".join(line.split("::")[-1].strip() for line in classifiers)

    return (metadata.get("License") or "").strip()


def _packages_in(section: str) -> list[str]:
    """ชื่อแพ็กเกจใน section ของล็อก โดยตัด extra (`requests[socks]`) ทิ้ง"""
    locked = json.loads(LOCK.read_text(encoding="utf-8"))
    return sorted(name.split("[")[0] for name in locked.get(section, {}))


def test_the_license_file_exists_and_is_mit():
    assert LICENSE.is_file(), "ไม่มีไฟล์ LICENSE — คนอื่นไม่มีสิทธิ์ใช้โค้ดนี้ตามกฎหมาย"

    text = LICENSE.read_text(encoding="utf-8")
    assert "MIT License" in text, "LICENSE ไม่ใช่ MIT แต่ ADR 0038 บอกว่าเป็น — ข้อไหนผิดต้องแก้ให้ตรงกัน"

    # ประโยคที่ทำให้มันเป็น MIT จริง ๆ ไม่ใช่แค่หัวเรื่องที่เขียนว่า MIT
    for clause in (
        "Permission is hereby granted, free of charge",
        "without restriction",
        "shall be included in all",
        'AS IS", WITHOUT WARRANTY',
    ):
        assert clause in text, f"เนื้อ MIT ขาดวรรค: {clause!r}"


def test_the_license_names_a_copyright_holder_and_year():
    """MIT ที่ไม่ระบุว่าใครถือลิขสิทธิ์ คือ MIT ที่ยังไม่ได้ให้สิทธิ์ใคร"""
    holders = [
        line.strip()
        for line in LICENSE.read_text(encoding="utf-8").splitlines()
        if line.startswith("Copyright (c)")
    ]
    assert holders, "LICENSE ไม่มีบรรทัด `Copyright (c) <ปี> <ชื่อ>`"

    for line in holders:
        remainder = line.removeprefix("Copyright (c)").strip()
        year, _, name = remainder.partition(" ")
        assert year.isdigit(), f"ปีลิขสิทธิ์ไม่ใช่ตัวเลข: {line!r}"
        assert len(year) == 4, f"ปีลิขสิทธิ์ไม่ใช่ปีสี่หลัก: {line!r}"
        assert name.strip(), f"ไม่มีชื่อผู้ถือลิขสิทธิ์ต่อท้ายปี: {line!r}"


@pytest.mark.parametrize("section", CORE_SECTIONS)
def test_no_core_dependency_carries_a_copyleft_obligation(section):
    """ไลบรารีของ core ต้อง permissive ทั้งหมด (ADR 0038)

    ถ้าเทสต์นี้แดงเพราะเพิ่ง `pipenv install` อะไรเข้าไป **อย่าเติมข้อยกเว้น** —
    ให้ย้ายมันไปเป็น plugin พร้อม category ของตัวเองตาม ADR 0025 หรือถ้าจำเป็น
    ต้องรับภาระนั้นจริง ให้แก้ ADR 0038 ก่อน แล้วค่อยแก้เทสต์
    """
    packages = _packages_in(section)
    assert packages, f"อ่าน section `{section}` จาก Pipfile.lock ไม่ได้เลย"

    unreadable, copyleft = [], []
    for name in packages:
        try:
            text = _license_text(name)
        except md.PackageNotFoundError:
            unreadable.append(name)
            continue
        if any(marker in text.upper() for marker in COPYLEFT_MARKERS):
            copyleft.append(f"{name}: {text}")

    # ต้องเช็คก่อนว่า "ไม่พบ" ไม่ได้แปลว่า "อ่านไม่ได้เลยจึงไม่พบ"
    assert not unreadable, (
        f"อ่าน license ของ {unreadable} ไม่ได้ — ติดตั้งให้ครบก่อน "
        f"(`pipenv sync --categories='{' '.join(CORE_SECTIONS)}'`) "
        "ไม่งั้นเทสต์นี้จะเขียวโดยไม่ได้ตรวจอะไร"
    )
    assert not copyleft, (
        f"ไลบรารีของ core ที่มีภาระ copyleft: {copyleft}\n"
        "การแจกจ่ายทั้งโปรเจกต์เปลี่ยนเงื่อนไขทันทีที่รับตัวนี้เข้ามา (ADR 0038)"
    )


def test_the_copyleft_libraries_we_do_have_live_in_plugin_categories():
    """ตัวที่มีภาระอยู่แล้วต้องอยู่ใน category ของ plugin ไม่ใช่ใน core

    ข้อนี้อ่านจากล็อกอย่างเดียว จึงเดินได้แม้ในสภาพที่ไม่ได้ติดตั้งไลบรารีของ
    plugin เลย (job `bare`) — และมันคือข้ออ้างของ ADR 0038 ที่ว่า
    "ถอดไดเรกทอรีของ plugin แล้วภาระทางกฎหมายหายไปด้วย"
    """
    locked = json.loads(LOCK.read_text(encoding="utf-8"))
    plugin_sections = [name for name in locked if name.startswith("plugin-")]
    assert plugin_sections, "ไม่เจอ category ของ plugin ในล็อกเลย"

    in_plugins = {name for section in plugin_sections for name in _packages_in(section)}
    in_core = {name for section in CORE_SECTIONS for name in _packages_in(section)}

    both = sorted(in_plugins & in_core)
    assert not both, (
        f"ไลบรารีที่อยู่ทั้งใน core และใน category ของ plugin: {both}\n"
        "ถอด plugin แล้ว supply chain (และภาระ license) ของมันจะไม่หายไปตาม"
    )
