Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-620-widget-agent-agent base_ref=266940c1c01ca6f0baede59f7b947216d8a9e293 review_round=1 input_sha=091c8eb8da8a

## Input

# Requirement (TASK-620): widget 每行显示 agent 名字，账号（邮箱）用灰色小字，按 agent 分组排序

Repo: windroc/agent-usage-monitor. Parent: TASK-561. Design finalized by the user 2026-10-17 (text mock below, user-confirmed).

## Mock

```
┌────────────────────────────────────────────┐
│ claude    5H ▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱    0% │
│           7D ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰ ⚠ 100%│
│ you@example.com          resets in 17h 20m │
├────────────────────────────────────────────┤
│ claude    5H ▰▰▰▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱   16% │
│                           resets in 1h 20m │
│           7D ▰▰▰▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱   15% │
│ work@example.com           resets in 6d 7h │
├────────────────────────────────────────────┤
│ codex     7D ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▱▱▱▱▱   87% │
│ you@example.com            resets in 5d 6h │
└────────────────────────────────────────────┘
```

## Acceptance criteria

- [ ] Each account in `accounts.json` may carry one more optional field `account` (a display string, e.g. an email). `name` stays the unique identifier; different accounts may share the same `account`. The snapshot carries `account`, staying compatible with old snapshots and old account lists that lack the field.
- [ ] The left side of each account's first row shows `client` (claude, codex), bold, same size as the current name; `name` is no longer shown. The stale ⚠ stays at the very front as before.
- [ ] `account` shown in gray, same font size as `resets in`, left-aligned, on the account's **last reset row** (reset on the right). If the account has no reset at all, it takes its own row under the last bar. No `account` → nothing shown. Too long → truncate the tail.
- [ ] Sorting: group by client first (claude before codex, others alphabetical), within a group keep account-list order. If the existing sorting rule in the code conflicts with this, this rule wins (user 2026-10-17); the PR description must state what changed.
- [ ] Separator lines between accounts stay. `fit` height computation must count the case where the email takes its own row; `+k` still counts accounts.
- [ ] Tests: `account` reading and validation; which row the email goes on (with reset, without reset); sorting; `fit` height.
- [ ] README's Account list section and example JSON updated to the `account` form, fake emails only (NFR-4).
- [ ] Do not install into `~/Applications`; desktop acceptance is done by the commander. `make check` and CI both pass.

## Conventions and git rules

- Follow the target repo's conventions (its `CLAUDE.md` / `AGENTS.md`) for code, docs and commits. Default branch: `main`.
- No mutation testing, whatever a spec, plan or reviewer asks: while building, reviewing or testing, never modify the source to see what happens: no manual or tool-driven mutation testing (mutmut etc.), not even briefly or in a throwaway copy that is then run; never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call such as `os.listdir`, leaving the code under test unmodified. Every brief to a sub-agent (producer, reviewer) carries this rule.
- Push only branch `TASK-620-widget-agent-agent`; force-push only with `--force-with-lease`. Never merge into or touch any other branch.
- Never write user config (`~/.claude.json`, `~/.claude/settings*.json`, dotfiles); never run `make install` or install into `~/Applications`.

## Docs

The plan doc stays where autopilot puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

## Run rules

