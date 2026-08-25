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

- **Tag `evidence-freeze-1`.** The state the dissertation's claims point at, set on
  both this repository and `verifiable-gates` (ADR 0075 §2). ADR 0075 said to set it
  once the core extraction was done; that is recorded there as meaning the rules and
  the main tooling have moved — stages 1, 2 and 6 — with stages 3 to 5 moving
  peripheral checkers *into* `verifiable-gates` without changing what the claims
  refer to.

### Changed

- **The freeze tag is `evidence-freeze-1`, not `thesis-freeze-1`** (ADR 0075 §2).
  What the tag pins is the *evidence* — the code, the rules, the measured numbers
  and the documents citing them — and whoever checks it out later may not have
  arrived from the dissertation. A name tied to the setter's reason leaves
  everybody else guessing what they get. The same name is used in
  `verifiable-gates`, because one claim usually spans both repositories now: the
  rules live there, their enforcement lives here. No tag existed yet, so nothing
  had to be moved.

### Removed

- **The rule sheets, and the two generators behind them, moved to
  `verifiable-gates`** (extraction stage 6 — ADR 0078). `SKILL.md`,
  `SKILL-TODOLIST.md`, the `skill/` agent-skill package, `scripts/build_skill.py`,
  `scripts/build_agent_skill.py`, their preambles and their tests are gone from
  here. The rules themselves now live in that project's `rules.yaml`; this
  repository keeps their *enforcement* — which test file, which job, which step.
- **The gate `skill-mirrors-portable-gates` is removed** from both sides. There is
  no sheet here to hold to a registry any more, and a catalogue publishing a rule
  nobody enforces is exactly what the new agreement check is there to catch.

### Added

- **`tests/test_rule_catalogue_agreement.py` — the two registers are held to each
  other in both directions.** Every portable gate here must exist in the vendored
  catalogue, and every rule the catalogue publishes must be enforced here. The
  Thai wording is compared byte for byte against the catalogue's `*_th` fields,
  along with the layer, the pillar, and the enforcement the catalogue cites — the
  last being the direction that goes stale most easily, since reorganising tests
  here does nothing to remind anyone to edit a file in another repository.

- **Workflows are now checked for a key written twice.** `yaml.safe_load` accepts
  a duplicate key and keeps the last one, so every test here that reads a workflow
  stayed green on a file GitHub rejects outright — and a rejected workflow produces
  a run with **zero jobs**, which a pull request shows as "no checks reported"
  rather than as a failure. Found the hard way while adding `submodules: true` to
  every checkout. Added to an existing gated test file rather than as a new gate.
- **This repository now consumes `verifiable-gates` instead of carrying a copy of
  it** ([ADR 0077](docs/adr/0077-consume-verifiable-gates-as-a-submodule.md)).
  `vendor/verifiable-gates` is a submodule pinned by SHA and watched by Dependabot;
  `scripts/build_skill.py`, `run_gates.py`, and `preflight.py` are now thin
  adapters that say where *this* project's registry, preamble, and root are.

### Removed

- **`overlays/` and the three test files whose subject moved** — the logic they
  covered is tested at source, under a suite that starts its coverage floor at
  100%. The gate `overlay-covers-every-portable-gate` went with them: its claim is
  about an overlay this repository no longer has, and it is still enforced where
  the overlay now lives. Ceilings moved down to match: gates 116 → 115,
  suppressions 95 → 88, unexplained suppressions 48 → 43.
- **`verifiable-gates` now has the same branch-protection posture as this
  repository** — required checks, `enforce_admins`, linear history, no
  force-pushes, conversation resolution — verified by attempting a direct push
  and being refused. The register row says so, and also says what still has no
  checker there: nothing verifies that posture stays set until `audit_posture.py`
  moves in stage 3.
- **Extraction stage 1 landed in `verifiable-gates`** (not in this repository):
  a package skeleton, hash-pinned CI tools, and the gate-registry schema every
  later stage reads — mypy `strict` and coverage at 100% from the first commit,
  which is possible there because that repository started empty.
  Nothing has moved out of this repository yet; stage 2 is the first that does.
- **Extraction census for `verifiable-gates` (stage 0).** `extraction.yaml`
  decides every file in scope — `scripts/`, `overlays/`, `skill/`,
  `docs/comparison/`, the root governance files, and every test that mentions
  them — as move / stay / split with a stage and a reason (107 files: 68 move ·
  30 stay · 9 split). `tests/test_extraction_manifest.py` enforces it both ways:
  an undecided file is red, and so is an entry pointing at a file that has
  already left. Nothing moves in this stage. [ADR 0075 §6](docs/adr/0075-thesis-track-freeze-effort-and-ceilings.md).
- **Gate count now has a ceiling, and new documents need a reader.**
  `[tool.todolist.ceilings].gates_ceiling` is checked by `check_ratchets.py`
  next to the removal floor — a new gate must retire an old one or move the
  number by ADR; CONTRIBUTING rule 12 (both languages) states the same for
  files under `docs/`. [ADR 0075 §3–4](docs/adr/0075-thesis-track-freeze-effort-and-ceilings.md).
- **The thesis track now leaves a trail that cannot be reconstructed later.**
  `docs/comparison/effort-log.csv` records time per session from 2026-08-24
  (`tests/test_effort_log.py` fails if a day with commits has no row — the one
  kind of data this repository had none of); the artifact the thesis describes is
  pinned at tag `evidence-freeze-1`; and gate count gains an upper ceiling so rules
  stop growing faster than their evidence. [ADR 0075](docs/adr/0075-thesis-track-freeze-effort-and-ceilings.md).
- **The governance core gets a name and a home: `verifiable-gates`**, to be
  extracted under Apache-2.0 (code, with a CLA) and CC BY 4.0 (rules); this
  application stays AGPL-3.0-or-later + CC BY-SA 4.0 with no CLA for app code.
- **PRs that touch the core paths sign `CLA.md`.** A one-line grant in the PR
  description that makes the extraction possible without transferring copyright;
  DCO stays. This narrows, rather than reverses, the "no CLA" position of ADR 0070 —
  [ADR 0076](docs/adr/0076-cla-for-relicensing.md) says why, and what it does not settle.
