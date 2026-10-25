Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-589-claude-claude-config-dir base_ref=3676e392023da5936aa09095542152f2d3d12294 review_round=2 input_sha=9b262e871ce8

## Input

Verbatim copy: <INPUT> (TASK-589: probe non-default Claude accounts with CLAUDE_CONFIG_DIR=<dir>; default account keeps it unset; README + docstring; FR-31, NFR-1/2/4).

## Verify

`make check` (Makefile: unittest discover under /usr/bin/python3, swift-test, app build)
CI checks: ["make check"]

## Progress log

- decision(parse): TASK-583 fixtures use the same `resets <Mon D> at <h[:mm]am|pm> (<zone>)` form as TASK-572's; claude_usage.parse already passes both (tests/test_claude_usage.py test_config_dir_fixtures). No parser change.
- decision(api): claude.refresh gains `config_dir=None` after `environ`; cli passes None for the default account (claude.is_default), else account.dir.
- S5 task 1 done: 866fa5d red=4 (test_config_dir_for_other_accounts, test_other_accounts, test_default_account_keeps_config_dir_unset, test_account_files_untouched)
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- S6 r1 @866fa5d: correctness=PASS requirement-fidelity=PASS doc=FAIL verification=PASS (CI make check success) -> doc#1 README:7 status line says only default Claude account shown; fixed in f0cb920
- S6 r2 @f0cb920: doc=PASS verification=PASS (CI make check success); correctness, requirement-fidelity carry r1 PASS
- residual NON-BLOCKING: doc#2 (README:87 detail on claude-written files; kept because the requirement asks to list them)

## Review items

- r1 doc#1 BLOCKING: README.md:7 status line says the widget shows only the default Claude account; cli now probes every Claude account.
- r1 doc#2 NON-BLOCKING: README.md:87 lists claude-written files in more detail than needed; consider pointing to the TASK-583 report.
- r1 verification#1 NON-BLOCKING: CI at 866fa5d passed: make check.

## Notes

- Fake claude: tests/helpers.py FAKE_CLAUDE reads $HOME/fake-claude.json; logs env keys incl. CLAUDE_CONFIG_DIR.
- Collect probe gate: quotaboard/cli.py:39; env builder quotaboard/claude.py _environment.
- `--probe` no longer exists (TASK-603): every collect probes Claude; FR-8 text in the input is stale.
- Local unit tests: `/usr/bin/python3 -m unittest tests.test_claude tests.test_cli` from the worktree.

## Task list

Global Constraints: default account (`~/.claude` realpath) → env has no `CLAUDE_CONFIG_DIR`; any other Claude account → `CLAUDE_CONFIG_DIR=<account.dir>` (realpath); ARGS, probe dir, stdin, timeout, other env unchanged. Tool writes nothing in account dirs (FR-31). No real dir names, emails or `/Users/<user>` paths in commits (NFR-4).

### Task 1: probe non-default Claude accounts with CLAUDE_CONFIG_DIR

- Files: quotaboard/claude.py, quotaboard/cli.py, tests/helpers.py, tests/test_claude.py, tests/test_cli.py, README.md.
- Produces: `claude.refresh(name, row, state_dir, environ, config_dir=None, now=None, timeout=..., version_timeout=...)`; `_environment(environ, probe_dir, config_dir)`.
- Tests first:
  - RefreshTest: config_dir given → fake claude env `CLAUDE_CONFIG_DIR` equals it, also overriding a parent value; `--version` call (unrecognized path) gets the same env.
  - CollectProbeTest: list with two non-default accounts (no `~/.claude`), fake claude answers per `CLAUDE_CONFIG_DIR` with the TASK-583 A1 (no 5h reset) and B1 fixtures → both rows source `usage`, values match fixtures via derive.reset_window, A1 row 5h used 0 / resets null, `usage_disabled_version` null; mixed list default + non-default → default call has no `CLAUDE_CONFIG_DIR`, the other has its dir. Replaces test_only_default_account.
  - test_cli FR-31: account-files test adds a non-default Claude account; its settings.json mtime and its dir listing are unchanged after collect.
- Checks: `/usr/bin/python3 -m unittest tests.test_claude tests.test_cli tests.test_claude_usage`.
- Docs: README Claude section and TASK-583 line; claude.py module docstring.
- Commit: `TASK-589: probe non-default Claude accounts with CLAUDE_CONFIG_DIR`
