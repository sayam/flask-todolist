# การรันงานตามรอบ (retention)

ระยะเก็บรักษาใน [DATA-CLASSIFICATION.md](DATA-CLASSIFICATION.md) — soft delete 30 วัน,
audit 1 ปี — **เป็นแค่ตัวเลขในเอกสารจนกว่าจะมีอะไรสั่งลบตามรอบจริง**
`flask purge-expired` เป็นคำสั่งเดียวในระบบที่ลบข้อมูลจริง แต่ตัวมันเองไม่ได้
ตั้งเวลาให้ เอกสารนี้คือส่วนที่ทำให้ระยะที่อนุมัติไว้เกิดขึ้นจริงบนเครื่องที่ deploy

> **สถานะตอนนี้: ยังไม่มี host ไหนติดตั้งตารางเวลานี้** เพราะยังไม่มีการ deploy จริง
> (ดู ROADMAP Phase 5) สคริปต์กับขั้นตอนพร้อมแล้ว รอเอาไปติดตั้งตอนมี host

> งานปฏิบัติการอีกเรื่องที่มี runbook ของตัวเอง: **backup/restore** อยู่ใน
> [RUNBOOK-BACKUP.md](RUNBOOK-BACKUP.md) — การซ้อม restore เป็นเทสต์ที่รัน
> ทุก push และคีย์ encrypt ต้องแยกจาก backup ของฐานเสมอ

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

## โพรบสุขภาพ (`/healthz` · `/readyz` — ADR 0048)

- `GET /healthz` = โปรเซสยังหายใจไหม — **ไม่แตะฐานข้อมูลโดยตั้งใจ** (liveness
  ที่ล้มตาม DB จะสั่ง restart ทุก replica พร้อมกันตอน DB สะดุด)
- `GET /readyz` = พร้อมรับงานไหม (`SELECT 1` จริง → 200/503) — ตัวที่ proxy/
  orchestrator ควรใช้ตัดสินการส่งงาน · HEALTHCHECK ของ image ใช้ตัวนี้อยู่แล้ว
- ทั้งคู่ไม่มี token ไม่มีข้อมูลภายใน และ**ไม่ลง log รายคำขอ** (ล้มยัง log)
- **อย่าประกาศ healthcheck ทับใน compose** — ของ image แนบ header
  `X-Forwarded-Proto` ไว้ ไม่งั้นใต้ stack TLS โพรบจะโดน redirect วนแล้ว app
  ค้าง unhealthy ทั้งที่เสิร์ฟปกติ (เจอจริงตอนเฟส 16)

## คีย์ encrypt (`DATA_ENCRYPTION_KEY` — ADR 0046)

ความลับ TOTP ถูก encrypt ใต้คีย์นี้ (base64 ของ 32 ไบต์ · แยกจาก `SECRET_KEY`
โดยตั้งใจ · ตั้งผ่าน env หรือ secrets source ก็ได้เพราะอยู่ใน `CORE_SECRETS`)

- **สำรองคีย์แยกจากสำรองฐานข้อมูล** — dump ฐานข้อมูลอย่างเดียวอ่านความลับ
  ไม่ได้ (นั่นคือ point) แต่แปลว่า**ทำคีย์หาย = ความลับ TOTP อ่านไม่ได้ถาวร**
  ผู้ใช้ MFA ทุกคนต้อง enroll ใหม่
- **หมุนคีย์ = ต้อง re-encrypt ก่อนทิ้งคีย์เก่า** — รูปเก็บ `enc:v1:` หมุนได้
  ทีละแถว แต่ยังไม่มีคำสั่ง re-encrypt สำเร็จรูป (งานค้างที่รู้ตัว) · เปลี่ยน
  คีย์เฉย ๆ โดยไม่ re-encrypt = แถวเก่าถอดไม่ได้ (แอปดังเป็น error ชัดเจน
  ไม่คืนขยะ)
- **เครื่องที่ไม่มีคีย์/ไม่มี `cryptography`**: plugin totp ปิดตัวเองพร้อม
  warn ครั้งเดียว — แอปที่เหลือทำงานปกติ (นี่คือสภาพของ job `bare`)

## ขั้นตอนหลัง deploy ทุกครั้ง (ลำดับนี้สำคัญ)

> **สัญญา N-1 (ADR 0048)**: migration ของรุ่นใหม่ต้องไม่ฆ่าโค้ดรุ่นก่อนหน้า
> ที่ยังรันอยู่ระหว่าง rolling — วินัยคือ *expand–contract* (เพิ่มก่อน ·
> เลิกใช้ · ค่อย drop ในรุ่นถัดไป) · job `n-1` พิสูจน์ทุก push ด้วยการรัน
> โค้ดของ tag ล่าสุดทับ schema ใหม่จริง · gunicorn มี `--graceful-timeout 30`
> คำขอที่ค้างอยู่ได้จบก่อนโปรเซสตาย

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
  CVE ตัวนั้นเป็นของจุด plug ไหน · **job นี้แดงได้ตั้งแต่ audit รอบ 13**
  (ADR 0025 โน้ต 1) เพราะการเตือนใส่ annotation ของ job ที่เขียวอยู่ วัดแล้วว่า
  ไม่มีใครอ่าน — เกณฑ์ที่แดงคือ **"ยังไม่มีใครตัดสิน"** ไม่ใช่ "มี CVE":
  ปลดด้วยการอัปเกรด · ถอด plugin (`DISABLED_PLUGINS` — ยังเป็นคำตอบที่เร็วที่สุด) ·
  หรือรับไว้อย่างเปิดเผยด้วยบรรทัดใน `app/plugins/accepted-advisories.txt`
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

