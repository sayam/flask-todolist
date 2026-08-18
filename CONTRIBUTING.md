# Contributing

> English first, because this file is where a stranger starts.
> ฉบับภาษาไทยอยู่ครึ่งล่างของไฟล์

## Read this first: the documentation is in Thai

The code, commit messages, and this file are in English. **Almost everything that
explains *why* the code looks the way it does is in Thai** — [`CLAUDE.md`](CLAUDE.md)
(the working notes), the 67 records in [`docs/adr/`](docs/adr/), and the rest of
`docs/`. Machine translation handles them acceptably, but you should know that
before you invest an afternoon.

You can still contribute without reading Thai: the gates described below will tell
you when you have broken a rule, and every one of them fails with a message that
names the rule. That is the point of having them.

## What this project optimises for

Not velocity. This is a personal todo list that is deliberately over-engineered as
a place to practise engineering discipline properly. A change that works but
arrives without a test that would have caught its absence is not finished here.
If that trade-off is not what you are looking for in a weekend contribution, that
is entirely reasonable — and better to know now.

## Setup

```bash
pipenv install --dev
pipenv run pre-commit install --hook-type pre-commit --hook-type commit-msg
cp .env.example .env      # then put a real SECRET_KEY in it (≥ 32 chars)
pipenv run flask db upgrade
pipenv run flask create-user <name>
pipenv run flask run --debug
```

Add dependencies with `pipenv install <pkg>`, **never `pip install`** — the latter
leaves `Pipfile`/`Pipfile.lock` out of sync and CI will catch it later and less
helpfully.

If your change needs a library for a *plugin*, it goes in that plugin's own pipenv
category, declared in the plugin's `plugin.json` — not in `[packages]`. A test
enforces this. See [ADR 0025](docs/adr/0025-plug-points-and-supply-chain-isolation.md).

## The rules that will surprise you

These are the ones that are unusual enough that you will not guess them.

### 1. Every new test must be proven to catch something

**This is not optional and it is not a formality.** Before a test counts as
finished, break the code it claims to cover — really break it, not a variable
beside it — confirm the test goes red, then restore the code from a copy and check
with `git diff` that you restored all of it.

A test that stays green when you delete the behaviour it names is not a weak test.
It is not a test. This has caught, among others, an ordering test that passed with
`order_by` removed and a preferences test that passed without writing the session.

### 2. Decisions need an ADR

Anything that closes off an alternative — a library choice, a schema shape, a
security trade-off — gets a numbered record in [`docs/adr/`](docs/adr/) and a row
in its index. The format is loose; what matters is that the *rejected* options and
the conditions that would reverse the decision are written down.

### 3. Quality thresholds ratchet upward only

Coverage, docstring coverage, and complexity limits live in `pyproject.toml` and
move in one direction. Lowering one to make a change fit is not an option on the
table; if a change genuinely warrants it, that is an ADR.

### 4. Business logic lives in `app/services/`

Routes and API views are thin adapters. Files under `app/services/` may not import
`request`, `session`, `g`, `flash`, `abort`, `redirect`, `render_template`,
`url_for`, `jsonify`, or `flask_login` — an AST scan enforces it. Services raise
`NotFoundError`/`ValidationError`/`ConflictError` and commit their own
transactions. See [ADR 0016](docs/adr/0016-service-layer-boundary.md).

### 5. Some files are generated — do not hand-edit them

`docs/openapi.json`, `app/password_blocklist.txt`, `app/sun_data.py`, the compiled
`.mo` catalogues, and — since the scaffolding phases — [`SKILL.md`](SKILL.md),
[`SKILL-TODOLIST.md`](SKILL-TODOLIST.md),
[`docs/GATES-ASVS.md`](docs/GATES-ASVS.md), and the whole
[`skill/`](skill/) package (ADR 0050). Each has a script in `scripts/` that
produces it, and CI compares the committed copy against a fresh run. Changing
`app/api/` without running
`PYTHONPATH=. pipenv run python scripts/generate_openapi.py` turns CI red, and a
rule written into `SKILL.md` by hand is overwritten the next time it is
regenerated — add a portable gate instead (see rule 8).

