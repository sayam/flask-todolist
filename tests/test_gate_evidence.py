"""ทุก gate ที่เพิ่มใหม่ต้องมาพร้อมหลักฐานว่า "แดงเมื่อควรแดง" — ADR 0059

audit governance รอบ 6 วัดจาก 200 run ล่าสุดแล้วได้ตัวเลขที่ตอบไม่ได้: **21 job
ไม่เคยแดงเลยสักครั้ง** ซึ่งจากภายนอกแยกไม่ออกระหว่าง "ของดีจริงจึงไม่แดง" กับ
"ด่านนั้นไม่ได้ตรวจอะไร" — และคำตอบของสองอย่างนี้ต่างกันคนละขั้ว

ที่นี่จึงบังคับให้ดัชนี**เก็บหลักฐานตอนที่มันเกิด** ไม่ใช่ตอนที่ต้องใช้:

- `kind: ci-red` — ด่านแดงเองใน CI ตอนของเสียจริง (`ref: run/<id>` · ตรวจซ้ำได้
  ด้วย `gh run view <id> --log-failed`) · เป็นหลักฐานที่แข็งกว่าเพราะไม่มีใครจัดฉาก
- `kind: mutation` — แดงตอนพังโค้ดโดยตั้งใจตอนเขียนด่าน (`ref: pr/<number>`)
  ซึ่งเป็นวินัยของโปรเจกต์อยู่แล้ว แค่ไม่เคยถูกเก็บไว้ให้ค้นได้

`UNPROVEN` คือ gate ที่มีอยู่ก่อนกติกานี้และยังไม่มีหลักฐาน — **หดได้ทางเดียว**
(ratchet แบบเดียวกับ `UNASSESSED_CEILING` ของ ASVS): พิสูจน์ตัวไหนได้ให้ย้าย
หลักฐานเข้า `gates.yaml` แล้วถอดชื่อออกจากที่นี่ · ห้ามเติมชื่อใหม่เข้าไปแทน
การพิสูจน์ — gate ใหม่ที่ยังไม่เคยเห็นแดงคือ gate ที่ยังไม่รู้ว่าตรวจอะไร
"""

import datetime
import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
GATES = ROOT / "gates.yaml"

FIELDS = {"kind", "ref", "date", "caught"}
# ชนิดของหลักฐาน → รูปของ ref ที่ตามหาต้นทางได้จริง
REF_SHAPE = {"ci-red": re.compile(r"^run/\d+$"), "mutation": re.compile(r"^pr/\d+$")}

# gate ที่เกิดก่อน ADR 0059 และยังไม่มีหลักฐานว่าเคยแดง — **รายการนี้หดได้ทางเดียว**
UNPROVEN = frozenset(
    {
        "skill-mirrors-portable-gates",
        "logic-knows-no-http",
        "delete-means-soft-delete",
        "every-write-audited",
        "core-never-names-plugins",
        "every-column-classified",
        "every-column-export-decided",
        "models-match-migrations",
        "dialect-discipline",
        "migration-class-declared",
        "csrf-guards-every-form",
        "session-hardening",
        "login-rate-limited-two-ways",
        "authz-in-service-layer",
        "password-policy-nist",
        "logs-carry-no-pii",
        "csp-no-inline",
        "config-fails-loud",
        "no-debug-entrypoint",
        "api-contract-snapshot",
        "api-fuzzed-from-spec",
        "fk-enforced-measured",
        "a11y-structural",
        "i18n-catalog-integrity",
        "asvs-evidence-real",
        "adr-index-complete",
        "cadence-not-overdue",
        "ropa-current",
        "architecture-description-current",
        "metrics-correct-across-workers",
        "risk-method-and-register-current",
        "backup-restore-drilled-every-push",
        "country-compliance-indexed",
        "iso27001-worksheet-honest",
        "agent-skill-package-derived",
        "design-doc-matches-the-ui",
        "admin-masking-by-classification",
        "admin-panels-read-real-state",
        "secrets-encrypted-at-rest",
        "legal-pdpa-worksheet-honest",
        "licensing-no-copyleft",
        "security-policy-consistent",
        "actions-sha-pinned",
        "image-digest-pinned",
        "ci-tools-hash-pinned",
        "pins-exceptions-honest",
        "semgrep-scope-proven",
        "dependabot-fits-the-gates",
        "app-behavior-suite",
        "n-minus-one-served",
        "codeql-can-parse-the-app",
        "schema-drift-zero",
        "openapi-regen-clean",
        "conventional-commits",
        "core-deps-cve-audit",
        "deploy-deps-cve-audit",
        "ci-tools-cve-audit",
        "a11y-real-browser",
        "image-built-and-probed",
        "image-exceptions-honest",
        "perf-regression-tripwire",
        "tls-modern-protocols-only",
        "tls-forward-secrecy",
        "oidc-end-to-end",
        "ldap-end-to-end",
        "vault-end-to-end",
        "push-secret-scan",
        "sbom-per-category",
        "codeql-sast",
        "scaffold-installs-and-runs",
        "openssf-scorecard",
    }
)
# เพดานของรายการข้างบน ณ วันที่กติกาเริ่ม (ADR 0059) — ขยับลงได้อย่างเดียว
UNPROVEN_CEILING = 74


