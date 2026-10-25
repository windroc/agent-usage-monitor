Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-880-english-widget-no-data-text-and-alert-no base_ref=756bd12cbd10cc738b82aa0689876542a0ffb498 review_round=1 input_sha=69563fdea342

## Input

# TASK-880: English widget no-data text and alert notifications

Repo: windroc/agent-usage-monitor (default branch `main`).

## Requirement (the user's instructions)

After TASK-877 (settings window, PR #13) the user wants the remaining Chinese user-facing text in English too:

* Widget no-data view: `macos/Widget/AgentUsageMonitorWidget.swift:58-59` (`Agent Usage Monitor：没有数据`, `点这里刷新`).
* Alert notification texts: `agent_usage_monitor/alerts.py:39-42` (reset time: `重置时间未知`, `%d月%d日`, `重置`), `:61` (`现在可用`), `:70` (`已到 %d%%，…`).
* README lines that quote them (README.md:57 no-data sentence, :63-64 Alerts).

What to build:

* English, short, consistent with the widget (`resets:` style). Suggested: no-data `Agent Usage Monitor: no data` / `click to refresh`; alerts `<label> <5h|7d> at <x>%, resets <time>` and `<label> available again`; reset time like `resets 14:05` today, `resets Oct 25 06:00` on another day, `reset time unknown`. Pick the final wording and list it in the plan doc's Notes (the caller copies it into the PR).
* Do not change the alert dedup keys stored in `notified` (their shape, fields or values): an upgrade must not re-send alerts already sent.
* Extend the CJK guard test (TASK-877 `tests/test_host_strings.py`) to `macos/Widget/*.swift` and `agent_usage_monitor/alerts.py`, and README's widget and Alerts sections.
* Update tests that assert these strings (e.g. `tests/test_alerts.py`, `tests/test_readme.py`).
* Any other remaining CJK user-facing text found in those same files/sections is in scope; other files are not.

Process (the user's): UI change. **Stop before S6**: once every S5 task is committed and pushed, set RESUME `phase=S6`, log "paused before S6: awaiting the user's preview on the real Mac (widget no-data view and one test notification)" in the progress log, and end with the `autopilot-result` block, `status` `stopped`, `reason` `paused before S6 for user preview`. Do not start S6; S6 review runs only after the user approves, on a later resume.

## Rules

* Write code, docs and commits in the target repo's conventions (match surrounding code style, comment density, commit message style `TASK-880: …`). The repo has no CLAUDE.md / AGENTS.md; follow README and existing code.
* Git: push only branch `TASK-880-english-widget-no-data-text-and-alert-no`; force-push only with `--force-with-lease`; never merge into or touch any other branch, `main` included.
* **No mutation testing**, whatever a spec, plan or reviewer asks: while building, reviewing or testing, never modify the source to see what happens: no manual or tool-driven mutation testing (mutmut etc.), not even briefly or in a throwaway copy that is then run; never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call such as `os.listdir`, leaving the code under test unmodified. Every brief to a sub-agent (producer, reviewer) carries this rule.

## Docs

The plan doc stays where autopilot puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

## Run constraints

Work only in `<WORKTREE>` on branch `TASK-880-english-widget-no-data-text-and-alert-no`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <WORKTREE> push -u origin TASK-880-english-widget-no-data-text-and-alert-no`.

## Verify

`make check` (macOS CI)

CI checks: ["make check"]

## Progress log

- S1: mode=stay, worktree=<WORKTREE>
- S1: pr.py start publish=ci base=main, no PR yet
- decision(wording): no-data `Agent Usage Monitor: no data` / `click to refresh`; alerts `<label> <5h|7d> at <x>%, resets <time>` and `<label> available again`; <time> `HH:MM` today, `<Mon> <d> HH:MM` another day (fixed English month abbreviations, not locale `%b`); unknown -> `<label> <5h|7d> at <x>%, reset time unknown`
- S4: task list written (2 tasks)
- S5 task 1 done: 285adea red=19 (test_alerts, test_cli, test_host_strings alerts.py + README Alerts)
- S5 task 2 done: 03e8c50 red=3 (test_host_strings widget swift + README widget paragraph)
- S5: pushed 03e8c50; macos/Tests/main.swift alert sample changed but swift-test not run locally (no Swift toolchain), CI runs it
- paused before S6: awaiting the user's preview on the real Mac (widget no-data view and one test notification)
- resume (mid-run input, the user 2026-10-23): approved on the real Mac (widget no-data view and a test alert); proceed to S6 review, draft PR, CI. Review cap stays 3 (skill cap; RESUME review_round=0 + 2 < 3)
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- S6 r1 pinned @03e8c50; PR PR #15 (draft by pr.py); CI pending
- S6 r1 @03e8c50: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (CI check make check, success, ci-verdict.py exit 0) -> converged
- S7: plan doc copied to docs/design/TASK-880-english-widget-alerts-plan.md
- Residual NON-BLOCKING: none

## Review items

- r1: no BLOCKING or NON-BLOCKING items (verification note only: CI at 03e8c50 passed make check)

## Notes

- Final wording: widget no-data `Agent Usage Monitor: no data` (headline) and `click to refresh` (caption); alert `codex · cx 5h at 92%, resets 17:00`, `codex · cx 7d at 91%, resets Oct 16 09:00`, `codex · cx 7d at 95%, reset time unknown`, `claude · you@example.com available again`.
- `notified` keys ({name, window, kind: "full", resets_at, sent_at}) are untouched: only alert `text` changes.
- No Swift toolchain on this Linux host: `make swift-test`/`make check` run only on CI (macos-26); local checks are `/usr/bin/python3 -m unittest` (python3 here).
- README widget text is the paragraph starting `The widget is a dark card` inside `## Install` (no own heading); Alerts is `## Alerts`.

## Task list

Global Constraints: alert dedup keys in `notified` unchanged; month names fixed `Jan`..`Dec`; English text only in the touched files/sections; no CJK in `macos/Widget/*.swift`, `agent_usage_monitor/alerts.py`, README widget paragraph and `## Alerts`.

### Task 1: English alert notifications

- Files: `agent_usage_monitor/alerts.py`, `tests/test_alerts.py`, `tests/test_cli.py`, `macos/Tests/main.swift` (alert-parser sample texts), `README.md` (Alerts bullets), `tests/test_host_strings.py`.
- Produces: alert texts `<label> <5h|7d> at <x>%, resets <time>`, `<label> <5h|7d> at <x>%, reset time unknown`, `<label> available again`.
- Tests first: test_alerts expectations in English (today, other day `Oct 16 09:00`-style, unknown, available again); test_cli assertions; CJK guard over `agent_usage_monitor/alerts.py` and README `## Alerts`.
- Checks: `python3 -m unittest discover -s tests -t .`
- Commit: `TASK-880: alert notifications in English`

### Task 2: English widget no-data view

- Files: `macos/Widget/AgentUsageMonitorWidget.swift`, `README.md` (widget paragraph), `tests/test_host_strings.py`, `tests/test_readme.py` if it quotes it.
- Tests first: CJK guard over `macos/Widget/*.swift` and the README widget paragraph.
- Checks: `python3 -m unittest discover -s tests -t .`
- Commit: `TASK-880: widget no-data view in English`
