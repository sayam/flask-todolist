# 0058 — เซ็น release artifact แบบ keyless + SLSA provenance

สถานะ: **accepted** (2026-08-16 — ช่องว่างข้อ 4 จากผล audit governance
ทำตามกำหนดใน `docs/RELEASE.md`: งานนี้ผูกกับ release เพราะแตะ workflow
ของการออกรุ่น ไม่ใช่ CI ทุก push)

**บริบท:** release แนบ SBOM 8 ไฟล์มาตั้งแต่ v1.0.0 แต่ไม่มีไฟล์ไหนถูกเซ็น
— คนที่โหลดไป verify ไม่ได้ว่ามาจาก CI ของ repo นี้จริงหรือถูกสลับกลางทาง
(SLSA ระดับ 0) และ SBOM ที่ generate บนเครื่อง dev แล้วอัปโหลดมือ ต่อให้
เซ็นก็ยังตอบไม่ได้ว่า*สร้างจากอะไร*

## คำตัดสิน

1. **workflow `release.yml` ทำงานตอน release ถูก publish**: generate SBOM
   ทุก category **ในตัว workflow เอง** จากโค้ดของ tag (provenance ที่
   attest ของซึ่งตัวเองไม่ได้สร้างคือกระดาษเปล่า) → เซ็น → verify → แนบ
   เข้า release · ขั้นตอน manual ของ `docs/RELEASE.md` เปลี่ยนจาก "แนบ
   SBOM เอง" เป็น "สร้าง release เปล่าแล้วให้ workflow แนบของ"
2. **เซ็นด้วย cosign แบบ keyless** (sigstore OIDC ของ GitHub Actions —
   ไม่มีคีย์ให้เก็บ ให้หมุน หรือให้หลุด) ออกเป็น bundle ต่อไฟล์
   (`<ไฟล์>.sigstore.json`) · ใน workflow ต้อง **verify สองทิศทันที**:
   identity ของ workflow นี้ต้องผ่าน และ identity อื่นต้องไม่ผ่าน —
   ลายเซ็นที่ไม่เคยถูก verify คือไฟล์แนบ
3. **provenance ผ่าน `actions/attest-build-provenance`** (attestation
   store ของ GitHub · SLSA v1) — verify ด้วย
   `gh attestation verify <ไฟล์> --repo sayam/flask-todolist`
4. gate `release-signed-and-attested` (`axis: supply-chain` — สมาชิกตัวที่
   18) · วิธี verify สำหรับผู้ใช้อยู่ใน `SECURITY.md`

## ทางที่ไม่ได้เลือก

- **slsa-github-generator** — ปัดตกด้วยเหตุขัดกันของด่าน: ตัว generator
  **บังคับอ้าง reusable workflow ด้วย tag** (`@vX.Y.Z` — เอกสารของมันระบุ
  ว่า verifier ตรวจกับ tag) ขณะที่ `tests/test_workflow_pinning.py` บังคับ
  SHA ทุก `uses:` — การยกเว้นด่าน pinning เพื่อได้ provenance คือการแลก
  supply chain ชั้นหนึ่งกับอีกชั้นหนึ่ง · attestation แบบ native ให้
  SLSA provenance ที่ pin SHA ได้และ verify ง่ายกว่า (`gh` CLI มีในเครื่อง
  ทุกคนที่ clone repo จาก GitHub อยู่แล้ว)
- **เซ็น commit ทุกอัน (signed commits)** — เลื่อนต่อ (ตามที่ ADR 0053
  บันทึก): พยานของ commit คือประวัติสาธารณะ + hash chain + required
  checks · คุณค่าเพิ่มของ signature ต่อ commit จะเกิดเมื่อมีผู้เขียนหลายคน
  — เงื่อนไขทบทวนเดียวกับ required review
- **เซ็น image ด้วย** — ยังไม่ทำ: image ไม่ถูก publish ไป registry ไหน
  (คน build เองจาก Dockerfile ที่ digest-pinned) — ทบทวนเมื่อเริ่ม push
  image ขึ้น registry จริง

## ผลที่ตามมา

- ผู้ใช้ verify ได้สองชั้น: `cosign verify-blob --bundle ...` (ลายเซ็น +
  identity) และ `gh attestation verify ...` (provenance) — คำสั่งเต็มใน
  `SECURITY.md`
- รอบแรกที่พิสูจน์ของจริงคือ v1.5.0 — ถ้า workflow ล้ม รันซ้ำได้ด้วย
  `workflow_dispatch` โดยไม่ต้องออก release ใหม่
- ด่าน bestpractices กลุ่ม `signed_releases` เปลี่ยนคำตอบได้หลังรุ่นแรก
  ที่เซ็นออกจริง

---

**โน้ต (2026-08-16 ค่ำ)**: gate `release-signed-and-attested` ยกขึ้น
`baseline` แล้ว (แบตช์รอบสามใต้หลักของ ADR 0057) — เงื่อนไข "พิสูจน์ด้วย
run จริงก่อน" ที่ทำให้จดเป็น internal ตอนเกิด สำเร็จครบใน v1.5.0
