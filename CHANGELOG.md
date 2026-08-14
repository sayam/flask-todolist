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

Ten more phases of work: five about making the engineering discipline in this
repo **portable and checkable** (8–12), then five phases of the 1.1 feature plan
(13–17) — rule layers and legal worksheets, an admin overhaul with data masking,
encryption at rest, an operations phase, and named auth profiles. Nothing in the
`/api/v1` contract changed.

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
work; the reasoning for each decision lives in the 49 records in
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

[Unreleased]: https://github.com/sayam/flask-todolist/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/sayam/flask-todolist/releases/tag/v1.0.0
