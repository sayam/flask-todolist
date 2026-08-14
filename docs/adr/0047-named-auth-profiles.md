# 0047 — auth หลาย profile ต่อ plugin เดียว + ลำดับที่ประกาศ ไม่มี fallback เงียบ

สถานะ: **accepted** (2026-08-15 — เสนอคู่กับ ADR 0046 และเจ้าของอนุมัติพร้อมกัน
· เปิดเฟส 17)

**บริบท:** วันนี้ plugin auth ภายนอกตั้ง config ได้ชุดเดียว (`OIDC_ISSUER`,
`LDAP_URL` ฯลฯ) — องค์กรที่มี directory สองวง (พนักงาน/พาร์ตเนอร์) หรือ IdP
สองตัวต้องเลือกได้ตัวเดียว · ข้อ 19 ของรายการ idea ขอ "หลาย profile +
fallback"

## คำตัดสิน

- **profile = instance ของ config ไม่ใช่ instance ของ plugin** — โค้ด plugin
  ตัวเดียว หลายชุดค่า: `AUTH_PROFILES="oidc:corp,ldap:hq,ldap:partner"`
  · ค่าใช้ prefix ต่อ profile: `OIDC_CORP_ISSUER=...` `LDAP_HQ_URL=...`
  · ไม่ประกาศ = พฤติกรรมเดิมทุกประการ (ชุดค่าเดี่ยวไม่มี prefix)
- **ประกาศ profile แล้ว ค่าของ profile นั้นมาจากคีย์ที่มี prefix เท่านั้น**
  ไม่ตกกลับไปคีย์เปล่า — การตกกลับทำให้สอง profile "ยืม" ค่ากันเงียบ ๆ
  แล้ววันที่ลบคีย์ของตัวหนึ่งทิ้ง อีกตัวเปลี่ยนพฤติกรรมโดยไม่มีใครสั่ง
- **ลำดับใน `AUTH_PROFILES` คือลำดับที่ลอง และเป็นลำดับที่ *ประกาศ*** —
  ไม่มีการเลื่อนตัวถัดไปขึ้นมาแทนโดยระบบ (บทเรียน `PLUGIN_PICKS`: ตัวที่
  ไม่ถูกเลือกเลื่อนขึ้นมาเอง = การ*เปิด*โดยไม่มีใครสั่ง)
- **fallback ข้าม profile เกิดเฉพาะกรณี "ติดต่อไม่ได้"** (timeout/connection)
  — "ปฏิเสธ" (รหัสผิด/ไม่รู้จักผู้ใช้) **หยุดทันที ไม่ลองตัวถัดไป** ไม่งั้น
  คนไล่รหัสได้จำนวนครั้งคูณด้วยจำนวน profile และบัญชีชื่อซ้ำสองวงจะ login
  ข้ามวงกันได้ · สองอย่างนี้แยกกันที่**ชนิด exception** ในชั้น service
  (`UnreachableError` ลองตัวถัดไปได้ · `ServiceError` อื่นทุกตัวหยุด) ไม่ใช่
  ที่การอ่านข้อความ
- **คีย์ของ profile คือ `<คีย์ plugin>:<ชื่อ profile>`** (`auth/oidc:corp`) —
  ใช้ที่ URL ของ SSO, ที่ `DISABLED_PLUGINS` (ปิดทีละ profile ได้ · ปิดคีย์
  plugin แม่ = ปิดทุก profile ของมัน) และที่ `flask plugin-list` (คีย์ที่
  ไม่เคยถูกพิมพ์ออกมา คือคีย์ที่ไม่มีใครใส่ลง `DISABLED_PLUGINS` ได้ถูก)
- identity ผูกด้วย `(issuer/directory, subject/external_id)` ต่อ profile —
  ตารางเดิมรองรับอยู่แล้ว (unique constraint คู่นี้มีตั้งแต่ ADR 0028/0029)
  **ไม่มี migration** · ปิดของค้าง "ผูกหลาย IdP กับผู้ใช้คนเดียว" เป็นผล
  พลอยได้: คนเดียว login จากสอง issuer ได้สองแถว identity ชี้ user เดียวกัน
- หน้า login แสดงปุ่มต่อ profile ที่ *ใช้งานได้จริง* (config ครบ) — ป้ายปุ่ม
  มาจาก `<PREFIX>_<PROFILE>_LABEL` (ไม่ตั้ง = ชื่อ plugin + ชื่อ profile)
  เพราะหลาย profile ของ plugin เดียวจะได้ปุ่มชื่อซ้ำกันหมดถ้าใช้ชื่อจาก
  manifest
- รหัสผ่านของที่นี่ยังมาก่อนเสมอ (ADR 0029 ข้อ 2) — profile ภายนอกต่อคิว
  หลังรหัสผ่าน local เหมือนเดิม

## ผลที่ตามมา

- callback URL ของ OIDC เป็นของแต่ละ profile (`/login/sso/auth/oidc:corp/callback`)
  — ต้องลงทะเบียนกับ IdP แยกใบ ใครเพิ่ม profile ต้องรู้ข้อนี้ (`docs/OPERATIONS.md`)
- เทสต์ต้องครอบ: ลำดับถูกเคารพ · ปฏิเสธไม่ fallback · ติดต่อไม่ได้จึง
  fallback · ปิด profile เดียวไม่กระทบตัวอื่น · ชื่อซ้ำสองวงไม่ปนกัน
- job `sso`/`ldap` ใน CI ขยายเป็นสอง profile อย่างน้อยหนึ่ง job — พิสูจน์
  ของจริง ไม่ใช่แค่ fake ในเทสต์
