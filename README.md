# Todolist

A personal to-do list built with Flask — and, more to the point, a place where
the engineering practices around a small app are taken all the way rather than
partway.

The app itself is modest and finished: tasks with categories, deadlines,
filters, two languages, three colour modes, accounts. What makes it worth reading
is everything around it — a plugin architecture where the core never names a
single plugin, an append-only audit trail that no feature has to remember to
call, and 21 CI jobs that run against real databases, a real reverse proxy, a
real identity provider, and a real directory server, with nothing mocked.

**This is a personal project, not a product.** It is deliberately
over-engineered for its size, on purpose, as a way to practise doing things
properly. If you are looking for the smallest possible Flask to-do example, this
is emphatically not it.

ฉบับภาษาไทยอยู่ครึ่งล่างของไฟล์ · [เอกสารทั้งหมด](docs/) เป็นภาษาไทย

## What it does

- Tasks with categories, start dates, and deadlines down to the minute, sorted
  so the closest deadline comes first
- Filters by status, category, and time — the next 15/30/45 minutes or 8 hours,
  today, tomorrow, or a range you choose; they combine
- English and Thai, remembered per user
- Light, dark, and automatic modes. Automatic follows real sunrise and sunset for
  your timezone, from a table covering all 598 zones that ships with the app — no
  network call, no JavaScript
- Accounts with roles, optional TOTP two-factor, and optional single sign-on
  against an OIDC provider or an LDAP directory
- A REST API at `/api/v1` with an OpenAPI 3.1 contract generated from the code
- Export your own data or close your own account, without asking anyone

There is **no signup page and no password reset by email**, both on purpose — the
project stores no email addresses. Accounts are created from the command line.

## Try it

```bash
git clone https://github.com/sayam/flask-todolist.git
cd flask-todolist
pipenv install
cp .env.example .env                                     # then set SECRET_KEY (≥ 32 chars)
python -c "import secrets; print(secrets.token_urlsafe(32))"
pipenv run flask db upgrade
pipenv run flask create-user alice
pipenv run flask run --debug
```

The app refuses to start without a `SECRET_KEY`, and there is deliberately no
default. Or bring up the whole stack — app, database, reverse proxy — with
Docker:

```bash
docker compose up                                        # SQLite
docker compose -f compose.yaml -f compose.mysql.yaml up   # MySQL
```

See [`docs/OPERATIONS.md`](docs/OPERATIONS.md) for replicas, TLS, and the
retention timer.

## How it is put together

**Logic lives in `app/services/`, and that layer does not know HTTP exists.** The
web routes and the API are both thin adapters over it — a rule enforced by an AST
scan that rejects any import of `request`, `session`, `flash`, or
`render_template` inside a service. Failures travel as exceptions carrying
machine-readable codes, and each adapter decides what a code means in its own
protocol.

**Almost everything is a plug point.** Themes, second factors, primary factors,
database brands, caches, and secret sources are all plugins under
`app/plugins/<type>/<id>/`. Adding one means dropping a directory in; removing
one means deleting it. The core is not allowed to name a specific plugin, and a
test enforces that by scanning the core for plugin names. Each plugin declares
its own libraries in its own pipenv category, so uninstalling a plugin takes its
supply chain with it instead of leaving it in `[packages]` forever — which turns
out to isolate licence obligations too, not just vulnerabilities.

**Deleting hides.** Every "delete" sets `deleted_at`, and the filter is added to
every ORM query automatically. Exactly one command actually removes rows, after
an approved retention period, and a test scans the codebase to keep it that way.

**Everything that changes the database is audited** by a session event, so a new
feature is covered without calling anything. The trail is a hash chain, and
appends serialise on a single lock row — which is what a hash chain requires the
moment more than one process writes to it. Finding that out took a load test, two
wrong fixes, and [three ADRs](docs/adr/).

## What is actually verified

Not "we have tests" — this is what runs on every push:

