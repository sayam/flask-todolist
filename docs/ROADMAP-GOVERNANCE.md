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
| G3 | ดัชนีแกน supply chain (`docs/SUPPLY-CHAIN.md`) | ✅ เสร็จ |
| G4 | โครง compliance รายประเทศ (`docs/COMPLIANCE.md`) | ✅ เสร็จ |
| G5 | ชั้น 2: multi-worker แบบไม่ลดด่าน + คำตัดสิน caching | ✅ เสร็จ — **แผน G ปิดครบทั้งใบ 2026-08-16** |

## หลังปิดแผน G — งานที่มาจากรอบ audit (r1–r7)

แผน G ปิดแล้วตั้งแต่ 2026-08-16 · งาน governance หลังจากนั้น**ไม่ได้มาจากแผน
ล่วงหน้า แต่มาจากรอบ audit** ที่ถามคำถามใหม่ทุกครั้ง (วิธีอยู่ใน
[SECURITY-CADENCE.md](SECURITY-CADENCE.md) และบันทึกของแต่ละรอบเป็น artifact)

| รอบ | คำถามของรอบ | ผลที่ลงเป็นโค้ด/เอกสาร |
|---|---|---|
| r1–r3 | อะไรยังไม่มี · ของที่มีเน่าไหม · นิ่งแล้วเสื่อมทางไหน | ADR 0053–0057 (PR-only · trivy · hadolint · perf tripwire · ยกชั้น gate) |
| r4 | **ใครพิสูจน์ตัวพิสูจน์** | `gate checkers-proven-two-way` — ตัวตัดสินของ supply chain มีเทสต์ตรรกะ |
| r5 | **ตัวแอปเอง** ส่งมอบให้คนอื่นได้ไหม | `gate route-authz-enumerated` · CLI กู้ MFA |
| r6 | **ด่านเคยจับของจริงไหม** | ADR 0059 `proved_by` · ADR 0060 preflight · `gate changed-lines-fully-tested` |
| r7 | **เครื่องมือวัดเชื่อได้ไหม · พึ่งใครอยู่ · ยังคุ้มกับขนาดไหม** | `rerun_census.py` (เห็นของที่ถูก rerun) · ADR 0061 job `posture` · ทะเบียนผู้ให้บริการ (SUPPLY-CHAIN ชั้นที่ 6) · ADR 0062 `guards:` · ADR 0063 overlay ส่งออกเครื่องมือ |

**กติกาที่ทำให้รอบซ้ำมีค่า**: แต่ละรอบต้องถามคำถามที่รอบก่อนถามไม่ได้ — ไม่ใช่
เช็คซ้ำว่า "แก้แล้วยัง" · และข้อความว่าอะไร "ไม่มี" ต้อง grep ยืนยันก่อนเขียนเสมอ
(พลาดมาแล้วสองครั้ง — ดู `CLAUDE.md` หัวข้อกติกาการตรวจเอกสาร)

## G1 — ธรรมนูญเข้าระบบ

- ADR 0051 → accepted พร้อมคำตัดสินของเจ้าของทั้งสามข้อ
- ธรรมนูญ (ลำดับสี่ชั้น) เข้า `ARCHITECTURE.md` §2 · intake เป็นกฎข้อ 10
  ใน `CONTRIBUTING.md` (สองภาษา) · กฎข้อ 8 บังคับ gate ใหม่ประกาศ `pillar:`
- `pillar:` ครบทุก gate ใน `gates.yaml` (`tests/test_gates.py` บังคับ —
  ค่าแรกประกาศ: security 52 · manageability 14 · devx 13 · performance 2)
- ภาพที่ pillar เผยทันที (ณ ตอนเปิดแผน): ชั้น performance มีด่านอัตโนมัติ
  น้อยสุด (2) เพราะ load test ตอนนั้นยังเป็นงานรันมือ — เป็นข้อมูลตั้งต้นของ
  G5 · ปัจจุบัน 4 รวมด่านต่อ push ตัวแรกของ pillar (ADR 0056)

## G2 — ISO/IEC 27001:2022 ✅ (เสร็จ 2026-08-16)

ผลจริง: `docs/ISO27001.md` (116 ข้อ = clause ระดับสอง 23 + Annex A 93) ·
gate: `iso27001-worksheet-honest` · **backlog ปิดแล้ว 2026-08-16 ตามคำสั่ง
เจ้าของ**: วิธีประเมินความเสี่ยง (6.1/8.2) → `docs/RISK-ASSESSMENT.md`
(gate `risk-method-and-register-current`) · backup/restore (A.5.30/A.8.13)
→ `docs/RUNBOOK-BACKUP.md` + การซ้อมเป็นเทสต์ทุก push (gate
`backup-restore-drilled-every-push`) · A.5.35 ปิดเมื่อ badge OpenSSF ถึง
passing (2026-08-16) · **ผลรวมสุดท้าย: ผ่าน 79 · ไม่เกี่ยวข้อง 37 ·
ยังไม่ผ่าน 0** · แผนเดิมของ story นี้:

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

