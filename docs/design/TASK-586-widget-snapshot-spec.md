# Spec: TASK-586 desktop widget shows the snapshot, auto-updated every 5 minutes

Requirement source: the `input` in `.autopilot/widget-5-plan.md` (TASK-586, from TASK-561 M1 PRD FR-23..FR-29, NFR-1..NFR-4, and TASK-585 D1). It overrides any other input.

## Goal

After `make install` the user adds a medium quotaboard widget that shows one row per account from `~/.local/state/quotaboard/snapshot.json`. A LaunchAgent runs the host app with `--scheduled` every 300 s (`quotaboard collect`); a widget tap opens the host app (`quotaboard collect --probe`). Today the repo has the Python `collect` (Codex only; `--probe` is accepted and does nothing yet) and the TASK-573 spike in `spike/clt-widget/` that proved a `swiftc` + CLT build of an ad-hoc-signed host + widget works.

## Scope

| In | Out |
|---|---|
| `macos/` host app, widget, LaunchAgent plist template | Claude `/usage` probe (FR-8..FR-11): TASK-587 |
| Top-level `Makefile`: `app`, `swift-test`, `install`, `uninstall`, extended `check` | Widget sizes other than medium, notifications (TASK-562), CLI table (TASK-563) |
| README install/rollback, checks, spike conclusions | URL schemes, App Groups, non-ad-hoc signing |
| Assert-based Swift self-test of the widget formatter | Changes to `spike/clt-widget/` (kept as the TASK-573 record) |

Constraints: Swift uses only system frameworks (AppKit, WidgetKit, SwiftUI, Foundation, OSLog); `make` needs only CLT, GNU make 3.81 (no `.SHELLFLAGS`, no `.ONESHELL`; `SHELL := /bin/bash` is allowed); no Python behaviour change; no build step runs `make install`, `launchctl` or touches the user's real `~/Applications`, `~/Library`, `~/.local`.

## Terms

- **host**: `Quotaboard.app`, bundle id `com.windroc.quotaboard`, executable `Quotaboard`.
- **widget**: `Quotaboard.app/Contents/PlugIns/QuotaboardWidget.appex`, bundle id `com.windroc.quotaboard.widget`.
- **run**: one host child `/bin/zsh -l -c 'exec "$HOME/.local/bin/quotaboard" collect[ --probe]'`.
- **display**: the pure formatter output for one snapshot: header line, row cells, overflow count.

## Acceptance criteria

TASK-595 replaced FR-26's text rows with progress bars: AC10 to AC12 and the `DisplayRow` shape below no longer hold.

- AC1 (FR-23): host `Info.plist` has `LSUIElement` true and no `CFBundleURLTypes`; host is signed without entitlements (unsandboxed).
- AC2 (FR-23): launched with `--scheduled` in `CommandLine.arguments` → one run of `collect`; any other launch → one run of `collect --probe`; after the last run → `WidgetCenter.shared.reloadAllTimelines()`, then the host exits after 2 s.
- AC3 (FR-23): a run still alive after 40 s → SIGTERM, then SIGKILL if still alive 2 s later; then reload and exit (a pending click is dropped).
- AC4 (FR-24): at launch, another running app with bundle id `com.windroc.quotaboard` and a lower pid → this process exits 0 at once (no run). Two hosts started within milliseconds can both run (a launchd-started host appears in `NSRunningApplication` only after AppKit checks in); harmless, `store.write` serializes them with `flock` (D2).
- AC5 (FR-24): reopen (`applicationShouldHandleReopen`) while the host lives → records one pending click (repeats collapse); when the current run ends and the 2 s grace passes, a pending click starts one more `collect --probe` run instead of exiting.
- AC6 (FR-25): `make install` renders `~/Library/LaunchAgents/com.windroc.quotaboard.plist`: `Label` `com.windroc.quotaboard`, `ProgramArguments` [`<HOME>/Applications/Quotaboard.app/Contents/MacOS/Quotaboard`, `--scheduled`], `StartInterval` 300, `RunAtLoad` true, `StandardOutPath` and `StandardErrorPath` `<HOME>/Library/Logs/quotaboard.log`; it creates that log 0600 (and chmods an existing one to 0600); the rendered plist passes `plutil -lint`.
- AC7 (FR-25, FR-29): `make install` builds, `ditto`s to `~/Applications/Quotaboard.app`, registers it (`lsregister -f`, `pluginkit -a`), and links `~/.local/bin/quotaboard` → `<repo>/bin/quotaboard`; an existing `~/.local/bin/quotaboard` that is not a symlink, or a symlink to another target → `make install` fails with `quotaboard: ~/.local/bin/quotaboard exists and is not a link to <repo>/bin/quotaboard` before replacing anything.
- AC8 (FR-29): `make uninstall` runs `launchctl bootout gui/$(id -u)/com.windroc.quotaboard` first (failure ignored), then `pluginkit -r`, `lsregister -u`, deletes `~/Applications/Quotaboard.app`, the `~/.local/bin/quotaboard` symlink (only if `readlink` equals `<repo>/bin/quotaboard`) and the plist; it keeps the state dir, account list and log. Works when nothing is installed.
- AC9 (FR-26): display header `可用 <n>/<m> · <rel>`: `n` rows with `available` true, `m` all rows; `<rel>` from `now - generated_at`: < 60 s or negative → `刚刚`, < 3600 s → `<min> 分钟前`, < 86400 s → `<h> 小时前`, else `<d> 天前` (floors); ` ⚠` appended when any row has `stale` true or `source` `none`.
- AC10 (FR-26, D1): each row in snapshot order is a `DisplayRow`: `name`; `5h <x>%`; `7d <y>%`; availability `是` (true) / `否 <time>` (false, `available_at` set) / `否 —` (false, null) / `未知` (null); stale row → availability cell ends ` ⚠`. A window that is `null` or has `used_percent` null → `5h —` / `7d —`.
- AC11 (FR-26): `<time>` is `HH:mm` when `available_at` is the same calendar day as now, else `周X HH:mm` (`周日`..`周六`), in the calendar's time zone.
- AC12 (FR-26): at most 5 rows; more → `more` = count beyond 5, shown as a last line `+<more>`; ≤ 5 → no such line. Zero accounts → header `可用 0/0 · <rel>`, no rows.
- AC13 (FR-27): snapshot file missing, unreadable, not JSON, not the expected shape, or `schema` not 1 → widget shows `quotaboard：没有数据` and `点这里刷新`.
- AC14 (FR-28): timeline has one entry dated now, policy `.after(now + 300 s)`; the widget sets no `widgetURL`/`Link`, so a tap anywhere opens the host.
- AC15 (NFR-3): widget signed with exactly `com.apple.security.app-sandbox` true and `com.apple.security.temporary-exception.files.home-relative-path.read-only` = [`/.local/state/quotaboard/`].
- AC16 (NFR-1, NFR-2): `make check` greps the NFR-1 strings in Python and Swift code (`quotaboard tests bin/quotaboard macos`) and finds none; Swift imports only system frameworks; the host starts only `/bin/zsh`.
- AC17 (FR-29): README has the install table (each step + rollback), account-list sample, `zsh -lc 'command -v claude codex'` check, rebuild → re-add widget note, TASK-572 and TASK-573 conclusions, and `make uninstall` behaviour.

