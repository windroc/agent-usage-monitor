Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-873-logged-out-claude-account-report-auth-an base_ref=156b93b40bbdbf3725ccb16eb88e8efae4290ca1 review_round=1 input_sha=92142df68d2e

# Input

## Requirement (TASK-873)

Title: Logged-out Claude account: report auth and show needs-login instead of disabling the probe
Repo: windroc/agent-usage-monitor
Link: TASK-873
Precedence: the user's requirements since the last build > the user's instructions > the PRD (none linked); within each, newer > older.

### Problem

A logged-out Claude account shows only a stale ⚠ in the widget and its probe silently disables itself.

Observed 2026-10-22 on one Claude account dir:

* `claude auth status` → `"loggedIn": false, "authMethod": "none"`.
* `/usage` in that state prints only the session cost screen (Total cost, durations, token counts), no plan limits and no auth error text.
* The parser finds no auth marker (`agent_usage_monitor/claude_usage.py:183-187`), so the result is `unrecognized`; `agent_usage_monitor/claude.py:145-151` then sets `usage_disabled_version`, and the probe stays off until Claude Code changes version (`claude.py:120-125`).
* After 6 h the row turns stale (`derive.py:8`, `derive.py:42`) and the widget prefixes ⚠ (`macos/Widget/Snapshot.swift:119`). Nothing tells the user to log in.

(Line numbers are from the issue text; verify against the source and follow the source where it differs.)

### Requirement

1. Detect a logged-out account as `auth` (existing kind, `claude.py:25`), not `unrecognized`. Suggested: run the official `claude auth status` (JSON, `loggedIn`) with the probe's env before `/usage`, or treat the cost-only `/usage` screen as logged out; pick one and justify in the PR (record the choice and its justification in the plan doc so the PR description can cite it). Stay within the PRD: no reading credential files or Keychain ourselves, no token refresh. The Makefile `check` target greps code for forbidden strings (credentials.json, oauth, security, etc.); keep it passing.
2. An `auth` result must not set `usage_disabled_version`; the next run retries, so logging in recovers without manual snapshot edits.
3. The widget shows that the account needs login (e.g. a distinct marker or short text instead of the plain stale ⚠). Keep medium's 3-account fit.
4. Tests for: logged-out detection, no disable on auth, recovery after login (Python unittest under tests/, and Swift tests in macos/Tests/main.swift for the widget/snapshot logic as fits the repo).

### Process

UI change: stop before S6 and post opaque light + dark previews; S6 review starts only after the user approves. So: after S5 (implementation pushed), do not start S6; produce opaque (non-transparent background) light-mode and dark-mode preview images of the widget's medium (and any other affected) family showing a needs-login account alongside normal accounts, commit nothing extra for them unless the repo keeps such previews (e.g. under docs/images), save them under <WORKDIR>/tmp/, and stop, reporting their paths. This environment is Linux without Swift/Xcode: if real widget rendering is impossible, render a faithful mockup (e.g. HTML/SVG → PNG, following macos/Widget layout, fonts, colors and sizes) and say it is a mockup.

### Conventions and git rules

- Write code, docs and commits in the repo's conventions (no CLAUDE.md/AGENTS.md; follow README.md, docs/, and surrounding code style; the pre-push PII scan `tests/pii_scan.py` must pass — no personal data such as real account paths, emails or usernames in tracked files).
- Default branch: `main`. Push only `TASK-873-logged-out-claude-account-report-auth-an`; force-push only with `--force-with-lease`; never merge into or touch any other branch; merge, never rebase.
- **No mutation testing**, whatever a spec, plan or reviewer asks: while building, reviewing or testing, never modify the source to see what happens: no manual or tool-driven mutation testing (mutmut etc.), not even briefly or in a throwaway copy that is then run; never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call such as `os.listdir`, leaving the code under test unmodified. Every brief to a sub-agent (producer, reviewer) carries this rule.

### Docs

The plan doc stays where autopilot puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

