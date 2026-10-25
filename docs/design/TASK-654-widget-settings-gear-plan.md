Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-654-widget base_ref=cdcb5d2cbb108ec736d1f6eb84d9973836c05cfd review_round=1 input_sha=e3236f39307f

# Plan: TASK-654 widget settings gear

## Input

Verbatim in <WORKDIR>/tmp/autopilot-input.md (input_sha e3236f39307f). Summary: medium and large widget get a small grey gear (`Link` to `agent-usage-monitor://settings`) at the bottom-right, also in the no-data state; the rest of the widget still opens `agent-usage-monitor://refresh` and only refreshes; the host shows the settings window for the settings URL (cold launch: start and show; running: bring to front); medium still fits 3 accounts; README says the gear opens the settings window; `make check` and CI pass; no install into ~/Applications, no killing system processes.

**Preview gate (mandatory):** after S5, before S6, stop and hand back previews (medium and large, dark, opaque, fake example.com data) as PNGs in <WORKDIR>/tmp/. Resume S6 r1 only once the caller passes the user's approval.

## Verify

Verify command: `make check`
CI checks: ["make check"]

## Progress log

- S1 done: mode=stay, branch TASK-654-widget, base_ref cdcb5d2.
- decision(gear-placement): the gear sits in the bottom-trailing content margin, one glyph size past the content's bottom-trailing corner (an overlay with an offset), so it takes no height from `fit` and covers no text: medium content is 123 pt and 3 compact accounts use 122 pt, so no row can give room. Center ≈ 11 pt from both widget edges with 16 pt margins, inside the rounded corner.
- decision(url-routing): pure `opensSettings(xpcServiceName:urls:)` in Settings.swift: with URLs, true iff one is `agent-usage-monitor://settings`; without, the TASK-645 LaunchServices rule. The running host routes each open the same way: settings → showSettings (activate, front), else refresh. Any other URL refreshes, as before.
- S5 task 1 done: a811839 red=swift-test build failed (11 opensSettings checks, missing `urls:` label); swift-test ok, make app ok (no warnings), pii-scan ok
- S5 task 2 done: 2276aa4 red=1 (test_settings_gear); swift-test ok, make app ok (no warnings), make test 208 OK, pii-scan ok
- previews (tmp/preview/: widget.swift with `@main` dropped and the gear's Link swapped for Group, since ImageRenderer draws Link as a placeholder): <WORKDIR>/tmp/preview-medium.png (3 accounts fit), preview-large.png, preview-medium-nodata.png; opaque, dark.
- S5 done, pushed 2276aa4 (`git push -u`; pr.py push --task had set no upstream). HOLD before S6 per the preview gate: resume S6 r1 only on the user's approval via the caller.
- user requirement (2026-10-17, via commander, after preview 1): gear size fine; position wrong: too far into the bottom-right corner, clipped by the rounded corner. Move it inward, clear of the corner radius, aligned with the right edge of the percent/reset column, below the last row; medium still fits 3 accounts; re-render medium, large and no-data previews at the same paths; stop again before S6.
- decision(gear-position-2): gear trailing edge on the content's trailing edge (the percent and reset column's right edge), its top 2 pt under the content frame's bottom, so it is under every row. Strictly inside WidgetKit's content frame is not possible at medium without losing a row or spacing: 3 compact accounts use 122 of 123 pt. Clearance: with 16 pt margins it spans 16–26 pt from the right edge and 4–14 pt from the bottom, its centre ≈ 11 pt from the 22 pt corner arc's centre, so the corner radius cannot clip it.
- S5 fix done (user change): b5b5b76 red=none (layout only; previews show it); swift-test ok, make app ok (no warnings), make test 208 OK, pii-scan ok
- previews re-rendered at the same paths: preview-medium.png (3 accounts fit), preview-large.png, preview-medium-nodata.png
- S5 done, pushed b5b5b76. HOLD again before S6 per the preview gate: resume S6 r1 only on the user's approval via the caller.
- user approved the moved gear (b5b5b76), via commander: preview gate passed; go on to S6.
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- S6 r1 pinned @b5b5b76; PR PR #10 (draft); CI peek: PENDING
- S6 r1 @b5b5b76: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (CI check make check, success) -> converged
- residual NON-BLOCKING: correctness#1 (cold-launch URL batch: refresh dropped when gear and body both tapped before launch finishes)

