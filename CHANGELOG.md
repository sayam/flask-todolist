# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> This file is in English only, unlike `README.md` and `SECURITY.md` which are
> bilingual. A changelog grows with every release, so a translated copy would be
> the first thing to fall behind — and a changelog that is behind is worse than
> one that is missing. เหตุผลของการตัดสินใจแต่ละเรื่องอยู่ใน
> [`docs/adr/`](docs/adr/) ซึ่งเป็นภาษาไทย

**What counts as a breaking change here:** removing or renaming anything in the
`/api/v1` contract, changing a response status code or the meaning of an error
`code`, dropping a CLI command, or a migration that cannot be applied to an
existing database. Adding fields, endpoints, or query parameters with defaults is
not breaking — see [ADR 0018](docs/adr/0018-api-v1-contract-and-versioning.md).

## [Unreleased]

### Added

- **Gates now carry proof that they have been red** — `proved_by` in
  `gates.yaml` (ADR 0059), the round-6 audit's finding: measuring 200 CI
  runs showed 9 jobs have failed at least once and **21 have never failed
  at all**, which from outside is indistinguishable between "nothing was
  ever broken" and "this gate checks nothing". Each entry records how the
  gate was proven (`ci-red` with a run id, or `mutation` with a PR),
  when, and *what it caught*. Gates that predate the rule sit in an
  `UNPROVEN` list that only shrinks; new gates arrive with evidence.
  Fourteen gates carry real evidence already — including the day the
  image scanner caught `CVE-2026-53615`, the release signer catching its
  own over-wide glob, and one `/readyz` bug turning `stack`, `siem`, and
  `dast` red at once.
- **Documentation swept after the round-7 batch** — six places still
  described a mechanism that same day's work had changed (`preflight`
  reading only `ci.yml`, the overlay shipping only checkers) and five
  more advertised 28 or 29 checks where CI now produces 30, including
  two ISO evidence rows. ADR 0060 carries a note pointing at 0063 rather
  than being edited in place, and `CLAUDE.md` no longer repeats "21 jobs
  never failed" without saying that figure came from a method blind to
  reruns. The audit rounds are now recorded in
  `docs/ROADMAP-GOVERNANCE.md`: plan G closed in August and every piece
  of governance work since has come from a round that asked a question
  the previous one could not — no document said so until now.

- **The overlay ships the tool, not just the rule** — `preflight.py`
  now travels with `overlays/flask/` (ADR 0063). The rule that a
  developer harness must report honestly has been baseline — exportable
  — since it was written, while the tool that makes following it easy
  stayed here, which in practice means nobody downstream would have one.
  The shipped copy is byte-identical to the one we run every day, with a
  test to keep it that way: a copy that can drift is the very trap
  preflight exists to close. It also stopped assuming this repository's
  names — jobs come from `scaffold.json` (`preflight_jobs`) and are
  looked up across every workflow file rather than `ci.yml` alone, which
  this repo needed anyway once `posture` landed in a second file. A test
  installs the overlay into an empty project and runs the result,
  because a tool that fails on its first run is a tool nobody runs twice.

- **Gates that have never fired now carry an expiry rule** — `guards:`
  in `gates.yaml` and ADR 0062 (audit round 7). Measuring the real cost
  of a push showed six real-service jobs — `perf-smoke`, `sso`,
  `scrape`, `vault`, `a11y`, `ldap` — taking 15% of the machine time
  (461 of 3,024 job-seconds) without having gone red once in the last
  200 runs. Nothing is removed: what changes is that the decision is
  written down in advance, and it needs two readings, not one. A job
  that never fires because nobody touched the code it guards is asleep;
  a job that never fires while that code changes weekly may not be
  checking anything. `scripts/rerun_census.py --never-red` gives the
  first reading and `guards:` makes the second one a `git log` away.
  Removing gates wholesale and opening bypasses both stay forbidden.

- **A register of who we depend on, and how we would find out** —
  `docs/SUPPLY-CHAIN.md` grows a sixth layer (audit round 7). The first
  five answer how the things we pull in are controlled; this one answers
  a different question: a chain also breaks when the middleman changes
  the terms. Every row names the supplier, what we lean on them for, and
  **what would go red** if they changed it — and a row whose answer is
  "nothing goes red" must carry a review row instead, because a risk with
  neither a gate nor a reminder is a risk nobody has decided about. The
  register is enforced both ways: every action and image the CI actually
  pulls must appear, every job the register leans on must exist, and the
  one row with no automated check must point at the cadence. It happened
  for real once already — Bitnami moved its free images to a legacy org
  and we found out because a job broke, not because anyone announced it.

- **The platform's own settings are checked by a machine now** — job
  `posture` and `scripts/audit_posture.py` (ADR 0061), the round-7
  audit's second finding: ADR 0053 declares that main takes changes
  only through PRs, that `enforce_admins` is on, and that every job
  running on pull requests is required — all of it GitHub-side
  configuration that nothing in the repository ever read. The checker
  compares three sources against what we declared: the required-check
  set both ways (a job running on PRs that is not required, and a
  required context no job can produce — the latter leaves every PR
  waiting for a check that will never arrive), the branch-protection
  flags, and the repo switches for auto-merge and SHA pinning. The
  audit also found `sha_pinning_required` switched off while our own
  test enforced the same rule, so the platform now enforces it too —
  two mechanisms, one catching it as you write, one as it runs.
  Reading failures are red (exit 2), never skipped: 403 means the token
  lacks `administration: read`, 5xx means GitHub is down, and a gate
  that skips when it cannot read reports all-clear on the day it sees
  nothing at all.

- **The failure counter can see failures that were rerun away** —
  `scripts/rerun_census.py` (audit round 7). `gh run list --json
  conclusion` reports the *last attempt*, so pressing rerun until green
  erases the original failure from the statistics; the only trace is in
  `/runs/<id>/attempts/<n>/jobs`, which nothing read. Measured over the
  last 100 runs: 7 visible failures and **3 hidden** — `dast` twice and
  `codeql` once, all three of which the old method reports as "never
  failed". Two things depended on that number: ADR 0059's baseline
  (now carries a correction note) and the `dast` flake review row, which
  literally prescribed the blind method (now fixed). The census also
  separates platform failures — a job dying in `Set up job` because
  GitHub returned 429 for an action download is not our flake, and
  mixing the two ripens a threshold that is not about us. Proven five
  ways by mutation, including a return to the original bug.

