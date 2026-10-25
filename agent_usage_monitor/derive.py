"""Derived snapshot fields (FR-15 to FR-19), recomputed on every write."""

from agent_usage_monitor.accounts import CLIENTS

# window key -> length in minutes; the one home of window names
WINDOWS = {"five_hour": 300, "seven_day": 10080}
BY_MINUTES = {mins: key for key, mins in WINDOWS.items()}
STALE_AFTER = 6 * 3600


def reset_window(window, now):
    """FR-15: a window whose reset has passed restarted at 0%."""
    if window is not None and window["resets_at"] is not None and window["resets_at"] <= now:
        return {"used_percent": 0, "resets_at": None}
    return window


def availability(windows, threshold):
    """FR-16 over the windows the account has (None = absent, skipped)."""
    windows = [w for w in windows if w is not None]
    over = [w for w in windows if w["used_percent"] is not None and w["used_percent"] >= threshold]
    if over:
        times = [w["resets_at"] for w in over]
        return False, None if None in times else max(times)
    if windows and all(w["used_percent"] is not None for w in windows):
        return True, None
    return None, None


def order_key(row):
    """Grouped by client, CLIENTS order then alphabetical (user 2026-10-17, replaces FR-18)."""
    client = row["client"]
    return (CLIENTS.index(client) if client in CLIENTS else len(CLIENTS), client)


def recompute(snapshot, threshold, now):
    """Recompute every derived field in place; rows arrive in account-list order."""
    for row in snapshot["accounts"]:
        for key in WINDOWS:
            row[key] = reset_window(row[key], now)
        row["available"], row["available_at"] = availability([row[k] for k in WINDOWS], threshold)
        row["stale"] = row["fetched_at"] is not None and now - row["fetched_at"] > STALE_AFTER
    snapshot["accounts"].sort(key=order_key)
    waiting = [r for r in snapshot["accounts"] if r["available"] is False and r["available_at"] is not None]
    first = min(waiting, key=lambda r: r["available_at"], default=None)
    snapshot["summary"] = {
        "available": [r["name"] for r in snapshot["accounts"] if r["available"] is True],
        "next": {"name": first["name"], "at": first["available_at"]} if first else None,
    }
    snapshot["generated_at"] = now
    snapshot["threshold"] = threshold
