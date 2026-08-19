"""วัดแอปที่ถูก generate ในการทดลองเฟส 12 — battery เดียวกันทั้งสองฝั่ง

รับไดเรกทอรีแม่ที่มีแอปย่อยหลายตัว (`ctrl/app1..N`, `skill/app1..N`) แล้ววัด
แต่ละแอปด้วยชุดเดียวกันเป๊ะ สามแกน:

1. **scan ของ overlay ทั้ง 8** (ตัวบังคับกฎสากล — stdlib ล้วน) → finding ต่อ gate
   · **แยก `na` ออกจาก `ok` เสมอ** เพราะ "ไม่มีของให้ตรวจ" ไม่ใช่ "ตรวจแล้วสะอาด"
   (แอปเล็ก ๆ ไม่มี Dockerfile/workflow/ADR ตัวสแกนพวกนั้นจึงไม่ตัดสินอะไรเลย)
2. **ASVS probe 10 ข้อ** (`scripts/asvs_probe.py`) → ผ่าน/ไม่ผ่าน/ไม่เกี่ยวข้อง
3. **semgrep** `p/flask` + `p/python` (ต้องตั้ง env `SEMGREP_BIN`) → จำนวน finding
   — แกนวัดภายนอกที่ไม่ได้นิยามโดยเราเอง ไม่ตั้ง = รายงานว่าข้าม ไม่ใช่ 0

ผลเป็น JSON (`--output`) และตาราง markdown ทาง stdout — **ไม่มีการตัดสินใน
สคริปต์นี้** ตัวเลขเปล่า ๆ เท่านั้น การตีความอยู่ใน `docs/comparison/`

ใช้: `pipenv run python scripts/measure_generated.py <apps-root> [--output x.json]`

บทบาท: reader — อ่านแล้วรายงาน — หลักฐานคือตัวเลขที่พิมพ์ต้องตรงกับแหล่ง · ห้ามตัดของทิ้งเงียบ
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
from typing import Any

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from asvs_probe import CHECKS, probe

# **เพดานเวลาของคำสั่งที่เรายิงออกไป** (audit รอบ 11 · ADR 0067) — `subprocess.run`
# ที่ไม่มี `timeout=` รอตลอดกาล ซึ่งกลายเป็น job ที่ไม่มีวันจบเมื่อรันใน CI
CHECKER_TIMEOUT_SECONDS = 300  # checker ตัวเดียวบนแอปที่ generate มา
SEMGREP_TIMEOUT_SECONDS = 1800  # semgrep สแกนทั้งแอป

REPO = pathlib.Path(__file__).resolve().parent.parent
CHECKERS = sorted((REPO / "overlays" / "flask" / "checks").glob("scan_*.py"))
DEFAULT_CONFIG = REPO / "overlays" / "flask" / "scaffold.json.default"

# ของที่ `install.py` วางให้เอง — ไม่ใช่ผลงานของ agent ฝั่งไหน จึงตัดออกก่อนวัด
# ทั้งสองฝั่ง (ฝั่งที่ไม่ได้ติดตั้ง overlay ก็ไม่มีอยู่แล้ว — การตัดจึงไม่ทำให้ใครเสียเปรียบ)
OVERLAY_ARTIFACTS = ("tools", ".github/workflows/gates.yml", "scaffold.json")


def run_scans(app_dir: pathlib.Path) -> dict[str, Any]:
    """สถานะต่อ checker: `na` / `ok` / จำนวน finding — ไม่ยุบสามอย่างนี้เข้าด้วยกัน

    วาง `scaffold.json` **ตัวเดียวกัน** (ค่าเริ่มต้นของ overlay) ให้ทุกแอปก่อนสแกน
    — config ที่ต่างกันคือด่านที่ต่างกัน แล้วตัวเลขสองฝั่งจะเทียบกันไม่ได้
    """
    shutil.copy2(DEFAULT_CONFIG, app_dir / "scaffold.json")
    status: dict[str, Any] = {}
    for checker in CHECKERS:
        result = subprocess.run(  # noqa: S603 — checker ของ repo เองกับ path ที่ผู้ใช้ชี้
            [sys.executable, str(checker), str(app_dir)],
            timeout=CHECKER_TIMEOUT_SECONDS,
            capture_output=True,
            text=True,
            check=False,
        )
        gate = checker.stem.removeprefix("scan_")
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        if any(line.startswith("NA:") for line in lines):
            status[gate] = "na"
        elif result.returncode == 1:
            status[gate] = len([line for line in lines if not line.startswith("NA:")])
        else:
            status[gate] = "ok"
    return status


def run_semgrep(app_dir: pathlib.Path, binary: pathlib.Path | None) -> int | None:
    """จำนวน finding ของ semgrep — None ถ้าไม่ได้ส่ง `--semgrep` มา (= ข้าม ไม่ใช่ 0)

    **รับ path ทาง argument ไม่ใช่ทาง environment** โดยตั้งใจ: ตัวรันที่มาจาก
    ตัวแปรแวดล้อมคือตัวรันที่เปลี่ยนได้โดยไม่มีใครเห็นในคำสั่ง (semgrep เองก็จับ
    รูปนี้ด้วยกฎ `dangerous-subprocess-use-tainted-env-args`) · path ถูกตรวจว่า
    มีจริงและเป็นไฟล์ก่อนเรียกเสมอ
    """
    if binary is None:
        return None
    resolved = binary.resolve(strict=True)
    if not resolved.is_file():
        raise SystemExit(f"--semgrep ไม่ใช่ไฟล์: {resolved}")
    result = subprocess.run(  # noqa: S603
        [
            str(resolved),
            "scan",
            "--config",
            "p/flask",
            "--config",
            "p/python",
            "--metrics=off",
            "--json",
            "--quiet",
        ],
        cwd=app_dir,
        timeout=SEMGREP_TIMEOUT_SECONDS,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise SystemExit(f"semgrep ล้มที่ {app_dir}: {result.stderr[-300:]}")
    results: list[object] = json.loads(result.stdout)["results"]
    return len(results)


def staged(app_dir: pathlib.Path, into: pathlib.Path) -> pathlib.Path:
    """สำเนาของแอปที่ **ตัดของที่ overlay ติดตั้งให้ออก** ก่อนวัด

    ฝั่งที่ใช้ skill รัน `install.py` ซึ่งวาง `tools/` (checker + doctor ของเรา),
    `scaffold.json` และ workflow ตั้งต้นลงในโปรเจกต์ — นับของพวกนั้นเป็นผลงาน
    เท่ากับเอาของเราเองไปบวกแต้มให้ฝั่งเดียว · ตัดออกทั้งหมดคือทิศที่**เข้มกับ
    ฝั่ง skill** ซึ่งเป็นทิศที่ถูกเมื่อผู้วัดมีส่วนได้เสียกับผลลัพธ์
    """
    target = into / app_dir.name
    shutil.copytree(app_dir, target, ignore=shutil.ignore_patterns("__pycache__", ".git"))
    if (target / "tools" / "overlay.json").is_file():
        for relative in OVERLAY_ARTIFACTS:
            path = target / relative
            if path.is_dir():
                shutil.rmtree(path)
            elif path.is_file():
                path.unlink()
    return target


def measure(
    app_dir: pathlib.Path, side: str, into: pathlib.Path, semgrep: pathlib.Path | None
) -> dict[str, Any]:
    """วัดแอปเดียวครบทั้งสามแกน — บนสำเนาที่ตัดของ overlay ออกแล้ว"""
    original = app_dir
    app_dir = staged(app_dir, into)
    asvs = probe(app_dir)
    gates = run_scans(app_dir)
    return {
        "side": side,
        "app": original.name,
        "overlay_installed": (original / "tools" / "overlay.json").is_file(),
        "py_files": len(list(app_dir.rglob("*.py"))),
        "py_lines": sum(
            len(p.read_text(encoding="utf-8", errors="replace").splitlines())
            for p in app_dir.rglob("*.py")
        ),
        "gates": gates,
        "gate_findings": sum(v for v in gates.values() if isinstance(v, int)),
        "gates_na": sorted(k for k, v in gates.items() if v == "na"),
        "asvs": asvs,
        "asvs_pass": sum(1 for v in asvs.values() if v is True),
        "asvs_fail": sorted(k for k, v in asvs.items() if v is False),
        "asvs_na": sorted(k for k, v in asvs.items() if v is None),
        "semgrep": run_semgrep(app_dir, semgrep),
    }


def main() -> int:
    """วัดทุกแอปใต้ root แล้วพิมพ์ตาราง + เขียน JSON"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path)
    parser.add_argument("--semgrep", type=pathlib.Path, help="path ของ semgrep — ไม่ส่ง = ข้ามแกนนี้")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as staging:
        rows = [
            measure(
                app_dir,
                side_dir.name,
                pathlib.Path(staging) / side_dir.name / app_dir.name,
                args.semgrep,
            )
            for side_dir in sorted(p for p in args.root.iterdir() if p.is_dir())
            for app_dir in sorted(p for p in side_dir.iterdir() if p.is_dir())
        ]

    applicable = len(CHECKS)
    print(f"| ฝั่ง | แอป | บรรทัด .py | gate ที่พบ | ASVS ผ่าน (จาก {applicable}) | semgrep |")
    print("|---|---|---|---|---|---|")
    for row in rows:
        semgrep = "ข้าม" if row["semgrep"] is None else row["semgrep"]
        na = len(row["asvs_na"])
        asvs = f"{row['asvs_pass']}" + (f" (+{na} ไม่เกี่ยวข้อง)" if na else "")
        print(
            f"| {row['side']} | {row['app']} | {row['py_lines']} "
            f"| {row['gate_findings']} | {asvs} | {semgrep} |"
        )

    if args.output:
        args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