### systemd timer — **ติดตั้งจากไฟล์จริง ไม่ใช่คัดลอกจากเอกสาร** (P5-16)

```
# วาง repo ไว้นอก home (ดูเหตุผลข้างล่าง) แล้ว:
sudo ./scripts/install_purge_timer.sh --dry-run        # ดูก่อนว่าจะทำอะไร
sudo ./scripts/install_purge_timer.sh                  # แบบ repo (pipenv)

# แบบ container (stack ของ Phase 5):
sudo TDL_PURGE_RUNNER="docker compose -f /opt/todolist/compose.yaml \
     -f /opt/todolist/compose.mysql.yaml run --rm -T app" \
     ./scripts/install_purge_timer.sh
```

unit อยู่ที่ `deploy/systemd/` **เป็นไฟล์จริงในที่เก็บโค้ด** — ตัวอย่างที่ต้อง
คัดลอกด้วยมือจะเพี้ยนจากของจริงในวันที่มีคนแก้ที่เดียว และไม่มีอะไรตรวจได้ว่า
มันยังถูกอยู่ (job `purge-timer` ใน CI ตรวจไฟล์ชุดนี้ทุก push)

**สามอย่างที่เจอตอนติดตั้งบน host จริง และไม่มีทางเจอจากการอ่าน:**

1. **`ProtectHome=true` ทำให้ /home และ /root มองไม่เห็นจากในหน่วย** —
   ExecStart ที่ชี้ไปที่นั่นล้มด้วย `203/EXEC` ซึ่ง**ไม่บอกสาเหตุอะไรเลย**
   (อ่านแล้วนึกว่าลืม `chmod +x`) · ตัวติดตั้งจึงปฏิเสธตั้งแต่ต้นพร้อมบอกเหตุผล
   **ทุกอย่างที่หน่วยนี้แตะต้องอยู่นอก home** รวมถึงไฟล์ compose ด้วย
2. **`Environment=` แยกคำตามช่องว่าง** — ค่าที่ไม่ได้ใส่เครื่องหมายคำพูดจะ
   เหลือแค่คำแรก ส่วนที่เหลือถูกทิ้งพร้อมคำเตือนใน journal **แล้วรันต่อ**
   ด้วยค่าที่ผิด (runner กลายเป็น `docker` เฉย ๆ)
3. **timer ไม่มี environment ของ shell ใคร** — ค่าที่ compose ต้องใช้
   (`SECRET_KEY`, `DB_PASSWORD` ฯลฯ) ต้องมาจาก `/etc/todolist/purge.env`
   ซึ่งหน่วยอ่านให้เอง (`EnvironmentFile=-` แปลว่าไม่มีไฟล์ก็ไม่เป็นไร)

**ตรวจว่ามันทำงานจริง:**

```
systemctl list-timers todolist-purge.timer   # นับถอยหลังอยู่ไหม
systemctl start todolist-purge.service       # สั่งเดี๋ยวนี้เลย
systemctl is-failed todolist-purge.service   # รอบล่าสุดพังไหม
journalctl -u todolist-purge.service         # พังเพราะอะไร
```

**`Persistent=true` สำคัญกว่าที่เห็น** — เครื่องที่ปิดอยู่ตอนถึงเวลาจะรันให้
ทันทีที่เปิดมา ไม่ใช่ข้ามรอบนั้นไปเงียบ ๆ ถ้าไม่มีข้อนี้ เครื่องที่ดับทุกคืน
จะไม่เคย purge เลยสักครั้งโดยไม่มีใครรู้

### ตัวอย่าง unit (ของเดิม — ตัวจริงอยู่ใน `deploy/systemd/`)

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
`WEB_CONCURRENCY` (ปุ่มเดียวที่รองรับสำหรับหลาย worker — ADR 0052)

**หลาย worker ในหนึ่ง container (opt-in — ADR 0052)**: ตั้ง
`WEB_CONCURRENCY=N` คู่กับ `METRICS_MULTIPROC_DIR` เสมอ — ไม่ตั้งคู่
แอป refuse ตอน start (ไม่งั้นตัวเลข `/metrics` สลับตัวนับต่อ scrape) ·
dir ต้องเป็นที่ที่**ตายพร้อม container** (เช่น `/tmp/metrics` บน tmpfs)
เพราะไฟล์ตัวนับของ boot เก่าไม่ควรรอด restart · ไฟล์ของ worker ที่ตาย
ระหว่างรันถูกนับต่อโดยตั้งใจ (counter สะสม) · ค่าเริ่มต้นยังเป็น worker
เดียว และทาง scale หลักยังเป็น replica ตามเดิม (ADR 0048)

**สิ่งที่ image รับประกันและมีด่านใน CI (`job: image`) ตรวจทุก push**
- รันในนามผู้ใช้ `todolist` ไม่ใช่ root
- โค้ดใน `/app` เขียนทับไม่ได้ (process ที่ถูกยึดแก้โค้ดตัวเองไม่ได้)
- ไม่มี `tests/`, `docs/`, `.env`, `instance/` อยู่ข้างใน
- start แล้ว healthcheck ขึ้น healthy และ `GET /login` ตอบ 200
- log ของแอปออก stderr ส่วน access log ออก stdout (ADR 0011 หมายเหตุท้ายไฟล์)
- OS layer ไม่มี CVE ระดับ HIGH/CRITICAL ที่มี fix แล้วค้างอยู่ — trivy สแกน
  ทุก push และตัดสินสองทิศเทียบ `deploy/accepted-image-advisories.txt`
  (ADR 0054 — รายการยกเว้นควรว่างเป็นปกติ)

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

