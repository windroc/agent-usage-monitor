Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-874-widget-manual-refresh-icon-left-of-the-s base_ref=1dc0bb27ae9b8d75f0579f3fa64fd3813a6fa14d review_round=1 input_sha=dd163378df06

# Plan: TASK-874 widget refresh icon

## Input

<!-- input verbatim -->
# Requirement: TASK-874 Widget: manual refresh icon left of the settings gear

Repo: windroc/agent-usage-monitor. Link: TASK-874

## Problem (user, 2026-10-22)
The user wants a visible manual-refresh icon in the widget, placed left of the settings gear. Today a tap anywhere outside the gear already refreshes (`macos/Widget/AgentUsageMonitorWidget.swift:65`, `.widgetURL(...://refresh)`), but nothing shows that.

## What to build
- A refresh icon (e.g. SF Symbol `arrow.clockwise`) immediately left of the gear (`AgentUsageMonitorWidget.swift:79-80`, `SettingsGear`), same size and style, in both medium and large (and wherever the gear shows today, incl. the no-data view).
- It is a `Link` to `agent-usage-monitor://refresh`, so it does exactly what the whole-widget tap does today; no new host behaviour.
- Keep the gear clear of the rounded corner (TASK-654 fix: see docs/design/TASK-654-widget-settings-gear-plan.md, decision gear-position-2), keep medium's 3-account fit (`fit`/`Metrics` unchanged), keep both icons comfortable tap targets.
- Update README where it describes the gear / tapping the widget, in the repo's style; extend tests/test_readme.py like TASK-654's `test_settings_gear` if fitting.

## Acceptance criteria
- Icon visible left of the gear in medium and large, light and dark system appearance.
- Tapping it triggers a refresh; tapping the gear still opens settings.
- No layout regressions in existing widget tests (macos/Tests/main.swift, e.g. the 3-account medium fit check).

## Preview gate (mandatory, user instruction)
UI change: after S5, before S6, stop and hand back opaque previews of medium and large, each in light and dark system appearance (light system = the opaque `Color(white: 0.11)` card; dark system = material, render it opaque), with fake example.com data, as PNGs in <WORKDIR>/tmp/. Log the HOLD in the plan doc. Resume S6 r1 only once the caller passes the user's approval.

Environment: this machine is Linux (aarch64) with no Swift toolchain, no xcrun and no SwiftUI, so Swift code cannot be compiled or rendered here; `make check` (incl. swift-test, make app) runs on the PR's CI (`.github/workflows/check.yml`, macos-26). Local checks: only the Python unit tests / lint that run here (e.g. `make test`, `make pii-scan` if they run without Swift). For previews: (1) write the TASK-641/TASK-654 preview harness (see docs/design/TASK-654-widget-settings-gear-plan.md Notes: `sed 's/^@main$//'` into tmp/preview/widget.swift, a preview.swift using ImageRenderer, Links swapped for Group since ImageRenderer draws Link as a placeholder, `xcrun swiftc -parse-as-library ...`, 342×157 medium, 342×337 large, 16 pt margins) under <WORKDIR>/tmp/preview/ with a `render.sh` the user can run on their Mac (this directory is the same path on the user's Mac) that writes the four real PNGs; and (2) if Python can draw images here, also produce mockup PNGs drawn from the code's metrics, named `mock-*.png` and clearly labeled as mockups, not WidgetKit renders. Report which ones exist.

