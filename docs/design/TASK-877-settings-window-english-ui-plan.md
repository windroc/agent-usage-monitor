Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-877-settings-window-english-ui base_ref=1dc0bb27ae9b8d75f0579f3fa64fd3813a6fa14d review_round=1 input_sha=2008cdca2e42

## Input

(verbatim copy: <INPUT>; input_sha 2008cdca2e42)

## Verify command

`make check` (macOS only: needs xcrun/swiftc; runs on CI). Locally (Linux): `/usr/bin/python3 -m unittest discover -s tests -t .` and `/usr/bin/python3 tests/pii_scan.py`.
CI checks: ["make check"]

## Progress log

- S1: mode=stay, publish=ci (pr.py start), base_ref=156b93b
- decision(scope): the widget's no-data text (`macos/Widget/AgentUsageMonitorWidget.swift:58-59`, README line 57) is widget, not settings window: left as is.
- decision(scope): Python validation messages (`agent_usage_monitor/accounts.py`) are already English; only the docstring naming 保存 changes.
- decision(labels): table headers stay key-style lowercase like `client`/`name`: 目录 → `dir`, 邮箱（可空） → `account (optional)`; buttons and menus in macOS title case.
- decision(process): the user asked to stop before S6 for a preview on the real Mac; this run stops after S5 and its push.
- S5 task 1 done: 97f9474 red=tests.test_host_strings (2 tests)
- stop(user process): stopped before S6 for the user's preview on the real Mac; next step: on approval, resume and run S6 r1 (verification=ci, CI checks ["make check"]).
- deferred(CJK outside scope): macos/Widget/AgentUsageMonitorWidget.swift:58-59 (no-data text), README.md:57 (same text), README.md:63-64 and agent_usage_monitor/alerts.py (alert texts, out of scope)
- mid-run input (user, 2026-10-23): approved the English settings window on the real Mac with the listed wording; proceed to S6 review and a draft PR with CI; alert texts and the widget no-data text stay out of scope. Asked to rebase on main (TASK-873, 1dc0bb2): merged origin/main instead (caller rule: never rebase), no conflicts; targeted tests (61) and pii_scan pass. Review cap 3 (skill's cap).
- base_ref -> 1dc0bb27ae9b8d75f0579f3fa64fd3813a6fa14d (merge-base after merging origin/main)
- decision(publish): pr.py push opened draft PR PR #13
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- S6 r1 @2857b10: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (command=CI make check, ci-verdict.py exit 0) -> converged
- S7: residual NON-BLOCKING items: none (verification#1 is CI evidence only)

## Review items

- r1: verification#1 (NON-BLOCKING): CI at 2857b10 passed: make check (success); ci-verdict.py exit 0; HEAD matched and status empty before the check

## Notes

- No local Swift toolchain (Linux): Swift tests (`macos/Tests/main.swift`, `make swift-test`) run only on CI (`make check`, macos-26).
- Host strings: `macos/Host/SettingsView.swift`, `macos/Host/Settings.swift` (SaveStatus), `macos/Host/main.swift` (window title, errors, menu, settingsHint line 24).
- Plan docs of earlier tasks live in `docs/design/TASK-<n>-<slug>-plan.md`.

## Task list

Global Constraints:
- After the change, no CJK character (U+3000–U+303F, U+4E00–U+9FFF, U+FF00–U+FFEF) in `macos/Host/*.swift` (strings and comments) or in README's `## Settings window` section.
- Strings: panel prompt `Choose`; `Loading…`; `Can't read the account list`; `The file stays as it is. After Start Over with Defaults, Save replaces it with the new list.`; `Start Over with Defaults`; `Add`; `Alert threshold`; `Alert at this usage; the account then counts as unavailable`; `Save`; headers `client`, `dir`, `account (optional)`, `name`; `Choose…`; help `Move Up`, `Move Down`, `Delete`; status `Saving…`, `Saved, refreshing the widget…`, `Saved, but the widget refresh failed (exit <n>)`, `Saved, but the widget refresh failed (timed out or didn't start)`; window title `Agent Usage Monitor Settings`; `Can't run ~/.local/bin/agent-usage-monitor read-accounts (exit <n>); run make install first`; `Save failed (exit <n>); the file is unchanged`; menus `Agent Usage Monitor` › `Quit Agent Usage Monitor`, `File` › `Close Window`, `Edit` › `Undo`, `Redo`, `Cut`, `Copy`, `Paste`, `Select All`; settingsHint `turn them on in System Settings › Notifications › Agent Usage Monitor`.
- Layout: window min width 860 stays; English threshold help is longer than the Chinese but fits the row (about 560 of 820 pt); error lines wrap.
- Out of scope: `agent_usage_monitor/alerts.py` alert texts and their tests/README lines; the widget.

### Task 1: Settings window strings in English

- Files: `macos/Host/SettingsView.swift`, `macos/Host/Settings.swift`, `macos/Host/main.swift`, `macos/Tests/main.swift` (SaveStatus expectations), `agent_usage_monitor/accounts.py` (docstring), `README.md` (`## Settings window`), new `tests/test_host_strings.py`.
- Consumes / Produces: none across tasks.
- Tests first: `tests/test_host_strings.py`: no CJK in any `macos/Host/*.swift`; none in README's `## Settings window` section. Red before the change. Update `macos/Tests/main.swift` SaveStatus expected texts (runs on CI).
- Checks: `/usr/bin/python3 -m unittest tests.test_host_strings tests.test_readme tests.test_accounts tests.test_cli`; `/usr/bin/python3 tests/pii_scan.py`.
- Commit: `TASK-877: settings window in English`