@pytest.fixture(scope="module")
def gates() -> list[dict]:
    return yaml.safe_load(GATES.read_text(encoding="utf-8"))["gates"]


# **runner ของ CI เดินตาม UTC ส่วนคนเขียนไม่ได้เดินตาม** — วันที่ที่ถูกต้อง
# ตามปฏิทินของผู้เขียน (UTC+7) เป็น "อนาคต" ในสายตา runner ตลอดเจ็ดชั่วโมงแรก
# ของทุกวัน · เจอจริงตอน PR ของ audit รอบ 17 ซึ่งแดงด้วยเรื่องที่ไม่เกี่ยวกับ
# เนื้อ PR เลย · โซนเวลาบนโลกอยู่ในช่วง UTC-12..UTC+14 ทั้งหมด **หนึ่งวัน**
# จึงเป็นระยะที่พอดี ไม่ใช่การผ่อนเกณฑ์: การลงวันที่ล่วงหน้าจริง ๆ ยังถูกจับ
CLOCK_SKEW = datetime.timedelta(days=1)


def _latest_allowed() -> datetime.date:
    """วันที่ล่าสุดที่หลักฐานลงได้ — วันนี้ตาม UTC บวกระยะของโซนเวลา"""
    return datetime.datetime.now(datetime.UTC).date() + CLOCK_SKEW


def _problems_with(item: object) -> list[str]:
    """ตรวจหลักฐานหนึ่งรายการ — คืนรายการปัญหา (ว่าง = ใช้ได้)"""
    if not isinstance(item, dict) or set(item) != FIELDS:
        return [f"แต่ละรายการต้องมีคีย์ครบพอดี {sorted(FIELDS)} — ได้ {item}"]

    found = []
    shape = REF_SHAPE.get(item["kind"])
    if shape is None:
        found.append(f"kind {item['kind']!r} ไม่รู้จัก (ต้องเป็น {sorted(REF_SHAPE)})")
    elif not shape.match(str(item["ref"])):
        found.append(f"ref {item['ref']!r} ไม่ตรงรูปของ {item['kind']}")

    try:
        when = datetime.date.fromisoformat(str(item["date"]))
    except ValueError:
        found.append(f"date {item['date']!r} ไม่ใช่ YYYY-MM-DD")
    else:
        if when > _latest_allowed():
            found.append(f"date {when} อยู่ในอนาคต")

    if len(str(item["caught"]).strip()) < 20:
        found.append(f"caught สั้นเกินกว่าจะบอกว่าจับอะไรได้ — {item['caught']!r}")
    return found


def test_every_piece_of_evidence_is_wellformed(gates):
    """หลักฐานที่ตามกลับไปดูของจริงไม่ได้ ก็เป็นแค่คำกล่าวอ้างอีกบรรทัด"""
    broken = []
    for gate in gates:
        evidence = gate.get("proved_by")
        if evidence is None:
            continue
        gid = gate["id"]
        if not isinstance(evidence, list) or not evidence:
            broken.append(f"{gid}: proved_by ต้องเป็น list ที่ไม่ว่าง")
            continue
        broken += [f"{gid}: {problem}" for item in evidence for problem in _problems_with(item)]
    assert not broken, "\n  ".join(["หลักฐานที่ใช้ไม่ได้:", *broken])


