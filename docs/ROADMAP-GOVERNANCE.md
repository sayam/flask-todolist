# แผน G — ธรรมนูญและ governance (หลัง v1.2.0)

> ที่มา: เจ้าของประกาศปรัชญาของโปรเจกต์ (2026-08-15) แล้วอนุมัติ
> [ADR 0051](adr/0051-project-constitution-and-intake.md) — แผนนี้คือการ
> ทำให้ปรัชญานั้นเป็นของที่เครื่องตรวจได้ ไล่จากชั้น 1 (security) ลงมา ·
> กติกาเดิมของ repo มีผลทั้งหมด: baseline ห้าม break · ทุกขั้น merge ได้
> เองโดย CI เขียว · เอกสารใหม่ทุกฉบับมีเทสต์กันเน่า
>
> ทำไมแผนนี้เป็นไฟล์ (ไม่ใช่แค่ ADR): วินัย story-file ที่รับมาจาก
> bmad-method — งานหลาย story ข้ามหลาย session ต้องมีที่ที่สถานะและบริบท
> ของแต่ละ story อยู่ครบโดยไม่ต้องเล่าใหม่

## สถานะ

| story | เรื่อง | สถานะ |
|---|---|---|
| G1 | ธรรมนูญ + intake เข้าเอกสาร + `pillar:` ครบทุก gate + เทสต์คุม | ✅ เสร็จ (PR แรกของแผน) |
| G2 | ISO/IEC 27001:2022 self-assessment ครบทุกข้อ | ✅ เสร็จ (`ISO27001.md`) |
| G3 | ดัชนีแกน supply chain (`docs/SUPPLY-CHAIN.md`) | ⬜ ถัดไป |
| G4 | โครง compliance รายประเทศ (`docs/COMPLIANCE.md`) | ⬜ |
| G5 | ชั้น 2: multi-worker แบบไม่ลดด่าน + คำตัดสิน caching | ⬜ หลัง G1–G4 |

## G1 — ธรรมนูญเข้าระบบ

- ADR 0051 → accepted พร้อมคำตัดสินของเจ้าของทั้งสามข้อ
- ธรรมนูญ (ลำดับสี่ชั้น) เข้า `ARCHITECTURE.md` §2 · intake เป็นกฎข้อ 10
  ใน `CONTRIBUTING.md` (สองภาษา) · กฎข้อ 8 บังคับ gate ใหม่ประกาศ `pillar:`
- `pillar:` ครบทุก gate ใน `gates.yaml` (`tests/test_gates.py` บังคับ —
  ค่าแรกประกาศ: security 52 · manageability 14 · devx 13 · performance 2)
- ภาพที่ pillar เผยทันที: ชั้น performance มีด่านอัตโนมัติน้อยสุด (2)
  เพราะ load test ยังเป็นงานรันมือ — เป็นข้อมูลตั้งต้นของ G5

## G2 — ISO/IEC 27001:2022 ✅ (เสร็จ 2026-08-16)

ผลจริง: `docs/ISO27001.md` — **ผ่าน 74 · ไม่เกี่ยวข้อง 37 · ยังไม่ผ่าน 5**
(116 ข้อ = clause ระดับสอง 23 + Annex A 93) · ช่องว่างจริงสามเรื่องเข้า
backlog ของไฟล์: วิธีประเมินความเสี่ยงเป็นเอกสาร (6.1/8.2) ·
**backup/restore ที่ซ้อมจริง** (A.5.30/A.8.13) · การทบทวนโดยอิสระ (A.5.35)
— สองเรื่องแรกเป็นผู้สมัคร G-story ถัดไปหลัง G3/G4 · gate:
`iso27001-worksheet-honest` · แผนเดิมของ story นี้:

- `docs/ISO27001.md` worksheet แบบเดียวกับ `ASVS.md`/`PDPA.md`:
  **clause 4–10 + Annex A ทั้ง 93 controls ประเมินครบทุกข้อ** —
  organizational controls ที่ไม่เข้ากับโปรเจกต์คนเดียวจดเป็น "ไม่เกี่ยวข้อง"
  พร้อมเหตุผล (การจดคือการประเมิน ไม่ใช่การข้าม)
- หลักฐานใน backtick ต้อง resolve จริงทุกชิ้น + เทสต์แบบ `test_asvs.py`
- มาตรฐานอ้างอิงต้องตรึงเวอร์ชัน (หลักเดียวกับ `asvs-5.0.0.json`) —
  27001 เป็นเอกสารเสียเงิน จึงตรึงด้วย**รายการหัวข้อ/รหัส control** ที่เรา
  พิมพ์เองพร้อม checksum ไม่ embed เนื้อความของมาตรฐาน (ลิขสิทธิ์)
- ความสัมพันธ์กับของเดิม: ASVS = ชั้นเทคนิคใต้ 27001 (A.8 ส่วนใหญ่ชี้กลับ
  หลักฐานเดิมได้) · ROPA/RUNBOOK-BREACH/SECURITY-CADENCE = หลักฐานฝั่ง
  operational อยู่แล้ว

## G3 — ดัชนีแกน supply chain

- `docs/SUPPLY-CHAIN.md`: แกนอิสระตามปรัชญา — รวม pins/ · SBOM ·
  plugin category (ADR 0025) · Scorecard · Dependabot ·
  accepted-advisories · gitleaks เข้าดัชนีเดียวที่ชี้ gate จริง
  (`pillar: security` ทุกตัวอยู่แล้ว — ดัชนีนี้ derive จาก gates.yaml
  ได้บางส่วน ห้ามเขียนเลขคู่ขนาน) + เทสต์กันเน่า

## G4 — โครง compliance รายประเทศ

- `docs/COMPLIANCE.md` เป็นดัชนี: ไทย = PDPA (มีแล้ว ไม่ย้ายไฟล์ —
  ลิงก์เดิมไม่ตาย) · ประเทศใหม่ = เพิ่มไฟล์ + แถวในดัชนีแบบ additive
- นิยามขั้นต่ำของ "ผ่านหนึ่งประเทศ": worksheet ที่หลักฐาน resolve + เทสต์คุม
  + ช่องว่างอยู่ใน backlog — แบบเดียวกับที่ PDPA ตั้งไว้

## G5 — ชั้น 2 (ทำหลังชั้น 1 ครบ)

- **multi-worker แบบไม่ลดด่าน**: ทางที่บันทึกไว้จากเฟส 16 — metrics
  aggregate ข้าม process (multiprocess mode) หรือคง scale ด้วย replica ·
  ตัดสินด้วย ADR ของตัวเอง ห้ามแตะเงื่อนไข "/metrics ต้องมี token" และ
  ความถูกต้องต่อ scrape (ADR 0031)
- **caching**: มี cache plugin เป็น seam แล้ว (`cache/noop` · `cache/redis`)
  — คำถามของ G5 คือ*ใช้กับอะไร* (ผลวัดเฟส 6 ชี้ว่าคอขวดคือ process ไม่ใช่
  query) · ถ้าการวัดไม่ชี้ว่า cache ช่วย = จดว่าไม่ทำพร้อมเหตุผล
- ทั้งสองเรื่องต้องมีการวัดก่อน/หลังตามวินัย `docs/PERFORMANCE.md`
  (วัดรอบเดียวไม่ใช่หลักฐาน)
