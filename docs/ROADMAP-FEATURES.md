# แผนเฟส 13–18 — Features ก่อน v1.1.0

> **✅ แผนนี้จบแล้วทั้งใบ และ v1.1.0 ออกจริงแล้ว 2026-08-15** (tag บน
> `fa8d8f0` · CI เขียวครบ 27 check · SBOM 8 ไฟล์แนบ release) — ที่เหลือ
> ของไฟล์นี้คือบันทึกของแผนและคำตัดสิน ไม่ใช่สถานะปัจจุบัน

> ที่มา: รายการ idea ~20 ข้อจากเจ้าของ (2026-08-14) + บทความ software
> development standards · เจ้าของกำหนดว่า **feature ชุดนี้ต้องเสร็จก่อนออก
> v1.1.0** · แผนนี้ใช้หลักเดียวกับ [ROADMAP-INFRA.md](ROADMAP-INFRA.md):
> **เทียบแต่ละ idea กับ strong idea ที่งานเดิมพิสูจน์แล้ว เอาตัวที่แข็งกว่า**
> — ไม่รับเพราะอยากได้ ไม่ตัดเพราะเสียดาย ทุกคำตัดสินชี้กลับไปที่ ADR/บทเรียน
> ที่จ่ายไปแล้ว

> กติกาเดิมของ repo มีผลทั้งหมด: coverage ratchet ขึ้นทางเดียว · เทสต์ใหม่ต้อง
> ผ่าน mutation test · ไฟล์เทสต์ใหม่ลงทะเบียนใน `gates.yaml` · core ห้ามรู้จัก
> ชื่อ plugin · ด่านใหม่พิสูจน์สองทิศ · การวัดรอบเดียวไม่ใช่หลักฐาน

---

## 1. คำตัดสินรายข้อ

### รับเต็ม

| ข้อ | คำตัดสิน | เหตุผล |
|---|---|---|
| **F. ความสัมพันธ์ todo ทั้งองค์กร** | **รับ — เฟสธง (เฟส 18)** | product feature จริงข้อเดียวในลิสต์ · ชนกับ ADR 0004 ตรง ๆ — การบอก "ผลกระทบ" ของงาน private คือการเปิดเผย*การมีอยู่*โดยไม่เปิดเผย*เนื้อหา* ต้องมี ADR privacy model ก่อนโค้ดบรรทัดแรก |
| 2. รันคู่ขนานข้ามเวอร์ชัน compatible | รับ (เฟส 16) | แปลงเป็นวิศวกรรมตรง ๆ: สัญญา N-1 + วินัย expand-contract migration + CI job รันโค้ดรุ่นก่อนกับ schema ใหม่ (รูปเดียวกับ job `dialects` ที่ยิงของจริง) |
| 4. ข้อมูล language/library version ใน admin | รับ (เฟส 14) | อ่านจาก runtime จริง ไม่เขียนมือ — บทเรียนรอบตรวจเอกสาร: เลขที่ไม่มีอะไรอ่านคู่คือเลขที่ผิดอยู่แล้ว |
| 7. แยก business skill ออกจาก baseline | รับ (เฟส 13) | ตรงกับผลการทดลองเฟส 12: สิ่งที่ scaffolding ให้แล้วอย่างอื่นให้ไม่ได้คือ**ข้อตกลงเฉพาะโปรเจกต์** — ควรมีชั้นของมันเอง |
| 10+16. data masking สำหรับ admin | รับ (เฟส 14) | กฎ mask **derive จาก DATA-CLASSIFICATION.md ที่มีอยู่แล้ว** (ชั้นสูง = mask โดยค่าเริ่มต้น, unmask = การกระทำที่ลง audit) |
| 18. lifecycle ของตัวเองใน admin | รับ (เฟส 14) | เวอร์ชัน · สถานะ migration (alembic current vs head) · สถานะ plugin — อ่านจากของจริงทั้งหมด |
| 19. หลาย auth profile + fallback | รับ (เฟส 17) | ต่อยอด "ผูกหลาย IdP" ที่ค้างใน backlog · **fallback ต้อง explicit เท่านั้น** — บทเรียน `PLUGIN_PICKS`: ตัวที่ไม่ถูกเลือกเลื่อนขึ้นมาแทนเงียบ ๆ คือการ*เปิด*โดยไม่มีใครสั่ง |

### รับแบบปรับรูป

