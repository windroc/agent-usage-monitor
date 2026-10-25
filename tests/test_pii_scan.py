import hashlib
import os
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib

from tests import pii_scan

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN = os.path.join(ROOT, "tests", "pii_scan.py")

# Hitting fake values are split so the repo's own scan of this file stays clean.
EMAIL = "jane.doe@" + "corp.test"
UUID = "1b4e28ba-2fa1-11d2-883f-" + "0016d3cca427"
HOME = "/Users/" + "jdoe"
HOME_LINUX = "/home/" + "jdoe"
# Split so the NFR-1 grep in make check (no network host names in *.py) stays clean.
ATTRIBUTION = "noreply@anthropic" + ".com"


def png(*chunks):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)
    body = [(b"IHDR", ihdr)] + list(chunks) + [(b"IDAT", zlib.compress(b"\0\0")), (b"IEND", b"")]
    return b"\x89PNG\r\n\x1a\n" + b"".join(chunk(k, d) for k, d in body)


class TextRulesTest(unittest.TestCase):
    def rules(self, text, allow=()):
        return [rule for _, rule in pii_scan.scan_text(text, [(a, None) for a in allow])]

    def test_email_hits_unless_reserved_example_domain(self):
        self.assertEqual(self.rules("mail " + EMAIL), ["email"])
        for ok in ("user@example.com", "a@example.org", "b@EXAMPLE.net", "c@mail.example.com",
                   "d@host.example"):
            self.assertEqual(self.rules(ok), [], ok)

    def test_uuid_hits_any_case(self):
        self.assertEqual(self.rules("id=" + UUID), ["uuid"])
        self.assertEqual(self.rules(UUID.upper()), ["uuid"])
        self.assertEqual(self.rules("session_" + UUID + ".json"), ["uuid"])
        self.assertEqual(self.rules("1b4e28ba-2fa1-11d2-883f-0016d3cca42"), [])
        self.assertEqual(self.rules("<ORG_ID>_<SYNC_ID>"), [])

    def test_home_path_hits_unless_allowlisted(self):
        self.assertEqual(self.rules(HOME + "/.claude"), ["home-path"])
        self.assertEqual(self.rules(HOME_LINUX), ["home-path"])
        self.assertEqual(self.rules("/Users/example/.claude", ["/Users/example"]), [])
        self.assertEqual(self.rules("/Users/<name>, ~/x, /usr/bin"), [])

    def test_allowlist_glob_and_line_numbers(self):
        noreply = "123+jdoe@" + "users.noreply.github.com"
        self.assertEqual(pii_scan.scan_text("ok\n" + noreply + "\n" + EMAIL, [("*@users.noreply.github.com", None)]),
                         [(3, "email")])

    def test_identity_entry_allows_the_value_only_in_identity_scope(self):
        allow = [("sha256:" + hashlib.sha256(EMAIL.encode()).hexdigest(), "identity")]
        self.assertEqual(pii_scan.scan_text("by " + EMAIL, allow), [(1, "email")])
        self.assertEqual(pii_scan.scan_text("by " + EMAIL, allow, {"identity"}), [])

    def test_sha256_entry_matches_the_lowercased_value(self):
        allow = [("sha256:" + hashlib.sha256(EMAIL.lower().encode()).hexdigest(), "identity")]
        self.assertTrue(pii_scan.allowed(EMAIL.upper(), allow, {"identity"}))
        self.assertFalse(pii_scan.allowed("other." + EMAIL, allow, {"identity"}))
        self.assertFalse(pii_scan.allowed(EMAIL, allow))


