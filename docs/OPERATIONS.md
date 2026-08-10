# การรันงานตามรอบ (retention)

ระยะเก็บรักษาใน [DATA-CLASSIFICATION.md](DATA-CLASSIFICATION.md) — soft delete 30 วัน,
audit 1 ปี — **เป็นแค่ตัวเลขในเอกสารจนกว่าจะมีอะไรสั่งลบตามรอบจริง**
`flask purge-expired` เป็นคำสั่งเดียวในระบบที่ลบข้อมูลจริง แต่ตัวมันเองไม่ได้
ตั้งเวลาให้ เอกสารนี้คือส่วนที่ทำให้ระยะที่อนุมัติไว้เกิดขึ้นจริงบนเครื่องที่ deploy

> **สถานะตอนนี้: ยังไม่มี host ไหนติดตั้งตารางเวลานี้** เพราะยังไม่มีการ deploy จริง
> (ดู ROADMAP Phase 5) สคริปต์กับขั้นตอนพร้อมแล้ว รอเอาไปติดตั้งตอนมี host

## สคริปต์

`scripts/purge_cron.sh` — ตัวห่อ `flask purge-expired` ให้เหมาะกับการรันแบบไม่มีคนดู

ทำสามอย่างที่การเรียก `flask purge-expired` ตรง ๆ จาก cron ไม่ได้ให้:

1. **หา repo root เอง** — cron รันด้วย cwd และ PATH คนละชุดกับ shell ของคน
   สคริปต์หาไดเรกทอรีจากตำแหน่งไฟล์จริง (ผ่าน symlink ได้) แล้ว `cd` เอง
2. **ล็อกกันรอบทับกัน** (`flock`) — รอบที่แล้วยังไม่จบแล้วรอบใหม่เข้ามาจะแย่งลบ
   แถวเดียวกัน เจอชนกันแล้วข้ามรอบนั้นไปเงียบ ๆ และจบด้วย exit 0 (ไม่ใช่ความผิดพลาด)
3. **ตรวจสาย audit ต่อท้าย** — purge เป็นงานเดียวที่ลบแถว audit ได้จริง
   (ตัดจากหัวสายแล้วเขียน checkpoint) จึงเป็นจังหวะที่คุ้มที่สุดที่จะพิสูจน์ว่า
   สายยังต่อกันอยู่ ถ้า `audit-verify` ไม่ผ่าน สคริปต์จบด้วย exit ที่ไม่ใช่ 0

### ตัวแปรแวดล้อม

| ตัวแปร | ค่าเริ่มต้น | ใช้ทำอะไร |
|---|---|---|
| `TDL_PURGE_LOCK` | `/tmp/todolist-purge.lock` | ไฟล์ล็อก — ตั้งใหม่ถ้ารันหลาย instance บนเครื่องเดียว |
| `TDL_PURGE_VERIFY_AUDIT` | `1` | ตั้ง `0` เพื่อข้ามการตรวจสาย audit หลัง purge |

### exit code

| ค่า | ความหมาย | ต้องทำอะไร |
|---|---|---|
| `0` | สำเร็จ **หรือ** ข้ามรอบเพราะรอบก่อนยังไม่จบ | ไม่ต้อง |
| ไม่ใช่ `0` | purge ล้มเหลว หรือ `audit-verify` ไม่ผ่าน | **ต้องมีคนดู** — ดูหัวข้อล่างสุด |

## ขั้นตอนหลัง deploy ทุกครั้ง (ลำดับนี้สำคัญ)

```
pipenv sync                                 # ไลบรารีของ core
pipenv sync --categories="$(pipenv run flask plugin-deps --categories)"   # ของ plugin
pipenv run flask db upgrade                 # ตารางของ core
pipenv run flask plugin-list                # ตารางของ plugin ตัวไหนยังไม่ถูกสร้าง
pipenv run flask plugin-install auth/totp   # ตารางของ plugin ที่ต้องการใช้
```

