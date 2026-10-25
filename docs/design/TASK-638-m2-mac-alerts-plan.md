Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-638-m2-mac base_ref=f0f6ba1a43c8e273bfd9134d32140eac8a511ac4 review_round=2 input_sha=5405c31f2907

## Input

# Requirement: TASK-638 M2 Mac 提醒（快满、重新可用）

Repo: windroc/agent-usage-monitor. Precedence: the user's requirements below > the user's instructions > the PRD; within each, newer > older.

## The user's requirements (newest first, highest precedence)

1. (2026-10-17, latest) Step 1 passed on the host-app path: send notifications from the host app with `UNUserNotificationCenter` (PRD FR-8), not osascript, so they show the Agent Usage Monitor name and icon. FR-8 replaces FR-5. Do not build the osascript sender. Keep the `AUM-ALERT ` stdout line protocol; without `--emit-alerts`, `collect`'s stdout stays empty (M1 FR-21). Step 2 (FR-1 to FR-4) and FR-9 are unchanged. FR-6 (osascript failure → not recorded) has no osascript to fail under FR-8: FR-8's rule wins (`collect` records `notified` as soon as it writes the line; a host send failure is only logged to `~/Library/Logs/agent-usage-monitor.log`).
2. README (FR-7) must contain:
   - Upgrade: after `git pull`, run `make -C ~/.local/share/agent-usage-monitor install` again (the existing README already has an "After `git pull`" line; extend, don't duplicate).
   - First-time notification authorization: on the first alert macOS asks to allow notifications from Agent Usage Monitor; click Allow (or enable it later in System Settings › Notifications › Agent Usage Monitor). This second Allow prompt for the production bundle ID `com.windroc.agent-usage-monitor` is unavoidable even after the spike: the spike used another bundle ID.
   - Step 1 conclusion (spike facts, 2026-10-17, macOS 26.7.1):
     - osascript path: a test LaunchAgent ran the installed host app, which ran `/bin/zsh -l -c` → a `/usr/bin/python3` script → the FR-5 `osascript` command; exit 0; `usernoted` delivered it as app `com.apple.ScriptEditor2`; the user saw it, title `Agent Usage Monitor`, but with Script Editor's generic script icon; no permission prompt. Works, but rejected in favor of the host-app path for the app's own name and icon.
     - host-app path (chosen): an ad-hoc-signed test app with the same name and icon but bundle ID `com.windroc.agent-usage-monitor.spike-un`, built outside `~/Applications` and started by a temporary LaunchAgent, called `UNUserNotificationCenter` `requestAuthorization`: macOS showed an Allow prompt for Agent Usage Monitor; the user allowed it; `granted=true`, the notification was added without error and shown with Agent Usage Monitor's name and icon; alert style banner.
   - Readers who ran that spike can remove the stale spike entry (a second "Agent Usage Monitor") in System Settings › Notifications.
   Keep README edits tight, in the README's existing style.

## The user's instructions

What to build: when an account's window reaches `threshold` (default 90, the existing M1 global `threshold`, configurable in accounts.json), the Mac shows a notification `<client> · <account> <5h|7d> 已到 <x>%，<重置时间> 重置`; when a previously full account becomes available again, `<client> · <account> 现在可用`. The same event notifies only once. An account without `account` uses `name` in place of `<account>`.

Order: Step 2: FR-1 to FR-4, FR-9 (decide whether to alert, dedupe, `notified` storage). Step 3: FR-7, FR-8 (sending from the host app, README).

Acceptance criteria:
- Every built FR's 「检查」 column in the PRD has a corresponding automated test (FR-8's manual check excluded; its unit-test part included). "发 N 条" in checks means N `AUM-ALERT ` lines emitted (and recorded).
- An account without `account` uses `name` in the notification text.
- NFR-1: no directory path in notification text; no new network requests; pii scan passes (`make pii-scan`) and the `make check` NFR-1 grep list stays empty (no `socket`, `URLSession`, `curl`, etc. in code).
- `make check` and CI pass. Never install into `~/Applications` (no `make install`/`make uninstall`). Never kill system processes. Tests never send a real notification (tests exercise `collect --emit-alerts` output and pure Swift helpers only, never `UNUserNotificationCenter`).

## PRD (context; FR/NFR ids refer to it)

Goals: near-full text `<账号> <5h|7d> 已到 <x>%，<重置时间> 重置`, `<账号>` = `<client> · <account>` (e.g. `claude · you@example.com`), `name` when no `account`. Available-again `<账号> 现在可用`. Snapshot only; never probe Claude for alerts. Not in scope: phone alerts, per-account/per-window thresholds, alert toggles/quiet hours/sound, widget changes. A widget-click-triggered `collect` (through the host) also evaluates and sends alerts. Mac asleep → no collect; the first `collect` after wake alerts by current state. Assumption: the M1 snapshot format can add fields without changing `schema`.

