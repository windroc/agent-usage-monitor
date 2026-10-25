Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-621-pre-push-hook-make-check base_ref=2f07d2bc111bd525dc917f3ce6345577331986e6 review_round=1 input_sha=83ea5f0f990d

## Input

# Requirement: TASK-621 follow-up: hashed identity allowlist entry (user, 2026-10-17)

Repo: windroc/agent-usage-monitor, PR #17 (branch `TASK-621-pre-push-hook-make-check`).

## User's requirements
- Blocker: `tests/pii-allowlist.txt` holds the owner's email address in plain text. The repo must never hold that literal, in any file.
- Store it as a SHA-256 of the lowercased address, e.g. `sha256:<hex> in:identity`.
- The scanner hashes each commit author/committer email and compares.
- Add a test using a fake address.
- Compute the hash locally from `git config user.email`; never print the address in logs, the PR or commits.
- Review: light-build re-review with correctness + verification.
- History issues are moot: the repo will be recreated from one squashed commit.

## Conventions and git rules
- Follow the target repo's conventions for code, docs and commits (subjects `TASK-621: ...`, trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Default branch: `main`.
- **No mutation testing**: never modify the source to see what happens: no manual or tool-driven mutation testing, not even briefly or in a throwaway copy that is then run; never put a known-wrong value into shipped code to force a branch. Every brief to a sub-agent (producer, reviewer) carries this rule.
- Push only branch `TASK-621-pre-push-hook-make-check`; force-push only with `--force-with-lease`. Never merge into or otherwise touch any other branch.

## Docs
The plan doc stays where autopilot puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

## Run constraints
Work only in `<WORKTREE>` on branch `TASK-621-pre-push-hook-make-check`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <WORKTREE> push -u origin TASK-621-pre-push-hook-make-check`.

## Verify

make check
CI checks: ["make check"]

## Progress log

- S1: mode=stay, branch TASK-621-pre-push-hook-make-check, base_ref 2f07d2b.
- decision(hash): allowlist pattern `sha256:<hex>` matches a value whose lowercased SHA-256 hex equals <hex>; works with or without scope. The allowlist-file exemption for scoped entries is removed: a hash never matches a scan rule, so the allowlist no longer needs it.
- decision(tests): the e2e owner-identity tests read the literal from the allowlist; they become unit tests with a fake hashed address, plus a guard that every `in:identity` entry in the repo allowlist is a sha256 hash.
- S5 task 1 done: 327f98a red=3 (sha256 matching missing; repo identity entry was a literal); scanner tests 23 OK; make pii-scan exit 0; no tracked file holds the owner email domain; hook dry run on 327f98a (owner as author) exit 0.
- decision(panel): user asked for correctness + verification re-review; requirement-fidelity and doc carry their PASS from the previous build's r1.
- S6 panel: pinned=[correctness,verification] verification=ci transport=Workflow
- S6 r1 @327f98a: correctness=PASS verification=PASS (CI make check success at 327f98a, ci-verdict exit 0) -> converged
- Residual NON-BLOCKING: correctness#1 no scan_push-level test with a sha256 identity entry; correctness#2 load_allowlist accepts malformed `sha256:` tails that never match.
- S7: plan doc copied to docs/design/TASK-621-hashed-identity-plan.md with machine paths replaced by `<WORKTREE>`, `<AUTOPILOT>`, `<WORKDIR>`.

## Review items

r1 (@327f98a):
- correctness#1 NON-BLOCKING: tests/test_pii_scan.py: the removed end-to-end owner tests (identity passes push, same value refused in message/file) have no hashed replacement; the sha256 path through scan_push:123 is covered only via allowed(). Add a PrePushTest or scan_push-level test with a sha256 entry of the fake EMAIL: author passes, message 'mail '+EMAIL refused.
- correctness#2 NON-BLOCKING: tests/pii_scan.py:43 load_allowlist accepts any `sha256:` tail; an entry with uppercase hex or a wrong length loads fine but never matches in matches():52. Validate `sha256:[0-9a-f]{64}` at load and exit with the line number, as for a bad scope.
- verification#1 NON-BLOCKING: CI make check success at 327f98a.

## Notes

## Task list

Global Constraints: the owner's address never in any file, log, commit or PR text; the hash comes from `git config user.email`, lowercased, newline stripped.

### Task 1: hashed identity entry

- Files: tests/pii_scan.py, tests/pii-allowlist.txt, tests/test_pii_scan.py, README.md (allowlist sentence if needed).
- Tests first: fake address hashed at runtime allowed as identity (any case), still a hit in text; repo allowlist identity entries are all `sha256:`.
- Checks: make test (scanner tests), make pii-scan, `git grep -c` for the owner email domain = 0.
- Commit: `TASK-621: store the owner's commit email as a SHA-256 in the allowlist`.
