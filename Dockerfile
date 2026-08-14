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

# **base image ถูก pin ด้วย digest ไม่ใช่แค่ tag** (2026-08-13)
#
# `python:3.13-slim` เป็น tag ที่ถูกย้ายทับได้ตลอด — สอง build ที่ห่างกันหนึ่ง
# ชั่วโมงจึงได้ base คนละตัวโดยไม่มีอะไรในไฟล์นี้เปลี่ยน ซึ่งแปลว่า image ที่
# ทดสอบผ่านกับ image ที่ deploy ไม่จำเป็นต้องเป็นตัวเดียวกัน
#
# **ราคาที่จ่ายและวิธีที่จ่ายไปแล้ว**: pin แล้ว security patch ของ base จะไม่มา
# เองอีก — ซึ่งจะแย่กว่าเดิมถ้าไม่มีใครขยับ · จึงเปิด `package-ecosystem: docker`
# ใน `.github/dependabot.yml` ให้มันเปิด PR ขยับ digest ให้ patch ยังมาเหมือนเดิม
# **แค่มาเป็น PR ที่มีคนเห็นและผ่าน check ทุกด่าน แทนที่จะมาเงียบ ๆ ตอน build**
#
# digest นี้เป็นของ **manifest index (multi-arch)** ไม่ใช่ของ image ต่อสถาปัตยกรรม
# — pin ผิดตัวจะล็อก build ไว้ที่ arch เดียวโดยไม่มี error ให้เห็นจนกว่าจะ build
# บนเครื่องคนละ arch · ทั้งสองชั้นต้องเป็น digest เดียวกัน (`tests/test_dockerfile_pinning.py`)
#
# ---------------------------------------------------------------- ชั้น build
FROM python:3.13-slim@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a AS builder

# ไม่เขียน .pyc และไม่ buffer stdout/stderr — log ต้องออกทันทีไม่ใช่ตอน buffer เต็ม
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# **ต้องเป็น path เดียวกับชั้นที่รันจริง** (`/app`) ไม่ใช่ `/build` — script ใน venv
# มี shebang เป็น path เต็มของ python ตอนที่ venv ถูกสร้าง ย้าย venv ไปที่อื่นแล้ว
# shebang ยังชี้ที่เดิมซึ่งไม่มีอยู่ในชั้นสุดท้าย ผลคือ container ตายตอน start ด้วย
# `exec /app/.venv/bin/gunicorn: no such file or directory` — **ข้อความนี้หลอก**
# ไฟล์นั้นมีอยู่จริง สิ่งที่หายคือ *interpreter* ที่ shebang ชี้ไป (เจอจริงใน CI)
WORKDIR /app

# **pipenv ก็ถูกตรึงด้วย hash เหมือนกัน** (ดู `pins/README.md`) — image ที่ base
# ถูก pin ด้วย digest แต่ยังหยิบ pipenv รุ่นล่าสุดมาสร้าง venv คือ image ที่
# reproducible ครึ่งเดียว · `--require-hashes` ยังปฏิเสธด้วยถ้ามี dependency
# ตัวไหนไม่ได้ถูกระบุไว้ ล็อกที่ครอบไม่ครบจึงพังตอน build ไม่ใช่ตอน deploy
COPY pins/pipenv/requirements.txt pins/pipenv/
RUN pip install --no-cache-dir --require-hashes -r pins/pipenv/requirements.txt

# คัดลอกแค่ไฟล์ล็อกก่อน — ชั้นนี้จะถูก cache ไว้ตราบใดที่ dependency ไม่เปลี่ยน
# (คัดลอกโค้ดมาก่อนแปลว่าแก้โค้ดหนึ่งบรรทัดแล้วต้องติดตั้ง dependency ใหม่ทั้งหมด)
COPY Pipfile Pipfile.lock ./

# **สองคำสั่งเพราะเป็นคนละคำถาม** — `verify` ตอบว่า Pipfile.lock ยังตรงกับ Pipfile
# ไหม ส่วน `sync` ติดตั้งตามล็อกเป๊ะ ๆ (`pipenv sync` ไม่มี flag `--deploy` ให้ใช้
# ซึ่งเป็นของ `install` — เคยเขียนผิดแล้ว build พังตั้งแต่บรรทัดแรกของ job `image`)
# image ที่ build จาก lock ที่ล้าสมัยคือ image ที่ไม่มีใครรู้ว่าข้างในมีอะไร
#
# **ไลบรารีของ plugin เป็น opt-in ผ่าน build arg** (ADR 0025) — ค่าเริ่มต้นว่าง
# image พื้นฐานจึงไม่แบก supply chain ของยี่ห้อ/ส่วนเสริมที่คนส่วนใหญ่ไม่ได้ใช้
# ใครต้องการก็ส่งชื่อ category มา เช่น `--build-arg PLUGIN_CATEGORIES="plugin-cache-redis"`
# (compose ของ stack ส่งให้เองตามยี่ห้อที่เลือก — ดู compose.yaml)
#
# ทำไมต้องมี: backend ของ cache/db ที่ถูกเลือกจะ `import` ไลบรารีของมันตอนโหลด
# และ **ตั้งใจให้ ImportError ทำให้แอปไม่ start** เพราะผู้ดูแลตั้งใจชี้ config มาที่
# ยี่ห้อนั้น การเงียบแล้วไม่ใช้ให้คือการโกหก — image จึงต้องมีของที่ config เรียกหา
ARG PLUGIN_CATEGORIES=""
ENV PIPENV_VENV_IN_PROJECT=1
RUN pipenv verify && pipenv sync --categories="packages deploy ${PLUGIN_CATEGORIES}"