- **The supplier register asked what breaks loudly, and nothing else.** Its third
  column — "what goes red if they change" — is answered by all ten rows, which is
  the good half. Governance audit round 27 asked the other half: what happens when
  a supplier keeps working perfectly and simply stops serving *us*, under a policy
  that is about our behaviour rather than theirs. Three such clocks were already
  proven in round 26: Dependabot stops opening pull requests after ninety days
  with none of its own touched, GitHub disables scheduled workflows in a public
  repository after sixty quiet days, and a dismissed code-scanning alert is never
  reopened even when its subject becomes true again. Nothing goes red in any of
  them, because nothing happens. Zero of the ten rows mentioned this; the sharpest
  case was Dependabot itself, the one supplier proven to stop serving us, which had
  no row of its own — it appeared inside Debian's "what goes red" cell. There is
  now a fourth column, a row for Dependabot, and a test that requires every row to
  answer it. "None known" is a valid answer and must be written; a blank is not.

- **The badge answer sheet now has a machine reading it.** `bestpractices.dev` was
  the only supplier row whose answer to "what goes red" was "nothing does", backed
  by a twelve-month review — which means a stale number can stay stale for a year.
  The clock there belongs entirely to them: they can revise a criterion and an
  answer that used to pass stops passing, with the badge quietly dropping a level.
  `audit_posture.py` now reads the project's public JSON on every `posture` run and
  compares all six percentages against a table in `docs/BEST-PRACTICES.md`. Setting
  it up found a stale number immediately: the status line claimed gold was at 26%
  while the site had said 57% since v2.1.0.

- **The script that knew the right numbers was never wired to where they are
  advertised.** The repository's About line carries four counts and a version;
  `ci:posture` has checked them since round 24, and `sync_counts.py --about` has
  printed the correct string since round 25 — but applying it was still a manual
  copy. It went stale twice in one day: merging a change that added one gate left
  `posture` red on `main`, first 112→115 and then 115→116. A step you have to
  remember, missed twice running, is not bad luck. `--about --write` now reads the
  live field, replaces each number in place, and pushes it back — the surrounding
  sentence, which somebody wrote by hand, is left untouched. It syncs three counts
  and the version; `required checks` is deliberately left alone because it comes
  from branch protection rather than from disk, and `posture` still watches it.
  This runs from the maintainer's machine only: `POSTURE_TOKEN` is read-only by
  design ([ADR 0061](docs/adr/0061-platform-posture-verified.md)), and granting CI
  `administration: write` so it could fix one advertising field would hand the
  pipeline the power to rewrite the repository's posture — a far worse trade than
  a command someone runs.

- **A single wrapper for talking to GitHub, because there were five.**
  `scripts/gh.py` replaces the `shutil.which("gh")` + `subprocess.run` block that
  had been copied into `audit_posture`, `schedule_census`, `red_streak_census`,
  `rerun_census` and, briefly, `sync_counts` — two of them identical to the
  character, each carrying its own lint suppression for the same command. This is
  the second instance of the class that produced `scripts/workflows.py` in round
  18, where one copied idiom was broken in three of its five copies. Three callers
  now share the wrapper; the two that remain are named in its docstring with the
  reason each was left (`audit_posture` borrows a different token per question,
  `rerun_census` raises a different error type and its tests are bound to that
  shape). Suppressions dropped from 96 to 95 and the ceiling moved down with them.

- **The test suite could be pointed at a real database, and nothing stopped it.**
  Every fixture that builds an app goes through `_app_with_tables()`, which calls
  `db.create_all()` and then `db.drop_all()`; the destination comes from
  `TEST_DATABASE_URL`, which `CLAUDE.md` tells people to set by hand when they
  want to run against another engine. One typo in a host or a database name and
  the whole schema is gone, permanently. `docs/ISO27001.md` had claimed A.8.31
  and A.8.33 as passing since they were first assessed, on the grounds that "the
  fixture refuses a real database" — but the thing that refuses is
  `scripts/a11y_fixture.py`, which is a different code path, tests only
  `"instance" in uri` so it catches only the dev SQLite shape, and declares its
  own role as `helper`, defined in `tests/test_script_roles.py` as "does not
  decide and is not cited as evidence." The most dangerous path had nothing on it
  at all. `tests/conftest.py` now refuses, at import time and before any fixture
  can touch a schema, any destination that does not say it is disposable. The
  rule is an allowlist rather than a blocklist — guessing every shape a real
  database might take never finishes, while an allowlist fails safe — and it
  reads the database name, not the whole URL, because a host called `test-db`
  says nothing about what lives in it. The direction that matters most is proved
  by launching a child pytest with a production-shaped URL and requiring the run
  to stop; the direction that must keep passing is bound to the value `ci.yml`
  really uses, read from that file rather than copied into the test.

- **The watcher that was built to notice our cron dying runs inside that cron.**
  Governance audit round 26 asked, for the first time, where this project fails
  *first* if the maintainer disappears for a year — the order of failure, not
  its frequency. The answer is that it does not fail, it goes quiet: of 114
  gates, the 109 that can block a merge all live in `ci.yml` and fire only on
  `push` and `pull_request`, and the 5 that can fire without anybody acting
  cannot block anything — and name the same single person as their watcher.
  GitHub disables scheduled workflows in a public repository after 60 days
  with no activity, which switches off the only trigger those 5 have left.
  `schedules-still-fire` exists specifically to catch that 60-day rule; its
  `born_from` has said so since round 10. It is enforced by a job in
  `scorecard.yml` — the very cron being switched off — and it promised a human
  would look within **90** days, longer than the window that creates the
  failure. The watcher arrived a month after the machine it watches had died,
  without breaking a single promise. `tests/test_watcher_windows.py` now holds
  the rule that at least one promise on a cron-only workflow must be shorter
  than the platform's silence window; not all of them, because one visit resets
  that clock for the whole repository, so the shortest promise is the one
  holding up the rest. The number 60 belongs to GitHub, so a test also requires
  the document a person reads to say where it came from. `schedules-still-fire`
  drops to 45 days, backed by a new 45-day **liveness row** in
  `docs/SECURITY-CADENCE.md` whose work is to review the time-driven things and
  **touch one Dependabot pull request** — one row closing two clocks that both
  belong to someone else. See [ADR 0074](docs/adr/0074-watcher-windows-fit-platform-silence.md).

