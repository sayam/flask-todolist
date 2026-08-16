# ขั้นตอนออก release — และงานที่ผูกกับรุ่นถัดไป

ขั้นตอนมาตรฐานเคยอยู่แค่ในบันทึกการทำงาน — เขียนเป็นเอกสารตั้งแต่รอบนี้
เพราะรุ่นถัดไปมี**งานที่สัญญาไว้ในเอกสารอื่นสี่ชิ้น**ผูกอยู่ ลืมชิ้นไหน
คำสัญญาในไฟล์นั้นกลายเป็นเท็จทันที · แถวทวงอยู่ในตาราง cadence ของ
`SECURITY-CADENCE.md` (เงื่อนไข "เมื่อจะออก release ถัดไป")

## ขั้นตอนมาตรฐาน (ใช้จริงมาแล้ว v1.1.0–v1.5.0 — รุ่นหลังคือรอบแรกของเส้นทางเซ็น)

1. รอบตรวจเอกสารก่อนออก — ทุก claim ปัจจุบันต้องตรงความจริง
2. `CHANGELOG.md`: ยก `[Unreleased]` เป็น `[X.Y.Z] — วันที่` + เติม
   `[Unreleased]` ว่างใหม่ + ลิงก์เทียบรุ่นท้ายไฟล์
3. ขยับ `__version__` ใน `app/__init__.py` (เทสต์ผูกกับ CHANGELOG สองที่)
4. PR → `gh pr merge N --rebase --delete-branch --auto` (**ทางเดียว — ADR
   0053 ไม่มี bypass** · auto-merge ให้ GitHub ตัดสินตอน 27 check ครบ)
5. tag แบบ annotated บน merge commit → push tag → job `n-1` ขยับ anchor เอง
6. `gh release create` พร้อม notes — **ไม่ต้องแนบ SBOM เอง**: `release.yml`
   (ADR 0058) generate + เซ็น + แนบให้ตอน publish · รอ workflow จบแล้ว
   ยืนยันจำนวน asset (SBOM 8 + bundle ลายเซ็น 8) และหน้า release ตอบ 200
7. อัปเดตช่อง About ของ repo — **สองช่อง ไม่ใช่ช่องเดียว**:
   - `description`: อัปเดตเลขรุ่น (เคยพลาดค้าง v1.1.0 มาสามรุ่นเพราะ
     ขั้นตอนนี้เขียนแค่ "อัปเดต About" โดยไม่บอกว่ามีอะไรบ้าง)
   - `Website` (homepage): ตั้งเป็น
     `https://github.com/sayam/flask-todolist/releases/latest` **ถาวรแล้ว**
     (2026-08-16) — มัน redirect ไปรุ่นล่าสุดเอง ห้ามเปลี่ยนกลับเป็น URL
     ของ tag ใดตายตัว ขั้นตอนนี้จึงเหลือแค่ตรวจว่าค่ายังถูก

## งานที่ผูกกับรุ่นถัดไป (ตั้งแต่ v1.5.0)

### 1. ระบุ CVE ที่แก้ลง release notes — **ทำแล้วใน v1.5.0 · เป็นกฎประจำทุกรุ่น**

v1.5.0 เป็นรุ่นแรกที่เข้าเงื่อนไขและ notes ระบุครบทั้งเจ็ด CVE ของ
cryptography · **กฎประจำจากนี้**: ทุกรุ่นที่ CHANGELOG มีหัวข้อ Security
ที่แก้ CVE ของ*ของที่ ship จริง* → notes ต้องมีหัวข้อ Security ระบุ ID ครบ
(ฝั่งเครื่องมือ CI เล่าเป็นหมายเหตุได้ แต่ไม่นับเป็น "ซอฟต์แวร์ที่โครงการ
ผลิต") · รุ่นที่ไม่มี CVE ใหม่ = ช่อง `release_notes_vulns` ของ
bestpractices คงชี้ v1.5.0 ต่อได้ ไม่ต้องแก้

### 2. เซ็น release + provenance — **สร้างแล้ว (ADR 0058)**

`release.yml` ทำงานเองตอน release ถูก publish: generate SBOM จากโค้ดของ
tag → เซ็น keyless → verify สองทิศ → แนบ provenance → อัปโหลด · ขั้นตอน
manual จึงเปลี่ยนเป็น **สร้าง release พร้อม notes เปล่า ๆ ไม่ต้องแนบ SBOM
เอง** (workflow แนบให้) · ล้มกลางทางรันซ้ำด้วย workflow_dispatch ใส่ tag
· signed commits เลื่อนต่อพร้อมเงื่อนไขใน ADR 0058

### 3. ปรับ bestpractices.dev (#14085) — ช่องที่ผูกกับรุ่น

- `release_notes_vulns`: เลิกตอบ "ยังไม่เคยมี" → ชี้ notes ของรุ่นใหม่ (ข้อ 1)
- `version_unique` / `version_tags`: เขียนแบบช่วง — แก้เลขปลายเป็น tag ใหม่
- `maintained`: เลขรุ่น + วันที่ล่าสุด
- `description`: เลขรุ่น (และเลข check ถ้าเปลี่ยน)
- ถ้าทำข้อ 2 แล้ว: ทบทวนเกณฑ์กลุ่ม `signed_releases` ด้วย
- verify จาก `https://www.bestpractices.dev/projects/14085.json` เสมอ
  (repo_url ต้องเป็นของเรา — เคยได้เลขโครงการผิดมาสามรอบ)

### 4. ขยับ badge เวอร์ชันใน `README.md`

badge ท้ายไฟล์เป็น static — แก้เลขในบรรทัด
`img.shields.io/badge/version-vX.Y.Z-blue` ให้ตรง tag ใหม่
(หรือเปลี่ยนเป็น `img.shields.io/github/v/release/...` ให้ขยับเองก็ได้
— ตัดสินตอนนั้น) · ช่อง About (ขั้นตอนมาตรฐานข้อ 7) ไปด้วยกัน

## หลังออกรุ่น

- แถว cadence ของงานชุดนี้: ขยับ "ครั้งล่าสุด" แล้วเปลี่ยนเงื่อนไขครบ
  กำหนดเป็นของรุ่นถัดไป (ข้อ 1/3/4 เป็นงานประจำทุกรุ่น · ข้อ 2 สร้างเสร็จ
  แล้ว — เหลือแค่ยืนยันว่า workflow เขียวทุกรุ่น)
- อัปเดต `docs/BEST-PRACTICES.md` ให้ตรงกับที่กรอกจริง
