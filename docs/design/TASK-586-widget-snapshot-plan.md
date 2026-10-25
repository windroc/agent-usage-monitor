Rules: <autopilot>/skills/build/SKILL.md <autopilot>/references/autopilot-common.md <autopilot>/references/review-round.md
RESUME: phase=done worktree=<worktree> branch=TASK-586-widget-5 base_ref=b0229b4f3c72a69d8548dae041f60e53e586b066 review_round=1 input_sha=2477b02e2cc2

## Input

# Requirement: TASK-586 desktop widget shows the snapshot, auto-updates every 5 minutes

Target repo: windroc/agent-usage-monitor (public). Default branch: `main`. PRD: `Product Design/2026-10-16-2312-TASK-561-m1-macos-widget.md` (TASK-561 M1 PRD; FR/NFR ids refer to it; text below).

## What to build (user's instructions, outrank the PRD)

After `make install`, the user can add the quotaboard widget (medium) to the desktop and see one row per account from the snapshot. A LaunchAgent starts the host app with `--scheduled` every 5 minutes to collect and refresh the widget; clicking the widget opens the host app, which runs `collect --probe`. Build with `swiftc` + Command Line Tools (CLT) per TASK-573's conclusion, no Xcode; reuse the TASK-573 spike code in `spike/clt-widget/` as a starting point. Gotcha: CLT's make is 3.81, `.SHELLFLAGS` has no effect there (the spike Makefile relies on it; the top-level Makefile must not).

## Acceptance criteria (user's instructions)

- [ ] FR-23: host app windowless, no Dock icon, unsandboxed; `--scheduled` runs `/bin/zsh -l -c '… collect'`, any other launch (incl. opened by the widget) runs `… collect --probe`; registers no URL scheme; after the run calls `reloadAllTimelines()` then exits; kills the child after 40 s.
- [ ] FR-24: only one host runs at a time; a reopen while running records the click, then after the current run runs `collect --probe` once more.
- [ ] FR-25: `make install` writes the LaunchAgent plist (300 s, `RunAtLoad`, log 0600); `plutil -lint` passes; within 5 minutes after `launchctl bootstrap` the snapshot updates.
- [ ] FR-26 to FR-28: widget layout matches the PRD sample (at most 5 rows plus `+k`); no data → shows `quotaboard：没有数据` and `点这里刷新`; timeline policy `.after(now + 5 minutes)`; tapping anywhere on the widget opens the host app.
- [ ] FR-29: README documents every install-table step and its rollback, the account-list sample, the `zsh -lc 'command -v claude codex'` check, and TASK-572 and TASK-573 conclusions; `make uninstall` first `launchctl bootout`, then deletes app, link and plist.
- [ ] NFR-1 (Swift part), NFR-2 (Swift uses only system frameworks, `make` needs only CLT), NFR-3 (widget sandboxed, only the home-relative read-only exception for the state dir).
- [ ] Manual desktop check steps go into the PR's How to verify, for the user to confirm.

## Carried over from TASK-585

- [ ] D1 (decided 2026-10-17): in the snapshot a window has three states: a value; `{"used_percent": null, ...}` unknown; the whole window `null` means the account has no such limit (the real default Codex account has only 7d). The widget shows `—` for a `null` window, not unknown or error.

## Scope notes

- The Claude `/usage` probe itself (FR-8..FR-11) is TASK-587, not this build; `collect --probe` already exists as a CLI flag or must at least be accepted — check `quotaboard/cli.py`. FR-23/24 checks "Claude row source becomes `usage`" only apply once TASK-587 lands; verify via `generated_at` and Codex rows here.
- Not in scope: other widget sizes, notifications, URL schemes, App Groups, signing other than ad-hoc.

## Relevant PRD excerpts (context; FR rows are requirements)

Install table (user runs; each step has its own rollback):