**image ทุกตัวในไฟล์ compose ถูกตรึงด้วย digest** (audit รอบ 15 —
`gate stack-images-pinned-and-moved`) จึงเป็นไบต์ชุดเดียวกันทุกเครื่องทุกครั้ง ·
ตัวขยับคือ ecosystem `docker-compose` ของ Dependabot ซึ่ง **ขอแค่ digest ใหม่
ไม่ใช่ยี่ห้อรุ่นใหม่** (`ignore` ของ major/minor ตั้งไว้แบบเดียวกับ base image) ·
การขึ้นรุ่นยี่ห้อเป็นคำตัดสินที่ต้องขยับเอกสาร เทสต์ และคอนฟิกพร้อมกัน

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

## รันหลาย replica (Phase 5 · P5-11)

```
docker compose -f compose.yaml -f compose.mysql.yaml -f compose.scale.yaml \
    up -d --scale app=2
# ทางเข้าอยู่ที่ proxy พอร์ต 8080 — app ไม่ publish พอร์ตของตัวเองแล้ว
```

**ต้องใช้กับยี่ห้อที่ไม่ใช่ SQLite** — SQLite ล็อกทั้งไฟล์ตอนเขียน สอง replica
ที่เขียนพร้อมกันจะได้ "database is locked" เป็นระยะ พอขึ้นหลาย replica
การเลือกยี่ห้อจึงไม่ใช่รสนิยมอีกต่อไป

**สามอย่างที่ต้องจริงพร้อมกัน** (job `stack` ใน CI ตรวจให้ทุก push):

1. **ทั้งสอง replica ได้รับคำขอจริง** ไม่ใช่แค่ start ขึ้นมา — nginx ต้อง
   `proxy_pass` ผ่าน**ตัวแปร** ไม่ใช่เขียนชื่อ host ลงไปตรง ๆ เพราะแบบหลัง
   nginx จะ resolve ครั้งเดียวตอนโหลด config แล้วจำไอพีนั้นไว้ตลอด →
   **ทุกคำขอวิ่งไป replica ตัวเดิมตัวเดียวโดยไม่มี error อะไรให้เห็น**
2. **โควตา rate limit เป็นก้อนเดียวข้าม replica** — มาจาก `CACHE_URL` ที่ชี้
   redis (P5-07) ถ้าเป็น `memory://` เพดานจริงจะเป็น N เท่าของที่ตั้งไว้
   แอปเตือนตอน start อยู่แล้วถ้ารู้ว่า store ไม่แชร์
3. **คุกกี้ที่ replica หนึ่งออกให้ ต้องใช้กับอีก replica ได้** — จริงเพราะสถานะ
   ของ session อยู่ในคุกกี้ที่เซ็นด้วย `SECRET_KEY` เดียวกันทั้งหมด ไม่มี state
   ค้างในหน่วยความจำของ process (`tests/test_proxy.py` เป็นตัวจับถ้าวันหนึ่งมีคนใส่เข้ามา)

**`TRUSTED_PROXY_HOPS` ต้องตรงกับจำนวน proxy ที่มีจริง** (ADR 0027)
`compose.scale.yaml` ตั้งเป็น 1 มาให้แล้วเพราะไฟล์นั้นเป็นคนวาง nginx เอง —
เพิ่มชั้นหน้าไปอีก (CDN, LB ขององค์กร) ต้องเพิ่มตัวเลขนี้ตาม ไม่งั้นไอพีที่แอปเห็น
จะเป็นของชั้นกลาง ไม่ใช่ของผู้ใช้

## เปิด TLS กับ HSTS (Phase 5 · P5-12)

```
./scripts/dev_tls_cert.sh          # ครั้งแรกเท่านั้น (ใบ self-signed สำหรับ dev)
docker compose -f compose.yaml -f compose.mysql.yaml \
    -f compose.scale.yaml -f compose.tls.yaml up -d --scale app=2
# https://localhost:8443 — ขา http (8080) เหลือไว้ส่งต่อไป https เท่านั้น
```

**ต้องต่อจาก `compose.scale.yaml`** เพราะไฟล์นั้นเป็นคนวาง proxy ลงไป และ TLS
เป็นคุณสมบัติของ proxy ไม่ใช่ของ app (app ยังพูด http อยู่ข้างหลังเหมือนเดิม)
ใช้กับ replica เดียวก็ได้

**`HTTPS_ENABLED=1` กับใบรับรองอยู่ในไฟล์เดียวกันโดยตั้งใจ** เปิดตัวใดตัวหนึ่ง
อย่างเดียวคือสองอาการที่แก้ยากพอกัน: เปิดแฟล็กแต่ไม่มี TLS = redirect วนจน
login ไม่ได้ · มี TLS แต่ไม่เปิดแฟล็ก = คุกกี้ไม่มี `Secure` และไม่มี HSTS
ทั้งที่ผู้ใช้เข้าใจว่าปลอดภัยแล้ว

**ใบจริงวางที่ `deploy/tls/server.crt` + `server.key`** ชื่อเดียวกับของ dev
ไดเรกทอรีนั้นถูก gitignore ไว้ — คีย์ไม่ควรอยู่ใน git แม้จะเป็นของ dev

### สามอย่างที่ต่างจากขา http และต้องรู้ก่อนแก้บั๊ก

1. **`ssl_protocols TLSv1.2 TLSv1.3;` ต้องประกาศเอง** — ไม่ประกาศไม่ได้แปลว่า
   "ใช้ค่าที่ปลอดภัยตามสมัย" แต่คือปล่อยให้ image ตัดสินแทน
