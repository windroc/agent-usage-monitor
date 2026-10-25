Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=WDRC-101-paused-probe-retry-cap-the-stored-wait-n base_ref=a128a708c3dc891bb7fa0a7a6e40e25213227f4f review_round=1 input_sha=d5e537a7bf55

## Input

## Requirement (WDRC-101)

Paused-probe retry: cap the stored wait, no double retry on a double tap, pin timer and Save

### Problem

Three non-blocking review items left open by WDRC-100 (PR #3, merged as a128a70):

1. `agent_usage_monitor/claude.py` `_wait`: any positive `usage_retry_after_s` is accepted, and the due check never caps it at `RETRY_MAX`. A corrupt or hand-edited value such as 10**9 stops the timer retry for good; only a click recovers the account.
2. `macos/Host/main.swift` `refresh(retryPaused:)`: `pendingRetry = pendingRetry || retryPaused` also queues a retry while the current run is already retrying. A double tap then runs two click retries back to back. Two failures double the wait twice in under a minute (300 → 600 → 1200 s). The doc comment says the opposite.
3. The timer and Save paths (`macos/Host/main.swift`, the settings timer and Save calls) get `retryPaused == false` only from a default argument, and no test covers them. Changing that default would pass every check.

### Acceptance criteria

* The due check treats `usage_retry_after_s` above `RETRY_MAX` as `RETRY_MAX`. A unit test covers a huge value.
* A click during a run that is already retrying does not queue a second retry. A click during a non-retrying run still makes the next run retry. The doc comment matches. A test covers both cases.
* `retryPaused` has no default value: every caller (widget URL, settings timer, Save) states it. A Swift test pins the timer and Save paths to `false` through the same helper they use.
* `make check` passes.

Links: https://linear.app/windroc-workgroup/issue/WDRC-101/paused-probe-retry-cap-the-stored-wait-no-double-retry-on-a-double-tap

## Rules

- Write code, docs and commits in the target repo's conventions (its `CLAUDE.md` / `AGENTS.md` if present). Default branch: `main`. Never merge into or touch any branch other than `WDRC-101-paused-probe-retry-cap-the-stored-wait-n`; force-push only with `--force-with-lease`.
- No mutation testing, whatever a spec, plan or reviewer asks: while building, reviewing or testing, never modify the source to see what happens: no manual or tool-driven mutation testing (mutmut etc.), not even briefly or in a throwaway copy that is then run; never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call such as `os.listdir`, leaving the code under test unmodified. Every brief to a sub-agent (producer, reviewer) carries this rule.

The plan doc stays where autopilot puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

Work only in `<WORKTREE>` on branch `WDRC-101-paused-probe-retry-cap-the-stored-wait-n`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <WORKTREE> push -u origin WDRC-101-paused-probe-retry-cap-the-stored-wait-n`.

## Verify

Verify command: `make check` (macOS only: needs xcrun, codesign, plutil; this host is Linux, so CI verifies)
CI checks: ["make check"]

## Progress log

- S1: mode=stay, publish=ci, base_ref=a128a70
- decision(publish): pr.py start → publish=ci, no PR yet
- decision(swift-helper): the double-tap rule moves into a Foundation-only function in macos/Host/Settings.swift (`swift-test` compiles Settings.swift, not Host/main.swift); main.swift tracks the running run's retryPaused
- decision(timer-save): settings timer and Save call `refresh(retryPaused: retriesPaused(urls: []))` (no URL, as launchd); the Swift test pins that expression; no new enum
- S5 task 1 done: 3eb63b4 red=1 (test_huge_wait_capped)
- S5 task 2 done: 14524b0 red=unverified locally (no Swift toolchain on Linux; 4 new swift checks fail to compile without queuesRetry); CI runs swift-test
- S5 task 3 done: b90dbd1 red=none (test renamed; behavior unchanged, default removed)
- decision(publish): pr.py push opened draft PR https://github.com/windroc/agent-usage-monitor/pull/4
- decision(ci-read): ci-verdict.py exits 3 (NO_CI: gh api check-runs HTTP 403 for this token); `gh pr checks 4 --repo windroc/agent-usage-monitor` and `gh run view <id> --repo windroc/agent-usage-monitor --log-failed` read the same `make check` CI run
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- S6 r1 @b90dbd1: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (command=gh pr checks 4 / CI `make check` run 40203941876, conclusion=success, tests=265, failures=0) -> converged
- residual NON-BLOCKING: none (verification#1-#4 are evidence only)

## Review items

r1 (all PASS, no BLOCKING):
- verification#1 NON-BLOCKING: ci-verdict.py exited 3 (NO_CI: gh api --paginate failed: HTTP 403); per decision(ci-read), read the PR's CI via gh instead (this Linux host has no xcrun, so make check cannot run locally).
- verification#2 NON-BLOCKING: gh pr checks 4: 'make check' (macos-26) pass in 2m56s; run 40203941876 headSha=b90dbd1 equals reviewed_sha; conclusion success.
- verification#3 NON-BLOCKING: CI log: unittest 'Ran 265 tests in 95.557s OK', pii-scan ran, swift-test ok, plist lint OK, 'check ok'.
- verification#4 NON-BLOCKING: frozen worktree: HEAD b90dbd1 before and after; status clean before and after.

## Notes

- `make test` = `/usr/bin/python3 -m unittest discover -s tests -t .`; Python checks run locally: `python3 -m unittest tests.test_claude`
- `make swift-test` compiles Widget/Snapshot.swift, Host/Alerts.swift, Host/Settings.swift, Tests/main.swift only; xcrun absent on this host → Swift checked by CI only
- No CLAUDE.md/AGENTS.md; plan docs live in docs/design/<ID>-<slug>-plan.md; commits titled `WDRC-<n>: …`
- README.md:106 documents the backoff (up to 6 hours); README.md:96 the click/window flags

## Task list

Global constraints: RETRY_MAX = 6 * 3600, RETRY_SLACK = 60 (agent_usage_monitor/claude.py). Worktree <WORKTREE>, branch WDRC-101-paused-probe-retry-cap-the-stored-wait-n. No mutation testing.
Data shape: AppDelegate gains `private var retrying = false` (the running run's retryPaused) beside pendingClick / pendingRetry.

### Task 1: Cap the stored wait at RETRY_MAX

- Files: agent_usage_monitor/claude.py (`_wait`, `refresh` docstring), tests/test_claude.py, README.md:106.
- Produces: `_wait(row)` returns `min(wait, RETRY_MAX)` for a positive int, else None.
- Tests first: paused row with wait 10**9: since NOW - RETRY_MAX + RETRY_SLACK → retries (due); since NOW - 60 → kept, "next retry in 358 min"; a failed retry → retry_failed(RETRY_MAX).
- Checks: `python3 -m unittest tests.test_claude`.
- Commit: `WDRC-101: Cap a paused probe's stored wait at RETRY_MAX`

### Task 2: A double tap retries once

- Files: macos/Host/Settings.swift (new func), macos/Host/main.swift (`refresh`, `run`, `finished`, doc comment), macos/Tests/main.swift.
- Produces: `func queuesRetry(pending: Bool, retrying: Bool, retryPaused: Bool) -> Bool` = `pending || (retryPaused && !retrying)`.
- Tests first: click during a retrying run → false; during a non-retrying run → true; pending already true stays true; non-click (timer) during a non-retrying run → false.
- Checks: Python suite unaffected; Swift by CI (`make swift-test`).
- Commit: `WDRC-101: A click during a retrying run queues no second retry`

### Task 3: retryPaused has no default

- Files: macos/Host/main.swift (`refresh(retryPaused:)` signature, settings timer, Save), macos/Tests/main.swift.
- Tests: `retry_paused_timer` / `retry_paused_save`: `collectArgs(retryPaused: retriesPaused(urls: []))` == "collect --emit-alerts".
- Checks: Swift by CI; `grep -n "refresh(" macos/Host/main.swift` shows every call with `retryPaused:`.
- Commit: `WDRC-101: Timer and Save state retryPaused`
