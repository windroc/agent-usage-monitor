"""Claude probe (FR-9 to FR-11): `claude -p /usage` per account (docs/spikes/TASK-572-claude-usage.md,
docs/spikes/TASK-583-claude-config-dir-usage.md).

Launch follows CodexBar's direct /usage probe (THIRD_PARTY_NOTICES.md); output parsing is claude_usage.
"""

import json
import os
import re
import subprocess
import tempfile
import time

from agent_usage_monitor import accounts, claude_usage, proc as procs, store

TIMEOUT = 30.0
VERSION_TIMEOUT = 10.0
POLL = 0.5
THROTTLE = 240  # under the LaunchAgent's 300 s, so a run starting a few seconds early still probes
ARGS = ["-p", "--no-session-persistence", "--strict-mcp-config", "--settings",
        '{"remoteControlAtStartup":false,"disableAllHooks":true}', "--model", "sonnet", "--effort", "low", "/usage"]
UNKNOWN_VERSION = "unknown"
DISABLE_AFTER = 3  # unrecognized outputs in a row on one claude version (WDRC-97)
# a disabled probe runs once more this long after its pause started; each failed retry doubles the wait (WDRC-100)
RETRY_FIRST = 300
RETRY_MAX = 6 * 3600
RETRY_SLACK = 60  # due this early, so a 300 s LaunchAgent run that starts a little early still retries (as THROTTLE)
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")
_VERSION = re.compile(r"\d{1,6}\.\d{1,6}\.\d{1,6}\S{0,30}( \(Claude Code\))?")  # at most 64 chars
DESCRIPTIONS = {
    "auth": "not logged in or login expired; run claude and /login",
    "usage_error": "claude could not load usage data; try again later",
    "loading": "usage data was still loading",
    "timeout": "no usable output (timed out, empty output or non-zero exit)",
}
# The row's error (WDRC-98), which the widget shows: short, and never a path, an account or raw output
REASONS = {"usage_error": "claude could not load usage data", "loading": "usage data still loading"}
# disabled, for any version: short enough for the large widget; the log line names the version
PAUSED = "/usage unreadable · paused"


def config_dir_of(account, environ):
    """CLAUDE_CONFIG_DIR for the probe: None for ~/.claude, else the account's dir.

    Set, even to ~/.claude, claude looks for a login item named after the dir and reads as logged out (TASK-583).
    """
    return None if account.dir == accounts.expand("~/.claude", environ) else account.dir


def _environment(environ, probe_dir, config_dir):
    drop = {"CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN"}
    env = {k: v for k, v in environ.items() if k not in drop and not k.startswith("ANTHROPIC_")}
    env.update(DISABLE_AUTOUPDATER="1", PWD=probe_dir)
    if config_dir is not None:
        env["CLAUDE_CONFIG_DIR"] = config_dir
    return env


