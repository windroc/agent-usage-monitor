# Ported to Python from CodexBar (https://github.com/steipete/CodexBar), commit
# 6480977b47f6e4ffd5dcaae1cb0c7fdf34ee449e:
# Sources/CodexBarCore/Providers/Claude/ClaudeStatusProbe.swift (parse and its helpers, parseResetDate),
# ClaudeUsageFetcher.swift (makeSnapshot) and ClaudeCLIScreen.swift (plain-report rendering).
#
# MIT License
#
# Copyright (c) 2026 Peter Steinberger
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
"""Claude `/usage` output parser (FR-10): pure functions, no I/O besides the local time zone."""

import json
import os
import re
import zoneinfo
from datetime import datetime, timedelta

from agent_usage_monitor import derive

MONTHS = {m: i for i, m in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
FULL_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august",
               "september", "october", "november", "december")

# --- reset dates (parseResetDate) ---

_T12 = r"(?P<h12>\d{1,2})(?::(?P<m12>\d{2}))? ?(?P<ap>[ap]m)"
_T24 = r"(?P<h24>\d{1,2}):(?P<m24>\d{2})"
_DATE = r"(?P<mon>[a-z]+) (?P<day>\d{1,2})"
_EXPLICIT = re.compile(r"%s,? (?P<year>\d{4}),? (?:%s|%s|(?P<hh>\d{1,2}))" % (_DATE, _T12, _T24), re.I)
_DATED = re.compile(r"%s,? (?:%s|%s)" % (_DATE, _T12, _T24), re.I)
_TIME = re.compile(r"%s|%s" % (_T12, _T24), re.I)


def _normalize(text):
    raw = (text or "").strip()
    if not raw:
        return None
    raw = re.sub(r"(?i)^resets?:?\s*", "", raw)
    raw = re.sub(r"(?i) at ", " ", raw)
    raw = re.sub(r"(?i)\b([A-Za-z]{3})(\d)", r"\1 \2", raw)
    raw = re.sub(r",(\d)", r", \1", raw)
    raw = re.sub(r"(?i)(\d)at(?=\d)", r"\1 ", raw)
    raw = re.sub(r"(?<=\d)\.(\d{2})\b", r":\1", raw)
    zone = None
    m = re.search(r"\(([^)]+)\)", raw)
    if m:
        zone = _zone(m.group(1).strip("() "))
        raw = (raw[:m.start()] + raw[m.end():]).strip()
    raw = re.sub(r"\s+", " ", raw).strip()
    return (raw, zone) if raw else None


def _zone(name):
    try:
        return zoneinfo.ZoneInfo(name)
    except (ValueError, zoneinfo.ZoneInfoNotFoundError):
        return None


def local_zone():
    """TZ when it names a zone, else the zone /etc/localtime links to, else the current fixed offset."""
    zone = _zone(os.environ["TZ"].lstrip(":")) if os.environ.get("TZ") else None
    if zone is None:
        try:
            link = os.readlink("/etc/localtime")
        except OSError:
            link = ""
        if "zoneinfo/" in link:
            zone = _zone(link.split("zoneinfo/", 1)[1])
    return zone or datetime.now().astimezone().tzinfo


def _month(name):
    name = name.lower()
    if name in MONTHS:
        return MONTHS[name]
    if name in FULL_MONTHS or name == "sept":
        return MONTHS[name[:3]]
    return None


def _time(m):
    """(hour, minute) from a _T12/_T24/hour-only match, or None when out of range."""
    if m.group("ap"):
        h, mi = int(m.group("h12")), int(m.group("m12") or 0)
        if not 1 <= h <= 12:
            return None
        h = h % 12 + (12 if m.group("ap").lower() == "pm" else 0)
    elif m.group("h24") is not None:
        h, mi = int(m.group("h24")), int(m.group("m24"))
    else:
        h, mi = int(m.group("hh")), 0
    return (h, mi) if h < 24 and mi < 60 else None


def _exact(zone, y, mo, d, h, mi):
    """Instants of a local wall time: none in a DST gap, both when it repeats."""
    out = []
    for fold in (0, 1):
        try:
            ts = datetime(y, mo, d, h, mi, tzinfo=zone, fold=fold).timestamp()
        except (ValueError, OverflowError):
            return []
        back = datetime.fromtimestamp(ts, zone)
        if (back.year, back.month, back.day, back.hour, back.minute) == (y, mo, d, h, mi) and ts not in out:
            out.append(ts)
    return out


