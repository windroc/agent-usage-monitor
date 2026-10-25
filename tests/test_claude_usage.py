import calendar
import json
import os
import unittest
import zoneinfo
from datetime import datetime
from unittest import mock

from agent_usage_monitor import claude_usage
from tests.helpers import ROOT

NY = "America/New_York"
WEEK = 7 * 24 * 3600


def iso(text):
    return calendar.timegm(datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").timetuple())


def local(zone, *parts):
    return int(datetime(*parts, tzinfo=zoneinfo.ZoneInfo(zone)).timestamp())


def reset(text, now, window=None):
    return claude_usage.parse_reset_date(text, now, window)


class ResetDateTest(unittest.TestCase):
    def test_fixture_resets(self):
        now = iso("2026-10-17T05:07:24Z")
        self.assertEqual(reset("Resets Oct 17 at 4:39am (America/New_York)", now, 5 * 3600),
                         local(NY, 2026, 10, 17, 4, 39))
        self.assertEqual(reset("resets Oct 24 at 12:59am (America/New_York)", now, WEEK),
                         local(NY, 2026, 10, 24, 0, 59))

    # ClaudeResetOccurrenceTests: parser preserves both repeated daylight saving times
    def test_repeated_dst_hour(self):
        first = iso("2026-11-01T05:30:00Z")  # 1:30 EDT
        second = iso("2026-11-01T06:30:00Z")  # 1:30 EST
        tomorrow = local(NY, 2026, 11, 2, 1, 30)
        for now, expected in ((first - 60, first), (first + 1800, second), (second + 60, tomorrow)):
            self.assertEqual(reset("Resets 1:30am (America/New_York)", now), expected)
        between = first + 1800
        self.assertEqual(reset("Resets Nov 1, 1:30am (America/New_York)", between), second)
        self.assertEqual(reset("Resets Nov 1, 1:30am (America/New_York)", second + 60, WEEK), second)
        self.assertEqual(reset("Resets Nov 1, 2026, 1:30am (America/New_York)", between), second)
        self.assertEqual(reset("Resets Nov 1, 2026, 1:30am (America/New_York)", second + 60), second)

    # ClaudeResetOccurrenceTests: parser searches across leap years
    def test_leap_years(self):
        leap = iso("2028-02-29T09:00:00Z")
        for now in (iso("2025-01-01T00:00:00Z"), iso("2024-03-01T00:00:00Z")):
            self.assertEqual(reset("Resets Feb 29, 9am (UTC)", now), leap)
        self.assertEqual(reset("Resets Feb 29, 9am (UTC)", iso("2024-02-29T10:00:00Z"), WEEK),
                         iso("2024-02-29T09:00:00Z"))

    # ClaudeResetOccurrenceTests: parser keeps explicit years authoritative across supported time forms
    def test_explicit_years(self):
        now = iso("2025-01-01T00:00:00Z")
        cases = [("Resets Jan 2, 2026, 10:59pm (Europe/Helsinki)", "2026-01-02T20:59:00Z"),
                 ("Resets Jan 2 2026 10pm (UTC)", "2026-01-02T22:00:00Z"),
                 ("Resets Jan 2, 2026, 22:15 (UTC)", "2026-01-02T22:15:00Z"),
                 ("Resets Jan 2, 2026, 22 (UTC)", "2026-01-02T22:00:00Z")]
        for text, expected in cases:
            self.assertEqual(reset(text, now), iso(expected), text)
        self.assertEqual(reset(cases[0][0], iso("2027-01-01T00:00:00Z")), iso(cases[0][1]))

    # ClaudeResetOccurrenceTests: parser rejects nonexistent explicit local time
    def test_nonexistent_local_time(self):
        self.assertIsNone(reset("Resets Mar 8, 2026, 2:30am (America/New_York)", iso("2026-01-01T00:00:00Z")))

    def test_time_only_forms(self):
        now = iso("2026-10-17T12:00:00Z")
        self.assertEqual(reset("Resets 11am (UTC)", now), iso("2026-10-18T11:00:00Z"))
        self.assertEqual(reset("Resets 3 pm (UTC)", now), iso("2026-10-17T15:00:00Z"))
        self.assertEqual(reset("Resets 14:30 (UTC)", now), iso("2026-10-17T14:30:00Z"))
        self.assertEqual(reset("Resets 4:39 AM (UTC)", now), iso("2026-10-18T04:39:00Z"))
        # just passed and inside the window, while the next one is beyond it -> the passed one
        self.assertEqual(reset("Resets 11:30am (UTC)", now, 3600), iso("2026-10-17T11:30:00Z"))

    def test_date_without_year(self):
        now = iso("2026-10-17T12:00:00Z")
        self.assertEqual(reset("Oct 24, 12:59am (UTC)", now), iso("2026-10-24T00:59:00Z"))
        self.assertEqual(reset("Resets Oct24 at 1pm (UTC)", now), iso("2026-10-24T13:00:00Z"))
        self.assertEqual(reset("Resets Jan 1, 9am (UTC)", now), iso("2027-01-01T09:00:00Z"))

    def test_local_zone_fallback(self):
        now = iso("2026-10-17T12:00:00Z")
        with mock.patch.dict(os.environ, {"TZ": "Asia/Tokyo"}):
            self.assertEqual(reset("Resets 3pm (Not/AZone)", now), iso("2026-10-18T06:00:00Z"))
            self.assertEqual(reset("Resets 3pm", now), iso("2026-10-18T06:00:00Z"))

    def test_garbage(self):
        now = iso("2026-10-17T12:00:00Z")
        for text in (None, "", "Resets", "Resets soon", "Resets 25:00 (UTC)", "Resets 13pm (UTC)",
                     "Resets Foo 3, 9am (UTC)"):
            self.assertIsNone(reset(text, now), text)


def fixture(name, folder="claude-usage"):
    with open(os.path.join(ROOT, "tests", "fixtures", folder, name), encoding="utf-8") as f:
        return f.read()


class FixtureTest(unittest.TestCase):
    def test_spike_fixtures(self):
        now = iso("2026-10-17T05:07:24Z")
        for name in ("A1.stdout.txt", "A2.stdout.txt"):
            parsed = claude_usage.parse(fixture(name))
            self.assertEqual(parsed, {"session_left": 83, "weekly_left": 99,
                                      "session_reset": "resets Oct 17 at 4:39am (America/New_York)",
                                      "weekly_reset": "resets Oct 24 at 12:59am (America/New_York)"})
            self.assertEqual(claude_usage.make_windows(parsed, now), {
                "five_hour": {"used_percent": 17, "resets_at": local(NY, 2026, 10, 17, 4, 39)},
                "seven_day": {"used_percent": 1, "resets_at": local(NY, 2026, 10, 24, 0, 59)}})

    def test_config_dir_fixtures(self):
        """TASK-583: explicit CLAUDE_CONFIG_DIR accounts; <dir-a> has no 5h window running."""
        now = iso("2026-10-17T16:00:31Z")
        for name in ("A1.stdout.txt", "A2.stdout.txt"):
            parsed = claude_usage.parse(fixture(name, "claude-usage-config-dir"))
            self.assertEqual(parsed, {"session_left": 100, "weekly_left": 0, "session_reset": None,
                                      "weekly_reset": "resets Oct 18 at 6am (America/New_York)"})
            self.assertEqual(claude_usage.make_windows(parsed, now), {
                "five_hour": {"used_percent": 0, "resets_at": None},
                "seven_day": {"used_percent": 100, "resets_at": local(NY, 2026, 10, 18, 6, 0)}})
        for name in ("B1.stdout.txt", "B2.stdout.txt"):
            parsed = claude_usage.parse(fixture(name, "claude-usage-config-dir"))
            self.assertEqual(parsed, {"session_left": 87, "weekly_left": 86,
                                      "session_reset": "resets Oct 17 at 2:40pm (America/New_York)",
                                      "weekly_reset": "resets Oct 24 at 1am (America/New_York)"})
            self.assertEqual(claude_usage.make_windows(parsed, now), {
                "five_hour": {"used_percent": 13, "resets_at": local(NY, 2026, 10, 17, 14, 40)},
                "seven_day": {"used_percent": 14, "resets_at": local(NY, 2026, 10, 24, 1, 0)}})

    def test_no_weekly_is_absent_window(self):
        parsed = claude_usage.parse("Current session: 40% used · resets 3pm (UTC)\n")
        self.assertEqual(parsed["weekly_left"], None)
        windows = claude_usage.make_windows(parsed, iso("2026-10-17T12:00:00Z"))
        self.assertEqual(windows["five_hour"], {"used_percent": 40, "resets_at": iso("2026-10-17T15:00:00Z")})
        self.assertIsNone(windows["seven_day"])

    def test_unparseable_reset_keeps_percent(self):
        parsed = claude_usage.parse("Current session: 40% used · resets whenever\n")
        self.assertEqual(claude_usage.make_windows(parsed, 0)["five_hour"], {"used_percent": 40, "resets_at": None})

    def test_fractional_percent_rounds_half_up(self):
        self.assertEqual(claude_usage.parse("Current session: 17.5% used\n")["session_left"], 83)

    def test_ansi_and_insights_tail(self):
        text = ("\x1b[1mCurrent session\x1b[0m: 10% used\n\x1b]8;;http://x\x07link\x1b]8;;\x07\n"
                "What's contributing to your limits usage?\nCurrent week (all models): 50% used\n")
        parsed = claude_usage.parse(text)
        self.assertEqual((parsed["session_left"], parsed["weekly_left"]), (90, None))


class CodexBarSampleTest(unittest.TestCase):
    """Inputs and assertions of CodexBar's ClaudeStatusProbe.parse tests (source names in the fixture)."""

    def test_samples(self):
        with open(os.path.join(ROOT, "tests", "fixtures", "codexbar-parse-samples.json"), encoding="utf-8") as f:
            cases = json.load(f)["cases"]
        self.assertEqual(len(cases), 44)
        for case in cases:
            with self.subTest(case["source"]):
                if "parsed" in case:
                    parsed = claude_usage.parse(case["input"])
                    self.assertEqual({k: parsed[k] for k in case["parsed"]}, case["parsed"])
                    continue
                with self.assertRaises(claude_usage.UsageError) as ctx:
                    claude_usage.parse(case["input"])
                error = ctx.exception
                if "not_kind" in case:
                    self.assertNotEqual(error.kind, case["not_kind"])
                    continue
                self.assertEqual(error.kind, case["kind"])
                message = str(error)
                for needle in case.get("contains", []):
                    self.assertIn(needle.lower(), message.lower())
                for needle in case.get("excludes", []):
                    self.assertNotIn(needle.lower(), message.lower())
                if "message" in case:
                    self.assertEqual(message, case["message"])


class IdentityTest(unittest.TestCase):
    def test_identity_lines_ignored(self):
        text = "Account: user@example.com\nOrg: Example Org\nCurrent session: 5% used\n"
        parsed = claude_usage.parse(text)
        self.assertEqual(set(parsed), {"session_left", "weekly_left", "session_reset", "weekly_reset"})
        self.assertNotIn("example", repr(claude_usage.make_windows(parsed, 0)).lower())


class ErrorKindTest(unittest.TestCase):
    def kind(self, text):
        with self.assertRaises(claude_usage.UsageError) as ctx:
            claude_usage.parse(text)
        return ctx.exception.kind

    def test_kinds(self):
        cases = [
            ('Failed to load usage data: {"error":{"type":"authentication_error","message":"OAuth token has expired"}}',
             "auth"),
            ("Failed to load usage data: token_expired", "auth"),
            ("Failed to load usage data: authentication_error", "auth"),
            ('Failed to load usage data: {"error":{"type":"permission_error","message":"nope"}}', "auth"),
            ('Failed to load usage data: {"error":{"type":"rate_limit_error","message":"slow down"}}', "usage_error"),
            ("Failed to load usage data: rate limited", "usage_error"),
            ("Failed to load usage data", "usage_error"),
            ("You are currently using your subscription to power your Claude Code usage\n", "usage_error"),
            ("Do you trust the files in this folder?\n\n/tmp/x\n", "usage_error"),
            # CodexBar extractFirst is case-insensitive: the folder lands in the message, which reads as auth here
            ("do you trust the files in this folder?\n\n/x/unauthorized\n", "auth"),
            ("Loading usage data…\n", "loading"),
            ("Settings: Usage\nLoading usage…\n", "loading"),
            ("", "timeout"),
            ("  \n\x1b[0m\n", "timeout"),
            ("50% used\n", "unrecognized"),
            ("Current week (all models): 50% used\n", "unrecognized"),
            ("hello from a model\n", "unrecognized"),
        ]
        for text, expected in cases:
            self.assertEqual(self.kind(text), expected, text)


class NoticeTest(unittest.TestCase):
    def test_mit_notice(self):
        for name in ("THIRD_PARTY_NOTICES.md", os.path.join("agent_usage_monitor", "claude_usage.py")):
            with open(os.path.join(ROOT, name), encoding="utf-8") as f:
                text = f.read()
            for needle in ("CodexBar", "https://github.com/steipete/CodexBar",
                           "6480977b47f6e4ffd5dcaae1cb0c7fdf34ee449e", "Copyright (c) 2026 Peter Steinberger",
                           "Permission is hereby granted, free of charge",
                           "The above copyright notice and this permission notice shall be included",
                           'THE SOFTWARE IS PROVIDED "AS IS"', "DEALINGS IN THE"):
                self.assertIn(needle, text, (name, needle))


if __name__ == "__main__":
    unittest.main()