| Step | Rollback |
|---|---|
| `git clone git@github.com:windroc/agent-usage-monitor.git ~/.local/share/quotaboard`; `make -C ~/.local/share/quotaboard install` (build, ad-hoc sign, `ditto` to `~/Applications/Quotaboard.app`, link `~/.local/bin/quotaboard`, write `~/Library/LaunchAgents/com.windroc.quotaboard.plist`) | `make -C ~/.local/share/quotaboard uninstall` |
| `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.windroc.quotaboard.plist` | `launchctl bootout gui/$(id -u)/com.windroc.quotaboard` |
| If accounts outside the default dirs: write `~/.config/quotaboard/accounts.json` per README | delete that file |
| Desktop right-click › Edit Widgets, add quotaboard (medium) | remove the widget |
| Only if TASK-572 rejected `/usage` (it did not; see docs/spikes/TASK-572-claude-usage.md): status line tap | — |

`make uninstall` removes app, link and plist; the state dir `~/.local/state/quotaboard` and the account list are the user's to delete.

Widget sample (medium):
```
可用 3/4 · 2 分钟前
claude       5h 42%  7d 61%  是
claude-work  5h  0%  7d 20%  是 ⚠
codex        5h 15%  7d 33%  是
claude-max   5h 93%  7d 70%  否 17:00
```

Snapshot format (FR-6):
```json
{"schema": 1, "generated_at": 1792130400, "threshold": 90,
 "accounts": [{"name": "claude-max", "client": "claude", "dir": "/Users/u/.claude-max",
   "available": false, "available_at": 1792134000,
   "five_hour": {"used_percent": 93, "resets_at": 1792134000},
   "seven_day": {"used_percent": 70, "resets_at": 1792483200},
   "fetched_at": 1792130280, "source": "cache", "stale": false, "usage_disabled_version": null}],
 "summary": {"available": ["claude", "claude-work", "codex"], "next": {"name": "claude-max", "at": 1792134000}}}
```

Risks: launchd-started host's `reloadAllTimelines` may be throttled (the timeline's 5-minute policy is the fallback; TASK-573 showed reload from an `open`ed host works); a rebuild changes the ad-hoc signature, so the widget may need re-adding (README says so); `claude`/`codex` only on `.zshrc` PATH are not found by `zsh -l` (README gives the check command). launchd and LaunchServices give a short PATH, hence `/bin/zsh -l -c`.