**ไลบรารีของ plugin ไม่ได้อยู่ใน `[packages]`** (ADR 0025) — `pipenv sync` เฉย ๆ
จึงไม่ติดตั้งให้ ตั้งใจให้เป็นแบบนี้เพื่อให้ "ไม่ใช้ plugin ตัวนั้น" แปลว่า
"ไม่ต้องเฝ้า CVE ของไลบรารีที่มันลากมา" ด้วยจริง ๆ
ข้ามขั้นนี้ระบบยังทำงานปกติ แค่ความสามารถที่พึ่งไลบรารีนั้นจะปิดตัวเองเงียบ ๆ
(`flask plugin-deps` บอกว่าอะไรขาด)

**ตารางของ plugin ไม่ได้อยู่ในสาย migration ของ core โดยตั้งใจ** (ADR 0023)
`db upgrade` จึงไม่สร้างให้ ถ้าข้ามขั้นที่สอง plugin นั้นจะถูกข้ามไปเงียบ ๆ
(ระบบยังทำงานปกติ แค่ไม่มีความสามารถนั้น — core เช็คให้ก่อนใช้งานเสมอ)

## เมื่อมี CVE ของไลบรารีที่ plugin ใช้ (ปิดทันทีโดยไม่ต้อง deploy)

```
pipenv run flask plugin-deps                # ใครพึ่งไลบรารีตัวนั้นบ้าง
# ใส่คีย์ที่ได้ลง .env แล้ว restart process (registry อ่าน config ตอน start)
DISABLED_PLUGINS=auth/totp#qr-segno
pipenv run flask plugin-list                # ต้องขึ้น DISABLED ต่อท้ายบรรทัดนั้น
```

ปิดแล้วระบบเดินต่อได้เหมือนไม่เคยมีของชิ้นนั้น และ `plugin-deps --categories`
จะไม่คืน category ของมันอีก — `pipenv sync` รอบถัดไปจึงไม่ติดตั้งไลบรารีนั้นแล้ว

**ข้อมูลของ plugin ยังอยู่ครบ** การปิดสวิตช์ไม่ลบอะไรทั้งสิ้น และคำสั่ง
`plugin-uninstall` ยังใช้ได้ตามปกติแม้ปิดสวิตช์ไว้ (ถ้าตัดสินใจเลิกใช้ถาวร)
ปิด plugin ของ core ไม่ได้ — ใส่ไปแล้วแอปจะไม่ start พร้อมบอกว่าคีย์ไหนผิด

**ระวังคีย์ของ plugin แม่กับของส่วนเสริมต่างกันแค่ `#`** — `auth/totp` คือปิด
การยืนยันสองขั้นทั้งหมด (คนที่เปิดไว้จะ login ด้วยรหัสผ่านอย่างเดียวได้ทันที
ข้อมูลยังอยู่ครบ เปิดกลับก็เหมือนเดิม) ส่วน `auth/totp#qr-segno` คือปิดแค่ตัววาด QR
ปิดปัจจัยยืนยันตัวตนจะมี log เตือนแยกอีกบรรทัดบอกผลที่ตามมาตรง ๆ ทุกครั้งที่ start

ทุกครั้งที่แอป start จะมีบรรทัด log ระดับ `WARNING` บอกว่าตอนนั้นอะไรถูกปิดอยู่
ใช้ตรวจย้อนหลังได้ว่าช่วงไหนระบบเดินอยู่โดยไม่มีความสามารถนั้น

### CVE มาจากไหน — ให้ CI บอก อย่าไล่เดา

- job **`plugin-audit`** audit ไลบรารีของ plugin **ทีละ category** จึงบอกได้ว่า
  CVE ตัวนั้นเป็นของจุด plug ไหน · job นี้ **ไม่ทำให้ pipeline แดง** โดยตั้งใจ
  (ของที่ถอดได้ ไม่ควรหยุด release ของ core) แต่จะยิง `::warning::` กับสรุปของ run
  ทุกครั้ง — เห็นเมื่อไหร่ให้ตัดสินใจว่า *ถอด* หรือ *อัปเกรด* ไม่ใช่ปล่อยผ่าน