### 6. English in code, Thai in translations

User-facing strings in code are English, because the English string *is* the
translation key. Thai lives in `app/translations/th/LC_MESSAGES/messages.po`.
Never write Thai directly in a template or a `.py` file, and remember to
`pybabel compile` — the `.mo` files are committed.

### 7. Commits are Conventional Commits, subject ≤ 72 characters

Enforced by a commit-msg hook and again in CI. `feat:`, `fix:`, `docs:`, `test:`,
`refactor:`, `chore:`, `ci:`, `perf:`, optionally scoped: `fix(audit): ...`.

**Merge with rebase, not squash — via auto-merge.** Use
`gh pr merge N --rebase --delete-branch --auto` and let GitHub land the
PR when all required checks pass. Squashing appends ` (#N)` to the subject,
which pushes anything near the limit over it — and the check that would have
caught it only runs after the merge has already landed on `main`. Merge commits
themselves are not linted, since GitHub writes those, not you.

### 8. A new test file has to be registered in `gates.yaml`

[`gates.yaml`](gates.yaml) is the index of every gate in the repo, and
`tests/test_gates.py` enforces it **in both directions**: every CI job must have a
gate, and **every file under `tests/` must be claimed by exactly one gate** — a
full partition, the same shape as the data-classification table. Adding a test
file without an entry turns CI red on purpose. You have two options:

- it belongs to an existing gate → add it to that gate's `tests:` list
- it enforces a new rule → add a gate, and declare its `layer:` —
  `baseline` (universal — must also be `portable: true`), `business`
  (an app-type agreement), or `internal` (this repo only) — **and its
  `pillar:`** — which layer of the project's priority stack it serves
  (`security` / `performance` / `manageability` / `devx`, ADR 0051;
  see rule 10). If the rule would
  hold in any project, mark it `portable: true` and write `born_from`: the trap
  that produced the rule. Portable gates are what [`SKILL.md`](SKILL.md),
  [`SKILL-TODOLIST.md`](SKILL-TODOLIST.md), and
  [`overlays/flask/`](overlays/flask/) are generated from, so the entry has to
  carry its own reason for existing.

### 9. UI work starts from the design document

Read [`docs/DESIGN.md`](docs/DESIGN.md) before touching anything under
`app/templates/` or `app/static/base.css`, and say which kind of change you
are making: **refine** (the default — hold the identity the document
describes) or **redesign** (change the identity — then the document must be
amended in the same PR). A new full page must also claim a mode
(Operate / Read / Enter) in the document's table — `tests/test_design_doc.py`
enforces the table against the templates on disk in both directions.

### 10. New ideas enter through the constitution's intake rules

The project's concerns are ranked ([ADR
0051](docs/adr/0051-project-constitution-and-intake.md)): **security**
(country law, worldwide standards, supply chain) over **scalability &
performance** over **manageability** over **DevSecOps friendliness**. When
two concerns collide, the higher layer wins without a new debate; a
temporary exception needs an ADR with an expiry condition.

Bringing in anything new — a skill, an idea, a standard, a tool — follows
three rules, in order: (1) the existing baseline must not break — no gate
turns red, gets weakened, or is removed without an owner-approved ADR;
(2) classify before adopting: better than the baseline → replace it, absent
from the baseline → adapt it in, good only in specific situations → adopt
it scoped (a plugin, a config, a documented section), conflicts with a
higher layer → reject it and record why; (3) significant adoptions and
rejections are recorded as ADRs — the ADR log *is* the intake log.

### 11. `main` only accepts pull requests — no exceptions, not even the owner

Branch protection enforces this for admins too
([ADR 0053](docs/adr/0053-solo-maintainer-sod-compensating-controls.md)):
every change, however small, travels branch → PR → 27 required checks green →
merge. The project has a single maintainer, so a second reviewer cannot
exist; the compensating controls (the real-service check wall, the
append-only audit chain, the public history) only work if they sit on the
mandatory path. Review count is intentionally 0 — the day a second regular
contributor arrives, required reviews turn on and ADR 0053 gets revisited.

## Before you open a pull request

```bash
pipenv run python scripts/preflight.py   # walks CI's own lint + test steps locally
```