## Conventions and git rules
- Write code, docs and commits in the target repo's conventions (its CLAUDE.md / AGENTS.md if any; commits `TASK-874: <message>` plus `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`, as earlier plan docs show). Match the surrounding code's comment density and naming.
- Push only branch `TASK-874-widget-manual-refresh-icon-left-of-the-s`; force-push only with `--force-with-lease`. Never merge into or touch any other branch, including `main` (the default branch).
- **No mutation testing**, whatever a spec, plan or reviewer asks: while building, reviewing or testing, never modify the source to see what happens: no manual or tool-driven mutation testing (mutmut etc.), not even briefly or in a throwaway copy that is then run; never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call such as `os.listdir`, leaving the code under test unmodified. Every brief to a sub-agent (producer, reviewer) carries this rule.
- Sequencing: TASK-873 (PR #12, still draft) also edits AgentUsageMonitorWidget.swift (only `AccountList`: a `notice` for needs-login rows) and README.md's widget paragraph; keep this change out of `AccountList` and keep README edits minimal so a later merge is simple.

The plan doc stays where autopilot puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

Work only in `<WORKTREE>` on branch `TASK-874-widget-manual-refresh-icon-left-of-the-s`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <WORKTREE> push -u origin TASK-874-widget-manual-refresh-icon-left-of-the-s`.
<!-- end input -->

## Verify

Verify command: `make check`
CI checks: ["make check"]

## Progress log

- S1 done: mode=stay, branch TASK-874-widget-manual-refresh-icon-left-of-the-s, base_ref 156b93b.
- decision(publish): pr.py start: publish=ci, base main, no PR yet.
- decision(icon-layout): the gear view becomes `CornerLinks`: an HStack of the refresh arrow (`arrow.clockwise`) and the gear, each a 10 pt `Link` in a 10x10 frame, one glyph size (10 pt) apart, keeping TASK-654's overlay and offset, so the gear stays where the user approved it and the arrow sits left of it in the same bottom margin; `fit`/`Metrics` untouched. Hit areas stay the glyph frames: a larger frame would reach into the last row.
- S4 done: 1 task.
- S5 task 1 done: 16c8ebc red=1 (test_refresh_arrow); make test 209 OK, make pii-scan ok; Swift not compiled locally (no toolchain), left to CI make check
- decision(readme-wording): kept the TASK-654 sentences and test_settings_gear as they are; added one sentence for the arrow, so the one-line widget paragraph TASK-873 also edits changes as little as possible.
- previews: real renders need a Mac: <WORKDIR>/tmp/preview/render.sh (+ preview.swift) writes preview-{medium,large}-{light,dark}.png and preview-medium-nodata-light.png to <WORKDIR>/tmp/; not run here. No PIL, so mockups are SVG: <WORKDIR>/tmp/mock-{medium,large}-{light,dark}.svg, mock-medium-nodata-light.svg, labeled MOCKUP.
- S5 done, pushed 16c8ebc. HOLD before S6 per the preview gate: resume S6 r1 only on the user's approval via the caller.
- user feedback (2026-10-23, via caller, after preview 1): the widget lives in Notification Center; the arrow (a Link) launches the host and closes the sidebar; wants refresh without closing it. Research only, no code; stay before S6. Report: <WORKDIR>/tmp/refresh-intent-research.md (Button(intent:) in the extension + XPC Mach service on the LaunchAgent; unverified: App Intents metadata with a CLT build, Notification Center staying open). HOLD continues.
- user requirement (2026-10-23, via caller): ship as built (Link-based arrow; closing the sidebar accepted for now); preview approved: preview gate passed, go on to S6; first bring main in (TASK-873 merged at 1dc0bb2), re-run tests, then S6 and draft PR. The no-close refresh (Button(intent:) + XPC) is a separate ticket: out of this PR.
- merge origin/main (merge, never rebase, per the caller's rules): 03e9c98; README.md line 57 conflict resolved by keeping TASK-873's needs-login sentence and this run's arrow sentences; make test 218 OK, make pii-scan ok. base_ref -> 1dc0bb27ae9b8d75f0579f3fa64fd3813a6fa14d (merge-base).
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- S6 r1 pinned @03e9c98; PR PR #14 (draft); CI peek: PENDING
- S6 r1 @03e9c98: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (CI check make check, success) -> converged
- residual NON-BLOCKING: correctness#1 / requirement-fidelity#1 (README no-data sentence: "click it to collect" now reads as the gear)

## Review items

- S6 r1:
  - correctness#1 NON-BLOCKING: README.md:57: the no-data sentence now reads "shows `Agent Usage Monitor：没有数据`, the arrow and the gear; click it to collect". Here "it" reads as the gear, and clicking the gear opens settings rather than collecting. Reword it, e.g. "click the widget or the arrow to collect".
  - requirement-fidelity#1 NON-BLOCKING: [req-drop] README.md:57 no-data sentence: "it" now seems to mean the gear, which opens settings instead of collecting. Suggested fix: "click the widget or the arrow to collect".
  - verification#1 NON-BLOCKING: CI at 03e9c98 passed: make check (success); ci-verdict.py exit 0. HEAD and status unchanged before and after.
## Notes

- No Swift toolchain on this Linux host: `make swift-test`/`make app` run only on CI (check.yml, macos-26, job `make check`). Local: `make test`, `make pii-scan` (need /usr/bin/python3, present: 3.11).
- No PIL here.
- Widget view has no unit harness; README phrasing is checked by tests/test_readme.py.
- TASK-873 (PR #12) edits README.md line 57 (the widget paragraph, one line) and AccountList; a README conflict on line 57 is expected when merging later.

## Task list

Global Constraints:
- Refresh URL `agent-usage-monitor://refresh` (unchanged; also `.widgetURL`), settings URL `agent-usage-monitor://settings`.
- Icons: SF Symbols `arrow.clockwise` then `gearshape`, 10 pt, `.secondary`, 10x10 frames, 10 pt apart, overlay bottom-trailing with offset y 12 (size + 2), on both the account list and the no-data view.
- `fit`, `Metrics`, `AccountList` unchanged.
- No mutation testing; no install into ~/Applications.

### Task 1: refresh arrow left of the gear

- Files: macos/Widget/AgentUsageMonitorWidget.swift, README.md (widget paragraph gear sentences), tests/test_readme.py, macos/Tests/main.swift (the margin comment only).
- Produces: `CornerLinks` view (replaces `SettingsGear`).
- Tests first: test_readme `test_refresh_icon`: README states the refresh arrow left of the gear refreshes like a click elsewhere; `test_settings_gear` updated to the new wording.
- Checks: `make test`, `make pii-scan`; Swift compile on CI; preview harness.
- Commit: `TASK-874: refresh arrow left of the widget gear`