| ข้อ | รูปที่รับ | สิ่งที่ตัดออกจากข้อนั้น |
|---|---|---|
| 1. benchmark plugin ใน admin | หน้า observability (อ่าน `/metrics` ของ process ตัวเอง + ป้ายกำกับ ADR 0031) — เฟส 14 | ตัวรัน benchmark จากหน้าเว็บ — Phase 6: ตัวเลขที่ตัดสินต้องมาจากฝั่ง client การยิงโหลดจากในแอปวัดผิดโดยนิยาม |
| 5. active SBOM + timeline | runtime SBOM จาก `importlib.metadata` เทียบ lock (จับ drift) + ระบุเจ้าของต่อ plugin (ADR 0025) · EOL ใช้ตาราง generate+ตรึงแบบ `asvs-5.0.0.json` — เฟส 14 | fetch ข้อมูลสดตอนรัน — หน้า/ด่านที่ต้องต่อเน็ตคือหน้า/ด่านที่พังเพราะเน็ต |
| 6. bytecode / multi-CPU / cache tiers | gunicorn workers (ของค้างเดิม — ปรับแล้ววัดใหม่) — เฟส 16 | fragment cache: **เลื่อนจนกว่าการวัดจะชี้** (Phase 6 วัดแล้ว คอขวดคือจำนวน process ไม่ใช่ query) · bytecode: Python คอมไพล์ `.pyc` อยู่แล้ว |
| 9. enforce policy แบบ SOA | มีเกือบครบ (`ASVS.md` = SOA · `GATES-ASVS.md` = หลักฐานเชื่อม) · เติม: การแยกชั้นที่บังคับด้วย partition + ใบ business ต้องประกาศ baseline เป็น prerequisite — เฟส 13 | เอกสาร SOA ใบใหม่แยกต่างหาก — ที่ที่สามคือที่ให้ drift |
| 11+17. encryption | **at rest**: `EncryptedType` ตามชั้นข้อมูล คีย์จาก secrets source (ADR 0030) · KMS-ready ตาม seam ใน backlog — เฟส 15 · **in transit**: มีแล้ว (TLS+PFS วัดจริง) | **in process** — ไม่มีกลไกจริงใน Python webapp เคลมไปคือคำขวัญ (ลง ADR ตัด) |
| 20. software development standards | ส่วนที่ขาดจริง: issue/PR template + `docs/DEVELOPMENT.md` map ข้อกำหนด → ตัวบังคับ — เฟส 13 | ที่เหลือมีครบแล้วและ*มีตัวบังคับ*แล้ว — บทความเองเตือนเรื่องมาตรฐานเกินพอดี (repo นี้ตอบด้วย 96% ratchet ไม่ใช่ 100%) |

### ตัด / เลื่อน (ลง ADR 0043)

| ข้อ | คำตัดสิน | เหตุผล |
|---|---|---|
| 3. A/B testing | ตัด | เป้าโหลด 5 concurrent (ADR 0031 — เลขมีที่มา) ไม่มีประชากรพอให้ A/B มีความหมาย — รายงานเฟส 12 เขียนเองว่า N เล็กไม่มีการปฏิบัติทางสถิติใดมีความหมาย · feature flag มีแล้ว (`DISABLED_PLUGINS`/`PLUGIN_PICKS`) |
| 12. CMMI / TOGAF / ITIL / COBIT / CISSP | ตัดเกือบหมด | กรอบ maturity ของ*องค์กร* — โปรเจกต์คนเดียว verify ไม่ได้ ขัดหลักแรงสุดของ repo: เคลมเฉพาะที่มีตัวบังคับ · **รับหนึ่งเดียว: ISO/IEC/IEEE 42010** — architecture description ที่ derive จาก ADR ที่มีอยู่ ตรวจได้จริง (เฟส 13) |
| 13. legal overlay ต่อประเทศ | รับครึ่ง (เฟส 13) | รับ*กลไก*ชั้น legal + **PDPA เป็น pilot** (มี ROPA · RUNBOOK-BREACH · export/close รออยู่แล้ว) · ประเทศที่สองรอผู้ใช้จริง |
| 8. แยก module admin? | ตัดสินแล้ว (ADR ในเฟส 14) | **ไม่แยกเป็น plugin แต่ยกเป็น package ที่ plugin เสียบ panel ได้** — admin ทำงานกับข้อมูลคนอื่น ต้องอยู่ใต้วินัย core เต็ม (audit · masking · RBAC) ถอดได้เมื่อไหร่คือช่องให้หลุดวินัย |
| in-process encryption (จาก 11/17) | ตัด | ไม่มีกลไกจริงระดับแอป Python (memory encryption เป็นเรื่อง hardware/enclave) |
| benchmark runner ใน admin (จาก 1) | ตัด | ดูตารางบน |
| fragment cache tiers (จาก 6) | เลื่อน — เงื่อนไขปลด: การวัดชี้ว่า endpoint ไหน p95 ตกเกณฑ์เพราะ render/query | ADR 0031: แก้เฉพาะสิ่งที่การวัดบอกว่าเสีย |