That one command reads `.github/workflows/ci.yml` and runs what CI runs, so the
list cannot drift from the pipeline (ADR 0060). The commit hook already covers
ruff, format, and mypy; xenon, interrogate, the coverage floor, and diff-cover
would otherwise meet you for the first time in CI. Steps it cannot run locally
are skipped **with the reason printed**. If you prefer the pieces:

```bash
pipenv run ruff check . && pipenv run ruff format .
pipenv run mypy app scripts
pipenv run pytest -v
pipenv run pytest --cov          # must not drop below the floor in pyproject.toml
```

CI runs 28 jobs (30 checks) against real services — three database brands, a real
reverse proxy, a real IdP, a real LDAP directory, a real Vault, an authenticated
ZAP scan, and a Chromium accessibility pass. Expect the pull request to take
longer to go green than it took to write. Nothing there is mocked, which is
deliberate.

Describe **what you changed and what would have gone wrong without it**. A diff
explains itself; the failure it prevents usually does not.

## Continuity: if the maintainer disappears

Nothing about this project's continuity depends on any private asset the
maintainer holds. The repository is public and MIT-licensed, so a fork
carries every right needed to continue. Everything the project produces
is reproduced from the repository itself: CI builds and signs release
artifacts **keyless** (sigstore OIDC — there is no private signing key
to lose), dependency updates arrive through Dependabot configuration
committed in-repo, and every gate, document, and generated file rebuilds
from committed sources. The one secret that exists,
`DATA_ENCRYPTION_KEY`, guards each operator's *own instance data* — it
is not a project asset and its loss affects no one else's deployment.
So the continuity plan is the repository: fork it, and the project
continues whole ([ADR 0053](docs/adr/0053-solo-maintainer-sod-compensating-controls.md)
records what changes when a second regular contributor arrives).

## Licensing of contributions

By opening a pull request you agree that your contribution is published under the
[MIT License](LICENSE), the same terms as the rest of the project. **There is no
CLA** and no copyright assignment — you keep the copyright in what you wrote. See
[ADR 0038](docs/adr/0038-mit-license.md).

## Conduct

[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) applies to every space this project
uses. Reports go to the maintainer through the private channel described there.

---

# การร่วมพัฒนา (ฉบับภาษาไทย)

## สิ่งที่โปรเจกต์นี้ให้ค่า

ไม่ใช่ความเร็ว · นี่เป็นแอปจดงานส่วนตัวที่ตั้งใจทำเกินความจำเป็นเพื่อใช้ฝึกวินัย
ทางวิศวกรรมให้ครบจริง ๆ · การเปลี่ยนแปลงที่ทำงานได้แต่มาโดยไม่มีเทสต์ที่จะจับได้
ตอนมันหายไป **ยังไม่ถือว่าเสร็จ**

## ตั้งเครื่อง

```bash
pipenv install --dev
pipenv run pre-commit install --hook-type pre-commit --hook-type commit-msg
cp .env.example .env      # แล้วใส่ SECRET_KEY จริง (ยาว ≥ 32 ตัว)
pipenv run flask db upgrade
pipenv run flask create-user <ชื่อ>
```

เพิ่ม dependency ด้วย `pipenv install` **ห้าม `pip install` ตรง ๆ** ·
ไลบรารีที่ *plugin* ต้องใช้ไปอยู่ใน category ของ plugin นั้น ไม่ใช่ `[packages]`
([ADR 0025](docs/adr/0025-plug-points-and-supply-chain-isolation.md) — มีเทสต์บังคับ)

## กติกาที่เดาเองไม่ได้

1. **เทสต์ใหม่ทุกตัวต้องพิสูจน์ว่าจับของจริงได้** — พังโค้ดที่มันอ้างว่าคุ้มอยู่จริง ๆ
   เทสต์ต้องแดง แล้วคืนโค้ดด้วย `cp` จากสำเนา ตรวจด้วย `git diff` ว่าคืนครบ ·
   เทสต์ที่ยังเขียวตอนลบพฤติกรรมที่มันเอ่ยชื่อออก ไม่ใช่เทสต์ที่อ่อน แต่ไม่ใช่เทสต์
