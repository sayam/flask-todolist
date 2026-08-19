"""image ของ stack ที่ CI ดึงมารัน ต้องตรึงด้วย digest — audit รอบ 15 ข้อ 1–2

โปรเจกต์นี้มีด่านบังคับการ pin อยู่แล้ว **สามตัว**: `tests/test_workflow_pinning.py`
(action → SHA) · `tests/test_dockerfile_pinning.py` (base image → digest) ·
`tests/test_ci_pinning.py` (เครื่องมือของ CI → hash) · **ไม่มีตัวไหนเปิดไฟล์ compose**

ผลที่วัดได้ 2026-08-19: image ของคนอื่น **11 ตัวถูกดึงด้วย tag** และรันใน
**11 จาก 25 job** ของ CI ทุก push · ในนั้นมี `ghcr.io/zaproxy/zaproxy:stable`
ซึ่งเป็น **tag ลอย** และเป็นตัว *ตัดสิน* ผลด้านความปลอดภัยของทุก push

**ทำไมเรื่องนี้ต่างจาก "ดึง image ไม่ได้แล้ว job แดง"**: `docs/SUPPLY-CHAIN.md`
ลงรายชื่อ image ชุดนี้ไว้แล้ว แต่ระบุผลกระทบไว้ว่า "job แดงทันทีที่ดึง image ไม่ได้"
ซึ่งเป็นเรื่อง *ความพร้อมใช้* · สิ่งที่หายไปคือ *ความสมบูรณ์* กับ **ความทำซ้ำได้**:
เขียวเมื่อวานกับเขียววันนี้อาจมาจาก scanner คนละตัว และไม่มีที่ไหนบันทึกว่าไบต์
ชุดไหนเป็นคนตัดสิน — โปรเจกต์นี้เขียนหลักข้อนี้ไว้เองแล้วในรูปอื่น (ADR 0055:
"รุ่นที่ตัดสินคือรุ่นใน action รุ่นบนเครื่องเป็นแค่ preview")

**ราคาที่การ pin เรียกเก็บ ต้องจ่ายพร้อมกัน**: ตรึงแล้วไม่มีใครขยับ = แช่ช่องโหว่
ไว้ตลอดกาล ซึ่งแย่กว่าไม่ตรึง · ที่นี่จึงบังคับสองข้อคู่กันเสมอ — ตรึง **และ**
มี ecosystem ของ Dependabot ที่ขยับมันอยู่จริง (`docker-compose` เป็นคนละตัวกับ
`docker` ซึ่งอ่านแค่ `Dockerfile` — เราประกาศไว้แค่ตัวหลังมาตลอด)
"""

import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEPENDABOT = ROOT / ".github" / "dependabot.yml"
COMPOSE = sorted(ROOT.glob("compose*.yaml"))
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
SCRIPTS = sorted((ROOT / "scripts").glob("*.sh"))

DIGEST = re.compile(r"@sha256:[0-9a-f]{64}")
# `image: mysql:8@sha256:…` ในไฟล์ compose และ service container ของ workflow
# **`[^\S\n]` ไม่ใช่ `\s`** — `\s` ข้ามบรรทัดได้ แล้วจะไปจับ job ที่ *ชื่อ* `image:`
# (ci.yml มีอยู่จริง) โดยหยิบค่าของบรรทัดถัดไปมาเป็น image reference
IMAGE_LINE = re.compile(r"^[^\S\n]+image:[^\S\n]*(\S+)[^\S\n]*$", re.MULTILINE)
# image ที่สคริปต์ยิงเอง เช่น `ZAP_IMAGE="${ZAP_IMAGE:-ghcr.io/zaproxy/zaproxy:stable}"`
# **tag กับ digest เป็น optional ทั้งคู่โดยตั้งใจ** — ถ้าบังคับว่าต้องมี tag
# reference ที่ไม่มี tag จะ *หลุดจากรายการ* แทนที่จะถูกฟ้อง แล้วด่านจะเขียว
# เพราะมองไม่เห็นของที่ผิด (จับได้ตอน mutation test ของด่านนี้เอง)
SCRIPT_IMAGE = re.compile(
    r"(?:ghcr\.io|quay\.io|docker\.io)/[\w./-]+(?::[\w.-]+)?(?:@sha256:[0-9a-f]{64})?"
)

# ค่าที่ถูกแทนตอนรัน (`${{ matrix.db.image }}`) ไม่ใช่ image reference — ตัวจริง
# อยู่ในตาราง matrix ซึ่งถูกอ่านด้วย regex เดียวกันอยู่แล้ว
TEMPLATED = re.compile(r"\$\{\{|\$\{?[A-Z_]+\}?")