Work only in `<WORKTREE>` on branch `TASK-873-logged-out-claude-account-report-auth-an`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <WORKTREE> push -u origin TASK-873-logged-out-claude-account-report-auth-an`.

# Verify

`make check` (macOS only: needs xcrun swiftc, codesign, plutil; runs pii-scan, Python unit tests, swift-test, app build and the NFR-1 grep)
CI checks: ["make check"]

# Progress log

- S1: mode=stay, branch TASK-873-logged-out-claude-account-report-auth-an, publish=ci (no PR yet)
- observation: in an empty CLAUDE_CONFIG_DIR, claude 2.1.309 `claude -p … /usage` exits 0 printing only the cost screen (Total cost / durations / code changes / Usage tokens) → parse() raises `unrecognized`; `claude auth status --json` exits 1 printing JSON with `"loggedIn": false, "authMethod": "none"`.
- decision(detection): use the official `claude auth status --json` (`loggedIn` is exactly false), run with the probe's env and dir, only after `/usage` gives `unrecognized`, or `timeout` from a process that exited (non-zero exit or empty output); not before every probe. Why: official, structured, documented signal vs. guessing from the cost screen (which a logged-in `-p` session might also print for other reasons, and whose text Claude Code may change); lazy, so a healthy account pays no extra claude launch per run; a real hang (no exit) skips it so a stuck probe costs no extra 10 s. Unknown/failed/non-JSON auth status → keep today's behaviour.
- decision(stale-disable): a row already disabled (usage_disabled_version set, version unchanged) also checks auth status; logged out → `auth`, and the disable is cleared, so accounts disabled by this bug before the upgrade recover after login without snapshot edits.
- decision(snapshot): new row field `needs_login` (bool, default false): true on an `auth` result, false on a successful probe, unchanged on other failures; the row's windows are kept as cache like any failed probe.
- decision(widget): a `needs_login` row shows the client title without ⚠ and, instead of its bars, a short yellow notice (now `needs login · claude /login`, see user feedback below); the account line stays. Row heights are unchanged, so medium still fits 3 accounts.
- S5 task 1 done: 4d83116 red=20 (18 failures, 2 errors: new auth tests, changed call counts, needs_login key)
- S5 task 2 done: cdd9065 red=14 (Swift compile errors: loginNotice, needsLogin, notice missing); swift-test ok with a local Linux Swift 6.1.2 toolchain (Foundation-only files); AgentUsageMonitorWidget.swift (SwiftUI) not compilable here, CI builds it
- S5 pushed: git push -u origin TASK-873-logged-out-claude-account-report-auth-an @cdd9065
- process: user requires stop before S6 with opaque light + dark previews; S6 starts only after the user approves
- stop(user gate) before S6 @cdd9065: previews <WORKDIR>/tmp/TASK-873-widget-preview-light.png and <WORKDIR>/tmp/TASK-873-widget-preview-dark.png (HTML mockup rendered with headless Chromium; source <WORKDIR>/tmp/preview/widget.html). Next: on the user's approval, start S6 r1 (pinned panel, verification=ci once a PR exists).
- user requirement (preview feedback): English notice `needs login · claude /login` (lowercase like `resets:`) unless it no longer fits medium; detection approach approved as built; push and stop again before S6; no new mockups (user previews on the Mac).
- fix(user) done: 7220642 red=1 (swift-test login_notice); notice ~180 pt at 13 pt semibold fits medium's 239 pt bar columns; swift-test ok, pii-scan ok, README test ok; pushed.
- stop(user gate) before S6 @7220642: awaiting the user's approval on the real Mac.
- user requirement: widget approved on the real Mac at 7220642; proceed to S6 and finish (draft PR, CI).
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- S6 r1 @7220642: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (command=ci-verdict.py on PR #12, make check success, exit code=0, tests=unknown, failures=0) -> converged
- S7: residual NON-BLOCKING: correctness#1 (see Review items), verification#1-#2 (evidence only)

# Review items

## S6 r1
- correctness#1 (NON-BLOCKING): agent_usage_monitor/claude.py:168-174: the unrecognized→disable return (and the still-disabled return at :142) does not reset needs_login, and store.write keeps the earlier row value. Repro: run 1 is logged out, so needs_login=True. The user logs in. Run 2's /usage output is unrecognized and auth status reports loggedIn true, so the row is disabled with needs_login still True. The widget then shows `needs login · claude /login` for an account that is logged in, and keeps showing it until the claude version changes. Fix: set needs_login=False in both disable returns, since _logged_out has just answered not-false there.
- verification#1 (NON-BLOCKING): python3 <AUTOPILOT>/scripts/ci-verdict.py --worktree <worktree> --sha 722064233d97dc160231455bc628c61937a2eba0 --plan-doc <plan_doc>: exit 0; CI at 7220642 passed: make check (success); tests run/failed: unknown (CI summary gives no count)
- verification#2 (NON-BLOCKING): reviewed_sha 722064233d97dc160231455bc628c61937a2eba0; HEAD before and after both equal reviewed_sha; git status --porcelain empty before and after

# Notes

- Python tests: `python3 -m unittest discover -s tests -t .` (~55 s); fake claude in tests/helpers.py answers `auth status` from cfg `auth_status`/`auth_exit`/`auth_hang`.
- No swiftc on this Linux host: Swift tests and widget build only run in CI (`make check` on macos-26).
- Widget content is forced dark; light system → opaque Color(white: 0.11) card, dark system → thinMaterial.

# Task list

Global constraints:
- Snapshot schema stays 1; new row key `needs_login` (bool), default false in `store.default_row()`.
- `claude.refresh` auth fields: `{"needs_login": True, "usage_disabled_version": None}` with kept=True and the existing `auth: <description>` stderr line; success fields gain `needs_login=False`.
- Auth status argv: `["auth", "status", "--json"]`, same probe_dir/env as `/usage`, timeout `version_timeout`; logged out only when stdout parses as a JSON object whose `loggedIn` is exactly `false` (exit code ignored: it is 1 when logged out).
- Swift: `Row.needsLogin: Bool?` (`var … = nil`, decoded from `needs_login`); `DisplayRow.notice: String?` (`var … = nil`); notice text `needs login · claude /login`.
- NFR-1 grep in Makefile `check` must stay clean (no `oauth`, `security `, `credentials.json`, … in code/tests); no credential files or Keychain reads; no token refresh.
- No mutation testing.

### Task 1: Detect logged-out Claude accounts as auth and keep the probe enabled

Files: agent_usage_monitor/claude.py, agent_usage_monitor/store.py, tests/helpers.py (fake claude answers `auth status`: cfg `auth_status` JSON text, default logged-in JSON, `auth_exit`), tests/fixtures/claude-usage/logged-out.stdout.txt (observed cost screen), tests/test_claude.py, tests/test_store.py, tests/test_cli.py (row key sets), README.md (Claude probe paragraph: logged-out → auth, needs_login, no disable).
Produces: `claude._logged_out(probe_dir, env, timeout) -> bool`; snapshot row `needs_login`.
Tests first:
- logged-out fixture + auth status `loggedIn:false` → kind auth message, fields `{"needs_login": True, "usage_disabled_version": None}`, kept; calls = [/usage, auth status] (no --version).
- cost-screen fixture with auth status logged in / non-JSON / exit with no output / claude auth hang (timeout 1) → unrecognized → disabled as before.
- non-zero-exit/empty /usage + logged out → auth; hung /usage (timeout) → no auth status call.
- disabled row (same version) + logged out → auth, disable cleared; disabled row + logged in → stays disabled (calls: --version, auth status).
- recovery: auth result row, then fake logs in (USAGE) → success, needs_login False, usage_disabled_version None.
- collect end-to-end: logged-out → row needs_login true, usage_disabled_version null, stderr `auth:`; next collect after login → needs_login false, source usage.
- default_row / row key sets include needs_login False.
- update existing call-count expectations (test_version_disable_cycle, test_version_failures, test_config_dir_for_other_accounts).
Checks: `python3 -m unittest discover -s tests -t .`, `python3 tests/pii_scan.py`, the Makefile NFR-1 grep over agent_usage_monitor tests bin macos.
Commit: `fix(claude): report a logged-out account as auth and keep probing it`

### Task 2: Widget shows needs-login instead of stale bars

Files: macos/Widget/Snapshot.swift (Row.needsLogin, DisplayRow.notice, rows()), macos/Widget/AgentUsageMonitorWidget.swift (render notice in compact and large rows), macos/Tests/main.swift, README.md (widget paragraph).
Consumes: snapshot row `needs_login`.
Tests first (Swift, run on CI via make swift-test): rows() for needsLogin true (stale or not) → title `claude` without ⚠, bars [], notice set, account kept; needsLogin false/nil → unchanged; loadSnapshot decodes `needs_login`; fit compact with 3 accounts incl. a notice row (with account) fits 155-32 like normal rows; titleWidth unaffected (no ⚠).
Checks: none runnable locally (no swiftc on Linux): review by reading; CI `make check` runs swift-test and builds the widget.
Commit: `feat(widget): show needs-login for a logged-out account`
