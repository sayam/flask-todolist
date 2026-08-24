# ผิวนอกรีโป — สิ่งที่เราพูดกับโลกภายนอก และใครเทียบมันกับของจริง

ทะเบียนนี้เกิดจาก **audit รอบ 24** ([AUDIT-LOG.md](AUDIT-LOG.md)) ซึ่งถามคำถามที่
ยี่สิบสามรอบก่อนไม่เคยถาม: *ผิวที่อยู่นอกการควบคุมเวอร์ชันทั้งหมดมีอะไรบ้าง*
— ก่อนหน้านี้ผิวเหล่านี้ถูกตรวจเป็นรายชิ้นตอนที่มีใครสังเกตเห็นเท่านั้น และ
ตอนที่ไปนับจริงพบว่ามีสำเนาของข้อเท็จจริงเดียวกันค้างอยู่พร้อมกันได้สามที่
โดยไม่มีด่านไหนเห็น

**กติกาของทะเบียนนี้มีข้อเดียว**: ทุกแถวต้องบอกว่า *ใครเทียบมันกับของจริง* และ
คำตอบต้องเป็นหนึ่งในสี่รูปเท่านั้น — `ci:posture` · `tests/<ไฟล์>` ·
`cadence:<หัวข้อในตารางรอบตรวจ>` · หรือ **`ยังไม่มีใคร`** ที่เขียนออกมาตรง ๆ
· รูปสุดท้ายมีเพดานใน `pyproject.toml` ที่โตไม่ได้ (`tests/test_external_surface.py`)
เพราะ *"ยังไม่มีใคร" ที่ไม่มีใครนับ* จะกลายเป็นค่าเริ่มต้นเงียบ ๆ ของทุกฟิลด์ใหม่

`tests/test_external_surface.py` บังคับสองทิศกับ `scripts/audit_posture.py`:
ฟิลด์ที่ตัวตรวจอ่านต้องมีแถวที่นี่ และแถวที่อ้างว่า `ci:posture` ตรวจให้ ต้องเป็น
ฟิลด์ที่ตัวตรวจอ่านจริง — ทะเบียนที่ drift จากตัวตรวจคือทะเบียนที่อ่านแล้วเข้าใจผิด

## GitHub — branch protection ของ `main`

| ฟิลด์ | ค่าที่ควรเป็น | ใครเทียบ |
|---|---|---|
| `required_checks` | ครบทุก job ที่รันบน pull request (สามทิศ — ADR 0061) | `ci:posture` |
| `enforce_admins` | `true` — ADR 0053 | `ci:posture` |
| `required_linear_history` | `true` | `ci:posture` |
| `allow_force_pushes` | `false` | `ci:posture` |
| `allow_deletions` | `false` | `ci:posture` |
| `strict` (ต้อง rebase ก่อน merge) | `false` โดยตั้งใจ — auto-merge จะวน rebase ทุกครั้งที่ main ขยับ | ยังไม่มีใคร |
| `required_pull_request_reviews` | 0 คน — ผู้ดูแลคนเดียว (ADR 0053) ด่านที่บังคับจริงคือ required check | ยังไม่มีใคร |
| `required_signatures` | `false` — เลื่อนไว้พร้อมเงื่อนไขใน ADR 0058 | ยังไม่มีใคร |
| `lock_branch` · `block_creations` | `false` ทั้งคู่ | ยังไม่มีใคร |

## GitHub — สวิตช์ระดับ repo

| ฟิลด์ | ค่าที่ควรเป็น | ใครเทียบ |
|---|---|---|
| `allow_auto_merge` | `true` (CONTRIBUTING ข้อ 7) | `ci:posture` · `cadence:allow_auto_merge` |
| `allow_squash_merge` | `false` | `ci:posture` |
| `allow_merge_commit` | `false` | `ci:posture` |
| `allow_rebase_merge` | `true` | `ci:posture` |
| `delete_branch_on_merge` | `true` | `ci:posture` |
| `description` (ช่อง About) | เลขรุ่น + สี่ตัวเลขที่นับจากดิสก์ได้ — **ซิงก์สามเลขกับรุ่นด้วย `scripts/sync_counts.py --about --write` ได้แล้ว** (audit รอบ 26) ส่วน `required checks` ยังเป็นงานมือเพราะนับจากดิสก์ไม่ได้ | `ci:posture` |
| `homepage` | ชี้ release ล่าสุด | ยังไม่มีใคร |
| `topics` | 8 คำ | ยังไม่มีใคร |
| `has_wiki` · `has_projects` | เปิดอยู่ทั้งคู่และไม่มีเนื้อ — พื้นผิวเอกสารที่อยู่นอก git ทั้งหมด | ยังไม่มีใคร |
| `has_discussions` · `web_commit_signoff_required` | `false` ทั้งคู่ | ยังไม่มีใคร |

## GitHub — Actions

