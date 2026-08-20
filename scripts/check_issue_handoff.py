"""issue ที่ติดป้าย `good first issue` ต้องไม่ถูกผู้ดูแลหยิบไปทำเงียบ ๆ

**เกิดจากเหตุจริง 2026-08-20**: issue ถูกสร้างพร้อมป้าย good first issue เวลา
12:14Z · ผู้ดูแลเปิด PR ของตัวเองทำ issue เดียวกัน 16:40Z · merge 16:51Z ·
ผู้ร่วมพัฒนาจากภายนอกเปิด PR ของเขา 17:39Z โดยลงมือมาก่อนหน้านั้นหลายชั่วโมง
· ป้ายยังติดอยู่ตลอดเวลา ไม่มีการ assign ไม่มีคอมเมนต์ว่ามีคนทำอยู่ — เขาจึง
ไม่มีทางรู้ และเสียเวลาไปทั้งบ่ายกับงานที่ปิดไปแล้ว

กฎที่ตามมาถูกเขียนไว้ใน `CONTRIBUTING.md` · ตัวนี้คือเครื่องที่บังคับมัน เพราะ
คำสัญญาที่อยู่ในคอมเมนต์ของ PR ที่ปิดไปแล้ว คือคำสัญญาที่ไม่มีใครหาเจออีก
(บทเรียนซ้ำของ repo นี้: `--delete-branch` อยู่ในเอกสารสองวันครึ่งโดยไม่มีผล)

**ไม่ได้ห้ามผู้ดูแลทำเอง** — ห้าม*ทำเงียบ ๆ* · ปลดป้ายออกก่อนคือทางที่ถูก
และถ้าตั้งใจทำทั้งที่ป้ายยังอยู่ ให้ประกาศในเนื้อ PR ด้วยบรรทัดที่เครื่องอ่านได้

บทบาท: decider — ตัดสินผ่าน/ไม่ผ่านให้ job `lint` และคืน exit code ที่บล็อก PR ได้
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

# บรรทัดประกาศในเนื้อ PR ที่ปลดด่านนี้ — ต้องมีเหตุผลต่อท้าย ไม่ใช่แค่คำสั่งเปล่า
OVERRIDE = re.compile(r"^good-first-issue-taken-back:\s*(?P<reason>.+\S.*)$", re.MULTILINE)
LABEL = "good first issue"
TOOL_TIMEOUT_SECONDS = 60


def _gh(*args: str) -> str:
    """เรียก `gh` แล้วคืน stdout — ล้มเหลวคือความล้มเหลวของด่าน ไม่ใช่ของ PR"""
    return subprocess.run(  # noqa: S603 — argument คงที่ + ไม่มี shell
        ["gh", *args],  # noqa: S607 — gh มาจาก PATH ของ runner โดยตั้งใจ
        capture_output=True,
        text=True,
        check=True,
        timeout=TOOL_TIMEOUT_SECONDS,
    ).stdout


def closing_issues(pull_request: str) -> list[dict]:
    """issue ที่ PR นี้จะปิด — อ่านจาก GitHub ไม่ใช่จากการเดาข้อความ

    `closingIssuesReferences` คือสิ่งที่ GitHub *จะทำจริง* ตอน merge ซึ่งต่างจาก
    การ grep หาคำว่า "Closes #N" ในเนื้อ PR: คำนั้นอยู่ในคอมเมนต์หรือใน commit
    ก็ได้ และเขียนผิดรูปก็ไม่ปิด — ด่านที่อ่านคนละอย่างกับที่แพลตฟอร์มทำ คือด่าน
    ที่ตอบถูกเฉพาะตอนที่ทั้งสองอย่างบังเอิญตรงกัน
    """
    raw = _gh("pr", "view", pull_request, "--json", "closingIssuesReferences")
    return list(json.loads(raw)["closingIssuesReferences"])


def labels_of(issue_number: int) -> set[str]:
    raw = _gh("issue", "view", str(issue_number), "--json", "labels")
    return {label["name"] for label in json.loads(raw)["labels"]}


def problems(closing: list[dict], labelled: dict[int, set[str]], body: str) -> list[str]:
    """คืนรายการปัญหา — ว่างแปลว่าผ่าน · ตรรกะล้วน ไม่แตะเครือข่าย จึงเทสต์ได้"""
    if OVERRIDE.search(body or ""):
        return []
    return [
        f"PR นี้จะปิด #{issue['number']} ({issue['title']}) ซึ่งยังติดป้าย {LABEL!r} อยู่"
        for issue in closing
        if LABEL in labelled.get(issue["number"], set())
    ]


def report(found: list[str]) -> str:
    """ข้อความตอนแดง — ต้องบอกทางออกทั้งสองทาง ไม่ใช่แค่บอกว่าผิด"""
    return "\n".join(
        [
            "issue ที่เปิดไว้ให้คนใหม่ กำลังถูกปิดโดยไม่ได้ปลดป้ายก่อน:",
            *(f"  - {line}" for line in found),
            "",
            "ทางที่ถูกมีสองทาง เลือกอย่างใดอย่างหนึ่ง:",
            f"  1. ปลดป้าย {LABEL!r} ออกจาก issue นั้นก่อน แล้วคอมเมนต์บอกว่ากำลังทำเอง",
            "  2. ถ้าตั้งใจทำทั้งที่ป้ายยังอยู่ ให้เขียนบรรทัดนี้ในเนื้อ PR:",
            "       good-first-issue-taken-back: <เหตุผล>",
            "",
            "ป้ายที่ยังติดอยู่คือคำเชิญที่ยังส่งอยู่ — คนที่รับคำเชิญไปแล้วลงมือทำ",
            "จะรู้ตัวก็ต่อเมื่องานของเขาถูกปิดไปแล้ว (เกิดขึ้นจริง 2026-08-20)",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", default=os.environ.get("PR_NUMBER", ""))
    parser.add_argument("--body", default=os.environ.get("PR_BODY", ""))
    args = parser.parse_args(argv)

    if not args.pr:
        print("ไม่มีหมายเลข PR — ด่านนี้มีความหมายเฉพาะบน pull_request")
        return 0

    closing = closing_issues(args.pr)
    if not closing:
        print("PR นี้ไม่ได้ปิด issue ไหน")
        return 0

    labelled = {issue["number"]: labels_of(issue["number"]) for issue in closing}
    found = problems(closing, labelled, args.body)
    if found:
        print(report(found), file=sys.stderr)
        return 1

    closed = " ".join(f"#{issue['number']}" for issue in closing)
    print(f"ปิด {closed} — ไม่มีใบไหนติดป้าย {LABEL!r} ค้างอยู่")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
