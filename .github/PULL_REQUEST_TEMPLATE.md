<!-- ถ้านี่เป็น PR แรกของคุณจากภายนอก: check จะยังไม่รันจนกว่าผู้ดูแลจะอนุมัติ
     (ตั้งใจของ GitHub ไม่ใช่ความผิดของคุณ) · ระหว่างรอ รัน
     `pipenv run python scripts/preflight.py` บนเครื่องได้เลย ซึ่งเดินด่านชุดเดียวกัน
     — เหตุผลเต็มอยู่ใน CONTRIBUTING.md หัวข้อ "What you will see after you push" -->

## What this fixes, and how it would break without it
<!-- แก้อะไร และถ้าไม่แก้จะพังอย่างไร — diff อธิบายตัวเองได้ แต่ความพังที่มันกันไว้อธิบายตัวเองไม่ได้ -->

## Checklist

- [ ] New tests are mutation-tested — broke the code, watched them go red, restored (CONTRIBUTING rule 1)
- [ ] New test files are registered in `gates.yaml` (CONTRIBUTING rule 8)
- [ ] Generated files were regenerated, not hand-edited (CONTRIBUTING rule 5)
- [ ] Commit subjects are Conventional Commits, ≤72 chars
- [ ] Decisions that close off alternatives have an ADR
