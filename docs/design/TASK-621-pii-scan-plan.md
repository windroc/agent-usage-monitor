Rules: <AUTOPILOT>/skills/light-build/SKILL.md <AUTOPILOT>/references/autopilot-common.md <AUTOPILOT>/references/review-round.md
RESUME: phase=done worktree=<WORKTREE> branch=TASK-621-pre-push-hook-make-check base_ref=266940c1c01ca6f0baede59f7b947216d8a9e293 review_round=2 input_sha=4298f0ddbfac

## Input

# Requirement: TASK-621 个人信息扫描放进 pre-push hook 和 make check

Repo: windroc/agent-usage-monitor. Parent TASK-561, NFR-4 (repo is public). User 2026-10-17: the scan must be generic, live in the test layer, and run before push, since a branch pushed to the public repo is already public; CI only catches it afterwards.

## What to build

One scan script, used in two places:
- **pre-push hook**: scans locally before push; any hit rejects the push.
- `make check`: CI also runs it, as the last line of defense.

## Rules
1. Email: any email whose domain is not reserved for examples (`example.com`, `example.org`, `example.net`, `*.example`, RFC 2606) is a hit.
2. UUID: any UUID-shaped string is a hit.
3. Real home paths: `/Users/<name>`, `/home/<name>`. Placeholder names (e.g. `example`, `u`, `runner`; take the ones the repo already uses) go in the allowlist.
4. Allowlist: a versioned file; each entry states which value and why it is allowed. Each new entry must be explained separately in the PR.

