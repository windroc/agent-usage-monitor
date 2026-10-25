import json
import os
import unittest

from agent_usage_monitor import accounts
from tests.helpers import ROOT, Env


class LoadTest(unittest.TestCase):
    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.cleanup)

    def load(self):
        return accounts.load(self.env.environ)

    def assert_invalid(self, data, *needles):
        self.env.write_accounts(data)
        with self.assertRaises(accounts.AccountsError) as cm:
            self.load()
        msg = str(cm.exception)
        self.assertIn(accounts.config_path(self.env.environ), msg)
        for n in needles:
            self.assertIn(n, msg)

    def test_config_path(self):
        self.assertEqual(accounts.config_path(self.env.environ),
                         os.path.join(self.env.config, "agent-usage-monitor", "accounts.json"))
        environ = dict(self.env.environ, XDG_CONFIG_HOME="")
        self.assertEqual(accounts.config_path(environ),
                         os.path.join(self.env.home, ".config", "agent-usage-monitor", "accounts.json"))

    def test_file_order_and_realpath(self):
        for n in ("c", "a", "b"):
            self.env.mkdir(n)
        os.symlink(os.path.join(self.env.home, "b"), os.path.join(self.env.home, "link-b"))
        self.env.write_accounts({"accounts": [
            {"name": "c", "client": "codex", "dir": "~/c"},
            {"name": "a", "client": "claude", "dir": os.path.join(self.env.home, "a")},
            {"name": "b", "client": "claude", "dir": "~/link-b"},
        ]})
        threshold, accts, hint = self.load()
        self.assertEqual(threshold, 90)
        self.assertIsNone(hint)
        home = os.path.realpath(self.env.home)
        self.assertEqual(accts, [
            accounts.Account("c", "codex", os.path.join(home, "c")),
            accounts.Account("a", "claude", os.path.join(home, "a")),
            accounts.Account("b", "claude", os.path.join(home, "b")),
        ])

    def test_defaults_both(self):
        for n in (".claude", ".codex", ".claude-bak"):
            self.env.mkdir(n)
        threshold, accts, hint = self.load()
        home = os.path.realpath(self.env.home)
        self.assertEqual(threshold, 90)
        self.assertEqual(accts, [
            accounts.Account("claude", "claude", os.path.join(home, ".claude")),
            accounts.Account("codex", "codex", os.path.join(home, ".codex")),
        ])
        self.assertIn(accounts.config_path(self.env.environ), hint)
        self.assertNotIn("\n", hint)

    def test_defaults_partial_and_none(self):
        _, accts, _ = self.load()
        self.assertEqual(accts, [])
        self.env.mkdir(".codex")
        _, accts, _ = self.load()
        self.assertEqual([a.name for a in accts], ["codex"])

    def test_invalid_json(self):
        self.assert_invalid("{not json", "JSON")

    def test_invalid_deeply_nested(self):
        self.assert_invalid("[" * 200000, "JSON")

    def test_invalid_shape(self):
        self.assert_invalid([], "object")
        self.assert_invalid({"accounts": {}}, "accounts")
        self.assert_invalid({}, "accounts")

    def test_invalid_item(self):
        self.env.mkdir("a")
        self.assert_invalid({"accounts": ["x"]}, "accounts[0]")
        self.assert_invalid({"accounts": [{"client": "codex", "dir": "~/a"}]}, "accounts[0]", "name")
        self.assert_invalid({"accounts": [{"name": "a", "dir": "~/a"}]}, "accounts[0]", "(a)", "client")
        self.assert_invalid({"accounts": [{"name": "a", "client": "codex", "dir": 3}]}, "accounts[0]", "dir")

    def test_invalid_duplicate_name(self):
        self.env.mkdir("a")
        self.env.mkdir("b")
        self.assert_invalid({"accounts": [
            {"name": "x", "client": "codex", "dir": "~/a"},
            {"name": "x", "client": "codex", "dir": "~/b"},
        ]}, "accounts[1]", "(x)", "duplicate")

    def test_invalid_client(self):
        self.env.mkdir("a")
        self.assert_invalid({"accounts": [{"name": "a", "client": "gemini", "dir": "~/a"}]},
                            "accounts[0]", "(a)", "client")

    def test_invalid_dir_missing(self):
        self.assert_invalid({"accounts": [{"name": "a", "client": "codex", "dir": "~/nope"}]},
                            "accounts[0]", "(a)", "dir")
        with open(os.path.join(self.env.home, "file"), "w"):
            pass
        self.assert_invalid({"accounts": [{"name": "a", "client": "codex", "dir": "~/file"}]},
                            "accounts[0]", "dir")

    def test_invalid_same_realpath(self):
        self.env.mkdir("a")
        os.symlink(os.path.join(self.env.home, "a"), os.path.join(self.env.home, "alias"))
        self.assert_invalid({"accounts": [
            {"name": "a", "client": "codex", "dir": "~/a"},
            {"name": "b", "client": "claude", "dir": "~/alias"},
        ]}, "accounts[1]", "(b)", "accounts[0]")

    def test_account_display_string(self):
        for n in ("a", "b", "c"):
            self.env.mkdir(n)
        self.env.write_accounts({"accounts": [
            {"name": "a", "client": "claude", "dir": "~/a", "account": "you@example.com"},
            {"name": "b", "client": "codex", "dir": "~/b", "account": "you@example.com"},
            {"name": "c", "client": "claude", "dir": "~/c"},
        ]})
        _, accts, _ = self.load()
        self.assertEqual([a.account for a in accts], ["you@example.com", "you@example.com", None])

    def test_example_file(self):
        for n in (".claude", ".claude-work", ".codex"):
            self.env.mkdir(n)
        with open(os.path.join(ROOT, "accounts.example.json"), encoding="utf-8") as f:
            self.env.write_accounts(f.read())
        home = os.path.realpath(self.env.home)
        self.assertEqual(self.load(), (90, [
            accounts.Account("claude", "claude", os.path.join(home, ".claude"), "you@example.com"),
            accounts.Account("claude-work", "claude", os.path.join(home, ".claude-work"), "work@example.com"),
            accounts.Account("codex", "codex", os.path.join(home, ".codex"), "you@example.com"),
        ], None))

    def test_invalid_account(self):
        self.env.mkdir("a")
        for bad in ("", 3, None, ["x"]):
            with self.subTest(bad=bad):
                self.assert_invalid({"accounts": [{"name": "a", "client": "codex", "dir": "~/a", "account": bad}]},
                                    "accounts[0]", "(a)", "account")

    def test_threshold(self):
        self.env.write_accounts({"threshold": 80, "accounts": []})
        self.assertEqual(self.load()[0], 80)
        self.env.write_accounts({"threshold": 100, "accounts": []})
        self.assertEqual(self.load()[0], 100)
        self.env.write_accounts({"threshold": 0.5, "accounts": []})
        self.assertEqual(self.load()[0], 0.5)

    def test_threshold_invalid(self):
        for bad in (0, 101, -1, "90", True, None):
            self.assert_invalid({"threshold": bad, "accounts": []}, "threshold")


