Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-874-widget-manual-refresh-icon-left-of-the-s base_ref=2e86815c2627c648f27ae54f089b9b20c43dbb37 review_round=1 input_sha=c5d00355a94a

# Plan: TASK-874 README no-data wording

## Input

# Requirement: TASK-874 follow-up (user, 2026-10-23, gate on PR #14)

Repo: windroc/agent-usage-monitor. Branch already holds the TASK-874 refresh arrow (plan doc .autopilot/widget-refresh-icon-plan.md, phase done; docs/design/TASK-874-widget-refresh-icon-plan.md).

## User's requirements
1. Fix README.md:57's no-data sentence: it reads "With no snapshot it shows `Agent Usage Monitor：没有数据`, the arrow and the gear; click it to collect." where "it" reads as the gear, which opens settings. It must say "click the widget or the arrow to collect" (the gear opens settings).
2. (PR body in English, no preview step: the caller writes the PR body; not this build's work.)

Earlier review items this resolves: correctness#1 and requirement-fidelity#1 of the TASK-874 build (README no-data sentence). Keep tests/test_readme.py passing; add or adjust an assertion only if it fits the existing style.

## Conventions and git rules
- Repo conventions; commits `TASK-874: <message>` plus `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Push only branch `TASK-874-widget-manual-refresh-icon-left-of-the-s`; force-push only with `--force-with-lease`. Never merge into or touch any other branch, including `main` (the default branch).
- **No mutation testing**, whatever a spec, plan or reviewer asks: while building, reviewing or testing, never modify the source to see what happens: no manual or tool-driven mutation testing (mutmut etc.), not even briefly or in a throwaway copy that is then run; never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call such as `os.listdir`, leaving the code under test unmodified. Every brief to a sub-agent (producer, reviewer) carries this rule.
- This Linux host has no Swift toolchain; Swift is checked only by CI (`make check`).

The plan doc stays where autopilot puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

Work only in `<WORKTREE>` on branch `TASK-874-widget-manual-refresh-icon-left-of-the-s`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <WORKTREE> push -u origin TASK-874-widget-manual-refresh-icon-left-of-the-s`.

## Verify

Verify command: `make check`
CI checks: ["make check"]

## Progress log

- S1 done: mode=stay, branch TASK-874-widget-manual-refresh-icon-left-of-the-s, base_ref 2e86815 (after merging origin/main incl. TASK-877 f1ff2cb).
- decision(publish): PR #14 (draft) is this branch's PR; publish=ci.
- S4 done: 1 task.
- S5 task 1 done: e100b7c red=1 (test_refresh_arrow new assertion); make test OK, make pii-scan ok
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- S6 r1 pinned @e100b7c; PR PR #14 (draft)
- S6 r1 @e100b7c: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (CI check make check, success) -> converged
- residual NON-BLOCKING: correctness#1 (README no-data sentence leaves out the `点这里刷新` caption; pre-existing)

## Review items

- S6 r1:
  - correctness#1 NON-BLOCKING: README.md:57: the no-data sentence lists what the widget shows as `Agent Usage Monitor：没有数据`, the arrow and the gear, but macos/Widget/AgentUsageMonitorWidget.swift:59 also shows a caption line `点这里刷新` in that state, and the sentence leaves it out. This gap was already there before this change. Consider adding the caption to the list so the README matches what the widget renders.
  - verification#1 NON-BLOCKING: CI at e100b7c passed: make check (success); ci-verdict.py exit 0. HEAD and status unchanged before and after.
## Notes

- Local checks: make test, make pii-scan; Swift only on CI.

## Task list

Global Constraints:
- PR: PR #14 (draft).
- New wording: "click the widget or the arrow to collect".

### Task 1: README no-data sentence names what collects

- Files: README.md (line 57), tests/test_readme.py.
- Tests first: test_refresh_arrow also asserts "the arrow and the gear; click the widget or the arrow to collect".
- Checks: make test (test_readme), make pii-scan.
- Commit: `TASK-874: README: the no-data widget collects on a click of the widget or the arrow`