# ---------------------------------------------------------------- ชั้นที่รันจริง
FROM python:3.13-slim@sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# **ผู้ใช้ที่ไม่ใช่ root และไม่มี shell** — process ที่ถูกยึดจะไม่ได้สิทธิ์เขียน
# ทับโค้ดของตัวเอง และ `--no-create-home` เพราะ container นี้ไม่มีอะไรต้องเก็บ
# ในบ้านของผู้ใช้ (ข้อมูลอยู่ในฐานข้อมูล ไม่ใช่ในไฟล์ระบบ)
RUN useradd --system --no-create-home --shell /usr/sbin/nologin --uid 10001 todolist

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
# คัดลอกเฉพาะของที่ runtime ต้องใช้ — ส่วนที่เหลือถูกกันไว้ด้วย .dockerignore
COPY app ./app
COPY migrations ./migrations
COPY config.py run.py ./

# `create_app()` เรียก `mkdir(instance_path)` เสมอ ต้องมีไดเรกทอรีนี้อยู่ก่อน
# ไม่งั้น container พังตั้งแต่ start ด้วย PermissionError (เจอตอนทดสอบก่อน push)
# **สร้างแล้วปล่อยให้เขียนไม่ได้เหมือนที่อื่น** — `mkdir(exist_ok=True)` ผ่านได้
# โดยไม่ต้องมีสิทธิ์เขียน และการยอมให้เขียนได้จะเปิดทางให้ค่าเริ่มต้น
# `sqlite:///todolist.db` เก็บข้อมูลลง layer ของ container ซึ่ง **หายเงียบ ๆ
# ตอน restart** — พังดัง ๆ ตอนตั้ง config ผิด ดีกว่าข้อมูลหายโดยไม่มีใครรู้
RUN mkdir -p /app/instance

# **ที่เดียวที่เขียนได้ และอยู่นอก `/app`** — named volume ที่ถูก mount ทับตรงนี้
# จะรับสิทธิ์กับเจ้าของจากไดเรกทอรีใน image มาให้เอง ถ้าไม่สร้างไว้ก่อน docker
# จะสร้าง volume ที่เป็นของ root แล้ว process (uid 10001) เขียนไม่ได้
# — SQLite จะล้มด้วย "unable to open database file" ซึ่งอ่านแล้วนึกว่า path ผิด
RUN install -d -o todolist -g todolist -m 0775 /data
VOLUME /data

# โค้ดเป็นของ root และ process รันเป็น todolist — **เขียนทับตัวเองไม่ได้**
RUN chown -R root:root /app && chmod -R a-w /app

USER todolist
EXPOSE 8000

# healthcheck ยิงหน้า login เพราะเป็นหน้าเดียวที่ตอบได้โดยไม่ต้อง login
# และการที่มันตอบ 200 แปลว่า config ผ่าน, ต่อฐานข้อมูลได้, template render ได้
# (endpoint `/healthz` แยกจะบอกน้อยกว่านี้ — มันตอบ 200 ได้แม้ฐานข้อมูลล่ม)
#
# **`X-Forwarded-Proto: https` จำเป็นตอน `HTTPS_ENABLED=1`** — ไม่งั้น Talisman
# เห็น scheme เป็น http แล้วเด้ง 302 ไป `https://127.0.0.1:8000` ซึ่งเป็นพอร์ตที่
# ไม่ได้พูด TLS (TLS จบที่ proxy) urllib ตามไปแล้วล้ม → container ถูกมาร์ค
# unhealthy ตลอดกาลทั้งที่แอปเสิร์ฟผู้ใช้อยู่ปกติ orchestrator จะ restart วนไม่จบ
# (เจอจริงตอนเปิด compose.tls.yaml ครั้งแรก — P5-12)
#
# ตอน `HTTPS_ENABLED=0` header นี้ไม่มีผลอะไร เพราะ `TRUSTED_PROXY_HOPS=0`
# ทำให้ ProxyFix ไม่ถูกผูกเลย (ADR 0027) จึงใส่ไว้ตายตัวได้ ไม่ต้องมีสองสูตร
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request as u; u.urlopen(u.Request('http://127.0.0.1:8000/login', headers={'X-Forwarded-Proto': 'https'})).read()"

# `--access-logfile -` ส่ง access log ออก stdout ส่วน log ของแอปออก stderr
# (ADR 0011 หมายเหตุท้ายไฟล์) runtime เก็บทั้งสองช่อง
# จำนวน worker ตั้งจากภายนอกด้วย `GUNICORN_CMD_ARGS` หรือ `WEB_CONCURRENCY`
# **รันหลาย worker แล้วต้องตั้ง `CACHE_URL` ให้ชี้ store ที่แชร์ได้ด้วย**
# ไม่งั้นเพดาน rate limit จะเป็น N เท่า (แอปเตือนตอน start — ดู app/cache.py)
# `--graceful-timeout` ชัดเจนเป็นส่วนหนึ่งของสัญญา rolling (ADR 0048) —
# SIGTERM แล้วคำขอที่กำลังทำอยู่ต้องได้จบก่อนโปรเซสตาย ไม่ใช่ถูกตัดกลางคัน
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--graceful-timeout", "30", "--access-logfile", "-", "run:app"]
