"""action ทุกตัวใน workflow ต้องถูก pin ด้วย commit SHA เต็ม

**tag ย้ายได้ commit ย้ายไม่ได้** — `@v7` ชี้ไปที่ไหนก็ได้ที่เจ้าของ action
ตัดสินใจย้ายมันไป และ action รันด้วยสิทธิ์ของ workflow เรา วันที่บัญชีของเขา
ถูกยึด (เกิดมาแล้วหลายครั้งกับ action ที่มีคนใช้เป็นล้าน) tag เดิมจะชี้ไปที่
โค้ดใหม่โดยที่ไฟล์ในนี้ไม่เปลี่ยนสักตัวอักษร

ราคาที่จ่ายคืออ่านยากขึ้นและต้องมีคนขยับให้ — **Dependabot ของ `github-actions`
ขยับ SHA พร้อมคอมเมนต์เลขรุ่นให้เอง** (ดู `.github/dependabot.yml`) ราคานั้น
จึงถูกจ่ายไปแล้วก่อนหน้านี้

คอมเมนต์ `# vX.Y.Z` ต่อท้ายไม่ใช่ของประดับ: มันคือสิ่งเดียวที่ทำให้คนอ่านรู้ว่า
กำลังใช้รุ่นไหนอยู่ และเป็นสิ่งที่ Dependabot อ่านเพื่อรู้ว่าต้องอัปเดตอะไร
"""

import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW_DIR = ROOT / ".github" / "workflows"

USES = re.compile(r"^\s*-?\s*uses:\s*(\S+)(?:\s+#\s*(\S+))?", re.MULTILINE)
SHA = re.compile(r"^[0-9a-f]{40}$")
VERSION_COMMENT = re.compile(r"^v\d+(\.\d+)*$")

# action ที่มาจาก repo นี้เอง (`./.github/actions/...`) ไม่ต้อง pin — มันคือ
# โค้ดของเราที่เดินทางมาพร้อม commit เดียวกันอยู่แล้ว
LOCAL = ("./", "docker://")


def _workflows() -> list[pathlib.Path]:
    found = sorted(WORKFLOW_DIR.glob("*.y*ml"))
    assert found, "ไม่เจอไฟล์ workflow สักไฟล์"
    return found


def _uses(path: pathlib.Path) -> list[tuple[str, str | None]]:
    return [
        (ref, comment)
        for ref, comment in USES.findall(path.read_text(encoding="utf-8"))
        if not ref.startswith(LOCAL)
    ]


@pytest.mark.parametrize("path", _workflows(), ids=lambda p: p.name)
def test_every_action_is_pinned_to_a_commit_sha(path):
    entries = _uses(path)
    assert entries, f"{path.name}: ไม่เจอ `uses:` สักบรรทัด — ตัวดึงพังหรือเปล่า"

    unpinned = [ref for ref, _ in entries if "@" not in ref or not SHA.match(ref.split("@")[-1])]
    assert not unpinned, (
        f"{path.name}: action ที่ยังไม่ได้ pin ด้วย SHA: {unpinned}\n"
        "tag ย้ายได้ commit ย้ายไม่ได้ — และ action รันด้วยสิทธิ์ของ workflow เรา"
    )


@pytest.mark.parametrize("path", _workflows(), ids=lambda p: p.name)
def test_every_pin_says_which_version_it_is(path):
    """SHA เปล่า ๆ ไม่มีใครรู้ว่าเป็นรุ่นไหน และ Dependabot ก็อัปเดตให้ไม่ได้"""
    missing = [
        ref for ref, comment in _uses(path) if not comment or not VERSION_COMMENT.match(comment)
    ]
    assert not missing, (
        f"{path.name}: pin ที่ไม่มีคอมเมนต์เลขรุ่นกำกับ: {missing}\n"
        "รูปแบบที่ต้องการคือ `uses: owner/repo@<sha40> # v1.2.3`"
    )


def test_the_same_action_is_pinned_to_one_sha_everywhere():
    """สอง SHA ของ action เดียวกันในไฟล์เดียวกันคือของที่ลืมขยับไปครึ่งหนึ่ง

    เจอมาแล้วในรูปของ tag: `actions/upload-artifact` ค้างที่ `@v4` อยู่จุดเดียว
    ใน job `dast` ขณะที่ที่อื่นเป็น `@v7` มาสิบวัน โดย CI เขียวตลอด
    """
    seen: dict[str, set[str]] = {}
    for path in _workflows():
        for ref, _ in _uses(path):
            action, _, sha = ref.partition("@")
            # subpath ของ repo เดียวกันต้องเป็น commit เดียวกัน
            repo = "/".join(action.split("/")[:2])
            seen.setdefault(repo, set()).add(sha)

    split = {repo: sorted(shas) for repo, shas in seen.items() if len(shas) > 1}
    assert not split, f"action ที่ถูก pin คนละ SHA กัน: {split}"