| | |
|---|---|
| Test suite | on SQLite, **and again on real MySQL 8 and MariaDB 11**, and once more with no plugin libraries installed at all |
| Static analysis | ruff with every rule enabled and exceptions justified one by one, mypy strict on a list that only grows, complexity and docstring floors that ratchet upward |
| Security | `pip-audit` on core, an SBOM, full-history secret scanning, and an **authenticated OWASP ZAP scan against the running app** |
| Accessibility | pa11y-ci driving real Chromium over dark mode, an alternate theme, and Thai — because contrast differs in each |
| Integration | the whole stack behind nginx with two replicas, TLS, a real OIDC provider, a real LDAP directory, a real Vault, a real systemd timer |
| Contracts | the OpenAPI file, the database schema, and the ASVS worksheet are regenerated and compared against what is committed |

**Every new test must be proven to catch something** before it counts as
finished: break the code it claims to cover, watch it go red, restore. That rule
has caught an ordering test that passed with `order_by` deleted, and a
preferences test that passed without writing anything.

Coverage is gated at **96%** and moves in one direction only. The API is
additionally fuzzed against its own OpenAPI spec, which found three bugs that
hand-written tests had walked straight past.

## Documentation

Written in Thai, because that is the language the thinking happened in.

| | |
|---|---|
| [`docs/adr/`](docs/adr/) | 38 architecture decision records — every choice, the options rejected, and what would reverse it |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | the seven phases, what each closed, and what was deliberately deferred |
| [`docs/ASVS.md`](docs/ASVS.md) | OWASP ASVS 5.0 Level 2 self-assessment — all 253 in-scope requirements answered, including the 48 that do not pass |
| [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) | measured numbers, including the ones that hurt |
| [`docs/DATA-CLASSIFICATION.md`](docs/DATA-CLASSIFICATION.md) | what is stored, how sensitive it is, how long it is kept |
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | running it for real |
| [`CLAUDE.md`](CLAUDE.md) | the working notes — every trap this project has already fallen into |

## Contributing, security, licence

- [`CONTRIBUTING.md`](CONTRIBUTING.md) — setup and the rules you would not guess
- [`SECURITY.md`](SECURITY.md) — how to report a vulnerability privately
- [`CHANGELOG.md`](CHANGELOG.md) — what changed and when
- [MIT](LICENSE) — Copyright (c) 2026 Sayam Sriphua

## Stack

Python 3.13 · Flask · Flask-SQLAlchemy with 2.0 typed models · Flask-Migrate ·
Flask-Login · Flask-WTF · Flask-Limiter · Flask-Babel · flask-smorest +
marshmallow · Talisman · SQLite / MySQL / MariaDB · pipenv

---

# Todolist (ฉบับภาษาไทย)

แอปจดงานส่วนตัวเขียนด้วย Flask — และที่สำคัญกว่านั้น เป็นที่ที่วินัยทางวิศวกรรม
รอบ ๆ แอปเล็ก ๆ ตัวหนึ่งถูกทำจนสุดทาง แทนที่จะทำครึ่งทาง

ตัวแอปเองเรียบและเสร็จแล้ว — งาน หมวด กำหนดส่ง ตัวกรอง สองภาษา สามโหมดสี
บัญชีผู้ใช้ · สิ่งที่ทำให้มันน่าอ่านคือของรอบ ๆ: สถาปัตยกรรม plugin ที่ core
ไม่รู้จักชื่อ plugin ตัวไหนเลย · audit trail แบบเติมได้อย่างเดียวที่ฟีเจอร์ใหม่
ไม่ต้องจำว่าต้องเรียก · และ CI 21 job ที่ยิงใส่ฐานข้อมูลจริง reverse proxy จริง
IdP จริง และ directory จริง โดยไม่มี mock สักตัว

**นี่เป็นโปรเจกต์ส่วนตัว ไม่ใช่ผลิตภัณฑ์** และตั้งใจทำเกินขนาดของมันเพื่อใช้ฝึก
ทำให้ครบจริง ๆ · ถ้ากำลังหาตัวอย่าง Flask to-do ที่เล็กที่สุด อันนี้ไม่ใช่แน่นอน