| ID | Requirement | Check |
|---|---|---|
| FR-5 | Snapshot is `~/.local/state/quotaboard/snapshot.json`; dir 0700, file 0600; only `snapshot.json`, `snapshot.lock`, and FR-9's `probe/` in it | — |
| FR-23 | `Quotaboard.app` is a windowless, no Dock icon (`LSUIElement`), unsandboxed app; launched with `--scheduled` → runs `/bin/zsh -l -c 'exec "$HOME/.local/bin/quotaboard" collect'` (`zsh -l` only for the PATH with `claude`, `codex`); any launch without `--scheduled` (incl. opened by the widget) → runs `… collect --probe`; registers no URL scheme; after the run calls `WidgetCenter.shared.reloadAllTimelines()` then exits; child running over 40 s → kill it, then exit | Manual: `open ~/Applications/Quotaboard.app` → within ~30 s snapshot `generated_at` updates, host exits; `--scheduled` run exits with no leftover process; with `~/.local/bin` not on login PATH `--scheduled` still updates the snapshot; `Info.plist` has no `CFBundleURLTypes` |
| FR-24 | Only one host at a time (check `NSRunningApplication` by bundle id): a new launch while one runs exits; the running host on reopen (`applicationShouldHandleReopen`) records one click, and after the current run runs `collect --probe` once more | Manual: `open` twice in a row → only one `collect --probe` process; `open` once during a `--scheduled` run → another `--probe` run follows |
| FR-25 | `make install` writes `~/Library/LaunchAgents/com.windroc.quotaboard.plist`: `ProgramArguments` host executable plus `--scheduled`, `StartInterval` 300, `RunAtLoad` true, stdout and stderr to `~/Library/Logs/quotaboard.log` (`make install` pre-creates it 0600); stderr reason lines carry no raw probe output | `plutil -lint` passes; snapshot `generated_at` updates within 5 min of `launchctl bootstrap` |
| FR-26 | medium size; first line `可用 <n>/<m> · <generated_at relative to now>` (`<m>` all accounts), plus ` ⚠` when any row is `stale` or has source `none`; then one row per account in snapshot order: name, `5h <x>%`, `7d <y>%`, `是` / `否 <available time>` / `否 —` / `未知`, `stale` row adds `⚠`; percent `null` shows `—`; at most 5 rows, extra shown as `+<k>`; available time today → `HH:mm`, else `周X HH:mm` | Manual: PRD sample snapshot → display matches sample; 7 accounts → 5 rows plus `+2` |
| FR-27 | Snapshot missing or unreadable → widget shows `quotaboard：没有数据` and a line `点这里刷新` | Manual: delete snapshot → that text; after click, data |
| FR-28 | timeline gives one entry each time, policy `.after(now + 5 minutes)`; a tap anywhere on the widget opens the host app | Manual: stop the LaunchAgent, edit the snapshot → widget changes within 10 min; tap → within ~30 s "n 分钟前" becomes just now |
| FR-29 | README documents each install-table step and rollback, the account-list sample, the `zsh -lc 'command -v claude codex'` check, the TASK-572 and TASK-573 conclusions; `make uninstall` removes the app, the `~/.local/bin/quotaboard` link and the plist, after `launchctl bootout` first | Install per README then `make uninstall` → `~/Applications/Quotaboard.app`, link, plist gone, `launchctl print gui/$(id -u)/com.windroc.quotaboard` fails |
| FR-31 | The tool writes only the state dir, `~/Library/Logs/quotaboard.log`, and the app, link and plist `make install` installs | — |
| NFR-1 | Reads no credential file or Keychain item, makes no network request itself | `grep` in Python and Swift code for `credentials.json`, `auth.json`, `security `, `keyring`, `oauth`, `refresh_token`, `anthropic.com`, `chatgpt.com`, `urllib`, `http.client`, `socket`, `URLSession`, `curl`, `/usr/bin/security`, `SecItem`, `kSecClass` → empty; child processes only `claude`, `codex`, `/bin/zsh`, `quotaboard` (extend the existing `make check` grep to Swift files) |
| NFR-2 | Swift only system frameworks; tests make no real probes | `/usr/bin/python3` full tests pass; `make` needs only CLT |
| NFR-3 | widget sandbox on, only the home-relative read-only exception for `/.local/state/quotaboard/` | `codesign -d --entitlements - <appex>` shows `com.apple.security.app-sandbox` and that one exception, no other file or network entitlement |
| NFR-4 | public repo: fixtures and README excerpts use placeholders for email, org, macOS login name, home path and account dir names | `git grep -i` for those → empty |

Testable logic: keep widget display formatting (row text, `+k`, relative time, `HH:mm`/`周X HH:mm`, `—` for null window/percent, header ⚠) in pure Swift functions that a CLT-built self-check (e.g. a `make` target compiling the formatter with a small assert-based test executable via `swiftc`) can exercise without a desktop; desktop-only behavior goes to manual checks.

## Conventions and git rules

- Follow the repo's existing conventions (README style, Makefile style, Python package layout, `tests/` with `unittest`); the repo has no CLAUDE.md/AGENTS.md.
- No mutation testing: never modify the source to see what happens: no manual or tool-driven mutation testing (mutmut etc.), not even briefly or in a throwaway copy that is then run; never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call such as `os.listdir`, leaving the code under test unmodified. Every brief to a sub-agent (producer, reviewer) carries this rule.
- Never touch, merge into or push any branch other than `TASK-586-widget-5`; never push to `main`; force-push only with `--force-with-lease`.
- Never run `make install`, `launchctl` or anything that changes the user's real `~/Applications`, `~/Library`, `~/.local` or desktop during the build: those are the user's manual checks. Building into the repo's `build/` dir and `make check` are fine. Never write user config (`~/.claude.json`, `~/.claude/settings*.json`, dotfiles).

