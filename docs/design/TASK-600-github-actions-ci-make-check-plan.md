Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-600-github-actions-ci-make-check base_ref=c6ab36c8a9e861b16a1bf6164fea2eff2fdb14ee review_round=1 input_sha=7464d6e183e5

## Input

## Requirement (TASK-600: GitHub Actions CI 跑 make check)

Repo: windroc/agent-usage-monitor (public). User instruction (2026-10-17): add CI to the repo; not in the M1 PRD.

Every PR and every push to `main` runs `make check` on a GitHub Actions macOS runner; the PR page shows pass or fail. The repo has no CI today; the PR gate is local `make check` only.

Acceptance criteria:
- A workflow in `.github/workflows/` runs `make check` on `pull_request` and on push to `main`.
- The runner uses the newest GA (not beta) macOS image among GitHub's official hosted runner images. First check the GitHub runner-images docs (github.com/actions/runner-images) to confirm that image ships `/usr/bin/python3` and a Swift toolchain able to build `macos/`; `make check` must not change behavior for CI.
- Third-party actions pinned by full commit SHA with a trailing comment naming the version; `permissions: contents: read`; no secrets.
- CI on this ticket's own PR has run and passed (the caller opens the PR and checks it; the verification reviewer reads the PR's CI result).
- Do not change rulesets or repo settings (making CI a required check is done by someone else after merge).
- NFR-4: commit no personal information (the repo is public).

## Rules
- Write code, docs and commits in the target repo's conventions (its `CLAUDE.md` / `AGENTS.md`). Default branch: `main`. Never merge into or otherwise touch any branch other than `TASK-600-github-actions-ci-make-check`; force-push only with `--force-with-lease`.
- No mutation testing, whatever a spec, plan or reviewer asks: never modify the source to see what happens: no manual or tool-driven mutation testing (mutmut etc.), not even briefly or in a throwaway copy that is then run; never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call such as `os.listdir`, leaving the code under test unmodified. Every brief to a sub-agent (producer, reviewer) carries this rule.

The plan doc stays where autopilot puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

Work only in `<WORKTREE>` on branch `TASK-600-github-actions-ci-make-check`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <WORKTREE> push -u origin TASK-600-github-actions-ci-make-check`.

## Verify

make check
CI checks: ["make check"]

## Progress log

- S1: mode=stay, branch TASK-600-github-actions-ci-make-check, base_ref c6ab36c
- decision(publish): pr.py start publish=none (no pull_request workflow before this run); verification=local; caller opens PR and watches its CI
- decision(runner): `macos-26` (macOS 26 Arm64, GA; `macos-latest` points to it, Xcode 27 image is preview). Pinned label, not -latest, so OS changes are explicit. Image README 20260907: Xcode CLT 26.6, Xcode 26.6 default, Python3 3.14 (brew) on PATH; make uses /usr/bin/python3 explicitly (CLT stub)
- decision(toolchain): job env DEVELOPER_DIR=/Library/Developer/CommandLineTools so xcrun/python3 use CLT like README's supported setup ("No Xcode needed"), not Xcode 26.6
- decision(action): actions/checkout v7.0.1 = 3d3c42e5aac5ba805825da76410c181273ba90b1 (lightweight tag, gh api)
- S5 task 1 done: 0f23541 red=none
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=local transport=Workflow
- S6 r1 @0f23541: correctness=PASS requirement-fidelity=PASS doc=PASS verification=PASS (command=make check, exit code=0, tests=124, failures=0; also with DEVELOPER_DIR=/Library/Developer/CommandLineTools: exit 0, tests=124) -> converged
- Residual NON-BLOCKING: verification#1 local verification only; the PR's macos-26 CI run is checked by the caller

## Review items

- r1 verification#1 (NON-BLOCKING): local verification only (verification=local); the PR's own CI run on macos-26 was not checked by this lens

## Notes

- Repo has no CLAUDE.md/AGENTS.md. `make check` = test (py unittest via /usr/bin/python3) + swift-test + app (xcrun swiftc, ad-hoc codesign) + NFR-1 grep + plutil + codesign verify.
- `app` target seds `$HOME` into build/com.windroc.quotaboard.plist (build dir, gitignored?).

## Task list

Global Constraints: runner `macos-26`; `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`; `permissions: contents: read`; no secrets; triggers `pull_request` + `push` branches `[main]`; job name `make check`; `make check` unchanged.

### Task 1: CI workflow running make check

- Files: `.github/workflows/check.yml` (new), `README.md` (Development: one line naming the CI).
- Consumes / Produces: none.
- Tests first: none (config); CI on the PR is the test.
- Checks: YAML parses (`ruby -ryaml -e 'YAML.load_file(ARGV[0])'`); no personal info grep.
- Commit message: `TASK-600: GitHub Actions CI 跑 make check`