| ฟิลด์ | ค่าที่ควรเป็น | ใครเทียบ |
|---|---|---|
| `sha_pinning_required` | `true` — แพลตฟอร์มบังคับสิ่งที่ `gate actions-sha-pinned` บังคับอยู่แล้ว | `ci:posture` |
| `default_workflow_permissions` | `read` — เหตุผลเดียวกับที่ทุก workflow ประกาศ `permissions:` เอง | `ci:posture` |
| `can_approve_pull_request_reviews` | `false` — GITHUB_TOKEN อนุมัติ PR ของตัวเองไม่ได้ | `ci:posture` |
| `allowed_actions` | `all` — เราตรึงด้วย SHA เองอยู่แล้ว จึงไม่พึ่งรายการของแพลตฟอร์ม | ยังไม่มีใคร |
| artifact & log retention | 90 วัน (เพดานของแผน) — **หลักฐาน `kind: ci-red` ของ gate อ่านไม่ได้หลังพ้นระยะนี้** | `cadence:หลักฐานของ gate ที่ชี้ไปที่ run` |

## GitHub — หน้า Security

| ฟิลด์ | ค่าที่ควรเป็น | ใครเทียบ |
|---|---|---|
| `alerts` ของ code scanning | ทุกใบต้องมีบรรทัดใน `.github/accepted-code-scanning-alerts.txt` (สองทิศ) | `ci:posture` |
| `secret_scanning` · `secret_scanning_push_protection` | เปิดทั้งคู่ | ยังไม่มีใคร |
| `secret_scanning_non_provider_patterns` · `secret_scanning_validity_checks` | **ปิดอยู่ทั้งคู่** — ยังไม่มีที่ไหนบันทึกว่าปิดโดยตั้งใจหรือโดยค่าเริ่มต้น | ยังไม่มีใคร |
| `dependabot_security_updates` · vulnerability alerts | เปิดทั้งคู่ | ยังไม่มีใคร |
| private vulnerability reporting | เปิด — `SECURITY.md` อ้างถึงมัน | ยังไม่มีใคร |

## GitHub — วัตถุที่ไม่ใช่ setting

| วัตถุ | สถานะวันนี้ | ใครเทียบ |
|---|---|---|
| secret `POSTURE_TOKEN` | fine-grained PAT อ่านอย่างเดียว หมดอายุ 2026-11-16 | `cadence:POSTURE_TOKEN` |
| webhook → Zenodo | 1 ใบ active · token ฝังอยู่ใน query string ของ URL · หมุนผ่านหน้าเว็บไม่ได้ | ยังไม่มีใคร |
| label (13 ใบ) | `.github/ISSUE_TEMPLATE/*` อ้าง `bug` และ `enhancement` · Dependabot อ้างอีกสาม | ยังไม่มีใคร |
| collaborator | 1 คน (เจ้าของ) | `cadence:hardening ของบัญชีเจ้าของ` |
| ruleset · environment · deploy key · GitHub Pages | ไม่มีเลยสักอัน — ท่าทีทั้งหมดอยู่ที่ branch protection แบบเก่า | ยังไม่มีใคร |
| repo `sayam/verifiable-gates` (placeholder — ADR 0075 ข้อ 6) | public · README บอกว่ายังไม่มีโค้ด · Apache-2.0 + CLA · CC BY 4.0 · ยังไม่มี branch protection/posture ของตัวเอง | ยังไม่มีใคร |
| หัวเรื่องของ issue ที่เปิดให้คนนอก | #186 โฆษณาเลข 48 ซึ่งลอกมาจาก `suppressions_without_reason` ใน `pyproject.toml` — เลขนั้นเป็น ratchet ที่ออกแบบมาให้*ลด* | ยังไม่มีใคร |

## บริการภายนอกที่ตีพิมพ์แทนเรา

| ผิว | สิ่งที่มันถือ | ใครเทียบ |
|---|---|---|
| ระเบียน Zenodo ของแต่ละรุ่น | ชื่อ · บทคัดย่อ · สัญญาอนุญาต · ผู้แต่ง · คำสำคัญ — อ่านจาก `.zenodo.json` + `CITATION.cff` ตอน archive — ด่านอยู่ที่**ต้นทาง** เพราะปลายทางแก้ไม่ได้ | `tests/test_identity_cards.py` |
| DOI ที่ `README.md` พิมพ์ | ต้องเป็นตัวเดียวกับที่ `CITATION.cff` ประกาศ | `tests/test_contributor_docs.py` |
| ระเบียนที่ตีพิมพ์ไปแล้ว | **แก้ย้อนหลังไม่ได้** — v2.2.0 ยังบอกจำนวนรอบ audit ไว้ผิดจนถึงรุ่นถัดไป | ยังไม่มีใคร |
| ใบตอบ badge บน bestpractices.dev | ~122 ช่อง + `description` ที่เป็นสำเนาของช่อง About | `cadence:bestpractices.dev` |
| รูป badge ที่ camo ของ GitHub ดึง | โฮสต์ต้องอยู่ในรายการที่วัดแล้วว่า camo ดึงไหว | `tests/test_contributor_docs.py` |
