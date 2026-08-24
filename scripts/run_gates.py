"""fail-fix harness — รัน gate จาก `gates.yaml` แล้วคืนผลเป็นของที่เครื่องอ่านได้

นี่คือกลไกที่เปลี่ยน checklist เป็น enforcement loop (INFRA-VISION ข้อ 3.4):
agent แก้โค้ด → รัน harness → ได้ (gate id, สาเหตุ, hint) → แก้ → วนจนผ่าน
จำนวนรอบถูกนับใน log เพื่อให้รู้ว่า gate ไหน fail บ่อย

**ขอบเขตที่ประกาศตรง ๆ**: harness รันเฉพาะ gate ชนิด `test` (pytest — สิ่งที่
loop การแก้โค้ดชนบ่อยที่สุด) · ชนิด `job`/`step` รายงานว่า **ข้ามพร้อมเหตุผล**
ไม่ใช่เงียบ — คำสั่งของมันอยู่ใน workflow และการลอกมารันคือการสร้างที่ที่สอง
(ADR 0039 ห้ามเก็บคำสั่งซ้ำ) ด่านพวกนั้นตัดสินใน CI ซึ่งบังคับทุก PR อยู่แล้ว

ใช้:
    pipenv run python scripts/run_gates.py                    # ทุก gate
    pipenv run python scripts/run_gates.py --only <gate-id>   # เฉพาะตัว (ซ้ำได้)
    pipenv run python scripts/run_gates.py --root <worktree>  # ตรวจ tree อื่น
    ... --output report.json                                  # เขียนรายงานเต็ม

บทบาท: decider — ตัดสินผ่าน/ไม่ผ่าน — หลักฐานคือเทสต์ที่ฝังความผิดแล้วต้องจับได้ · ของสะอาดต้องไม่ถูกจับ
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time

# pyyaml มากับ dev tools และไม่มี stub — เหตุผลเดียวกับ build_gates_crosswalk.py
import yaml  # type: ignore[import-untyped] - library lacks type stubs

# **เพดานเวลาของคำสั่งที่เรายิงออกไป** (audit รอบ 11 · ADR 0067) — `subprocess.run`
# ที่ไม่มี `timeout=` รอตลอดกาล ซึ่งกลายเป็น job ที่ไม่มีวันจบเมื่อรันใน CI
GATE_TIMEOUT_SECONDS = 1800  # หนึ่ง gate = pytest ชุดย่อย · ชุดเต็มบนเครื่องใช้ ~5 นาที

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
ROUND_LOG = ".gate-rounds.jsonl"  # gitignore แล้ว — เป็นบันทึกของเครื่องใครเครื่องมัน


def run_test_gate(gate: dict, root: pathlib.Path) -> dict:
    """รัน pytest ของ gate หนึ่งตัวใน tree ที่ชี้ — คืนผลพร้อมสาเหตุถ้าแดง"""
    files = gate["enforced_by"]["tests"]
    started = time.monotonic()
    result = subprocess.run(  # noqa: S603 — interpreter ตัวเดียวกับ harness + path จากดัชนีที่มีเทสต์คุม
        [sys.executable, "-m", "pytest", "-q", "--no-header", *files],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=GATE_TIMEOUT_SECONDS,
    )
    seconds = round(time.monotonic() - started, 2)
    if result.returncode == 0:
        return {"status": "pass", "seconds": seconds}

    # สาเหตุ = ท้าย stdout ของ pytest (บรรทัดสรุป + assertion สุดท้าย) — พอให้
    # loop รู้ว่าต้องไปดูตรงไหน โดยไม่แบก log ทั้งก้อนไว้ในรายงาน
    tail = [line for line in result.stdout.splitlines() if line.strip()][-12:]
    return {"status": "fail", "seconds": seconds, "cause": "\n".join(tail)}


def run_all(gates: list[dict], root: pathlib.Path, only: set[str]) -> list[dict]:
    """เดินทุก gate ตามลำดับในดัชนี — ข้ามพร้อมเหตุผล ไม่ข้ามเงียบ ๆ"""
    results = []
    for gate in gates:
        if only and gate["id"] not in only:
            continue
        entry: dict = {"gate": gate["id"], "kind": gate["kind"]}
        if gate["kind"] != "test":
            requires = ", ".join(gate.get("requires") or []) or "สภาพแวดล้อมของ CI"
            entry |= {
                "status": "skip",
                "cause": f"บังคับใน CI job `{gate['enforced_by']['job']}` — ต้องมี {requires}",
            }
        else:
            entry |= run_test_gate(gate, root)
            if entry["status"] == "fail":
                # hint = กับดักที่ให้กำเนิดกฎ — บอก loop ว่ากฎนี้กันอะไรอยู่
                entry["hint"] = " ".join(str(gate.get("born_from", "")).split())
        results.append(entry)
    return results


def main() -> int:
    """รันหนึ่งรอบ พิมพ์สรุป เขียนรายงาน/round log แล้วคืน exit ตามผล"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gates-file", type=pathlib.Path, default=REPO_ROOT / "gates.yaml")
    parser.add_argument("--root", type=pathlib.Path, default=REPO_ROOT)
    parser.add_argument("--only", action="append", default=[], metavar="GATE_ID")
    parser.add_argument("--output", type=pathlib.Path, help="เขียนรายงานเต็มเป็น JSON ที่นี่")
    args = parser.parse_args()

    gates = yaml.safe_load(args.gates_file.read_text(encoding="utf-8"))["gates"]
    known = {g["id"] for g in gates}
    unknown = sorted(set(args.only) - known)
    if unknown:
        print(f"ไม่รู้จัก gate: {unknown}", file=sys.stderr)
        return 2

    results = run_all(gates, args.root.resolve(), set(args.only))

    counts = {
        status: sum(1 for r in results if r["status"] == status)
        for status in ("pass", "fail", "skip")
    }
    failed = [r for r in results if r["status"] == "fail"]
    for r in failed:
        print(f"[FAIL] {r['gate']}")
        print("   " + r["cause"].replace("\n", "\n   "))
        if r.get("hint"):
            print(f"   hint: {r['hint']}")

    # round log — นับรอบของ loop และจดว่า gate ไหน fail เพื่อหาตัวที่ fail บ่อย
    log_path = args.root.resolve() / ROUND_LOG
    previous = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    record = {
        "round": len(previous) + 1,
        "counts": counts,
        "failed": [r["gate"] for r in failed],
    }
    log_path.write_text("\n".join([*previous, json.dumps(record, ensure_ascii=False)]) + "\n")

    if args.output:
        args.output.write_text(
            json.dumps({"round": record["round"], "results": results}, ensure_ascii=False, indent=1)
        )

    summary = f"ผ่าน {counts['pass']} · แดง {counts['fail']} · ข้าม {counts['skip']}"
    print(f"รอบที่ {record['round']}: {summary}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
