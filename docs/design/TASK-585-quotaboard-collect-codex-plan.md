Rules: <PLUGIN>/skills/build/SKILL.md <PLUGIN>/references/autopilot-common.md <PLUGIN>/references/review-round.md
RESUME: phase=S7 worktree=<WORKTREE> branch=TASK-585-quotaboard-collect-codex-m1-tracer-bulle base_ref=8dedf36596c59e7d335e93f41c6b063cfe5570a4 review_round=2 input_sha=2228d3bfc0b2

## Input

# Requirement: TASK-585 quotaboard collect 采到 Codex 用量（M1 tracer bullet）

Target repo: windroc/agent-usage-monitor (public). Default branch: `main`.

## Requirements (precedence: the user's instructions > the PRD; newer > older)

### The user's instructions (verbatim)

跑 `quotaboard collect` 后，快照里有默认 Codex 账号（`~/.codex`）真实的 5h、7d 用量和重置时间，以及可用判定、`可用 n/m` 汇总和排序。默认 Claude 账号也作为一行出现在快照里，但还没有值（Claude 探测在后续 ticket）。这一张同时搭好 repo 骨架：Python 3.9 标准库的 `quotaboard` 包和入口，以及 Makefile 的测试目标。

Acceptance criteria:
- FR-2：没有账号清单时，账号是存在的 `~/.claude`（`claude`）和 `~/.codex`（`codex`），stderr 写一行带清单路径的提示。
- FR-5 到 FR-7：快照存储。目录 0700、文件 0600，目录里只有快照和锁文件；所有写入只走一个存储函数（`fcntl` 排他锁、重读、按 name 合并、按清单重建行、重算派生字段、同目录临时文件加 rename）；快照坏了当作空快照。
- FR-12、FR-13：Codex 探测。每次 `collect` 跑 `codex app-server`（`CODEX_HOME=<dir>`），只发 `initialize`、`initialized`、`account/rateLimits/read`，超时 10 s，结束后没有残留进程；失败保留上次的值。协议先用官方文档或 schema 加一份真实回复确认。
- PRD 实施步骤 2 的验证：有 Codex session 在跑时跑一次 app-server，前后比较 `auth.json` 的 `stat -f '%m %i %z'`（不打开文件），结论写进 issue（write it into the PR description and the build's final report; the caller relays it to the issue）；变了就实现 FR-32。
- FR-15 到 FR-20：窗口重置、可用判定、汇总、排序、`stale`，每次写入都按当时时间重算。
- FR-21、FR-22：`quotaboard collect [--probe]`，stdout 为空、成功 exit 0；`--probe` 先接受但还不探测 Claude；未知参数 exit 2。
- NFR-1、NFR-2（Python 部分）：PRD 列的 `grep` 检查为空；测试只用假 `codex`，用 `/usr/bin/python3` 全部通过。
- NFR-4：提交的 fixture 和文档已脱敏（repo 是 public）。

Also in scope by PRD implementation step 1 (this ticket covers steps 1 and 2): FR-1, FR-3, FR-4 (account list file, its validation, threshold). Out of scope: FR-8 to FR-11 (Claude probe), FR-14, FR-23+ (host app, widget, LaunchAgent, install), FR-30, FR-31.

### PRD

Read the full PRD at `<WORKDIR>/tmp/prd.md` (FR/NFR ids refer to it). It is the requirement source together with the instructions above.

## Conventions and git rules

- The repo has no CLAUDE.md/AGENTS.md; follow its existing style (README in English; code, docs, commits in English). Python 3.9 standard library only; must run under `/usr/bin/python3` (3.9.6). Add a Makefile with a `test` target (e.g. `/usr/bin/python3 -m unittest discover`).
- NFR-1: the Python code must contain none of `credentials.json`, `auth.json`, `security `, `keyring`, `oauth`, `refresh_token`, `anthropic.com`, `chatgpt.com`, `urllib`, `http.client`, `socket`, `URLSession`, `curl`, `/usr/bin/security`, `SecItem`, `kSecClass` (grep is case-sensitive per PRD; the FR-9 env var names are the only exception, not relevant here). Never open, read or copy any credentials file, including `~/.codex/auth.json`; only `stat -f '%m %i %z'` it for the step 2 check.
- NFR-4: the repo is public. Before committing any fixture (e.g. a real app-server reply) or doc, replace email, org names, macOS login name, home paths (`/Users/<name>`), account directory names, account/user ids and plan identifiers that identify the user with placeholders. `git grep -i` for them must be empty.
- Tests use only fake `codex` executables on PATH; never run the real `codex` or `claude` in tests.
- The real `codex app-server` may be run by hand only to confirm the protocol (one real reply) and for the step 2 `auth.json` stat check; send only `initialize`, `initialized`, `account/rateLimits/read`. Confirm the protocol first from official docs or the published schema (e.g. `codex app-server generate-json-schema` or the openai/codex repo docs) before the live run.
- No mutation testing: while building, reviewing or testing, never modify the source to see what happens: no manual or tool-driven mutation testing (mutmut etc.), not even briefly or in a throwaway copy that is then run; never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call such as `os.listdir`, leaving the code under test unmodified. Every brief to a sub-agent (producer, reviewer) carries this rule.
- Commit only to the branch below; never touch `main` or any other branch; force-push only with `--force-with-lease`.