- job **`security`** audit เฉพาะ core ซึ่งถอดไม่ได้ — ที่นั่นแดงคือแดงจริง ต้องแก้
- artifact **`sbom`** ของทุก run มี `sbom-core.json` กับ `sbom-<category>.json`
  แยกไฟล์ ใช้ตอบคำถาม "ถอด plugin ตัวนี้แล้ว component ไหนหายไปบ้าง" ได้ทันที

### ความสามารถหายไปทั้งที่ไม่ได้ปิดอะไรเลย

```
pipenv run flask plugin-list     # ดูคอลัมน์ provides <ความสามารถ> (serving / NOT serving)
```

`NOT serving` ทั้งที่ไม่มี `DISABLED` และไลบรารีก็ครบ = มีผู้ให้บริการความสามารถ
นั้นมากกว่าหนึ่งตัวแต่ไม่มีใครเลือก (ระบบปิดไว้ทั้งหมด — ไม่เดาให้) หรือ
`PLUGIN_PICKS` ชี้ไปตัวที่ตอนนี้ใช้ไม่ได้ · คำสั่งเดียวกันจะ log เหตุผลออกมาด้วย
แก้โดยระบุตัวที่ต้องการใน `.env`:

```
PLUGIN_PICKS=auth/totp#qr=qr-segno
```

## ก่อนติดตั้งครั้งแรก

ดูก่อนเสมอว่ามันจะลบอะไร — `--dry-run` เป็นฟังก์ชันอ่านอย่างเดียวคนละตัวกับตัวลบจริง

```
pipenv run flask purge-expired --dry-run
```

แล้วลองรันตัวสคริปต์ด้วยมือหนึ่งครั้งจากไดเรกทอรีอื่น (พิสูจน์ว่ามันหา repo เจอเอง):

```
cd /tmp && /path/to/todolist/scripts/purge_cron.sh
```

## ติดตั้งตารางเวลา

รันด้วย **ผู้ใช้ที่เป็นเจ้าของ `.env` และไฟล์ฐานข้อมูล** ไม่ใช่ root
(root จะสร้างไฟล์ที่ผู้ใช้แอปเขียนต่อไม่ได้ ถ้าเผลอไปแตะ)

รอบที่แนะนำคือ **วันละครั้งช่วงที่คนใช้น้อย** ระยะเก็บรักษาเป็นหน่วยวัน
ความถี่กว่านี้ไม่ได้ทำให้ตรงตามนโยบายมากขึ้น มีแต่เพิ่มโอกาสชนกันเอง
เวลาที่ยกตัวอย่างเป็น 03:17 — เลี่ยงนาทีที่ 0 เพราะเป็นจุดที่งานตามรอบทั้งเครื่องชอบมากอง

### cron ของผู้ใช้ (ง่ายสุด ไม่ต้องใช้ sudo)

```
crontab -e
```

```cron
17 3 * * * /path/to/todolist/scripts/purge_cron.sh >> /var/log/todolist/purge.log 2>&1
```

### /etc/cron.d (ทั้งระบบ — ต้องใช้ sudo)

```cron
# /etc/cron.d/todolist-purge
17 3 * * *  appuser  /path/to/todolist/scripts/purge_cron.sh >> /var/log/todolist/purge.log 2>&1
```

> เครื่อง dev ปัจจุบันเป็น Gentoo + OpenRC (ไม่มี systemd) จึงใช้ cron
> ต้องมี cron daemon เปิดอยู่จริง: `rc-service cronie status`

### systemd timer (ถ้า host ที่ deploy ใช้ systemd)

```ini
# /etc/systemd/system/todolist-purge.service
[Unit]
Description=todolist retention purge

[Service]
Type=oneshot
User=appuser
ExecStart=/path/to/todolist/scripts/purge_cron.sh
```