Spec and plan doc stay where autopilot puts them; S7 copies them to where the repo keeps design docs; never `git add -f` them.

Work only in `<worktree>` on branch `TASK-586-widget-5`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After each task and each review round, run exactly `git -C <worktree> push -u origin TASK-586-widget-5`.

## Verify command

`make -C <worktree> check`

## Progress log

- S1 done: mode=stay, publish=none
- S2 done: spec .autopilot/widget-5-spec.md, check-spec OK
- S3 panel: core=[architecture-reviewer, spec-fitness-reviewer] +optional=[security-reviewer] transport=Workflow
- S3 r1: architecture=PASS spec-fitness=PASS security=PASS -> advance; adopted arch#1 arch#2 fit#2(manual) fit#3 sec#1 sec#2 fit#1(manual) into spec
- S4 done: 4 tasks
- S5 task 1 done: c48d6af red=swift-test compile failed without Snapshot.swift (78 errors)
- S5 task 2 done: 3dffc5f red=none (glue; make check)
- S5 task 3 done: e884cf4 red=none (hermetic install/uninstall run with temp HOME and fake pluginkit/launchctl/lsregister)
- S5 task 4 done: 4496847 red=none (doc)
- decision(panel): drop performance-reviewer: formatter runs once per 5 min over <=N rows, host is a one-shot process; no hot path
- S6 panel: core=[correctness-reviewer, doc-reviewer, requirement-fidelity-reviewer, verification-reviewer] +optional=[architecture-reviewer, code-quality-reviewer, test-reviewer] verification=local transport=Workflow
- S6 r1 @449684723ae3d41108474109175ef6d1ba92ff0d: correctness=PASS doc=PASS requirement-fidelity=PASS verification=PASS (command=make check, exit code=0, tests=79 python + swift-test ok, failures=0) architecture=PASS code-quality=PASS test=PASS -> converged
- Residual NON-BLOCKING: correctness#1, correctness#2, doc#1, architecture#1, code-quality#1 (deferred to manager/user)
- S7: spec and plan copied (paths sanitized) to docs/design/TASK-586-widget-snapshot-{spec,plan}.md

## Review items

S3 r1 NON-BLOCKING: architecture#1 rename Window->UsageWindow (adopted); architecture#2 DisplayRow struct (adopted); spec-fitness#1 AC3 observable check (adopted manual); spec-fitness#2 7-account overflow manual check (adopted); spec-fitness#3 zero accounts (adopted: header 0/0, no rows); security#1 $${HOME:?} guard (adopted); security#2 link ownership via readlink (adopted).

S6 r1 NON-BLOCKING:
- correctness#1: macos/Host/main.swift:42-46: the 40 s SIGTERM/SIGKILL goes only to the exec'd python. quotaboard/codex.py:120-122 starts `codex app-server` with start_new_session=True, and python's default SIGTERM skips `finally: _stop(proc)` (codex.py:131-132). Case: 4 codex accounts with a hung app-server need about 4 x (10 s TIMEOUT + 1 s wait) = 44 s. At 40 s python dies mid-probe and the app-server is orphaned unless it exits on stdin EOF. store.write (cli.py:27) never runs, so the healthy accounts' results are lost too. Fix: have the CLI turn SIGTERM into SystemExit (signal.signal(SIGTERM, lambda *a: sys.exit(143))) so `finally` still kills the group.
- correctness#2: macos/Host/main.swift:64-68: AC4 says two hosts started together leave exactly one, but that is not guaranteed. A launchd-spawned `--scheduled` host only appears in NSRunningApplication after NSApplication checks in, which happens after this check runs. Case: a launchd start and a widget `open` within milliseconds both pass the check and both run collect. This is harmless because store.py:71-73 flock serializes the writes. Either relax AC4 or note this in spec D2.
- doc#1: README.md Install section: '⚠ marks ... an account that could not be read' is imprecise; per macos/Widget/Snapshot.swift:48-55 a row gets ⚠ only when stale, while source none adds ⚠ to the header line only.
- architecture#1: macos/Widget/Snapshot.swift:20 Snapshot ignores the `schema` key that quotaboard/store.py:12,91 writes (SCHEMA = 1), so the Python-to-Swift contract has no version check at its edge. If a future schema 2 renames or retypes a field that is still optional, decoding still succeeds and the widget shows wrong cells instead of the no-data text. Decode `schema` and make loadSnapshot return nil unless it is 1.
- code-quality#1: macos/Widget/QuotaboardWidget.swift: `ForEach(d.rows, id: \.name)` assumes unique account names; two accounts with the same name would collide. Use the row index or a unique id.

