Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-645-host-app-accounts-json base_ref=ef4dc66410b3a0ff2ca856a41b12e6901206ae40 review_round=2 input_sha=a76f14cfca12

# Plan: TASK-645 host app settings window

## Input

Verbatim in <WORKDIR>/tmp/input.md (input_sha a76f14cfca12). Summary: settings window when the user opens the app directly; edits accounts.json's accounts and threshold; widget click unchanged; PRD TASK-644 FR-1..FR-10, NFR-1..NFR-3. Stop after S5 for user preview approval (two PNGs in <WORKDIR>/tmp/) before S6.

## Verify

Verify command: `make check`
CI checks: ["make check"]

## Progress log

- S1 done: mode=stay, branch TASK-645-host-app-accounts-json, base_ref ef4dc66.
- decision(launch-detection): PRD assumption 1 holds; verified by a throwaway probe app in tmp (log below), plus SDK header NSApplication.h:662 (LaunchIsDefaultLaunchKey) and `launchctl print gui/<uid>/com.windroc.agent-usage-monitor` (read-only: job env XPC_SERVICE_NAME=com.windroc.agent-usage-monitor).
  - cold exec (launchd-like): event oapp, LaunchIsDefaultLaunch=1, XPC_SERVICE_NAME inherited (launchd: the job label)
  - cold `open App.app` (Finder/Spotlight/Dock): event oapp, LaunchIsDefaultLaunch=1, XPC_SERVICE_NAME=application.<bundle id>.<n>.<n>
  - cold `open <scheme>://refresh` (widgetURL): application(_:open:) before applicationDidFinishLaunching, LaunchIsDefaultLaunch=0
  - running instance + `open App.app`: applicationShouldHandleReopen (rapp) only; + `open <scheme>://refresh`: application(_:open:) (GURL) only, no reopen
  - so: widget gets `.widgetURL(agent-usage-monitor://refresh)`; host shows settings iff no URL at launch and XPC_SERVICE_NAME starts with `application.` (fails safe: an unknown launcher just refreshes); a reopen while running = user open → settings; a URL while running = widget click → refresh. LaunchServices-vs-launchd by XPC_SERVICE_NAME is observed, not documented: manual check in the PR.
