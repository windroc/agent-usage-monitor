Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-645-host-app-accounts-json base_ref=a59f5873d84683ad62f42fa3c52f5287aa47421f review_round=1 input_sha=65fcda6d56c0

# Plan: TASK-645 PR gate fixes on #9

## Input

Verbatim in <WORKDIR>/tmp/input2.md (input_sha 65fcda6d56c0). Fix correctness#3 (no `accounts` key opens as an empty table; use accounts.validate so it shows the FR-9 state) and requirement-fidelity#1 (keep a row's original dir string when its displayed value is unchanged; test). Leave correctness#2, #4, #5, #6, #7; keep them in the PR body. Earlier run: .autopilot/settings-window-plan.md (phase=done), docs/design/TASK-645-settings-window-plan.md.

## Verify

Verify command: `make check`
CI checks: ["make check"]

## Progress log

- S1 done: mode=stay, base_ref a59f587; PR #9 (draft) adopted.
- decision(fr9-via-validate): editable runs accounts.validate and treats its file-level problems (index None: top level not an object, threshold, accounts not a list) as the FR-9 state, with validate's own text; row problems stay editable, fixed on 保存. A threshold out of (0, 100] now also opens in the FR-9 state, as collect rejects it too. The window-only check (each item an object with string name, client, dir, account) stays, since the window cannot show other values.
- decision(dir-kept): save keeps the item's original `dir` string when abbreviate(original dir) equals the row's dir; otherwise writes the row's dir.

- S5 task 1 done: b8c3d17 red=3 (2 subtests error=None, dir rewritten); test_accounts+test_cli OK, pii-scan OK; pushed
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- S6 r1 pinned @b8c3d17
- S6 r1 @b8c3d17: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (CI check make check, success) -> converged
- note: the validate path also opens {"threshold": NaN} as unreadable (_bad_threshold fails `0 < nan`), so correctness#4 is covered by the #3 fix; the PR body says so (requirement-fidelity#2 below)
- residual NON-BLOCKING: requirement-fidelity#2, doc#1; earlier run's correctness#2, #5, #6, #7 left as is per the user
- S7: plan doc copied to docs/design/TASK-645-pr-gate-fixes-plan.md (paths as placeholders)

## Review items

### r1 @b8c3d17
- requirement-fidelity#2 NON-BLOCKING: [spec-drift] agent_usage_monitor/accounts.py:148: the validate path also sends {"threshold": NaN} to the FR-9 state, because _bad_threshold (accounts.py:62-63) fails `0 < nan`. That effectively closes correctness#4, which the user said to leave as is, and the decision(fr9-via-validate) entry in .autopilot/pr-gate-fixes-plan.md does not record it. Add a note to the plan log, and to the correctness#4 entry the PR #9 body keeps, saying the #3 fix now covers it, so the body does not list it as still open.
- doc#1 NON-BLOCKING: docs/design/TASK-645-settings-window-plan.md:78 and :88 describe the unreadable state as 'unparsable or uneditable' and 'accounts not a list'. They do not record that a missing accounts key or an out-of-range threshold now also opens as unreadable, or that unedited dirs are kept as written. The author's own plan log, .autopilot/pr-gate-fixes-plan.md:18, records both (decision(fr9-via-validate)). Neither statement is false, so this is only a missing note.
- verification#1 NON-BLOCKING: CI at b8c3d17 passed: make check (success); ci-verdict.py exit 0; reviewed_sha=b8c3d179a18c6fa4ee4384d4c219ef63f269ded9; HEAD and status unchanged before/after (clean)

## Notes

- Earlier run's Notes: .autopilot/settings-window-plan.md.

## Task list

Global constraints: no mutation testing (Engineer rule, every brief). Test data example.com only.

### Task 1: editable's FR-9 state from accounts.validate; save keeps unedited dirs

- Files: agent_usage_monitor/accounts.py, tests/test_accounts.py.
- Tests first: `{"threshold": 80}` and `{"threshold": 0, "accounts": []}` open with an error naming validate's problem, defaults shown, file unchanged; an untouched row whose file dir is `<home>/x` stays `<home>/x` after save, an edited row gets the new dir, a `~/x` row stays `~/x`.
- Checks: `/usr/bin/python3 -m unittest tests.test_accounts tests.test_cli`, `make pii-scan`.
- Commit: `TASK-645: settings window: file-level problems open as unreadable, unedited dirs saved as they were`