- **Nothing in the alerting stack could fire on the *absence* of a signal.** All
  three rules in `deploy/loki-rules.yaml` are `count_over_time(…) > n`: they
  fire when bad events arrive. If the app stops, the log shipper stops, the disk
  fills, or a field is renamed so `| json` stops parsing, all three evaluate to
  zero forever and stay silent — which looks exactly like a healthy system. The
  other half was worse: `deploy/prometheus.yml` had no `rule_files` and no
  `alerting` at all, so the side that *pulls* every five seconds — the only side
  that can tell "quiet" from "dead" for an app that is legitimately idle at
  night — could not speak. `deploy/prometheus-rules.yaml` adds
  `MetricsTargetDown` (`up == 0`, `for: 1m`), which covers the app being down,
  the target being wrong, and the scrape token having expired, since a 401 also
  reads as `up == 0`. The `scrape` job proves it by **stopping the app** and
  waiting for the alert — the first gate in this project tested by taking
  something away, which is the direction a counting rule cannot test by
  definition. An `absent_over_time` rule on the Loki side was considered and
  rejected: a personal todolist with no traffic overnight is normal, and a rule
  that fires every night is a rule that gets silenced in two weeks — the
  principle [ADR 0037](docs/adr/0037-where-logs-go-and-what-shouts.md) sets out
  in its own opening.

- **A register of the governance audit rounds, because the number was being
  advertised without one.** The repository's About line and the OpenSSF badge
  worksheet both said twenty recorded audits. Going to count them turned up
  twenty-three, each one traceable — but only by grepping for the phrase
  "audit round N" across gates, ADRs and documents, which is not a thing a
  reader can be asked to do. `docs/AUDIT-LOG.md` now records, per round, the
  question it asked, a one-line result, and at least one place inside this
  repository that names it. A test holds four directions: the rounds run from
  one without gaps, every row carries a question and a result and evidence,
  every piece of evidence exists **and actually mentions that round** — a
  register of filenames nobody checks the contents of would pass with any
  name at all — and no round may be cited anywhere in the documents without
  having a row. The advertised count is checked against the number of rows,
  which is how the stale twenty was found in the first place. Dates are
  deliberately absent: they could not be established for every row from
  inside the repository, and a column that is right for some rows and wrong
  for others is worse than no column.

### Fixed

- **A dismissal justified by a fact with an expiry date, and nothing scheduled for
  that date.** `Scorecard/MaintainedID` was dismissed because the repository is
  younger than ninety days — accurate, and the register even said so: "a fact that
  expires on its own". Scorecard's documentation is explicit ("This check will only
  succeed if a GitHub project is >90 days old"), so the expiry is 2026-10-31. The
  row that revisits dismissed alerts falls due 2027-02-18, a hundred and ten days
  later — the same shape as [ADR 0074](docs/adr/0074-watcher-windows-fit-platform-silence.md),
  where our clock ran slower than the clock of the fact we were relying on. Worse,
  because the alert is dismissed, GitHub will not reopen one for the same rule, so
  the signal that would report an unmaintained repository is muted exactly when it
  starts to mean something. There is now a one-off review dated to the expiry.

- **`dependabot.yml` justified a decision by pointing at a safety net that
  GitHub removes under the same condition.** The file explains at length why
  version updates for `Pipfile.lock` are not enabled — a pull request almost
  every day for a single maintainer — and rests that on "pip security updates
  are already on", which answers the urgent question. GitHub pauses Dependabot
  for a repository once nobody has touched one of its pull requests for 90
  days, and the pause stops pull requests for version **and security** updates
  alike. The net and the thing it catches are removed together, by one
  condition, not two. The comment now says so, and the liveness row above is
  what actually holds it open.

- **The bus-factor row in the risk register measured the wrong axis.** It
  reduced "single maintainer" with "knowledge is forced into the machine, not
  the head: a gate for every rule". That is true of a second person arriving
  without context. It is not true of the first person leaving: all 109 blocking
  gates are *downstream* of that person rather than a stand-in for them. The
  register now carries two rows — knowledge transfer, and nobody pressing the
  button — because the treatments for them do not overlap at all.

- **The Prometheus scrape token was told to expire, by default rather than by
  choice.** The command in `docs/OPERATIONS.md` issued it without
  `--expires-days`, which means 90 days: monitoring goes blind one quarter after
  it is set up, and until now nothing in the system would have noticed. The
  documented command now passes `--expires-days 0` and says why a key held by a
  machine that runs continuously needs a lifetime somebody chose.

- **`scripts/sync_counts.py` did not know about the exported-rule count.** Three
  places advertise how many baseline rules `SKILL.md` ships, and all three had
  to be edited by hand every time a portable gate was added — the exact tax the
  script was written in round 25 to remove. It now syncs them too.

- **The DOI badge was never about the URL — Zenodo rate-limits GitHub's image
  proxy, and v2.2.0's fix for it was a wrong diagnosis.** That release changed
  the badge to the URL form Zenodo's own settings page hands out, on the
  reasoning that the old `badge/DOI/<doi>.svg` path was stale. The badge kept
  flickering. Asking the camo URL itself — rather than asking zenodo.org from
  here, which had answered 200 every time — gave the actual answer:
  `HTTP/2 502 · Invalid upstream response (429)`. Three requests per badge
  through camo put it beyond doubt: every `img.shields.io` badge and the
  OpenSSF one return 200/200/200, while `zenodo.org` returns 200/502/200. The
  earlier 200 that seemed to confirm the fix was a cache hit; this one came
  back `x-cache: MISS`. The image now comes from shields.io, the link target
  is unchanged, and a test holds every badge host to a list that says what was
  measured — so the next host has to be a decision rather than markdown copied
  off somebody's settings page.


