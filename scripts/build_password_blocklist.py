"""สร้าง `app/password_blocklist.txt` ใหม่จากรายการรหัสผ่านที่หลุดแล้ว (Phase 4)

    pipenv run python scripts/build_password_blocklist.py

ไฟล์ผลลัพธ์เป็น **ของที่ generate มา ห้ามแก้ด้วยมือ** เหมือน `app/sun_data.py`
ต้นทางคือรายการ 100,000 รหัสที่ถูกใช้บ่อยที่สุดซึ่ง NCSC (สหราชอาณาจักร)
สกัดจากคลัง Have I Been Pwned แล้วเผยแพร่ไว้ให้เอาไปทำ blocklist โดยเฉพาะ

**ทำไมถึงกรองทิ้งเยอะ:** รหัสที่สั้นกว่าเกณฑ์ความยาวขั้นต่ำถูกปฏิเสธด้วย
กฎความยาวอยู่แล้ว เก็บไว้ในรายการก็ไม่มีทางถูกใช้เทียบ — จาก 100k เหลือ ~46k
ทำให้ไฟล์เล็กลงครึ่งหนึ่งโดยไม่ได้ลดการป้องกันลงเลยแม้แต่รหัสเดียว

รูปแบบในไฟล์ต้องตรงกับที่ `app/services/passwords.py` ใช้เทียบเป๊ะ
(NFKC + casefold) — ตัว normalize จึง import มาจากที่นั่นตัวเดียว ไม่ก๊อปสูตรมาไว้ที่นี่

บทบาท: generator — สร้างไฟล์ที่ commit ไว้ — หลักฐานคือผลลัพธ์ต้องตรงกับที่ commit (coverage ไม่ใช่ตัววัดของชนิดนี้)
"""

import argparse
import pathlib
import sys
import urllib.request

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "app" / "password_blocklist.txt"

# รายการของ NCSC ที่ SecLists รวบรวมไว้ (ทั้งสองที่เผยแพร่เพื่อให้เอาไปใช้แบบนี้)
SOURCE_URL = (
    "https://raw.githubusercontent.com/danielmiessler/SecLists/master/"
    "Passwords/Common-Credentials/100k-most-used-passwords-NCSC.txt"
)

HEADER = """\
# app/password_blocklist.txt — ไฟล์ที่ generate มา ห้ามแก้ด้วยมือ
# สร้างใหม่: pipenv run python scripts/build_password_blocklist.py
#
# ที่มา: {source}
#   รายการ 100k รหัสที่ถูกใช้บ่อยที่สุดในคลัง Have I Been Pwned
#   เผยแพร่โดย NCSC (UK) เพื่อให้เอาไปทำ blocklist โดยเฉพาะ
#
# ทุกบรรทัดผ่าน NFKC + casefold มาแล้ว และยาวอย่างน้อย {min_length} ตัว
# (สั้นกว่านั้นถูกกฎความยาวปฏิเสธก่อนอยู่แล้ว — ดู app/services/passwords.py)
# จำนวน: {count} รายการ
"""


def read_source(source: str) -> str:
    """อ่านต้นทาง — รับได้ทั้ง URL และไฟล์บนเครื่อง (เอาไว้ generate ซ้ำแบบ offline)"""
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source) as response:  # noqa: S310  URL คงที่ในไฟล์นี้
            return response.read().decode("utf-8", errors="replace")
    return pathlib.Path(source).read_text(encoding="utf-8", errors="replace")


def build(raw: str, min_length: int, to_key) -> list[str]:
    """แปลงเป็นรายการที่พร้อมเทียบ: normalize+casefold, ตัดตัวที่สั้นเกินไป, ตัดซ้ำ, เรียง"""
    entries = set()
    for line in raw.splitlines():
        candidate = to_key(line.strip())
        if len(candidate) >= min_length:
            entries.add(candidate)
    return sorted(entries)


def main() -> int:
    sys.path.insert(0, str(REPO_ROOT))
    from app.services.passwords import MIN_LENGTH, blocklist_key

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=SOURCE_URL, help="URL หรือ path ของรายการต้นทาง")
    args = parser.parse_args()

    entries = build(read_source(args.source), MIN_LENGTH, blocklist_key)
    if not entries:
        print("ต้นทางไม่มีรายการที่ผ่านเกณฑ์เลย — ไม่เขียนทับไฟล์เดิม", file=sys.stderr)
        return 1

    header = HEADER.format(source=args.source, min_length=MIN_LENGTH, count=len(entries))
    OUTPUT_PATH.write_text(header + "\n".join(entries) + "\n", encoding="utf-8")
    print(f"เขียน {OUTPUT_PATH.relative_to(REPO_ROOT)} แล้ว — {len(entries)} รายการ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
