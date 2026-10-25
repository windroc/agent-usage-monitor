> The spike code this report describes was removed after M1; it is in git history at commit 315af6e (`spike/clt-widget/`). The product build in `macos/` and the `Makefile` replaced it.

# Spike: CLT-only WidgetKit widget (TASK-573)

Can `swiftc` + the Command Line Tools (CLT) SDK, with no Xcode and no signing certificate, build an ad-hoc-signed host app plus WidgetKit extension that macOS shows, that reads `~/.local/state/quotaboard/`, and that opens its host app on click? The answer picks M1's build: pass → `make` with `swiftc` + CLT; fail → Xcode project + `xcodebuild` with ad-hoc signing.

## Layout

| Path | Role |
|---|---|
| `Host/main.swift`, `Host/Info.plist` | `QuotaboardSpike.app` (`com.windroc.quotaboard.spike`), `LSUIElement`, unsandboxed. Each launch writes `opened <UTC time>` to `~/.local/state/quotaboard/spike.txt`, calls `WidgetCenter.shared.reloadAllTimelines()`, exits after 2 s. |
| `Widget/SpikeWidget.swift`, `Widget/Info.plist` | `QuotaboardSpikeWidget.appex` (`com.windroc.quotaboard.spike.widget`, extension point `com.apple.widgetkit-extension`), medium only. Shows the content of `spike.txt` or `read failed: …`; logs `read ok` / `read failed` to subsystem `com.windroc.quotaboard.spike`. |
| `Widget/widget.entitlements` | `com.apple.security.app-sandbox` + `com.apple.security.temporary-exception.files.home-relative-path.read-only` = `/.local/state/quotaboard/`, nothing else. |
| `Makefile` | Build, sign, install, uninstall, check. CLT tools only. |

## Commands

Run from this directory, or with `make -C spike/clt-widget <target>`.

| Target | Does |
|---|---|
| `make build` | `xcrun swiftc -O Host/main.swift -o …/MacOS/QuotaboardSpike`; `xcrun swiftc -O -parse-as-library -application-extension Widget/SpikeWidget.swift -Xlinker -e -Xlinker _NSExtensionMain -o …/QuotaboardSpikeWidget.appex/Contents/MacOS/QuotaboardSpikeWidget`; `codesign --force -s - --entitlements Widget/widget.entitlements <appex>`, then `codesign --force -s - <app>`. Output: `build/QuotaboardSpike.app`. |
| `make install` | `build`, then `ditto` to `~/Applications/QuotaboardSpike.app`, `lsregister -f` it, `pluginkit -a` the appex, create `~/.local/state/quotaboard/` (0700) and seed `spike.txt` with `installed <UTC time>` if absent. |
| `make check` | `build`, `plutil -lint` the plists, `codesign --verify --deep --strict`, and diff the appex's signed entitlements against `Widget/widget.entitlements`. |
| `make uninstall` | `pluginkit -r`, `lsregister -u`, delete `~/Applications/QuotaboardSpike.app` and `spike.txt`, remove `~/.local/state/quotaboard/` if empty. |
| `make clean` | Delete `build/`. |

Each rebuild changes the ad-hoc signature; a widget already on the desktop may need removing and re-adding.

## Results (macOS 26.7.1, `swiftc` 6.4, CLT only, 2026-10-17)

Home paths below are shown as `~`.

Verified on this Mac:

- `make check`: exit 0; `Host/Info.plist: OK`, `Widget/Info.plist: OK`, `Widget/widget.entitlements: OK`; `check ok: appex entitlements match Widget/widget.entitlements`.
- `make install`: exit 0.
- `codesign --verify --deep --strict --verbose=2 ~/Applications/QuotaboardSpike.app`: exit 0, `valid on disk`, `satisfies its Designated Requirement`.
- `codesign -dv <appex>`: `Signature=adhoc`, `TeamIdentifier=not set`.
- `codesign -d --entitlements - <appex>`:
  ```
  [Key] com.apple.security.app-sandbox
  [Value] [Bool] true
  [Key] com.apple.security.temporary-exception.files.home-relative-path.read-only
  [Value] [Array] [String] /.local/state/quotaboard/
  ```
  The host app has no entitlements.
- `pluginkit -m -v -i com.windroc.quotaboard.spike.widget`: `com.windroc.quotaboard.spike.widget(0.1)	<uuid>	2026-10-17 05:01:46 +0000	~/Applications/QuotaboardSpike.app/Contents/PlugIns/QuotaboardSpikeWidget.appex (1 plug-in)`; it is also listed under `pluginkit -m -p com.apple.widgetkit-extension`.
- `log show` (chronod, the WidgetKit daemon): `Added extensions: [<WidgetExtension - identifier: com.windroc.quotaboard.spike::com.windroc.quotaboard.spike.widget, … isApple: false>]` and `Reload requested for com.windroc.quotaboard.spike::com.windroc.quotaboard.spike.widget … reason: extensionChanged`. It also logs `Requested to add extension, but purging instead because we shouldn't cache it: … isApple? false`; what that means for the gallery is unknown (no other third-party widget on this Mac to compare).
- `open ~/Applications/QuotaboardSpike.app`: the host ran and exited; `spike.txt` became `opened 2026-10-17T05:02:00Z`. chronod logged `Ignoring restricted or unknown extension com.windroc.quotaboard.spike` for its reload, the same line it logs for Apple apps such as `com.apple.Notes`; no widget had been added yet.

| Pass condition | Status |
|---|---|
Manual checks by the user, 2026-10-17:

| Pass condition | Status | Evidence |
|---|---|---|
| 1. Widget appears in the widget gallery | pass | `Quotaboard Spike` listed in Edit Widgets; medium widget added to the desktop. |
| 2. Widget reads a file under `~/.local/state/quotaboard/` | pass | Widget shows `Quotaboard spike`, `opened 2026-10-17T05:30:44Z`, `rendered 1:30 AM`; log: `QuotaboardSpikeWidget … [com.windroc.quotaboard.spike:widget] read ok: opened 2026-10-17T05:30:44Z`. |
| 3. Clicking the widget opens the host app | pass | After a click `spike.txt` changed from `opened 2026-10-17T05:29:20Z` to `opened 2026-10-17T05:30:44Z`, and the widget showed the new time within seconds, so `reloadAllTimelines()` from this host works. |

**Conclusion: pass.** M1's `make` builds with `swiftc` + CLT; NFR-2 needs only CLT. The chronod `shouldn't cache it` line did not stop the gallery from listing the widget.

## Manual checks

1. `make -C spike/clt-widget install` (skip if already installed and not rebuilt).
2. **Condition 1**: right-click the desktop › Edit Widgets, search `Quotaboard Spike`. Pass: it is listed. Add the medium size to the desktop.
3. **Condition 2**: the widget shows `installed <time>` or `opened <time>` (the content of `spike.txt`). Pass: that text; fail: `read failed: …`. Evidence: `/usr/bin/log show --last 10m --predicate 'subsystem == "com.windroc.quotaboard.spike"'` shows `read ok: …`.
4. **Condition 3**: note the time in the widget, click it. Pass: `cat ~/.local/state/quotaboard/spike.txt` shows a new `opened <time>`. If the widget also shows the new time within a few seconds, `reloadAllTimelines()` from this host works (a PRD risk); if not, the timeline refreshes within about 5 minutes.
5. Clean up: remove the widget from the desktop, then `make -C spike/clt-widget uninstall` (also deletes `spike.txt`; M1 allows only its own files in that directory).
