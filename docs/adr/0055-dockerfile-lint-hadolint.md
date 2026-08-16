# 0055 — lint Dockerfile ด้วย hadolint (IaC ชิ้นแรกที่ถูกสแกน)

สถานะ: **accepted** (2026-08-16 — ช่องว่างข้อ 3 จากผล audit governance
5 มิติ: IaC ทั้งหมดของ repo ไม่ผ่าน scanner ตัวไหนเลย)

**บริบท:** โค้ด python ผ่าน SAST สองเครื่องยนต์ แต่ไฟล์ที่**นิยาม**สภาพแวดล้อม
ที่โค้ดนั้นรัน (Dockerfile · compose · nginx conf) ไม่ถูกตรวจอะไรเลยนอกจาก
การที่มันใช้งานได้ — misconfiguration ชั้นนี้เป็นชั้นที่ CIS Docker
Benchmark ครอบและเป็นของที่เครื่องตรวจได้ฟรี เริ่มจาก Dockerfile เพราะ
เป็นไฟล์เดียวที่นิยามของที่ ship จริง (compose/nginx มี job `stack`/`dast`
เดินของจริงใส่ทุก push อยู่แล้ว — ยังไม่มี linter แต่มีด่านพฤติกรรม)

## คำตัดสิน

1. **hadolint รันใน job `lint`** ผ่าน `hadolint/hadolint-action` (pin SHA
   ตามกติกา workflow pinning · Dependabot ecosystem `github-actions`
   ขยับให้) — อยู่ใน job `lint` เพราะเป็น static analysis ไม่ต้องมี
   container runtime
2. **เกณฑ์คือทุกระดับรวม info ต้องเขียว** — ของใหม่ทุกข้อต้องถูกแก้ หรือ
   ถูกยกเว้นใน `.hadolint.yaml` **พร้อมเหตุผลเป็นคอมเมนต์กำกับ** (หลัก
   เดียวกับ `pins/accepted-advisories.txt`) · ตอนตั้งด่านมีข้อยกเว้นเดียว:
   `DL3059` (RUN ติดกันใน stage สุดท้าย ซึ่งตั้งใจแยกเพราะแต่ละ RUN มี
   เอกสารเหตุผลของตัวเอง)
3. **พิสูจน์สองทิศก่อนเข้า CI** (บนเครื่อง — hadolint เป็น static binary
   ตรวจ checksum แล้ว): Dockerfile ปัจจุบัน + config = exit 0 · เติม
   `MAINTAINER` = exit 1

## ทางที่ไม่ได้เลือก

- **checkov/trivy config scan ครอบ compose+nginx ด้วย** — เลื่อน: สองไฟล์
  นั้นมีด่านพฤติกรรมจริงทุก push อยู่แล้ว (`stack` เดิน compose จริง ·
  `dast` ยิงผ่าน nginx TLS จริง) linter เพิ่มความครอบเชิงรูปแบบซึ่งคุ้ม
  ก็ต่อเมื่อไฟล์โตหรือมีคนแก้บ่อย — ทบทวนเมื่อ compose มี override
  เพิ่มอีกหรือมีเหตุ misconfig ที่ด่านพฤติกรรมจับไม่ได้
- **ดาวน์โหลด binary + pin checksum ใน `pins/`** — ปัดตก: action ทางการ
  pin SHA ได้ผลเท่ากันและ Dependabot เฝ้าให้ฟรี ส่วน `pins/` มีไว้สำหรับ
  ของที่ติดตั้งผ่าน package manager ซึ่งไม่มีตัวตรึงของตัวเอง

## ผลที่ตามมา

- gate ใหม่ `dockerfile-linted` (baseline · portable · `axis: supply-chain`
  — แกนขยับเป็น 17) ลงดัชนีใน `docs/SUPPLY-CHAIN.md` ชั้น 3
- ช่องว่าง IaC ที่เหลือ (compose · nginx) บันทึกไว้ข้างบนพร้อมเงื่อนไข
  ทบทวน · งานถัดไปของชุดนี้คือการเซ็น release (cosign/SLSA)
