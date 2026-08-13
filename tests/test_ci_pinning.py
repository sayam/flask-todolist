"""เครื่องมือที่ CI ติดตั้งเอง ต้องถูกตรึงด้วย hash — ดู `pins/README.md`

`pip install pipenv` หยิบรุ่นล่าสุด ณ วินาทีที่ job รัน สอง run ที่ห่างกันหนึ่ง
ชั่วโมงจึงใช้เครื่องมือคนละตัวได้โดยไม่มีอะไรใน repo เปลี่ยน — และเครื่องมือ
พวกนี้รันด้วยสิทธิ์ของ workflow เรา อ่าน source อ่าน token ที่ job นั้นมี

**ตรึงด้วยเลขรุ่นอย่างเดียวไม่พอ** เพราะเลขรุ่นบอกได้แค่ว่า "ตัวไหน" ไม่ได้บอก
ว่า "ไบต์ชุดไหน" · `--require-hashes` ยังบังคับอีกข้อที่สำคัญกว่า: **dependency
ทุกตัวในต้นไม้ต้องถูกระบุไว้** ล็อกที่ครอบไม่ครบจึงเป็น error ตอนติดตั้ง
ไม่ใช่ช่องโหว่ที่เงียบอยู่จนถึงวันที่มีคนใช้มัน

เทสต์นี้คู่กับ `tests/test_workflow_pinning.py` (action → SHA) และ
`tests/test_dockerfile_pinning.py` (base image → digest) — สามชั้นเดียวกัน
คนละแหล่งที่มา · และเหมือนกันอีกข้อ: **pin โดยไม่มีใครขยับ = แช่ช่องโหว่ไว้**
ข้อสุดท้ายในไฟล์นี้จึงบังคับว่าทุกไดเรกทอรีใน `pins/` ต้องมี Dependabot ดูแล
"""

import json
import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW_DIR = ROOT / ".github" / "workflows"
DOCKERFILE = ROOT / "Dockerfile"
DEPENDABOT = ROOT / ".github" / "dependabot.yml"
PINS = ROOT / "pins"

# `pip install`, `pip3 install`, `python -m pip install`, `/tmp/x/bin/pip install`
PIP_INSTALL = re.compile(r"(?:^|[\s/])pip3?\s+install\b")
NPM = re.compile(r"(?:^|[\s/])npm\s+(\S+)")
REQUIREMENT_FILE = re.compile(r"(?:-r|--requirement)[\s=]+(\S+)")

# บรรทัดในไฟล์ล็อก: `name==1.2.3 \` แล้วตามด้วย `--hash=...` ที่ย่อหน้าเข้าไป
PIN_LINE = re.compile(r"^(?P<name>[A-Za-z0-9._-]+)\s*(?P<spec>[=<>!~].*)$")


def _scannable(path: pathlib.Path) -> list[str]:
    """บรรทัดคำสั่งของไฟล์ — ต่อบรรทัดที่ลงท้ายด้วย `\\` และตัดคอมเมนต์ทิ้ง

    ตัดคอมเมนต์ทิ้งเพราะไฟล์พวกนี้ **อธิบายตัวเองด้วยการยกคำสั่งที่ห้ามใช้มาเขียน**
    (คอมเมนต์ในหัว `ci.yml` มีคำว่า `pip install pipenv` อยู่จริง ๆ) ด่านที่นับ
    คอมเมนต์เป็นคำสั่งคือด่านที่แดงเพราะมีคนเขียนอธิบายให้ดีขึ้น
    """
    joined: list[str] = []
    buffer = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.lstrip().startswith("#"):
            continue
        buffer += raw.rstrip()
        if buffer.endswith("\\"):
            buffer = buffer[:-1]
            continue
        joined.append(buffer)
        buffer = ""
    if buffer:
        joined.append(buffer)
    return joined


def _command_files() -> list[pathlib.Path]:
    found = [*sorted(WORKFLOW_DIR.glob("*.y*ml")), DOCKERFILE]
    assert all(p.is_file() for p in found), f"หาไฟล์ไม่ครบ: {found}"
    return found


@pytest.fixture(scope="module")
def pip_installs() -> list[tuple[pathlib.Path, str]]:
    found = [
        (path, line)
        for path in _command_files()
        for line in _scannable(path)
        if PIP_INSTALL.search(line)
    ]
    # ตัวดึงที่หาไม่เจออะไรเลยจะ "ผ่าน" ทุกข้อข้างล่างโดยไม่ได้ตรวจอะไร
    assert found, "ไม่เจอคำสั่ง `pip install` สักบรรทัด — ตัวดึงพังหรือเปล่า"
    return found


def test_every_pip_install_requires_hashes(pip_installs):
    loose = [
        f"{p.name}: {line.strip()}" for p, line in pip_installs if "--require-hashes" not in line
    ]
    assert not loose, (
        "`pip install` ที่ยังไม่ได้ตรึงด้วย hash:\n  " + "\n  ".join(loose) + "\n"
        "รูปแบบที่ต้องการคือ `pip install --require-hashes -r pins/<ชื่อ>/requirements.txt`"
    )


def test_every_pip_install_points_at_a_lock_file_that_exists(pip_installs):
    """path ที่พิมพ์ผิดจะพังตอน CI รัน ไม่ใช่ตอนเขียน — และพังทุก job พร้อมกัน"""
    missing = []
    for path, line in pip_installs:
        targets = REQUIREMENT_FILE.findall(line)
        if not targets:
            missing.append(f"{path.name}: ไม่มี `-r <ไฟล์>` ใน {line.strip()}")
            continue
        missing += [f"{path.name}: ชี้ไปที่ {t} ซึ่งไม่มีอยู่" for t in targets if not (ROOT / t).is_file()]
    assert not missing, "\n  ".join(["`pip install` ที่ชี้ไปผิดที่:", *missing])


