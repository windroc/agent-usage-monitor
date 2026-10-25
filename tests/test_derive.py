import unittest

from agent_usage_monitor import derive

NOW = 1792130400
H = 3600


def w(pct, at=None):
    return {"used_percent": pct, "resets_at": at}


UNKNOWN = object()


def row(name, five=UNKNOWN, seven=UNKNOWN, fetched=NOW, source="app-server", client="codex"):
    return {"name": name, "client": client, "dir": "/d/" + name,
            "five_hour": w(None) if five is UNKNOWN else five,
            "seven_day": w(None) if seven is UNKNOWN else seven,
            "fetched_at": fetched, "source": source}


def run(*rows, threshold=90, now=NOW):
    snap = {"accounts": list(rows)}
    derive.recompute(snap, threshold, now)
    return snap


class WindowsTest(unittest.TestCase):
    def test_by_minutes_inverts_windows(self):
        self.assertEqual(derive.BY_MINUTES, {300: "five_hour", 10080: "seven_day"})


class ResetTest(unittest.TestCase):
    def test_passed_reset_zeroes(self):
        r = run(row("a", w(93, NOW - 1), w(10, NOW)))["accounts"][0]
        self.assertEqual(r["five_hour"], w(0))
        self.assertEqual(r["seven_day"], w(0), "resets_at == now counts as passed")

    def test_unknown_with_passed_reset_zeroes(self):
        r = run(row("a", w(None, NOW - 1), w(10, NOW + H)))["accounts"][0]
        self.assertEqual(r["five_hour"], w(0))
        self.assertIs(r["available"], True)

    def test_null_reset_kept(self):
        r = run(row("a", w(50), w(10, NOW + H)))["accounts"][0]
        self.assertEqual(r["five_hour"], w(50))
        self.assertEqual(r["seven_day"], w(10, NOW + H))

    def test_absent_window_unchanged(self):
        r = run(row("a", None, w(10, NOW + H)))["accounts"][0]
        self.assertIsNone(r["five_hour"])


class AvailableTest(unittest.TestCase):
    def verdict(self, five, seven, threshold=90):
        r = run(row("a", five, seven), threshold=threshold)["accounts"][0]
        return r["available"], r["available_at"]

    def test_cases(self):
        at17, at18, fri9 = NOW + H, NOW + 2 * H, NOW + 3 * 24 * H
        self.assertEqual(self.verdict(w(42, at17), w(61, fri9)), (True, None))
        self.assertEqual(self.verdict(w(93, at17), w(70, fri9)), (False, at17))
        self.assertEqual(self.verdict(w(95, at18), w(92, fri9)), (False, fri9))
        self.assertEqual(self.verdict(w(90, at17), w(10, fri9)), (False, at17))
        self.assertEqual(self.verdict(w(95), w(10, fri9)), (False, None))
        self.assertEqual(self.verdict(w(95, at17), w(92)), (False, None))
        self.assertEqual(self.verdict(w(None), w(None)), (None, None))
        self.assertEqual(self.verdict(w(None), w(10, fri9)), (None, None))
        self.assertEqual(self.verdict(w(None), w(95, fri9)), (False, fri9))

    def test_threshold_80(self):
        self.assertEqual(self.verdict(w(85, NOW + H), w(10, NOW + H), threshold=80), (False, NOW + H))
        self.assertEqual(self.verdict(w(79, NOW + H), w(10, NOW + H), threshold=80), (True, None))

    def test_absent_windows(self):
        fri = NOW + 3 * 24 * H
        self.assertEqual(self.verdict(None, w(87, fri)), (True, None))
        self.assertEqual(self.verdict(None, w(95, fri)), (False, fri))
        self.assertEqual(self.verdict(w(95, NOW + H), None), (False, NOW + H))
        self.assertEqual(self.verdict(None, w(None)), (None, None))

    def test_both_absent(self):
        r = run(row("a", None, None))["accounts"][0]
        self.assertEqual((r["available"], r["available_at"]), (None, None))


class SummaryTest(unittest.TestCase):
    def test_prd_sample(self):
        at17 = NOW + H
        snap = run(row("claude", w(42, at17), w(61, at17)),
                   row("claude-work", w(0, at17), w(20, at17)),
                   row("codex", w(15, at17), w(33, at17)),
                   row("claude-max", w(93, at17), w(70, NOW + 9 * H)))
        self.assertEqual(snap["summary"], {"available": ["claude", "claude-work", "codex"],
                                           "next": {"name": "claude-max", "at": at17}})

    def test_none_available(self):
        snap = run(row("a", w(95), w(1)), row("b", w(95), w(1)))
        self.assertEqual(snap["summary"], {"available": [], "next": None})

    def test_tie_takes_earlier(self):
        snap = run(row("a", w(95, NOW + H), w(1)), row("b", w(95, NOW + H), w(1)))
        self.assertEqual(snap["summary"]["next"], {"name": "a", "at": NOW + H})


class OrderTest(unittest.TestCase):
    def test_client_groups_keep_list_order(self):
        # user 2026-10-17: replaces FR-18's order by availability
        snap = run(row("A", w(95, NOW + H), w(1)),
                   row("B", client="claude"),
                   row("C", w(1), w(1), client="gemini"),
                   row("D", w(1), w(1)),
                   row("E", w(95, NOW + H), w(1), client="claude"),
                   row("F", w(1), w(1), client="claude"),
                   row("G", client="aider"))
        self.assertEqual([r["name"] for r in snap["accounts"]], ["B", "E", "F", "A", "D", "G", "C"])

    def test_next_is_earliest_whatever_the_order(self):
        snap = run(row("A", w(95, NOW + 2 * H), w(1), client="claude"),
                   row("B", w(95, NOW + H), w(1)))
        self.assertEqual(snap["summary"]["next"], {"name": "B", "at": NOW + H})


class StaleTest(unittest.TestCase):
    def stale(self, fetched):
        return run(row("a", fetched=fetched))["accounts"][0]["stale"]

    def test_cases(self):
        self.assertIs(self.stale(NOW - 7 * H), True)
        self.assertIs(self.stale(NOW - 5 * H), False)
        self.assertIs(self.stale(NOW - 6 * H), False)
        self.assertIs(self.stale(NOW - 6 * H - 1), True)
        self.assertIs(self.stale(None), False)


class TopLevelTest(unittest.TestCase):
    def test_generated_at_and_threshold(self):
        snap = run(threshold=80)
        self.assertEqual(snap["generated_at"], NOW)
        self.assertEqual(snap["threshold"], 80)
        self.assertEqual(snap["summary"], {"available": [], "next": None})


if __name__ == "__main__":
    unittest.main()