```ini
# /etc/systemd/system/todolist-purge.timer
[Unit]
Description=รัน todolist retention purge วันละครั้ง

[Timer]
OnCalendar=*-*-* 03:17:00
Persistent=true

[Install]
WantedBy=timers.target
```

```
systemctl enable --now todolist-purge.timer
systemctl list-timers todolist-purge.timer
```

`Persistent=true` สำคัญ — เครื่องปิดอยู่ตอนถึงเวลาแล้วเปิดมาใหม่ มันจะรันชดเชยให้
ไม่ใช่ข้ามไปทั้งวัน (cron ธรรมดาไม่ชดเชยให้ ถ้า host ปิด ๆ เปิด ๆ ให้ใช้ anacron แทน)

## รันด้วย container image (Phase 5 · P5-09)

```
docker build -t todolist .
docker run -p 8000:8000 \
  -e SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" \
  -e DATABASE_URL="mysql+pymysql://user:pass@dbhost/todolist" \
  todolist
```

**image ไม่ migrate ฐานข้อมูลให้เอง** และไม่ใช่เพราะลืม — การเปลี่ยน schema เป็น
การตัดสินใจของผู้ดูแล ไม่ใช่ผลข้างเคียงของการ start container ถ้า migrate อัตโนมัติ:
deploy ที่ rollback แล้วจะเจอฐานข้อมูลที่ล้ำหน้าโค้ดอยู่ และการ start หลาย replica
พร้อมกันจะแย่งกัน migrate — รัน `flask db upgrade` เป็นขั้นตอนแยกก่อนปล่อยของใหม่
(ดูหัวข้อ "ขั้นตอนหลัง deploy ทุกครั้ง")

**ไลบรารีของ plugin ไม่ได้อยู่ใน image** ตามหลักของ ADR 0025 — ใครใช้ยี่ห้อไหน
หรือเปิดส่วนเสริมตัวไหน ต่อ image นี้แล้วติดตั้ง category ของตัวเองเพิ่ม:

```dockerfile
FROM todolist
USER root
RUN pipenv sync --categories="plugin-db-mysql"
USER todolist
```

**รันหลาย worker/replica ต้องตั้ง `CACHE_URL` ให้ชี้ store ที่แชร์ได้ด้วย**
ไม่งั้นเพดาน rate limit จะเป็น N เท่าตามจำนวน process (แอปเตือนตอน start
ถ้ารู้ว่า store ไม่แชร์ — ดู `app/cache.py`) จำนวน worker ตั้งด้วย
`WEB_CONCURRENCY` หรือ `GUNICORN_CMD_ARGS`

**สิ่งที่ image รับประกันและมีด่านใน CI (`job: image`) ตรวจทุก push**
- รันในนามผู้ใช้ `todolist` ไม่ใช่ root
- โค้ดใน `/app` เขียนทับไม่ได้ (process ที่ถูกยึดแก้โค้ดตัวเองไม่ได้)
- ไม่มี `tests/`, `docs/`, `.env`, `instance/` อยู่ข้างใน
- start แล้ว healthcheck ขึ้น healthy และ `GET /login` ตอบ 200
- log ของแอปออก stderr ส่วน access log ออก stdout (ADR 0011 หมายเหตุท้ายไฟล์)

## รัน stack ทั้งชุดด้วย compose (Phase 5 · P5-10)

```
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"

docker compose up                                          # SQLite (เร็วที่สุด)
docker compose -f compose.yaml -f compose.mysql.yaml up     # MySQL 8
docker compose -f compose.yaml -f compose.mariadb.yaml up   # MariaDB 11
docker compose -f compose.yaml -f compose.sso.yaml up       # + Keycloak (สำหรับ SSO)
```

