"""Process helpers shared by the probes."""

import errno
import os
import signal
import subprocess
import threading

_lock = threading.Lock()
_live = set()
_stopping = False


def popen(args, **kwargs):
    """Start a probe in its own process group; refuse once kill_all has run."""
    with _lock:
        if _stopping:
            raise OSError(errno.ECANCELED, "agent-usage-monitor is stopping")
        proc = subprocess.Popen(args, start_new_session=True, **kwargs)
        _live.add(proc)
    return proc


def kill_all():
    """Kill the process group of every probe not yet stopped, and refuse new probes."""
    global _stopping
    with _lock:
        _stopping = True
        for proc in _live:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass


def stop(proc):
    """Close stdin, give the process 1 s, then kill its whole group, reap it and close its pipes."""
    with _lock:
        _live.discard(proc)
    try:
        if proc.stdin:
            proc.stdin.close()
    except OSError:
        pass
    try:
        proc.wait(1)
    except subprocess.TimeoutExpired:
        pass
    try:
        # the group outlives its leader while children remain
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    proc.wait()
    for f in (proc.stdout, proc.stderr):
        if f:
            f.close()


def reason(e):
    return errno.errorcode.get(e.errno, str(e.errno)) if e.errno else type(e).__name__