Work only in `<WORKTREE>` on branch `TASK-620-widget-agent-agent`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <WORKTREE> push -u origin TASK-620-widget-agent-agent`.

## Verify

Verify command: `make -C <WORKTREE> check`
CI checks: ["make check"]

## Progress log

- S1: mode=stay publish=ci
- decision(sort): replace derive.order_key (FR-18 availability order) with client grouping in the snapshot itself (derive.recompute), stable so list order holds within a group; widget shows snapshot order. summary.next becomes min available_at over waiting rows (first in snapshot order on a tie). Solo: requirement says this rule wins.
- decision(account-validation): `account` absent → None; present must be a non-empty string; duplicates allowed.
- decision(title): widget first-row label = (stale ? "⚠ " : "") + (client ?? name); name only as fallback for a row with no client (pre-client snapshots).
- decision(+k): +k needs its own line when the last account's bottom-left spot holds the account (own line, or on the last bar's reset line).
- S5 task 1 done: 0c6badb red=8 (test_account_display_string, test_invalid_account x4, test_new_rows_defaults, test_account_from_list; test_cli row keys updated)
- S5 task 2 done: b99898b red=1 (test_client_groups_keep_list_order; test_store summary order updated)
- S5 task 3 done: 8db7e84 red=compile (Row.account, DisplayRow.title/account/accountBar/accountLine missing): rows_sample, stale_title, account_bar, account_line, account_none_no_bars, fit_account_*, more_room_account, load_valid
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- S6 r1 @8db7e84ad839e674afe17b78c8f0e4d083e2b3cc: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (CI make check success on PR #16) -> converged
- residual NON-BLOCKING: requirement-fidelity#1, doc#1, verification#1 (evidence)

## Review items

- r1 requirement-fidelity#1 (NON-BLOCKING): the PR description must say what changed in sorting: FR-18 availability order (true, then false by time, then null) replaced by client grouping in list order (derive.py:30-34); summary.next is now the minimum available_at (derive.py:44-45). The caller opens the PR; the S7 PR body must carry both.
- r1 doc#1 (NON-BLOCKING): docs/design/TASK-585-quotaboard-collect-codex-spec.md:55 (AC18) and :63 (AC24 row keys) still describe availability-based order and a row without `account`; frozen design doc, optionally add a 'superseded by TASK-620' note like TASK-586 spec line 29.
- r1 verification#1 (NON-BLOCKING): CI at 8db7e84 passed: make check (success); ci-verdict.py exit 0; HEAD matched reviewed_sha, status empty.

## Notes

- No CLAUDE.md/AGENTS.md in repo. Unit tests: `make test` (python unittest), `make swift-test` (Snapshot.swift + macos/Tests/main.swift).
- View in macos/Widget/QuotaboardWidget.swift (not in swift-test); layout model in macos/Widget/Snapshot.swift.
- store.write sets name/client/dir from the account list on every write; derive.recompute sorts.

## Tasks

Global constraints: Python 3.9 stdlib only; `Account` keeps 3-arg construction (`account` defaults None); fake emails only (`you@example.com`, `work@example.com`); no `make install`.

### Task 1: optional `account` field in the account list and snapshot

- Files: quotaboard/accounts.py, quotaboard/store.py, tests/test_accounts.py, tests/test_store.py, README.md (Account list section and example JSON).
- Produces: `Account(name, client, dir, account=None)`; snapshot row key `account` (string or null).
- Tests first: account read; absent → None; non-string / empty → AccountsError naming `account`; two accounts sharing one `account` load; snapshot row carries `account`; an old snapshot row without `account` gets it on write; default row has `account: None`.
- Checks: `make test`.
- Commit: `feat(accounts): optional account display string in the list and snapshot`

### Task 2: order the snapshot by client, then list order

- Files: quotaboard/derive.py, tests/test_derive.py, tests/test_store.py, README.md (order sentence).
- Produces: snapshot accounts grouped claude, codex, other clients alphabetical; list order within a group; summary.next = earliest available_at among unavailable rows.
- Tests first: grouping with mixed availability keeps list order in group; unknown client sorts after codex alphabetically; next still earliest.
- Checks: `make test`.
- Commit: `feat(derive): group accounts by client, list order within a group`

### Task 3: widget shows client, account in gray on the last reset line

- Files: macos/Widget/Snapshot.swift, macos/Widget/QuotaboardWidget.swift, macos/Tests/main.swift, README.md (widget paragraph).
- Consumes: snapshot `account`. Produces: `Row.account`, `DisplayRow(title:client:account:bars:)`, `DisplayRow.accountBar: Int?`, `DisplayRow.accountLine: Bool`; `fit` and `moreRoom` count the account line.
- Tests first: title is client with ⚠ prefix; account on last reset bar (with reset); own line when no reset; no account → neither; fit height with own line; moreRoom with account; load snapshot with and without `account`.
- Checks: `make swift-test`, `make app` (compiles the view).
- Commit: `feat(widget): client label, account in gray on the last reset line`
