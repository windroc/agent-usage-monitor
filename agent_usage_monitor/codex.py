"""Codex probe (FR-12, FR-13): read rate limits through `codex app-server`.

Protocol (codex app-server generate-json-schema, codex-cli 0.163.0): one JSON object per
line on stdio, no "jsonrpc" field; initialize -> initialized -> account/rateLimits/read.
"""

import json
import os
import select
import subprocess
import time

from agent_usage_monitor import __version__, derive, proc as procs

TIMEOUT = 10.0
MAX_LINE = 1 << 20


class ProbeError(Exception):
    pass


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def parse_rate_limits(result):
    """Map the reply's windows by duration; a window it does not report is None (absent)."""
    limits = result.get("rateLimits") if isinstance(result, dict) else None
    if not isinstance(limits, dict):
        raise ProbeError("unrecognized reply")
    found = {}
    for slot in ("primary", "secondary"):
        w = limits.get(slot)
        if w is None:
            continue
        if not isinstance(w, dict):
            raise ProbeError("unrecognized reply")
        mins, pct, at = w.get("windowDurationMins"), w.get("usedPercent"), w.get("resetsAt")
        key = derive.BY_MINUTES.get(mins) if _is_int(mins) else None
        if key is None or key in found or not _is_int(pct) or not (at is None or _is_int(at)):
            raise ProbeError("unrecognized reply")
        found[key] = {"used_percent": pct, "resets_at": at}
    if not found:
        raise ProbeError("unrecognized reply")
    return {key: found.get(key) for key in derive.WINDOWS}


class _Session:
    def __init__(self, proc, timeout):
        self.proc = proc
        self.timeout = timeout
        self.deadline = time.monotonic() + timeout
        self.buf = b""

    def send(self, msg):
        self.proc.stdin.write(json.dumps(msg).encode() + b"\n")
        self.proc.stdin.flush()

    def line(self):
        while b"\n" not in self.buf:
            if len(self.buf) > MAX_LINE:
                raise ProbeError("unrecognized output")
            remaining = self.deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.proc.stdout], [], [], remaining)[0]:
                raise ProbeError("timed out after %g s" % self.timeout)
            chunk = os.read(self.proc.stdout.fileno(), 65536)
            if not chunk:
                raise ProbeError("app-server exited before replying")
            self.buf += chunk
        line, self.buf = self.buf.split(b"\n", 1)
        if len(line) > MAX_LINE:
            raise ProbeError("unrecognized output")
        return line

    def response(self, rid):
        """Return the result for request rid, skipping notifications and server requests."""
        while True:
            try:
                msg = json.loads(self.line())
            except (ValueError, RecursionError):
                raise ProbeError("unrecognized output")
            if not isinstance(msg, dict):
                raise ProbeError("unrecognized output")
            if msg.get("id") != rid or "method" in msg:
                continue
            if "error" in msg:
                code = msg["error"].get("code") if isinstance(msg["error"], dict) else None
                raise ProbeError("app-server error %d" % code if _is_int(code) else "app-server error")
            return msg.get("result")


def probe(codex_home, environ, timeout=TIMEOUT):
    """Return {window key: window|None} for every derive.WINDOWS key, or raise ProbeError."""
    try:
        proc = procs.popen(["codex", "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, env=dict(environ, CODEX_HOME=codex_home))
    except OSError as e:
        raise ProbeError("cannot start codex: %s" % procs.reason(e))
    session = _Session(proc, timeout)
    try:
        session.send({"id": 1, "method": "initialize",
                      "params": {"clientInfo": {"name": "agent-usage-monitor", "version": __version__}}})
        session.response(1)
        session.send({"method": "initialized"})
        session.send({"id": 2, "method": "account/rateLimits/read"})
        return parse_rate_limits(session.response(2))
    except OSError as e:
        raise ProbeError("app-server i/o failed: %s" % procs.reason(e))
    finally:
        procs.stop(proc)