## Docs

Spec and plan doc stay where autopilot puts them; S7 copies them to where the repo keeps design docs; never `git add -f` them.

## Workspace

Work only in `<WORKTREE>` on branch `TASK-585-quotaboard-collect-codex-m1-tracer-bulle`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After each task and review round, run exactly `git -C <WORKTREE> push -u origin TASK-585-quotaboard-collect-codex-m1-tracer-bulle`.

## Progress log

S1 done: mode=stay publish=none
checked(app-server-protocol): codex app-server generate-json-schema (codex-cli 0.163.0) -> ClientRequest initialize{clientInfo{name,version}}, ClientNotification initialized, account/rateLimits/read (params optional) -> GetAccountRateLimitsResponse{rateLimits{primary,secondary: RateLimitWindow{usedPercent:int,windowDurationMins:int|null,resetsAt:int|null}|null}}; JSON lines on stdio without "jsonrpc" field
checked(auth-json-stat): live app-server read on ~/.codex with codex sessions running (two sessions) -> stat -f '%m %i %z' auth.json identical before and after (values not recorded); FR-32 not needed
checked(live-reply): real reply has primary={usedPercent:87,windowDurationMins:10080,resetsAt:...}, secondary=null (no 5h window); a server notification remoteControl/status/changed arrives before the id=2 response
fork(absent-window): options=[absent-is-no-limit, absent-is-unknown, absent-is-zero]; criteria=[verdict matches what the account can actually do, no fabricated numbers in snapshot, least departure from PRD format]; prior=absent-is-no-limit
decision(absent-window): chose absent-is-no-limit over absent-is-unknown, absent-is-zero - verdict matches the account, no invented numbers, nothing reads the snapshot yet; dissent: none (2 members flag it as the author's call in principle; decided per common Council, flagged in the PR); tally=absent-is-no-limit:3
S2 done: spec .autopilot/quotaboard-collect-codex-spec.md, check-spec OK
S3 panel: core=[architecture-reviewer, spec-fitness-reviewer] +optional=[security-reviewer] transport=Workflow
S3 r1: architecture=PASS spec-fitness=FAIL security=FAIL -> spec-fitness#1 OSError on spawn/write/read must map to ProbeError; spec-fitness#2 security#1 absolute home paths in spec/plan reach the public repo at S7, AC27 grep scope too narrow; fixing
S3 r2: architecture=PASS spec-fitness=PASS security=PASS -> spec passed; adopted architecture#2 (D9) and security#6 (hermetic PATH)
S4 done: 6 tasks
S5 task 1 done: 568fef5 red=2
S5 task 2 done: 2b7e8dc red=13 (module missing)
S5 task 3 done: de1bea9 red=14 (module missing)
S5 task 4 done: f69035b red=12
S5 task 5 done: 2c7272f red=3 (+ test_codex module missing)
S5 task 6 done: 13a2474 red=none (docs)
decision(panel): dropped performance-reviewer - one short CLI run every 5 min, sequential probes bounded by 10 s each, no hot path
S6 panel: core=[correctness-reviewer, doc-reviewer, requirement-fidelity-reviewer, verification-reviewer] +optional=[architecture-reviewer, code-quality-reviewer, test-reviewer] verification=local transport=Workflow
S6 r1 @13a247489110059c71d8f9615852d089c742258c: correctness=PASS doc=PASS requirement-fidelity=FAIL verification=PASS (command=make check, exit code=0, tests=76, failures=0) architecture=PASS code-quality=PASS test=PASS -> requirement-fidelity#1 Makefile NFR-1 grep skips bin/quotaboard (BSD --include); fixing
S6 r2 @aef7344: correctness=PASS doc=PASS requirement-fidelity=PASS verification=PASS (command=make check, exit code=0, tests=79, failures=0) -> all lenses pass; converged
residual NON-BLOCKING: architecture#2 (store.snapshot_path for FR-11), architecture#3 (keep args.probe for FR-8), architecture#5/code-quality#4 (window keys in three places), code-quality#3 (--probe parsed, no effect yet), verification#1 (ResourceWarning lines in test output)

## Review items

### S3 r1
- spec-fitness#1 BLOCKING: only EOF and FileNotFoundError map to ProbeError; BrokenPipeError after fake exit 1 or PermissionError (non-executable codex) escape, collect crashes. Fix: map any OSError on spawn, write or read to ProbeError, state reason text.
- spec-fitness#2 BLOCKING: spec header and D2 embed absolute /Users/<login> paths; S7 copies the spec into the public repo, AC27 grep would fail. Fix: sanitize spec and plan before the S7 copy.
- security#1 BLOCKING: AC27 scope and grep list narrower than NFR-4: copied spec/plan out of scope; account dir names, email, org name missing from the grep. Fix: widen scope and list, grep the final tree after the S7 copy.
- architecture#1 NON-BLOCKING: read shape check misses malformed known fields (window not dict, non-int times) -> TypeError under lock forever. (adopted: AC8 widened)
- architecture#2 NON-BLOCKING: accounts.load and store.read write stderr themselves; cli should own stderr. (not adopted)
- spec-fitness#3 NON-BLOCKING: two windows with the same duration unspecified. (adopted: unrecognized)
- spec-fitness#4 NON-BLOCKING: FR-15 for used_percent null with past resets_at unspecified. (adopted: becomes 0)
- spec-fitness#5 NON-BLOCKING: AC10/AC13 need a named fake mode proving group kill. (adopted)
- security#2 NON-BLOCKING: error code from untrusted output to stderr; require int. (adopted)
- security#3 NON-BLOCKING: unbounded line buffer; cap 1 MiB. (adopted)
- security#4 NON-BLOCKING: do not publish auth.json stat values. (adopted)
- security#5 NON-BLOCKING: test 0600 kept on replace. (adopted: AC29)
### S3 r2
- architecture#2 NON-BLOCKING (repeat): store.read/accounts.load print stderr themselves. (adopted: D9)
- security#6 NON-BLOCKING: tests keep the inherited PATH; a missing/non-executable fake falls through to the real codex. Fix: PATH = fake-bin:/usr/bin:/bin. (adopted)
### S6 r1 @13a2474
- requirement-fidelity#1 BLOCKING: Makefile --include='*.py' makes BSD grep skip bin/quotaboard; NFR-1 check never looks at the entry script. Fix: add --include=quotaboard. (fixed)
- correctness#1 NON-BLOCKING: deeply nested JSON raises RecursionError (not ValueError) in codex/store read -> crash. (fixed, also accounts)
- verification#1 NON-BLOCKING: make check exit 0, 76 tests; ResourceWarning lines in test output (non-failing).
- verification#2 NON-BLOCKING: NFR-4 grep clean except pre-existing tests/fixtures/claude-usage/observations.json <WORKDIR> paths (not this build's work).
- verification#3 NON-BLOCKING: spec and plan contain absolute work paths; sanitize before the S7 copy.
- architecture#1 NON-BLOCKING: codex.probe uses global os.environ; pass environ through. (fixed)
- architecture#2 NON-BLOCKING: add store.snapshot_path for the FR-11 throttle. (deferred to step 3)
- architecture#3 NON-BLOCKING: cli discards parse_args result; keep args.probe for FR-8. (deferred to step 3)
- architecture#4 NON-BLOCKING: HOME resolution duplicated in accounts.home and store.state_dir. (fixed)
- architecture#5 NON-BLOCKING: window key names in three places (codex.WINDOWS, derive.WINDOWS, store.default_row). (not adopted)
- code-quality#1 NON-BLOCKING: store.state_dir re-implements accounts.home. (fixed, same as architecture#4)
- code-quality#2 NON-BLOCKING: accounts.load calls expand twice per client. (fixed)
- code-quality#3 NON-BLOCKING: --probe parsed and discarded. (not adopted: FR-21 requires accepting it)
- code-quality#4 NON-BLOCKING: codex.WINDOWS and derive.WINDOWS name the same windows. (not adopted, same as architecture#5)

## Notes

- Run tests: make -C <worktree> check (76 tests, ~10 s). Fake codex in tests/helpers.py (FAKE_CODEX), behaviour via $CODEX_HOME/fake.json.
- Real reply lives only in the scratchpad (live_reply.jsonl); committed fixture is sanitized.

## Verify command

`make -C <WORKTREE> check` (runs `/usr/bin/python3 -m unittest discover -s tests -t .` then the NFR-1 grep)

## Task list

Spec: <WORKTREE>/.autopilot/quotaboard-collect-codex-spec.md

Global Constraints: Python 3.9 stdlib only, run with `/usr/bin/python3`; no NFR-1 strings in Python code (see spec Makefile); tests hermetic (temp HOME, XDG_CONFIG_HOME, QUOTABOARD_STATE_DIR; PATH=`<fake-bin>:/usr/bin:/bin`); never run real `codex`/`claude` in tests; commit trailer `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; conventional commit subjects; no mutation testing.

### Task 1: skeleton, CLI parsing, Makefile
- Files: `quotaboard/__init__.py`, `quotaboard/__main__.py`, `quotaboard/cli.py`, `bin/quotaboard`, `Makefile`, `tests/__init__.py`, `tests/helpers.py` (Env with run_cli), `tests/test_cli.py`.
- Produces: `cli.main(argv=None) -> int`; `tests.helpers.Env` (temp HOME/config/state, fake-bin PATH, `run(*args) -> CompletedProcess` of `bin/quotaboard`).
- Tests first: AC22 usage errors (exit 2, usage on stderr); `collect` and `collect --probe` exit 0, stdout empty (stub collect).
- Checks: `make test`, `make check`.
- Commit: `feat: quotaboard package, entry point and Makefile`

### Task 2: account list
- Files: `quotaboard/accounts.py`, `tests/test_accounts.py`.
- Produces: `Account(name, client, dir)`, `AccountsError`, `config_path(environ)`, `load(environ) -> (threshold, [Account], hint)`.
- Tests first: AC1, AC2 (defaults, partial, none), AC3 each case, AC4 threshold cases incl. `true`, `null`.
- Checks: `/usr/bin/python3 -m unittest tests.test_accounts`.
- Commit: `feat(accounts): load and validate the account list`

### Task 3: derived fields
- Files: `quotaboard/derive.py`, `tests/test_derive.py`.
- Produces: `recompute(snapshot, threshold, now) -> None`.
- Tests first: AC15 (incl. null percent, absent window), AC16 (all listed cases incl. D1), AC17, AC18, AC19 boundary.
- Checks: `/usr/bin/python3 -m unittest tests.test_derive`.
- Commit: `feat(derive): availability, summary, order and stale`

### Task 4: snapshot store and collect without probes
- Files: `quotaboard/store.py`, `quotaboard/cli.py`, `tests/test_store.py`, `tests/test_cli.py`.
- Consumes: `accounts.load`, `derive.recompute`. Produces: `store.state_dir(environ)`, `store.read(path) -> (dict|None, warning|None)`, `store.write(state_dir, accounts, threshold, updates, failed=(), now=None) -> list[str]`.
- Tests first: AC5, AC29, AC6 (concurrent writers via subprocess), AC7 (patch `json.dumps`), AC8 (garbage + malformed fields + mode 000), AC20, AC21, AC23 (claude row), AC24, AC3 snapshot unchanged, AC2 hint via CLI, `failed` fallback cache/none (D7).
- Checks: `/usr/bin/python3 -m unittest tests.test_store tests.test_cli`.
- Commit: `feat(store): locked snapshot store and collect command`

### Task 5: Codex app-server probe
- Files: `quotaboard/codex.py`, `quotaboard/cli.py`, `tests/fixtures/codex-app-server/rate-limits-read.jsonl`, `tests/helpers.py` (fake codex), `tests/test_codex.py`, `tests/test_cli.py`.
- Consumes: `store.write(..., updates, failed)`. Produces: `codex.ProbeError`, `codex.probe(codex_home, timeout=10.0) -> dict`, `codex.parse_rate_limits(result) -> dict`.
- Tests first: AC9, AC10 (spawn_child+hang), AC11 (fixture, map by duration, absent replaces old), AC12 (each case), AC13 (timeout=1), AC14, CLI failure → cache/none.
- Fixture: sanitized from the live reply (scratchpad live_reply.jsonl) per spec.
- Checks: `/usr/bin/python3 -m unittest tests.test_codex tests.test_cli`; `make check`.
- Commit: `feat(codex): read 5h and 7d limits from codex app-server`

### Task 6: docs
- Files: `docs/codex-app-server.md`, `README.md`.
- Content per spec (protocol, step 2 result without stat values, D1; README Development section).
- Checks: AC27 grep on changed files.
- Commit: `docs: codex app-server protocol and development notes`
