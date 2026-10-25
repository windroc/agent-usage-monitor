# Agent Usage Monitor

A macOS desktop widget that shows, for every Claude Code and Codex account on one Mac, the 5-hour and 7-day usage limits, when they reset, and whether the account is usable right now. Pick an account before you start work without opening each one.

![Medium and large Agent Usage Monitor widgets: each account's name with 5H and 7D usage bars, percent and reset time (`resets: 2h 9m`), in the medium widget the 5H and 7D bars side by side, with the account and reset times on a second line; in the large one stacked, red from 90% with a warning triangle in the large one](docs/images/widget-demo.png)

> **Status:** in development (milestone M2). Installable: the widget shows every Codex and Claude account, and macOS notifications tell you when a limit is nearly used up or an account is usable again.

## How it works

```
LaunchAgent (every 5 min) ─┐
widget click ──────────────┴─> AgentUsageMonitor.app ─> agent-usage-monitor collect ─┬─> codex app-server (each run)
                                                                                     └─> claude -p /usage (each run)
                                                                       snapshot.json <─┘
                                                                             │
                                                               desktop widget (WidgetKit)
```

- `agent-usage-monitor collect` (Python 3.9 standard library) reads every account's limits at once, so a stuck CLI holds up only its own account, and writes one snapshot file that the widget displays.
- Codex limits come from `codex app-server` and Claude limits from `claude -p /usage`, every 5 minutes and when you click the widget.
- Each Claude account is a `CLAUDE_CONFIG_DIR`, each Codex account a `CODEX_HOME`.
- The host app runs `collect --emit-alerts` (on a widget click also `--retry-paused`) and posts the alerts it prints as macOS notifications ([Alerts](#alerts)).
- Opened from Applications, Spotlight or Finder instead, or from the gear in the widget's bottom-right corner, the host app shows the [settings window](#settings-window).

## Principles

- Only the official `claude` and `codex` CLIs talk to the network: no undocumented endpoints, no reading of credential files or the Keychain, no changes to your Claude or Codex settings.
- Checking usage does not spend quota: in testing, `claude -p /usage` made no model request ([spike report](docs/spikes/TASK-572-claude-usage.md)).
- Known risks of running `claude -p /usage` every 5 minutes:
  - The subscription login is meant for ordinary use of Claude Code ([legal and compliance](https://code.claude.com/docs/en/legal-and-compliance)); an unattended probe every 5 minutes may fall outside it.
  - A future `claude` that sends `-p /usage` to the model as a prompt instead of running the command would spend quota on every run.
- Builds with the Xcode Command Line Tools alone, ad-hoc signed, no Xcode or developer account ([widget spike](docs/spikes/TASK-573-clt-widget.md)).

## Requirements

- macOS 26 (tested on 26.7.1)
- Xcode Command Line Tools
- `/usr/bin/python3` (3.9)
- `claude` and `codex` on your login shell's `PATH`: `zsh -lc 'command -v claude codex'` prints both. The host app runs `agent-usage-monitor` through `/bin/zsh -l`, a login shell, which reads `~/.zprofile` but not `~/.zshrc`. If the check finds nothing but the CLIs are in `~/.local/bin` (their default install location), `collect` still finds them: it appends `~/.local/bin` to `PATH` when missing. Otherwise move the `PATH` lines from `.zshrc` to `.zprofile`.

## Install

Each step can be rolled back on its own.

| Step | Rollback |
|---|---|
| `git clone git@github.com:windroc/agent-usage-monitor.git ~/.local/share/agent-usage-monitor`, then `make -C ~/.local/share/agent-usage-monitor install`: builds and ad-hoc signs `AgentUsageMonitor.app`, copies it to `~/Applications/AgentUsageMonitor.app`, links `~/.local/bin/agent-usage-monitor`, creates `~/Library/Logs/agent-usage-monitor.log` (0600), writes `~/Library/LaunchAgents/com.windroc.agent-usage-monitor.plist` | `make -C ~/.local/share/agent-usage-monitor uninstall` |
| `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.windroc.agent-usage-monitor.plist`: runs `collect` now and every 5 minutes | `launchctl bootout gui/$(id -u)/com.windroc.agent-usage-monitor` |
| Only with accounts outside `~/.claude` and `~/.codex`: add them in the [settings window](#settings-window), or write `~/.config/agent-usage-monitor/accounts.json` ([account list](#account-list)) | Delete that file |
| Right-click the desktop › Edit Widgets, search `Agent Usage Monitor`, add the medium or large size | Remove the widget |

`make install` refuses to replace a `~/.local/bin/agent-usage-monitor` that is not its own link. Each rebuild changes the ad-hoc signature: after `make install` again, remove and re-add the widget if it stops updating. `make app` also stamps both bundles' `CFBundleVersion` with the build time, so macOS sees each install as a new build; Apple does not document whether that makes the widget gallery pick up changed sizes. `make install` also stops the running widget extension, matched by its installed path: the old process keeps serving the replaced bundle, so every widget reload fails with `Bundle version did not match` until it exits; macOS starts the new one on the next reload. `make uninstall` runs `launchctl bootout` first, then deletes the app, the link and the plist; delete `~/.local/state/agent-usage-monitor`, `~/.config/agent-usage-monitor` and `~/Library/Logs/agent-usage-monitor.log` yourself.

After `git pull`, run `make -C ~/.local/share/agent-usage-monitor install` again: the link makes the new CLI live at once, and it must match the installed host (an older host passes `--probe`, which the current CLI rejects with exit 2; an M1 host runs `collect` without `--emit-alerts`, so it sends no alerts; a host from before `record-alerts` never records its alerts, so it repeats them every run).

The widget is a dark card with one group per account, grouped by client ([account list](#account-list)) and separated by thin lines: the client (`claude`, `codex`), then one row per limit (`5H`, `7D`) with a progress bar and the percent, and under the percent when the limit resets, in days, hours and minutes without leading zero units (`resets: 38m`, `2h 9m`, `6d 1h 1m`; no line when unknown). The account's `account` string, if set, shows in small grey type at the left of its last reset line, or on a line of its own under the last bar when no limit shows a reset; a long one loses its tail. It shows as many accounts as its size fits; the rest show as `+<k>` under the last one. The bar is teal for Claude, periwinkle for Codex and grey for other clients, yellow from 80% and red from 90%, where a red triangle also precedes the percent; an unknown percent shows an empty bar and `—`, and a limit the account does not have shows no row. When the account's values are older than 6 hours (`stale`), a red triangle precedes the client. If its last probe failed, or it has no values yet, the reason `collect` recorded (`error` in its snapshot row, such as `timed out`, `cannot start claude: ENOENT` or `/usage unreadable · paused`) shows in yellow in place of its bars, like the login notice, and loses its tail when too long. A stale account without a reason (a snapshot from before WDRC-98) keeps its bars, and so does a failing account whose values are under 6 hours old; its reason is then only in the snapshot and the log. An account that needs login (`needs_login`, TASK-873) shows, instead of its bars, a yellow `needs login · claude /login` after the client, without the triangle; its account and line heights stay, so the medium widget still fits three accounts. There is no header line. This layout (TASK-595) replaces the PRD's FR-26 text rows. The medium widget packs each account into two lines (TASK-641): the client with the `5H` and `7D` bars side by side, a missing limit leaving its column empty; under them the account on the left and each reset time under its own bar; no red triangle before the percent, so the bars are longer; the rest of the rules are the same. A small grey gear sits at the bottom right, under the rows and right-aligned with the percents, in the widget's margin, so the medium widget still fits three accounts; it opens the [settings window](#settings-window). A click anywhere but the gear runs `collect` and refreshes the widget within about 30 seconds; it also retries a paused Claude account ([account list](#account-list)). A small grey refresh arrow just left of the gear does the same and shows that. With no snapshot it shows `Agent Usage Monitor: no data` over `click to refresh`, the arrow and the gear; click the widget or the arrow to collect.

## Alerts

Each host run (every 5 minutes and on a widget click) runs `collect --emit-alerts`; a widget click adds `--retry-paused`. Under the same lock as the snapshot write, `collect` decides the alerts from the snapshot and prints each as an `AUM-ALERT {"text": …, "add": […], "remove": […]}` line, where `add` and `remove` are the `notified` entries the alert records and clears; the host posts them as notifications titled Agent Usage Monitor, then passes the lines macOS took to `record-alerts`, which makes those changes. Without `--emit-alerts`, `collect` decides no alerts and prints nothing.

- `<client> · <account> <5h|7d> at <x>%, resets <reset>`: a limit is at or above `threshold` ([account list](#account-list)). `<account>` is the account's `account`, else its `name`; `<reset>` is the local reset time, `14:05`, with the date when it is not today, `Oct 25 06:00`; with no reset time the clause reads `reset time unknown`.
- `<client> · <account> available again`: an account that had such an alert is available again, after that limit's reset: its recorded reset time has passed, the provider reports a reset time more than 10 minutes from it (an early reset), or the limit is below `threshold`.

Each alert is sent once: `record-alerts` records it in the snapshot's `notified` list, under the same lock, once macOS has it (account, limit, reset time, `sent_at`), and `collect` alerts on that limit again only for a reset time more than 10 minutes from the recorded one; entries older than 7 days are dropped. An alert macOS did not take (notifications not allowed, no answer to the prompt, a posting error or timeout) is logged to `~/Library/Logs/agent-usage-monitor.log`, kept for the next run and sent again then. While the Mac sleeps nothing is collected; the first run after waking alerts on the current state.

The first alert makes macOS ask whether Agent Usage Monitor may send notifications: click Allow, or turn them on later in System Settings › Notifications › Agent Usage Monitor. The host waits up to 3 minutes for the answer; unanswered, macOS withdraws the prompt and may not ask again. The installed app (`com.windroc.agent-usage-monitor`) asks even if you allowed the [TASK-638 spike](#spike-conclusions) app, which had another bundle ID. A second Agent Usage Monitor entry may remain in System Settings › Notifications from that testing; you can leave it switched off.

No notifications? Turn them on in System Settings › Notifications › Agent Usage Monitor; the log says so when macOS refuses them. Alerts not sent are kept for the next run, so they arrive within 5 minutes.

## Development

```sh
make test                  # unit tests with /usr/bin/python3; fake codex and claude only
make pii-scan              # tracked files hold no emails, UUIDs, real home paths or image metadata (NFR-4)
make hooks                 # enable the pre-push hook in this clone (make check also does)
make swift-test            # widget display model and alert-line parser self-test
make app                   # build/AgentUsageMonitor.app (swiftc + Command Line Tools, ad-hoc signed)
make check                 # all of the above, then plist lint, signature, widget entitlements and app icon,
                           # and checks the code never names credential files or network APIs
bin/agent-usage-monitor collect     # read every account, write the snapshot; the host adds --emit-alerts
bin/agent-usage-monitor record-alerts < lines  # the host: record the AUM-ALERT lines macOS took as sent
bin/agent-usage-monitor read-accounts          # the settings window: the account list as one JSON line
bin/agent-usage-monitor write-accounts < edit  # the settings window: check and write its edit; problems: exit 1
```

CI ([`.github/workflows/check.yml`](.github/workflows/check.yml)) runs `make check` on a macOS 26 runner with the Command Line Tools for every pull request and push to `main`. On a pull request it first runs the pre-push scan below on the pull request's commits (`tests/pii_scan.py --commits`): their author and committer emails, messages and files, so a push that skipped the hook is still caught.

The repo is public, so personal data is caught before a push: after `make hooks`, [`.githooks/pre-push`](.githooks/pre-push) runs [`tests/pii_scan.py`](tests/pii_scan.py) on the files, commit messages and author and committer emails the push would publish, and refuses the push on a hit. Commit with your GitHub noreply address as `user.email`. A value that may be public goes in [`tests/pii-allowlist.txt`](tests/pii-allowlist.txt) with its reason, with `in:identity` when it may only be a commit author or committer email, and as `sha256:<hex>` of the lowercased value when no file may hold it; explain each new entry in its pull request.

### Settings window

Open Agent Usage Monitor from Applications, Spotlight or Finder (`~/Applications/AgentUsageMonitor.app`), or click the small grey gear at the bottom right of the widget, to edit the [account list](#account-list): one row per account with its client, `dir` (type it, or pick a folder in Finder with Choose…; your home shows as `~`), `account` (may be empty) and `name`; add, delete and move rows; set `threshold` (50 to 100). The app shows in the Dock while the window is open; closing the window quits it, after a running collect. Save checks the list with `collect`'s own rules and shows each problem on its row, writing nothing; otherwise it replaces `accounts.json` in one rename (mode 0600), keeping fields the window does not show, and runs `collect` at once. With no file the window starts from the default accounts and creates the file only on Save. A file it cannot read shows the error and stays as it is; Start Over with Defaults, then Save, replaces it. While the window is open its app collects every 5 minutes itself: the LaunchAgent's runs exit while another host runs.

A widget click opens the app with `agent-usage-monitor://refresh`, so it only collects, with `--retry-paused`, and refreshes; the window's own runs and the LaunchAgent's do not pass that flag; `agent-usage-monitor://settings` shows the window, starting the app if it is not running and otherwise bringing the window to the front. A launch without that URL shows the window only when LaunchServices started the app (`XPC_SERVICE_NAME` is `application.<bundle id>.…`; launchd sets the job label), an observed rather than documented difference.

### Account list

`collect` reads the account list `~/.config/agent-usage-monitor/accounts.json` (honors `XDG_CONFIG_HOME`). Without it, the accounts are `~/.claude` (`claude`) and `~/.codex` (`codex`), whichever exist. The snapshot and the widget list accounts by client, Claude then Codex, in file order within each; `threshold` (default 90) is the percent at which an account counts as not available. `name` identifies an account and must be unique; the optional `account`, a non-empty string such as the login email, is only shown in the widget and may repeat across accounts.

You can still edit `accounts.json` by hand. To write one, copy [`accounts.example.json`](accounts.example.json) (two Claude accounts, one Codex account) to `~/.config/agent-usage-monitor/accounts.json`, then edit it: set each `dir` to an existing account directory and `account` to your own; drop `account` to show none. JSON has no comments, so the fields are explained here only.

It writes `~/.local/state/agent-usage-monitor/snapshot.json`. Codex limits come from `codex app-server` ([protocol notes](docs/codex-app-server.md)).

Claude limits come from `collect`, which runs `claude -p /usage` for every Claude account in `~/.local/state/agent-usage-monitor/probe/`, with the arguments and environment from the [spike report](docs/spikes/TASK-572-claude-usage.md). The default account (`~/.claude`) runs without `CLAUDE_CONFIG_DIR`; any other account runs with `CLAUDE_CONFIG_DIR=<dir>`. In each such `<dir>`, `claude` itself rewrites `.claude.json` (with a copy under `backups/`) on every probe, syncs the account's plugins and skills under `plugins/synced/` and `skills/synced/` on the first one, and creates an empty `projects/<probe dir>/memory/`; agent-usage-monitor writes nothing there. An account probed less than 4 minutes ago is skipped. If `claude` prints output the parser does not recognize, or exits without usable output, `collect` runs `claude auth status --json` the same way; when it reports `loggedIn: false` (a logged-out account's `/usage` prints only the session cost screen), the row gets `needs_login: true` and the next run probes again, so logging in recovers it (TASK-873); a successful probe, or unrecognized output while not logged out, sets it back to `false`. Otherwise each unrecognized output keeps the row's values, is logged, and replaces `probe/last-unrecognized-<name>.txt` (mode 0600; the raw stdout and stderr, only there, never in the snapshot or the log; characters of the account name other than letters, digits, `.`, `_` and `-` become `_`). The 3rd unrecognized output in a row on one `claude --version` (`unrecognized_count` in the snapshot row) pauses that account's probe (`usage_disabled_version`, widget reason `/usage unreadable · paused`) until `claude --version` changes; a successful probe or a new version starts the count again. A paused account runs its probe once more when you click the widget (`collect --retry-paused`) and on a backoff: first 5 minutes after the pause, then each failed retry doubles the wait (10, 20, 40 minutes, …) up to 6 hours, a run up to a minute early counting as on time (`usage_disabled_at`, when it paused or last retried, and `usage_retry_after_s`, the wait, in its snapshot row); the LaunchAgent and the settings window retry it only on that schedule. If a retry succeeds the account recovers and the schedule is cleared; unrecognized output pauses it again at once, without 3 more strikes, and any other failure keeps the pause; both, after a click too, double the wait (WDRC-100). A pause recorded without that schedule retries on the next run. A disabled account found logged out is enabled again.

Sources: Python collector in `agent_usage_monitor/`; host app (`macos/Host`, not sandboxed, posts the alerts; no window or Dock icon except the settings window) and widget (`macos/Widget`, sandboxed, read-only access to `~/.local/state/agent-usage-monitor/` only) in `macos/`.

## Spike conclusions

- **TASK-573** ([report](docs/spikes/TASK-573-clt-widget.md)): pass. `swiftc` with the Command Line Tools SDK builds an ad-hoc-signed host app and WidgetKit extension that macOS 26.7.1 lists in the widget gallery; the sandboxed widget reads `~/.local/state/agent-usage-monitor/` through a home-relative read-only exception, and a click opens the host app. No Xcode needed.
- **TASK-572** ([report](docs/spikes/TASK-572-claude-usage.md)): pass for Claude Code 2.1.302 and the default account only. `claude -p --no-session-persistence --strict-mcp-config --settings '{"remoteControlAtStartup":false,"disableAllHooks":true}' --model sonnet --effort low /usage` in an empty directory, stdin `/dev/null`, without `ANTHROPIC_*` and `CLAUDE_CODE_OAUTH_TOKEN`, with `DISABLE_AUTOUPDATER=1`, printed the 5h and 7d limits with no model request, no session file, no hook and no MCP server; no session cleanup or status line tap is needed.
- **TASK-583** ([report](docs/spikes/TASK-583-claude-config-dir-usage.md)): pass for non-default accounts with `CLAUDE_CONFIG_DIR` set to the account dir. The default account must keep it unset: set, `claude` looks for a login item named after the dir and reads as logged out. An account with no 5h window running prints `Current session: 0% used` without a reset time, shown as 5h 0%.
- **TASK-638** (2026-10-17, macOS 26.7.1): both ways of notifying work from the LaunchAgent; the host app's is used.
  - `osascript` `display notification` run by the installed host through `/bin/zsh -l` and `/usr/bin/python3`: exit 0, shown with no permission prompt, but as Script Editor (`com.apple.ScriptEditor2`), with its generic script icon.
  - `UNUserNotificationCenter` from an ad-hoc-signed test app with the host's name and icon (bundle ID `com.windroc.agent-usage-monitor.spike-un`, outside `~/Applications`, started by a temporary LaunchAgent): macOS showed an Allow prompt for Agent Usage Monitor; once allowed, `requestAuthorization` returned granted and the notification showed as a banner with Agent Usage Monitor's name and icon.

## Credits

The Claude `/usage` probe and its output parser are ported from [CodexBar](https://github.com/steipete/CodexBar) (MIT); see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## License

[MIT](LICENSE) © windroc
