import json
import os
import subprocess
import sys
import unittest
from unittest import mock

from agent_usage_monitor import store
from agent_usage_monitor.accounts import Account
from tests.helpers import ROOT, Env

NOW = 1792130400
H = 3600


def w(pct, at=None):
    return {"used_percent": pct, "resets_at": at}


class Base(unittest.TestCase):
    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.cleanup)
        self.dir = self.env.state
        self.accounts = [Account("a", "codex", "/d/a"), Account("b", "claude", "/d/b")]

    def write(self, updates=None, failed=(), accounts=None, now=NOW, threshold=90):
        return store.write(self.dir, self.accounts if accounts is None else accounts, threshold,
                           updates or {}, failed, now=now)

    def snap(self):
        return self.env.snapshot()

    def row(self, name):
        return next(r for r in self.snap()["accounts"] if r["name"] == name)


class WriteTest(Base):
    def test_new_rows_defaults(self):
        self.assertEqual(self.write(), [])
        snap = self.snap()
        self.assertEqual(snap["schema"], 1)
        self.assertEqual(snap["generated_at"], NOW)
        self.assertEqual(self.row("b"), {
            "name": "b", "client": "claude", "dir": "/d/b", "available": None, "available_at": None,
            "five_hour": w(None), "seven_day": w(None), "fetched_at": None, "source": "none",
            "stale": False, "usage_disabled_version": None, "usage_disabled_at": None, "unrecognized_count": 0,
            "unrecognized_version": None, "needs_login": False, "error": None, "account": None})

    def test_old_row_without_error(self):
        """WDRC-98: a row written before `error` existed reads as no error; a failed run's reason replaces it."""
        os.makedirs(self.dir)
        with open(self.env.snapshot_path, "w") as f:
            json.dump({"schema": 1, "accounts": [{"name": "a", "five_hour": None, "seven_day": w(1, 2),
                                                  "fetched_at": NOW - 60}]}, f)
        self.write()
        self.assertIsNone(self.row("a")["error"])
        self.assertEqual(self.snap()["schema"], 1)
        self.write({"a": {"error": "timed out after 10 s"}}, failed=["a"])
        self.assertEqual((self.row("a")["error"], self.row("a")["source"]), ("timed out after 10 s", "cache"))
        self.write(failed=["a"])
        self.assertEqual(self.row("a")["error"], "timed out after 10 s", "a skipped run keeps the reason")

    def test_update_recomputes(self):
        self.write({"a": {"five_hour": w(10, NOW + H), "seven_day": w(10, NOW + H), "fetched_at": NOW,
                          "source": "app-server"},
                    "b": {"five_hour": w(10, NOW + H), "seven_day": w(10, NOW + H), "fetched_at": NOW,
                          "source": "app-server"}})
        self.assertEqual(self.snap()["summary"]["available"], ["b", "a"], "claude b first")
        self.write({"a": {"five_hour": w(95, NOW + 2 * H)}})
        snap = self.snap()
        self.assertEqual([r["name"] for r in snap["accounts"]], ["b", "a"])
        self.assertIs(self.row("a")["available"], False)
        self.assertEqual(self.row("a")["seven_day"], w(10, NOW + H), "other fields kept")
        self.assertEqual(snap["summary"], {"available": ["b"], "next": {"name": "a", "at": NOW + 2 * H}})

    def test_absent_window_replaces_old(self):
        self.write({"a": {"five_hour": w(50, NOW + H), "seven_day": w(10, NOW + H), "fetched_at": NOW}})
        self.write({"a": {"five_hour": None, "seven_day": w(87, NOW + H), "fetched_at": NOW}})
        self.assertIsNone(self.row("a")["five_hour"])
        self.assertIs(self.row("a")["available"], True)

    def test_unknown_keys_kept(self):
        self.write()
        snap = self.snap()
        snap["extra"] = {"x": 1}
        snap["accounts"][0]["mine"] = "keep"
        name = snap["accounts"][0]["name"]
        with open(self.env.snapshot_path, "w") as f:
            json.dump(snap, f)
        self.write()
        self.assertEqual(self.snap()["extra"], {"x": 1})
        self.assertEqual(self.row(name)["mine"], "keep")

    def test_list_fields_overwrite_row(self):
        self.write()
        self.write(accounts=[Account("a", "codex", "/d/new")])
        self.assertEqual(self.row("a")["dir"], "/d/new")

    def test_account_from_list(self):
        os.makedirs(self.dir)
        with open(self.env.snapshot_path, "w") as f:
            # a row written before the account field existed
            json.dump({"accounts": [{"name": "a", "five_hour": None, "seven_day": w(1, 2), "fetched_at": None}]}, f)
        self.write(accounts=[Account("a", "codex", "/d/a", "you@example.com"), Account("b", "claude", "/d/b")])
        self.assertEqual((self.row("a")["account"], self.row("b")["account"]), ("you@example.com", None))

    def test_removed_account_dropped(self):
        self.write()
        self.write(accounts=self.accounts[:1])
        self.assertEqual([r["name"] for r in self.snap()["accounts"]], ["a"])

    def test_failed_with_previous_values_is_cache(self):
        self.write({"a": {"five_hour": w(10, NOW + H), "seven_day": w(20, NOW + H), "fetched_at": NOW - 60,
                          "source": "app-server"}})
        self.write(failed=["a"])
        r = self.row("a")
        self.assertEqual((r["source"], r["five_hour"], r["fetched_at"]), ("cache", w(10, NOW + H), NOW - 60))

    def test_failed_without_values_is_none(self):
        self.write(failed=["a"])
        r = self.row("a")
        self.assertEqual((r["source"], r["five_hour"], r["seven_day"]), ("none", w(None), w(None)))
        # a row with only an absent window but no fetched_at is also reset
        snap = self.snap()
        snap["accounts"][[x["name"] for x in snap["accounts"]].index("a")]["five_hour"] = None
        with open(self.env.snapshot_path, "w") as f:
            json.dump(snap, f)
        self.write(failed=["a"])
        self.assertEqual(self.row("a")["five_hour"], w(None))

    def test_failed_write_keeps_old(self):
        self.write()
        with open(self.env.snapshot_path, "rb") as f:
            before = f.read()
        with mock.patch("agent_usage_monitor.store.json.dumps", side_effect=ValueError("boom")):
            with self.assertRaises(ValueError):
                self.write(now=NOW + 1)
        with open(self.env.snapshot_path, "rb") as f:
            self.assertEqual(f.read(), before)
        self.assertEqual(sorted(os.listdir(self.dir)), ["snapshot.json", "snapshot.lock"])

    def test_modes_and_entries(self):
        self.write()
        self.write()
        self.assertEqual(os.stat(self.dir).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(self.env.snapshot_path).st_mode & 0o777, 0o600)
        self.assertEqual(sorted(os.listdir(self.dir)), ["snapshot.json", "snapshot.lock"])

    def test_concurrent_writers(self):
        code = (
            "import sys; sys.path.insert(0, %r)\n"
            "from agent_usage_monitor import store\n"
            "from agent_usage_monitor.accounts import Account\n"
            "accts = [Account('a', 'codex', '/d/a'), Account('b', 'codex', '/d/b')]\n"
            "name, pct = sys.argv[1], int(sys.argv[2])\n"
            "for i in range(30):\n"
            "    store.write(%r, accts, 90, {name: {'five_hour': {'used_percent': pct + i, 'resets_at': None},"
            " 'fetched_at': 1}})\n"
        ) % (ROOT, self.dir)
        procs = [subprocess.Popen([sys.executable, "-c", code, name, str(pct)])
                 for name, pct in (("a", 10), ("b", 50))]
        for p in procs:
            self.assertEqual(p.wait(60), 0)
        self.assertEqual(self.row("a")["five_hour"]["used_percent"], 39)
        self.assertEqual(self.row("b")["five_hour"]["used_percent"], 79)