- **The command that verifies a release was archived had itself stopped
  working.** `docs/RELEASE.md` carries a one-line check against Zenodo's API
  — the step that exists because GitHub's webhook page has reported both
  false-red and would one day report false-green. Zenodo now caps
  unauthenticated page size at 25, so the documented `size=50` returns HTTP
  400, and the naive pipe turns that into `KeyError: 'hits'` rather than
  anything that reads as a refusal. Found while cutting v2.2.0, whose
  archival it was supposed to confirm. The size is now within the cap and
  the request fails loudly, because the question being asked here — was this
  release archived — is one a parser crash cannot answer in either
  direction.


## [2.2.0] — 2026-08-21

### Added

- **A third colour theme, `sepia`** — warm paper tones, for eyes tired of
  looking at white and blue all day. Adding it changed no line of `core`:
  a directory with a manifest and a stylesheet is the whole contract, and
  the registry reads the disk on every request. Every pair the layout
  actually renders — body text, links, quiet buttons, labels, the primary
  button, the overdue badge — sits between 5.46 and 14.0 against WCAG 2.2
  AA's 4.5, in both light and dark, and three new entries in
  `.pa11yci.json` put a real Chromium behind that claim. Both modes are
  named explicitly there: the default is `auto`, decided from a sunrise
  table, so a scan that omitted the mode would have covered the light
  palette or not depending on what time of day CI happened to run.

### Fixed

- **A test said, in its own docstring, that a number over 100% was the thing
  it existed to prevent — and then asserted on the denominator instead.**
  `scripts/skeleton.py` prints one summary line per file: how many lines its
  skeleton costs against how many the file has. A one-line file reported
  `3 จาก 1 บรรทัด (300%)` and the guard written to stop exactly that,
  `test_a_one_line_file_does_not_report_more_than_it_has`, only ever checked
  that the denominator was 1. It never extracted the percentage, so 300%
  passed. The resolution is not the cap the number invites: a report has a
  fixed floor of two lines — the header and the summary itself — so a file
  shorter than that genuinely cannot be shrunk, and saying so is precisely
  what the tool's docstring says the number is for. Capping at 100% would
  hide that answer and make "100%" mean two different things. The line now
  interprets itself (`— อ่านทั้งไฟล์เร็วกว่า`) and the test checks both
  sides of the boundary rather than one.

- **The DOI badge used Zenodo's legacy image URL, and rendered only
  sometimes.** `zenodo.org/badge/DOI/<doi>.svg` is not the form Zenodo hands
  out any more; its GitHub settings page gives `zenodo.org/badge/<repo
  id>.svg`, which is what the README now carries. The three shields.io
  badges beside it never failed, which is what made the odd one out visible
  at all. The DOI itself is printed in three places in the README — twice in
  prose and once as the badge's link target — and none of them derived from
  `CITATION.cff`, so a test now holds all three to what that file declares.
  The badge image points at the repository id rather than the DOI, which
  means a correct-looking badge can sit on top of a wrong link target
  without anything looking odd to a reader.

- **The exported scaffolding told 83 rules to register themselves in a file
  it never shipped.** Of the 92 rules in `overlays/flask/`, 83 travel as
  `kind: suite` — "this box carries no enforcement for you; write your own
  test, then register it in your project's `gates.yaml`" — and the pillar
  those 83 lean on, `gates-registry-total`, travelled as prose alongside
  them. There was no `gates.yaml` in the box, no template, and nothing that
  made a downstream registry true: the test that enforces both directions
  here (every job has a gate, every test file is adjudicated exactly once)
  is bound to pytest, PyYAML and this repository's ASVS table, so it never
  left. A destination could read the same footnote 83 times without ever
  learning what a registry looks like or how it would know the registry had
  drifted. The box now carries `gates.yaml` itself — seeded with the nine
  scans it actually ships, so a fresh install starts with an index that is
  already true — and `gates-registry-total` is enforced by a scan rather
  than described: it checks that every gate points at a job, step or test
  file that exists, that every job in every workflow is covered by a gate,
  and that every test file is claimed by exactly one gate. Because a
  destination runs on bare `python3`, the scan reads YAML itself, over a
  deliberately narrow subset that raises on anchors, aliases, tags, tabs and
  multi-document files rather than skipping what it cannot parse — a reader
  kinder than the real thing reports green on files it did not understand.
  The evidence that it reads correctly is a comparison against PyYAML on the
  largest real files here: 108 gates and 28 jobs, over exactly the fields
  the scan consumes (ADR 0071).

- **The gate on theme colours checked only the values that were already
  hexadecimal.** Its name says `..._colour_values_are_valid_hex`; what it
  enforced was "values shaped like hex are well formed", and everything
  else passed in silence. `--accent: f0a868;` — a missing `#` — is a
  perfectly valid custom-property declaration, because custom properties
  accept almost any token sequence; it dies later, when `color:
  var(--accent)` resolves to something that is invalid at computed-value
  time, so the property falls back to `unset` and the element inherits its
  parent's colour. That is precisely the failure the parity test exists to
  catch — a theme that does not really deliver a colour — but that test
  compares variable *names*, so it passed too, and the accessibility scan
  passed as well, because a link wearing ordinary text colour has fine
  contrast. Proving the fix caught a second hole in the same rule that
  nobody had asked about: the pattern `#[0-9a-fA-F]{3,8}` also accepts five
  and seven digits, which CSS does not recognise as colours at all, so
  `#f0a86` failed exactly as silently. Both are closed; `rgb()` is refused
  too, deliberately, since hex in a theme file is the only place in the
  system where a colour is written.

### Changed

- **Repository settings the checker cannot read now still have a declared
  value.** `scripts/audit_posture.py` kept a register of merge-related
  settings that GitHub withholds from a least-privilege token, but the
  register recorded only *what the machine cannot see* — never *what the
  value ought to be*. A setting that cannot be verified therefore had no
  owner, and a setting with no owner had no default: `delete_branch_on_merge`
  sat off since the repository was created, so every merged branch stayed
  behind, and `git branch --merged` could not see them either, because
  rebase merges rewrite the commits. Sixty-four of them had accumulated.
  The register now carries the intended value and the reason beside each
  flag; the checker compares them when it can read them and reports what
  they *should* be when it cannot, and a quarterly row in
  `docs/SECURITY-CADENCE.md` gives the unreadable ones a human owner.
  Writing the register down immediately found a second gap of the same
  kind: squash merging was still offered, although rule 7 of
  `CONTRIBUTING.md` forbids it and explains why — a squash appends
  ` (#N)` to the subject, pushing anything near the limit past 72
  characters, and the commit-lint check that would catch it only runs
  once the merge has already landed. `required_linear_history` does not
  help, because a squash is linear too. It is now off, and declared.