## Design

### Data shape (`macos/Widget/Snapshot.swift`, Foundation only)

```swift
struct UsageWindow: Decodable { let usedPercent: Int?; let resetsAt: Int? }
struct Row: Decodable {
    let name: String
    let available: Bool?; let availableAt: Int?
    let fiveHour: UsageWindow?; let sevenDay: UsageWindow?
    let source: String?; let stale: Bool?
}
struct Snapshot: Decodable { let generatedAt: Int; let accounts: [Row] }
struct DisplayRow: Equatable { let name, fiveHour, sevenDay, availability: String }
struct Display: Equatable { let header: String; let rows: [DisplayRow]; let more: Int }

func loadSnapshot(path: String) -> Snapshot?            // JSONDecoder, .convertFromSnakeCase; any error → nil
func display(_ s: Snapshot, now: Date, calendar: Calendar) -> Display
```

Unknown JSON keys are ignored. `UsageWindow?` nil covers D1's whole-window `null`. Times via `calendar.dateComponents`, no `DateFormatter`.

### `macos/Widget/QuotaboardWidget.swift`

`@main struct QuotaboardWidget: Widget`, kind `Quotaboard`, display name `quotaboard`, `.supportedFamilies([.systemMedium])`. Provider reads `<pw_dir>/.local/state/quotaboard/snapshot.json` (`getpwuid(getuid())`, as the spike: `NSHomeDirectory()` is the container), entry `{date, display: Display?}`; nil → AC13 text; read failure logged via `Logger(subsystem: "com.windroc.quotaboard", category: "widget")`. View: header, then a SwiftUI `Grid` (name leading; cells monospaced digits), then `+<more>`; `.containerBackground(.fill.tertiary, for: .widget)`.

### `macos/Widget/Info.plist`, `macos/Widget/widget.entitlements`

From the spike with the ids above; `CFBundleDisplayName` `quotaboard`; entitlements as AC15.

### `macos/Host/main.swift`, `macos/Host/Info.plist`

Info.plist from the spike: id `com.windroc.quotaboard`, name/executable `Quotaboard`, `LSUIElement`. `main.swift`: AC4 check before `NSApplication.shared.run()`; `AppDelegate` holds `pendingClick`, `timedOut`, current `Process`. `applicationDidFinishLaunching` → `run(probe: !CommandLine.arguments.contains("--scheduled"))`. `run` sets the 40 s timer (AC3); `terminationHandler` hops to main → reload → after 2 s: `pendingClick && !timedOut` → clear it and `run(probe: true)`, else `NSApp.terminate(nil)`. `Process.run()` throwing → message to stderr, same finish path. Child stdio is inherited (launchd → the log).

### `macos/com.windroc.quotaboard.plist`

