"""นับความล้มเหลวของ CI **รวมของที่ถูก rerun จนหายไปจากสถิติ** — audit รอบ 7

`gh run list --json conclusion` รายงานผลของ **attempt ล่าสุด** เท่านั้น · กด rerun
จนเขียวเมื่อไหร่ ความล้มเหลวเดิมหายจากผลลัพธ์ทันที เหลือร่องรอยอยู่แค่ใน
`/runs/<id>/attempts/<n>/jobs` ที่ไม่มีใครเปิดดู — วัดจริง 2026-08-17: เห็น 11 ใบ
ที่ล้ม **ซ่อนอยู่อีก 3 ใบ** (`dast` สองครั้ง · `codeql` หนึ่งครั้ง)

ทิศของความคลาดเคลื่อนอันตรายกว่าตัวเลข: การ rerun ทำให้ job ที่เคยแดง
**กลับไปเป็น "ไม่เคยแดง"** ได้ — ซึ่งเป็นข้อมูลที่ ADR 0059 (`proved_by`) กับแถว
ทบทวน flake ใน `docs/SECURITY-CADENCE.md` ใช้ตัดสินทั้งคู่

**แยกสองคลาสด้วย step ที่ล้ม**: step ของ runner เอง (`Set up job` — โหลด action
ไม่ได้ ฯลฯ) คือความล้มเหลว *ของแพลตฟอร์ม* ซึ่งเราแก้ไม่ได้และไม่ควรปนกับเกณฑ์
flake ของด่านเรา · ที่เหลือนับเป็นของเรา

ใช้:
    python3 scripts/rerun_census.py --limit 200          # ดึงสดจาก GitHub ผ่าน gh
    python3 scripts/rerun_census.py --input runs.json    # ตัดสินจากไฟล์ (ออฟไลน์)
    python3 scripts/rerun_census.py --max-hidden 0       # ใช้เป็นด่านตอนทบทวนตามรอบ
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import shutil
import subprocess
import sys

# pyyaml มากับ dev tools และไม่มี stub — เหตุผลเดียวกับ build_gates_crosswalk.py
import yaml  # type: ignore[import-untyped]

ROOT = pathlib.Path(__file__).resolve().parent.parent

# step ที่เป็นของ runner ไม่ใช่ของด่าน — ล้มตรงนี้แปลว่าแพลตฟอร์มมีปัญหา
PLATFORM_STEPS = frozenset({"Set up job", "Set up runners", "Complete job"})


def _gh(path: str) -> dict:
    """เรียก `gh api` แล้วคืน JSON — แยกออกมาเพื่อให้เทสต์ปลอมได้ที่จุดเดียว"""
    binary = shutil.which("gh")
    if not binary:
        raise RuntimeError("ไม่มี gh บนเครื่องนี้ — ตัวนับต้องถาม GitHub API ผ่านมัน")
    result = subprocess.run(  # noqa: S603 — path มาจาก shutil.which และ argument เป็นของเราเอง
        [binary, "api", path],
        capture_output=True,
        text=True,
        check=True,
    )
    return dict(json.loads(result.stdout))


def collect(limit: int) -> list[dict]:
    """ดึง run ล่าสุดพร้อม**ทุก attempt ที่ถูกแทนที่ไปแล้ว** — ส่วนที่ต้องต่อเน็ต"""
    runs = _gh(f"repos/:owner/:repo/actions/runs?per_page={limit}")
    records = []
    for run in runs["workflow_runs"]:
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
                    {"attempt": n, "job": job["name"], "step": steps[0] if steps else ""}
                )
        records.append({"id": run["id"], "attempt": attempt, "failures": failures})
    return records


def census(records: list[dict]) -> dict:
    """สรุปว่าอะไรล้มจริงบ้าง — ของที่ถูก rerun ต้องยังถูกนับ

    `visible` = ล้มใน attempt สุดท้าย (คือสิ่งที่ `gh run list` เห็น) ·
    `hidden` = ล้มใน attempt ก่อนหน้าแล้วถูก rerun จนเขียว (คือสิ่งที่หายไป)
    """
    by_job: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    runs = {"visible": 0, "hidden": 0}
    classes: collections.Counter = collections.Counter()

    for record in records:
        last = record.get("attempt", 1)
        seen = set()
        for failure in record.get("failures", []):
            where = "visible" if failure.get("attempt", 1) >= last else "hidden"
            job = str(failure.get("job", "?")).split(" (")[0]
            by_job[job][where] += 1
            kind = "platform" if failure.get("step") in PLATFORM_STEPS else "ของเรา"
            classes[kind] += 1
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


def jobs_never_red(summary: dict, defined: set[str]) -> list[str]:
    """job ที่ไม่แดงเลยในหน้าต่างที่ตรวจ — ครึ่งหนึ่งของคำถาม "ด่านนี้ยังคุ้มไหม"

    อีกครึ่งคือ `guards:` ใน `gates.yaml` (โค้ดที่มันคุ้มถูกแก้ในช่วงเดียวกันไหม)
    — ADR 0062 · **ไม่แดงเพราะไม่มีใครแตะของที่มันคุ้ม** ต่างจาก **ไม่แดงทั้งที่
    ของนั้นถูกแก้ทุกสัปดาห์** คนละคำตอบกันคนละขั้ว
    """
    return sorted(defined - set(summary["jobs"]))


def report(summary: dict) -> None:
    """พิมพ์ผลให้คนอ่าน — ตัวเลขที่ซ่อนอยู่ต้องเด่นกว่าตัวเลขที่ทุกคนเห็นอยู่แล้ว"""
    print(f"ตรวจ {summary['runs_examined']} run")
    print(f"  ล้มแบบที่ `gh run list` เห็น : {summary['runs_failed_visible']}")
    print(f"  ล้มแล้วถูก rerun จนหายไป    : {summary['runs_failed_hidden']}")
    for kind, count in sorted(summary["failures_by_class"].items()):
        print(f"  ความล้มเหลวชนิด {kind}: {count}")
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

    summary = census(records)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        report(summary)

    if args.never_red:
        defined = set()
        for path in sorted((ROOT / ".github" / "workflows").glob("*.y*ml")):
            defined |= set(yaml.safe_load(path.read_text(encoding="utf-8")).get("jobs", {}))
        never = jobs_never_red(summary, defined)
        print(f"\njob ที่ไม่แดงเลยในหน้าต่างนี้ ({len(never)}): {', '.join(never)}")
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