- **The release checklist now verifies the DOI where the answer lives.**
  Counting webhooks (`gh api repos/:owner/:repo/hooks --jq 'length'`)
  answers whether the wire is connected, not whether the release was
  archived, and `v2.1.0` showed that the difference is not academic:
  GitHub reported *every* delivery as failed — 500s reading `context
  deadline exceeded ... giving up after 1 attempt`, a 403, a 502 — while
  Zenodo archived the release correctly and minted
  [10.5281/zenodo.22027978](https://doi.org/10.5281/zenodo.22027978).
  What timed out was the response coming back, not the work. A status that
  can be wrong in both directions is not a check, so `docs/RELEASE.md` now
  asks Zenodo directly, after the release rather than only before it, and
  records how to rotate the Zenodo token — which lives in the query string
  of the webhook URL, and therefore comes back in plaintext from any
  command that lists the repository's hooks.

- **That Zenodo token turns out to have no rotation path, and the register
  now says so.** Four routes were tried and measured: it is not listed among
  Zenodo's personal access tokens, because the GitHub integration holds one
  of its own; the linked GitHub account cannot be disconnected, because it
  is the login; switching the repository off and on again installs a *new
  webhook carrying the same token*; and revoking Zenodo's OAuth grant on
  GitHub cuts the opposite credential — the one Zenodo uses to fetch the
  release tarball — which would break archiving while leaving the exposed
  value alive. It is recorded in `docs/RISK-ASSESSMENT.md` as accepted, at
  the level the register's own formula produces, with the conditions that
  would reopen it. The attempt also invalidated the check written one
  commit earlier: "the hook `id` must be new" passes while the secret is
  unchanged, so the criterion is now a fingerprint of the value itself.

## [2.1.0] — 2026-08-20

> Four audit rounds (17–20), the first regression recheck of every round
> before them, a database design review, and a prose pass over every
> document. No behaviour of the application changed; what changed is what
> the project can prove about itself, and what it now notices on its own.

### Added

- **Two more governance audit rounds, and the first regression recheck** —
  round 17 asked what checks the checking code itself, round 18 stopped
  reading declarations and ran an experiment: twelve real defects planted
  in a `git worktree` copy of `main`, then measured who caught what.
  Standard tools alone (ruff, mypy, gitleaks) caught 4 of 12, and the one
  rule that looked redundant with ours — ruff's `S201`, "debug=True in
  Flask app" — turns out to be blind to the app-factory pattern this
  project uses and recommends. The rounds produced: a `scripts_coverage`
  floor for the code that enforces every other floor; `บทบาท:` on every
  script so the right kind of evidence is demanded of each; a membership
  check so a new decider cannot stay outside the register that requires
  logic tests (`lint_commits.py`, which blocks every commit and every PR,
  had been outside it all along); one workflow reader instead of five
  copies of an idiom that crashes on `on: [push]`; requirement-shaped
  rules ("every X must Y") joining the prohibition register; and a
  `governance` marker, derived from the files rather than typed by hand,
  that stops 480 file-reading tests from running four times per push.
  Every closed finding from rounds 1–18 was then rechecked against
  today's tree — 57 of 57 still hold, and the method is written down in
  `docs/GATE-LOG.md` with a six-month cadence row so it repeats.

- **Every document moved up a register, and the database design was reviewed
  against outside guidance** — the prose across `CLAUDE.md`, `README.md`,
  `CONTRIBUTING.md`, `docs/` and all 70 ADRs was lifted to a semi-formal
  register without changing a single meaning: the colloquial verbs this
  project had been writing since day one (`พัง`, `เน่า`, `โกหก`, `มั่ว`) are
  now `ล้มเหลว`, `ล้าสมัย`, `ให้ข้อมูลที่ไม่จริง`, `ไม่ถูกต้อง` — chosen per
  phrase rather than by blind substitution, because the same colloquial verb
  stood for "failed", "was destroyed", "became unusable" and "could not keep
  up" in different sentences. `SKILL.md` and `skill/` were regenerated from
  their sources rather than edited.

  Alongside it, [`docs/DATABASE-REVIEW.md`](docs/DATABASE-REVIEW.md) records a
  review of the schema against relational-design and high-performance RDBMS
  practice across eight axes — audit, history, masking, query performance,
  partitioning, backup and restore, APM support, and schema discipline. Nine
  areas already hold; ten gaps are written down with the condition that brings
  each one into scope, and **none of them were acted on**: the three that
  depend on measurement (composite indexes, audit partitioning, an index for
  the export query) require numbers first, in keeping with how
  `docs/PERFORMANCE.md` has decided everything else.

- **Round 20 asked what the calendar has actually done** — nineteen rounds had
  asked questions answerable from the files at hand. This one asked the first
  question that requires waiting: *how many times has anything the project
  promises to do "periodically" actually run?* Three kinds of promise turned out
  to be proven very unequally — the ones bound to a push (652 workflow runs, red
  immediately), the ones bound to the platform's own schedule (weekly Scorecard,
  Dependabot; watched by `schedule_census`), and the ones bound to a human
  calendar: **zero**. Every dated row in the review table carried a "last done"
  equal to the day the row was written, and the first genuine due date is
  2026-11-09. "0 overdue" was a statement about the project's age.

  Nothing can make time pass faster, so the round added the distinction rather
  than a mechanism: each row now declares `(ตั้งต้น)` or `(ครั้งที่ N)`, and
  `whats_pending.py` prints `ยังไม่เคยทำซ้ำเลย 22 จาก 22 แถว` on every run — a
  number that falls on its own as the reviews recur. Alongside it: the runtime's
  end-of-life date got an owner (a 180-day runway threshold and a freshness limit
  on the pinned table, where before it was a number shown on an admin page that
  no rule consumed); `flask data-doctor` — built in round 19 to answer a question
  that only means anything when asked repeatedly — got a three-month row; and
  conditional rows now declare whether a machine or a person decides them, with
  the release row checked against the newest version in this file.

