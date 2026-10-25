# Spec: TASK-587 `collect --probe` reads the default Claude account's limits from `claude -p /usage`

Requirement source: the plan doc's `## Input` (the user's TASK-587 instructions, verbatim) and the PRD excerpt it names, `<WORKDIR>/tmp/prd-TASK-561.md`. They override any other input; the user's instructions override the PRD. FR/NFR ids are the PRD's.

## Goal

`quotaboard collect --probe` runs CodexBar's `/usage` probe (ported to Python) for the default Claude account (`~/.claude`) and writes its 5h and 7d percent and reset time to the snapshot with `source: "usage"`. Today `collect` probes only Codex; `--probe` is parsed and ignored, and Claude rows stay empty. Also closes three TASK-585 review leftovers (snapshot path helper, `args.probe` wiring, one home for window names).

## Scope

| In | Out |
|---|---|
| FR-8 `--probe` gate | FR-14 concurrent probes (PRD step 4): probes stay sequential |
| FR-9 probe for the default account (dir realpath = realpath `~/.claude`), as corrected by the user: `CLAUDE_CONFIG_DIR` removed | Non-default Claude accounts: not probed, row kept as is (later ticket, TASK-583) |
| FR-10 parser port, five error kinds, per-version disable, MIT notices | FR-9 session-file cleanup (TASK-572 saw no session files; user: not enabled) |
| FR-11 5-minute throttle | FR-30 tap; host app, widget, FR-23/24 40 s budget |
| TASK-585 leftovers: `store.snapshot_path`, `args.probe`, window names from `derive.WINDOWS` | Porting identity, Opus/Sonnet and model-scoped weekly windows, spend cap, PTY screen replay, the order-based percent fallback |
| README Claude lines, `THIRD_PARTY_NOTICES.md` | |

Constraints: Python 3.9 stdlib only (`zoneinfo` allowed), runs under `/usr/bin/python3`. Tests never run a real `claude`/`codex`. `make check` (NFR-1 grep) stays clean: no `oauth`, `security `, etc. in `quotaboard/`, `tests/`, `bin/` (D6). Fixtures under `tests/fixtures/claude-usage/` unchanged.

## Terms

- **Default account**: a `client: "claude"` account whose `dir` equals `accounts.expand("~/.claude", environ)`.
- **Probe dir**: `<state dir>/probe/`.
- **Kept**: the row keeps its previous windows and `fetched_at`; the store sets `source: "cache"`, or `"none"` with unknown windows when `fetched_at` is null (existing `failed` path of `store.write`, FR-13 semantics).
- **Error kinds**: `auth`, `usage_error`, `loading`, `timeout`, `unrecognized` (FR-10).

## Acceptance criteria

Gate and selection
- AC1 (FR-8): fake `claude` that records every call. `collect` → no call; the Claude row is byte-for-byte the previous row except derived fields. `collect --probe` → called.
- AC2 (user scope): accounts `claude` (`~/.claude`) and `claude-work` (`~/.claude-work`), `--probe` → only `claude` probed; `claude-work` row unchanged except derived fields, no stderr line about it.

Probe invocation (FR-9 as corrected)
- AC3: the fake receives argv exactly `-p --no-session-persistence --strict-mcp-config --settings {"remoteControlAtStartup":false,"disableAllHooks":true} --model sonnet --effort low /usage`; stdin empty (reads EOF at once); cwd = realpath of the probe dir; env has `PWD` = that path, `DISABLE_AUTOUPDATER=1`, no `CLAUDE_CONFIG_DIR`, no `CLAUDE_CODE_OAUTH_TOKEN`, no key starting `ANTHROPIC_`, even when the parent sets `CLAUDE_CONFIG_DIR`, `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`; other parent vars (e.g. `PATH`, `HOME`) pass through.
- AC4: after the first probe, the probe dir is mode 0700 and holds `.claude/settings.local.json` whose JSON is exactly `{"disableDeepLinkRegistration": "disable"}`; the state dir is 0700; state dir entries are `snapshot.json`, `snapshot.lock`, `probe`. A second probe with both already present succeeds and leaves no temp file in `.claude/`. A pre-existing probe dir with another mode is chmod-ed to 0700.
- AC5: fake prints `A1.stdout.txt` (or `A2`) from `tests/fixtures/claude-usage/`, exit 0 → row `five_hour` `{"used_percent": 17, "resets_at": <2026-10-17 04:39 America/New_York>}`, `seven_day` `{"used_percent": 1, "resets_at": <2026-10-24 00:59 America/New_York>}`, `source: "usage"`, `fetched_at` = now, `usage_disabled_version: null`, no stderr line, exit 0. (Reset epochs computed with `now` = the fixture's `started_utc`, via the parser's `now` argument in unit tests; the CLI test checks percents, source and that both `resets_at` are ints.)
- AC6: fake hangs past the timeout (unit test with a short timeout) → kind `timeout`; the fake and any child it spawned are dead afterwards. Production timeout 30 s.
- AC7: `claude` not on PATH → row kept, stderr `quotaboard: claude <name>: cannot start claude: ENOENT`, exit 0.

