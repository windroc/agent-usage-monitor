Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-621-pre-push-hook-make-check base_ref=f3a515f30d51ff8a47ce63866334b1218fbfa4b2 review_round=1 input_sha=7edd784029a7

## Input

# Requirement: TASK-621 follow-up: MIT license (user, 2026-10-17)

Repo: windroc/agent-usage-monitor, PR #17 (branch `TASK-621-pre-push-hook-make-check`).

## User's requirements
- Add `LICENSE` with the standard MIT text from https://opensource.org/license/mit, with the line `Copyright (c) 2026 windroc` (the GitHub handle, not a real name).
- Add a short "License" section at the end of README pointing to it. Keep THIRD_PARTY_NOTICES.md as is.
- The PII scan (`make pii-scan`, tests/pii_scan.py) must still pass.
- Review: light-build settings; re-review only what this touches, plus the verifier.

## Conventions and git rules
- Follow the target repo's conventions for docs and commits (subjects `TASK-621: ...`, trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`). Default branch: `main`.
- **No mutation testing**: never modify the source to see what happens: no manual or tool-driven mutation testing, not even briefly or in a throwaway copy that is then run; never put a known-wrong value into shipped code to force a branch. Every brief to a sub-agent (producer, reviewer) carries this rule.
- Push only branch `TASK-621-pre-push-hook-make-check`; force-push only with `--force-with-lease`. Never merge into or otherwise touch any other branch.
- No real personal values (emails, UUIDs, home paths) in files, commit messages, the plan doc or PR text.

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

- S1: mode=stay, branch TASK-621-pre-push-hook-make-check, base_ref f3a515f (merge of origin/main into the branch, before this build).
- decision(text): MIT text verbatim from opensource.org/license/mit (curly quotes kept), with the conventional `MIT License` title line and the copyright line the user gave.
- S5 task 1 done: 7a9c209 red=none (docs only); make pii-scan exit 0.
- decision(panel): user asked to re-review only what this touches plus the verifier; the change is docs only (LICENSE, README), so correctness is not dispatched.
- user requirement mid-run (2026-10-17): copyright line = owner's name + GitHub noreply address (name approved for LICENSE only); add that exact address to tests/pii-allowlist.txt with reason "owner's GitHub noreply address (LICENSE)". Supersedes the handle-only line. Done in a second commit before r1.
- user requirement mid-run 2: copyright line uses the owner's published contact address instead of noreply; allowlist that exact address (reason "owner's published contact (LICENSE, commit author)") instead of the noreply entry. Commit b9f76f1. The r1 dispatched at 60299cf was stopped before any verdict (stale) and re-run at b9f76f1.
- user decision: the owner's address as commit author is fine (allowlisted); do not add the GitHub web-flow committer address. Hook dry run on this branch now exit 0.
- S6 panel: pinned=[requirement-fidelity,doc,verification] verification=ci transport=Workflow
- user requirement mid-run 3: owner's address only in LICENSE, scoped by file; flagged as commit author/committer; allowlist owner's GitHub noreply and GitHub's web-merge committer. Implemented uncommitted, then superseded by 4 before commit (discarded).
- user requirement mid-run 4: LICENSE copyright line name only, no address; remove the owner-address entry and its file scoping; keep the noreply entries; README License = `[MIT](LICENSE) © <owner name linked to LinkedIn>`. Commit 83f71cc.
- user requirement mid-run 5: owner's git user.email stays; allowlist it for commit author/committer only, still a hit in files and messages; LICENSE stays name-only. Commit f780768: allowlist `in:identity` scope.
- Hook dry run over full history (remote with no refs): identity hits 0; remaining hits are history only: LICENSE email in b9f76f1 (this branch, pushed), real UUIDs in TASK-572 fixture blobs from before TASK-618. Reported to the user, no history rewrite.
- decision(panel): code changed (scanner), so the full light-build panel runs; the earlier 3-lens freeze never got a verdict.
- S6 r1 dispatched at f780768, stopped before any verdict: user added the TASK-622 rename to this PR (HEAD would move).
- user requirement mid-run 6: product rename per Linear TASK-622 (every layer quotaboard -> Agent Usage Monitor; no migration code; frozen spikes and plan docs may keep the old name, listed in the PR; pii scan, make check, CI pass; no install into ~/Applications; PR title covers both). Task 2 added.
- decision(rename-scope): kept old name in docs/design/* (frozen plan/spec docs), docs/spikes/*, spike/clt-widget/* (frozen spike); renamed docs/codex-app-server.md (reference doc) and THIRD_PARTY_NOTICES.md's path (file moved). Env var QUOTABOARD_STATE_DIR -> AGENT_USAGE_MONITOR_STATE_DIR. Host Info.plist gains CFBundleDisplayName.
- S5 task 2 done: 780205e red=none (mechanical rename); make test 156 OK; swift-test ok; pii-scan exit 0; plutil lint OK; NFR-1 grep clean.
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow (refrozen at 780205e)

- S6 r1 @780205e: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (CI make check success at 780205e, ci-verdict exit 0) -> converged
- Residual NON-BLOCKING: requirement-fidelity#1 PR title/body must cover license + rename and list files keeping the old name; requirement-fidelity#2 PR body must explain the three new allowlist entries. Both are PR text, done by the caller.
- S7: plan doc copied to docs/design/TASK-621-license-and-rename-plan.md with machine paths replaced by `<WORKTREE>`, `<AUTOPILOT>`, `<WORKDIR>`.

## Review items

r1 (@780205e):
- requirement-fidelity#1 NON-BLOCKING: PR #17 title/body predate the license and rename; list files keeping the old name.
- requirement-fidelity#2 NON-BLOCKING: PR body lacks rows for the new allowlist entries (owner noreply, GitHub web-merge committer, `in:identity` owner address).
- verification#1 NON-BLOCKING: CI make check success at 780205e.

## Notes

- PR #17 already exists (previous build, plan doc docs/design/TASK-621-pii-scan-plan.md); this build adds one commit to it.

## Task list

Global Constraints: copyright line exactly as the latest user requirement (progress log); THIRD_PARTY_NOTICES.md unchanged.

### Task 1: MIT license

- Files: LICENSE, README.md.
- Tests: none (docs only); `make pii-scan` exit 0.
- Checks: `make pii-scan`.
- Commit: `TASK-621: add MIT license`.

### Task 2: rename to Agent Usage Monitor (TASK-622)

- Files: agent_usage_monitor/ (from quotaboard/), bin/agent-usage-monitor, macos/* (plists, widget swift, entitlements, LaunchAgent plist), Makefile, README.md, THIRD_PARTY_NOTICES.md, docs/codex-app-server.md, tests/*.
- Tests: existing suite updated to new names.
- Checks: make test, make swift-test, make pii-scan, plutil -lint, NFR-1 grep.
- Commit: `TASK-622: rename the product to Agent Usage Monitor`.
