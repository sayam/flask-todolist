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
pipenv run flask db upgrade              # ตารางของ core
pipenv run flask plugin-list             # ดูว่าตารางของ plugin ตัวไหนยังไม่ถูกสร้าง
pipenv run flask plugin-install auth/totp   # ตารางของ plugin ที่ต้องการใช้
```

**ตารางของ plugin ไม่ได้อยู่ในสาย migration ของ core โดยตั้งใจ** (ADR 0023)
`db upgrade` จึงไม่สร้างให้ ถ้าข้ามขั้นที่สอง plugin นั้นจะถูกข้ามไปเงียบ ๆ
(ระบบยังทำงานปกติ แค่ไม่มีความสามารถนั้น — core เช็คให้ก่อนใช้งานเสมอ)

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