## Review items

- S6 r1:
  - correctness#1 NON-BLOCKING: macos/Host/main.swift:95 (open) with macos/Host/Settings.swift:10: on a cold launch, URLs from separate clicks pile up in openedURLs and are routed as one batch. Case: the user taps the widget body, then the gear, before applicationDidFinishLaunching. openedURLs is [refresh, settings], so only showSettings runs and the refresh is dropped. The widget then stays stale until the window's 300 s timer fires. Suggested fix: when the batch also holds a non-settings URL, call refresh() as well as showSettings().
  - verification#1 NON-BLOCKING: CI mode: ci-verdict.py --sha b5b5b76 exited 0: CI at b5b5b76 passed: make check (success). Pre-check HEAD=b5b5b76, status empty.

## Notes

- Commits: `TASK-654: <message>` plus `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Plan docs live in docs/design/ with <WORKDIR>/<WORKTREE>/<AUTOPILOT> placeholders for local paths.
- Swift self-test: macos/Tests/main.swift via `make swift-test` (builds Snapshot.swift, Alerts.swift, Settings.swift); README test tests/test_readme.py via `make test`.
- Preview renderer pattern (TASK-641): `sed 's/^@main$//'` the widget file into tmp/preview/widget.swift, `xcrun swiftc -parse-as-library Snapshot.swift widget.swift preview.swift`; ImageRenderer works with CLT; widget 342×157 medium, 342×337 large, 16 pt margins.

## Task list

Global Constraints:
- Settings URL: `agent-usage-monitor://settings`; refresh URL unchanged `agent-usage-monitor://refresh` (scheme already registered in macos/Host/Info.plist).
- Gear: SF Symbol `gearshape`, 10 pt, `.secondary` (the account line's style), bottom-trailing, outside the content frame by one glyph size; on both the account list and the no-data view.
- `fit` and `Metrics` unchanged; `fit_compact_screenshot` keeps 3 accounts at 155 − 2·16.
- Never install into ~/Applications or kill processes; no mutation testing.

### Task 1: host shows the settings window for the settings URL

- Files: macos/Host/Settings.swift, macos/Host/main.swift, macos/Tests/main.swift, README.md (Settings window section's URL paragraph).
- Produces: `func opensSettings(xpcServiceName: String?, urls: [URL]) -> Bool` (replaces `openedURL: Bool`).
- Tests first (macos/Tests/main.swift): settings URL on a LaunchServices cold launch → true; refresh URL → false; settings URL with no XPC name (running host) → true; other scheme `x://settings` → false; unknown host `agent-usage-monitor://other` → false; settings among several URLs → true; existing no-URL cases unchanged.
- Code: AppDelegate keeps the cold-launch URLs; applicationDidFinishLaunching and application(_:open:) both route through opensSettings → showSettings or refresh.
- Checks: `make swift-test`, `make app`.
- Commit: `TASK-654: the settings URL shows the settings window; other URLs still only refresh`

### Task 2: widget gear opens the settings window

- Files: macos/Widget/AgentUsageMonitorWidget.swift, README.md (how it works, widget, settings window), tests/test_readme.py, macos/Tests/main.swift (comment on the 3-account medium fit check only).
- Consumes: the settings URL (Task 1).
- Tests first: test_readme `test_settings_gear`: README states the gear opens the settings window. Widget view has no unit harness: preview render checks placement.
- Code: `SettingsGear` view (Link to the settings URL, gearshape 10 pt, secondary), overlaid bottom-trailing on the widget content with offset (10, 10), both states; widgetURL stays refresh.
- Checks: `make swift-test`, `make app`, `make test`, `make pii-scan`; render previews.
- Commit: `TASK-654: gear in the widget's bottom-right corner opens the settings window`
