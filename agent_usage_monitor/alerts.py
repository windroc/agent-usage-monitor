"""M2 alerts (FR-1 to FR-3, FR-9): decided from the snapshot inside store.write, deduped in its `notified`.

An alert is {"text", "add": [key], "remove": [key]}: the `notified` change that `apply` makes once the host has
handed it to macOS (TASK-640); until then nothing is recorded, so the next collect decides it again.
"""

import time

from agent_usage_monitor import derive

LABELS = {"five_hour": "5h", "seven_day": "7d"}
SAME_RESET = 600
KEEP = 7 * 86400
# not %b: that follows the locale
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _int_or_none(v):
    return v is None or (isinstance(v, int) and not isinstance(v, bool))


def _valid(key):
    return (isinstance(key, dict) and isinstance(key.get("name"), str) and key.get("window") in derive.WINDOWS
            and key.get("kind") == "full" and "resets_at" in key and _int_or_none(key["resets_at"])
            and isinstance(key.get("sent_at"), int) and not isinstance(key["sent_at"], bool))


def keys(value):
    """`notified` as read, without entries this version cannot use."""
    return [k for k in value if _valid(k)] if isinstance(value, list) else []


def _same_reset(a, b):
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) < SAME_RESET


def _reset_text(at, now):
    if at is None:
        return "reset time unknown"
    t, today = time.localtime(at), time.localtime(now)
    day = "" if t[:3] == today[:3] else "%s %d " % (MONTHS[t.tm_mon - 1], t.tm_mday)
    return "resets %s%s" % (day, time.strftime("%H:%M", t))


def evaluate(snap, threshold, now):
    """Return this run's alerts, in row order; snap["notified"] is only pruned."""
    notified = keys(snap.get("notified"))
    found = []
    for row in snap["accounts"]:
        label = "%s · %s" % (row["client"], row.get("account") or row["name"])
        mine = [k for k in notified if k["name"] == row["name"]]

        def ended(k):
            # WDRC-91: a provider may reset a window before the resets_at in the key
            w = row.get(k["window"])
            if w is not None and (not _same_reset(k["resets_at"], w["resets_at"])
                                  or w["used_percent"] is not None and w["used_percent"] < threshold):
                return True
            return k["resets_at"] is not None and k["resets_at"] <= now

        done = [k for k in mine if ended(k)]
        if row["available"] is True and done:
            found.append({"text": "%s available again" % label, "add": [], "remove": done})
            mine = [k for k in mine if k not in done]
        for window in derive.WINDOWS:
            w = row.get(window)
            if w is None or w["used_percent"] is None or w["used_percent"] < threshold:
                continue
            if any(k["window"] == window and _same_reset(k["resets_at"], w["resets_at"]) for k in mine):
                continue
            key = {"name": row["name"], "window": window, "kind": "full", "resets_at": w["resets_at"], "sent_at": now}
            found.append({"text": "%s %s at %d%%, %s" % (label, LABELS[window], w["used_percent"],
                                                      _reset_text(w["resets_at"], now)), "add": [key], "remove": []})
    # a key older than 7 days still ends in its available-again alert (Mac asleep that long), until it is delivered
    removing = [k for a in found for k in a["remove"]]
    snap["notified"] = [k for k in notified if now - k["sent_at"] <= KEEP or k in removing]
    return found


def apply(notified, sent):
    """notified after the alerts in `sent` (as parsed back from the host) were handed to macOS."""
    for alert in sent:
        remove = keys(alert.get("remove"))
        notified = [k for k in notified if k not in remove]
        for key in keys(alert.get("add")):
            if not any(k["name"] == key["name"] and k["window"] == key["window"]
                       and _same_reset(k["resets_at"], key["resets_at"]) for k in notified):
                notified.append(key)
    return notified
