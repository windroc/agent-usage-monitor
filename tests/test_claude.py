import json
import os
import time
import unittest
from datetime import datetime, timedelta, timezone

from agent_usage_monitor import claude, claude_usage, derive
from tests.helpers import (FIXTURES, Env, claude_calls, install_fake_claude, install_fake_codex, rate_limits, reaped,
                           window)

A1 = os.path.join(FIXTURES, "claude-usage", "A1.stdout.txt")
# TASK-873: /usage of a logged-out account (claude 2.1.309, empty CLAUDE_CONFIG_DIR) prints only the cost screen
LOGGED_OUT = os.path.join(FIXTURES, "claude-usage", "logged-out.stdout.txt")
LOGGED_OUT_STATUS = json.dumps({"loggedIn": False, "authMethod": "none", "apiProvider": "firstParty"})
AUTH_STATUS = ["auth", "status", "--json"]
AUTH_FIELDS = {"needs_login": True, "usage_disabled_version": None, "usage_disabled_at": None,
               "usage_retry_after_s": None, "error": None}
VERSION = "2.1.302 (Claude Code)"
# The row's error while the probe is disabled, for any version (WDRC-98): short enough for the large widget
PAUSED = "/usage unreadable · paused"


NOW = 1792213644  # 2026-10-17T05:07:24Z, the A1 run
HOUR = 3600


def disabled(version=VERSION, at=NOW, wait=300):
    """Fields of the disabling result: paused at `at`, next retry `wait` s later; auth status has just said not
    logged out."""
    return {"usage_disabled_version": version, "usage_disabled_at": at, "usage_retry_after_s": wait,
            "unrecognized_count": 0, "unrecognized_version": None, "needs_login": False, "error": PAUSED}


def retry_failed(wait):
    """Fields of a retry that failed other than unrecognized: still disabled, next retry `wait` s from now
    (WDRC-100)."""
    return {"needs_login": False, "usage_disabled_at": NOW, "usage_retry_after_s": wait, "error": PAUSED}


# a disabled row kept disabled
KEPT_DISABLED = {"needs_login": False, "error": PAUSED}


def _hour(at):
    return "%d%s" % (at.hour % 12 or 12, "pm" if at.hour >= 12 else "am")


# Resets ahead of the real clock: collect runs at time.time(), and a past reset reads as 0% (FR-15).
_SESSION = datetime.now(timezone.utc) + timedelta(hours=2)
_WEEK = datetime.now(timezone.utc) + timedelta(days=3)
USAGE = ("Current session: 40%% used · resets %s (UTC)\n" % _hour(_SESSION)
         + "Current week (all models): 10%% used · resets %s %d at %s (UTC)\n" % (_WEEK.strftime("%b"), _WEEK.day, _hour(_WEEK)))


def fresh_row(**fields):
    return dict({"fetched_at": None, "usage_disabled_version": None}, **fields)


def strike(count, version=VERSION):
    """Fields of the count-th unrecognized output in a row on version, below the disable (WDRC-97)."""
    return {"unrecognized_count": count, "unrecognized_version": version, "usage_disabled_version": None,
            "usage_disabled_at": None, "usage_retry_after_s": None, "needs_login": False,
            "error": "/usage output not recognized (%d of 3)" % count}


def paused_row(since=NOW - 60, wait=300, version=VERSION, **fields):
    """A row whose probe was disabled or last retried at `since`, next retry `wait` s later (WDRC-100)."""
    return fresh_row(usage_disabled_version=version, usage_disabled_at=since, usage_retry_after_s=wait, **fields)


