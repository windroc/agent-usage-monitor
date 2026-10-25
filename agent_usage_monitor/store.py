"""Snapshot store (FR-5 to FR-7): the one module that writes snapshot.json."""

import contextlib
import fcntl
import json
import os
import tempfile
import time

from agent_usage_monitor import alerts, derive
from agent_usage_monitor.accounts import home

SCHEMA = 1


def state_dir(environ):
    return environ.get("AGENT_USAGE_MONITOR_STATE_DIR") or os.path.join(home(environ), ".local", "state", "agent-usage-monitor")


def default_row():
    row = {"available": None, "available_at": None}
    row.update({k: {"used_percent": None, "resets_at": None} for k in derive.WINDOWS})
    row.update(fetched_at=None, source="none", stale=False, usage_disabled_version=None, needs_login=False)
    return row


def _int_or_none(v):
    return v is None or (isinstance(v, int) and not isinstance(v, bool))


def _valid_window(w):
    return w is None or (isinstance(w, dict) and "used_percent" in w and "resets_at" in w
                         and _int_or_none(w["used_percent"]) and _int_or_none(w["resets_at"]))


def _valid(snap):
    if not isinstance(snap, dict) or not isinstance(snap.get("accounts"), list):
        return False
    for row in snap["accounts"]:
        if not isinstance(row, dict) or not isinstance(row.get("name"), str):
            return False
        if not all(_valid_window(row[k]) for k in derive.WINDOWS if k in row):
            return False
        if not _int_or_none(row.get("fetched_at")):
            return False
    return True


def read(path):
    """Return (snapshot or None, warning line or None); a missing file is silently empty."""
    try:
        with open(path, encoding="utf-8") as f:
            snap = json.load(f)
    except FileNotFoundError:
        return None, None
    except (OSError, ValueError, RecursionError) as e:
        return None, "agent-usage-monitor: snapshot %s unreadable, starting empty: %s" % (path, e)
    if not _valid(snap):
        return None, "agent-usage-monitor: snapshot %s unreadable, starting empty: unexpected structure" % path
    return snap, None


def snapshot_path(directory):
    return os.path.join(directory, "snapshot.json")


def ensure_dir(directory):
    if not os.path.isdir(directory):
        os.makedirs(directory, mode=0o700, exist_ok=True)
        os.chmod(directory, 0o700)


@contextlib.contextmanager
def _locked(directory):
    ensure_dir(directory)
    lock = os.open(os.path.join(directory, "snapshot.lock"), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield
    finally:
        os.close(lock)


def _replace(directory, snap):
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".snapshot.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(snap, indent=1))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, snapshot_path(directory))
    except BaseException:
        os.unlink(tmp)
        raise


def write(directory, accounts, threshold, updates, failed=(), now=None, emit=None):
    """Merge one writer's updates into the snapshot under the lock; return warning lines.

    updates: {name: {field: value}} collected this run; failed: names whose values this run keeps
    from the snapshot (probe failed or skipped). emit: called with each alert (alerts.evaluate) once the
    snapshot is written, still under the lock (FR-1); recorded only by a later `record`. None decides no alerts.
    """
    path = snapshot_path(directory)
    with _locked(directory):
        old, warning = read(path)
        snap = old or {}
        previous = {row["name"]: row for row in snap.get("accounts", [])}
        rows = []
        for account in accounts:
            row = default_row()
            row.update(previous.get(account.name, {}))
            row.update(name=account.name, client=account.client, dir=account.dir, account=account.account)
            row.update(updates.get(account.name, {}))
            if account.name in failed:
                if row["fetched_at"] is None:
                    blank = default_row()
                    row.update({k: blank[k] for k in derive.WINDOWS}, source="none")
                else:
                    row["source"] = "cache"
            rows.append(row)
        snap["accounts"] = rows
        snap["schema"] = SCHEMA
        now = int(time.time()) if now is None else now
        derive.recompute(snap, threshold, now)
        snap["notified"] = alerts.keys(snap.get("notified"))
        found = alerts.evaluate(snap, threshold, now) if emit else []
        _replace(directory, snap)
        for alert in found:
            emit(alert)
        return [warning] if warning else []


def record(directory, sent):
    """Record in `notified` the alerts the host handed to macOS (TASK-640), under the lock; return warning lines."""
    path = snapshot_path(directory)
    with _locked(directory):
        snap, warning = read(path)
        if snap is None:
            return ["agent-usage-monitor: snapshot %s missing or unreadable, sent alerts not recorded" % path]
        snap["notified"] = alerts.apply(alerts.keys(snap.get("notified")), [a for a in sent if isinstance(a, dict)])
        _replace(directory, snap)
        return []