class ReadTest(Base):
    def assert_garbage(self, content):
        os.makedirs(self.dir, exist_ok=True)
        with open(self.env.snapshot_path, "w") as f:
            f.write(content if isinstance(content, str) else json.dumps(content))
        snap, warning = store.read(self.env.snapshot_path)
        self.assertIsNone(snap)
        self.assertIn(self.env.snapshot_path, warning)
        self.assertNotIn("\n", warning)
        self.assertEqual(len(self.write()), 1)
        self.assertEqual(len(self.snap()["accounts"]), 2)

    def test_missing_is_silent(self):
        self.assertEqual(store.read(self.env.snapshot_path), (None, None))

    def test_garbage_text(self):
        self.assert_garbage("\x00garbage{")

    def test_garbage_deeply_nested(self):
        self.assert_garbage("[" * 200000)

    def test_garbage_shapes(self):
        row = {"name": "a", "five_hour": w(1), "seven_day": None, "fetched_at": 1}
        for bad in ([], {"accounts": {}}, {"accounts": ["x"]}, {"accounts": [{"name": 3}]},
                    {"accounts": [dict(row, five_hour=5)]},
                    {"accounts": [dict(row, five_hour={"used_percent": "1", "resets_at": None})]},
                    {"accounts": [dict(row, seven_day={"used_percent": 1})]},
                    {"accounts": [dict(row, five_hour=w(True))]},
                    {"accounts": [dict(row, fetched_at="x")]}):
            with self.subTest(bad=bad):
                self.assert_garbage(bad)

    def test_valid_partial_row_accepted(self):
        os.makedirs(self.dir)
        with open(self.env.snapshot_path, "w") as f:
            json.dump({"accounts": [{"name": "a", "five_hour": None, "seven_day": w(1, 2), "fetched_at": None}]}, f)
        snap, warning = store.read(self.env.snapshot_path)
        self.assertIsNone(warning)
        self.assertEqual(snap["accounts"][0]["name"], "a")

    @unittest.skipIf(os.geteuid() == 0, "root reads mode 000 files")
    def test_unreadable(self):
        self.write()
        os.chmod(self.env.snapshot_path, 0)
        snap, warning = store.read(self.env.snapshot_path)
        self.assertIsNone(snap)
        self.assertIn("unreadable", warning)


class StateDirTest(unittest.TestCase):
    def test_env_override_and_default(self):
        self.assertEqual(store.state_dir({"AGENT_USAGE_MONITOR_STATE_DIR": "/x", "HOME": "/h"}), "/x")
        self.assertEqual(store.state_dir({"HOME": "/h"}), "/h/.local/state/agent-usage-monitor")

    def test_snapshot_path(self):
        self.assertEqual(store.snapshot_path("/s"), "/s/snapshot.json")

    def test_ensure_dir_creates_0700(self):
        env = Env()
        self.addCleanup(env.cleanup)
        d = os.path.join(env.state, "x")
        store.ensure_dir(d)
        self.assertEqual(os.stat(d).st_mode & 0o777, 0o700)
        store.ensure_dir(d)


if __name__ == "__main__":
    unittest.main()
