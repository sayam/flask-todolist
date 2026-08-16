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
work; the reasoning for each decision lives in the 56 records in
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

[Unreleased]: https://github.com/sayam/flask-todolist/compare/v1.4.0...HEAD
[1.4.0]: https://github.com/sayam/flask-todolist/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/sayam/flask-todolist/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/sayam/flask-todolist/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/sayam/flask-todolist/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/sayam/flask-todolist/releases/tag/v1.0.0
