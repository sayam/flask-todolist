# 0006 — สถาปัตยกรรม plugin แบบ Moodle

สถานะ: accepted (backfill — ตัดสินใจจริงช่วง theme plugin)

**บริบท:** ทิศทางแอปคือ core + ส่วนขยาย โดยส่วนขยายรับผิดชอบตัวเองล้วน ๆ
**คำตัดสิน:** plugin = ไดเรกทอรี `app/plugins/<ชนิด>/<ไอดี>/` + `plugin.json`
core รู้แค่วิธีค้นหา ห้าม hardcode ชื่อ plugin / เพิ่ม-ถอน = วาง-ลบไดเรกทอรี /
ถอนตัวที่ถูกใช้อยู่ต้อง fallback ไม่พัง / plugin ที่มีข้อมูลดูแล table ตัวเอง
**ผล:** พิสูจน์กับ theme แล้ว (purge ขณะใช้งาน → ตกกลับ core, DB ไม่ถูกแตะ)
มีเทสต์ grep กัน core อ้างชื่อ plugin / DB backend plugin มี semantics ต่าง:
ห้าม purge ตัว active (ROADMAP ข้อ 4.1)
