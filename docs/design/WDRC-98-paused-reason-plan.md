Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=WDRC-98-widget-shows-why-a-row-is-stale-instead base_ref=a948c5313f34624f8d85251a4e73a422d307127f review_round=1 input_sha=285d46d9e4f4

## Input

WDRC-98 (light-build): the unrecognized-output reason is exactly `/usage unreadable · paused`

Repo: windroc/agent-usage-monitor (default branch `main`). Ticket: https://linear.app/windroc-workgroup/issue/WDRC-98/widget-shows-why-a-row-is-stale-instead-of-a-bare-warning-sign

## Requirements (precedence: the user's requirements since the last build > the user's instructions; within each, newer > older)

### The user's requirements since the last build (2026-10-25; highest precedence)

1. After previewing the branch on the real Mac: the unrecognized-output reason is too long and truncates (medium shows `/usage output not recognized, pa…`, large `/usage output not recogniz…`), hiding that the probe is paused. Make the widget `error` for that case (the Claude probe disabled for a version: newly at the DISABLE_AFTER-th unrecognized output, or kept from an earlier run; known or unknown version) exactly `/usage unreadable · paused`, with no version; the version stays in the log line. Keep every other reason as is.
2. The reason replaces the bars only on stale rows (values older than 6 h) or rows with no values yet; a failing row with values under 6 h keeps its bars (already built; keep it).
3. Commander (latest): this ticket runs on light-build. Scope of this build is the wording change in 1; no spec doc.

### The user's instructions (already built on this branch; the review checks they still hold)

- `collect` writes a short, English `error` string on a row whenever that row's probe fails this run and the row keeps old values; null on success. `needs_login` rows keep their own notice (`needs login · claude /login`, no triangle). Every failure kind of each probe has a reason. The text holds no email, path or other personal data.
- The widget shows `error` in place of the bars, styled like the TASK-873 login notice, in every widget size, truncated with an ellipsis if too long.
- Every stale row has a red `exclamationmark.triangle.fill` SF Symbol before the title instead of the text `⚠ `; a stale row without `error` (older snapshot) keeps its bars.
- Snapshot schema stays compatible: `error` optional, older snapshots decode.
- Tests: Python unit tests set and clear `error` for each failure kind; Swift tests (`macos/Tests/main.swift`) render a row with `error` and one without.
- README describes the notice. `make check` passes.
- Out of scope: the retry rule for unrecognized output (WDRC-97), alert notifications, the settings window.

## What this build changes

- `agent_usage_monitor/claude.py`: the paused reason becomes the constant `/usage unreadable · paused` (replacing `_paused(version)`); remove helpers left without users (`_short_version`, `_SUFFIX`) and their test (`tests/test_claude.py::test_short_version`). Log lines unchanged.
- Tests quoting the old text: `tests/test_claude.py` (`UNKNOWN_PAUSED`, `paused()`, `KEPT_DISABLED` and users), `macos/Tests/main.swift` (`let reason = …`).
- `README.md`: its reason example `/usage output not recognized, paused for claude 2.1.302` becomes `/usage unreadable · paused`; keep `tests/test_readme.py` passing.
- Every other reason stays as is (including `/usage output not recognized (<n> of <m>)`).

## Branch state (important)

This branch already holds commits 5026619, 0a5d224, db51bcd, 21ac4f4 (Codex reason and the `error` field; Claude reasons; widget notice and red triangle; README) from an earlier run whose plan doc was lost before its work review, so they were never reviewed. They ARE this build's work: right after S1, set RESUME `base_ref` to `git -C <worktree> merge-base HEAD origin/main` (a948c5313f34624f8d85251a4e73a422d307127f) and log it as `decision(base_ref)`, so S6 reviews them with this build's commits. An abandoned build plan doc, `.autopilot/stale-row-error-plan.md` (stopped at S3), and its spec belong to another input: leave them untouched.

## Conventions and git rules