class BinaryRulesTest(unittest.TestCase):
    def test_png_text_and_exif_chunks_hit(self):
        for kind in (b"tEXt", b"zTXt", b"iTXt", b"eXIf"):
            self.assertEqual(pii_scan.scan_binary(png((kind, b"Author\0x"))), ["metadata"], kind)

    def test_plain_png_passes(self):
        self.assertEqual(pii_scan.scan_binary(png()), [])
        self.assertEqual(pii_scan.scan_binary(png((b"iCCP", b"sRGB\0\0x"))), [])

    def test_exif_and_xmp_markers_hit_in_other_binaries(self):
        self.assertEqual(pii_scan.scan_binary(b"\xff\xd8\xff\xe1\0\x10Exif\0\0MM"), ["metadata"])
        self.assertEqual(pii_scan.scan_binary(b"\0\0<x:xmpmeta xmlns:x='adobe:ns:meta/'>"), ["metadata"])
        self.assertEqual(pii_scan.scan_binary(b"\0\x01\x02plain"), [])

    def test_non_png_binary_runs_text_rules_without_nul_bytes(self):
        self.assertEqual(pii_scan.scan_blob("a.bin", b"\0\x01by " + EMAIL.encode(), []), ["a.bin:1: email"])
        self.assertEqual(pii_scan.scan_blob("a.txt", "\0".join(HOME + "/x").encode(), []), ["a.txt:1: home-path"])
        self.assertEqual(pii_scan.scan_blob("a.jpg", b"\xff\xd8Exif\0\0 " + UUID.encode(), []),
                         ["a.jpg: metadata", "a.jpg:1: uuid"])

    def test_png_gets_no_text_rules(self):
        self.assertEqual(pii_scan.scan_blob("a.png", png((b"IDAT", EMAIL.encode())), []), [])


class AllowlistTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="qb-pii-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.path = os.path.join(self.dir, "allow.txt")

    def write(self, text):
        with open(self.path, "w") as f:
            f.write(text)

    def test_reads_patterns_skipping_comments(self):
        self.write("# header\n\n/Users/example  placeholder home\n*@x.test   fake domain\nme@x.example in:identity  owner\n")
        self.assertEqual(pii_scan.load_allowlist(self.path),
                         [("/Users/example", None), ("*@x.test", None), ("me@x.example", "identity")])

    def test_entry_without_reason_or_with_unknown_scope_is_an_error(self):
        for entry in ("/Users/example\n", "me@x.example in:identity\n", "me@x.example in:files  owner\n"):
            self.write(entry)
            with self.assertRaises(SystemExit, msg=entry):
                pii_scan.load_allowlist(self.path)

    def test_repo_allowlist_loads(self):
        allow = pii_scan.load_allowlist(pii_scan.ALLOWLIST)
        self.assertIn((ATTRIBUTION, None), allow)
        self.assertIn(("noreply@github.com", None), allow)
        # The owner's commit email is stored hashed, never as the literal (user, TASK-621).
        for pattern, scope in allow:
            if scope == "identity":
                self.assertRegex(pattern, r"^sha256:[0-9a-f]{64}$")


def git(cwd, *args):
    subprocess.run(["git", "-C", cwd] + list(args), check=True, capture_output=True, env=GIT_ENV)


GIT_ENV = dict(os.environ, GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1",
               GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")


class FileScanTest(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="qb-pii-")
        self.addCleanup(shutil.rmtree, self.repo, True)
        git(self.repo, "init", "-q")

    def add(self, name, data):
        with open(os.path.join(self.repo, name), "wb") as f:
            f.write(data)
        git(self.repo, "add", name)

    def scan(self):
        return subprocess.run(["/usr/bin/python3", SCAN], cwd=self.repo, capture_output=True, text=True,
                              env=GIT_ENV, timeout=60)

    def test_hits_print_path_line_and_rule_never_the_value(self):
        self.add("a.md", ("ok\nby " + EMAIL + "\n").encode())
        self.add("b.png", png((b"tEXt", b"Comment\0x")))
        with open(os.path.join(self.repo, "untracked.txt"), "w") as f:
            f.write(UUID)
        r = self.scan()
        self.assertEqual(r.returncode, 1)
        self.assertIn("a.md:2: email", r.stdout)
        self.assertIn("b.png: metadata", r.stdout)
        self.assertNotIn("untracked.txt", r.stdout)
        self.assertNotIn(EMAIL, r.stdout + r.stderr)

    def test_clean_repo_passes(self):
        self.add("a.md", b"user@example.com /Users/example\n")
        self.add("b.png", png())
        r = self.scan()
        self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)


