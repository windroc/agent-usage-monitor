Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-638-m2-mac base_ref=f8103a1134a63b567f98633d072655c8fc981a7c review_round=1 input_sha=70b9b70ab82e

## Input

# Requirement: TASK-638 PR #5 gate fixes (M2 Mac alerts)

Repo: windroc/agent-usage-monitor, branch `TASK-638-m2-mac` (PR #5, already built: `agent_usage_monitor/alerts.py`, `store.py`, `cli.py --emit-alerts`, `macos/Host/main.swift`, `macos/Host/Alerts.swift`, README Alerts section; earlier plan doc `docs/design/TASK-638-m2-mac-alerts-plan.md`).

## The user's requirements (2026-10-17, PR gate; highest precedence)

1. correctness#1: in `agent_usage_monitor/alerts.py`, run the FR-3 (available-again) check on the unpruned `notified` list, then prune entries whose `sent_at` is older than 7 days. Add a test for the sleep-across-reset-and-7-days case: a 7d `full` key with `sent_at` S and `resets_at` R = S + 6 d; the Mac sleeps from before R until after S + 7 d; the first collect after waking, with the account available, sends exactly one `现在可用` and leaves no key older than 7 days.
2. correctness#2: in `macos/Host/Alerts.swift`, split lines with `split(whereSeparator: \.isNewline)` (Swift treats "\r\n" as one Character, so `split(separator: "\n")` misses CRLF). Add a `make swift-test` case with a CRLF-terminated login-shell line right before an `AUM-ALERT` line; that alert must be parsed.
3. doc#1: README `make swift-test` comment: say it is the widget display model and alert-line parser self-test.
4. README Alerts section: remove the unverified claim that the stale spike entry can be deleted in System Settings › Notifications. Say only that a second Agent Usage Monitor entry may remain there from testing and can be left switched off. Keep `tests/test_readme.py` passing.
- Leave correctness#3 (notified written before the AUM-ALERT lines print) as is: the window is tiny and the PRD records on write.

Context (unchanged requirements): FR-3 — a `full` key has "ended" when its `resets_at` has passed, or `resets_at` is null and that window is now < threshold; an account now `available: true` with ≥1 ended `full` key → one `<账号> 现在可用`, and all that account's ended `full` keys are deleted. FR-9 — keys whose `sent_at` is older than 7 days are deleted; check: `notified` holds no key with `sent_at` older than 7 days.

## Conventions and git rules

- Follow the target repo's conventions (code style of `agent_usage_monitor/`, `tests/`, `macos/`; Python 3.9 stdlib, `/usr/bin/python3`; Swift via `xcrun swiftc`; README style; commit messages `TASK-638: …`). No CLAUDE.md/AGENTS.md; see README › Development and the Makefile.
- Default branch `main`. Never push to or touch any branch other than `TASK-638-m2-mac`; force-push only with `--force-with-lease`; never merge.
- No mutation testing, whatever a spec, plan or reviewer asks: never modify the source to see what happens (no manual or tool-driven mutation testing, not even briefly or in a throwaway copy that is then run); never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call or use a fake executable on PATH, leaving the code under test unmodified. Every brief to a sub-agent (producer, reviewer) carries this rule.
- Never write user config, never run `make install`/`make uninstall`, never install into `~/Applications`, never `launchctl`, never kill system processes, never send a real notification.

The plan doc stays where autopilot puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

Work only in `<WORKTREE>` on branch `TASK-638-m2-mac`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <WORKTREE> push -u origin TASK-638-m2-mac`.

Verify: `make check`
CI checks: ["make check"]

## Progress log

- S1: mode=stay branch=TASK-638-m2-mac publish=ci; PR PR #5 (decision: continue it)
- S5 task 1 done: 25c248e red=test_available_again_after_sleep_past_7_days
- S5 task 2 done: 0a0f68b red=alerts_crlf (got [])
- S5 task 3 done: 5727d54 red=none (docs)
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- S6 r1 @5727d54: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (CI make check success, ci-verdict exit 0) -> converged
- decision(prune-last): prune after the whole evaluation, so a near-full key older than 7 days still dedupes in that run and re-alerts one run (5 min) later; simpler than pruning between FR-3 and FR-2
- residual NON-BLOCKING: requirement-fidelity#1

## Review items

### r1
- requirement-fidelity#1 NON-BLOCKING: alerts.py:44,63-71: pruning at the end lets FR-2 dedupe see keys older than 7 days; a null-resets_at key 8 d old with the window still full re-alerts one run later instead of this run.

## Notes

- alerts.evaluate in agent_usage_monitor/alerts.py; tests in tests/test_alerts.py (store-level, fixed NOW)
- swift-test builds macos/Widget/Snapshot.swift + macos/Host/Alerts.swift + macos/Tests/main.swift
- README Alerts section is checked by tests/test_readme.py

## Task list

### Header

Global Constraints: PR to update: #5. `KEEP = 7 * 86400`. FR-3 runs on the unpruned `notified`; the 7-day prune runs after it. correctness#3 untouched.

### Task 1: FR-3 before the 7-day prune (correctness#1)

Files: `agent_usage_monitor/alerts.py`, `tests/test_alerts.py`.

Tests first: 7d key `sent_at` S, `resets_at` S + 6 d, account otherwise available; first write at S + 7 d + 1 h → exactly `["claude · you@example.com 现在可用"]`, `notified` empty, no key older than 7 d; existing prune test still passes.

Checks: `/usr/bin/python3 -m unittest discover -s <worktree>/tests -t <worktree> -p test_alerts.py`.

Commit: `TASK-638: 先判定重新可用再删 7 天前的 notified`

### Task 2: CRLF in host output (correctness#2)

Files: `macos/Host/Alerts.swift`, `macos/Tests/main.swift`.

Tests first: `alertTexts(Data("motd\r\nAUM-ALERT {\"text\": \"x\"}\r\n".utf8)) == ["x"]`.

Checks: `make -C <worktree> swift-test`.

Commit: `TASK-638: host 解析提醒时也按 CRLF 分行`

### Task 3: README fixes (doc#1, stale spike entry)

Files: `README.md`.

Content: `make swift-test` comment → widget display model and alert-line parser self-test; Alerts: replace "is stale and can be removed" with: a second Agent Usage Monitor entry may remain there from testing and can be left switched off.

Checks: `/usr/bin/python3 -m unittest discover -s <worktree>/tests -t <worktree> -p test_readme.py`; `make -C <worktree> pii-scan`.

Commit: `TASK-638: README 改 swift-test 说明和 spike 旧条目`