def _prepare(state_dir):
    """Create <state>/probe/ (0700) with CodexBar's .claude/settings.local.json; return its realpath."""
    store.ensure_dir(state_dir)
    probe_dir = os.path.join(state_dir, "probe")
    os.makedirs(probe_dir, mode=0o700, exist_ok=True)
    os.chmod(probe_dir, 0o700)
    settings_dir = os.path.join(probe_dir, ".claude")
    os.makedirs(settings_dir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=settings_dir, prefix=".settings.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"disableDeepLinkRegistration": "disable"}, f)
        os.replace(tmp, os.path.join(settings_dir, "settings.local.json"))
    except BaseException:
        os.unlink(tmp)
        raise
    return os.path.realpath(probe_dir)


def capture_path(probe_dir, name):
    """<probe dir>/last-unrecognized-<name>.txt, each character of name outside [A-Za-z0-9._-] as `_`."""
    return os.path.join(probe_dir, "last-unrecognized-%s.txt" % _UNSAFE.sub("_", name))


def _save_capture(path, out, err):
    """Replace path (0600) with the raw output; it stays local, never in the snapshot or the log (WDRC-97)."""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".capture.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("--- stdout ---\n%s\n--- stderr ---\n%s\n" % (out, err))
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def _run(args, probe_dir, env, timeout):
    """Return (stdout, stderr, exit code or None on timeout); raise OSError when claude cannot start."""
    proc = procs.popen(["claude"] + args, cwd=probe_dir, env=env, stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    deadline = time.monotonic() + timeout
    exited = False
    try:
        while True:
            try:
                out, err = proc.communicate(timeout=max(0, min(POLL, deadline - time.monotonic())))
                break
            except subprocess.TimeoutExpired as e:
                # a child claude left behind can hold the pipes open: once claude has exited, take
                # what one more slice reads
                if exited or time.monotonic() >= deadline:
                    out, err = e.output or b"", e.stderr or b""
                    break
                exited = proc.poll() is not None
        code = proc.poll()
    finally:
        procs.stop(proc)
    return out.decode("utf-8", "replace"), err.decode("utf-8", "replace"), code


def _version(probe_dir, env, timeout):
    """The first stdout line of `claude --version` when it is a version, else None."""
    try:
        out, _, code = _run(["--version"], probe_dir, env, timeout)
    except OSError:
        return None
    lines = out.strip().splitlines()
    line = lines[0].strip() if code == 0 and lines else ""
    return line if _VERSION.fullmatch(line) else None


def _timeout_reason(code):
    if code is None:
        return "timed out"
    if code != 0:
        return "claude exited with code %d" % code
    return "no output from claude"


def _logged_out(probe_dir, env, timeout):
    """True only when `claude auth status --json` says loggedIn false (it exits 1 then); False when unknown."""
    try:
        out, _, _ = _run(["auth", "status", "--json"], probe_dir, env, timeout)
    except OSError:
        return False
    try:
        status = json.loads(out)
    except (ValueError, RecursionError):
        return False
    return isinstance(status, dict) and status.get("loggedIn") is False


def _wait(row):
    """The row's wait from usage_disabled_at to its next retry (usage_retry_after_s), None when unset or invalid.

    At most RETRY_MAX, so a corrupt or hand-edited wait cannot stop the timer retry (WDRC-101)."""
    wait = row.get("usage_retry_after_s")
    return min(wait, RETRY_MAX) if type(wait) is int and wait > 0 else None


def _next(seconds):
    return "next retry in %d min or on a widget click" % -(-seconds // 60)


def refresh(name, row, state_dir, environ, config_dir=None, now=None, timeout=TIMEOUT,
            version_timeout=VERSION_TIMEOUT, retry_paused=False):
    """Probe one account; return (fields to merge, kept, stderr line or None).

    An account fetched under THROTTLE ago is skipped, unless retry_paused: a widget click probes at once (WDRC-480).
    kept: the row keeps its snapshot values (store.write's failed set). An `auth` result never disables the
    probe and clears an earlier disable (TASK-873), so logging in recovers the account on the next run.
    An `unrecognized` result disables it only as the DISABLE_AFTER-th in a row on one claude version
    (unrecognized_count, unrecognized_version); a success or a disable resets the count (WDRC-97).
    A disabled probe (usage_disabled_version) runs once more when retry_paused (a widget click) or its next retry is
    due: usage_retry_after_s, at most RETRY_MAX (WDRC-101), less RETRY_SLACK, after usage_disabled_at, when it
    paused or last retried; a pause without a valid schedule, or one ahead of now, is due. A success or `auth` then
    ends the pause as usual and clears its schedule; any other result keeps it at once, with no count, and doubles
    the wait up to RETRY_MAX (WDRC-100).
    An unrecognized result or a disable, new or kept, clears needs_login: auth status has just said the account
    is not logged out. Every result but a throttled skip sets error: the failure's reason, or None (WDRC-98).
    """
    now = int(time.time()) if now is None else now
    fetched = row.get("fetched_at")
    if not retry_paused and fetched is not None and 0 <= now - fetched < THROTTLE:
        return {}, True, None
    prefix = "agent-usage-monitor: claude %s: " % name

    def failed(reason, log, **fields):
        return dict(fields, error=reason), True, prefix + log

    try:
        probe_dir = _prepare(state_dir)
    except OSError as e:
        reason = "cannot prepare probe dir: %s" % procs.reason(e)
        return failed(reason, reason)
    env = _environment(environ, probe_dir, config_dir)
    # the login notice is its reason
    auth = failed(None, "auth: " + DESCRIPTIONS["auth"], needs_login=True, usage_disabled_version=None,
                  usage_disabled_at=None, usage_retry_after_s=None)

    disabled = row.get("usage_disabled_version")
    retry = False
    since, wait = row.get("usage_disabled_at"), _wait(row)
    # a failed retry keeps the pause and doubles its wait; an old pause without one starts at RETRY_FIRST
    backoff = min(2 * (wait or RETRY_FIRST), RETRY_MAX)

    def kept_paused(log):
        return failed(PAUSED, "retry: %s; probe stays disabled for %s; %s" % (log, disabled, _next(backoff)),
                      needs_login=False, usage_disabled_at=now, usage_retry_after_s=backoff)

    if disabled is not None:
        current = _version(probe_dir, env, version_timeout)
        if current is None or current == disabled:
            # logged out explains the output that disabled it (before TASK-873 that was `unrecognized`)
            if _logged_out(probe_dir, env, version_timeout):
                return auth
            if not retry_paused and type(since) is int and wait and 0 <= now - since < wait - RETRY_SLACK:
                return failed(PAUSED, "probe disabled for %s; %s"
                              % (disabled, _next(since + wait - RETRY_SLACK - now)), needs_login=False)
            retry = True

    try:
        out, err, code = _run(ARGS, probe_dir, env, timeout)
    except OSError as e:
        reason = "cannot start claude: %s" % procs.reason(e)
        return kept_paused(reason) if retry else failed(reason, reason)
    try:
        parsed = claude_usage.parse(out + "\n" + err)
    except claude_usage.UsageError as e:
        kind = e.kind
    else:
        kind = None
    if kind not in ("auth", "usage_error", "loading") and (code != 0 or not out.strip()):
        kind = "timeout"
    # logged out, /usage prints only the session cost screen and no auth error (TASK-873); a hung probe skips this
    if kind in ("unrecognized", "timeout") and code is not None and _logged_out(probe_dir, env, version_timeout):
        kind = "auth"
    if kind is None:
        fields = dict(claude_usage.make_windows(parsed, now), fetched_at=now, source="usage",
                      usage_disabled_version=None, usage_disabled_at=None, usage_retry_after_s=None,
                      unrecognized_count=0, unrecognized_version=None, needs_login=False, error=None)
        return fields, False, None
    if kind == "auth":
        return auth
    if kind != "unrecognized":
        log = "%s: %s" % (kind, DESCRIPTIONS[kind])
        if retry:
            return kept_paused(log)
        return failed(_timeout_reason(code) if kind == "timeout" else REASONS[kind], log)
    path = capture_path(probe_dir, name)
    try:
        _save_capture(path, out, err)
        capture = "raw output in %s" % path
    except OSError as e:
        capture = "raw output not saved to %s: %s" % (path, procs.reason(e))
    version = _version(probe_dir, env, version_timeout) or UNKNOWN_VERSION
    fields = {"usage_disabled_version": version, "usage_disabled_at": now,
              "usage_retry_after_s": backoff if retry else RETRY_FIRST, "unrecognized_count": 0,
              "unrecognized_version": None, "needs_login": False}
    shown = "version unknown" if version == UNKNOWN_VERSION else version
    if retry:
        return failed(PAUSED, "retry: output not recognized; probe disabled again for %s; %s; %s"
                      % (shown, _next(backoff), capture), **fields)
    count = row.get("unrecognized_count")
    count = count + 1 if type(count) is int and row.get("unrecognized_version") == version else 1
    if count < DISABLE_AFTER:
        return failed("/usage output not recognized (%d of %d)" % (count, DISABLE_AFTER),
                      "unrecognized: output not recognized (%d of %d on %s); %s"
                      % (count, DISABLE_AFTER, shown, capture),
                      unrecognized_count=count, unrecognized_version=version, usage_disabled_version=None,
                      usage_disabled_at=None, usage_retry_after_s=None, needs_login=False)
    message = "unrecognized: output not recognized %d times; " % count
    if version == UNKNOWN_VERSION:
        return failed(PAUSED, message + "version unknown, probe disabled until claude --version answers; %s; %s"
                      % (_next(RETRY_FIRST), capture), **fields)
    return failed(PAUSED, message + "probe disabled for %s until claude changes version; %s; %s"
                  % (version, _next(RETRY_FIRST), capture), **fields)
