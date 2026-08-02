# 0009 — ชุดเครื่องมือ quality gate (Phase 0)

สถานะ: accepted (2026-08-03)

**บริบท:** ต้องการ gate อัตโนมัติก่อนเริ่มเฟสถัดไป (ดู docs/STANDARDS.md)
**คำตัดสิน:**
- ruff `select=ALL` + ignore รายข้อพร้อมเหตุผลใน pyproject / ruff format
- mypy โหมด gradual: ทั้งแอปหลวม + strict list (`tz`, `filters`, `plugins`,
  `sun_data`) ขยายจนครบใน Phase 2 — ty/pyrefly ยัง beta เป็น watch list
- threshold แบบ **ratchet จากค่าวัดจริง**: coverage(branch) ≥92, interrogate ≥49,
  xenon B/A/A — ขยับขึ้นได้อย่างเดียว ห้ามลด
- semgrep `p/flask`+`p/python` (CI), pip-audit, gitleaks, SBOM (CycloneDX)
- pre-commit เป็น local hooks เรียก venv ของ pipenv — เวอร์ชันเดียวกับ lock
- **ไม่ใช้ gitlint**: pin click ชนกับ Flask ecosystem (lock ไม่ได้) →
  `scripts/lint_commits.py` แทน / **ไม่ใช้ CodeQL**: repo private ต้องจ่าย GHAS
**ผล:** push ที่ทำเทสต์แดง/coverage ตก/CVE ใหม่/complexity เกิน ถูกจับใน CI
ข้อจำกัดที่ยอมรับ: push ตรงเข้า main ทำให้ gate ทำงานหลัง push — วินัยฝั่งเครื่อง
คือ pre-commit + รันเทสต์ก่อน push (ถ้ามีผู้ร่วมพัฒนาเพิ่มต้องเปิด branch protection)