- **The badge worksheet is read by a test now** — `docs/BEST-PRACTICES.md`
  had drifted three ways with nothing to catch it: it still called
  v1.5.0 the latest release, still claimed 18 supply-chain gates when
  `gates.yaml` has 19, and quoted a test count from a day earlier that
  was already wrong. `docs/RELEASE.md` had an instruction to update the
  file; the instruction rotted exactly like an unchecked number would.
  Version claims are now tied to `__version__`, the gate count to
  `gates.yaml`, and the coverage floor to `pyproject.toml`. The test
  count is simply gone — every PR adds tests, so a snapshot there is
  wrong by the next commit; the criteria it answers are the enforced
  ones (required job, ratcheted floor, 100% on changed lines).

- **The evidence rule paid for itself the same day**: `semgrep-sast`
  turned red on the preflight's own `shell=True`, so it left the
  `UNPROVEN` list with a run id attached (81 → 79 across the two changes).
  The fix runs steps through `bash -e -c` — which is what the GitHub
  runner does anyway, so the preflight and CI can no longer disagree
  about bashisms.

- **A preflight that mirrors CI instead of copying it** —
  `scripts/preflight.py` (ADR 0060): the commit hook checks ruff, format,
  and mypy; xenon, interrogate, the coverage floor, and diff-cover live
  only in CI, and that gap made one PR red twice in a row for exactly
  that class. The script reads `.github/workflows/ci.yml` and runs the
  `lint` and `test` steps locally — the workflow stays the single source
  of the commands, and anything it cannot run (actions, environment
  setup) is skipped **with the reason printed**, never dropped. Its first
  real run caught two ruff errors in its own source. It is deliberately
  not wired into a hook: a four-minute wait per commit gets bypassed
  within a week, and a bypassed hook is worse than none.

- **The gate that fails most often is finally in the index** —
  `changed-lines-fully-tested`: `diff-cover` accounted for 5 of the 13
  failed runs in that sample yet had no row in `gates.yaml`, because
  "every job needs a gate" treated job `test` as covered by the gates of
  its test files. Repository-wide coverage that is already high will
  always hide new untested lines.

- **The judges are judged now** — `gate checkers-proven-two-way`, the
  round-4 audit's finding: `audit_pins.py`, `audit_image.py`, and
  `check_semgrep.py` decide whether the supply-chain gates are green,
  yet nothing ran their decision logic — inverting one set operation
  left the whole suite green while CI reported "nothing new" forever.
  `tests/test_checker_logic.py` now drives each one through `main()`
  with planted violations and clean input, the same shape the eight
  exported overlay checkers have always had (proven five ways by
  mutation). The rule itself is baseline and portable: any project that
  writes its own checkers inherits it.

### Security

- **The image scanner caught its first real CVE**: `CVE-2026-53615`
  (util-linux, HIGH, fixed in Debian) is present in the pinned
  `python:3.13-slim` layer, and upstream has not rebuilt yet — the
  pinned digest is already the newest one published. Accepted
  temporarily with reasoning per ADR 0054's ordering (no Dependabot PR,
  no newer digest), with an automatic removal condition: the two-way
  judge goes red the moment a rebuilt digest makes the advisory
  disappear, forcing the exception out.

- **The two files that mute a security check are now checked
  themselves** (round-9 audit). Reading all thirteen "declared debt"
  registers side by side for the first time showed the inconsistency:
  the CVE acceptance lists carry two-way tests, while `.zap/rules.tsv`
  (8 muted findings) and `.hadolint.yaml` (1) were governed only by a
  sentence in CLAUDE.md that nothing enforced. Every line in them does
  carry a reason today — the risk was the tenth line, added in a hurry,
  with nothing to object. The new tests require a real reason per line,
  unique rule ids, that the rule file actually reaches ZAP, that each
  hadolint exception has its reason written above it, and that the
  workflow does not quietly loosen `failure-threshold`, which would
  waive a whole severity class without writing a single reason.
  A floor on the number of `FAIL` rules keeps the regression net from
  shrinking by a one-word edit.

- Documentation swept after the round-9 batch: ADR 0061's rejected-option
  line still claimed `administration: read` was enough for `GITHUB_TOKEN`
  (it is not a scope at all — the note at the end now corrects the line
  itself), the supply-chain register described the posture check as
  running only on main pushes and rule changes, the governance roadmap's
  audit table stopped at r7, and the risk register's "gate that is green
  without checking" row gained the sharper variant this round found: a
  gate that never ran at all because it is not a required check. Two
  fixes came from the missing-marks axis rather than the stale-claims
  one: a finished row in the dialect-landmine table had lost its ✅, and
  the small-backlog row for MFA recovery codes still said no CLI existed,
  four days after round 5 added one.

### Changed

- The verify commands in `SECURITY.md` are now bound to the workflow
  that actually signs (round-4 audit item 2): tests tie the identity
  regexp, OIDC issuer, and example asset names to `release.yml`, so
  renaming the workflow or moving the repo can no longer leave users
  with a command that fails and reads as a forged artifact.
- The risk register's "gate that is green without checking" row is
  raised to **high** (medium × high) and its mitigation now cites the
  new checker tests — the row already existed, so this corrects it
  rather than adding a duplicate.
- A cadence row now tracks the **cost of governance** yearly (baseline
  recorded: 60 commits = docs 26 · feat 17 · chore 7 · fix 6), with the
  rule that a slowdown means finding gates that never caught anything —
  never lowering gates wholesale and never reopening bypass.

- The yearly review row now sweeps **both** registers of open
  decisions: the review conditions ADRs declare, and the app's own
  "not doing this yet" list in CLAUDE.md — round 5 found the latter
  outside the net, with MFA recovery codes the first entry whose
  context had actually changed.
