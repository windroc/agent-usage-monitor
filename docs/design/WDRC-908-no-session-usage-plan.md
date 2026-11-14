Rules: <updraft>/skills/light-build/SKILL.md <updraft>/references/updraft-common.md <updraft>/references/review-round.md
RESUME: phase=S7 worktree=<worktree> branch=WDRC-908-claude-usage-without-a-current-session-l base_ref=4c61860dd6ace3f6dcc4aa858992f6bb2f46ca96 review_round=2 input_sha=97c4496b1aa0

## Input

WDRC-908: Claude /usage without a Current session line is rejected; a click must always refresh

Repo: windroc/agent-usage-monitor

## Problem

Reported by the user (2026-11-13): after a usage reset on one Claude account, the widget still shows the old values (5H 100%, 7D 14%), even after several clicks on refresh.

## Evidence (main, 4c61860)

* After the reset, `claude -p /usage` prints no `Current session` line; the account's `<state>/probe/last-unrecognized-<name>.txt` capture holds:

  ```
  You are currently using your subscription to power your Claude Code usage

  Current week (all models): 0% used · resets Nov 14 at 11am (America/New_York)
  Current week (Fable): 1% used · resets Nov 14 at 11am (America/New_York)
  ```
* `agent_usage_monitor/claude_usage.py:444`: `parse` raises `UsageError("unrecognized", "Missing Current session.")` when that label is missing, so the whole output is rejected, the 7-day value too.
* After 3 such outputs the account's probe is paused (snapshot row: `usage_disabled_version: 2.1.325 (Claude Code)`, error `/usage unreadable · paused`); each click retries once, gets the same output, pauses again and doubles the wait. The row keeps its old values, and since they are under 6 hours old the widget shows the old bars, not the reason (WDRC-98).
* Caller's reading (verify it): a widget click already runs `collect --emit-alerts --retry-paused` (macos/Host/Settings.swift `collectArgs`), and `claude.refresh(retry_paused=True)` skips both the THROTTLE skip and the paused-probe wait. So once `parse` accepts this output, a click on a paused account succeeds and the success clears the pause. Check whether any other path still keeps a click from fetching and showing fresh values (e.g. the codex path, store.write keeping old window values when a window is None, the widget's staleness rules), and fix only what really blocks requirement 1.

## Requirements

1. The user's words (2026-11-13): "manual点击要always刷新" (a manual click must always refresh). A widget click fetches every account's current usage and the widget shows it, whatever the account's throttle, pause or backoff state.
2. `/usage` output without a `Current session` line (no active 5-hour session, e.g. right after a reset) is read, not rejected: the weekly value updates, and the 5H row shows no usage in that window (it must not keep showing an old 5H value such as 100%). Output with neither a `Current session` nor a `Current week (all models)` value is still `unrecognized`. Check that `usage_error`'s subscription-notice-only rule does not catch this fixture (it contains `Current week`).

## Additional requirements (round 1), the user's, newer, hard constraint

3. The user's words (2026-11-13): "如果没有5h的limit就不要显示了，如果只有7d的话" (when an account has no 5-hour limit, only the 7-day one, do not show the 5H row). So for an account whose latest successful read has no 5-hour window (e.g. the fixture above), the widget hides that account's 5H bar/row and shows only 7D; it must not show an old 5H value or a placeholder 5H bar. This refines requirement 2's "5H 0% or absent": absent, and hidden in the widget. Find how the snapshot stores a missing window (store.py, derive.py) and how the widget (macos/Widget, macos/Host) renders rows, and hide the 5H row when it is absent; codex accounts or others with both windows render as before.

## Constraints

* Keep the paused-probe backoff for the LaunchAgent and settings runs (WDRC-100, WDRC-101) and the click throttle skip (WDRC-480).
* No frozen-interface change (snapshot schema, CLI flags, widget contract); if one is needed, stop and report it instead of making it. A window that is already nullable in the snapshot staying null is not a schema change.

## Acceptance

* The fixture above parses: 7D 0%, resets Nov 14 11am America/New_York; 5H absent.
* A paused account recovers on the next click when its output is now readable.
* The widget shows no 5H row for an account with only a 7-day window.
* Tests pin all three (unit tests in tests/test_claude_usage.py, tests/test_claude.py, tests/test_store.py as relevant, and the macOS checks in macos/Tests for the widget; put the fixture in tests/fixtures following existing naming, with no account name or email in it).