2. **`proxy_set_header Host $http_host;` ไม่ใช่ `$host`** — `$host` ตัดพอร์ตทิ้ง
   แล้ว Flask-WTF จะปฏิเสธทุก POST ด้วย **400** (มันเทียบ Referer กับ url_root
   ของคำขอ ซึ่งไม่ตรงเมื่อพอร์ตหาย) **การตรวจ Referer นี้ทำงานเฉพาะ https**
   ขา http จึงไม่เคยแสดงอาการนี้เลย
3. **คำขอ POST ที่ไม่มี Referer จะได้ 400 บน https** (`WTF_CSRF_SSL_STRICT`)
   browser ส่งให้เองอยู่แล้ว แต่ curl/สคริปต์ต้องใส่ `-e <url>` เอง
   — `/api/v1` ไม่กระทบเพราะยกเว้น CSRF ทั้ง blueprint อยู่แล้ว (ADR 0018)

**HSTS มีเจ้าของเดียวคือแอป** (Talisman — ADR 0010) ไม่ได้ตั้งซ้ำที่ nginx
เพราะสองที่จะเพี้ยนจากกันวันที่มีคนแก้ `max-age` ที่เดียว · ด่านใน CI ตรวจว่า
header นี้มีมา **หนึ่งบรรทัดพอดี**

## Auth หลาย profile (เฟส 17 — ADR 0047)

plugin ยืนยันตัวตนภายนอกตัวเดียวรับ config ได้หลายชุดด้วย
`AUTH_PROFILES="oidc:corp,ldap:hq"` — ค่าของแต่ละ profile ใช้คีย์ที่สอดชื่อ
ไว้ (`OIDC_CORP_ISSUER`, `LDAP_HQ_URL`) และ**ไม่ตกกลับคีย์เปล่า**

- **ลำดับที่ประกาศคือลำดับที่ลอง** และคำปฏิเสธเป็นที่สิ้นสุด — ระบบเลื่อนไป
  ถามวงถัดไปเฉพาะเมื่อวงก่อนหน้า *ติดต่อไม่ได้* (timeout/ต่อไม่ติด)
- **callback URL ของ OIDC เป็นของแต่ละ profile**:
  `https://<โฮสต์>/login/sso/auth/oidc:corp/callback` — เพิ่ม profile ใหม่
  ต้องไปลงทะเบียน redirect URI ใบใหม่ที่ IdP ด้วย ไม่งั้น IdP ปฏิเสธตั้งแต่ขาไป
- ปิดชั่วคราวทีละ profile ได้ด้วย `DISABLED_PLUGINS=auth/oidc:corp`
  (คีย์ดูจาก `flask plugin-list`) — profile อื่นของ plugin เดียวกันไม่กระทบ
- `AUTH_PROFILES` ที่ชี้ plugin ที่ไม่มี/รูปแบบผิด/ซ้ำ = **แอปไม่ start**
  (หลักเดียวกับ scheme ของ `DATABASE_URL` — ADR 0026)

## Prometheus + Grafana ดูด `/metrics` (เฟส 16 · 16-04)

```bash
# 1) ออก token ให้ตัวดูด (/metrics ต้องมี token เสมอ — ADR 0031)
flask token-create <ผู้ใช้> --name "prometheus"   # เก็บบรรทัด token ลงไฟล์
echo 'tdl_...' > ./metrics-token

# 2) ขึ้น stack — Prometheus อ่าน token จากไฟล์ (อ่านใหม่ทุกรอบ scrape
#    เพิกถอนใบเก่า/ออกใบใหม่แล้วแก้ไฟล์ได้เลย ไม่ต้อง restart)
METRICS_TOKEN_FILE=$PWD/metrics-token GRAFANA_PASSWORD=... \
  docker compose -f compose.yaml -f compose.metrics.yaml up -d
```

- Prometheus: `:9090` · Grafana: `:3001` (datasource ถูก provision จากไฟล์)
- ค่าที่แอปนับเป็นของ process นั้นคนเดียว (ADR 0031) — การรวมข้าม replica
  เป็นหน้าที่ของฝั่ง Prometheus
- job `scrape` ใน CI พิสูจน์ทุก push ว่าตัวเลขไปถึง TSDB จริงผ่านด่าน token
  (และ token ผิดต้อง `up=0` — วัดจริงแล้วทั้งสองทิศ)

## เปิด SSO ด้วย OIDC (Phase 5 · P5-13)

```
export SECRET_KEY=... KEYCLOAK_ADMIN_PASSWORD=...
docker compose -f compose.yaml -f compose.sso.yaml up -d
docker compose -f compose.yaml -f compose.sso.yaml run --rm app flask db upgrade
# **ตารางของ plugin อยู่นอกสาย migration ของ core** ต้องสั่งเอง (ADR 0023)
docker compose -f compose.yaml -f compose.sso.yaml run --rm app flask plugin-install auth/oidc
docker compose -f compose.yaml -f compose.sso.yaml run --rm app flask create-user somchai
```

แล้วเปิด `http://127.0.0.1:8000/login` จะเห็นปุ่มของ IdP เพิ่มขึ้นมาข้างฟอร์ม
รหัสผ่าน (ผู้ใช้ทดสอบใน realm คือ `somchai` — ดูรหัสใน `deploy/keycloak-realm.json`
ซึ่งเป็นค่าสาธารณะโดยตั้งใจ **ห้ามใช้ realm นั้นกับของจริง**)

### ค่าที่ต้องตั้งเมื่อใช้ IdP จริง

