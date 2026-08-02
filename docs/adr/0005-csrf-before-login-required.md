# 0005 — ยอมรับลำดับ CSRF ตัดก่อน login_required

สถานะ: accepted (backfill — พบและตัดสินใจช่วงตรวจ CSRF)

**บริบท:** `CSRFProtect` ทำงานใน before_request จึงตัดก่อน `@login_required`
POST ที่ไม่มีทั้ง token และ session ได้ 400 ไม่ใช่ 302
**ทางเลือก:** เขียน middleware จัดลำดับใหม่ vs ยอมรับพฤติกรรม
**คำตัดสิน:** ยอมรับ — สองด่านยังอยู่ครบ (พิสูจน์แล้ว: มี token ถูกแต่ไม่ login
ก็ยังติด 302) การ reorder คือ custom security code ที่เสี่ยงกว่าตัวพฤติกรรมเอง
**ผล:** จดตาราง status ไว้ใน CLAUDE.md — เห็น 400 อย่าสรุปว่า "ไม่ได้ login"
