"""gate: gates-registry-total — ดัชนี gate ของโปรเจกต์ต้องตรงกับความจริงสองทิศ

กฎอีก 70 กว่าข้อในกล่องนี้ลงท้ายเหมือนกันหมดว่า "ลงทะเบียนใน gates.yaml ของ
โปรเจกต์" — คำสั่งนั้นไม่มีความหมายเลยถ้าไม่มีอะไรบังคับว่าทะเบียนตรงกับความจริง
ตัวนี้คือเสาต้นนั้น: ดัชนีที่ไม่ถูกบังคับให้ตรงกับความจริง คือดัชนีที่โกหกเงียบ ๆ

สี่ทิศที่ตรวจ (แบบเดียวกับ `tests/test_gates.py` ของ reference implementation):
- **ทิศไป (job)**: ทุก gate ชี้ไปหา job ที่มีจริงใน workflow
- **ทิศไป (step/test)**: `kind: step` ชี้ชื่อ step ที่มีจริง · `kind: test`
  ชี้ไฟล์ที่มีจริง
- **ทิศกลับ (job)**: ทุก job ในทุก workflow ต้องมี gate — job ใหม่ที่ไม่มี = พบ
- **ทิศกลับ (เทสต์)**: ไฟล์เทสต์ทุกไฟล์ถูกตัดสินว่าเป็นของ gate ตัวเดียว
  (partition — ของใหม่ที่ไม่ถูกตัดสินต้องดัง ไม่ใช่หลุดสายตา)

**ตัวอ่าน YAML เป็นสับเซตที่แคบโดยตั้งใจ** — stdlib ล้วน ไม่มี pyyaml ให้พึ่ง
และของที่มันอ่านไม่ออกจะ **ดัง** ไม่ใช่ข้ามเงียบ ๆ (ตัวอ่านที่ใจดีกว่าของจริง
คือตัวที่รายงานเขียวบนไฟล์ที่มันไม่เข้าใจ)

exit 0 = สะอาด/NA · 1 = พบ · 2 = เรียกผิด
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

KINDS = {"test", "step", "job"}
GATE_ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
# ตัวเปิด block scalar ต้องอยู่ท้ายบรรทัดและตามหลัง `: ` หรือ `- ` เท่านั้น
# (`title: a|` ไม่ใช่ block scalar — ตัวจับที่หยาบกว่านี้จะกลืนบรรทัดถัดไปทิ้ง)
BLOCK_SCALAR = re.compile(r"(?:^|(?<=: )|(?<=- ))[|>][-+]?$")


class SubsetError(Exception):
    """ไฟล์ใช้ YAML นอกสับเซตที่ตัวอ่านนี้รับ — ต้องดัง ไม่ใช่เดา"""


def _uncomment(line: str) -> str:
    """ตัดคอมเมนต์ท้ายบรรทัด โดยไม่แตะ `#` ที่อยู่ในเครื่องหมายคำพูด"""
    quote = None
    for index, char in enumerate(line):
        if quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "#" and (index == 0 or line[index - 1] in " \t"):
            return line[:index]
    return line


def _significant(text: str) -> list[tuple[int, str]]:
    """(คอลัมน์, เนื้อ) ของบรรทัดที่มีความหมาย — `- x` ถูกแยกเป็นสองรายการ

    เนื้อของ block scalar ถูกทิ้ง (เราไม่ใช้ค่าของมัน) แต่ **ต้องถูกข้ามให้ถูก**
    ไม่งั้นร้อยแก้วในนั้นจะถูกอ่านเป็นโครงสร้าง
    """
    raw = text.splitlines()
    out: list[tuple[int, str]] = []
    index = 0
    while index < len(raw):
        line = raw[index]
        index += 1
        if "\t" in line:
            raise SubsetError(f"บรรทัด {index}: มีแท็บ — YAML เยื้องด้วยช่องว่างเท่านั้น")
        content = _uncomment(line).rstrip()
        if not content.strip():
            continue
        column = len(content) - len(content.lstrip(" "))
        content = content.strip()
        if content.startswith(("---", "...")):
            raise SubsetError(f"บรรทัด {index}: เอกสารหลายชุดในไฟล์เดียว — นอกสับเซต")
        if content[0] in "&*!":
            raise SubsetError(f"บรรทัด {index}: anchor/alias/tag — นอกสับเซต")
        if BLOCK_SCALAR.search(content):
            while index < len(raw) and (
                not raw[index].strip() or len(raw[index]) - len(raw[index].lstrip(" ")) > column
            ):
                index += 1
            content = BLOCK_SCALAR.sub('""', content)
        while content.startswith("- ") or content == "-":
            out.append((column, "-"))
            rest = content[1:].lstrip(" ")
            if not rest:
                break
            column += len(content) - len(rest)
            content = rest
        else:
            out.append((column, content))
    return out


def _flow_value(text: str) -> tuple[object, str]:
    """ค่าเดี่ยวในรูป flow — คืน (ค่า, ส่วนที่เหลือ)"""
    text = text.lstrip()
    if text[:1] in ("[", "{"):
        return _flow(text)
    if text[:1] in ('"', "'"):
        quote = text[0]
        end = text.find(quote, 1)
        if end < 0:
            raise SubsetError(f"เครื่องหมายคำพูดไม่ปิด: {text!r}")
        return text[1:end], text[end + 1 :]
    end = 0
    while end < len(text):
        char = text[end]
        if char in ",]}" or (char == ":" and text[end + 1 : end + 2] in ("", " ")):
            break
        end += 1
    return text[:end].strip(), text[end:]


def _flow(text: str) -> tuple[object, str]:
    """`[a, b]` หรือ `{k: v}` — รูปเดียวที่ดัชนีใช้เขียนค่าสั้น ๆ ในบรรทัดเดียว"""
    closing = "]" if text[0] == "[" else "}"
    rest = text[1:].lstrip()
    items: list[object] = []
    mapping: dict[str, object] = {}
    if rest.startswith(closing):
        return (items if closing == "]" else mapping), rest[1:]
    while True:
        key, rest = _flow_value(rest)
        if closing == "]":
            items.append(key)
        else:
            rest = rest.lstrip()
            if not rest.startswith(":"):
                raise SubsetError(f"flow map ขาด ':' ที่ {rest!r}")
            value, rest = _flow_value(rest[1:])
            mapping[str(key)] = value
        rest = rest.lstrip()
        if rest.startswith(","):
            rest = rest[1:].lstrip()
            continue
        if rest.startswith(closing):
            return (items if closing == "]" else mapping), rest[1:]
        raise SubsetError(f"flow ปิดไม่ถูก ที่ {rest!r}")


def _scalar(raw: str) -> object:
    raw = raw.strip()
    if raw[:1] in ("[", "{"):
        value, rest = _flow(raw)
        if rest.strip():
            raise SubsetError(f"มีของเกินหลัง flow: {rest!r}")
        return value
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        return raw[1:-1]
    return raw


def _split_key(text: str) -> tuple[str, str]:
    quote = None
    depth = 0
    for index, char in enumerate(text):
        if quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
        elif char == ":" and depth == 0 and text[index + 1 : index + 2] in ("", " "):
            return str(_scalar(text[:index])), text[index + 1 :].strip()
    raise SubsetError(f"ไม่ใช่คู่คีย์: {text!r}")


def _is_key(text: str) -> bool:
    try:
        _split_key(text)
    except SubsetError:
        return False
    return True


def _parse(lines: list[tuple[int, str]], index: int, column: int) -> tuple[object, int]:
    if lines[index][1] == "-":
        return _parse_sequence(lines, index, column)
    if not _is_key(lines[index][1]):
        # scalar เดี่ยว ๆ (สมาชิกของรายการ เช่น `- tests/test_x.py`)
        return _scalar(lines[index][1]), index + 1
    return _parse_mapping(lines, index, column)


def _parse_sequence(lines, index, column):  # type: ignore[no-untyped-def]
    items: list[object] = []
    while index < len(lines) and lines[index][0] == column and lines[index][1] == "-":
        index += 1
        if index < len(lines) and lines[index][0] > column:
            value, index = _parse(lines, index, lines[index][0])
        else:
            value = None
        items.append(value)
    return items, index


def _parse_mapping(lines, index, column):  # type: ignore[no-untyped-def]
    mapping: dict[str, object] = {}
    while index < len(lines) and lines[index][0] == column and lines[index][1] != "-":
        key, raw = _split_key(lines[index][1])
        index += 1
        if raw:
            value: object = _scalar(raw)
        elif index < len(lines) and lines[index][0] > column:
            value, index = _parse(lines, index, lines[index][0])
        elif index < len(lines) and lines[index][0] == column and lines[index][1] == "-":
            value, index = _parse_sequence(lines, index, column)
        else:
            value = None
        mapping[key] = value
    return mapping, index


def load(text: str) -> object:
    """อ่าน YAML สับเซตที่ดัชนีกับ workflow ใช้ — ของนอกสับเซตต้อง raise"""
    lines = _significant(text)
    if not lines:
        return None
    value, index = _parse(lines, 0, lines[0][0])
    if index != len(lines):
        raise SubsetError(f"อ่านไม่จบ — การเยื้องไม่สม่ำเสมอที่ {lines[index][1]!r}")
    return value


def workflow_jobs(root: pathlib.Path) -> tuple[dict[str, list[str]], list[str]]:
    """job → ชื่อ step ที่ตั้งชื่อไว้ · พร้อมรายการไฟล์ที่อ่านไม่ออก"""
    jobs: dict[str, list[str]] = {}
    unreadable: list[str] = []
    for path in sorted((root / ".github" / "workflows").glob("*.y*ml")):
        try:
            workflow = load(path.read_text(encoding="utf-8"))
        except SubsetError as error:
            unreadable.append(f"{path.relative_to(root)}: {error}")
            continue
        if not isinstance(workflow, dict):
            unreadable.append(f"{path.relative_to(root)}: ไม่ใช่ mapping")
            continue
        for name, job in (workflow.get("jobs") or {}).items():
            steps = (job or {}).get("steps") or [] if isinstance(job, dict) else []
            jobs[str(name)] = [
                str(s["name"]) for s in steps if isinstance(s, dict) and s.get("name")
            ]
    return jobs, unreadable


def _gate_findings(gates: list[object]) -> tuple[list[str], list[dict]]:
    """คัดเฉพาะ gate ที่มีรูปถูกต้องออกมาใช้ต่อ — ที่เหลือรายงานเป็นสิ่งที่พบ"""
    findings: list[str] = []
    usable: list[dict] = []
    seen: set[str] = set()
    for gate in gates:
        if not isinstance(gate, dict):
            findings.append(f"แถวที่ไม่ใช่ mapping ในดัชนี: {gate!r}")
            continue
        gid = str(gate.get("id") or "")
        if not GATE_ID.match(gid):
            findings.append(f"id ไม่ใช่ kebab-case: {gid!r}")
            continue
        if gid in seen:
            findings.append(f"id ซ้ำ: {gid}")
            continue
        seen.add(gid)
        if not gate.get("title"):
            findings.append(f"{gid}: ไม่มี title")
        if gate.get("kind") not in KINDS:
            findings.append(f"{gid}: kind {gate.get('kind')!r} ไม่รู้จัก (ต้องเป็น {sorted(KINDS)})")
        if not isinstance(gate.get("enforced_by"), dict) or not gate["enforced_by"].get("job"):
            findings.append(f"{gid}: enforced_by ต้องบอก job ที่บังคับกฎนี้")
            continue
        usable.append(gate)
    return findings, usable


def _forward(gates: list[dict], jobs: dict[str, list[str]], root: pathlib.Path) -> list[str]:
    """ทิศไป: gate ชี้ไปหา job/step/ไฟล์ที่มีจริงไหม"""
    findings: list[str] = []
    for gate in gates:
        gid, enforced = gate["id"], gate["enforced_by"]
        job = str(enforced["job"])
        if job not in jobs:
            findings.append(f"{gid}: ชี้ไปหา job {job!r} ที่ไม่มีใน workflow")
        elif gate["kind"] == "step":
            step = enforced.get("step")
            if not step or str(step) not in jobs[job]:
                findings.append(f"{gid}: ไม่มี step {step!r} ใน job {job!r}")
        elif gate["kind"] == "test":
            files = enforced.get("tests") or []
            if not isinstance(files, list) or not files:
                findings.append(f"{gid}: kind test ต้องมีรายชื่อไฟล์เทสต์")
            else:
                findings += [
                    f"{gid}: ไม่มีไฟล์ {name}" for name in files if not (root / str(name)).is_file()
                ]
    return findings


def _partition(gates: list[dict], root: pathlib.Path, tests_dir: pathlib.Path) -> list[str]:
    """ทิศกลับ (เทสต์): ไฟล์เทสต์ทุกไฟล์ถูกตัดสิน และถูกตัดสินโดย gate เดียว"""
    if not tests_dir.is_dir():
        return []
    claims: dict[str, list[str]] = {}
    for gate in gates:
        for name in gate["enforced_by"].get("tests") or []:
            claims.setdefault(str(name), []).append(gate["id"])

    prefix = tests_dir.relative_to(root).as_posix()
    on_disk = {f"{prefix}/{path.name}" for path in tests_dir.glob("test_*.py")}
    findings = [
        f"ไฟล์เทสต์ที่ยังไม่ถูกตัดสินว่าเป็นของ gate ไหน: {name}" for name in sorted(on_disk - claims.keys())
    ]
    findings += [f"ดัชนีอ้างไฟล์ที่ไม่มีแล้ว: {name}" for name in sorted(claims.keys() - on_disk)]
    findings += [
        f"partition แตก — {name} ถูกอ้างโดย {sorted(owners)}"
        for name, owners in sorted(claims.items())
        if len(owners) > 1
    ]
    return findings


def _read_registry(registry: pathlib.Path) -> tuple[list[str], list[object]]:
    """อ่านดัชนี — อ่านไม่ออกหรือรูปผิดคือสิ่งที่พบ ไม่ใช่ข้ออ้างให้ข้าม"""
    try:
        document = load(registry.read_text(encoding="utf-8"))
    except SubsetError as error:
        return [f"{registry.name} อ่านไม่ออก — {error}"], []
    if not isinstance(document, dict) or not isinstance(document.get("gates"), list):
        return [f"{registry.name} ต้องมีคีย์ `gates` ที่เป็นรายการ"], []
    return [], document["gates"]


def main(root: pathlib.Path) -> int:
    config_path = root / "scaffold.json"
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.is_file() else {}
    declared = config.get("gates_path", "gates.yaml")
    registry = root / declared
    if not registry.is_file():
        print(f"NA: ไม่มี {declared} — ยังไม่มีดัชนีให้ตรวจ")
        return 0

    findings, rows = _read_registry(registry)
    if not findings:
        shape, gates = _gate_findings(rows)
        findings += shape
        if not gates and not shape:
            findings.append(f"{registry.name} ไม่มี gate สักตัว — ดัชนีที่ว่างไม่บังคับอะไรเลย")

        jobs, unreadable = workflow_jobs(root)
        findings += [f"workflow อ่านไม่ออก — {problem}" for problem in unreadable]
        findings += _forward(gates, jobs, root)

        covered = {str(gate["enforced_by"]["job"]) for gate in gates}
        findings += [
            f"job ที่ไม่มี gate ในดัชนี: {job} — เพิ่ม gate ให้มัน" for job in sorted(set(jobs) - covered)
        ]
        findings += _partition(gates, root, root / config.get("tests_path", "tests"))

    for finding in findings:
        print(f"gates-registry-total: {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("ใช้: scan_gates_registry.py <root>", file=sys.stderr)
        sys.exit(2)
    sys.exit(main(pathlib.Path(sys.argv[1]).resolve()))
