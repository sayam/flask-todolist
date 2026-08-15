# 0052 — ชั้น performance (G5): multi-worker แบบไม่ลดด่าน และคำตัดสิน caching

สถานะ: **accepted** (2026-08-16 — เจ้าของ "อนุมัติ ADR 0052 ทั้ง 3 ข้อ
เริ่ม G5 ได้เลย": ทาง multiproc opt-in · อนุญาตสตาร์ท VM เพื่อวัด · หลัก
"วัดก่อน — ไม่ชนะ = จดว่าไม่ทำ" ของ caching)

**บริบท:** pillar `performance` มีด่านอัตโนมัติน้อยสุด (2 จาก 81 — ตัวเลข
ที่ G1 เผย) และของค้างจากเฟส 16 มีสองเรื่องที่วัดไว้แล้วแต่ยังไม่ตัดสิน:

1. **multi-worker**: วัดจริงแล้ว workers=2 ลด tail latency ~ครึ่งที่ 25–50
   VUs และเพิ่ม throughput ~66% แต่**คง 1 worker** เพราะ `/metrics` เป็น
   per-process (ADR 0031) — หลาย worker ทำให้ตัวนับสลับตัวทุก scrape
   ตัวเลขที่ Prometheus เห็นกลายเป็นมั่ว · ทาง scale ปัจจุบัน = เพิ่ม replica
2. **caching**: มี seam อยู่แล้ว (plugin ชนิด `cache` — noop/redis ใช้กับ
   rate-limit counter) แต่ยังไม่เคยตัดสินว่า cache *ข้อมูลของแอป* อะไรบ้าง
   — และผลวัดเฟส 6 บอกว่า**คอขวดคือจำนวน process ไม่ใช่ query**

## คำตัดสินที่เสนอ

### 1. multi-worker เป็น opt-in ผ่านโหมด multiproc ของ `/metrics`