class RefreshTest(unittest.TestCase):
    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.cleanup)

    def refresh(self, row=None, now=NOW, **kw):
        return claude.refresh("claude", row or fresh_row(), self.env.state, self.env.environ, now=now, **kw)

    @property
    def probe_dir(self):
        return os.path.realpath(os.path.join(self.env.state, "probe"))

    @property
    def capture(self):
        return os.path.join(self.probe_dir, "last-unrecognized-claude.txt")

    def run_from(self, row, runs, now=NOW):
        """Refresh runs times, 300 s apart, merging each result into row; return the results and the row."""
        results = []
        for i in range(runs):
            results.append(self.refresh(row, now=now + 300 * i))
            row = dict(row, **results[-1][0])
        return results, row

    def test_argv_stdin_cwd_env(self):
        install_fake_claude(self.env, stdout=USAGE)
        self.env.environ.update(CLAUDE_CONFIG_DIR=os.path.join(self.env.home, ".claude"),
                                CLAUDE_CODE_OAUTH_TOKEN="x", ANTHROPIC_API_KEY="x", ANTHROPIC_BASE_URL="x")
        self.refresh()
        [call] = claude_calls(self.env)
        self.assertEqual(call["argv"], ["-p", "--no-session-persistence", "--strict-mcp-config", "--settings",
                                        '{"remoteControlAtStartup":false,"disableAllHooks":true}',
                                        "--model", "sonnet", "--effort", "low", "/usage"])
        self.assertEqual(call["stdin"], "")
        self.assertEqual(call["cwd"], self.probe_dir)
        self.assertEqual(call["env"], {"PWD": self.probe_dir, "DISABLE_AUTOUPDATER": "1",
                                       "PATH": self.env.environ["PATH"], "HOME": self.env.home})
        self.assertEqual(call["anthropic"], [])

    def test_config_dir_for_other_accounts(self):
        install_fake_claude(self.env, stdout="50% used\n")
        self.env.environ.update(CLAUDE_CONFIG_DIR=os.path.join(self.env.home, ".claude"))
        other = self.env.mkdir(".claude-a")
        self.refresh(config_dir=other)
        probe, auth, version = claude_calls(self.env)
        self.assertEqual((auth["argv"], version["argv"]), (AUTH_STATUS, ["--version"]))
        for call in (probe, auth, version):
            self.assertEqual(call["env"], {"PWD": self.probe_dir, "DISABLE_AUTOUPDATER": "1", "CLAUDE_CONFIG_DIR": other,
                                           "PATH": self.env.environ["PATH"], "HOME": self.env.home})

    def test_probe_dir_setup(self):
        install_fake_claude(self.env, stdout=USAGE)
        os.makedirs(os.path.join(self.env.state, "probe"), mode=0o755)
        os.chmod(os.path.join(self.env.state, "probe"), 0o755)
        for _ in range(2):
            self.refresh()
            self.assertEqual(os.stat(self.probe_dir).st_mode & 0o777, 0o700)
            settings = os.path.join(self.probe_dir, ".claude")
            self.assertEqual(os.listdir(settings), ["settings.local.json"])
            with open(os.path.join(settings, "settings.local.json")) as f:
                self.assertEqual(json.load(f), {"disableDeepLinkRegistration": "disable"})
        self.assertEqual(sorted(os.listdir(self.env.state)), ["probe"])

    def test_fixture(self):
        install_fake_claude(self.env, stdout_file=A1)
        fields, kept, message = self.refresh()
        self.assertEqual((kept, message), (False, None))
        self.assertEqual(fields["source"], "usage")
        self.assertEqual(fields["fetched_at"], NOW)
        self.assertIsNone(fields["usage_disabled_version"])
        self.assertIs(fields["needs_login"], False)
        self.assertIsNone(fields["error"])
        self.assertEqual(fields["five_hour"], {"used_percent": 17, "resets_at": 1792226340})
        self.assertEqual(fields["seven_day"]["used_percent"], 1)

    def test_timeout_kills_group(self):
        install_fake_claude(self.env, hang=True, spawn_child=True)
        start = time.monotonic()
        fields, kept, message = self.refresh(timeout=1)
        self.assertLess(time.monotonic() - start, 10)
        self.assertEqual((fields, kept), ({"error": "timed out"}, True))
        self.assertIn("timeout", message)
        [call] = claude_calls(self.env)
        self.assertTrue(reaped(call["pid"], call["child"]))

    def test_child_of_successful_probe_is_killed(self):
        install_fake_claude(self.env, stdout=USAGE, spawn_child=True)
        self.assertFalse(self.refresh()[1])
        self.assertTrue(reaped(claude_calls(self.env)[0]["child"]))

    def test_exited_claude_whose_child_holds_stdout(self):
        install_fake_claude(self.env, stdout=USAGE, child_holds_stdout=True)
        start = time.monotonic()
        fields, kept, message = self.refresh(timeout=5)
        self.assertLess(time.monotonic() - start, 4)
        self.assertEqual((kept, message, fields["source"]), (False, None, "usage"))
        self.assertTrue(reaped(claude_calls(self.env)[0]["child"]))

    def test_claude_missing(self):
        fields, kept, message = self.refresh()
        self.assertEqual((fields, kept), ({"error": "cannot start claude: ENOENT"}, True))
        self.assertEqual(message, "agent-usage-monitor: claude claude: cannot start claude: ENOENT")

    def test_error_kinds(self):
        # WDRC-98: each kind's fields, its reason as `error` (auth: none, the login notice says it)
        cases = [
            ({"stdout": 'Failed to load usage data: {"error":{"type":"authentication_error","message":"x"}}'}, "auth",
             AUTH_FIELDS),
            ({"stderr": "Failed to load usage data: token_expired", "exit": 1}, "auth", AUTH_FIELDS),
            ({"stdout": "Failed to load usage data: rate limited"}, "usage_error",
             {"error": "claude could not load usage data"}),
            ({"stdout": "Loading usage data…\n"}, "loading", {"error": "usage data still loading"}),
            ({"stdout": ""}, "timeout", {"error": "no output from claude"}),
            ({"stdout": "something went wrong\n", "exit": 2}, "timeout", {"error": "claude exited with code 2"}),
            ({"stdout": USAGE, "exit": 1}, "timeout", {"error": "claude exited with code 1"}),
            ({"stdout": "50% used\n"}, "unrecognized", strike(1)),
        ]
        for cfg, kind, expected in cases:
            with self.subTest(kind=kind, cfg=cfg):
                install_fake_claude(self.env, **cfg)
                fields, kept, message = self.refresh()
                self.assertTrue(kept)
                self.assertTrue(message.startswith("agent-usage-monitor: claude claude: %s: " % kind), message)
                for raw in ("token_expired", "rate limited", "50%", "something went wrong", "authentication_error"):
                    self.assertNotIn(raw, message)
                self.assertEqual(fields, expected)

    def test_disabled_version_unknown_or_unreadable(self):
        """WDRC-98: a kept-disabled row whose version is unknown, or not a version at all, has the same reason."""
        install_fake_claude(self.env, stdout=USAGE, version_exit=1)
        for value in ("unknown", "/Users/u/secret"):
            with self.subTest(value=value):
                fields, kept, _ = self.refresh(paused_row(version=value))
                self.assertEqual((fields, kept), ({"needs_login": False, "error": PAUSED}, True))

    def test_logged_out(self):
        """TASK-873: a logged-out account's /usage shows only the cost screen; auth status tells why."""
        install_fake_claude(self.env, stdout_file=LOGGED_OUT, auth_status=LOGGED_OUT_STATUS, auth_exit=1)
        fields, kept, message = self.refresh()
        self.assertEqual((fields, kept), (AUTH_FIELDS, True))
        self.assertEqual(message, "agent-usage-monitor: claude claude: auth: " + claude.DESCRIPTIONS["auth"])
        probe, auth = claude_calls(self.env)
        self.assertEqual(auth["argv"], AUTH_STATUS)
        self.assertEqual((auth["cwd"], auth["env"], auth["stdin"]), (probe["cwd"], probe["env"], ""))

    def test_logged_out_failed_probe(self):
        # a /usage that exited without usable output is checked too
        for cfg in ({"stdout": ""}, {"stdout": "something went wrong\n", "exit": 1}):
            with self.subTest(cfg=cfg):
                install_fake_claude(self.env, auth_status=LOGGED_OUT_STATUS, auth_exit=1, **cfg)
                fields, kept, message = self.refresh()
                self.assertEqual((fields, kept), (AUTH_FIELDS, True))
                self.assertIn(": auth: ", message)

    def test_auth_status_not_logged_out(self):
        # logged in, or an answer that is not exactly loggedIn false: the cost screen stays unrecognized
        for cfg in ({}, {"auth_status": "not json"}, {"auth_status": "", "auth_exit": 1},
                    {"auth_status": json.dumps({"loggedIn": None})}, {"auth_status": json.dumps({"loggedIn": "false"})},
                    {"auth_status": json.dumps([{"loggedIn": False}])}, {"auth_hang": True}):
            with self.subTest(cfg=cfg):
                install_fake_claude(self.env, stdout_file=LOGGED_OUT, **cfg)
                fields, kept, message = self.refresh(version_timeout=1)
                self.assertEqual((fields, kept), (strike(1), True))
                self.assertIn(": unrecognized: ", message)

    def test_hung_probe_skips_auth_status(self):
        install_fake_claude(self.env, hang=True, auth_status=LOGGED_OUT_STATUS, auth_exit=1)
        fields, kept, message = self.refresh(timeout=1)
        self.assertEqual((fields, kept), ({"error": "timed out"}, True))
        self.assertIn(": timeout: ", message)
        self.assertEqual(len(claude_calls(self.env)), 1)

    def test_logged_in_unrecognized_clears_needs_login(self):
        """Logged out, then logged in with output the parser does not know: counted, no longer needs login."""
        install_fake_claude(self.env, stdout_file=LOGGED_OUT, auth_status=LOGGED_OUT_STATUS, auth_exit=1)
        row = fresh_row(**self.refresh()[0])
        self.assertIs(row["needs_login"], True)
        install_fake_claude(self.env, stdout="50% used\n")  # the user logged in
        fields, kept, message = self.refresh(row, now=NOW + 300)
        self.assertEqual((fields, kept), (strike(1), True))
        self.assertIn(": unrecognized: ", message)
        # a row disabled while still flagged (a snapshot from before this fix) is cleared on its next run
        fields, kept, message = self.refresh(dict(row, usage_disabled_version=VERSION, usage_disabled_at=NOW,
                                                  usage_retry_after_s=HOUR), now=NOW + 600)
        self.assertEqual((fields, kept), (KEPT_DISABLED, True))
        self.assertIn("probe disabled for 2.1.302 (Claude Code)", message)

    def test_logged_out_clears_disable(self):
        """A row disabled while logged out (before TASK-873) is enabled again, so logging in recovers it."""
        install_fake_claude(self.env, stdout_file=LOGGED_OUT, auth_status=LOGGED_OUT_STATUS, auth_exit=1)
        fields, kept, message = self.refresh(fresh_row(usage_disabled_version="2.1.302 (Claude Code)"))
        self.assertEqual((fields, kept), (AUTH_FIELDS, True))
        self.assertIn(": auth: ", message)
        self.assertEqual([c["argv"] for c in claude_calls(self.env)], [["--version"], AUTH_STATUS])

    def test_recovers_after_login(self):
        install_fake_claude(self.env, stdout_file=LOGGED_OUT, auth_status=LOGGED_OUT_STATUS, auth_exit=1)
        row = fresh_row(**self.refresh()[0])
        # still logged out: the next run probes again and is not disabled
        fields, kept, _ = self.refresh(row, now=NOW + 300)
        self.assertEqual((fields, kept), (AUTH_FIELDS, True))
        self.assertEqual([c["argv"] for c in claude_calls(self.env)].count(AUTH_STATUS), 2)
        install_fake_claude(self.env, stdout=USAGE)  # the user logged in
        fields, kept, message = self.refresh(row, now=NOW + 600)
        self.assertEqual((kept, message), (False, None))
        self.assertEqual((fields["needs_login"], fields["usage_disabled_version"], fields["source"], fields["error"]),
                         (False, None, "usage", None))

    def test_version_disable_cycle(self):
        install_fake_claude(self.env, stdout="50% used\n", version="2.1.302 (Claude Code)")
        _, row = self.run_from(fresh_row(), 3)
        self.assertEqual(row["usage_disabled_version"], "2.1.302 (Claude Code)")

        fields, kept, message = self.refresh(row, now=NOW + 839)  # 1 s before the first retry is due
        self.assertEqual((fields, kept), (KEPT_DISABLED, True))
        self.assertIn("probe disabled for 2.1.302 (Claude Code)", message)
        # logged in: still disabled, without running /usage
        self.assertEqual([c["argv"] for c in claude_calls(self.env)][-2:], [["--version"], AUTH_STATUS])
        self.assertEqual(len(claude_calls(self.env)), 11)

        install_fake_claude(self.env, stdout=USAGE, version="2.1.303 (Claude Code)")
        fields, kept, message = self.refresh(row, now=NOW + 1260)
        self.assertEqual((kept, message, fields["usage_disabled_version"]), (False, None, None))

        row = fresh_row()  # the user deleted the key
        self.assertFalse(self.refresh(row)[1])

    def test_version_failures(self):
        for cfg in ({"version_exit": 1}, {"version": ""}, {"version": "banner\nline two"},
                    {"version": "9" * 80}, {"version": "2.1.302" + "x" * 60}, {"version_hang": True}):
            with self.subTest(cfg=cfg):
                install_fake_claude(self.env, stdout="50% used\n", **cfg)
                fields, kept, message = self.refresh(timeout=1, version_timeout=1)
                self.assertEqual(fields, strike(1, "unknown"))
                self.assertIn("version unknown", message)
                self.assertNotIn("banner", message)
                # a disabled row whose version cannot be read stays disabled
                n = len(claude_calls(self.env))
                fields, kept, message = self.refresh(paused_row(), version_timeout=1)
                self.assertEqual((fields, kept), (KEPT_DISABLED, True))
                self.assertEqual([c["argv"] for c in claude_calls(self.env)[n:]], [["--version"], AUTH_STATUS])

    def test_version_first_line(self):
        install_fake_claude(self.env, stdout="50% used\n", version="2.1.302 (Claude Code)\nUpdate available")
        fields, _, message = self.refresh()
        self.assertEqual(fields, strike(1))
        self.assertNotIn("Update available", message)

    def test_third_unrecognized_disables(self):
        """WDRC-97: the 1st and 2nd unrecognized outputs on one version are kept-row failures; the 3rd disables."""
        install_fake_claude(self.env, stdout="50% used\n")
        results, _ = self.run_from(fresh_row(), 4)
        for count, (fields, kept, message) in enumerate(results[:2], 1):
            self.assertEqual((fields, kept), (strike(count), True))
            self.assertEqual(message, "agent-usage-monitor: claude claude: unrecognized: output not recognized "
                                      "(%d of 3 on 2.1.302 (Claude Code)); raw output in %s" % (count, self.capture))
        fields, kept, message = results[2]
        self.assertEqual((fields, kept), (disabled(at=NOW + 600), True))
        self.assertEqual(message, "agent-usage-monitor: claude claude: unrecognized: output not recognized 3 times; "
                                  "probe disabled for 2.1.302 (Claude Code) until claude changes version; "
                                  "next retry in 5 min or on a widget click; raw output in %s" % self.capture)
        fields, kept, message = results[3]
        # WDRC-100: the next run, 5 minutes on, is the first retry
        self.assertEqual((fields, kept), (disabled(at=NOW + 900, wait=600), True))
        self.assertIn("retry: output not recognized; probe disabled again for 2.1.302 (Claude Code)", message)
        self.assertEqual([c["argv"][-1] for c in claude_calls(self.env)].count("/usage"), 4)

    def test_success_resets_count(self):
        install_fake_claude(self.env, stdout="50% used\n")
        _, row = self.run_from(fresh_row(), 2)
        install_fake_claude(self.env, stdout=USAGE)
        fields, kept, message = self.refresh(row, now=NOW + 600)
        self.assertEqual((kept, message), (False, None))
        self.assertEqual((fields["unrecognized_count"], fields["unrecognized_version"], fields["error"]), (0, None, None))
        row = dict(row, **fields)
        install_fake_claude(self.env, stdout="50% used\n")
        results, row = self.run_from(row, 3, now=NOW + 900)
        self.assertEqual([r[0] for r in results], [strike(1), strike(2), disabled(at=NOW + 1500)])

    def test_version_change_resets_count(self):
        install_fake_claude(self.env, stdout="50% used\n")
        _, row = self.run_from(fresh_row(), 2)
        self.assertEqual(row["unrecognized_count"], 2)
        install_fake_claude(self.env, stdout="50% used\n", version="2.1.303 (Claude Code)")
        results, row = self.run_from(row, 3, now=NOW + 600)
        new = "2.1.303 (Claude Code)"
        self.assertEqual([r[0] for r in results], [strike(1, new), strike(2, new), disabled(new, NOW + 1200)])

    def test_reenabled_by_version_change_counts_again(self):
        # a disabled row on a new claude version probes again and needs 3 more before it is disabled again
        install_fake_claude(self.env, stdout="50% used\n", version="2.1.303 (Claude Code)")
        fields, kept, _ = self.refresh(fresh_row(**disabled()))
        self.assertEqual((fields, kept), (strike(1, "2.1.303 (Claude Code)"), True))

    def test_other_failures_keep_count(self):
        """auth, timeout, usage_error and loading return what they did before WDRC-97 and leave the count alone."""
        row = fresh_row(unrecognized_count=2, unrecognized_version=VERSION)
        for cfg, expected in (({"stdout": ""}, {"error": "no output from claude"}),
                              ({"stdout": "Failed to load usage data: rate limited"},
                               {"error": "claude could not load usage data"}),
                              ({"stdout": "Loading usage data…\n"}, {"error": "usage data still loading"}),
                              ({"stdout_file": LOGGED_OUT, "auth_status": LOGGED_OUT_STATUS, "auth_exit": 1}, AUTH_FIELDS)):
            with self.subTest(cfg=cfg):
                install_fake_claude(self.env, **cfg)
                fields, kept, _ = self.refresh(row)
                self.assertEqual((fields, kept), (expected, True))
        self.assertFalse(os.path.exists(self.capture))
        install_fake_claude(self.env, stdout="50% used\n")
        self.assertEqual(self.refresh(row)[0], disabled())

    def test_unknown_version_disables_on_third(self):
        install_fake_claude(self.env, stdout="50% used\n", version_exit=1)
        results, row = self.run_from(fresh_row(), 3)
        self.assertEqual([r[0] for r in results[:2]], [strike(1, "unknown"), strike(2, "unknown")])
        self.assertIn("(2 of 3 on version unknown)", results[1][2])
        self.assertEqual(results[2][0], disabled("unknown", NOW + 600))
        self.assertIn("version unknown, probe disabled until claude --version answers; next retry in 5 min or on a "
                      "widget click", results[2][2])

    def test_capture_file(self):
        """WDRC-97: each unrecognized output's raw stdout and stderr replace <probe>/last-unrecognized-<name>.txt."""
        install_fake_claude(self.env, stdout="50% used\n", stderr="warning: first\n")
        fields, _, message = self.refresh()
        self.assertEqual(os.stat(self.capture).st_mode & 0o777, 0o600)
        with open(self.capture, encoding="utf-8") as f:
            self.assertEqual(f.read(), "--- stdout ---\n50% used\n\n--- stderr ---\nwarning: first\n\n")
        self.assertIn(self.capture, message)
        self.assertNotIn("50%", message)
        self.assertNotIn("warning", message)
        self.assertNotIn("50%", json.dumps(fields))
        for path in (self.capture, self.env.home, self.env.state):
            self.assertNotIn(path, fields["error"])
        install_fake_claude(self.env, stdout="other output\n")
        self.refresh(fresh_row(**fields), now=NOW + 300)
        with open(self.capture, encoding="utf-8") as f:
            self.assertEqual(f.read(), "--- stdout ---\nother output\n\n--- stderr ---\n\n")
        self.assertEqual(os.stat(self.capture).st_mode & 0o777, 0o600)
        self.assertEqual(sorted(n for n in os.listdir(self.probe_dir) if n != ".claude"), ["last-unrecognized-claude.txt"])

    def test_capture_file_name(self):
        # an account name may hold any character; the file stays in the probe dir
        install_fake_claude(self.env, stdout="50% used\n")
        _, _, message = claude.refresh("../a b/é", fresh_row(), self.env.state, self.env.environ, now=NOW)
        path = os.path.join(self.probe_dir, "last-unrecognized-.._a_b__.txt")
        self.assertTrue(os.path.isfile(path), os.listdir(self.probe_dir))
        self.assertIn("raw output in %s" % path, message)

    def test_capture_file_not_written(self):
        install_fake_claude(self.env, stdout="50% used\n")
        os.makedirs(os.path.join(self.capture, "x"))  # a directory where the file goes: the replace fails
        fields, kept, message = self.refresh()
        self.assertEqual((fields, kept), (strike(1), True))
        self.assertIn("; raw output not saved to %s: E" % self.capture, message)
        self.assertEqual(sorted(n for n in os.listdir(self.probe_dir) if n != ".claude"), ["last-unrecognized-claude.txt"])

    def test_probe_dir_unusable(self):
        install_fake_claude(self.env, stdout=USAGE)
        os.makedirs(self.env.state)
        open(os.path.join(self.env.state, "probe"), "w").close()
        self.assertEqual(self.refresh(), ({"error": "cannot prepare probe dir: EEXIST"}, True,
                                          "agent-usage-monitor: claude claude: cannot prepare probe dir: EEXIST"))
        self.assertEqual(claude_calls(self.env), [])

    def test_unknown_sentinel_reprobes_once_version_reads(self):
        install_fake_claude(self.env, stdout=USAGE)
        fields, kept, message = self.refresh(fresh_row(usage_disabled_version="unknown"))
        self.assertEqual((kept, message), (False, None))

    def test_click_retry_success(self):
        """WDRC-100: a widget click (retry_paused) runs a paused probe once; a parsing output ends the pause."""
        install_fake_claude(self.env, stdout=USAGE)
        fields, kept, message = self.refresh(paused_row(unrecognized_count=0, error=PAUSED), retry_paused=True)
        self.assertEqual((kept, message), (False, None))
        keys = ("usage_disabled_version", "usage_disabled_at", "usage_retry_after_s", "unrecognized_count",
                "unrecognized_version", "needs_login", "error", "source", "fetched_at")
        self.assertEqual({k: fields[k] for k in keys},
                         {"usage_disabled_version": None, "usage_disabled_at": None, "usage_retry_after_s": None,
                          "unrecognized_count": 0,
                          "unrecognized_version": None, "needs_login": False, "error": None, "source": "usage",
                          "fetched_at": NOW})
        self.assertEqual(fields["five_hour"]["used_percent"], 40)
        self.assertEqual([c["argv"][-1] for c in claude_calls(self.env)].count("/usage"), 1)

    def test_retry_unrecognized_pauses_again(self):
        """A retry's unrecognized output pauses again at once, with no 3 more strikes, and doubles the wait."""
        for kw, since in (({"retry_paused": True}, NOW - 60), ({}, NOW - 300)):
            with self.subTest(kw=kw):
                install_fake_claude(self.env, stdout="50% used\n")
                fields, kept, message = self.refresh(paused_row(since), **kw)
                self.assertEqual((fields, kept), (disabled(wait=600), True))
                self.assertEqual(message, "agent-usage-monitor: claude claude: retry: output not recognized; probe "
                                          "disabled again for 2.1.302 (Claude Code); next retry in 10 min or on a "
                                          "widget click; raw output in %s" % self.capture)
                with open(self.capture, encoding="utf-8") as f:
                    self.assertIn("50% used", f.read())
        install_fake_claude(self.env, stdout="50% used\n", version_exit=1)
        fields, _, message = self.refresh(paused_row(version="unknown"), retry_paused=True)
        self.assertEqual(fields, disabled("unknown", wait=600))
        self.assertIn("probe disabled again for version unknown", message)

    def test_retry_other_failure_keeps_pause(self):
        """timeout, a non-zero exit, usage_error, loading or a missing claude keep the pause and double its wait."""
        for cfg, kind in (({"stdout": ""}, "timeout: "), ({"stdout": "50% used\n", "exit": 1}, "timeout: "),
                          ({"stdout": "Failed to load usage data: rate limited"}, "usage_error: "),
                          ({"stdout": "Loading usage data…\n"}, "loading: "), ({"hang": True}, "timeout: ")):
            with self.subTest(cfg=cfg):
                install_fake_claude(self.env, **cfg)
                fields, kept, message = self.refresh(paused_row(), timeout=1, retry_paused=True)
                self.assertEqual((fields, kept), (retry_failed(600), True))
                self.assertTrue(message.startswith("agent-usage-monitor: claude claude: retry: " + kind), message)
                self.assertIn("; probe stays disabled for 2.1.302 (Claude Code); next retry in 10 min or on a widget "
                              "click", message)

    def test_retry_claude_missing_keeps_pause(self):
        fields, kept, message = self.refresh(paused_row(version="unknown"), retry_paused=True)
        self.assertEqual((fields, kept), (retry_failed(600), True))
        self.assertEqual(message, "agent-usage-monitor: claude claude: retry: cannot start claude: ENOENT; probe stays "
                                  "disabled for unknown; next retry in 10 min or on a widget click")

    def test_retry_logged_out(self):
        """A retry whose /usage reads as logged out ends the pause with the login notice, as before WDRC-100."""
        install_fake_claude(self.env, stdout_file=LOGGED_OUT, auth_status=LOGGED_OUT_STATUS, auth_exit=1)
        fields, kept, message = self.refresh(paused_row(), retry_paused=True)
        self.assertEqual((fields, kept), (AUTH_FIELDS, True))
        self.assertIn(": auth: ", message)

    def test_timer_no_retry_before_wait(self):
        install_fake_claude(self.env, stdout=USAGE)
        # due 60 s before the wait ends, as THROTTLE is 240 s under the LaunchAgent's 300 s
        for since, wait, left in ((NOW - 239, 300, 1), (NOW - 60, 300, 3), (NOW, 300, 4), (NOW - 61, 600, 8),
                                  (NOW - 6 * HOUR + 61, 6 * HOUR, 1)):
            with self.subTest(since=since, wait=wait):
                fields, kept, message = self.refresh(paused_row(since, wait))
                self.assertEqual((fields, kept), (KEPT_DISABLED, True))
                self.assertEqual(message, "agent-usage-monitor: claude claude: probe disabled for 2.1.302 "
                                          "(Claude Code); next retry in %d min or on a widget click" % left)
        self.assertNotIn("/usage", [c["argv"][-1] for c in claude_calls(self.env)])

    def test_timer_retry_when_due(self):
        """A retry that parses ends the pause and clears its schedule."""
        install_fake_claude(self.env, stdout=USAGE)
        for since, wait in ((NOW - 240, 300), (NOW - 300, 300), (NOW - 400, 300), (NOW - 6 * HOUR + 60, 6 * HOUR)):
            with self.subTest(since=since, wait=wait):
                fields, kept, message = self.refresh(paused_row(since, wait))
                self.assertEqual((kept, message), (False, None))
                self.assertEqual((fields["usage_disabled_version"], fields["usage_disabled_at"],
                                  fields["usage_retry_after_s"]), (None, None, None))
        self.assertEqual([c["argv"][-1] for c in claude_calls(self.env)].count("/usage"), 4)

    def test_launchagent_run_1s_early(self):
        """A LaunchAgent run a second short of 5 minutes after the pause still takes the first retry, and the next
        retry stays on its 10-minute schedule."""
        install_fake_claude(self.env, stdout="50% used\n")
        fields, kept, message = self.refresh(paused_row(NOW, 300), now=NOW + 299)
        self.assertEqual((fields, kept), (disabled(at=NOW + 299, wait=600), True))
        self.assertIn("retry: output not recognized", message)
        row = paused_row(NOW + 299, 600)
        # two runs 300 s apart, each a second early: the second one retries
        self.assertEqual(self.refresh(row, now=NOW + 299 + 299)[0], KEPT_DISABLED)
        self.assertEqual(self.refresh(row, now=NOW + 299 + 599)[0], disabled(at=NOW + 898, wait=1200))
        self.assertEqual([c["argv"][-1] for c in claude_calls(self.env)].count("/usage"), 2)

    def test_backoff_doubles_to_cap(self):
        """Each failed timer retry doubles the wait, from 5 minutes up to 6 hours."""
        install_fake_claude(self.env, stdout="50% used\n")
        row, now, waits = paused_row(NOW, 300), NOW, []
        for _ in range(9):
            self.assertEqual(self.refresh(row, now=now + row["usage_retry_after_s"] - 61)[0], KEPT_DISABLED)
            now += row["usage_retry_after_s"] - 60
            fields, kept, _ = self.refresh(row, now=now)
            self.assertEqual((fields["usage_disabled_at"], kept), (now, True))
            row = dict(row, **fields)
            waits.append(row["usage_retry_after_s"])
        self.assertEqual(waits, [600, 1200, 2400, 4800, 9600, 19200, 21600, 21600, 21600])

    def test_backoff_cap(self):
        install_fake_claude(self.env, stdout="")
        for since, wait, kw, want in ((NOW - 4 * HOUR, 4 * HOUR, {}, 6 * HOUR),
                                      (NOW - 6 * HOUR, 6 * HOUR, {}, 6 * HOUR),
                                      (NOW - 60, 6 * HOUR, {"retry_paused": True}, 6 * HOUR),
                                      (NOW - 60, 9 * HOUR, {"retry_paused": True}, 6 * HOUR)):
            with self.subTest(wait=wait, kw=kw):
                self.assertEqual(self.refresh(paused_row(since, wait), **kw)[0], retry_failed(want))

    def test_huge_wait_capped(self):
        """WDRC-101: a stored wait above RETRY_MAX (corrupt or hand-edited) counts as RETRY_MAX, so the timer still
        retries."""
        install_fake_claude(self.env, stdout=USAGE)
        fields, kept, message = self.refresh(paused_row(NOW - 60, 10 ** 9))
        self.assertEqual((fields, kept), (KEPT_DISABLED, True))
        self.assertIn("next retry in 358 min", message)
        fields, kept, message = self.refresh(paused_row(NOW - 6 * HOUR + 60, 10 ** 9))
        self.assertEqual((kept, message), (False, None))
        self.assertIsNone(fields["usage_disabled_version"])
        install_fake_claude(self.env, stdout="")
        self.assertEqual(self.refresh(paused_row(NOW - 6 * HOUR + 60, 10 ** 9))[0], retry_failed(6 * HOUR))

    def test_failed_click_retry_doubles(self):
        install_fake_claude(self.env, stdout="50% used\n")
        fields, _, _ = self.refresh(paused_row(NOW - 60, 1200), retry_paused=True)
        self.assertEqual(fields, disabled(wait=2400))

    def test_old_pause_retries(self):
        """A pause recorded without its schedule (before WDRC-100's backoff) retries on the next run; so does one
        with a bad schedule or one ahead of the clock."""
        install_fake_claude(self.env, stdout=USAGE)
        rows = (fresh_row(usage_disabled_version=VERSION),
                fresh_row(usage_disabled_version=VERSION, usage_disabled_at=NOW), paused_row(None),
                paused_row("1792213644"), paused_row(True), paused_row(1.5), paused_row(NOW + 60),
                paused_row(wait=None), paused_row(wait=0), paused_row(wait=-300), paused_row(wait=True),
                paused_row(wait="300"))
        for row in rows:
            with self.subTest(row=row):
                fields, kept, _ = self.refresh(row)
                self.assertFalse(kept)
                self.assertIsNone(fields["usage_disabled_version"])
        # a failed retry of an old pause starts the backoff at its second step
        install_fake_claude(self.env, stdout="")
        self.assertEqual(self.refresh(fresh_row(usage_disabled_version=VERSION))[0], retry_failed(600))

    def test_unpaused_retry_flag_keeps_strikes(self):
        # retry_paused leaves an unpaused row's 3-strike count as it is
        install_fake_claude(self.env, stdout="50% used\n")
        self.assertEqual(self.refresh(retry_paused=True)[0], strike(1))

    def test_click_skips_throttle(self):
        """WDRC-480: a widget click (retry_paused) probes an account fetched under THROTTLE ago."""
        install_fake_claude(self.env, stdout=USAGE)
        for fetched in (NOW - 60, NOW - 239):
            with self.subTest(fetched=fetched):
                fields, kept, message = self.refresh(fresh_row(fetched_at=fetched), retry_paused=True)
                self.assertEqual((kept, message, fields["fetched_at"], fields["source"]), (False, None, NOW, "usage"))
                self.assertEqual(fields["five_hour"]["used_percent"], 40)
        self.assertEqual([c["argv"][-1] for c in claude_calls(self.env)].count("/usage"), 2)

    def test_throttle(self):
        install_fake_claude(self.env, stdout=USAGE, fail=True)
        for fetched in (NOW - 60, NOW - 239):
            row = fresh_row(fetched_at=fetched, usage_disabled_version="2.1.302 (Claude Code)")
            self.assertEqual(self.refresh(row), ({}, True, None))
        self.assertEqual(claude_calls(self.env), [])
        install_fake_claude(self.env, stdout=USAGE)
        # 299: a 5-minute LaunchAgent run whose previous fetched_at landed a second late
        for fetched in (NOW - 240, NOW - 299, NOW - 360, NOW + 600, None):
            with self.subTest(fetched=fetched):
                self.assertFalse(self.refresh(fresh_row(fetched_at=fetched))[1])


