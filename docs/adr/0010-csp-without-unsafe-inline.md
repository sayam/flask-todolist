# 0010 — CSP ไม่มี unsafe-inline และพฤติกรรมฝั่ง client อยู่ในไฟล์เดียว

สถานะ: accepted (2026-08-03)

**บริบท:** Phase 1 ต้องตั้ง security header baseline (ISO/IEC 25010 §Security)
ก่อนที่จะมี template เพิ่มอีกมากในเฟสถัดไป ตอนนั้นแอปมี `onsubmit=`/`onchange=`
และ `style=` กระจายใน template

**คำตัดสิน:**
- ใช้ Flask-Talisman ตั้ง CSP แบบ `'self'` ล้วน **ไม่มี `unsafe-inline`
  และไม่มี `unsafe-eval`** พร้อม `base-uri 'none'`, `object-src 'none'`,
  `frame-ancestors 'none'`, `form-action 'self'`
- **ไม่ใช้ nonce** เพราะไม่มี inline script เหลือแล้ว nonce จะเพิ่ม state
  ให้ทุก response โดยไม่ได้อะไรกลับมา
- พฤติกรรมฝั่ง client ทั้งหมดย้ายไป `app/static/app.js` ตัวเดียว ใช้
  event delegation ที่ `document` และสื่อสารกับ template ผ่าน `data-*`
  (`data-confirm`, `data-auto-submit`) — element ที่ render มาทีหลังจึงทำงานได้เอง
- ของที่ผูกกับ TLS (HSTS, บังคับ https, cookie `Secure`) คุมด้วย
  `HTTPS_ENABLED=1` ตัวเดียว เปิดพร้อมกันตอนมี reverse proxy จริงใน Phase 5

**เหตุผลที่ไม่เลือกทางอื่น:** ใส่ `unsafe-inline` แล้วค่อยเก็บทีหลังแปลว่า CSP
แทบไม่กัน XSS เลยตลอดเฟส 2–4 ซึ่งเป็นเฟสที่จะเพิ่ม template มากที่สุด
และ "ค่อยเก็บทีหลัง" คือการกลับไปแก้ของเก่า ซึ่งลำดับเฟสตั้งใจหลีกเลี่ยง

**ผล:** ถ้าใครใส่ `onclick=` หรือ `style=` กลับเข้า template **browser จะบล็อก
เงียบ ๆ โดยไม่มี error ฝั่ง server** ซึ่งเป็นความล้มเหลวแบบมองไม่เห็น
`tests/test_security_headers.py` จึงตรวจสองชั้น — header ที่ส่งออกจริง
และตัว template ว่าไม่มี inline หลงเหลือ

ข้อจำกัดที่ยอมรับ: theme plugin เขียน CSS ได้แต่เขียน JS ไม่ได้ (Phase 5 ถ้า
ต้องการจริงค่อยออกแบบ ให้ plugin ลงทะเบียนไฟล์ static ผ่าน manifest แทนการ inline)

---

## หมายเหตุเพิ่มเติม (2026-08-10 — Phase 5 · P5-12)

ตอนเปิด TLS จริงที่ reverse proxy มีคำถามว่า HSTS ควรมาจาก nginx หรือจากแอป
**คำตอบคือแอปที่เดียว** — Talisman ส่งให้อยู่แล้วเมื่อ `HTTPS_ENABLED=1` การเพิ่ม
`add_header` ที่ nginx ด้วยจะได้ header สองบรรทัดที่มีค่าไม่ตรงกันได้ และวันที่
ต้องแก้ `max-age` จะมีสองที่ให้ลืม · ด่านใน CI ตรวจว่ามี **หนึ่งบรรทัดพอดี**
ไม่ใช่แค่ "มี" เพราะ "มีสองบรรทัด" คืออาการของการมีสองเจ้าของ

คำตัดสินเดิมของ ADR นี้ไม่เปลี่ยน — เพิ่มความชัดว่าขอบเขต "header ชุดความ
ปลอดภัยอยู่ที่ `app/security_headers.py` ที่เดียว" ครอบถึง reverse proxy ด้วย
