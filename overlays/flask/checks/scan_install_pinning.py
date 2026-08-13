"""gate: ci-tools-hash-pinned — เครื่องมือที่ CI ติดตั้งเองต้องตรึงด้วย hash

`pip install <ชื่อ>` หยิบรุ่นล่าสุด ณ วินาทีที่ job รัน และรันด้วยสิทธิ์ของ
workflow · ต้องเป็น `--require-hashes -r <ล็อก>` · ฝั่ง node ต้อง `npm ci`
(`npm install pkg@x` ตรึงได้แค่ตัวเดียว ที่เหลือทั้งต้นไม้ลอย)

คอมเมนต์ถูกตัดทิ้งก่อนตรวจ — ไฟล์พวกนี้ชอบอธิบายตัวเองด้วยการยกคำสั่งต้องห้าม

exit 0 = สะอาด/NA · 1 = พบ · 2 = เรียกผิด
"""

from __future__ import annotations

import pathlib
import re
import sys

PIP_INSTALL = re.compile(r"(?:^|[\s/])pip3?\s+install\b")
NPM_INSTALL = re.compile(r"(?:^|[\s/])npm\s+(?:install|i|add)\b")


def _commands(path: pathlib.Path) -> list[str]:
    joined, buffer = [], ""
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


def main(root: pathlib.Path) -> int:
    targets = sorted((root / ".github" / "workflows").glob("*.y*ml"))
    targets += [p for p in [root / "Dockerfile"] if p.is_file()]
    if not targets:
        print("NA: ไม่มี workflow/Dockerfile — ยังไม่มีอะไรให้ตรวจ")
        return 0

    findings: list[str] = []
    for path in targets:
        for line in _commands(path):
            if PIP_INSTALL.search(line) and "--require-hashes" not in line:
                findings.append(f"{path.relative_to(root)}: {line.strip()[:70]}")
            if NPM_INSTALL.search(line):
                findings.append(f"{path.relative_to(root)}: ใช้ npm ci แทน — {line.strip()[:60]}")

    for finding in findings:
        print(f"ci-tools-hash-pinned: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("ใช้: scan_install_pinning.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
