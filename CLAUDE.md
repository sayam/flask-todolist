# Todolist (Flask)

## Stack
- Flask + Flask-SQLAlchemy, SQLite (dev), pipenv จัดการ env
- Flask-Migrate (alembic) จัดการ schema, Flask-Login จัดการ session, Flask-WTF จัดการ CSRF,
  Flask-Limiter จำกัดจำนวนครั้งที่หน้า login
- flask-smorest + marshmallow ทำ `/api/v1` และ generate OpenAPI spec จากโค้ด
- segno สร้าง QR ของ MFA — **อยู่ใน category `plugin-auth-totp-qr-segno` ไม่ใช่ `[packages]`**
  เพราะเป็นไลบรารีของ *ส่วนเสริม* ของ plugin ไม่ใช่ของ core (ADR 0025)
  ถอด `app/plugins/auth/totp/enhancements/qr-segno/` ทิ้ง = ไม่มี QR แต่ MFA ยังใช้ได้
- Python 3.13

## Commands
- รัน dev server: `pipenv run flask run --debug`
- รัน test: `pipenv run pytest -v` (coverage gate: `pipenv run pytest --cov`)
- lint/format: `pipenv run ruff check .` / `pipenv run ruff format .`
- type check: `pipenv run mypy app scripts` (strict list ใน pyproject — ขยาย ห้ามหด)
- ครั้งแรกหลัง clone: `pipenv run pre-commit install --hook-type pre-commit --hook-type commit-msg`
- เพิ่ม dependency: `pipenv install <pkg>` (ห้ามใช้ `pip install` ตรง ๆ — Pipfile/Pipfile.lock จะไม่ sync)
- สร้าง user: `pipenv run flask create-user <ชื่อ>` (ไม่มีหน้าสมัครสมาชิก โดยตั้งใจ)
- ดู user: `pipenv run flask list-users`
- ปิดบัญชี (ทางเดียวที่ถูก): `pipenv run flask delete-user <ชื่อ>` (ADR 0034)
- ระงับ/เลิกระงับบัญชี (PDPA ม.34): `pipenv run flask suspend-user <ชื่อ>` /
  `unsuspend-user <ชื่อ>` — ระงับ ≠ ลบ ย้อนกลับได้เสมอ ข้อมูลไม่ถูกแตะ
- ตั้งรหัสผ่านให้คนอื่น (ทางกู้บัญชีทางเดียว): `pipenv run flask set-password <ชื่อ>`
- ส่งออกข้อมูลของผู้ใช้: `pipenv run flask export-user <ชื่อ> [--output ไฟล์]`
- ตั้งบทบาท: `pipenv run flask set-role <ชื่อ> admin|user` (ทางเดียวที่ตั้ง admin คนแรกได้)
- plugin ที่มีตารางของตัวเอง: `pipenv run flask plugin-list` /
  `plugin-install auth/totp` / `plugin-uninstall auth/totp` (**ถอนแล้วข้อมูลหายจริง**)
- ไลบรารีที่ plugin ต้องใช้: `pipenv run flask plugin-deps` (ดูว่าอะไรขาด)
  ติดตั้ง: `pipenv sync --categories="$(pipenv run flask plugin-deps --categories)"`
  **`pipenv sync --dev` เฉย ๆ ไม่ติดตั้งให้** โดยตั้งใจ (ADR 0025)
- ออก API token: `pipenv run flask token-create <ชื่อผู้ใช้> --name "<ใช้ทำอะไร>"`
  (ดู `token-list` / เพิกถอน `token-revoke <ชื่อผู้ใช้> <id>`)
- ล้างข้อมูลที่พ้นระยะ: `pipenv run flask purge-expired` (ดูก่อนด้วย `--dry-run`)
- ตรวจ audit: `pipenv run flask audit-verify` / อ่าน audit: `pipenv run flask audit-log`
- เปลี่ยน schema: `pipenv run flask db migrate -m "..."` แล้ว `pipenv run flask db upgrade`
- อัปเดตสัญญา API: `PYTHONPATH=. pipenv run python scripts/generate_openapi.py`
  (ต้องรันทุกครั้งที่แก้ `app/api/` ไม่งั้น CI แดง)

## Structure
- `app/__init__.py` — app factory (`create_app`), init db/migrate/csrf/limiter/login_manager
  และ errorhandler ของ 429