---

## 2. ภาพรวมเฟส

| เฟส | ชื่อ | รวมข้อ | ขนาด | ต้องทำก่อน |
|---|---|---|---|---|
| **13** | ชั้นของกฎ + governance | 7, 9, 12*, 13, 20 | กลาง | — |
| **14** | Admin ยกเครื่อง (masking ก่อนหน้าใหม่) | 1*, 4, 5, 8, 10, 16, 18 | ใหญ่ | 13 |
| **15** | Encryption at rest | 11, 17 | กลาง | 13 |
| **16** | Operations / HA / N-1 | 2, 6*, 14, 15 | กลาง-ใหญ่ | 15 |
| **17** | Auth หลาย profile + fallback ที่ประกาศ | 19 | กลาง | 13 |
| **18** | Org todo graph (เฟสธง) | F | ใหญ่สุด | 14, 15 |

**ขนานได้**: 14‖15 (ระวังจุดชนที่ migration) · 16‖17 · **18 ท้ายสุดโดยตั้งใจ**
— feature ที่แตะข้อมูลข้ามผู้ใช้ต้องเกิด*หลัง* masking กับ encryption พร้อม
· เฟส 16 ต้องตามหลัง 15 เพราะ schema ของ encryption ต้องลงก่อนประกาศสัญญา N-1

---

## Phase 13 — ชั้นของกฎ + governance

> **สถานะ: ปิดแล้ว (2026-08-14)** — ADR 0042/0043 · `layer:` ครบทุก gate ·
> `SKILL-TODOLIST.md` แยกใบ · `docs/PDPA.md` + `tests/test_pdpa.py`

**เป้า**: กฎทุกข้อรู้ว่าตัวเองอยู่ชั้นไหน (baseline / business / internal) ·
business skill แยกใบ · ชั้น legal เป็น overlay ที่ไม่ break พื้นฐาน ·
มาตรฐานการพัฒนาที่ยังขาดถูกเติมด้วยของที่ตรวจได้

| ขั้น | งาน | ไฟล์หลัก |
|---|---|---|
| 13-01 | ADR 0042: โมเดลสามชั้น (baseline skill → framework overlay → business skill) · คีย์ `layer:` · ทิศระหว่างชั้นบังคับที่ตัว render (partition ของสองใบ + ใบ business ประกาศ baseline เป็น prerequisite — `requires:` ใน gates.yaml เป็นของ environment อยู่แล้ว ไม่ยืมมาใช้) · ADR 0043: scope cuts ของแผนนี้ทั้งหมด | `docs/adr/0042-*`, `0043-*` |
| 13-02 | เติม `layer:` ให้ gate ทั้ง 71 + `tests/test_gates.py` บังคับ: ทุก gate มี layer · baseline ⇒ portable · internal ⇒ ไม่ portable | `gates.yaml`, `tests/test_gates.py` |
| 13-03 | `build_skill.py` render สองใบ: `SKILL.md` (baseline) + `SKILL-TODOLIST.md` (business) · `tests/test_skill.py` สองทิศ: portable gate ทุกตัวอยู่ในใบเดียวเป๊ะ · ban list ชื่อ framework ใช้ทั้งสองใบ · overlay ยังครอบ portable ทุกตัวเหมือนเดิม (todolist บน framework อื่นใช้ checker ชุดเดียวกัน) | `scripts/build_skill.py`, `SKILL.md`, `SKILL-TODOLIST.md` |
| 13-04 | PDPA overlay (pilot ของชั้น legal): `docs/PDPA.md` worksheet แบบเดียวกับ `ASVS.md` (สถานะต่อข้อ + หลักฐานใน backtick ที่เทสต์ตรวจว่ามีจริง) — ส่วนใหญ่ผ่านด้วยของที่มีแล้ว (export=ม.30/31 · close=ม.33 · ROPA=ม.39 · breach 72 ชม.=ม.37(4) · retention=DATA-CLASSIFICATION) | `docs/PDPA.md`, `tests/test_pdpa.py` |
| 13-05 | `docs/ARCHITECTURE.md` ตามโครง ISO/IEC/IEEE 42010 — view/viewpoint/stakeholder/concern โดย rationale ชี้ไป ADR จริง · เทสต์ตรวจ citation | `docs/ARCHITECTURE.md`, เทสต์ |
| 13-06 | `docs/DEVELOPMENT.md` (map มาตรฐาน → ตัวบังคับจริง + จุดที่จงใจไม่ทำตามและทำไม) · issue/PR templates | `docs/DEVELOPMENT.md`, `.github/` |

