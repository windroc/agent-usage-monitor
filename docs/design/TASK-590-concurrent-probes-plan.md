Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-590-build base_ref=1787bde2a780e97f39de3a2d6720368147875de6 review_round=1 input_sha=193565b15c59

## Input

# Requirement: TASK-590 并发探测与配置隔离 (windroc/agent-usage-monitor)

Precedence: the user's requirements since the last build (none) > the user's instructions below > the PRD; within each, newer > older. Linked documents are context, never requirements.

## The user's instructions (requirements)

Parent TASK-561 M1 PRD (FR/NFR ids refer to it): https://github.com/windroc/private_docs/blob/main/Product%20Design/2026-10-16-2312-TASK-561-m1-macos-widget.md

What to build: with several accounts, probe each account concurrently; a stuck probe affects only its own row; the tool writes into no account directory.

Acceptance criteria:
- FR-14: one fake app-server and one fake `claude` hang, the others behave → the healthy rows have values; the whole `collect --probe` run takes ≤ 35 s.
- FR-31: before vs after running `collect` and `collect --probe`, the mtime of every `settings.json`, `config.toml` in the account directories and of the account list (accounts.json) is unchanged. (Only exception allowed by the PRD: FR-9 cleanup of `<dir>/projects/<probe dir name>/*.jsonl` when cleanup is on.)
- NFR-2: tests use fake executables; the full suite passes under `/usr/bin/python3` (3.9, stdlib only).

Carried over from TASK-585:
- The Codex probe does not close the app-server's `proc.stdout` after probing (`make test` prints 30 `ResourceWarning: unclosed file`). Close it as part of the concurrency work; `make test` shows no ResourceWarning.