2. **การตัดสินใจต้องมี ADR** — สิ่งที่ต้องเขียนคือทางเลือกที่*ไม่ได้เลือก*
   และเงื่อนไขที่จะทำให้คำตัดสินนั้นหมดอายุ
3. **เพดานคุณภาพขยับขึ้นทางเดียว** — ลดเพื่อให้งานผ่านไม่ใช่ตัวเลือกที่มีอยู่
4. **ตรรกะอยู่ใน `app/services/`** route เป็น adapter บาง ๆ (มี AST scan บังคับ)
5. **ไฟล์ที่ generate มาห้ามแก้ด้วยมือ** — `docs/openapi.json`,
   `app/password_blocklist.txt`, `app/sun_data.py`, ไฟล์ `.mo`, `SKILL.md`,
   `SKILL-TODOLIST.md`, `docs/GATES-ASVS.md` และทั้งโฟลเดอร์ `skill/`
   (แพ็กเกจ agent skill — ADR 0050)
6. **ข้อความในโค้ดเป็นภาษาอังกฤษ** เพราะ msgid คือภาษาอังกฤษ · ไทยอยู่ใน `.po`
7. **commit เป็น Conventional Commits หัวไม่เกิน 72 ตัว** · merge ด้วย
   rebase ไม่ใช่ squash — ผ่าน auto-merge:
   `gh pr merge N --rebase --delete-branch --auto`
8. **เพิ่มไฟล์เทสต์ใหม่ต้องมาลงทะเบียนใน `gates.yaml`** — ดัชนีนั้นถูกบังคับ
   สองทิศ: ทุก job ต้องมี gate และ**ไฟล์ใต้ `tests/` ทุกไฟล์ต้องเป็นของ gate
   เดียว** (partition เต็ม) · ไม่ลงทะเบียน = CI แดงโดยตั้งใจ · gate ใหม่ต้อง
   ประกาศ `layer:` ด้วย (`baseline`/`business`/`internal` — baseline ต้อง
   portable) **และ `pillar:`** — รับใช้ชั้นไหนของธรรมนูญ (`security`/
   `performance`/`manageability`/`devx` — ADR 0051 ดูกฎข้อ 10) ·
   ถ้ากฎนั้นใช้ได้กับโปรเจกต์อื่นด้วย ให้ตั้ง `portable: true` +
   `born_from` (กับดักที่ให้กำเนิดกฎข้อนั้น) เพราะ `SKILL.md`,
   `SKILL-TODOLIST.md` กับ `overlays/flask/` generate มาจากตรงนั้น
9. **งาน UI เริ่มจาก [`docs/DESIGN.md`](docs/DESIGN.md)** — อ่านก่อนแตะ
   `app/templates/` หรือ `app/static/base.css` และประกาศว่าเป็น **refine**
   (ค่าเริ่มต้น — รักษาตัวตนตามเอกสาร) หรือ **redesign** (เปลี่ยนตัวตน —
   ต้องแก้เอกสารใน PR เดียวกัน) · หน้าเต็มใหม่ต้องเพิ่มแถวในตารางโหมดด้วย
   (`tests/test_design_doc.py` บังคับสองทิศ)
10. **ของใหม่เข้าผ่านกติกา intake ของธรรมนูญ**
    ([ADR 0051](docs/adr/0051-project-constitution-and-intake.md)) —
    ความกังวลเรียงสี่ชั้น: **security** (กฎหมายรายประเทศ · มาตรฐานสากล ·
    supply chain) > **scalability & performance** > **manageability** >
    **DevSecOps friendliness** · ชนกันเมื่อไหร่ชั้นบนชนะ ยกเว้นชั่วคราว
    ต้องมี ADR พร้อมเงื่อนไขหมดอายุ · รับของใหม่สามขั้นตามลำดับ:
    (1) baseline ห้าม break — gate แดง/ถูกลด/ถูกถอดโดยไม่มี ADR ที่เจ้าของ
    อนุมัติ = break · (2) จำแนกก่อนรับ: ดีกว่า=แทน · ไม่เคยมี=ปรับเข้า ·
    ดีเฉพาะบางสถานการณ์=รับแบบจำกัดขอบเขต · ขัดชั้นบน=ปัดตกพร้อมจดเหตุผล ·
    (3) การรับ/ปัดตกที่มีนัยจดเป็น ADR — ADR คือ intake log