| ตัวแปร | ความหมาย |
|---|---|
| `EXTERNAL_URL` | URL สาธารณะของแอปนี้ — **จำเป็น** redirect_uri ประกอบจากค่านี้ |
| `OIDC_ISSUER` | URL ของ realm/tenant — **ต้องเป็น https** |
| `OIDC_CLIENT_ID` / `OIDC_CLIENT_SECRET` | client แบบ confidential ที่เปิดเฉพาะ code flow |
| `OIDC_ADMIN_GROUP` | ชื่อกลุ่มที่แปลว่า admin ที่นี่ · ไม่ตั้ง = ไม่แตะบทบาทเลย |
| `OIDC_AUTO_CREATE` | `1` = ให้ IdP เป็นคนตัดสินว่าใครมีบัญชี · **ค่าเริ่มต้นคือปิด** |
| `OIDC_INSECURE_ISSUER` | `1` = ยอมให้ issuer เป็น http — **สำหรับ IdP ทดสอบเท่านั้น** |

**`EXTERNAL_URL` ไม่มีค่าเริ่มต้นให้เดา** — ถ้าประกอบ redirect_uri จาก header
`Host` ของคำขอ (`url_for(_external=True)`) คนยิงตั้งค่านั้นเองได้ ในทางปฏิบัติ
IdP ที่ตั้งค่าถูกจะปฏิเสธเพราะไม่ตรงรายการที่ลงทะเบียน แต่การพึ่งการตั้งค่าที่
*ปลายทาง* ไม่ใช่การป้องกันที่ฝั่งเรา (semgrep จับข้อนี้ให้ตอน P5-13)

**`OIDC_INSECURE_ISSUER=1` ทำให้คำตัดสินข้อ 4 ของ ADR 0028 ตกทั้งข้อ** เพราะ
สิ่งที่มาแทนการตรวจลายเซ็น ID token คือการยืนยันตัวตนของ server ด้วย TLS
แอปจะ log เตือนทุกครั้งที่ค่านี้ถูกใช้ ไม่ใช่ครั้งเดียวตอน start

### ชื่อโฮสต์ของ IdP ต้องเป็นตัวเดียวกันจากทุกทาง

`issuer` เป็นสตริงที่ถูกเทียบตรง ๆ กับ `iss` ใน ID token ถ้า browser เข้าถึง IdP
ด้วยชื่อหนึ่งแต่แอปคุยด้วยอีกชื่อหนึ่ง จะได้ token ที่ `iss` ไม่ตรงตลอดกาล
ใน stack ทดสอบแก้ที่ฝั่ง client (`curl --resolve keycloak:8080:127.0.0.1`)
**ไม่ใช่ตั้ง issuer ให้ต่างกันสองที่** ซึ่งคือการทำให้มันไม่มีวันตรง

**job `sso` ใน CI เดินเส้นทางนี้จริงทุก push** — ไปหน้า login ของ Keycloak,
กรอกรหัส, กลับมาที่แอปแล้วได้ 200 และผู้ใช้ต้องถูกยกเป็น admin ตามกลุ่มใน realm

## เปิดการยืนยันตัวตนกับ directory (LDAP · Phase 5 · P5-14)

```
docker compose -f compose.yaml -f compose.ldap.yaml up -d
docker compose -f compose.yaml -f compose.ldap.yaml run --rm app flask db upgrade
docker compose -f compose.yaml -f compose.ldap.yaml run --rm app flask plugin-install auth/ldap
```

**ไม่มีปุ่มเพิ่มบนหน้า login** ต่างจาก SSO — ผู้ใช้กรอกชื่อกับรหัสผ่านในฟอร์มเดิม
แล้วระบบเป็นคนไล่ถามให้เอง เพราะ LDAP เป็นปัจจัยหลักแบบ `credential` (ADR 0029)

**ลำดับคือรหัสผ่านของที่นี่ก่อนเสมอ** แล้วค่อยถาม directory — วันที่ directory
ล่ม ผู้ดูแลที่มีรหัสผ่านของที่นี่ต้องยังเข้าได้ ไม่ใช่ถูกกันออกพร้อมคนทั้งองค์กร

| ตัวแปร | ความหมาย |
|---|---|
| `LDAP_URL` | **ต้องเป็น `ldaps://`** — รหัสผ่านเดินทางไปที่นั่นทุกครั้งที่ login |
| `LDAP_BIND_DN` / `LDAP_BIND_PASSWORD` | บัญชีบริการ — **ใช้ค้น `dn` เท่านั้น** |
| `LDAP_BASE_DN` | จุดเริ่มค้น |
| `LDAP_USER_FILTER` | เช่น `(uid=%s)` — ค่าที่แทนถูก escape ให้เสมอ |
| `LDAP_GROUP_FILTER` | ค่าเริ่มต้น `(member=%s)` — ค้นกลุ่มจาก `dn` ของผู้ใช้ |
| `LDAP_ADMIN_GROUP` | `dn` ของกลุ่มที่แปลว่า admin · ไม่ตั้ง = ไม่แตะบทบาท |
| `LDAP_ID_ATTRIBUTE` | attribute ที่ใช้ผูกบัญชี (เช่น `entryUUID`) · ไม่ตั้ง = ใช้ `dn` |
| `LDAP_AUTO_CREATE` | `1` = ให้ directory ตัดสินว่าใครมีบัญชี · **ค่าเริ่มต้นคือปิด** |
| `LDAP_INSECURE` | `1` = ยอมให้ `ldap://` — **สำหรับ directory ทดสอบเท่านั้น** |

### สองอย่างที่จะเจอตอนต่อกับ OpenLDAP ของจริง

1. **ldap3 ปฏิเสธ `memberOf` ตาม schema ที่ดึงมา** (`invalid attribute type`)
   ทั้งที่ directory ตอบได้ปกติ — แก้ด้วย `get_info=NONE` ตอนสร้าง `Server`
