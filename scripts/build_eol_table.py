"""ตรึงตาราง EOL ของ runtime หลักไว้ใน repo — `docs/eol-pinned.json`

หลักเดียวกับ `docs/asvs-5.0.0.json`: หน้า admin ที่ต้องต่อเน็ตคือหน้าที่พัง
เพราะเน็ต และข้อมูลที่เปลี่ยนใต้เท้าทำให้จอเมื่อวานกับวันนี้ไม่ตรงกันโดยไม่มี
commit ไหนบอก — จึง fetch **ด้วยมือเป็นรอบ** แล้ว commit ไฟล์ที่ตรึงไว้
(รอบทบทวนอยู่ใน `docs/SECURITY-CADENCE.md`)

ใช้: `pipenv run python scripts/build_eol_table.py --fetch` แล้ว commit
ไฟล์ที่เปลี่ยน · รันเปล่า ๆ = ตรวจว่าไฟล์ที่ตรึงยัง parse ได้และครอบ runtime
ที่ใช้อยู่จริง (exit 1 ถ้าไม่ครอบ)

บทบาท: generator — สร้างไฟล์ที่ commit ไว้ — หลักฐานคือผลลัพธ์ต้องตรงกับที่ commit (coverage ไม่ใช่ตัววัดของชนิดนี้)
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "eol-pinned.json"

#: ผลิตภัณฑ์ที่ตรึง — เฉพาะ runtime (endoflife.date ไม่มีข้อมูลของ Flask —
#: ตรวจแล้ว 404 · framework เฝ้าผ่าน pip-audit/Dependabot ซึ่งเป็นช่องที่ถูกอยู่แล้ว
#: การกุ timeline ของของที่ไม่มีแหล่งจริงคือการโกหกที่หน้าตาเหมือนข้อมูล)
PRODUCTS = ("python",)


def fetch() -> dict:
    """ดึงตาราง EOL จาก endoflife.date — เรียกด้วยมือเท่านั้น ไม่มีทางถูกเรียกตอนรัน"""
    data: dict[str, object] = {
        "_source": "https://endoflife.date/api/<product>.json",
        "_fetched_on": datetime.date.today().isoformat(),
    }
    for product in PRODUCTS:
        url = f"https://endoflife.date/api/{product}.json"
        with urllib.request.urlopen(url, timeout=30) as response:
            data[product] = json.load(response)
    return data


def verify() -> int:
    """ไฟล์ที่ตรึงต้อง parse ได้ และครอบ python cycle ที่กำลังรันอยู่จริง"""
    data = json.loads(OUT.read_text(encoding="utf-8"))
    running = f"{sys.version_info.major}.{sys.version_info.minor}"
    cycles = {row["cycle"] for row in data.get("python", [])}
    if running not in cycles:
        print(f"ตาราง EOL ที่ตรึงไม่ครอบ python {running} — รัน --fetch แล้ว commit ใหม่")
        return 1
    print(f"ตาราง EOL ครอบ python {running} · fetch ล่าสุด {data.get('_fetched_on')}")
    return 0


def main() -> int:
    """--fetch = ดึงใหม่แล้วเขียนทับ · รันเปล่า = ตรวจของที่ตรึงไว้"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    if args.fetch:
        OUT.write_text(json.dumps(fetch(), ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"เขียน {OUT.relative_to(ROOT)}")
        return 0
    return verify()


if __name__ == "__main__":
    sys.exit(main())
