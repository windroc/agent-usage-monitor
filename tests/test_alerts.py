import json
import os
import re
import time
import unittest

from agent_usage_monitor import alerts, store
from agent_usage_monitor.accounts import Account
from tests.helpers import Env

DAY = 86400
H = 3600
# a local 12:00, so +/- a few hours stays on the same local date
NOW = int(time.mktime((2026, 10, 14, 12, 0, 0, 0, 0, -1)))
PATH = re.compile(r"(^|\s)/\S")


def w(pct, at=None):
    return {"used_percent": pct, "resets_at": at}


def clock(t):
    return time.strftime("%H:%M", time.localtime(t))


class AlertsTest(unittest.TestCase):
    def setUp(self):
        self.env = Env()
        self.addCleanup(self.env.cleanup)
        self.accounts = [Account("claude-max", "claude", "/d/max", "you@example.com"), Account("cx", "codex", "/d/cx")]

    def write(self, updates=None, now=NOW, threshold=90, emit=True, accounts=None, delivered=True):
        """One collect; the host hands every alert to macOS unless delivered is False. Returns the texts."""
        sent = []
        store.write(self.env.state, self.accounts if accounts is None else accounts, threshold, updates or {},
                    now=now, emit=sent.append if emit else None)
        if delivered and sent:
            self.assertEqual(store.record(self.env.state, sent), [])
        return [a["text"] for a in sent]

    def notified(self):
        return self.env.snapshot()["notified"]

    def full(self, name, window, resets_at, sent_at=NOW):
        return {"name": name, "window": window, "kind": "full", "resets_at": resets_at, "sent_at": sent_at}

    def seed(self, rows, notified):
        """Write rows, then replace notified as an earlier run would have left it."""
        self.write(rows, emit=False)
        snap = self.env.snapshot()
        snap["notified"] = notified
        with open(self.env.snapshot_path, "w") as f:
            json.dump(snap, f)

    def test_near_full_once(self):
        sent = self.write({"cx": {"five_hour": w(92, NOW + H), "seven_day": w(10, NOW + DAY)}})
        self.assertEqual(sent, ["codex · cx 5h at 92%%, resets %s" % clock(NOW + H)])
        self.assertEqual(self.notified(), [self.full("cx", "five_hour", NOW + H)])
        self.assertEqual(self.env.snapshot()["schema"], 1)

    def test_below_threshold_none(self):
        self.assertEqual(self.write({"cx": {"five_hour": w(85, NOW + H), "seven_day": w(10, NOW + DAY)}}), [])
        self.assertEqual(self.notified(), [])

    def test_threshold_from_list(self):
        sent = self.write({"cx": {"five_hour": w(85, NOW + H)}}, threshold=80)
        self.assertEqual(len(sent), 1)
        self.assertIn("5h at 85%", sent[0])

    def test_upgrade_snapshot_without_notified(self):
        self.write({"cx": {"five_hour": w(92, NOW + H)}}, emit=False)
        snap = self.env.snapshot()
        del snap["notified"]
        with open(self.env.snapshot_path, "w") as f:
            json.dump(snap, f)
        self.assertEqual(len(self.write()), 1, "already over threshold before the upgrade")

    def test_resets_at_jitter_dedupes(self):
        self.write({"cx": {"five_hour": w(92, NOW + H)}})
        self.assertEqual(self.write({"cx": {"five_hour": w(93, NOW + H + 60)}}, now=NOW + 300), [])
        self.assertEqual(self.write({"cx": {"five_hour": w(93, NOW + H + 660)}}, now=NOW + 600),
                         ["codex · cx 5h at 93%%, resets %s" % clock(NOW + H + 660)], "11 min later is a new reset")

    def test_null_resets_at_dedupes_and_text(self):
        self.assertEqual(self.write({"cx": {"seven_day": w(95)}}), ["codex · cx 7d at 95%, reset time unknown"])
        self.assertEqual(self.write(), [])
        self.assertEqual(self.notified(), [self.full("cx", "seven_day", None)])

    def test_three_runs_one_alert(self):
        total = []
        for i in range(3):
            total += self.write({"cx": {"five_hour": w(92, NOW + H)}}, now=NOW + i * 300)
        self.assertEqual(len(total), 1)
        self.assertEqual(len(self.notified()), 1)

    def test_account_label(self):
        sent = self.write({"claude-max": {"five_hour": w(90, NOW + H)}})
        self.assertEqual(sent, ["claude · you@example.com 5h at 90%%, resets %s" % clock(NOW + H)])

    def test_quote_in_name_verbatim(self):
        sent = self.write({'a"b': {"five_hour": w(99, NOW + H)}}, accounts=[Account('a"b', "codex", "/d/q")])
        self.assertEqual(sent[0].split(" 5h")[0], 'codex · a"b')

    def test_other_day_reset_format(self):
        friday = NOW + 2 * DAY - 3 * H
        sent = self.write({"cx": {"seven_day": w(91, friday)}})
        self.assertEqual(sent, ["codex · cx 7d at 91%%, resets Oct 16 %s" % clock(friday)])

    def test_month_names_english(self):
        for month, name in ((1, "Jan"), (5, "May"), (12, "Dec")):
            at = int(time.mktime((2027, month, 3, 6, 0, 0, 0, 0, -1)))
            self.assertEqual(alerts._reset_text(at, NOW), "resets %s 3 06:00" % name)

    def test_upgrade_keeps_sent_alerts(self):
        """TASK-880: a key recorded before the English texts still dedupes, so an upgrade re-sends nothing."""
        self.seed({"cx": {"five_hour": w(92, NOW + H)}}, [self.full("cx", "five_hour", NOW + H)])
        self.assertEqual(self.write(), [])
        self.assertEqual(self.notified(), [self.full("cx", "five_hour", NOW + H)])

    def test_available_again_after_both_resets(self):
        five = NOW + 5 * H                   # "17:00"
        seven = NOW + 3 * DAY                # "Friday 09:00"
        self.write({"claude-max": {"five_hour": w(95, five), "seven_day": w(92, seven)}})
        self.assertEqual(len(self.notified()), 2)
        # 17:01: 5h reset, still blocked by 7d
        self.assertEqual(self.write(now=five + 60), [])
        self.assertEqual(len(self.notified()), 2)
        # Friday 09:01: both reset, available
        self.assertEqual(self.write(now=seven + 60), ["claude · you@example.com available again"])
        self.assertEqual(self.notified(), [])
        self.assertEqual(self.write(now=seven + 120), [])

    def test_available_again_null_reset_below_threshold(self):
        self.write({"cx": {"five_hour": w(95), "seven_day": w(10, NOW + DAY)}})
        self.assertEqual(self.write({"cx": {"five_hour": w(96)}}), [], "still full")
        self.assertEqual(self.write({"cx": {"five_hour": w(40)}}), ["codex · cx available again"])
        self.assertEqual(self.notified(), [])

    def test_available_again_after_early_reset(self):
        """WDRC-91: Codex reset its 7d window days before the resets_at in the key."""
        def at(day, hh, mm):
            return int(time.mktime((2026, 10, day, hh, mm, 0, 0, 0, -1)))
        sent = self.write({"cx": {"five_hour": None, "seven_day": w(95, at(24, 20, 22))}}, now=at(18, 8, 13))
        self.assertEqual(sent, ["codex · cx 7d at 95%, resets Oct 24 20:22"])
        self.assertEqual(self.write({"cx": {"seven_day": w(11, at(29, 13, 38))}}, now=at(22, 21, 38)),
                         ["codex · cx available again"])
        self.assertEqual(self.notified(), [])
        self.assertEqual(self.write({"cx": {"seven_day": w(36, at(30, 13, 43))}}, now=at(24, 20, 23)), [])
        self.assertEqual(self.write({"cx": {"seven_day": w(92, at(30, 13, 43))}}, now=at(25, 9, 0)),
                         ["codex · cx 7d at 92%, resets Oct 30 13:43"], "the new window can still fill up")

    def test_available_again_below_threshold_before_reset(self):
        self.write({"cx": {"five_hour": None, "seven_day": w(95, NOW + DAY)}})
        self.assertEqual(self.write({"cx": {"seven_day": w(40, NOW + DAY + 60)}}, now=NOW + H),
                         ["codex · cx available again"])
        self.assertEqual(self.notified(), [])

    def test_early_reset_while_not_available_no_alert(self):
        self.write({"cx": {"five_hour": w(10, NOW + H), "seven_day": w(95, NOW + DAY)}})
        self.assertEqual(self.write({"cx": {"five_hour": w(97, NOW + 2 * H), "seven_day": w(5, NOW + 7 * DAY)}},
                                    now=NOW + 300), ["codex · cx 5h at 97%%, resets %s" % clock(NOW + 2 * H)])
        self.assertEqual(len(self.notified()), 2, "the 7d key is kept while 5h blocks")
        self.assertEqual(self.write({"cx": {"five_hour": w(10, NOW + 7 * H)}}, now=NOW + 2 * H + 60),
                         ["codex · cx available again"])
        self.assertEqual(self.notified(), [])

    def test_window_no_longer_reported_ends_at_stored_reset(self):
        self.write({"cx": {"five_hour": w(95, NOW + H), "seven_day": w(10, NOW + DAY)}})
        self.assertEqual(self.write({"cx": {"five_hour": None}}, now=NOW + 300), [])
        self.assertEqual(len(self.notified()), 1)
        self.assertEqual(self.write(now=NOW + H + 60), ["codex · cx available again"])
        self.assertEqual(self.notified(), [])

    def test_not_available_unknown_no_alert(self):
        self.write({"cx": {"five_hour": w(95, NOW + H), "seven_day": w(None)}})
        # 5h reset passed, 7d unknown: availability None, not True
        self.assertEqual(self.write(now=NOW + H + 60), [])
        self.assertEqual(len(self.notified()), 1)

    def test_available_again_after_sleep_past_7_days(self):
        sent = NOW - 7 * DAY - H
        self.seed({"claude-max": {"five_hour": w(10, NOW + H), "seven_day": w(30, NOW + 6 * DAY)}},
                  [self.full("claude-max", "seven_day", sent + 6 * DAY, sent)])
        # asleep from before the 7d reset until after the key turned 7 days old
        self.assertEqual(self.write(), ["claude · you@example.com available again"])
        self.assertEqual(self.notified(), [])

    def test_prune_after_7_days(self):
        self.seed({"cx": {"five_hour": w(10, NOW + H)}}, [
            self.full("old", "five_hour", None, NOW - 8 * DAY), self.full("cx", "seven_day", None, NOW - 6 * DAY)])
        self.write()
        self.assertEqual(self.notified(), [self.full("cx", "seven_day", None, NOW - 6 * DAY)])

    def test_garbage_notified_sanitized(self):
        for garbage in ("x", [1, {"name": 2}, {"name": "cx"}], None):
            self.seed({"cx": {"five_hour": w(92, NOW + H)}}, garbage)
            self.assertEqual(len(self.write()), 1, garbage)

    def test_not_delivered_not_recorded_resent(self):
        updates = {"cx": {"five_hour": w(92, NOW + H)}}
        self.assertEqual(len(self.write(updates, delivered=False)), 1)
        self.assertEqual(self.notified(), [])
        self.assertEqual(len(self.write(now=NOW + 300)), 1, "sent again")
        self.assertEqual(self.notified(), [self.full("cx", "five_hour", NOW + H, NOW + 300)])
        self.assertEqual(self.write(now=NOW + 600), [])
        self.assertEqual(self.write(now=NOW + 900), [])

    def test_available_again_not_delivered_keeps_keys(self):
        key = self.full("cx", "five_hour", NOW - 60, NOW - 8 * DAY)
        self.seed({"cx": {"five_hour": w(10, NOW + H), "seven_day": w(10, NOW + DAY)}}, [key])
        self.assertEqual(self.write(delivered=False), ["codex · cx available again"])
        self.assertEqual(self.notified(), [key], "kept, though older than 7 days")
        self.assertEqual(self.write(), ["codex · cx available again"])
        self.assertEqual(self.notified(), [])

    def test_record_dedupes_and_ignores_unknown_keys(self):
        sent = []
        store.write(self.env.state, self.accounts, 90, {"cx": {"five_hour": w(92, NOW + H)}}, now=NOW, emit=sent.append)
        self.assertEqual(store.record(self.env.state, sent + sent), [])
        self.assertEqual(self.notified(), [self.full("cx", "five_hour", NOW + H)])
        store.record(self.env.state, [dict(sent[0], add=[dict(sent[0]["add"][0], resets_at=NOW + H + 60, sent_at=NOW + 1)])])
        self.assertEqual(len(self.notified()), 1, "same reset within 10 minutes")
        store.record(self.env.state, [{"text": "x", "add": [{"name": "cx"}, "s"], "remove": "x"}, {"text": "y"}, "z"])
        self.assertEqual(self.notified(), [self.full("cx", "five_hour", NOW + H)])

    def test_record_without_snapshot(self):
        lines = store.record(self.env.state, [{"text": "x", "add": [self.full("cx", "five_hour", None)], "remove": []}])
        self.assertEqual(len(lines), 1)
        self.assertIn("not recorded", lines[0])
        self.assertFalse(os.path.exists(self.env.snapshot_path))

    def test_without_emit_no_evaluation(self):
        self.assertEqual(self.write({"cx": {"five_hour": w(92, NOW + H)}}, emit=False), [])
        self.assertEqual(self.notified(), [])
        old = self.full("cx", "seven_day", None, NOW - 8 * DAY)
        self.seed({}, [old])
        self.write(emit=False)
        self.assertEqual(self.notified(), [old], "kept as is")

    def test_no_paths_in_texts(self):
        texts = self.write({"cx": {"five_hour": w(95), "seven_day": w(10, NOW + DAY)}, "claude-max": {"seven_day": w(99, NOW + DAY)}})
        texts += self.write({"cx": {"five_hour": w(10)}})
        self.assertEqual(len(texts), 3)
        for t in texts:
            self.assertIsNone(PATH.search(t), t)
            self.assertNotIn("/d/", t)


class KeysTest(unittest.TestCase):
    def test_keys(self):
        good = {"name": "a", "window": "five_hour", "kind": "full", "resets_at": None, "sent_at": 1}
        self.assertEqual(alerts.keys([good, dict(good, sent_at="1"), dict(good, window="x"), dict(good, resets_at=True),
                                      dict(good, name=None), "s"]), [good])
        self.assertEqual(alerts.keys({"a": 1}), [])


if __name__ == "__main__":
    unittest.main()
