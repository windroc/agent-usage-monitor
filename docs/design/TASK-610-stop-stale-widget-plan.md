Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-610-widget-widgetkit base_ref=2c59e37a9ab96fda53a614f3725117fe7078cd0d review_round=2 input_sha=d4a111a7adc9

## Input

## Requirement (TASK-610, revised by the user 2026-10-17): `make install` stops the old widget extension process

Repo: windroc/agent-usage-monitor. Parent TASK-561. This replaces the earlier TASK-610 reload-budget scope, which is dropped (moved to a separate issue): do none of it.

### Cause (the user's chronod log evidence)
`Bundle version did not match` reload errors began at 10:30:09 when `make install` replaced the installed bundle and continued until the user killed the running widget extension process (started 10:33:49 from the replaced bundle) at 11:23; the same happened at 09:18. `make install` already runs `lsregister -f` (Makefile:47); that alone was not the fix. The cause: `make install` replaces the bundle but leaves the old extension process running.

### What to build
1. In the Makefile `install` target, after the `lsregister -f` and `pluginkit -a` lines, stop our own running widget extension. Only our process, matched by the installed appex path, e.g. `pkill -f "$(DEST)/Contents/PlugIns/QuotaboardWidget.appex/Contents/MacOS/QuotaboardWidget" || true`. chronod relaunches it from the new bundle on the next reload. No system processes.
2. Add one README line explaining why.
3. `make check` and CI must pass. Do not install into `~/Applications` (do not run `make install`) yourself.

Facts already checked (context): the running extension's argv starts with its full path, `/Users/<u>/Applications/Quotaboard.app/Contents/PlugIns/QuotaboardWidget.appex/Contents/MacOS/QuotaboardWidget -LaunchArguments …`; macOS `man pkill`: "By default, the current pgrep or pkill process and all of its ancestors are excluded", so the recipe's own shell, whose command line holds the pattern, is not matched.

Links (context only): TASK-610

### Rules
- Follow the target repo's conventions (its `CLAUDE.md` / `AGENTS.md`, else the existing Makefile/README style) for code, docs and commits.
- Default branch is `main`. Never push to, merge into or otherwise touch any branch except `TASK-610-widget-widgetkit`; force-push only with `--force-with-lease`.
- No mutation testing, whatever a spec, plan or reviewer asks: never modify the source to see what happens (no manual or tool-driven mutation testing, not even briefly or in a throwaway copy); never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call, leaving the code under test unmodified. Every brief to a sub-agent (producer, reviewer) carries this rule.
- Do not kill any process (reviewers and verifiers included); do not run `make install` or `make uninstall`; do not write to `~/Applications`.

The plan doc stays where autopilot puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

Work only in `<WORKTREE>` on branch `TASK-610-widget-widgetkit`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <WORKTREE> push -u origin TASK-610-widget-widgetkit`.

## Verify

Verify command: `make -C <WORKTREE> check`
CI checks: ["make check"]

## Progress log

- S1: mode=stay (earlier plan doc widget-refresh-budget-plan.md is the dropped scope, phase=stopped, left untouched)
- decision(pattern): pkill -f with the installed appex executable path, as the requirement's example; macOS pkill excludes itself and its ancestors, so the recipe shell is safe; `|| true` since exit 1 = no match.

## Review items

## Notes

- Makefile install target: ditto → lsregister -f → pluginkit -a (lines 45-48); DEST uses $${HOME:?}.
- `make install` is not run by `make check` / CI; the new line is not exercised there.
- README line 51: the make install paragraph.

## Task list

Global Constraints: Only our extension, matched by `$(DEST)/Contents/PlugIns/QuotaboardWidget.appex/Contents/MacOS/QuotaboardWidget`; never run `make install`; no process kills while building or checking.

### Task 1: make install stops the old widget extension
- Files: Makefile, README.md.
- Tests first: none (a Makefile recipe line; `make check` does not run install). Check `make -n install` prints the pkill line after pluginkit -a (dry run, executes nothing but `make app` prerequisite listing).
- Checks: `make -n install`, `make check`.
- Commit: `TASK-610: make install stops the old widget extension`
- S5 task 1 done: 574ab13 red=none (Makefile line; checked by make -n install and pgrep -lf of the pattern: only the extension pid)
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- S6 r1 @574ab13: correctness=PASS requirement-fidelity=PASS doc=PASS verification=FAIL (CI make check, run 39045163346) -> verification#1 test_every_collect_probes 0 != 40: USAGE fixture "resets 3pm (UTC)" reads as already reset 15:00-20:00 UTC (claude_usage._resolve + derive.reset_window); weekly "Oct 24" same from 2026-10-24; fixing in tests only
- r1 items: verification#1 BLOCKING CI "make check" failure at 574ab13 (job 117432325498). doc#1 NON-BLOCKING README:51 "remove and re-add the widget if it stops updating" may be outdated now; trim once confirmed.
- S6 r2 @b077bb4: correctness=PASS verification=PASS (CI make check success at b077bb4; correctness parsed the fixture every 17 min 2026-2029, resets always ahead) -> converged
- residual NON-BLOCKING: doc#1 README:51 "remove and re-add the widget if it stops updating" may be outdated now that install stops the old extension; trim once confirmed.
