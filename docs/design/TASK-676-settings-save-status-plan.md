Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-676-widget base_ref=1d02dcedaf2de841de8a4f431ea1d63ccdd07e14 review_round=1 input_sha=abbc8bc8756f

# Plan: TASK-676 settings window status after save

## Input

Verbatim in <WORKDIR>/tmp/input.md (input_sha abbc8bc8756f). Summary: after 保存 the window shows 「已保存，正在刷新 widget」 (macos/Host/main.swift:317) forever. Clear it when the post-save `refresh()` ends (success: clear, or brief 「已刷新」 then clear, choice in this doc); on failure or timeout show a short failure message; an edit to the table after the save clears the status too. Tests (swift-test, or a small testable function): save ok → 正在刷新 → refresh ends → empty; refresh fails → failure message. `make check` and CI pass; no install into ~/Applications, no killing system processes. No mutation testing.

## Verify

Verify command: `make check`
CI checks: ["make check"]

## Progress log

- S1 done: mode=stay, branch TASK-676-widget, base_ref 1d02dce.
- decision(success-text): on success clear the line at once, no 「已刷新」 flash: no timer and no extra state; the line vanishing is the signal, and a failure stays on screen.
- decision(which-collect): the save's refresh is the first collect that starts after write-accounts succeeds. A collect already running when the save lands (the 300 s timer's, or an earlier save's) read the old file: its end leaves the line alone, and the pending rerun is the save's. A newer save in flight or waiting also wins over an older collect's end.
- decision(dropped-rerun): `finished()` drops a pending rerun after a timed-out collect (`again = pendingClick && !timedOut`); a save waiting on that rerun then shows the timeout failure instead of 正在刷新 forever. The rerun policy itself is unchanged.
- decision(edit-detection): the view's `.onChange(of: model.draft)`, `draft` = the JSON write-accounts would get (rows' fields and original, threshold; not the row ids or problems), so showing problems or clearing them is no edit. A failure that lands after an edit still shows: the widget is stale either way.
- S5 task 1 done: b1c9517 red=swift-test build failed (SaveStatus missing, 12 errors); swift-test ok, make app ok (no warnings), pii-scan ok
- S5 done, pushed b1c9517.
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow

- S6 r1 pinned @b1c9517; PR PR #11 (draft); CI peek: PENDING
- S6 r1 @b1c9517: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (CI check make check, success) -> converged
- residual NON-BLOCKING: correctness#1 (a failed newer save drops an older written save's wait), correctness#2 (an edit during 正在保存… is overwritten by 正在刷新), doc#1 (README settings section could mention the status line)

## Review items

- S6 r1:
  - correctness#1 NON-BLOCKING: macos/Host/Settings.swift:72 saveEnded(written: false) sets waiting=false, which drops an earlier save that is still waiting. Case: S1 is written while the timer collect C0 runs (waiting=true, pendingClick), then S2's write fails, so waiting becomes false. C0 ends and rerun C1 starts with collecting=false, so C1's failure never shows and the line stays empty. Fix: use `waiting = waiting || written`, or log this as intended in decision(which-collect).
  - correctness#2 NON-BLOCKING: macos/Host/Settings.swift:71 an edit during 正在保存… is undone by saveEnded. Case: click 保存, edit a field before write-accounts returns, so edited() clears the line. saveEnded(true) then sets 「已保存，正在刷新 widget」 although the table no longer matches what was saved. Fix: track an edit made while saving and skip the 正在刷新 text, or record this choice in decision(edit-detection).
  - doc#1 NON-BLOCKING: README.md:94 Settings window section says 保存 "runs `collect` at once" but not that the status line clears after the refresh or shows a failure message. Optional one-clause addition.

## Notes

- swift-test builds Snapshot.swift, Alerts.swift, Settings.swift and macos/Tests/main.swift only; SettingsView.swift (SwiftUI) and main.swift are not under test, so the logic goes in Settings.swift (Foundation only).
- `cli()` passes nil for a run over the timeout or a failed start; collect exits 0, 2 (accounts error) or 143 (SIGTERM).
- `make check` = hooks, pii-scan, Python tests, swift-test, app build, NFR-1 grep, plist lint, codesign checks. `make app` builds into build/, no install.
- Design docs live in docs/design/ as `TASK-<n>-<slug>-plan.md`.

## Task list

Global constraints: texts 「正在保存…」, 「已保存，正在刷新 widget」, failure 「已保存，但刷新 widget 失败（exit <n>）」 and, for a timeout or a collect that did not start, 「已保存，但刷新 widget 失败（超时或没能启动）」. Commit messages in the repo's style (`TASK-676: …`). Data shape: `struct SaveStatus` in macos/Host/Settings.swift, held by `SettingsModel.save`; it replaces `SettingsModel.status` and `SettingsModel.saving`.

### Task 1: SaveStatus drives the status line from 保存 to the end of its collect

- Files: macos/Host/Settings.swift, macos/Host/SettingsView.swift, macos/Host/main.swift, macos/Tests/main.swift.
- Produces: `struct SaveStatus` with `text: String`, `saving: Bool` (read-only), and mutating `saveStarted()`, `saveEnded(written: Bool)`, `collectStarted()`, `collectEnded(_ exit: Int32?)`, `collectDropped()`, `edited()`. `SettingsModel.save: SaveStatus`, `SettingsModel.draft: Data?`. main.swift: `save()` calls saveStarted / saveEnded; `run()` calls collectStarted, its completion collectEnded(status); `finished()` calls collectDropped when no rerun follows. SettingsModel.failed no longer touches the status. View shows `model.save.text`, disables 保存 on `model.save.saving`, calls `model.save.edited()` on a draft change.
- Tests first (macos/Tests/main.swift): save ok → 正在刷新 → collect ends 0 → empty; ends 2 → exit failure; ends nil → timeout failure; write fails → empty; edit after save → empty; a collect that started before the save ends → still 正在刷新, the next one ends → empty; a newer save waiting or writing when an older collect ends → its text kept; dropped rerun → timeout failure; dropped with nothing waiting and a collect with no save → unchanged.
- Checks: `make swift-test`, `make app`, `make pii-scan`.
- Commit: `TASK-676: 设置窗口保存后 刷新完就清掉状态 失败时提示`
