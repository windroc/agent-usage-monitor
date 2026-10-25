Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-600-github-actions-ci-make-check base_ref=c8602e77654d8da4d9b0076d707c0c15d61cb67c review_round=1 input_sha=b914e0cf8f96

## Input

## Requirement (TASK-600 fix build 1: PR CI check `make check` fails)

Repo: windroc/agent-usage-monitor (public). This branch adds `.github/workflows/check.yml` (TASK-600), running `make check` on `macos-26` with `DEVELOPER_DIR=/Library/Developer/CommandLineTools`. Its first run on PR #9 failed; make the PR's `make check` CI check pass. Locally `make check` passes (also with that DEVELOPER_DIR).

Failing check: `make check`, run https://github.com/windroc/agent-usage-monitor/actions/runs/39036318732. Log (failed step):

```
/usr/bin/python3 -m unittest discover -s tests -t .
.............................F..............................................................................................
FAIL: test_timeout_kills_group (tests.test_claude.RefreshTest)
Traceback (most recent call last):
  File "/Users/runner/work/agent-usage-monitor/agent-usage-monitor/tests/test_claude.py", line 78, in test_timeout_kills_group
    self.assertFalse(alive(call["child"]))
AssertionError: True is not false
Ran 124 tests in 64.866s
FAILED (failures=1)
make: *** [test] Error 1
```

Find the root cause (e.g. a timing race where the killed child is not yet gone or reaped when the test checks, on a slower runner; compare `test_exited_claude_whose_child_holds_stdout`, which already waits up to 3 s for launchd to reap) and fix it where it originates: in the test if the product code is correct, in `quotaboard/` if the product leaves the child running. Do not weaken what the test proves. Keep the workflow's acceptance criteria intact: `make check` not changed for CI, actions pinned by SHA, `permissions: contents: read`, no secrets, no personal information (public repo), no ruleset or repo-setting changes.

## Rules
- Write code, docs and commits in the target repo's conventions (its `CLAUDE.md` / `AGENTS.md`; it has neither, follow existing code). Default branch: `main`. Never merge into or otherwise touch any branch other than `TASK-600-github-actions-ci-make-check`; force-push only with `--force-with-lease`.
- No mutation testing, whatever a spec, plan or reviewer asks: never modify the source to see what happens: no manual or tool-driven mutation testing (mutmut etc.), not even briefly or in a throwaway copy that is then run; never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call such as `os.listdir`, leaving the code under test unmodified. Every brief to a sub-agent (producer, reviewer) carries this rule.

The plan doc stays where autopilot puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

Work only in `<WORKTREE>` on branch `TASK-600-github-actions-ci-make-check`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <WORKTREE> push -u origin TASK-600-github-actions-ci-make-check`.

## Verify

make check
CI checks: ["make check"]

## Progress log

- S1: mode=stay, base_ref c8602e7
- decision(publish): pr.py start (run after S5 commit) -> publish=ci, pr=PR #9 (opened by caller)
- decision(root cause): product is correct: proc.stop (quotaboard/proc.py:36) kills the whole group and reaps the leader. The grandchild (fake claude's child) is orphaned when its parent is SIGKILLed; it stays a zombie until launchd reaps it, and `alive()` (os.kill(pid, 0)) is True for a zombie. tests/test_claude.py:78 and :83 check right after the kill; :92-95, tests/test_codex.py:66-72 and tests/test_cli.py:240-243 already wait up to 3 s. On the slower CI runner the reap lost the race.
- S5 task 1 done: e355d51 red=CI run 39036318732 (test_timeout_kills_group)
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- decision(scope): S5 also moved the identical inline 3 s wait loops in tests/test_codex.py and tests/test_cli.py onto `reaped` (same assertions; cli adds an explicit 2-pid count that `[False, False]` implied), so one helper holds the reap wait
- S6 r1 @e355d51: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (CI check make check success at e355d51, ci-verdict exit 0) -> converged
- Residual NON-BLOCKING: requirement-fidelity#1 (spec-drift: test_cli/test_codex edits not in Task 1 Files; logged above)

## Review items

- r1 requirement-fidelity#1 (NON-BLOCKING): [spec-drift] Task 1 Files names only tests/helpers.py and tests/test_claude.py, but e355d51 also rewrites tests/test_cli.py:240-241 and tests/test_codex.py:67 to use `reaped`; same checks; no decision recorded and the commit message says only "claude tests".
- r1 verification#1 (NON-BLOCKING): CI at e355d51 passed: make check (success).

## Notes

- Test helpers in tests/helpers.py (`alive`, `pids`, `claude_calls`).

## Task list

Global Constraints: product code unchanged; `make check` and the workflow unchanged; wait bound 3 s, poll 0.05 s (existing pattern).

### Task 1: wait for launchd to reap orphaned grandchildren in claude tests

- Files: tests/helpers.py (new `reaped(*pids)`: polls `alive` up to 3 s, returns True when none alive), tests/test_claude.py (use it at :77-78, :83 and in place of the inline loop at :92-95).
- Tests first: n/a (test-only race fix; red is the CI log above).
- Checks: `/usr/bin/python3 -m unittest tests.test_claude` with and without DEVELOPER_DIR=/Library/Developer/CommandLineTools.
- Commit message: `TASK-600: wait for launchd to reap killed grandchildren in claude tests`
