"""base image ของ Dockerfile ต้องถูก pin ด้วย digest

`python:3.13-slim` เป็น tag ที่ถูกย้ายทับได้ตลอด — build สองครั้งที่ห่างกัน
หนึ่งชั่วโมงจึงได้ base คนละตัวโดยไม่มีอะไรในไฟล์เปลี่ยน แปลว่า image ที่ผ่าน
การทดสอบกับ image ที่ deploy ไม่จำเป็นต้องเป็นตัวเดียวกัน

**ราคาที่การ pin เรียกเก็บ**: security patch ของ base จะไม่มาเองอีก ซึ่งแย่กว่า
เดิมถ้าไม่มีใครขยับ · จ่ายไปแล้วด้วย `package-ecosystem: docker` ใน
`.github/dependabot.yml` ซึ่งเปิด PR ขยับ digest ให้ — เทสต์ที่นี่บังคับว่า
**สองอย่างนี้ต้องมาคู่กันเสมอ** เพราะ pin โดยไม่มีใครขยับคือการแช่ช่องโหว่ไว้
"""

import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCKERFILE = ROOT / "Dockerfile"
DEPENDABOT = ROOT / ".github" / "dependabot.yml"

# `FROM python:3.13-slim@sha256:<64 hex> AS builder`
FROM_LINE = re.compile(r"^FROM\s+(\S+)", re.MULTILINE)
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")


@pytest.fixture(scope="module")
def images() -> list[str]:
    """ทุก image ที่ `FROM` อ้างถึง — ไม่รวมการอ้างชั้นก่อนหน้าใน multi-stage"""
    assert DOCKERFILE.is_file(), "ไม่มี Dockerfile"
    text = DOCKERFILE.read_text(encoding="utf-8")

    stages = set(re.findall(r"^FROM\s+\S+\s+AS\s+(\S+)", text, re.MULTILINE))
    found = [ref for ref in FROM_LINE.findall(text) if ref not in stages]
    assert found, "อ่านบรรทัด FROM จาก Dockerfile ไม่ได้เลย"
    return found


def test_every_base_image_is_pinned_by_digest(images):
    unpinned = [ref for ref in images if not DIGEST.search(ref)]
    assert not unpinned, (
        f"base image ที่ยังไม่ได้ pin ด้วย digest: {unpinned}\n"
        "tag ถูกย้ายทับได้ — image ที่ทดสอบผ่านกับที่ deploy จะไม่ใช่ตัวเดียวกัน"
    )


def test_every_stage_uses_the_same_digest(images):
    """multi-stage ที่ base คนละ digest = ชั้น build กับชั้นรันจริงคนละระบบ

    ขยับ digest แล้วลืมขยับอีกชั้นเป็นความผิดพลาดที่ build ผ่านได้สบาย ๆ
    (หลักเดียวกับ `tests/test_workflow_pinning.py` ที่บังคับ SHA เดียวกันทุกที่)
    """
    digests = {ref.split("@", 1)[1] for ref in images if "@" in ref}
    assert len(digests) <= 1, f"ชั้นต่าง ๆ ใช้ base คนละ digest: {sorted(digests)}"


def test_the_digest_still_says_which_tag_it_is(images):
    """`FROM <ชื่อ>:<tag>@<digest>` — ตัด tag ออกแล้วไม่มีใครรู้ว่ารันอะไรอยู่

    และ Dependabot ใช้ tag เป็นตัวบอกว่าควรขยับไปไหนต่อ
    """
    without_tag = [ref for ref in images if ":" not in ref.split("@", 1)[0]]
    assert not without_tag, f"digest ที่ไม่มี tag กำกับ: {without_tag}"


def test_dependabot_is_the_one_keeping_the_digest_fresh():
    """pin โดยไม่มีใครขยับ = แช่ช่องโหว่ของ base image ไว้ตลอดกาล

    **ข้อนี้คือเหตุผลที่การ pin ยอมรับได้** — ถอด entry นี้ออกเมื่อไหร่ ต้องแดง
    ไม่ใช่เงียบ ๆ กลายเป็น image ที่ไม่มีใครอัปเดตให้
    """
    config = yaml.safe_load(DEPENDABOT.read_text(encoding="utf-8"))
    docker = [e for e in config["updates"] if e["package-ecosystem"] == "docker"]
    assert docker, (
        "ไม่มี `package-ecosystem: docker` ใน .github/dependabot.yml — "
        "base image ถูก pin ไว้แล้วไม่มีใครขยับ security patch ให้"
    )
    for entry in docker:
        assert entry.get("schedule", {}).get("interval"), "docker: ไม่ได้ตั้งรอบ"


def test_dependabot_asks_for_a_fresh_digest_not_a_new_python():
    """ต้องปิด major/minor ไว้ ไม่งั้นมันเสนอขึ้นรุ่น Python ให้เอง

    PR ใบแรกที่มันเปิดคือ `3.13-slim` → `3.14-slim` ซึ่งไม่ใช่สิ่งที่การ pin
    digest ต้องการ · รุ่นของ Python ถูกตรึงไว้อีกหลายจุด (`Pipfile`,
    `pyproject.toml`, `ci.yml`) การขยับที่ Dockerfile ที่เดียวจึงเป็นการทำให้
    image ไม่ตรงกับทุกที่ที่เหลือ ไม่ใช่การอัปเดต — **การขึ้นรุ่น Python
    ต้องขยับพร้อมกันทั้งโปรเจกต์ ไม่ใช่มาในรูป PR อัตโนมัติที่แก้ไฟล์เดียว**
    """
    config = yaml.safe_load(DEPENDABOT.read_text(encoding="utf-8"))
    docker = [e for e in config["updates"] if e["package-ecosystem"] == "docker"]

    for entry in docker:
        ignored = {
            update_type
            for rule in entry.get("ignore", [])
            if rule.get("dependency-name") in ("python", "*")
            for update_type in rule.get("update-types", [])
        }
        missing = {"version-update:semver-major", "version-update:semver-minor"} - ignored
        assert not missing, (
            f"docker: ไม่ได้ปิดการขยับรุ่นชนิด {sorted(missing)} ของ image `python` — "
            "Dependabot จะเสนอขึ้นรุ่น Python ให้เองโดยแก้แค่ Dockerfile"
        )


def test_the_python_version_is_the_same_everywhere():
    """digest ใน Dockerfile ต้องเป็น Python รุ่นเดียวกับที่ทุกที่ประกาศไว้

    ข้อนี้คือเหตุผลที่ปิด major/minor ข้างบน — เขียนเป็นเทสต์ไว้ด้วยเพราะ
    ถ้าวันหนึ่งมีคน merge PR ขึ้นรุ่นเข้ามาโดยไม่ขยับที่อื่น ต้องมีอะไรดัง
    """
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    in_image = set(re.findall(r"^FROM\s+python:(\d+\.\d+)-", dockerfile, re.MULTILINE))
    assert in_image, "อ่านรุ่น Python จาก Dockerfile ไม่ได้"

    declared = set(re.findall(r'python_version\s*=\s*"(\d+\.\d+)"', (ROOT / "Pipfile").read_text()))
    assert declared, "อ่าน python_version จาก Pipfile ไม่ได้"

    assert in_image == declared, (
        f"Dockerfile ใช้ Python {sorted(in_image)} แต่ Pipfile ประกาศ {sorted(declared)}"
    )