- Two small closes from the round-3 governance audit, batched: arming
  auto-merge on a Dependabot PR now requires reading the lock/SHA diff
  first (green checks prove behaviour, not upstream intent), and the
  yearly worksheet-review cadence row now sweeps the 122 Best Practices
  form answers alongside ASVS/PDPA/ISO — the audit's third round found
  the layering fully converged, leaving only these.

- **`CLAUDE.md` now has a declared ceiling that ratchets** (round-8 audit,
  D3 — the owner's decision, not a gate's). The file every session reads
  in full grew from 22 lines on day one to 1,240 lines / 8,488 words in
  16 days, with 66 commits touching it in the last week alone: no single
  line was wrong, and nobody had ever decided how large it may get. The
  ceiling is enforced two ways — the file may not exceed it, **and the
  ceiling may not float far above the file**, so trimming content forces
  the ceiling down instead of leaving room to refill quietly. Lines and
  words are both counted, because counting lines alone would make
  re-wrapping look like shrinking. Raising it takes an ADR; a cadence row
  revisits it every six months (ADR 0065).

- **Real CI failures can now be harvested as gate evidence**
  (round-9 audit, item 1). ADR 0059's `UNPROVEN` list is shrink-only and
  had stopped shrinking: 76 of 97 gates carried no proof they had ever
  been red for a real defect, and the list sat exactly at its ceiling
  while CI went red several times a week and the evidence disappeared
  with the logs. `rerun_census.py --evidence` reads which test files
  failed out of each job's log and maps them back to gates through the
  partition `tests/test_gates.py` already enforces, then **proposes**
  `proved_by` rows. It stops at proposing on purpose — deciding what a
  red actually proves is a person's job, since a test can fail because a
  fixture broke rather than because the gate caught anything. A cadence
  row every six months makes someone act on it and lower the ceiling by
  whatever was really proven.

- **The posture check can be triggered on demand.** `scorecard.yml` only
  ran on pushes to main, a weekly schedule, or a branch-protection
  change, so verifying that `POSTURE_TOKEN` actually carries enough
  permission meant waiting for the next merge. It now also accepts
  `workflow_dispatch` — a gate that can only be proven by waiting for an
  event is harder to test than it needs to be, and that matters most on
  the day the token expires and someone has to confirm the replacement.
  A cadence row tracks that expiry (first token: 2026-11-16).

- **The posture check no longer reports a setting as off when it simply
  cannot see it.** Its first real run claimed `allow_auto_merge` was
  disabled; auto-merge is on and used by every PR. GitHub only returns
  merge-related fields to callers holding `contents:write`, which the
  read-only `POSTURE_TOKEN` deliberately lacks, so the field arrives as
  `None` rather than `False`. Granting a read-only auditor write access
  to the code it audits would be the wrong trade, so absent fields are
  now reported as unreadable notes, `False` still fails, a cadence row
  checks the setting by hand quarterly, and the daily compensating
  control is that `gh pr merge --auto` would fail outright if it were
  really off (ADR 0061, second note).

### Fixed

- **The failure census only ever looked at 100 runs, however many you
  asked for.** GitHub caps `per_page` at 100 and silently returns that
  many, so the two cadence rows that say `--limit 200` were measuring
  half the window they claimed. It now pages through, which is the same
  class of defect the counter itself exists to close: a statistic that
  quietly sees less than it reports.

- **The platform-posture gate had never run once** (round-9 audit, found
  while closing another item). `posture` declared
  `permissions: administration: read`, which is not a scope GitHub's
  `GITHUB_TOKEN` can grant, so GitHub rejected the whole file before
  creating any job: `scorecard.yml` had failed on every push — main
  included — since the commit that introduced the job, 22 of the last 30
  runs at the time it was caught. Nothing surfaced it because that
  workflow is deliberately not a required check, and because a run that
  fails with zero jobs was invisible to the failure census, which counts
  failures per job. All three holes are closed: the scope is gone and
  the permission now comes from a `POSTURE_TOKEN` PAT (missing token
  still means red, per ADR 0061), the census records runs that never
  started, and a new test validates every workflow's permission scopes,
  triggers, and jobs against what GitHub accepts.

- **The CI failure census was reading the wrong signal** (round-8 audit,
  D1). It told platform failures apart from ours by the *name of the
  failing step* (`Set up job`) — but during the GitHub outage of
  2026-08-17/18 `codeql` failed four times inside
  `Run github/codeql-action/init@…`, whose actual cause was a 503 from
  GitHub itself, and all four were counted as ours. The counter now
  classifies by the **failure message** in the check run's annotations,
  and anything it cannot decide lands in a third class, `ต้องอ่านเอง`
  ("read it yourself"), instead of silently defaulting to ours. Status
  codes only count as platform evidence with HTTP context around them,
  because this app asserts `503` on `/readyz` in its own tests. The
  supply-chain register and the flake cadence row, both of which named
  the old signal, were corrected too.
- Pressing rerun now has a written procedure (round-8 audit, D2):
  ask `githubstatus.com` **before** rerunning — anything but
  operational means wait, not retry — then classify the failure, and
  rerun only what is provably the platform's. Six red runs during that
  outage had nothing of ours broken in them.

## [1.6.0] — 2026-08-17

The silver release: the OpenSSF Best Practices badge reached **Silver
(100%)**, unlocked by the signed v1.5.0 release and a continuity
statement; a second governance audit then closed its own findings —
every open ADR review condition now has a machine-read reminder, the
owner's account (the root of trust behind signed releases) is hardened
with a passkey as the preferred second factor and reviewed on a yearly
cadence row, four more gates moved to the layer their rules belong to,
and repo-level auto-merge replaced hand-rolled merge scripts across the
board. A release of reminders and promotions rather than features — the
kind a governance constitution is supposed to produce.

### Changed

- **Repo-level auto-merge is now the merge norm**
  (`gh pr merge N --rebase --delete-branch --auto`): hand-rolled
  wait-then-merge scripts accumulated five distinct timing traps in a
  single day; GitHub's auto-merge sits inside the required-check gate
  and has none of them by construction. Recorded in SECURITY-CADENCE,
  CONTRIBUTING rule 7 (both languages), DEVELOPMENT, and RELEASE.