**DoD**: gate ทุกตัวมี layer และเทสต์บังคับทิศ · `SKILL.md`+`SKILL-TODOLIST.md`
generate สดตรงกับดัชนี · PDPA worksheet หลักฐานจริงทุก backtick ·
เอกสารใหม่ทุกใบมีเทสต์กันเน่า (หลัก Phase 7: เอกสารที่ไม่มีเทสต์คุม = เน่า)

## Phase 14 — Admin ยกเครื่อง

> **สถานะ: ปิดแล้ว (2026-08-14)** — ADR 0044/0045 · `app/admin/` package +
> panel registry · masking ตามชั้นข้อมูล · หน้า environment/SBOM/lifecycle/
> observability · `/privacy` + ระงับบัญชี (PDPA ม.23/ม.34)

**หลักที่ล็อกไว้ก่อนเริ่ม**: masking มาก่อนหน้าใหม่ทุกหน้า — ห้ามมีหน้า admin
ใหม่ที่แสดงข้อมูลผู้ใช้โดยไม่ผ่านชั้น mask

| ขั้น | งาน |
|---|---|
| 14-01 | ADR 0044: โครง admin — core package ที่ plugin ลงทะเบียน panel ได้ (หลัก capability เดิม) ไม่แยกเป็น plugin · ADR 0045: data masking ตามชั้นข้อมูล — ชั้นไหน mask อะไร unmask ต้องทำอะไร |
| 14-02 | ชั้น masking: derive จาก `DATA-CLASSIFICATION.md` · unmask = การกระทำที่ลง audit (`admin.unmask`) · เทสต์บังคับว่าทุกคอลัมน์ที่จัดชั้นแล้วมีคำตัดสิน mask/แสดง (partition แบบเดียวกับ export) |
| 14-03 | restructure `app/admin.py` → package + registry ของ panel |
| 14-04 | หน้า environment: Python/ไลบรารีจาก runtime จริง (`sys.version`, `importlib.metadata`) |
| 14-05 | หน้า active SBOM: installed เทียบ `Pipfile.lock` (จับ drift) + package ไหนเป็นของ plugin ไหน + สถานะ advisory จากไฟล์ audit ที่ CI สร้าง · ตาราง EOL generate+ตรึง + สคริปต์ refresh |
| 14-06 | หน้า lifecycle: `__version__` · alembic current vs head · plugin ติดตั้ง/เปิด/ปิด · หน้า observability: histogram จาก `/metrics` ของ process ตัวเอง + ป้าย "process นี้คนเดียว" |

## Phase 15 — Encryption at rest

> **สถานะ: ปิดแล้ว (2026-08-15)** — ADR 0046 · ที่ต่างจากแผน (บันทึกใน ADR):
> ตัวคอลัมน์ `EncryptedSecret` อยู่ใน `models.py` ของ plugin ไม่ใช่
> `app/db_types.py` (คอลัมน์แรกที่ encrypt เป็นของ plugin — core ไม่ควรแบก
> type ที่ยังไม่มีคอลัมน์ core ใช้) · การย้ายข้อมูลเดิมเป็น encrypt-on-use
> ไม่ใช่ migration (ตารางของ plugin อยู่นอกสาย alembic — ADR 0023) ·
> ได้กลไกแถม: `plugins.requirements_met()` — plugin ที่ไลบรารีขาดปิดตัวเอง

