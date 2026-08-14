# ASVS 5.0.0 — self-assessment ระดับ L2

มาตรฐาน: [OWASP Application Security Verification Standard](https://owasp.org/www-project-application-security-verification-standard/)
เวอร์ชัน **5.0.0** ตรึงไว้ที่ [`docs/asvs-5.0.0.json`](asvs-5.0.0.json) (CC BY-SA 4.0)

## นี่คืออะไร และไม่ใช่อะไร

**เป็น**: การประเมินตัวเองของเจ้าของโปรเจกต์ ว่าแต่ละข้อกำหนดของ ASVS L2
มีอะไรในระบบรองรับอยู่จริงบ้าง โดยชี้ไปที่ **หลักฐานที่ตรวจสอบได้** —
ไฟล์โค้ด เทสต์ที่รันจริง job ใน CI หรือ ADR ที่บันทึกการตัดสินใจไว้

**ไม่ใช่**: ใบรับรอง · ผลการตรวจจากบุคคลที่สาม · หรือคำรับประกันว่าไม่มีช่องโหว่
การประเมินตัวเองมีค่าเท่ากับความซื่อสัตย์ของคนกรอกเท่านั้น ช่องที่เขียนว่า
"ยังไม่ผ่าน" ในเอกสารนี้จึงมีค่ามากกว่าช่องที่เขียนว่า "ผ่าน"

## ทำไม L2 ไม่ใช่ L1 หรือ L3

ASVS แบ่งเป็นสามระดับ: L1 คือขั้นต่ำที่ทุกแอปควรมี · L2 คือระดับที่ ASVS แนะนำ
สำหรับแอปที่จัดการข้อมูลส่วนบุคคลหรือทำธุรกรรม · L3 สำหรับระบบที่ความเสียหาย
รุนแรงมาก (การเงิน สุขภาพ ความมั่นคง)

ระบบนี้เก็บข้อมูลส่วนบุคคลของผู้ใช้ (ชื่อ งานที่ต้องทำ พฤติกรรมการใช้งาน)
และอยู่ใต้ PDPA — **L2 จึงเป็นระดับที่ตรงกับความเสี่ยงจริง** ส่วน L3 เรียกร้อง
สิ่งที่ scale นี้จ่ายไม่ไหวและไม่ได้ลดความเสี่ยงตามสัดส่วน (เช่น HSM,
storage แบบ write-once สำหรับ audit ซึ่ง [ADR 0014](adr/0014-pdpa-vs-audit-retention.md)
บันทึกไว้แล้วว่ารู้ตัวว่าไม่มี)

**ข้อ L3 ไม่อยู่ในตารางนี้เลย** ไม่ใช่ตกหล่น — ถ้าวันหนึ่งขยับเป็น L3
ให้เปลี่ยน `IN_SCOPE` ใน `scripts/build_asvs_worksheet.py` แล้วรันใหม่
แถวที่ประเมินไว้แล้วจะไม่ถูกทับ

## สถานะที่ใช้ได้ มีสี่ค่าเท่านั้น

| สถานะ | แปลว่า | ต้องมีอะไรในช่องหลักฐาน |
|---|---|---|
| `ผ่าน` | มีของจริงรองรับ | **หลักฐานที่ชี้ไปได้อย่างน้อยหนึ่งชิ้น** |
| `ไม่เกี่ยวข้อง` | ระบบนี้ไม่มีสิ่งที่ข้อนั้นพูดถึง | เหตุผลว่าทำไมไม่เกี่ยวข้อง |
| `ยังไม่ผ่าน` | เกี่ยวข้อง แต่ยังไม่มี | เหตุผล + ต้องอยู่ใน backlog ท้ายเอกสาร |
| `ยังไม่ประเมิน` | ยังไม่มีใครดูข้อนี้ | — (สถานะชั่วคราวของเฟส 7) |

**`ยังไม่ประเมิน` จะถูกห้ามเมื่อ P7-02 จบ** — `tests/test_asvs.py` มีเพดานที่
ขยับลงได้อย่างเดียว (ratchet เหมือน coverage) จำนวนข้อที่ยังไม่ประเมินจึงลดลง
ได้ทางเดียว และวันที่มันถึงศูนย์ เพดานจะกลายเป็นข้อห้ามถาวร

## รูปแบบของหลักฐาน — ต้องชี้ไปได้ ไม่ใช่คำบรรยาย

ทุกอย่างที่อยู่ใน backtick ในช่องหลักฐาน **ถูกตรวจว่ามีอยู่จริง** โดย
`tests/test_asvs.py` ถ้าไฟล์ถูกลบ เทสต์ถูกเปลี่ยนชื่อ หรือ job ใน CI หายไป
เอกสารนี้จะแดงทันที — นี่คือเหตุผลเดียวที่ทำให้ checklist ไม่เน่า

| เขียนแบบนี้ | ตรวจว่า |
|---|---|
| `` `app/session_security.py` `` | ไฟล์นั้นมีอยู่ |
| `` `tests/test_auth.py::test_login_rejects_wrong_password` `` | ไฟล์มีอยู่ **และ** มี `def` ชื่อนั้น |
| `` `ci:dialects` `` | job ชื่อนั้นมีอยู่ใน `.github/workflows/ci.yml` |
| `` `ADR 0020` `` | `docs/adr/0020-*.md` มีอยู่ |
| ข้อความนอก backtick | ไม่ถูกตรวจ — ใช้อธิบายได้ตามสบาย |

**หลักฐานที่ดีที่สุดคือเทสต์** เพราะมันรันทุก push · รองลงมาคือ job ใน CI ·
ไฟล์โค้ดเปล่า ๆ พิสูจน์แค่ว่า "มีโค้ด" ไม่ได้พิสูจน์ว่ามันยังทำงาน ·
ADR พิสูจน์ว่า *ตัดสินใจแล้ว* ไม่ได้พิสูจน์ว่า *ทำแล้ว*

## วิธีรีเฟรชตารางเมื่อขยับเวอร์ชันมาตรฐาน

```
PYTHONPATH=. pipenv run python scripts/build_asvs_worksheet.py --fetch   # ดึงของใหม่
PYTHONPATH=. pipenv run python scripts/build_asvs_worksheet.py           # เติมแถวที่เพิ่ม
```

สคริปต์ **ไม่เคยทับคำตัดสินที่เขียนไว้แล้ว** มันเติมได้แค่แถวใหม่
(สถานะตั้งต้น `ยังไม่ประเมิน`) และข้อที่มาตรฐานถอดออกจะหายไปพร้อมคำตัดสิน
— นั่นถูกต้องแล้ว เพราะคำตัดสินของข้อที่ไม่มีอยู่แล้วไม่มีความหมาย

## ช่องที่ยังไม่ผ่าน (backlog)

ทุกข้อที่มีสถานะ `ยังไม่ผ่าน` ในตารางต้องมีชื่ออยู่ตรงนี้ (`tests/test_asvs.py`
บังคับ) — ข้อที่ซ่อนอยู่กลางตาราง 253 แถวคือข้อที่ไม่มีใครกลับมาทำ

ผลรวมของการประเมิน: **ผ่าน 138 · ไม่เกี่ยวข้อง 67 · ยังไม่ผ่าน 48** จาก 253 ข้อ

ช่องที่ยังไม่ผ่านทั้ง 48 ข้ออยู่ในตารางนี้ครบ จัดกลุ่มตาม *สิ่งที่ต้องทำ*
ไม่ใช่ตามหมวดของ ASVS เพราะข้อที่อยู่คนละหมวดมักถูกปลดล็อกด้วยงานชิ้นเดียวกัน

| กลุ่ม | ข้อ | สาระ | ปลดล็อกด้วย |
|---|---|---|---|
| **เอกสารที่ยังไม่ได้เขียน** | V2.1.1 · V2.1.2 · V2.1.3 · V2.3.2 · V6.1.2 · V6.2.11 · V7.1.2 · V7.1.3 · V8.1.2 · V11.1.1 · V11.1.2 · V11.2.2 · V12.2.2 · V13.1.1 · V13.3.2 · V15.1.3 · V15.2.2 | กฎมีอยู่จริงในโค้ดเกือบทุกข้อ แต่ **ไม่มีที่ไหนประกาศไว้ให้คนที่ไม่ได้อ่านโค้ดรู้** — ครึ่งหนึ่งของช่องที่ไม่ผ่านทั้งหมดเป็นแบบนี้ | **P7-04 ทำส่วนกรอบเวลาแก้ช่องโหว่ไปแล้ว** ที่เหลือรอ P7-08 (ROPA + บัญชีรายการ log + นโยบายกุญแจ) |
| **ลายเซ็นของ ID token** | V6.8.2 · V9.1.1 · V9.1.2 | เบี่ยงโดยตั้งใจตาม `ADR 0028` (ยืนยันด้วย TLS ตาม OIDC Core 3.1.3.7) ซึ่ง **OIDC อนุญาตแต่ ASVS ไม่ยกเว้นให้** | ตัดสินใจใหม่พร้อม ADR — บังคับทันทีถ้าวันหนึ่งรับ token ผ่านเบราว์เซอร์ |
| **การตรวจที่ขาดไปทีละนิด** | V9.2.1 · V10.5.3 · V6.8.4 | ไม่ตรวจ nbf · ไม่เทียบฟิลด์ issuer ในเอกสาร discovery · ไม่อ่าน acr/amr/auth_time และไม่มีทางถอยที่ประกาศไว้ | งานเล็กสามชิ้น ทำได้เลย แต่ละชิ้นต้องมีเทสต์ของตัวเอง |
| **ต้องมี session store ฝั่ง server ก่อน** | V7.4.1 · V7.4.3 · V7.4.5 · V7.5.2 · V7.6.1 | logout ไม่ฆ่าคุกกี้ที่ถูกดักไว้ · ไม่มีหน้า "อุปกรณ์ที่ login อยู่" · ผู้ดูแลจบ session ของคนอื่นไม่ได้ · ปิด MFA ไม่ไล่ session อื่น | `ADR 0020` บันทึกไว้แล้วว่าต้องมี store ก่อน — เป็นงานของเฟสถัดไป |
| **บันทึกเหตุการณ์ความปลอดภัย** | V16.3.2 · V16.3.3 · V16.4.2 | 403/404/429/CSRF ไม่ทิ้งร่องรอยที่ค้นได้ · Loki ยังรันบนเครื่องเดียวกับแอป | ส่ง log ออกไปเครื่องอื่นจริง ๆ |
| **หัวข้อ HTTP และคุกกี้** | V3.3.1 · V3.3.3 · V3.5.3 · V4.1.2 · V14.3.2 | ไม่มี `__Host-` นำหน้าคุกกี้ · `/lang` กับ `/mode` เป็น GET ที่เขียนโปรไฟล์ · `/api/v1` ถูก redirect http→https แทนที่จะล้ม · หน้าที่มีข้อมูลส่วนตัวไม่ได้ตั้ง no-store | งานเล็กที่ทำได้เลย — แต่ละข้อกระทบพฤติกรรมที่มีเทสต์อยู่แล้ว จึงต้องแก้เทสต์ไปด้วย |
| **ขาออกและเครือข่าย** | V1.3.6 · V4.2.1 · V12.1.2 · V12.3.1 · V12.3.3 · V12.3.4 · V13.2.1 · V13.2.4 · V13.2.5 · V15.3.2 | แอปคุยกับฐานข้อมูลด้วยรหัสผ่านที่ไม่หมุน · ไม่มี allowlist ของ host ขาออก · `urllib` ตาม redirect ให้เอง · ไม่ประกาศ ssl_ciphers · แอป↔ฐานข้อมูล↔redis และ proxy↔app ยังไม่เข้ารหัส · ไม่มีอะไรพิสูจน์เรื่อง request smuggling | ส่วนใหญ่เป็นงานชั้น deployment · V15.3.2 กับ V1.3.6 เป็นโค้ดและควรทำก่อน |
| **บัญชีและปัจจัยยืนยันตัว** | V6.4.1 · V6.4.4 | รหัสที่ผู้ดูแลตั้งให้กลายเป็นรหัสถาวรได้ · ไม่มี recovery code และไม่มีกระบวนการยืนยันตัวก่อนปิด MFA ให้ | recovery code คือสิ่งที่ปลดล็อกการบังคับ MFA (`ADR 0033` ข้อ 3) |
| **กันการยิงรัว** | V2.4.1 | หน้า login และ `/api/v1` มีโควตาแล้ว แต่ route ของหน้าเว็บที่ login แล้วยังไม่มีเพดานเลย | ต่อจาก P7-10 (ต้องเห็นก่อนว่าอะไรผิดปกติ) |

<!-- ตารางประเมินเริ่มที่นี่ — ทุกอย่างใต้บรรทัดนี้สร้างโดยสคริปต์ -->

## V1 — Encoding and Sanitization

### V1.1 Encoding and Sanitization Architecture

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V1.1.1 | 2 | Verify that input is decoded or unescaped into a canonical form only once, it is only decoded when encoded data in that form is expected, and that this is done before processing the input further, for example it is not performed after input validation or sanitization. | ผ่าน | Werkzeug ถอดรหัส query string และ form ให้ครั้งเดียวก่อนถึงโค้ดของเรา และไม่มีที่ไหนถอดซ้ำเอง — ตัวกรองและ service รับค่าที่ถอดแล้วเสมอ (`app/filters.py` · `app/services/todos.py`) |
| V1.1.2 | 2 | Verify that the application performs output encoding and escaping either as a final step before being used by the interpreter for which it is intended or by the interpreter itself. | ผ่าน | Jinja2 autoescape เป็นตัวทำขั้นสุดท้ายก่อนออกเป็น HTML และ SQLAlchemy เป็นตัวประกอบ query — ไม่มีการต่อสตริงเองในทั้งสองทาง · `tests/test_write_discipline.py` สแกนห้าม raw SQL |

### V1.2 Injection Prevention

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V1.2.1 | 1 | Verify that output encoding for an HTTP response, HTML document, or XML document is relevant for the context required, such as encoding the relevant characters for HTML elements, HTML attributes, HTML comments, CSS, or HTTP header fields, to avoid changing the message or document structure. | ผ่าน | autoescape ของ Jinja2 เปิดอยู่ทุกไฟล์ และข้อความที่ส่งไปให้ JS ใช้ผ่าน data-* attribute ซึ่ง Jinja escape ให้ — `ADR 0010` · `tests/test_security_headers.py` |
| V1.2.2 | 1 | Verify that when dynamically building URLs, untrusted data is encoded according to its context (e.g., URL encoding or base64url encoding for query or path parameters). Ensure that only safe URL protocols are permitted (e.g., disallow javascript: or data:). | ผ่าน | URL สร้างด้วย url_for() ซึ่ง encode ให้เอง · การ redirect กลับหลังสลับภาษา/โหมดรับเฉพาะ path ภายในเว็บเรา (_safe_referrer() ใน `app/routes.py`) จึงใส่ javascript: หรือ data: ไม่ได้ · หน้า login ไม่รองรับ ?next= โดยตั้งใจเพื่อกัน open redirect |
| V1.2.3 | 1 | Verify that output encoding or escaping is used when dynamically building JavaScript content (including JSON), to avoid changing the message or document structure (to avoid JavaScript and JSON injection). | ผ่าน | **ไม่มี inline script เหลือในระบบเลย** จึงไม่มีที่ที่ JavaScript ถูกประกอบจากข้อมูล — ค่าถูกส่งผ่าน data-* attribute แทน `ADR 0010` · `tests/test_security_headers.py` |
| V1.2.4 | 1 | Verify that data selection or database queries (e.g., SQL, HQL, NoSQL, Cypher) use parameterized queries, ORMs, entity frameworks, or are otherwise protected from SQL Injection and other database injection attacks. This is also relevant when writing stored procedures. | ผ่าน | ทุก query ผ่าน SQLAlchemy ORM · raw SQL ถูกห้ามด้วยตัวสแกนโค้ด ไม่ใช่แค่ธรรมเนียม — `tests/test_write_discipline.py` |
| V1.2.5 | 1 | Verify that the application protects against OS command injection and that operating system calls use parameterized OS queries or use contextual command line output encoding. | ผ่าน | แอปไม่เรียกคำสั่งของระบบปฏิบัติการเลย (ไม่มี subprocess/os.system ในโค้ดที่รันตอนให้บริการ) — สคริปต์ใน `scripts/` รันด้วยมือ ไม่ใช่ส่วนของแอป |
| V1.2.6 | 2 | Verify that the application protects against LDAP injection vulnerabilities, or that specific security controls to prevent LDAP injection have been implemented. | ผ่าน | ค่าที่แทนลงในตัวกรอง LDAP ถูก escape ด้วย escape_filter_chars ทุกจุด ทั้งตอนค้นผู้ใช้และตอนค้นกลุ่ม — `app/plugins/auth/ldap/factor.py` · `tests/test_ldap.py::test_a_search_that_blows_up_becomes_a_refusal_not_a_500` |
| V1.2.7 | 2 | Verify that the application is protected against XPath injection attacks by using query parameterization or precompiled queries. | ไม่เกี่ยวข้อง | ไม่มี XML หรือ XPath ในระบบ |
| V1.2.8 | 2 | Verify that LaTeX processors are configured securely (such as not using the "--shell-escape" flag) and an allowlist of commands is used to prevent LaTeX injection attacks. | ไม่เกี่ยวข้อง | ไม่มีการประมวลผล LaTeX |
| V1.2.9 | 2 | Verify that the application escapes special characters in regular expressions (typically using a backslash) to prevent them from being misinterpreted as metacharacters. | ผ่าน | regex ทุกตัวในโค้ดเป็นค่าคงที่ที่นักพัฒนาเขียน ไม่มีที่ไหนประกอบ pattern จากค่าที่ผู้ใช้ส่งมา — `app/i18n.py` · `app/logging_setup.py` (ตัวตรวจว่า X-Request-Id เป็น UUID จริง) · `tests/test_logging.py::test_bogus_incoming_id_is_replaced` |

### V1.3 Sanitization

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V1.3.1 | 1 | Verify that all untrusted HTML input from WYSIWYG editors or similar is sanitized using a well-known and secure HTML sanitization library or framework feature. | ไม่เกี่ยวข้อง | ไม่มีตัวแก้ไขข้อความแบบ WYSIWYG และไม่มีที่ไหนรับ HTML จากผู้ใช้ — ชื่องานและชื่อหมวดเป็นข้อความล้วนที่ถูก escape ตอนแสดงผล |
| V1.3.2 | 1 | Verify that the application avoids the use of eval() or other dynamic code execution features such as Spring Expression Language (SpEL). Where there is no alternative, any user input being included must be sanitized before being executed. | ผ่าน | ไม่มี eval/exec ในโค้ดของแอป · การโหลด plugin ใช้ importlib กับไดเรกทอรีที่ค้นเจอบนดิสก์ ไม่ใช่การ execute สตริง — `app/plugins/__init__.py` · `tests/test_plugins.py` สแกน AST ของทุกจุด plug |
| V1.3.3 | 2 | Verify that data being passed to a potentially dangerous context is sanitized beforehand to enforce safety measures, such as only allowing characters which are safe for this context and trimming input which is too long. | ผ่าน | ค่าที่เข้าสู่บริบทที่มีผลถูกจำกัดก่อนเสมอ — ความยาวของทุกคอลัมน์ String ถูกกำหนดในโมเดล และ id ที่มาจากภายนอกต้องผ่าน lookup.by_id() ซึ่งกันค่าที่เกิน 64 บิตไม่ให้กลายเป็น 500 (`app/services/lookup.py` · `tests/test_api_fuzz.py`) |
| V1.3.4 | 2 | Verify that user-supplied Scalable Vector Graphics (SVG) scriptable content is validated or sanitized to contain only tags and attributes (such as draw graphics) that are safe for the application, e.g., do not contain scripts and foreignObject. | ผ่าน | SVG เดียวที่ระบบสร้างคือ QR ซึ่งสร้างจากไลบรารีทั้งก้อน ไม่ได้รับ SVG จากผู้ใช้ที่ไหนเลย — และเสิร์ฟภายใต้ CSP เดิมโดยไม่ผ่อนอะไร (`tests/test_totp.py::test_serving_the_qr_does_not_loosen_the_csp`) |
| V1.3.5 | 2 | Verify that the application sanitizes or disables user-supplied scriptable or expression template language content, such as Markdown, CSS or XSL stylesheets, BBCode, or similar. | ไม่เกี่ยวข้อง | ไม่รับ Markdown, CSS, XSL หรือ BBCode จากผู้ใช้ — CSS ของธีมมาจาก plugin บนดิสก์ ไม่ใช่จากผู้ใช้ |
| V1.3.6 | 2 | Verify that the application protects against Server-side Request Forgery (SSRF) attacks, by validating untrusted data against an allowlist of protocols, domains, paths and ports and sanitizing potentially dangerous characters before using the data to call another service. | ยังไม่ผ่าน | กัน scheme ที่ไม่ใช่ https ก่อนเปิดปลายทางของ IdP แล้ว (`app/plugins/auth/oidc/factor.py`) แต่ **ยังไม่มี allowlist ของ domain/port** — ข้อเดียวกับ V13.2.4 |
| V1.3.7 | 2 | Verify that the application protects against template injection attacks by not allowing templates to be built based on untrusted input. Where there is no alternative, any untrusted input being included dynamically during template creation must be sanitized or strictly validated. | ผ่าน | template ทุกไฟล์อยู่บนดิสก์ ไม่มีที่ไหนประกอบ template จากข้อมูลที่รับมา (ไม่มีการเรียก render_template_string เลย) — `app/templates/` · `app/routes.py` |
| V1.3.8 | 2 | Verify that the application appropriately sanitizes untrusted input before use in Java Naming and Directory Interface (JNDI) queries and that JNDI is configured securely to prevent JNDI injection attacks. | ไม่เกี่ยวข้อง | ไม่ใช่ Java และไม่มี JNDI |
| V1.3.9 | 2 | Verify that the application sanitizes content before it is sent to memcache to prevent injection attacks. | ไม่เกี่ยวข้อง | ไม่ได้ใช้ memcache — cache plugin ที่มีคือ no-op กับ redis (`ADR 0026` ตระกูลเดียวกัน) และเก็บแต่ตัวนับโควตา |
| V1.3.10 | 2 | Verify that format strings which might resolve in an unexpected or malicious way when used are sanitized before being processed. | ผ่าน | ข้อความที่มีตัวแปรใช้ named placeholder ของ gettext เสมอ ไม่ใช่ f-string และตัว msgid เป็นค่าคงที่ในโค้ด ไม่ได้มาจากผู้ใช้ — `tests/test_i18n.py` |
| V1.3.11 | 2 | Verify that the application sanitizes user input before passing to mail systems to protect against SMTP or IMAP injection. | ไม่เกี่ยวข้อง | ระบบไม่ส่งอีเมลเลย และไม่เก็บที่อยู่อีเมลด้วย (`ADR 0019` — เหตุผลที่ไม่มี self-service reset) |

### V1.4 Memory, String, and Unmanaged Code

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V1.4.1 | 2 | Verify that the application uses memory-safe string, safer memory copy and pointer arithmetic to detect or prevent stack, buffer, or heap overflows. | ผ่าน | Python จัดการหน่วยความจำเองและไม่มี pointer arithmetic · แอปไม่มีส่วนขยายที่เขียนด้วยภาษาที่ไม่ปลอดภัยด้านหน่วยความจำ — `Pipfile` ประกาศ dependency ทั้งหมดและ `ci:sbom` ออกรายการจริงทุก push |
| V1.4.2 | 2 | Verify that sign, range, and input validation techniques are used to prevent integer overflows. | ผ่าน | จำนวนเต็มของ Python ไม่ล้น แต่ **ค่าที่ใหญ่เกินกว่าที่ฐานข้อมูลรับได้เคยทำให้เกิด 500 จริง** จึงมี lookup.by_id() เป็นทางเดียวที่หาแถวตาม id จากภายนอก — `app/services/lookup.py` · `tests/test_api_fuzz.py` (ตัว fuzz เป็นคนหาเจอ) |
| V1.4.3 | 2 | Verify that dynamically allocated memory and resources are released, and that references or pointers to freed memory are removed or set to null to prevent dangling pointers and use-after-free vulnerabilities. | ผ่าน | Python เก็บกวาดหน่วยความจำเอง · ทรัพยากรที่ต้องปิดถูกปิดด้วย context manager — `app/plugins/auth/oidc/factor.py` (urlopen) · `app/audit.py` (connection ของฐานข้อมูล) |

### V1.5 Safe Deserialization

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V1.5.1 | 1 | Verify that the application configures XML parsers to use a restrictive configuration and that unsafe features such as resolving external entities are disabled to prevent XML eXternal Entity (XXE) attacks. | ไม่เกี่ยวข้อง | ไม่มีการอ่าน XML ที่ไหนในระบบ |
| V1.5.2 | 2 | Verify that deserialization of untrusted data enforces safe input handling, such as using an allowlist of object types or restricting client-defined object types, to prevent deserialization attacks. Deserialization mechanisms that are explicitly defined as insecure must not be used with untrusted input. | ผ่าน | ข้อมูลจากภายนอกถูกย่อยด้วย JSON + marshmallow schema ที่ประกาศชนิดไว้ชัดและ **ปฏิเสธชื่อฟิลด์ที่ไม่รู้จัก** (`ADR 0018`) ไม่มี pickle หรือการ deserialize เป็น object ที่ client เลือกได้ · คุกกี้ session ถูกเซ็นและ itsdangerous ตรวจก่อนย่อย |

## V2 — Validation and Business Logic

### V2.1 Validation and Business Logic Documentation

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V2.1.1 | 1 | Verify that the application's documentation defines input validation rules for how to check the validity of data items against an expected structure. This could be common data formats such as credit card numbers, email addresses, telephone numbers, or it could be an internal data format. | ยังไม่ผ่าน | กฎการตรวจค่ามีอยู่จริงและรวมศูนย์ในสัญญา API (`docs/openapi.json` ที่ generate จากโค้ด) แต่ **ฝั่งเว็บยังไม่มีเอกสารที่ประกาศกฎของแต่ละช่อง** ไว้ให้คนอ่านโดยไม่ต้องอ่านโค้ด |
| V2.1.2 | 2 | Verify that the application's documentation defines how to validate the logical and contextual consistency of combined data items, such as checking that suburb and ZIP code match. | ยังไม่ผ่าน | มีการตรวจความสอดคล้องอยู่บ้างในโค้ด (เช่นตัวกรองช่วงวันที่) แต่ยังไม่ได้ประกาศเป็นกฎในเอกสาร — ผูกกับ V2.1.1 |
| V2.1.3 | 2 | Verify that expectations for business logic limits and validations are documented, including both per-user and globally across the application. | ยังไม่ผ่าน | ยังไม่ได้ประกาศเพดานเชิงธุรกิจ (จำนวนงานต่อผู้ใช้ จำนวนหมวด จำนวน token) ทั้งต่อคนและทั้งระบบ |

### V2.2 Input Validation

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V2.2.1 | 1 | Verify that input is validated to enforce business or functional expectations for that input. This should either use positive validation against an allow list of values, patterns, and ranges, or be based on comparing the input to an expected structure and logical limits according to predefined rules. For L1, this can focus on input which is used to make specific business or security decisions. For L2 and up, this should apply to all input. | ผ่าน | ค่าที่รู้จักถูกตรวจแบบ allowlist และค่าที่ไม่รู้จักตกกลับเป็นค่าเริ่มต้นอย่างจงใจ ส่วน category ที่เป็นของคนอื่นตอบ 404 — `app/filters.py` · `tests/test_due_and_filter.py` · `tests/test_api_fuzz.py` ยิงคำขอที่สร้างจากสัญญา API เอง |
| V2.2.2 | 1 | Verify that the application is designed to enforce input validation at a trusted service layer. While client-side validation improves usability and should be encouraged, it must not be relied upon as a security control. | ผ่าน | การตรวจค่าอยู่ในชั้น service ซึ่งไม่รู้จัก HTTP เลย จึงเป็นด่านเดียวกันทั้ง HTML/API/CLI — `ADR 0016` · `tests/test_service_layer.py` |
| V2.2.3 | 2 | Verify that the application ensures that combinations of related data items are reasonable according to the pre-defined rules. | ผ่าน | update_todo() รับ dict ของเฉพาะฟิลด์ที่ส่งมาจริง จึงแยก "ไม่ได้ส่ง" ออกจาก "ส่ง null มาเพื่อล้างค่า" ได้ และปฏิเสธชื่อที่ไม่รู้จัก — `app/services/todos.py` · `tests/test_services.py` |

### V2.3 Business Logic Security

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V2.3.1 | 1 | Verify that the application will only process business logic flows for the same user in the expected sequential step order and without skipping steps. | ผ่าน | ขั้นตอนที่มีลำดับถูกบังคับให้เดินตามลำดับจริง — login ที่มีปัจจัยที่สอง **หยุดครึ่งทางและยังไม่เรียก login_user()** (`ADR 0024` · `tests/test_totp.py::test_verify_refuses_a_secret_that_was_never_confirmed`) และ handshake ของ SSO ถูกใช้ได้ครั้งเดียว (`tests/test_oidc.py::test_a_pending_handshake_is_spent_even_when_the_attempt_fails`) |
| V2.3.2 | 2 | Verify that business logic limits are implemented per the application's documentation to avoid business logic flaws being exploited. | ยังไม่ผ่าน | ไม่มีเพดานเชิงธุรกิจให้บังคับ เพราะยังไม่ได้ประกาศ — ผูกกับ V2.1.3 |
| V2.3.3 | 2 | Verify that transactions are being used at the business logic level such that either a business logic operation succeeds in its entirety or it is rolled back to the previous correct state. | ผ่าน | service เป็นคน commit เอง ผู้เรียกไม่ต้องรู้เรื่อง session และความล้มเหลวสื่อสารด้วย exception ทำให้ทั้งก้อนถูกย้อน — `ADR 0016` · `tests/test_services.py` · `tests/test_soft_delete.py` |
| V2.3.4 | 2 | Verify that business logic level locking mechanisms are used to ensure that limited quantity resources (such as theater seats or delivery slots) cannot be double-booked by manipulating the application's logic. | ผ่าน | ทรัพยากรที่ต้องล็อกจริงในระบบนี้มีอย่างเดียวคือปลายสาย audit ซึ่งถูกล็อกด้วย FOR UPDATE — `ADR 0032` · `tests/test_audit.py::test_two_connections_appending_at_once_do_not_collide` (เดินจริงเฉพาะ `ci:dialects`) |

### V2.4 Anti-automation

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V2.4.1 | 2 | Verify that anti-automation controls are in place to protect against excessive calls to application functions that could lead to data exfiltration, garbage-data creation, quota exhaustion, rate-limit breaches, denial-of-service, or overuse of costly resources. | ยังไม่ผ่าน | หน้า login มีโควตาสองมิติ (`ADR 0021`) และ /api/v1 มีโควตาต่อใบ token (`tests/test_api_ratelimit.py::test_each_token_gets_its_own_quota`) แต่ **route ของหน้าเว็บที่ login แล้วยังไม่มีเพดานเลย** — ผู้ใช้ที่ถูกยึด session ดูดข้อมูลออกได้เร็วเท่าที่เครื่องจะไหว |

## V3 — Web Frontend Security

### V3.2 Unintended Content Interpretation

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V3.2.1 | 1 | Verify that security controls are in place to prevent browsers from rendering content or functionality in HTTP responses in an incorrect context (e.g., when an API, a user-uploaded file or other resource is requested directly). Possible controls could include: not serving the content unless HTTP request header fields (such as Sec-Fetch-\*) indicate it is the correct context, using the sandbox directive of the Content-Security-Policy header field or using the attachment disposition type in the Content-Disposition header field. | ผ่าน | ทุกคำตอบมี X-Content-Type-Options: nosniff และ CSP ที่ปิด object-src/base-uri — `app/security_headers.py` · `tests/test_security_headers.py::test_security_headers_on_every_page` · `tests/test_security_headers.py::test_csp_locks_down_the_dangerous_directives` |
| V3.2.2 | 1 | Verify that content intended to be displayed as text, rather than rendered as HTML, is handled using safe rendering functions (such as createTextNode or textContent) to prevent unintended execution of content such as HTML or JavaScript. | ผ่าน | ฝั่ง client ไม่ประกอบ HTML เลย — `app/static/app.js` ไม่มี innerHTML/insertAdjacentHTML สักที่ ทุกอย่างมาจาก template ที่ Jinja escape ให้ (`tests/test_security_headers.py::test_behaviour_uses_data_attributes`) |

### V3.3 Cookie Setup

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V3.3.1 | 1 | Verify that cookies have the 'Secure' attribute set, and if the '\__Host-' prefix is not used for the cookie name, the '__Secure-' prefix must be used for the cookie name. | ยังไม่ผ่าน | คุกกี้ติด Secure เมื่อเปิด TLS แล้ว (`tests/test_security_headers.py::test_https_flag_marks_session_cookie_secure`) แต่ **ยังใช้ชื่อ session เปล่า ๆ ไม่มี __Host- หรือ __Secure- นำหน้า** ซึ่งข้อนี้บังคับ |
| V3.3.2 | 2 | Verify that each cookie's 'SameSite' attribute value is set according to the purpose of the cookie, to limit exposure to user interface redress attacks and browser-based request forgery attacks, commonly known as cross-site request forgery (CSRF). | ผ่าน | SameSite=Lax ตั้งใจเลือกให้ cross-site POST ไม่พาคุกกี้ไป แต่คลิกลิงก์เข้าเว็บเรายังใช้ได้ — `tests/test_security_headers.py::test_session_cookie_is_samesite_lax` · `ci:dast` ยิง ZAP ใส่ stack จริงทุก push (กฎ 10054 ตั้งเป็น FAIL) |
| V3.3.3 | 2 | Verify that cookies have the '__Host-' prefix for the cookie name unless they are explicitly designed to be shared with other hosts. | ยังไม่ผ่าน | ข้อเดียวกับ V3.3.1 — คุกกี้ไม่ได้ตั้งใจแชร์ข้ามโฮสต์ จึงควรใช้ __Host- แต่ยังไม่ได้ทำ |
| V3.3.4 | 2 | Verify that if the value of a cookie is not meant to be accessible to client-side scripts (such as a session token), the cookie must have the 'HttpOnly' attribute set and the same value (e. g. session token) must only be transferred to the client via the 'Set-Cookie' header field. | ผ่าน | HttpOnly ตั้งตรงตอน start ไม่รอ Talisman ตั้งให้ตอน request แรก และค่าเดินทางผ่าน Set-Cookie อย่างเดียว — `tests/test_security_headers.py::test_session_cookie_is_http_only` · `ci:dast` ยิง ZAP ใส่ stack จริงทุก push (กฎ 10010 ตั้งเป็น FAIL) |

### V3.4 Browser Security Mechanism Headers

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V3.4.1 | 1 | Verify that a Strict-Transport-Security header field is included on all responses to enforce an HTTP Strict Transport Security (HSTS) policy. A maximum age of at least 1 year must be defined, and for L2 and up, the policy must apply to all subdomains as well. | ผ่าน | HSTS อายุ 1 ปีครอบ subdomain (ค่าของ Talisman) และ **เปิดพร้อม TLS เท่านั้น** — `tests/test_security_headers.py::test_hsts_is_off_until_tls_exists` · `tests/test_security_headers.py::test_https_flag_turns_on_hsts_and_redirect` · `ci:dast` ยิง ZAP ใส่ stack จริงทุก push (กฎ 10035 ตั้งเป็น FAIL) · `ci:stack` ตรวจบน TLS จริงว่า HSTS มีและมาจากเจ้าของเดียว |
| V3.4.2 | 1 | Verify that the Cross-Origin Resource Sharing (CORS) Access-Control-Allow-Origin header field is a fixed value by the application, or if the Origin HTTP request header field value is used, it is validated against an allowlist of trusted origins. When 'Access-Control-Allow-Origin: *' needs to be used, verify that the response does not include any sensitive information. | ผ่าน | ไม่ตั้ง Access-Control-Allow-Origin เลย จึงไม่มี origin ไหนอ่านคำตอบข้ามโดเมนได้ — ค่าที่จำกัดที่สุดคือการไม่มีหัวข้อนี้ · `tests/test_security_headers.py::test_security_headers_on_every_page` |
| V3.4.3 | 2 | Verify that HTTP responses include a Content-Security-Policy response header field which defines directives to ensure the browser only loads and executes trusted content or resources, in order to limit execution of malicious JavaScript. As a minimum, a global policy must be used which includes the directives object-src 'none' and base-uri 'none' and defines either an allowlist or uses nonces or hashes. For an L3 application, a per-response policy with nonces or hashes must be defined. | ผ่าน | CSP เป็น 'self' ล้วน **ไม่มี unsafe-inline** และมี object-src 'none' กับ base-uri 'none' ครบ — `ADR 0010` · `tests/test_security_headers.py::test_csp_has_no_unsafe_directives` · `ci:dast` ยิง ZAP ใส่ stack จริงทุก push (กฎ 10038 ตั้งเป็น FAIL) |
| V3.4.4 | 2 | Verify that all HTTP responses contain an 'X-Content-Type-Options: nosniff' header field. This instructs browsers not to use content sniffing and MIME type guessing for the given response, and to require the response's Content-Type header field value to match the destination resource. For example, the response to a request for a style is only accepted if the response's Content-Type is 'text/css'. This also enables the use of the Cross-Origin Read Blocking (CORB) functionality by the browser. | ผ่าน | nosniff ทุกคำตอบ — `tests/test_security_headers.py::test_security_headers_on_every_page` · `ci:dast` ยิง ZAP ใส่ stack จริงทุก push (กฎ 10021 ตั้งเป็น FAIL) |
| V3.4.5 | 2 | Verify that the application sets a referrer policy to prevent leakage of technically sensitive data to third-party services via the 'Referer' HTTP request header field. This can be done using the Referrer-Policy HTTP response header field or via HTML element attributes. Sensitive data could include path and query data in the URL, and for internal non-public applications also the hostname. | ผ่าน | Referrer-Policy เป็น strict-origin-when-cross-origin — `app/security_headers.py` · `tests/test_security_headers.py::test_security_headers_on_every_page` |
| V3.4.6 | 2 | Verify that the web application uses the frame-ancestors directive of the Content-Security-Policy header field for every HTTP response to ensure that it cannot be embedded by default and that embedding of specific resources is allowed only when necessary. Note that the X-Frame-Options header field, although supported by browsers, is obsolete and may not be relied upon. | ผ่าน | frame-ancestors 'none' อยู่ใน CSP และ **ตั้งใจไม่ใช้ X-Frame-Options** เพราะเป็นของเก่า — `tests/test_security_headers.py::test_csp_locks_down_the_dangerous_directives` · `ci:dast` ยิง ZAP ใส่ stack จริงทุก push (กฎ 10020 ตั้งเป็น FAIL) |

### V3.5 Browser Origin Separation

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V3.5.1 | 1 | Verify that, if the application does not rely on the CORS preflight mechanism to prevent disallowed cross-origin requests to use sensitive functionality, these requests are validated to ensure they originate from the application itself. This may be done by using and validating anti-forgery tokens or requiring extra HTTP header fields that are not CORS-safelisted request-header fields. This is to defend against browser-based request forgery attacks, commonly known as cross-site request forgery (CSRF). | ผ่าน | CSRFProtect คุมทั้งแอปและตัดก่อน @login_required ด้วยซ้ำ — `ADR 0005` · `tests/test_csrf.py` ซึ่งรันบนแอปที่ **เปิด CSRF จริง** ไม่ใช่แอปเทสต์ปกติที่ปิดไว้ · `ci:dast` ยิง ZAP ใส่ stack จริงทุก push (กฎ 10202 ตั้งเป็น FAIL) |
| V3.5.2 | 1 | Verify that, if the application relies on the CORS preflight mechanism to prevent disallowed cross-origin use of sensitive functionality, it is not possible to call the functionality with a request which does not trigger a CORS-preflight request. This may require checking the values of the 'Origin' and 'Content-Type' request header fields or using an extra header field that is not a CORS-safelisted header-field. | ไม่เกี่ยวข้อง | ไม่ได้พึ่ง CORS preflight เป็นด่าน — ด่านคือ CSRF token (V3.5.1) และแอปไม่ตั้งหัวข้อ CORS เลย |
| V3.5.3 | 1 | Verify that HTTP requests to sensitive functionality use appropriate HTTP methods such as POST, PUT, PATCH, or DELETE, and not methods defined by the HTTP specification as "safe" such as HEAD, OPTIONS, or GET. Alternatively, strict validation of the Sec-Fetch-* request header fields can be used to ensure that the request did not originate from an inappropriate cross-origin call, a navigation request, or a resource load (such as an image source) where this is not expected. | ยังไม่ผ่าน | การกระทำที่สำคัญเป็น POST ครบ (ออกจากระบบ ลบ แก้ไข) แต่ **/lang/<code> และ /mode/<value> เป็น GET ที่เขียนลงโปรไฟล์ของผู้ใช้** — ผลเสียจำกัด (เปลี่ยนภาษา/โหมดของเหยื่อ) แต่เป็น GET ที่เปลี่ยนสถานะจริง |
| V3.5.4 | 2 | Verify that separate applications are hosted on different hostnames to leverage the restrictions provided by same-origin policy, including how documents or scripts loaded by one origin can interact with resources from another origin and hostname-based restrictions on cookies. | ไม่เกี่ยวข้อง | มีแอปเดียวบนโฮสต์เดียว ไม่มีแอปอื่นมาแชร์ origin |
| V3.5.5 | 2 | Verify that messages received by the postMessage interface are discarded if the origin of the message is not trusted, or if the syntax of the message is invalid. | ไม่เกี่ยวข้อง | ไม่ใช้ postMessage — `app/static/app.js` เป็น JS ทั้งหมดของฝั่ง client |

### V3.7 Other Browser Security Considerations

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V3.7.1 | 2 | Verify that the application only uses client-side technologies which are still supported and considered secure. Examples of technologies which do not meet this requirement include NSAPI plugins, Flash, Shockwave, ActiveX, Silverlight, NACL, or client-side Java applets. | ผ่าน | ใช้แต่ HTML/CSS/JS มาตรฐาน ไม่มี plugin ของเบราว์เซอร์รุ่นเก่า — `app/static/app.js` ไฟล์เดียว (`tests/test_security_headers.py::test_app_js_is_served`) |
| V3.7.2 | 2 | Verify that the application will only automatically redirect the user to a different hostname or domain (which is not controlled by the application) where the destination appears on an allowlist. | ผ่าน | การพาไปโฮสต์อื่นมีทางเดียวคือไป IdP ซึ่ง issuer มาจาก config ของผู้ติดตั้ง (allowlist ที่มีสมาชิกเดียว) และต้องเป็น https — `tests/test_oidc.py::test_starting_sso_redirects_the_browser_to_the_provider` · การ redirect กลับหลังสลับภาษารับเฉพาะ path ภายใน |

## V4 — API and Web Service

### V4.1 Generic Web Service Security

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V4.1.1 | 1 | Verify that every HTTP response with a message body contains a Content-Type header field that matches the actual content of the response, including the charset parameter to specify safe character encoding (e.g., UTF-8, ISO-8859-1) according to IANA Media Types, such as "text/", "/+xml" and "/xml". | ผ่าน | Flask ใส่ charset=utf-8 ให้ทุกคำตอบ HTML และ /metrics ประกาศ charset ของตัวเองชัด — `app/metrics.py` · `tests/test_metrics.py` |
| V4.1.2 | 2 | Verify that only user-facing endpoints (intended for manual web-browser access) automatically redirect from HTTP to HTTPS, while other services or endpoints do not implement transparent redirects. This is to avoid a situation where a client is erroneously sending unencrypted HTTP requests, but since the requests are being automatically redirected to HTTPS, the leakage of sensitive data goes undiscovered. | ยังไม่ผ่าน | force_https ของ Talisman redirect **ทุก path รวมทั้ง /api/v1** — client ที่เผลอยิง http จึงถูกพาไป https แทนที่จะล้ม ซึ่งแปลว่า token เดินทางแบบไม่เข้ารหัสไปแล้วหนึ่งครั้งก่อนถูก redirect |
| V4.1.3 | 2 | Verify that any HTTP header field used by the application and set by an intermediary layer, such as a load balancer, a web proxy, or a backend-for-frontend service, cannot be overridden by the end-user. Example headers might include X-Real-IP, X-Forwarded-*, or X-User-ID. | ผ่าน | หัวข้อของ proxy ถูกเชื่อ **ตามจำนวนชั้นที่ประกาศ** และค่าเริ่มต้นคือ 0 = ไม่เชื่อเลย — `ADR 0027` · `app/proxy.py` · `tests/test_proxy.py` |

### V4.2 HTTP Message Structure Validation

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V4.2.1 | 2 | Verify that all application components (including load balancers, firewalls, and application servers) determine boundaries of incoming HTTP messages using the appropriate mechanism for the HTTP version to prevent HTTP request smuggling. In HTTP/1.x, if a Transfer-Encoding header field is present, the Content-Length header must be ignored per RFC 2616. When using HTTP/2 or HTTP/3, if a Content-Length header field is present, the receiver must ensure that it is consistent with the length of the DATA frames. | ยังไม่ผ่าน | พึ่งพฤติกรรมค่าเริ่มต้นของ nginx และ gunicorn ซึ่งจัดการ Transfer-Encoding/Content-Length ถูกตามสเปก แต่ **ยังไม่มีอะไรในระบบพิสูจน์ข้อนี้** — เป็นความเชื่อ ไม่ใช่หลักฐาน |

### V4.3 GraphQL

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V4.3.1 | 2 | Verify that a query allowlist, depth limiting, amount limiting, or query cost analysis is used to prevent GraphQL or data layer expression Denial of Service (DoS) as a result of expensive, nested queries. | ไม่เกี่ยวข้อง | ไม่มี GraphQL — API เป็น REST ตาม `ADR 0018` |
| V4.3.2 | 2 | Verify that GraphQL introspection queries are disabled in the production environment unless the GraphQL API is meant to be used by other parties. | ไม่เกี่ยวข้อง | ไม่มี GraphQL |

### V4.4 WebSocket

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V4.4.1 | 1 | Verify that WebSocket over TLS (WSS) is used for all WebSocket connections. | ไม่เกี่ยวข้อง | ไม่มี WebSocket ในระบบ |
| V4.4.2 | 2 | Verify that, during the initial HTTP WebSocket handshake, the Origin header field is checked against a list of origins allowed for the application. | ไม่เกี่ยวข้อง | ไม่มี WebSocket ในระบบ |
| V4.4.3 | 2 | Verify that, if the application's standard session management cannot be used, dedicated tokens are being used for this, which comply with the relevant Session Management security requirements. | ไม่เกี่ยวข้อง | ไม่มี WebSocket ในระบบ |
| V4.4.4 | 2 | Verify that dedicated WebSocket session management tokens are initially obtained or validated through the previously authenticated HTTPS session when transitioning an existing HTTPS session to a WebSocket channel. | ไม่เกี่ยวข้อง | ไม่มี WebSocket ในระบบ |

## V5 — File Handling

### V5.1 File Handling Documentation

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V5.1.1 | 2 | Verify that the documentation defines the permitted file types, expected file extensions, and maximum size (including unpacked size) for each upload feature. Additionally, ensure that the documentation specifies how files are made safe for end-users to download and process, such as how the application behaves when a malicious file is detected. | ไม่เกี่ยวข้อง | ระบบนี้ไม่รับไฟล์อัปโหลดเลย — งานและหมวดเป็นข้อความล้วน ไม่มีหน้าไหนมี input type=file |

### V5.2 File Upload and Content

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V5.2.1 | 1 | Verify that the application will only accept files of a size which it can process without causing a loss of performance or a denial of service attack. | ไม่เกี่ยวข้อง | ไม่มีการอัปโหลดไฟล์ |
| V5.2.2 | 1 | Verify that when the application accepts a file, either on its own or within an archive such as a zip file, it checks if the file extension matches an expected file extension and validates that the contents correspond to the type represented by the extension. This includes, but is not limited to, checking the initial 'magic bytes', performing image re-writing, and using specialized libraries for file content validation. For L1, this can focus just on files which are used to make specific business or security decisions. For L2 and up, this must apply to all files being accepted. | ไม่เกี่ยวข้อง | ไม่มีการอัปโหลดไฟล์ |
| V5.2.3 | 2 | Verify that the application checks compressed files (e.g., zip, gz, docx, odt) against maximum allowed uncompressed size and against maximum number of files before uncompressing the file. | ไม่เกี่ยวข้อง | ไม่มีการอัปโหลดไฟล์ จึงไม่มีการแตกไฟล์บีบอัด |

### V5.3 File Storage

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V5.3.1 | 1 | Verify that files uploaded or generated by untrusted input and stored in a public folder, are not executed as server-side program code when accessed directly with an HTTP request. | ไม่เกี่ยวข้อง | ไม่มีไฟล์ที่มาจากผู้ใช้ถูกเก็บไว้ให้เสิร์ฟ — ของใน `app/static/` เป็นของนักพัฒนาทั้งหมด |
| V5.3.2 | 1 | Verify that when the application creates file paths for file operations, instead of user-submitted filenames, it uses internally generated or trusted data, or if user-submitted filenames or file metadata must be used, strict validation and sanitization must be applied. This is to protect against path traversal, local or remote file inclusion (LFI, RFI), and server-side request forgery (SSRF) attacks. | ผ่าน | เส้นทางเดียวที่ประกอบ path จากค่าใน URL คือ route ที่เสิร์ฟ CSS ของ plugin ซึ่ง **เทียบไอดีกับรายการที่ค้นเจอบนดิสก์ก่อนเสมอ** จึง traverse ออกไปไม่ได้ — `app/plugins/__init__.py` · `tests/test_plugins.py` |

### V5.4 File Download

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V5.4.1 | 2 | Verify that the application validates or ignores user-submitted filenames, including in a JSON, JSONP, or URL parameter and specifies a filename in the Content-Disposition header field in the response. | ผ่าน | มีเส้นทางดาวน์โหลดแล้ว (สำเนาข้อมูลของเจ้าตัว) และ **ชื่อไฟล์สร้างฝั่งเซิร์ฟเวอร์เสมอ ไม่รับจากผู้ใช้** พร้อมตั้ง Content-Disposition — `app/services/personal_data.py` · `tests/test_personal_data.py::test_the_filename_never_comes_from_the_user` · `tests/test_personal_data.py::test_the_web_page_returns_a_download` |
| V5.4.2 | 2 | Verify that file names served (e.g., in HTTP response header fields or email attachments) are encoded or sanitized (e.g., following RFC 6266) to preserve document structure and prevent injection attacks. | ผ่าน | ชื่อไฟล์ถูกกรองให้เหลือแต่อักษร/ตัวเลข/ขีด ก่อนใส่ในหัวข้อ Content-Disposition — `tests/test_personal_data.py::test_the_filename_never_comes_from_the_user` |
| V5.4.3 | 2 | Verify that files obtained from untrusted sources are scanned by antivirus scanners to prevent serving of known malicious content. | ไม่เกี่ยวข้อง | ไม่มีไฟล์จากแหล่งที่ไม่น่าเชื่อถือเข้าหรือออกจากระบบ |

## V6 — Authentication

### V6.1 Authentication Documentation

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V6.1.1 | 1 | Verify that application documentation defines how controls such as rate limiting, anti-automation, and adaptive response, are used to defend against attacks such as credential stuffing and password brute force. The documentation must make clear how these controls are configured and prevent malicious account lockout. | ผ่าน | กันสองมิติพร้อมเหตุผลและวิธีตั้งค่า — ต่อ IP และ **ต่อชื่อผู้ใช้** (`ADR 0021`) · หักโควตาเฉพาะตอนได้ 401 จึงไม่มีใครล็อกบัญชีคนอื่นได้ด้วยการยิงรหัสผิด — `tests/test_ratelimit.py::test_correct_password_does_not_burn_quota` |
| V6.1.2 | 2 | Verify that a list of context-specific words is documented in order to prevent their use in passwords. The list could include permutations of organization names, product names, system identifiers, project codenames, department or role names, and similar. | ยังไม่ผ่าน | ยังไม่มีรายการคำเฉพาะบริบท (ชื่อองค์กร ชื่อระบบ ชื่อโครงการ) ที่ประกาศไว้เป็นเอกสาร — ตอนนี้กันได้แค่ชื่อผู้ใช้ของเจ้าตัว |
| V6.1.3 | 2 | Verify that, if the application includes multiple authentication pathways, these are all documented together with the security controls and authentication strength which must be consistently enforced across them. | ผ่าน | สามเส้นทางถูกบันทึกครบและระบุความแรงของแต่ละเส้น — รหัสผ่าน + `ADR 0028` (OIDC) + `ADR 0029` (LDAP) · **รหัสผ่านของที่นี่ถูกลองก่อน directory ภายนอกเสมอ** |

### V6.2 Password Security

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V6.2.1 | 1 | Verify that user set passwords are at least 8 characters in length although a minimum of 15 characters is strongly recommended. | ผ่าน | ขั้นต่ำ 8 ตัวตามนโยบายที่เดียว — `app/services/passwords.py` · `tests/test_passwords.py::test_short_password_is_rejected` · `tests/test_passwords.py::test_password_exactly_at_the_minimum_is_accepted` |
| V6.2.2 | 1 | Verify that users can change their password. | ผ่าน | เปลี่ยนได้จากหน้า /settings — `tests/test_passwords.py::test_web_change_password_then_sign_in_with_the_new_one` |
| V6.2.3 | 1 | Verify that password change functionality requires the user's current and new password. | ผ่าน | ต้องกรอกทั้งรหัสเดิมและรหัสใหม่ — `tests/test_passwords.py::test_change_password_needs_the_current_one` · `tests/test_passwords.py::test_web_change_password_rejects_a_wrong_current_password` |
| V6.2.4 | 1 | Verify that passwords submitted during account registration or password change are checked against an available set of, at least, the top 3000 passwords which match the application's password policy, e.g. minimum length. | ผ่าน | เทียบกับรายการ 46,000 รายการที่ generate จาก NCSC/SecLists (มากกว่า 3,000 ที่ข้อนี้ขอ) — `app/password_blocklist.txt` · `tests/test_passwords.py::test_the_blocklist_is_actually_loaded` · `tests/test_passwords.py::test_breached_password_is_rejected` |
| V6.2.5 | 1 | Verify that passwords of any composition can be used, without rules limiting the type of characters permitted. There must be no requirement for a minimum number of upper or lower case characters, numbers, or special characters. | ผ่าน | **ไม่มีกฎ complexity โดยตั้งใจ** ตาม NIST SP 800-63B — `ADR 0019` · `tests/test_passwords.py::test_there_is_no_complexity_rule` |
| V6.2.6 | 1 | Verify that password input fields use type=password to mask the entry. Applications may allow the user to temporarily view the entire masked password, or the last typed character of the password. | ผ่าน | ทุกช่องรหัสผ่านในทุกฟอร์มเป็น type=password — `app/templates/` (6 ช่อง: login, เปลี่ยนรหัส 3 ช่อง, ยืนยันตัวก่อนออก token, ปิด MFA) |
| V6.2.7 | 1 | Verify that "paste" functionality, browser password helpers, and external password managers are permitted. | ผ่าน | ไม่มีตัวขวางการวางหรือตัวจัดการรหัสผ่านเลย — CSP ห้าม inline handler อยู่แล้ว (`ADR 0010`) และ `app/static/app.js` ไม่มีตัวดัก paste · `tests/test_security_headers.py` สแกน template ห้าม handler ในหน้า |
| V6.2.8 | 1 | Verify that the application verifies the user's password exactly as received from the user, without any modifications such as truncation or case transformation. | ผ่าน | ไม่ตัดความยาว ไม่แปลงตัวพิมพ์ ไม่ตัดช่องว่าง — `tests/test_passwords.py::test_spaces_are_kept_not_trimmed` · **มีการ normalize แบบ NFKC ซึ่งเปิดเผยไว้ตรงนี้** ทำเท่ากันทั้งตอนตั้งและตอนตรวจ (`ADR 0019`) และเป็นสิ่งที่ NIST SP 800-63B แนะนำเอง ไม่งั้นคนที่ตั้งรหัสเป็นภาษาไทยจะ login ไม่ได้ — `tests/test_passwords.py::test_unicode_forms_that_look_alike_are_the_same_password` |
| V6.2.9 | 2 | Verify that passwords of at least 64 characters are permitted. | ผ่าน | เพดาน 128 ตัว — `tests/test_passwords.py::test_cap_leaves_room_for_the_length_nist_requires` · `tests/test_passwords.py::test_password_at_the_cap_is_accepted` |
| V6.2.10 | 2 | Verify that a user's password stays valid until it is discovered to be compromised or the user rotates it. The application must not require periodic credential rotation. | ผ่าน | **ไม่บังคับเปลี่ยนตามรอบโดยตั้งใจ** — `ADR 0019` · ไม่มีคอลัมน์วันหมดอายุของรหัสผ่านในตาราง (`docs/DATA-CLASSIFICATION.md`) |
| V6.2.11 | 2 | Verify that the documented list of context specific words is used to prevent easy to guess passwords being created. | ยังไม่ผ่าน | ผลพวงของ V6.1.2 — บังคับได้แค่ "ห้ามมีชื่อผู้ใช้ของตัวเองอยู่ข้างใน" (`tests/test_passwords.py::test_password_containing_the_username_is_rejected`) ยังไม่มีรายการคำเฉพาะบริบทให้บังคับ |
| V6.2.12 | 2 | Verify that passwords submitted during account registration or password changes are checked against a set of breached passwords. | ผ่าน | รายการ blocklist สร้างจากชุดรหัสผ่านที่รั่วซึ่งเผยแพร่ไว้ให้ใช้แบบนี้ — `scripts/build_password_blocklist.py` · `tests/test_passwords.py::test_create_user_rejects_a_breached_password` |

### V6.3 General Authentication Security

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V6.3.1 | 1 | Verify that controls to prevent attacks such as credential stuffing and password brute force are implemented according to the application's security documentation. | ผ่าน | ทำจริงตามที่เอกสารบอก และเทสต์เดินทั้งสองมิติ — `tests/test_ratelimit.py::test_repeated_failures_get_blocked` · `tests/test_ratelimit.py::test_failures_add_up_per_username_across_different_ips` · `tests/test_ratelimit.py::test_blocked_user_still_cannot_login_with_right_password` |
| V6.3.2 | 1 | Verify that default user accounts (e.g., "root", "admin", or "sa") are not present in the application or are disabled. | ผ่าน | ไม่มีบัญชีตั้งต้นเลย — create_app ไม่สร้างผู้ใช้ใด ๆ และไม่มีหน้าสมัครสมาชิก ทุกบัญชีต้องมาจาก flask create-user · `tests/test_rbac.py::test_set_role_command_creates_the_first_administrator` แสดงว่าแม้แต่ admin คนแรกก็ต้องตั้งด้วยมือ |
| V6.3.3 | 2 | Verify that either a multi-factor authentication mechanism or a combination of single-factor authentication mechanisms, must be used in order to access the application. For L3, one of the factors must be a hardware-based authentication mechanism which provides compromise and impersonation resistance against phishing attacks while verifying the intent to authenticate by requiring a user-initiated action (such as a button press on a FIDO hardware key or a mobile phone). Relaxing any of the considerations in this requirement requires a fully documented rationale and a comprehensive set of mitigating controls. | ผ่าน | **ผ่านทางเหตุผลที่บันทึกไว้ ไม่ใช่เพราะบังคับ MFA** — ข้อนี้เขียนทางออกไว้เองว่าการผ่อนต้องมีเหตุผลครบถ้วนและมาตรการชดเชยที่ครอบคลุม ซึ่งอยู่ใน `ADR 0033` พร้อมตารางมาตรการ 11 ข้อที่มีเทสต์คุมทุกข้อ และ **เงื่อนไขที่ทำให้คำตัดสินหมดอายุ** ที่ถูกทบทวนตามรอบใน `docs/SECURITY-CADENCE.md` (`tests/test_cadence.py` บังคับว่าไม่เลยกำหนด) |
| V6.3.4 | 2 | Verify that, if the application includes multiple authentication pathways, there are no undocumented pathways and that security controls and authentication strength are enforced consistently. | ผ่าน | ไม่มีเส้นทางที่ไม่ได้บันทึก และปัจจัยที่สองยืนขวางทุกเส้นเท่ากัน — `tests/test_oidc.py::test_a_second_factor_still_stands_between_sso_and_the_app` · `ADR 0029` |

### V6.4 Authentication Factor Lifecycle and Recovery

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V6.4.1 | 1 | Verify that system generated initial passwords or activation codes are securely randomly generated, follow the existing password policy, and expire after a short period of time or after they are initially used. These initial secrets must not be permitted to become the long term password. | ยังไม่ผ่าน | ไม่มีรหัสที่ระบบสร้างให้ (ผู้ดูแลพิมพ์เองตอน flask create-user) แต่ความเสี่ยงที่ข้อนี้พูดถึงยังอยู่ — **รหัสแรกกลายเป็นรหัสระยะยาวได้** เพราะไม่มีการบังคับเปลี่ยนตอน login ครั้งแรก ผู้ดูแลจึงรู้รหัสของผู้ใช้ตลอดไป |
| V6.4.2 | 1 | Verify that password hints or knowledge-based authentication (so-called "secret questions") are not present. | ผ่าน | ไม่มีคำใบ้รหัสผ่านและไม่มีคำถามลับ — ไม่มีคอลัมน์สำหรับสิ่งเหล่านี้ใน `app/models.py` และการกู้บัญชีทางเดียวคือผู้ดูแล (`ADR 0019`) |
| V6.4.3 | 2 | Verify that a secure process for resetting a forgotten password is implemented, that does not bypass any enabled multi-factor authentication mechanisms. | ผ่าน | ไม่มี self-service reset โดยตั้งใจ (ไม่เก็บอีเมล) ทางกู้เดียวคือ flask set-password ซึ่งเป็นช่องทางนอกระบบ และ **ไม่ข้ามปัจจัยที่สอง** — ผู้ใช้ยังต้องผ่าน MFA ตอน login · `ADR 0019` · `tests/test_passwords.py::test_admin_reset_does_not_ask_for_the_old_password_but_still_validates` |
| V6.4.4 | 2 | Verify that if a multi-factor authentication factor is lost, evidence of identity proofing is performed at the same level as during enrollment. | ยังไม่ผ่าน | ทำโทรศัพท์หายแล้วต้องให้ผู้ดูแลปิด MFA ให้ — **ยังไม่มีทั้ง recovery code และกระบวนการยืนยันตัวตนที่เขียนไว้** ว่าผู้ดูแลต้องตรวจอะไรก่อนปิดให้ |

### V6.5 General Multi-factor authentication requirements

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V6.5.1 | 2 | Verify that lookup secrets, out-of-band authentication requests or codes, and time-based one-time passwords (TOTPs) are only successfully usable once. | ผ่าน | รหัส TOTP ที่ใช้ไปแล้วใช้ซ้ำไม่ได้ และการยืนยันซ้ำก็ย้อนตัวกันไม่ได้ — `tests/test_totp.py::test_a_used_code_cannot_be_used_again` · `tests/test_totp.py::test_confirming_again_cannot_rewind_the_replay_guard` |
| V6.5.2 | 2 | Verify that, when being stored in the application's backend, lookup secrets with less than 112 bits of entropy (19 random alphanumeric characters or 34 random digits) are hashed with an approved password storage hashing algorithm that incorporates a 32-bit random salt. A standard hash function can be used if the secret has 112 bits of entropy or more. | ไม่เกี่ยวข้อง | ไม่มี lookup secret ในระบบ (ยังไม่มี recovery code — ดู V6.4.4) · ส่วนเมล็ด TOTP ต้องเก็บค่าจริงเพราะต้องคำนวณรหัสเทียบทุกครั้ง จัดเป็นชั้น C1 และถูกลบทิ้งจริงเมื่อปิด MFA (`docs/DATA-CLASSIFICATION.md`) |
| V6.5.3 | 2 | Verify that lookup secrets, out-of-band authentication code, and time-based one-time password seeds, are generated using a Cryptographically Secure Pseudorandom Number Generator (CSPRNG) to avoid predictable values. | ผ่าน | เมล็ดสร้างจาก secrets.token_bytes 20 ไบต์ (160 บิต) — `tests/test_totp.py::test_a_fresh_secret_is_random_and_long_enough` |
| V6.5.4 | 2 | Verify that lookup secrets and out-of-band authentication codes have a minimum of 20 bits of entropy (typically 4 random alphanumeric characters or 6 random digits is sufficient). | ไม่เกี่ยวข้อง | ไม่มี lookup secret หรือรหัสส่งนอกช่องทาง |
| V6.5.5 | 2 | Verify that out-of-band authentication requests, codes, or tokens, as well as time-based one-time passwords (TOTPs) have a defined lifetime. Out of band requests must have a maximum lifetime of 10 minutes and for TOTP a maximum lifetime of 30 seconds. | ผ่าน | คาบ 30 วินาทีตาม RFC 6238 และยอมรับหน้าต่างข้างเคียงหนึ่งช่วงเท่านั้น — `tests/test_totp.py::test_matches_the_rfc_6238_test_vectors` · `tests/test_totp.py::test_codes_from_further_away_are_rejected` |

### V6.6 Out-of-Band authentication mechanisms

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V6.6.1 | 2 | Verify that authentication mechanisms using the Public Switched Telephone Network (PSTN) to deliver One-time Passwords (OTPs) via phone or SMS are offered only when the phone number has previously been validated, alternate stronger methods (such as Time based One-time Passwords) are also offered, and the service provides information on their security risks to users. For L3 applications, phone and SMS must not be available as options. | ไม่เกี่ยวข้อง | ไม่มีการส่งรหัสทาง SMS หรือโทรศัพท์ — ระบบไม่เก็บเบอร์โทรเลย (`docs/DATA-CLASSIFICATION.md`) |
| V6.6.2 | 2 | Verify that out-of-band authentication requests, codes, or tokens are bound to the original authentication request for which they were generated and are not usable for a previous or subsequent one. | ไม่เกี่ยวข้อง | ไม่มีการยืนยันตัวนอกช่องทาง · สถานะครึ่งทางของ MFA ผูกกับคำขอเดิมและมีอายุ 5 นาที ซึ่งถูกประเมินที่ V6.5.1 |
| V6.6.3 | 2 | Verify that a code based out-of-band authentication mechanism is protected against brute force attacks by using rate limiting. Consider also using a code with at least 64 bits of entropy. | ไม่เกี่ยวข้อง | ไม่มีรหัสส่งนอกช่องทาง · ขั้นที่สองมีโควตาต่อบัญชีเหมือนหน้า login ซึ่งถูกประเมินที่ V6.3.1 |

### V6.8 Authentication with an Identity Provider

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V6.8.1 | 2 | Verify that, if the application supports multiple identity providers (IdPs), the user's identity cannot be spoofed via another supported identity provider (eg. by using the same user identifier). The standard mitigation would be for the application to register and identify the user using a combination of the IdP ID (serving as a namespace) and the user's ID in the IdP. | ผ่าน | ตัวตนจาก IdP เก็บเป็นคู่ (issuer, sub) ไม่ใช่ sub เปล่า ๆ ชื่อผู้ใช้จาก IdP คนละเจ้าจึงชนกันไม่ได้ — `app/plugins/auth/oidc/models.py` · `tests/test_oidc.py::test_first_login_links_by_username_then_uses_sub` |
| V6.8.2 | 2 | Verify that the presence and integrity of digital signatures on authentication assertions (for example on JWTs or SAML assertions) are always validated, rejecting any assertions that are unsigned or have invalid signatures. | ยังไม่ผ่าน | ข้อเดียวกับ V9.1.1 — `ADR 0028` เลือกยืนยันด้วย TLS ตาม OIDC Core 3.1.3.7 แทนการตรวจลายเซ็น ซึ่งสเปกของ OIDC อนุญาตแต่ **ASVS ข้อนี้ไม่ยกเว้นให้** |
| V6.8.3 | 2 | Verify that SAML assertions are uniquely processed and used only once within the validity period to prevent replay attacks. | ไม่เกี่ยวข้อง | ไม่รองรับ SAML — มีแต่ OIDC (`ADR 0028`) |
| V6.8.4 | 2 | Verify that, if an application uses a separate Identity Provider (IdP) and expects specific authentication strength, methods, or recentness for specific functions, the application verifies this using the information returned by the IdP. For example, if OIDC is used, this might be achieved by validating ID Token claims such as 'acr', 'amr', and 'auth_time' (if present). If the IdP does not provide this information, the application must have a documented fallback approach that assumes that the minimum strength authentication mechanism was used (for example, single-factor authentication using username and password). | ยังไม่ผ่าน | ไม่ได้อ่าน acr/amr/auth_time จาก ID token และ **ยังไม่มีเอกสารที่ประกาศว่าเมื่อไม่มีข้อมูลนั้นให้ถือว่าเป็นการยืนยันตัวปัจจัยเดียว** ซึ่งข้อนี้กำหนดให้ต้องมี |

## V7 — Session Management

### V7.1 Session Management Documentation

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V7.1.1 | 2 | Verify that the user's session inactivity timeout and absolute maximum session lifetime are documented, are appropriate in combination with other controls, and that the documentation includes justification for any deviations from NIST SP 800-63B re-authentication requirements. | ผ่าน | idle 30 นาที + absolute 12 ชม. ตรวจที่ server พร้อมเหตุผลของตัวเลข — `ADR 0020` · `app/session_security.py` · `tests/test_session_security.py::test_idle_timeout_signs_the_user_out` · `tests/test_session_security.py::test_absolute_timeout_signs_out_even_when_still_active` |
| V7.1.2 | 2 | Verify that the documentation defines how many concurrent (parallel) sessions are allowed for one account as well as the intended behaviors and actions to be taken when the maximum number of active sessions is reached. | ยังไม่ผ่าน | ยังไม่ได้ประกาศว่าหนึ่งบัญชีเปิดพร้อมกันได้กี่ session และจะทำอย่างไรเมื่อเกิน — ตอนนี้ไม่จำกัดโดยพฤตินัยเพราะไม่มี session store ฝั่ง server ที่จะนับได้ (`ADR 0020`) |
| V7.1.3 | 2 | Verify that all systems that create and manage user sessions as part of a federated identity management ecosystem (such as SSO systems) are documented along with controls to coordinate session lifetimes, termination, and any other conditions that require re-authentication. | ยังไม่ผ่าน | มี IdP ภายนอกแล้ว (`ADR 0028`) แต่ยังไม่มีเอกสารที่ผูกอายุ session ของเรากับของ IdP หรือบอกว่าเมื่อไรต้องยืนยันตัวใหม่ |

### V7.2 Fundamental Session Management Security

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V7.2.1 | 1 | Verify that the application performs all session token verification using a trusted, backend service. | ผ่าน | อายุและการผูก session ถูกตัดสินที่ server ทุกคำขอ ไม่ได้พึ่งวันหมดอายุบนคุกกี้ — `app/session_security.py` · `tests/test_session_security.py::test_a_session_without_timestamps_counts_as_expired` |
| V7.2.2 | 1 | Verify that the application uses either self-contained or reference tokens that are dynamically generated for session management, i.e. not using static API secrets and keys. | ผ่าน | คุกกี้ session ของ Flask เป็น self-contained ที่เซ็นด้วย SECRET_KEY ซึ่งไม่มีค่าเริ่มต้นและต้องยาว ≥ 32 ตัว — `tests/test_config.py` · `ADR 0020` |
| V7.2.3 | 1 | Verify that if reference tokens are used to represent user sessions, they are unique and generated using a cryptographically secure pseudo-random number generator (CSPRNG) and possess at least 128 bits of entropy. | ไม่เกี่ยวข้อง | ไม่ได้ใช้ reference token กับ session (ใช้คุกกี้แบบ self-contained) · ส่วน PAT ที่เป็น reference token จริงถูกประเมินที่ V6.2/V11 และใช้ค่าสุ่ม 256 บิต (`ADR 0017`) |
| V7.2.4 | 1 | Verify that the application generates a new session token on user authentication, including re-authentication, and terminates the current session token. | ผ่าน | start_session() ล้าง session ทั้งใบก่อนเสมอ ทั้งตอน login และตอนเปลี่ยนรหัสผ่าน (กัน session fixation) — `tests/test_session_security.py::test_login_throws_away_whatever_was_in_the_session_before` · `tests/test_session_security.py::test_changing_the_password_issues_a_fresh_session` |

### V7.3 Session Timeout

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V7.3.1 | 2 | Verify that there is an inactivity timeout such that re-authentication is enforced according to risk analysis and documented security decisions. | ผ่าน | idle 30 นาที ตรวจที่ server — `tests/test_session_security.py::test_idle_timeout_signs_the_user_out` · `tests/test_session_security.py::test_activity_pushes_the_idle_clock_forward` |
| V7.3.2 | 2 | Verify that there is an absolute maximum session lifetime such that re-authentication is enforced according to risk analysis and documented security decisions. | ผ่าน | absolute 12 ชม. ที่นาฬิกาไม่ขยับตามการใช้งาน — `tests/test_session_security.py::test_the_absolute_clock_does_not_move_with_activity` |

### V7.4 Session Termination

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V7.4.1 | 1 | Verify that when session termination is triggered (such as logout or expiration), the application disallows any further use of the session. For reference tokens or stateful sessions, this means invalidating the session data at the application backend. Applications using self-contained tokens will need a solution such as maintaining a list of terminated tokens, disallowing tokens produced before a per-user date and time or rotating a per-user signing key. | ยังไม่ผ่าน | logout ล้าง session ฝั่ง client ครบ (`tests/test_session_security.py::test_logout_leaves_nothing_behind`) แต่ **ไม่มี session store ฝั่ง server** คุกกี้ที่ถูกดักไว้ก่อนหน้าจึงยังใช้ได้จนหมดอายุ — ข้อจำกัดที่ `ADR 0020` บันทึกไว้เอง |
| V7.4.2 | 1 | Verify that the application terminates all active sessions when a user account is disabled or deleted (such as an employee leaving the company). | ผ่าน | ปิดบัญชีแล้วคุกกี้ทุกใบตายทันทีเพราะผูกกับ password_hash ที่เพิ่งถูกล้าง และ token ทุกใบถูกเพิกถอน — `app/services/personal_data.py` · `tests/test_close_account.py::test_the_password_is_cleared_immediately_not_after_the_grace_period` · `tests/test_close_account.py::test_api_keys_are_revoked_not_just_hidden` |
| V7.4.3 | 2 | Verify that the application gives the option to terminate all other active sessions after a successful change or removal of any authentication factor (including password change via reset or recovery and, if present, an MFA settings update). | ยังไม่ผ่าน | เปลี่ยนรหัสผ่านแล้ว **ทุก session ตายทันทีโดยไม่ต้องเลือก** ซึ่งแรงกว่าที่ข้อนี้ขอ (`tests/test_session_security.py::test_the_password_change_leaves_the_old_cookie_useless`) แต่การ**ปิดปัจจัยที่สอง**ไม่ได้ทำให้ session อื่นตาย — ข้อนี้จึงยังไม่ครบ |
| V7.4.4 | 2 | Verify that all pages that require authentication have easy and visible access to logout functionality. | ผ่าน | ปุ่มออกจากระบบอยู่ใน nav ของ `app/templates/base.html` ซึ่งทุกหน้าที่ต้อง login extend อยู่แล้ว |
| V7.4.5 | 2 | Verify that application administrators are able to terminate active sessions for an individual user or for all users. | ยังไม่ผ่าน | ผู้ดูแลทำได้แค่เปลี่ยนบทบาท (`app/admin/users.py`) · การไล่ session ของคนอื่นทำได้ทางอ้อมผ่าน flask set-password เท่านั้น ซึ่งเป็นการเปลี่ยนรหัสผ่านของเขา ไม่ใช่การจบ session |

### V7.5 Defenses Against Session Abuse

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V7.5.1 | 2 | Verify that the application requires full re-authentication before allowing modifications to sensitive account attributes which may affect authentication such as email address, phone number, MFA configuration, or other information used in account recovery. | ผ่าน | เปลี่ยนรหัสผ่าน ปิดปัจจัยที่สอง และออก API token ล้วนต้องกรอกรหัสผ่านซ้ำ — `app/services/passwords.py` · `app/routes.py` · `tests/test_totp.py` · `tests/test_tokens.py` |
| V7.5.2 | 2 | Verify that users are able to view and (having authenticated again with at least one factor) terminate any or all currently active sessions. | ยังไม่ผ่าน | ยังไม่มีหน้า "อุปกรณ์ที่ login อยู่" — ต้องมี session store ฝั่ง server ก่อน (`ADR 0020`) ตอนนี้ทำได้แค่เปลี่ยนรหัสผ่านซึ่งไล่ออกทุกเครื่องพร้อมกัน |

### V7.6 Federated Re-authentication

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V7.6.1 | 2 | Verify that session lifetime and termination between Relying Parties (RPs) and Identity Providers (IdPs) behave as documented, requiring re-authentication as necessary such as when the maximum time between IdP authentication events is reached. | ยังไม่ผ่าน | ยังไม่มี single logout และไม่ได้ผูกอายุ session ของเรากับเวลาที่ IdP ยืนยันตัวครั้งล่าสุด — `ADR 0028` บันทึกไว้แล้วว่ายังไม่ทำ |
| V7.6.2 | 2 | Verify that creation of a session requires either the user's consent or an explicit action, preventing the creation of new application sessions without user interaction. | ผ่าน | session เกิดจากการกดปุ่มของผู้ใช้เท่านั้น และการกลับจาก IdP ต้องมี handshake ที่ยังไม่ถูกใช้รออยู่ — `tests/test_oidc.py::test_callback_without_a_pending_handshake_is_refused` · `tests/test_oidc.py::test_a_pending_handshake_is_spent_even_when_the_attempt_fails` |

## V8 — Authorization

### V8.1 Authorization Documentation

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V8.1.1 | 1 | Verify that authorization documentation defines rules for restricting function-level and data-specific access based on consumer permissions and resource attributes. | ผ่าน | สองแกนแยกกันชัดและบันทึกไว้ทั้งคู่ — ความเป็นเจ้าของตอบ 404 (`ADR 0004`) ส่วนบทบาทตอบ 403 (`ADR 0022`) |
| V8.1.2 | 2 | Verify that authorization documentation defines rules for field-level access restrictions (both read and write) based on consumer permissions and resource attributes. Note that these rules might depend on other attribute values of the relevant data object, such as state or status. | ยังไม่ผ่าน | มีกฎระดับฟิลด์อยู่จริงในโค้ด (แก้ username ไม่ได้, แก้บทบาทตัวเองบนเว็บไม่ได้, update_todo() ปฏิเสธชื่อฟิลด์ที่ไม่รู้จัก) แต่ **ยังไม่มีเอกสารที่ประกาศกฎเหล่านี้ไว้รวมกัน** คนอ่านโค้ดเท่านั้นที่รู้ |

### V8.2 General Authorization Design

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V8.2.1 | 1 | Verify that the application ensures that function-level access is restricted to consumers with explicit permissions. | ผ่าน | ตรวจสิทธิ์ใน service ไม่ใช่ที่ route จึงครอบทั้ง HTML/API/CLI — `app/services/roles.py` · `tests/test_rbac.py::test_require_admin_stops_everyone_else` · `tests/test_rbac.py::test_the_cli_path_validates_the_role_too` |
| V8.2.2 | 1 | Verify that the application ensures that data-specific access is restricted to consumers with explicit permissions to specific data items to mitigate insecure direct object reference (IDOR) and broken object level authorization (BOLA). | ผ่าน | ทุก query กรองด้วย user_id และของคนอื่นตอบ 404 ไม่ใช่ 403 เพื่อไม่ให้รู้ว่า id นั้นมีจริง — `ADR 0004` · `app/services/lookup.py` · `tests/test_api_fuzz.py` (ยิงคำขอที่สร้างจากสัญญา API เอง) |
| V8.2.3 | 2 | Verify that the application ensures that field-level access is restricted to consumers with explicit permissions to specific fields to mitigate broken object property level authorization (BOPLA). | ผ่าน | update_todo() รับเฉพาะฟิลด์ที่ประกาศไว้และ **ปฏิเสธชื่อที่ไม่รู้จักแทนที่จะเมิน** ส่วนฝั่ง API ตั้ง unknown=RAISE — `app/services/todos.py` · `ADR 0016` · `tests/test_services.py` |

### V8.3 Operation Level Authorization

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V8.3.1 | 1 | Verify that the application enforces authorization rules at a trusted service layer and doesn't rely on controls that an untrusted consumer could manipulate, such as client-side JavaScript. | ผ่าน | ปุ่มที่ถูก disabled บนหน้าเว็บไม่ใช่การกันสิทธิ์ ตัวที่กันจริงอยู่ใน service เสมอ — `ADR 0016` · `tests/test_service_layer.py` · `tests/test_rbac.py::test_posting_a_role_change_as_a_normal_user_changes_nothing` |

### V8.4 Other Authorization Considerations

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V8.4.1 | 2 | Verify that multi-tenant applications use cross-tenant controls to ensure consumer operations will never affect tenants with which they do not have permissions to interact. | ไม่เกี่ยวข้อง | ไม่ใช่ระบบหลายผู้เช่า — ขอบเขตการแยกข้อมูลคือรายบุคคล ซึ่งถูกประเมินที่ V8.2.2 แล้ว |

## V9 — Self-contained Tokens

### V9.1 Token source and integrity

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V9.1.1 | 1 | Verify that self-contained tokens are validated using their digital signature or MAC to protect against tampering before accepting the token's contents. | ยังไม่ผ่าน | **เบี่ยงจากข้อนี้โดยตั้งใจและบันทึกไว้แล้ว** — `ADR 0028` เลือกยืนยัน ID token ด้วย TLS ตาม OIDC Core 1.0 หัวข้อ 3.1.3.7 ข้อ 6 (token มาจาก token endpoint โดยตรงผ่านช่องที่ยืนยันตัว server แล้ว) แทนการตรวจลายเซ็น · สเปกอนุญาต แต่ **ข้อกำหนดของ ASVS ข้อนี้ไม่ถูกทำตามตามตัวอักษร** จึงตอบว่ายังไม่ผ่าน ไม่ใช่ไม่เกี่ยวข้อง |
| V9.1.2 | 1 | Verify that only algorithms on an allowlist can be used to create and verify self-contained tokens, for a given context. The allowlist must include the permitted algorithms, ideally only either symmetric or asymmetric algorithms, and must not include the 'None' algorithm. If both symmetric and asymmetric must be supported, additional controls will be needed to prevent key confusion. | ยังไม่ผ่าน | ผลพวงของ V9.1.1 — เมื่อไม่ตรวจลายเซ็นก็ไม่มี allowlist ของอัลกอริทึม (รวมถึงการปฏิเสธ 'None') · จะมีพร้อมกันเมื่อทำ V9.1.1 |
| V9.1.3 | 1 | Verify that key material that is used to validate self-contained tokens is from trusted pre-configured sources for the token issuer, preventing attackers from specifying untrusted sources and keys. For JWTs and other JWS structures, headers such as 'jku', 'x5u', and 'jwk' must be validated against an allowlist of trusted sources. | ไม่เกี่ยวข้อง | ไม่ได้ดึงคีย์จากที่ไหนเลย จึงไม่มีช่องให้ token ระบุแหล่งคีย์ของตัวเอง (jku/x5u/jwk) — ความเสี่ยงที่เหลืออยู่ถูกนับไว้ที่ V9.1.1 แล้ว ไม่ใช่หายไป |

### V9.2 Token content

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V9.2.1 | 1 | Verify that, if a validity time span is present in the token data, the token and its content are accepted only if the verification time is within this validity time span. For example, for JWTs, the claims 'nbf' and 'exp' must be verified. | ยังไม่ผ่าน | ตรวจ exp พร้อมเผื่อความคลาดของนาฬิกาแล้ว (`app/plugins/auth/oidc/factor.py` · `tests/test_oidc.py::test_id_token_claims_are_all_checked`) แต่ **ไม่ได้ตรวจ nbf** — token ที่ IdP ออกให้มีผลในอนาคตจะถูกรับตั้งแต่ตอนนี้ |
| V9.2.2 | 2 | Verify that the service receiving a token validates the token to be the correct type and is meant for the intended purpose before accepting the token's contents. For example, only access tokens can be accepted for authorization decisions and only ID Tokens can be used for proving user authentication. | ผ่าน | ใช้เฉพาะ id_token จาก token endpoint สำหรับการยืนยันตัวตน ไม่เคยรับ access token มาตัดสินสิทธิ์ — `app/plugins/auth/oidc/factor.py` · `tests/test_oidc.py::test_a_token_response_without_an_id_token_is_refused` |
| V9.2.3 | 2 | Verify that the service only accepts tokens which are intended for use with that service (audience). For JWTs, this can be achieved by validating the 'aud' claim against an allowlist defined in the service. | ผ่าน | เทียบ aud กับ OIDC_CLIENT_ID ของเราเสมอ รับทั้งแบบสตริงเดียวและรายการ — `tests/test_oidc.py::test_id_token_claims_are_all_checked` |
| V9.2.4 | 2 | Verify that, if a token issuer uses the same private key for issuing tokens to different audiences, the issued tokens contain an audience restriction that uniquely identifies the intended audiences. This will prevent a token from being reused with an unintended audience. If the audience identifier is dynamically provisioned, the token issuer must validate these audiences in order to make sure that they do not result in audience impersonation. | ไม่เกี่ยวข้อง | ระบบนี้เป็นผู้รับ token ไม่ใช่ผู้ออก — PAT ของเราไม่ใช่ self-contained token แต่เป็นกุญแจที่ต้องไปค้นในฐานข้อมูล (`ADR 0017`) |

## V10 — OAuth and OIDC

### V10.1 Generic OAuth and OIDC Security

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V10.1.1 | 2 | Verify that tokens are only sent to components that strictly need them. For example, when using a backend-for-frontend pattern for browser-based JavaScript applications, access and refresh tokens shall only be accessible for the backend. | ผ่าน | token ไม่เคยออกจากฝั่ง server — เบราว์เซอร์เห็นแค่ redirect และ code ส่วน id_token ถูกแลกที่ backend แล้วทิ้ง ไม่มีการเก็บลงที่ไหน · `app/plugins/auth/oidc/factor.py` · `tests/test_oidc.py::test_a_full_round_trip_signs_the_user_in` |
| V10.1.2 | 2 | Verify that the client only accepts values from the authorization server (such as the authorization code or ID Token) if these values result from an authorization flow that was initiated by the same user agent session and transaction. This requires that client-generated secrets, such as the proof key for code exchange (PKCE) 'code_verifier', 'state' or OIDC 'nonce', are not guessable, are specific to the transaction, and are securely bound to both the client and the user agent session in which the transaction was started. | ผ่าน | state, nonce และ code_verifier ของ PKCE ถูกเก็บใน session ของ user agent เดิมและ **ถูกใช้ได้ครั้งเดียว** — `tests/test_oidc.py::test_state_that_does_not_match_is_refused` · `tests/test_oidc.py::test_a_pending_handshake_is_spent_even_when_the_attempt_fails` |

### V10.2 OAuth Client

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V10.2.1 | 2 | Verify that, if the code flow is used, the OAuth client has protection against browser-based request forgery attacks, commonly known as cross-site request forgery (CSRF), which trigger token requests, either by using proof key for code exchange (PKCE) functionality or checking the 'state' parameter that was sent in the authorization request. | ผ่าน | ใช้ทั้ง PKCE และ state ไม่ใช่อย่างใดอย่างหนึ่ง — `tests/test_oidc.py::test_begin_asks_for_the_code_flow_with_pkce` · `tests/test_oidc.py::test_callback_without_a_pending_handshake_is_refused` |
| V10.2.2 | 2 | Verify that, if the OAuth client can interact with more than one authorization server, it has a defense against mix-up attacks. For example, it could require that the authorization server return the 'iss' parameter value and validate it in the authorization response and the token response. | ไม่เกี่ยวข้อง | รองรับ IdP ได้ทีละเจ้าเท่านั้น (issuer เดียวจาก config) จึงไม่มีสถานการณ์ mix-up · ถ้าวันหนึ่งรองรับหลายเจ้า ข้อนี้ต้องกลับมาเป็น "เกี่ยวข้อง" ทันที |

### V10.3 OAuth Resource Server

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V10.3.1 | 2 | Verify that the resource server only accepts access tokens that are intended for use with that service (audience). The audience may be included in a structured access token (such as the 'aud' claim in JWT), or it can be checked using the token introspection endpoint. | ไม่เกี่ยวข้อง | ไม่ได้เป็น OAuth resource server — /api/v1 ใช้ personal access token ของเราเองที่ต้องไปค้นในฐานข้อมูล ไม่ใช่ access token ของ OAuth (`ADR 0017`) |
| V10.3.2 | 2 | Verify that the resource server enforces authorization decisions based on claims from the access token that define delegated authorization. If claims such as 'sub', 'scope', and 'authorization_details' are present, they must be part of the decision. | ไม่เกี่ยวข้อง | ไม่ได้เป็น OAuth resource server (ดู V10.3.1) |
| V10.3.3 | 2 | Verify that if an access control decision requires identifying a unique user from an access token (JWT or related token introspection response), the resource server identifies the user from claims that cannot be reassigned to other users. Typically, it means using a combination of 'iss' and 'sub' claims. | ไม่เกี่ยวข้อง | ไม่ได้เป็น OAuth resource server · การระบุตัวผู้ใช้จาก ID token ถูกประเมินที่ V10.5.2 |
| V10.3.4 | 2 | Verify that, if the resource server requires specific authentication strength, methods, or recentness, it verifies that the presented access token satisfies these constraints. For example, if present, using the OIDC 'acr', 'amr' and 'auth_time' claims respectively. | ไม่เกี่ยวข้อง | ไม่ได้เป็น OAuth resource server · ความแรงของการยืนยันตัวจาก IdP ถูกประเมินที่ V6.8.4 ซึ่งเป็นช่องว่างที่บันทึกไว้แล้ว |

### V10.4 OAuth Authorization Server

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V10.4.1 | 1 | Verify that the authorization server validates redirect URIs based on a client-specific allowlist of pre-registered URIs using exact string comparison. | ไม่เกี่ยวข้อง | ระบบนี้ไม่ได้เป็น authorization server — เป็นฝ่ายที่ไปขอ (relying party) |
| V10.4.2 | 1 | Verify that, if the authorization server returns the authorization code in the authorization response, it can be used only once for a token request. For the second valid request with an authorization code that has already been used to issue an access token, the authorization server must reject a token request and revoke any issued tokens related to the authorization code. | ไม่เกี่ยวข้อง | ไม่ได้เป็น authorization server |
| V10.4.3 | 1 | Verify that the authorization code is short-lived. The maximum lifetime can be up to 10 minutes for L1 and L2 applications and up to 1 minute for L3 applications. | ไม่เกี่ยวข้อง | ไม่ได้เป็น authorization server |
| V10.4.4 | 1 | Verify that for a given client, the authorization server only allows the usage of grants that this client needs to use. Note that the grants 'token' (Implicit flow) and 'password' (Resource Owner Password Credentials flow) must no longer be used. | ไม่เกี่ยวข้อง | ไม่ได้เป็น authorization server · ฝั่งเราขอเฉพาะ code flow ไม่มีที่ไหนใช้ implicit หรือ password grant (`ADR 0028`) |
| V10.4.5 | 1 | Verify that the authorization server mitigates refresh token replay attacks for public clients, preferably using sender-constrained refresh tokens, i.e., Demonstrating Proof of Possession (DPoP) or Certificate-Bound Access Tokens using mutual TLS (mTLS). For L1 and L2 applications, refresh token rotation may be used. If refresh token rotation is used, the authorization server must invalidate the refresh token after usage, and revoke all refresh tokens for that authorization if an already used and invalidated refresh token is provided. | ไม่เกี่ยวข้อง | ไม่ได้เป็น authorization server และไม่ได้ใช้ refresh token เลย |
| V10.4.6 | 2 | Verify that, if the code grant is used, the authorization server mitigates authorization code interception attacks by requiring proof key for code exchange (PKCE). For authorization requests, the authorization server must require a valid 'code_challenge' value and must not accept a 'code_challenge_method' value of 'plain'. For a token request, it must require validation of the 'code_verifier' parameter. | ไม่เกี่ยวข้อง | ไม่ได้เป็น authorization server · ฝั่งเราส่ง code_challenge แบบ S256 เสมอ ซึ่งประเมินที่ V10.2.1 |
| V10.4.7 | 2 | Verify that if the authorization server supports unauthenticated dynamic client registration, it mitigates the risk of malicious client applications. It must validate client metadata such as any registered URIs, ensure the user's consent, and warn the user before processing an authorization request with an untrusted client application. | ไม่เกี่ยวข้อง | ไม่ได้เป็น authorization server |
| V10.4.8 | 2 | Verify that refresh tokens have an absolute expiration, including if sliding refresh token expiration is applied. | ไม่เกี่ยวข้อง | ไม่ได้เป็น authorization server และไม่มี refresh token |
| V10.4.9 | 2 | Verify that refresh tokens and reference access tokens can be revoked by an authorized user using the authorization server user interface, to mitigate the risk of malicious clients or stolen tokens. | ไม่เกี่ยวข้อง | ไม่ได้เป็น authorization server · การเพิกถอน PAT ของเราเองประเมินที่ V6/V7 (`ADR 0017`) |
| V10.4.10 | 2 | Verify that confidential client is authenticated for client-to-authorized server backchannel requests such as token requests, pushed authorization requests (PAR), and token revocation requests. | ไม่เกี่ยวข้อง | ไม่ได้เป็น authorization server · ฝั่งเรายืนยันตัวเป็น confidential client ด้วย client_secret ตอนเรียก token endpoint |
| V10.4.11 | 2 | Verify that the authorization server configuration only assigns the required scopes to the OAuth client. | ไม่เกี่ยวข้อง | ไม่ได้เป็น authorization server — scope ที่ขอถูกกำหนดฝั่งเราให้น้อยที่สุดเท่าที่ต้องใช้ |

### V10.5 OIDC Client

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V10.5.1 | 2 | Verify that the client (as the relying party) mitigates ID Token replay attacks. For example, by ensuring that the 'nonce' claim in the ID Token matches the 'nonce' value sent in the authentication request to the OpenID Provider (in OAuth2 refereed to as the authorization request sent to the authorization server). | ผ่าน | เทียบ nonce ใน ID token กับค่าที่ส่งไปในคำขอด้วย hmac.compare_digest — `tests/test_oidc.py::test_id_token_claims_are_all_checked` |
| V10.5.2 | 2 | Verify that the client uniquely identifies the user from ID Token claims, usually the 'sub' claim, which cannot be reassigned to other users (for the scope of an identity provider). | ผ่าน | ผูกด้วยคู่ (issuer, sub) ไม่ใช่ sub เปล่า และ **ผูกครั้งแรกด้วยชื่อผู้ใช้แล้วใช้ sub ตลอดไป** — `app/plugins/auth/oidc/models.py` · `tests/test_oidc.py::test_first_login_links_by_username_then_uses_sub` |
| V10.5.3 | 2 | Verify that the client rejects attempts by a malicious authorization server to impersonate another authorization server through authorization server metadata. The client must reject authorization server metadata if the issuer URL in the authorization server metadata does not exactly match the pre-configured issuer URL expected by the client. | ยังไม่ผ่าน | ตรวจ iss ใน ID token กับ issuer ที่ตั้งไว้แล้ว (`tests/test_oidc.py::test_id_token_claims_are_all_checked`) แต่ **ไม่ได้ตรวจฟิลด์ issuer ในเอกสาร discovery เอง** ซึ่งข้อนี้ขอให้เทียบแบบตรงตัว |
| V10.5.4 | 2 | Verify that the client validates that the ID Token is intended to be used for that client (audience) by checking that the 'aud' claim from the token is equal to the 'client_id' value for the client. | ผ่าน | เทียบ aud กับ OIDC_CLIENT_ID ของเรา รับทั้งสตริงเดียวและรายการตามสเปก — `tests/test_oidc.py::test_id_token_claims_are_all_checked` |
| V10.5.5 | 2 | Verify that, when using OIDC back-channel logout, the relying party mitigates denial of service through forced logout and cross-JWT confusion in the logout flow. The client must verify that the logout token is correctly typed with a value of 'logout+jwt', contains the 'event' claim with the correct member name, and does not contain a 'nonce' claim. Note that it is also recommended to have a short expiration (e.g., 2 minutes). | ไม่เกี่ยวข้อง | ยังไม่รองรับ back-channel logout (`ADR 0028` บันทึกไว้ว่ายังไม่ทำ) จึงไม่มี logout token ให้ตรวจ — ต้องกลับมาเมื่อทำ single logout |

### V10.6 OpenID Provider

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V10.6.1 | 2 | Verify that the OpenID Provider only allows values 'code', 'ciba', 'id_token', or 'id_token code' for response mode. Note that 'code' is preferred over 'id_token code' (the OIDC Hybrid flow), and 'token' (any Implicit flow) must not be used. | ไม่เกี่ยวข้อง | ไม่ได้เป็น OpenID Provider |
| V10.6.2 | 2 | Verify that the OpenID Provider mitigates denial of service through forced logout. By obtaining explicit confirmation from the end-user or, if present, validating parameters in the logout request (initiated by the relying party), such as the 'id_token_hint'. | ไม่เกี่ยวข้อง | ไม่ได้เป็น OpenID Provider |

### V10.7 Consent Management

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V10.7.1 | 2 | Verify that the authorization server ensures that the user consents to each authorization request. If the identity of the client cannot be assured, the authorization server must always explicitly prompt the user for consent. | ไม่เกี่ยวข้อง | การขอความยินยอมเป็นหน้าที่ของ authorization server ซึ่งไม่ใช่เรา |
| V10.7.2 | 2 | Verify that when the authorization server prompts for user consent, it presents sufficient and clear information about what is being consented to. When applicable, this should include the nature of the requested authorizations (typically based on scope, resource server, Rich Authorization Requests (RAR) authorization details), the identity of the authorized application, and the lifetime of these authorizations. | ไม่เกี่ยวข้อง | ไม่ได้เป็น authorization server |
| V10.7.3 | 2 | Verify that the user can review, modify, and revoke consents which the user has granted through the authorization server. | ไม่เกี่ยวข้อง | ไม่ได้เป็น authorization server |

## V11 — Cryptography

### V11.1 Cryptographic Inventory and Documentation

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V11.1.1 | 2 | Verify that there is a documented policy for management of cryptographic keys and a cryptographic key lifecycle that follows a key management standard such as NIST SP 800-57. This should include ensuring that keys are not overshared (for example, with more than two entities for shared secrets and more than one entity for private keys). | ยังไม่ผ่าน | ยังไม่มีนโยบายการจัดการกุญแจที่เขียนไว้ (วงจรชีวิต ใครถือได้ หมุนเมื่อไร) · ของที่มีคือคำเตือนกระจายอยู่ตามที่ต่าง ๆ เช่น เปลี่ยน SECRET_KEY แล้วเทียบค่าเก่าใน audit ไม่ได้ (`ADR 0014`) ซึ่งไม่ใช่นโยบาย |
| V11.1.2 | 2 | Verify that a cryptographic inventory is performed, maintained, regularly updated, and includes all cryptographic keys, algorithms, and certificates used by the application. It must also document where keys can and cannot be used in the system, and the types of data that can and cannot be protected using the keys. | ยังไม่ผ่าน | ยังไม่มีบัญชีรายการของกุญแจ/อัลกอริทึม/ใบรับรองที่ใช้อยู่ทั้งระบบไว้ที่เดียว — จะทำพร้อม V11.1.1 |

### V11.2 Secure Cryptography Implementation

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V11.2.1 | 2 | Verify that industry-validated implementations (including libraries and hardware-accelerated implementations) are used for cryptographic operations. | ผ่าน | ใช้ของมาตรฐานทั้งหมด ไม่มี crypto ที่เขียนเอง — hashlib/hmac/secrets ของ Python (OpenSSL) และ scrypt ของ werkzeug · `app/audit.py` · `app/services/tokens.py` |
| V11.2.2 | 2 | Verify that the application is designed with crypto agility such that random number, authenticated encryption, MAC, or hashing algorithms, key lengths, rounds, ciphers and modes can be reconfigured, upgraded, or swapped at any time, to protect against cryptographic breaks. Similarly, it must also be possible to replace keys and passwords and re-encrypt data. This will allow for seamless upgrades to post-quantum cryptography (PQC), once high-assurance implementations of approved PQC schemes or standards are widely available. | ยังไม่ผ่าน | ยังไม่มีเส้นทางหมุนที่เขียนไว้ — เปลี่ยนวิธีแฮชรหัสผ่านแล้วไม่มีกลไกอัปเกรด hash เก่าตอน login และการเปลี่ยนกุญแจ HMAC ของ audit ทำให้เทียบค่าเก่าไม่ได้ถาวร (`ADR 0014`) · ผูกกับ V11.1.1 |
| V11.2.3 | 2 | Verify that all cryptographic primitives utilize a minimum of 128-bits of security based on the algorithm, key size, and configuration. For example, a 256-bit ECC key provides roughly 128 bits of security where RSA requires a 3072-bit key to achieve 128 bits of security. | ผ่าน | ต่ำสุดคือ SHA-256/HMAC-SHA256 และค่าสุ่ม 160–256 บิต ไม่มีอะไรต่ำกว่า 128 บิต — `app/services/tokens.py` (256 บิต) · `tests/test_totp.py::test_a_fresh_secret_is_random_and_long_enough` (160 บิต) |

### V11.3 Encryption Algorithms

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V11.3.1 | 1 | Verify that insecure block modes (e.g., ECB) and weak padding schemes (e.g., PKCS#1 v1.5) are not used. | ไม่เกี่ยวข้อง | ระบบไม่เข้ารหัสข้อมูลเลย จึงไม่มี block mode หรือ padding ให้เลือกผิด — ความลับทุกตัวถูกเก็บเป็น hash และคุกกี้ session ถูก *เซ็น* ไม่ใช่ *เข้ารหัส* (`ADR 0020`) |
| V11.3.2 | 1 | Verify that only approved ciphers and modes such as AES with GCM are used. | ไม่เกี่ยวข้อง | ไม่มีการเข้ารหัสข้อมูลในระบบ (ดู V11.3.1) · การเข้ารหัสระหว่างทางเป็นเรื่องของ TLS ซึ่งประเมินที่ V12 |
| V11.3.3 | 2 | Verify that encrypted data is protected against unauthorized modification preferably by using an approved authenticated encryption method or by combining an approved encryption method with an approved MAC algorithm. | ไม่เกี่ยวข้อง | ไม่มีข้อมูลที่ถูกเข้ารหัส · ความสมบูรณ์ของ audit ใช้ hash chain ซึ่งประเมินที่ V11.4.3 |

### V11.4 Hashing and Hash-based Functions

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V11.4.1 | 1 | Verify that only approved hash functions are used for general cryptographic use cases, including digital signatures, HMAC, KDF, and random bit generation. Disallowed hash functions, such as MD5, must not be used for any cryptographic purpose. | ผ่าน | SHA-256 และ HMAC-SHA256 ทั้งระบบ ไม่มี MD5 ที่ไหนเลย — `app/audit.py` · `app/services/tokens.py` · **ข้อยกเว้นที่เปิดเผยไว้: TOTP ใช้ HMAC-SHA1 เพราะ RFC 6238 กำหนดไว้เพื่อความเข้ากันได้ของแอปยืนยันตัว** ซึ่ง NIST ยังยอมรับสำหรับการใช้แบบ HMAC (`tests/test_totp.py::test_matches_the_rfc_6238_test_vectors`) |
| V11.4.2 | 2 | Verify that passwords are stored using an approved, computationally intensive, key derivation function (also known as a "password hashing function"), with parameter settings configured based on current guidance. The settings should balance security and performance to make brute-force attacks sufficiently challenging for the required level of security. | ผ่าน | scrypt ผ่าน werkzeug พร้อม salt ต่อรายการ — `ADR 0019` · `tests/test_passwords.py::test_a_password_that_normalization_rewrites_still_signs_in` · **PAT ตั้งใจไม่ใช้ scrypt** เพราะค่าสุ่ม 256 บิตไม่มี dictionary ให้ไล่ ส่วน scrypt ต่อ request คือช่องให้ยิงถล่ม (`ADR 0017`) |
| V11.4.3 | 2 | Verify that hash functions used in digital signatures, as part of data authentication or data integrity are collision resistant and have appropriate bit-lengths. If collision resistance is required, the output length must be at least 256 bits. If only resistance to second pre-image attacks is required, the output length must be at least 128 bits. | ผ่าน | สาย audit ใช้ SHA-256 (256 บิต ทนการชน) — `ADR 0015` · `tests/test_audit.py::test_the_checkpoint_records_what_it_replaced` |
| V11.4.4 | 2 | Verify that the application uses approved key derivation functions with key stretching parameters when deriving secret keys from passwords. The parameters in use must balance security and performance to prevent brute-force attacks from compromising the resulting cryptographic key. | ผ่าน | ที่เดียวที่ derive กุญแจจากรหัสผ่านคือการแฮชรหัสผ่านเอง ซึ่งใช้ scrypt ที่มี key stretching อยู่แล้ว — `ADR 0019` |

### V11.5 Random Values

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V11.5.1 | 2 | Verify that all random numbers and strings which are intended to be non-guessable must be generated using a cryptographically secure pseudo-random number generator (CSPRNG) and have at least 128 bits of entropy. Note that UUIDs do not respect this condition. | ผ่าน | ทุกค่าที่ต้องเดาไม่ได้มาจาก secrets ของ Python — PAT 256 บิต (`ADR 0017`), เมล็ด TOTP 160 บิต, state/nonce ของ OIDC 256 บิต (`tests/test_oidc.py::test_begin_asks_for_the_code_flow_with_pkce`) · request_id เป็น UUID แต่เป็นค่าไว้ correlate ไม่ใช่ค่าลับ |

### V11.6 Public Key Cryptography

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V11.6.1 | 2 | Verify that only approved cryptographic algorithms and modes of operation are used for key generation and seeding, and digital signature generation and verification. Key generation algorithms must not generate insecure keys vulnerable to known attacks, for example, RSA keys which are vulnerable to Fermat factorization. | ไม่เกี่ยวข้อง | แอปไม่สร้างกุญแจและไม่เซ็นอะไรด้วย public key · ใบรับรอง TLS เป็นของชั้น deployment (`deploy/nginx-tls.conf`) ส่วน `scripts/dev_tls_cert.sh` มีไว้สำหรับ dev/CI เท่านั้น |

## V12 — Secure Communication

### V12.1 General TLS Security Guidance

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V12.1.1 | 1 | Verify that only the latest recommended versions of the TLS protocol are enabled, such as TLS 1.2 and TLS 1.3. The latest version of the TLS protocol must be the preferred option. | ผ่าน | 1.2 กับ 1.3 เท่านั้น และ **พิสูจน์ที่ฝั่ง server ไม่ใช่ที่ client** — `deploy/nginx-tls.conf` · `ci:stack` ยิง 1.0/1.1 ทุก push แล้วต้องถูกปฏิเสธ |
| V12.1.2 | 2 | Verify that only recommended cipher suites are enabled, with the strongest cipher suites set as preferred. L3 applications must only support cipher suites which provide forward secrecy. | ยังไม่ผ่าน | ไม่ได้ประกาศ ssl_ciphers ไว้ จึงตกไปใช้ค่าเริ่มต้นของ image — เหตุผลเดียวกับที่ไฟล์นั้นเขียนไว้เองเรื่อง ssl_protocols ว่า "การไม่เขียนบรรทัดนี้คือปล่อยให้ image ตัดสินแทน" ยังใช้กับ cipher เหมือนกัน |
| V12.1.3 | 2 | Verify that the application validates that mTLS client certificates are trusted before using the certificate identity for authentication or authorization. | ไม่เกี่ยวข้อง | ไม่ได้ใช้ mTLS ที่ไหน |

### V12.2 HTTPS Communication with External Facing Services

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V12.2.1 | 1 | Verify that TLS is used for all connectivity between a client and external facing, HTTP-based services, and does not fall back to insecure or unencrypted communications. | ผ่าน | เปิด TLS แล้ว http ถูก redirect ไป https พร้อม HSTS และคุกกี้ติด Secure — คุมด้วยสวิตช์เดียว (`app/security_headers.py` · `ci:stack`) |
| V12.2.2 | 1 | Verify that external facing services use publicly trusted TLS certificates. | ยังไม่ผ่าน | ใบรับรองใน repo เป็น self-signed สำหรับ dev/CI ซึ่งถูกต้อง แต่ **เอกสารยังไม่ได้บอกผู้ติดตั้งว่า production ต้องใช้ใบรับรองที่เชื่อถือได้สาธารณะ** — เป็นช่องว่างของเอกสาร ไม่ใช่ของโค้ด |

### V12.3 General Service to Service Communication Security

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V12.3.1 | 2 | Verify that an encrypted protocol such as TLS is used for all inbound and outbound connections to and from the application, including monitoring systems, management tools, remote access and SSH, middleware, databases, mainframes, partner systems, or external APIs. The server must not fall back to insecure or unencrypted protocols. | ยังไม่ผ่าน | ขาออกเข้ารหัสครบ (OIDC บังคับ https · LDAP บังคับ ldaps:// เว้นแต่สั่งเป็นอย่างอื่นแล้วมันจะเตือนทุกครั้ง · Vault ผ่าน https) แต่ **การต่อจากแอปไปฐานข้อมูลและ redis ใน compose ยังไม่ได้เข้ารหัส** |
| V12.3.2 | 2 | Verify that TLS clients validate certificates received before communicating with a TLS server. | ผ่าน | ตัว client ตรวจใบรับรองตามค่าเริ่มต้นและการปิดต้องสั่งอย่างชัดแจ้งพร้อม log เตือนทุกครั้งที่ start — `tests/test_oidc.py::test_an_http_issuer_that_is_opted_in_warns_every_time` · `tests/test_oidc.py::test_endpoints_from_the_discovery_document_must_be_https` |
| V12.3.3 | 2 | Verify that TLS or another appropriate transport encryption mechanism used for all connectivity between internal, HTTP-based services within the application, and does not fall back to insecure or unencrypted communications. | ยังไม่ผ่าน | ช่วง proxy → app ภายใน network ของ docker ยังเป็น http — ผูกกับ V12.3.1 |
| V12.3.4 | 2 | Verify that TLS connections between internal services use trusted certificates. Where internally generated or self-signed certificates are used, the consuming service must be configured to only trust specific internal CAs and specific self-signed certificates. | ยังไม่ผ่าน | ต้องมี V12.3.3 ก่อนถึงจะมีใบรับรองภายในให้พูดถึง |

## V13 — Configuration

### V13.1 Configuration Documentation

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V13.1.1 | 2 | Verify that all communication needs for the application are documented. This must include external services which the application relies upon and cases where an end user might be able to provide an external location to which the application will then connect. | ผ่าน | ปลายทางทุกตัวที่ระบบคุยด้วยอยู่ในตารางเดียวใน `docs/ROPA.md` ข้อ 4 พร้อมบอกว่าส่งอะไรออกไปและเข้ารหัสหรือยัง · **ทุกตัวเลือกด้วย config ตัวเดียว ไม่มีปลายทางที่ฝังในโค้ด** — `tests/test_ropa.py::test_every_outward_destination_is_listed` บังคับว่าคีย์ใหม่ต้องถูกบันทึก |

### V13.2 Backend Communication Configuration

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V13.2.1 | 2 | Verify that communications between backend application components that don't support the application's standard user session mechanism, including APIs, middleware, and data layers, are authenticated. Authentication must use individual service accounts, short-term tokens, or certificate-based authentication and not unchanging credentials such as passwords, API keys, or shared accounts with privileged access. | ยังไม่ผ่าน | แอปคุยกับฐานข้อมูลด้วยรหัสผ่านที่ไม่หมุน — ยังไม่ใช้บัญชีบริการรายตัวหรือ token อายุสั้น · `ADR 0030` วางทางไว้แล้ว (ความลับมาจากแหล่งที่ประกาศ) แต่ค่ายังเป็นค่าเดิมตลอด · **อยู่ในกลุ่ม "ขาออกและเครือข่าย" ของ backlog** |
| V13.2.2 | 2 | Verify that communications between backend application components, including local or operating system services, APIs, middleware, and data layers, are performed with accounts assigned the least necessary privileges. | ผ่าน | แอปต่อฐานข้อมูลด้วยบัญชี todolist ไม่ใช่ root — `compose.mysql.yaml` · และ container รันด้วยผู้ใช้ที่ไม่ใช่ root (`Dockerfile`) |
| V13.2.3 | 2 | Verify that if a credential has to be used for service authentication, the credential being used by the consumer is not a default credential (e.g., root/root or admin/admin). | ผ่าน | ไม่มีรหัสผ่านค่าเริ่มต้นเลย — compose ประกาศเป็นตัวแปรที่ **ไม่มีค่าเริ่มต้นและ start ไม่ขึ้นถ้าไม่ตั้ง** (`compose.mysql.yaml`) หลักเดียวกับ SECRET_KEY (`tests/test_config.py`) |
| V13.2.4 | 2 | Verify that an allowlist is used to define the external resources or systems with which the application is permitted to communicate (e.g., for outbound requests, data loads, or file access). This allowlist can be implemented at the application layer, web server, firewall, or a combination of different layers. | ยังไม่ผ่าน | ปลายทางขาออกถูกจำกัดด้วย scheme และค่า config (`app/plugins/auth/oidc/factor.py` ปฏิเสธ scheme ที่ไม่ใช่ https ก่อนเปิด) แต่ **ยังไม่มี allowlist ของ host** — endpoint ที่เอามาใช้จริงมาจากเอกสาร discovery ของ IdP ซึ่งเป็นข้อมูลภายนอก |
| V13.2.5 | 2 | Verify that the web or application server is configured with an allowlist of resources or systems to which the server can send requests or load data or files from. | ยังไม่ผ่าน | ไม่มี allowlist ที่ชั้น web server หรือ firewall — ผูกกับ V13.2.4 |

### V13.3 Secret Management

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V13.3.1 | 2 | Verify that a secrets management solution, such as a key vault, is used to securely create, store, control access to, and destroy backend secrets. These could include passwords, key material, integrations with databases and third-party systems, keys and seeds for time-based tokens, other internal secrets, and API keys. Secrets must not be included in application source code or included in build artifacts. For an L3 application, this must involve a hardware-backed solution such as an HSM. | ผ่าน | ความลับมาจากแหล่งที่ประกาศด้วย scheme ของ SECRETS_URL รวมถึง vault:// — `ADR 0030` · `ci:vault` พิสูจน์ทุก push ว่าค่ามาจาก Vault จริง และ **แหล่งที่ถามไม่ได้ทำให้ไม่ start** · ความลับไม่อยู่ในซอร์ส (`ci:secret-scan`) |
| V13.3.2 | 2 | Verify that access to secret assets adheres to the principle of least privilege. | ยังไม่ผ่าน | ยังไม่ได้เขียนนโยบายว่าใคร/อะไรอ่านความลับตัวไหนได้ — policy ของ Vault ที่ใช้ใน `ci:vault` เป็นของสำหรับทดสอบ ไม่ใช่ต้นแบบที่ประกาศไว้ว่าเป็นสิทธิ์ขั้นต่ำ |

### V13.4 Unintended Information Leakage

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V13.4.1 | 1 | Verify that the application is deployed either without any source control metadata, including the .git or .svn folders, or in a way that these folders are inaccessible both externally and to the application itself. | ผ่าน | `.dockerignore` ตัด .git/ .github/ .gitignore ออกจาก build context — `ci:image` build จริงทุก push |
| V13.4.2 | 2 | Verify that debug modes are disabled for all components in production environments to prevent exposure of debugging features and information leakage. | ผ่าน | image รัน gunicorn ตรง ๆ ไม่มี --reload และไม่ตั้ง FLASK_DEBUG — `Dockerfile` · debug ของ Flask ต้องสั่งเองด้วย flask run --debug เท่านั้น |
| V13.4.3 | 2 | Verify that web servers do not expose directory listings to clients unless explicitly intended. | ผ่าน | nginx ไม่เปิด autoindex และ Flask ไม่เสิร์ฟรายการไดเรกทอรี — `deploy/nginx-location.conf` · `ci:dast` ยิง ZAP ใส่ stack จริงทุก push (กฎ 10033 ตั้งเป็น FAIL) |
| V13.4.4 | 2 | Verify that using the HTTP TRACE method is not supported in production environments, to avoid potential information leakage. | ผ่าน | TRACE ได้ 405 เพราะไม่มี route ไหนประกาศเมธอดนี้ — `app/routes.py` · `app/auth.py` · `app/admin/users.py` (ทุก route ระบุ methods ที่รับไว้ชัด) |
| V13.4.5 | 2 | Verify that documentation (such as for internal APIs) and monitoring endpoints are not exposed unless explicitly intended. | ผ่าน | /metrics ต้องมี token เสมอ ไม่มีโหมดสาธารณะ (`ADR 0031` · `tests/test_metrics.py`) · สัญญา API เปิดสาธารณะ**โดยตั้งใจและประกาศไว้** ใน PUBLIC_PATHS ของ `tests/test_api_auth.py` ซึ่งเป็นรายการที่ต้องแก้อย่างจงใจถ้าจะเพิ่ม |

## V14 — Data Protection

### V14.1 Data Protection Documentation

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V14.1.1 | 2 | Verify that all sensitive data created and processed by the application has been identified and classified into protection levels. This includes data that is only encoded and therefore easily decoded, such as Base64 strings or the plaintext payload inside a JWT. Protection levels need to take into account any data protection and privacy regulations and standards which the application is required to comply with. | ผ่าน | ทุกคอลัมน์ถูกจำแนกชั้นและมีเทสต์บังคับว่าคอลัมน์ใหม่ต้องถูกจัดชั้นด้วย — `docs/DATA-CLASSIFICATION.md` · `tests/test_data_classification.py::test_every_column_is_classified` |
| V14.1.2 | 2 | Verify that all sensitive data protection levels have a documented set of protection requirements. This must include (but not be limited to) requirements related to general encryption, integrity verification, retention, how the data is to be logged, access controls around sensitive data in logs, database-level encryption, privacy and privacy-enhancing technologies to be used, and other confidentiality requirements. | ผ่าน | แต่ละชั้นมีข้อกำหนดของตัวเองครบ (เข้ารหัส/ความสมบูรณ์/ระยะเก็บ/ลง log ได้แค่ไหน) — `docs/DATA-CLASSIFICATION.md` · `ADR 0014` · `tests/test_data_classification.py::test_every_secret_was_explicitly_reviewed` |

### V14.2 General Data Protection

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V14.2.1 | 1 | Verify that sensitive data is only sent to the server in the HTTP message body or header fields, and that the URL and query string do not contain sensitive information, such as an API key or session token. | ผ่าน | **ห้ามมีความลับใน URL เด็ดขาด** เพราะ path ลง log ทุกบรรทัด — QR ของ MFA จึงเป็นไฟล์ที่ path ไม่มีความลับ ไม่ใช่ data URI · `ADR 0024` · `tests/test_totp.py::test_the_qr_url_never_carries_the_secret` · PAT ส่งทาง header เท่านั้น (`tests/test_api_auth.py`) · `ci:dast` ยิง ZAP ใส่ stack จริงทุก push (กฎ 10024 ตั้งเป็น FAIL) |
| V14.2.2 | 2 | Verify that the application prevents sensitive data from being cached in server components, such as load balancers and application caches, or ensures that the data is securely purged after use. | ผ่าน | cache ที่มีเก็บแต่ตัวนับโควตา ไม่ได้เก็บข้อมูลของผู้ใช้ — `app/cache.py` · `tests/test_cache.py` |
| V14.2.3 | 2 | Verify that defined sensitive data is not sent to untrusted parties (e.g., user trackers) to prevent unwanted collection of data outside of the application's control. | ผ่าน | ไม่มี tracker หรือปลายทางภายนอกในหน้าเว็บเลย และ CSP เป็น 'self' ล้วนซึ่งบล็อกการเพิ่มทีหลังด้วย — `ADR 0010` · `tests/test_security_headers.py` |
| V14.2.4 | 2 | Verify that controls around sensitive data related to encryption, integrity verification, retention, how the data is to be logged, access controls around sensitive data in logs, privacy and privacy-enhancing technologies, are implemented as defined in the documentation for the specific data's protection level. | ผ่าน | audit ปิดบังค่าตามชั้นจริง (`tests/test_audit.py::test_editing_a_task_records_only_what_changed`) · ระยะเก็บบังคับด้วย flask purge-expired ที่มี timer จริง (`ci:purge-timer`) · log ไม่มีชื่อจริง (`tests/test_logging.py::test_log_uses_username_not_real_name`) |

### V14.3 Client-side Data Protection

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V14.3.1 | 1 | Verify that authenticated data is cleared from client storage, such as the browser DOM, after the client or session is terminated. The 'Clear-Site-Data' HTTP response header field may be able to help with this but the client-side should also be able to clear up if the server connection is not available when the session is terminated. | ผ่าน | ไม่เก็บอะไรไว้ฝั่ง client เลยนอกจากคุกกี้ session — `app/static/app.js` ไม่แตะ localStorage/sessionStorage/IndexedDB และ logout ล้างคุกกี้ทิ้ง (`tests/test_session_security.py::test_logout_leaves_nothing_behind`) |
| V14.3.2 | 2 | Verify that the application sets sufficient anti-caching HTTP response header fields (i.e., Cache-Control: no-store) so that sensitive data is not cached in browsers. | ยังไม่ผ่าน | ตั้ง no-store เฉพาะหน้าที่แสดงความลับครั้งเดียว (QR ของ MFA และตอนออก token — `tests/test_totp.py::test_the_qr_is_not_cached_anywhere`) แต่ **หน้าที่มีข้อมูลส่วนตัวของผู้ใช้ทั่วไปยังไม่ได้ตั้ง** ปุ่มย้อนกลับหลัง logout จึงยังเห็นหน้าที่แคชไว้ได้ |
| V14.3.3 | 2 | Verify that data stored in browser storage (such as localStorage, sessionStorage, IndexedDB, or cookies) does not contain sensitive data, with the exception of session tokens. | ผ่าน | ไม่มีอะไรถูกเก็บใน browser storage เลย — มีแต่คุกกี้ session ซึ่งเป็นข้อยกเว้นที่ข้อนี้อนุญาต · `app/static/app.js` |

## V15 — Secure Coding and Architecture

### V15.1 Secure Coding and Architecture Documentation

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V15.1.1 | 1 | Verify that application documentation defines risk based remediation time frames for 3rd party component versions with vulnerabilities and for updating libraries in general, to minimize the risk from these components. | ผ่าน | critical 7 วัน · high 30 · medium 90 · low รอบถัดไป นับจาก**วันที่รู้** ไม่ใช่วันที่ CVE ออก — `docs/SECURITY-CADENCE.md` · advisory ที่ไม่ให้คะแนนถือเป็น high ไว้ก่อน · ไลบรารีของ plugin มีทางออกที่เร็วกว่ารอ patch เสมอคือถอดทิ้ง (`ADR 0025`) |
| V15.1.2 | 2 | Verify that an inventory catalog, such as software bill of materials (SBOM), is maintained of all third-party libraries in use, including verifying that components come from pre-defined, trusted, and continually maintained repositories. | ผ่าน | SBOM ออกทุก push และแยกตาม category ของ plugin — `ci:sbom` · `ci:plugin-audit` · ทุกไลบรารีมาจาก PyPI ผ่าน `Pipfile.lock` ที่ตรึง hash ไว้ |
| V15.1.3 | 2 | Verify that the application documentation identifies functionality which is time-consuming or resource-demanding. This must include how to prevent a loss of availability due to overusing this functionality and how to avoid a situation where building a response takes longer than the consumer's timeout. Potential defenses may include asynchronous processing, using queues, and limiting parallel processes per user and per application. | ยังไม่ผ่าน | รู้แล้วว่าคอขวดอยู่ที่ไหนและวัดไว้เป็นตัวเลข (`docs/PERFORMANCE.md` · `ADR 0031`) แต่ **ยังไม่ได้เขียนว่าจะกันการใช้งานเกินตัวอย่างไร** เช่นเพดานของคำขอที่แพง หรือ timeout ที่สัมพันธ์กับของ client |

### V15.2 Security Architecture and Dependencies

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V15.2.1 | 1 | Verify that the application only contains components which have not breached the documented update and remediation time frames. | ผ่าน | มีทั้งกรอบเวลาที่ประกาศแล้ว (`docs/SECURITY-CADENCE.md`) และตัวตรวจที่ทำให้ pipeline แดงจริงสำหรับ core — `ci:security` · ของ plugin อยู่ที่ `ci:plugin-audit` ซึ่งเตือนแทนที่จะบล็อกโดยตั้งใจ |
| V15.2.2 | 2 | Verify that the application has implemented defenses against loss of availability due to functionality which is time-consuming or resource-demanding, based on the documented security decisions and strategies for this. | ยังไม่ผ่าน | ผูกกับ V15.1.3 — มีโควตาที่หน้า login และที่ /api/v1 แล้ว แต่ยังไม่มีการตัดสินใจที่บันทึกไว้ว่าฟังก์ชันไหนแพงและจะกันอย่างไร |
| V15.2.3 | 2 | Verify that the production environment only includes functionality that is required for the application to function, and does not expose extraneous functionality such as test code, sample snippets, and development functionality. | ผ่าน | image เป็น multi-stage และไม่มีโค้ดเทสต์หรือของสำหรับ dev อยู่ข้างใน · ไลบรารีของ plugin ก็ไม่อยู่ใน image โดยตั้งใจ (`ADR 0025`) — `Dockerfile` · `.dockerignore` · `ci:image` |

### V15.3 Defensive Coding

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V15.3.1 | 1 | Verify that the application only returns the required subset of fields from a data object. For example, it should not return an entire data object, as some individual fields should not be accessible to users. | ผ่าน | คำตอบถูกประกอบจาก schema ที่ประกาศฟิลด์ไว้ชัด ไม่ใช่การคาย object ทั้งก้อน — `app/api/schemas.py` · `ADR 0018` · password_hash ห้ามออกจากระบบทุกกรณีแม้แต่ในรูป hash (`docs/DATA-CLASSIFICATION.md`) |
| V15.3.2 | 2 | Verify that where the application backend makes calls to external URLs, it is configured to not follow redirects unless it is intended functionality. | ยังไม่ผ่าน | urllib **ตาม redirect ให้เองโดยปริยาย** และการตรวจ scheme เกิดเฉพาะกับ URL ตัวแรกเท่านั้น — IdP ที่ถูกยึดจึงพาเราไปปลายทางอื่นได้หลังผ่านด่านไปแล้ว (`app/plugins/auth/oidc/factor.py`) |
| V15.3.3 | 2 | Verify that the application has countermeasures to protect against mass assignment attacks by limiting allowed fields per controller and action, e.g., it is not possible to insert or update a field value when it was not intended to be part of that action. | ผ่าน | update_todo() รับเฉพาะฟิลด์ที่ประกาศและปฏิเสธชื่อที่ไม่รู้จัก ส่วนฝั่ง API ตั้ง unknown=RAISE ทั้ง body และ query — `ADR 0016` · `ADR 0018` · `tests/test_api_fuzz.py` |
| V15.3.4 | 2 | Verify that all proxying and middleware components transfer the user's original IP address correctly using trusted data fields that cannot be manipulated by the end user, and the application and web server use this correct value for logging and security decisions such as rate limiting, taking into account that even the original IP address may not be reliable due to dynamic IPs, VPNs, or corporate firewalls. | ผ่าน | IP ที่ใช้ทั้งใน log และในการนับโควตามาจากจำนวนชั้น proxy ที่ประกาศไว้ ค่าเริ่มต้นคือไม่เชื่อเลย — `ADR 0027` · `tests/test_proxy.py` |
| V15.3.5 | 2 | Verify that the application explicitly ensures that variables are of the correct type and performs strict equality and comparator operations. This is to avoid type juggling or type confusion vulnerabilities caused by the application code making an assumption about a variable type. | ผ่าน | โมเดลเป็น typed ทั้งหมด (Mapped[]) และ mypy รันแบบ strict ใน `ci:lint` · การเทียบความลับใช้ hmac.compare_digest ไม่ใช่ == (`app/services/tokens.py`) |
| V15.3.6 | 2 | Verify that JavaScript code is written in a way that prevents prototype pollution, for example, by using Set() or Map() instead of object literals. | ผ่าน | `app/static/app.js` ไม่รวม object จากภายนอกเข้าด้วยกันและไม่แตะ prototype — อ่านค่าจาก data-* attribute เป็นสตริงล้วน (`tests/test_security_headers.py::test_behaviour_uses_data_attributes`) |
| V15.3.7 | 2 | Verify that the application has defenses against HTTP parameter pollution attacks, particularly if the application framework makes no distinction about the source of request parameters (query string, body parameters, cookies, or header fields). | ผ่าน | Flask แยกแหล่งของพารามิเตอร์ออกจากกันชัด (args/form/cookies/headers) และโค้ดอ่านจากแหล่งที่ตั้งใจเสมอ · ชื่อพารามิเตอร์ที่ไม่รู้จักฝั่ง API ถูกปฏิเสธด้วย 422 (`ADR 0018`) |

## V16 — Security Logging and Error Handling

### V16.1 Security Logging Documentation

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V16.1.1 | 2 | Verify that an inventory exists documenting the logging performed at each layer of the application's technology stack, what events are being logged, log formats, where that logging is stored, how it is used, how access to it is controlled, and for how long logs are kept. | ผ่าน | บัญชีรายการของ log อยู่ใน `docs/ROPA.md` ข้อ 3 — บอกครบว่าชั้นไหนเขียนอะไร รูปแบบไหน ไปที่ไหน ใครอ่านได้ และเก็บนานเท่าไร · `tests/test_ropa.py::test_the_log_inventory_answers_the_four_questions` บังคับว่าตอบครบทั้งสี่คำถาม และบังคับให้เขียนปลายทาง**จริง** (stdout) ไม่ใช่ปลายทางที่ตั้งใจจะมี |

### V16.2 General Logging

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V16.2.1 | 2 | Verify that each log entry includes necessary metadata (such as when, where, who, what) that would allow for a detailed investigation of the timeline when an event happens. | ผ่าน | `app/logging_setup.py` · `tests/test_logging.py::test_log_has_the_agreed_fields` · `tests/test_logging.py::test_log_records_the_status_and_path` · `ADR 0011` |
| V16.2.2 | 2 | Verify that time sources for all logging components are synchronized, and that timestamps in security event metadata use UTC or include an explicit time zone offset. UTC is recommended to ensure consistency across distributed systems and to prevent confusion during daylight saving time transitions. | ผ่าน | UTC เสมอพร้อมตัว "Z" ท้ายสตริง ไม่ขึ้นกับโซนของเครื่องที่รัน — `tests/test_logging.py::test_timestamp_is_utc_not_local_time` |
| V16.2.3 | 2 | Verify that the application only stores or broadcasts logs to the files and services that are documented in the log inventory. | ผ่าน | ปลายทางเดียวคือ stdout และมันถูกประกาศไว้ในบัญชีรายการแล้ว — `docs/ROPA.md` · `app/logging_setup.py` · `tests/test_ropa.py::test_the_log_inventory_answers_the_four_questions` |
| V16.2.4 | 2 | Verify that logs can be read and correlated by the log processor that is in use, preferably by using a common logging format. | ผ่าน | JSON บรรทัดละ event + request_id ที่ correlate ได้ — `ADR 0011` · `tests/test_logging.py::test_log_line_is_valid_json` · `tests/test_logging.py::test_log_id_matches_response_header` |
| V16.2.5 | 2 | Verify that when logging sensitive data, the application enforces logging based on the data's protection level. For example, it may not be allowed to log certain data, such as credentials or payment details. Other data, such as session tokens, may only be logged by being hashed or masked, either in full or partially. | ผ่าน | ชั้นข้อมูลตัดสินว่าอะไรลง log ได้ — `docs/DATA-CLASSIFICATION.md` · `ADR 0014` · `tests/test_logging.py::test_log_uses_username_not_real_name` (ชื่อจริงห้ามหลุด, actor เก็บ username) |

### V16.3 Security Events

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V16.3.1 | 2 | Verify that all authentication operations are logged, including successful and unsuccessful attempts. Additional metadata, such as the type of authentication or factors used, should also be collected. | ผ่าน | ทั้งสำเร็จและล้มเหลว รวมขั้นที่สองและ SSO — `app/auth.py` · `tests/test_audit.py::test_login_and_logout_are_audited` · `tests/test_audit.py::test_failed_login_is_audited` |
| V16.3.2 | 2 | Verify that failed authorization attempts are logged. For L3, this must include logging all authorization decisions, including logging when sensitive data is accessed (without logging the sensitive data itself). | ยังไม่ผ่าน | 403 ของบทบาท (`ADR 0022`) และ 404 ของความเป็นเจ้าของ (`ADR 0004`) ตอบถูกแล้วแต่ **ไม่ถูกบันทึกเป็นเหตุการณ์** — คนที่ไล่ยิง id ของคนอื่นจึงไม่ทิ้งร่องรอยที่ค้นได้ |
| V16.3.3 | 2 | Verify that the application logs the security events that are defined in the documentation and also logs attempts to bypass the security controls, such as input validation, business logic, and anti-automation. | ยังไม่ผ่าน | การชนโควตา (429) และ CSRF ที่ถูกปฏิเสธ (400) ไม่ถูกบันทึกแยกเป็นเหตุการณ์ความปลอดภัย — และยังไม่มีเอกสารที่ประกาศว่า "เหตุการณ์ความปลอดภัย" ของระบบนี้มีอะไรบ้าง |
| V16.3.4 | 2 | Verify that the application logs unexpected errors and security control failures such as backend TLS failures. | ผ่าน | traceback ลง log พร้อม request_id — `app/logging_setup.py` · `tests/test_logging.py::test_exception_is_serialised` |

### V16.4 Log Protection

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V16.4.1 | 2 | Verify that all logging components appropriately encode data to prevent log injection. | ผ่าน | ทุกบรรทัดผ่าน json.dumps จึง escape ให้เอง และ header X-Request-Id ที่รับจากภายนอกถูกทิ้งถ้าไม่ใช่ UUID — `tests/test_logging.py::test_bogus_incoming_id_is_replaced` · `tests/test_logging.py::test_log_line_is_valid_json` |
| V16.4.2 | 2 | Verify that logs are protected from unauthorized access and cannot be modified. | ยังไม่ผ่าน | log ที่ส่งออกไปแล้วแก้ที่ต้นทางไม่ได้ (`ADR 0037`) และสาย audit แก้ไม่ได้จริง (`ADR 0015`) — แต่ Loki เองยังรันอยู่บนเครื่องเดียวกับแอป คนที่ยึดเครื่องได้จึงยังลบของทั้งสองที่ได้ |
| V16.4.3 | 2 | Verify that logs are securely transmitted to a logically separate system for analysis, detection, alerting, and escalation. The aim is to ensure that if the application is breached, the logs are not compromised. | ผ่าน | log ถูกส่งไปเก็บที่ Loki ซึ่งเป็น service แยกจากแอป — `compose.siem.yaml` · `deploy/alloy.river` · `ADR 0037` · `ci:siem` ยิงจริงทุก push และต้องเห็น alert **ดังจริง** ไม่ใช่แค่ stack ขึ้นได้ · **ข้อจำกัดที่เปิดเผยไว้: ยังอยู่บนเครื่องเดียวกัน** เครื่องที่ถูกยึดทั้งเครื่องยังเข้าถึงทั้งสองอย่างได้ |

### V16.5 Error Handling

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V16.5.1 | 2 | Verify that a generic message is returned to the consumer when an unexpected or security-sensitive error occurs, ensuring no exposure of sensitive internal system data such as stack traces, queries, secret keys, and tokens. | ผ่าน | HTML ใช้หน้า error มาตรฐานของ Flask (ไม่มี traceback เมื่อ debug ปิด) ส่วน API ตอบซองเดียวรูปเดียว — `app/api/errors.py` · `ADR 0018` · `tests/test_api_fuzz.py` · `ci:dast` ยิง ZAP ใส่ stack จริงทุก push (กฎ 90022 กับ 10023 ตั้งเป็น FAIL) |
| V16.5.2 | 2 | Verify that the application continues to operate securely when external resource access fails, for example, by using patterns such as circuit breakers or graceful degradation. | ผ่าน | แหล่งความลับที่ถามไม่ได้ = ไม่ start (fail-closed ตั้งใจ ไม่ใช่เดินต่อด้วยค่าเก่า) — `ADR 0030` · `tests/test_secrets.py::test_vault_that_cannot_be_read_refuses_to_start` · cache ที่ไม่มีตกกลับเป็น no-op `app/cache.py` |
| V16.5.3 | 2 | Verify that the application fails gracefully and securely, including when an exception occurs, preventing fail-open conditions such as processing a transaction despite errors resulting from validation logic. | ผ่าน | ความล้มเหลวสื่อสารด้วย exception จาก service ไม่ใช่ค่าคืนที่ผู้เรียกอาจลืมเช็ค — `ADR 0016` · `app/services/errors.py` · `tests/test_service_layer.py` |

## V17 — WebRTC

### V17.1 TURN Server

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V17.1.1 | 2 | Verify that the Traversal Using Relays around NAT (TURN) service only allows access to IP addresses that are not reserved for special purposes (e.g., internal networks, broadcast, loopback). Note that this applies to both IPv4 and IPv6 addresses. | ไม่เกี่ยวข้อง | ไม่มี WebRTC ในระบบ — ไม่มี TURN, media server หรือ signaling server |

### V17.2 Media

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V17.2.1 | 2 | Verify that the key for the Datagram Transport Layer Security (DTLS) certificate is managed and protected based on the documented policy for management of cryptographic keys. | ไม่เกี่ยวข้อง | ไม่มี WebRTC ในระบบ |
| V17.2.2 | 2 | Verify that the media server is configured to use and support approved Datagram Transport Layer Security (DTLS) cipher suites and a secure protection profile for the DTLS Extension for establishing keys for the Secure Real-time Transport Protocol (DTLS-SRTP). | ไม่เกี่ยวข้อง | ไม่มี WebRTC ในระบบ |
| V17.2.3 | 2 | Verify that Secure Real-time Transport Protocol (SRTP) authentication is checked at the media server to prevent Real-time Transport Protocol (RTP) injection attacks from leading to either a Denial of Service condition or audio or video media insertion into media streams. | ไม่เกี่ยวข้อง | ไม่มี WebRTC ในระบบ |
| V17.2.4 | 2 | Verify that the media server is able to continue processing incoming media traffic when encountering malformed Secure Real-time Transport Protocol (SRTP) packets. | ไม่เกี่ยวข้อง | ไม่มี WebRTC ในระบบ |

### V17.3 Signaling

| ข้อ | L | ข้อกำหนด | สถานะ | หลักฐาน / เหตุผล |
|---|---|---|---|---|
| V17.3.1 | 2 | Verify that the signaling server is able to continue processing legitimate incoming signaling messages during a flood attack. This should be achieved by implementing rate limiting at the signaling level. | ไม่เกี่ยวข้อง | ไม่มี WebRTC ในระบบ |
| V17.3.2 | 2 | Verify that the signaling server is able to continue processing legitimate signaling messages when encountering malformed signaling message that could cause a denial of service condition. This could include implementing input validation, safely handling integer overflows, preventing buffer overflows, and employing other robust error-handling techniques. | ไม่เกี่ยวข้อง | ไม่มี WebRTC ในระบบ |