def _resolve(candidates, now, expected_window):
    candidates = sorted(candidates)
    future = next((c for c in candidates if c >= now), None)
    if future is None:
        return candidates[-1] if candidates else None
    if expected_window is None:
        return future
    horizon = max(0, expected_window)
    past = [c for c in candidates if c < now]
    past_ok = bool(past) and now - past[-1] <= horizon
    return past[-1] if past_ok and future - now > horizon else future


def parse_reset_date(text, now, expected_window=None):
    """Epoch seconds of a reset description such as `Resets Oct 17 at 4:39am (America/New_York)`."""
    normalized = _normalize(text)
    if normalized is None:
        return None
    raw, zone = normalized
    zone = zone or local_zone()
    today = datetime.fromtimestamp(now, zone).date()

    m = _EXPLICIT.fullmatch(raw) or _DATED.fullmatch(raw) or _TIME.fullmatch(raw)
    if m is None:
        return None
    t = _time(m)
    if t is None:
        return None
    if m.re is _TIME:
        days = [today + timedelta(days=k) for k in (-1, 0, 1)]
        found = [ts for d in days for ts in _exact(zone, d.year, d.month, d.day, *t)]
    else:
        mo, day = _month(m.group("mon")), int(m.group("day"))
        if mo is None:
            return None
        if m.re is _EXPLICIT:
            found = _exact(zone, int(m.group("year")), mo, day, *t)
        else:
            # eight years either side covers the gap between leap days (e.g. 2096 to 2104)
            found = [ts for y in range(today.year - 8, today.year + 9) for ts in _exact(zone, y, mo, day, *t)]
    result = _resolve(found, now, expected_window)
    return None if result is None else int(result)


# --- /usage text (ClaudeStatusProbe.parse) ---

INSIGHTS_MARKER = "What's contributing to your limits usage?"
SESSION_LABEL = "Current session"
WEEKLY_LABEL = "Current week (all models)"
SESSION_MINUTES = 5 * 60  # ClaudeUsageFetcher.sessionWindowMinutes
WEEKLY_MINUTES = 7 * 24 * 60  # ClaudeUsageFetcher.weeklyWindowMinutes
SUBSCRIPTION_ONLY = ("Claude CLI /usage returned a subscription notice without session quota data. "
                     "Local cost and token history remain available.")
# CodexBar's list; its "<provider> account information not found" marker is cut to the shared tail (spec D6)
AUTH_MARKERS = (
    "authentication_error", "permission_error", "token_expired", "token expired", "token has expired",
    "account information not found", "does not have access to claude code", "run /login",
    "run `claude login`", "run claude login", "api error: 401", "api error: 403", "forbidden",
    "invalid api key", "invalid_api_key", "invalid credential", "not authenticated", "not authorized",
    "token revoked", "unauthorized",
)
RATE_LIMITED = "Claude CLI usage endpoint is rate limited right now. Please try again later."
LOAD_FAILED = "Claude CLI could not load usage data. Open the CLI and retry `/usage`."

_TOKENS = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]?|\][\s\S]*?(?:\x07|\x1b\\|\Z)|.)|[^\x1b]+")
_NEWLINES = re.compile(r"[\n\x0b\x0c\r\x85  ]")
_SPACE_SEPARATORS = "    -   　"
_PERCENT = re.compile(r"([0-9]{1,3}(?:\.[0-9]+)?)[%s]*%%" % _SPACE_SEPARATORS)
_WEEKLY_MODEL = re.compile(r"current\s*week\s*\(([^)]+)\)", re.I)


class UsageError(Exception):
    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


def _round(x):
    """Swift .rounded(): half away from zero (inputs here are never negative)."""
    return int(x + 0.5)


def _compact(text):
    return "".join(c for c in text if not c.isspace())


def _norm(text):
    return "".join(c for c in text.lower() if c.isalnum())


def clean_capture(text):
    """ClaudeCLIScreen.render's plain path (escape sequences dropped; spec D4), then cut after the insights heading."""
    rendered = "".join(t for t in _TOKENS.findall(text) if not t.startswith("\x1b"))
    i = rendered.lower().find(INSIGHTS_MARKER.lower())
    return rendered if i < 0 else rendered[:i + len(INSIGHTS_MARKER)]


def _weekly_model(line):
    m = _WEEKLY_MODEL.search(line)
    return m.group(1).strip() if m else None


def _edit_distance(a, b):
    row = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        diagonal, row[0] = row[0], i
        for j in range(1, len(b) + 1):
            diagonal, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, diagonal + (a[i - 1] != b[j - 1]))
    return row[len(b)]