2. **`memberOf` ไม่ได้มีในทุก directory** — Active Directory มีให้ในตัว ส่วน
   OpenLDAP ต้องเปิด overlay และ **overlay ไม่เติมย้อนหลังให้สมาชิกที่มีอยู่
   ก่อนเปิด** ระบบนี้จึง **ค้นจากฝั่งกลุ่ม** (`(member=<dn>)`) ซึ่งใช้ได้กับทุก
   directory เพราะสมาชิกถูกเก็บไว้ที่กลุ่มเสมอตามนิยามของ `groupOfNames`

**job `ldap` ใน CI ยิงจริงทุก push**: login ด้วยรหัสของ directory ได้ 302 ·
บทบาทถูกยกตามกลุ่ม · รหัสผ่านของที่นี่ยังใช้ได้ · **รหัสผ่านว่างได้ 401**

## ย้ายความลับออกจาก environment (Phase 5 · P5-15)

```
# ค่าเริ่มต้นคือ env:// — ไม่ต้องตั้งอะไรถ้ายังพอใจกับที่เป็นอยู่
export SECRETS_URL=file:///run/secrets
```

ความลับชื่อ `SECRET_KEY` จะถูกอ่านจากไฟล์ `/run/secrets/secret_key`
(**ชื่อไฟล์เป็นตัวพิมพ์เล็ก** ตามธรรมเนียมของ docker/kubernetes)

**ทำไมไฟล์ดีกว่า environment**: ค่าใน env **ติดไปกับโปรเซสลูกทุกตัว**
(`flask db upgrade` ที่รันทุก deploy เห็นรหัสผ่านของ IdP ไปด้วย) · อ่านได้จาก
`/proc/<pid>/environ` และ `docker inspect` · และหมุนไม่ได้ · ส่วนไฟล์ใช้สิทธิ์
ของระบบไฟล์ที่มีอยู่แล้ว และไม่ไปไหนโดยไม่มีใครสั่ง

**ย้ายทีละค่าได้** — ชื่อที่ไม่มีในแหล่งตกกลับไปอ่าน environment ตามเดิม
(ADR 0030 ข้อ 4) จึงไม่ต้องยกทั้งกองในวันเดียว

**แต่แหล่งที่ถามไม่ได้ = แอปไม่ start** (ข้อ 6) — ไดเรกทอรีที่ยังไม่ได้ mount
กับ path ที่พิมพ์ผิดให้ผลเหมือนกันเป๊ะ ถ้าปล่อยผ่านเป็น "ไม่มีความลับสักตัว"
ระบบจะรันด้วยค่าเก่าจาก environment ทั้งที่ผู้ดูแลตั้งใจย้ายไปแล้ว

**ความลับที่ระบบรู้จัก**: `SECRET_KEY`, `AUDIT_HMAC_KEY`, `DATABASE_URL`,
`CACHE_URL` (ของ core) และคีย์ของ plugin ทุกตัวที่ถามผ่าน `secrets.get()`

### อ่านจาก Vault

```
export VAULT_TOKEN=<token ที่อ่าน path นั้นได้>
export SECRETS_URL=vault://vault.example.com:8200/secret/todolist
# `vault+http://` สำหรับ Vault ทดสอบที่ยังไม่มี TLS เท่านั้น
```

โดย `secret` คือ mount ของ KV v2 และ `todolist` คือ path ของความลับชุดนั้น ·
**ชื่อคีย์ใน Vault เป็นตัวพิมพ์เล็ก** (`secret_key`) เหมือนชื่อไฟล์ของ `file://`
เพื่อให้ย้ายไป-กลับได้โดยไม่ต้องเปลี่ยนชื่ออะไร

**อ่านครั้งเดียวตอน start** (ADR 0030 ข้อ 5) — หมุนความลับแล้วต้อง restart
แลกกับการที่ Vault ไม่กลายเป็น dependency ของทุก request

**`VAULT_TOKEN` ยังอยู่ใน environment** และนั่นคือไก่กับไข่ที่แก้ไม่ได้:
แหล่งความลับเองต้องมี credential จากที่อื่น สิ่งที่ทำได้คือทำให้ของที่เหลือ
ใน env เป็น **กุญแจดอกเดียวที่ไปเอาของที่เหลือ** ไม่ใช่ของทั้งกอง

**Vault ที่ถามไม่ได้ = แอปไม่ start** — path ที่ไม่มี, ต่อไม่ติด, ไม่มี token
ทั้งสามอย่างหยุดแอปพร้อมบอกสาเหตุ ไม่ตกกลับไปใช้ค่าจาก environment
(job `vault` ใน CI ยิงทั้งสามกรณีจริงทุก push)

### exit path (ADR 0030 ข้อ 7)

| ผูกกับ | ออกอย่างไร |
|---|---|
| `env://` | เป็นค่าเริ่มต้น ไม่ต้องออก |
| `file://` | เขียนไฟล์ที่อื่นแล้วชี้ path ใหม่ |
| `vault://` | `vault kv get` ออกมาเขียนเป็นไฟล์ แล้วสลับเป็น `file://` |

สัญญาของแหล่งมีแค่ `get(name) -> ค่า หรือ ไม่มี` — **ไม่มี backend ตัวไหนได้
เก็บสถานะที่แหล่งอื่นอ่านไม่ได้** ซึ่งเป็นสิ่งที่ทำให้ย้ายกลับได้เสมอ

## เวลาที่งานล้มเหลว

**อย่าปล่อยผ่าน** — งานตามรอบที่ล้มเหลวเงียบ ๆ แย่กว่าไม่มีงานตามรอบเลย
เพราะเอกสารยังอ้างว่าลบภายใน 30 วันอยู่ทั้งที่ไม่มีอะไรลบมาหลายเดือน

