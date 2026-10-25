Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-630-security-review-ci-commit-nul-widget-fix base_ref=abb59d7c3eee18baca351eb9824dd4e4e92c998e review_round=1 input_sha=d1fcf10b1bfa

## Input

Verbatim copy: <WORKDIR>/tmp/input.txt (input_sha d1fcf10b1bfa).

## Verify

Command: `make check` (repo root; runs hooks, pii-scan, unit tests, swift-test, app build, NFR-1 grep, plist/codesign checks).
CI checks: ["make check"]

## Progress log

- S1: mode=stay, branch TASK-630-security-review-ci-commit-nul-widget-fix, base_ref abb59d7.
- decision(fixture-scope): only A1.find.txt:5 names a synced plugin; B1 has none. Same class elsewhere: the agent work dir path under `<HOME>` in tests/fixtures/claude-usage/observations.json (2x) and docs/design/TASK-585-quotaboard-collect-codex-plan.md:101 -> `<WORKDIR>`, the placeholder prior plan docs use. Not consumed by any test.
- decision(ci-range): CI scans `HEAD^1..HEAD^2` of the pull_request merge commit (actions/checkout's refs/pull/N/merge): exactly the PR's commits, no event-payload interpolation. fetch-depth: 0 set unconditionally (push to main gains full history; cheap; one config).
- decision(widget-log): fixed message, no path (option 2 of the requirement); `.private` still logs it when private logging is on.
- deferred(private-links): Linear workspace URLs and the private docs repo name in docs/design + docs/spikes are references, not synced plugin paths; left for the user.
- S5 task 1 done: 36a1b84 red=none (mechanical)
- S5 task 2 done: 3fe114e red=test_non_png_binary_runs_text_rules_without_nul_bytes
- S5 task 3 done: 30cd716 red=test_pr_commit_identity_and_message_hits_fail_without_values
- S5 task 4 done: 1b8de43 red=none (log text)
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- S6 r1 @1b8de43: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (CI check make check: success at 1b8de43) -> converged
- residual NON-BLOCKING: correctness#1, doc#1
- S7: plan doc copied to docs/design/TASK-630-security-hardening-plan.md with machine paths replaced by `<WORKTREE>`, `<AUTOPILOT>`, `<WORKDIR>`.

## Review items

- r1 correctness#1 NON-BLOCKING: tests/pii_scan.py:91-93: deleting NUL bytes joins the tokens on either side, so lookbehinds miss values in NUL-separated data (e.g. `find -print0` output): a home path or UUID right after a NUL-terminated token is not hit. Fix: also run the text rules with each NUL replaced by a newline, merge hits; add the case to the test.
- r1 doc#1 NON-BLOCKING: README.md:70-72 describes CI as only running `make check` and the PII scan as a pre-push hook; add a clause that CI also scans a pull request's commits (`--commits`).
- r1 verification#1 NON-BLOCKING: frozen worktree HEAD == 1b8de43, status clean; ci-verdict exit 0, make check success.

## Notes

- publish=ci: `pr.py push --task` is a no-op; the branch is pushed at S5 end and each round pin.

- No CLAUDE.md/AGENTS.md. Commit titles: `TASK-<n>: <Chinese summary>`. Prior plan docs copied to docs/design/TASK-<n>-<slug>-plan.md with machine paths replaced by `<WORKTREE>`, `<AUTOPILOT>`, `<WORKDIR>`.
- pii_scan output prints location + rule, never the value; tests split fake values so the repo's own scan stays clean.
- Unit tests: `/usr/bin/python3 -m unittest discover -s tests -t .`; scan: `/usr/bin/python3 tests/pii_scan.py`.
- Widget Swift compiled only by `make app` (swiftc ... AgentUsageMonitorWidget.swift).

## Task list

Global Constraints: no real personal values (names, emails, home paths, private plugin names) in code, fixtures, commits, logs or PR text. No mutation testing. Hit output never prints the value.

### Task 1: fixtures and docs drop private plugin and work-dir paths

- Files: tests/fixtures/claude-usage-config-dir/A1.find.txt (line 5 -> `<dir-a>/plugins/synced/<ORG_ID>_<SYNC_ID>/.staging/33428/<PLUGIN>/...`), tests/fixtures/claude-usage/observations.json (2 marker paths -> `<WORKDIR>/tmp/captures/A<n>-marker`), docs/design/TASK-585-quotaboard-collect-codex-plan.md:101 (work-dir path -> `<WORKDIR>`).
- Tests: none (mechanical); `git grep` for the plugin and work-dir names returns nothing.
- Checks: `/usr/bin/python3 -m unittest tests.test_claude_usage`, `/usr/bin/python3 tests/pii_scan.py`.
- Commit: `TASK-630: fixture 和文档里的私有插件路径、工作目录改成占位`

### Task 2: pii_scan runs text rules on non-PNG binaries

- Files: tests/pii_scan.py (scan_blob), tests/test_pii_scan.py.
- Produces: scan_blob(name, data, allow): PNG -> scan_binary only; other data with NUL -> scan_binary hits plus text-rule hits on data with NULs removed; text unchanged.
- Tests first: NUL-holding blob with an email -> `name:1: email`; NUL inside the value (split by NUL) still hits; PNG holding the value outside metadata chunks -> no text hit; binary with metadata marker and a value -> both.
- Checks: `/usr/bin/python3 -m unittest tests.test_pii_scan`, `/usr/bin/python3 tests/pii_scan.py`.
- Commit: `TASK-630: pii-scan 对 PNG 以外的二进制去掉 NUL 后照样跑文本规则`

### Task 3: CI scans the PR's commits like the pre-push hook

- Files: tests/pii_scan.py (`--commits <range>` mode sharing scan_push's rev scan), tests/test_pii_scan.py, .github/workflows/check.yml (checkout `fetch-depth: 0`; step on pull_request: `/usr/bin/python3 tests/pii_scan.py --commits HEAD^1..HEAD^2`).
- Produces: scan_revs(revs, allow) used by scan_push and `--commits`.
- Tests first: temp repo, range with a bad author email and a home-path message -> exit 1, `author: email`, `message:1: home-path`, no value in output; commits before the range not scanned; clean range -> exit 0.
- Checks: `/usr/bin/python3 -m unittest tests.test_pii_scan`; YAML parses.
- Commit: `TASK-630: CI 对 PR 的 commit 跑 pii-scan 身份和 message 扫描`

### Task 4: widget logs a fixed message

- Files: macos/Widget/AgentUsageMonitorWidget.swift:33.
- Tests: none (log text); compile via `xcrun swiftc -parse-as-library -application-extension -typecheck macos/Widget/Snapshot.swift macos/Widget/AgentUsageMonitorWidget.swift`.
- Commit: `TASK-630: widget 日志不再写 home 路径`