LaunchAgent template with `@HOME@` placeholders; `make` renders `build/com.windroc.quotaboard.plist` with `sed "s|@HOME@|$HOME|g"`.

### `Makefile`

Keeps `test`. Adds:

| Target | Does |
|---|---|
| `app` | spike `build` steps for `build/Quotaboard.app` with the `macos/` sources (widget compiles `Snapshot.swift` + `QuotaboardWidget.swift`), ad-hoc signs appex (entitlements) then app; renders `build/com.windroc.quotaboard.plist` |
| `swift-test` | `xcrun swiftc macos/Widget/Snapshot.swift macos/Tests/main.swift -o build/swift-test` then runs it |
| `install` | AC6, AC7 |
| `uninstall` | AC8 |
| `check` | `test`, `swift-test`, `app`; NFR-1 grep incl. `--include='*.swift'` and `macos`; `plutil -lint` all `macos` plists + rendered plist; `codesign --verify --deep --strict`; appex entitlements diff (spike) |
| `clean` | `rm -rf build` |

Every multi-command recipe line uses `&&`/`if … fi`; nothing relies on `.SHELLFLAGS`. Every `$HOME` path, the `sed` render included, uses `$${HOME:?}`, so an unset HOME fails instead of touching `/Applications`.

### `README.md`

Status: installable. New `Install` section (table + rollback, AC17), keeps Development; Development lists `make swift-test`, `make check`. TASK-572: `/usage` passes (Claude Code 2.1.302, default account, no model request, no session cleanup); TASK-573: `swiftc` + CLT pass.

## Verification

| AC | Test or check |
|---|---|
| AC1 | `make check` (`plutil -lint`); review of `macos/Host/Info.plist`; manual: `codesign -d --entitlements - ~/Applications/Quotaboard.app` empty |
| AC2 | manual: `open ~/Applications/Quotaboard.app` → `generated_at` updates within ~30 s, host exits; `--scheduled` run exits, no leftover |
| AC3 | code review of `macos/Host/main.swift` (timer path); manual: temporarily point `~/.local/bin/quotaboard` at a script that sleeps 60 s, `open` the host → after ~40 s no host or child in `ps`; restore with `ln -sfn <repo>/bin/quotaboard ~/.local/bin/quotaboard` |
| AC4 | manual: `open` twice → one `collect --probe` process |
| AC5 | manual: `open` during a `--scheduled` run → a `--probe` run follows (`ps`) |
| AC6 | `make check` lints rendered plist; manual: `plutil -p ~/Library/LaunchAgents/com.windroc.quotaboard.plist`, `stat -f %Lp ~/Library/Logs/quotaboard.log` = 600, `launchctl bootstrap` → `generated_at` updates within 5 min |
| AC7 | manual: `make install`; `ls -l ~/.local/bin/quotaboard` |
| AC8 | manual: `make uninstall` → app, link, plist gone; `launchctl print gui/$(id -u)/com.windroc.quotaboard` fails |
| AC9 | `macos/Tests/main.swift`: `header_sample`, `header_warn_none`, `relative_times` |
| AC10 | `macos/Tests/main.swift`: `rows_sample`, `null_window`, `null_percent`, `availability_cells` |
| AC11 | `macos/Tests/main.swift`: `time_today`, `time_other_day` |
| AC12 | `macos/Tests/main.swift`: `overflow_5_6_7`, `zero_accounts`; manual: 7-account snapshot shows 5 rows and `+2` fully |
| AC13 | `macos/Tests/main.swift`: `load_missing`, `load_garbage`, `load_wrong_shape`, `load_no_schema`, `load_schema_2`, `load_schema_1`, `load_valid`; manual: delete snapshot → text |
| AC14 | code review; manual: tap → widget refreshes |
| AC15 | `make check` entitlements diff |
| AC16 | `make check` grep |
| AC17 | doc review |

Tests are hermetic: Swift tests use a temp dir and a fixed `Calendar` (gregorian, `America/New_York`). Every suite the repo names passes: `make test`, `make swift-test`, `make check`.

## Decisions

- D1: header ` ⚠` follows FR-26's rule even though the PRD sample header omits it while showing a stale row; the explicit rule is newer and more specific.
- D2: single-instance by lowest pid among `NSRunningApplication`s (PRD names that API); a plain "exit if any other" would let two simultaneous starts both exit. Pid wrap is ignored. Not a hard guarantee: two hosts started within milliseconds both pass the check before either is listed, and both run `collect`; `store.write`'s `flock` makes that harmless.
- D3: timeout kill drops a pending click and exits (FR-23 "结束它再退出").
- D4: relative time thresholds (AC9) are not in the PRD; `刚刚` comes from FR-28's check.
- D5: whole-window `null` and `used_percent` null both render `—` (FR-26 + D1); availability is the Python's, the widget only displays.
- D6: `spike/clt-widget/` stays untouched as the TASK-573 record.
- D7: the log is kept by `make uninstall`, like the state dir (FR-29 lists only app, link, plist).
- Left to the implementer: SwiftUI fonts and spacing within the medium size; test function names.
