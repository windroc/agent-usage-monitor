import json
import os
import shutil
import subprocess
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin", "agent-usage-monitor")


class Env:
    """Temp HOME, config and state dirs, and a PATH of fakes only."""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="qb-test-")
        self.home = os.path.join(self.root, "home")
        self.config = os.path.join(self.root, "config")
        self.state = os.path.join(self.root, "state")
        self.fake_bin = os.path.join(self.root, "bin")
        for d in (self.home, self.config, self.fake_bin):
            os.makedirs(d)
        self.environ = {
            "HOME": self.home,
            "XDG_CONFIG_HOME": self.config,
            "AGENT_USAGE_MONITOR_STATE_DIR": self.state,
            "PATH": self.fake_bin + ":/usr/bin:/bin",
            "LANG": "C",
        }

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def run(self, *args, input=None):
        return subprocess.run(["/usr/bin/python3", BIN] + list(args), env=self.environ, input=input,
                              capture_output=True, text=True, timeout=60)

    def mkdir(self, name):
        path = os.path.join(self.home, name)
        os.makedirs(path)
        return path

    def write_accounts(self, data):
        d = os.path.join(self.config, "agent-usage-monitor")
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, "accounts.json")
        with open(path, "w") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))
        return path

    @property
    def snapshot_path(self):
        return os.path.join(self.state, "snapshot.json")

    def snapshot(self):
        with open(self.snapshot_path) as f:
            return json.load(f)


FIXTURES = os.path.join(ROOT, "tests", "fixtures")

# Fake `codex`: behaviour comes from $CODEX_HOME/fake.json; it logs to $CODEX_HOME.
FAKE_CODEX = r'''#!/usr/bin/python3
import json, os, signal, subprocess, sys, time
home = os.environ["CODEX_HOME"]
cfg = json.load(open(os.path.join(home, "fake.json")))
def log(name, line):
    with open(os.path.join(home, name), "a") as f:
        f.write(line + "\n")
log("pids", str(os.getpid()))
log("received.jsonl", json.dumps({"argv": sys.argv[1:], "codex_home": home}))
if cfg.get("ignore_term"):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
if cfg.get("spawn_child"):
    child = subprocess.Popen([sys.executable, "-c",
        "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(600)"])
    log("pids", str(child.pid))
if "exit" in cfg:
    sys.exit(cfg["exit"])
def emit(msg, rid):
    line = msg if isinstance(msg, str) else json.dumps(dict(msg, id=rid) if msg.get("id") == "$id" else msg)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()
for line in sys.stdin:
    log("received.jsonl", line.rstrip("\n"))
    msg = json.loads(line)
    method = msg.get("method")
    if method == cfg.get("exit_after"):
        sys.exit(1)
    if method == cfg.get("hang_on"):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        sys.stdin.close()
        time.sleep(600)
    if "id" not in msg:
        continue
    default = {"initialize": [{"id": "$id", "result": {}}],
               "account/rateLimits/read": [{"id": "$id", "result": cfg.get("result")}]}
    for out in cfg.get("responses", {}).get(method, default.get(method, [])):
        emit(out, msg["id"])
'''


def window(pct, mins, at=None):
    return {"usedPercent": pct, "windowDurationMins": mins, "resetsAt": at}


def rate_limits(primary=None, secondary=None):
    return {"rateLimits": {"limitId": "codex", "primary": primary, "secondary": secondary}}


def install_fake_codex(env, codex_home, **cfg):
    path = os.path.join(env.fake_bin, "codex")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(FAKE_CODEX)
        os.chmod(path, 0o755)
    os.makedirs(codex_home, exist_ok=True)
    with open(os.path.join(codex_home, "fake.json"), "w") as f:
        json.dump(cfg, f)


def received(codex_home):
    with open(os.path.join(codex_home, "received.jsonl")) as f:
        return [json.loads(l) for l in f]


def pids(codex_home):
    with open(os.path.join(codex_home, "pids")) as f:
        return [int(l) for l in f]


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def reaped(*pids):
    # a killed orphan stays a zombie, alive to os.kill(pid, 0), until launchd reaps it
    deadline = time.monotonic() + 3
    while any(alive(p) for p in pids) and time.monotonic() < deadline:
        time.sleep(0.05)
    return not any(alive(p) for p in pids)


# Fake `claude`: behaviour comes from $HOME/fake-claude.json; it logs each call to $HOME/claude-calls.jsonl.
FAKE_CLAUDE = r'''#!/usr/bin/python3
import json, os, signal, subprocess, sys, time
home = os.environ["HOME"]
try:
    cfg = json.load(open(os.path.join(home, "fake-claude.json")))
except FileNotFoundError:
    cfg = {}
stdin = sys.stdin.buffer.read() if not sys.stdin.isatty() else b""
keys = ("PWD", "DISABLE_AUTOUPDATER", "CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN", "PATH", "HOME")
call = {"argv": sys.argv[1:], "cwd": os.getcwd(), "stdin": stdin.decode(), "pid": os.getpid(),
        "env": {k: os.environ[k] for k in keys if k in os.environ},
        "anthropic": sorted(k for k in os.environ if k.startswith("ANTHROPIC_"))}
if cfg.get("spawn_child"):
    child = subprocess.Popen([sys.executable, "-c",
        "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(600)"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    call["child"] = child.pid
if cfg.get("child_holds_stdout"):
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"], stdin=subprocess.DEVNULL)
    call["child"] = child.pid
with open(os.path.join(home, "claude-calls.jsonl"), "a") as f:
    f.write(json.dumps(call) + "\n")
if cfg.get("fail"):
    sys.exit(97)
if sys.argv[1:] == ["--version"]:
    if cfg.get("version_hang"):
        time.sleep(600)
    sys.stdout.write(cfg.get("version", "2.1.302 (Claude Code)") + "\n")
    sys.exit(cfg.get("version_exit", 0))
if sys.argv[1:3] == ["auth", "status"]:
    if cfg.get("auth_hang"):
        time.sleep(600)
    sys.stdout.write(cfg.get("auth_status", json.dumps({"loggedIn": True, "authMethod": "claude.ai"})) + "\n")
    sys.exit(cfg.get("auth_exit", 0))
if cfg.get("hang"):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    time.sleep(600)
stdout_file = cfg.get("stdout_files", {}).get(os.environ.get("CLAUDE_CONFIG_DIR", ""), cfg.get("stdout_file"))
if stdout_file:
    sys.stdout.write(open(stdout_file, encoding="utf-8").read())
sys.stdout.write(cfg.get("stdout", ""))
sys.stderr.write(cfg.get("stderr", ""))
sys.exit(cfg.get("exit", 0))
'''


def install_fake_claude(env, **cfg):
    path = os.path.join(env.fake_bin, "claude")
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write(FAKE_CLAUDE)
        os.chmod(path, 0o755)
    with open(os.path.join(env.home, "fake-claude.json"), "w") as f:
        json.dump(cfg, f)


def claude_calls(env):
    try:
        with open(os.path.join(env.home, "claude-calls.jsonl")) as f:
            return [json.loads(l) for l in f]
    except FileNotFoundError:
        return []