## Notes

- No CI workflow; publish=none; verification=local. GNU make 3.81, swiftc 6.4.
- S7 copy of spec/plan to docs/design/ must replace absolute /Users/... paths with placeholders (NFR-4; TASK-585 hit this).
- Verify command: `make check` (runs make test, swift-test, app, lint, codesign, entitlements diff, NFR-1 grep).
- Spike build recipe: spike/clt-widget/Makefile (swiftc -parse-as-library -application-extension -Xlinker -e -Xlinker _NSExtensionMain).


## Task list

Spec: <worktree>/.autopilot/widget-5-spec.md

Global Constraints: host id `com.windroc.quotaboard`, exe `Quotaboard`; widget id `com.windroc.quotaboard.widget`, `QuotaboardWidget.appex`, kind `Quotaboard`; LaunchAgent label `com.windroc.quotaboard`, StartInterval 300; log `~/Library/Logs/quotaboard.log` 0600; state `~/.local/state/quotaboard/snapshot.json`; make 3.81 (no .SHELLFLAGS); `$${HOME:?}` in every home path; Swift system frameworks only; no mutation testing; never run install/launchctl during the build.

### Task 1: widget formatter and Swift self-test
- Files: macos/Widget/Snapshot.swift, macos/Tests/main.swift, Makefile (`swift-test`, `clean`), .gitignore unchanged (build/ already ignored).
- Produces: `UsageWindow`, `Row`, `Snapshot`, `DisplayRow`, `Display`, `loadSnapshot(path:) -> Snapshot?`, `display(_:now:calendar:) -> Display` (spec Design).
- Tests first (macos/Tests/main.swift): AC9-AC13 cases: header_sample, header_warn_none, relative_times, rows_sample, null_window, null_percent, availability_cells, time_today, time_other_day, overflow_5_6_7, zero_accounts, load_missing, load_garbage, load_wrong_shape, load_valid.
- Checks: `make swift-test`.
- Commit: `TASK-586: widget snapshot formatter with Swift self-test`

### Task 2: host app, widget extension, LaunchAgent template, `make app` and `make check`
- Files: macos/Host/main.swift, macos/Host/Info.plist, macos/Widget/QuotaboardWidget.swift, macos/Widget/Info.plist, macos/Widget/widget.entitlements, macos/com.windroc.quotaboard.plist, Makefile (`app`, `check`).
- Consumes: Task 1 API.
- Tests: none new (AppKit/WidgetKit glue; manual checks); `make check` lints plists, verifies signature, diffs entitlements, greps NFR-1 strings incl. Swift.
- Checks: `make check`.
- Commit: `TASK-586: Quotaboard host app, widget and LaunchAgent template`

### Task 3: `make install` and `make uninstall`
- Files: Makefile.
- Behaviour: AC6, AC7, AC8.
- Tests: none run (would touch the real home); `make -n install` / `make -n uninstall` dry-run review only.
- Checks: `make -n install`, `make -n uninstall`, `make check`.
- Commit: `TASK-586: make install and uninstall`

### Task 4: README install guide
- Files: README.md.
- Behaviour: AC17.
- Checks: none (doc).
- Commit: `TASK-586: README install, rollback and spike conclusions`
