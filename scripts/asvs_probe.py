"""ตรวจข้อ ASVS ที่ *ตรวจอัตโนมัติได้* บนแอป Flask เล็ก ๆ ที่ถูก generate มา

**ตัวจริงอยู่ที่ verifiable-gates แล้ว** (ADR 0077 · ขั้น 5) — `verifiable_gates.asvs_probe`
· ไฟล์นี้เหลือเป็นที่อยู่ที่คนกับ agent เรียกถึงได้เหมือนเดิม

**การทดลองย้ายไปด้วยทั้งชุด** เพราะมันตอบคำถามเกี่ยวกับ vg ไม่ใช่เกี่ยวกับที่นี่ —
รายงานและข้อมูลดิบอยู่ที่ `docs/comparison/` ของ vg ส่วนที่นี่เหลือเป็นบันทึก
การพัฒนาที่ freeze แล้ว (`docs/comparison/README.md`)

ใช้ในการทดลองเท่านั้น — **ไม่ใช่การประเมิน ASVS เต็มรูป** (ของจริงอยู่ใน
`docs/ASVS.md` 253 ข้อ ประเมินด้วยคน) ที่นี่คือ 10 ข้อที่พิสูจน์ได้จากตัวไฟล์
โดยไม่ต้องรันแอป

บทบาท: decider — ตัดสินผ่าน/ไม่ผ่าน — หลักฐานคือเทสต์ที่ฝังความผิดแล้วต้องจับได้ · ของสะอาดต้องไม่ถูกจับ
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "vendor" / "verifiable-gates" / "src"))

from verifiable_gates import asvs_probe  # noqa: E402 — ต้องต่อ path ให้ vendor ก่อน import

CHECKS = asvs_probe.CHECKS
NOT_OUR_CODE = asvs_probe.NOT_OUR_CODE
probe = asvs_probe.probe
python_files = asvs_probe.python_files