Parser and error kinds (FR-10)
- AC8: every usage-input sample from CodexBar tests that call `ClaudeStatusProbe.parse` (D3 rule) is a Python test asserting the same session/weekly percent-left and reset descriptions (and the same thrown error mapped to a kind) as the original assertions.
- AC9: one input per kind, through the probe: auth (`Failed to load usage data: {"error":{"type":"authentication_error","message":"OAuth token has expired"}}` style and a `token_expired` failure line) → `auth`; rate limit / `failed to load usage data` / subscription notice only / folder trust prompt → `usage_error`; `Loading usage…` with no percent → `loading`; empty output, or non-zero exit with output of none of the above, or hang → `timeout`; exit 0 with `50% used` and no `Current session` → `unrecognized`. Each → row kept, one stderr line `quotaboard: claude <name>: <kind>: <fixed description>` with no probe output in it; only `unrecognized` sets `usage_disabled_version`.
- AC10: input with `Account: user@example.com` and `Org: Example Org` lines plus valid usage → the snapshot row has no email or org value anywhere.
- AC11 (per-version disable): after `unrecognized`, the row's `usage_disabled_version` is the stripped stdout of `claude --version` (same env and cwd as the probe). Next `--probe` ≥ 5 min later with the same version → `claude` is called only with `--version`; row kept; stderr `quotaboard: claude <name>: probe disabled for <version>; delete usage_disabled_version from the snapshot to retry`. Version changed → probe runs; on success `usage_disabled_version` becomes `null`. Key deleted by the user → probe runs. `--version` failing (non-zero, timeout, cannot start, or first stdout line not matching `^\d+\.\d+\.\d+\S*( \(Claude Code\))?$`, max 64 chars) after `unrecognized` → `usage_disabled_version: "unknown"`, stderr line says the version is unknown; when checking a disabled row, a failing `--version` → skip the probe (stay disabled). Only the validated first line is ever stored or printed.
- AC12: reset parsing matches CodexBar `parseResetDate(from:now:expectedWindow:)` on: `Resets 4:39am (America/New_York)` (time only → next occurrence, or the just-passed one when within the window and the next is beyond it), `Oct 17 at 4:39am (…)`, `Oct 24, 12:59am`, `Jan 1, 2027, 9am`, `Resets 11am`, `Feb 29 at 9am` (leap-year resolution), `Resets 3pm (Not/AZone)` (unknown zone → local zone), 24-hour `14:30`, garbage → `null`; the repeated hour on a DST fall-back day yields the CodexBar choice. Unparseable reset → `resets_at: null`, percent still stored.

Throttle (FR-11)
- AC13: row `fetched_at` 60 s ago → `--probe` makes no `claude` call (not even `--version`), row kept with `source: "cache"`; 360 s ago → probed; no row in snapshot, or `fetched_at: null` → probed. Boundary: `now - fetched_at >= 300` probes; a `fetched_at` in the future (negative age) probes.

Leftovers
- AC14: `store.snapshot_path(directory)` returns `<directory>/snapshot.json`; `store.write` and the throttle read both use it; no other code builds that path.
- AC15: `cli.main` passes `args.probe` to `collect(environ, probe=...)`.
- AC16: window names and durations live only in `derive.WINDOWS`; `codex` (by minutes), `store.default_row` and the Claude mapping derive from it; existing Codex and store tests pass unchanged.