## ทำอะไรได้บ้าง

- งานที่มีหมวด วันเริ่ม และกำหนดส่งถึงระดับนาที เรียงงานที่ใกล้ครบกำหนดขึ้นก่อน
- กรองตามสถานะ หมวด และเวลา — ภายใน 15/30/45 นาที หรือ 8 ชั่วโมง วันนี้ พรุ่งนี้
  หรือเลือกช่วงเอง · ใช้ร่วมกันได้
- ไทยกับอังกฤษ จำภาษาที่เลือกไว้ให้รายคน
- โหมดสว่าง มืด และอัตโนมัติ — อัตโนมัติสลับตามเวลาดวงอาทิตย์ขึ้น-ตกจริงของ
  เขตเวลานั้น จากตารางครบทั้ง 598 เขตที่ฝังมากับแอป ไม่ต่อเน็ตและไม่ใช้ JS
- บัญชีผู้ใช้ที่มีบทบาท · ปัจจัยที่สองแบบ TOTP · และ SSO ผ่าน OIDC หรือ LDAP
- REST API ที่ `/api/v1` พร้อมสัญญา OpenAPI 3.1 ที่ generate จากโค้ด
- ขอสำเนาข้อมูลของตัวเอง และปิดบัญชีตัวเองได้ โดยไม่ต้องขอใคร

**ไม่มีหน้าสมัครสมาชิกและไม่มีการรีเซ็ตรหัสผ่านทางอีเมล** ทั้งคู่ตั้งใจ —
ระบบไม่เก็บอีเมล · บัญชีสร้างจากบรรทัดคำสั่ง

## ลองรัน

```bash
git clone https://github.com/sayam/flask-todolist.git
cd flask-todolist
pipenv install
cp .env.example .env                                     # แล้วใส่ SECRET_KEY (ยาว ≥ 32 ตัว)
python -c "import secrets; print(secrets.token_urlsafe(32))"
pipenv run flask db upgrade
pipenv run flask create-user alice
pipenv run flask run --debug
```

ไม่มี `SECRET_KEY` แล้วแอปไม่ start และไม่มีค่า default โดยตั้งใจ ·
หรือยกทั้ง stack ขึ้นมาด้วย `docker compose up` (ดู
[`docs/OPERATIONS.md`](docs/OPERATIONS.md) สำหรับ replica, TLS
และ timer ของงานลบข้อมูล)

## ประกอบขึ้นมาอย่างไร

**ตรรกะอยู่ใน `app/services/` และชั้นนั้นไม่รู้จัก HTTP เลย** route ของเว็บกับ
API เป็น adapter บาง ๆ เหนือมันทั้งคู่ — มี AST scan บังคับว่าไฟล์ใน service
ห้าม import `request`, `session`, `flash`, `render_template` ·
ความล้มเหลวเดินทางด้วย exception ที่มี code ให้เครื่องอ่าน แล้วแต่ละ adapter
ตัดสินเองว่า code นั้นแปลว่าอะไรในโปรโตคอลของตัว

**เกือบทุกอย่างเป็นจุด plug** ธีม ปัจจัยที่สอง ปัจจัยหลัก ยี่ห้อฐานข้อมูล cache
และแหล่งความลับ เป็น plugin ทั้งหมด · เพิ่ม = วางไดเรกทอรี ถอด = ลบไดเรกทอรี ·
core ห้ามรู้จักชื่อ plugin ตัวใดตัวหนึ่ง และมีเทสต์ grep บังคับ ·
**ไลบรารีของ plugin อยู่ใน category ของตัวเอง** ถอด plugin แล้ว supply chain
หายไปด้วย — ซึ่งกลายเป็นว่ามันแยก*ภาระ license*ไปด้วย ไม่ใช่แค่ CVE