| ขั้น | งาน |
|---|---|
| 15-01 | ADR 0046: field-level encryption — เลือกคอลัมน์จากชั้นข้อมูล (เริ่ม: ความลับ TOTP ของ plugin) · คีย์จาก secrets source · key rotation story · **ADR ต้องผ่านตาเจ้าของก่อนลงมือ** |
| 15-02 | `EncryptedType` ใน `app/db_types.py` + migration ของข้อมูลเดิม (วินัยเดิม: สำรองก่อน · ตรวจไป-กลับ · ระวัง batch_alter บน SQLite) |
| 15-03 | เทสต์สองทิศ: ค่าใน DB ต้องอ่านไม่ออกด้วย SQL ตรง ๆ · decrypt ได้ถูก · คีย์หาย = ปฏิเสธชัดเจน ไม่ใช่ข้อมูลขยะเงียบ ๆ · จำแนกใน DATA-CLASSIFICATION |

## Phase 16 — Operations / HA / N-1

> **สถานะ: ปิดแล้ว (2026-08-15)** — ADR ตัวจริงคือ **0048** (แผนเดิมเขียน 0047
> ก่อนลำดับ accept จริงจะลงตัว) · job `n-1` พิสูจน์โค้ด tag ล่าสุดบน schema
> ของ HEAD ทุก push (สองทิศ) · `/healthz`+`/readyz` ไม่มี token/ไม่มีข้อมูล
> ภายใน/ไม่ spam log · Prometheus+Grafana ดูด `/metrics` จริงผ่านด่าน token
> (job `scrape` — token ผิดต้อง `up=0` วัดแล้ว) · วัด `--workers` แล้ว:
> **คง 1 worker** (เหตุผลเรื่อง `/metrics` per-process — ตัวเลขใน
> PERFORMANCE.md) · วัด rolling ซ้ำ: ยังหลุดฝั่ง proxy — graceful shutdown
> ไม่ใช่ตัวแก้ จดเป็นงานค้าง (dynamic upstream ของ nginx)

| ขั้น | งาน |
|---|---|
| 16-01 | ADR 0047: นิยาม compatible range (N-1) + วินัย expand-contract migration |
| 16-02 | readiness/liveness endpoint (แยกจาก `/metrics` — ไม่ต้องมี token แต่ไม่มีข้อมูลภายใน) + graceful shutdown · วัด rolling ซ้ำด้วย bench เดิมของเฟส 10 |
| 16-03 | CI job `n-1`: checkout รุ่นก่อน รันชุดเทสต์ของมันกับ schema ที่ migrate เป็นรุ่นใหม่แล้ว |
| 16-04 | Prometheus + Grafana scrape `/metrics` จริง (ปิดของค้าง "ยังไม่มีใคร scrape") — compose overlay + ci พิสูจน์ว่า scrape ได้จริง |
| 16-05 | ปรับ `--workers` ของ gunicorn แล้ว**วัดใหม่ทั้งชุด** เทียบกับตัวเลขใน PERFORMANCE.md (ห้ามเดาว่าดีขึ้น) |

## Phase 17 — Auth หลาย profile

> **สถานะ: ปิดแล้ว (2026-08-15)** — ADR ตัวจริงคือ **0047** (แผนเดิมตั้งเลข 0048
> ไว้ก่อน 0046 ถูก accept — เลขจริงตามลำดับ accept) · profile = instance ของ
> config คีย์มี prefix ไม่ตกกลับคีย์เปล่า · ปฏิเสธ = สิ้นสุด, fallback เฉพาะ
> "ติดต่อไม่ได้" (`UnreachableError`) · ปิดทีละ profile ผ่าน `DISABLED_PLUGINS`
> · ผูกหลาย directory เข้าผู้ใช้เดียวได้ (ปิดของค้าง "หลาย IdP") · job `ldap`
> ใน CI เดินสอง profile จริง (ตัวแรกต่อไม่ติด ต้อง fallback แล้ว login สำเร็จ)

| ขั้น | งาน |
|---|---|
| 17-01 | ADR 0048: named profiles — plugin เดียว หลาย config instance (`ldap:corp`, `ldap:partner`) · ลำดับลองต้อง**ประกาศ** · ไม่มี fallback เงียบ · ปิด profile เดียวได้โดยไม่กระทบตัวอื่น |
| 17-02 | registry รองรับ instance + เทสต์ (รวมเคส: profile แรกตาย → พฤติกรรมตามที่ประกาศเท่านั้น) |
| 17-03 | ผูกหลาย identity เข้าผู้ใช้เดียว (ปิดของค้าง "ผูกหลาย IdP") |