def _references() -> list[tuple[str, str]]:
    """(ไฟล์, image reference) ของทุกที่ที่เราสั่งให้ดึง image ของคนอื่นมารัน"""
    found = []
    for path in [*COMPOSE, *WORKFLOWS]:
        text = path.read_text(encoding="utf-8")
        found += [
            (str(path.relative_to(ROOT)), ref)
            for ref in IMAGE_LINE.findall(text)
            if not TEMPLATED.search(ref)
        ]
    for path in SCRIPTS:
        text = path.read_text(encoding="utf-8")
        found += [
            (str(path.relative_to(ROOT)), match.group(0).rstrip('"'))
            for match in SCRIPT_IMAGE.finditer(text)
        ]
    return found


@pytest.fixture(scope="module")
def references() -> list[tuple[str, str]]:
    found = _references()
    # **ไม่พอที่จะเช็คว่า "ไม่ว่าง"** — regex ที่เลิกแมตช์ของบางชนิดจะทำให้ด่านเขียว
    # โดยที่มันมองไม่เห็นของที่ผิด · อย่างน้อยต้องได้หนึ่งตัวต่อไฟล์ compose
    # หนึ่งไฟล์ บวกของที่สคริปต์ยิงเอง
    assert len(found) >= len(COMPOSE) + 1, (
        f"เจอ image reference แค่ {len(found)} ตัวจาก {len(COMPOSE)} ไฟล์ compose — "
        "regex อ่านไฟล์ไม่เจอแล้ว ซึ่งทำให้ด่านนี้เขียวโดยไม่ได้ตรวจอะไร"
    )
    return found


def test_every_stack_image_is_pinned_by_digest(references):
    """tag ย้ายได้ digest ย้ายไม่ได้ — และผลตรวจที่ทำซ้ำไม่ได้ ไม่ใช่หลักฐาน"""
    unpinned = sorted({f"{where}: {ref}" for where, ref in references if not DIGEST.search(ref)})
    assert not unpinned, (
        "image ที่ยังดึงด้วย tag เปล่า:\n  " + "\n  ".join(unpinned) + "\n"
        "หา digest ด้วย `docker buildx imagetools inspect <ref>` แล้วเขียนเป็น "
        "`<ชื่อ>:<tag>@sha256:<digest>` — **เก็บ tag ไว้ด้วย** เพราะ Dependabot ใช้มัน"
    )


def test_every_digest_keeps_its_tag(references):
    """`name@sha256:…` เฉย ๆ อ่านแล้วไม่มีใครรู้ว่ารันรุ่นไหนอยู่ และ Dependabot ขยับไม่ถูก"""
    without_tag = sorted(
        {f"{where}: {ref}" for where, ref in references if ":" not in ref.split("@", 1)[0]}
    )
    assert not without_tag, "digest ที่ไม่มี tag กำกับ:\n  " + "\n  ".join(without_tag)


def test_the_same_image_is_pinned_to_one_digest_everywhere(references):
    """image เดียวกันคนละ digest ในคนละไฟล์ = stack ที่ประกอบจากของคนละชุด

    เกิดง่ายมากตอนขยับทีละไฟล์ (`grafana/grafana` อยู่ทั้ง compose.metrics
    และ compose.siem) และไม่มีอะไรฟ้องเพราะทั้งสอง job ก็ยังเขียวของใครของมัน
    """
    seen: dict[str, set[str]] = {}
    for _where, ref in references:
        if "@" in ref:
            name = ref.split(":", 1)[0]
            seen.setdefault(name, set()).add(ref.split("@", 1)[1])
    split = {name: sorted(digests) for name, digests in seen.items() if len(digests) > 1}
    assert not split, f"image เดียวกันถูกตรึงคนละ digest: {split}"


def test_dependabot_moves_the_images_it_pins():
    """**ข้อนี้คือเหตุผลที่การ pin ยอมรับได้** — ถอด entry ออกเมื่อไหร่ต้องแดง

    `docker` อ่านแค่ `Dockerfile` · ไฟล์ compose เป็นของ ecosystem `docker-compose`
    ซึ่งเป็นคนละตัว · การตรึง image ไว้โดยไม่ประกาศตัวหลัง คือการแช่ช่องโหว่ของ
    ทั้ง stack ไว้ตลอดกาล ซึ่งแย่กว่าการปล่อยให้ tag ลอย
    """
    config = yaml.safe_load(DEPENDABOT.read_text(encoding="utf-8"))
    entries = [e for e in config["updates"] if e["package-ecosystem"] == "docker-compose"]
    assert entries, (
        "ไม่มี `package-ecosystem: docker-compose` ใน .github/dependabot.yml — "
        "image ของ stack ถูกตรึงไว้แล้วไม่มีใครขยับให้"
    )
    for entry in entries:
        assert entry.get("schedule", {}).get("interval"), "docker-compose: ไม่ได้ตั้งรอบ"
