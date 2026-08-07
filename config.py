import os

# คีย์ที่สั้นกว่านี้เดาได้เร็วเกินไป — session และ CSRF token เซ็นด้วยคีย์นี้ทั้งคู่
MIN_SECRET_KEY_LENGTH = 32

# ภาษาที่รองรับ: รหัส -> ชื่อที่แสดงในตัวเลือกภาษา (เขียนด้วยภาษานั้นเอง)
# เพิ่มภาษาใหม่ = เพิ่มบรรทัดที่นี่ แล้ว `pybabel init -l <รหัส>`
LANGUAGES = {
    "en": "English",
    "th": "ไทย",
}
DEFAULT_LANGUAGE = "en"

# ชุดสีมาจากการค้นหา plugin ไม่ได้ประกาศไว้ที่นี่ (ดู app/plugins/)
# core จึงไม่รู้จักธีมตัวไหนเป็นการเฉพาะ เพิ่มธีม = วางไดเรกทอรี ไม่ต้องแก้ไฟล์นี้


def _parse_picks(raw):
    """แปลง `a#b=c,d#e=f` เป็น dict — ค่าที่รูปแบบผิดถูกข้ามไปเงียบ ๆ

    ข้ามแทนที่จะพัง เพราะ config ที่พิมพ์ผิดหนึ่งตัวไม่ควรทำให้แอปไม่ start
    ผลของการข้ามคือความสามารถนั้นถูกปิด (fail closed) ซึ่งเห็นได้จาก log อยู่แล้ว
    """
    picks = {}
    for entry in raw.split(","):
        target, separator, choice = entry.partition("=")
        if separator and target.strip() and choice.strip():
            picks[target.strip()] = choice.strip()
    return picks


def _parse_keys(raw):
    """แปลง `a/b,c/d#e` เป็น frozenset ของคีย์ — ช่องว่างและรายการว่างถูกทิ้ง"""
    return frozenset(entry.strip() for entry in raw.split(",") if entry.strip())