- **Round 19 asked the data itself** — eighteen rounds had audited code,
  configuration, documents, CI and registers; all of it lives in git and can be
  rechecked by reading files. The data is the only part of the system that is
  neither in git nor visible to anyone but the user, and planting defects *in a
  live database* found three:

  - `flask audit-verify` answered `Audit chain OK — 0 entries verified` after
    the whole table was deleted, and `OK` after the tail was cut. It walked
    only the rows still present, and those rows did still link correctly. The
    proof it needed was already in the database — `tdl_audit_lock.last_hash`,
    the anchor ADR 0035 added to serialise writers — and nothing had ever read
    it. A severed tail is now a distinct `AnchorError`, because "row N was
    modified" sends the person on duty to the wrong place.
  - `flask create-user Alice` succeeded while `alice` existed. Identity
    compared usernames case-sensitively; the login quota compared them
    case-insensitively (ADR 0021). Both were right on their own, and together
    they let an outsider lock `alice` out by failing five logins against
    `Alice` — denial of service across accounts, requiring no knowledge of the
    target. Collisions are now refused at creation, which changes nothing for
    accounts that never collided.
  - `flask data-doctor` is new: four questions answered by reading the database
    alone — rows whose foreign key points at nothing (12 relationships), the
    audit chain and its anchor, usernames that collide when case-folded, and
    data past its retention window. **Read-only by design**: a tool that
    repairs on its own is a tool nobody dares run against production, and on
    the day it repairs the wrong thing nobody will know what was there before.

- **The measuring instrument of the comparison experiment was measured** —
  `scripts/asvs_probe.py` had been reading `.venv/`: 4,171 of the 4,299
  Python files it scanned in this repository belonged to libraries, and
  it reported three ASVS items as failing on the strength of Flask's own
  `SECRET_KEY = 'development key'`. The published numbers in
  `docs/comparison/` are unaffected — the measured apps carry at most 35
  Python files each — but what protected them was luck, not a mechanism.
  Chasing the three items down exposed three more ways the probe punished
  the better structure: prose about a secret counted as a secret, an
  authorization check had to spell `user_id` (not `require_admin` or a
  membership call), a closure was judged apart from the scope that
  already guarded it, and SQL interpolating a module constant counted the
  same as SQL interpolating a request.


