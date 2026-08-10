# image ของแอป — multi-stage, ไม่รันเป็น root (Phase 5 · P5-09)
#
# **สองชั้นเพราะเครื่องมือ build ไม่ควรอยู่ใน image ที่รันจริง** — pipenv, หัว
# compiler และ cache ของ pip เป็นพื้นที่โจมตีที่ไม่มีใครต้องการตอน runtime
# ชั้นสุดท้ายได้แค่ python + venv ที่ติดตั้งแล้ว + โค้ดของแอป
#
# **ไม่รัน `flask db upgrade` ให้เอง** โดยตั้งใจ — การเปลี่ยน schema เป็นการ
# ตัดสินใจของผู้ดูแล ไม่ใช่ผลข้างเคียงของการ start container การ upgrade อัตโนมัติ
# แปลว่า deploy ที่ rollback แล้วจะเจอฐานข้อมูลที่ล้ำหน้าโค้ดอยู่ และการ start
# หลาย replica พร้อมกันจะแย่งกัน migrate (ดู docs/OPERATIONS.md)

# ---------------------------------------------------------------- ชั้น build
FROM python:3.13-slim AS builder

# ไม่เขียน .pyc และไม่ buffer stdout/stderr — log ต้องออกทันทีไม่ใช่ตอน buffer เต็ม
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN pip install --no-cache-dir pipenv

# คัดลอกแค่ไฟล์ล็อกก่อน — ชั้นนี้จะถูก cache ไว้ตราบใดที่ dependency ไม่เปลี่ยน
# (คัดลอกโค้ดมาก่อนแปลว่าแก้โค้ดหนึ่งบรรทัดแล้วต้องติดตั้ง dependency ใหม่ทั้งหมด)
COPY Pipfile Pipfile.lock ./

# `--deploy` ล้มทันทีถ้า Pipfile.lock ไม่ตรงกับ Pipfile — image ที่ build จาก
# lock ที่ล้าสมัยคือ image ที่ไม่มีใครรู้ว่าข้างในมีอะไร
# **ติดตั้งเฉพาะ category ที่ image ต้องใช้**: core + `deploy` (gunicorn)
# ไลบรารีของ plugin ไม่ได้ติดตั้งที่นี่ตามหลักของ ADR 0025 — ใครใช้ยี่ห้อไหน
# ค่อยต่อ image ตัวนี้แล้ว sync category ของตัวเองเพิ่ม
ENV PIPENV_VENV_IN_PROJECT=1
RUN pipenv sync --deploy --categories="packages deploy"

# ---------------------------------------------------------------- ชั้นที่รันจริง
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# **ผู้ใช้ที่ไม่ใช่ root และไม่มี shell** — process ที่ถูกยึดจะไม่ได้สิทธิ์เขียน
# ทับโค้ดของตัวเอง และ `--no-create-home` เพราะ container นี้ไม่มีอะไรต้องเก็บ
# ในบ้านของผู้ใช้ (ข้อมูลอยู่ในฐานข้อมูล ไม่ใช่ในไฟล์ระบบ)
RUN useradd --system --no-create-home --shell /usr/sbin/nologin --uid 10001 todolist

WORKDIR /app

COPY --from=builder /build/.venv /app/.venv
# คัดลอกเฉพาะของที่ runtime ต้องใช้ — ส่วนที่เหลือถูกกันไว้ด้วย .dockerignore
COPY app ./app
COPY migrations ./migrations
COPY config.py run.py ./

# โค้ดเป็นของ root และ process รันเป็น todolist — **เขียนทับตัวเองไม่ได้**
RUN chown -R root:root /app && chmod -R a-w /app

USER todolist
EXPOSE 8000

# healthcheck ยิงหน้า login เพราะเป็นหน้าเดียวที่ตอบได้โดยไม่ต้อง login
# และการที่มันตอบ 200 แปลว่า config ผ่าน, ต่อฐานข้อมูลได้, template render ได้
# (endpoint `/healthz` แยกจะบอกน้อยกว่านี้ — มันตอบ 200 ได้แม้ฐานข้อมูลล่ม)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/login').read()"

# `--access-logfile -` ส่ง access log ออก stdout ส่วน log ของแอปออก stderr
# (ADR 0011 หมายเหตุท้ายไฟล์) runtime เก็บทั้งสองช่อง
# จำนวน worker ตั้งจากภายนอกด้วย `GUNICORN_CMD_ARGS` หรือ `WEB_CONCURRENCY`
# **รันหลาย worker แล้วต้องตั้ง `CACHE_URL` ให้ชี้ store ที่แชร์ได้ด้วย**
# ไม่งั้นเพดาน rate limit จะเป็น N เท่า (แอปเตือนตอน start — ดู app/cache.py)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "run:app"]
