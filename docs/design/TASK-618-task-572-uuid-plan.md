Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-618-task-572-uuid base_ref=3676e392023da5936aa09095542152f2d3d12294 review_round=2 input_sha=fc86a98eed3c

## Input

## Requirement (TASK-618)

Repo: windroc/agent-usage-monitor (public repo; NFR-4 of PRD TASK-561 forbids personal data in it).

Problem: on `main`, `tests/fixtures/claude-usage/A1.find.txt` and `A2.find.txt` contain real UUIDs, one an organization ID, brought in by PR #2 (d97e999, TASK-572). Other TASK-572 fixtures may also have some.

Acceptance criteria:
- Replace every real UUID, organization ID and session ID in the repo's current files with placeholders such as `<ORG_ID>`, `<SESSION_ID>`, written the same way as the TASK-583 fixtures (PR #13). Tests that use these fixtures still pass.
- Scan the whole repo for what NFR-4 lists: emails, organizations, login names, home paths, account directory names. Replace any real values found the same way. Record the scan commands and their results (counts / file list, never the real values) for the PR description. Never write a real value into any file, commit message, plan doc or PR text.
- Fix only the current files. Do not rewrite git history (the user decides that separately).
- `make check` and CI pass.

## Conventions and git rules
- Follow the target repo's conventions (its CLAUDE.md / AGENTS.md); default branch `main`.
- No mutation testing: never modify the source to see what happens, no mutmut or similar, not even briefly or in a throwaway copy; never put a known-wrong value into shipped code to force a branch. Every brief to a sub-agent carries this rule.
- Push only branch `TASK-618-task-572-uuid`; force-push only with `--force-with-lease`. Never touch other branches.

The plan doc stays where autopilot puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

Work only in `<WORKTREE>` on branch `TASK-618-task-572-uuid`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <WORKTREE> push -u origin TASK-618-task-572-uuid`.

## Verify

make check
CI checks: ["make check"]

## Progress log

- S1: mode=stay, branch TASK-618-task-572-uuid, base_ref 3676e39.
- decision(placeholders): `plugins/synced/<uuid>_<uuid>` → `<ORG_ID>_<SYNC_ID>` (TASK-583 fixtures name the same path segment so); the five session-log UUIDs → `<SESSION_ID_1>`..`<SESSION_ID_5>`, n matching the `<OTHER_PROJECT_n>` they sit under (one session per project), so distinct sessions stay distinct.
- decision(scope): no new NFR-4 guard in `make check`; the requirement asks for the cleanup and a scan, not a new check.
- S5 task 1 done: af1d062 red=none (data-only); make test exit 0 (126 tests); UUID grep 0; literal-value scan 0 (other scan counts in Notes).
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- S6 r1 @af1d062: correctness=PASS requirement-fidelity=FAIL doc=PASS verification=PASS (CI make check success) -> requirement-fidelity#1 scan recorded as machine path leaking encoded home/login, not rerunnable; fixing (plan doc only, no commit: .autopilot/ is untracked)
- decision(doc#1): leave docs/design/TASK-583 plan's "deferred" line as is; it is that run's historical record.
- S6 r2 @af1d062: requirement-fidelity=PASS (raw VERDICT PASS; its one BLOCKING entry is the prior-items status line, #1 and #2 RESOLVED, no open item) verification=PASS (CI make check success) -> converged
- Residual NON-BLOCKING: doc#1 (TASK-583 plan's deferred line could point to TASK-618).
- S7: plan doc copied to docs/design/TASK-618-task-572-uuid-plan.md with machine paths replaced by `<WORKTREE>`, `<AUTOPILOT>`, `<WORKDIR>`.

## Review items

r1:
- requirement-fidelity#1 BLOCKING: Notes recorded the scan as an absolute scratchpad path that embeds the home path and login in dash-encoded form; not rerunnable. Fix: runnable commands, no machine path.
- requirement-fidelity#2 NON-BLOCKING: "scan all 0" omits the counts and file list for the email-shaped and /Users/ patterns.
- doc#1 NON-BLOCKING: docs/design/TASK-583-claude-config-dir-usage-plan.md:17 still lists the TASK-572 fixture UUIDs as deferred; optionally point to TASK-618.
- verification#1 NON-BLOCKING: CI make check success at af1d062.

## Notes

- Real UUIDs (31 lines) only in tests/fixtures/claude-usage/{A1.find.txt,A2.find.txt,observations.json}; no test reads find.txt or observations.json (tests read only A1/A2.stdout.txt).
- NFR-4 scan, run from the repo root (values never printed; `<values>` is a temp file outside the repo):
  1. `git grep -cIiE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'` (UUIDs)
  2. `git grep -cIE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}'` (emails)
  3. `git grep -cIE '/(Users|home)/[A-Za-z0-9._-]+'` (home paths)
  4. Literal values: `{ id -un; echo "$HOME"; echo "$HOME" | tr / -; git config --global user.email; for f in ~/.claude.json ~/.claude-*/.claude.json; do jq -r '.oauthAccount // {} | .emailAddress, .organizationName, .organizationUuid, .accountUuid, .displayName | values' "$f"; done; for d in ~/.claude-* ~/.codex-*; do [ -d "$d" ] && basename "$d"; done; } 2>/dev/null | grep -v '^$' | sort -u > <values>` then `git grep -cIiF -f <values>` (login, home path incl. dash-encoded form, emails, org names, org/account IDs, display name, account directory names; 14 values)
  5. PNGs (`docs/images/widget-demo.png`, `macos/Host/AppIcon.png`): `strings -n 6 <png> | grep -ciE "/Users/|$(id -un)|<account dir names>|<email regex>"`