**"ลบ" แปลว่าซ่อน** ทุกการลบตั้ง `deleted_at` และตัวกรองถูกเติมให้ทุก ORM query
อัตโนมัติ · มีคำสั่งเดียวที่ลบจริงหลังพ้นระยะเก็บรักษา และมีเทสต์สแกนโค้ดคุมไว้

**ทุกการเขียนฐานข้อมูลถูก audit** ด้วย event ของ session ฟีเจอร์ใหม่จึงถูกครอบ
โดยไม่ต้องเรียกอะไร · สายเป็น hash chain และการเติมต่อคิวกันที่แถวล็อกแถวเดียว
ซึ่งเป็นสิ่งที่ hash chain ต้องการทันทีที่มีมากกว่าหนึ่ง process เขียน —
กว่าจะรู้ข้อนี้ต้องผ่าน load test หนึ่งรอบ การแก้ผิดสองครั้ง และ ADR สามใบ

## อะไรที่ถูกพิสูจน์จริง

ไม่ใช่ "มีเทสต์" แต่คือของพวกนี้รันทุก push: ชุดเทสต์บน SQLite **และบน MySQL 8
กับ MariaDB 11 ของจริง** และอีกรอบในสภาพที่ไม่มีไลบรารีของ plugin เลย ·
ruff ที่เปิดทุกกฎ · mypy strict ที่ขยายได้อย่างเดียว · `pip-audit` · SBOM ·
secret scan ทั้งประวัติ · **ZAP ที่ login แล้วยิงใส่แอปที่รันอยู่จริง** ·
pa11y-ci บน Chromium จริงทั้งโหมดมืด ธีมอื่น และภาษาไทย · stack เต็มหลัง nginx
ที่มีสอง replica, TLS, IdP จริง, LDAP จริง, Vault จริง, systemd timer จริง

**เทสต์ใหม่ทุกตัวต้องถูกพิสูจน์ว่าจับของจริงได้** ก่อนถือว่าเสร็จ — พังโค้ดที่มัน
อ้างว่าคุ้ม ดูให้แดง แล้วคืน · กติกาข้อนี้จับเทสต์ลำดับการเรียงที่ผ่านทั้งที่ถอด
`order_by` ออก และเทสต์ preferences ที่ผ่านทั้งที่ไม่ได้เขียนอะไรเลย ·
coverage มีพื้นที่ **96%** และขยับขึ้นทางเดียว · API ยังถูก fuzz ด้วยสเปคของ
ตัวเอง ซึ่งเจอบั๊กสามตัวที่เทสต์ที่คนเขียนเองเดินผ่านไป

## เอกสาร

[`docs/adr/`](docs/adr/) 38 ใบ (ทุกการตัดสินใจ ทางที่ไม่ได้เลือก และเงื่อนไข
ที่จะทำให้มันหมดอายุ) · [`docs/ROADMAP.md`](docs/ROADMAP.md) ·
[`docs/ASVS.md`](docs/ASVS.md) · [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md) ·
[`docs/DATA-CLASSIFICATION.md`](docs/DATA-CLASSIFICATION.md) ·
[`docs/OPERATIONS.md`](docs/OPERATIONS.md) ·
[`CLAUDE.md`](CLAUDE.md) (บันทึกการทำงาน — กับดักทุกอันที่โปรเจกต์นี้เคยตกไปแล้ว)

## License

[MIT](LICENSE) — Copyright (c) 2026 Sayam Sriphua ·
เหตุผลที่เลือกและสิ่งที่ตรวจก่อนตัดสินอยู่ใน
[ADR 0038](docs/adr/0038-mit-license.md) · **ไลบรารีของ core เป็น permissive
ทั้งหมด** ตัวที่มีภาระ copyleft ตัวเดียวคือ `ldap3` (LGPLv3) ซึ่งอยู่ใน category
ของ plugin ที่ถอดทิ้งได้ (`tests/test_licensing.py` ตรึงไว้)