def test_no_workflow_installs_npm_packages_without_the_lock_file():
    """`npm install <pkg>@<รุ่น>` ตรึงได้แค่ตัวมันเอง ที่เหลือในต้นไม้ยังลอยอยู่

    `npm ci` ติดตั้งจาก `package-lock.json` ตรง ๆ ซึ่งมี integrity hash ครบทั้ง
    ต้นไม้ และ **ล้มทันทีถ้า lock ไม่ตรงกับ package.json** — ต่างจาก `npm install`
    ที่จะแก้ lock ให้เงียบ ๆ แล้วเดินต่อ
    """
    subcommands = [
        (path.name, sub)
        for path in _command_files()
        for line in _scannable(path)
        for sub in NPM.findall(line)
    ]
    assert subcommands, "ไม่เจอคำสั่ง `npm` สักบรรทัด — ตัวดึงพังหรือเปล่า"

    bad = [f"{name}: npm {sub}" for name, sub in subcommands if sub in ("install", "i", "add")]
    assert not bad, "npm ที่ไม่ได้ติดตั้งจาก lock:\n  " + "\n  ".join(bad) + "\nใช้ `npm ci`"


@pytest.mark.parametrize(
    "lock", sorted(PINS.glob("*/requirements.txt")), ids=lambda p: p.parent.name
)
def test_every_pinned_requirement_carries_a_hash(lock):
    """ทุกบรรทัดที่เป็น requirement ต้องมีทั้ง `==` และ `--hash=`

    ไฟล์ที่มีสักตัวไม่ครบ = `pip install --require-hashes` ปฏิเสธทั้งไฟล์
    ซึ่งถูกแล้ว แต่จะรู้ตอน CI แดงกลาง run — ที่นี่รู้ตั้งแต่ก่อน commit
    """
    blocks: dict[str, str] = {}
    current = None
    for line in lock.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or not line.strip():
            continue
        matched = PIN_LINE.match(line)
        if matched:
            current = matched.group("name")
            blocks[current] = line
        elif current:
            blocks[current] += line
    assert blocks, f"{lock}: อ่าน requirement ไม่ได้สักตัว"

    unpinned = sorted(name for name, text in blocks.items() if "==" not in text.split("--hash")[0])
    assert not unpinned, f"{lock}: ไม่ได้ตรึงรุ่น: {unpinned}"

    unhashed = sorted(name for name, text in blocks.items() if "--hash=sha256:" not in text)
    assert not unhashed, f"{lock}: ไม่มี hash: {unhashed}"


@pytest.mark.parametrize(
    "lock", sorted(PINS.glob("*/requirements.txt")), ids=lambda p: p.parent.name
)
def test_every_lock_file_keeps_the_input_it_was_compiled_from(lock):
    """`requirements.in` ต้องถูก commit ไปด้วย ไม่งั้น Dependabot ขยับให้ไม่ได้

    มันไม่ได้แก้ hash ทีละบรรทัด แต่ compile ไฟล์ใหม่จาก `.in` — ไฟล์ล็อกที่
    ไม่มีต้นฉบับจึงเป็นไฟล์ที่ไม่มีใครอัปเดตได้อีก (และคนก็ regenerate ไม่ได้)
    """
    assert (lock.parent / "requirements.in").is_file(), f"{lock.parent}: ไม่มี requirements.in"


def test_the_npm_lock_pins_every_package_by_integrity_hash():
    lock = json.loads((PINS / "pa11y" / "package-lock.json").read_text(encoding="utf-8"))
    assert lock["lockfileVersion"] >= 2, "lockfileVersion 1 ไม่มี integrity ครบทั้งต้นไม้"

    # แพ็กเกจรากคือตัว package.json เอง ไม่ได้ถูกดาวน์โหลดมาจึงไม่มี integrity
    downloaded = {name: meta for name, meta in lock["packages"].items() if name}
    assert len(downloaded) > 100, f"lock มีแค่ {len(downloaded)} package — ครอบไม่ครบแน่"

    missing = sorted(name for name, meta in downloaded.items() if not meta.get("integrity"))
    assert not missing, f"package ที่ไม่มี integrity hash: {missing}"


def test_dependabot_keeps_every_pin_fresh():
    """**ข้อนี้คือเหตุผลที่การตรึงยอมรับได้** — เพิ่ม `pins/<ชื่อ>` แล้วลืมต่อ
    Dependabot ให้ ต้องแดง ไม่ใช่กลายเป็นเครื่องมือที่ไม่มีใครอัปเดตให้อีก
    (หลักเดียวกับ `tests/test_dockerfile_pinning.py` เรื่อง digest ของ base image)
    """
    config = yaml.safe_load(DEPENDABOT.read_text(encoding="utf-8"))
    watched = {
        directory
        for entry in config["updates"]
        for directory in ([entry["directory"]] if "directory" in entry else entry["directories"])
    }

    pinned = {f"/pins/{d.name}" for d in PINS.iterdir() if d.is_dir()}
    assert pinned, "ไม่มีไดเรกทอรีใน pins/ เลย"

    unwatched = sorted(pinned - watched)
    assert not unwatched, (
        f"ไดเรกทอรีใน pins/ ที่ไม่มีใครขยับให้: {unwatched}\n"
        "pin โดยไม่มีใครขยับคือการแช่ช่องโหว่ไว้ตลอดกาล — แย่กว่าไม่ pin เลย"
    )
