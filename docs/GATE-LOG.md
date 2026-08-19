# fail-fix harness — กลไก ขอบเขต และบันทึกการพิสูจน์

`scripts/run_gates.py` คือกลไกที่เปลี่ยน checklist เป็น enforcement loop
(เฟส 11 ของ [ROADMAP-INFRA.md](ROADMAP-INFRA.md)): agent แก้โค้ด → รัน harness
→ ได้ `(gate id, สาเหตุ, hint)` เป็น JSON → แก้ → วนจนผ่าน

## ขอบเขต — ประกาศตรง ๆ

- **รันเฉพาะ gate ชนิด `test`** (pytest — สิ่งที่ loop การแก้โค้ดชนบ่อยที่สุด)
- ชนิด `job`/`step` **ข้ามพร้อมเหตุผล** ไม่ใช่เงียบ — คำสั่งของมันอยู่ใน
  workflow และการลอกมารันคือการสร้างที่ที่สอง (ADR 0039) · ด่านพวกนั้นตัดสิน
  ใน CI ซึ่งบังคับทุก PR อยู่แล้ว
- round log (`.gate-rounds.jsonl` — gitignore) นับรอบต่อ tree และจดว่า gate
  ไหนแดง เพื่อหาตัวที่แดงบ่อย · `--output` ให้รายงานเต็มเป็น JSON

## วิธีใช้กับ branch ที่กำลังแก้

```sh
pipenv run python scripts/run_gates.py                     # ทุก gate
pipenv run python scripts/run_gates.py --only <gate-id>    # เจาะตัวเดียว
pipenv run python scripts/run_gates.py --root <worktree>   # ตรวจ tree อื่น
```

`tests/test_harness.py` คุมกลไก: สามสถานะรายงานตรงความจริง · สาเหตุพาไปถึง
assertion ที่พัง · hint มาจาก `born_from` · เลขรอบนับต่อ · gate ที่ไม่รู้จัก
เป็น usage error ไม่ใช่ผ่านเงียบ ๆ

## harness ตัวที่สอง — `scripts/preflight.py` (ADR 0060)

คนละคำถามกับ `run_gates.py` จึงเป็นคนละเครื่องมือ:

| | `run_gates.py` | `preflight.py` |
|---|---|---|
| ตอบคำถาม | gate ตัวไหนแดง และเพราะอะไร | PR นี้จะผ่าน CI ไหม |
| ครอบ | gate ชนิด `test` (pytest) | step ของ job ที่ `scaffold.json` ประกาศไว้ (`preflight_jobs` — ที่นี่คือ `lint` + `test`) **ตามที่ workflow เขียนไว้** |
| แหล่งคำสั่ง | `gates.yaml` | workflow **ทุกไฟล์** ใต้ `.github/workflows/` (อ่านสด ไม่ลอกมาเก็บ) |

```sh
pipenv run python scripts/preflight.py              # job ที่ scaffold.json ประกาศ
pipenv run python scripts/preflight.py --only lint  # เฉพาะที่เร็ว (~1 นาที)
```

**ไฟล์นี้ถูกส่งออกไปกับ overlay ด้วย** (ADR 0063) — `overlays/flask/preflight.py`
ต้องตรงกับ `scripts/preflight.py` **ไบต์ต่อไบต์** และเทสต์ติดตั้งลง repo เปล่า
แล้วรันจริงทุกครั้ง · ชื่อ job จึงมาจาก config ไม่ใช่ฝังในโค้ด

เหมือนกันข้อสำคัญคือ **ข้ามอะไรต้องบอกเหตุผล** — preflight ข้าม step ที่เป็น
action (ตัวตัดสินคือรุ่นใน CI) · step ที่จัดสภาพแวดล้อม (`pipenv sync` แก้
`.venv` ของคนที่กดรัน) · และ step ที่ **expression ของ CI แทนค่าไม่ได้** ทั้งใน
คำสั่งและใน `env:` · job ที่ต้องมี docker/service ไม่อยู่ในขอบเขตเลยและ
ประกาศไว้ตรง ๆ ว่า "preflight เขียว ≠ CI เขียว"

**`env:` ของ step เป็นส่วนหนึ่งของคำสั่ง ไม่ใช่ของประกอบ** (audit รอบ 17) —
ตอนที่ยังทิ้งไป step ที่วัด coverage ของ `scripts/` เขียนทับ `.coverage` ของแอป
บนเครื่อง ทั้งที่ CI ตั้ง `COVERAGE_FILE` ไว้นอก workspace เพื่อกันเรื่องนี้
โดยเฉพาะ · preflight ที่รันคำสั่งเดียวกันใน*สภาพแวดล้อมคนละชุด* คือ preflight
ที่ตอบคำถามอื่นกับที่ CI ถาม · `${{ github.base_ref }}` กับ `${{ runner.temp }}`
มีของเทียบเท่าบนเครื่องจึงถูกแทนค่าให้ ส่วนที่เหลือ (เช่น `secrets.*`) = ข้าม

