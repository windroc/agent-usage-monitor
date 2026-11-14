Rules: <updraft>/skills/light-build/SKILL.md <updraft>/references/updraft-common.md <updraft>/references/review-round.md
RESUME: phase=done worktree=<worktree> branch=WDRC-924-make-install-leaves-the-launchagent-fail base_ref=cbbbeca68e568f4385118a19b9771fe584bb6848 review_round=1 input_sha=1b4f8412fbdf

## Input

(verbatim copy: <workdir>/tmp/input.md; reproduced below)

## Requirement (WDRC-924): make install leaves the LaunchAgent failing to spawn the rebuilt app (EX_CONFIG)

Repo: windroc/agent-usage-monitor

### Problem
Reported by the user (2026-11-14): the widget stopped refreshing on its own; only a click updated it (a Gmail account's 7D jumped from 17% to 22% on one click).

### Evidence (main, cbbbeca)
* `launchctl print gui/$(id -u)/com.windroc.agent-usage-monitor` after the 2026-11-13 `make install` (WDRC-909): `job state = spawn failed`, `last exit code = 78: EX_CONFIG`, properties include `needs LWCR update`. The app's binary was rebuilt at 22:48 with a new ad-hoc signature.
* `Makefile:52` `install` copies the plist into `~/Library/LaunchAgents` but runs no `launchctl`; only `uninstall` (`Makefile:68-69`) runs `launchctl bootout`. README.md:49 has the user run `launchctl bootstrap` by hand once.
* `launchctl bootout` then `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.windroc.agent-usage-monitor.plist` fixed it: `runs = 2`, `last exit code = 0`, the snapshot updated at the next 5-minute interval (06:42).

### Requirement
After `make install`, the LaunchAgent runs the newly installed app every 5 minutes without a manual step.

### Constraints
* The user (2026-11-13): no over-defensive code; do not widen the scope.
* No frozen-interface change; stop and ask if one is needed.

### Acceptance
* On a Mac with the LaunchAgent loaded, `make install` leaves it loaded and its next run exits 0.
* README's install and upgrade steps match.

### Expected smallest change (engineer's note, not a requirement)
In the Makefile `install` target, after copying the plist: unload the job if it is loaded (`launchctl bootout gui/$(id -u)/com.windroc.agent-usage-monitor`; a first install has none loaded, which must not fail the target or print a misleading error), then `launchctl bootstrap gui/$(id -u) "$(PLIST)"`. No retries or sleeps. README: fold the manual `launchctl bootstrap` row into the `make install` row (rollback stays `make uninstall`, which already boots it out), and say in the install notes that `make install` reloads the LaunchAgent so launchd picks up the newly signed app (why: a rebuilt ad-hoc signature leaves a loaded job at `spawn failed`, EX_CONFIG). This repo runs on Linux here: no `launchctl`, `swiftc` or `make install`; verify the Makefile with `make -n install` (dry run) and `make test` / `python3 tests/pii_scan.py`. CI (`make check` on macOS 26) never runs `install`. Real-Mac verification of the acceptance is for the user/verifier; never claim it passed.

### Conventions and git rules
- No CLAUDE.md/AGENTS.md: follow README.md, docs/ and surrounding code. Makefile is GNU make 3.81: chain dependent commands with `&&`; keep the existing comment density. Commit subjects `WDRC-924: …`, trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. `tests/pii_scan.py` must pass; commit with the configured noreply identity.
- Default branch `main`. Never rebase; never force-push except `--force-with-lease` on this branch.
- No mutation testing: never modify source to see what happens, not even briefly or in a throwaway copy; never put a known-wrong value into shipped code. A test's red step is its failure before its code exists. Every brief to a sub-agent (producer, reviewer) carries this rule.
- Fix root causes; subtract before you add; redesign from first principles.

The plan doc stays where updraft puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

Work only in `<worktree>` on branch `WDRC-924-make-install-leaves-the-launchagent-fail`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <worktree> push -u origin WDRC-924-make-install-leaves-the-launchagent-fail`.

## Verify

`make check` (macOS 26; CI runs it on every PR)
CI checks: ["make check"]

## Progress log

- S1: mode=stay, publish=ci, base_ref=cbbbeca
- decision(bootout-guard): bootout only when `launchctl print` finds the job, so a first install neither fails nor prints a launchctl error; no retries or sleeps (user: no over-defensive code)
- decision(test): no automated test; the change is two launchctl lines in a Makefile target CI never runs (install touches the real user domain); checked with `make -n install` dry run

- S5 task 1 done: ded19f9 red=none (no automated test; stub launchctl run: loaded -> print,bootout,bootstrap; not loaded -> print,bootstrap; both exit 0)
- S6 panel: core=[correctness, doc, requirement-fidelity, verification] +optional=[] verification=ci (draft PR https://github.com/windroc/agent-usage-monitor/pull/8)
- S6 r1 @ded19f900a2641daec81d2678fe3efd205b6e904: correctness=PASS doc=PASS requirement-fidelity=PASS verification=PASS (CI check make check: success) -> converged
- residual NON-BLOCKING: none
- S7: plan doc copied to docs/design/WDRC-924-launchagent-reload-plan.md (paths as <updraft>/<worktree>/<workdir>, per earlier plan docs)

## Review items

- r1: no items (verification note: CI at ded19f9 passed: make check)

## Notes

- Linux here: no launchctl/swiftc; `make -n install` prints the recipe. Local checks: `make test`, `/usr/bin/python3 tests/pii_scan.py` (python3 if absent).
- Commit identity from env GIT_AUTHOR_* (bot noreply).

## Task list

Global Constraints: GNU make 3.81 (chain dependent commands with `&&`; `$$` for shell vars); label `com.windroc.agent-usage-monitor`; domain `gui/$$(id -u)`; plist `$(PLIST)`; no frozen-interface change; no retries/sleeps.

### Task 1: make install reloads the LaunchAgent
- Files: Makefile (`install`), README.md (Install table and notes; upgrade paragraph).
- Consumes / Produces: none across tasks.
- Tests first: none automated (see decision(test)); `make -n install` shows bootout guarded by `launchctl print`, then `launchctl bootstrap gui/$(id -u) <PLIST>` after the plist copy.
- Checks: `make -n install`, `make test`, `python3 tests/pii_scan.py`.
- Commit: `WDRC-924: make install reloads the LaunchAgent so it runs the rebuilt app`