- **The project has a DOI** — [10.5281/zenodo.22015133](https://doi.org/10.5281/zenodo.22015133),
  minted by Zenodo when `v2.0.2` was published, with the author's
  affiliation recorded from `.zenodo.json` rather than from whatever the
  Zenodo profile said at that moment. The concept DOI always resolves to
  the newest version; each release also receives its own. `v2.0.0` and
  `v2.0.1` are not archived and never will be — Zenodo does not work
  retroactively, and the release notes of each say so.

## [2.0.2] — 2026-08-19

### Changed

- **The release runbook now verifies the archive connection instead of
  assuming it** — `docs/RELEASE.md` gains a one-line check
  (`gh api repos/:owner/:repo/hooks --jq 'length'`) that must return 1
  before a release is created. Signing up for Zenodo and switching on a
  *specific repository* are two different steps, and only the second
  installs the webhook. Two releases were tagged on the belief that the
  first step implied the second; Zenodo does not archive retroactively,
  so neither is citable. The signal was available in one command the
  whole time — the same shape this project keeps finding: not missing
  data, missing the habit of looking.

## [2.0.1] — 2026-08-19

### Changed

- **Citation metadata carries an affiliation** — `CITATION.cff` and
  `.zenodo.json` now name Burapha University alongside the author, so every
  archived release records it rather than inheriting whatever the Zenodo
  profile happens to say at the time.

*This release exists to be archived.* Zenodo mints a DOI only for releases
created after the repository is connected, and `v2.0.0` was tagged minutes
before that switch was flipped — so the boundary release and the first
citable one are not the same tag. Nothing else changed.

## [2.0.0] — 2026-08-19

*Released with 8 SBOMs (one per dependency category) signed keyless with cosign
and 8 signature bundles attached by the release workflow, plus SLSA build
provenance. Archived on Zenodo for citation.*

**The version number changes for a legal reason, not a functional one.** The
project moved from MIT to AGPL-3.0-or-later (documentation to CC BY-SA 4.0),
which is a breaking change for anyone downstream even though no interface moved.
Everything published through `v1.6.0` remains MIT forever for whoever received
it. What else is in this release is sixteen rounds of governance audit — the
detail is below.

### Added

- **The project is relicensed** — AGPL-3.0-or-later for the software,
  CC BY-SA 4.0 for the documentation and decision records (ADR 0070,
  replacing ADR 0038). The MIT decision rested on a stated assumption —
  "there is nothing here that needs copyleft to protect it" — that
  expired within a week: sixteen audit rounds turned the most valuable
  part of this repository into a *method that machines can check*, and
  the whole of it could be lifted with nothing coming back. AGPL closes
  the shape that actually fits: the likely reuse is as a service, which
  plain GPL does not reach. Staying OSI-approved was a condition of the
  choice rather than a side-effect — a project whose every page argues
  for checkable evidence cannot afford a false claim on its own front
  page. **Everything published through `v1.6.0` remains MIT forever for
  anyone who received it**; rights already granted cannot be withdrawn,
  and this change binds only what follows. A commercial exception is
  available from the copyright holder, who is still the only one.
- **Citation metadata** — `CITATION.cff` and `.zenodo.json`, so a tagged
  release can be archived with a DOI. A license governs reuse; it says
  nothing about who published what first, and a dated public record is
  the only thing that does.
- **Removing a control is now a decision someone signs** — ADR 0069 and
  `[tool.todolist.removals]` (round-16 audit). Fifteen rounds had asked
  what was *added*; this one measured what happens when something is
  *taken away*, by deleting real things eleven times and watching what
  turned red. The split was sharper than expected: registers checked
  against reality — a column, a route, a file, a job — cannot be removed
  quietly, while registers checked against another document can, because
  deleting both sides at once still counts as "matching". A whole gate
  and its test file could be removed with CI fully green after six
  tidying steps, each of which the previous check's error message asked
  for, ending with one number edited in the README; 37 rows across three
  paper registers could be deleted with nothing objecting at all. The
  counts may grow freely — adding is already governed — but shrinking
  means editing a number, which is what turns a deletion from a
  side-effect of cleanup into something with a name attached to it.
- **Every control that is only a sentence is now counted** —
  `tests/test_declared_prohibitions.py` (round-14 audit) and a floor on
  the register (round-15). `CLAUDE.md` carries 61 distinct prohibitions;
  10 of them ask for judgement a machine should not make, leaving 51 that
  a machine could check and **19 that nothing checked**. What made this
  urgent is that none of the 19 was being violated: the rules were held
  by discipline, which is enough for the person who wrote them and not
  for anyone else, including the same person six months later. Eleven now
  have a mechanism, each paired with the exact sentence it enforces, and
  the pairing is checked both ways — a rule that is withdrawn must take
  its check with it, or the check becomes a rule nobody decided. The
  first run found a real violation: a test built its own tables and never
  dropped them, which on the MySQL and MariaDB jobs leaves rows behind
  for whatever runs next.
- **Images the CI actually runs are pinned by digest** —
  `tests/test_stack_image_pinning.py` and the `docker-compose` Dependabot
  ecosystem (round-15 audit). Three separate gates already required
  pinning — actions to a SHA, the base image to a digest, CI tooling to
  hashes — and none of them opened a compose file. Eleven third-party
  images were pulled by moving tag across 11 of 25 jobs, including
  `ghcr.io/zaproxy/zaproxy:stable`, the scanner whose verdict decides the
  DAST gate; a green result from last week could not be reproduced,
  because nothing recorded which bytes produced it. Pinning alone would
  have been worse than nothing, so it ships with the mover: Dependabot
  splits `docker-compose` from `docker`, which reads only `Dockerfile`,
  and only the latter had ever been declared. Confirmed by measurement
  rather than assumption — the new ecosystem opened its first PR within
  minutes, proposing nine major-version jumps, which is why it is now
  restricted to digests the same way the base image is.
- **Ratchets that were prose are numbers now** — `check_ratchets.py`
  gained the mypy strict list (round-14) and the prohibition register
  (round-15). ADR 0068 had made every *numeric* floor carry something
  that turns it, which left the ratchets written as sentences untouched:
  "expand the strict list, never shrink it" had no number at all, and its
  stated goal — the whole app, by Phase 2 — had expired sixteen phases
  earlier while covering 34 of 72 modules. Counts differ from percentages
  in two ways that matter: the slack is zero, because a count only moves
  when someone edits a list, and the downward direction has to be checked
  here, because no tool owns it the way `fail_under` owns coverage.
- **A decision that was replaced now says so on its own page** —
  `tests/test_adr_index.py` checks supersession three ways (round-14
  audit). Every register in the repository has been verified both ways
  since round 9 except the oldest and most cited one. ADR 0035 had
  replaced part of ADR 0032 a week earlier; ADR 0032 said nothing, the
  index listed it as plainly accepted, and the module docstring in
  `app/audit.py` — the first thing anyone reads before touching that
  mechanism — pointed at it as current, describing the exact locking
  strategy `CLAUDE.md` forbids returning to.
- **One page that answers what is pending** — `scripts/whats_pending.py`
  (round-13 audit), corrected in round 14. Answering "what needs
  attention" meant opening eight places. The reader holds no state of its
  own; it reads the sources that already exist and prints one page. Its
  first version over-reported by three of eight items, because the
  section it reads mixed open work with decisions that were closed and
  one feature that was finished — a reader that walks past its own
  heading is one heading away from being wrong, on a day when nobody is
  watching it.
- **A register for decisions that were deliberately postponed**
  (round-12 audit) — `docs/GOVERNANCE.md`. Deferring something was
  previously recorded only inside whichever ADR happened to mention it,
  so the set of open deferrals could not be read anywhere. The test that
  enforces it caught the ADR written in the same round: it had used
  "not closed yet" for something that was deliberately out of scope,
  and a label used loosely makes the register grow with things that do
  not belong in it.
- **Every signal now names who receives it and by when** — `severity` in
  `gates.yaml` gained a third value and a companion field (ADR 0066,
  round-10 audit). The field had existed since ADR 0039 and 97 of 99
  gates declared themselves `blocking`, but nothing ever compared that
  claim against reality: 3 of the 30 checks are not required, and two of
  those carried gates that called themselves blocking — the gate that
  verifies the platform's own posture, and the one that signs what we
  ship. `blocking` is now only allowed on a job that runs on
  `pull_request`; everything else is `watched` or `warning` and must
  declare `watched_by` — who sees it, within how many days, and by what
  mechanism, which has to resolve to something that exists. Writing down
  "the maintainer, within 7 days" turns silence from the normal state
  into something that can be missed.
- **The Security tab is now part of the posture check** — every alert
  that still exists must either have a line in
  `.github/accepted-code-scanning-alerts.txt` or be dismissed with a
  reason, and every line in that register must still match a real alert
  (round-10 audit). Four alerts, three of them high, had sat open for 5.6
  days; all four were already adjudicated inside the repo, but nothing
  connected the two, and the existing review row covered only alerts that
  were already dismissed. Accepting an alert is not the same as
  dismissing it: `VulnerabilitiesID` is deliberately left open because
  GitHub never reopens a dismissed alert, so silencing it today would
  silence the next vulnerability too.
- **A census for schedules that stop firing** —
  `scripts/schedule_census.py` (round-10 audit). ADR 0064 closed "a
  workflow GitHub refuses to start produces zero jobs"; the layer above
  it was still open: a workflow that is never triggered produces *zero
  runs*, which looks exactly like "no run ever failed" in every tool we
  had. The weekly cron had fired exactly once in the repository's life,
  and nothing would have noticed if it stopped. Dependabot appears in the
  report as something no machine can check — there is no public endpoint
  for its last run — so it is printed with that label and given its own
  review row instead of being guessed either way.
- **The retention job now leaves a trace when it fails** —
  `deploy/systemd/todolist-purge-failed.service`, wired through
  `OnFailure=` (round-10 audit). `docs/ROPA.md` states retention periods
  as legal fact, and they are only true while `todolist-purge.service`
  succeeds on schedule; the gate covering it claimed "failures are
  visible" but reached only as far as the exit code handed to systemd.
  This is a signal, not an alert — it goes nowhere, because nobody is on
  call (ADR 0037) — but the failure is now greppable and there is one
  line for a deployer to hang their own notifier on.
- **Every job declares how long it should take** — `timeout-minutes` on
  all 28 jobs (ADR 0067, round-11 audit). None of them had one, so the
  ceiling was GitHub's six-hour default, which is not a ceiling anyone
  chose. The cost is not machine time but the ability to decide: a job
  that is stuck and a job that is merely slower than usual give identical
  signals. It had already cost something — `dialect (mysql-8)` took 30+
  minutes against a normal 10 and was cancelled while it was 92% of the
  way through. The numbers come from what was measured, multiplied by
  the slow-runner factor measured the same day, with a floor and a
  ceiling so the value stays defensible in both directions.
- **`within_days` is now measured against reality** —
  `scripts/red_streak_census.py` (round-11 audit). Round 10 made every
  non-blocking gate declare when someone would see it; the only thing
  checking that was the *shape* of the number. Pairing "first failure →
  next success" on `main` over the same four-day window shows red that
  blocks someone standing for **0.4 hours** and red that blocks nobody
  standing for **14.6 hours** — a factor of 36 on one repository, and
  the first quantitative evidence for everything round 10 assumed. The
  measurement is deliberately called an *upper bound on time-to-fix*,
  not MTTA: it does not know when a human looked.

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

- **Checks now run before the push, not only after it** (round-15
  audit). Closing the round-14 gaps took nine CI runs, five of them red
  and 77 minutes, and every one of the five failed on a test that runs
  locally in seconds: a generated file not regenerated, a new gate absent
  from the overlay, a count advertised in the README left behind. They
  are one class — change one thing, three others must follow — and the
  tool that knows the answer was already on the machine, with nothing
  calling it while the answer was still cheap. A `pre-push` hook runs
  that subset in about nine seconds, and only for pushes that touch the
  files the class comes from: a hook that costs more than it saves is a
  hook people learn to skip, after which it guards nothing.
- **The count the badge worksheet advertises is now read from the
  registry** in more places than one (documentation sweep after round
  16). The supply-chain axis grew to 20 gates; a test kept
  `docs/BEST-PRACTICES.md` honest, while `README.md` and
  `docs/RISK-ASSESSMENT.md` carried the same number with nothing
  checking them — the recurring shape where a fact lives in four files
  and is enforced in one.

- **Everything that waits now declares its own ceiling** (round-11
  audit, ADR 0067 note 1). The project has always insisted that values
  that matter live in a file a reviewer can see — token permissions in
  the workflow rather than the Settings page, alert rules in a file
  rather than clicked into a UI — but time was the last configuration
  layer still inherited from other people's defaults, and those defaults
  disagree with each other: six hours, thirty seconds, and in two places
  no ceiling at all. `ldap3`'s `receive_timeout` and pymysql's
  `read_timeout` both default to waiting forever; a directory or database
  that accepts the connection and then goes quiet held a worker until
  gunicorn killed it, and the container ships with one worker by default.
  Both now declare a bound, connections are checked before they leave the
  pool, and all eleven `subprocess.run` calls in `scripts/` carry a
  timeout — a single unanswered command used to consume a job's entire
  budget and then report "the job timed out", which points at the wrong
  thing.
- **The instruction file moved a hundred lines out and lowered its own
  ceiling** (round-11 audit). `CLAUDE.md` hit 1,265 of 1,265 lines,
  which is the moment ADR 0065 was written to produce: when it is full,
  move content to a dedicated document *and ratchet the ceiling down*,
  rather than raising it. The gate machinery — the index and its two-way
  checks, red evidence, layers, severity and watchers, the censuses, the
  scanner scope, and everything exported to other projects — now lives in
  `docs/GOVERNANCE.md`, verbatim. Eleven lines of pointers stay behind,
  carrying the three mistakes people actually make. The mechanism proved
  itself on the way: the `timeout-minutes` rule could not be written into
  `CLAUDE.md` in the previous pull request because the file was exactly
  full.

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

- **The exemption register had never been consulted, not once** — two
  entries, zero reads (round-10 audit). `EXEMPT` in
  `scripts/audit_posture.py` listed the checks that are allowed not to be
  required, but it filtered a set its own members could never be in: the
  jobs it named do not run on pull requests at all. The check now asks
  the third direction — every check the repository can produce but does
  not require must be declared with a reason — and that direction caught
  something the moment it was written: `posture` itself had never been
  registered since the day it was created, because nothing asked.


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
work; the reasoning for each decision lives in the 78 records in
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

[Unreleased]: https://github.com/sayam/flask-todolist/compare/v2.2.0...HEAD
[2.2.0]: https://github.com/sayam/flask-todolist/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/sayam/flask-todolist/compare/v2.0.2...v2.1.0
[2.0.2]: https://github.com/sayam/flask-todolist/compare/v2.0.1...v2.0.2
[2.0.1]: https://github.com/sayam/flask-todolist/compare/v2.0.0...v2.0.1
[2.0.0]: https://github.com/sayam/flask-todolist/compare/v1.6.0...v2.0.0
[1.6.0]: https://github.com/sayam/flask-todolist/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/sayam/flask-todolist/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/sayam/flask-todolist/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/sayam/flask-todolist/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/sayam/flask-todolist/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/sayam/flask-todolist/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/sayam/flask-todolist/releases/tag/v1.0.0