Notices and hygiene
- AC17: `THIRD_PARTY_NOTICES.md` at repo root and the ported module's header both contain `Copyright (c) 2026 Peter Steinberger` and the full MIT text, naming CodexBar, its URL and commit `6480977b47f6e4ffd5dcaae1cb0c7fdf34ee449e`.
- AC18 (NFR-1/2/4): `make check` passes (tests + grep). New fixtures/test strings hold no real email, org, login name, `/Users/<name>` or account dir name (CodexBar's synthetic `example.com` style values allowed).
- AC19: README no longer says Claude rows have no values / the probe "will be ported"; it states `--probe` probes only the default account, the throttle and the per-version disable, in one place.

## Design

### quotaboard/derive.py
`WINDOWS = {"five_hour": 300, "seven_day": 10080}` (window minutes; dict order is the key order). Existing iteration over `WINDOWS` keeps working.

### quotaboard/codex.py
Drop its `WINDOWS`; `_BY_MINUTES = {m: k for k, m in derive.WINDOWS.items()}`; return `{key: found.get(key) for key in derive.WINDOWS}`.

### quotaboard/store.py
- `snapshot_path(directory)` → `os.path.join(directory, "snapshot.json")`; `write` uses it.
- `ensure_dir(directory)`: the existing "create 0700 if missing" block, reused by the probe.
- `default_row()` builds windows from `derive.WINDOWS`.
- `write(..., failed=())` docstring: `failed` = names this run keeps from the snapshot (probe failed or skipped). Behaviour unchanged.

### quotaboard/claude_usage.py (port; MIT header per AC17)
Pure functions, no I/O. Port of `ClaudeStatusProbe.parse` (minus identity, Opus, scoped weekly, order fallback), its helpers (`cleanCapture` with plain-report rendering = strip escape sequences per `ClaudeCLIScreen` token regex and drop the insights tail after `What's contributing to your limits usage?`; `trimToLatestUsagePanel`; `extractPercent` exact-then-fuzzy with the 12-line window and label-boundary rule; `percentFromLine`; `extractReset` 14-line window; `resetFromLine`; `cleanResetLine`; `extractUsageError` incl. JSON form; `usageProbeError` marker list; `isUsageStillLoading`; `isSubscriptionNoticeOnly`; `usageCaptureHasSessionValue`; `allPercents` only as used by the loading check), `makeSnapshot` conversion, and `parseResetDate` with occurrence resolution.

```python
class UsageError(Exception):          # .kind in ("auth", "usage_error", "loading", "timeout", "unrecognized")
    def __init__(self, kind, message): ...
def parse(text) -> dict               # {"session_left", "weekly_left", "session_reset", "weekly_reset"}; raises UsageError
def make_windows(parsed, now) -> dict # {session key: window, weekly key: window|None}
def parse_reset_date(text, now, expected_window=None) -> int|None   # epoch seconds
```
- `parse`: empty after cleaning → `timeout`; `extractUsageError` hit → `auth` when the message has a CodexBar auth marker, else `usage_error`; still loading → `loading`; no `Current session` percent → `unrecognized`. Weekly percent/reset only when a `Current week (all models)` label (fuzzy all-models) is present.
- `make_windows`: keys come from `derive.WINDOWS` by minutes (300 → session, 10080 → weekly, CodexBar `sessionWindowMinutes`/`weeklyWindowMinutes`), never a literal key name. `used_percent = 100 - left` (clamped 0..100, int); `resets_at = parse_reset_date(reset, now, minutes*60)`; `seven_day` is `None` (absent window, TASK-585 D1) when there is no weekly percent. Rounding of fractional percents: half away from zero, as Swift `.rounded()`.
- `parse_reset_date`: normalise as `normalizeResetInput`; `(Zone/Id)` → `zoneinfo.ZoneInfo`, invalid or missing → local zone (`TZ` env if a valid zone, else the zone named by `/etc/localtime`'s link target, else the fixed current offset); formats by regex covering the five CodexBar format lists, case-insensitive am/pm; wall time → instants via `fold` 0 and 1, keeping only those that round-trip (drops gap times, keeps both repeated times); yearly candidates for years ±8 skipping invalid dates; daily candidates for yesterday/today/tomorrow; `resolveOccurrence` as CodexBar.

### quotaboard/claude.py
```python
TIMEOUT = 30.0
VERSION_TIMEOUT = 10.0
THROTTLE = 300
ARGS = ["-p", "--no-session-persistence", "--strict-mcp-config", "--settings",
        '{"remoteControlAtStartup":false,"disableAllHooks":true}', "--model", "sonnet", "--effort", "low", "/usage"]
def is_default(account, environ) -> bool
def refresh(name, row, state_dir, environ, now=None, timeout=TIMEOUT) -> (fields: dict, kept: bool, message: str|None)
```
Process handling is shared with Codex: move `codex._reason` and `codex._stop` (group kill + reap) into `quotaboard/proc.py` (`reason(e)`, `stop(proc)`); both probes and `--version` call `stop` after every run, success included. `--version` uses the probe's launch (env, cwd, stdin `DEVNULL`, `start_new_session`, `VERSION_TIMEOUT`).
`refresh` order: (1) throttle on `row["fetched_at"]` → `({}, True, None)`; (2) prepare probe dir (`store.ensure_dir(state_dir)`, `mkdir` probe 0700 + `chmod`, `.claude/` `exist_ok`, settings via `tempfile.mkstemp` in `.claude/` + `os.replace`); (3) `row["usage_disabled_version"]` set → run `--version`; equal or failing → `({}, True, disabled line)`; (4) run the probe: `Popen(["claude"] + ARGS, cwd=probe, stdin=DEVNULL, stdout=PIPE, stderr=PIPE, env=..., start_new_session=True)`, `communicate(timeout)`, on timeout `killpg(SIGKILL)` and reap; decode UTF-8 with `replace`; (5) classify `text = stdout + "\n" + stderr` (D2): `UsageError` from `parse` for `auth`/`usage_error`/`loading` first; else timed out, empty output or non-zero exit → `timeout`; else `parse` result or its `unrecognized`; (6) success → `(make_windows(...) + {"fetched_at": now, "source": "usage", "usage_disabled_version": None}, False, None)`; `unrecognized` → run `--version`, `({"usage_disabled_version": v} if v else {}, True, line)`; other kinds → `({}, True, line)`. Fixed descriptions per kind, never probe output.
Env: copy of `environ` minus `CLAUDE_CONFIG_DIR`, `CLAUDE_CODE_OAUTH_TOKEN` and every `ANTHROPIC_*`; plus `DISABLE_AUTOUPDATER=1`, `PWD=<realpath probe>`.

### quotaboard/cli.py
`collect(environ, probe=False)`; after the Codex loop, when `probe`: read the snapshot once via `store.read(store.snapshot_path(state))` (a warning from it is not printed here; `write` prints it), map rows by name, and for each default account call `claude.refresh(name, row or {"fetched_at": None, "usage_disabled_version": None}, ...)`; fields go to `updates`, `kept` names to `failed`, message to stderr. `main`: `args = parser.parse_args(argv)`; `--probe` help: "also probe the default Claude account".

### tests
- `tests/helpers.py`: `FAKE_CLAUDE` script (config `$HOME/fake-claude.json`: `stdout_file`|`stdout`, `stderr`, `exit`, `hang`, `spawn_child`, `version`, `version_exit`; logs one JSON line per call to `$HOME/claude-calls.jsonl`: argv, cwd, env subset, stdin bytes) and `install_fake_claude(env, **cfg)`.
- `tests/test_claude_usage.py`: parser + reset tests (AC8, AC10, AC12, fixtures).
- `tests/test_claude.py`: `refresh` unit tests (AC3–AC7, AC9, AC11, AC13) and CLI end-to-end (AC1, AC2, AC5).
- `tests/test_cli.py`: replace TASK-585's "`--probe` invokes no claude" assertion with AC1.

### Docs
- `THIRD_PARTY_NOTICES.md` (new): CodexBar name, URL, commit, what was ported (`quotaboard/claude_usage.py`), full LICENSE text.
- `README.md`: replace the "Claude rows have no values yet" and "will be ported" lines (AC19).

## Verification

Test-first per task; all tests hermetic (temp HOME/state via `tests.helpers.Env`, fake `claude` on a fakes-only PATH, `TZ` set explicitly where local zone matters).

| AC | Test or check |
|---|---|
| AC1 | `tests/test_claude.py::CollectProbeTest.test_probe_gate`; `tests/test_cli.py::CollectTest.test_stdout_empty_exit0` (updated) |
| AC2 | `tests/test_claude.py::CollectProbeTest.test_only_default_account` |
| AC3 | `tests/test_claude.py::RefreshTest.test_argv_stdin_cwd_env` |
| AC4 | `tests/test_claude.py::RefreshTest.test_probe_dir_setup` |
| AC5 | `tests/test_claude_usage.py::FixtureTest` (A1, A2); `tests/test_claude.py::CollectProbeTest.test_fixture_end_to_end` |
| AC6 | `tests/test_claude.py::RefreshTest.test_timeout_kills_group` |
| AC7 | `tests/test_claude.py::RefreshTest.test_claude_missing` |
| AC8 | `tests/test_claude_usage.py::CodexBarSampleTest` (one method per ported sample) |
| AC9 | `tests/test_claude.py::RefreshTest.test_error_kinds` |
| AC10 | `tests/test_claude_usage.py::IdentityTest`; `tests/test_claude.py::CollectProbeTest.test_no_identity_in_snapshot` |
| AC11 | `tests/test_claude.py::RefreshTest.test_version_disable_cycle` |
| AC12 | `tests/test_claude_usage.py::ResetDateTest` |
| AC13 | `tests/test_claude.py::RefreshTest.test_throttle` |
| AC14 | `tests/test_store.py::test_snapshot_path`; `grep -rn '"snapshot.json"' quotaboard` → only `store.snapshot_path` |
| AC15 | `tests/test_claude.py::CollectProbeTest.test_probe_gate` (CLI path) |
| AC16 | existing `tests/test_codex.py`, `tests/test_store.py`, `tests/test_derive.py` pass; `grep -rn '"five_hour"' quotaboard` → only `derive.py` |
| AC17 | `tests/test_claude_usage.py::NoticeTest` (reads both files) |
| AC18 | `make check` |
| AC19 | review of `README.md` |

Every suite the repo names passes: `make check` (which runs `make test`) under `/usr/bin/python3`.

## Decisions

- D1: Default account = realpath match with `~/.claude`; non-default Claude rows untouched and silent (user: left for TASK-583).
- D2: Classification reads stdout and stderr together (`claude -p` may print errors to stderr); percent labels are line-window anchored, so appended stderr cannot change a parsed value. A non-zero exit or timeout with otherwise parseable output is `timeout`, not success (conservative; retries next click).
- D3: CodexBar samples ported: every `ClaudeStatusProbe.parse` call in `Tests/CodexBarTests/` at the pinned commit (`StatusProbeTests`, `ClaudeAllModelsWeeklyDuplicateTests`, `ClaudeCLIScopedWeeklyUsageTests`, `ClaudeCLIScreenProbeTests`, `ClaudeCLIScreenTests`, `ClaudeCLIPanelTransitionTests`, `ClaudeCLISpendCapTests`, `ClaudeResilienceTests`, `ClaudeUsageInsightsTests`) whose assertions touch session/weekly percent, their reset descriptions, or the thrown error; assertions on Opus, scoped/extra windows, identity, spend cap and raw text are dropped. Skipped whole: samples that need PTY screen replay (cursor-move CSI or backspace) or that pass only through the order-based fallback (those become `unrecognized` cases where useful). Each ported test names its source test in a one-line comment; the skipped list with reasons goes in the plan doc Notes and the PR description, not the repo.
- D4: `-p` output is plain, so only the plain path of `ClaudeCLIScreen.render` is ported (strip escapes).
- D5: Reason lines are fixed per kind (FR-25: no raw output). CodexBar's JSON error text is used only for classification.
- D6: CodexBar's auth marker `oauth account information not found` is ported as `account information not found` so the NFR-1 grep (`oauth`) stays empty; same matches in practice.
- D7: `claude --version` failure after `unrecognized` records the sentinel `"unknown"`, which stays disabled until a valid version is read (it never equals one) or the user deletes the key; on a disabled row a failing `--version` stays disabled. Bounds spend to once per version per account (PRD risk).
- D8: Start failure (`claude` missing) is reported as `cannot start claude: <errno>` and treated like `timeout` (kept, retried).
- D10: The throttle reads the snapshot outside the store lock; a concurrent writer can at worst cause one duplicate probe.
- D9: Sequential probes may exceed the host's later 40 s budget (Codex 10 s + Claude 30 s + version 10 s worst case); FR-14 (step 4) addresses it.
- Left to the implementer: internal helper names, regex details reproducing CodexBar behaviour, fake-claude config keys beyond those listed.
