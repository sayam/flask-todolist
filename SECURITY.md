# Security Policy

> This file is written in English first because the people most likely to read it
> are strangers who found something wrong. ฉบับภาษาไทยอยู่ครึ่งล่างของไฟล์

## Reporting a vulnerability

**Use [GitHub's private vulnerability reporting](https://github.com/sayam/flask-todolist/security/advisories/new).**
It is the only channel — there is deliberately no email address in this file, and
no security issues in the public tracker.

Private reporting gives you a private thread with the maintainer, a place to attach
a proof of concept, and a path to a CVE if the finding warrants one. Please do not
open a public issue for anything that lets someone reach data that is not theirs.

**Please include** the version or commit you tested, how to reproduce it, and what
an attacker gains. A working proof of concept is welcome but not required — a clear
description of the flaw is worth more than an exploit that only works on your setup.

### What happens next

| Step | Timeframe |
|---|---|
| Acknowledgement that a human has read your report | **7 days** |
| Initial assessment — is it real, how bad, what is the plan | **14 days** |
| Fix released | by severity, see the table below |

This project is maintained by **one person in their spare time**. Those numbers are
deliberately unambitious so they can be met rather than admired. If a deadline is
going to slip you will hear about it in the thread before it does, not after.

### Fix deadlines by severity

Counted from **the day we learn about it**, not the day a CVE was published:

| Severity | Fixed within |
|---|---|
| Critical | **7 days** |
| High | **30 days** |
| Medium | **90 days** |
| Low | Next review cycle |

Severity comes from the advisory's own CVSS score; when there is none, the finding
is treated as **High** until someone has read it and argued otherwise in writing.
These are the same deadlines the project already holds itself to for dependency
vulnerabilities — see [docs/SECURITY-CADENCE.md](docs/SECURITY-CADENCE.md), which
is checked by a test so it cannot quietly go stale.

### Disclosure

Coordinated. The fix ships first, then the advisory. You will be credited by
whatever name you ask for, or not at all if you prefer. **There is no bounty
program** — this is an unfunded personal project, and saying so up front is more
honest than letting you find out after the work.

## Scope

**In scope** — anything that lets someone reach data that is not theirs, forge a
session, bypass the audit trail, escape the plugin sandbox, or take the app down
with a request an ordinary user could send.

**Out of scope** — these are known, documented, and deliberate:

- **Credentials in `compose.*.yaml`, `.env.example`, `deploy/`, and the test
  suite.** They are placeholders for a stack that only ever runs on a developer's
  machine and in CI. The app refuses to start without a real `SECRET_KEY` of its
  own.
- **MFA is offered, not required.** The reasoning and the compensating controls
  are written down in [ADR 0033](docs/adr/0033-mfa-is-offered-not-required.md),
  along with the conditions that would reverse the decision.
- **There is no self-service password reset and no signup page.** Both are
  intentional; the project stores no email addresses to send a reset to.
- **`memory://` rate limiting counts per process.** Running several workers with
  it multiplies the effective limit. The app warns about this at startup rather
  than refusing to run, because it is correct for a single worker.
- Findings that require an attacker who already has the server's `SECRET_KEY`,
  filesystem, or database.
- Volumetric denial of service, and automated scanner output pasted without a
  reproduction.

Anything you are unsure about: report it. A duplicate costs a few minutes; a
report nobody sent costs much more.

### Safe harbour

Testing against **your own installation** is welcome and will never be treated as
an attack. Do not test against installations you do not own. Stay within the scope
above, do not access, modify, or keep data that is not yours, and give the
maintainer a reasonable chance to fix the issue before telling the world.

## Supported versions

| Version | Supported |
|---|---|
| `main` | ✅ |
| v1.x | ✅ latest patch release |
| < v1.0.0 | ❌ pre-release, nothing was promised |

There is no long-term support branch. Fixes land on `main` and go out in the next
release.

---

# นโยบายความปลอดภัย (ฉบับภาษาไทย)

## แจ้งช่องโหว่อย่างไร

**ใช้ [ช่องทางแจ้งแบบส่วนตัวของ GitHub](https://github.com/sayam/flask-todolist/security/advisories/new)**
ซึ่งเป็นช่องทางเดียว — ในไฟล์นี้ไม่มีอีเมลโดยตั้งใจ และ**อย่าเปิด issue สาธารณะ**
สำหรับอะไรก็ตามที่ทำให้คนหนึ่งเข้าถึงข้อมูลของอีกคนได้

ช่วยบอกเวอร์ชันหรือ commit ที่ทดสอบ · วิธีทำซ้ำ · และผู้โจมตีได้อะไรไป
PoC มีก็ดีแต่ไม่จำเป็น — คำอธิบายที่ชัดมีค่ากว่า exploit ที่ทำงานเฉพาะบนเครื่องคุณ

### จะเกิดอะไรต่อ

| ขั้น | ภายใน |
|---|---|
| ตอบรับว่ามีคนอ่านแล้ว | **7 วัน** |
| ประเมินเบื้องต้น — จริงไหม หนักแค่ไหน จะทำอย่างไร | **14 วัน** |
| ออกตัวแก้ | ตามระดับความรุนแรง (critical 7 วัน · high 30 · medium 90) |

โปรเจกต์นี้มีคนดูแล **คนเดียวและทำนอกเวลางาน** ตัวเลขข้างบนจึงตั้งไว้ต่ำ
พอที่จะทำได้จริง ไม่ใช่ตั้งไว้ให้ดูดี · ถ้าจะเลยกำหนด คุณจะได้ยินก่อนที่มันจะเลย
ไม่ใช่หลังจากนั้น · กรอบเวลาชุดเดียวกับที่โปรเจกต์ใช้กับช่องโหว่ของ dependency
อยู่แล้ว ([docs/SECURITY-CADENCE.md](docs/SECURITY-CADENCE.md) ซึ่งมีเทสต์คุมไม่ให้ค้าง)

**ไม่มีเงินรางวัล** — เป็นโปรเจกต์ส่วนตัวที่ไม่มีทุน บอกไว้ตั้งแต่ต้นตรงกว่า
ปล่อยให้รู้ทีหลังตอนทำงานไปแล้ว · การเปิดเผยเป็นแบบประสานงาน: แก้เสร็จก่อน
แล้วค่อยประกาศ และจะให้เครดิตตามชื่อที่คุณอยากให้ใช้ หรือไม่ให้เลยถ้าคุณต้องการ

## ขอบเขต

**อยู่ในขอบเขต** — อะไรก็ตามที่ทำให้เข้าถึงข้อมูลของคนอื่น ปลอม session
ข้ามสาย audit หลุดออกจากขอบเขตของ plugin หรือทำให้ระบบล่มด้วยคำขอที่ผู้ใช้ธรรมดาส่งได้

**อยู่นอกขอบเขต** — ของพวกนี้รู้อยู่แล้ว บันทึกไว้แล้ว และตั้งใจให้เป็นแบบนั้น:

- **รหัสผ่านใน `compose.*.yaml`, `.env.example`, `deploy/` และในชุดเทสต์**
  เป็นค่าตัวอย่างของ stack ที่รันแค่บนเครื่อง dev กับใน CI · ตัวแอปเองไม่ยอม
  start ถ้าไม่มี `SECRET_KEY` จริง
- **ไม่บังคับ MFA** — เหตุผลและมาตรการชดเชยอยู่ใน
  [ADR 0033](docs/adr/0033-mfa-is-offered-not-required.md) พร้อมเงื่อนไขที่จะทำให้
  คำตัดสินนั้นหมดอายุ
- **ไม่มีหน้าสมัครสมาชิกและไม่มีการรีเซ็ตรหัสผ่านด้วยตัวเอง** ตั้งใจทั้งคู่ —
  ระบบไม่เก็บอีเมลจึงไม่มีที่ให้ส่งลิงก์รีเซ็ตไป
- **`memory://` นับโควตาแยกต่อ process** รันหลาย worker แล้วเพดานจริงจะเป็น N เท่า
  แอปเตือนตอน start แทนที่จะปฏิเสธไม่ start เพราะมันถูกต้องสำหรับ worker เดียว
- สิ่งที่ต้องให้ผู้โจมตีมี `SECRET_KEY` ไฟล์บนเครื่อง หรือฐานข้อมูลอยู่แล้ว
- DoS แบบยิงปริมาณ และผลจาก scanner ที่วางมาดิบ ๆ โดยไม่มีวิธีทำซ้ำ

ไม่แน่ใจว่าเข้าข่ายไหม — **แจ้งมาเถอะ** รายงานซ้ำเสียเวลาไม่กี่นาที
ส่วนรายงานที่ไม่มีใครส่งมาราคาแพงกว่านั้นมาก

### การทดสอบที่ปลอดภัยสำหรับคุณ

ทดสอบกับ**ระบบที่คุณติดตั้งเอง**ได้เต็มที่ ไม่ถือเป็นการโจมตี · ห้ามทดสอบกับ
ระบบของคนอื่น · อย่าเข้าถึง แก้ไข หรือเก็บข้อมูลที่ไม่ใช่ของคุณ และให้เวลาคนดูแล
ได้แก้ก่อนบอกคนอื่น
