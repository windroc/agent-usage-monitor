Rules: <updraft>/skills/light-build/SKILL.md <updraft>/references/updraft-common.md <updraft>/references/review-round.md
RESUME: phase=done worktree=<worktree> branch=WDRC-909-available-again-alert-waits-for-the-old base_ref=bbe7564798adced62deb4d9ae859fee1b9105569 review_round=1 input_sha=34dd71923511

## Input

## Requirement (WDRC-909): Available-again alert waits for the old 5h reset when /usage reports no 5h window

Repo: windroc/agent-usage-monitor

### Problem
Deferred from WDRC-908 (PR #6, merged as bbe7564), correctness#1 in its review; the user chose to fix it in its own issue (2026-11-13).

After a Claude usage reset, `/usage` prints no `Current session` line, so since WDRC-908 the row's `five_hour` is `null` on a successful read. A notified 5h `full` alert key whose stored `resets_at` is still ahead is then not ended early: the "available again" alert waits until the old 5h reset time, up to 5 hours, while the widget already shows the account as available.

### Evidence (main, bbe7564)
* `agent_usage_monitor/alerts.py:53-59` (`ended`): when `row.get(k["window"])` is `None`, it falls through to `k["resets_at"] <= now`.
* Case from the PR #6 review: notified `{name: "claude", window: "five_hour", resets_at: now+3600}`, then the no-session fixture is read (`five_hour` null, `seven_day` 0%). `derive.recompute` sets `available=True`, but `alerts.evaluate` returns `[]` and keeps the key. The same row with `five_hour {0%, now+5h}` gets "claude · claude available again" at once.
* `tests/test_alerts.py::test_window_no_longer_reported_ends_at_stored_reset` pins the current behavior.

### Requirement
When a successful read reports no window that an alert key names (e.g. no 5h window right after a reset), "available again" is sent on that run, as for an early reset (WDRC-91).

### Constraints
* The user (2026-11-13): no over-defensive code; do not widen the scope.
* No frozen-interface change; stop and ask if one is needed.

### Acceptance
* The case above sends "available again" on the run that reads the no-session output.
* A row that keeps its values without a successful read (pause, failure) does not end the key early.
* Tests pin both.

### Caller's investigation notes (context; verify in the source)
* `store.write` keeps a failed/skipped row's previous windows; a never-fetched failed row gets blank window dicts (`{"used_percent": None, "resets_at": None}`), never `None`. Claude's failure, pause and throttle paths (`claude.py`) return no window fields. So a `None` window in a row appears to come only from a successful read that did not report it; if that holds, the smallest fix may be that `ended` treats a `None` window as ended, with no new parameter. Confirm or refute before choosing; prefer no signature change to `alerts.evaluate`/`store.write` unless needed.

## Conventions and git rules
* Write code, docs and commits in the repo's conventions (its `CLAUDE.md` / `AGENTS.md` / README if present). Default branch: `main`.
* **No mutation testing**: while building, reviewing or testing, never modify the source to see what happens: no manual or tool-driven mutation testing (mutmut etc.), not even briefly or in a throwaway copy that is then run; never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call, leaving the code under test unmodified. Every brief to a sub-agent (producer, reviewer) carries this rule.
* Fix root causes; subtract before you add; redesign from first principles (updraft principles).
* At planning, use the `model-the-domain` principle for the data shape; implement, verify and commit each small unit before the next (`sequence-verifiable-units`).
* Push only branch `WDRC-909-available-again-alert-waits-for-the-old`; force-push only with `--force-with-lease`.

## Docs
The plan doc stays where updraft puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

Work only in `<worktree>` on branch `WDRC-909-available-again-alert-waits-for-the-old`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <worktree> push -u origin WDRC-909-available-again-alert-waits-for-the-old`.

## Verify

make check
CI checks: ["make check"]

## Progress log

- S1: mode=stay, publish=ci, base_ref=bbe7564.
- decision(design): a `None` window in a row means a successful read did not report it. Verified: store.write gives a failed never-fetched row blank window dicts, never None (store.py default_row, write); claude.py failure/pause/throttle paths return no window fields, so kept rows keep their previous windows; only claude_usage.make_windows and codex windows produce None. So `ended` treats a None window as ended, no new parameter; evaluate/store.write signatures unchanged. Reverses WDRC-91's "ends at stored resets_at" rule for absent windows (docs/design/WDRC-91-early-reset-alert-plan.md:28), which this requirement replaces.
- S5 task 1 done: 9505f20 red=test_window_no_longer_reported_ends_at_once (test_failed_read_keeps_key_until_stored_reset and the not-available test pin existing behavior); checks: tests.test_alerts OK, tests.test_readme OK, pii_scan OK
- Note: AlertsTest.write gained `failed=()`; a failed row needs fetched_at set, else store.write blanks its windows.
- S6 panel: core=[correctness, doc, requirement-fidelity, verification] +optional=[code-quality, test] verification=ci
- decision(panel): performance-reviewer dropped: the change edits one boolean condition with no loop, I/O or allocation change.
- PR: https://github.com/windroc/agent-usage-monitor/pull/7 (draft, by pr.py)
- S6 r1 @9505f20: correctness=PASS doc=PASS requirement-fidelity=PASS code-quality=PASS test=PASS verification=PASS (CI make check success at 9505f20) -> converged
- Residual NON-BLOCKING: test#1, test#2, test#3 (see Review items).

## Review items

- verification#1 (NON-BLOCKING): CI at 9505f20 passed: make check (success).
- test#1 (NON-BLOCKING): tests/test_alerts.py: the "pause" half of the acceptance is not tested by name. Only `failed={"claude-max"}` is used, so a regression in how the `--retry-paused` skip is built into `failed` would go unnoticed. The `store.write` docstring says `failed` covers both cases, so the code path is shared.
- test#2 (NON-BLOCKING): agent_usage_monitor/store.py:117 blanks the windows when a failed row has `fetched_at None`, which makes `ended()` return True through the new `w is None` branch. No test covers a failed read for a row that has a notified key but was never fetched. The failed-read test sets `fetched_at` explicitly, so it never reaches this branch.
- test#3 (NON-BLOCKING): tests/test_alerts.py: `test_window_no_longer_reported_ends_at_once` and the failed-read test only exercise the `claude-max` account. The not-available case uses `cx`. Neither test checks `five_hour` becoming `None` while `seven_day` stays at or above the threshold on the same account as an "available again" case.

## Notes

- Unit tests: `/usr/bin/python3 -m unittest discover -s tests -t .` (Makefile `test`); single module: `python3 -m unittest tests.test_alerts`. PII scan: `python3 tests/pii_scan.py`. No swiftc on Linux; CI `make check` on macos-26.
- tests/test_alerts.py `AlertsTest.write` helper wraps store.write (no `failed` arg yet); `seed`/`full`/`notified` helpers exist.
- README.md:64 documents when "available again" fires; must gain the no-longer-reported case.
- Design plans live in docs/design/<ID>-<slug>-plan.md.

## Task list

Global Constraints: threshold 90 in tests; `derive.WINDOWS` keys `five_hour`, `seven_day`; no change to `alerts.evaluate`, `store.write`, snapshot schema, CLI or widget contract. No mutation testing.
Data shape: unchanged. A row window is `None` (the last successful read did not report it) or `{"used_percent", "resets_at"}`; an alert key `{name, window, kind: "full", resets_at, sent_at}` ends when its window is `None`, reports a different reset, is below threshold, or its stored reset has passed.
PR: none yet (publish=ci; caller opens/adopts it onto main).

### Task 1: End an alert key when a read no longer reports its window
- Files: agent_usage_monitor/alerts.py (`evaluate.ended`), tests/test_alerts.py, README.md:64.
- Consumes / Produces: none across tasks.
- Behavior: `ended(k)` is true when the row's `k["window"]` is `None`; else as before (different reset, below threshold, or stored reset passed).
- Tests first: replace `test_window_no_longer_reported_ends_at_stored_reset` with: key for claude-max five_hour at NOW+H notified; next write reports five_hour None, seven_day 0% -> ["claude · you@example.com available again"] on that run, notified empty. New: same key, then a write where the account fails (store.write `failed`, no updates; values kept, five_hour still {95, NOW+H}) -> [] and key kept; then the stored reset passes -> available again. Keep: window None while the other window is full -> no alert, key kept.
- Checks: `python3 -m unittest tests.test_alerts`, `python3 tests/pii_scan.py`.
- Commit: `fix(alerts): end an alert when a read no longer reports its window (WDRC-909)`
