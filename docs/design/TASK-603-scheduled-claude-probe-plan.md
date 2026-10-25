Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-603-claude-5 base_ref=c6ab36c8a9e861b16a1bf6164fea2eff2fdb14ee review_round=1 input_sha=051939481e34

## Input

## Requirement (TASK-603, windroc/agent-usage-monitor)

ENG: 定时采集也读 Claude 用量（每 5 分钟）. Parent: TASK-561 (M1 PRD; FR/NFR ids refer to it).

PRD revision (the user, 2026-10-17): the background scheduled collect also reads Claude usage, every 5 minutes, like Codex; no longer only when the widget is clicked. FR-8 becomes: every `collect` probes the Claude account (FR-11 throttle still applies). The user accepts two known risks: (1) the subscription login is meant for "ordinary use" (https://code.claude.com/docs/en/legal-and-compliance); (2) a future `claude` that sends `-p /usage` to the model as a prompt would spend quota every 5 minutes.

### What to build
The scheduled collect that the LaunchAgent starts every 5 minutes (`macos/com.windroc.quotaboard.plist`, StartInterval 300, host `--scheduled`) also reads the default Claude account's `/usage`, so the widget's Claude numbers update without a click. Clicking the widget still collects immediately.

### Acceptance criteria
- Scheduled collect (host `--scheduled`) also probes the default Claude account; command, environment and arguments of the probe unchanged (FR-9).
- With the LaunchAgent interval at 300 s, every scheduled collect probes: the FR-11 throttle (`quotaboard/claude.py` THROTTLE / `fetched_at` check) must not make it probe only every other run (e.g. skipped because `fetched_at` is a few seconds short of 300 s old). Test: two collects 300 s apart both invoke the fake `claude`.
- Widget-click behavior unchanged; repeated clicks within the throttle window do not re-probe.
- Non-default Claude accounts still handled as TASK-589 left them; do not touch that here.
- Smallest change; delete branches/flags that become unused (e.g. `--probe` / `probe=` plumbing in `quotaboard/cli.py` and `macos/Host/main.swift` if no longer needed, with their tests and docs). README "How it works", Principles and the Claude section no longer say Claude is read only on click; say it is read every 5 minutes, and state the two risks above.
- NFR-1, NFR-2 (tests use only a fake `claude`), NFR-4.

### Conventions and git rules
- Follow the repo's conventions (its CLAUDE.md / AGENTS.md if present, README, existing code style). Default branch: `main`.
- No mutation testing: while building, reviewing or testing, never modify the source to see what happens: no manual or tool-driven mutation testing (mutmut etc.), not even briefly or in a throwaway copy that is then run; never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call such as `os.listdir`, leaving the code under test unmodified. Every brief to a sub-agent (producer, reviewer) carries this rule.
- Push only branch `TASK-603-claude-5`; force-push only with `--force-with-lease`. Never merge into or touch any other branch.

### Docs
The plan doc stays where autopilot puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

Work only in `<WORKTREE>` on branch `TASK-603-claude-5`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <WORKTREE> push -u origin TASK-603-claude-5`.

## Verify

Verify command: `make -C <WORKTREE> check`

## Progress log

- S1: mode=stay, worktree on TASK-603-claude-5 at c6ab36c.
- decision(publish): publish=none (no .github workflows); verification=local.
- decision(throttle): THROTTLE 300 -> 240: keeps FR-11 for every collect and click bursts, margin for launchd/zsh startup jitter; scheduled-only bypass rejected (needs flag plumbing the requirement asks to delete).
- decision(flags): drop --probe (cli, host) and --scheduled (host, plist); an installed old host passing --probe to the new CLI exits 2 until `make install` is rerun (note in PR).
- decision(test placement): collect-level 300 s-apart test written in Task 2 (no --probe churn).
- S5 task 1 done: 7eb6392 red=test_throttle (NOW-240, NOW-299 subtests)
- S5 task 2 done: e3ae52b red=10 (CollectProbeTest x7, test_account_files_untouched, test_local_bin_appended_to_path x2)
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=local transport=Workflow
- S6 r1 @e3ae52b8aec5d05bb8c055d9d2c95b97b77b75e5: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (command=make check, exit code=0, tests=125, failures=0) -> converged
- residual NON-BLOCKING: correctness#1 (upgrade gap: installed host passes --probe until `make install`), correctness#2 (overlapping click + scheduled hosts can both probe claude), requirement-fidelity#1 (README Claude section does not say every 5 minutes)

## Review items

- correctness#1 NON-BLOCKING: Upgrade gap. Makefile:43 symlinks ~/.local/bin/quotaboard to the repo's bin/quotaboard, so a git pull alone updates the CLI. An already-installed host still runs `collect --probe`, which the parser now rejects (quotaboard/cli.py:71) with exit 2. Every widget click then collects nothing until `make install` is rerun. Fix: mention the reinstall in the README install section, not only in the PR.
- correctness#2 NON-BLOCKING: Concurrent probes. macos/com.windroc.quotaboard.plist starts the executable directly, so a LaunchAgent run that fires while a click-started host is still collecting can run a second process. Both read the same old fetched_at (quotaboard/cli.py:33, outside snapshot.lock), so both run `claude -p /usage`. This could already happen for codex; it now happens for claude too. Optional fix: re-read the row under the lock, or document the double probe as accepted.
- requirement-fidelity#1 NON-BLOCKING: [req-drop] README.md:81 Claude section reads 'Claude limits come from `collect`, which runs `claude -p /usage`...' but never says when that runs. The requirement asks the Claude section to say Claude is read every 5 minutes; today that is stated only in How it works (README.md:19). Add 'every 5 minutes (LaunchAgent) and on a widget click' to the README.md:81 sentence.
- verification#1 NON-BLOCKING: `make check` exit 0, 125 tests, 0 failed; swift-test ok, app build, codesign, NFR-1 grep, plutil lint, entitlements diff; 'check ok'. HEAD and status unchanged.

## Notes

- No AGENTS.md / CLAUDE.md; no .github CI. Unit tests: `make test` (`/usr/bin/python3 -m unittest discover -s tests -t .`); `make check` = test + swift-test + app + NFR-1 grep + plist lint + codesign.
- Gate today: `quotaboard/cli.py` collect(environ, probe=False) reads the snapshot and adds `claude.refresh` jobs only when probe; `main` passes `--probe`. Host `macos/Host/main.swift` passes ` --probe` unless argv has `--scheduled`; `macos/com.windroc.quotaboard.plist` passes `--scheduled`, StartInterval 300.
- Throttle: `quotaboard/claude.py` THROTTLE=300, `refresh` skips when `0 <= now - fetched_at < THROTTLE`; `fetched_at` = `now` at refresh start, so two scheduled runs ~300 s apart can differ by 299 s and the second is skipped.
- Non-default Claude accounts: `claude.is_default`; untouched (TASK-589).

## Task list

Global Constraints: Python 3.9 stdlib only; `claude.THROTTLE = 240` (below the LaunchAgent's 300 s StartInterval, above any click burst); every `collect` probes the default Claude account; no `--probe` / `--scheduled` flag remains anywhere (cli, host, plist, tests, README); FR-9 command, env and args (`claude.ARGS`, `_environment`) unchanged; tests use only fake `claude` (NFR-2). Data shape unchanged.

### Task 1: Throttle below the 5-minute schedule

- Files: `quotaboard/claude.py`, `tests/test_claude.py`, `README.md` (the "less than 5 minutes ago is skipped" sentence).
- Produces: `claude.THROTTLE = 240`, comment why (LaunchAgent 300 s; `fetched_at` jitter must not skip a scheduled run).
- Tests first: refresh with `fetched_at` NOW-299 and NOW-240 → probed; NOW-239 and NOW-60 → not probed (no call). Collect-level: two collects whose `now` differ by 300 s (or fetched_at rewritten to 299 s ago between runs) both call the fake `claude`.
- Checks: `make -C <WORKTREE> test`.
- Commit: `Claude throttle 240 s so every 5-minute run probes`

### Task 2: Every collect probes the default Claude account

- Files: `quotaboard/cli.py` (drop `probe` param, `--probe` arg and gate), `macos/Host/main.swift` (drop `probe:` param, `--scheduled` check, ` --probe`; header comment), `macos/com.windroc.quotaboard.plist` (drop `--scheduled`), `tests/test_claude.py`, `tests/test_cli.py` (drop `--probe` args; FR-8 test now: plain `collect` calls fake claude; repeated collect within throttle → no second call), `README.md` (status line, How it works diagram "(click only)", Codex/Claude bullet, Principles: risks, Development `--probe` line, widget click sentence, Claude section "only from `collect --probe`").
- README must state Claude is read every 5 minutes and the two accepted risks: subscription login is for "ordinary use" (https://code.claude.com/docs/en/legal-and-compliance); a future `claude` that sends `-p /usage` to the model would spend quota every 5 minutes.
- Tests first: `collect()` with no args → fake claude called for default account only; second immediate `collect()` → no new call.
- Checks: `make -C <WORKTREE> test`, `make -C <WORKTREE> swift-test`, `make -C <WORKTREE> app`.
- Commit: `Every collect probes the default Claude account`