## G3 — ดัชนีแกน supply chain ✅ (เสร็จ 2026-08-16)

ผลจริง: `docs/SUPPLY-CHAIN.md` — ห้าชั้นของห่วงโซ่ (ของในแอป · เครื่องมือ
ของ CI · ของที่รันจริง · ใครขยับ pin · หลักฐาน posture) · สมาชิกแกนประกาศ
ที่ gate ด้วย field `axis: supply-chain` (14 ตัวตอนปิด G3 · ปัจจุบัน 19 — ข้าม pillar ได้:
`bare-clone-still-green` เป็น manageability แต่รับใช้แกนนี้) ·
`tests/test_supply_chain.py` บังคับดัชนี↔ธงสองทิศ · gate:
`supply-chain-axis-indexed`

## G4 — โครง compliance รายประเทศ ✅ (เสร็จ 2026-08-16)

ผลจริง: `docs/COMPLIANCE.md` — ดัชนีประเทศ (ไทย = PDPA ไม่ย้ายไฟล์) +
นิยามขั้นต่ำสี่ข้อของ "ประเมินแล้วหนึ่งประเทศ" + สิ่งที่ตั้งใจไม่ทำ
(ไม่ประเมินประเทศที่ไม่มีใคร deploy · ไม่ทำ abstraction ข้ามกฎหมาย —
เหตุผลเดียวกับ ADR 0040) · ผูกด้วย convention: gate ชั้น legal ใช้ id
`legal-*` — `tests/test_compliance_index.py` บังคับดัชนี↔gate สองทิศ +
worksheet มีจริง + legal ทุกตัวอยู่ pillar security · gate:
`country-compliance-indexed`

## G5 — ชั้น 2 ✅ (เสร็จ 2026-08-16 — ปิดแผน G)

ผลจริง (ADR 0052 — เจ้าของอนุมัติทั้งสามข้อ):

- **multi-worker opt-in เสร็จ**: `WEB_CONCURRENCY>1` + `METRICS_MULTIPROC_DIR`
  → `/metrics` รวมทุก worker ถูกต้อง (กลไก stdlib ตาม idiom ของ
  `app/metrics.py` — ไม่เพิ่ม dependency · หมายเหตุกลไกใน ADR) · ครึ่ง ๆ =
  ไม่ start · gate `metrics-correct-across-workers` (ด่านที่สามของ pillar
  performance)
- **วัดสี่ config บน VM** (2026-08-16 · ผลเต็มใน `PERFORMANCE.md` หัวข้อ G5):
  ที่เป้า exit 0 ทั้ง 16 รอบ · workers=2 ชนะชัดที่โหลดสูง (p95@25 ลดครึ่ง ·
  rps@50 +129%) · **ผลไม่คาด: บน host เดียว 2 replica แย่กว่า 1** (แชร์
  vCPU + hop proxy + audit serialize ข้าม process) — replica = availability
  ไม่ใช่ throughput บนเครื่องเดียว
- **คำตัดสิน caching: ไม่ทำ cache ของข้อมูลแอป** — หลักฐานชี้ว่าคอขวดคือ
  จำนวน process ไม่ใช่ query · เงื่อนไขทบทวนจดใน `PERFORMANCE.md`
  (การจดว่าไม่ทำคือ deliverable ตามหลัก measure-first ของ ADR 0052)

แผนเดิมของ story นี้:

- **multi-worker แบบไม่ลดด่าน**: ทางที่บันทึกไว้จากเฟส 16 — metrics
  aggregate ข้าม process (multiprocess mode) หรือคง scale ด้วย replica ·
  ตัดสินด้วย ADR ของตัวเอง ห้ามแตะเงื่อนไข "/metrics ต้องมี token" และ
  ความถูกต้องต่อ scrape (ADR 0031)
- **caching**: มี cache plugin เป็น seam แล้ว (`cache/noop` · `cache/redis`)
  — คำถามของ G5 คือ*ใช้กับอะไร* (ผลวัดเฟส 6 ชี้ว่าคอขวดคือ process ไม่ใช่
  query) · ถ้าการวัดไม่ชี้ว่า cache ช่วย = จดว่าไม่ทำพร้อมเหตุผล
- ทั้งสองเรื่องต้องมีการวัดก่อน/หลังตามวินัย `docs/PERFORMANCE.md`
  (วัดรอบเดียวไม่ใช่หลักฐาน)
