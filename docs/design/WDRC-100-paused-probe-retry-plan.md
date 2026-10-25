Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=WDRC-100-paused-claude-probe-retries-on-a-user-re base_ref=3ccf863ff925b154a1e5e81987dac9408fb00147 review_round=2 input_sha=25459cc51b86

## Input

WDRC-100: Paused Claude probe retries on a user refresh and every 6 hours

Repo: windroc/agent-usage-monitor

## Problem

A paused Claude account (`usage_disabled_version` set, widget reason `/usage unreadable · paused`) only recovers when `claude --version` changes or someone deletes the field from `snapshot.json` by hand. On 2026-10-25 one transient unrecognized output (00:28, before WDRC-97's 3-strike rule) paused a healthy, logged-in account for about 10 hours. A manual probe at 08:35 parsed fine. The user had to clear the field with a Python one-liner.

Source:

* `agent_usage_monitor/claude.py:176-183`: while `usage_disabled_version` equals the current version, every run skips the probe and returns the paused reason. There is no retry.
* `macos/Host/main.swift:111-123`: a widget click (tap, refresh arrow) and the LaunchAgent run the same `collect --emit-alerts`, so a click cannot ask for a retry.

## Acceptance criteria

* **Retry on click:** a refresh the user starts (widget tap or refresh arrow: `agent-usage-monitor://refresh`) probes paused accounts once. `collect` gets a flag for this, e.g. `--retry-paused`. The LaunchAgent and the settings window's periodic refresh do not pass it.
* **Retry on a timer:** a paused account is also probed once its pause is 6 hours old. Record when the pause started (e.g. `usage_disabled_at`, epoch seconds) next to `usage_disabled_version`.
* **Retry result:** if the retry parses, the account recovers as on any success (pause, count and `error` cleared). If the output is unrecognized again, the pause stays and its clock restarts. It does not take 3 more strikes. Logged-out (`auth`) behaves as today. Other failures (`timeout`, etc.) keep the pause and restart its clock.
* A pause recorded before this change (no `usage_disabled_at`) counts as older than 6 hours, so it is retried on the next run.
* README's description of the disable rule and of the widget click is updated.
* Unit tests cover: click retry, success and failure; timer retry before and after 6 h; a pause without `usage_disabled_at`; the LaunchAgent run does not retry before 6 h. A Swift or host test checks that the click path passes the flag and the timer path does not.
* `make check` passes.

## Out of scope

The 3-strike rule itself (WDRC-97), widget layout, Codex.

## Rules and conventions

* Write code, docs and commits in the target repo's conventions (its `CLAUDE.md` / `AGENTS.md`, if any, and the surrounding code's style, comment density and naming). The default branch is `main`.
* Push only branch `WDRC-100-paused-claude-probe-retries-on-a-user-re`; force-push it only with `--force-with-lease`. Never merge into or otherwise touch any other branch, including `main`.
* **No mutation testing**, whatever a spec, plan or reviewer asks: while building, reviewing or testing, never modify the source to see what happens: no manual or tool-driven mutation testing (mutmut etc.), not even briefly or in a throwaway copy that is then run; never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call such as `os.listdir`, leaving the code under test unmodified. Every brief to a sub-agent (producer, reviewer) carries this rule.

The plan doc stays where autopilot puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