Functional requirements (ID | requirement | check):
- FR-1 提醒判定: only `collect` evaluates and emits alerts; evaluation, emitting and recording happen inside the same `snapshot.lock` exclusive lock in which M1 writes the snapshot: re-read `notified`, skip existing keys; judge by current state only, not by comparison with the previous snapshot; on first run after upgrade a window already over threshold alerts normally. | Check: two `collect` runs at once, condition met → only 1 alert.
- FR-2: near-full: a row's window `used_percent` (as processed by M1) ≥ threshold, and `notified` has no key with the same name, window, kind `full`, and `resets_at` within 10 minutes (both `null` also matches) → record key `{name, window, kind: "full", resets_at}` and send `<账号> <5h|7d> 已到 <x>%，<重置时间> 重置` (`resets_at` null → `重置时间未知`). | Check: snapshot 5h 92%, threshold 90 → 1 alert containing `5h 已到 92%`; 85% → none; first `collect` after upgrade already at 92% → 1; next probe `resets_at` 60 s later → no re-send.
- FR-3: available again: a `full` key has "ended" when its `resets_at` has passed, or `resets_at` is null and that window is now < threshold; an account now `available: true` (M1 FR-16) with ≥1 ended `full` key → send one `<账号> 现在可用` and delete all that account's ended `full` keys; snapshot only, no probing. | Check: claude-max has 5h `full` (17:00) and 7d `full` (Friday 09:00); at 17:01 still unavailable due to 7d → none; Friday 09:01 available → exactly 1, both keys deleted, fake `claude` not called; run again → none; 5h `full` with `resets_at` null, 5h dropped to 40%, account available → 1.
- FR-9 去重: after sending, record the key in the snapshot's top-level `notified` (a list, each item with `sent_at`); delete keys whose `sent_at` is older than 7 days. | Check: 3 consecutive `collect` with near-full condition always met → only 1; `notified` holds no key with `sent_at` older than 7 days.
- FR-4: adding `notified` to the snapshot does not change `schema`; M1's snapshot fixture gains this field. | Check: test compares the fixture's key set; `schema` still 1.
- FR-7 文档: README covers upgrade steps, first-time notification authorization, Step 1 conclusion. | Check: README has these three.
- FR-8 发送 (replaces FR-5): the host app runs `collect --emit-alerts` (without that flag `collect`'s stdout stays empty, M1 FR-21); `collect` writes this run's alerts to stdout, one per line, as `AUM-ALERT ` followed by JSON `{"text": …}` (the prefix separates them from login-shell output); the host posts each with `UNUserNotificationCenter` and exits only after all are handed to the system; `collect` records `notified` once written; a host send failure only writes to `~/Library/Logs/agent-usage-monitor.log`. | Check: manual (done in Step 1); unit: `collect --emit-alerts` stdout lines are each `AUM-ALERT ` + valid JSON with `text`, and their keys are in `notified`; without the flag → stdout empty.
- FR-5, FR-6: not built (replaced by FR-8, see user requirement 1).
- NFR-1 安全: no directory paths in alert text; no new network requests. | Check: unit test triggers both alert kinds, text contains no `/`-starting path; the `make check` NFR-1 grep stays empty.

## Conventions and git rules

- Follow the target repo's conventions: code style of `agent_usage_monitor/`, `tests/`, `macos/`; Python 3.9 stdlib only via `/usr/bin/python3`; Swift built with `xcrun swiftc` and the Command Line Tools only (see Makefile); README style; commit messages like existing history (`TASK-638: …`). The repo has no CLAUDE.md/AGENTS.md; read README › Development and the Makefile.
- Default branch `main`. Never push to or touch any branch other than `TASK-638-m2-mac`; force-push only with `--force-with-lease`; never merge.
- No mutation testing, whatever a spec, plan or reviewer asks: never modify the source to see what happens (no manual or tool-driven mutation testing, not even briefly or in a throwaway copy that is then run); never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call or use a fake executable on PATH, leaving the code under test unmodified. Every brief to a sub-agent (producer, reviewer) carries this rule.
- Never write user config (`~/.claude*`, `~/.claude.json`, dotfiles, `~/.config/agent-usage-monitor`), never run `make install`/`make uninstall`, never install into `~/Applications`, never `launchctl` the real agent, never kill system processes, never send a real notification.

The plan doc stays where autopilot puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

Work only in `<WORKTREE>` on branch `TASK-638-m2-mac`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <WORKTREE> push -u origin TASK-638-m2-mac`.

Verify: `make check`
CI checks: ["make check"]

## Progress log

- S1: mode=stay branch=TASK-638-m2-mac publish=ci
- decision(no-flag): without --emit-alerts collect evaluates nothing and keeps notified, so a manual collect never swallows the host's alerts
- decision(reset-format): reset time local HH:MM today, else M月D日 HH:MM (no `/`, NFR-1)
- decision(fr6): FR-5/FR-6 not built; FR-8 records notified on write (user requirement 1)
- S5 task 1 done: de42269 red=test_alerts (ImportError: no alerts module), test_snapshot_format (notified key)
- S5 task 2 done: 762e080 red=EmitAlertsTest x3 (usage error exit 2)
- S5 task 3 done: aa9d670 red=swift-test (cannot find alertTexts)
- S5 task 4 done: 219927f red=none (docs)
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- S6 r1 @219927f: correctness=PASS requirement-fidelity=FAIL doc=PASS verification=PASS (CI make check success, ci-verdict exit 0) -> requirement-fidelity#1 FR-7 has no automated README test; fixing
- decision(auth-options): requestAuthorization([.alert]) without .sound; PRD excludes sound settings
- spike cleanup: removed tmp/spike and tmp/spike-un (workdir only)
- S6 r2 @fe874f9: requirement-fidelity=PASS verification=PASS (CI make check success, ci-verdict exit 0) -> converged
- residual NON-BLOCKING: correctness#1, correctness#2, correctness#3, doc#1

## Review items

### r1
- correctness#1 NON-BLOCKING: alerts.py: 7-day prune runs before the FR-3 ended-key check; a full key can be pruned before its available-again alert fires (sleep across reset and 7 d).
- correctness#2 NON-BLOCKING: macos/Host/Alerts.swift:12 split(separator: "\n") does not split CRLF; a CRLF login-shell line merges with the next alert line, which is dropped. Fix: split(whereSeparator: \.isNewline).
- correctness#3 NON-BLOCKING: store.py: notified replaced before AUM-ALERT lines print; a kill between them leaves recorded but unprinted alerts.
- requirement-fidelity#1 BLOCKING: FR-7 has no automated test that README has upgrade, first-time authorization, Step 1 conclusion.
- requirement-fidelity#2 NON-BLOCKING: requestAuthorization options [.alert] vs plan [.alert, .sound]; log decision.
- requirement-fidelity#3 NON-BLOCKING: spike plists and logs still in workdir tmp; remove.
- doc#1 NON-BLOCKING: README `make swift-test` comment omits the alert-line parser.

### r2
- requirement-fidelity: prior #1-#3 resolved; no new items.
- verification: CI make check passed at fe874f9.

## Notes

- store.write is the one snapshot writer, under snapshot.lock; alerts evaluated there after derive.recompute
- tests: tests/helpers.py Env runs bin/agent-usage-monitor with fake codex/claude on PATH
- swift-test compiles macos/Widget/Snapshot.swift + macos/Tests/main.swift


## Task list

### Header

Global Constraints:
- Python 3.9 stdlib, `/usr/bin/python3`; Swift via `xcrun swiftc` (Command Line Tools only).
- Alert texts: near-full `<client> · <account|name> <5h|7d> 已到 <x>%，<reset> 重置`; `<reset>` = local `HH:MM` when `resets_at` is on today's local date, else local `M月D日 HH:MM` (no `/`, NFR-1); `resets_at` null → the clause `<reset> 重置` becomes `重置时间未知`. Available-again `<client> · <account|name> 现在可用`.
- Window key in `notified` is the snapshot's window key (`five_hour`, `seven_day`); label map `five_hour`→`5h`, `seven_day`→`7d`.
- Dedupe window 600 s; prune `sent_at` older than 7 × 86400 s.
- Stdout line: `AUM-ALERT ` + `json.dumps({"text": text})` (ASCII-escaped), flushed per line.
- Without `--emit-alerts`: no evaluation, no stdout, `notified` kept as is (sanitized).
- Verify: `make check`; CI check `make check`.

Data shape: snapshot top-level `notified`: list of `{"name": str, "window": "five_hour"|"seven_day", "kind": "full", "resets_at": int|null, "sent_at": int}`. Invalid entries (not dict, wrong types) are dropped on read; a non-list `notified` becomes `[]`. Always present in a written snapshot (`[]` by default); `schema` stays 1.

### Task 1: alert evaluation and `notified` storage (FR-1 to FR-4, FR-9, NFR-1 text)

Files: new `agent_usage_monitor/alerts.py`; `agent_usage_monitor/store.py`; new `tests/test_alerts.py`; `tests/test_store.py`; `tests/test_cli.py` (`test_snapshot_format` key set gains `notified`); `macos/Tests/main.swift` (valid fixture gains `"notified": [...]`, still loads).

Produces:
- `alerts.keys(value) -> list` sanitized `notified`.
- `alerts.evaluate(snap, threshold, now) -> [text]`: mutates `snap["notified"]`: prune >7 d; per row (snapshot order): available-again (FR-3) then near-full (FR-2) per window in `derive.WINDOWS` order.
- `store.write(directory, accounts, threshold, updates, failed=(), now=None, emit=None)`: always sets `snap["notified"] = alerts.keys(...)`; when `emit` is given, evaluates after `derive.recompute`, writes the snapshot, then calls `emit(text)` for each, all inside the lock.

Tests first (store-level, fixed `now`): 5h 92% thr 90 → 1 text containing `5h 已到 92%` and key recorded with `sent_at`; 85% → none; prior snapshot without `notified` (upgrade) at 92% → 1; second write with `resets_at` +60 s → none, +11 min → 1; both `resets_at` null dedupe; 3 writes → 1; FR-3 claude-max scenario (5h key 17:00, 7d key Friday 09:00; 17:01 still unavailable → none; Friday 09:01 → exactly 1 `现在可用`, both keys gone; again → none); null-`resets_at` key + window at 40% + available → 1; prune: key with `sent_at` 8 d old gone, 6 d kept; `account` set → `claude · you@example.com`, unset → `claude · <name>`; name containing `"` kept verbatim; no text matches `(^|\s)/\S`; reset clock formats (today, other day, null); garbage `notified` (`"x"`, `[1, {"name": 2}]`) → sanitized, no crash; `emit=None` → no evaluation, `notified` unchanged; key set of snapshot includes `notified`, `schema` 1.

Checks: `/usr/bin/python3 -m unittest tests.test_alerts tests.test_store tests.test_cli`; `make swift-test`.

Commit: `TASK-638: 快满和重新可用提醒的判定与 notified 去重`

### Task 2: `collect --emit-alerts` (FR-1 lock, FR-8 Python side)

Files: `agent_usage_monitor/cli.py`; `tests/test_cli.py`.

Consumes: `store.write(..., emit=...)`.

Tests first (subprocess, fake codex/claude): `collect --emit-alerts` with a codex account at 92% → stdout exactly one line `AUM-ALERT ` + JSON with `text`, key in `notified`; second run → stdout empty; without flag → stdout empty and `notified` empty; two `collect --emit-alerts` started together → exactly 1 alert line total; FR-3 via collect with Claude account whose probe is skipped (fresh `fetched_at`) → `现在可用` emitted and fake `claude` not called; `--help` / usage errors still exit 2.

Checks: `/usr/bin/python3 -m unittest tests.test_cli`.

Commit: `TASK-638: collect --emit-alerts 把提醒写到 stdout`

### Task 3: host app posts alerts with UNUserNotificationCenter (FR-8)

Files: new `macos/Host/Alerts.swift` (Foundation only: `alertTexts(_ output: Data) -> [String]`, keeps lines starting `AUM-ALERT ` whose rest is JSON with a string `text`, skips the rest); `macos/Host/main.swift`; `macos/Tests/main.swift`; `Makefile` (`app` builds host from both files; `swift-test` adds `macos/Host/Alerts.swift`).

Behavior: host runs `collect --emit-alerts`, drains stdout on a background thread; after collect exits (wait ≤ 2 s more for EOF), parses alerts; none → existing flow; else `requestAuthorization([.alert, .sound])`, then `add` each request (title `Agent Usage Monitor`, body text, trigger nil), waits until every add completion returned (cap 60 s, then logs and continues), then the existing reload/exit flow. Delegate `willPresent` → `[.banner, .list]`. Failures (not granted, add error, cap) append one line to `~/Library/Logs/agent-usage-monitor.log`, never retried. Collect timeout path unchanged.

Tests first: swift checks for `alertTexts`: two valid lines among login-shell noise; bad JSON, missing/non-string `text`, prefix without space, empty output → skipped; unicode and `"` text verbatim.

Checks: `make swift-test`; `make app` (build only, no install).

Commit: `TASK-638: host app 用 UNUserNotificationCenter 发提醒`

### Task 4: README (FR-7)

Files: `README.md`.

Content per input requirement 2: How it works diagram gains alerts; a short "Alerts" section (texts, threshold, once per event, `notified`); upgrade (extend the existing "After `git pull`" line); first Allow prompt for `com.windroc.agent-usage-monitor`; Spike conclusions gains TASK-638 (osascript works but Script Editor icon; host-app path chosen, facts); stale spike entry removable; status line M2; uninstall note unchanged.

Checks: `make pii-scan`.

Commit: `TASK-638: README 写提醒、升级、通知授权和 Step 1 结论`