- Write code, docs and commits in the repo's conventions (no `CLAUDE.md` / `AGENTS.md`; commit subjects so far are `WDRC-98: <Sentence>`).
- No mutation testing, whatever a spec, plan or reviewer asks: while building, reviewing or testing, never modify the source to see what happens: no manual or tool-driven mutation testing (mutmut etc.), not even briefly or in a throwaway copy that is then run; never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call such as `os.listdir`, leaving the code under test unmodified. Every brief to a sub-agent (producer, reviewer) carries this rule.
- Push only branch `WDRC-98-widget-shows-why-a-row-is-stale-instead`; force-push only with `--force-with-lease`. Never merge into or otherwise touch any other branch, `main` included.
- This Linux host has no swiftc; Swift checks (`make swift-test`, `make app`) run on CI.

The plan doc stays where autopilot puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

Work only in `<WORKTREE>` on branch `WDRC-98-widget-shows-why-a-row-is-stale-instead`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <WORKTREE> push -u origin WDRC-98-widget-shows-why-a-row-is-stale-instead`.

Verify: `make check` (pii-scan, `/usr/bin/python3 -m unittest discover -s tests -t .`, swift-test, app; macOS only)
CI checks: ["make check"]

## Progress log

- S1: mode=stay branch=WDRC-98-widget-shows-why-a-row-is-stale-instead
- decision(base_ref): base_ref=a948c5313f34624f8d85251a4e73a422d307127f (merge-base HEAD origin/main), not resolver's 21ac4f4, so S6 reviews unreviewed commits 5026619..21ac4f4 (input: Branch state)
- decision(publish): publish=ci (pull_request workflow `check`), base=main
- S4 done: 1 task
- S5 task 1 done: c72f288 red=15 (paused-reason tests in tests/test_claude.py)
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- decision(ci-read): ci-verdict.py gets HTTP 403 on the check-runs API (NO_CI); `gh pr checks` works, so the verifier prompt names it as the way to read the same `make check` result; draft PR https://github.com/windroc/agent-usage-monitor/pull/2 opened by pr.py push
- S6 r1 @c72f288db2e360bb4a2159fe3990056ff0bf3c23: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (command=gh pr checks 2 --watch (ci-verdict NO_CI 403), make check pass in 2m43s, run 40199696589) -> converged
- residual NON-BLOCKING: none (verifier's evidence notes only)

## Review items

- S6 r1: no BLOCKING items. NON-BLOCKING (verification): verification#1 ci-verdict.py exited 3 (NO_CI: check-runs HTTP 403), CI read via gh; verification#2 `make check` pass on c72f288 (run 40199696589); verification#3 HEAD and status unchanged before and after.

## Notes

- S6 converged after r1.

- Local checks (Linux, no swiftc): `/usr/bin/python3 -m unittest tests.test_claude tests.test_cli tests.test_store tests.test_readme`, `/usr/bin/python3 tests/pii_scan.py`.
- claude.py `failed(reason, log, **fields)` returns (fields+error, True, prefix+log); paused reason used at the kept-disabled branch and both disable branches.

## Task list

Global Constraints: paused reason exactly `/usage unreadable · paused` (U+00B7 middle dot, spaces around it); log lines unchanged; every other reason unchanged; no mutation testing.

### Task 1: The paused reason is `/usage unreadable · paused`

- Files: `agent_usage_monitor/claude.py`, `tests/test_claude.py`, `macos/Tests/main.swift`, `README.md`, `tests/test_readme.py` (only if it quotes the old text).
- Produces: `claude.PAUSED = "/usage unreadable · paused"`; `_paused`, `_short_version`, `_SUFFIX` removed.
- Tests first: in `tests/test_claude.py` replace `UNKNOWN_PAUSED` and `paused()` with `claude.PAUSED`-independent literal `"/usage unreadable · paused"` for known, unknown and unreadable versions (new disable and kept disable); log-line assertions keep the version; delete `test_short_version`. Red: the paused tests fail before the code changes.
- Code: `PAUSED` constant replaces `_paused(...)` at its 3 call sites.
- Swift fixture `let reason` and README example `/usage output not recognized, paused for claude 2.1.302` → `/usage unreadable · paused`.
- Checks: the local checks in Notes.
- Commit: `WDRC-98: Show the paused probe's reason as /usage unreadable · paused`