class CollectProbeTest(unittest.TestCase):
    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.cleanup)
        self.claude_dir = os.path.realpath(self.env.mkdir(".claude"))

    def collect(self, *args):
        r = self.env.run("collect", *args)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "")
        return r

    def row(self, name="claude"):
        return next(r for r in self.env.snapshot()["accounts"] if r["name"] == name)

    def test_every_collect_probes(self):
        install_fake_claude(self.env, stdout=USAGE)
        self.collect()  # FR-8
        self.assertEqual(len(claude_calls(self.env)), 1)
        probed = self.row()
        self.assertEqual((probed["source"], probed["five_hour"]["used_percent"]), ("usage", 40))
        self.assertEqual(probed["seven_day"]["used_percent"], 10)

        self.collect()  # FR-11: fetched just now, values kept
        self.assertEqual(len(claude_calls(self.env)), 1)
        self.assertEqual(self.row()["source"], "cache")
        self.assertEqual({k: self.row()[k] for k in ("five_hour", "seven_day", "fetched_at")},
                         {k: probed[k] for k in ("five_hour", "seven_day", "fetched_at")})

    def test_runs_300_s_apart_both_probe(self):
        install_fake_claude(self.env, stdout=USAGE)
        self.collect()
        # the LaunchAgent's next run, 300 s later, starting a second early
        with open(self.env.snapshot_path) as f:
            snap = json.load(f)
        for row in snap["accounts"]:
            row["fetched_at"] = int(time.time()) - 299
        with open(self.env.snapshot_path, "w") as f:
            json.dump(snap, f)
        self.collect()
        self.assertEqual(len(claude_calls(self.env)), 2)
        self.assertEqual(self.row()["source"], "usage")

    def test_click_collect_skips_throttle(self):
        """WDRC-480: a widget click right after a LaunchAgent run probes again and writes the new values."""
        install_fake_claude(self.env, stdout=USAGE)
        self.collect()
        install_fake_claude(self.env, stdout=USAGE.replace("40% used", "91% used"))
        self.collect("--retry-paused")
        self.assertEqual(len(claude_calls(self.env)), 2)
        self.assertEqual((self.row()["source"], self.row()["five_hour"]["used_percent"]), ("usage", 91))

    def test_other_accounts(self):
        """TASK-583: <dir-a> has no 5h window running, <dir-b> has one; ~/.claude is not listed."""
        dirs = [os.path.realpath(self.env.mkdir(d)) for d in (".claude-a", ".claude-b")]
        files = [os.path.join(FIXTURES, "claude-usage-config-dir", n) for n in ("A1.stdout.txt", "B1.stdout.txt")]
        self.env.write_accounts({"accounts": [{"name": "a", "client": "claude", "dir": "~/.claude-a"},
                                              {"name": "b", "client": "claude", "dir": "~/.claude-b"}]})
        install_fake_claude(self.env, stdout_files=dict(zip(dirs, files)))
        r = self.collect()
        self.assertEqual(r.stderr, "")
        self.assertEqual(sorted(c["env"]["CLAUDE_CONFIG_DIR"] for c in claude_calls(self.env)), dirs)
        snap = self.env.snapshot()
        for name, path in zip("ab", files):
            row = self.row(name)
            self.assertEqual((row["source"], row["usage_disabled_version"]), ("usage", None))
            with open(path, encoding="utf-8") as f:
                windows = claude_usage.make_windows(claude_usage.parse(f.read()), row["fetched_at"])
            for key in derive.WINDOWS:
                self.assertEqual(row[key], derive.reset_window(windows[key], snap["generated_at"]))
        self.assertEqual(self.row("a")["five_hour"], {"used_percent": 0, "resets_at": None})

    def test_default_account_keeps_config_dir_unset(self):
        other = os.path.realpath(self.env.mkdir(".claude-a"))
        self.env.write_accounts({"accounts": [{"name": "claude", "client": "claude", "dir": "~/.claude"},
                                              {"name": "a", "client": "claude", "dir": "~/.claude-a"}]})
        install_fake_claude(self.env, stdout=USAGE)
        self.collect()
        self.assertEqual(sorted(c["env"].get("CLAUDE_CONFIG_DIR", "") for c in claude_calls(self.env)), ["", other])
        self.assertEqual((self.row()["source"], self.row("a")["source"]), ("usage", "usage"))
        self.assertEqual(sorted(os.listdir(self.env.state)), ["probe", "snapshot.json", "snapshot.lock"])

    def test_fixture_end_to_end(self):
        install_fake_claude(self.env, stdout_file=A1)
        self.collect()
        snap = self.env.snapshot()
        row = self.row()
        self.assertEqual(row["source"], "usage")
        self.assertIsNone(row["usage_disabled_version"])
        with open(A1, encoding="utf-8") as f:
            windows = claude_usage.make_windows(claude_usage.parse(f.read()), row["fetched_at"])
        for key in derive.WINDOWS:
            self.assertEqual(row[key], derive.reset_window(windows[key], snap["generated_at"]))
        self.assertEqual([windows[k]["used_percent"] for k in derive.WINDOWS], [17, 1])

    def test_probe_dir_unusable_still_writes_codex(self):
        install_fake_claude(self.env, stdout=USAGE)
        later = int(time.time()) + 3600
        install_fake_codex(self.env, self.env.mkdir(".codex"),
                           result=rate_limits(window(10, 300, later), window(20, 10080, later)))
        os.makedirs(self.env.state)
        open(os.path.join(self.env.state, "probe"), "w").close()
        r = self.collect()
        self.assertIn("agent-usage-monitor: claude claude: cannot prepare probe dir: EEXIST", r.stderr)
        self.assertEqual(self.row()["source"], "none")
        codex = self.row("codex")
        self.assertEqual((codex["source"], codex["five_hour"]["used_percent"]), ("app-server", 10))

    def test_failure_keeps_row_and_reports(self):
        install_fake_claude(self.env, stdout="Failed to load usage data: token_expired")
        r = self.collect()
        self.assertIn("agent-usage-monitor: claude claude: auth: ", r.stderr)
        self.assertNotIn("token_expired", r.stderr)
        self.assertEqual(self.row()["source"], "none")

    def test_error_set_then_cleared(self):
        """WDRC-98: a failed run writes the reason into the row, a successful one clears it."""
        install_fake_claude(self.env, stdout="Failed to load usage data: rate limited")
        self.collect()
        self.assertEqual((self.row()["error"], self.row()["source"]), ("claude could not load usage data", "none"))
        install_fake_claude(self.env, stdout=USAGE)
        self.collect()
        self.assertEqual((self.row()["error"], self.row()["source"]), (None, "usage"))

    def test_logged_out_then_login(self):
        """TASK-873: the row says it needs login, stays enabled, and recovers once the user logs in."""
        install_fake_claude(self.env, stdout_file=LOGGED_OUT, auth_status=LOGGED_OUT_STATUS, auth_exit=1)
        r = self.collect()
        self.assertIn("agent-usage-monitor: claude claude: auth: ", r.stderr)
        row = self.row()
        self.assertEqual((row["needs_login"], row["usage_disabled_version"], row["source"]), (True, None, "none"))
        install_fake_claude(self.env, stdout=USAGE)
        r = self.collect()
        self.assertNotIn("claude claude:", r.stderr)
        row = self.row()
        self.assertEqual((row["needs_login"], row["usage_disabled_version"], row["source"]), (False, None, "usage"))
        self.assertEqual(row["five_hour"]["used_percent"], 40)

    def test_logged_out_then_logged_in_unrecognized(self):
        install_fake_claude(self.env, stdout_file=LOGGED_OUT, auth_status=LOGGED_OUT_STATUS, auth_exit=1)
        self.collect()
        self.assertIs(self.row()["needs_login"], True)
        install_fake_claude(self.env, stdout="50% used\n")
        r = self.collect()
        self.assertIn(": unrecognized: ", r.stderr)
        row = self.row()
        self.assertEqual((row["needs_login"], row["usage_disabled_version"], row["unrecognized_count"]), (False, None, 1))

    def test_three_unrecognized_collects_disable(self):
        """WDRC-97: the count lives in the snapshot row; the raw output only in the capture file."""
        install_fake_claude(self.env, stdout="Account: user@example.com\n50% used\n")
        capture = os.path.join(os.path.realpath(self.env.state), "probe", "last-unrecognized-claude.txt")
        for count in (1, 2):
            r = self.collect()
            self.assertIn("unrecognized: output not recognized (%d of 3 on 2.1.302 (Claude Code)); raw output in %s"
                          % (count, capture), r.stderr)
            row = self.row()
            self.assertEqual((row["unrecognized_count"], row["usage_disabled_version"], row["source"]), (count, None, "none"))
        r = self.collect()
        self.assertIn("probe disabled for 2.1.302 (Claude Code) until claude changes version", r.stderr)
        row = self.row()
        self.assertEqual((row["unrecognized_count"], row["usage_disabled_version"]), (0, "2.1.302 (Claude Code)"))
        self.assertNotIn("example", r.stderr)
        with open(self.env.snapshot_path) as f:
            self.assertNotIn("example", f.read())
        with open(capture, encoding="utf-8") as f:
            self.assertIn("user@example.com", f.read())

    def paused(self, since, wait=300):
        """Write a snapshot whose claude row was paused at `since`, next retry `wait` s later (WDRC-100)."""
        os.makedirs(self.env.state, exist_ok=True)
        with open(self.env.snapshot_path, "w") as f:
            json.dump({"schema": 1, "accounts": [{"name": "claude", "fetched_at": None, "error": PAUSED,
                                                  "usage_disabled_version": VERSION, "usage_disabled_at": since,
                                                  "usage_retry_after_s": wait}]}, f)

    def test_launchagent_run_keeps_pause(self):
        """WDRC-100: the LaunchAgent's run (no --retry-paused) leaves a pause alone until its next retry is due."""
        install_fake_claude(self.env, stdout=USAGE)
        since = int(time.time()) - 60
        self.paused(since)
        r = self.collect("--emit-alerts")
        self.assertIn("probe disabled for 2.1.302 (Claude Code); next retry in ", r.stderr)
        self.assertNotIn("/usage", [c["argv"][-1] for c in claude_calls(self.env)])
        row = self.row()
        self.assertEqual((row["usage_disabled_version"], row["usage_disabled_at"], row["usage_retry_after_s"],
                          row["error"]), (VERSION, since, 300, PAUSED))

    def test_click_collect_retries(self):
        """A widget click's collect --retry-paused probes the paused account once; a parsing output ends the pause."""
        install_fake_claude(self.env, stdout=USAGE)
        self.paused(int(time.time()) - 60)
        r = self.collect("--emit-alerts", "--retry-paused")
        self.assertNotIn("claude claude:", r.stderr)
        self.assertEqual([c["argv"][-1] for c in claude_calls(self.env)].count("/usage"), 1)
        row = self.row()
        self.assertEqual((row["usage_disabled_version"], row["usage_disabled_at"], row["usage_retry_after_s"],
                          row["error"], row["source"]), (None, None, None, None, "usage"))

    def test_no_identity_in_snapshot(self):
        install_fake_claude(self.env, stdout="Account: user@example.com\nOrg: Example Org\n" + USAGE)
        self.collect()
        with open(self.env.snapshot_path) as f:
            text = f.read().lower()
        self.assertEqual(self.row()["source"], "usage")
        self.assertNotIn("example", text)


if __name__ == "__main__":
    unittest.main()