- **purge ล้มเหลว** — ข้อมูลที่พ้นระยะยังอยู่ครบ ไม่มีอะไรเสียหาย แต่ผิดนโยบาย
  ตั้งแต่วินาทีนั้น แก้แล้วรันด้วยมือได้เลย ไม่ต้องรอรอบถัดไป
- **ตรวจสุขภาพข้อมูลทั้งใบ**: `flask data-doctor` (audit รอบ 19) — **อ่านอย่างเดียว
  ไม่แก้อะไร** · ตอบสี่คำถามที่ไม่มีใครถามมาก่อน: แถวที่ชี้ไปหาแถวที่ไม่มีอยู่ ·
  สาย audit ต่อครบและหางตรงกับสมอไหม · ชื่อผู้ใช้ที่ชนกันแบบ casefold ·
  ข้อมูลที่พ้นระยะเก็บรักษาแล้วแต่ยังอยู่ (= ไม่มีอะไรรัน `purge-expired` ตามรอบ)
  · เจอปัญหา = exit ที่ไม่ใช่ 0 · **การแก้เป็นการตัดสินใจของคน** เครื่องมือที่
  ซ่อมเองคือเครื่องมือที่ไม่มีใครกล้ารันบนฐานจริง

- **`audit-verify` ไม่ผ่าน** — เรื่องใหญ่กว่ามาก **และข้อความบอกว่าเป็นอาการไหน
  ในสองอาการที่แก้คนละทาง**:
  - *"audit chain ขาดที่แถว id=N"* — แถวที่ยังอยู่ถูกแก้ หรือถูกเจาะกลางสาย ·
    เริ่มจาก `flask audit-log` รอบ ๆ แถวนั้น
  - *"หางของสาย audit ไม่ตรงกับสมอที่บันทึกไว้"* — **มีแถวหายไปจากท้ายสาย**
    (audit รอบ 19) · แถวที่เหลือยังต่อกันครบทุกข้อ การไล่ดูทีละแถวจึงไม่เจออะไร ·
    ข้อความบอกทั้งค่าที่สมอชี้และหางที่เหลือ — เอาไปเทียบกับ backup ล่าสุดได้ทันที
    ว่าหายไปกี่แถวและช่วงไหน
  **ห้ามรัน purge ซ้ำเพื่อ "ให้มันหาย"** ให้เก็บฐานข้อมูลไว้ตามสภาพแล้วตรวจด้วยคน
  ดู ADR 0015 ว่าสายบอกอะไรได้บ้างและบอกไม่ได้บ้าง

alert อัตโนมัติมาจาก **ruler ของ Loki** (`deploy/loki-rules.yaml` — stack
`compose.siem.yaml` · ADR 0037 · job `siem` พิสูจน์ว่าดังจริงทุก push) และ
ตัวเลข latency ดูได้จาก Prometheus/Grafana (`compose.metrics.yaml`) —
ส่วน**งานตามรอบ (purge/audit-verify) รันนอกตัวแอป ruler จึงมองไม่เห็น**

**สิ่งที่มีให้แล้วสำหรับงานตามรอบ (audit รอบ 10 ข้อ 4)**: หน่วยหลักตั้ง
`OnFailure=todolist-purge-failed.service` ไว้ ซึ่งพิมพ์บรรทัดระดับ `err` ที่มีคำว่า
**`TDL_PURGE_FAILED`** ลง journal ทุกครั้งที่รอบไหนล้ม — หาเจอด้วย

```bash
systemctl show -p Result,ExecMainExitTimestamp todolist-purge.service
journalctl -u todolist-purge.service --grep TDL_PURGE_FAILED
```

**นี่คือสัญญาณ ไม่ใช่การแจ้งเตือน** — มันไม่ส่งไปไหนเพราะยังไม่มีใครรับ
(หลักเดียวกับ ADR 0037: ปลายทางที่ไม่มีคนอ่านจะถูกปิดเสียงภายในสองสัปดาห์)
สิ่งที่มันเปลี่ยนคือความล้มเหลว **ค้นเจอด้วยเครื่อง**และมี**จุดแขวน**: ผู้ deploy
ที่มีปลายทางของตัวเองแล้ว แก้ `ExecStart` ของหน่วยนั้นบรรทัดเดียวได้โดยไม่ต้อง
แตะหน่วยที่ทำงานจริง · ส่วนการไปดูว่ารอบล่าสุดเดินจริงไหม เป็นแถวทุก 3 เดือน
ใน `docs/SECURITY-CADENCE.md` แล้ว

## CI แดง — ตัดสินก่อนกด rerun ว่า "ของเราพัง" หรือ "โลกพัง" (audit r8 · D2)

**การกด rerun เป็นการตัดสินใจ ไม่ใช่ปฏิกิริยา** — และเป็นการตัดสินใจที่ลบหลักฐาน
ของตัวเองทิ้ง: `gh run list` รายงานผลของ attempt สุดท้ายเท่านั้น ความล้มเหลวที่
ถูก rerun จนเขียวจึงหายไปจากสถิติที่ `proved_by` (ADR 0059) กับเกณฑ์ flake ใน
`SECURITY-CADENCE.md` ใช้ตัดสินทั้งคู่ · ลำดับสามขั้นก่อนกด:

1. **ถามแพลตฟอร์มก่อนเสมอ** — ผู้ให้บริการรายงานสถานะของตัวเองอยู่แล้ว

   ```
   curl -fsS https://www.githubstatus.com/api/v2/status.json | jq -r .status.indicator
   curl -fsS https://www.githubstatus.com/api/v2/components.json \
     | jq -r '.components[] | select(.name=="Actions") | .status'
   ```

   ได้ `none` / `operational` = แพลตฟอร์มปกติ · **ได้อย่างอื่นเมื่อไหร่ให้ "รอ"
   ไม่ใช่ "ยิงซ้ำ"** — การ rerun ตอนผู้ให้บริการมีปัญหาคือการเผาโควตาและเพิ่ม
   ภาระให้ระบบที่กำลังล้มอยู่ แล้วได้ผลเดิม (วัดจริง 2026-08-17/18: CI แดง 6 ครั้ง
   โดยไม่มีอะไรของเราเสียเลย)

