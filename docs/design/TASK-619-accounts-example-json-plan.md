Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-619-repo-accounts-example-json base_ref=315af6e25637e13a513cc449ee6df9ee69a0b179 review_round=1 input_sha=585ab8a437f9

## Input

## Requirement (TASK-619: repo 加 accounts.example.json 样例)

Repo: windroc/agent-usage-monitor. Product was renamed (TASK-622): the local config is `~/.config/agent-usage-monitor/accounts.json` (honouring `${XDG_CONFIG_HOME}` as the code does), the package is `agent_usage_monitor`. Read the old name `quotaboard` in the ticket as the new names.

User (2026-10-17): the real config lives only locally at `~/.config/agent-usage-monitor/accounts.json` (never in the repo); the repo holds only an example.

Acceptance criteria:
1. Add `accounts.example.json` at the repo root: two Claude accounts and one Codex account; names as fake email-style values (`you@example.com`, `work@example.com`); `dir` also placeholder values. Fields exactly what `agent_usage_monitor/accounts.py` actually reads, including the `account` field (added by TASK-620; it now exists).
2. Add a test (in the repo's existing test style, e.g. `tests/test_accounts.py`): the example loads cleanly through `accounts.load`, so a stale example is caught.
3. README's "Account list" section: point to this file and say to copy it to `~/.config/agent-usage-monitor/accounts.json` and then edit it. JSON can't carry comments, so the explanation lives in the README.
4. Don't change name truncation: it keeps the start and cuts the end (user 2026-10-17).
5. NFR-4: no real email addresses anywhere. `make check` and CI pass. The pre-push hook scans for personal info (TASK-621); it is already enabled in the worktree via `make hooks`; if `tests/pii-allowlist.txt` needs nothing, add nothing.
Out of scope: the README demo screenshot `docs/images/widget-demo.png` (the commander takes it on the desktop; do not touch it).

## Rules
- Follow the repo's conventions (its `CLAUDE.md`/`AGENTS.md`/README) for code, docs and commits. Default branch is `main`; never push to or touch `main` or any branch other than the one below; force-push only with `--force-with-lease`.
- No mutation testing, whatever a plan or reviewer asks: never modify the source to see what happens (no manual or tool-driven mutation testing, not even briefly or in a throwaway copy); never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call, leaving code under test unmodified. Every brief to a sub-agent (producer, reviewer) carries this rule.

## Docs
The plan doc stays where autopilot puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

Work only in `<WORKTREE>` on branch `TASK-619-repo-accounts-example-json`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <WORKTREE> push -u origin TASK-619-repo-accounts-example-json`.

## Verify

Verify command: `make check`
CI checks: ["make check"]

## Progress log

- S1: mode=stay, publish=ci, base_ref=315af6e
- decision(example-shape): `name` stays a unique id (`claude`, `claude-work`, `codex`); the fake emails (`you@example.com`, `work@example.com`) go in `account`, which TASK-620 added for exactly that and which may repeat; emails as `name` would need a third fake for codex. Same values as the README's current inline example.
- decision(readme): the README's inline JSON block moves into `accounts.example.json`; the README links to it instead (one home per fact).

- S5 task 1 done: 298775f red=1 (test_example_file: FileNotFoundError, no accounts.example.json)
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow

- S6 r1 @298775f: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (CI check make check success, ci-verdict exit 0) -> converged
- residual NON-BLOCKING: correctness#1

## Review items

- r1 correctness#1 (NON-BLOCKING): tests/test_accounts.py:129 test_example_file checks only the values that accounts.load returns. accounts.load (agent_usage_monitor/accounts.py:73-91) ignores unknown keys, so an unused key added to the example later (e.g. {"label": "x"} on an account, or a misspelled "acount") would still pass, and the 'fields exactly what accounts.py reads' rule would no longer be checked. Fix: also assert set(data)=={'threshold','accounts'} and that each item's keys == {'name','client','dir','account'}.
- r1 verification#1 (NON-BLOCKING): CI at 298775f passed: make check (success); ci-verdict.py exit 0.

## Notes

- `accounts.load(environ)` reads `${XDG_CONFIG_HOME:-$HOME/.config}/agent-usage-monitor/accounts.json`; each `dir` must exist (realpath, unique); fields: threshold, accounts[].name/client/dir/account.
- tests use `tests.helpers.Env` (temp HOME + XDG_CONFIG_HOME; `mkdir`, `write_accounts`); `helpers.ROOT` is the repo root.
- No CLAUDE.md/AGENTS.md in repo. Prior plan docs in `docs/design/TASK-<n>-<slug>-plan.md` replace absolute paths with `<AUTOPILOT>` / `<WORKTREE>` (pii scan rejects real home paths).
- Commit style: conventional, e.g. `feat(accounts): …`.

## Task list

Global Constraints: example values only `you@example.com`, `work@example.com`, dirs `~/.claude`, `~/.claude-work`, `~/.codex`, threshold 90. Name truncation (widget) untouched. `docs/images/widget-demo.png` untouched.

### Task 1: accounts.example.json, its load test, README pointer

- Files: `accounts.example.json` (new), `tests/test_accounts.py`, `README.md` (Account list section).
- Consumes: `accounts.load`, `accounts.Account`, `tests.helpers.Env`, `tests.helpers.ROOT`.
- Tests first: `test_example_file` in `LoadTest`: mkdir the three example dirs under the fake HOME, write the file's text via `env.write_accounts`, `load()` returns threshold 90 and the exact `Account` list (2 claude, 1 codex, accounts set), hint None. Red: file missing → FileNotFoundError.
- README: replace the inline JSON block with a pointer: copy `accounts.example.json` to `~/.config/agent-usage-monitor/accounts.json`, then edit; field explanations stay in the README prose.
- Checks: `/usr/bin/python3 -m unittest tests.test_accounts`, `/usr/bin/python3 tests/pii_scan.py`.
- Commit: `feat(accounts): accounts.example.json, loaded by a test`
