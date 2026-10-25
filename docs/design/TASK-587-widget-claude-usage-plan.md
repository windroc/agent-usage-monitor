Rules: <AUTOPILOT>/skills/build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=S7 worktree=<WORKTREE> branch=TASK-587-widget-claude-usage base_ref=b0229b4f3c72a69d8548dae041f60e53e586b066 review_round=1 input_sha=e7b9851e9545

## Input

TASK-587: 点 widget 刷新默认 Claude 账号 /usage 探测 (repo windroc/agent-usage-monitor)

## Requirements (precedence: the user's instructions below > the PRD; newer > older)

### The user's instructions (TASK-587)

`quotaboard collect --probe`（点 widget 时 host app 跑的就是它）为默认 Claude 账号跑 `/usage` 探测，快照里 Claude 行有 5h、7d 的百分比和重置时间，来源 `usage`。移植 CodexBar 的探测和解析。非默认 Claude 账号（`dir` 不是 `~/.claude`）这一张先不探测，保留快照里的值，留给后续 ticket（看 TASK-583 的结论）。

Acceptance criteria:
- FR-8：只有 `--probe` 才探测 Claude；没有时 Claude 行保留快照里的值。
- FR-9（默认账号）：命令、环境和参数按 TASK-572 报告（repo 里的 `docs/spikes/TASK-572-claude-usage.md`），含 `--model sonnet --effort low`。**默认账号不设 `CLAUDE_CONFIG_DIR`，从环境里移除**：TASK-572 实测显式设成 `~/.claude` 会显示未登录，这一点修正了 PRD FR-9 的「一律设 `CLAUDE_CONFIG_DIR=<dir>`」。探测目录 `probe/` 和 `settings.local.json` 按 FR-9；TASK-572 实测没有写会话文件，所以不启用清理。
- FR-10：移植 `ClaudeStatusProbe.parse` 和 `makeSnapshot` 的换算，用 TASK-572 的两份 fixture（`tests/fixtures/claude-usage/`）和 CodexBar 测试样例测试；五种错误；`unrecognized` 按版本停探测；移植文件头和 `THIRD_PARTY_NOTICES.md` 保留 CodexBar 的 MIT 声明。
- FR-11：`fetched_at` 不到 5 分钟不探测。
- NFR-1、NFR-2：测试只用假 `claude`，不发真实探测；NFR-4：fixture 脱敏。