- decision(single-rule-source): Python owns read, validation and write (accounts.py); the host calls new CLI subcommands `read-accounts` / `write-accounts` through the same `/bin/zsh -l -c` as collect, so both see the same XDG_CONFIG_HOME and the same rules. Problem text comes from accounts.py (English, like collect's stderr); window labels Chinese like the widget.
- decision(unknown-fields): read-accounts passes each item's and the top level's original JSON as an opaque `original` string; write-accounts updates the known keys in it (key order kept); `account` empty → key removed.
- decision(settings-stays-open): while the window is open the host refreshes every 300 s, since a launchd run exits on seeing this older host (one host at a time) and the widget and alerts would otherwise stall.
- S5 task 1 done: 1ea9413 red=9 (all SettingsTest, SettingsCliTest); make test 204 OK, pii-scan OK
- S5 task 2 done: 784ea7e red=swift-test build failed on the missing Settings.swift symbols; swift-test ok, make app ok (no warnings), plist lint, pii-scan, NFR-1 grep
- previews: rendered offscreen (NSHostingView + cacheDisplay, tmp/preview/main.swift): tmp/preview-editing.png, tmp/preview-row-error.png, tmp/preview-unreadable.png
- S5 task 3 done: 75cffd4 red=1 (test_settings_window); make test OK, pii-scan OK
- S5 done, pushed 75cffd4. Paused before S6 per the requirement: previews to the user via the caller; resume S6 r1 on the user's approval.
- user requirement (2026-10-17, via commander): previews unreadable on a dark Mac (transparent PNG); re-render light and dark with an opaque background; real window must work in dark mode (system background, semantic colours); size the window to its content with a sensible minimum.
- S5 fix done: d46a2ce red=render showed content clipped at 200 pt after load (window did not follow content); now .background(windowBackgroundColor), .fixedSize(vertical), window.setContentSize(fittingSize), minimum 860 x 200; swift-test ok, make app ok, pii-scan ok
- previews: tmp/preview-{editing,row-error,unreadable}-{light,dark}.png (opaque, corner pixel alpha 1); older transparent ones removed
- user approved the layout ("looks good", via commander): go on to S6 without stopping
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- S6 r1 pinned @d46a2ce; PR PR #9 (draft); CI peek: PENDING
- S6 r1 @d46a2ce: correctness=FAIL requirement-fidelity=PASS doc=PASS verification=PASS (CI check make check, success) -> correctness#1 no main menu, so Cmd+V/C/X/A/Z/W/Q do nothing in the window; fixing
- user requirement (via commander, during r1): remove the 配置文件：<path> line at the top of the window; the FR-9 error may still name the file; fold into the fix after r1; re-render previews
- S6 fix r1: b775cca (pre-fix HEAD d46a2ce): correctness#1 main menu (Quit closes the window, so the close path still records alerts); 配置文件 line and the unused path field removed; previews re-rendered; swift-test, make app, test_accounts/test_cli, pii-scan ok
- S6 r2 pinned @b775cca; re-review: correctness, requirement-fidelity (user change), verification; doc carries PASS
- S6 r2 @b775cca: correctness=PASS requirement-fidelity=PASS doc=PASS (carried from r1) verification=PASS (CI check make check, success) -> converged
- plan doc: Data shape line updated for the removed path field (requirement-fidelity#2)
- residual NON-BLOCKING: correctness#2 (superseded in part by #6), correctness#3, correctness#4, correctness#5, correctness#6, correctness#7, requirement-fidelity#1
- S7: plan doc copied to docs/design/TASK-645-settings-window-plan.md (paths as placeholders, as earlier plan docs)
- decision(close): closing the window drops the Dock icon at once and exits once any running collect/alert delivery finishes, so sent alerts still get recorded.

## Review items

### r1 @d46a2ce
- correctness#1 BLOCKING: macos/Host/main.swift:275-303 (showSettings) + main.swift:343-346: the app never sets NSApp.mainMenu (grep for mainMenu/NSMenu in macos/ finds nothing; Info.plist has no NSMainNibFile). AppKit sends Cmd+V/C/X/A/Z to text fields through the main menu's key equivalents, so with no Edit menu they do nothing. Concrete case: copy '~/.claude-work' or an email, focus the 目录 or 邮箱 TextField (SettingsView.swift:140,142), press Cmd+V: nothing is pasted (beep). Cmd+W and Cmd+Q don't work either. Fix: before showing the window, build a minimal main menu with an app menu (Quit) and an Edit menu (Undo/Redo/Cut/Copy/Paste/Select All, standard selectors) and a Close item.
- correctness#2 NON-BLOCKING: main.swift:276 + main.swift:326-331: once the policy is .regular, Quit from the Dock menu calls NSApp.terminate directly and skips the decision(close) path. If a collect is delivering alerts at that moment, alerts macOS already took never reach record-alerts and get sent again on the next run. Fix: add applicationShouldTerminate that returns .terminateLater while `running` and replies from finished().
- correctness#3 NON-BLOCKING: accounts.py:142-145 editable: a file with no 'accounts' key (e.g. {"threshold": 80}) gives error null and an empty table. load fails on the same file with 'accounts must be a list' (checked by calling both in a mktemp dir), so the window hides that collect is broken. Treat a missing accounts key as an FR-9 error, the same as a non-list.
- correctness#4 NON-BLOCKING: accounts.py:142-150 editable: {"threshold": NaN} passes the isinstance check, so read-accounts prints 'threshold': NaN (checked). Swift's JSONDecoder rejects NaN, lastLine returns nil, and the window says to run make install (main.swift:299). Reject non-finite thresholds in editable (math.isfinite) so the FR-9 error path handles them.
- correctness#5 NON-BLOCKING: SettingsView.swift:36-41 + main.swift:306-323: only Save is disabled while saving; rows can still be moved or deleted. model.failed then applies problems by index to the current rows, so after a delete or reorder during the save a problem lands on the wrong row. Disable row edits while model.saving, or map problems by row id captured in the request.
- requirement-fidelity#1 NON-BLOCKING: [spec-drift] agent_usage_monitor/accounts.py:243 + :257: editable() shows each dir with the home shortened to `~` (FR-3 only asks for that in the display), and save() writes the row's dir back exactly as shown. So saving rewrites rows the user never touched: a file with "dir": "<HOME>/.claude-work" comes back as "~/.claude-work". expand() reads both forms the same way, but neither the plan's decision(unknown-fields) nor the Task 1 tests record this rewrite. Either log it as a decision or keep the original dir when the row's displayed value has not changed.
- verification#1 NON-BLOCKING: CI at d46a2ce passed: make check (success); ci-verdict.py exit 0; HEAD d46a2ce78f4a3b643c8f57dc512b0e2e2a376cce, status clean before; nothing else run

### r2 @b775cca
- correctness#1: RESOLVED (main menu set before the window shows; Quit closes the window).
- correctness#6 NON-BLOCKING: macos/Host/main.swift:352: only the menu's Cmd+Q waits for a running collect. A Dock-menu Quit or a logout sends NSApp.terminate directly, and there is no applicationShouldTerminate. Case: Save at :311 starts refresh(), then the user picks Quit from the Dock menu while deliver/record is running. The host exits after the alerts reach macOS but before record-alerts runs, so the next collect sends the same alerts again. Fix: add applicationShouldTerminate that, while `running`, closes the settings window and returns .terminateCancel. The custom quit(_:) can then become the standard terminate: selector.
- correctness#7 NON-BLOCKING: macos/Host/main.swift:357-361: closing the window or pressing Cmd+Q while a write-accounts save is in flight (`running` is false) ends the app at once. The orphaned child still writes the file, but the refresh() at :311 never runs, so the widget shows the old accounts until the next scheduled collect. Fix: also wait on model.saving before terminating.
- requirement-fidelity#1: OPEN (non-blocking): fix diff leaves accounts.py save() unchanged (lines 159-173): row dir is still written back exactly as editable() shows it (~-abbreviated), so an untouched row with "<HOME>/.claude-work" is saved as "~/.claude-work", and no decision is logged
- requirement-fidelity#2 NON-BLOCKING: [spec-drift] .autopilot/settings-window-plan.md:66 Data shape still says read-accounts prints `"path": str (~-abbreviated)`, but b775cca removed that field (accounts.py:136-137, Settings.swift AccountsFile). Update the line so it matches the removal logged at plan:40
- verification#2 NON-BLOCKING: CI at b775cca passed: make check (success); ci-verdict.py exit 0; reviewed_sha b775cca5431c969dcd448478f2ed932dd17b691a; HEAD and status clean before and after

## Notes

- Host build: `xcrun swiftc -O macos/Host/*.swift` list is explicit in Makefile `app`; swift-test builds Snapshot.swift + Alerts.swift + Tests/main.swift (Foundation only).
- `make check` greps Swift/Python for 'socket', 'curl', 'security ', 'oauth', 'URLSession', … : keep those strings out of code and comments.
- Python tests: `/usr/bin/python3 -m unittest discover -s tests -t .`; helpers.Env gives temp HOME/XDG_CONFIG_HOME.
- accounts.load error format `<path>: accounts[i] (name): <problem>`; tests in tests/test_accounts.py assert substrings.

## Task list

Global constraints:
- Rules in one place: `accounts.validate(data, environ)` is what `load` and `write-accounts` both run.
- Data shape: read-accounts prints one JSON line `{"error": str|null (names the file), "threshold": number, "accounts": [{"name","client","dir","account": str, "original": str}], "original": str}`; on a missing file: defaults, error null; on an unparsable or uneditable file: defaults, error set, threshold 90, original "{}". write-accounts reads `{"threshold", "accounts": [same rows], "original"}` on stdin; exit 0 written; exit 1 and one line `{"problems": [{"index": int|null, "message": str}]}`; exit 2 malformed request.
- URL scheme `agent-usage-monitor`, widget URL `agent-usage-monitor://refresh`.
- threshold UI range 50…100 step 1, default 90; collect still accepts (0, 100].
- Test data only example.com emails and `~/.claude-example`-style dirs (NFR-3).
- No mutation testing (Engineer rule, every brief).

### Task 1: accounts.py validate/editable/save and the read-accounts, write-accounts subcommands

- Files: agent_usage_monitor/accounts.py, agent_usage_monitor/cli.py, tests/test_accounts.py, tests/test_cli.py.
- Produces: `accounts.validate(data, environ) -> (threshold, [Account], [(index|None, where, problem)])`; `accounts.defaults(environ)`; `accounts.editable(environ) -> dict`; `accounts.save(environ, request) -> [(index|None, problem)]`; CLI `read-accounts`, `write-accounts`.
- Tests first: load messages unchanged (existing suite); validate collects one problem per bad row (empty name, duplicate name, missing dir, bad client, same dir) with its index; editable: missing file → defaults, no file created; corrupt JSON → error, file unchanged; accounts not a list / non-string field → error; home-absolute dir → `~/…`; save: each rule → problems, file unchanged; unknown top-level and per-account fields kept; mode 0600; threshold 85 → `85`; empty account removes the key; symlinked accounts.json keeps the link; missing config dir created; CLI exit codes 0/1/2 and one JSON line.
- Checks: `make test`, `make pii-scan`.
- Commit: `TASK-645: accounts.json read and write for the settings window, one rule set with collect`

### Task 2: host app settings window and launch routing

- Files: macos/Host/Settings.swift (new, Foundation: Codable rows, `opensSettings`), macos/Host/SettingsView.swift (new, SwiftUI view + @Observable model), macos/Host/main.swift, macos/Host/Info.plist (CFBundleURLTypes), macos/Widget/AgentUsageMonitorWidget.swift (widgetURL), macos/Tests/main.swift, Makefile (new sources in app and swift-test).
- Consumes: Task 1's JSON.
- Tests first (swift-test): `opensSettings` for launchd label / application.* / nil / URL; decoding a read-accounts line (with a login-shell line before it); encoding a save request keeps `original`.
- Checks: `make swift-test`, `make app`, `make pii-scan`.
- Commit: `TASK-645: settings window when the app is opened directly; widget clicks still only refresh`

### Task 3: README: opening the settings window; hand editing still works

- Files: README.md, tests/test_readme.py.
- Tests first: README names how to open the settings window and keeps the manual-edit section.
- Checks: `make test`, `make pii-scan`.
- Commit: `TASK-645: README: the settings window`