Work only in `<WORKTREE>` on branch `WDRC-100-paused-claude-probe-retries-on-a-user-re`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <WORKTREE> push -u origin WDRC-100-paused-claude-probe-retries-on-a-user-re`.

## Verify

`make check` (pii-scan, unit tests, swift-test, app build, grep and plist checks; needs macOS: runs on CI)
CI checks: ["make check"]

## Progress log

- decision(switch): the user's instruction moved this ticket from build to light-build; the build's plan and spec (S3 r1 stopped before verdicts) are set aside in .autopilot/dropped-build/
- decision(publish): pr.py start -> publish=ci (pull_request workflow check.yml), no PR yet
- S5 task 1 done: 845a024 red=47 failures + 11 errors (new and updated tests in test_claude/test_store/test_cli run against the base revision's agent_usage_monitor copied to tmp/red; code was drafted before the tests, red checked after)
- S5 task 2 done: 1cfc98f red=3 failures + 2 errors (MainTest flag/help, click collect; test_launchagent_run_keeps_pause passed red: pre-change behavior it guards)
- S5 task 3 done: 990f7b1 red=not run locally (no swiftc on Linux); Swift checks run on CI make check
- S5 task 4 done: 8381aca red=1 (test_paused_retry)
- mid-run input (user requirement, round 2, newer than and over the input): "Replace the fixed 6-hour retry with exponential backoff: first retry 5 min after the pause starts, then double on each failed retry (5m, 10m, 20m, ... ) capped at 6 h; persist the schedule (e.g. usage_disabled_at + usage_retry_after_s), clear it on success; a failed click retry also doubles; an old pause without schedule fields retries on the next run. Tests: doubling, the 6 h cap, reset on success, old pause. Click retry (--retry-paused) stays as specified. Still light-build." -> Tasks 5 and 6 added
- decision(backoff): usage_disabled_at = when the pause started or its last retry ran; usage_retry_after_s = wait from then to the next timer retry (300 on a new pause; a failed retry, click or timer, sets min(2 * wait, 21600)); due when either field is not a positive int / int, or now - usage_disabled_at not in [0, wait). An old pause (no schedule) retries next run; if that fails, the wait doubles from 300 to 600. Exactly 300 s, as asked: a LaunchAgent run a second early takes the first retry one run later (10 min).
- S5 task 5 done: 6e31a3d red=67 failures + 3 errors
- S5 task 6 done: e5f46ae red=not run separately (README test and text edited together; the old text fails its assertNotIn)
- S5 done: unit suite (260+ tests) OK locally; pushed
- pr.py push opened draft PR https://github.com/windroc/agent-usage-monitor/pull/3
- S6 r1 peek: ci-verdict.py exit 3 NO_CI (gh api check-runs: HTTP 403 Resource not accessible by integration); `gh pr checks 3` reads the `make check` check fine
- decision(verification): verification=ci (make check needs macOS; this host is Linux); the verifier is told to read the check with `gh pr checks 3 --repo github.com/windroc/agent-usage-monitor --watch` when ci-verdict.py returns NO_CI
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- mid-run input (user requirement, round 3, during S6 r1): "fix the off-by-a-run issue you noted. A retry is due when now >= usage_disabled_at + usage_retry_after_s - 60 (same slack idea as THROTTLE 240 vs the 300 s LaunchAgent), so the 5 min retry lands on the next LaunchAgent run, not 10 min later; the doubling then stays on schedule. Add a test with a run 1 s early. Fold it into this review round fix (one fix per round)." -> goes into the r1 fix commit with the round's blockers
- S6 r1 @e5f46ae: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (command=CI make check run 40202509649, exit code=0 (success), tests=unknown, failures=0) -> no blockers; the user's round-3 requirement (60 s slack) goes in as the round's fix (it also resolves correctness#1)
- decision(re-review): the fix changes the due rule after an all-PASS round, so r2 re-runs the whole pinned panel, not only the verifier
- S6 r2 @8adf638: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (command=CI make check run 40203018393, exit code=0 (success), tests=unknown, failures=0) -> converged
- residual NON-BLOCKING (deferred): correctness#2 (_wait not capped at RETRY_MAX), correctness#3 (pendingRetry double tap / comment), requirement-fidelity#1 (timer/Save call sites untested)
- S7: plan doc copied to docs/design/WDRC-100-paused-probe-retry-plan.md (paths replaced by placeholders, as WDRC-98's)

## Review items

### S6 r1 (@e5f46ae)
- correctness#1 NON-BLOCKING: claude.py:210 due check has no slack; waits are multiples of the 300 s LaunchAgent interval, so a run 1 s short slips each step one interval; allow a margin (due when now - since >= wait - 60). -> fixed by the user's round-3 requirement
- correctness#2 NON-BLOCKING: claude.py:150-153 `_wait` accepts any positive int and the not-due check never caps it at RETRY_MAX; usage_retry_after_s=10**9 (hand-edited/corrupt) means the timer never retries, only a click recovers. -> deferred
- correctness#3 NON-BLOCKING: main.swift:116-121 comment says a click during a run that did not retry makes the next run retry, but `pendingRetry = pendingRetry || retryPaused` also queues a retry during a retrying run; a double tap runs two click retries back to back, two failures double the wait twice in under a minute. -> deferred
- requirement-fidelity#1 NON-BLOCKING [req-drop]: macos/Tests/main.swift `retry_paused_timer` checks only collectArgs(retryPaused: retriesPaused(urls: [])); the real timer and Save paths call self.refresh() with the default retryPaused=false and no test exercises that. -> deferred
- verification#1 NON-BLOCKING: ci-verdict.py exit 3 NO_CI (HTTP 403); read the check via gh pr checks.
- verification#2 NON-BLOCKING: CI make check (run 40202509649, job 121196482937) pass in 2m50s at e5f46ae; test counts unknown (logs not read).
- verification#3 NON-BLOCKING: worktree clean at e5f46ae before and after; no local checks (Linux).

### S6 r2 (@8adf638)
- correctness#1 RESOLVED (due now >= since + wait - 60; traced and tests OK).
- correctness#2 NON-BLOCKING OPEN (deferred): claude.py:151-154 `_wait` accepts any positive int; usage_retry_after_s=10**9 never retries on the timer; clamp with min(wait, RETRY_MAX).
- correctness#3 NON-BLOCKING OPEN (deferred): Swift click path unchanged by the fix.
- requirement-fidelity#1 NON-BLOCKING OPEN (deferred): macos/Tests/main.swift `retry_paused_timer` covers only collectArgs(retriesPaused(urls: [])); timer and Save call sites use refresh()'s default retryPaused=false untested.
- verification#4 NON-BLOCKING: ci-verdict.py NO_CI (403); read via gh.
- verification#5 NON-BLOCKING: run 40203018393 at 8adf638 success, make check pass in 2m52s; test counts unknown.
- verification#6 NON-BLOCKING: worktree clean at 8adf638 before and after; no local checks (Linux).

## Notes

- Local env is Linux: `make test` (python3 -m unittest discover -s tests -t .) runs; swift-test, app and make check need macOS (CI job `make check`, macos-26).
- Repo keeps plan docs in docs/design/ (e.g. WDRC-98-paused-reason-plan.md).
- Snapshot row keys listed in tests/test_cli.py:14,105 and tests/test_store.py:47 and macos/Tests/main.swift:255.

## Task list

### Header

Global constraints:
- Data shape: the snapshot row gains `usage_disabled_at`: int epoch seconds when the current pause started or last restarted, else `null`; set wherever `usage_disabled_version` is set, cleared (`None`) wherever it is cleared (success, auth, 1st/2nd strike). `store.default_row()` has it; `store.SCHEMA` stays 1.
- `claude.RETRY_PAUSED_AFTER = 6 * 3600`. **Due**: `usage_disabled_at` is not an int (missing, null, bool, other type), or `now - usage_disabled_at` is not in `[0, RETRY_PAUSED_AFTER)`.
- **Paused** = today's skip condition (`claude.py:177-182`: disabled version set, `claude --version` equals it or reads nothing, not logged out). A paused row probes once (a **retry**) when `retry_paused` or due; else returns as today (`error=PAUSED`, `needs_login=False`, kept True).
- Retry results: parses → the usual success fields plus `usage_disabled_at=None`; `auth` → as today plus `usage_disabled_at=None`; `unrecognized` → capture as today, then pause again at once (no count): `usage_disabled_version=<version read now or "unknown">`, `usage_disabled_at=now`, `unrecognized_count=0`, `unrecognized_version=None`, `needs_login=False`, `error=PAUSED`; `timeout`/`usage_error`/`loading`/`cannot start claude` → `usage_disabled_at=now`, `needs_login=False`, `error=PAUSED`, version kept (not in fields). Log lines name the retry and its failure.
- Host: a widget click (non-empty URLs that do not open settings) runs `collect --emit-alerts --retry-paused`; launchd (no URL), the settings timer and a settings save run `collect --emit-alerts`. A click during a running non-retry collect makes the follow-up run retry.
- Decisions: retry failures show `error=PAUSED` (row stays paused, no flicker; log names the failure); a settings save does not retry (requirement names only tap and arrow as user refreshes); a future `usage_disabled_at` is due (matches the throttle's `0 <=` rule); `cannot prepare probe dir` stays before the pause check, unchanged.
- No mutation testing (see Input). Local checks: `/usr/bin/python3 -m unittest discover -s tests -t .` (or the touched test modules); Swift is checked on CI only (Linux here).

### Task 1: retry paused Claude probes in claude.refresh

- Files: `agent_usage_monitor/claude.py`, `agent_usage_monitor/store.py`, `tests/test_claude.py`, `tests/test_store.py`, `tests/test_cli.py` (row-key lists).
- Produces: `claude.refresh(..., retry_paused=False)` (keyword, last), `claude.RETRY_PAUSED_AFTER`, row field `usage_disabled_at`.
- Tests first (`RefreshTest`): click retry success; click retry unrecognized (paused again at once, clock = now); click retry other failures (timeout, non-zero exit, usage_error, loading, claude missing: keep pause, clock = now, error PAUSED); retry logged out (auth fields, usage_disabled_at None); timer: not retried at 6 h − 1 s, retried at exactly 6 h and 7 h; pause without `usage_disabled_at` (missing, null, string, bool) retried; future timestamp retried; 3rd strike sets `usage_disabled_at=now`, 1st/2nd set None; unpaused row unaffected by `retry_paused`. Update existing paused tests to give recent `usage_disabled_at` where they expect the pause kept.
- Checks: `/usr/bin/python3 -m unittest tests.test_claude tests.test_store tests.test_cli`.
- Commit: `WDRC-100: retry a paused Claude probe every 6 hours or when asked`

### Task 2: collect --retry-paused

- Files: `agent_usage_monitor/cli.py`, `tests/test_claude.py` (`CollectProbeTest`), `tests/test_cli.py`.
- Consumes: `claude.refresh(retry_paused=)`. Produces: `cli.collect(environ, emit_alerts=False, retry_paused=False)`, `collect --retry-paused` (help: probe paused Claude accounts once, as a widget click does).
- Tests first: LaunchAgent run (`collect(environ, True)`) on a row paused 1 h ago runs no /usage; `collect(environ, True, retry_paused=True)` probes and a parsing output clears `usage_disabled_version`/`usage_disabled_at` in the snapshot; `cli.main(["collect", "--retry-paused"])` passes True, without the flag False.
- Checks: `/usr/bin/python3 -m unittest tests.test_claude tests.test_cli`.
- Commit: `WDRC-100: collect --retry-paused probes paused Claude accounts`

### Task 3: widget click passes --retry-paused

- Files: `macos/Host/Settings.swift`, `macos/Host/main.swift`, `macos/Tests/main.swift`.
- Produces: `func retriesPaused(urls: [URL]) -> Bool` (non-empty and not opensSettings), `func collectArgs(retryPaused: Bool) -> String`; main.swift `refresh(retryPaused: Bool = false)`, `pendingRetry`, `run(retryPaused:)`.
- Tests first (Swift `check`s): refresh URL → retries, flag in args; no URL (launchd, settings timer, save) → no flag; settings URL → no retry.
- Checks: CI `make check` (swift-test, app build); locally none (Linux).
- Commit: `WDRC-100: a widget click asks collect to retry paused probes`

### Task 4: README

- Files: `README.md`, `tests/test_readme.py`.
- Content: Claude probe paragraph: replace "Delete `usage_disabled_version` from its snapshot row to retry sooner." with the retry rule (click, 6 h after `usage_disabled_at`, success recovers, unrecognized or other failure keeps the pause and restarts its 6 hours, no 3 more strikes, a pause from before this change retries on the next run). Widget click (line ~57), host run (~61) and URL (~96) text: a click runs `collect --emit-alerts --retry-paused`; launchd and settings-window runs do not. Keep phrases tests/test_readme.py asserts.
- Tests first: `test_paused_retry` asserts the new text and that "Delete `usage_disabled_version`" is gone.
- Checks: `/usr/bin/python3 -m unittest tests.test_readme tests.test_host_strings`.
- Commit: `WDRC-100: README: paused Claude probes retry on a click and every 6 hours`

### Task 5: exponential backoff for paused retries (round 2)

- Files: `agent_usage_monitor/claude.py`, `agent_usage_monitor/store.py`, `tests/test_claude.py`, `tests/test_store.py`, `tests/test_cli.py`.
- Produces: `claude.RETRY_FIRST = 300`, `claude.RETRY_MAX = 6 * 3600` (replace `RETRY_PAUSED_AFTER`); row field `usage_retry_after_s` (default None) beside `usage_disabled_at`; set/cleared as decision(backoff).
- Tests first: doubling over consecutive failed timer retries (300, 600, 1200, ...); 6 h cap (wait 4 h -> 6 h, 6 h -> 6 h); failed click retry doubles; not due before the wait, due at it; reset on success (both fields None); old pause without schedule fields retried next run, then wait 600; new pause (3rd strike) gets 300.
- Checks: `/usr/bin/python3 -m unittest tests.test_claude tests.test_store tests.test_cli`.
- Commit: `WDRC-100: back off paused Claude retries from 5 minutes to 6 hours`

### Task 6: README for the backoff

- Files: `README.md`, `tests/test_readme.py`.
- Content: the account-list retry sentence: first retry 5 min after the pause, each failed retry doubles the wait up to 6 h (`usage_disabled_at`, `usage_retry_after_s`), success clears it; click unchanged.
- Checks: `/usr/bin/python3 -m unittest tests.test_readme tests.test_host_strings`.
- Commit: `WDRC-100: README: paused Claude retries back off from 5 minutes to 6 hours`