2. **อ่านว่าอะไรแดง แล้วจำแนกให้ได้ก่อน** — `python3 scripts/rerun_census.py --limit 50`
   แยกสามชั้นให้: `platform` (แก้ไม่ได้ ไม่นับเข้าเกณฑ์ flake ของด่านเรา) ·
   `ของเรา` (**ห้าม rerun — ไปแก้**) · `ต้องอ่านเอง` (เครื่องตัดสินไม่ได้ ต้องเปิด
   log ดูเอง) · ชั้นที่สามมีอยู่เพราะ**ตัวจำแนกที่เดาแทนคนคือตัวที่เดาผิดเงียบ ๆ**
   (audit r8: ฉบับแรกอ่านจากชื่อ step แล้วนับ 503 ของ GitHub เป็นของเรา 4 ครั้ง)

2.5 **job ที่ "ยังไม่จบ" ไม่ใช่ job ที่ค้างเสมอไป** (ADR 0067 — audit รอบ 11) ·
   ทุก job ประกาศ `timeout-minutes` ของตัวเองแล้ว ดังนั้น**ถ้ามันยังเดินอยู่ แปลว่า
   มันยังไม่ชนเพดานที่เราตั้งไว้** — ปล่อยให้จบเอง อย่า cancel · ชนเพดานเมื่อไหร่
   GitHub จะจบให้เองพร้อมข้อความที่บอกว่าหมดเวลา ซึ่งเป็นสัญญาณคนละอันกับ
   "แดงเพราะของเสีย" · เกิดจริง 2026-08-18: `dialect (mysql-8)` ใช้เวลา 30+ นาที
   (ปกติ 10) แล้วถูก cancel ทิ้งทั้งที่เดินอยู่ที่ 92% เพราะตอนนั้นยังไม่มีเพดาน
   ให้ดูเลย · **การ cancel ของคนคือการลบหลักฐาน** — log ของ attempt นั้นจบกลางคัน
   และสำมะโนจะนับมันเป็นความล้มเหลวที่ถูกซ่อน

3. **rerun ได้เฉพาะเมื่อสรุปได้ว่าเป็น `platform`** และแพลตฟอร์มกลับมาปกติแล้ว ·
   ถ้าเป็น `ของเรา` แต่ "รันใหม่แล้วเขียว" นั่นคือ **flake ที่ต้องขึ้นทะเบียน**
   ตามแถวใน `SECURITY-CADENCE.md` ไม่ใช่เรื่องที่ผ่านไปได้เฉย ๆ

**ห้ามใช้ rerun เป็นนโยบาย** — ด่านที่ถูกกด rerun เป็นนิสัย คือด่านที่วันแดงจริง
ก็ถูกกด rerun เหมือนกัน (หลักเดียวกับเงื่อนไข flaky ของ ADR 0056)

## `POSTURE_TOKEN` — สิทธิ์อ่านท่าทีของ repo (ADR 0061)

`scripts/audit_posture.py` เทียบ branch protection · required check · auto-merge ·
sha pinning กับสิ่งที่ ADR 0053 ประกาศไว้ · **`GITHUB_TOKEN` ของ Actions อ่าน
branch protection ไม่ได้** — สิทธิ์ Administration ไม่อยู่ในชุด scope ที่มันให้ได้
เลย (ประกาศ `administration: read` ใน workflow **ทำให้ทั้งไฟล์ไม่ start** ซึ่ง
เกิดขึ้นจริงและเงียบอยู่ข้ามวัน เพราะ `posture` ไม่ใช่ required check)

ออก token: Settings → Developer settings → **Fine-grained personal access tokens**
→ เลือกเฉพาะ repo นี้ → Repository permissions: **Administration: Read-only** และ
**Metadata: Read-only** (บังคับมาคู่กัน) → ตั้งวันหมดอายุตามรอบที่รับได้ →
เก็บเป็น secret ชื่อ `POSTURE_TOKEN` ที่ Settings → Secrets and variables → Actions

**ยืนยันว่าสิทธิ์พอโดยไม่ต้องรอ PR ใบถัดไป** — workflow มี `workflow_dispatch`:

```
gh workflow run scorecard.yml
gh run watch "$(gh run list --workflow scorecard.yml --limit 1 --json databaseId --jq '.[0].databaseId')"
```

**token หมดอายุแล้วต้องต่อ** — ใบแรกออก 2026-08-18 หมด **2026-11-16** (มีแถวทวง
ใน `docs/SECURITY-CADENCE.md` ที่ครบกำหนดก่อนหนึ่งสัปดาห์) · ออกใบใหม่ด้วยขั้นตอน
เดิม แทนค่าใน secret เดิม แล้ว `gh workflow run scorecard.yml` เพื่อยืนยัน

**ไม่มี token = job แดง ไม่ใช่ job ที่ข้าม** (ADR 0061 ข้อ 3) — ด่านที่เงียบตอน
อ่านไม่ได้ คือด่านที่รายงานว่าท่าทีถูกต้องทั้งที่ไม่เคยอ่านอะไรเลย · token หมดอายุ
เมื่อไหร่จะเห็นเป็นสีแดงที่ workflow `scorecard` ทันที ไม่ใช่ความเงียบ
