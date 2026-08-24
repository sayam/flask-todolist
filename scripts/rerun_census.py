"""นับความล้มเหลวของ CI **รวมของที่ถูก rerun จนหายไปจากสถิติ** — audit รอบ 7

`gh run list --json conclusion` รายงานผลของ **attempt ล่าสุด** เท่านั้น · กด rerun
จนเขียวเมื่อไหร่ ความล้มเหลวเดิมหายจากผลลัพธ์ทันที เหลือร่องรอยอยู่แค่ใน
`/runs/<id>/attempts/<n>/jobs` ที่ไม่มีใครเปิดดู — วัดจริง 2026-08-17: เห็น 11 ใบ
ที่ล้ม **ซ่อนอยู่อีก 3 ใบ** (`dast` สองครั้ง · `codeql` หนึ่งครั้ง)

ทิศของความคลาดเคลื่อนอันตรายกว่าตัวเลข: การ rerun ทำให้ job ที่เคยแดง
**กลับไปเป็น "ไม่เคยแดง"** ได้ — ซึ่งเป็นข้อมูลที่ ADR 0059 (`proved_by`) กับแถว
ทบทวน flake ใน `docs/SECURITY-CADENCE.md` ใช้ตัดสินทั้งคู่

**แยกคลาสด้วย*ข้อความ*ของความล้มเหลว ไม่ใช่ชื่อ step** (แก้ตาม audit r8) —
ฉบับแรกอ่านแค่ชื่อ step (`Set up job`) แล้ววันที่ GitHub ล่มจริง (2026-08-17/18)
`codeql` ล้มสี่ครั้งที่ step `Run github/codeql-action/init@…` ซึ่ง*ข้างใน*คือ
HTTP 503 ของ GitHub เอง — ตัวนับอ่านว่า "ของเรา" ทั้งสี่ครั้ง · **ชื่อ step บอก
ว่าล้มตรงไหน ไม่ได้บอกว่าใครพัง** สัญญาณที่บอกได้คือ annotation ของ check run

สามคลาส ไม่ใช่สอง:

- `platform` — มีร่องรอยของ "โลกพัง" ชัดเจน (429/503 · No server is currently
  available ฯลฯ) หรือล้มที่ step ของ runner เอง · เราแก้ไม่ได้ ไม่ปนเกณฑ์ flake
- `ของเรา` — ล้มที่ step ที่เป็นคำสั่งของเราเอง พร้อมข้อความที่ไม่ใช่ของแพลตฟอร์ม
- `ต้องอ่านเอง` — **ที่เหลือทั้งหมด** (ไม่มี annotation ให้อ่าน หรือล้มใน action
  ของคนอื่นโดยไม่มีร่องรอยว่าฝั่งไหนพัง) · ชั้นนี้มีไว้เพื่อให้ของที่จำแนกไม่ได้
  **ไม่ตกไปอยู่ "ของเรา" เงียบ ๆ** — การเดาผิดทิศนั้นทำให้เกณฑ์ flake สุกงอม
  ด้วยเรื่องที่เราแก้ไม่ได้ ซึ่งคือความผิดพลาดที่ฉบับแรกทำมาแล้ว

ใช้:
    python3 scripts/rerun_census.py --limit 200          # ดึงสดจาก GitHub ผ่าน gh
    python3 scripts/rerun_census.py --input runs.json    # ตัดสินจากไฟล์ (ออฟไลน์)
    python3 scripts/rerun_census.py --max-hidden 0       # ใช้เป็นด่านตอนทบทวนตามรอบ

บทบาท: reader — อ่านแล้วรายงาน — หลักฐานคือตัวเลขที่พิมพ์ต้องตรงกับแหล่ง · ห้ามตัดของทิ้งเงียบ
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import shutil
import subprocess
import sys
import typing

# pyyaml มากับ dev tools และไม่มี stub — เหตุผลเดียวกับ build_gates_crosswalk.py
import yaml  # type: ignore[import-untyped] - library lacks type stubs

ROOT = pathlib.Path(__file__).resolve().parent.parent

# **เพดานเวลาของคำสั่งที่เรายิงออกไป** (audit รอบ 11 · ADR 0067) — `subprocess.run`
# ที่ไม่มี `timeout=` รอตลอดกาล ซึ่งกลายเป็น job ที่ไม่มีวันจบเมื่อรันใน CI
NETWORK_TIMEOUT_SECONDS = 60  # หนึ่งคำขอไป GitHub API
LOG_TIMEOUT_SECONDS = 180  # log ของ job หนึ่งตัวอาจใหญ่มาก

# step ที่เป็นของ runner ไม่ใช่ของด่าน — ล้มตรงนี้แปลว่าแพลตฟอร์มมีปัญหา
PLATFORM_STEPS = frozenset({"Set up job", "Set up runners", "Complete job"})

PLATFORM = "platform"
OURS = "ของเรา"
UNKNOWN = "ต้องอ่านเอง"

# ร่องรอยของ "โลกพัง" ในข้อความของความล้มเหลว — เก็บจาก outage จริง 2026-08-17/18
# **รหัสสถานะต้องมีบริบท HTTP กำกับเสมอ** ไม่ใช่ตัวเลขลอย ๆ เพราะเทสต์ของแอปนี้
# assert 503 กับ `/readyz` อยู่จริง — ตัวเลขลอยจะทำให้ความล้มเหลวของเราถูกอ่าน
# เป็นของแพลตฟอร์ม ซึ่งเป็นความผิดพลาดทิศเดียวกับที่ audit r8 เพิ่งจับได้
PLATFORM_MESSAGES = re.compile(
    r"""(?ix)
      \bhttp/?[\d.]*\s* (?:error\s*)? (?:429|50[234])\b
    | \b(?:status|code)\b [^\n]{0,20} \b(?:429|50[234])\b
    | \b(?:429|50[234])\b \s* [:-]? \s*
      (?:too\ many\ requests|bad\ gateway|service\ unavailable|gateway\ time-?out)
    | too\ many\ requests
    | bad\ gateway
    | service\ unavailable
    | server\ error
    | no\ server\ is\ currently\ available
    | (?:api\ )?rate\ limit\ exceeded
    | you\ have\ exceeded\ a\ secondary\ rate\ limit
    """
)

# step ที่รัน action ของคนอื่น — ชื่อเริ่มด้วย "Run <เจ้าของ>/<ชื่อ>@<รุ่น>"
# ล้มตรงนี้โดยไม่มีข้อความของแพลตฟอร์ม แปลว่าตัดสินไม่ได้ว่าเป็นเซิร์ฟเวอร์ของเขา
# หรือ config ของเรา (เคสของ codeql ที่ r8 เจอ) → ต้องมีคนอ่าน ไม่ใช่ให้ตัวนับเดา
THIRD_PARTY_STEP = re.compile(r"^Run [\w.-]+/[\w./-]+@")


def classify(failure: dict) -> str:
    """ความล้มเหลวหนึ่งครั้งเป็นของใคร — **อ่านข้อความก่อน แล้วค่อยดูว่าล้มตรงไหน**

    ลำดับนี้สำคัญ: ข้อความคือหลักฐาน ส่วนชื่อ step เป็นแค่บริบท · ที่ไม่มีหลักฐาน
    ทั้งสองทางต้องออกทาง `ต้องอ่านเอง` เสมอ (ดูหัวไฟล์ — ADR ของบทเรียนนี้คือ
    audit r8: ตัวจำแนกที่ผ่าน mutation test ครบ ยังอ่านโลกจริงผิดได้ 4 ใน 9 ครั้ง)
    """
    message = str(failure.get("message") or "").strip()
    if message and PLATFORM_MESSAGES.search(message):
        return PLATFORM
    if failure.get("step") in PLATFORM_STEPS:
        return PLATFORM
    if not message:
        return UNKNOWN
    if THIRD_PARTY_STEP.match(str(failure.get("step") or "")):
        return UNKNOWN
    return OURS


def _gh_json(path: str) -> typing.Any:
    """เรียก `gh api` แล้วคืน JSON ดิบ — แยกออกมาเพื่อให้เทสต์ปลอมได้ที่จุดเดียว"""
    binary = shutil.which("gh")
    if not binary:
        raise RuntimeError("ไม่มี gh บนเครื่องนี้ — ตัวนับต้องถาม GitHub API ผ่านมัน")
    result = subprocess.run(  # noqa: S603 — path มาจาก shutil.which และ argument เป็นของเราเอง
        [binary, "api", path],
        timeout=NETWORK_TIMEOUT_SECONDS,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def _gh(path: str) -> dict:
    """ปลายทางที่คืน object เดียว (runs · jobs)"""
    return dict(_gh_json(path))


def _annotations(job: dict) -> str:
    """ข้อความของความล้มเหลวจาก check run ของ job นั้น — หลักฐานว่าใครพัง

    **อ่านไม่ได้ต้องคืนค่าว่าง ห้าม raise** (สิทธิ์ไม่พอ · annotation หมดอายุ ·
    หรือ API ล่มเอง) แล้วปล่อยให้ความล้มเหลวนั้นตกชั้น `ต้องอ่านเอง` — สำมะโนที่
    ตายกลางทางเพราะ job เดียวอ่านไม่ได้ คือสำมะโนที่รันไม่ได้ตอน GitHub มีปัญหา
    ซึ่งเป็นตอนที่ต้องการมันที่สุด
    """
    url = str(job.get("check_run_url") or "")
    if not url:
        return ""
    try:
        rows = _gh_json(f"{url}/annotations")
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return ""
    return " · ".join(
        str(row.get("message") or "")
        for row in rows
        if isinstance(row, dict) and row.get("annotation_level") == "failure"
    ).strip()


def startup_failure(run: dict, failures: list[dict]) -> list[dict]:
    """run ที่ล้ม **โดยไม่มี job ไหนล้มเลย** คือ workflow ที่ไม่ได้ start

    จุดบอดที่เจอตอน audit r9: ตัวนับไล่ดูความล้มเหลวจาก*job* — run ที่ GitHub
    ปฏิเสธตั้งแต่ก่อนสร้าง job ("This run likely failed because of a workflow
    file issue") จึงมี 0 job และ**หายไปจากสำมะโนทั้งใบ** · ของจริงที่ซ่อนอยู่ใต้
    จุดบอดนี้: `scorecard.yml` ล้มทุก run ข้ามวันรวมบน main เพราะ scope ที่
    `GITHUB_TOKEN` ไม่มี ทำให้ job `posture` (ADR 0061) ไม่เคยรันเลยสักครั้ง

    นับเป็นชนิด "ของเรา" เพราะไฟล์ workflow เป็นของเรา — แต่ขั้นตอนก่อนกด rerun
    ใน `docs/OPERATIONS.md` ยังใช้เหมือนเดิม: ถามแพลตฟอร์มก่อนเสมอ
    """
    if failures or run.get("conclusion") != "failure":
        return failures
    return [
        {
            "attempt": run.get("run_attempt", 1),
            "job": f"{run.get('name') or '(ไม่ทราบ workflow)'} — ไม่ได้ start",
            "step": "",
            "message": "workflow file issue — run นี้ไม่ได้สร้าง job สักตัว",
        }
    ]


# **`per_page` ของ GitHub ตันที่ 100** — ขอ 200 แล้วได้ 100 เงียบ ๆ ซึ่งแปลว่า
# หน้าต่างที่แถว cadence สั่งไว้ (`--limit 200`) เคยแคบกว่าที่เขียนไว้ครึ่งหนึ่ง
# โดยไม่มีอะไรบอก (เจอตอน audit r9 ขณะเขียนตัวเก็บหลักฐาน)
PAGE_SIZE = 100


def _recent_runs(limit: int) -> list[dict]:
    """run ล่าสุด `limit` ใบ — **ไล่ทีละหน้า** เพราะ API ให้ทีละ 100 เท่านั้น"""
    runs: list[dict] = []
    page = 1
    while len(runs) < limit:
        size = min(PAGE_SIZE, limit - len(runs))
        batch = _gh(f"repos/:owner/:repo/actions/runs?per_page={size}&page={page}")
        got = batch.get("workflow_runs", [])
        if not got:
            break
        runs.extend(got)
        page += 1
    return runs[:limit]


def collect(limit: int) -> list[dict]:
    """ดึง run ล่าสุดพร้อม**ทุก attempt ที่ถูกแทนที่ไปแล้ว** — ส่วนที่ต้องต่อเน็ต"""
    records = []
    for run in _recent_runs(limit):
        attempt = run.get("run_attempt", 1)
        base = f"repos/:owner/:repo/actions/runs/{run['id']}"
        failures = []
        for n in range(1, attempt + 1):
            # attempt สุดท้ายอ่านจาก /jobs ตรง ๆ ส่วนที่ถูกแทนที่ไปแล้วอยู่ใต้ /attempts/<n>
            jobs = _gh(f"{base}/jobs" if n == attempt else f"{base}/attempts/{n}/jobs")
            for job in jobs["jobs"]:
                if job.get("conclusion") != "failure":
                    continue
                steps = [
                    s["name"] for s in job.get("steps", []) if s.get("conclusion") == "failure"
                ]
                failures.append(
                    {
                        "attempt": n,
                        "job": job["name"],
                        "step": steps[0] if steps else "",
                        "message": _annotations(job),
                        "job_id": job.get("id"),
                    }
                )
        records.append(
            {
                "id": run["id"],
                "attempt": attempt,
                "failures": startup_failure(run, failures),
            }
        )
    return records


def job_identity() -> tuple[set[str], dict[str, str], dict[str, list[str]]]:
    """ไอดีของ job ทุกตัว · แม็ปจาก **ชื่อ check** กลับไปหาไอดี · และไอดีต่อไฟล์ workflow

    **ทำไมต้องมีแม็ป** (audit รอบ 13 ข้อ 1): API คืน *ชื่อ check* ซึ่งเป็นค่าของ
    `name:` ถ้า job ตั้งไว้ — `dialects` ประกาศ `name: dialect (${{ matrix.db.name }})`
    ชื่อที่กลับมาจึงเป็น `dialect (mysql-8)` · ฝั่งที่ถามว่า "job ไหนไม่เคยแดง"
    อ่านไอดีจากไฟล์ workflow (`dialects`) — สองฝั่งจึงไม่มีทางแมตช์กัน และผลคือ
    **รายงานฉบับเดียวบอกว่า `dialect` ล้ม 10 ครั้ง แล้วบอกว่า `dialects` ไม่เคยแดง**
    ซึ่งเป็นครึ่งหนึ่งของคำตัดสินตาม ADR 0062 ว่าด่านไหนควรย้ายไปรันตามรอบ
    """
    ids: set[str] = set()
    by_name: dict[str, str] = {}
    by_path: dict[str, list[str]] = {}
    for path in sorted((ROOT / ".github" / "workflows").glob("*.y*ml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        jobs = workflow.get("jobs") or {}
        ids |= set(jobs)
        by_path[f".github/workflows/{path.name}"] = sorted(jobs)
        for job_id, body in jobs.items():
            by_name[job_id] = job_id
            declared = (body or {}).get("name")
            if not declared:
                continue
            # ตัดส่วนที่เป็น template ของ matrix ออก เหลือส่วนที่คงที่จริง ๆ
            static = str(declared).split("${{")[0].strip().rstrip("(").strip()
            if static:
                by_name[static] = job_id
    return ids, by_name, by_path


def census(records: list[dict], by_name: dict[str, str] | None = None) -> dict:
    """สรุปว่าอะไรล้มจริงบ้าง — ของที่ถูก rerun ต้องยังถูกนับ

    `visible` = ล้มใน attempt สุดท้าย (คือสิ่งที่ `gh run list` เห็น) ·
    `hidden` = ล้มใน attempt ก่อนหน้าแล้วถูก rerun จนเขียว (คือสิ่งที่หายไป)

    `by_name` แปลง **ชื่อ check** ที่ API คืนมา กลับเป็น **ไอดี job** — ต้องส่งมาเสมอ
    ตอนใช้งานจริง ไม่งั้นตัวเลขฝั่งนี้จะคีย์คนละแบบกับฝั่ง "ไม่เคยแดง" (audit รอบ 13)
    """
    by_job: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    runs = {"visible": 0, "hidden": 0}
    classes: collections.Counter = collections.Counter()

    for record in records:
        last = record.get("attempt", 1)
        seen = set()
        for failure in record.get("failures", []):
            where = "visible" if failure.get("attempt", 1) >= last else "hidden"
            label = str(failure.get("job", "?")).split(" (")[0]
            job = (by_name or {}).get(label, label)
            by_job[job][where] += 1
            classes[classify(failure)] += 1
            seen.add(where)
        for where in seen:
            runs[where] += 1

    return {
        "runs_examined": len(records),
        "runs_failed_visible": runs["visible"],
        "runs_failed_hidden": runs["hidden"],
        "failures_by_class": dict(classes),
        "jobs": {job: dict(counts) for job, counts in sorted(by_job.items())},
    }


def unresolved_labels(summary: dict, ids: set[str]) -> list[str]:
    """ชื่อที่นับความล้มเหลวไว้แต่แปลงกลับเป็นไอดี job ไม่ได้

    ชื่อแบบนั้นคือชื่อที่จะตกไปอยู่ฝั่ง "ไม่เคยแดง" เงียบ ๆ — ซึ่งเป็นบั๊กที่ audit
    รอบ 13 เจอ · run ที่ไม่ได้ start ถูกตั้งชื่อด้วย path จึงไม่นับเป็นชื่อแปลก
    """
    return sorted(
        label for label in summary["jobs"] if label not in ids and " — ไม่ได้ start" not in label
    )


def jobs_never_red(summary: dict, defined: set[str]) -> list[str]:
    """job ที่ไม่แดงเลยในหน้าต่างที่ตรวจ — ครึ่งหนึ่งของคำถาม "ด่านนี้ยังคุ้มไหม"

    อีกครึ่งคือ `guards:` ใน `gates.yaml` (โค้ดที่มันคุ้มถูกแก้ในช่วงเดียวกันไหม)
    — ADR 0062 · **ไม่แดงเพราะไม่มีใครแตะของที่มันคุ้ม** ต่างจาก **ไม่แดงทั้งที่
    ของนั้นถูกแก้ทุกสัปดาห์** คนละคำตอบกันคนละขั้ว
    """
    return sorted(defined - set(summary["jobs"]))


# บรรทัดที่ pytest พิมพ์ตอนสรุป: "FAILED tests/test_x.py::test_y - AssertionError"
PYTEST_FAILED = re.compile(r"^FAILED\s+(tests/[\w/]+\.py)::", re.MULTILINE)


def failing_tests(log: str) -> set[str]:
    """ไฟล์เทสต์ที่แดงใน log หนึ่งก้อน — **หลักฐานว่าด่านไหนเพิ่งจับของได้จริง**

    ADR 0059 บอกว่า gate ต้องมีหลักฐานว่าเคยแดงตอนของเสียจริง · หลักฐานแบบนั้น
    เกิดขึ้นเองทุกครั้งที่ CI แดง แล้วหายไปกับ log — ที่นี่หยิบมันออกมาก่อนหาย
    """
    return set(PYTEST_FAILED.findall(log))


def gates_by_test_file(gates: list[dict]) -> dict[str, dict]:
    """แม็ป ไฟล์เทสต์ → gate ที่มันบังคับ (partition ที่ `tests/test_gates.py` คุมอยู่)"""
    return {path: gate for gate in gates for path in gate.get("enforced_by", {}).get("tests", [])}


def evidence_proposals(records: list[dict], gates: list[dict]) -> list[dict]:
    """ข้อเสนอ `proved_by` จากความแดงจริง — **เสนอ ไม่ใช่เขียนให้**

    ตัดสินว่าความแดงนั้น*พิสูจน์*อะไรได้จริงไหม เป็นงานของคน (เทสต์อาจแดงเพราะ
    fixture พัง ไม่ใช่เพราะ gate จับของเสีย) เครื่องมือจึงหยุดที่การเสนอ ·
    เสนอเฉพาะ gate ที่**ยังไม่มีหลักฐาน** เพราะที่มีแล้วไม่ต้องการเพิ่ม
    """
    owners = gates_by_test_file(gates)
    found: dict[str, dict] = {}
    for record in records:
        for failure in record.get("failures", []):
            if classify(failure) != OURS:
                continue
            for path in sorted(failure.get("tests", [])):
                gate = owners.get(path)
                if gate is None or gate.get("proved_by"):
                    continue
                entry = found.setdefault(
                    gate["id"], {"gate": gate["id"], "run": record["id"], "tests": set()}
                )
                entry["tests"].add(path)
    return [
        {**entry, "tests": sorted(entry["tests"])}
        for entry in sorted(found.values(), key=lambda e: e["gate"])
    ]


def _job_log(job_id: object) -> str:
    """log ของ job — หมดอายุ/อ่านไม่ได้ให้คืนค่าว่าง ไม่ใช่ล้มทั้งสำมะโน"""
    if not job_id:
        return ""
    binary = shutil.which("gh")
    if not binary:
        return ""
    result = subprocess.run(  # noqa: S603 — argument เป็นของเราเอง
        [
            binary,
            "api",
            "--allow-escape-sequences",
            f"repos/:owner/:repo/actions/jobs/{job_id}/logs",
        ],
        timeout=LOG_TIMEOUT_SECONDS,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else ""


def harvest(records: list[dict]) -> None:
    """เติมรายชื่อไฟล์เทสต์ที่แดงลงในแต่ละความล้มเหลว (ส่วนที่ต้องต่อเน็ต)"""
    for record in records:
        for failure in record.get("failures", []):
            if classify(failure) == OURS and "tests" not in failure:
                failure["tests"] = sorted(failing_tests(_job_log(failure.get("job_id"))))


def report_evidence(proposals: list[dict]) -> None:
    """พิมพ์แถวที่พร้อมวางลง `gates.yaml` — คนอ่านแล้วตัดสินเองว่ารับไหม"""
    if not proposals:
        print("\nไม่มี gate ไหนที่ยังไม่มีหลักฐานแล้วแดงจริงในหน้าต่างนี้")
        return
    print(f"\ngate ที่แดงจริงในหน้าต่างนี้และยังไม่มีหลักฐาน ({len(proposals)}):")
    for proposal in proposals:
        print(f"\n  # {proposal['gate']} — จาก {', '.join(proposal['tests'])}")
        print("    proved_by:")
        print("      - kind: ci-red")
        print(f"        ref: run/{proposal['run']}")
        print("        date: <วันที่ของ run นั้น>")
        print("        caught: <มันจับอะไรได้ — เขียนเอง อย่าลอกชื่อเทสต์มาวาง>")
    print("\n**อ่าน log ก่อนรับทุกแถว** — เทสต์ที่แดงเพราะ fixture พัง ไม่ได้แปลว่า gate จับของเสียได้")


def report(summary: dict) -> None:
    """พิมพ์ผลให้คนอ่าน — ตัวเลขที่ซ่อนอยู่ต้องเด่นกว่าตัวเลขที่ทุกคนเห็นอยู่แล้ว"""
    print(f"ตรวจ {summary['runs_examined']} run")
    print(f"  ล้มแบบที่ `gh run list` เห็น : {summary['runs_failed_visible']}")
    print(f"  ล้มแล้วถูก rerun จนหายไป    : {summary['runs_failed_hidden']}")
    for kind, count in sorted(summary["failures_by_class"].items()):
        print(f"  ความล้มเหลวชนิด {kind}: {count}")
    unread = summary["failures_by_class"].get(UNKNOWN, 0)
    if unread:
        print(
            f"  ↳ {unread} ครั้งจำแนกด้วยเครื่องไม่ได้ — เปิดอ่านเองก่อนนับเข้าเกณฑ์ flake\n"
            '    (ขั้นตอนตัดสิน "ของเราพัง vs โลกพัง" อยู่ใน docs/OPERATIONS.md)'
        )
    for job, counts in summary["jobs"].items():
        hidden = counts.get("hidden", 0)
        mark = f"  (ซ่อน {hidden})" if hidden else ""
        print(f"    {job}: {counts.get('visible', 0)}{mark}")


def main(argv: list[str] | None = None) -> int:
    """ดึง (หรืออ่านไฟล์) → สรุป → พิมพ์ · คืน 1 เมื่อของที่ซ่อนเกินเพดานที่ตั้งไว้"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100, help="จำนวน run ที่ดึงมาตรวจ")
    parser.add_argument("--input", help="ไฟล์ JSON ของ record (ข้ามการต่อเน็ต)")
    parser.add_argument("--json", action="store_true", help="พิมพ์ผลเป็น JSON")
    parser.add_argument(
        "--never-red",
        action="store_true",
        help="ลงท้ายด้วยรายชื่อ job ที่ไม่แดงเลยในหน้าต่างนี้ (ADR 0062)",
    )
    parser.add_argument(
        "--evidence",
        action="store_true",
        help="เสนอแถว proved_by จาก gate ที่แดงจริงในหน้าต่างนี้ (ADR 0059)",
    )
    parser.add_argument(
        "--max-hidden",
        type=int,
        default=None,
        help="เพดานของความล้มเหลวที่ถูก rerun จนหาย — เกินแล้วคืน exit 1",
    )
    args = parser.parse_args(argv)

    if args.input:
        records = json.loads(pathlib.Path(args.input).read_text(encoding="utf-8"))
    else:
        records = collect(args.limit)

    if args.evidence:
        if not args.input:
            harvest(records)
        gates = yaml.safe_load((ROOT / "gates.yaml").read_text(encoding="utf-8"))["gates"]
        report_evidence(evidence_proposals(records, gates))

    ids, by_name, by_path = job_identity()
    summary = census(records, by_name)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        report(summary)

    strange = unresolved_labels(summary, ids)
    if strange:
        print(
            f'\n**ชื่อที่แปลงกลับเป็นไอดี job ไม่ได้** — ตัวเลขของมันจะไม่ถูกนับเข้าฝั่ง "ไม่เคยแดง": {strange}',
            file=sys.stderr,
        )

    if args.never_red:
        never = jobs_never_red(summary, ids)
        clash = sorted(set(never) & set(summary["jobs"]))
        assert not clash, f"รายงานขัดกันเอง: {clash} อยู่ทั้งสองรายการ"
        print(f"\njob ที่ไม่แดงเลยในหน้าต่างนี้ ({len(never)}): {', '.join(never)}")
        for label, count in sorted(summary["jobs"].items()):
            owned = by_path.get(label.split(" — ")[0], [])
            silent = [job for job in owned if job in never]
            if silent:
                print(
                    f"  หมายเหตุ: {', '.join(silent)} ไม่เคยแดงเอง แต่ workflow ของมัน"
                    f"ล้มก่อนสร้าง job {sum(count.values())} ครั้ง — คนละเรื่องกับ 'ไม่มีอะไรพัง'"
                )
        print("อ่านคู่กับ `guards:` ใน gates.yaml ก่อนตัดสินว่าด่านไหนควรย้ายไปรันตามรอบ (ADR 0062)")

    if args.max_hidden is not None and summary["runs_failed_hidden"] > args.max_hidden:
        print(
            f"\nความล้มเหลวที่ถูก rerun จนหายไปมี {summary['runs_failed_hidden']} ใบ "
            f"(เพดาน {args.max_hidden}) — อ่านว่าอะไรแดงก่อนตัดสินว่าเป็น flake",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
