import gc
import json
import os
import time
import unittest
import warnings

from agent_usage_monitor import codex
from tests.helpers import (FIXTURES, Env, install_fake_codex, pids, rate_limits, reaped, received,
                           window)


def fixture_lines():
    with open(os.path.join(FIXTURES, "codex-app-server", "rate-limits-read.jsonl")) as f:
        return [l.rstrip("\n") for l in f]


class ParseTest(unittest.TestCase):
    def test_real_fixture(self):
        result = json.loads(fixture_lines()[2])["result"]
        self.assertEqual(codex.parse_rate_limits(result), {
            "five_hour": None, "seven_day": {"used_percent": 87, "resets_at": 1792772261}})

    def test_map_by_duration(self):
        r = rate_limits(window(70, 10080, 2000), window(20, 300, 1000))
        self.assertEqual(codex.parse_rate_limits(r), {
            "five_hour": {"used_percent": 20, "resets_at": 1000},
            "seven_day": {"used_percent": 70, "resets_at": 2000}})
        r = rate_limits(window(20, 300, None))
        self.assertEqual(codex.parse_rate_limits(r), {
            "five_hour": {"used_percent": 20, "resets_at": None}, "seven_day": None})

    def test_unrecognized(self):
        for bad in (None, [], {}, {"rateLimits": None}, {"rateLimits": []},
                    rate_limits(), rate_limits("x"),
                    rate_limits({"windowDurationMins": 300, "resetsAt": 1}),
                    rate_limits(window("5", 300)), rate_limits(window(True, 300)),
                    rate_limits(window(5, 300, "soon")),
                    rate_limits(window(5, 60, 1)), rate_limits(window(5, None, 1)),
                    rate_limits(window(5, 300, 1), window(9, 600, 1))):
            with self.subTest(bad=bad), self.assertRaises(codex.ProbeError) as cm:
                codex.parse_rate_limits(bad)
            self.assertEqual(str(cm.exception), "unrecognized reply")

    def test_duplicate_duration(self):
        with self.assertRaises(codex.ProbeError):
            codex.parse_rate_limits(rate_limits(window(5, 300, 1), window(9, 300, 2)))


class ProbeTest(unittest.TestCase):
    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.cleanup)
        self.home = os.path.join(self.env.home, ".codex")

    def probe(self, timeout=10.0):
        return codex.probe(self.home, self.env.environ, timeout=timeout)

    def assert_fails(self, needle, timeout=10.0):
        with self.assertRaises(codex.ProbeError) as cm:
            self.probe(timeout)
        self.assertIn(needle, str(cm.exception))
        self.assertNotIn("\n", str(cm.exception))
        return cm.exception

    def assert_no_leftovers(self):
        self.assertTrue(reaped(*pids(self.home)), pids(self.home))

    def test_success_and_messages(self):
        install_fake_codex(self.env, self.home, result=rate_limits(window(10, 300, 5), window(40, 10080, 9)))
        self.assertEqual(self.probe(), {"five_hour": {"used_percent": 10, "resets_at": 5},
                                        "seven_day": {"used_percent": 40, "resets_at": 9}})
        msgs = received(self.home)
        self.assertEqual(msgs[0], {"argv": ["app-server"], "codex_home": self.home})
        self.assertEqual([m.get("method") for m in msgs[1:]],
                         ["initialize", "initialized", "account/rateLimits/read"])
        self.assertEqual(msgs[1]["params"]["clientInfo"]["name"], "agent-usage-monitor")
        self.assertIn("version", msgs[1]["params"]["clientInfo"])
        self.assertNotIn("id", msgs[2])
        self.assert_no_leftovers()

    def test_real_fixture_replay(self):
        lines = fixture_lines()
        install_fake_codex(self.env, self.home, responses={
            "initialize": [lines[0]], "account/rateLimits/read": [lines[1], lines[2]]})
        self.assertEqual(self.probe()["seven_day"], {"used_percent": 87, "resets_at": 1792772261})

    def test_skips_notifications(self):
        install_fake_codex(self.env, self.home, responses={
            "initialize": [{"method": "note"}, {"id": 99, "result": {}}, {"id": "$id", "result": {}}],
            "account/rateLimits/read": [
                {"id": "$id", "method": "server/request", "params": {}},
                {"method": "account/rateLimits/updated", "params": {}},
                dict(id="$id", result=rate_limits(window(1, 300, 1)))]})
        self.assertEqual(self.probe()["five_hour"], {"used_percent": 1, "resets_at": 1})

    def test_no_leftover_processes(self):
        install_fake_codex(self.env, self.home, spawn_child=True, ignore_term=True,
                           hang_on="account/rateLimits/read")
        started = time.monotonic()
        self.assert_fails("timed out", timeout=1)
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(len(pids(self.home)), 2)
        self.assert_no_leftovers()

    def test_success_with_child_leaves_none(self):
        install_fake_codex(self.env, self.home, spawn_child=True, ignore_term=True,
                           result=rate_limits(window(1, 300, 1)))
        self.probe()
        self.assert_no_leftovers()

    def test_pipes_closed(self):
        for cfg in ({"result": rate_limits(window(1, 300, 1))}, {"hang_on": "initialize"}):
            with self.subTest(cfg=cfg), warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", ResourceWarning)
                install_fake_codex(self.env, self.home, **cfg)
                try:
                    self.probe(timeout=1)
                except codex.ProbeError:
                    pass
                gc.collect()
                self.assertEqual([w for w in caught if issubclass(w.category, ResourceWarning)], [])

    def test_timeout(self):
        install_fake_codex(self.env, self.home, hang_on="initialize")
        self.assert_fails("timed out", timeout=1)
        self.assert_no_leftovers()

    def test_not_found(self):
        self.assert_fails("cannot start codex")

    def test_not_executable(self):
        install_fake_codex(self.env, self.home)
        os.chmod(os.path.join(self.env.fake_bin, "codex"), 0o644)
        self.assert_fails("cannot start codex")

    def test_exit1_before_read(self):
        install_fake_codex(self.env, self.home, exit=1)
        self.assert_fails("app-server")

    def test_exit1_after_initialize(self):
        install_fake_codex(self.env, self.home, exit_after="initialized")
        self.assert_fails("app-server")

    def test_error_response(self):
        install_fake_codex(self.env, self.home, responses={"account/rateLimits/read": [
            {"id": "$id", "error": {"code": -32600, "message": "user@example.com secret"}}]})
        e = self.assert_fails("app-server error -32600")
        self.assertNotIn("example.com", str(e))
        install_fake_codex(self.env, self.home, responses={"account/rateLimits/read": [
            {"id": "$id", "error": {"code": "user@example.com\nx"}}]})
        e = self.assert_fails("app-server error")
        self.assertEqual(str(e), "app-server error")

    def test_non_json(self):
        install_fake_codex(self.env, self.home, responses={"initialize": ["not json"]})
        self.assert_fails("unrecognized output")
        install_fake_codex(self.env, self.home, responses={"initialize": ["[1, 2]"]})
        self.assert_fails("unrecognized output")

    def test_deeply_nested(self):
        install_fake_codex(self.env, self.home, responses={"initialize": ["[" * 200000]})
        self.assert_fails("unrecognized output")

    def test_long_line(self):
        install_fake_codex(self.env, self.home, responses={"initialize": ["x" * (codex.MAX_LINE + 10)]})
        self.assert_fails("unrecognized output")

    def test_unrecognized_reply(self):
        install_fake_codex(self.env, self.home, result={"nothing": 1})
        self.assert_fails("unrecognized reply")


if __name__ == "__main__":
    unittest.main()
