"""NFR-4: find personal data before it is public. Prints where and the rule, never the value.

From the repo root: `/usr/bin/python3 tests/pii_scan.py` scans the git-tracked files (make check);
`... --pre-push <remote>` reads the pre-push hook's stdin and scans what the push publishes;
`... --commits <base>..<head>` scans those commits the same way (CI, for a pull request).
"""

import fnmatch
import hashlib
import os
import re
import struct
import subprocess
import sys

ALLOWLIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pii-allowlist.txt")
# `in:identity`: a commit author or committer email only.
SCOPES = {"identity"}

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@((?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})")
# RFC 2606: domains reserved for examples.
EXAMPLE_DOMAIN = re.compile(r"(?:.+\.)?example\.(?:com|org|net)|.+\.example", re.I)
RULES = (
    ("email", EMAIL),
    ("uuid", re.compile(r"(?<![0-9a-f])[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?![0-9a-f])", re.I)),
    ("home-path", re.compile(r"(?<![\w.-])/(?:Users|home)/[A-Za-z0-9._-]+")),
)
PNG = b"\x89PNG\r\n\x1a\n"
PNG_METADATA = {b"tEXt", b"zTXt", b"iTXt", b"eXIf"}
METADATA_MARKERS = (b"Exif\0\0", b"<x:xmpmeta", b"<?xpacket")
ENTRY = re.compile(r"(\S+)(?:\s+in:(\S+))?\s+(?!in:)(\S.*)")


def load_allowlist(path):
    """[(pattern, scope or None)] from entries `<value, fnmatch glob or sha256:<hex>> [in:<scope>] <why it is allowed>`;
    `#` starts a comment line. An entry without a scope applies everywhere."""
    patterns = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = ENTRY.fullmatch(line)
            if not m or m.group(2) not in SCOPES | {None}:
                sys.exit("%s:%d: allowlist entry needs a reason and a scope in %s, if any" % (path, n, sorted(SCOPES)))
            patterns.append(m.group(1, 2))
    return patterns


def matches(value, pattern):
    """`sha256:<hex>` is the SHA-256 of the lowercased value, so the allowlist need not hold it."""
    if pattern.startswith("sha256:"):
        return hashlib.sha256(value.lower().encode()).hexdigest() == pattern[len("sha256:"):]
    return fnmatch.fnmatchcase(value, pattern)


def allowed(value, allow, scopes=()):
    return any(matches(value, p) and (scope is None or scope in scopes) for p, scope in allow)


def scan_text(text, allow, scopes=()):
    """[(line number, rule)] for each value no allowlist entry allows, counting scoped entries only in `scopes`."""
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        for rule, pattern in RULES:
            for m in pattern.finditer(line):
                if rule == "email" and EXAMPLE_DOMAIN.fullmatch(m.group(1)):
                    continue
                if not allowed(m.group(0), allow, scopes):
                    hits.append((n, rule))
    return hits


def scan_binary(data):
    if data.startswith(PNG):
        i = len(PNG)
        while i + 8 <= len(data):
            size, kind = struct.unpack(">I4s", data[i:i + 8])
            if kind in PNG_METADATA:
                return ["metadata"]
            i += 12 + size
        return []
    return ["metadata"] if any(m in data for m in METADATA_MARKERS) else []


def scan_blob(name, data, allow):
    """Hit lines `name:line: rule`. A PNG is checked for metadata only; any other file holding a NUL byte
    is binary: checked for metadata, then by the text rules with its NUL bytes removed."""
    if data.startswith(PNG):
        return ["%s: %s" % (name, rule) for rule in scan_binary(data)]
    hits = ["%s: %s" % (name, rule) for rule in scan_binary(data)] if b"\0" in data else []
    text = data.replace(b"\0", b"").decode("utf-8", "replace")
    return hits + ["%s:%d: %s" % (name, n, rule) for n, rule in scan_text(text, allow)]


def git(*args):
    return subprocess.run(["git"] + list(args), check=True, capture_output=True).stdout


def scan_files(allow):
    hits = []
    for name in git("ls-files", "-z").decode().split("\0"):
        if os.path.islink(name):
            hits += scan_blob(name, os.readlink(name).encode(), allow)
        elif name and os.path.isfile(name):
            with open(name, "rb") as f:
                hits += scan_blob(name, f.read(), allow)
    return hits


def scan_push(remote, refs, allow):
    """Blobs, commit messages, author and committer emails reachable from the pushed tips but from no ref of `remote`."""
    tips = [line.split()[1] for line in refs if line.strip() and line.split()[1].strip("0")]
    if not tips:
        return []
    # shortcut: a push to a URL instead of a remote name excludes nothing, so it scans all reachable history.
    return scan_revs(tips + ["--not", "--remotes=" + remote], allow)


def scan_revs(revs, allow):
    """Blobs, commit messages, author and committer emails of the commits `git rev-list <revs>` names."""
    hits = []
    for line in git("rev-list", "--objects", "--filter=object:type=blob", *revs).decode().splitlines():
        sha, _, path = line.partition(" ")
        if path:
            hits += scan_blob("%s (%s)" % (path, sha[:7]), git("cat-file", "blob", sha), allow)
    for entry in filter(None, git("log", "-z", "--format=%h%n%ae%n%ce%n%B", *revs).decode().split("\0")):
        commit, author, committer, message = (entry + "\n\n\n").split("\n", 3)
        for who, email in (("author", author), ("committer", committer)):
            # Any address, dotted or not: git's fallback identity is user@hostname.
            if "@" in email and not (allowed(email, allow, SCOPES) or EXAMPLE_DOMAIN.fullmatch(email.rpartition("@")[2])):
                hits.append("commit %s %s: email" % (commit, who))
        hits += ["commit %s message:%d: %s" % (commit, n, rule) for n, rule in scan_text(message, allow)]
    return hits


def main(argv):
    allow = load_allowlist(ALLOWLIST)
    if argv[:1] == ["--pre-push"]:
        hits = scan_push(argv[1], sys.stdin, allow)
    elif argv[:1] == ["--commits"]:
        hits = scan_revs([argv[1]], allow)
    else:
        hits = scan_files(allow)
    for hit in hits:
        print(hit)
    if hits:
        print("pii-scan: %d hit(s). Replace each value with a placeholder, or allow a non-personal one in "
              "tests/pii-allowlist.txt with its reason; for a commit author, set a GitHub noreply user.email "
              "for this repo." % len(hits), file=sys.stderr)
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