11. **`main` รับของทาง PR เท่านั้น — ไม่มีข้อยกเว้นแม้แต่เจ้าของ**
    ([ADR 0053](docs/adr/0053-solo-maintainer-sod-compensating-controls.md))
    — branch protection บังคับถึง admin (`enforce_admins`) ทุกงานเดิน
    branch → PR → required check เขียวครบ 27 → merge · review count เป็น 0
    โดยตั้งใจ (คนเดียว review ตัวเองไม่ได้ — มาตรการชดเชยอยู่ใน ADR) ·
    มี contributor ประจำคนที่สองเมื่อไหร่ เปิด required review ทันที

## ก่อนเปิด pull request

```bash
pipenv run python scripts/preflight.py   # เดิน step ของ job lint + test ตามที่ CI ทำ
```

คำสั่งเดียวนี้อ่าน `.github/workflows/ci.yml` แล้วรันตามที่ CI รันจริง รายการจึง
drift จาก pipeline ไม่ได้ (ADR 0060) · hook ก่อน commit ครอบ ruff/format/mypy
อยู่แล้ว ส่วน xenon · interrogate · coverage floor · diff-cover จะเจอกันครั้งแรก
ใน CI ถ้าไม่รันตัวนี้ · step ที่รันบนเครื่องไม่ได้ถูก**ข้ามพร้อมเหตุผลที่พิมพ์ออกมา**
· อยากรันทีละชิ้นก็ได้:

```bash
pipenv run ruff check . && pipenv run ruff format .
pipenv run mypy app scripts
pipenv run pytest -v
pipenv run pytest --cov
```

CI มี 28 job (30 check) ที่ยิงของจริงทั้งหมด — สามยี่ห้อฐานข้อมูล, reverse proxy,
IdP, LDAP, Vault, ZAP แบบ login แล้ว และ Chromium สำหรับ accessibility ·
ไม่มี mock สักตัว โดยตั้งใจ (`dialects` เป็น matrix สองยี่ห้อ จึงนับเป็นสอง check) · เขียนอธิบายว่า**แก้อะไร และถ้าไม่แก้จะพังอย่างไร**
เพราะ diff อธิบายตัวเองได้ แต่ความพังที่มันกันไว้อธิบายตัวเองไม่ได้

## ความต่อเนื่อง: ถ้าผู้ดูแลหายไป

ความต่อเนื่องของโปรเจกต์ไม่พึ่งของส่วนตัวชิ้นไหนของผู้ดูแลเลย — repo
สาธารณะ + MIT แปลว่า fork เดียวได้สิทธิ์ครบ · ทุกอย่างที่โปรเจกต์ผลิต
สร้างซ้ำได้จากตัว repo: CI เซ็น release แบบ **keyless** (ไม่มีคีย์ส่วนตัว
ให้หาย) · Dependabot ตั้งค่าในไฟล์ที่ commit ไว้ · gate/เอกสาร/ไฟล์
generate ทั้งหมดสร้างใหม่จาก source ที่ commit · ความลับตัวเดียวที่มีคือ
`DATA_ENCRYPTION_KEY` ซึ่งเป็นของ*ข้อมูลใน instance ของผู้ deploy แต่ละคน*
ไม่ใช่ของโปรเจกต์ — แผนความต่อเนื่องจึงคือตัว repo เอง: fork แล้วเดินต่อ
ได้ครบ (ADR 0053 บันทึกว่าอะไรเปลี่ยนเมื่อมี contributor ประจำคนที่สอง)

## license ของสิ่งที่คุณส่งมา

เปิด PR = ยอมให้เผยแพร่ภายใต้ [MIT](LICENSE) เหมือนส่วนที่เหลือ ·
**ไม่มี CLA** และไม่มีการโอนลิขสิทธิ์ คุณยังถือลิขสิทธิ์ในสิ่งที่คุณเขียน