def _is_all_models(normalized_model):
    return normalized_model == "allmodels" or _edit_distance(normalized_model, "allmodels") <= 2


def _matches_label(line, label, fuzzy):
    expected = _weekly_model(label)
    if expected is None:
        return _norm(label) in _norm(line)
    actual = _weekly_model(line)
    if actual is None:
        return False
    if fuzzy and _is_all_models(_norm(expected)):
        return _is_all_models(_norm(actual))
    return _norm(actual) == _norm(expected)


def _crosses_label_boundary(line, label, fuzzy):
    if not _norm(line).startswith("current"):
        return False
    expected = _weekly_model(label)
    if expected is None:
        return _norm(label) not in _norm(line)
    actual = _weekly_model(line)
    if actual is None:
        return True
    if fuzzy and _is_all_models(_norm(expected)):
        return not _is_all_models(_norm(actual))
    return _norm(actual) != _norm(expected)


def _is_status_context_line(line):
    return "|" in line and any(t in line.lower() for t in ("opus", "sonnet", "haiku", "default"))


def percent_left(line, assume_remaining=False):
    """Percent left on a line: `17% used` -> 83, `40% left` -> 40; None without a used/left keyword."""
    if _is_status_context_line(line):
        return None
    m = _PERCENT.search(line)
    if not m:
        return None
    value = max(0.0, min(100.0, float(m.group(1))))
    lower = line.lower()
    if any(k in lower for k in ("used", "spent", "consumed")):
        return _round(max(0.0, min(100.0, 100 - value)))
    if any(k in lower for k in ("left", "remaining", "available")) or assume_remaining:
        return _round(value)
    return None


def _after_label(lines, label, size, pick):
    """First pick(line) in the `size` lines from each label line, stopping at the next label; exact match first."""
    for fuzzy in (False, True):
        for idx, line in enumerate(lines):
            if not _matches_label(line, label, fuzzy):
                continue
            for candidate in lines[idx:idx + size]:
                if _crosses_label_boundary(candidate, label, fuzzy):
                    break
                value = pick(candidate)
                if value is not None:
                    return value
    return None


def _clean_reset_line(raw):
    cleaned = raw.strip().strip(" )")
    cleaned = re.sub(r"(?i)\b([A-Za-z]{3}\s+\d{1,2})\s+t\s+(\d)", r"\1 at \2", cleaned)
    if cleaned.count("(") > cleaned.count(")"):
        cleaned += ")"
    return cleaned


def reset_description(line):
    m = re.search(r"(?i)\bresets?\b", line) or re.search(r"\b(?:Reset|Resets)(?=[A-Z0-9])", line)
    return _clean_reset_line(line[m.start():]) if m else None


def _all_percents(text):
    normalized = _compact(text.lower())
    windows = "currentsession" in normalized or "currentweek" in normalized
    keywords = any(k in normalized for k in ("used", "left", "remaining", "available"))
    if not windows or not keywords:
        return []
    return [p for p in (percent_left(line) for line in _NEWLINES.split(text)) if p is not None]


def _has_session_value(normalized):
    i = normalized.find("what'scontributingtoyourlimitsusage?")
    quota = normalized if i < 0 else normalized[:i]
    j = quota.find("currentsession")
    return j >= 0 and re.search(r"[0-9]{1,3}(?:\.[0-9]+)?%", quota[j + len("currentsession"):]) is not None


def _still_loading(text):
    normalized = _compact(clean_capture(text).lower())
    return "loadingusage" in normalized and not _has_session_value(normalized) and not _all_percents(text)


def _subscription_notice_only(text):
    n = _compact(text.lower())
    if "currentlyusingyoursubscription" not in n or "claudecodeusage" not in n:
        return False
    return not any(k in n for k in ("currentsession", "currentweek", "%used", "%left", "%remaining", "%available"))


def _usage_error_json(text):
    m = re.search(r"Failed\s*to\s*load\s*usage\s*data:\s*(\{.*\})", text, re.S)
    if not m:
        return None
    try:
        payload = json.loads(m.group(1).replace("\r", "").replace("\n", "") or m.group(1))
    except (ValueError, RecursionError):
        return None
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return None

    def text_of(v):
        return v.strip() if isinstance(v, str) else None

    message = text_of(error.get("message"))
    details = error.get("details")
    code = text_of(details.get("error_code")) if isinstance(details, dict) else None
    kind = (text_of(error.get("type")) or "").lower() or None
    if kind == "rate_limit_error":
        return RATE_LIMITED
    parts = [p for p in (message, "(%s)" % code if code else None) if p]
    if not parts:
        return None
    hint = " ".join(parts)
    if code and "token" in code.lower():
        return "%s. Run `claude login` to refresh." % hint
    if kind in ("authentication_error", "permission_error"):
        return "Claude CLI authentication error: %s. Run `claude login`." % hint
    return "Claude CLI error: %s" % hint