**รอบแรกที่รันจริงจับของได้ทันที**: ruff แดงสองข้อในไฟล์ของ preflight เอง
(บรรทัดยาวเกิน + assert ที่ควรแยก) ซึ่งเป็นคลาสที่ hook ก่อน commit จับได้อยู่
แล้ว — ส่วนคลาสที่มันถูกสร้างมาดัก (xenon · interrogate · diff-cover) พิสูจน์
ด้วย mutation สี่ทิศใน `tests/test_preflight.py` แทน

## coverage ของโค้ดที่บังคับกฎ — วัดยังไงถึงไม่โกหก (audit รอบ 17)

**83 จาก 106 gate ตัดสินด้วยโค้ดใน `scripts/`** ซึ่งอยู่นอก `source` ของ coverage
มาตลอด · ตอนนี้ job `test` วัดมันแยกไฟล์ข้อมูล แล้วพื้นเป็น ratchet
(`scripts_coverage` ใน `pyproject.toml` — `scripts/check_ratchets.py` บังคับ)

สองอย่างที่ทำให้ตัวเลขนี้เชื่อได้ และเป็นสองอย่างที่รอบ 17 ต้องแก้ก่อน:

- **`COVERAGE_PROCESS_START` ต้องถูกตั้ง** (ชี้ `.coveragerc-scripts`) ไม่งั้น
  coverage ไม่ตามเข้าไปในลูกที่เป็น subprocess — ซึ่งคือรูปที่ repo นี้บังคับเอง
  ว่าดีกว่า (`test_harness` · `test_preflight` · `test_measure_generated` ยิงผ่าน
  subprocess ทั้งหมด) · ก่อนแก้ `measure_generated.py` รายงาน **0%** ทั้งที่มีเทสต์
  11 ตัว และตัวเลขรวมคือ 43.8% แทนที่จะเป็น 60.28% —
  *เกณฑ์ที่ลงโทษวิธีทดสอบที่ดีกว่า คือเกณฑ์ที่จะถูกเลี่ยงด้วยการเขียนให้แย่ลง*
- **รายการไฟล์ที่วัด derive มา ไม่ใช่พิมพ์มือ** — workflow คัดด้วย `grep` ส่วน
  `tests/test_checker_logic.py` คัดด้วย **AST** แล้วเทียบกัน · สองวิธีที่พังคนละแบบ
  ตรวจทะเบียนใบเดียวกัน (รายการที่ไม่มีการตรวจสมาชิก ครบเฉพาะวันที่มีคนนึกได้)

ชนิดของหลักฐานต่างกันตามชนิดของสคริปต์ (`บทบาท:` ในหัวไฟล์ — `tests/test_script_roles.py`):
`decider` ต้องมีเทสต์ planted violation + clean input · `generator` ต้องถูกตรวจที่
**ผลลัพธ์** · `reader` ต้องพิสูจน์ว่าตัวเลขที่พิมพ์ตรงกับแหล่งและไม่ตัดของทิ้งเงียบ

## บันทึกการพิสูจน์ 11-03 — ฝังช่องโหว่จริงใน worktree (2026-08-14)

ตามเงื่อนไขสำเร็จของ INFRA-VISION ข้อ 3.4 — ทำใน `git worktree` แยก
(ไม่มีไฟล์ช่องโหว่ปลอมอยู่ใน repo ให้ scanner ตัวอื่นสะดุด ซึ่งแข็งกว่า
ทางเลือก template ที่แผนเสนอไว้):

| รอบ | การกระทำ | ผล |
|---|---|---|
| 1–2 | ฝัง `from flask import request` กลาง docstring ของ `app/services/lookup.py` | **ผ่านทั้งที่ตั้งใจให้แดง** — plant อยู่ในสตริง ไม่ใช่โค้ด (AST ไม่เห็น) · บทเรียนเดิมของ repo ทำงานอีกครั้ง: ตรวจว่า mutation โดนของจริงก่อนสรุปว่าด่านบอด |
| 3 | ฝังใหม่ที่ module level (ยืนยันด้วย `ast.parse` ว่าเป็นโค้ดจริง) | **แดง** — `logic-knows-no-http` ชี้ `lookup.py:26` พร้อม hint จาก `born_from` · exit 1 |
| 4 | ถอนช่องโหว่ (`git checkout`) | **ผ่าน** — exit 0 · round log นับ 1→4 ต่อเนื่อง |

loop ครบวงใน 2 รอบที่นับจริง (แดง → แก้ → ผ่าน) · ความผิดพลาดของรอบ 1–2
เป็นของ*ผู้ฝัง* ไม่ใช่ของ harness — และมันคือเหตุผลที่การพิสูจน์ต้องยืนยันว่า
plant ถูกฝังจริง ไม่ใช่แค่รันแล้วดูสี