## Acceptance criteria
- [ ] Scan covers all git-tracked text files. Binary files (PNG etc.) are at least checked for metadata blocks such as EXIF and XMP (TASK-605's screenshots were cleaned once already).
- [ ] The pre-push hook also scans the message and author email of every commit being pushed. An author email that is a GitHub noreply address, or the attribution's `noreply@anthropic.com`, is allowed and is written into the allowlist.
- [ ] The hook file lives in the repo, e.g. `.githooks/pre-push`. A fresh clone enables it automatically or with one command: e.g. `make install` or `make check` also sets `git config core.hooksPath .githooks` (repo-local config; never touch the user's global git config). README says how to enable it.
- [ ] First run a full scan against current `main`. Never paste hit values into the PR; give only file and line number; list uncertain ones for the user to decide whether to allow.
- [ ] Tests: each rule has at least one hitting and one non-hitting example (fake values). `make check` and CI pass.
- [ ] No real value appears in the PR description or commit messages.

## Conventions and git rules
- Follow the target repo's conventions (its `CLAUDE.md` / `AGENTS.md`) for code, docs and commits. Default branch: `main`.
- **No mutation testing**: never modify the source to see what happens: no manual or tool-driven mutation testing (mutmut etc.), not even briefly or in a throwaway copy that is then run; never put a known-wrong value into shipped code to force a branch. A test's red step is its failure before its code exists. To test a guard, call it; to fake the environment, patch a stdlib call, leaving the code under test unmodified. Every brief to a sub-agent (producer, reviewer) carries this rule.
- Push only branch `TASK-621-pre-push-hook-make-check`; force-push only with `--force-with-lease`. Never merge into or otherwise touch any other branch.
- Never write user config (`~/.gitconfig`, global git config, dotfiles); `core.hooksPath` only via repo-local `git config`.
- Real hit values (emails, UUIDs, home paths found in the repo) must not appear in commits messages, the plan doc, or any PR text; refer to them by file:line only. Test fixtures use fake values only.

## Docs
The plan doc stays where autopilot puts it; S7 copies it to where the repo keeps design docs; never `git add -f` it.

## Run constraints
Work only in `<WORKTREE>` on branch `TASK-621-pre-push-hook-make-check`, with absolute paths; create no other clone, worktree or branch.
Commits merged from `origin/main` are not this build's work.
Your and your producers' local checks, in every phase: only lint and the unit tests of the projects you changed; never integration tests or full suites: the verification reviewer runs them, on the PR's CI when the repo has a `pull_request` workflow, else locally.
Ask for no pull request: the caller opens it, onto `main`.
After S5 and each fix, run exactly `git -C <WORKTREE> push -u origin TASK-621-pre-push-hook-make-check`.

## Verify

make check
CI checks: ["make check"]

## Progress log

- S1: mode=stay, branch TASK-621-pre-push-hook-make-check, base_ref 266940c.
- S1 publish=ci (pr.py start); verification=ci planned.
- decision(location): scanner tests/pii_scan.py, allowlist tests/pii-allowlist.txt, tests tests/test_pii_scan.py (user: scan lives in the test layer).
- decision(push-scope): hook scans blobs and commits in `git rev-list --objects <local shas> --not --remotes=<remote>`: exactly what the push publishes, intermediate commits and binaries included.
- decision(enable): `make hooks` sets repo-local core.hooksPath; `check` depends on it.
- decision(values): scanner prints path:line and rule only, never the value (CI logs of a public repo are public).
- decision(binary): a file with a NUL byte is binary; PNG: chunk walk flags eXIf/tEXt/zTXt/iTXt; other binaries: byte search for EXIF (`Exif\0\0`) and XMP (`<x:xmpmeta`, `<?xpacket`) markers.
- S5 task 1 done: 9a6e40b red=12 (module missing); make test 140 OK; make pii-scan exit 0.
- decision(allowlist): 8 entries, each used on main except `*@users.noreply.github.com` (author emails, Task 2); per-entry hit counts measured by removing each.
- S5 task 2 done: 9766119 red=4 (refusal tests passed pushes before the hook existed); make test 147 OK; make pii-scan exit 0; hook dry run on this branch: 2 author-email hits (local user.email), expected.
- decision(hook-local): hook not enabled in this clone (no make hooks/check locally) so the required push runs; verification=ci.
- S6 panel: pinned=[correctness,requirement-fidelity,doc,verification] verification=ci transport=Workflow
- S6 r1 @9766119: correctness=FAIL requirement-fidelity=PASS doc=PASS verification=FAIL (CI make check failure, NFR-1 grep) -> correctness#1 UUID \b misses word-adjacent UUIDs; verification#1 tests spell the attribution domain the NFR-1 grep forbids; fixing
- fix r1 7a32492 (pre-fix 9766119): also took correctness#2, correctness#5, doc#1.
- deferred(correctness#3): annotated tag objects (message, tagger) not scanned by the hook.
- deferred(correctness#4): git failures in the hook surface as a traceback without git's stderr (push still refused).


## Notes

- Repo: Makefile `PY := /usr/bin/python3`, tests `make test` = unittest discover -s tests -t .; commit subjects `TASK-<n>: ...`, trailer Co-Authored-By.
- CI `.github/workflows/check.yml` job name `make check`, actions/checkout depth 1 (file scan only in CI).
- Baseline scan of main (ad-hoc git grep, values not recorded): no UUIDs; non-example emails = iconset file name (Makefile:29, TASK-605/618 plans), SSH user in clone URLs (README:46, TASK-586/618 plans), attribution address (TASK-585/618 plans); home paths = placeholder names example/u/runner and an elided `...`. All certain non-personal -> allowlist.
- Local git author email is a real non-noreply address, as are past commits: once the hook is enabled, pushes of new commits authored with it are rejected (by design); report to the user, change no identity.

## Task list

Global Constraints: stdlib only, run with /usr/bin/python3; never print matched values; tests build hitting fake values at runtime (split literals) so the repo scan stays clean; tests touching git set GIT_CONFIG_GLOBAL=/dev/null, GIT_CONFIG_NOSYSTEM=1 and author/committer env, never user config.

### Task 1: file scan in make check

- Files: tests/pii_scan.py, tests/pii-allowlist.txt, tests/test_pii_scan.py, Makefile, README.md.
- Produces: `load_allowlist(path) -> list[str]` (fnmatch globs; each line `<pattern> <reason>`, `#` comments; a pattern without a reason is an error); `scan_text(text, allow) -> [(line, rule)]` rules `email`, `uuid`, `home-path`; `scan_binary(data) -> [rule]` (`metadata`); `scan_blob(data, allow)`; CLI `python3 tests/pii_scan.py` scans `git ls-files` in cwd, prints `path:line: rule`, exit 1 on hits.
- Tests first: per rule one hit and one non-hit (example.com/.org/.net/sub.example, *.example; UUID vs non-UUID hex; /Users/<fake> vs allowlisted placeholder); allowlist glob; reason-less entry rejected; PNG with tEXt/eXIf flagged, plain PNG not; JPEG-ish Exif and XMP markers flagged; CLI on a temp git repo: hit exit 1 without value in output, clean exit 0.
- Checks: `make test`; `/usr/bin/python3 tests/pii_scan.py` on the worktree exit 0.
- Commit: `TASK-621: scan tracked files for personal data in make check`.

### Task 2: pre-push hook

- Files: .githooks/pre-push, tests/pii_scan.py, tests/test_pii_scan.py, Makefile, README.md.
- Consumes: Task 1 functions. Produces: `--pre-push <remote>` mode reading pre-push stdin; scans new blobs (rev-list --objects --filter=object:type=blob) with scan_blob, and each new commit's message (scan_text) and author email (email rule); `make hooks` = `git config core.hooksPath .githooks`; `check: hooks pii-scan ...`.
- Tests first: e2e with a temp bare remote and clone, core.hooksPath -> this repo's .githooks: push rejected for hit in file / commit message / author email; accepted for clean commit with noreply author (GitHub noreply, noreply@anthropic.com); a hit only in an intermediate commit still rejected; branch delete push passes.
- Checks: `make test`; scanner on worktree exit 0.
- Commit: `TASK-621: pre-push hook scans pushed commits for personal data`.