Carried over from TASK-585 (PR #4 non-blocking review items), also required:
- 加 `store.snapshot_path(directory)`（或让 `read()` 收目录），FR-11 节流读 Claude 行的 `fetched_at` 时用它，不要再写一遍 `snapshot.json`。
- CLI 保留 `parse_args` 的结果，把 `args.probe` 传进 `collect`（FR-8）。
- 窗口名现在写在三处（`codex.WINDOWS`、`derive.WINDOWS`、`store.default_row`）；加 Claude 的窗口映射前，改成都从 `derive.WINDOWS` 派生。

### The PRD

Relevant excerpt (verbatim FR/NFR rows) of the parent PRD TASK-561 "用量监控 M1 macOS widget" (`windroc/private_docs` › `Product Design/2026-10-16-2312-TASK-561-m1-macos-widget.md`) is in `<WORKDIR>/tmp/prd-TASK-561.md`; read it in full. Scope for this build: FR-8, FR-9 (default account only, as corrected above), FR-10, FR-11, plus NFR-1, NFR-2, NFR-4 for the new code. Not in scope: FR-14 concurrency, FR-30 tap, host app/widget, non-default Claude accounts. CodexBar source to port (MIT): https://github.com/steipete/CodexBar at commit 6480977b47f6e4ffd5dcaae1cb0c7fdf34ee449e (`Sources/CodexBarCore/Providers/Claude/ClaudeStatusProbe.swift`, `ClaudeUsageFetcher.swift` makeSnapshot, `ClaudeCLISession.swift` env, and its tests under `Tests/`); fetch read-only via `gh api` or raw.githubusercontent.com.

## Conventions and git rules

- Follow the repo's existing conventions (no CLAUDE.md/AGENTS.md; match `quotaboard/*.py`, `tests/*`, `docs/design/` style; Python 3.9 stdlib only; tests run with `/usr/bin/python3`). Default branch: `main`.
- **No mutation testing**, whatever a spec, plan or reviewer asks: while building, reviewing or testing, never modify the source to see what happens: no manual or tool-driven mutation testing (mutmut etc.), not even briefly or in a throwaway copy that is then run; never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call such as `os.listdir`, leaving the code under test unmodified. Every brief to a sub-agent (producer, reviewer) carries this rule.
- Never run a real `claude` or `codex` (no real probes); tests use fake executables only.
- Push only branch `TASK-587-widget-claude-usage`; force-push only with `--force-with-lease`; never merge into or touch any other branch.

Spec and plan doc stay where autopilot puts them; S7 copies them to where the repo keeps design docs; never `git add -f` them.

Work only in `<WORKTREE>` on branch `TASK-587-widget-claude-usage`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After each task and review round, run exactly `git -C <WORKTREE> push -u origin TASK-587-widget-claude-usage`.

## Verify

`make -C <WORKTREE> check` (runs `make test` then the NFR-1 grep) with /usr/bin/python3.
CI checks: []

## Progress log

- S1: mode=stay publish=none
- S2: spec written, check-spec OK
- S3 panel: core=[architecture-reviewer, spec-fitness-reviewer] +optional=[security-reviewer] transport=Workflow
- S3 r1: architecture=PASS spec-fitness=PASS security=PASS -> advance; non-blockers architecture#1-3, spec-fitness#1-3, security#1-3 folded into spec as clarifications (proc.py shared stop/reason, key mapping by minutes, future fetched_at probes, D10 unlocked read, version sentinel "unknown", --version launch, version validation)
- S5 task 1 done: d5e49cb red=none (mechanical)
- S5 task 2 done: b47c9b5 red=2 (test_snapshot_path, test_ensure_dir_creates_0700)
- S5 task 3 done: 1183b4a red=10 (module missing)
- S5 task 4 done: 569cbdb red=none (parser written before its tests; CodexBar samples green on first run, 44 cases)
- S5 task 5 done: d5a6edb red=11 (module missing)
- S5 task 6 done: 06408cd red=5 (CollectProbeTest)
- decision(panel): performance-reviewer dropped: no loops over large data; runtime is subprocess-bound (probe timeouts)
- S6 panel: core=[correctness-reviewer, doc-reviewer, requirement-fidelity-reviewer, verification-reviewer] +optional=[architecture-reviewer, code-quality-reviewer, test-reviewer] verification=local transport=Workflow
- S6 r1 @06408cd: correctness=PASS doc=PASS requirement-fidelity=PASS verification=PASS (command=make check, exit code=0, tests=114, failures=0) architecture=PASS code-quality=PASS test=PASS -> advance to S7
- residual NON-BLOCKING: correctness#1-4, doc#1, requirement-fidelity#1-2, architecture#1-2, code-quality#1-4, test#1-2 (see Review items)

## Review items

S3 r1 (all NON-BLOCKING):
- architecture#1: share codex._reason/_stop with the Claude probe; Claude kills group only on timeout.
- architecture#2: probes have different contracts (codex raises; claude.refresh returns triple); unify for FR-14.
- architecture#3: make_windows keys must come from derive.WINDOWS by minutes, not literal names.
- spec-fitness#1: future fetched_at blocks probe until clock catches up; state rule.
- spec-fitness#2: same as architecture#3.
- spec-fitness#3: throttle reads snapshot outside lock; record decision.
- security#1: failing --version after unrecognized records nothing -> repeated spend; use sentinel.
- security#2: --version must use probe launch (DEVNULL stdin, new session, killpg).
- security#3: validate/cap --version output before storing/printing.

S6 r1 (all NON-BLOCKING):
- correctness#1: claude.py:69-70 output discarded on TimeoutExpired even if claude exited but a child holds stdout -> timeout after 30 s instead of success.
- correctness#2: claude.py _prepare OSError (e.g. <state>/probe is a file) uncaught -> collect traceback, snapshot (incl. Codex updates) not written.
- correctness#3: _version requires exactly one stdout line; spec AC11 says first line -> multi-line version output stored as "unknown".
- correctness#4: folder-trust regex case-sensitive; CodexBar extractFirst is case-insensitive.
- doc#1: TASK-585 design docs still say --probe does nothing (historical, ticket-scoped).
- requirement-fidelity#1: same as correctness#3.
- requirement-fidelity#2: CodexBar samples run as one data-driven test with subTests, not one method per sample as D3/AC8 say.
- architecture#1: minutes->key inverse built twice (codex.BY_MINUTES, claude_usage.make_windows) and 300/10080 hardcoded in make_windows; export derive.BY_MINUTES.
- architecture#2: claude_usage not pure: local_zone reads TZ and /etc/localtime; pass fallback zone in.
- code-quality#1: claude_usage.KINDS unused.
- code-quality#2: same as architecture#1.
- code-quality#3: refresh classification flow could return early.
- code-quality#4: _version length check redundant with regex.
- test#1: Env PATH includes /usr/bin:/bin, so a real claude there could run in tests without a fake.
- test#2: same as requirement-fidelity#2.

## Notes

- Repo: no CI, no CLAUDE.md/AGENTS.md. Tests: `make -C <worktree> test` (`/usr/bin/python3 -m unittest discover -s tests -t .`); `make check` adds NFR-1 grep (case-sensitive: `oauth`, `security `, `socket`, `curl`, ... over quotaboard/ tests/ bin/quotaboard).
- Single test: `/usr/bin/python3 -m unittest tests.test_x -v` run with cwd = worktree (use `make -C`, or `cd` not allowed by delegate rule -> use `/usr/bin/python3 -m unittest discover -s <worktree>/tests -t <worktree> -p 'test_x.py'`).
- tests/helpers.py: `Env` (temp HOME/config/state, PATH fakes-only + /usr/bin:/bin, LANG=C), FAKE_CODEX pattern; store.write(directory, accounts, threshold, updates, failed, now).
- CodexBar sources cached at <WORKDIR>/tmp/codexbar/ (Swift + tests/ + LICENSE).
- TASK-572 fixture started_utc A1 2026-10-17T05:07:24.915359Z; 5h reset 2026-10-17 04:39 America/New_York = 1792226340.
- CodexBar parse samples skipped (D3), 19:
  - StatusProbeTests.swift::parse claude status with plan and ansi noise: reason: asserts only loginMethod / accountEmail / accountOrganization (not ported). Parse must just not raise (text has Current session 10% used, all models 20%
  - StatusProbeTests.swift::parse claude status with bracket plan noise no esc: reason: asserts only loginMethod (not ported). Parse must not raise (session 10% used / all models 20% used present).
  - ClaudeCLIScopedWeeklyUsageTests.swift::CLI usage surfaces Fable scoped weekly limit: reason: result goes through ClaudeUsageFetcher.loadLatestUsage with a fetch override; asserts only extraRateWindows (Fable / Example Model) and opus == nil (not
  - ClaudeCLIScopedWeeklyUsageTests.swift::compact scoped weekly label is parsed: reason: asserts only extraRateWindows (not ported). Parse must not raise ('Current session / 9% used' present; session 91 not asserted).
  - ClaudeCLIScopedWeeklyUsageTests.swift::overlapping scoped model names do not cross panel boundaries: reason: asserts only extraRateWindows (not ported). Parse must not raise (session 9% used present).
  - ClaudeCLIScopedWeeklyUsageTests.swift::informational Sonnet prose does not duplicate a scoped limit: reason: asserts only opusPercentLeft == nil and extraRateWindows (not ported).
  - ClaudeCLIScopedWeeklyUsageTests.swift::Sonnet prefixed scoped model does not become legacy quota: reason: asserts only opusPercentLeft == nil and extraRateWindows (not ported).
  - ClaudeCLIScopedWeeklyUsageTests.swift::later complete scoped panel replaces partial redraw: reason: asserts only extraRateWindows count / usedPercent / resetDescription (not ported).
  - ClaudeCLIScopedWeeklyUsageTests.swift::incomplete Opus panel does not consume prefixed scoped percentage: reason: asserts only opusPercentLeft == nil and extraRateWindows (not ported).
  - ClaudeCLIScopedWeeklyUsageTests.swift::later complete scoped panel replaces earlier complete value: reason: asserts only extraRateWindows (not ported).
  - ClaudeCLIScreenProbeTests.swift::differential redraw preserves the scoped weekly quota and reset spacing: reason: input is fixture usage-pty-differential-redraw.ansi (not in tests/ dir; raw PTY stream) and needs screen replay (cursor moves); also asserts Fable scope
  - ClaudeCLIScreenProbeTests.swift::panel taller than fifty rows keeps the session quota on screen: reason: input is fixture usage-pty-2.1.294-tall-panel.ansi (not in tests/ dir; raw PTY stream) and needs screen replay / 200-row terminal. Swift expects session
  - ClaudeCLIScreenProbeTests.swift::identity uses the final status frame with cursor positioned spaces: reason: asserts only identity (email/org/loginMethod) and rawText (not ported); status fixture needs screen replay. parse(text: 'Current session\n3% used', stat
  - ClaudeCLIScreenTests.swift::synthetic differential frame matches the visible panel golden: reason: needs screen replay (frame uses ESC[H, ESC[6;1H, ESC[5G, ESC[8G, ESC[9G, ESC[K to overwrite 'abc xye jkl' into '51% used'); also compares extraRateWindo
  - ClaudeCLIScreenTests.swift::backspace edits are replayed without a CSI sequence: reason: needs screen replay of backspace (text 'Current session\n39\x085% used' -> 65% left); without replay the first percent is '5%'.
  - ClaudeCLIScreenTests.swift::clearing the screen cannot resurrect an earlier quota: reason: needs screen replay (ESC[H ... ESC[2J clears the quota; Swift raises ClaudeStatusProbeError); without replay it would parse session 97.
  - ClaudeCLIScreenTests.swift::erase below the old column bound removes the entire quota: reason: needs screen replay (cursor addressing ESC[180;1H / ESC[200;1H / ESC[J); Swift expects a ClaudeStatusProbeError.
  - ClaudeCLIPanelTransitionTests.swift::reused session dismisses panels before capturing identity and refreshing usage: reason: drives a fake claude binary through ClaudeCLISession (PTY); parse input is the live capture, not a literal. Asserts also email / loginMethod and the com
  - ClaudeResilienceTests.swift::CLI parse failures keep prior Claude snapshot but authentication loss clears it: reason: store-level integration test (UsageStore.refreshProvider); the only ClaudeStatusProbe.parse call is inside the private helper CLIAuthenticationFailureFe
- A child of `claude` that keeps stdout open makes communicate() wait until the 30 s timeout (fake child spawns with DEVNULL pipes).

## Task list

Spec: <WORKTREE>/.autopilot/widget-claude-usage-spec.md

Global Constraints:
- Python 3.9 stdlib only, `/usr/bin/python3`; `zoneinfo` allowed.
- Never run a real `claude`/`codex`; no mutation testing.
- No string `oauth`, `security `, `socket`, `curl`, `urllib`, `auth.json`, `credentials.json`, `keyring`, `refresh_token`, `anthropic.com`, `chatgpt.com` (case-sensitive) in quotaboard/, tests/, bin/.
- Window keys and minutes only in `derive.WINDOWS = {"five_hour": 300, "seven_day": 10080}`.
- Claude argv: `["claude", "-p", "--no-session-persistence", "--strict-mcp-config", "--settings", '{"remoteControlAtStartup":false,"disableAllHooks":true}', "--model", "sonnet", "--effort", "low", "/usage"]`.
- Commit style: short imperative subject, `TASK-587:` prefix as earlier history? -> match `git log` style.
- After each task commit: `git -C <WORKTREE> push -u origin TASK-587-widget-claude-usage`.

### Task 1: One home for window names
- Files: quotaboard/derive.py, quotaboard/codex.py, quotaboard/store.py.
- Produces: `derive.WINDOWS` dict key -> minutes; `codex` maps by inverted dict; `store.default_row()` windows from `derive.WINDOWS`.
- Tests first: none new (mechanical); existing tests must pass unchanged. Check `grep -rn '"five_hour"\|"seven_day"' quotaboard` → only derive.py.
- Checks: `make -C <worktree> check`.
- Commit: `Derive window names from derive.WINDOWS`

### Task 2: Store and process helpers for the Claude probe
- Files: quotaboard/store.py, quotaboard/proc.py (new), quotaboard/codex.py, tests/test_store.py.
- Produces: `store.snapshot_path(directory)`, `store.ensure_dir(directory)` (create 0700 when missing, as write did), `write` uses both; `failed` docstring = names kept from the snapshot. `proc.reason(e)`, `proc.stop(proc)` moved from codex (`_reason`, `_stop`), codex uses them.
- Tests first: `test_snapshot_path` (returns `<dir>/snapshot.json`); existing store/codex tests unchanged.
- Checks: `make -C <worktree> check`.
- Commit: `Add store.snapshot_path and shared process helpers`

### Task 3: Port CodexBar's reset-date parser
- Files: quotaboard/claude_usage.py (new; MIT header with CodexBar name, URL, commit 6480977b47f6e4ffd5dcaae1cb0c7fdf34ee449e, `Copyright (c) 2026 Peter Steinberger`, full MIT text), THIRD_PARTY_NOTICES.md (new), tests/test_claude_usage.py (new).
- Produces: `parse_reset_date(text, now, expected_window=None) -> int|None` (spec Design; port of normalizeResetInput, formats, occurrences, resolveOccurrence; local zone fallback chain).
- Tests first: `ResetDateTest` (AC12 cases, incl. ClaudeResetOccurrenceTests samples where they exercise parseResetDate), `NoticeTest` (AC17). Set `TZ` explicitly in tests needing local zone (patch `os.environ` via `unittest.mock.patch.dict`).
- Checks: `make -C <worktree> check`.
- Commit: `Port CodexBar reset-date parsing`

### Task 4: Port ClaudeStatusProbe.parse and makeSnapshot
- Files: quotaboard/claude_usage.py, tests/test_claude_usage.py.
- Consumes: `parse_reset_date`, `derive.WINDOWS`.
- Produces: `UsageError(kind, message)`, `parse(text) -> {"session_left","weekly_left","session_reset","weekly_reset"}`, `make_windows(parsed, now) -> {key: window|None}` (spec Design, D2–D6).
- Tests first: `FixtureTest` (A1, A2 → 17/1 used, reset epochs with now = started_utc), `CodexBarSampleTest` (D3 rule; one method per sample, comment naming source test; skipped list → plan doc Notes), `IdentityTest` (AC10), error-kind inputs at parse level (auth JSON, token_expired line, rate limit, failed to load, subscription notice only, folder trust, loading, empty → timeout, `50% used` without label → unrecognized).
- Checks: `make -C <worktree> check`.
- Commit: `Port CodexBar /usage output parser`

### Task 5: Claude probe runner
- Files: quotaboard/claude.py (new), tests/helpers.py (FAKE_CLAUDE, install_fake_claude, claude_calls), tests/test_claude.py (new, RefreshTest).
- Consumes: `store.ensure_dir`, `proc.stop/reason`, `claude_usage.parse/make_windows/UsageError`.
- Produces: `TIMEOUT=30.0`, `VERSION_TIMEOUT=10.0`, `THROTTLE=300`, `ARGS`, `is_default(account, environ)`, `refresh(name, row, state_dir, environ, now=None, timeout=TIMEOUT) -> (fields, kept, message)` per spec Design order (1)–(6), version validation and sentinel `"unknown"`.
- Tests first: RefreshTest: test_argv_stdin_cwd_env (AC3), test_probe_dir_setup (AC4), test_fixture (AC5 unit), test_timeout_kills_group (AC6, short timeout, spawn_child), test_claude_missing (AC7), test_error_kinds (AC9), test_version_disable_cycle (AC11 incl. invalid version output, sentinel), test_throttle (AC13 incl. future fetched_at).
- Checks: `make -C <worktree> check`.
- Commit: `Add the Claude /usage probe runner`

### Task 6: Wire --probe into collect
- Files: quotaboard/cli.py, tests/test_cli.py, tests/test_claude.py (CollectProbeTest), README.md.
- Consumes: `claude.refresh`, `claude.is_default`, `store.read`, `store.snapshot_path`.
- Produces: `collect(environ, probe=False)`; `main` passes `args.probe`; README Claude lines (AC19).
- Tests first: CollectProbeTest: test_probe_gate (AC1, AC15), test_only_default_account (AC2), test_fixture_end_to_end (AC5), test_no_identity_in_snapshot (AC10); update test_cli `--probe invokes no claude` and state-dir entries expectations.
- Checks: `make -C <worktree> check`.
- Commit: `collect --probe probes the default Claude account`
