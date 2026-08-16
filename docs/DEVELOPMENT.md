# Development Standards — มาตรฐานการพัฒนา และ*ตัวบังคับ*ของแต่ละข้อ

เฟส 13-06 ([ROADMAP-FEATURES.md](ROADMAP-FEATURES.md)) — map มาตรฐานการพัฒนา
ซอฟต์แวร์ที่ยอมรับกันทั่วไป เข้ากับ**กลไกที่บังคับมันจริงใน repo นี้** ·
หลักของไฟล์: **มาตรฐานที่ไม่มีตัวบังคับคือคำขวัญ** — ทุกแถวข้างล่างจึงต้อง
ชี้ตัวบังคับได้ และแถวที่*จงใจไม่ทำตาม*ต้องบอกเหตุผล ไม่ใช่เงียบ

## มาตรฐาน → ตัวบังคับ

| หมวดมาตรฐาน | ที่ repo นี้ทำ | ตัวบังคับ |
|---|---|---|
| Code formatting & style | ruff เปิดทุกกฎ ข้อยกเว้นมีเหตุผลรายข้อ + ruff format | pre-commit + `ci:lint` (บล็อก merge) |
| Type safety | mypy strict บนรายชื่อ module ที่**ขยายได้อย่างเดียว** | `pyproject.toml` + `ci:lint` |
| Testing & coverage | เทสต์ใหม่ต้องผ่าน mutation test ก่อนถือว่าเสร็จ · coverage 96% แบบ ratchet · fuzz จาก OpenAPI spec | `CONTRIBUTING.md` กฎข้อ 1 · `ci:test` + diff-cover · `tests/test_api_fuzz.py` |
| Secure coding (OWASP) | ประเมิน ASVS 5.0 L2 ครบทุกข้อ · SAST สองตัว · DAST แบบ login แล้ว | `docs/ASVS.md` · `ci:security` · `ci:dast` · `ci:codeql` |
| Security management & compliance | ISO/IEC 27001:2022 ครบ 116 ข้อ · แกน supply chain · ดัชนี legal รายประเทศ (ธรรมนูญ ADR 0051) | `docs/ISO27001.md` · `docs/SUPPLY-CHAIN.md` · `docs/COMPLIANCE.md` · `tests/test_iso27001.py` |
| Bug tracking / issue management | GitHub Issues + template ที่บังคับข้อมูลจำเป็น (repro, expected, actual) | `.github/ISSUE_TEMPLATE/` · PR template ถามว่า "ถ้าไม่แก้จะพังอย่างไร" |
| Documentation | เอกสาร derive ได้ = generate · เอกสารคำตัดสิน = ตรวจอ้างอิงสองทิศ · เลขที่โฆษณามีเทสต์อ่านคู่ | `tests/test_skill.py` · `tests/test_asvs.py` · `tests/test_contributor_docs.py` |
| Version control | Conventional Commits (หัว ≤72) · merge ด้วย rebase ผ่าน auto-merge (`--auto`) · linear history | commit-msg hook + `ci:commit-lint` + branch protection |
| CI/CD | 27 job (29 check) ยิงของจริงทุก push — สามยี่ห้อฐานข้อมูล, stack จริง, IdP จริง | `.github/workflows/ci.yml` · required checks |
| Small batches | ทุกเฟสแตกเป็นขั้นที่ merge ได้ทีละขั้นโดย CI เขียว | ธรรมเนียมใน `docs/ROADMAP-FEATURES.md` (ภาพรวมเฟส) |
| Feature toggles | สวิตช์ปิด plugin ตอน runtime โดยไม่ deploy ใหม่ | `DISABLED_PLUGINS` / `PLUGIN_PICKS` (`tests/test_plugins.py`) |
| UI / design discipline | ตัวตนของ UI + โหมดต่อหน้า (Operate/Read/Enter) · งาน UI ประกาศ refine/redesign | `docs/DESIGN.md` · `tests/test_design_doc.py` · `ci:a11y` |
| Observability | log JSON + request id · `/metrics` ต้องมี token · `/healthz`+`/readyz` (ADR 0048) · SIEM stack ที่ alert ดังจริง · Prometheus ดูดจริง | `app/logging_setup.py` · `app/metrics.py` · `app/health.py` · `compose.metrics.yaml` · `ci:siem` · `ci:scrape` |
| Ownership | ผู้ดูแลคนเดียวถือ end-to-end — เครื่องมือถูกสร้างให้ "ลืมแล้วแดง" แทนการพึ่งความจำ | `gates.yaml` ทั้งดัชนี |

## จุดที่จงใจ*ไม่ทำตาม*ธรรมเนียม — และทำไม

ธรรมเนียมที่บทความมาตรฐานส่วนใหญ่แนะนำ แต่ repo นี้เลือกทางอื่นอย่างเปิดเผย
(บทความที่ดีเองก็เตือนเรื่อง "มาตรฐานเกินพอดี" — นี่คือการรับคำเตือนนั้นจริง ๆ):

| ธรรมเนียม | ที่นี่ทำ | เหตุผล |
|---|---|---|
| 100% coverage | 96% แบบ ratchet ขึ้นทางเดียว | เปอร์เซ็นต์สุดท้ายซื้อด้วยเทสต์ที่ทดสอบ mock ไม่ใช่พฤติกรรม — mutation test ให้ความเชื่อมั่นต่อบรรทัดสูงกว่า |
| comment ทุกฟังก์ชัน | docstring ขั้นต่ำ 84% (interrogate) และคอมเมนต์อธิบาย*ทำไม*ไม่ใช่*อะไร* | คอมเมนต์ที่บังคับให้มีคือคอมเมนต์ที่ถูกเขียนให้ผ่านด่าน ไม่ใช่ให้คนอ่าน |
| review โดยคนที่สอง | required checks ทั้งชุดแทน — อยู่บนเส้นทางบังคับจริงตั้งแต่ `enforce_admins` เปิด (มาตรการชดเชยบันทึกใน ADR 0053) | ตั้ง approvals ≥1 กับคนเดียว = merge ไม่ได้ตลอดกาล · เงื่อนไขทบทวน: มีผู้ดูแลคนที่สอง (เงื่อนไขหมดอายุของ ADR 0053) |
| A/B testing / canary | ไม่ทำ | เป้าโหลด 5 concurrent ไม่มีประชากรพอ — `ADR 0043` |
| microservices | monolith + plugin architecture | ขนาดของระบบไม่ถึงจุดที่ค่า orchestration คุ้ม — จุด plug ให้ความยืดหยุ่นที่ต้องการแล้ว |

## เครื่องมือประจำ (ดูคำสั่งเต็มใน `CLAUDE.md` และ `CONTRIBUTING.md`)

- ก่อนเปิด PR: `ruff check` + `ruff format` + `mypy app scripts` + `pytest --cov`
- ไฟล์เทสต์ใหม่ต้องลงทะเบียนใน `gates.yaml` (`CONTRIBUTING.md` กฎข้อ 8)
- ไฟล์ generate ห้ามแก้มือ — รายชื่ออยู่ใน `CONTRIBUTING.md` กฎข้อ 5
- fail-fix loop สำหรับไล่ gate ทีละตัว: `scripts/run_gates.py`
