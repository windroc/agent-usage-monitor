Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-640-m2 base_ref=d66cd9bd1bcfab9237b1cce5aa886413022f7bdd review_round=1 input_sha=5493ddde4867

## Input

## Requirement (TASK-640 follow-up: README alert-line format)

Repo: windroc/agent-usage-monitor, PR #6 (branch `TASK-640-m2`).

### The user's requirements (2026-10-17, highest precedence)
- One fix before merge: the README still shows the alert line as `{"text": …}`, which this PR made false. Update it to the real line format and add the case to tests/test_readme.py if that fits.
- Leave the other two non-blocking items as is: a widget click during the Allow wait (launchd does not start an overlapping run of the same job); the two narrow duplicate cases (re-sending once is the intended tradeoff).

### Context (earlier requirement, already built in this branch)
TASK-640: an alert not handed to macOS is not recorded in `notified`; the next `collect` emits it again. `collect --emit-alerts` prints each alert as `AUM-ALERT ` + JSON `{"text": …, "add": [key], "remove": [key]}` (agent_usage_monitor/cli.py `_emit`, agent_usage_monitor/alerts.py `evaluate`); the host passes the lines macOS took to `record-alerts`.

### Conventions and git rules
- Write code, docs and commits in the target repo's conventions (no CLAUDE.md/AGENTS.md; README style; commits `TASK-640: …`). Default branch: `main`.
- No mutation testing, for you and every producer/reviewer sub-agent (put this rule in every brief): never modify the source to see what happens, no manual or tool-driven mutation testing (mutmut etc.), not even briefly or in a throwaway copy; never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call, leaving the code under test unmodified.
- Push only branch `TASK-640-m2`; force-push only with `--force-with-lease`. Never merge into or touch any other branch.
- Do not install into `~/Applications`, do not kill system processes, do not change the user's notification settings.

### Docs
The plan doc stays where autopilot puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

### Run rules
Work only in `<WORKTREE>` on branch `TASK-640-m2`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <WORKTREE> push -u origin TASK-640-m2`.

Verify: `make check`
CI checks: ["make check"]

## Progress log

- S1: mode=stay branch=TASK-640-m2 publish=ci
- decision(publish): continues draft PR PR #6
- S4: 1 task
- S5 task 1 done: f4464df red=test_readme.test_alert_line_format
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- S6 r1 @f4464df: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (CI make check success, ci-verdict exit 0) -> converged
- residual NON-BLOCKING: doc#1

## Review items

### r1
- doc#1 NON-BLOCKING: docs/design/TASK-638-m2-mac-alerts-plan.md:45,115 still show the line as {"text": …} and say collect records notified itself; historical, superseded by the TASK-640 plan.
- verification: CI make check passed at f4464df.

## Notes

- README Alerts section line 60 names the line format; tests/test_readme.py `section("Alerts")` helper
- emitted line: cli._emit prints `AUM-ALERT ` + json.dumps(alert), alert = {"text", "add", "remove"} (alerts.evaluate)

## Task list

### Header

Global Constraints: README alert line shown as `AUM-ALERT {"text": …, "add": […], "remove": […]}`, with `add`/`remove` explained as the `notified` change `record-alerts` makes. PR: #6.

### Task 1: README shows the real alert line
- Files: README.md, tests/test_readme.py.
- Tests first: test_readme asserts the Alerts section shows the line with `"add"` and `"remove"` and no longer the bare `{"text": …}` form.
- Checks: `make test`.
- Commit: `TASK-640: README: the alert line carries its notified change`
