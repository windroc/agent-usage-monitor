import glob
import os
import re
import unittest

from tests.helpers import ROOT

# CJK punctuation, ideographs and full-width forms.
CJK = re.compile("[　-〿一-鿿＀-￯]")


class HostStringsTest(unittest.TestCase):
    """TASK-877: the settings window, its menus and its status and error lines are in English.
    TASK-880: so are the widget and the alert notifications."""

    def setUp(self):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
            self.readme = f.read()

    def assert_files_no_cjk(self, paths):
        self.assertTrue(paths)
        for path in paths:
            with open(path, encoding="utf-8") as f:
                for n, line in enumerate(f, 1):
                    with self.subTest(file=os.path.basename(path), line=n):
                        self.assertIsNone(CJK.search(line), line)

    def assert_readme_no_cjk(self, start, end):
        i = self.readme.index(start)
        self.assertIsNone(CJK.search(self.readme[i:self.readme.index(end, i + 1)]))

    def test_host_swift_has_no_cjk(self):
        self.assert_files_no_cjk(sorted(glob.glob(os.path.join(ROOT, "macos", "Host", "*.swift"))))

    def test_widget_swift_has_no_cjk(self):
        self.assert_files_no_cjk(sorted(glob.glob(os.path.join(ROOT, "macos", "Widget", "*.swift"))))

    def test_alerts_have_no_cjk(self):
        self.assert_files_no_cjk([os.path.join(ROOT, "agent_usage_monitor", "alerts.py")])

    def test_readme_settings_window_has_no_cjk(self):
        self.assert_readme_no_cjk("\n### Settings window\n", "\n### ")

    def test_readme_widget_has_no_cjk(self):
        self.assert_readme_no_cjk("\nThe widget is a dark card", "\n\n")

    def test_readme_alerts_has_no_cjk(self):
        self.assert_readme_no_cjk("\n## Alerts\n", "\n## ")


if __name__ == "__main__":
    unittest.main()
