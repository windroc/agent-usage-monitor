# Spec: TASK-585 `quotaboard collect` writes real Codex usage to the snapshot

Requirement source: `<WORKDIR>/tmp/input.md` (the user's instructions, verbatim) and the PRD it names, `<WORKDIR>/tmp/prd.md` (a copy of `windroc/private_docs` `Product Design/2026-10-16-2312-TASK-561-m1-macos-widget.md`). They override any other input; FR/NFR ids are the PRD's. `<WORKDIR>` is the agent's local work directory.

## Goal

`quotaboard collect` reads the account list, reads each Codex account's 5h and 7d limits from `codex app-server`, and writes one snapshot with availability, summary and order, ready for the later widget. The default Claude account appears as a row with no values. Today the repo holds only spikes, fixtures and a README; this ticket adds the Python package, its entry point and a Makefile.

## Scope

| In | Out |
|---|---|
| Package `quotaboard` (Python 3.9 stdlib), entry `bin/quotaboard`, `python3 -m quotaboard` | FR-8 to FR-11 Claude probe (PRD step 3); `--probe` is accepted and does nothing yet |
| FR-1 to FR-4 account list, threshold | FR-14 concurrent probes, FR-31 isolation check (step 4); probes run one after another |
| FR-5 to FR-7 snapshot store | FR-23 to FR-29 host app, LaunchAgent, widget, `make install` (steps 5, 6) |
| FR-12, FR-13 Codex probe | FR-30 tap (only if TASK-572 had failed; it passed) |
| FR-15 to FR-22 derived fields, `collect` CLI | FR-32: not needed, step 2 check found `auth.json` unchanged (D2) |
| Step 2 check result, protocol note, sanitized real reply fixture | NFR-3 (widget) |
| NFR-1, NFR-2 (Python), NFR-4 | |

Constraints: stdlib only; runs under `/usr/bin/python3` 3.9.6 (no `match`, no `X | Y` types at runtime, no `zoneinfo` needed). No file under `spike/` or `tests/fixtures/claude-usage/` changes. Never open any credentials file.

## Terms

- **Window**: one limit of a row, key `five_hour` or `seven_day`. A window is either an object `{"used_percent": int|null, "resets_at": int|null}` or `null`. **Unknown window**: an object with `used_percent: null`. **Absent window**: `null`, meaning the last successful read reported no such limit for this account (D1).
- **Store function**: `store.write(...)`, the only code that writes `snapshot.json`.
- **Updates**: a dict `{name: {field: value}}` of fields one writer collected this run.

## Acceptance criteria

Account list
- AC1 (FR-1): `accounts.json` with 3 valid entries → snapshot `accounts` holds those 3 rows; when all have the same availability group, file order. `dir` `~/x` is expanded and stored as its realpath.
- AC2 (FR-2): no `accounts.json`; HOME has `.claude`, `.codex`, `.claude-bak` → rows exactly `claude` (client `claude`) and `codex` (client `codex`); stderr has exactly one line naming the absent file's path. Only one of the two dirs exists → only that row. Neither → zero rows, exit 0.
- AC3 (FR-3): each of: invalid JSON; top level not an object or `accounts` not a list; an item not an object or missing/non-string `name`/`client`/`dir`; duplicate `name`; `client` not `claude`/`codex`; `dir` not an existing directory; two items with the same realpath → exit 2, one stderr line naming the file and the item (index and name when known), stdout empty, snapshot file unchanged (bytes and mtime) and no state dir created when absent.
- AC4 (FR-4): `"threshold": 80` and 5h 85% → `available: false`; snapshot `threshold` is 80. Absent → 90. `0`, `101`, `"90"`, `true`, `null` → exit 2, stderr contains `threshold`.

Snapshot store
- AC5 (FR-5): after one `collect` with an absent state dir → dir mode 0700, `snapshot.json` mode 0600, dir entries exactly `snapshot.json`, `snapshot.lock`. State dir is `$QUOTABOARD_STATE_DIR` when set, else `~/.local/state/quotaboard` (parents created as needed).
- AC6 (FR-6): two processes call the store function at once, each updating a different row → final file is valid JSON with both new values. Updating one row to 5h 95% (no probe) → that row `available: false`, `summary` and order recomputed. An unknown top-level key and an unknown row key survive a `collect`. An account removed from the list → its row is gone.
- AC7 (FR-6): a failed write (e.g. JSON encode error) leaves the old snapshot intact and no temp file in the dir.
- AC8 (FR-7): snapshot is garbage, or valid JSON that is not an object with a list `accounts` of objects each with a string `name`, or a row whose `five_hour`/`seven_day` is neither `null` nor an object with `used_percent` and `resets_at` each int or `null`, or whose `fetched_at` is neither int nor `null` → `collect` exit 0, exactly one stderr line about it, resulting snapshot valid. A snapshot that cannot be read (an `OSError` other than not-found, e.g. mode 000) is treated the same; a missing one is empty with no stderr line.

Codex probe
- AC9 (FR-12): two Codex accounts, fake `codex` answering per `CODEX_HOME` → each row has its own values, `source: "app-server"`, `fetched_at` = now. The fake received, in order, exactly `initialize` (with `clientInfo`), `initialized`, `account/rateLimits/read`; its env had `CODEX_HOME=<that dir>`; argv was `app-server`.
- AC10 (FR-12): after `collect`, no fake app-server process (nor a child it spawned) is alive.
- AC11 (FR-12, D1): windows map by `windowDurationMins` (300 → `five_hour`, 10080 → `seven_day`), whichever of `primary`/`secondary` holds them; `usedPercent` → `used_percent`, `resetsAt` → `resets_at`. A window the reply does not report is stored as `null`, replacing any earlier value. The sanitized real reply fixture (7d only) → `five_hour: null`, `seven_day` 87% with its reset.
- AC12 (FR-13): `codex` missing from PATH or not executable, fake exits 1 (before or after reading input), hangs past the timeout, answers with a JSON-RPC error, sends non-JSON or a line over 1 MiB, or the reply is unrecognized (no `rateLimits` object; a non-null window that is not an object, lacks an int `usedPercent`, has `resetsAt` neither int nor null, or has a `windowDurationMins` other than 300/10080; two windows with the same duration; no recognized window at all) → row keeps its previous windows and `fetched_at`, `source: "cache"`; with no previous values (no row, or row `fetched_at: null`) → both windows `{"used_percent": null, "resets_at": null}`, `source: "none"`. One stderr line `quotaboard: codex <name>: <reason>` without the raw output; other rows unaffected; exit 0.
- AC13 (FR-12): the probe gives up after 10 s total (configurable only as a function argument for tests) and the process group is killed.
- AC14: server notifications and server requests interleaved before the response (a message without the awaited `id`) are skipped; the real reply's `remoteControl/status/changed` notification is skipped.

Derived fields (each write, at that write's `now`)
- AC15 (FR-15): `five_hour.resets_at` ≤ now and 93% → stored `{"used_percent": 0, "resets_at": null}`; the same with `used_percent: null` → also 0 (the window restarted). `resets_at: null` → percent kept. Absent window unchanged.
- AC16 (FR-16): 42/61 → `true`, `available_at: null`; 5h 93% (17:00) / 7d 70% → `false`, 17:00; 5h 95% (18:00) / 7d 92% (Fri 09:00) → `false`, Fri 09:00; 5h exactly 90 → `false`; 5h 95% with `resets_at: null` → `false`, `null`; both unknown (`source: none`) → `null`, `null`; one unknown and the other < threshold → `null`; one unknown and the other ≥ threshold → `false` with that window's reset. Absent windows are skipped (D1): `five_hour: null`, 7d 87% → `true`; 7d 95% (Fri) → `false`, Fri; both absent → `null`.
- AC17 (FR-17): the PRD's widget sample → `summary.available` = `["claude", "claude-work", "codex"]`, `summary.next` = `{"name": "claude-max", "at": <17:00>}`; two rows `false` with `available_at: null` → `available: []`, `next: null`. Ties take the earlier row in `accounts` order.
- AC18 (FR-18): list A (`false` 19:00), B (`null`), C (`true`), D (`false` 18:00), E (`true`), F (`false`, `null`) → order C, E, D, A, B, F.
- AC19 (FR-19): `fetched_at` 7 h ago → `stale: true`; 5 h ago → `false`; `null` → `false`. Boundary: > 6 h (21600 s) is stale.
- AC20 (FR-20): a Claude row whose 5h `resets_at` has passed, `collect` without `--probe` → 5h 0, `available` recomputed, `generated_at` = now.

CLI
- AC21 (FR-21): `quotaboard collect` and `quotaboard collect --probe` → stdout empty, exit 0, `generated_at` updated. `--probe` invokes no `claude` (a fake `claude` on PATH that records calls is never called).
- AC22 (FR-22): `collect --nosuch`, `quotaboard nosuch`, no subcommand → exit 2, usage on stderr, snapshot unchanged.
- AC23 (user): no account list, HOME with `.claude` and `.codex`, fake `codex` → snapshot has a `codex` row with values and a `claude` row with both windows `{null, null}`, `fetched_at: null`, `source: "none"`, `available: null`, `stale: false`, `usage_disabled_version: null`.
- AC24 (FR-6 format): every row has keys `name, client, dir, available, available_at, five_hour, seven_day, fetched_at, source, stale, usage_disabled_version`; top level has `schema: 1, generated_at, threshold, accounts, summary`; times are int epoch seconds.

Non-functional
- AC25 (NFR-1): `make check` greps `quotaboard/`, `bin/`, `tests/` (Python) for the PRD's NFR-1 strings and finds none. Subprocesses: only `codex`.
- AC26 (NFR-2): `make test` runs the whole suite with `/usr/bin/python3`, passes, and never runs the real `codex` or `claude` (tests set PATH to a temp dir of fakes plus `/usr/bin:/bin` and set HOME, `XDG_CONFIG_HOME`, `QUOTABOARD_STATE_DIR` to temp dirs).
- AC27 (NFR-4): everything committed (fixture, docs, README, and the spec and plan copied at S7) contains no email, org name, macOS login name, home path (`/Users/<name>`, absolute work paths), hostname, account directory names other than the generic `.claude`/`.codex`, account id, installation id, user agent, or plan type. Checked on the final tree after the S7 copy: `git grep -i` for the user's login name, email, hostname, `/Users/<login name>`, and the ids from the live reply → empty.
- AC28 (step 2): the doc records the protocol confirmation and that `auth.json` was unchanged (no stat values, which describe a credential file, go into the public repo); the PR description carries the conclusion.
- AC29 (FR-5): a second `collect` that replaces an existing snapshot leaves `snapshot.json` at 0600.

## Design

Data shape: the snapshot is a plain dict (FR-6 format). Row defaults for a new account:

```python
{"name", "client", "dir",          # from the account list, overwritten every write
 "available": None, "available_at": None,
 "five_hour": {"used_percent": None, "resets_at": None},
 "seven_day": {"used_percent": None, "resets_at": None},
 "fetched_at": None, "source": "none", "stale": False, "usage_disabled_version": None}
```

### `quotaboard/__init__.py`
`__version__ = "0.1.0"` (sent as `clientInfo.version`).

### `quotaboard/__main__.py`, `bin/quotaboard`
`bin/quotaboard` (mode 755, `#!/usr/bin/python3`) puts the repo root (`realpath(__file__)/../..`) on `sys.path` and calls `sys.exit(quotaboard.cli.main())`; resolving the realpath keeps it working through the later `~/.local/bin` symlink. `__main__.py` does `sys.exit(main())`.

### `quotaboard/cli.py`
`main(argv=None) -> int`. `argparse` with prog `quotaboard`, required subcommand `collect`, flag `--probe` (store_true; no effect yet). argparse's own exit 2 + usage covers FR-22. `collect`:
1. `threshold, accounts, hint = accounts.load(environ)`; print `hint` to stderr when not None; `AccountsError` → print `quotaboard: <msg>` to stderr, return 2. `cli` owns all stderr output (D9).
2. For each Codex account, `codex.probe(dir)`: success → `updates[name] = {"five_hour", "seven_day", "fetched_at": now, "source": "app-server"}`; `ProbeError` → stderr `quotaboard: codex <name>: <reason>`, name added to `failed`. Claude accounts get no update (D6).
3. `store.write(store.state_dir(environ), accounts, threshold, updates, failed)`; return 0.

### `quotaboard/accounts.py`
`Account = namedtuple("Account", "name client dir")`. `class AccountsError(Exception)`. `config_path(environ) -> str`: `$XDG_CONFIG_HOME/quotaboard/accounts.json`, `XDG_CONFIG_HOME` unset or empty → `~/.config`. `load(environ=os.environ) -> (threshold, [Account])`:
- File absent (`FileNotFoundError`) → defaults `claude` → `~/.claude`, `codex` → `~/.codex`, each only if `os.path.isdir`, realpath'd; hint `quotaboard: no account list at <path>; using default accounts in ~/.claude and ~/.codex`; threshold 90. `load` returns `(threshold, accounts, hint)`, `hint` None when the file exists.
- Other read errors and every FR-3/FR-4 case → `AccountsError("<path>: accounts[<i>] (<name>): <problem>")` / `"<path>: threshold must be a number in (0, 100]"`. `bool` is not a number. Duplicate realpath message names both items.
- `~` expansion uses `os.path.expanduser` (honors `HOME`).

### `quotaboard/derive.py`
Pure: `recompute(snapshot, threshold, now) -> None` mutates in place: per row apply FR-15 to each non-null window, then FR-16 (D1: judge only non-null windows; zero non-null windows → `null`; any unknown window and no window ≥ threshold → `null`), FR-19 `stale = fetched_at is not None and now - fetched_at > 21600`; then stable-sort `accounts` by group key (`true` → 0; `false` with time → (1, at); else 2), the incoming order being account-list order; then FR-17 `summary`; set `generated_at = now`, `threshold`.

### `quotaboard/store.py`
`state_dir(environ) -> str`. `read(path) -> (dict | None, warning | None)`: (None, `quotaboard: snapshot <path> unreadable, starting empty: <reason>`) on any OSError other than not-found, decode error, or shape mismatch; not-found → (None, None). `write(state_dir, accounts, threshold, updates, failed=(), now=None) -> list[str]` returns the warning lines (at most the read warning) for the caller to print:
1. `os.makedirs(dir, mode=0o700, exist_ok=True)`; if it did not exist, `os.chmod(dir, 0o700)` (umask).
2. `fd = os.open(lock, O_RDWR|O_CREAT, 0o600)`; `fcntl.flock(fd, LOCK_EX)`.
3. Re-read snapshot; index old rows by name.
4. Rebuild `accounts` in account-list order: old row (or defaults) with `name/client/dir` overwritten, `updates[name]` merged key by key; for each name in `failed`: row `fetched_at` not null → `source: "cache"`, else both windows `{"used_percent": None, "resets_at": None}` and `source: "none"` (D7).
5. `derive.recompute(snap, threshold, now or int(time.time()))`; `snap["schema"] = 1`.
6. `mkstemp(dir=state_dir, prefix=".snapshot.", suffix=".tmp")`, write `json.dumps(snap, indent=1)`, `fsync`, `os.replace` onto `snapshot.json`; on any exception unlink the temp file and re-raise.
7. Unlock and close in `finally`.

### `quotaboard/codex.py`
`class ProbeError(Exception)`. `probe(codex_home, environ, timeout=10.0) -> dict` returns `{"five_hour": window|None, "seven_day": window|None}` or raises `ProbeError(reason)`.
- `Popen(["codex", "app-server"], stdin=PIPE, stdout=PIPE, stderr=DEVNULL, env={**environ, "CODEX_HOME": codex_home}, start_new_session=True)`. Any `OSError` on spawn, write or read (not found, not executable, `BrokenPipeError` after the child exited) → `ProbeError("<what failed>: <errno name>")`.
- Messages are one JSON object per line, no `jsonrpc` field (D3): send `{"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "quotaboard", "version": __version__}}}`; wait for `id` 1; send `{"method": "initialized"}` and `{"id": 2, "method": "account/rateLimits/read"}`; wait for `id` 2. Messages with another or no `id` are skipped. A response with `error` → `ProbeError("app-server error <code>")`, `<code>` only when it is an int, else `ProbeError("app-server error")` (no untrusted text in stderr).
- Reading uses `select` on the stdout fd with the remaining time of one overall deadline, and a byte buffer split on `\n`; a buffered line over 1 MiB → `ProbeError("unrecognized output")`; EOF → `ProbeError("app-server exited <code>")`; deadline → `ProbeError("timed out after 10 s")`; bad JSON → `ProbeError("unrecognized output")`.
- `finally`: close stdin; `wait(1)`; then `os.killpg(pid, SIGKILL)` (ignore `ProcessLookupError`) and `wait()`; the group kill also reaps grandchildren.
- Parsing per AC11/AC12; `parse_rate_limits(result) -> dict` is a separate pure function tested on the fixture.

### `Makefile`
```make
PY := /usr/bin/python3
test:
	$(PY) -m unittest discover -s tests -t .
check: test
	! grep -rnF -e 'credentials.json' … quotaboard bin tests --include='*.py' --include=quotaboard
.PHONY: test check
```
The grep lists every NFR-1 string; `bin/quotaboard` has no `.py` suffix, so the grep includes `bin` explicitly.

### `tests/`
`tests/__init__.py`, `tests/helpers.py`: `Env` context that makes temp HOME, `XDG_CONFIG_HOME`, `QUOTABOARD_STATE_DIR`, PATH set to exactly `<fake-bin>:/usr/bin:/bin` (never the inherited PATH, so a missing or non-executable fake cannot fall through to a real `codex`), and writes fake `codex` (a `#!/usr/bin/python3` script that reads `$CODEX_HOME/fake.json` for its behavior: `reply` messages, `exit`, `hang`, `spawn_child`, and appends each received line plus its argv and `CODEX_HOME` to `$CODEX_HOME/received.jsonl` and its pid(s) to `$CODEX_HOME/pids`). CLI tests run `bin/quotaboard` via `subprocess` with that env. Test files: `test_accounts.py`, `test_store.py`, `test_derive.py`, `test_codex.py`, `test_cli.py`.

### `tests/fixtures/codex-app-server/rate-limits-read.jsonl`
The 3 lines of the real reply (codex-cli 0.163.0), with `userAgent`, `codexHome`, `serverName`, `installationId`, `accountId`, `planType` replaced by `<USER_AGENT>`, `<CODEX_HOME>`, `<HOST>`, `<INSTALLATION_ID>`, `<ACCOUNT_ID>`, `<PLAN>`.

### `docs/codex-app-server.md`
Protocol (schema source command, the 3 messages, window mapping, the 7d-only real reply and D1), the step 2 result (date, codex-cli version, sessions running, `stat -f '%m %i %z'` output identical before and after, values not recorded; so FR-32 is not built).

### S7 copy of spec and plan
S7 copies the spec and plan doc to `docs/design/TASK-585-quotaboard-collect-codex-spec.md` and `…-plan.md`, replacing the agent work directory path with `<WORKDIR>`, the worktree path with `<WORKTREE>`, the plugin cache path with `<PLUGIN>`, and removing the `auth.json` stat values (keep "unchanged"); then runs the AC27 grep.

### `README.md`
Add a "Development" section: `make test`, `make check`, `bin/quotaboard collect`, the account list path and a sample (placeholder names), and the snapshot path. Keep the status line ("Nothing is installable yet").

## Verification

| AC | Test or check |
|---|---|
| AC1 | `test_accounts.LoadTest.test_file_order_and_realpath` |
| AC2 | `test_accounts.LoadTest.test_defaults_*`; `test_cli.CollectTest.test_defaults_hint` |
| AC3 | `test_accounts.LoadTest.test_invalid_*` (one per case); `test_cli.CollectTest.test_bad_list_exit2_snapshot_unchanged` |
| AC4 | `test_accounts.LoadTest.test_threshold_*`; `test_derive.AvailableTest.test_threshold_80` |
| AC5 | `test_cli.CollectTest.test_state_dir_modes_and_entries` |
| AC6 | `test_store.WriteTest.test_concurrent_writers` (two `multiprocessing`/subprocess writers), `test_update_recomputes`, `test_unknown_keys_kept`, `test_removed_account_dropped` |
| AC7 | `test_store.WriteTest.test_failed_write_keeps_old` (patch `json.dumps` to raise) |
| AC8 | `test_store.ReadTest.test_garbage_*`; `test_cli.CollectTest.test_corrupt_snapshot` |
| AC9 | `test_cli.CollectTest.test_two_codex_accounts` |
| AC10 | `test_codex.ProbeTest.test_no_leftover_processes` (fake mode `spawn_child` + `hang`, both ignoring SIGTERM and stdin EOF; both pids dead after `probe` returns) |
| AC11 | `test_codex.ParseTest.test_real_fixture`, `test_map_by_duration`; `test_store.WriteTest.test_absent_window_replaces_old` |
| AC12 | `test_codex.ProbeTest.test_not_found`, `test_not_executable`, `test_exit1_before_read`, `test_exit1_after_initialize`, `test_error_response`, `test_non_json`, `test_long_line`; `test_codex.ParseTest.test_unrecognized_*`, `test_duplicate_duration`; `test_cli.CollectTest.test_probe_failure_cache_and_none` |
| AC13 | `test_codex.ProbeTest.test_timeout` (timeout=1) |
| AC14 | `test_codex.ProbeTest.test_skips_notifications` |
| AC15 | `test_derive.ResetTest.*` |
| AC16 | `test_derive.AvailableTest.*` |
| AC17 | `test_derive.SummaryTest.*` |
| AC18 | `test_derive.OrderTest.test_prd_example` |
| AC19 | `test_derive.StaleTest.*` |
| AC20 | `test_cli.CollectTest.test_claude_row_recomputed` |
| AC21 | `test_cli.CollectTest.test_stdout_empty_exit0`, `test_probe_flag_no_claude` |
| AC22 | `test_cli.CollectTest.test_usage_errors` |
| AC23 | `test_cli.CollectTest.test_default_claude_row_empty` |
| AC24 | `test_cli.CollectTest.test_snapshot_format` |
| AC25 | `make check` |
| AC26 | `make test` with `/usr/bin/python3` |
| AC27 | after the S7 copy, `git grep -i` for the login name, email, hostname, `/Users/<login name>`, and the live reply's ids over the tree → empty |
| AC28 | read `docs/codex-app-server.md` and the PR description |
| AC29 | `test_cli.CollectTest.test_state_dir_modes_and_entries` (second run) |

Tests are hermetic (temp HOME, config, state dir, fakes first on PATH). Every suite the repo names (`make test`, `make check`) passes.

## Decisions

- D1: A window the successful read does not report is stored as `null` (absent) and FR-16 judges only non-null windows; zero non-null windows → `null`. The live read of the default account reported only a 7d window; the literal FR-16 would show it `未知` while under threshold. Council 3/3; departs from FR-16's wording and adds a third window state the widget ticket (FR-26) must render (e.g. `—`). Flagged in the PR for the author.
- D2: FR-32 is not built: with Codex sessions running, one live app-server read left `~/.codex/auth.json` `stat -f '%m %i %z'` output identical before and after (2026-10-17, codex-cli 0.163.0).
- D3: Protocol confirmed from `codex app-server generate-json-schema` (codex-cli 0.163.0) and one real reply: JSON lines on stdio, no `jsonrpc` field, `initialize` needs `clientInfo{name, version}`, `account/rateLimits/read` takes no params.
- D4: A window with an unknown `windowDurationMins` makes the reply unrecognized (FR-13), not ignored, so a new limit never silently yields `available: true`.
- D5: Codex accounts are probed one after another (FR-14 is step 4); total time ≤ 10 s per Codex account.
- D6: Claude rows get no update this ticket: an existing row keeps all its values and source; a new one has the defaults (`source: "none"`).
- D7: `failed` names are resolved under the lock (cache vs none), so a concurrent writer's newer values are kept.
- D8: `make check` holds the NFR-1 grep so the strings live outside Python code.
- D9: `accounts.load` and `store.write` return their FR-2/FR-7 lines and `cli` prints them, so later writers (tap, concurrent probes) choose what reaches stderr (architecture#2).
- Left to the implementer: exact stderr wording beyond the stated prefixes, helper names inside tests, fake `codex` file format.