## Phase 18 — Org todo graph (เฟสธง)

> **สถานะ: ปิดแล้ว (2026-08-15)** — ADR 0049 accepted (เจ้าของอนุมัติตามร่าง +
> ตัดสินคำถามเปิดสามข้อ: ไม่มีแชร์ปิดชื่อในเฟสแรก · วง admin-only · ป้าย
> impact บนหน้า list หลัก) · สี่ตาราง core ใหม่เดินครบวงจร (จำแนกชั้น ·
> masking · audit · ROPA · export · close_account · purge) · แชร์เผยสี่ฟิลด์
> ผ่าน `SharedTodoView` เท่านั้น · dependency เชิญ→ยอมรับ + จุดตัดเดียว
> `sever_invisible_dependencies()` · impact deterministic กันวงวน ·
> `/api/v1` ได้ฟิลด์ `is_at_risk` (additive) · เทสต์ privacy สองทิศ 33 ตัว
> (mutation 5 จุด) + หน้า /teams เข้า pa11y

| ขั้น | งาน |
|---|---|
| 18-01 | **ADR 0049: privacy model — ต้องผ่านตาเจ้าของก่อนโค้ดทุกบรรทัด**: อะไรของงาน private ที่คนอื่นเห็นได้ (การมีอยู่? กำหนดส่ง? เจ้าของ?) · dependency ข้ามคนสร้างอย่างไร (เชิญ/ยอมรับ — ห้าม unilateral เพราะเท่ากับ probe การมีอยู่ของงานคนอื่น ขัด ADR 0004) · impact ประเมินจากอะไร |
| 18-02 | data model: org/team + dependency (ตาราง core ใหม่ → ครบวงจรเดิม: จำแนกชั้น · ตัดสิน export · audit · migration) |
| 18-03 | service layer + กติกา impact (เริ่มจาก deterministic: ห่วงโซ่กำหนดส่ง — งานที่เราพึ่งเลยกำหนด = ความเสี่ยงของเรา) |
| 18-04 | UI + `/api/v1` (additive เท่านั้น — ถ้าจำเป็นต้องเปลี่ยนความหมายของเดิม = สัญญาณ v2 ต้องกลับมาคุย) |
| 18-05 | เทสต์ privacy สองทิศ: สิ่งที่ประกาศว่าเห็นได้ต้องเห็น · สิ่งที่ประกาศว่าไม่ได้ต้อง**พิสูจน์ว่าไม่รั่ว**ผ่านทุกช่องทาง (หน้าเว็บ · API · impact signal) |

---

## 3. ADR ที่ต้องเขียน

| ADR | เรื่อง | เฟส |
|---|---|---|
| 0042 | โมเดลสามชั้นของกฎ + `layer:` + ทิศของ requires | 13-01 |
| 0043 | scope cuts ของแผนนี้ (A/B · maturity frameworks · in-process encryption · benchmark runner · fragment cache พร้อมเงื่อนไขปลด) | 13-01 |
| 0044 | โครง admin: core package + pluggable panels | 14-01 |
| 0045 | data masking ตามชั้นข้อมูล | 14-01 |
| 0046 | field-level encryption at rest | 15-01 |
| 0047 | สัญญา N-1 + expand-contract | 16-01 |
| 0048 | named auth profiles + ลำดับที่ประกาศ | 17-01 |
| 0049 | privacy model ของ org todo graph | 18-01 |

## 4. Release

ครบทุกเฟส → **v1.1.0** ตามที่เจ้าของกำหนด — **ออกจริงแล้ว 2026-08-15** ·
ทุกอย่าง additive ต่อ `/api/v1` จริงตามแผน (ฟิลด์ใหม่ตัวเดียว: `is_at_risk`)
จึงเป็น 1.x ตาม ADR 0018 — จุดเฝ้าเดียว: ถ้าเฟส 18 เปลี่ยน
*ความหมาย*ของ todo เดิม (ไม่ใช่แค่เพิ่ม) เข้าเงื่อนไข v2 ซึ่งตัดสินตอน ADR 0049
· `CHANGELOG` มีหัวข้อ Unreleased รออยู่แล้ว เฟสใหม่เติมเข้าไฟล์เดิม
