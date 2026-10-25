import argparse
import concurrent.futures
import functools
import json
import os
import signal
import sys
import time

from agent_usage_monitor import accounts, claude, codex, proc as procs, store


def _codex(account, environ):
    try:
        windows = codex.probe(account.dir, environ)
    except codex.ProbeError as e:
        # the ProbeError texts hold no path or account data, so the widget can show them (WDRC-98)
        return {"error": str(e)}, True, "agent-usage-monitor: codex %s: %s" % (account.name, e)
    return dict(windows, fetched_at=int(time.time()), source="app-server", error=None), False, None


PREFIX = "AUM-ALERT "


def _emit(alert):
    # the prefix sets alerts apart from anything the host's login shell prints
    print(PREFIX + json.dumps(alert), flush=True)


def record_alerts(environ, lines):
    """The host passes back the AUM-ALERT lines it handed to macOS; only those count as sent (TASK-640)."""
    sent = []
    for line in lines:
        if not line.startswith(PREFIX):
            continue
        try:
            alert = json.loads(line[len(PREFIX):])
        except ValueError:
            alert = None
        if isinstance(alert, dict):
            sent.append(alert)
        else:
            print("agent-usage-monitor: record-alerts: skipping a malformed line", file=sys.stderr)
    for line in store.record(store.state_dir(environ), sent):
        print(line, file=sys.stderr)
    return 0


def write_accounts(environ, text):
    """TASK-645: the settings window's edit on stdin; its problems as one JSON line and exit 1, or written."""
    try:
        problems = accounts.save(environ, json.loads(text))
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        print("agent-usage-monitor: write-accounts: malformed request: %r" % e, file=sys.stderr)
        return 2
    except OSError as e:
        print("agent-usage-monitor: write-accounts: %s" % e, file=sys.stderr)
        return 2
    if problems:
        print(json.dumps({"problems": [{"index": i, "message": m} for i, m in problems]}))
        return 1
    return 0


def collect(environ, emit_alerts=False, retry_paused=False):
    path = environ.get("PATH", "")
    local_bin = os.path.join(accounts.home(environ), ".local", "bin")
    if local_bin not in path.split(os.pathsep):
        # claude and codex install here; the host's zsh -l skips ~/.zshrc, where PATH usually gains it
        environ = dict(environ, PATH=path + os.pathsep + local_bin if path else local_bin)
    try:
        threshold, accts, hint = accounts.load(environ)
    except accounts.AccountsError as e:
        print("agent-usage-monitor: %s" % e, file=sys.stderr)
        return 2
    if hint:
        print(hint, file=sys.stderr)
    state = store.state_dir(environ)
    snap, _ = store.read(store.snapshot_path(state))  # store.write reports an unreadable snapshot
    rows = {row["name"]: row for row in (snap or {}).get("accounts", [])}
    jobs = {}
    for account in accts:
        if account.client == "codex":
            jobs[account.name] = (_codex, account, environ)
        else:
            jobs[account.name] = (functools.partial(claude.refresh, retry_paused=retry_paused), account.name,
                                  rows.get(account.name, {}), state, environ, claude.config_dir_of(account, environ))
    updates, failed = {}, set()
    # FR-14: one thread per account, so a stuck probe holds up only its own row
    interrupted = None
    with concurrent.futures.ThreadPoolExecutor(max(len(jobs), 1)) as pool:
        futures = {name: pool.submit(*job) for name, job in jobs.items()}
        try:
            concurrent.futures.wait(futures.values())
        except SystemExit as e:
            # SIGTERM (main): end the probes still running and write the rows that finished
            interrupted = e
            procs.kill_all()
        for name, future in futures.items():
            fields, kept, message = future.result()
            updates[name] = fields
            if kept:
                failed.add(name)
            if message:
                print(message, file=sys.stderr)
    for line in store.write(state, accts, threshold, updates, failed, emit=_emit if emit_alerts else None):
        print(line, file=sys.stderr)
    if interrupted:
        raise interrupted
    return 0


def main(argv=None):
    # the default SIGTERM action skips finally, which would orphan the probes' process groups
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    parser = argparse.ArgumentParser(prog="agent-usage-monitor")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("collect", help="read every account's limits and write the snapshot")
    p.add_argument("--emit-alerts", action="store_true", help="decide alerts and print each as an AUM-ALERT line")
    p.add_argument("--retry-paused", action="store_true",
                   help="probe paused Claude accounts once (a widget click, WDRC-100)")
    sub.add_parser("record-alerts", help="record the AUM-ALERT lines on stdin as sent (the host, after posting them)")
    sub.add_parser("read-accounts", help="print the account list as the settings window shows it, as one JSON line")
    sub.add_parser("write-accounts", help="check and write the settings window's edit from stdin (exit 1: problems)")
    args = parser.parse_args(argv)
    if args.command == "read-accounts":
        print(json.dumps(accounts.editable(os.environ)))
        return 0
    if args.command == "write-accounts":
        return write_accounts(os.environ, sys.stdin.read())
    if args.command == "record-alerts":
        return record_alerts(os.environ, sys.stdin.read().splitlines())
    return collect(os.environ, args.emit_alerts, args.retry_paused)
