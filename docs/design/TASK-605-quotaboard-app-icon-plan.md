Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-605-quotaboard-app-edit-widgets base_ref=3bb2c23c2d13656280d8fbb5577ea5150c7175ef review_round=2 input_sha=ac1bda8768de

## Input

## Requirement (TASK-605: Quotaboard app icon, no longer blank in Edit Widgets list)

Give `Quotaboard.app` the user's icon: source file `<user-supplied quota-widget-icon.png>` (1024×1024 RGBA: dark rounded square, full-bleed to the canvas edges, with three progress bars green/yellow/red). Today Quotaboard's icon is blank in the desktop Edit Widgets list (left column) and in Finder.

Acceptance criteria (precedence: these are the user's instructions; newer > older):
1. Build only with Command Line Tools and macOS built-in tools (e.g. `sips`, `iconutil`); no Xcode, no `actool` (NFR-2). Commit the source PNG to the repo (copy it in; strip any metadata chunks); generate the `.icns` during `make app`, or commit a generated one, whichever is the smaller change. `macos/Host/Info.plist` points to it (`CFBundleIconFile`).
2. First consult Apple docs (Human Interface Guidelines "App icons", and how macOS 26 treats icon shapes / legacy icons, e.g. the gray container for icons not matching the shape) to decide whether this already-rounded, full-canvas 1024 PNG must be scaled down / padded to the macOS icon grid (e.g. ~824px body centered in 1024 with transparent margin), so it doesn't render oversized on macOS 26 or get placed in a gray backing plate. Record the cited doc URLs and the decision in the plan doc; they go into the PR description. Do the scaling with built-in tools only (e.g. `sips --resampleHeightWidth` then `sips --padToHeightWidth`), at build time or on the committed source, whichever is smaller.
3. `make check` passes, and CI on the PR passes (CI runs `make check` on macos-26 with `DEVELOPER_DIR=/Library/Developer/CommandLineTools`; make sure `iconutil`/`sips` are available there, they are /usr/bin tools). If cheap, have `make check` assert the built app contains the icon (e.g. `test -s build/Quotaboard.app/Contents/Resources/<name>.icns`).
4. How to verify (for the PR description): after `make install`, Finder shows the icon on `~/Applications/Quotaboard.app` and the Edit Widgets list shows it; the user confirms. Note any icon-cache caveat (e.g. LaunchServices / iconservices cache) if relevant.
5. NFR-4: the image holds no personal info; commit no local machine paths (no `/Users/...` anywhere in committed files, including the plan doc).

## Conventions and git rules
- Follow the target repo's conventions (its `CLAUDE.md` / `AGENTS.md` if any; Makefile style: GNU make 3.81, chain dependent commands with `&&`; existing comment density). Update README only where it describes the build/app bundle and becomes incomplete.
- Default branch is `main`. Never push to or merge into `main` or any branch but `TASK-605-quotaboard-app-edit-widgets`; force-push only with `--force-with-lease`.
- No mutation testing: never modify the source to see what happens (no manual or tool-driven mutation testing, not even briefly or in a throwaway copy that is then run); never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call, leaving the code under test unmodified. Every brief to a sub-agent (producer, reviewer) carries this rule.

## Docs
The plan doc stays where autopilot puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

Work only in `<WORKTREE>` on branch `TASK-605-quotaboard-app-edit-widgets`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <WORKTREE> push -u origin TASK-605-quotaboard-app-edit-widgets`.

## Verify

Verify command: `make check` (repo root; CI job `make check` in `.github/workflows/check.yml`, macos-26, `DEVELOPER_DIR=/Library/Developer/CommandLineTools`)
CI checks: ["make check"]

## Progress log

- S1: mode=stay; publish=ci (pr.py start), no PR yet; base main @3bb2c23.
- decision(icon-grid): no scaling/padding; commit the source PNG as-is. Docs: HIG App icons (https://developer.apple.com/design/human-interface-guidelines/app-icons) says macOS icons are square and "the system applies masking to produce rounded corners"; it covers Icon Composer layers only, not how macOS 26 treats a legacy `.icns`. Apple documents no rule for legacy icons; third-party reports (https://developer.apple.com/forums/thread/797971, https://heise.de/-11075561) say macOS 26 shrinks non-conforming legacy icons onto a gray squircle. So a quick live test on macOS 26.7.1: two ad-hoc-signed test bundles, one `.icns` from the full-bleed PNG, one from the PNG scaled to 824 and padded to 1024 (`sips -z` / `sips -p`), rendered with `NSWorkspace.icon(forFile:)` (what Finder draws): both render identically, fitted to the system squircle, no gray plate. Padding changes nothing, so it is skipped.
- decision(icns): generate at `make app` from the one 1024 PNG (`iconutil` on an iconset holding only `icon_512x512@2x.png`; tested: iconutil accepts it, 28 KB `.icns`); macOS downsamples for small sizes. Smaller than committing a binary `.icns` plus its regeneration recipe; no `sips` needed.
- decision(png-metadata): source PNG has only IHDR, IDAT, IEND chunks: no metadata to strip; image shows only bars (NFR-4).

- S5 task 1 done: c672754 red=2 (icns test -s, CFBundleIconFile check); targeted: make app, both checks, plutil -lint, codesign --verify; NSWorkspace render of built app shows icon.
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- S6 r1 @c6727548: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (CI check make check, success) -> converged
- scope addition (user, mid-run): README demo screenshot `docs/images/` after the one-line intro, metadata stripped, alt text; then make check, re-run doc + verification only, push, report head.
- S5 scope task done: 1ef905b README demo screenshot (`docs/images/widget-demo.png`: converted to sRGB with `sips -m`, then only IHDR/IDAT/IEND chunks kept); make check exit 0.
- S6 r2 @1ef905bb: doc=PASS verification=PASS (CI check make check, success; PNG only IHDR/IDAT/IEND) -> converged
- Residual NON-BLOCKING: none.

## Review items

- r1: none BLOCKING. verification#1 (NON-BLOCKING, info): CI at c672754 passed: make check (success).
- r2: none BLOCKING. verification#2-4 (NON-BLOCKING, info): CI at 1ef905b passed; PNG chunk scan clean; frozen worktree held.

## Notes

- Build: `Makefile` target `app` assembles `build/Quotaboard.app`; `check` = test + swift-test + app + grep/plist/codesign checks. GNU make 3.81: chain dependent commands with `&&`.
- `build/` is gitignored. Design docs live in `docs/design/` with local paths replaced by `<AUTOPILOT>` / `<WORKTREE>` placeholders.
- S7 copy: replace every `/Users/...` path (input source PNG path, worktree, plugin paths) with a placeholder (NFR-4).

## Task list

Global Constraints: icon file `macos/Host/AppIcon.png` (the user's 1024×1024 RGBA PNG, unchanged bytes); bundle path `Contents/Resources/AppIcon.icns`; `CFBundleIconFile` = `AppIcon`; tools: `iconutil` only (built in), no Xcode, no `actool`. No mutation testing (never modify source to see what happens; never put a known-wrong value into shipped code).

### Task 1: Quotaboard.app icon

- Files: `macos/Host/AppIcon.png` (new, copied from the user's PNG), `macos/Host/Info.plist`, `Makefile`.
- Consumes / Produces: `$(APP)/Contents/Resources/AppIcon.icns`.
- Tests first: add to `make check` `test -s $(APP)/Contents/Resources/AppIcon.icns` and that the built `Info.plist`'s `CFBundleIconFile` is `AppIcon`; red: run those two commands against the current `build/Quotaboard.app` before the change (icns missing → fails).
- Code: `app` target makes `build/AppIcon.iconset` (clean first), copies the PNG to `icon_512x512@2x.png`, `iconutil -c icns … -o $(APP)/Contents/Resources/AppIcon.icns`, before codesign. Info.plist adds `CFBundleIconFile` `AppIcon`.
- Checks: `make app`, then the two new check commands, `plutil -lint macos/Host/Info.plist`, `codesign --verify --deep --strict build/Quotaboard.app`.
- Commit: `feat(app): Quotaboard.app icon (TASK-605)`