- The owner-account hardening review (round-2 audit's one owner-side
  item) is now a yearly cadence row, recorded as verified: a passkey is
  configured and set as the preferred 2FA method (phishing-resistant),
  backed by TOTP + GitHub Mobile, no SMS, recovery codes viewed, and
  the PAT/OAuth-app inventory walked clean - the first review closes
  with no residual at all.

- **Re-layering round three** (under ADR 0057's principle, from the
  round-2 audit): `release-signed-and-attested` rises to baseline now
  that a real signed release proved it; the design-doc, admin-honesty,
  and PDPA-worksheet gates become business-layer agreements. Registry:
  66 baseline / 10 business / 15 internal, 75 portable.

### Fixed

- **Every ADR review condition now has a machine-read reminder** (round-2
  audit's top finding): a cadence row sweeps all open ADR conditions
  yearly - five recent ADRs carried conditions with no reminder at all.
  The manual-pentest row gains a second trigger (external adopters of
  the exported overlay/skill), and the risk register gains the
  single-account root-of-trust row with its residual stated.
- Documentation reviews now have a standing rule (CLAUDE.md): check
  symbols, marks, and badges for consistency alongside the text — a
  missing mark is a bug equal to a wrong sentence. Born from the
  ROADMAP overview table miss below.
- The ROADMAP phase-overview table now shows phases 5-7 as done - they
  closed on 2026-08-12, but only their detail sections were marked, and
  the overview's missing ticks read as three phases still open.
- The repo About's Website field had pointed at the v1.1.0 tag for three
  releases; it now points at `releases/latest`, which follows every
  future release by itself — and `docs/RELEASE.md` step 7 now names both
  About fields so the class of miss cannot recur.

### Added

- **The OpenSSF Best Practices badge reached Silver (100%)** on
  2026-08-16 — all 55 silver criteria answered (46 met, 6 N/A, 3
  deliberately unmet SHOULD/SUGGESTED with reasons), unlocked by the
  signed v1.5.0 release and the new continuity statement.
  `docs/BEST-PRACTICES.md` now carries the silver worksheet beside the
  passing one; Gold sits at 26% and is structurally gated on a second
  contributor.
- **A continuity statement in CONTRIBUTING (both languages)**: nothing
  about the project's continuity depends on a private asset — keyless
  signing, in-repo automation, MIT — so a fork continues the project
  whole. Written for the humans it reassures, and it happens to answer
  the Best Practices `access_continuity` criterion.

## [1.5.0] — 2026-08-16

The enforced-path release: a five-dimension governance audit
(OWASP/SSDF · PDPA · ISO 25010 · DevSecOps · COBIT/ITIL) ran against the
whole repository, and every gap it found is closed in this release — main
only accepts pull requests now, for the owner too; the image's OS layer
and the Dockerfile are scanned every push; the performance pillar has its
first per-push gate; release artifacts are signed with provenance; and
this is the project's first release that fixes published CVEs, listed
below. Seven gates also moved to the layer their rules actually belong
to, and every hand-written document was swept back to current truth.

### Security

- **The first releases-line CVE fixes in this project's history** — both
  found by the repo's own gates, both verified clean after the bump:
  - `cryptography` 45.0.7 → 50.0.0 in the `plugin-auth-totp` category
    (flagged by the `plugin-audit` job: seven advisories including
    CVE-2026-2141 and the PYSEC-2026-355x series; the `~=45.0` spec could
    never receive the fixes). Spec moved in both the Pipfile category and
    the plugin manifest, per ADR 0023.
  - semgrep 1.172.0 → 1.173.0 in `pins/semgrep/`, whose loosened `mcp` pin
    (1.23.3 → 1.29.0) clears CVE-2026-52870/52869/59950; the three PYSEC
    ids left `pins/accepted-advisories.txt` in the same commit, as the
    two-way audit gate requires.
- **`main` accepts pull requests only — enforced for admins too**
  ([ADR 0053](docs/adr/0053-solo-maintainer-sod-compensating-controls.md)):
  `enforce_admins` is now on, so the 27 required checks sit on the
  mandatory path for everyone. The ADR records the solo-maintainer
  compensating controls and the expiry condition (a second regular
  contributor turns required reviews on). CONTRIBUTING rule 11 announces
  it; the ISO 27001 A.5.3 row now cites it.

### Changed

- **The at-rest encryption boundary is now stated, not implied**
  (`docs/DATA-CLASSIFICATION.md` rule 5): whole-database encryption at
  rest is deliberately delegated to the infrastructure layer, while the
  app encrypts only usable C1 secrets itself (ADR 0046) — the two layers
  defend against different attackers, and "not mentioned" should never
  read as "already handled".
- The branch-protection notes in `SECURITY-CADENCE.md` and `ROADMAP.md`
  caught up with ADR 0053/0056 reality: `enforce_admins` is on, required
  checks are 27 of 28.
- **Seven gates re-layered to match what their rules actually are**
  ([ADR 0057](docs/adr/0057-gate-relayering-batch.md), from the
  governance audit's D2 recheck): backup drill and the risk register
  rise to `baseline` (universal); ROPA, admin masking, encrypted
  secrets, and the three-brand suite become `business` (agreements of
  this kind of app — the business sheet now tells the personal-data
  story end to end); the migration time-type lint folds into
  `dialect-discipline`. Registry now 90 gates (65 baseline · 7 business
  · 18 internal · 71 portable); `SKILL.md` and `SKILL-TODOLIST.md`
  regenerated accordingly.
- **Release artifacts are now signed with provenance**
  ([ADR 0058](docs/adr/0058-signed-releases-and-provenance.md)): a
  release-published workflow generates every SBOM from the tag's own
  code, signs each keyless (cosign bundle), verifies both ways in place
  (the workflow's identity passes, a foreign identity must fail), emits
  SLSA provenance via GitHub's native attestation (`gh attestation
  verify`), and attaches everything to the release.
  slsa-github-generator was rejected on record: it demands tag-pinned
  workflow references, which the SHA-pinning gate forbids. Verification
  commands live in `SECURITY.md`; gate `release-signed-and-attested`
  brings the supply-chain axis to 18.
- **The release procedure is now a document, not folklore**
  ([`docs/RELEASE.md`](docs/RELEASE.md)): the standard cut steps as
  practised since v1.1.0, plus the four tasks bound to the next release
  (first-ever CVE-fixing release notes, cosign/SLSA signing, the Best
  Practices fields tied to versions, the README version badge) — with a
  cadence-table row so the test-read schedule carries the reminder.
- **A full documentation currency sweep** (three parallel reviewers over
  every hand-written doc): stale counts and claims from the ADR
  0053–0056 window fixed across twelve files — required-check numbers,
  supply-chain axis 17, portable gates 66, plan G closed, cryptography
  `~=50.0`, one remaining accepted advisory, the Best Practices submit
  checklist collapsed to a done record, and the per-push job table now
  lists `perf-smoke`, `commit-lint`, and the hadolint step.

### Added

- **A per-push performance tripwire — the pillar's first**
  ([ADR 0056](docs/adr/0056-perf-smoke-tripwire.md)): the `perf-smoke`
  job walks the real k6 journey against the shipped image (SQLite stack,
  5 VUs, 60s) with thresholds at twice the ADR 0031 targets — loose on
  purpose, because a shared runner cannot judge the real targets without
  flaking. It catches step-change regressions; the evidence for the real
  targets remains the multi-round curves in `docs/PERFORMANCE.md`.
- **The Dockerfile is linted by hadolint on every push**
  ([ADR 0055](docs/adr/0055-dockerfile-lint-hadolint.md)): every level
  including info must be green; exceptions live in `.hadolint.yaml` alone,
  each with a written reason (one exception at adoption: DL3059, the
  final stage's deliberately separate `RUN` blocks). Gate
  `dockerfile-linted` joins the supply-chain axis, bringing it to 17.
- **The image's OS layer is now scanned for CVEs on every push**
  ([ADR 0054](docs/adr/0054-image-os-layer-cve-scanning.md)): trivy runs in
  the `image` job against the image just built (HIGH/CRITICAL, fixable
  only — the scope is declared once, on the trivy step), and
  `scripts/audit_image.py` judges the report against
  `deploy/accepted-image-advisories.txt` **in both directions**, the same
  contract as the `pins/` audit. Two new supply-chain gates
  (`image-os-cve-audit`, `image-exceptions-honest`) bring the axis to 16.
- Version and license badges at the bottom of the README.

## [1.4.0] — 2026-08-16

The clean-scoreboard release: the OpenSSF Best Practices badge reached
**passing (100%)**, which closed the last open ISO/IEC 27001:2022 item —
every assessment worksheet in the repository now reads zero unresolved
(ISO 79 pass · 37 n/a · 0 fail; PDPA backlog empty; ASVS fully answered
within scope). A small release by diff, a large one by what it certifies.

### Changed

- **The ISO/IEC 27001:2022 worksheet reads 79 pass · 37 n/a · 0 fail** —
  the last open item, A.5.35 (independent review), closed when the OpenSSF
  Best Practices badge reached **passing** (project 14085, 100%, verified
  against the badge API): a full review against an external framework's 67
  criteria, with every answer published and the badge under the provider's
  ongoing surveillance. A full human third-party review remains a recorded
  option (the pentest cadence row). The README no longer mentions failing
  ISO items, and `docs/BEST-PRACTICES.md` records the form-filling lesson:
  criteria marked *(URL required)* stay unanswered until the justification
  contains an actual URL.

## [1.3.0] — 2026-08-16

The governance release: the owner declared the project's philosophy — security
first (country law, worldwide standards, an independent supply-chain axis),
then scalability, then manageability, then DevSecOps friendliness — and this
release makes that constitution machine-checked, closes plan G in full
(G1–G5), and ships the three adopted ideas from the bmad/impeccable/skillsmp
analysis. Cut as a fresh N-1 anchor, as tradition now demands.

### Changed

- Documentation refresh after the governance plan landed: the gate count in
  the ISO worksheet no longer hardcodes a number that rots, the OpenSSF
  worksheet's test count moved to the current suite (1,258, counted after
  plan G), the annual ASVS review row in the security cadence now names its
  PDPA and ISO 27001 companions, ADR 0043's "42010 only" verdict carries a
  dated note pointing at ADR 0051, and the architecture correspondence
  table gains rows for the three new document↔reality tests.

### Added

- **The governance plan, closed** — G5's measurements shipped: four
  configurations ({1,2 workers} × {1,2 replicas}) on the reference VM, 16/16
  target-load rounds passing thresholds. Two workers in one container halve
  p95 at 25 VUs and add 129% throughput at 50 VUs — now legal because
  `/metrics` aggregates correctly; the surprise finding is recorded too: on
  a single host, two replicas are *worse* than one at every load level
  (shared vCPUs, proxy hop, cross-process audit serialization) — replicas
  are for availability and rolling upgrades, not single-host throughput.
  The multiproc mode was proven on real gunicorn (two workers' snapshot
  files, aggregated counts, monotonic scrapes). Caching verdict per the
  measure-first rule: **no app-data cache** — the bottleneck is process
  count, not queries; revisit conditions recorded in
  `docs/PERFORMANCE.md`.
- **Opt-in multi-worker with correct metrics**
  ([ADR 0052](docs/adr/0052-performance-layer-g5.md) — G5 of the governance
  plan): set `WEB_CONCURRENCY` above 1 together with
  `METRICS_MULTIPROC_DIR` and `/metrics` now aggregates every worker of the
  container correctly — each worker snapshots its counters to the declared
  directory (atomic rename, stdlib only, no new dependency) and the scraped
  worker merges them; half a configuration refuses to start instead of
  serving numbers that flip per scrape. The default stays one worker, and
  replicas remain the primary scaling path. Guarded by
  `tests/test_metrics_multiproc.py` (gate `metrics-correct-across-workers`
  — the performance pillar's third gate).
- **The ISO 27001 backlog, closed to one item** (owner-ordered): a written
  **risk-assessment method and first register** (`docs/RISK-ASSESSMENT.md`
  — likelihood × impact with a fixed product formula so the machine can
  check every level, an acceptance rule per level, nine assessed risks
  with real mechanisms and honest residuals, and an annual cadence row) —
  and a **backup/restore runbook whose rehearsal is a test**
  (`docs/RUNBOOK-BACKUP.md` + `scripts/backup_drill.py`: backup → damage
  → restore → verify runs on a real schema **on every push**, proven to
  detect a restore that lost data; the runbook's key rule — keep
  `DATA_ENCRYPTION_KEY` away from the database backup — is itself
  test-guarded). Items 6.1, 8.2, A.5.30 and A.8.13 flip to pass: the
  worksheet now reads **78 pass · 37 n/a · 1 fail** (independent review,
  owner-side). Gates: `risk-method-and-register-current`,
  `backup-restore-drilled-every-push`.
- **The per-country compliance index** (`docs/COMPLIANCE.md` — G4 of the
  governance plan): Thailand (PDPA) today, plus the contract for adding a
  country — additive only, a four-point minimum bar set by the PDPA
  worksheet, and two deliberate non-goals (no worksheets for countries
  nobody deploys in, no cross-law abstraction). Legal-layer gates follow a
  `legal-*` naming convention and `tests/test_compliance_index.py` keeps
  the index honest both ways (gate `country-compliance-indexed`).
- **The supply-chain axis** (`docs/SUPPLY-CHAIN.md` — G3 of the governance
  plan): the constitution names supply chain an independent axis of the
  security pillar; this index tells its story in five layers (what enters
  the app, what CI installs, what runs in production, who moves the pins,
  what proves the posture) over the 14 gates that guard them. Membership
  is declared on the gates themselves (`axis: supply-chain` in
  `gates.yaml`) and `tests/test_supply_chain.py` keeps the index honest in
  both directions (gate `supply-chain-axis-indexed`).
- **ISO/IEC 27001:2022 self-assessment** (`docs/ISO27001.md` — G2 of the
  governance plan): all 116 items answered — clauses 4–10 at the second
  level plus every Annex A control — with resolvable evidence, honest
  not-applicable verdicts for a one-person project, and the 5 real gaps in
  a backlog (a written risk-assessment method, a rehearsed backup/restore
  procedure, an independent review). The standard is pinned as a
  self-typed outline of item codes (`docs/iso27001-2022-outline.json`,
  checksummed) — no copyrighted text embedded. Guarded by
  `tests/test_iso27001.py` (gate `iso27001-worksheet-honest`).
- **The project constitution**
  ([ADR 0051](docs/adr/0051-project-constitution-and-intake.md)): concerns
  are ranked — security (country law · worldwide standards · supply chain)
  over scalability & performance over manageability over DevSecOps
  friendliness — and every gate in `gates.yaml` now declares which pillar it
  serves (`pillar:`, enforced by `tests/test_gates.py`; first tally:
  security 52 · manageability 14 · devx 13 · performance 2). New external
  ideas enter through documented intake rules (CONTRIBUTING rule 10): the
  baseline must not break, classify before adopting, record adoptions and
  rejections as ADRs. The governance plan (G1–G5, next: an ISO/IEC
  27001:2022 self-assessment) lives in
  [`docs/ROADMAP-GOVERNANCE.md`](docs/ROADMAP-GOVERNANCE.md).
- `skill/` — the exported rules repackaged as an installable **agent skill**
  ([ADR 0050](docs/adr/0050-agent-skill-package-export.md)): frontmatter and
  a usage preface wrapped around the same generated baseline sheet, the
  business sheet as a reference file, and the overlay's eight stdlib checkers
  copied per its manifest. Built by `scripts/build_agent_skill.py`;
  `tests/test_agent_skill.py` compares every committed byte — including the
  file set itself — against a fresh render.
- `docs/DESIGN.md` — the UI's identity, a per-page mode table
  (Operate/Read/Enter, adapted from the *impeccable* skill), the
  refine-vs-redesign rule for UI changes, and a bounded-verification
  discipline. Guarded two ways by `tests/test_design_doc.py`: every full-page
  template must be assigned a mode, and the theme-variable set in the document
  must match what `base.css` actually uses.

### Fixed

- Documentation refresh after v1.2.0: README now describes the Site
  administration hub and the team-rename change log in both languages and
  links `docs/DESIGN.md`; the OpenSSF worksheet's version rows cover all
  three tags and its test count is current (1,239, was 1,002); the password
  blocklist size is stated as the shipped file's real count (46,476, was
  46,483 since Phase 4); stale plugin/gate/check tallies in the
  infrastructure roadmap corrected. `docs/DEVELOPMENT.md` now carries a
  UI-discipline row and joined the docs whose advertised CI numbers are
  enforced by `tests/test_contributor_docs.py`.

## [1.2.0] — 2026-08-15

Post-release change requests from real use, plus one scanner fix. Cut before a
planned structural rework so the N-1 gate has a fresh anchor.

### Added

- A safe **Back** button on the public `/privacy` page — the referrer is used
  only when it points inside the app; anything else falls back to the home page
  (or the login page for anonymous visitors), and `..` paths are rejected.
- A fixed-English **"Reset language to English"** escape hatch on the settings
  page, deliberately never translated — so a user who picked a language they
  cannot read can always find the way back.
- A **Site administration** hub at `/admin`, Moodle-style: panels grouped into
  *Users & teams*, *Server*, and *Reports*; the old "Users" nav item now points
  here, and the hub link lives only in the top nav.
- Admins can **rename a team**, with a mandatory reason; every rename lands in
  a member-visible change log (when / who / from / to / reason) on the new
  `/teams/<id>/info` page — separate from the audit trail on purpose, because
  the audit trail keeps C3 values as HMACs while this log exists to be read.

- Table captions are now left-aligned with the page instead of floating in
  the centre — one rule in the core stylesheet, applied to every table.

### Fixed

- CodeQL could not parse three files that used PEP 695 syntax — the audit
  module was silently excluded from security scanning entirely. Rewritten in
  TypeVar style, with a test that keeps PEP 695 out of `app/` until the
  extractor supports it.

## [1.1.0] — 2026-08-15

Eleven more phases of work: five about making the engineering discipline in
this repo **portable and checkable** (8–12), then the whole 1.1 feature plan
(13–18) — rule layers and legal worksheets, an admin overhaul with data masking,
encryption at rest, an operations phase, named auth profiles, and the org todo
graph. Nothing in the `/api/v1` contract changed; it only gained fields.

### Added

- `gates.yaml` — an index of every gate in the repo, verified in both directions:
  every job must have a gate, and every test file must be assigned to exactly one
  gate (a full partition, the same shape as `docs/DATA-CLASSIFICATION.md`). A
  `standard:` reference may only cite an ASVS requirement that passes *and* whose
  evidence points back at that gate. See
  [ADR 0039](docs/adr/0039-gates-registry-verified-two-way.md).
- `SKILL.md` — framework-agnostic baseline rules, **generated** from the portable
  gates (rule = the gate's title, the trap that produced it = `born_from`).
  Writing a rule directly into the file is not possible; add a gate and
  regenerate. App-type agreements are split into their own generated sheet,
  `SKILL-TODOLIST.md`, with every gate declaring its layer — see
  [ADR 0042](docs/adr/0042-three-layer-skill-model.md).
- `overlays/flask/` — the enforcement half of those rules for other Flask
  projects: 8 scanners (standard library only), `gates_doctor.py`, and a
  manifest-driven `install.py`. CI job `scaffold` proves on every push that it
  installs into an empty repo *and* that this repo passes its own overlay
  (dogfooding).
- A `migration` class (`live` / `warm` / `cold`) declared by every plugin and
  enforced at load time, with the numbers to back each claim measured under load
  — see [ADR 0041](docs/adr/0041-migration-class-per-plugin.md) and
  `docs/PERFORMANCE.md`. The `cache` port was **demoted from `live` to `warm` by
  measurement**, not by relaxing the criterion.
- `scripts/run_gates.py` — a fail-fix loop over `gates.yaml` that reports three
  honest states (ran / skipped-with-a-reason / failed), proven against a real
  planted vulnerability in `docs/GATE-LOG.md`.
- `docs/comparison/` — an experiment measuring whether the exported scaffolding
  changes the code that actually gets written: one spec, three arms of five
  generated apps each, one measurement battery
  (`scripts/measure_generated.py`, `scripts/asvs_probe.py`).
- `docs/PDPA.md` — a legal worksheet in the same shape as the ASVS one (a status
  per article, evidence in backticks that a test resolves), the pilot of the
  *legal* rule layer. Includes the two features it demanded: a public `/privacy`
  page and **account suspension** (suspend ≠ delete, reversible, admin page and
  CLI, live sessions cut on the next request) — PDPA articles 23 and 34.
- The admin area is now a package with a panel registry: user rows pass through
  a **masking layer driven by the data classification** (C1/C3 hidden, C2 masked,
  unmask is an audited POST — see
  [ADR 0045](docs/adr/0045-admin-data-masking-by-classification.md)), plus read-only
  panels for the runtime environment, an active SBOM view that diffs installed
  packages against `Pipfile.lock`, lifecycle (alembic current vs head, plugin
  state), and per-process latency histograms.
- TOTP secrets are now **encrypted at rest** (AES-256-GCM, `enc:v1:` format with
  the version inside the value so keys can rotate row by row). The key is
  `DATA_ENCRYPTION_KEY`, separate from `SECRET_KEY` by design and fed from the
  secrets source; legacy plaintext rows still verify and are re-encrypted on
  first use — see [ADR 0046](docs/adr/0046-field-encryption-at-rest.md). A plugin
  whose declared libraries are missing now **disables itself with a warning**
  instead of breaking the page that lists it.
- One external-auth plugin can now run **several named config profiles**
  (`AUTH_PROFILES="oidc:corp,ldap:hq"`, per-profile keys like
  `OIDC_CORP_ISSUER`, no silent fallback to the bare key). The declared order is
  the order tried; a profile is only skipped when it is *unreachable* — a
  rejection is final, so a password guesser never gets one quota per directory
  and same-named accounts cannot log in across realms. Profiles can be disabled
  one at a time via `DISABLED_PLUGINS=auth/oidc:corp`, and one user can hold
  identities from several directories — see
  [ADR 0047](docs/adr/0047-named-auth-profiles.md).
- An **N-1 compatibility contract** with an expand–contract migration
  discipline: CI builds the schema from HEAD and then runs the code of the
  latest tag against it, end to end through `/api/v1` — a migration that would
  break the replicas still serving during a rolling deploy now fails the build.
  New `/healthz` and `/readyz` probes (no token, no internal data, liveness
  deliberately independent of the database) and an explicit gunicorn graceful
  timeout — see [ADR 0048](docs/adr/0048-n-minus-one-compatibility.md).
- Prometheus and Grafana actually scrape `/metrics` now
  (`compose.metrics.yaml`; the scrape token lives in a file that is re-read on
  every scrape, so it can be rotated without a restart), and CI proves on every
  push that the app's numbers reach the TSDB through the token gate — with the
  wrong token, the target reads down. Worker-count tuning was measured rather
  than guessed: two workers roughly halve tail latency at 25–50 concurrent, but
  the default stays at one worker because `/metrics` counts per process — the
  measured path to scale is replicas, not workers (`docs/PERFORMANCE.md`).
- **Org todo graph** ([ADR 0049](docs/adr/0049-org-todo-graph-privacy-model.md)):
  tasks stay private by default; owners opt in per task by sharing it into an
  admin-managed team, which reveals exactly four fields (title, due date, done
  state, owner). Cross-person dependencies are invite–accept only — a private
  task never leaks even its existence, and probing an unshared id answers 404.
  A deterministic impact signal walks accepted dependencies (cycle-safe) and
  marks your tasks "at risk" when something you rely on is overdue; the badge
  carries no upstream details. Unsharing, removing a member, deleting a team,
  and closing an account all funnel through one severing rule, and the API
  gained an additive `is_at_risk` field. Every "cannot see" claim is proven by
  tests across the page, the API, the impact signal, and the notices.

### Changed

- `docs/GATES-ASVS.md` (generated) now states which ASVS rows are backed by a
  gate that runs on every push and which pass on documented reasoning alone —
  117 versus 21 of the 138 that pass. Same assessment, honest confidence levels.

### Fixed

- `tests/test_api_fuzz.py` no longer fails on negative payloads that evaporate
  before reaching the app: query strings and headers are strings by definition in
  HTTP, so a wrong-typed value never reaches the wire, while the check judged the
  data *before* serialisation. Negative bodies are still enforced.

## [1.0.0] — 2026-08-12

First public release. Everything below arrived across seven planned phases of
work; the reasoning for each decision lives in the 67 records in
[`docs/adr/`](docs/adr/), and the phase-by-phase plan in
[`docs/ROADMAP.md`](docs/ROADMAP.md).

### Added — the application

- Todos with categories, start dates, and due dates down to the minute, sorted so
  the closest deadline comes first.
- Filters by status, by category, and by due date — within the next 15/30/45
  minutes or 8 hours, today, tomorrow, or a range you pick. They combine.
- A dedicated edit page, because a list row that is also an editor is a list row
  nobody can read.
- English and Thai throughout, with the language remembered per user.
- Light, dark, and automatic colour modes. Automatic follows real sunrise and
  sunset for the user's timezone, from a table covering all 598 zones that ships
  with the app — no network call and no JavaScript.
- A settings page holding profile, password, API tokens, two-factor enrolment,
  language, theme, mode, and timezone.
- Export your own data, and close your own account — see
  [ADR 0034](docs/adr/0034-data-subject-rights.md).

### Added — `/api/v1`

- Todos, categories, and tokens over HTTP, driven by the same service layer as
  the web pages, with an OpenAPI 3.1 contract generated from the code and checked
  against the committed copy on every push.
- Personal access tokens as machine credentials, stored as a SHA-256 of the
  secret, shown once at issue and never again.
- Per-token rate limiting.

### Added — plugin architecture

- Themes, authentication factors, database backends, caches, and secret sources
  are all plug points. Adding one means dropping in a directory; removing one
  means deleting it. The core never names a specific plugin, and a test enforces
  that by scanning the core for plugin names.
- Each plugin declares its own libraries in its own pipenv category, so removing
  a plugin removes its supply chain instead of leaving it in `[packages]` forever
  — [ADR 0025](docs/adr/0025-plug-points-and-supply-chain-isolation.md).
- Enhancements nest one level deeper, selected by capability rather than by id.
- `DISABLED_PLUGINS` turns any plug point off at runtime, for the afternoon a CVE
  lands in a library you can simply stop using.
- Bundled: two themes, TOTP two-factor with an optional QR renderer, SQLite,
  MySQL, MariaDB, Redis cache, Vault secrets, OIDC, and LDAP.

### Added — operations

- Docker image, compose stacks per database brand, an nginx reverse proxy in
  front of multiple replicas, and TLS termination — each exercised by CI against
  the real thing on every push, none of it mocked.
- systemd unit and timer for the retention job, installed by a script and proven
  on a host with real systemd.
- Prometheus metrics with per-endpoint latency at `/metrics`, behind the same
  token gate as the API.
- Structured JSON logs with a request id, shipped to Loki with alerting rules —
  [ADR 0037](docs/adr/0037-where-logs-go-and-what-shouts.md).

### Security

- No signup page and no self-service password reset, by design; the project
  stores no email addresses.
- Password policy following NIST 800-63B: length and a 46,000-entry breach list,
  no composition rules and no forced rotation —
  [ADR 0019](docs/adr/0019-password-policy-nist-800-63b.md).
- Server-side session lifetime, cookies bound to the current credential so a
  password change invalidates every cookie already issued, and session fixation
  handled on every login — [ADR 0020](docs/adr/0020-session-lifetime-and-binding.md).
- Login rate limiting in two dimensions, per IP and per username, so rotating
  addresses does not buy more attempts —
  [ADR 0021](docs/adr/0021-per-username-login-throttle.md).
- Optional TOTP second factor that stops the login half-way rather than after
  authenticating. It is offered, not required, and
  [ADR 0033](docs/adr/0033-mfa-is-offered-not-required.md) records why together
  with the compensating controls and the conditions that would reverse it.
- Content Security Policy with no `unsafe-inline`; every client-side behaviour
  lives in one JavaScript file and is wired through `data-` attributes.
- Roles checked in the service layer rather than at the route, since there are
  three adapters over it — [ADR 0022](docs/adr/0022-minimal-rbac.md).
- Objects belonging to another user answer 404, not 403, so ids cannot be probed
  for existence — [ADR 0004](docs/adr/0004-ownership-404-not-403.md).
- Append-only audit trail with a hash chain, written automatically by a session
  event so new features are covered without calling anything. Appends serialise
  on a single lock row, which is what a hash chain requires once more than one
  process writes — [ADR 0035](docs/adr/0035-audit-appends-queue-on-one-row.md).
- Deleting hides; a separate purge command is the only code that removes rows,
  after an approved retention period —
  [ADR 0014](docs/adr/0014-pdpa-vs-audit-retention.md).
- Reverse proxy headers trusted only as many hops as you declare, defaulting to
  none — [ADR 0027](docs/adr/0027-trusting-reverse-proxy-headers.md).
- Secrets come from a declared source: environment, file, or Vault. "The source
  did not have that name" falls back; "the source could not be reached" refuses
  to start — [ADR 0030](docs/adr/0030-secrets-come-from-a-declared-source.md).
- Assessed against OWASP ASVS 5.0 Level 2 — all 253 in-scope requirements
  answered, every "pass" carrying a reference that a test resolves, and the 48
  that do not pass listed openly in [`docs/ASVS.md`](docs/ASVS.md).
- WCAG 2.2 AA, checked both by a structural test suite and by pa11y-ci driving a
  real Chromium over dark mode, an alternate theme, and Thai.

[Unreleased]: https://github.com/sayam/flask-todolist/compare/v1.6.0...HEAD
[1.6.0]: https://github.com/sayam/flask-todolist/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/sayam/flask-todolist/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/sayam/flask-todolist/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/sayam/flask-todolist/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/sayam/flask-todolist/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/sayam/flask-todolist/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/sayam/flask-todolist/releases/tag/v1.0.0