- `app/models.py` — SQLAlchemy models ของ core (`User`, `ApiToken`, `Category`,
  `Todo` และของ org graph: `Team`, `TeamMember`, `TodoShare`, `TodoDependency`,
  `TeamNameChange` — บันทึกเปลี่ยนชื่อวงที่สมาชิกอ่านได้ CR#3)
  แบบ 2.0 typed (`Mapped[]`) — ของ plugin อยู่ใน `models.py` ของ plugin เอง
- `app/services/` — **ตรรกะทั้งหมดอยู่ที่นี่ และไม่รู้จัก HTTP เลย** (ดูหัวข้อ service layer)
  `lookup.by_id()` เป็นทางเดียวที่หาแถวตาม id ที่มาจากภายนอก (กัน id เกิน 64 บิต → 500)
- `app/routes.py` — view functions ของงาน/หมวด/ตั้งค่า ผูกกับ blueprint `main`
  เป็น **adapter บาง ๆ** เหนือ service ไม่ใช่ที่อยู่ของตรรกะ
- `app/api/` — `/api/v1` (flask-smorest) adapter อีกตัวบน service ชุดเดียวกัน
- `app/auth.py` — login/logout + ขั้นที่สองของ MFA ผูกกับ blueprint `auth`
- `app/admin/` — **package** ของผู้ดูแลระบบ (blueprint `admin` — ADR 0044):
  `__init__.py` (registry ของ panel — หน้าใหม่เรียก `register_panel(endpoint,
  title, category)` ตอน import · หน้า `/admin` = Site administration จัดกลุ่ม
  ตามหมวดแบบ Moodle · ลิงก์เข้า hub มีที่เดียวคือ top nav — sub-nav ของหน้า
  admin มีเฉพาะตัว panel (CR#2) และ nav วนจาก registry) · `users.py` (บทบาท + **unmask ที่ลง audit** +
  ระงับ/เลิกระงับ) · `teams.py` (วงของ org graph — ADR 0049) · `system.py`
  (environment/lifecycle/observability/SBOM) · ทำงานกับข้อมูล **ของคนอื่น**
  จึงแยกจาก `routes.py` ที่ทำงานกับข้อมูลของเจ้าของ session เท่านั้น
  · **ข้อมูลผู้ใช้บนหน้า admin ผ่านชั้น mask ตามชั้นข้อมูลเสมอ** (ADR 0045 —
  `app/services/masking.py`: C1/C3 ไม่ออกจอ · C2 mask · unmask เป็น POST ที่ลง
  audit) เพิ่มคอลัมน์ใหม่ต้องมาตัดสินที่นั่นด้วย (`tests/test_masking.py` บังคับ)
- `app/session_security.py` — อายุ/การผูก/การล้าง session ทั้งหมด (ดูหัวข้อ session)
- `app/password_blocklist.txt` — **ไฟล์ที่ generate มา ห้ามแก้ด้วยมือ**
  (`scripts/build_password_blocklist.py`)
- `app/cli.py` — custom flask CLI commands
- `app/health.py` — `/healthz` (liveness — **ไม่แตะ DB โดยตั้งใจ**) + `/readyz`
  (SELECT 1 จริง → 200/503) ไม่มี token ไม่มีข้อมูลภายใน (ADR 0048) ·
  `logging_setup` ข้าม log รายคำขอของสอง path นี้ (ล้มยัง log) · HEALTHCHECK
  ของ image ยิง `/readyz` พร้อม header `X-Forwarded-Proto` — **อย่าประกาศ
  healthcheck ทับใน compose** (เคยทำแล้ว stack TLS พังทั้งแถบเพราะ header หาย)
- `app/services/teams.py` + `sharing.py` + `dependencies.py` — org graph
  (ADR 0049): วง admin-only · แชร์เผยสี่ฟิลด์ผ่าน `SharedTodoView` เท่านั้น ·
  dependency เชิญ→ยอมรับ · จุดตัดสินการมองเห็นเดียว `sharing.can_see_todo()`
  และจุดตัดเดียว `sever_invisible_dependencies()` · impact deterministic กันวงวน
  · เปลี่ยนชื่อวง (`teams.rename` — เหตุผลบังคับ) ลง `TeamNameChange` ให้
  สมาชิกอ่านที่ `/teams/<id>/info` (สิทธิ์ = สมาชิก**หรือ** admin — CR#3)
- `app/services/suspension.py` — ระงับบัญชี (ม.34) · `app/services/masking.py` —
  mask ตามชั้นข้อมูล (ADR 0045) · `app/services/system_info.py` — ข้อมูลหน้า
  environment/SBOM/lifecycle ของ admin
- `app/plugins/auth/totp/crypto.py` — AES-256-GCM ของความลับ TOTP (ADR 0046)
  รูปเก็บ `enc:v1:<nonce>:<ct>` · คีย์คือ `DATA_ENCRYPTION_KEY` · แถว legacy
  ถูก encrypt ตอน verify สำเร็จครั้งถัดไป (ตาราง plugin อยู่นอกสาย alembic)
- `compose.metrics.yaml` + `deploy/prometheus.yml` — Prometheus+Grafana ดูด
  `/metrics` จริง (token อยู่ในไฟล์ `METRICS_TOKEN_FILE` อ่านใหม่ทุก scrape)
  job `scrape` พิสูจน์ทุก push · `scripts/n1_smoke.py` + job `n-1` — โค้ดของ
  tag ล่าสุดต้องให้บริการบน schema ของ HEAD (ADR 0048 · expand–contract)
- `app/tz.py` — แปลงเวลา UTC ↔ เวลาท้องถิ่นของผู้ใช้
- `app/theme.py` — เลือกชุดสีและโหมด, `app/sun_data.py` — ตารางดวงอาทิตย์ (generate)
- `app/plugins/` — registry ของ plugin + ตัว plugin เอง (5 ชนิด: `themes`,
  `auth`, `db`, `cache`, `secrets` — ดูหัวข้อ "สถาปัตยกรรม plugin")
- `app/metrics.py` — latency histogram ต่อ endpoint + `/metrics` (Prometheus)
  **ต้องมี token เสมอ** (ด่านเดียวกับ `/api/v1`) · **label เป็นชื่อ endpoint
  ไม่ใช่ `request.path`** ไม่งั้นคนนอกยิง path มั่ว ๆ ให้ time series ระเบิดได้
  · ค่าที่นับ **เป็นของ process นั้นคนเดียว** (ADR 0031) — ยกเว้นเปิดโหมด
  multiproc (`METRICS_MULTIPROC_DIR` — ADR 0052) ซึ่งรวมทุก worker ของ
  container · `WEB_CONCURRENCY>1` โดยไม่เปิด = ไม่ start
- `app/security_headers.py` — CSP + security header (Talisman), `app/logging_setup.py` — JSON log + request id
- `app/db_engine.py` — **เลือก backend ของฐานข้อมูลจาก scheme ของ `DATABASE_URL`**
  (ADR 0026) ค่าเฉพาะยี่ห้ออยู่ใน `backend.py` ของ plugin ชนิด `db` ไม่ใช่ที่นี่
- `app/db_types.py` — `UTCDateTime` ที่คอลัมน์เวลาทุกตัวต้องใช้ (ดูหัวข้อวินัย dialect)
- `app/soft_delete.py` — ตัวกรอง `deleted_at IS NULL` อัตโนมัติ, `app/purge.py` — จุดเดียวที่ลบจริง
- `app/audit.py` — audit trail แบบเติมได้อย่างเดียว + hash chain (ดูหัวข้อ Audit trail)
  · ตาราง `tdl_audit_lock` มีแถวเดียว ไม่มีข้อมูล เป็นที่ต่อคิวของผู้เขียน (ADR 0035)
- `app/metrics.py` — latency histogram ต่อ endpoint + `/metrics` (**ต้องมี token เสมอ**
  ดูหัวข้อ Performance) · `loadtest/journey.js` + `scripts/loadtest_curve.sh` — ชุด load test
- `app/static/base.css` — เลย์เอาต์ของ core **ห้ามมีสีดิบ** สีมาจากธีมทั้งหมด
- `app/static/app.js` — พฤติกรรมฝั่ง client **ทั้งหมด** (ห้ามมี inline handler ที่อื่น)
- `.pa11yci.json` — รายการหน้าที่ job `a11y` ใน CI สแกน (รวมโหมดมืด/ธีม ocean/ภาษาไทย)
- `Dockerfile` + `.dockerignore` — image ที่รันจริง (multi-stage, ไม่ใช่ root)
  **ไม่ migrate ให้เอง** โดยตั้งใจ · ไลบรารีของ plugin ไม่อยู่ใน image (ADR 0025)
  job `image` ใน CI build จริงแล้วยิงใส่มันทุก push — ดู docs/OPERATIONS.md
- `app/secrets.py` — **ความลับมาจากแหล่งที่ประกาศด้วย scheme ของ `SECRETS_URL`**
  (ADR 0030) `env://` เป็นค่าเริ่มต้นและไม่เปลี่ยนอะไรเลย · `file://` อ่านจาก
  ไฟล์แบบ docker/kubernetes · เรียก **ก่อน `check_secret_key()`** ใน `create_app`
  **"ไม่มีชื่อนั้นในแหล่ง" ตกกลับไป env ได้ แต่ "ถามแหล่งไม่ได้" = ไม่ start**
  · `vault://` เป็น plugin (hvac ใน category ของตัวเอง) อ่านครั้งเดียวตอน start
- `app/proxy.py` — แปลง header ของ reverse proxy **ตามจำนวนชั้นที่ประกาศ**
  (`TRUSTED_PROXY_HOPS` ค่าเริ่มต้น 0 = ไม่เชื่อเลย — ADR 0027) ผูก**ก่อน**
  `init_security_headers` เพราะ Talisman ตัดสิน redirect จาก `request.scheme`
- `deploy/nginx.conf` — reverse proxy หน้า replica หลายตัว (ขา TLS อยู่ใน
  `nginx-tls.conf` · กฎส่งต่อไป app อยู่ใน `nginx-location.conf` ที่ทั้งคู่ include)
  **`Host $http_host` ไม่ใช่ `$host`** — `$host` ตัดพอร์ตทิ้งแล้ว POST บน https
  จะได้ 400 ทุกอัน (Flask-WTF เทียบ Referer กับ url_root เฉพาะคำขอที่เป็น https)
- `compose.yaml` + `compose.{mysql,mariadb,scale,sso}.yaml` — stack ที่รันจริง
  **เลือกยี่ห้อด้วยไฟล์ override ไม่ใช่ตัวแปร** (ไฟล์เดียวเปลี่ยนทั้ง service และ
  `DATABASE_URL` จึงขัดกันเองไม่ได้) · job `stack` ใน CI ยิงจริงทุก push
  **`compose.scale.yaml` ต้องใช้กับยี่ห้อที่ไม่ใช่ SQLite** (ไฟล์เดียวล็อกทั้งไฟล์)
  **`compose.tls.yaml` ต้องต่อจาก `compose.scale.yaml`** (TLS เป็นของ proxy)
  และถือทั้งใบรับรองกับ `HTTPS_ENABLED=1` ไว้ด้วยกัน — เปิดข้างเดียวพังคนละแบบ
- `deploy/systemd/` — unit + timer ของงานลบข้อมูลพ้นระยะ **เป็นไฟล์จริง
  ไม่ใช่ตัวอย่างในเอกสาร** (ติดตั้งด้วย `scripts/install_purge_timer.sh`)
  `ProtectHome=true` ทำให้ **ทุกอย่างที่หน่วยแตะต้องอยู่นอก home** ไม่งั้นได้
  `203/EXEC` ที่ไม่บอกสาเหตุ · `Environment=` ต้องใส่เครื่องหมายคำพูดถ้ามีช่องว่าง
- `scripts/` — สคริปต์ที่รันมือ ไม่ได้ถูกเรียกตอนแอปทำงาน
- `.semgrepignore` — **ขอบเขตของ semgrep ประกาศที่นี่ ไม่ใช่ค่าเริ่มต้นในตัวมัน**
  ซึ่งตัด `tests/` ทิ้งเงียบ ๆ (61 จาก 136 ไฟล์ — เจอตอน P8) · ไฟล์นี้**แทน
  ค่าเริ่มต้นทั้งชุด** `.venv/`/`node_modules/` จึงต้องเขียนเอง · `ci.yml` ห้ามมี
  `--exclude` แล้ว (ขอบเขตสองที่ = ตัวตรวจคำนวณเซตที่คาดหวังผิด)
  · ตัวตัดสินคือ `scripts/check_semgrep.py` ที่อ่านรายงาน `--json --time` แล้ว
  **เทียบเซตไฟล์ที่สแกนจริงกับ `git ls-files` ลบด้วยไฟล์นี้** ไม่ใช่เลขขั้นต่ำ
  (`tests/test_semgrep_gate.py` คุมอีกชั้น — ห้ามใส่ `--error` กลับ มันทำให้
  semgrep ตายก่อนถึงตัวตรวจ)
- `gates.yaml` — **ดัชนี gate ของทั้ง repo** (ADR 0039) — ดัชนี ไม่ใช่แหล่ง:
  ตัวบังคับจริงคือเทสต์กับ job · `tests/test_gates.py` บังคับสองทิศ:
  ทุก job ต้องมี gate และ **ไฟล์เทสต์ทุกไฟล์ต้องถูกตัดสินว่าเป็นของ gate ไหน
  ตัวเดียว** (partition แบบ DATA-CLASSIFICATION) — **เพิ่มไฟล์เทสต์ใหม่ต้องมา
  ลงทะเบียนที่นี่ด้วย** (gate ใหม่ หรือแถวใน `app-behavior-suite`) ไม่งั้นแดง
  · `portable: true` ต้องมี `born_from` · `standard` อ้างได้เฉพาะข้อ ASVS
  ที่ประเมินว่า "ผ่าน" **และหลักฐานของแถวนั้นต้องชี้กลับมาหา gate นี้จริง**
  (อ้างแถวที่มีอยู่แต่หลักฐานไม่หนุน = แดง)
- **ทุก gate ประกาศ `layer:`** — `baseline` (สากล ต้อง portable → `SKILL.md`) ·
  `business` (ข้อตกลงระดับชนิดแอป → `SKILL-TODOLIST.md` ที่ generate จากตัว
  render เดียวกัน) · `internal` (ของ repo นี้) — ADR 0042 · `tests/test_gates.py`
  บังคับความสอดคล้องของชั้น
- **ทุก gate ประกาศ `pillar:` ด้วย** (ADR 0051 — ธรรมนูญ): `security` >
  `performance` > `manageability` > `devx` คือลำดับความสำคัญของโปรเจกต์
  ชนกันเมื่อไหร่ชั้นบนชนะ · ของใหม่จากภายนอกเข้าผ่าน intake (CONTRIBUTING
  กฎข้อ 10) — baseline ห้าม break · แผนงาน governance อยู่ใน
  `docs/ROADMAP-GOVERNANCE.md` (G1–G4 เสร็จแล้ว · เหลือ G5 ชั้น performance รอเจ้าของตัดสิน ADR 0052)
- `SKILL.md` — กฎสากลของ scaffolding **generate มา ห้ามแก้ด้วยมือ**
  (`scripts/build_skill.py` จาก portable gate ใน `gates.yaml`) · กฎใหม่ที่เป็น
  สากล = เพิ่ม gate `portable: true` + `born_from` แล้ว regenerate — ห้ามเขียน
  กฎลงไฟล์นี้ตรง ๆ · **ห้ามมีชื่อไลบรารีของ Flask ในชั้นนี้** (`tests/test_skill.py`
  ตรวจที่ผล render สด จับได้ตั้งแต่ตอนพิมพ์ลง gates.yaml)
- `skill/` — **แพ็กเกจ agent skill ที่ generate ล้วน ห้ามแก้ด้วยมือ** (ADR 0050
  — `scripts/build_agent_skill.py`): frontmatter + render ชั้น baseline ตัวเดียว
  กับ `SKILL.md` + business sheet ใน `reference/` + checker คัดลอกตาม manifest
  ของ overlay · `tests/test_agent_skill.py` เทียบผล generate สด**รวมทั้งเซตไฟล์**
  (ไฟล์แปลกปลอม = แดง) — แก้กฎ = แก้ `gates.yaml` แล้ว regenerate สองที่
- `overlays/flask/` — enforcement ของกฎสากลสำหรับโปรเจกต์ Flask อื่น:
  scan checker 8 ตัว (stdlib ล้วน) + `gates_doctor.py` + `install.py`
  (copy ตาม manifest `overlay.json` — ไม่ครบ = ล้มดัง) · job `scaffold` พิสูจน์
  ทุก push ว่า import ลง repo เปล่าได้จริง **และ repo นี้ผ่าน scan ของ overlay
  ตัวเอง** (dogfood — `scaffold.json` ที่รากคือ config ของการ dogfood นั้น)
  · เพิ่ม portable gate ต้องเพิ่ม entry ใน `overlay.json` ด้วย ไม่งั้น
  `tests/test_overlay.py` แดง
- `docs/GATES-ASVS.md` — crosswalk gate ↔ ASVS **generate มา ห้ามแก้ด้วยมือ**
  (`scripts/build_gates_crosswalk.py`) derive จากหลักฐานใน `ASVS.md` ผ่าน
  partition ของ `gates.yaml` — บอกด้วยว่าแถวไหนผ่านด้วยด่านที่รันทุก push
  และแถวไหนผ่านด้วยเหตุผล/เอกสารเท่านั้น (ความเชื่อมั่นคนละระดับ)
- `docs/comparison/` — การทดลองว่ากฎที่ export ออกไป **เปลี่ยนโค้ดที่ถูกเขียนจริง
  ไหม**: spec กลางหนึ่งชุด (`spec-notes-app.md` — ห้ามแก้ถ้อยคำ ถ้าแก้ต้องวัดใหม่
  ทั้งชุด) · 3 แขน แขนละ 5 แอป · battery เดียวกัน (`scripts/measure_generated.py`
  + `scripts/asvs_probe.py`) · ผลกับข้อมูลดิบอยู่คู่กัน และ `tests/test_asvs_probe.py`
  **บังคับว่าตัวเลขในรายงานต้องตรงกับ JSON** และรายงานต้องบันทึกโมเดล+วันที่+spec
  · **probe ถูกตรวจสองทิศด้วย fixture สามสำนวน** — มันเคยลงโทษโครงที่ *ดีกว่า*
  มาแล้วสี่ครั้ง (helper กลาง · `session.get()` ของ Flask · `SECRET_KEY` ใน
  conftest · `@login_required` ที่อยู่บนบรรทัด decorator ซึ่งไม่อยู่ใน
  `ast.get_source_segment()` ของ FunctionDef)
- `pins/` — **ล็อกไฟล์ของเครื่องมือที่ CI ติดตั้งเอง** (pipenv, pip, semgrep, pa11y-ci)
  ไม่ใช่ dependency ของแอป (ของแอปอยู่ใน `Pipfile.lock`) · ทุก `pip install` ใน
  workflow และ `Dockerfile` ต้องเป็น `--require-hashes -r pins/<ชื่อ>/requirements.txt`
  และฝั่ง node ต้องเป็น **`npm ci` ไม่ใช่ `npm install`** — `npm install pkg@x`
  ตรึงได้แค่ตัวมันเอง ที่เหลือในต้นไม้ยังลอยอยู่ (`tests/test_ci_pinning.py` บังคับ)
  **เพิ่มไดเรกทอรีที่นี่ต้องต่อ Dependabot ให้ด้วย** ไม่งั้นแดง — pin โดยไม่มีใคร
  ขยับคือการแช่ช่องโหว่ไว้ · วิธี regenerate อยู่ใน `pins/README.md`
  · CVE ตรวจด้วย `scripts/audit_pins.py` ใน job `security` (**แดงได้เหมือน core**)
  **ครอบทั้ง `requirements.txt` (pip-audit) และ `package-lock.json` (npm audit)**
  — ด่านที่ครอบภาษาเดียวในไดเรกทอรีที่มีสองภาษา คือด่านที่ชื่อของมันชวนให้เข้าใจ
  ว่าครอบแล้ว · ตรวจ **สองทิศ**: เจอของที่ไม่อยู่ใน `pins/accepted-advisories.txt`
  = แดง และ **ID ที่ยกเว้นไว้แต่ไม่โผล่แล้ว = แดงเหมือนกัน** เพราะการยกเว้นเงียบ
  เสมอเมื่อ ID หายไป รายการที่ไม่มีใครถอดจะกลายเป็นตัวปิดของจริงในวันหนึ่ง
  · เหตุผลของแต่ละข้ออยู่ใน `docs/SECURITY-CADENCE.md` (`tests/test_pins_audit.py`
  บังคับให้ไฟล์กับเอกสารตรงกัน) · **`npm audit` นับตาม package ที่โดน ไม่ใช่ตาม
  advisory** ต้นตออยู่ใน `via` ที่เป็น object เท่านั้น (6 หัวข่าว = 1 เรื่อง)
- `docs/openapi.json` — **ไฟล์ที่ generate มา ห้ามแก้ด้วยมือ** (ดูหัวข้อ API v1)
- `docs/ASVS.md` — self-assessment ต่อ ASVS 5.0 L2 (ดูหัวข้อ ASVS)
- `docs/COMPLIANCE.md` — ดัชนี legal รายประเทศ (G4 — ADR 0051): gate ชั้น
  legal ใช้ id `legal-*` เป็น convention (`tests/test_compliance_index.py`
  บังคับสองทิศ + pillar security) · ประเทศใหม่ = worksheet + gate + แถว
  แบบ additive ตามนิยามขั้นต่ำสี่ข้อในไฟล์
- `docs/SUPPLY-CHAIN.md` — ดัชนีแกน supply chain (G3 — ADR 0051): สมาชิก
  ประกาศที่ gate ด้วย `axis: supply-chain` (16 ตัว) · เพิ่มด่าน supply chain
  ใหม่ต้องติดธง+ลงดัชนี ไม่งั้น `tests/test_supply_chain.py` แดงสองทิศ
- `docs/RISK-ASSESSMENT.md` — วิธีประเมินความเสี่ยง (โอกาส×ผลกระทบ สูตรผลคูณ)
  + ทะเบียน · ระดับต้องตรงสูตร (`tests/test_risk_assessment.py`) · รอบเต็ม
  12 เดือนมีแถวใน SECURITY-CADENCE · `docs/RUNBOOK-BACKUP.md` — backup/restore
  ที่**ซ้อมเป็นเทสต์ทุก push** (`scripts/backup_drill.py` — รันมือกับฐานจริง
  ได้ อ่านต้นฉบับอย่างเดียว) · คีย์ encrypt ต้องแยกจาก backup ของฐานเสมอ
- `docs/ISO27001.md` — self-assessment ต่อ ISO/IEC 27001:2022 ครบ 116 ข้อ
  (G2 — ADR 0051) · outline ตรึงใน `docs/iso27001-2022-outline.json` +
  checksum ในเทสต์ · หลักฐานใน backtick ถูกตรวจเหมือน ASVS และรับสองรูปเพิ่ม:
  `gate <id>` กับรหัสข้ออ้างข้ามกัน (`tests/test_iso27001.py`)
- `docs/ROPA.md` — บันทึกกิจกรรมการประมวลผล + **บัญชีรายการ log** + ปลายทางที่คุยด้วย
  `docs/RUNBOOK-BREACH.md` — ขั้นตอนตอนข้อมูลรั่ว (ทั้งคู่มี `tests/test_ropa.py` คุม)
  `docs/asvs-5.0.0.json` คือมาตรฐานที่ตรึงไว้ **generate มา ห้ามแก้ด้วยมือ**
- `app/templates/` — Jinja2 templates (ทุกหน้า extend `base.html`)
  **ก่อนแตะ template หรือ `base.css` ให้อ่าน `docs/DESIGN.md` ก่อน** — ตัวตน
  ของ UI + โหมดต่อหน้า (Operate/Read/Enter) · งาน UI ต้องประกาศ refine หรือ
  redesign (redesign = แก้ DESIGN.md ใน PR เดียวกัน) · หน้าเต็มใหม่ต้องเพิ่ม
  แถวในตารางโหมดด้วย (`tests/test_design_doc.py` บังคับสองทิศ)
- `app/static/` — `logo.svg` (120px ใช้หน้า login) และ `logo-small.svg` (32px ใช้บน header + favicon)
  ตัวเล็กไม่ใช่ตัวใหญ่ย่อลงมา แต่ตัดรายละเอียดออกให้เหลือแค่เครื่องหมายถูก
- `migrations/` — alembic migration scripts (commit ลง git ด้วย)
  `env.py` ตั้ง `version_table` เป็น `tdl_alembic_version` และเปลี่ยนชื่อตารางเวอร์ชันเก่าให้เอง
- `tests/` — pytest, fixture จาก `conftest.py`
- `pyproject.toml` — config กลางของ ruff/mypy/coverage/interrogate/pytest
  (pytest.ini ถูกยุบเข้ามาแล้ว) threshold เป็น ratchet: ขยับขึ้นได้อย่างเดียว
- `docs/adr/` — การตัดสินใจสำคัญทุกเรื่อง ตัดสินใจใหม่ต้องมี ADR
- commit message เป็น Conventional Commits หัวไม่เกิน 72 ตัว (hook + CI บังคับ)

## Conventions
- Route คืน `render_template`/`redirect` เท่านั้น ไม่คืน raw string
- Query model นอก request ต้องอยู่ใน `with app.app_context():`
- **ทุก route ต้องมี `@login_required`** และ query ต้อง filter ด้วย `user_id=current_user.id` เสมอ
  — ข้อยกเว้นที่ตั้งใจมีเท่านี้: `/login*` · `/lang/<code>`+`/mode/<value>` (ใช้จาก
  หน้า login) · `/privacy` (PDPA ม.23) · `/healthz`+`/readyz` (ของ orchestrator —
  ADR 0048) · `/api/v1`+`/metrics` (ด่าน token คนละชั้น)
- **แถวในลิสต์งานอ่านอย่างเดียว** การแก้อยู่ที่หน้า `/edit/<id>` แยกต่างหาก
  เพราะมีทั้งชื่อ หมวด วันเริ่ม และกำหนดส่ง ใส่ในแถวเดียวแล้วอ่านไม่ออก
- checkbox "แสดงวันเริ่ม" จำไว้ใน session ต้องมี hidden `filters_submitted`
  ในฟอร์มด้วย เพราะ checkbox ที่ไม่ติ๊กจะไม่ถูกส่งมาเลย แยกไม่ออกจากการกดลิงก์อื่น
- **ลบหมวดได้เฉพาะตอนไม่มีงานอยู่เลย** งานที่ทำเสร็จแล้วก็ยังนับ
  (มันยังโผล่ในตัวกรอง "เสร็จแล้ว") ปุ่มบนหน้าเว็บถูก disabled ไว้ด้วย
  แต่การกันจริงอยู่ที่ route — อย่าเชื่อแค่ปุ่ม
- ห้ามใช้ `db.get_or_404()` กับข้อมูลที่มีเจ้าของ — ใช้ `get_todo()`/`get_category()`/
  `get_token()` ของ service ซึ่ง raise `NotFoundError` (→ 404 ไม่ใช่ 403) เมื่อเป็น
  ของคนอื่น เพื่อไม่ให้รู้ว่า id นั้นมีจริง (ADR 0004)
- `create_app` **ไม่เรียก** `db.create_all()` แล้ว — schema มาจาก migration เท่านั้น
  (เทสต์สร้างตารางเองใน fixture `app`)
- **`TestConfig` ใน `tests/conftest.py` ต้อง `class TestConfig(Config)` เสมอ**
  ห้ามเขียนใหม่แบบ standalone — ลืม copy ค่าใหม่จาก `Config` มาแล้ว 4 ครั้ง
  (LANGUAGES, RATELIMIT_STORAGE_URI, THEMES, LOG_LEVEL) เทสต์จะพังแบบงง ๆ
  เพราะ config ขาดไปเฉย ๆ ไม่ใช่เพราะโค้ดผิด — สืบทอดแล้ว override เฉพาะที่ต่าง
- ส่งข้อความจาก template ไปให้ JS ใช้ `data-*` attribute (Jinja escape ให้เอง)
  ไม่ต้อง `|tojson` แล้วเพราะไม่มี inline script เหลือ — ดูหัวข้อ CSP ด้านล่าง
- **ตั้งชื่องาน/หมวดในเทสต์อย่าให้ตรงกับข้อความบน UI** เช่น "ยังไม่เสร็จ"/"เสร็จแล้ว"
  เป็น label ของลิงก์ตัวกรองที่อยู่ในหน้าเสมอ `assert ... not in resp.data` จะพังทันที
- **ทุก `<form method="post">` ต้องมี `{{ csrf_field() }}` หรือ hidden input `csrf_token`**
  `CSRFProtect` คุมทั้งแอป ลืมใส่แล้ว form นั้นจะได้ 400 ทันที
- เทสต์ทั่วไปปิด CSRF (`WTF_CSRF_ENABLED = False` ใน `TestConfig`) ตัว CSRF มีเทสต์แยกใน
  `tests/test_csrf.py` ที่เปิดใช้จริงผ่าน fixture `csrf_app` — ห้ามลบไฟล์นั้นทิ้ง
  ไม่งั้นจะไม่มีอะไรจับได้เวลา `csrf.init_app()` หลุด

## Mutation test — บังคับ ไม่ใช่ทางเลือก

**เทสต์ใหม่ทุกตัวต้องถูกพิสูจน์ว่าจับของจริงได้ ก่อนถือว่าเสร็จ**
วิธี: พังโค้ดที่เทสต์นั้นอ้างว่าคุ้มอยู่ทีละจุด → เทสต์ต้องแดง → คืนโค้ดกลับ
ถ้าพังแล้วยังเขียว แปลว่าเทสต์นั้นไม่ได้ทดสอบอะไรเลย ให้แก้เทสต์ ไม่ใช่ปล่อยผ่าน

ต้องพังให้ตรงกับสิ่งที่เทสต์อ้าง — ลบ `aria-label` ออกจริง ๆ ไม่ใช่แค่แก้ตัวแปร
ข้าง ๆ และคืนโค้ดกลับด้วย `cp` จากสำเนา ไม่ใช่แก้มือย้อน (พลาดง่าย)
ตรวจว่าคืนครบด้วย `git diff` หรือ `diff -r` ทุกครั้ง

ที่จับได้มาแล้วเพราะทำขั้นนี้:
- เทสต์ลำดับการเรียงที่ผ่านทั้งที่ถอด `order_by` ออก (แก้: ใส่งานสลับลำดับที่คาดไว้)
- เทสต์บันทึก preferences ที่ผ่านทั้งที่ไม่ได้เขียน session (แก้: seed session ค้างไว้ก่อน)
- `resolve_mode()` ที่ผ่านทั้งที่เป็น stub (แก้: เทสต์ end-to-end หาโซนที่ตอนนี้เป็นกลางคืน)
- regex จับ `#, fuzzy` ที่พลาด `#, fuzzy, python-format`

**API มีตัว fuzz ให้ด้วย** `tests/test_api_fuzz.py` ยิงคำขอที่สร้างจาก
`docs/openapi.json` เอง จับของที่เทสต์ซึ่งคนเขียนเองมองข้าม — รอบแรกจับได้สามอย่าง
ที่กระทบหน้าเว็บด้วย (ตัวกรองวันที่ย่อยไม่ได้ → 500, id เกิน 64 บิต → 500,
คำขอที่ตกตั้งแต่ชั้น routing ได้ HTML) **เพิ่ม endpoint ใหม่แล้วมันครอบให้เอง**

**เทสต์ที่ผลลัพธ์ขึ้นกับเครื่อง ต้องปลอม input เอง** อย่าพึ่งว่าเครื่องที่รันมีอะไร
(`available_timezones()` มี `localtime` บน Ubuntu แต่ไม่มีบน Gentoo →
เขียวบนเครื่อง dev แดงบน CI ดู `test_pseudo_zones_are_never_offered`)

### session ในเทสต์: สองกับดักที่ทำให้เทสต์เขียวโดยไม่ได้ทดสอบอะไร

1. **`with app.app_context():` ซ้อนใน context ของ fixture = session คนละตัว**
   object ที่ fixture สร้างไว้ผูกอยู่กับ session ข้างนอก การแก้ค่าบนมันแล้ว commit
   ในชั้นใน **ไม่ถูกเขียนลงฐานข้อมูลเลย** ทั้งที่ค่าในหน่วยความจำเปลี่ยนแล้ว
   → fixture ที่ `yield` object ให้ ต้องเปิด context ค้างไว้เอง แล้วตัวเทสต์ห้ามเปิดซ้อน
   (ดูหัวเรื่องของ `tests/test_services.py`)
2. **`with app.app_context():` ที่ค้างอยู่ตอนยิง HTTP ทำให้ทุก request ใช้ `g` ก้อนเดียวกัน**
   Flask จะ push app context ใหม่ให้ request **ก็ต่อเมื่อยังไม่มีของแอปนั้นค้างอยู่**
   ถ้า fixture เปิดค้างไว้ `g` จึงถูกใช้ร่วมกันข้าม request — และ Flask-Login
   cache `current_user` ไว้ใน `g` ผลคือ **ผู้ใช้ของ request ก่อนหน้าติดมาให้
   request ถัดไป** เทสต์ที่ login เป็นคนละคนสองรอบจะกลายเป็นคนเดิมทั้งสองรอบ
   → fixture ที่เทสต์ฝั่งเว็บใช้ ต้อง**ปิด context ก่อน return** (คืน id ไม่ใช่ object)
   ส่วน fixture ที่ยัง `yield` object ให้ ใช้ได้เฉพาะเทสต์ที่เรียก service ตรง ๆ
   (ดูสอง fixture ใน `tests/test_rbac.py` ที่แยกกันด้วยเหตุผลนี้)
3. **การอ่านซ้ำจาก session ใหม่ ไม่ได้พิสูจน์ว่า commit แล้ว** เพราะ sqlite
   `:memory:` ใช้ connection เดียวร่วมกัน (StaticPool) session ใหม่จึงยังอยู่ใน
   transaction เดิมและเห็นของที่ยังไม่ commit → ต้อง `db.session.remove()`
   (rollback + ปิด session) ก่อนอ่าน ถ้าอยากพิสูจน์ว่าข้อมูลลงจริง
   ถอด `db.session.commit()` ออกจาก service แล้วเทสต์ต้องแดง ไม่งั้นแปลว่ายังไม่ได้พิสูจน์

## ลำดับด่านของ request (สำคัญตอนอ่าน status code)

`CSRFProtect` ทำงานใน `before_request` จึง**ตัดก่อน** `@login_required` เสมอ
POST ที่ทั้งไม่มี token และไม่ได้ login จะได้ **400 (CSRF) ไม่ใช่ 302 (ไป login)**

| สถานะคำขอ | ผลลัพธ์ |
|---|---|
| ไม่มี token + ไม่ได้ login | 400 |
| มี token ถูกต้อง + ไม่ได้ login | 302 → `/login` |
| มี token + login แล้ว + ของคนอื่น | 404 |
| POST `/login` ผิดรหัสเกินโควตา (ต่อ IP หรือต่อชื่อผู้ใช้) | 429 |
| POST `/login` ถูก แต่เปิดการยืนยันสองขั้นไว้ | 302 → `/login/verify` (ยังไม่ถือว่า login) |
| GET หน้าอื่นระหว่างรอขั้นที่สอง | 302 → `/login` (ยังไม่มีสิทธิ์อะไรเลย) |
| session หมดอายุ / รหัสผ่านถูกเปลี่ยนจากที่อื่น | 302 → `/login` พร้อม flash |
| บัญชีถูกระงับ (ม.34) ระหว่างมี session | 302 → `/login` พร้อม flash (ตัดที่คำขอถัดไปทันที) |
| POST `/login` ของบัญชีที่ถูกระงับ (รหัสถูกก็ตาม) | 403 + audit `auth.login_suspended` |
| เข้าหน้าผู้ดูแลโดยไม่ใช่ admin | 403 (ไม่ใช่ 404 — ดู ADR 0022) |

ทั้งสองด่านยังอยู่ครบ แค่ CSRF มาก่อน — คนนอกขอ token จากหน้า `/login` ได้ก็จริง
แต่ยิงต่อไปก็ยังติด `@login_required` อยู่ดี

ผลที่ตามมาเวลาแก้บั๊ก:
- เห็น **400** ที่ POST อย่าเพิ่งสรุปว่า "ไม่ได้ login" ให้เช็ค `csrf_token` ใน form ก่อน
- อย่าเขียนเทสต์ที่ assert 302 สำหรับคนที่ยังไม่ login **บนแอปที่เปิด CSRF** โดยไม่แนบ token
  (เทสต์ส่วนใหญ่ปิด CSRF ไว้ จึงได้ 302 ตามปกติ — ต่างกันตรงนี้)

## Environment
- ต้องมี `.env` ที่มี `SECRET_KEY` ไม่งั้นแอปจะไม่ start (ดู `.env.example`)
- `SECRET_KEY` **ไม่มีค่า default โดยตั้งใจ** และต้องยาว ≥ 32 ตัว — ตรวจใน `check_secret_key()`
  ห้ามใส่ default กลับเข้าไปเพื่อความสะดวก มีเทสต์ใน `tests/test_config.py` ดักไว้
- เปลี่ยน `SECRET_KEY` แล้ว session และ CSRF token เดิมใช้ไม่ได้ ทุกคนต้อง login ใหม่
- `.env` ถูก gitignore — `.env.example` เป็นตัวที่ commit
- `DATA_ENCRYPTION_KEY` (base64 ของ 32 ไบต์ — ADR 0046) คีย์ encrypt ความลับ
  TOTP · แยกจาก `SECRET_KEY` โดยตั้งใจ (หมุนคนละจังหวะ) · อยู่ใน `CORE_SECRETS`
  จึงมาจาก secrets source ได้ · **ทำหาย = ความลับ TOTP อ่านไม่ได้ถาวร**
  ไม่มีคีย์ plugin ปิดตัวเอง (enroll ไม่ได้ แต่แอปไม่พัง)
- `AUTH_PROFILES` (ADR 0047) — auth plugin เดียวหลายชุด config:
  `"oidc:corp,ldap:hq"` ลำดับประกาศ = ลำดับลอง · คีย์ต่อ profile
  (`OIDC_CORP_ISSUER`) **ไม่ตกกลับคีย์เปล่า** · ปฏิเสธ = สิ้นสุด fallback
  เฉพาะ "ติดต่อไม่ได้" · config ผิด/ซ้ำ/ชี้ของที่ไม่มี = แอปไม่ start
- `LOGIN_RATE_LIMIT` (default `5 per minute; 20 per hour`) และ `RATELIMIT_STORAGE_URI`
  (default `memory://`) ปรับผ่าน env ได้
- **`RATELIMIT_STORAGE_URI` ตามหลัง `CACHE_URL` โดยค่าเริ่มต้น** (P5-07) — ตั้ง store
  ที่แชร์ได้ครั้งเดียวแล้วโควตาย้ายตามเอง ตั้งแยกได้ถ้าตั้งใจให้ counter อยู่คนละที่
- **`memory://` นับแยกต่อ process** — รันหลาย worker (gunicorn ฯลฯ) แล้วเพดานจริง
  จะเป็น N เท่าของที่ตั้งไว้ **ตอนนี้แอปเตือนตอน start ถ้ารู้ว่า store ไม่แชร์**
  (`app/cache.py::warn_if_counters_are_not_shared`) ไม่ refuse to start เพราะ
  `memory://` ถูกต้องสำหรับ dev/single worker — สิ่งที่ผิดคือการไม่รู้ว่าอยู่สภาพไหน
  store ที่เราไม่มี cache plugin ให้ (memcached ฯลฯ) จะ**ไม่ถูกเดา**ว่าไม่แชร์

## กำหนดส่ง วันเริ่ม และตัวกรอง
- **`Todo.due_date` ใน DB เป็น UTC แบบ naive เสมอ** เหมือน `created_at`/`updated_at`
  ค่าที่ผู้ใช้กรอกจาก `<input type="datetime-local">` เป็นเวลาท้องถิ่นของเขา
  ต้องผ่าน `tz.to_utc()` ก่อนเก็บ และ `tz.to_local()` ก่อนแสดง (ดู `app/tz.py`)
  ใน template ใช้ `todo.due_local` ไม่ใช่ `todo.due_date`
- `Todo.is_overdue` เทียบ UTC กับ UTC จึงไม่ขึ้นกับ timezone ของใคร
  ส่วน `is_due_today` ต้องเทียบวันตามเวลาท้องถิ่นของ **เจ้าของงาน** ไม่ใช่ UTC
  งานที่ `done=True` ไม่นับว่าเลยกำหนด และ `is_due_today` เป็น False ถ้าเลยกำหนดไปแล้ว
  (ไม่ให้ขึ้นป้ายซ้อนกันสองอัน)
- property พวก `due_local`/`is_overdue` แตะ `todo.user` จึงเรียกนอก app context ไม่ได้
  (lazy-load ไม่ได้) เทสต์ต้องอ่านค่าใน `with app.app_context():`
- **`batch_alter_table` บน SQLite ทำข้อมูลพังตอนเปลี่ยนชนิดคอลัมน์เป็น DATETIME**
  alembic คัดลอกข้อมูลด้วย `CAST(col AS DATETIME)` และ DATETIME มี NUMERIC affinity
  `'2026-08-02'` จึงกลายเป็นเลข `2026` — **วิธีแก้: อ่านค่าเก็บไว้ก่อน ปล่อยให้
  batch alter ทำลาย แล้ว UPDATE เขียนกลับด้วยพารามิเตอร์ข้อความ** (ตัวอย่างจริงอยู่ใน
  migration `89cd0c572bf9` ซึ่งถูกยุบไปแล้วตอน P5-02 — หาได้ในประวัติ git)
  **ทุกครั้งที่ migration แตะข้อมูลเดิม ให้สำรอง `instance/todolist.db` ก่อนรัน**
- เรียงลำดับ: งานที่มีกำหนดส่งขึ้นก่อน (ใกล้ครบกำหนดสุดก่อน) แล้วค่อยงานไม่มีกำหนด
  เรียงตาม `created_at` ล่าสุดก่อน
- `Todo.start_date` เก็บแบบเดียวกับ `due_date` (UTC naive) มี `start_local` คู่กัน
  เป็นข้อมูลประกอบเท่านั้น **ตัวกรองตามวันดูจาก `due_date` อย่างเดียว**
- ตัวกรองรับผ่าน query string: `?status=all|active|completed`, `?category=<id>|none`
  และ `?when=all|upcoming|today|tomorrow|range` (+ `within` นาที, `date_from`/`date_to`)
  ค่าที่ไม่รู้จักใน `status`/`when`/`within` fallback เป็นค่าเริ่มต้น
  แต่ `category` ที่เป็นของคนอื่นตอบ 404
- **ชื่อพารามิเตอร์ต้องเป็น `date_from`/`date_to` ไม่ใช่ `from`/`to`**
  เพราะ `from` เป็น keyword ของ Python ส่งเข้า `url_for()` ตรง ๆ ไม่ได้
- ตรรกะตัวกรองอยู่ใน `app/filters.py` คำนวณช่วงเป็นเวลาท้องถิ่นก่อน
  แล้วค่อย `tz.to_utc()` ตอนไปเทียบกับ DB — งานที่ไม่มี `due_date` ถูกกรองออก
  เมื่อมีการเลือกช่วง เพราะตอบคำถาม "ครบกำหนดช่วงนี้ไหม" ไม่ได้
- `Upcoming` นับจาก **ตอนนี้** ไปข้างหน้าตามช่วงที่เลือก งานที่เลยกำหนดแล้วไม่นับ
  ถ้าช่วงคร่อมเที่ยงคืนก็จะรวมงานของวันถัดไปด้วย (ตั้งใจ — "ภายใน 8 ชม." คือ 8 ชม. จริง)
- เลือกช่วงเองโดยใส่แค่ `date_from` = ครอบทั้งวันนั้น (00:00–23:59)
- `_parse_due_date()` raise `ValueError` ถ้ารูปแบบผิด — route ต้อง catch แล้ว flash
  (browser ส่งมาถูกเสมอ แต่คนยิง POST ตรง ๆ ส่งอะไรมาก็ได้)

## หลายภาษา (i18n)
- ใช้ Flask-Babel (gettext) ภาษาที่รองรับประกาศใน `config.LANGUAGES` ค่าเริ่มต้นคือ `en`
- **ข้อความในโค้ดต้องเป็นภาษาอังกฤษเสมอ** เพราะ msgid คือภาษาอังกฤษ
  ภาษาไทยอยู่ใน `app/translations/th/LC_MESSAGES/messages.po` — ห้ามเขียนไทยลงโค้ดตรง ๆ
- ใช้ `gettext as _` ในไฟล์ `.py` และ `{{ _('...') }}` ใน template
  ใช้ `lazy_gettext` เฉพาะข้อความที่ประกาศตอน import (ยังไม่มี request) เช่น `login_message`
- นับจำนวนใช้ `ngettext` — ไทยมี `nplurals=1` มี `msgstr[0]` อย่างเดียว
- ส่งค่าเข้าข้อความใช้ named placeholder `%(name)s` ไม่ใช่ f-string
  ไม่งั้น pybabel ดึง msgid ไม่ได้และผู้แปลสลับลำดับคำไม่ได้

### workflow เวลาเพิ่ม/แก้ข้อความ
```
pipenv run pybabel extract -F babel.cfg -k _l -k _ -k ngettext:1,2 -o messages.pot .
pipenv run pybabel update -i messages.pot -d app/translations
# แก้คำแปลใน app/translations/*/LC_MESSAGES/messages.po
pipenv run pybabel compile -d app/translations
```
- **`tests/test_i18n.py` บังคับสองเรื่องที่ต่างกัน**: catalog ไม่มีช่องว่าง/fuzzy
  **และ catalog ครอบ msgid ที่มีในโค้ดครบ** — ข้อหลังเพิ่มทีหลัง (P7-03b) เพราะ
  ข้อความของ SSO/LDAP ทั้งชุดจาก Phase 5 ไม่เคยถูก extract เข้า catalog เลย
  ผู้ใช้ภาษาไทยเห็นภาษาอังกฤษมาตลอดโดยไม่มีอะไรฟ้อง
  · ด่านนั้นอ่านด้วย API ของ babel และ **มีเทสต์อีกตัวเทียบว่ามันอ่านชุดเดียวกับ
  คำสั่งที่คนพิมพ์จริง** — ด่านที่ตรวจของคนละชุดกับที่ใช้อยู่คือด่านที่เขียวเปล่า ๆ
- **ไฟล์ `.mo` ถูก commit ลง git ด้วย** เพื่อให้ clone แล้วรันได้เลย
  แก้ `.po` แล้วต้อง compile ใหม่ ไม่งั้นคำแปลจะไม่เปลี่ยน — `tests/test_i18n.py` ดักไว้
- **ระวัง `#, fuzzy`** — `pybabel update` จะเดาคำแปลให้จากข้อความที่คล้ายกัน
  (เคยเดา "First name" เป็น "ชื่องาน" มาแล้ว) และ `compile` จะข้ามรายการ fuzzy ไป
  ทำให้ตกกลับเป็นภาษาอังกฤษเงียบ ๆ ต้องแก้คำแปลแล้วลบบรรทัด `#, fuzzy` ออก
  ตรวจแค่ `msgstr ""` ไม่พอ — มีเทสต์เช็คทั้งสองอย่าง
- เพิ่มภาษาใหม่: เติมใน `config.LANGUAGES` แล้ว `pybabel init -i messages.pot -d app/translations -l <รหัส>`

### ลำดับการเลือกภาษา (ดู `app/i18n.py`)
`?lang=` → session → `User.locale` → `Accept-Language` → `en`
session มาก่อนโปรไฟล์เพื่อให้กดสลับแล้วเห็นผลทันที และการกดสลับจะบันทึกลงโปรไฟล์ให้ด้วย

### สิ่งที่ไม่ได้แปล
- ชื่องานและชื่อหมวดเป็นข้อมูลของผู้ใช้ ไม่ผ่าน gettext
- หมวดตั้งต้นสร้างตาม `--lang` ของ `flask create-user` แล้วคงที่ ไม่เปลี่ยนตามภาษาที่เลือกทีหลัง
- **ข้อความของ CLI เป็นภาษาอังกฤษตายตัว ไม่ผ่าน gettext** เพราะ CLI รันนอก request context
  จึงไม่มีข้อมูลว่าจะใช้ภาษาไหน — `select_locale()` กันไว้ด้วย `has_request_context()`
  ถ้าเรียกแปลนอก request จะได้ภาษาเริ่มต้นแทนที่จะ RuntimeError (`tests/test_i18n.py` ดักไว้)

## สถาปัตยกรรม plugin

เป้าหมายระยะยาวคือให้ todolist เป็น core + plugin แบบ Moodle — ตอนนี้มี **5 ชนิด**
บนดิสก์แล้ว (`themes` · `auth` · `db` · `cache` · `secrets`) registry เดียวกันหมด

**สัญญาที่ห้ามผิด**
- core **ห้าม hardcode ชื่อ plugin ตัวใดตัวหนึ่ง** — รู้แค่วิธีค้นหา
  (`tests/test_plugins.py` grep หาชื่อธีมที่ไม่ใช่ core ในโค้ด core ทั้งหมด)
- plugin หนึ่งตัว = หนึ่งไดเรกทอรีใต้ `app/plugins/<ชนิด>/<ไอดี>/` + `plugin.json`
  ชื่อไดเรกทอรีคือไอดี
- **เพิ่ม plugin = วางไดเรกทอรี ลบ plugin = ลบไดเรกทอรี** ไม่ต้องแก้ core
  และไม่ต้อง restart (registry อ่านดิสก์ทุกครั้ง แอปเล็กพอที่จะไม่ต้อง cache)
- ถอน plugin ที่มีคนใช้อยู่แล้วระบบต้องไม่พัง — ค่าที่เก็บไว้ใน `User.theme`
  ไม่ถูกลบ แค่ไม่ผ่าน `theme_is_supported()` จึงตกกลับไปใช้ธีม core
- ธีม `system` เป็น core (`"core": true` ใน manifest) **ต้องมีเสมอ**
  ถ้าหายแอปจะไม่ start (`plugins.check_installation()` เรียกใน `create_app`)
- plugin ที่ต้องเก็บข้อมูลเพิ่มต้องดูแล table ของตัวเอง ห้ามแก้ table ของ core
  (ทำจริงแล้วใน Phase 4 — ดูหัวข้อ "plugin ที่มีข้อมูลของตัวเอง")

### plugin ที่มีข้อมูลของตัวเอง (Phase 4 — ADR 0023)
- วาง `models.py` ในไดเรกทอรีของ plugin **ชื่อตารางต้องขึ้นต้น `tdl_<ชนิด>_<ไอดี>_`**
  (บังคับตอนโหลด แอปไม่ start ถ้าผิด) core รู้ว่าตารางไหนของใครจากการดูว่า
  มีอะไรโผล่เข้า metadata ระหว่าง import ไม่ใช่จากการประกาศซ้ำใน manifest
- **ตารางของ plugin อยู่นอกสาย migration ของ core** — `include_object` ใน
  `migrations/env.py` กรองออกทั้ง table/index/constraint ไม่งั้นวาง plugin แล้ว
  `flask db migrate` ตัวถัดไปจะสร้างให้ และ**ถอน plugin แล้วตัวถัดไปจะ drop ทิ้งเงียบ ๆ**
- **หลัง `flask db upgrade` ต้อง `flask plugin-install <ชนิด>/<ไอดี>` ด้วย**
  ไม่งั้น plugin นั้นถูกข้ามไปเงียบ ๆ (core เช็ค `is_installed()` ก่อนใช้งานเสมอ
  — ตารางที่ยังไม่ถูกสร้างแปลว่ายังไม่มีใครลงทะเบียน จึงข้ามได้อย่างถูกต้อง
  ถ้าไม่เช็ค หน้า login จะพังทั้งหน้าด้วย `no such table`)
- วงจรชีวิตเป็นของ plugin เอง: `flask plugin-install` / `plugin-uninstall`
  (ถอน = ลบตารางจริง ไม่ใช่ soft delete — ข้อมูลของความสามารถที่ไม่มีอยู่แล้ว
  ไม่มีใครดูแล และ purge job ของ core ก็ไม่รู้จักตารางนั้น)
- **ไลบรารีของ plugin ประกาศใน manifest ของตัวเอง** (`requires.pip`) และติดตั้ง
  แยก category ของ pipenv ที่**คำนวณจากคีย์** (`auth/totp` → `plugin-auth-totp`)
  — ถอน plugin แล้ว supply chain ของมันต้องหายไปด้วย ไม่ใช่ค้างอยู่ใน `[packages]`
  ตลอดไป มีเทสต์บังคับว่าไลบรารีของ plugin ห้ามโผล่ใน `[packages]` ของ core
- **โค้ดของจุด plug import ได้แค่ stdlib + ของที่ core แบกอยู่แล้ว + ที่ manifest
  ตัวเองประกาศ** (`tests/test_plugins.py` สแกน AST บังคับ ทุกชั้นรวมส่วนเสริม)
  **plugin แม่ประกาศแทนส่วนเสริมไม่ได้** — แต่ละจุด plug ถูกตัดสินด้วย manifest
  ของตัวเองเท่านั้น ไม่งั้นคำว่า "ถอดไดเรกทอรีแล้ว supply chain หายไปด้วย" ไม่จริง
  (ของที่ core มีอยู่แล้วเช่น `sqlalchemy` ไม่ต้องประกาศ เพราะถอด plugin ก็ถอดมันไม่ได้)
- **ไม่มีไลบรารี = ปิดตัวเอง ไม่ใช่พัง** — ใช้กับ **plugin เต็มตัวด้วย** ไม่ใช่แค่
  ส่วนเสริม: `plugins.requirements_met()` เช็ค `requires.pip` ของ manifest
  ตัวที่ขาดหายจากรายการที่ใช้งานได้ (เช่น totp หายจาก `mfa.available()`)
  พร้อม warn ครั้งเดียวต่อ process — ADR 0046 ทำให้ auth/totp มีไลบรารีจริง
  เป็นครั้งแรก (`cryptography`) job `bare` จึงเดินเส้นนี้ทุก push
  · `import` ที่ล้มเป็นสถานะปกติที่ออกแบบไว้
  (หลักเดียวกับตารางที่ยังไม่ถูกสร้าง) เส้นทาง "ไม่มีของเสริม" ต้องเป็นโค้ด
  เส้นเดียวกับตอนที่ยังไม่เคยมี ไม่ใช่เส้นทางสำรองที่เขียนเพิ่ม
- **ชั้นข้อมูลของคอลัมน์ plugin ประกาศใน `models.py` ของ plugin เอง**
  (`AUDIT_POLICIES`) ไม่ใช่ใน `app/audit.py` — ชื่อคอลัมน์ของ plugin ที่ไปอยู่ใน
  โค้ด core จะกลายเป็นขยะค้างทันทีที่ถอน plugin (และเทสต์ห้ามไว้อยู่แล้ว)
- ข้อมูลของ plugin ยังอยู่ใต้กติกาเดิมทุกข้อ: ถูก audit อัตโนมัติ, ต้องถูกจำแนกใน
  `docs/DATA-CLASSIFICATION.md`, และอยู่ใต้ `tests/test_write_discipline.py`

### ส่วนเสริมของ plugin (Phase 4.5 — ADR 0025)
- **กติกาเดิมใช้ซ้อนอีกชั้น**: `app/plugins/<ชนิด>/<ไอดี>/enhancements/<ไอดีส่วนเสริม>/`
  ที่มี `plugin.json` + `provide.py` — คีย์คือ `auth/totp#qr-segno`
- manifest ประกาศ `provides` (ชื่อความสามารถ) และ `requires.pip`
  **host ขอด้วยชื่อความสามารถ ไม่ใช่ไอดี**: `plugins.capability(plugin, "qr")`
- **ส่วนเสริมห้ามมี `models.py`** (บังคับตอนค้นหา) — ถ้ามีข้อมูลของตัวเอง
  การสลับไป implementation ตัวอื่นจะกลายเป็นการย้ายข้อมูล ไม่ใช่การ plug
- **ไลบรารีขาด/`ImportError` = ปิดตัวเองเงียบ ๆ** ส่วนข้อผิดพลาดอื่น (syntax ผิด,
  ตัวแปรไม่มี) **ต้องดัง** เพราะเป็นบั๊กของ plugin ไม่ใช่สถานะปกติ
- **มีหลายตัวที่ `provides` เหมือนกันแต่ config ไม่ได้เลือก = ปิดทั้งหมด + log เตือน**
  (`PLUGIN_PICKS="auth/totp#qr=qr-segno"`) การเดาให้แปลว่าวางไดเรกทอรีเพิ่ม
  แล้วพฤติกรรมของระบบเปลี่ยนโดยไม่มีใครสั่ง
- **ถ้ามี pick อยู่ pick ชนะเสมอ แม้จะเหลือผู้ให้บริการตัวเดียว** — ไม่งั้นวันที่ตัวที่
  ถูกเลือกใช้ไม่ได้ (ปิดเพราะ CVE/ไลบรารีหาย) ตัวที่ไม่ได้ถูกเลือกจะถูกเลื่อนขึ้นมาแทนเงียบ ๆ
  คือการปิดตัวหนึ่งกลายเป็นการ *เปิด* อีกตัวหนึ่งโดยไม่มีใครสั่ง
- **สัญญาของความสามารถเป็นเรื่องของ host** registry ไม่รู้ว่าแต่ละความสามารถต้องมี
  ฟังก์ชันอะไร host จึงต้องตรวจเองแล้ว raise `PluginError` ที่บอกว่าใครผิดสัญญาข้อไหน
- ส่วนเสริมที่มี manifest แต่ไม่มี `provide.py` = แพ็กมาไม่ครบ → แอปไม่ start

### job `dialects`: ยิงชุดเทสต์ทั้งชุดใส่ MySQL กับ MariaDB จริง (Phase 5 — P5-04)
- CI มี matrix `mysql:8` + `mariadb:11` เป็น service container · `fail-fast: false`
  เพราะ "พังยี่ห้อเดียว" กับ "พังทั้งสอง" เป็นคนละอาการ
- **เลือกยี่ห้อตอนรันเทสต์ด้วย `TEST_DATABASE_URL` ไม่ใช่ `DATABASE_URL`**
  (`.env` ของเครื่องต้องไม่มีผลกับเทสต์ — หลักเดียวกับ `RATELIMIT_ENABLED`)
  ยิงเองในเครื่องได้: `TEST_DATABASE_URL="mysql+pymysql://u:p@host/db" pipenv run pytest`
- **ทุก fixture ที่สร้างแอปต้องเดินผ่าน `_app_with_tables()`** ห้ามเรียก
  `db.create_all()` เอง — `sqlite:///:memory:` ตายไปพร้อม engine จึงให้อภัยการ
  ลืมเก็บกวาดมาตลอด แต่ยี่ห้ออื่นเก็บตารางไว้ข้ามเทสต์ ข้อมูลของตัวก่อนหน้าจะ
  ค้างมาให้ตัวถัดไปเห็น (เจอจริงตอนเปิด job นี้: `Duplicate entry 'tester'`)
- **แอปที่มีชีวิตข้ามเทสต์ใช้ฐานร่วมกับ fixture ไม่ได้** — teardown ของเทสต์อื่น
  จะลบตารางที่มันยังใช้อยู่กลางคัน `tests/test_api_fuzz.py` จึงตรึงเป็น SQLite เสมอ
  (ชุดนั้นตรวจสัญญาของ API เทียบ spec ซึ่งไม่ขึ้นกับยี่ห้อ)
- เทสต์ที่เป็นพฤติกรรมของยี่ห้อเดียวจริง ๆ (`PRAGMA`) ใช้ `skipif` **อย่างเปิดเผย**
  ไม่ใช่ `try/except` — pytest รายงานจำนวนที่ข้ามทุกครั้ง

### job `bare`: "ถอดแล้วไม่พัง" ต้องวัดได้ ไม่ใช่แค่ตั้งใจ
- CI รันชุดเทสต์ **สองรอบ** — job `test` ติดตั้ง category ครบ, job `bare` รัน
  `pipenv sync --dev` เฉย ๆ (= สภาพของทุกคนที่เพิ่ง clone) แล้วต้องเขียว
- **เทสต์ที่ต้องมีไลบรารีของ plugin ต้องมี `@pytest.mark.plugin_deps`**
  job `bare` รันด้วย `-m "not plugin_deps"` — ลืมมาร์กแล้ว job นั้นแดง (ตั้งใจ)
  แต่ **ห้ามใช้ `importorskip`** เพราะจะทำให้ job `test` ข้ามเทสต์นั้นเงียบ ๆ ด้วย
  ตอนที่ไลบรารีหาย ซึ่งคือกรณีที่เราต้องการให้มันแดงที่สุด
- จำลองบนเครื่อง: ย้าย package ออกจาก `.venv/lib/python3.13/site-packages/`
  ชั่วคราวแล้วรัน `pipenv run pytest -q -m "not plugin_deps"` (คืนกลับให้ครบด้วย)
- `pip-audit`/SBOM แยกตาม category แล้ว: core อยู่ใน job `security`/`sbom` (แดงได้)
  ของ plugin อยู่ใน job `plugin-audit` ซึ่ง **ไม่ทำให้ pipeline แดง** แต่ยิง
  `::warning::` + สรุปของ run เพราะคำตอบของ CVE ที่ถอดได้คือ "ถอดก่อน"

### สวิตช์ปิดตอน runtime (`DISABLED_PLUGINS`)
- ปิดจุด plug ได้ทุกชั้นด้วยคีย์เดียวกับที่ `flask plugin-list` แสดง
  (`themes/ocean`, `auth/totp`, `auth/totp#qr-segno` และ **auth profile ทีละตัว**
  ด้วย `auth/oidc:corp` — ADR 0047) คั่นด้วยจุลภาค ไม่ต้องแก้โค้ด
  ไม่ต้องรอ deploy — มีไว้สำหรับวันที่ CVE ของไลบรารีใน plugin ออกตอนบ่ายสาม
- **ปิดแล้วต้องเหมือนไม่เคยวางไดเรกทอรีลงไป** การกรองอยู่ที่ `discover()` กับ
  `enhancements()` ที่เดียว ห้ามเพิ่มเงื่อนไข "ถ้าปิดอยู่ให้..." กระจายตามที่ใช้งาน
  เพราะนั่นคือการสร้างสถานะที่สามที่ไม่มีเทสต์ตัวไหนเคยเดินผ่าน
- **สวิตช์ปิดโค้ด ไม่ได้ปิดข้อมูล** — `load_models()`/`owned_tables()` และ
  `plugin-install`/`plugin-uninstall` ใช้ `installed_on_disk()`/`find_on_disk()`
  ซึ่ง**ไม่สนสวิตช์** ถ้าเผลอเปลี่ยนไปใช้ `installed()`/`find()` ตารางของ plugin
  ที่ถูกปิดจะกลายเป็นตารางไม่มีเจ้าของ แล้ว `flask db migrate` ตัวถัดไปของ core
  จะออก migration ที่ **drop มันทิ้งเงียบ ๆ** (`tests/test_plugins.py` ดักไว้)
- ปิด plugin ของ core ไม่ได้ → แอปไม่ start พร้อมข้อความที่บอกว่าคีย์ไหนผิด
- **ปิด plugin ที่เป็นปัจจัยยืนยันตัวตนมี log เตือนแยกอีกบรรทัด** เพราะคนที่เปิด MFA ไว้
  จะ login ด้วยรหัสผ่านอย่างเดียวได้ทันที (คีย์ของ plugin แม่กับของส่วนเสริมต่างกันแค่ `#`)
- `flask plugin-list` แสดง**ทุกชั้นรวมส่วนเสริม** เพราะคีย์ที่ไม่เคยถูกพิมพ์ออกมา
  คือคีย์ที่ไม่มีใครใส่ลง `DISABLED_PLUGINS` ได้ถูก
- **`TestConfig` ตรึง `DISABLED_PLUGINS`/`PLUGIN_PICKS` ไว้** ไม่ให้ `.env` ของเครื่องที่รัน
  ทำเทสต์แดง (หลักเดียวกับ `RATELIMIT_ENABLED`)
- ปิดแล้ว `plugin-deps --categories` จะไม่คืน category ของมันอีก — `pipenv sync`
  รอบถัดไปจึงไม่ติดตั้งไลบรารีนั้น (ถ้ายังติดตั้งอยู่ การปิดก็แค่ซ่อนปุ่ม)
- ทุกครั้งที่ start จะ log ว่าอะไรถูกปิดอยู่ และเตือนถ้าคีย์ไม่ตรงกับอะไรบนดิสก์เลย

### ธีมเป็น plugin
- สีทั้งหมดอยู่ใน `app/plugins/themes/<id>/theme.css` ส่วนเลย์เอาต์อยู่ใน
  `app/static/base.css` ของ core ซึ่งอ้าง `var(--...)` อย่างเดียว
  **เพิ่มธีมใหม่ = ก๊อป `theme.css` ไปเปลี่ยนค่าสี ไม่ต้องเขียน CSS เลย์เอาต์ซ้ำ**
- ทุกธีมต้องกำหนดตัวแปรชุดเดียวกันครบทั้งโหมดสว่างและมืด ไม่งั้นจะมีสีตกค้าง
  จากธีมก่อนหน้า — มีเทสต์เทียบตัวแปรข้ามธีม
- หน้าเว็บโหลด `base.css` ก่อนแล้วค่อยโหลดธีม ลำดับนี้สำคัญ ธีมถึงจะทับสีได้
- `/plugin/themes/<id>/style.css` เป็น route ของ core ที่เสิร์ฟไฟล์ของ plugin
  ตรวจไอดีกับรายการที่ค้นเจอจริงก่อนเสมอ จึง traverse ออกนอกไดเรกทอรีไม่ได้

### ฐานข้อมูลเป็น plugin ชนิด `db` (Phase 5 — ADR 0026)
- `app/plugins/db/<ไอดี>/plugin.json` ประกาศ `schemes` ที่รับได้ · **scheme ของ
  `DATABASE_URL` เป็นตัวเลือก backend ตัวเดียว** ไม่มี config ตัวที่สอง
- **scheme ที่ไม่ตรงกับ backend ตัวไหนเลย = แอปไม่ start** ห้ามตกกลับ SQLite เงียบ ๆ
  (prod ที่ config ผิดจะ "ทำงานได้" จนถึงวันที่มีคนถามหาข้อมูลที่หายไป)
- **ชนิดนี้ต่างจาก theme/auth สามข้อ**: ถอดตัวที่ใช้อยู่แล้วไม่มีระบบเหลือ ·
  active ได้ทีละตัว · การสลับคือการย้ายข้อมูล ไม่ใช่การ plug
- **ห้ามมี `models.py`** — เป็นเจ้าของ *ทาง* ที่ข้อมูลวิ่งผ่าน ไม่ใช่เจ้าของข้อมูล
  **migration เป็นของ core** (ตรงข้ามกับ ADR 0023 โดยตั้งใจ ไม่งั้น schema แตกสามสาย)
- ปิด backend ที่ active ด้วย `DISABLED_PLUGINS` ไม่ได้ และ `plugin-uninstall`
  กับชนิดนี้ถูกปฏิเสธพร้อมบอกทางที่ถูก
- ค่าเฉพาะยี่ห้ออยู่ใน `backend.py` ของ plugin นั้น (ไม่ต้องตั้งอะไรก็ไม่ต้องมีไฟล์)
  โหลดโดย `db_engine.load()` ใน `create_app` **ก่อน `db.init_app()`**
- driver อยู่ใน category ของตัวเอง (`plugin-db-mysql`) — คนที่รัน SQLite ไม่ต้อง
  ติดตั้งและไม่ต้องเฝ้า CVE ของ driver ยี่ห้ออื่น

## ธีมกับโหมด (สว่าง/มืด/อัตโนมัติ)

แยกสองแกน อย่าเอามาปนกัน:
- **theme** = ชุดสี มาจาก plugin (ดูข้างบน) ค่าเริ่มต้นคือ `system`
- **mode** = ระดับความสว่าง `light` / `dark` / `auto` ค่าเริ่มต้นคือ `auto`

- `User.theme` เก็บไอดีธีม ส่วน `User.mode` เก็บระดับความสว่าง
  **`auto` เก็บเป็นสตริง `'auto'` ไม่ใช่ NULL** (ต่างจาก `locale`/`timezone_name`
  ที่ NULL แปลว่ายังไม่เลือก) เพราะ auto เป็นตัวเลือกจริงที่ผู้ใช้ตั้งใจเลือก
- ลำดับเหมือนภาษา: `?mode=` → session → `User.mode` → `auto` (ดู `app/theme.py`)
- **โหมด "ตามระบบ" (`prefers-color-scheme`) ถูกตัดทิ้งแล้ว** server ตัดสินโหมด
  มาให้เสมอและส่งเป็น `data-theme="light|dark"` บน `<html>`

### ตารางดวงอาทิตย์ (โหมด auto)
- `app/sun_data.py` เก็บเวลาขึ้น-ตกรายเดือนของ **ทุกชื่อที่ zoneinfo รู้จัก (598)**
  **เป็นไฟล์ที่ generate มา ห้ามแก้ด้วยมือ** สร้างใหม่ด้วย
  `python scripts/generate_sun_table.py`
- พิกัดมาจาก `zone.tab` ของ tzdata คำนวณด้วยสูตรดาราศาสตร์ในสคริปต์เอง
  ไม่มี dependency เพิ่มและไม่เรียก API ครอบคลุมสามชั้น:
  418 โซนมีพิกัดเอง, 135 ชื่อพ้องยืมจากโซนที่ไฟล์ tzdata เหมือนกันเป๊ะ,
  45 โซนแบบ `Etc/GMT±N` ใช้เส้นศูนย์สูตรตาม offset (ขึ้น ~06:00 ตก ~18:00)
- **ตารางต้องครอบคลุมทุกชื่อใน `tz.all_timezones()`** ไม่งั้นโซนที่ขาด
  จะได้ `light` ตลอดเวลาเงียบ ๆ — เคยหลุดมาแล้วตอนสร้างจาก `zone1970.tab`
  (312 โซน) ขณะที่ dropdown มี 598 ชื่อ `tests/test_mode.py` ดักไว้แล้ว
- หน่วยเป็นนาทีนับจากเที่ยงคืน **ตามเวลาท้องถิ่นของโซนนั้น**
  ค่า `-1` = ทั้งเดือนดวงอาทิตย์ไม่ขึ้น (คืนขั้วโลก), `-2` = ไม่ตกเลย
- ความแม่นยำระดับไม่กี่นาที เพียงพอสำหรับสลับสี ไม่ได้ทำมาให้ดูฤกษ์
- **ตัวแยกพิกัดของ zone.tab เคยพังเงียบ ๆ มาแล้ว** — มีสองรูปแบบคือ 11 ตัว
  (`±DDMM±DDDMM`) กับ 15 ตัว (`±DDMMSS±DDDMMSS`) ถ้าเดาความยาวผิดจะได้
  ลองจิจูดมั่วโดยไม่มี error ตอนนี้ raise ทันทีถ้ารูปแบบไม่ตรง

## หน้า Settings
- `/settings` รวม โปรไฟล์ + **รหัสผ่าน** + **API token** + **การยืนยันสองขั้น** +
  ภาษา + ธีม + โหมด + timezone ไว้ที่เดียว
  nav = Tasks · Categories · **Teams (เฉพาะคนที่อยู่ในวงอย่างน้อยหนึ่งวง)** ·
  Settings (กับ **Site administration** ที่ชี้ `/admin` ถ้าเป็น admin) ·
  footer มีลิงก์ `/privacy` สาธารณะ (มีปุ่มกลับที่ตก fallback อย่างปลอดภัย)
  · หน้า settings มีลิงก์ **"Reset language to English" เป็นอังกฤษตายตัว
  ห้ามผ่าน gettext** (ทางหนีของคนเลือกภาษาที่อ่านไม่ออก — Change Req #1)
  ส่วนหน้า login มีตัวสลับภาษา/โหมดของตัวเอง
  (route `/lang/<code>` และ `/mode/<value>` ใช้จากหน้า login ไม่ต้อง login)
- `_safe_referrer()` ใน `routes.py` ใช้ร่วมกันทั้งสลับภาษาและสลับโหมด รับเฉพาะ path ในเว็บเรา
- **username แก้ที่หน้านี้ไม่ได้** เพราะเป็นตัวระบุตอน login (ช่องเป็น `disabled`)
- ชื่อ/นามสกุลที่เว้นว่างเก็บเป็น **NULL ไม่ใช่ `''`** ไม่งั้น `full_name` จะมีช่องว่างเกิน
- บันทึก preferences แล้วต้อง **อัปเดต session ด้วย** ไม่ใช่แค่เขียน DB
  เพราะ session ชนะโปรไฟล์ในลำดับการเลือก ถ้าลืมแล้วผู้ใช้เคยกดสลับไว้ที่หน้า login
  ค่าที่เพิ่งบันทึกจะไม่มีผลเลย — `tests/test_settings.py` ดักไว้

## Identity (Phase 4 — ดู ADR 0019–0024)

### รหัสผ่าน (ADR 0019)
- นโยบายอยู่ที่ `app/services/passwords.py` **ที่เดียว** ทั้ง CLI และหน้าเว็บเรียกตัวเดียวกัน
- ยาว 8–128, เทียบกับ `app/password_blocklist.txt` (46k รายการ), ห้ามมี username ตัวเอง
  **ไม่มีกฎ complexity ไม่บังคับเปลี่ยนตามรอบ ไม่ตัดช่องว่าง** — สามข้อนี้ตั้งใจไม่มี
- **normalize NFKC อยู่ใน `User.set_password`/`check_password`** ไม่ใช่ที่ผู้เรียก
  เกิดข้างเดียวเมื่อไหร่ คนที่ตั้งรหัสเป็นภาษาไทย (สระอำ ถูกแตกเป็นสองอักขระ)
  จะ login ไม่ได้ทั้งที่พิมพ์เหมือนเดิม
- ไม่มี self-service reset โดยตั้งใจ (ไม่เก็บอีเมล) — กู้ผ่าน `flask set-password`
- **รหัสในเทสต์ต้องผ่านนโยบายด้วย** เพราะบางเทสต์สร้าง user ผ่าน CLI จริง

### session (ADR 0020)
- ทุกอย่างอยู่ใน `app/session_security.py` ผูกเข้าทุก request ด้วย `before_request`
- idle 30 นาที + absolute 12 ชม. **ตรวจที่ server** ไม่ใช่พึ่งวันหมดอายุบนคุกกี้
- login/เปลี่ยนรหัส → `start_session()` ซึ่ง **ล้าง session ทั้งใบก่อน** (session fixation)
- **ห้ามตั้ง `session.permanent = True`** — `session_protection="strong"` ของ Flask-Login
  จะเลิกล้าง session ให้ทันที (มันแค่ mark ว่าไม่ fresh) การผูกคุกกี้กับเครื่องจะหายเงียบ ๆ
- คุกกี้ผูกกับ **credential ปัจจุบัน** ด้วย HMAC ของ `password_hash` → เปลี่ยนรหัสแล้ว
  คุกกี้ทุกใบที่ออกก่อนหน้า (รวมใบที่อยู่ในมือคนอื่น) ใช้ไม่ได้ทันที
- ด่านนี้ **ไม่แตะคำขอที่ขึ้นต้นด้วย `/api/`** และไม่แตะไฟล์ static

### บทบาท (ADR 0022)
- `tdl_user.role` = `user` | `admin` — **ตรวจสิทธิ์ใน service (`roles.require_admin`)
  ไม่ใช่ที่ route** เพราะมี adapter สามทางแล้ว (HTML/API/CLI)
- บทบาทไม่ถึงตอบ **403** ไม่ใช่ 404 (ต่างจาก ADR 0004 ที่เป็นเรื่องความเป็นเจ้าของ)
- แก้บทบาทตัวเองบนหน้าเว็บไม่ได้ (กันผู้ดูแลคนสุดท้ายถอดสิทธิ์ตัวเอง) ส่วน CLI ทำได้
- เมนู "Users" บน nav โผล่เฉพาะ admin — **การซ่อนเมนูไม่ใช่การกันสิทธิ์**

### MFA (ADR 0024)
- **ความลับ TOTP ถูก encrypt at rest แล้ว** (ADR 0046 — `EncryptedSecret` ใน
  models ของ plugin · dual-read แถว legacy + encrypt-on-verify) และ plugin
  ปิดตัวเองเมื่อไม่มี `cryptography` หรือไม่มีคีย์
- core รู้จักปัจจัยที่สองผ่าน `app/services/mfa.py` เท่านั้น และรู้แค่
  `is_enrolled(user)` / `verify(user, code)` — **ห้ามมีชื่อ plugin ในโค้ด core
  แม้แต่ในคอมเมนต์** (`tests/test_plugins.py` grep บังคับ)
- login ที่มีปัจจัยที่สอง **หยุดครึ่งทาง** ที่ `/login/verify` ไม่เรียก `login_user()`
  ก่อน (ไม่งั้นคนที่รู้แค่รหัสผ่านเข้าถึงข้อมูลได้ทันทีด้วยการพิมพ์ URL อื่น)
- สถานะครึ่งทางมีอายุ 5 นาที และขั้นที่สองมีโควตาต่อบัญชีเหมือนหน้า login
- **QR เสิร์ฟเป็นไฟล์ SVG ที่ `/settings/mfa/<ไอดี plugin>/image` ไม่ใช่ data URI**
  เพราะ data URI ต้องผ่อน CSP เป็น `img-src 'self' data:` — และ **ห้ามมีความลับ
  ใน URL** เด็ดขาด (`path` อยู่ใน log ทุกบรรทัด ชั้น C6 อายุ 90 วัน) ตัวรูปตอบ
  `no-store` และหายเป็น 404 ทันทีที่ยืนยันเสร็จ สีฝังในตัว SVG เพราะตัวสแกน
  ต้องการโมดูลเข้มบนพื้นอ่อนเสมอ ไม่ว่าธีมจะเป็นแบบไหน

## Rate limit
- จำกัดเฉพาะ `POST /login` (+ `POST /login/verify` ของขั้นที่สอง) GET ไม่โดน
- **มีสองมิติ**: ต่อ IP (`LOGIN_RATE_LIMIT`) และ **ต่อชื่อผู้ใช้**
  (`LOGIN_USERNAME_RATE_LIMIT` — ADR 0021) มิติหลังปิดช่องคนที่เปลี่ยน IP ไปเรื่อย ๆ
  กุญแจเป็น sha256 ของชื่อที่ casefold แล้ว ไม่ใช่ชื่อดิบ (มันจะไปนอนใน redis วันหนึ่ง)
- `deduct_when` หักโควตาเฉพาะตอนได้ 401 — login ถูกไม่กินโควตา
- โดนกันแล้วต้องได้ 429 แม้จะใส่รหัสถูก ไม่งั้นคนไล่เดารหัสจะรู้ทันทีว่าเจอรหัสที่ใช่
- เทสต์ทั่วไปปิด rate limit (`RATELIMIT_ENABLED = False`) ตัวจริงเทสต์ใน `tests/test_ratelimit.py`
  ผ่าน fixture `ratelimit_app` ซึ่งต้อง `limiter.reset()` **หลัง** `create_app` เท่านั้น
  (ก่อน `init_app` ยังไม่มี storage จะ assert พัง)

## CSP กับพฤติกรรมฝั่ง client (Phase 1 — ดู ADR 0010)
- CSP เป็น `'self'` ล้วน **ไม่มี `unsafe-inline`** ตั้งที่ `app/security_headers.py`
- **ห้ามมี `onclick=`/`onsubmit=`/`onchange=` หรือ `style=` ใน template เด็ดขาด**
  browser จะบล็อกเงียบ ๆ ไม่มี error ฝั่ง server ให้เห็น — `tests/test_security_headers.py`
  ตรวจไฟล์ template ตรง ๆ อีกชั้น
- พฤติกรรมทั้งหมดอยู่ใน `app/static/app.js` ไฟล์เดียว คุยกับ template ผ่าน `data-*`:
  `data-confirm="ข้อความ"` บน `<form>` = ถามยืนยัน, `data-auto-submit` บน control = submit เอง
- **`app.js` ต้องโหลดแบบ sync ใน `<head>` ห้ามใส่ `defer`/`async`** เพราะต้องติดคลาส
  `js` ให้ `<html>` ก่อน body render ไม่งั้นปุ่มสำรอง `.js-hidden` จะโผล่แวบหนึ่งแล้วหาย
- ของที่ผูกกับ TLS (HSTS/บังคับ https/cookie `Secure`) เปิดด้วย `HTTPS_ENABLED=1`
  ตัวเดียว **อย่าเปิดตอนยังรัน http** จะ redirect วนจน login ไม่ได้

## Accessibility (WCAG 2.2 AA — ดู ADR 0012)
- **ทุก `<form>` ต้องมีปุ่ม submit จริง** ฟอร์มที่พึ่ง `data-auto-submit` อย่างเดียว
  ใช้ไม่ได้เลยเมื่อ JS ไม่ทำงาน — ใส่ `<button type="submit" class="js-hidden">` เป็นทางสำรอง
  (`.js .js-hidden { display: none }` ซ่อนเฉพาะตอน JS ทำงานจริง **ห้ามเปลี่ยนเป็น
  `.js-hidden { display: none }` เปล่า ๆ** จะกลายเป็นฟอร์มที่ submit ไม่ได้)
- ทุก control ต้องมีชื่อ — `<label for>`, `<label>` ห่อ, `aria-label` หรือ `aria-labelledby`
  (ทั้งสี่ทางถูกต้องเท่ากัน) แถวงานใช้ `aria-label` เพราะไม่มีที่วาง label ที่มองเห็น
- **ตรวจด้วยมือรอบล่าสุด: `docs/ACCESSIBILITY-AUDIT.md`** (P7-09) — บอกด้วยว่า
  อะไร **ยังไม่ได้พิสูจน์** (ยังไม่ได้ฟังด้วย screen reader จริง · ยังไม่ได้เดิน
  ด้วยแป้นพิมพ์บนเบราว์เซอร์จริง) ซึ่งสำคัญกว่ารายการที่ผ่าน
- ที่ตรวจด้วยมือแล้วเจอ: ไม่มี `<main>` (ข้าม nav ไม่ได้) · ช่องชื่อ/นามสกุลไม่มี
  `autocomplete` · checkbox ของแถวงานเล็กกว่า 24px — **แก้แล้วทั้งสามและมีเทสต์คุม**
- **ห้ามพึ่งข้อยกเว้นเรื่องระยะห่างของ 2.5.8** เกณฑ์ยอมให้เป้าเล็กได้ถ้าวงกลม 24px
  ไม่ทับเป้าอื่น แต่มันจะพังทันทีที่มีใครวางปุ่มเพิ่มข้าง ๆ โดยไม่มีอะไรฟ้อง
- ตรวจสองชั้น: `tests/test_a11y.py` (โครงสร้าง รันทุกครั้ง) + job `a11y` ใน CI
  (pa11y-ci + Chromium จริง สแกนโหมดมืด ธีม ocean และภาษาไทยด้วย เพราะ contrast ต่างกัน)
- รัน pa11y เองบนเครื่อง: ตั้ง `DATABASE_URL` ชี้ไฟล์ทิ้ง → `flask db upgrade` →
  `PYTHONPATH=. python scripts/a11y_fixture.py` → `flask run --port 5099` → `pa11y-ci`
  (สคริปต์ fixture ปฏิเสธถ้า `DATABASE_URL` ชี้ไปฐานข้อมูลจริง)

## Log (Phase 1 — ดู ADR 0011)
- log เป็น JSON บรรทัดละ event ออก stdout ตั้งที่ `app/logging_setup.py`
- ทุก request ได้ `request_id` — รับต่อจาก header `X-Request-Id` ได้ **เฉพาะที่เป็น UUID จริง**
  ค่ามั่วถูกทิ้งแล้วสร้างใหม่ (กันคนนอกปลอม/inject log) และส่งกลับใน response header ด้วย
- ส่งค่าเพิ่มเข้า log ผ่าน `extra={...}` มันจะถูกยกเป็น field ระดับบนสุดเอง
- **`actor` เก็บ `username` ไม่ใช่ชื่อจริง** ลด PII — มีเทสต์ดักว่าชื่อจริงต้องไม่หลุดลง log

## สิทธิ์ของเจ้าของข้อมูล (Phase 7 · P7-06 — ดู ADR 0034)

- `POST /settings/export` ส่งสำเนาข้อมูลของเจ้าตัวเป็น JSON · CLI คือ
  `flask export-user <ชื่อ>` — **ทั้งคู่เรียก `app/services/personal_data.py` ตัวเดียวกัน**
- **เป็น POST ไม่ใช่ GET และต้องกรอกรหัสผ่านซ้ำ** — คำขอเดียวดูดข้อมูลทั้งบัญชี
  ออกไป ลิงก์ที่หลุดจึงเท่ากับข้อมูลทั้งบัญชีที่หลุด (หลักเดียวกับการออก API token)
- **ไม่มี endpoint ใน `/api/v1` โดยตั้งใจ** — PAT เป็นกุญแจของเครื่องซึ่งกรอก
  รหัสผ่านซ้ำไม่ได้ การกระทำที่อ่อนไหวต้องเริ่มจากตัวตนที่แรงกว่าเสมอ
  (เหตุผลเดียวกับที่ออก token ผ่าน API ไม่ได้ — ดูหัวไฟล์ `app/api/tokens.py`)
- **ข้อมูลของ plugin ให้ plugin ตอบเอง** ผ่านโมดูล `personal_data.py` ที่มี
  `export_for(user)` — core วนถามทุกตัวที่ติดตั้งอยู่และ**ไม่รู้จักชื่อใครเลย**
  · plugin ตัวเดียวพังต้องไม่ทำให้ทั้งคำขอล้ม (log แล้วใส่หมายเหตุแทน)
- **โมดูลของ plugin ต้อง `from .models import ...` ไม่ใช่ absolute path**
  เพราะ registry โหลด models ด้วยชื่อโมดูลที่คำนวณจากคีย์ การ import แบบ absolute
  จะนิยามตารางซ้ำแล้วได้ `Table ... is already defined`
- **ปิดบัญชี**: `POST /settings/close` (ต้องกรอกรหัสผ่านซ้ำ) และ `flask delete-user`
  เรียก `close_account()` ตัวเดียวกัน — **ทางเดียวที่ปิดบัญชีได้** เพราะตอนที่
  ต่างคนต่างไล่ลบ CLI ลืมล้างความลับของปัจจัยที่สองไปทั้งดุ้น (ADR 0034 ข้อ 4)
  · ทันที: ล้างรหัสผ่าน + ลบข้อมูลของ plugin จริง + เพิกถอน token
  · ตามระยะ: soft delete แล้ว `purge-expired` ล้างจริงเมื่อพ้น 30 วัน
- **ผู้ดูแลคนสุดท้ายปิดบัญชีตัวเองไม่ได้** แต่ **CLI ทำได้** — CLI เป็นตัวตนที่แรงกว่า
  และเป็นทางกู้ระบบทางเดียวที่เหลือ (หลักเดียวกับ ADR 0022 เรื่องแก้บทบาทตัวเอง)
- เส้นแบ่งว่าอะไรอยู่ในไฟล์คือ**ชั้นข้อมูล** — `tests/test_personal_data.py`
  บังคับว่า **ทุกคอลัมน์ของตารางที่มีเจ้าของต้องถูกตัดสิน** ว่าอยู่ใน export
  หรืออยู่ใน `NOT_EXPORTED` พร้อมเหตุผล (หลักเดียวกับ DATA-CLASSIFICATION)

## ASVS self-assessment (Phase 7 — `docs/ASVS.md`)

- ประเมินตัวเองต่อ **ASVS 5.0.0 ระดับ L2** (253 ข้อ) · L3 อยู่นอกขอบเขตโดยตั้งใจ
- **มาตรฐานถูกตรึงไว้ที่ `docs/asvs-5.0.0.json`** พร้อม checksum ในสคริปต์ —
  ด่านที่ต้องต่อเน็ตคือด่านที่แดงเพราะเน็ต และมาตรฐานที่เปลี่ยนใต้เท้าทำให้
  "ผ่าน" ของเมื่อวานไม่ใช่ของวันนี้โดยไม่มี commit ไหนบอก
- **ทุกอย่างที่อยู่ใน backtick ในช่องหลักฐาน ถูกตรวจว่ามีอยู่จริง**
  (`tests/test_asvs.py`) — ไฟล์, `tests/x.py::ชื่อเทสต์`, `ci:ชื่อ job`, `ADR 00NN`
  **อย่าใช้ backtick กับคำอธิบายทั่วไปในช่องนั้น** เทสต์จะหาว่าเป็นไฟล์แล้วแดง
- สถานะมีสี่ค่า: `ผ่าน` / `ไม่เกี่ยวข้อง` / `ยังไม่ผ่าน` / `ยังไม่ประเมิน`
  · `ผ่าน` ต้องมีหลักฐานอย่างน้อยหนึ่งชิ้น · `ยังไม่ผ่าน` ต้องอยู่ใน backlog ด้วย
  · **`UNASSESSED_CEILING` เป็น 0 แล้ว** (P7-02 ประเมินครบ 253 ข้อ) สถานะ
  `ยังไม่ประเมิน` จึงเป็นข้อห้ามถาวร — ข้อกำหนดใหม่ที่มากับเวอร์ชันถัดไป
  ต้องถูกประเมินใน commit เดียวกับที่ขยับเวอร์ชัน ไม่ใช่ค้างไว้
- ผลปัจจุบัน: **ผ่าน 141 · ไม่เกี่ยวข้อง 64 · ยังไม่ผ่าน 48**
  ครึ่งหนึ่งของช่องที่ไม่ผ่านคือ **เอกสารที่ยังไม่ได้เขียน** ไม่ใช่โค้ดที่ยังไม่มี
- เพิ่มแถวเมื่อขยับเวอร์ชัน: `scripts/build_asvs_worksheet.py --fetch` แล้วรันเปล่า
  **สคริปต์ไม่เคยทับคำตัดสินที่เขียนไว้แล้ว** และอ่านเฉพาะใต้เครื่องหมายในไฟล์
  (คำนำมีตาราง backlog ที่แถวหน้าตาเหมือนกัน — เคยเขียนทับมาแล้วรอบหนึ่ง)

## รอบการตรวจสอบ (Phase 7 · P7-04 — `docs/SECURITY-CADENCE.md`)

- **นโยบายรอบการตรวจมีเทสต์คุม** (`tests/test_cadence.py`) — ตารางการตรวจที่ต้อง
  ทำด้วยมือถูกอ่านจริง เลยกำหนดเกิน 7 วันแล้ว CI แดง · แก้ได้สองทาง: ไปทำ
  หรือเลื่อนอย่างเปิดเผยพร้อมเหตุผล **ห้ามแก้เทสต์ให้เงียบ**
- กำหนดต้องเป็น **วันที่** หรือ **เงื่อนไขที่ขึ้นต้นด้วย "เมื่อ"** และยาวพอจะ
  ตัดสินได้ — "เมื่อพร้อม" ไม่ผ่าน เพราะเป็นวันที่ไม่มีวันมาถึง
- กรอบเวลาแก้ช่องโหว่: **critical 7 วัน · high 30 · medium 90** นับจากวันที่รู้
  ไม่ใช่วันที่ CVE ออก · advisory ที่ไม่ให้คะแนนถือเป็น high ไว้ก่อน
- **MFA ไม่บังคับ และเหตุผลอยู่ใน `ADR 0033`** พร้อมมาตรการชดเชย 11 ข้อที่มี
  เทสต์คุมทุกข้อ และเงื่อนไขที่ทำให้คำตัดสินหมดอายุ (มี recovery code เมื่อไหร่
  ให้กลับมาพิจารณาบังคับทันที) — ASVS V6.3.3 ผ่าน**ทางเหตุผลที่บันทึกไว้**
  ไม่ใช่เพราะบังคับ

## ปลายทางของ log และกฎแจ้งเตือน (Phase 7 · P7-10 — ดู ADR 0037)

- `compose.siem.yaml` = Loki (เก็บ + ruler) · Alloy (เก็บ log จากไฟล์ของ docker) ·
  Grafana (ให้คนดู) — **แอปไม่รู้จักปลายทางนี้เลย ยังออก stdout เหมือนเดิม**
  ถอดไฟล์ override ทิ้งแล้วแอปทำงานเหมือนเดิมทุกประการ
- **กฎอยู่ที่ ruler ของ Loki ไม่ใช่ที่ Grafana** เพราะสถานะถามผ่าน API ได้ตรง ๆ
  `ci:siem` จึงพิสูจน์ได้ว่า alert **ดังจริง** ไม่ใช่แค่ stack ขึ้นได้
  · กฎอยู่ใน `deploy/loki-rules.yaml` **ไม่ใช่ของที่คลิกไว้ใน UI** ซึ่งหายไปพร้อม volume
- **ทุกกฎต้องมี annotation `runbook`** — กฎที่ดังแล้วไม่มีใครรู้ว่าต้องทำอะไรต่อ
  จะถูกปิดเสียงภายในสองสัปดาห์ แล้วกฎที่เหลือก็ถูกมองข้ามไปด้วย
- **กฎที่นับแต่ 401 เงียบพอดีตอนที่การโจมตีหนักที่สุด** เพราะโควตาตัดที่ 5 ครั้ง
  ที่เหลือกลายเป็น 429 — ต้องนับทั้งสองอย่าง (วัดจริง: ยิง 12 ได้ 401 ห้า 429 เจ็ด)
- `retention_period` ใน `deploy/loki.yaml` ต้องตรงกับชั้น C6 (90 วัน) **และต้อง
  เปิด compactor** ไม่งั้นค่านั้นเป็นแค่ตัวเลขที่ไม่มีอะไรบังคับ
- **รหัสของ Grafana มีผลเฉพาะตอน start ครั้งแรก** เปลี่ยนตัวแปรแล้ว restart ไม่เปลี่ยนอะไร

## DAST — job `dast` (Phase 7 · P7-03)

- ZAP baseline ยิงใส่ stack ที่รันจริง (TLS + 2 replica) **แบบที่ login แล้ว**
  ตัวสั่งงานคือ `scripts/dast_scan.sh` ซึ่งรันเองบนเครื่องได้ด้วยคำสั่งเดียวกัน
- **สแกนโดยไม่ login เห็นแค่หน้า login** — ด่านแบบนั้นเขียวตลอดโดยไม่ได้ตรวจอะไร
- **curl ที่ login กับ ZAP ต้องเป็นเบราว์เซอร์ตัวเดียวกัน** เพราะ
  `session_protection="strong"` ของ Flask-Login ผูก session กับ User-Agent
  แล้ว**ทิ้ง session ทั้งใบ**เมื่อไม่ตรง — อาการคือ 302 ทุกหน้าอย่างเงียบ ๆ
  · ค่า User-Agent **ห้ามมีช่องว่าง** เพราะ `-z` ของ ZAP แยกอาร์กิวเมนต์ด้วยช่องว่าง
  · ใน `-z` **ห้ามใส่ backslash หน้าวงเล็บ** ของ `replacer.full_list(0)`
- กติกาต่อรายการอยู่ใน `.zap/rules.tsv` — **ทุกบรรทัดต้องมีเหตุผล** และ
  ข้อที่ตั้งเป็น FAIL ทั้งหมด**ผ่านอยู่แล้ว** มันเป็นตาข่ายกันถอยหลัง ไม่ใช่ตัวหาของใหม่
- **spider ใช้ thread เดียว** เพราะ ZAP submit ฟอร์มด้วย การ crawl หลาย thread
  จึงไปกระตุ้น MySQL deadlock ที่ ADR 0032 บันทึกว่ายังไม่ได้แก้ แล้ว job แดง
  ด้วยเรื่องที่ไม่เกี่ยวกับ PR นั้น
- **ด่านที่วัดว่าการสแกนได้ตรวจจริง อ่านจาก log ของแอป ไม่ใช่จากรายงานของ ZAP**
  (รายงานมีแค่ URL ที่มี alert — วันที่แก้จนไม่เหลือ alert การเช็คจากรายงาน
  จะกลายเป็น "ไม่เจอ = ไม่ได้สแกน") · และมีด่านแยกว่าแอปต้องไม่พ่น traceback เลย

## Performance (Phase 6 — ดู ADR 0031 · ผลวัดใน docs/PERFORMANCE.md)

- **เป้าคือ p95 < 200ms และ p99 < 500ms ที่ 5 คำขอพร้อมกัน** เลข 5 มาจากขนาด
  การใช้งานจริง (ส่วนตัว/ครอบครัว) ไม่ใช่เลขกลม — จะเปลี่ยนต้องเปลี่ยน ADR ก่อน
- `/metrics` **ต้องมี API token เสมอ ไม่มีโหมดสาธารณะ** ผ่าน `require_api_token()`
  ตัวเดียวกับ `/api/v1` (path ของมันอยู่ใน `MACHINE_PATHS` ของ `app/api/auth.py`)
- **label ของ metric ต้องเป็น `request.endpoint` ห้ามใช้ `request.path`**
  ไม่งั้นจำนวน time series โตตามจำนวนงานในระบบ และคนนอกยิง path มั่ว ๆ ให้ระเบิดได้
- **ตัวเลขที่ตัดสิน DoD มาจากฝั่ง client (k6) ไม่ใช่จาก `/metrics`** เพราะเวลาที่
  ผู้ใช้รอรวมคิวใน gunicorn และการรอ connection ซึ่งเกิด*ก่อน*ตัวจับเวลาเริ่มทำงาน
  — ตัวเลขจาก `/metrics` สวยกว่าความจริงเสมอ มีไว้*วินิจฉัย*ว่า endpoint ไหนช้า
- **วัดรอบเดียวไม่ใช่หลักฐาน** p99 ของสี่รอบที่เหมือนกันทุกอย่างต่างกันได้สี่เท่า
  สิ่งที่ยืนยันได้คือ "ไม่มีรอบไหนตกเกณฑ์" (k6 คืน exit 0) ไม่ใช่ค่าใดค่าหนึ่ง
- ไล่หาจุดที่ระบบเริ่มพังด้วย `NO_THRESHOLDS=1` (ต้อง "ไม่ผ่าน" เป็นเรื่องปกติ)
  ส่วนการวัดที่โหลดเป้าต้อง**เปิด** threshold แล้วอ่าน exit code
- **รหัสผ่านของผู้ใช้ทดสอบต้องผ่านนโยบายของแอปเอง** (ห้ามมีชื่อผู้ใช้อยู่ข้างใน —
  ADR 0019) ไม่งั้น `create-user` ปฏิเสธเงียบ ๆ แล้ว k6 รายงานว่า login ไม่ผ่านทั้งชุด
- **คอขวดตอนนี้คือจำนวน process ที่รับงานได้พร้อมกัน ไม่ใช่ query** — throughput
  ตันที่ ~57–70 req/s แล้วตกลง ซึ่งเป็นรูปของคิวที่ล้น การไปเพิ่ม index ตอนนี้
  คือการแก้สิ่งที่การวัดไม่ได้บอกว่าเสีย (gunicorn ยังเป็น worker เดียวต่อ container)

## Schema identity (Phase 2 ด่านแรก — ดู ADR 0013)
- **ทุกตารางขึ้นต้น `tdl_`** ตาราง core คือ `tdl_user` / `tdl_category` / `tdl_todo`
  ตารางของ alembic คือ `tdl_alembic_version` — plugin ใช้ `tdl_<ชนิด>_<ไอดี>_*`
  ผลพลอยได้: `user` ไม่ใช่ชื่อตารางอีกแล้ว landmine reserved word ตายถาวร
- ชื่อ constraint/index มาจาก `NAMING_CONVENTION` ใน `app/__init__.py` ไม่ใช่ชื่อ auto
  **แก้รูปแบบนี้ต้องมี migration รองรับ** ไม่งั้น alembic จะ drop constraint ที่ชื่อไม่ตรง
- คอลัมน์ boolean ขึ้นต้น `is_`/`has_` — `Todo.is_done` (เดิมชื่อ `done`)
- model เป็น SQLAlchemy 2.0 typed style ทั้งหมด (`Mapped[]` + `mapped_column`)
  คอลัมน์ที่ nullable ต้องเป็น `Mapped[X | None]` ให้ตรงกับ DB จริง

### env.py: ห้ามแตะ connection ก่อน `context.configure()`
เคยพังมาแล้วตอน Phase 2 — โค้ดที่ `inspect()` หรือ execute บน connection ตัวเดียวกับ
ที่ส่งให้ alembic **ทำให้ migration ทั้งชุดถูก rollback เงียบ ๆ**
log ขึ้น "Running upgrade" ครบทุกตัว exit code เป็น 0 แต่ฐานข้อมูลไม่เปลี่ยนเลย
งานที่ต้องแตะ DB ก่อน configure ให้ใช้ `engine.begin()` เปิด connection ของตัวเอง
`tests/test_migrations.py` เป็นที่เดียวในชุดเทสต์ที่รัน migration จริง — **ห้ามลบ**
เทสต์อื่นใช้ `db.create_all()` จึงไม่มีทางจับบั๊กชั้นนี้ได้

### model กับ migration ต้องตรงกัน
`db.create_all()` สร้างตารางจาก model ตรง ๆ เทสต์ที่ใช้มันจึงตรงกับ model เสมอ
โดยนิยาม **ต่อให้ migration เขียนอะไรไว้ก็มองไม่เห็น** — เคยหลุดมาแล้วจริง:
`deleted_at` มี index ใน migration แต่ model ไม่ได้ประกาศ `index=True`
ผลคือ `flask db migrate` ครั้งถัดไปจะออก migration ที่ **drop index ทิ้งเงียบ ๆ**
ทั้งที่ทุก SELECT ในระบบมี `deleted_at IS NULL` ต่อท้าย

ตอนนี้มีสองด่านที่ทับกัน (ตั้งใจ) — **เพิ่มคอลัมน์/index ต้องผ่านทั้งคู่**:
- `tests/test_migrations.py::test_models_match_the_migrated_schema`
- job `schema` ใน CI — `flask db upgrade` บนฐานข้อมูลเปล่าแล้ว `flask db check`
  (รันเองบนเครื่องได้ด้วย `DATABASE_URL=sqlite:////tmp/x.db pipenv run flask db check`)

## Soft delete และ purge (Phase 2 — ดู ADR 0014)
- **"ลบ" ทั้งระบบแปลว่าซ่อน** ตั้ง `deleted_at` ไม่ใช่ลบแถว
  ห้ามใช้ `db.session.delete()` หรือ `.delete()` แบบ bulk ที่ไหนอีกนอก `app/purge.py`
  **`tests/test_write_discipline.py` สแกนโค้ดบังคับข้อนี้อยู่** รวมถึง raw SQL /
  `text()` / Core DML / `synchronize_session` ซึ่งเลี่ยง `after_flush` จึงไม่ลง audit
  จำเป็นต้องใช้จริงต้องเพิ่มใน `ALLOWED_LINES` พร้อมเหตุผล ไม่ใช่ลบเทสต์ทิ้ง
- **ตัวกรองถูกเติมอัตโนมัติทุก ORM query** ผ่าน event `do_orm_execute` ใน
  `app/soft_delete.py` ไม่ต้องใส่เอง และ**ห้ามพึ่งการใส่เอง** เพราะลืมได้
  งานที่ต้องเห็นของที่ลบแล้วต้องขอด้วย `.execution_options(**INCLUDE_DELETED)`
- **ข้อจำกัดที่ต้องรู้:** ถ้า object ยังอยู่ใน identity map `session.get()` จะคืนตัวนั้น
  โดยไม่ query จึงไม่ถูกกรอง — request จริงไม่เจอเพราะได้ session ใหม่ทุกครั้ง
  แต่ **เทสต์ต้อง `expunge_all()` ไม่ใช่ `expire_all()`**
- `purge-expired` เป็นคำสั่งเดียวที่ลบจริง (`--dry-run` ดูก่อนได้)
  **`--dry-run` ต้องเรียก `preview_expired()` เท่านั้น** ห้ามทำเป็น flag ที่เรียก
  ตัวลบจริงแล้วค่อย rollback — เคยเขียนแบบนั้นแล้ว**ลบข้อมูลจริง** เพราะตัว purge
  commit ไปก่อน savepoint จึงถูกปิดไปแล้ว
- ผู้ใช้ที่ถูก purge **ไม่ถูกลบแถวทิ้ง** เหลือเป็น tombstone (`username` → `#deleted-<id>`)
  ให้ audit อ้าง `actor_id` ได้ ส่วน `password_hash` ถูกล้างทันทีที่ soft delete ไม่รอ grace
- ระยะที่อนุมัติ: soft delete 30 วัน / audit 1 ปี / log 90 วัน (ดู docs/DATA-CLASSIFICATION.md)
- **ระยะพวกนั้นจะเป็นจริงก็ต่อเมื่อมีอะไรรัน `purge-expired` ตามรอบ** ตัวห่อสำหรับ
  cron/timer อยู่ที่ `scripts/purge_cron.sh` วิธีติดตั้งอยู่ใน `docs/OPERATIONS.md`
  **unit จริงอยู่ที่ `deploy/systemd/` แล้ว** (P5-16) ติดตั้งด้วย
  `scripts/install_purge_timer.sh` และพิสูจน์บน host ที่มี systemd จริงแล้วว่า
  หน่วยรันจบด้วย exit 0 · timer นับถอยหลังอยู่ · และ **ความล้มเหลวมองเห็นได้**
  ผ่าน `systemctl is-failed` (งานตามรอบที่เงียบตอนพังแย่กว่าไม่มีเลย)
  ในสคริปต์ห้ามรับ exit code แบบ `if ! cmd; then status=$?` เด็ดขาด —
  `$?` ในกิ่งนั้นเป็น 0 เสมอ งานที่ล้มเหลวจะรายงานว่าสำเร็จ ใช้ `cmd || status=$?`

## Audit trail (Phase 2 ข้อสุดท้าย — ดู ADR 0015)

- ตาราง `tdl_audit` **เติมได้อย่างเดียว** โค้ดอยู่ที่ `app/audit.py` ไฟล์เดียว
- **ไม่ต้องเรียกอะไรเวลาเขียนฟีเจอร์ใหม่** — event `after_flush` ของ Session ดักทุก
  insert/update/delete ให้เอง ครอบทั้ง route, CLI และสคริปต์
  **ข้อจำกัด:** bulk update/delete ระดับ Core และ raw SQL ไม่ถูกดัก
  (ตอนนี้ระบบไม่มีเหลือแล้ว — เพิ่มใหม่ต้องรู้ตัวว่ามันจะไม่ถูกบันทึก)
- เหตุการณ์ที่ไม่ใช่การเขียน DB (login/logout) เรียก `audit.record()` เอง แล้ว commit
- **ชื่อเหตุการณ์ตามความหมาย ไม่ใช่ตามคำสั่ง SQL** — soft delete เป็น `todo.delete`
  (ไม่ใช่ `todo.update`), คืนค่าเป็น `todo.restore`, ลบจริงเป็น `todo.purge`
- **ค่าที่บันทึกได้ขึ้นกับชั้นข้อมูล** ประกาศไว้ที่ `PLAIN_COLUMNS`/`SECRET_COLUMNS`/
  `HASHED_COLUMNS` ใน `app/audit.py` — **เพิ่มคอลัมน์ใหม่ต้องมาจัดชั้นที่นี่ด้วย**
  (`tests/test_audit.py` บังคับ) ค่าเริ่มต้นตอนรันคือ HMAC = ปิดบังไว้ก่อน
- `actor` เก็บ **`actor_id` เป็นเลข ไม่เก็บ username** และ "ที่ไหน" เก็บ `request_id`
  **ไม่เก็บ IP** เพราะ IP มีอายุ 90 วันตามชั้น C6 เอาไปค้นต่อใน log เอา
- **เวลาในตารางนี้ตัดเศษวินาทีทิ้ง** ห้ามเอา microsecond กลับมา — MySQL ปัดทิ้งเอง
  แล้ว hash ที่คำนวณใหม่จะไม่ตรง (ดู ROADMAP ข้อ 4.5)
- ตรวจสาย: `pipenv run flask audit-verify` / อ่าน: `pipenv run flask audit-log`
- **แก้/ลบแถว audit ผ่าน ORM ไม่ได้** ด่านอยู่ที่ `before_flush` — purge job ต้องขอ
  สิทธิ์ด้วย `allow_purge()` แล้วคืนด้วย `finish_purge()` ทันที
- **purge audit ตัดได้จากหัวสายเท่านั้น** (`_expired_audit` หยุดที่แถวแรกที่ยังไม่หมดอายุ)
  ห้ามเปลี่ยนเป็น `WHERE created_at < cutoff` เฉย ๆ — นาฬิกาที่ถูกปรับย้อนหลังจะทำให้
  เจาะรูกลางสายแล้ว verify ไม่ผ่านตลอดกาล
- **checkpoint ต้องเขียนก่อนลบเสมอ** ไม่งั้นตอนล้างทั้งตารางมันจะหาแถวก่อนหน้าไม่เจอ
  แล้วตั้งต้นที่ genesis — สายยัง "ผ่าน" แต่ไม่ผูกกับประวัติที่มันอ้างว่าแทนอีกต่อไป
- **การต่อสายเป็นลำดับด้วยการล็อกแถวเดียวของ `tdl_audit_lock`** (ADR 0035
  — **แทนที่วิธีของ ADR 0032**) `_last_hash()` ล็อกแถวนั้นก่อนอ่านหางสายเสมอ
  **ห้ามกลับไปใช้ `ORDER BY id DESC LIMIT 1 FOR UPDATE` บน `tdl_audit`**
  เพราะ InnoDB จับ next-key lock ที่รวมช่องว่างท้ายตาราง และช่องว่างเข้ากันได้
  กับช่องว่าง ผู้เขียนหลายรายจึงผ่านไปพร้อมกันแล้วไปชนกันตอน INSERT เป็น
  **deadlock** แทน (วัดจริง: writer 8 ตัว ตาย 128 จาก 160 ครั้ง)
  · **หางสายเก็บอยู่บน `tdl_audit_lock.last_hash` ไม่ใช่อ่านจาก `tdl_audit`**
  เพราะการอ่านแบบธรรมดาใต้ REPEATABLE READ เห็น snapshot ที่ตั้งไว้ตั้งแต่ query
  แรกของ transaction และ **คำขอจริงทุกใบอ่านก่อนเขียนเสมอ** — ล็อกได้แต่ยังชน
  · **ยี่ห้อที่มี MVCC รันที่ READ COMMITTED** (ADR 0036 — ตั้งใน `backend.py`
  ของยี่ห้อนั้น ไม่ใช่ที่ core) เพราะ MariaDB 11.6+ เปิด innodb_snapshot_isolation
  ซึ่งห้าม transaction ล็อกแถวที่ถูกแก้หลัง snapshot ของตัวเอง — REPEATABLE READ
  จึงใช้กับสาย audit ไม่ได้เลยบนยี่ห้อนั้น
  · **แถวล็อกเกิดพร้อมตาราง ไม่ใช่เกิดตอนแอปหาไม่เจอ** — แอปที่สร้างแถวให้เอง
  คือแอปที่ผู้เขียนหลายรายสร้างแถวพร้อมกันได้ ซึ่งพากลับไปที่ปัญหาเดิม
  · **เทสต์ความขนานต้องใช้ ≥8 สาย และต้องอ่านก่อนเขียน** สองสายไม่พอจะสร้าง
  วงจรของ deadlock และการเขียนเป็น statement แรกทำให้ snapshot ถูกตั้งตอนที่ยัง
  ไม่มีใครแข่ง — **ทั้งสองอย่างเคยทำให้เทสต์เขียวทั้งที่โค้ดพัง**
- **(ประวัติ) วิธีเดิมตาม ADR 0032 คือ `FOR UPDATE` บนหางสาย**
  สอง process ที่อ่าน "แถวสุดท้าย" ตัวเดียวกันจะต่อสายด้วย `prev_hash` เดียวกัน
  แล้วตัวหลังชนกุญแจ unique → ผู้ใช้เห็น **500** · วัดได้จริงตอน load test:
  0.36% ที่โหลดเป้าและ 9.5% ที่โหลดสูง เมื่อรัน 2 replica (1 replica ไม่เกิดเลย)
  **ผลที่ยอมรับโดยรู้ตัว: การเขียนที่ต้องลง audit serialize กันทั้งระบบ**
  ซึ่งเป็นสิ่งที่สาย hash ต้องการโดยนิยาม ไม่ใช่ผลข้างเคียงที่ปรับจูนได้
  (SQLAlchemy ตัด `FOR UPDATE` ทิ้งเองบน SQLite และนั่นถูกแล้ว — SQLite ล็อกทั้งไฟล์อยู่แล้ว)
  `tests/test_audit.py::test_two_connections_appending_at_once_do_not_collide`
  ดักไว้ และ **`skipif` บน SQLite** จึงเดินจริงเฉพาะ job `dialects`

## Service layer (Phase 3 — ดู ADR 0016)

- **ตรรกะอยู่ใน `app/services/` ที่เดียว** route ของ HTML กับ view ของ API เป็น
  adapter ที่อ่าน input → เรียก service → เลือกคำตอบ เท่านั้น
- **ไฟล์ใน `app/services/` ห้าม import** `request`, `session`, `g`, `flash`, `abort`,
  `redirect`, `render_template`, `url_for`, `jsonify`, `make_response`, ทั้งโมดูล
  `flask`, `flask_login`, `app.routes`/`app.auth`/`app.api`
  (`current_app` อนุญาต — ผูกกับแอป ไม่ใช่กับ request) `tests/test_service_layer.py`
  สแกน AST บังคับ + มีเทสต์ที่รันตรรกะทั้งเส้นในapp context เปล่า ๆ
- **ความล้มเหลวสื่อสารด้วย exception ไม่ใช่ `abort()`** — `NotFoundError` /
  `ValidationError` / `ConflictError` แต่ละตัวมี `code` (ภาษาเครื่อง เป็นส่วนหนึ่ง
  ของสัญญา API) แยกจาก `message` (ภาษาคน เปลี่ยนถ้อยคำได้)
- **service `commit()` เอง** ผู้เรียกไม่ต้องรู้เรื่อง session — "ลืม commit" คือบั๊ก
  ที่เงียบที่สุดชนิดหนึ่ง (ทำงานถูกทุกอย่างแต่ข้อมูลไม่ถูกเขียน)
- service รับ **`datetime` ที่ย่อยแล้ว** เป็นเวลาท้องถิ่นของผู้ใช้ ไม่ใช่สตริงดิบ
  การแปลงเป็น UTC เกิดในตัว service (ผู้เรียกไม่ต้องรู้เรื่อง timezone)
- `update_todo()` รับ **dict ของเฉพาะฟิลด์ที่ส่งมา** ไม่ใช่ argument ต่อฟิลด์ เพราะ
  PATCH ต้องแยก "ไม่ได้ส่งฟิลด์นี้มา" ออกจาก "ส่ง null มาเพื่อล้างค่า"
  ชื่อฟิลด์ที่ไม่รู้จัก **ถูกปฏิเสธ ไม่ใช่ถูกเมิน**

## API v1 (Phase 3 — ดู ADR 0018)

- `/api/v1` = todos + categories + tokens โค้ดอยู่ใน `app/api/` ใช้ flask-smorest
  + marshmallow เรียก service ชุดเดียวกับหน้าเว็บ **ห้ามมีตรรกะของโดเมนในนี้**
- **สร้าง blueprint ของ API ได้ทางเดียวคือ `api_blueprint()` ใน `app/api/base.py`**
  ซึ่งผูกด่าน token (`before_request`) และ error handler ให้ครบ — blueprint ที่
  สร้างเองจะไม่มีด่านและไม่มีอะไรฟ้อง
- **ด่านตรวจ `g.api_token` ไม่ใช่แค่ `current_user.is_authenticated`**
  API ยกเว้น CSRF ไว้ ถ้ายอมรับ session cookie ด้วยจะเปิดรู CSRF ทันที
  และ **token ใช้กับหน้าเว็บ HTML ไม่ได้** (loader จำกัดด้วย path `/api/`)
- `require_api_token()` ต้องแตะ `current_user` ก่อนหนึ่งครั้ง — Flask-Login เรียก
  `request_loader` แบบ lazy ถ้าไม่แตะ `g.api_token` จะว่างเสมอแล้วทุกคำขอได้ 401
- ซอง error รูปเดียวทุกกรณี: `{"error": {"code": ..., "message": ...}}`
  โดย `code` มาจาก `ServiceError.code` ตรง ๆ (400 = แก้ค่าที่ส่งมา, 409 = ไปแก้
  สถานะก่อน, 404 = ไม่มีหรือของคนอื่น ตาม ADR 0004, 422 = schema จับได้ก่อนถึง service)
- **`_register_error_handlers()` ของ smorest ถูก override ให้ไม่ทำอะไร** ไม่งั้น
  มันจะยึด handler ของ `HTTPException` ทั้งแอปแล้วหน้า 404 ของเว็บกลายเป็น JSON
- **เวลาในสัญญาเป็นเวลาท้องถิ่นของเจ้าของข้อมูล ไม่มี offset** ค่าที่มี offset
  ถูกปฏิเสธ ย่อยด้วย `tz.parse_naive()` ตัวเดียวกับฝั่ง HTML
- ชื่อ query parameter ที่ไม่รู้จัก **ถูกปฏิเสธ (422)** — ต้องระบุ `unknown=ma.RAISE`
  เอง เพราะ webargs ตั้งค่าเริ่มต้นของ query เป็น EXCLUDE (พิมพ์ชื่อตัวกรองผิดแล้ว
  ได้ผลลัพธ์ที่ไม่ได้กรองกลับไปเงียบ ๆ) ส่วน **ค่า**ที่ไม่รู้จักยังตกกลับเป็นค่าเริ่มต้น
  เหมือนฝั่งเว็บ
- **แก้ `app/api/` แล้วต้องรัน `scripts/generate_openapi.py`** — `docs/openapi.json`
  เป็นภาพถ่ายที่มีเทสต์กับ job `openapi` ใน CI เทียบว่าตรงกับโค้ดเป๊ะ
- **เวอร์ชันอยู่ที่ path และ v1 แก้ไม่ได้** เพิ่ม field/endpoint/query ที่มีค่าเริ่มต้นได้
  แต่ลบ/เปลี่ยนชื่อ/เปลี่ยนชนิด/เปลี่ยน status code/เปลี่ยนความหมายของ `code` ต้องขึ้น v2
- ยังไม่มี: pagination, ETag, rate limit ของ API

## Personal access token (Phase 3 — ดู ADR 0017)

- token คือกุญแจของ **เครื่อง** ไม่ใช่ของคน ใช้กับ `/api/v1` แทน session cookie
  โค้ดอยู่ที่ `app/services/tokens.py` ตารางคือ `tdl_api_token`
- รูปแบบ `tdl_<id>_<ความลับ>` เก็บลง DB เป็น **sha256 ของความลับ ไม่ใช่ scrypt**
  (ค่าสุ่ม 256 บิตไม่มี dictionary ให้ไล่ ส่วน scrypt ต่อ request คือช่องให้ยิงถล่ม)
  เทียบด้วย `hmac.compare_digest` เสมอ ห้ามใช้ `==`
- **ความลับจริงแสดงครั้งเดียวตอนออกใบ** ไม่มีทางดูอีก ทำหายให้ออกใบใหม่
- **เพิกถอน = ล้าง hash ทิ้งทันที** ไม่ใช่แค่ soft delete — กู้แถวคืนมาก็ใช้ไม่ได้
  `delete-user` ก็ทำแบบเดียวกันกับทุกใบของคนนั้น
- ค่าเริ่มต้นมีวันหมดอายุ 90 วัน ใบที่ไม่มีวันหมดต้องขอเอง (`--expires-days 0`)
- **ห้ามเพิ่ม `last_used_at`** — เขียนทุก request = แถว audit ต่อ request
  คำถาม "ใช้ครั้งล่าสุดเมื่อไหร่" ตอบจาก log ที่มี `token_id`
- `token_hash` เป็นชั้น C1 เท่ารหัสผ่าน อยู่ใน `SECRET_COLUMNS` ของ `app/audit.py`
  (audit บันทึกได้แค่ `{"changed": true}`)

## Foreign key (Phase 2)
- **SQLite ปิดการบังคับ FK เป็นค่าเริ่มต้น และเป็นค่าต่อ connection** ไม่ใช่ต่อไฟล์
  ตัว listener อยู่ที่ `app/plugins/db/sqlite/backend.py` (ย้ายมาจาก core ตอน P5-05
  เพราะเป็นเรื่องของยี่ห้อนั้นล้วน ๆ) ผูกที่คลาส `Engine` จึงครอบทุก engine
- **`create_app` ต้องเรียก `db_engine.load()` ก่อน `db.init_app()` เสมอ**
  ตัวนั้นเป็นคนโหลด `backend.py` ของยี่ห้อที่ใช้อยู่ ถ้าลบทิ้งหรือย้ายไปหลัง
  init FK จะเลิกถูกบังคับโดยไม่มี error อะไรให้เห็น ผลคือลบหมวดแล้วงานจะเหลือ
  `category_id` ชี้ไปแถวที่ไม่มีอยู่ — ข้อมูลเสียแบบเงียบ
  (`tests/test_db_integrity.py` ดักไว้ — ถอดบรรทัดนั้นออกแล้วแดงสามตัว)
- `tests/test_db_integrity.py` วัด **ผล** ของการบังคับ (insert ที่ผิดต้อง IntegrityError,
  `ondelete="SET NULL"` ต้องทำงานจริง) ไม่ใช่แค่ค่า pragma — ห้ามลด assert เหลือแค่อ่าน pragma
- batch migration ของ alembic กับ FK เปิดอยู่ ทดสอบแล้วว่าไป-กลับได้ข้อมูลครบ
  และ `PRAGMA foreign_key_check` สะอาด — แต่ migration ใหม่ที่ย้ายข้อมูลควรตรวจซ้ำทุกครั้ง

## วินัย dialect (มีผลทันที — เตรียมรองรับ DB หลายยี่ห้อ ดู ROADMAP ข้อ 4)
- raw SQL ใน migration ต้อง quote ตารางที่เป็น reserved word — โดยเฉพาะ `"user"`
  (reserved ใน PostgreSQL/Oracle/MSSQL — migration เก่า 3 จุดปล่อยไว้ จะล้างด้วย
  baseline squash ตอน Phase 5 อย่าเพิ่มจุดใหม่)
  **ตารางปัจจุบันไม่มีชื่อนี้แล้ว** หลังใส่ prefix `tdl_` — เหลือแค่ใน migration เก่า
- **คอลัมน์เวลาต้องใช้ `UTCDateTime` จาก `app/db_types.py` ห้ามใช้ `DateTime` เปล่า**
  (`DATETIME` ของ MySQL/MariaDB ตัดเศษวินาทีทิ้งเงียบ ๆ — ไม่มี warning ไม่มี error
  งานที่สร้างห่างกันไม่กี่มิลลิวินาทีจะมีเวลาเท่ากันแล้วเรียงลำดับสลับกันเอง)
  `tests/test_dialect_parity.py` บังคับทั้งฝั่ง model และฝั่ง migration
  **`sa.DateTime()` ที่ `flask db migrate` ออกให้ ต้องแก้เป็น `UTCDateTime` ทุกครั้ง**
- ห้ามเทียบ DATETIME แบบ exact ข้าม insert บนคอลัมน์ที่ไม่ได้ใช้ `UTCDateTime`
- คอลัมน์ String ระบุความยาวเสมอ (MySQL บังคับ) — ตอนนี้ครบทุกคอลัมน์แล้ว

## แผนระยะยาว
- มาตรฐาน/เครื่องมือที่ตัดสินแล้ว (naming, prefix `tdl_`, ruff/mypy/semgrep ฯลฯ)
  อยู่ใน `docs/STANDARDS.md` — verdict ข้อ 4 บอกว่าอะไรเข้าเฟสไหน
- **การจำแนกชั้นข้อมูลและระยะเก็บรักษาอยู่ใน `docs/DATA-CLASSIFICATION.md`**
  เพิ่มคอลัมน์ใหม่ต้องระบุชั้นในเอกสารนั้นด้วย (`tests/test_data_classification.py` บังคับ)
  กติกาที่มีผลกับโค้ด: **audit ห้ามเก็บค่าของ C1/C2/C3** เก็บได้แค่ชื่อคอลัมน์ + HMAC
  และ `password_hash` ห้ามออกจากระบบทุกกรณีแม้แต่ในรูป hash (ดู ADR 0014)
- **ผลวัดประสิทธิภาพจริงอยู่ใน `docs/PERFORMANCE.md`** (Phase 6 — ปิดเฟสแล้ว)
  เป้าที่ 5 concurrent ผ่าน ยืนยันด้วยการรันซ้ำ 4 รอบ ไม่มีรอบไหนตกเกณฑ์ ·
  ระหว่างทางเจอว่า **การรัน ≥2 replica ทำให้การเขียนล้มเพราะสาย audit ต่อขนาน
  ข้าม process ไม่ได้** (ข้อจำกัดที่ ADR 0015 บันทึกไว้เองว่าต้องแก้เมื่อถึงวันที่
  เขียนขนานจริง — วันนั้นมาถึงพร้อม Phase 5) **แก้แล้วด้วย ADR 0032**
- แผนแม่บท (ISO/IEC 25010:2023 + audit/data governance) อยู่ใน `docs/ROADMAP.md`
  เรียงเป็นเฟสตามหลักลด rework — **ก่อนเริ่มฟีเจอร์ใหม่ให้เช็คว่าอยู่เฟสไหนของแผน**

## ยังไม่ได้ทำ
- หน้า login ไม่รองรับ `?next=` โดยตั้งใจ (กัน open redirect) login เสร็จเด้งไปหน้าแรกเสมอ
- **ไม่มี recovery code ของ MFA** — ทำโทรศัพท์หายต้องให้ผู้ดูแลปิดให้ (ยังไม่มีคำสั่ง CLI
  ของ plugin สำหรับข้อนี้ — งานที่เหลืออยู่จริง)
- ปัจจัยหลักมีสองรูปแบบ (ADR 0029): `redirect` (OIDC — `begin`/`finish`) กับ
  `credential` (LDAP — `authenticate`) **manifest ประกาศด้วย `style` core ไม่เดา**
  · **รหัสผ่านของที่นี่ถูกลองก่อน directory ภายนอกเสมอ**
- OIDC เสร็จแล้วตั้งแต่ P5-13 (ADR 0028)
  core รู้จักปัจจัยหลักที่ไม่ใช่รหัสผ่านผ่าน `app/services/sso.py` (`begin`/`finish`)
  เท่านั้น และ **ไม่รู้จักชื่อ plugin ตัวไหนเลย** · ตาราง `tdl_auth_oidc_identity`
  เก็บแค่ `(issuer, sub) → user_id` ถอน plugin แล้วผู้ใช้ยังอยู่ครบ
  **ยังไม่มี: single logout, refresh token, การผูกหลาย IdP กับผู้ใช้คนเดียว**
- `password` เป็น plugin ที่มีแต่ manifest — core ยังเรียก `check_password()` ตรง ๆ
  (ยังไม่ยกขึ้นเป็น plugin จริง แม้จะมีปัจจัยหลักตัวที่สองแล้ว เพราะ seam ที่ต้องมี
  คือ "ปัจจัยหลัก*เพิ่มเติม*" ซึ่งทำแล้ว ส่วนการย้ายรหัสผ่านออกจาก core ไม่ได้
  ทำให้อะไรถอดได้เพิ่มขึ้น — รหัสผ่านต้องอยู่เสมอตาม ADR 0028 ข้อ 7)
- ยังไม่มีหน้า "อุปกรณ์ที่ login อยู่" / ปุ่มออกจากระบบทีละเครื่อง — ต้องมี session
  store ฝั่ง server ก่อน (ADR 0020) ตอนนี้ทำได้แค่เปลี่ยนรหัสผ่านซึ่งไล่ออกทุกใบพร้อมกัน
- **ยังไม่มี: nested group ของ LDAP · การหมุนความลับโดยไม่ restart ·
  KMS ของผู้ให้บริการคลาวด์** (รูปสัญญาเดียวกับ `secrets` ที่มีแล้ว แต่ยังไม่มี
  ใครต้องใช้) · IaC ตาม infra เป้าหมายจริง
- **ยังไม่ลองใหม่เมื่อ MySQL deadlock (error 1213)** — หลังแก้ ADR 0032 แล้ว
  ยังเจอ 2 ครั้งต่อรอบที่ 25 VUs · deadlock ลองใหม่ได้ตามนิยาม (ฐานข้อมูลยกเลิก
  ฝ่ายหนึ่งให้เอง) ต่างจากการชน `prev_hash` ที่ต้องย้อนทั้ง transaction
- ~~ยังไม่ปรับ `--workers` ของ gunicorn~~ **แก้แล้ว (ADR 0052 — G5)**:
  multi-worker เป็น opt-in — `WEB_CONCURRENCY>1` ต้องคู่กับ
  `METRICS_MULTIPROC_DIR` (ไม่คู่ = ไม่ start) แล้ว `/metrics` รวมทุก worker
  ของ container ถูกต้อง (กลไก stdlib: ไฟล์ snapshot ต่อ worker + merge ตอน
  scrape — `tests/test_metrics_multiproc.py`) · ค่าเริ่มต้นยัง 1 worker ·
  scale หลักยัง replica · ตัวเลขเฟส 16 ใน `docs/PERFORMANCE.md`
- ~~ยังไม่มีใคร scrape `/metrics` จริง~~ **ปิดแล้ว (เฟส 16)** — `compose.metrics.yaml`
  (Prometheus + Grafana · token จากไฟล์ อ่านใหม่ทุกรอบ scrape) และ job `scrape`
  พิสูจน์ทุก push ว่าตัวเลขถึง TSDB ผ่านด่าน token จริง

## Phase 8–12 ปิดแล้ว — scaffolding ที่ export ได้และวัดผลแล้ว (2026-08-14)

**อะไรเปลี่ยนไป**: `gates.yaml` เป็นดัชนี gate ที่ตรวจสองทิศ · `SKILL.md`
generate จาก portable gate · `overlays/flask/` เอากฎไปบังคับที่โปรเจกต์อื่นได้
และ repo นี้ dogfood ตัวเองทุก push · ทุก plugin ประกาศ `migration` class ที่มี
ตัวเลขวัดหนุน · `scripts/run_gates.py` เป็น fail-fix loop · และ `docs/comparison/`
วัดว่าทั้งหมดนี้เปลี่ยนโค้ดจริงไหม

**ผลของการวัดนั้นกลับมาแก้ความเชื่อของเราเอง**: การสั่งให้ agent "ทบทวนงาน
ตัวเองหนึ่งรอบ" เฉย ๆ ปิดช่องว่างด้านความปลอดภัยไปได้ ~3 ใน 4 ของที่ scaffolding
ทำได้ · สิ่งที่ scaffolding ให้แล้วอย่างอื่นให้ไม่ได้คือ **ข้อตกลงเฉพาะของ
โปรเจกต์** (soft delete ไม่มีแอปไหนในแขนทบทวนคิดถึงเลยสักตัว) กับความสม่ำเสมอ

## Phase 5–7 ปิดแล้ว (2026-08-12)

**อะไรเปลี่ยนไปหลัง Phase 5**: ฐานข้อมูล/cache/แหล่งความลับ/ปัจจัยยืนยันตัวตน
เป็น plugin ที่เลือกด้วย config ตัวเดียวทั้งหมด · มี stack ที่รันจริงพร้อม
reverse proxy, TLS, ≥2 replica, IdP และ directory · CI มี **25 job (27 check)** ที่ยิง
ของจริงทุก push (ไม่ใช่ mock): สามยี่ห้อฐานข้อมูล, stack, SSO, LDAP, Vault,
image, timer ของงานลบข้อมูล

**อะไรเปลี่ยนไปหลัง Phase 6**: มีตัวเลขจริงแทนคำว่า "เร็วพอ" — เป้าเป็นตัวเลข
ที่มีที่มา (ADR 0031), มี `/metrics` ที่ต้องมี token, มีชุด load test ที่รันซ้ำได้
ใน repo และรายงานผลใน `docs/PERFORMANCE.md` · และการวัดนั้นเป็นตัวที่**หาบั๊ก
ของ Phase 5 เจอ** (สาย audit ต่อขนานข้าม process ไม่ได้ → ADR 0032)

**อะไรเปลี่ยนไปหลัง Phase 7**: มีการประเมินต่อเกณฑ์ภายนอกที่ **หลักฐานทุกชิ้น
ชี้ไปได้จริง** (ASVS 253/253 · ผ่าน 141) · ZAP ยิง stack จริงทุก push แบบที่ login
แล้ว · ผู้ใช้ขอสำเนาและปิดบัญชีตัวเองได้ · log ไปอยู่ที่ที่ค้นได้พร้อมกฎที่**พิสูจน์
แล้วว่าดังจริง** · และเอกสารทุกฉบับที่เพิ่มมามีเทสต์คุมไม่ให้เน่า

**บทเรียนที่ใช้ได้กับทุกเฟสถัดไป — สามข้อ เรื่องเดียวกัน:**
1. ด่านที่ "มีอยู่" กับด่านที่ "ครอบชั้นที่พังจริง" เป็นคนละเรื่อง และความต่าง
   มักอยู่ที่ **สัญญาณที่วัด** ไม่ใช่ตรรกะ (`openssl s_client` ตอบเหมือนกันไม่ว่า
   server ปฏิเสธหรือไม่มีใครฟังพอร์ต · `flask --help` คืน 0 แม้โหลดแอปไม่สำเร็จ ·
   fake ที่ใจดีกว่าของจริง · ด่าน "2 replica ใช้ได้" ที่ทดสอบแค่การอ่าน)
   **เขียนด่านใหม่ต้องทดสอบสองทิศเสมอ**: พังเมื่อควรพัง และผ่านเมื่อควรผ่าน
2. **การวัดรอบเดียวไม่ใช่หลักฐาน** p99 ของสี่รอบที่เหมือนกันทุกอย่างต่างกันได้
   สี่เท่า — สิ่งที่ยืนยันได้คือ "ไม่มีรอบไหนตกเกณฑ์" ไม่ใช่ค่าใดค่าหนึ่ง
   (หลักเดียวกับ mutation test: พิสูจน์ด้วยการที่มันแดงเมื่อควรแดง
   ไม่ใช่ด้วยการที่มันเขียวหนึ่งครั้ง)
3. **เครื่องมือวัดที่เราสร้างเองเพื่อพิสูจน์ว่าแก้ถูก ก็โกหกได้** (Phase 7) —
   repro ที่ยืนยันว่า deadlock หายไปเรียก `audit.record()` เป็น statement แรก
   ซึ่งไม่มีคำขอจริงใบไหนทำ (ทุกใบอ่านก่อนเขียน) มันจึงรายงาน 160/160 ผ่าน
   ทั้งที่ของจริงผ่าน 21/160 · **เพิ่มการอ่านหนึ่งบรรทัด ตัวเลขเปลี่ยนจาก
   "แก้แล้ว" เป็น "ยังพังอยู่ 87%"** — อันตรายกว่าสองข้อบน เพราะมันตอบว่าผ่าน
   ในจังหวะที่เรากำลังอยากได้ยิน · **repro ต้องเหมือนรูปของคำขอจริง ไม่ใช่แค่
   เรียกฟังก์ชันที่สงสัย**
