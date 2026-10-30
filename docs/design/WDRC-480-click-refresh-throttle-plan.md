Rules: /opt/ensemble/plugins/updraft/skills/light-build/SKILL.md /opt/ensemble/plugins/updraft/references/updraft-common.md /opt/ensemble/plugins/updraft/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=WDRC-480-widget-refresh-click-does-not-show-the-l base_ref=9729a06106ab3aced3f3cd34c9927fd4afefb0a2 review_round=1 input_sha=f2ba89f2d5f7

## Input

## Requirement (WDRC-480: Widget refresh click does not show the latest usage right away)

Goal: a click on the widget's refresh arrow (or anywhere on the widget) fetches current usage for every account, and the widget shows it as soon as that collect finishes, without waiting for the 5-minute timeline refresh.

User report (2026-10-29): clicking the refresh arrow leaves the old numbers (three claude accounts, one codex).

Path: `macos/Widget/AgentUsageMonitorWidget.swift:65,81` open `agent-usage-monitor://refresh` → `macos/Host/main.swift` `refresh(retryPaused:)` → `agent-usage-monitor collect --emit-alerts --retry-paused` (`collectArgs`, `macos/Host/Settings.swift:27`) → `WidgetCenter.shared.reloadAllTimelines()` in `finished`.

Root cause (reproduced by the caller at 9729a06 with the tests' fake claude: `collect --emit-alerts`, then fake usage changed 40% → 91%, then `collect --emit-alerts --retry-paused` a moment later → no second claude call, row still 40%): `agent_usage_monitor/claude.py` `refresh` returns `({}, True, None)` when `0 <= now - fetched_at < THROTTLE` (240 s), before anything else, also on a click run. The LaunchAgent probes every 300 s, so a click usually lands within 240 s of the last probe and every Claude row keeps its old values. Codex has no throttle.

Required behavior:
- A click run (`collect --retry-paused`, which only a widget click passes) probes every Claude account regardless of the throttle. Runs without that flag (LaunchAgent, the settings window's timer and Save) keep the 240 s throttle unchanged.
- Keep WDRC-100 / WDRC-101 behavior: a click retries a paused probe; a double tap retries once (the host's queued run during a retrying run gets no `--retry-paused`, so it stays throttled; keep that).
- No frozen-interface change: keep the CLI flags (`--retry-paused`, `--emit-alerts`), host↔CLI contract and snapshot schema; if one is needed, stop and say so. Update the `--retry-paused` help text and the `refresh` docstring for the new meaning.
- A test pins it: a refresh/collect with `retry_paused` and `fetched_at` inside the throttle window probes and writes the new values; without it, still skipped (keep `test_throttle`'s existing cases).
- Update README (it says "An account probed less than 4 minutes ago is skipped" and describes the click's `--retry-paused`) and any other doc the change makes false.
- The PR must name the root cause; note in the plan doc's decisions that the host's `reloadAllTimelines` path was not changed and why (collect values were stale before the reload).

Constraints and conventions: follow the repo's existing style (comment density, naming, requirement-id comments like `WDRC-100`), Python 3.9 stdlib only, tests via `make test` (`python3 -m unittest discover -s tests -t .`) and `make pii-scan`; Swift tests (`make swift-test`) need macOS and cannot run here. Fix root causes (read `/opt/ensemble/team/principles/fix-root-causes.md`); subtract before you add (`/opt/ensemble/team/principles/subtract-before-you-add.md`); redesign from first principles (`/opt/ensemble/team/principles/redesign-from-first-principles.md`); every reviewer brief names those three files for the reviewer to read. No mutation testing: never modify the source to see what happens (no manual or tool-driven mutation testing, not even in a throwaway copy); a test's red step is its failure before its code exists; every brief to a sub-agent carries this rule. Commits in the repo's conventions; never rebase or force-push except `--force-with-lease`; the default branch is `main`.

The plan doc stays where updraft puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

Work only in `<WORKTREE>` on branch `WDRC-480-widget-refresh-click-does-not-show-the-l`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <WORKTREE> push -u origin WDRC-480-widget-refresh-click-does-not-show-the-l`.

## Verify

python3 -m unittest discover -s tests -t . && python3 tests/pii_scan.py
CI checks: []
(`make check` also runs swift-test and app, which need macOS; CI's macos-26 job could not start, see decision(publish). The change touches no Swift.)

## Progress log

- decision(root cause): claude.refresh's THROTTLE check ran before the click flag, so a click within 240 s of the last probe (most clicks, with the 300 s LaunchAgent) skipped every Claude account; reproduced with the fake claude (collect, usage 40%->91%, collect --retry-paused -> 1 call, 40%).
- decision(scope): host `reloadAllTimelines` path unchanged: the snapshot it reloads already held the stale Claude values (no probe ran), so the reload showed them faithfully; Codex rows, unthrottled, already updated on a click.
- decision(name): keep `retry_paused` / `--retry-paused` (host<->CLI contract, no interface change); docstring and help now say it also skips the throttle.
- decision(double tap): WDRC-101 unchanged: the host's queued run behind a retrying run gets no --retry-paused, so a double tap probes Claude once.
- PR https://github.com/windroc/agent-usage-monitor/pull/5 opened by pr.py push.
- S5 task 1 done: 9c0e248 red=test_click_skips_throttle,test_click_collect_skips_throttle
- decision(publish): CI `make check` at 9c0e248 not started: GitHub annotation "The job was not started because recent account payments have failed or your spending limit needs to be increased" (run 40985901134); not a code failure, no fix can address it; verification=local with the Python suite and pii-scan (Linux host, no macOS for swift-test/app).
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=local transport=Workflow
- S6 r1 @9c0e24889d7705f6da73925a426b539017aba65d: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (command=python3 -m unittest discover -s tests -t . && python3 tests/pii_scan.py, exit code=0, tests=267, failures=0) -> converged
- residual NON-BLOCKING: requirement-fidelity#1 (PR body must name the root cause; the caller's final PR description does).

## Review items

- r1 requirement-fidelity#1 (NON-BLOCKING): [req-drop] PR #5 body says only what the fix does; it does not name the root cause (claude.refresh's THROTTLE check returned ({}, True, None) before the click flag was considered). Put decision(root cause) into the PR body.
- r1 verification#1-#4 (NON-BLOCKING, evidence): frozen worktree at reviewed_sha, clean before and after; unittest exit 0, 267 tests OK; pii_scan exit 0; not run: make check swift-test/app (no macOS) and CI (billing).

## Notes

- Throttle: agent_usage_monitor/claude.py refresh, first check `0 <= now - fetched_at < THROTTLE` (240) -> ({}, True, None); store.write marks a kept row `source: cache`.
- retry_paused reaches claude.refresh via cli.collect functools.partial; only the host's widget-click URL passes --retry-paused (macos/Host/Settings.swift retriesPaused/collectArgs).
- tests/test_claude.py test_unpaused_retry_flag_no_effect pins the old click throttle (line ~595); test_throttle covers no-flag cases; CollectProbeTest for collect-level.
- tests/test_readme.py asserts README sentences about --retry-paused.
- Local checks: `python3 -m unittest discover -s tests -t .` and `python3 tests/pii_scan.py`; swift-test/app need macOS (CI `make check` on macos-26).

## Task list

Global Constraints: `claude.THROTTLE = 240` unchanged for runs without `--retry-paused`; CLI flags, host code and snapshot schema unchanged; Python 3.9 stdlib only; tests use only the fake `claude`.
Data shape: no new state. The existing `retry_paused: bool` (CLI `--retry-paused`, only a widget click) now means "a user's click: probe now"; it skips the throttle and retries a paused probe.

### Task 1: A widget click probes Claude within the throttle

- Files: `agent_usage_monitor/claude.py` (refresh: throttle check skipped when `retry_paused`; docstring), `agent_usage_monitor/cli.py` (`--retry-paused` help), `tests/test_claude.py`, `README.md`, `tests/test_readme.py` if its asserted sentences change.
- Consumes / Produces: `claude.refresh(..., retry_paused=False)` signature unchanged.
- Tests first: refresh with `retry_paused=True` and `fetched_at` NOW-60 / NOW-239 probes and returns the new values (replaces the throttle half of `test_unpaused_retry_flag_no_effect`); `test_throttle` cases unchanged (no flag: NOW-60, NOW-239 skipped); collect-level: `collect` then changed fake usage then `collect --retry-paused` right after -> second claude call, row `source: usage` with the new percent; a plain second `collect` still skipped (existing `test_every_collect_probes`).
- Checks: `python3 -m unittest discover -s tests -t .`, `python3 tests/pii_scan.py`.
- Commit: `WDRC-480: Widget click probes Claude accounts within the throttle`