## Conventions and git rules

* Follow the repo's conventions (its CLAUDE.md / AGENTS.md if any, README, Makefile, existing code and test style; docs/design holds plan docs named `<ID>-<slug>-plan.md`). Default branch: `main`.
* No mutation testing: never modify the source to see what happens, not even briefly or in a throwaway copy; never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call. Every brief to a sub-agent (producer, reviewer) carries this rule.
* Push only this branch; force-push only with `--force-with-lease`.
* Implement, verify and commit each small unit before the next (sequence-verifiable-units). At planning choose the data shape for the parse result, the missing-window representation and the pause/retry branching before splitting tasks (model-the-domain). Subtract before you add; fix the root cause (the parser's rejection), not a guard around it.

The plan doc stays where updraft puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

Work only in `<worktree>` on branch `WDRC-908-claude-usage-without-a-current-session-l`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <worktree> push -u origin WDRC-908-claude-usage-without-a-current-session-l`.

Verify command: make check (macOS CI job `make check`; locally on Linux only `/usr/bin/python3 -m unittest discover -s tests -t .` and `python3 tests/pii_scan.py` run)
CI checks: ["make check"]

## Progress log

- S1: mode=stay, publish=ci, branch WDRC-908-claude-usage-without-a-current-session-l, base_ref 4c61860
- decision(req1): a click already probes every account at once: host passes `--retry-paused` (macos/Host/Settings.swift collectArgs, WDRC-100 checks in macos/Tests/main.swift); claude.refresh(retry_paused=True) skips THROTTLE and the pause wait; codex (_codex in cli.py) has no throttle. The only blocker is parse rejecting weekly-only output, so a paused account re-pauses on every click. No host/probe change.
- decision(parse): accept output with no `Current session` label only when it has a `Current week (all models)` percent and no line that looks like a misread session label (normalized starts with `curr` and contains `session`, e.g. CodexBar sample `Curretsession`). Rejected: accept any weekly-only output, which would turn the two pinned `Curretsession` samples (a real 15%/6% 5H) into "no 5H". Conservative: unknown session label stays unrecognized as today.
- decision(req3): absent = the parse result's session_left None -> make_windows five_hour None -> snapshot five_hour null (already nullable: store._valid_window, derive.availability skips None) -> widget rows() drops a null window (large: no 5H row; medium: empty 5H column, no label). No widget code change; pin it with a Swift check. Config-dir A output (`Current session: 0% used`, no reset) keeps 5H 0%: that account has a 5h limit, it is just idle.
- S5 task 1 done: 0101f55 red=test_no_session_fixture,test_weekly_only_is_not_an_error,test_click_reads_output_without_session (test_launchagent_run_keeps_pause_with_values first failed on a test bug: --emit-alerts printed the 100% alert; flag dropped); checks: unittest test_claude_usage test_claude test_readme OK (95), pii_scan OK
- S5 task 2 done: 69c5293 red=none (pins existing rows() behavior; Swift not runnable here: no swiftc on Linux, CI `make check` runs it); checks: pii_scan OK
- decision(publish): pr.py push opened draft PR https://github.com/windroc/agent-usage-monitor/pull/6 (publish=ci; CI runs only on pull_request); the caller adopts it.
- decision(panel): drop performance-reviewer (matched *.py/*.swift only; the change adds one O(lines) scan on a short CLI output) and security-reviewer (matched the word `session`, which here is a usage window, not auth; no input, secret or authz surface changes).
- S6 panel: core=[correctness-reviewer, doc-reviewer, requirement-fidelity-reviewer, verification] +optional=[architecture-reviewer, code-quality-reviewer, test-reviewer] verification=ci
- S6 r1 @69c5293: correctness=FAIL doc=PASS requirement-fidelity=PASS architecture=PASS code-quality=PASS test=PASS verification=PASS (CI check make check success at 69c5293) -> correctness#1 a 5h full alert key is not ended early when five_hour turns null; re-reviewing under round-2 requirements
- mid-run input (user, 2026-11-13, Additional requirements (round 2), hard constraints): "eng不要过度防御" no guards, fallbacks or checks for cases the requirements and evidence do not show; "不要扩大范围" change only what the requirements need.
- decision(r1 fix): no code change for correctness#1. alerts.py is outside requirements 1-3 (round 2: do not widen scope), and the existing pinned test tests/test_alerts.py test_window_no_longer_reported_ends_at_stored_reset asserts exactly this behavior (a window no longer reported ends at its stored reset). Deferred to the PR for the user.
- decision(guard vs round 2): keep `_unread_session_label`: the case is shown by evidence in the repo (two pinned CodexBar samples with `Curretsession` and a real 5h percent, expected `unrecognized`); dropping it would change their pinned result to "no 5h" and hide a real 5h value, a behavior change the requirements do not ask for.
- S6 r2 @69c5293: correctness=PASS (correctness#1 INVALID per reviewer: existing pinned behavior, outside scope under round 2) requirement-fidelity=PASS verification=PASS (CI check make check success at 69c5293); others carry PASS -> converged
- residual NON-BLOCKING: doc#1, code-quality#1, code-quality#2

## Review items

r1 items:
- correctness#1 BLOCKING: agent_usage_monitor/alerts.py:55-61 `ended`: with five_hour null after a successful read, a 5h full key whose stored reset is ahead is not ended early; "available again" waits up to the old 5h reset.
- doc#1 NON-BLOCKING: docs/design/TASK-587-widget-claude-usage-spec.md:86 says no `Current session` percent -> unrecognized; historical spec, optional superseded note.
- code-quality#1 NON-BLOCKING: claude_usage.py parse docstring 4 lines; trim to contract + why.
- code-quality#2 NON-BLOCKING: `_unread_session_label` name/`n`; e.g. `_looks_like_session_label` with a docstring.

## Notes

- Local env is Linux: no swiftc/xcrun, so swift-test and `make check` run only in CI (macOS job `make check`).
- tests/test_claude CollectProbeTest.collect asserts empty stdout: a row >= threshold emits an AUM-ALERT under --emit-alerts.


## Task list

Global constraints: no snapshot schema, CLI flag or widget contract change. Parse result keeps its four keys; `session_left`/`session_reset` None = no 5-hour window in the output. No account name or email in fixtures (pii_scan). No mutation testing.
Data shape: parse dict {session_left, weekly_left, session_reset, weekly_reset}; five_hour window None end to end (make_windows -> store row -> widget Row.fiveHour nil -> no 5H Bar).
PR: none yet (publish=ci; caller opens/adopts it onto main).

### Task 1: Read /usage output without a Current session line

- Files: agent_usage_monitor/claude_usage.py (parse, its docstring), tests/fixtures/claude-usage/no-session.stdout.txt (new, the issue's three lines), tests/test_claude_usage.py, tests/test_claude.py, README.md (the TASK-583 / probe paragraph: weekly-only output reads as no 5h window).
- Consumes/produces: claude_usage.parse(text) -> dict as before, session fields None when no session label; raises UsageError("unrecognized") when neither session nor all-models weekly percent, or when a line looks like an unreadable session label.
- Tests first: FixtureTest no-session fixture parses to session_left None, weekly_left 100, session_reset None, weekly_reset "resets Nov 14 at 11am (America/New_York)"; make_windows -> five_hour None, seven_day {0, Nov 14 11:00 NY}. ErrorKindTest: weekly-only line no longer unrecognized (moved to a parse assertion); `Current week (Fable): 1% used` alone and `Curretsession\n15%used\nCurrent week (all models): 3% used` stay unrecognized. test_claude CollectProbeTest: a paused row holding old values (5H 100%, 7D 14%, fetched 1 h ago) + fixture output + `collect --emit-alerts --retry-paused` -> pause cleared, error None, five_hour null, seven_day 0%; and the same without --retry-paused leaves the pause (WDRC-100 kept).
- Checks: /usr/bin/python3 -m unittest tests.test_claude_usage tests.test_claude tests.test_readme; python3 tests/pii_scan.py.
- Commit: `fix(claude): read /usage output without a Current session line (WDRC-908)`

### Task 2: Pin the widget hiding 5H for a 7-day-only claude account

- Files: macos/Tests/main.swift.
- Tests: a claude row with five_hour null and seven_day 0% shows one bar, 7D, no 5H, in rows(); loadSnapshot of such a row decodes fiveHour nil.
- Checks: swift-test runs only on macOS (CI `make check`); none locally (Linux, no swiftc) - logged.
- Commit: `test(widget): pin no 5H bar for a 7-day-only claude account (WDRC-908)`