class SettingsTest(unittest.TestCase):
    """TASK-645: the settings window reads and writes the list with collect's rules."""

    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.cleanup)
        self.path = accounts.config_path(self.env.environ)

    def row(self, name, client, dir, account="", original="{}"):
        return {"name": name, "client": client, "dir": dir, "account": account, "original": original}

    def save(self, rows, threshold=90, original="{}"):
        return accounts.save(self.env.environ, {"threshold": threshold, "accounts": rows, "original": original})

    def read_file(self):
        with open(self.path, encoding="utf-8") as f:
            return json.load(f)

    def test_validate_one_problem_per_row(self):
        self.env.mkdir("a")
        self.env.mkdir("b")
        os.symlink(os.path.join(self.env.home, "a"), os.path.join(self.env.home, "alias"))
        _, accts, problems = accounts.validate({"threshold": 85, "accounts": [
            {"name": "a", "client": "claude", "dir": "~/a"},
            {"name": "", "client": "claude", "dir": "~/b"},
            {"name": "a", "client": "codex", "dir": "~/b"},
            {"name": "c", "client": "gemini", "dir": "~/b"},
            {"name": "d", "client": "codex", "dir": "~/nope"},
            {"name": "e", "client": "codex", "dir": "~/alias"},
            {"name": "f", "client": "codex", "dir": "~/b"},
        ]}, self.env.environ)
        self.assertEqual([a.name for a in accts], ["a", "f"])
        self.assertEqual([(i, where) for i, where, _ in problems],
                         [(1, "accounts[1]"), (2, "accounts[2] (a)"), (3, "accounts[3] (c)"),
                          (4, "accounts[4] (d)"), (5, "accounts[5] (e)")])
        texts = [p for _, _, p in problems]
        for i, needle in enumerate(("name", "duplicate name, also accounts[0]", "client", "~/nope", "accounts[0]")):
            self.assertIn(needle, texts[i])

    def test_validate_top_level(self):
        _, _, problems = accounts.validate({"threshold": 0, "accounts": {}}, self.env.environ)
        self.assertEqual([(i, w) for i, w, _ in problems], [(None, None), (None, None)])
        self.assertIn("threshold", problems[0][2])
        self.assertIn("accounts", problems[1][2])

    def test_editable_missing_file_defaults(self):
        self.env.mkdir(".claude")
        view = accounts.editable(self.env.environ)
        self.assertIsNone(view["error"])
        self.assertEqual(view["threshold"], 90)
        self.assertEqual(view["accounts"], [self.row("claude", "claude", "~/.claude")])
        self.assertFalse(os.path.exists(self.path))
        self.assertFalse(os.path.exists(os.path.dirname(self.path)))

    def test_editable_shows_file(self):
        a = self.env.mkdir("a")
        item = {"name": "a", "client": "codex", "dir": a, "account": "you@example.com", "note": 1}
        self.env.write_accounts({"threshold": 85, "accounts": [item], "extra": True})
        view = accounts.editable(self.env.environ)
        self.assertIsNone(view["error"])
        self.assertEqual(view["threshold"], 85)
        self.assertEqual(view["accounts"], [self.row("a", "codex", "~/a", "you@example.com", json.dumps(item))])
        self.assertEqual(json.loads(view["original"])["extra"], True)

    def test_editable_unparsable_left_alone(self):
        self.env.mkdir(".codex")
        for bad in ("{not json", "[]", {"accounts": {}}, {"accounts": ["x"]}, {"accounts": [{"name": 3}]},
                    {"threshold": "90", "accounts": []}):
            with self.subTest(bad=bad):
                self.env.write_accounts(bad)
                with open(self.path, "rb") as f:
                    before = f.read()
                view = accounts.editable(self.env.environ)
                self.assertIn("accounts.json", view["error"])
                self.assertEqual(view["accounts"], [self.row("codex", "codex", "~/.codex")])
                self.assertEqual(view["original"], "{}")
                with open(self.path, "rb") as f:
                    self.assertEqual(f.read(), before)

    def test_editable_file_problems_from_validate(self):
        """correctness#3: what collect rejects at file level opens as unreadable, with collect's own text."""
        self.env.mkdir(".codex")
        for bad, needle in (({"threshold": 80}, "accounts must be a list"),
                            ({"threshold": 0, "accounts": []}, "threshold must be a number")):
            with self.subTest(bad=bad):
                self.env.write_accounts(bad)
                with self.assertRaises(accounts.AccountsError):
                    accounts.load(self.env.environ)
                view = accounts.editable(self.env.environ)
                self.assertIn(needle, view["error"])
                self.assertEqual(view["accounts"], [self.row("codex", "codex", "~/.codex")])

    def test_save_keeps_unedited_dir(self):
        """requirement-fidelity#1: only an edited row's dir is rewritten."""
        a, b = self.env.mkdir("a"), self.env.mkdir("b")
        self.env.mkdir("c")
        self.env.write_accounts({"accounts": [
            {"name": "a", "client": "claude", "dir": a},
            {"name": "b", "client": "claude", "dir": b},
            {"name": "c", "client": "codex", "dir": "~/c"},
        ]})
        view = accounts.editable(self.env.environ)
        rows = view["accounts"]
        self.assertEqual([r["dir"] for r in rows], ["~/a", "~/b", "~/c"])
        rows[1]["dir"] = "~/c"
        rows[2]["dir"] = "~/b"
        self.assertEqual(self.save(rows, original=view["original"]), [])
        self.assertEqual([i["dir"] for i in self.read_file()["accounts"]], [a, "~/c", "~/b"])

    def test_save_problems_write_nothing(self):
        self.env.mkdir("a")
        cases = [
            ([self.row("", "claude", "~/a")], "name"),
            ([self.row("a", "claude", "~/a"), self.row("a", "codex", "~/a")], "duplicate"),
            ([self.row("a", "claude", "~/nope")], "dir"),
            ([self.row("a", "gemini", "~/a")], "client"),
        ]
        for rows, needle in cases:
            with self.subTest(needle=needle):
                problems = self.save(rows)
                self.assertEqual(len(problems), 1)
                self.assertEqual(problems[0][0], len(rows) - 1)
                self.assertIn(needle, problems[0][1])
                self.assertFalse(os.path.exists(self.path))
        self.assertEqual(self.save([], threshold=101)[0][0], None)

    def test_save_keeps_unknown_fields_mode_600(self):
        self.env.mkdir("a")
        self.env.mkdir("b")
        item = {"note": "keep", "name": "old", "client": "claude", "dir": "~/a", "account": "you@example.com"}
        self.env.write_accounts({"comment": "keep", "threshold": 90, "accounts": [item]})
        os.chmod(self.path, 0o644)
        original = accounts.editable(self.env.environ)["original"]
        self.assertEqual(self.save([self.row("b", "codex", "~/b"), self.row("new", "claude", "~/a", original=json.dumps(item))],
                                   threshold=85.0, original=original), [])
        data = self.read_file()
        self.assertEqual(data, {"comment": "keep", "threshold": 85, "accounts": [
            {"name": "b", "client": "codex", "dir": "~/b"},
            {"note": "keep", "name": "new", "client": "claude", "dir": "~/a"},
        ]})
        self.assertIsInstance(data["threshold"], int)
        self.assertEqual(os.stat(self.path).st_mode & 0o777, 0o600)
        self.assertEqual(accounts.load(self.env.environ)[0], 85)
        self.assertEqual(os.listdir(os.path.dirname(self.path)), ["accounts.json"])

    def test_save_creates_dir_and_follows_link(self):
        self.env.mkdir("a")
        self.assertEqual(self.save([self.row("a", "claude", "~/a", "you@example.com")]), [])
        self.assertEqual(self.read_file()["accounts"][0]["account"], "you@example.com")
        target = os.path.join(self.env.root, "dotfiles-accounts.json")
        os.replace(self.path, target)
        os.symlink(target, self.path)
        self.assertEqual(self.save([self.row("a", "claude", "~/a")], threshold=70), [])
        self.assertTrue(os.path.islink(self.path))
        self.assertEqual(self.read_file()["threshold"], 70)


if __name__ == "__main__":
    unittest.main()
