import os
import unittest

from tests.helpers import ROOT


class ReadmeTest(unittest.TestCase):
    """M2 FR-7: the README covers the upgrade, the first notification permission and the Step 1 conclusion."""

    def setUp(self):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            self.text = f.read()

    def section(self, heading):
        start = self.text.index("\n## %s\n" % heading)
        end = self.text.find("\n## ", start + 1)
        return self.text[start:end if end >= 0 else None]

    def test_upgrade(self):
        self.assertIn("After `git pull`, run `make -C ~/.local/share/agent-usage-monitor install` again", self.text)

    def test_first_notification_permission(self):
        alerts = self.section("Alerts")
        self.assertIn("click Allow", alerts)
        self.assertIn("System Settings › Notifications › Agent Usage Monitor", alerts)
        self.assertIn("`com.windroc.agent-usage-monitor`", alerts)

    def test_no_notification_turn_on(self):
        alerts = self.section("Alerts")
        self.assertIn("No notifications?", alerts)
        self.assertIn("kept for the next run", alerts)

    def test_alert_line_format(self):
        alerts = self.section("Alerts")
        self.assertIn('`AUM-ALERT {"text": …, "add": […], "remove": […]}`', alerts)
        self.assertNotIn('`AUM-ALERT {"text": …}`', alerts)

    def test_step1_conclusion(self):
        spike = self.section("Spike conclusions")
        self.assertIn("**TASK-638**", spike)
        for fact in ("`osascript`", "Script Editor", "`UNUserNotificationCenter`", "Allow prompt"):
            self.assertIn(fact, spike)

    def test_settings_window(self):
        """TASK-645 FR-10: how to open the settings window, and hand editing still works."""
        accounts = self.section("Development")
        self.assertIn("### Settings window", accounts)
        self.assertIn("Open Agent Usage Monitor from Applications, Spotlight or Finder", self.text)
        self.assertIn("You can still edit `accounts.json` by hand", self.text)

    def test_settings_gear(self):
        """TASK-654: the widget's gear opens the settings window; the rest of the widget refreshes."""
        self.assertIn("click the small grey gear at the bottom right of the widget", self.text)
        self.assertIn("A click anywhere but the gear runs `collect`", self.text)

    def test_refresh_arrow(self):
        """TASK-874: a refresh arrow left of the gear shows that a click refreshes."""
        self.assertIn("A small grey refresh arrow just left of the gear does the same", self.text)
        self.assertIn("the arrow and the gear; click the widget or the arrow to collect", self.text)

    def test_stale_reason(self):
        """WDRC-98: the red triangle and the reason notice replace the `⚠` prefix."""
        self.assertIn("a red triangle precedes the client", self.text)
        self.assertIn("(`error` in its snapshot row", self.text)
        self.assertIn("keeps its bars", self.text)
        self.assertNotIn("The client starts with `⚠`", self.text)

    def test_paused_retry(self):
        """WDRC-100: a paused Claude probe retries on a widget click and 6 hours after its pause started."""
        self.assertIn("A paused account runs its probe once more when you click the widget (`collect --retry-paused`) "
                      "and once its pause is 6 hours old (`usage_disabled_at`", self.text)
        self.assertIn("A pause recorded before `usage_disabled_at` existed retries on the next run", self.text)
        self.assertIn("a widget click adds `--retry-paused`", self.text)
        self.assertNotIn("Delete `usage_disabled_version`", self.text)
        self.assertNotIn("so it only collects and refreshes, as before", self.text)


if __name__ == "__main__":
    unittest.main()