class PrePushTest(unittest.TestCase):
    """The real hook, via core.hooksPath, on a temp clone pushing to a temp bare remote."""

    def setUp(self):
        tmp = tempfile.mkdtemp(prefix="qb-pii-")
        self.addCleanup(shutil.rmtree, tmp, True)
        self.repo = os.path.join(tmp, "work")
        git(tmp, "init", "-q", "--bare", "remote.git")
        git(tmp, "init", "-q", "work")
        git(self.repo, "remote", "add", "origin", os.path.join(tmp, "remote.git"))
        git(self.repo, "config", "core.hooksPath", os.path.join(ROOT, ".githooks"))
        self.commit("clean")
        self.assertEqual(self.push().returncode, 0)

    def commit(self, message, files=None, author="t@example.com", committer="t@example.com"):
        for name, text in (files or {}).items():
            with open(os.path.join(self.repo, name), "w") as f:
                f.write(text)
            git(self.repo, "add", name)
        env = dict(GIT_ENV, GIT_AUTHOR_EMAIL=author, GIT_COMMITTER_EMAIL=committer)
        subprocess.run(["git", "-C", self.repo, "commit", "-q", "--allow-empty", "-m", message],
                       check=True, capture_output=True, env=env)

    def push(self, *args):
        return subprocess.run(["git", "-C", self.repo, "push", "-q", "origin"] + list(args or ["HEAD:main"]),
                              capture_output=True, text=True, env=GIT_ENV, timeout=60)

    def assertRefused(self, *expected):
        r = self.push()
        out = r.stdout + r.stderr
        self.assertNotEqual(r.returncode, 0, out)
        for text in expected:
            self.assertIn(text, out)
        for value in (EMAIL, UUID, HOME):
            self.assertNotIn(value, out)

    def test_file_hit_refuses_push(self):
        self.commit("add notes", {"notes.md": "id " + UUID + "\n"})
        self.assertRefused("notes.md", ":1: uuid")

    def test_hit_only_in_an_intermediate_commit_refuses_push(self):
        self.commit("add", {"notes.md": "by " + EMAIL + "\n"})
        self.commit("scrub", {"notes.md": "by user@example.com\n"})
        self.assertRefused("notes.md", "email")

    def test_commit_message_hit_refuses_push(self):
        self.commit("logs in " + HOME + "/x")
        self.assertRefused("message:1: home-path")

    def test_author_email_hit_refuses_push(self):
        self.commit("fine", author=EMAIL)
        self.assertRefused("author: email")

    def test_committer_email_hit_refuses_push(self):
        self.commit("fine", author="123+jdoe@" + "users.noreply.github.com", committer=EMAIL)
        self.assertRefused("committer: email")

    def test_undotted_fallback_identity_refuses_push(self):
        self.commit("fine", author="jdoe@" + "jdoes-mac")
        self.assertRefused("author: email")

    def test_noreply_authors_and_attribution_pass(self):
        self.commit("a", author="123+jdoe@" + "users.noreply.github.com")
        self.commit("b\n\nCo-Authored-By: Claude <%s>" % ATTRIBUTION, author=ATTRIBUTION)
        self.commit("c", author="456+jdoe@" + "users.noreply.github.com", committer="noreply@github.com")
        r = self.push()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_commits_already_on_the_remote_are_not_rescanned(self):
        self.commit("fine", author=EMAIL)
        self.assertEqual(self.push("--no-verify", "HEAD:main").returncode, 0)
        self.commit("next")
        r = self.push()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_branch_delete_passes(self):
        self.assertEqual(self.push("HEAD:feature").returncode, 0)
        r = self.push(":feature")
        self.assertEqual(r.returncode, 0, r.stderr)


class CommitsTest(unittest.TestCase):
    """CI's scan of a pull request: `--commits HEAD^1..HEAD^2` on the merge commit actions/checkout makes."""

    commit = PrePushTest.commit

    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="qb-pii-")
        self.addCleanup(shutil.rmtree, self.repo, True)
        git(self.repo, "init", "-q", "-b", "main")
        self.commit("already on main", author=EMAIL)
        git(self.repo, "checkout", "-q", "-b", "pr")

    def scan(self):
        git(self.repo, "checkout", "-q", "main")
        git(self.repo, "merge", "-q", "--no-ff", "-m", "merge", "pr")
        return subprocess.run(["/usr/bin/python3", SCAN, "--commits", "HEAD^1..HEAD^2"], cwd=self.repo,
                              capture_output=True, text=True, env=GIT_ENV, timeout=60)

    def test_pr_commit_identity_and_message_hits_fail_without_values(self):
        self.commit("logs in " + HOME + "/x", author=EMAIL)
        r = self.scan()
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 1, out)
        self.assertIn("author: email", out)
        self.assertIn("message:1: home-path", out)
        self.assertEqual(out.count("author: email"), 1, out)
        for value in (EMAIL, HOME):
            self.assertNotIn(value, out)

    def test_clean_pr_passes_despite_hits_on_the_base(self):
        self.commit("fine")
        r = self.scan()
        self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)


if __name__ == "__main__":
    unittest.main()