def _evidence(**overrides: object) -> dict:
    """หลักฐานที่ใช้ได้หนึ่งชิ้น — ผู้เรียกแก้เฉพาะช่องที่อยากให้ผิด"""
    return {
        "kind": "mutation",
        "ref": "pr/1",
        "date": "2026-08-01",
        "caught": "พังโค้ดที่ด่านนี้อ้างว่าคุ้ม แล้วมันแดงจริง",
        **overrides,
    }


def test_evidence_dated_in_the_future_is_rejected():
    """ลงวันที่ล่วงหน้า = อ้างการพิสูจน์ที่ยังไม่เกิด — ต้องจับได้"""
    ahead = datetime.datetime.now(datetime.UTC).date() + datetime.timedelta(days=5)

    assert _problems_with(_evidence(date=ahead.isoformat())), f"ปล่อยวันที่ {ahead} ผ่าน"


def test_the_authors_calendar_day_is_not_treated_as_the_future():
    """runner เดินตาม UTC ส่วนคนเขียนอยู่ UTC+7 — วันนี้ของเขาต้องไม่ถูกปฏิเสธ

    เจอจริง: PR ของรอบ 17 แดงเพราะหลักฐานลงวันที่ตามปฏิทินไทย ซึ่ง runner
    ยังนับเป็นพรุ่งนี้ · ด่านที่แดงด้วยเรื่องที่ไม่เกี่ยวกับ PR คือด่านที่คนจะ
    เรียนรู้ที่จะข้าม
    """
    theirs = datetime.datetime.now(datetime.UTC).date() + datetime.timedelta(days=1)

    assert _problems_with(_evidence(date=theirs.isoformat())) == []


def test_a_gate_without_evidence_must_be_on_the_declared_list(gates):
    """gate ใหม่ต้องมาพร้อมหลักฐาน — ไม่ใช่มาพร้อมความตั้งใจว่าจะพิสูจน์ทีหลัง"""
    silent = sorted(g["id"] for g in gates if not g.get("proved_by") and g["id"] not in UNPROVEN)
    assert not silent, (
        f"gate ที่ไม่มี proved_by และไม่ได้อยู่ในรายการที่ยกไว้: {silent}\n"
        "เพิ่ม proved_by ใน gates.yaml (ci-red จาก run จริง หรือ mutation ตอนเขียนด่าน) — "
        "การเติมชื่อลง UNPROVEN แทนการพิสูจน์คือการยกเลิกกติกาข้อนี้"
    )


def test_the_declared_list_has_no_ghosts_and_no_settled_rows(gates):
    """สองทิศ: ชื่อในรายการต้องมีจริง และตัวที่พิสูจน์แล้วต้องถูกถอดออก

    รายการยกเว้นที่ไม่มีใครถอด จะกลายเป็นตัวปิดของจริงในวันหนึ่ง — หลักเดียวกับ
    `pins/accepted-advisories.txt` ที่ ID ซึ่งไม่โผล่แล้วก็แดงเหมือนกัน
    """
    ids = {g["id"] for g in gates}
    proved = {g["id"] for g in gates if g.get("proved_by")}

    ghosts = sorted(UNPROVEN - ids)
    assert not ghosts, f"UNPROVEN อ้าง gate ที่ไม่มีแล้ว: {ghosts}"

    settled = sorted(UNPROVEN & proved)
    assert not settled, (
        f"gate ที่มีหลักฐานแล้วแต่ยังค้างใน UNPROVEN: {settled}\nถอดชื่อออกจากรายการใน {__file__}"
    )


def test_the_unproven_list_only_shrinks():
    """ratchet — เพดานขยับลงได้อย่างเดียว เหมือน threshold ตัวอื่นของ repo นี้"""
    assert len(UNPROVEN) <= UNPROVEN_CEILING, (
        f"รายการ gate ที่ยังไม่มีหลักฐานโตขึ้น ({len(UNPROVEN)} > {UNPROVEN_CEILING}) — "
        "ทางที่ถูกคือพิสูจน์ ไม่ใช่ขยายเพดาน"
    )