- **หมายเหตุกลไก (พบตอนลงมือ):** metrics ของ repo เขียนเองล้วนโดยตั้งใจ
  ไม่มี `prometheus_client` อยู่เลย (หัวไฟล์ `app/metrics.py` — "การห่อ
  ไลบรารีเพื่อ counter แพงกว่าการเขียนเอง") การ import ไลบรารีเพื่อเอา
  เครื่องจักร mmap จึงเพิ่มรายการ supply chain เพื่อแก้สิ่งที่ ~60 บรรทัด
  ใน idiom เดิมแก้ได้ — กลไกจริงที่ใช้: **worker แต่ละตัวเขียน snapshot
  (JSON · atomic rename) ลง `METRICS_MULTIPROC_DIR` แบบผ่อนตามเวลา และ
  ตัวที่รับ scrape รวมค่าสดของตัวเองกับไฟล์ของตัวอื่น** — counter สะสม
  จึง monotonic · ไฟล์ของ worker ที่ตายถูกนับต่อโดยตั้งใจ (งานที่เคยเกิด
  ไม่หายไปกับ process) · dir ต้องตายพร้อม container (tmpfs) —
  รูปเดียวกับ multiprocess mode ของ prometheus_client แต่ไม่มี dependency
- `/metrics` รวมค่าจากทุก worker ของ container นั้นได้ถูกต้อง — เงื่อนไข
  ที่ทำให้ ADR 0031 ห้ามหลาย worker หายไป **ด้วยการออกแบบ ไม่ใช่ด้วยการ
  ลดด่าน**
- **ค่าเริ่มต้นคง 1 worker** — deploy เดิมไม่มีอะไรเปลี่ยน · ทาง scale
  หลักยังเป็น replica (ADR 0048) · multi-worker เป็นทางเลือกของเครื่องเดี่ยว
  ที่ไม่อยากรัน compose scale
- **config ครึ่ง ๆ = ไม่ start** (หลัก fail-loud ของธรรมนูญ):
  `WEB_CONCURRENCY > 1` (ปุ่มเดียวที่รองรับ) โดยไม่มี multiproc dir → refuse พร้อมข้อความบอกทาง
  ไม่ใช่เงียบ ๆ แล้วให้ตัวเลขมั่ว
- ADR 0031 ถูกแก้เฉพาะข้อ "ค่าเป็นของ process เดียว" โดยชี้มา ADR นี้ —
  ด่าน token ของ `/metrics` และ label เป็น endpoint **ไม่แตะ**
- ด่านใหม่: เทสต์พิสูจน์ว่า (ก) โหมด multiproc รวมตัวเลขข้าม worker ถูกจริง
  (ข) config ครึ่ง ๆ ไม่ start (ค) โหมดเดิม 1 worker พฤติกรรมเดิมทุกประการ
  — และ job `scrape` ต้องเขียวทั้งสองโหมด

### 2. caching ของข้อมูลแอป: วัดก่อน — ไม่ชนะ = จดว่าไม่ทำ

- หลักจากบทเรียนเฟส 6: "การเพิ่ม index ตอนนี้คือการแก้สิ่งที่การวัดไม่ได้
  บอกว่าเสีย" ใช้กับ cache คำต่อคำ — จะไม่เพิ่ม cache layer เพราะ "ควรมี"
- ขั้นตอน: รัน battery เดิม (k6 · 4 รอบ · เกณฑ์ ADR 0031) บนสภาพ
  ปัจจุบัน → ระบุ endpoint ที่ p95 สูงสุดจาก `/metrics` → ถ้าคอขวดยังเป็น
  process ไม่ใช่ query (คาดว่าใช่) → **จดใน PERFORMANCE.md ว่าไม่ทำ cache
  ของข้อมูลแอป พร้อมเงื่อนไขทบทวน** (เมื่อ query time โผล่เป็นคอขวดจริง
  หรือข้อมูลโตเกิน N แถว) — การจดว่าไม่ทำคือ deliverable เท่า ๆ กับการทำ
- ถ้าการวัดชี้ว่า query ชนะจริง (surprise) → เลือกจุด cache แคบสุดที่
  แก้คอขวดนั้น ผ่าน seam ของ plugin `cache` เดิม + invalidation ที่พิสูจน์ได้

### 3. การวัด

- ใช้ VM เดิม (`incus`: ubuntu-docker-vm-6 · MySQL stack · วิธีเดียวกับ
  เฟส 16) — วัดสี่ config: {1 worker, 2 workers} × {1 replica, 2 replica}
  อย่างละ 4 รอบ ตัดสินแบบ "ไม่มีรอบไหนตกเกณฑ์" · ผลลง `docs/PERFORMANCE.md`
- **การสตาร์ท VM ต้องได้รับอนุญาตจากเจ้าของก่อน** (กติกาเครื่อง)

## ทางเลือกที่ปัดตก

- **statsd/สidecar aggregator** — เพิ่มชิ้นส่วน runtime ทั้งชุดเพื่อแก้
  ปัญหาที่ multiprocess mode ของไลบรารีที่มีอยู่แก้ได้ · ขัด manageability
- **เลิกให้ `/metrics` เสิร์ฟจากแอปแล้วให้ proxy รวม** — ย้ายปัญหาไปที่อื่น
  และทำให้ด่าน token ซับซ้อนขึ้น
- **ทำ cache ทันทีเพราะ "ยังไงก็ช่วย"** — ขัดวินัยการวัดของ repo ตรง ๆ

## เงื่อนไขหมดอายุ

- ถ้า upstream ของ prometheus_client เปลี่ยนกลไก multiproc จน semantics
  ของ histogram เปลี่ยน → ทบทวนข้อ 1
- เงื่อนไขทบทวนของข้อ 2 เขียนไว้กับผลวัดใน `docs/PERFORMANCE.md`

## คำถามเปิด — รอเจ้าของตัดสิน

1. อนุมัติทาง multiproc opt-in (ข้อ 1) พร้อมการแก้ ADR 0031 แบบชี้กลับ?
2. อนุญาตให้สตาร์ท VM `ubuntu-docker-vm-6` เพื่อรัน battery การวัด?
3. เห็นด้วยกับหลัก "วัดก่อน — ไม่ชนะ = จดว่าไม่ทำ" สำหรับ caching (ข้อ 2)?
