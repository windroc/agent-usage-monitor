Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=WDRC-91-available-again-alert-fires-late-after-a base_ref=c4415bf52f30ec9e2ae87f0ae3ec89f1101ba2ea review_round=1 input_sha=ecb670aa44df

## Input

Fix WDRC-91: "available again" alert fires late after an early window reset. Repo windroc/agent-usage-monitor.

## Requirement

### Problem
The "available again" alert fires days late when a provider resets a window before the `resets_at` recorded in the alert key.

Observed on the Codex account (2026-10-24):

| When | Snapshot | `notified` |
| -- | -- | -- |
| 10-18 08:13 | Codex 7d at or above threshold, alert sent | key `codex` / `seven_day`, `resets_at` 10-24 20:22 |
| 10-22 21:38 | Codex 7d at 11%, `resets_at` 10-29 13:38 (the window already reset) | same key, still pending |
| 10-24 20:23 | Codex 7d at 36%, `resets_at` 10-30 13:43 | key removed, alert "codex · <account> available again" shown |

The user got "available again" about two days after Codex was usable again, at a moment when nothing changed, which reads as a false alert.

### Cause (source)
`agent_usage_monitor/alerts.py` `evaluate`, inner `ended(k)`: checks only the key's stored `resets_at <= now`; it falls back to the current `used_percent < threshold` only when the key has no `resets_at`. A window that resets early (new `resets_at`, usage below threshold) is not treated as ended until the old `resets_at` passes; the following lines then emit the late alert. The 36% value itself is not stale (not a fetch bug).

### Acceptance criteria
* A notified key also ends when the row's current window for that key exists and either its `resets_at` is not the same reset as the key's (`_same_reset`) or its `used_percent` is below the threshold. The "available again" alert then fires on the first collect after the early reset.
* Unchanged: a key whose stored `resets_at` has passed still ends; a key for a window the row no longer reports still ends at its stored `resets_at`; no alert when the row is not `available`.
* No duplicate alert: after the early-reset "available again", a later collect does not emit it again (after `apply` removes the key), and a new full alert for the new window is still possible.
* Unit tests in `tests/test_alerts.py` cover the early-reset case (the table above as fixture data, with epoch timestamps for those dates; use a placeholder account name, never a real one — the repo's `make pii-scan` forbids personal data) and the unchanged cases.
* `make check` passes.

### Out of scope
Alert wording, thresholds, the widget, Codex 5h handling (the account reports no 5h window).

## Conventions and git rules
- Follow the repo's conventions (its README / docs, existing code style in `agent_usage_monitor/alerts.py` and `tests/test_alerts.py`); keep the change minimal and match the surrounding comment density.
- Commit only to this branch; never merge into or touch any other branch, including `main` (the default branch). Never rebase; force-push only with `--force-with-lease`.
- **No mutation testing**, whatever a spec, plan or reviewer asks: while building, reviewing or testing, never modify the source to see what happens: no manual or tool-driven mutation testing (mutmut etc.), not even briefly or in a throwaway copy that is then run; never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call such as `os.listdir`, leaving the code under test unmodified. Every brief to a sub-agent (producer, reviewer) carries this rule.

The plan doc stays where autopilot puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

Work only in `<WORKTREE>` on branch `WDRC-91-available-again-alert-fires-late-after-a`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <WORKTREE> push -u origin WDRC-91-available-again-alert-fires-late-after-a`.

## Verify

`make check` (macOS only: xcrun, codesign, plutil; runs on CI `macos-26`)
CI checks: ["make check"]

## Progress log

- decision(worktree): resolver mode=stay on the run branch.
- S5 task 1 done: 56bfb0e red=test_available_again_after_early_reset,test_available_again_below_threshold_before_reset,test_early_reset_while_not_available_no_alert
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- S6 r1 @56bfb0e49cb6c45302a087e72854adc20a524481: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (command=make check on CI run 40157774350, conclusion=success, tests=unknown, failures=0) -> converged
- decision(publish): ci-verdict.py gets HTTP 403 (NO_CI) on the REST check-runs API; the verifier read CI via `gh pr checks` / `gh run view`.
- Residual NON-BLOCKING: verification#1, verification#2, verification#3 (evidence notes only).

## Review items

- S6 r1 BLOCKING: none.
- verification#1 (NON-BLOCKING): ci-verdict.py exited 3 (NO_CI: gh api --paginate failed: HTTP 403); fell back to gh pr checks / gh run view for the PR's CI job, since `make check` is macOS-only and this host is Linux.
- verification#2 (NON-BLOCKING): CI `make check` on PR #1 (run 40157774350, headSha 56bfb0e = reviewed_sha): conclusion success, pass in 2m24s; per-test counts not extracted (unknown).
- verification#3 (NON-BLOCKING): Frozen worktree: HEAD 56bfb0e and empty status before and after; no local checks run, so no state leaked.

## Notes

- Run tests without cd: `/usr/bin/python3 -m unittest discover -s <wt>/tests -t <wt> -p test_alerts.py`; pii_scan needs cwd=<wt> (uses `git ls-files`).

- Design docs live in `docs/design/<ID>-<slug>-plan.md`; S7 copies this plan doc to `docs/design/WDRC-91-early-reset-alert-plan.md`.
- Unit tests: `/usr/bin/python3 -m unittest tests.test_alerts` from the repo root (Makefile `test`: `-m unittest discover -s tests -t .`).
- README.md line 64 documents when "available again" fires; it must name the early reset too.
- Tests drive `store.write` via `AlertsTest.write`/`seed`; `w(pct, at)` builds a window; account `cx` is codex with no email (label `codex · cx`).

## Task list

Global Constraints: threshold default in tests 90; `SAME_RESET` 600 s; `derive.WINDOWS` keys `five_hour`, `seven_day`; a row's window is `None` or `{"used_percent", "resets_at"}` (either may be `None`); `available` is True only when every reported window has a known `used_percent` below threshold. No new state or data shape. Draft PR: opened by CI publish (`pr.py`), none yet.

### Task 1: End a notified key on an early window reset

- Files: `agent_usage_monitor/alerts.py` (`evaluate` › `ended`), `tests/test_alerts.py`, `README.md` (line 64, the "available again" bullet).
- Consumes / Produces: none across tasks.
- Behavior: `ended(k)` is true when the row's window `k["window"]` is not `None` and either `not _same_reset(k["resets_at"], w["resets_at"])` or its `used_percent` is not `None` and `< threshold`; otherwise true when `k["resets_at"]` is not `None` and `<= now`. (The old no-`resets_at` fallback is subsumed.)
- Tests first (red before the code where the behavior is new):
  - Early reset, the issue's table as fixture (local times via `time.mktime`, account `cx`, 7d only): 10-18 08:13 7d ≥ threshold with `resets_at` 10-24 20:22 → full alert; 10-22 21:38 7d 11% `resets_at` 10-29 13:38 → `["codex · cx available again"]`, `notified` empty; 10-24 20:23 7d 36% `resets_at` 10-30 13:43 → `[]`; then 7d ≥ threshold in the new window → a new full alert.
  - Same reset but usage now below threshold before the stored `resets_at` → available again.
  - Unchanged: a key for a window the row no longer reports ends only at its stored `resets_at`; early reset while the row is not available (other window full) → no alert, key kept; a jittered `resets_at` (within `SAME_RESET`) still ≥ threshold → no alert.
- Checks: `/usr/bin/python3 -m unittest tests.test_alerts` from the worktree root; `/usr/bin/python3 tests/pii_scan.py`.
- Commit message: `fix(alerts): end a notified key on an early window reset (WDRC-91)`