ยี่ห้อที่ไม่ใช่ SQLite ต้องตั้ง `DB_PASSWORD` กับ `DB_ROOT_PASSWORD` ด้วย
ส่วน Keycloak ต้องมี `KEYCLOAK_ADMIN_PASSWORD` — **ทุกตัวไม่มีค่าเริ่มต้น**
compose จะไม่ start พร้อมบอกว่าขาดอะไร แทนที่จะขึ้นมาด้วยรหัสที่ทุกคนรู้

**เลือกยี่ห้อด้วยไฟล์ override ไม่ใช่ตัวแปร** เพราะการเลือกต้องเปลี่ยนสองอย่าง
พร้อมกัน (service ที่ start กับ `DATABASE_URL` ที่ app ใช้) แยกเป็นสองตัวแปร
เมื่อไหร่ วันหนึ่งจะมีคนแก้ตัวเดียวแล้วได้ stack ที่ start MySQL ขึ้นมาแต่ app
ยังเขียนลง SQLite — ไฟล์ override ทำให้สองอย่างนั้นอยู่ด้วยกันเสมอ (ADR 0026)

**ต้อง migrate เองหลัง `up` ครั้งแรก** — image ไม่ทำให้ตามเหตุผลข้างบน:

```
docker compose -f compose.yaml -f compose.mysql.yaml run --rm app flask db upgrade
docker compose -f compose.yaml -f compose.mysql.yaml run --rm app flask create-user somchai
```

**ไลบรารีของ plugin เข้ามาทาง build arg** — `compose.yaml` ส่ง `PLUGIN_CATEGORIES`
ให้ image ตามยี่ห้อที่เลือก (เช่น `plugin-cache-redis plugin-db-mysql`)
image พื้นฐานไม่มีของพวกนี้ตาม ADR 0025 และ backend ที่ถูกเลือกจะ `import`
ไลบรารีของมันตอนโหลด — **ไม่มีของ = แอปไม่ start** ซึ่งตั้งใจให้เป็นแบบนั้น
เพราะผู้ดูแลตั้งใจชี้ config มาที่ยี่ห้อนั้น การเงียบแล้วไม่ใช้ให้คือการโกหก

**ที่ CI ตรวจให้ทุก push (`job: stack`)**: stack ขึ้นครบและ healthy ทุก service ·
ตารางยังไม่มีก่อนสั่ง migrate (พิสูจน์ว่า image ไม่แอบ migrate) · สร้าง user แล้ว
login ผ่าน CSRF ได้ 302 · ข้อมูลลงฐานข้อมูลของ stack จริงไม่ใช่ SQLite ใน image

## เวลาที่งานล้มเหลว

**อย่าปล่อยผ่าน** — งานตามรอบที่ล้มเหลวเงียบ ๆ แย่กว่าไม่มีงานตามรอบเลย
เพราะเอกสารยังอ้างว่าลบภายใน 30 วันอยู่ทั้งที่ไม่มีอะไรลบมาหลายเดือน

- **purge ล้มเหลว** — ข้อมูลที่พ้นระยะยังอยู่ครบ ไม่มีอะไรเสียหาย แต่ผิดนโยบาย
  ตั้งแต่วินาทีนั้น แก้แล้วรันด้วยมือได้เลย ไม่ต้องรอรอบถัดไป
- **`audit-verify` ไม่ผ่าน** — เรื่องใหญ่กว่ามาก แปลว่าสาย hash ขาดหรือมีคนแก้แถวเก่า
  **ห้ามรัน purge ซ้ำเพื่อ "ให้มันหาย"** ให้เก็บฐานข้อมูลไว้ตามสภาพแล้วตรวจด้วยคน
  (`flask audit-log` ดูรอบ ๆ จุดที่ขาด) ดู ADR 0015 ว่าสายบอกอะไรได้บ้างและบอกไม่ได้บ้าง

ตอนนี้ยังไม่มีการส่ง alert อัตโนมัติ — ต้องพึ่งเมลของ cron หรือ log ที่ redirect ไว้
การต่อเข้าระบบ monitoring จริงอยู่ใน Phase 7 (งาน SIEM)
