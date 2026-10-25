Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-640-m2 base_ref=2a68a411b29557b8f25dd4bcb44ce54de2eee133 review_round=1 input_sha=165bec35ad18

## Input

## Requirement (TASK-640: M2 提醒没交给系统时不记成已提醒)

Repo: windroc/agent-usage-monitor. Parent TASK-562 (M2 PRD FR-8); previous work TASK-638 (PR #5).

### Problem (2026-10-17, measured on the user's Mac)
1. First notification: macOS showed the "allow notifications" request (usernoted log 18:07:42 presented). The user didn't notice; the host app waited the full 60 s and exited; the request was withdrawn at 18:08:50. Log: `1 alert(s) not handed to macOS within 60 s`.
2. macOS then treated it as "not allowed" and no longer asks. Next run: `notifications not allowed: ... UNErrorDomain Code=1 ...; 1 alert(s) dropped`.
3. Both runs' alerts were already recorded in `notified` when `collect --emit-alerts` wrote them out, so they are never re-sent. Only after the user enabled notifications manually in System Settings and the commander cleared `notified` were they sent.

### What to build
- An alert not actually handed to macOS does not count as sent; the next `collect` emits it again. "Not handed to the system" includes: not authorized, timeout waiting for permission, `add` error, timeout. This changes FR-8's original "record on write-out" rule; the user agreed 2026-10-17.
  - One approach: the host tells `collect` which alerts were delivered successfully, and only those are recorded, done under the same `snapshot.lock`. Choose the concrete design yourself and write it in the plan.
  - Requirements: the same event alerts at most once, never duplicated; `collect` without `--emit-alerts` keeps stdout empty.
- Time waiting for the user to click "Allow" does not count toward the send timeout, or the wait is relaxed. Either way the host must never hang: the LaunchAgent runs every 5 minutes, and the host must exit before the next run.
- When not authorized, log one line telling the user to enable it in 「系统设置 › 通知 › Agent Usage Monitor」 (System Settings › Notifications › Agent Usage Monitor). README gives the same instruction.

### Acceptance criteria
- Test: when the host reports not delivered, `notified` lacks the key; the next `collect` outputs the same alert again.
- Test: after successful delivery, two more consecutive runs output nothing.
- README states: if no notification arrives, enable it in System Settings.
- `make check` and CI pass. Do not install into `~/Applications`, do not kill system processes, do not change the user's notification settings.

### Conventions and git rules
- Write code, docs and commits in the target repo's conventions (its `CLAUDE.md` / `AGENTS.md`). Default branch: `main`.
- No mutation testing, for you and every producer/reviewer sub-agent (put this rule in every brief): never modify the source to see what happens, no manual or tool-driven mutation testing (mutmut etc.), not even briefly or in a throwaway copy; never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call, leaving the code under test unmodified.
- Push only branch `TASK-640-m2`; force-push only with `--force-with-lease`. Never merge into or touch any other branch.

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
- fork(record-protocol): options=[confirm-after, hold-lock, rollback]; criteria=[no lost alert on host crash, no duplicate notification, host always exits before next run, smallest change]; prior=confirm-after
- decision(record-protocol): chose confirm-after over hold-lock, rollback - singleton host means no duplicate notification; rollback loses alerts on host kill; hold-lock blocks snapshot.lock for minutes and fights collectTimeout; dissent: none; tally=confirm-after:3
- omitted(record-protocol): lease (pending keys with expiry so two concurrent collect --emit-alerts emit once); only a manual terminal run races the singleton host
- decision(same-lock): "under the same snapshot.lock" read as the same lock file: collect and record-alerts each hold snapshot.lock
- decision(timeouts): Allow wait 180 s before grant, adds 20 s after grant, record-alerts 20 s; with collect 40+2+2 and exit 2 the host ends by ~268 s < 300 s LaunchAgent interval
- decision(prune): only collect prunes 7-day-old keys, keeping any key an emitted available-again alert would remove; record-alerts never prunes, so an undelivered available-again alert keeps its keys
- S4: 2 tasks
- S5 task 1 done: 91ee726 red=test_alerts + EmitAlertsTest (24: no store.record / record-alerts usage error); swift-test parser change written with its check
- S5 task 2 done: d7ae5c0 red=test_readme.test_no_notification_turn_on
- decision(publish): pr.py opened draft PR PR #6
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- S6 r1 @d7ae5c0: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (CI make check success, ci-verdict exit 0) -> converged
- residual NON-BLOCKING: correctness#1, requirement-fidelity#1, requirement-fidelity#2, doc#1

## Review items

### r1
- correctness#1 NON-BLOCKING: macos/Host/main.swift (finished): the pendingClick re-run starts a second full cycle after record, so the ~268 s bound covers one cycle only; a widget click during the Allow wait can push the host to ~536 s, past the next 300 s run (launchd skips it). Fix: skip the re-run once elapsed time plus one cycle would pass 300 s, or when the first cycle hit authTimeout.
- requirement-fidelity#1 NON-BLOCKING: two at-least-once windows send an alert twice with no recorded decision: record-alerts fails or times out after macOS has the alert; center.add succeeds after the 20 s addTimeout. Log a decision accepting them.
- requirement-fidelity#2 NON-BLOCKING: decision(timeouts) leaves out the pendingClick re-run (same case as correctness#1).
- doc#1 NON-BLOCKING: README Alerts describes the line as `AUM-ALERT {"text": …}`; it now also carries `add` and `remove`.
- verification: CI make check passed at d7ae5c0.

## Notes

- store.write is the one snapshot writer, under snapshot.lock; alerts.evaluate runs inside it after derive.recompute
- tests/helpers.py Env runs bin/agent-usage-monitor with fake codex/claude on PATH
- host: macos/Host/main.swift (deliver, finished); line parser macos/Host/Alerts.swift; swift-test = Snapshot.swift + Alerts.swift + macos/Tests/main.swift
- repo has no CLAUDE.md/AGENTS.md; commit style `TASK-640: ...`; design docs in docs/design/


## Task list

### Header

Global Constraints:
- Python 3.9 stdlib via `/usr/bin/python3`; Swift via `xcrun swiftc` (Command Line Tools). Commits `TASK-640: …`.
- Protocol (confirm-after): `collect --emit-alerts` prints each alert as `AUM-ALERT ` + `json.dumps({"text": str, "add": [key], "remove": [key]})` and records none of them. The host hands alerts to macOS, then runs `$HOME/.local/bin/agent-usage-monitor record-alerts` (no login shell) with the delivered lines, verbatim, on stdin. `record-alerts` takes `snapshot.lock`, re-reads the snapshot, removes each `remove` key (dict equality), appends each valid `add` key unless one with the same name, window, kind and same reset (600 s, both null) exists, writes atomically; prints nothing on stdout; skips unparsable lines with a stderr warning; missing/unreadable snapshot: warning, nothing written.
- Prune (7 d) only in `collect`, never dropping a key in this run's `remove` lists.
- Without `--emit-alerts`: unchanged (no evaluation, stdout empty, notified kept).
- Host timeouts: Allow wait `authTimeout` 180 s (before grant only), `addTimeout` 20 s after grant, `recordTimeout` 20 s. A late grant after the Allow timeout posts nothing.
- Not allowed / no answer: one log line ending `turn them on in 系统设置 › 通知 › Agent Usage Monitor (System Settings › Notifications › Agent Usage Monitor)`.
- Never send a real notification in tests, never install, never kill system processes, no mutation testing.

Data shape: `notified` unchanged (list of `{name, window, kind: "full", resets_at, sent_at}`). An alert: `{"text": str, "add": [key], "remove": [key]}` (near-full: add one key; available-again: remove the ended keys).

### Task 1: record only alerts handed to macOS
- Files: agent_usage_monitor/alerts.py, store.py, cli.py; macos/Host/Alerts.swift, macos/Host/main.swift; tests/test_alerts.py, tests/test_cli.py, tests/test_store.py if touched; macos/Tests/main.swift.
- Produces: `alerts.evaluate(snap, threshold, now) -> [alert]` (snap["notified"] only pruned); `alerts.apply(notified, alerts) -> notified`; `store.record(directory, alerts) -> [warning]`; CLI `record-alerts`; Swift `alerts(_ output: Data) -> [AlertLine]` with `AlertLine{text, line}`.
- Tests first: not delivered → notified lacks key, next collect emits same alert; delivered (record-alerts) → two more collects emit nothing; undelivered available-again keeps keys and re-emits; two concurrent collects + records → one key; record-alerts stdout empty, garbage skipped, dedupe; swift alerts parse keeps raw line.
- Checks: `make test`, `make swift-test`.
- Commit: `TASK-640: record an alert only once the host hands it to macOS`

### Task 2: README
- Files: README.md, tests/test_readme.py.
- README Alerts: recorded after the host reports delivery; undelivered retried next run; Allow wait 3 min; if no notification arrives, turn on in System Settings › Notifications › Agent Usage Monitor. Development: `record-alerts` line.
- Tests first: test_readme asserts the "no notification" instruction.
- Checks: `make test`.
- Commit: `TASK-640: README: alerts not handed to macOS are retried; where to turn notifications on`