class Config:
    # ไม่มีค่า default โดยตั้งใจ — ไม่ตั้งแล้วต้องแอปพังตั้งแต่ตอน start
    # ดีกว่าเผลอรันด้วยคีย์ที่ใคร ๆ ก็รู้
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///todolist.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # นับเฉพาะ login ที่ล้มเหลว ล็อกอินถูกไม่กินโควตา
    LOGIN_RATE_LIMIT = os.environ.get("LOGIN_RATE_LIMIT", "5 per minute; 20 per hour")
    # โควตาที่นับ **ต่อชื่อผู้ใช้** ไม่ใช่ต่อ IP — ปิดช่องคนที่เปลี่ยน IP ไปเรื่อย ๆ
    # ตั้งหลวมกว่าฝั่ง IP โดยตั้งใจ เพราะโควตานี้เป็นของ *เหยื่อ* ไม่ใช่ของคนยิง
    # (ดู app/auth.py และ ADR 0021 — หน้าต่างสั้นเพื่อจำกัดเวลาที่เจ้าของบัญชี
    # ตัวจริงถูกกันออกไปด้วย)
    LOGIN_USERNAME_RATE_LIMIT = os.environ.get(
        "LOGIN_USERNAME_RATE_LIMIT", "10 per 5 minutes; 60 per hour"
    )
    # --- cache (Phase 5 · ROADMAP ข้อ 4.3 — ดู app/cache.py) ---
    # **ค่าเริ่มต้นคือไม่มี cache จริง ๆ ไม่ใช่ dict ต่อ process** เพราะ cache ที่
    # ไม่แชร์กันทำให้คำขอเหมือนกันได้คำตอบต่างกันตาม worker ที่รับ ซึ่งจากภายนอก
    # แยกไม่ออกจากบั๊ก — cache ต้องเป็น optimization เท่านั้น ห้ามเป็น correctness
    # scheme ของค่านี้เป็นตัวเลือก plugin ชนิด `cache` (หลักเดียวกับ DATABASE_URL)
    CACHE_URL = os.environ.get("CACHE_URL", "memory://")

    # **ตามหลัง `CACHE_URL` โดยค่าเริ่มต้น** (P5-07) — ตั้ง store ที่แชร์ได้ครั้งเดียว
    # แล้วโควตา rate limit ย้ายตามเอง ไม่ต้องตั้งซ้ำและไม่มีทางลืมตั้งตัวใดตัวหนึ่ง
    #
    # หนี้ที่ปิดตรงนี้: เดิมค่าเริ่มต้นเป็น `memory://` ตายตัว ซึ่งนับ **แยกต่อ process**
    # วันที่ใครรันหลาย worker เพดานจริงจะกลายเป็น N เท่าของที่ตั้งไว้เงียบ ๆ —
    # ไม่มี error ไม่มี log มีแต่คนไล่เดารหัสผ่านที่ได้โควตามากกว่าที่เราคิด
    #
    # ตั้งแยกได้ถ้า**ตั้งใจ**ให้ counter อยู่คนละที่กับ cache (เช่นคนละ redis db
    # หรือ store ที่ limits รองรับแต่เราไม่มี cache plugin ให้) — `create_app`
    # จะเตือนตอน start ถ้ารู้ว่า store ที่เลือกไม่ได้แชร์ข้ามโปรเซส
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI") or CACHE_URL

    # โควตาของ `/api/v1` — **นับต่อ *ใบ token* ไม่ใช่ต่อ IP** (P5-08)
    # client ของ API เป็นเครื่อง ซึ่งมักออกเน็ตผ่าน IP เดียวกัน (NAT, egress ของ
    # cloud) การนับต่อ IP จึงทำให้ client ที่ยิงถี่ตัวเดียวกินโควตาของทุกคนที่อยู่
    # หลัง gateway เดียวกัน และคนที่มี IP เยอะก็เดินผ่านได้สบาย
    # คำขอที่ยังไม่ผ่านด่าน token ตกกลับไปนับต่อ IP เพื่อไม่ให้ยิงฟรีไม่จำกัด
    API_RATE_LIMIT = os.environ.get("API_RATE_LIMIT", "120 per minute; 2000 per hour")

    # **เปิด header ของโควตา** — `Retry-After` เป็นข้อบังคับของ RFC 9110 สำหรับ 429
    # ไม่มีแล้ว client ต้องเดาว่าจะกลับมาเมื่อไหร่ ซึ่งส่วนใหญ่แปลว่ายิงซ้ำทันที
    # ส่วน `X-RateLimit-*` ทำให้ client ชะลอตัวเองได้ *ก่อน* โดนกัน ซึ่งเป็นความ
    # ต่างระหว่าง client ที่ถอยเป็นกับ client ที่ยิงชนกำแพงแล้วยิงต่อ
    RATELIMIT_HEADERS_ENABLED = True

    # --- อายุของ session (Phase 4 — ดู app/session_security.py และ ADR 0020) ---
    # ค่าแรกคือ idle timeout สำหรับเครื่องที่ถูกทิ้งไว้
    # ค่าที่สองคือ absolute timeout ที่หมดอายุแม้จะใช้งานอยู่ตลอด
    SESSION_IDLE_MINUTES = int(os.environ.get("SESSION_IDLE_MINUTES", "30"))
    SESSION_ABSOLUTE_HOURS = int(os.environ.get("SESSION_ABSOLUTE_HOURS", "12"))
    # **ไม่มี `PERMANENT_SESSION_LIFETIME` โดยตั้งใจ** — คุกกี้ของแอปนี้เป็น
    # คุกกี้แบบจบเมื่อปิดเบราว์เซอร์ อายุจริงบังคับที่ server ทุก request
    # (ดูเหตุผลเต็มใน `app/session_security.py`)
    # อายุของสถานะ "ผ่านรหัสผ่านแล้วแต่ยังไม่ผ่านขั้นที่สอง" — สั้นโดยตั้งใจ
    # เพราะมันคือครึ่งทางของการยืนยันตัวตน (ADR 0024)
    MFA_PENDING_SECONDS = int(os.environ.get("MFA_PENDING_SECONDS", "300"))

    # --- ตัวเลือกของ plugin (Phase 4.5 — ADR 0025) ---
    # ความสามารถที่มีส่วนเสริมให้เลือกหลายตัว ต้องระบุว่าจะใช้ตัวไหน ไม่งั้นปิดทั้งหมด
    # รูปแบบคือรายการที่คั่นด้วยจุลภาค แต่ละตัวเขียนว่า
    # ชนิด/ไอดี ตามด้วย # ความสามารถ ตามด้วยเครื่องหมายเท่ากับ แล้วไอดีของส่วนเสริม
    PLUGIN_PICKS = _parse_picks(os.environ.get("PLUGIN_PICKS", ""))
    # สวิตช์ปิดจุด plug ตอน runtime — คั่นด้วยจุลภาค ใช้คีย์เดียวกับ `flask plugin-list`
    # (`themes/ocean`, `auth/totp`, `auth/totp#qr-segno`) ปิดของ core ไม่ได้
    # มีไว้สำหรับวันที่ CVE ของไลบรารีใน plugin ออกตอนบ่ายสาม: ปิดได้ทันทีโดยไม่ต้อง
    # แก้โค้ด ไม่ต้องรอ deploy และไม่ต้องลบข้อมูลของ plugin ทิ้ง
    DISABLED_PLUGINS = _parse_keys(os.environ.get("DISABLED_PLUGINS", ""))

    LANGUAGES = LANGUAGES
    BABEL_DEFAULT_LOCALE = DEFAULT_LANGUAGE
    BABEL_DEFAULT_TIMEZONE = os.environ.get("BABEL_DEFAULT_TIMEZONE", "Asia/Bangkok")

    # เปิดพร้อมกันเมื่อมี TLS จริงหน้า reverse proxy (Phase 5):
    # บังคับ https, HSTS, และ cookie flag Secure
    # เปิดตอนยังรัน http อยู่จะ redirect วนจน login ไม่ได้
    HTTPS_ENABLED = os.environ.get("HTTPS_ENABLED", "") == "1"
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

    # --- OpenAPI / API v1 (ดู app/api/__init__.py และ ADR 0018) ---
    # ตัวเลขนี้เป็นเวอร์ชันของ **เอกสาร** ไม่ใช่ของสัญญา — สัญญาอยู่ที่ path
    # `/api/v1` ซึ่งเปลี่ยนได้ทางเดียวคือขึ้น v2 ใหม่ทั้งชุด
    API_TITLE = "Todolist API"
    API_VERSION = "1.0.0"
    OPENAPI_VERSION = "3.1.0"
    # เสิร์ฟแค่ตัว JSON ไม่มี Swagger UI — UI โหลดของจาก CDN ซึ่ง CSP บล็อกอยู่แล้ว
    OPENAPI_URL_PREFIX = "/api/v1"
    OPENAPI_JSON_PATH = "openapi.json"

    # กุญแจปิดบังค่าของชั้น C2/C3 ใน audit (ดู app/audit.py)
    # ไม่ตั้งก็ได้ — จะแยกสายมาจาก SECRET_KEY ให้เอง แต่ตั้งแยกจะดีกว่าเพราะ
    # เปลี่ยน SECRET_KEY ทีหลังแล้วยังเทียบค่าเก่าใน audit ได้อยู่
    AUDIT_HMAC_KEY = os.environ.get("AUDIT_HMAC_KEY")


def check_secret_key(secret_key):
    """ตรวจ SECRET_KEY ตอนสร้างแอป ไม่ใช่ตอน import config
    (ถ้า raise ตอน import จะพังแม้แต่ config ที่ตั้งคีย์เองอย่างในเทสต์)"""
    if not secret_key:
        raise RuntimeError(
            "ยังไม่ได้ตั้ง SECRET_KEY — ใส่ลงไฟล์ .env ก่อน (ดูตัวอย่างใน .env.example)\n"
            "สร้างคีย์ใหม่: "
            "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )
    if len(secret_key) < MIN_SECRET_KEY_LENGTH:
        raise RuntimeError(
            f"SECRET_KEY สั้นเกินไป ({len(secret_key)} ตัว) ต้องยาวอย่างน้อย {MIN_SECRET_KEY_LENGTH} ตัว"
        )
