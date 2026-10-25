import json
import os
import signal
import subprocess
import time
import unittest
from unittest import mock

from agent_usage_monitor import accounts, cli, codex
from tests.helpers import (BIN, Env, claude_calls, install_fake_claude, install_fake_codex, pids, rate_limits, reaped,
                           received, window)

ROW_KEYS = {"name", "client", "dir", "available", "available_at", "five_hour", "seven_day",
            "fetched_at", "source", "stale", "usage_disabled_version", "unrecognized_count", "unrecognized_version",
            "needs_login", "error", "account"}


class CollectTest(unittest.TestCase):
    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.cleanup)

    def collect(self, *args):
        r = self.env.run("collect", *args)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "")
        return r

    def test_stdout_empty_exit0(self):
        before = int(time.time())
        self.collect()
        self.assertGreaterEqual(self.env.snapshot()["generated_at"], before)

    def test_usage_errors(self):
        self.collect()
        mtime = os.stat(self.env.snapshot_path).st_mtime_ns
        for args in (["collect", "--nosuch"], ["nosuch"], []):
            r = self.env.run(*args)
            self.assertEqual(r.returncode, 2, args)
            self.assertIn("usage: agent-usage-monitor", r.stderr)
            self.assertEqual(r.stdout, "")
        self.assertEqual(os.stat(self.env.snapshot_path).st_mtime_ns, mtime)

    def test_defaults_hint(self):
        for n in (".claude", ".codex", ".claude-bak"):
            self.env.mkdir(n)
        r = self.collect()
        lines = [l for l in r.stderr.splitlines() if "no account list" in l]
        self.assertEqual(len(lines), 1)
        self.assertIn(os.path.join(self.env.config, "agent-usage-monitor", "accounts.json"), lines[0])
        self.assertEqual(sorted(x["name"] for x in self.env.snapshot()["accounts"]), ["claude", "codex"])

    def test_bad_list_exit2_snapshot_unchanged(self):
        self.collect()
        with open(self.env.snapshot_path, "rb") as f:
            before = f.read()
        mtime = os.stat(self.env.snapshot_path).st_mtime_ns
        self.env.write_accounts('{"accounts": [{"name": "x", "client": "nope", "dir": "/"}]}')
        r = self.env.run("collect")
        self.assertEqual(r.returncode, 2)
        self.assertIn("accounts[0] (x)", r.stderr)
        self.assertEqual(r.stdout, "")
        with open(self.env.snapshot_path, "rb") as f:
            self.assertEqual(f.read(), before)
        self.assertEqual(os.stat(self.env.snapshot_path).st_mtime_ns, mtime)

    def test_bad_list_creates_no_state_dir(self):
        self.env.write_accounts("{")
        self.assertEqual(self.env.run("collect").returncode, 2)
        self.assertFalse(os.path.exists(self.env.state))

    def test_threshold_in_snapshot(self):
        self.env.write_accounts({"threshold": 80, "accounts": []})
        self.collect()
        self.assertEqual(self.env.snapshot()["threshold"], 80)

    def test_state_dir_modes_and_entries(self):
        self.env.mkdir(".claude")
        self.collect()
        self.assertEqual(os.stat(self.env.state).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(self.env.snapshot_path).st_mode & 0o777, 0o600)
        self.assertEqual(sorted(os.listdir(self.env.state)), ["probe", "snapshot.json", "snapshot.lock"])
        self.collect()
        self.assertEqual(os.stat(self.env.snapshot_path).st_mode & 0o777, 0o600)
        self.assertEqual(sorted(os.listdir(self.env.state)), ["probe", "snapshot.json", "snapshot.lock"])

    def test_corrupt_snapshot(self):
        self.env.mkdir(".claude")
        os.makedirs(self.env.state)
        with open(self.env.snapshot_path, "w") as f:
            f.write("garbage")
        r = self.collect()
        self.assertEqual(len([l for l in r.stderr.splitlines() if "snapshot" in l]), 1)
        self.assertEqual([x["name"] for x in self.env.snapshot()["accounts"]], ["claude"])

    def test_default_claude_row_empty(self):
        self.env.mkdir(".claude")
        self.collect()
        snap = self.env.snapshot()
        self.assertEqual(snap["accounts"][0], {
            "name": "claude", "client": "claude", "dir": os.path.realpath(os.path.join(self.env.home, ".claude")),
            "available": None, "available_at": None,
            "five_hour": {"used_percent": None, "resets_at": None},
            "seven_day": {"used_percent": None, "resets_at": None},
            "fetched_at": None, "source": "none", "stale": False, "usage_disabled_version": None,
            "unrecognized_count": 0, "unrecognized_version": None, "needs_login": False, "error": None,
            "account": None})

    def test_claude_row_recomputed(self):
        self.env.mkdir(".claude")
        self.collect()
        snap = self.env.snapshot()
        now = int(time.time())
        snap["accounts"][0].update(five_hour={"used_percent": 93, "resets_at": now - 60},
                                   seven_day={"used_percent": 10, "resets_at": now + 3600},
                                   fetched_at=now - 600, source="cache", available=False)
        with open(self.env.snapshot_path, "w") as f:
            json.dump(snap, f)
        self.collect()
        row = self.env.snapshot()["accounts"][0]
        self.assertEqual(row["five_hour"], {"used_percent": 0, "resets_at": None})
        self.assertIs(row["available"], True)
        self.assertEqual(row["source"], "cache")

    def test_snapshot_format(self):
        self.env.mkdir(".claude")
        self.collect()
        snap = self.env.snapshot()
        self.assertEqual(set(snap), {"schema", "generated_at", "threshold", "accounts", "summary", "notified"})
        self.assertEqual(snap["schema"], 1)
        self.assertIsInstance(snap["generated_at"], int)
        for row in snap["accounts"]:
            self.assertEqual(set(row), ROW_KEYS)

    def codex_account(self, name, **cfg):
        d = os.path.join(self.env.home, name)
        install_fake_codex(self.env, d, **cfg)
        return {"name": name, "client": "codex", "dir": d}

    def row(self, name):
        return next(r for r in self.env.snapshot()["accounts"] if r["name"] == name)

    def test_two_codex_accounts(self):
        later = int(time.time()) + 3600
        self.env.write_accounts({"accounts": [
            self.codex_account("c1", result=rate_limits(window(10, 300, later), window(20, 10080, later))),
            self.codex_account("c2", result=rate_limits(window(70, 10080, later))),
        ]})
        before = int(time.time())
        self.collect()
        c1, c2 = self.row("c1"), self.row("c2")
        self.assertEqual((c1["five_hour"], c1["seven_day"], c1["source"]),
                         ({"used_percent": 10, "resets_at": later}, {"used_percent": 20, "resets_at": later},
                          "app-server"))
        self.assertGreaterEqual(c1["fetched_at"], before)
        self.assertEqual((c2["five_hour"], c2["seven_day"], c2["available"]),
                         (None, {"used_percent": 70, "resets_at": later}, True))
        for name in ("c1", "c2"):
            d = os.path.realpath(os.path.join(self.env.home, name))
            self.assertEqual(received(d)[0]["codex_home"], d)

    def test_probe_failure_cache_and_none(self):
        later = int(time.time()) + 3600
        ok = self.codex_account("ok", result=rate_limits(window(10, 300, later), window(20, 10080, later)))
        flaky = self.codex_account("flaky", result=rate_limits(window(30, 300, later), window(40, 10080, later)))
        self.env.write_accounts({"accounts": [ok, flaky]})
        self.collect()
        fetched = self.row("flaky")["fetched_at"]
        install_fake_codex(self.env, flaky["dir"], exit=1)
        self.codex_account("new", exit=1)
        self.env.write_accounts({"accounts": [ok, flaky, {"name": "new", "client": "codex",
                                                          "dir": os.path.join(self.env.home, "new")}]})
        r = self.collect()
        self.assertEqual([l for l in r.stderr.splitlines()],
                         ["agent-usage-monitor: codex flaky: app-server exited before replying",
                          "agent-usage-monitor: codex new: app-server exited before replying"])
        f, n = self.row("flaky"), self.row("new")
        self.assertEqual((f["source"], f["five_hour"]["used_percent"], f["fetched_at"]), ("cache", 30, fetched))
        self.assertEqual((n["source"], n["five_hour"], n["available"]),
                         ("none", {"used_percent": None, "resets_at": None}, None))
        self.assertEqual(self.row("ok")["source"], "app-server")
        # WDRC-98: the reason, without the log line's prefix
        self.assertEqual((f["error"], n["error"], self.row("ok")["error"]),
                         ("app-server exited before replying", "app-server exited before replying", None))

    def test_codex_error_each_kind(self):
        """WDRC-98: every ProbeError text becomes the row's error as is."""
        account = accounts.Account("c", "codex", "/d/c")
        for text in ("cannot start codex: ENOENT", "timed out after 10 s", "app-server exited before replying",
                     "app-server error -32600", "app-server error", "unrecognized output", "unrecognized reply",
                     "app-server i/o failed: EPIPE"):
            with self.subTest(text=text), mock.patch.object(codex, "probe", side_effect=codex.ProbeError(text)):
                self.assertEqual(cli._codex(account, {}), ({"error": text}, True, "agent-usage-monitor: codex c: " + text))

    def test_codex_error_cleared_on_success(self):
        later = int(time.time()) + 3600
        flaky = self.codex_account("flaky", exit=1)
        self.env.write_accounts({"accounts": [flaky]})
        self.collect()
        self.assertEqual(self.row("flaky")["error"], "app-server exited before replying")
        install_fake_codex(self.env, flaky["dir"], result=rate_limits(window(30, 300, later), window(40, 10080, later)))
        self.collect()
        row = self.row("flaky")
        self.assertEqual((row["error"], row["source"]), (None, "app-server"))

    def test_stuck_probes_hold_up_only_their_rows(self):
        later = int(time.time()) + 3600
        self.env.mkdir(".claude")
        install_fake_claude(self.env, hang=True)
        self.env.write_accounts({"accounts": [
            {"name": "claude", "client": "claude", "dir": "~/.claude"},
            self.codex_account("stuck", hang_on="account/rateLimits/read"),
            self.codex_account("ok", result=rate_limits(window(10, 300, later), window(20, 10080, later))),
        ]})
        start = time.monotonic()
        self.collect()
        self.assertLessEqual(time.monotonic() - start, 35)  # FR-14
        ok = self.row("ok")
        self.assertEqual((ok["source"], ok["five_hour"]["used_percent"], ok["seven_day"]["used_percent"]),
                         ("app-server", 10, 20))
        self.assertEqual((self.row("stuck")["source"], self.row("claude")["source"]), ("none", "none"))

    def test_account_files_untouched(self):
        later = int(time.time()) + 3600
        claude_dir = self.env.mkdir(".claude")
        other_dir = self.env.mkdir(".claude-a")
        install_fake_claude(self.env, stdout="Current session: 40% used · resets 3pm (UTC)\n"
                                             "Current week (all models): 10% used · resets Oct 24 at 1am (UTC)\n")
        codex = self.codex_account("codex", result=rate_limits(window(10, 300, later), window(20, 10080, later)))
        listing = self.env.write_accounts({"accounts": [{"name": "claude", "client": "claude", "dir": "~/.claude"},
                                                        {"name": "a", "client": "claude", "dir": "~/.claude-a"},
                                                        codex]})
        files = [listing]
        for d in (claude_dir, other_dir, codex["dir"]):
            for name in ("settings.json", "config.toml"):
                files.append(os.path.join(d, name))
                with open(files[-1], "w") as f:
                    f.write("{}")
                os.utime(files[-1], (1, 1))
        os.utime(listing, (1, 1))
        listings = [sorted(os.listdir(d)) for d in (claude_dir, other_dir)]
        self.collect()
        self.assertEqual([sorted(os.listdir(d)) for d in (claude_dir, other_dir)], listings)
        self.assertEqual((self.row("claude")["source"], self.row("a")["source"]), ("usage", "usage"))
        self.assertEqual(self.row("codex")["source"], "app-server")
        self.assertEqual([os.stat(p).st_mtime for p in files], [1] * len(files))  # FR-31

    def test_sigterm_stops_probes_and_writes_snapshot(self):
        later = int(time.time()) + 3600
        stuck = self.codex_account("stuck", spawn_child=True, ignore_term=True, hang_on="account/rateLimits/read")
        ok = self.codex_account("ok", result=rate_limits(window(10, 300, later), window(20, 10080, later)))
        self.env.write_accounts({"accounts": [stuck, ok]})
        proc = subprocess.Popen(["/usr/bin/python3", BIN, "collect"], env=self.env.environ,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(proc.kill)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            done = [os.path.exists(os.path.join(d["dir"], "received.jsonl"))
                    and received(d["dir"])[-1].get("method") == "account/rateLimits/read" for d in (stuck, ok)]
            if all(done) and len(pids(stuck["dir"])) == 2:
                break
            time.sleep(0.05)
        time.sleep(0.5)  # ok's reply is read
        start = time.monotonic()
        proc.send_signal(signal.SIGTERM)
        out, err = proc.communicate(timeout=5)
        self.assertLess(time.monotonic() - start, 3)
        self.assertEqual(proc.returncode, 143, err)
        self.assertEqual(out, b"")
        self.assertEqual(len(pids(stuck["dir"])), 2)
        self.assertTrue(reaped(*pids(stuck["dir"])))
        self.assertEqual((self.row("ok")["source"], self.row("ok")["five_hour"]["used_percent"]), ("app-server", 10))
        self.assertEqual(self.row("stuck")["source"], "none")

    def test_local_bin_appended_to_path(self):
        self.env.mkdir(".claude")
        install_fake_claude(self.env, stdout="Current session: 40% used · resets 3pm (UTC)\n"
                                             "Current week (all models): 10% used · resets Oct 24 at 1am (UTC)\n")
        local_bin = os.path.join(self.env.home, ".local", "bin")
        os.makedirs(local_bin)
        os.rename(os.path.join(self.env.fake_bin, "claude"), os.path.join(local_bin, "claude"))
        path = self.env.environ["PATH"]
        for env_path, seen in ((path, path + ":" + local_bin), (local_bin + ":" + path, local_bin + ":" + path)):
            with self.subTest(path=env_path):
                self.env.environ["PATH"] = env_path
                if os.path.exists(self.env.snapshot_path):
                    os.unlink(self.env.snapshot_path)
                self.collect()
                self.assertEqual(self.row("claude")["source"], "usage")
                self.assertEqual(claude_calls(self.env)[-1]["env"]["PATH"], seen)


class EmitAlertsTest(unittest.TestCase):
    """FR-8, Python side: alerts as `AUM-ALERT ` lines on stdout, recorded in notified (FR-1, FR-9) only once the
    host passes the delivered lines to `record-alerts` (TASK-640)."""

    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.cleanup)
        self.later = int(time.time()) + 3600
        d = os.path.join(self.env.home, "cx")
        install_fake_codex(self.env, d, result=rate_limits(window(92, 300, self.later), window(10, 10080, self.later)))
        self.env.write_accounts({"accounts": [{"name": "cx", "client": "codex", "dir": d}]})

    def alerts(self, r):
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = r.stdout.splitlines()
        for line in lines:
            self.assertTrue(line.startswith("AUM-ALERT "), line)
        return [json.loads(line[len("AUM-ALERT "):])["text"] for line in lines]

    def record(self, stdout):
        r = self.env.run("record-alerts", input=stdout)
        self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)
        return r

    def keys(self):
        return [(k["name"], k["window"], k["kind"], k["resets_at"]) for k in self.env.snapshot()["notified"]]

    def test_delivered_recorded_once(self):
        r = self.env.run("collect", "--emit-alerts")
        texts = self.alerts(r)
        self.assertEqual(len(texts), 1)
        self.assertIn("codex · cx 5h at 92%", texts[0])
        self.assertEqual(self.keys(), [], "not recorded before the host reports it sent")
        self.record("login shell noise\n" + r.stdout)
        self.assertEqual(self.keys(), [("cx", "five_hour", "full", self.later)])
        for _ in range(2):
            self.assertEqual(self.alerts(self.env.run("collect", "--emit-alerts")), [])

    def test_not_delivered_sent_again(self):
        first = self.alerts(self.env.run("collect", "--emit-alerts"))
        self.assertEqual(self.keys(), [])
        self.assertEqual(self.alerts(self.env.run("collect", "--emit-alerts")), first)

    def test_record_garbage_lines_skipped(self):
        self.env.run("collect")
        r = self.record("AUM-ALERT not json\nAUM-ALERT [1]\n")
        self.assertEqual(r.stderr.count("agent-usage-monitor: "), 2, r.stderr)
        self.assertEqual(self.keys(), [])

    def test_without_flag_stdout_empty_nothing_recorded(self):
        r = self.env.run("collect")
        self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)
        self.assertEqual(self.env.snapshot()["notified"], [])

    def test_two_collects_at_once_one_key(self):
        procs = [subprocess.Popen(["/usr/bin/python3", BIN, "collect", "--emit-alerts"], env=self.env.environ,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
        out = [p.communicate(timeout=60)[0] for p in procs]
        self.assertEqual([p.returncode for p in procs], [0, 0])
        self.assertEqual([len(o.splitlines()) for o in out], [1, 1], out)
        procs = [subprocess.Popen(["/usr/bin/python3", BIN, "record-alerts"], env=self.env.environ,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                 for _ in out]
        self.assertEqual([p.communicate(o, timeout=60)[0] for p, o in zip(procs, out)], ["", ""])
        self.assertEqual(len(self.env.snapshot()["notified"]), 1)

    def test_available_again_without_probing(self):
        self.env.mkdir(".claude")
        self.env.write_accounts({"accounts": [{"name": "claude-max", "client": "claude", "dir": "~/.claude"}]})
        self.env.run("collect")
        now = int(time.time())
        snap = self.env.snapshot()
        snap["accounts"][0].update(five_hour={"used_percent": 95, "resets_at": now - 60},
                                   seven_day={"used_percent": 10, "resets_at": now + 3600},
                                   fetched_at=now - 60, source="usage")
        snap["notified"] = [{"name": "claude-max", "window": "five_hour", "kind": "full", "resets_at": now - 60,
                             "sent_at": now - 3600}]
        with open(self.env.snapshot_path, "w") as f:
            json.dump(snap, f)
        install_fake_claude(self.env, fail=True)
        r = self.env.run("collect", "--emit-alerts")
        self.assertEqual(self.alerts(r), ["claude · claude-max available again"])
        self.assertEqual(claude_calls(self.env), [])
        self.assertEqual(len(self.env.snapshot()["notified"]), 1, "kept until delivered")
        self.record(r.stdout)
        self.assertEqual(self.env.snapshot()["notified"], [])


class SettingsCliTest(unittest.TestCase):
    """TASK-645: read-accounts and write-accounts, the settings window's way to accounts.json."""

    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.cleanup)

    def test_read_one_json_line(self):
        self.env.mkdir(".codex")
        r = self.env.run("read-accounts")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(r.stdout.splitlines()), 1)
        self.assertEqual([a["name"] for a in json.loads(r.stdout)["accounts"]], ["codex"])

    def test_write(self):
        self.env.mkdir("a")
        row = {"name": "a", "client": "codex", "dir": "~/a", "account": "", "original": "{}"}
        r = self.env.run("write-accounts", input=json.dumps({"threshold": 85, "accounts": [row], "original": "{}"}))
        self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)
        self.collect_reads_it()

        r = self.env.run("write-accounts", input=json.dumps(
            {"threshold": 85, "accounts": [row, dict(row, dir="~/nope")], "original": "{}"}))
        self.assertEqual(r.returncode, 1)
        problems = json.loads(r.stdout)["problems"]
        self.assertEqual([p["index"] for p in problems], [1])
        self.assertIn("duplicate", problems[0]["message"])

        for bad in ("", "[]", '{"threshold": 85}', '{"threshold": 85, "accounts": [{}], "original": "{}"}'):
            with self.subTest(bad=bad):
                r = self.env.run("write-accounts", input=bad)
                self.assertEqual(r.returncode, 2)
                self.assertIn("write-accounts", r.stderr)
        self.collect_reads_it()

    def collect_reads_it(self):
        install_fake_codex(self.env, os.path.join(self.env.home, "a"), result=rate_limits())
        r = self.env.run("collect")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.env.snapshot()["threshold"], 85)


if __name__ == "__main__":
    unittest.main()