- Scan results at base 3676e39: (1) 31 lines in tests/fixtures/claude-usage/{A1.find.txt 7, A2.find.txt 4, observations.json 20}; (4) A1.find.txt 1, A2.find.txt 1, observations.json 2 (org ID and account ID).
- Scan results at af1d062: (1) 0; (4) 0; (5) 0 both PNGs; (2) 15 lines in 10 files, all synthetic: Makefile 1 (`icon_512x512@2x.png`), README.md 1 and TASK-586 plan 1 (`git@github.com:` clone URL), TASK-585 plan 1 (`noreply@anthropic.com` trailer), TASK-587 spec 1, TASK-605 plan 2 (`@2x.png`), codexbar-parse-samples.json 4, test_claude.py 1, test_claude_usage.py 1, test_codex.py 2 (`user@example.com` / `fixture@example.com`); (3) 12 lines in 5 files, all synthetic: TASK-586 plan 2 (`/Users/u`, `/Users/...`), TASK-600 plan 1 (`/Users/runner` CI log), TASK-605 plan 2 (`/Users/...`), macos/Tests/main.swift 1 (`/Users/u`), codexbar-parse-samples.json 6 (`/Users/example`).
- The S7 copy of this plan doc must replace every absolute worktree path (Rules, RESUME, Input lines) with `<worktree>` / `<autopilot>` placeholders, as earlier docs/design plans do, and pass scan (4) with the dash-encoded home form.
- Redaction placeholder list lives in docs/spikes/TASK-572-claude-usage.md:83; must add the new placeholders there.
- Commit subject convention: `TASK-<n>: <Chinese subject>`.
- Local check for this change: `make test` (Python unittest); fixtures are data only.

## Tasks

Global Constraints: placeholders exactly `<ORG_ID>`, `<SYNC_ID>`, `<SESSION_ID_1>`..`<SESSION_ID_5>`; no real value in any file, commit message or PR text; no history rewrite.

### Task 1: Redact TASK-572 fixture UUIDs

- Files: tests/fixtures/claude-usage/A1.find.txt, A2.find.txt, observations.json; docs/spikes/TASK-572-claude-usage.md (placeholder list, line 83).
- Consumes / Produces: none.
- Tests to write first: none (data-only; no test reads these files). Check after: UUID regex `git grep -E` over the repo returns nothing; scan script shows 0 for org ID / account ID.
- Checks: `make test`; UUID grep; scan script.
- Commit message: `TASK-618: TASK-572 样本里的真实 UUID 换成占位符`