Carried over from TASK-586 (PR #5 correctness#1):
- The host's 40 s timeout SIGTERMs only python; python's default SIGTERM handling skips `finally`, so `codex app-server` (own session) is orphaned and the healthy accounts' results are not written to the snapshot. Make the CLI turn SIGTERM into `SystemExit` (e.g. `signal.signal(SIGTERM, lambda *a: sys.exit(143))`) so `finally` still kills child process groups; add a test. After concurrency the whole run is ≤ 35 s, so normally the host's 40 s is never reached.

Carried over from TASK-587:
- PR #6 correctness#1: when `claude` has exited but its child still holds stdout, `_run` drops the output already read on `TimeoutExpired` and after 30 s records a timeout instead of success. Fix and add a test.
- `claude`/`codex` not found (commander observed, 2026-10-17): the host runs `/bin/zsh -l -c`; a login non-interactive shell does not read `~/.zshrc`. On this Mac both CLIs live in `~/.local/bin` (official install location) and PATH adds it only in `.zshrc`, so `collect` reports `cannot start claude/codex: ENOENT`. Do not change the user's shell config: when `~/.local/bin` is not on PATH, `collect` appends it to the end; add a test; the README's `command -v` check explains this.

## PRD context (relevant rows, verbatim excerpts)
- FR-14 并发: 各账号并发探测；一个卡住的探测只影响自己那一行。
- FR-31 配置隔离: 工具只写状态目录、`~/Library/Logs/quotaboard.log`，以及 `make install` 装的 app、链接和 plist；不写账号目录和账号清单，FR-9 清理开启时删除的 `<dir>/projects/<probe 目录名>/*.jsonl` 和清空后的该目录除外。
- FR-9: Claude probe timeout 30 s; FR-12: Codex app-server timeout 10 s, close the child at the end, no leftover app-server process.
- FR-6: every snapshot write goes through the single store function (fcntl lock, re-read, merge by name, mkstemp + rename).
- NFR-1: no credential files/Keychain, no own network requests; subprocesses only `claude`, `codex`, `/bin/zsh`, `quotaboard`.
- NFR-2: collection uses only the Python 3.9 standard library; tests never run real probes, `claude`/`codex` are fake executables.
- NFR-4: public repo; fixtures/README must not contain the user's email, org, macOS login name, `/Users/<user>` home paths or account dir names.

## Conventions and git rules
- Write code, docs and commits in the target repo's conventions (no CLAUDE.md/AGENTS.md; follow the existing code style, `Makefile` `make test`, docs/design/ for design docs). Default branch `main`.
- No mutation testing: while building, reviewing or testing, never modify the source to see what happens: no manual or tool-driven mutation testing (mutmut etc.), not even briefly or in a throwaway copy that is then run; never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call such as `os.listdir`, leaving the code under test unmodified. Every brief to a sub-agent (producer, reviewer) carries this rule.
- Push only branch `TASK-590-build`; force-push only with `--force-with-lease`. Never merge into or otherwise touch any other branch.

The plan doc stays where autopilot puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

Work only in `<WORKTREE>` on branch `TASK-590-build`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <WORKTREE> push -u origin TASK-590-build`.

## Verify

Verify command: `make -C <WORKTREE> check` (runs `/usr/bin/python3 -m unittest discover -s tests -t .` then the NFR-1 grep); also confirm its output has no `ResourceWarning`.

## Progress log

- S1: mode=stay, branch TASK-590-build, base_ref 1787bde.
- decision(tests-real-time): FR-14 end-to-end test runs the real 10 s / 30 s timeouts through `bin/quotaboard` (the literal acceptance check, ~31 s); no test-only timeout env var.
- decision(sigterm): SIGTERM -> SystemExit(143) in main; collect catches it while waiting, kills every live probe process group (registry in proc.py, which then refuses new spawns), still writes the snapshot with finished rows, then re-raises.
- decision(run-exit): claude `_run` polls in 0.5 s slices; once the leader has exited, one more slice drains the pipes, then uses what was read with the leader's exit code.
- S5 task 1 done: 044dba2 red=1 (test_pipes_closed)
- S5 task 2 done: a72594c red=1 (test_exited_claude_whose_child_holds_stdout)
- S5 task 3 done: 1cba2ba red=1 (test_stuck_probes_hold_up_only_their_rows; test_account_files_untouched passed before: FR-31 already held)
- S5 task 4 done: 30ba80f red=1 (test_sigterm_stops_probes_and_writes_snapshot: -15)
- S5 task 5 done: 17e280f red=1 (test_local_bin_appended_to_path)
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=local transport=Workflow
- S6 r1 @17e280fdce9c8757397eff1e0506374c5ad69a48: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (command=make check, exit code=0, tests=124, failures=0, ResourceWarning=0) -> converged
- residual NON-BLOCKING: correctness#1, correctness#2 (see Review items)
- S7: plan doc copied to docs/design/TASK-590-concurrent-probes-plan.md (paths replaced by placeholders, NFR-4)

## Review items

### r1 (@17e280f)
BLOCKING: none.
NON-BLOCKING:
- correctness#1: quotaboard/cli.py:46-50: a SIGTERM that lands after the ThreadPoolExecutor starts but before `try: wait(...)` (while the pool.submit loop runs), or a second SIGTERM during the `future.result()` loop, raises SystemExit outside the except. Executor __exit__ then waits for the probes (up to 30 s) without calling kill_all, and no snapshot is written. Fix: put the submit loop and the result loop inside the try (or call kill_all in a finally) so every SystemExit reaches kill_all.
- correctness#2: quotaboard/claude.py:133 with proc.py:17: claude finishes with exit 0 and unrecognized output, then SIGTERM runs kill_all before refresh calls _version. popen then raises ECANCELED, _version returns None, and the row is written with usage_disabled_version="unknown" because of shutdown, not because of claude. It clears on the next run, but treating ECANCELED as kept with no field change would avoid recording a false disable.
- verification (evidence): `make -C <worktree> check`: exit 0; Ran 124 tests, OK, 61 s; NFR-1 grep no matches; 0 ResourceWarning; HEAD and status unchanged.

## Notes

- Tests drive `bin/quotaboard` via tests/helpers.py `Env.run` (real subprocess, real timeouts); fake codex/claude in helpers.py configured by JSON files.
- Only the default Claude account (~/.claude) is probed (`claude.is_default`, TASK-583).
- No CI workflow (.github absent): verification local.

## Task list

Global Constraints: Python 3.9 stdlib only; codex timeout 10 s (`codex.TIMEOUT`), claude 30 s (`claude.TIMEOUT`); whole `collect --probe` ≤ 35 s; exit code on SIGTERM 143; `~/.local/bin` = `accounts.home(environ) + "/.local/bin"`, appended only when absent from PATH entries. Data shape: collect builds one job per probed account (codex accounts, default Claude account with `--probe`), each returning `(name, fields|None, kept: bool, message|None)`; results merged into the existing `updates` dict and `failed` set in account-list order (stderr lines keep account order).

### Task 1: close probe pipes in proc.stop
- Files: quotaboard/proc.py, tests/test_codex.py.
- Produces: `proc.stop(proc)` also closes `proc.stdout`, `proc.stderr` after reaping.
- Tests first: codex probe success and timeout under `warnings.catch_warnings(record=True)` + `gc.collect()` → no ResourceWarning.
- Checks: `/usr/bin/python3 -W error::ResourceWarning -m unittest tests.test_codex tests.test_claude`.
- Commit: `fix(proc): close probe pipes when stopping a probe`

### Task 2: claude _run keeps output when claude exits before its child
- Files: quotaboard/claude.py, tests/helpers.py (fake claude `child_holds_stdout`), tests/test_claude.py.
- Tests first: fake claude prints USAGE, leaves a child holding stdout, exits 0 → `refresh(timeout=5)` returns source `usage` within < 4 s; child killed.
- Checks: `/usr/bin/python3 -m unittest tests.test_claude`.
- Commit: `fix(claude): keep output when claude exits but its child holds stdout`

### Task 3: probe accounts concurrently (FR-14, FR-31)
- Files: quotaboard/cli.py, tests/test_cli.py.
- Consumes: `codex.probe`, `claude.refresh` unchanged signatures.
- Tests first: one hanging app-server, one healthy codex, hanging fake claude (default account) → healthy row `app-server` with values, others `cache`/`none`, elapsed ≤ 35 s; FR-31: settings.json, config.toml in each account dir and accounts.json keep mtime_ns across `collect` and `collect --probe`.
- Checks: `/usr/bin/python3 -m unittest tests.test_cli`.
- Commit: `feat(collect): probe accounts concurrently`

### Task 4: SIGTERM ends probes and still writes the snapshot
- Files: quotaboard/proc.py (live-process registry: `popen`, `kill_all`), quotaboard/codex.py, quotaboard/claude.py (spawn via `procs.popen`), quotaboard/cli.py, tests/test_cli.py.
- Tests first: hanging app-server (spawns child) + healthy codex; SIGTERM python after the healthy row is probed → exit 143 within a few s, no app-server/child alive, snapshot has the healthy row `app-server`.
- Checks: `/usr/bin/python3 -m unittest tests.test_cli tests.test_codex tests.test_claude`.
- Commit: `fix(cli): turn SIGTERM into SystemExit and stop probes`

### Task 5: append ~/.local/bin to PATH when missing
- Files: quotaboard/cli.py, tests/test_cli.py, README.md.
- Tests first: fake codex only in `$HOME/.local/bin`, PATH without it → row `app-server`; PATH already containing it → not duplicated (fake records PATH).
- Checks: `/usr/bin/python3 -m unittest tests.test_cli`.
- Commit: `fix(collect): find claude and codex in ~/.local/bin`
