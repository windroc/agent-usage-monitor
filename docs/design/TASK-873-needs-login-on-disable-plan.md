Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-873-logged-out-claude-account-report-auth-an base_ref=583d04c1a9baa28de372f8c70198bd2df440069a review_round=1 input_sha=318932ed85ea

# Input

## Requirement (TASK-873, gate feedback on PR #12)

Repo: windroc/agent-usage-monitor (branch TASK-873-logged-out-claude-account-report-auth-an, PR PR #12; earlier plan: docs/design/TASK-873-logged-out-auth-plan.md)

1. Fix correctness#1 now (not deferred): in `agent_usage_monitor/claude.py`, set `needs_login=False` in both disable returns (the still-disabled return in the `usage_disabled_version` branch, ~:142, and the unrecognized→disable returns, ~:168-174), since `claude auth status` has just said the account is not logged out. Add a test for the repro: logged out (needs_login True), then logged in with unrecognized `/usage` output → the row is disabled with needs_login False. The PR's deferred section drops it.
2. PR body wording (the caller writes the PR body; nothing in the repo): detection approach "approved by the commander", not "the user".

### Conventions and git rules

- Write code, docs and commits in the repo's conventions (no CLAUDE.md/AGENTS.md; follow README.md, docs/ and surrounding code; `tests/pii_scan.py` must pass; keep the Makefile `check` NFR-1 grep clean).
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

`make check` (macOS; CI job `make check`)
CI checks: ["make check"]

# Progress log

- S1: mode=stay, base_ref 583d04c
- decision(pr): PR #12 (draft) is this branch's PR; the caller updates its body (item 2)
- S5 task 1 done: 4977e8e red=18 (new repro tests + updated disable-field expectations)
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- S6 r1 @4977e8e: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (command=ci-verdict.py on PR #12, make check success, exit code=0) -> converged
- S7: residual NON-BLOCKING: verification#1 (evidence only)

# Review items

## S6 r1
- verification#1 (NON-BLOCKING): CI at 4977e8e passed: make check (success); ci-verdict.py exit 0; HEAD 4977e8e7983ec7d537d56f009a6bfd300b3764a2 and clean status before and after

# Notes

- Python tests: `python3 -m unittest discover -s tests -t .`; fake claude in tests/helpers.py (`auth_status`, `auth_exit`).

# Task list

Global constraints: PR #12 is the branch's PR. The row field is `needs_login` (bool). Both disable returns in `claude.refresh` also carry `"needs_login": False`. No mutation testing.

### Task 1: Clear needs_login when the probe is disabled while logged in

Files: agent_usage_monitor/claude.py, tests/test_claude.py.
Tests first:
- RefreshTest: logged out → AUTH_FIELDS. Then logged in with unrecognized output → fields `{"usage_disabled_version": "2.1.302 (Claude Code)", "needs_login": False}`. Then the disabled row (same version, logged in) → fields `{"needs_login": False}`.
- CollectProbeTest end to end: logged out, then logged in with unrecognized output → row has needs_login False and usage_disabled_version set.
- Update the existing expectations for disable fields (test_error_kinds, test_auth_status_not_logged_out, test_version_failures, test_version_first_line, test_version_disable_cycle).
Checks: python unit tests, pii_scan, NFR-1 grep.
Commit: `fix(claude): clear needs_login when the probe is disabled while logged in`
