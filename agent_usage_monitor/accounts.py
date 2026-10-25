"""Account list (FR-1 to FR-4)."""

import collections
import json
import os
import tempfile

# account: a display string such as an email, or None; unlike name it may repeat
Account = collections.namedtuple("Account", "name client dir account", defaults=(None,))

CLIENTS = ("claude", "codex")
DEFAULT_THRESHOLD = 90


class AccountsError(Exception):
    pass


def home(environ):
    return environ.get("HOME") or os.path.expanduser("~")


def expand(path, environ):
    if path == "~" or path.startswith("~/"):
        path = home(environ) + path[1:]
    return os.path.realpath(path)


def config_path(environ):
    base = environ.get("XDG_CONFIG_HOME") or os.path.join(home(environ), ".config")
    return os.path.join(base, "agent-usage-monitor", "accounts.json")


def defaults(environ):
    dirs = [(name, expand("~/." + name, environ)) for name in CLIENTS]
    return [Account(name, name, d) for name, d in dirs if os.path.isdir(d)]


def load(environ):
    """Return (threshold, [Account], hint); hint is a stderr line or None."""
    path = config_path(environ)
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        hint = ("agent-usage-monitor: no account list at %s; using default accounts in ~/.claude and ~/.codex"
                % path)
        return DEFAULT_THRESHOLD, defaults(environ), hint
    except (OSError, UnicodeDecodeError) as e:
        raise AccountsError("%s: cannot read: %s" % (path, e))
    try:
        data = json.loads(text)
    except (ValueError, RecursionError) as e:
        raise AccountsError("%s: not valid JSON: %s" % (path, e))
    threshold, accounts, problems = validate(data, environ)
    if problems:
        _, where, problem = problems[0]
        raise AccountsError("%s: %s" % (path, "%s: %s" % (where, problem) if where else problem))
    return threshold, accounts, None


def _bad_threshold(threshold):
    return isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 < threshold <= 100


def validate(data, environ):
    """Return (threshold, [Account], problems), each problem (index or None, where, text); collect stops at the
    first, the settings window shows each on its row (TASK-645)."""
    if not isinstance(data, dict):
        return DEFAULT_THRESHOLD, [], [(None, None, "top level must be an object")]
    problems = []
    threshold = data.get("threshold", DEFAULT_THRESHOLD)
    if _bad_threshold(threshold):
        problems.append((None, None, "threshold must be a number in (0, 100]"))
    items = data.get("accounts")
    if not isinstance(items, list):
        return threshold, [], problems + [(None, None, "accounts must be a list")]

    accounts = []
    seen_names = {}
    seen_dirs = {}

    def check(i, item):
        if not isinstance(item, dict):
            return "must be an object"
        name = item.get("name")
        if not isinstance(name, str) or not name:
            return "name must be a non-empty string"
        if name in seen_names:
            return "duplicate name, also accounts[%d]" % seen_names[name]
        seen_names[name] = i
        client = item.get("client")
        if client not in CLIENTS:
            return "client must be one of %s" % ", ".join(CLIENTS)
        raw_dir = item.get("dir")
        if not isinstance(raw_dir, str) or not raw_dir:
            return "dir must be a non-empty string"
        real = expand(raw_dir, environ)
        if not os.path.isdir(real):
            return "dir %s is not an existing directory" % raw_dir
        if real in seen_dirs:
            return "dir is the same directory as accounts[%d]" % seen_dirs[real]
        seen_dirs[real] = i
        account = item.get("account")
        if "account" in item and (not isinstance(account, str) or not account):
            return "account must be a non-empty string"
        accounts.append(Account(name, client, real, account))
        return None

    for i, item in enumerate(items):
        problem = check(i, item)
        if problem:
            where = "accounts[%d]" % i
            name = item.get("name") if isinstance(item, dict) else None
            if isinstance(name, str) and name:
                where = "%s (%s)" % (where, name)
            problems.append((i, where, problem))
    return threshold, accounts, problems


FIELDS = ("name", "client", "dir", "account")


def abbreviate(path, environ):
    # realpath too: the default dirs come back from expand
    for h in (home(environ), os.path.realpath(home(environ))):
        if path == h or path.startswith(h + "/"):
            return "~" + path[len(h):]
    return path


def editable(environ):
    """The settings window's view of the file (TASK-645 FR-5, FR-9): defaults when it is missing; defaults and an
    error, the file left alone, when collect rejects it as a whole or the window cannot show its rows. Problems
    with one row stay editable, for Save to report."""
    path = config_path(environ)
    shown = abbreviate(path, environ)
    view = {"error": None, "threshold": DEFAULT_THRESHOLD, "original": "{}",
            "accounts": [{"name": a.name, "client": a.client, "dir": abbreviate(a.dir, environ), "account": "",
                          "original": "{}"} for a in defaults(environ)]}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.loads(f.read())
    except FileNotFoundError:
        return view
    except (OSError, UnicodeDecodeError, ValueError, RecursionError) as e:
        return dict(view, error="%s: %s" % (shown, e))
    file_problems = [problem for i, _, problem in validate(data, environ)[2] if i is None]
    if file_problems:
        return dict(view, error="%s: %s" % (shown, "; ".join(file_problems)))
    items = data["accounts"]
    if not all(isinstance(item, dict) and all(isinstance(item.get(k, ""), str) for k in FIELDS) for item in items):
        return dict(view, error="%s: each of accounts must be an object whose %s are strings"
                                % (shown, ", ".join(FIELDS)))
    rows = [dict({k: item.get(k, "") for k in FIELDS}, dir=abbreviate(item.get("dir", ""), environ),
                 original=json.dumps(item)) for item in items]
    return dict(view, threshold=data.get("threshold", DEFAULT_THRESHOLD), accounts=rows, original=json.dumps(data))


def save(environ, request):
    """Write the settings window's edit (TASK-645 FR-6, FR-7) with collect's rules; return [(index or None, problem)],
    empty once written. Keys the window does not know stay as they were in `original`."""
    data = json.loads(request["original"])
    threshold = request["threshold"]
    data["threshold"] = int(threshold) if isinstance(threshold, float) and threshold.is_integer() else threshold
    items = []
    for row in request["accounts"]:
        item = json.loads(row["original"])
        item.update({k: row[k] for k in ("name", "client")})
        # an unedited row keeps its dir as written, not as editable() shortened it
        if not (isinstance(item.get("dir"), str) and abbreviate(item["dir"], environ) == row["dir"]):
            item["dir"] = row["dir"]
        if row["account"]:
            item["account"] = row["account"]
        else:
            item.pop("account", None)
        items.append(item)
    data["accounts"] = items
    _, _, problems = validate(data, environ)
    if problems:
        return [(i, problem) for i, _, problem in problems]
    # realpath: a symlinked accounts.json stays a link to the file it names
    path = os.path.realpath(config_path(environ))
    directory = os.path.dirname(path)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    # mkstemp: mode 0600; the rename means collect reads the whole old file or the whole new one
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".accounts.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise
    return []