def _failure_line(text):
    found = re.findall(r"(?i)failed\s*to\s*load\s*usage\s*data[^\r\n]*", text)
    return found[-1] if found else None


def usage_error(text):
    """CodexBar extractUsageError: the CLI's own error message in the output, or None."""
    hint = _usage_error_json(text)
    if hint:
        return hint
    lower = text.lower()
    if "do you trust the files in this folder?" in lower and "current session" not in lower:
        m = re.search(r"(?i)Do you trust the files in this folder\?\s*(?:\r?\n)+\s*([^\r\n]+)", text)
        folder = m.group(1).strip() if m else ""
        if folder:
            return ("Claude CLI is waiting for a folder trust prompt (%s). CodexBar tries to auto-accept this, "
                    'but if it keeps appearing run: `cd "%s" && claude` and choose \u201cYes, proceed\u201d, then retry.'
                    % (folder, folder))
        return ("Claude CLI is waiting for a folder trust prompt. CodexBar tries to auto-accept this, but if it keeps "
                "appearing open `claude` once, choose \u201cYes, proceed\u201d, then retry.")
    failure = (_failure_line(text) or "").lower()
    if "token_expired" in failure or "token has expired" in failure:
        return "Claude CLI token expired. Run `claude login` to refresh."
    if "authentication_error" in failure:
        return "Claude CLI authentication error. Run `claude login`."
    if "rate_limit_error" in failure or "rate limited" in failure or "ratelimited" in _compact(failure):
        return RATE_LIMITED
    if _subscription_notice_only(text):
        if INSIGHTS_MARKER.lower() in lower:
            return "Claude CLI /usage returned usage insights without quota data."
        return SUBSCRIPTION_ONLY
    if "failed to load usage data" in lower or "failedtoloadusagedata" in _compact(lower):
        return LOAD_FAILED
    return None


def _latest_usage_panel(text):
    i = text.lower().rfind("settings:")
    if i < 0:
        return None
    tail = text[i:]
    lower = tail.lower()
    if "usage" not in lower:
        return None
    words = any(k in lower for k in ("used", "left", "remaining", "available"))
    return tail if ("%" in lower and words) or "loading usage" in lower else None


def parse(text):
    """Return {session_left, weekly_left, session_reset, weekly_reset} or raise UsageError.

    Not ported: identity, Opus and model-scoped weekly windows, and the first-percent fallback
    when there is no `Current session` label (that is `unrecognized` here).
    """
    clean = clean_capture(text)
    if not clean.strip():
        raise UsageError("timeout", "empty output")
    message = usage_error(clean)
    if message:
        kind = "auth" if any(m in message.lower() for m in AUTH_MARKERS) else "usage_error"
        raise UsageError(kind, message)
    panel = _latest_usage_panel(clean)
    if _still_loading(panel or clean):
        raise UsageError("loading", "Claude CLI /usage is still loading usage data.")
    lines = _NEWLINES.split(panel or clean)
    session = _after_label(lines, SESSION_LABEL, 12, percent_left)
    if session is None:
        raise UsageError("unrecognized", "Missing Current session.")
    has_weekly = any(_is_all_models(_norm(m)) for m in filter(None, map(_weekly_model, lines)))
    return {
        "session_left": session,
        "weekly_left": _after_label(lines, WEEKLY_LABEL, 12, percent_left),
        "session_reset": _after_label(lines, SESSION_LABEL, 14, reset_description),
        "weekly_reset": _after_label(lines, WEEKLY_LABEL, 14, reset_description) if has_weekly else None,
    }


def make_windows(parsed, now):
    """makeSnapshot's conversion: percent left -> used, reset description -> epoch; keys from derive.WINDOWS."""
    def window(left, reset, minutes):
        if left is None:
            return None
        return {"used_percent": max(0, min(100, 100 - left)),
                "resets_at": parse_reset_date(reset.strip() if reset else None, now, minutes * 60)}

    session = window(parsed["session_left"], parsed["session_reset"], SESSION_MINUTES)
    weekly = window(parsed["weekly_left"], parsed["weekly_reset"], WEEKLY_MINUTES)
    return {derive.BY_MINUTES[SESSION_MINUTES]: session, derive.BY_MINUTES[WEEKLY_MINUTES]: weekly}
