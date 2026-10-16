"""Behaviour tests for plugin/skills/setup/scripts/merge_settings.py.

Run from anywhere:  python3 -I -B tests/plugin/test_merge.py [python-to-test]
(`bun run test:plugin` runs it.) Everything happens in a fresh temp directory with CLAUDE_CONFIG_DIR
pointed inside it, so your real ~/.claude is never touched. Exits 1 when any check fails.
"""
import atexit, json, os, shlex, stat, subprocess, sys, tempfile, importlib.util, shutil
sys.dont_write_bytecode = True   # never leave __pycache__ inside plugin/ (its content is hashed at build time)
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
M = os.path.join(REPO, "plugin", "skills", "setup", "scripts", "merge_settings.py")
PY = sys.argv[1] if len(sys.argv) > 1 else sys.executable
# The temp dir must not be inside a git repository: merge_settings refuses backup dirs there.
root = tempfile.mkdtemp(prefix="ainative-merge-test-")
atexit.register(shutil.rmtree, root, True)
cfg = os.path.join(root, "cfg")
env = dict(os.environ, CLAUDE_CONFIG_DIR=cfg, PYTHONDONTWRITEBYTECODE="1")
results = []
def check(name, cond, detail=""):
    results.append((name, bool(cond))); print(("PASS " if cond else "FAIL ") + name + ((" | " + detail) if detail and not cond else ""))
def run(args, stdin=None):
    p = subprocess.run([PY, M] + args, capture_output=True, text=True, env=env, input=stdin)
    return p.returncode, p.stdout + p.stderr
def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f: f.write(text)
def read(path):
    with open(path, encoding="utf-8") as f: return f.read()

SECRET = "sk-live-DEMO0000secretvalue9999"
base = {"env": {"ANTHROPIC_AUTH_TOKEN": SECRET, "PLAIN": "visible-but-redacted"},
        "permissions": {"allow": ["Bash(ls *)"], "defaultMode": "acceptEdits"},
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "client --token demo-secret-123"}]}]},
        "model": "opus", "note": "说明：中文内容"}
t = os.path.join(root, "proj it's", ".claude", "settings.json")   # path with a single quote
write(t, json.dumps(base, indent=4, ensure_ascii=False))
orig = read(t)
patch = {"permissions": {"deny": ["Bash(rm -rf ~)"], "defaultMode": "default"}, "model": "sonnet",
         "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "curl -u alice:demo-pass https://example.com"}]}]}}  # gitleaks:allow (fake credential, checks redaction)
pj = json.dumps(patch)

# 1 help
code, out = run(["--help"]); check("help exits 0 and mentions --expect-plan", code == 0 and "--expect-plan" in out)
# 2 dry-run: no secrets in text or json output; file untouched
code, out = run(["--target", t, "--patch-json", pj, "--dry-run"])
check("dry-run exit 0", code == 0, out[-300:])
check("dry-run text hides env secret", SECRET not in out and "visible-but-redacted" not in out)
check("dry-run text hides existing hook token", "demo-secret-123" not in out)
check("dry-run text redacts new hook credentials", "alice:demo-pass" not in out)
check("dry-run lists conflicts with JSON pointers", "/permissions/defaultMode" in out and "/model" in out)
code, js = run(["--target", t, "--patch-json", pj, "--dry-run", "--json"])
rep = json.loads(js)
check("json report hides secrets", SECRET not in js and "demo-secret-123" not in js and "alice:demo-pass" not in js)
pid_keep = rep["plan_id"]
check("file untouched after dry-run", read(t) == orig)
# 3 write without / with wrong plan id is refused
code, out = run(["--target", t, "--patch-json", pj]); check("write without --expect-plan refused (exit 4)", code == 4, out[-200:])
code, out = run(["--target", t, "--patch-json", pj, "--expect-plan", "deadbeefdeadbeef"]); check("wrong plan id refused", code == 4)
check("file still untouched", read(t) == orig)
# 4 per-path overwrite: authorize only /permissions/defaultMode
code, js = run(["--target", t, "--patch-json", pj, "--overwrite", "/permissions/defaultMode", "--dry-run", "--json"])
rep2 = json.loads(js); pid_ow = rep2["plan_id"]
ops = {c["path"]: c["op"] for c in rep2["changes"]}
check("overwrite only the authorized path", ops.get("/permissions/defaultMode") == "replace" and ops.get("/model") == "conflict_kept", str(ops))
check("plan id changes with --overwrite", pid_ow != pid_keep)
code, out = run(["--target", t, "--patch-json", pj, "--overwrite", "/permissions/defaultMode", "--expect-plan", pid_keep])
check("plan id from a different dry-run refused", code == 4)
code, out = run(["--target", t, "--patch-json", pj, "--overwrite", "/permissions/defaultMode", "--expect-plan", pid_ow])
check("write with matching plan id succeeds", code == 0, out[-400:])
new = json.loads(read(t))
check("authorized value replaced, other conflict kept", new["permissions"]["defaultMode"] == "default" and new["model"] == "opus")
check("existing secrets preserved in file", new["env"]["ANTHROPIC_AUTH_TOKEN"] == SECRET and new["hooks"]["Stop"][0]["hooks"][0]["command"].endswith("demo-secret-123"))
check("chinese not escaped", "说明：中文内容" in read(t))
check("write output hides secrets", SECRET not in out and "demo-secret-123" not in out)
# 5 backup location and modes, undo command quoting
bdir = os.path.join(cfg, "backups", "ainative")
files = os.listdir(bdir) if os.path.isdir(bdir) else []
check("backup outside repo in config dir", len(files) == 1 and not os.path.exists(t + ".bak"), str(files))
if files:
    bpath = os.path.join(bdir, files[0])
    check("backup dir mode 0700", stat.S_IMODE(os.stat(bdir).st_mode) == 0o700, oct(os.stat(bdir).st_mode))
    check("backup file mode 0600", stat.S_IMODE(os.stat(bpath).st_mode) == 0o600)
    check("backup bytes equal original", read(bpath) == orig)
undo_line = [l for l in out.splitlines() if l.startswith("undo:")][0][len("undo:"):].strip()
toks = shlex.split(undo_line)
check("undo is cp -- <backup> <target> with safe quoting", toks[:2] == ["cp", "--"] and toks[3] == os.path.realpath(t), str(toks))
subprocess.run(["sh", "-c", undo_line], check=True)
check("running the undo command restores the original", read(t) == orig)
# 6 idempotent re-run
code, js = run(["--target", t, "--patch-json", pj, "--dry-run", "--json"]); pid = json.loads(js)["plan_id"]
run(["--target", t, "--patch-json", pj, "--expect-plan", pid])
code, out = run(["--target", t, "--patch-json", pj, "--dry-run"])
check("second run has nothing to change", "no effective change" in out)
# 7 strict JSON: NaN, Infinity, 1e999, duplicate keys, wrong types
for label, ptxt in [("NaN", '{"x": NaN}'), ("Infinity", '{"x": Infinity}'), ("1e999", '{"x": 1e999}'),
                    ("duplicate key", '{"permissions": {"deny": ["a"]}, "permissions": {"deny": ["b"]}}'),
                    ("deny wrong type", '{"permissions": {"deny": "wrong-type"}}'),
                    ("enabledPlugins non-bool", '{"enabledPlugins": {"a@b": "yes"}}'),
                    ("skillOverrides bad value", '{"skillOverrides": {"x": "maybe"}}'),
                    ("hook without command", '{"hooks": {"Stop": [{"hooks": [{"type": "command"}]}]}}')]:
    code, out = run(["--target", t, "--patch-json", ptxt, "--dry-run"])
    check("patch rejected: " + label, code == 1, out[-200:])
bad = os.path.join(root, "bad.json")
for label, txt in [("existing NaN", '{"a": NaN}'), ("existing duplicate", '{"a": 1, "a": 2}'),
                   ("existing wrong type", '{"permissions": {"deny": "wrong-type"}}')]:
    write(bad, txt); code, out = run(["--target", bad, "--patch-json", '{"model": "x"}', "--dry-run"])
    check("existing file rejected: " + label, code == 2 and read(bad) == txt, out[-200:])
# 8 file changed between dry-run and apply -> plan mismatch, nothing written
c2 = os.path.join(root, "c2.json"); write(c2, '{"model": "opus"}')
code, js = run(["--target", c2, "--patch-json", '{"permissions": {"deny": ["Bash(rm -rf /)"]}}', "--dry-run", "--json"]); pid = json.loads(js)["plan_id"]
write(c2, '{"model": "opus", "user_edit": true}')
code, out = run(["--target", c2, "--patch-json", '{"permissions": {"deny": ["Bash(rm -rf /)"]}}', "--expect-plan", pid])
check("changed after dry-run: refused, user edit kept", code == 4 and json.loads(read(c2)).get("user_edit") is True, out[-200:])
# 9 race: file modified right before the swap -> exit 5, nothing restored, user edit kept
spec = importlib.util.spec_from_file_location("ms", M); ms = importlib.util.module_from_spec(spec); spec.loader.exec_module(ms)
os.environ["CLAUDE_CONFIG_DIR"] = cfg
c3 = os.path.join(root, "c3.json"); write(c3, '{"model": "opus"}')
args = ["--target", c3, "--patch-json", '{"permissions": {"deny": ["Bash(rm -rf /)"]}}']
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf): ms.main(args + ["--dry-run", "--json"])
pid = json.loads(buf.getvalue())["plan_id"]
real_mkstemp = ms.tempfile.mkstemp
def racing_mkstemp(*a, **k):
    r = real_mkstemp(*a, **k); write(c3, '{"model": "opus", "concurrent": 1}'); return r
ms.tempfile.mkstemp = racing_mkstemp
buf = io.StringIO()
with contextlib.redirect_stdout(buf): rc = ms.main(args + ["--expect-plan", pid])
ms.tempfile.mkstemp = real_mkstemp
check("race before swap: exit 5, concurrent edit kept, no restore", rc == 5 and json.loads(read(c3)).get("concurrent") == 1, buf.getvalue()[-300:])
check("race: no temp files left", not [f for f in os.listdir(root) if f.startswith(".ainative-")])
# 10 managed paths refused (logical, drop-in, symlinked)
for tgt in ["/Library/Application Support/ClaudeCode/managed-settings.json", "/etc/claude-code/managed-settings.d/x.json"]:
    code, out = run(["--target", tgt, "--patch-json", '{"model": "x"}', "--dry-run"]); check("managed refused: " + tgt, code == 1 and "managed" in out)
link = os.path.join(root, "sneaky"); os.symlink("/Library/Application Support/ClaudeCode", link)
code, out = run(["--target", os.path.join(link, "anything.json"), "--patch-json", '{"model": "x"}', "--dry-run"])
check("managed refused through a symlinked directory", code == 1 and "managed" in out, out[-200:])
# 11 symlinked settings file is written through; new file creation; --scope user uses CLAUDE_CONFIG_DIR
real_file = os.path.join(root, "dot", "real.json"); write(real_file, '{"model": "opus"}')
ln = os.path.join(root, "link.json"); os.symlink(real_file, ln)
code, js = run(["--target", ln, "--patch-json", '{"permissions": {"deny": ["Bash(rm -rf /)"]}}', "--dry-run", "--json"]); pid = json.loads(js)["plan_id"]
code, out = run(["--target", ln, "--patch-json", '{"permissions": {"deny": ["Bash(rm -rf /)"]}}', "--expect-plan", pid])
check("symlink kept and real file updated", code == 0 and os.path.islink(ln) and "deny" in read(real_file))
code, js = run(["--scope", "user", "--patch-json", '{"permissions": {"deny": ["Bash(rm -rf ~)"]}}', "--dry-run", "--json"])
check("--scope user resolves inside CLAUDE_CONFIG_DIR", json.loads(js)["target"].startswith(cfg) or cfg in json.loads(js)["target"].replace("~", os.path.expanduser("~")))
pid = json.loads(js)["plan_id"]
code, out = run(["--scope", "user", "--patch-json", '{"permissions": {"deny": ["Bash(rm -rf ~)"]}}', "--expect-plan", pid])
check("new file created with undo rm", code == 0 and os.path.exists(os.path.join(cfg, "settings.json")) and "rm --" in out)
check("real ~/.claude/settings.json not targeted", os.path.realpath(os.path.join(cfg, "settings.json")) != os.path.realpath(os.path.expanduser("~/.claude/settings.json")))

# ---- recheck round: Codex reproductions
# R1 plan id: ["/a\n/b"] vs ["/a","/b"] must differ; duplicates and order don't matter
r1 = os.path.join(root, "r1.json"); write(r1, '{"model": "opus"}')
def pid_of(args):
    code, js = run(["--target", r1, "--patch-json", '{"permissions": {"deny": ["Bash(rm -rf /)"]}}', "--dry-run", "--json"] + args)
    return json.loads(js)["plan_id"]
check("R1 plan id: newline-joined pointer differs from two pointers", pid_of(["--overwrite", "/a\n/b"]) != pid_of(["--overwrite", "/a", "--overwrite", "/b"]))
check("R1 plan id: order and duplicates of --overwrite don't matter", pid_of(["--overwrite", "/b", "--overwrite", "/a", "--overwrite", "/a"]) == pid_of(["--overwrite", "/a", "--overwrite", "/b"]))
# R2 backup dir is bound to the plan
code, js = run(["--target", r1, "--patch-json", '{"permissions": {"deny": ["Bash(rm -rf /)"]}}', "--dry-run", "--json"])
rep = json.loads(js); pid = rep["plan_id"]
check("R2 dry-run reports the backup dir", rep.get("backup_dir", "").endswith("backups/ainative"), rep.get("backup_dir"))
other = os.path.join(root, "other-backups")
code, out = run(["--target", r1, "--patch-json", '{"permissions": {"deny": ["Bash(rm -rf /)"]}}', "--backup-dir", other, "--expect-plan", pid])
check("R2 switching --backup-dir after the dry-run is refused", code == 4 and not os.path.exists(other), out[-200:])
# R3 backup dir inside a git repository is refused (simulated repo: a directory with a .git folder)
repo = os.path.join(root, "somerepo"); os.makedirs(os.path.join(repo, ".git"))
code, out = run(["--target", r1, "--patch-json", '{"permissions": {"deny": ["Bash(rm -rf /)"]}}', "--backup-dir", os.path.join(repo, "bk"), "--dry-run"])
check("R3 --backup-dir inside a git repo refused at dry-run", code == 1 and "git repository" in out, out[-200:])
env_saved = dict(env); env["CLAUDE_CONFIG_DIR"] = os.path.join(repo, ".claude-config")
code, out = run(["--target", r1, "--patch-json", '{"permissions": {"deny": ["Bash(rm -rf /)"]}}', "--dry-run"])
check("R3 CLAUDE_CONFIG_DIR inside a git repo refused with a hint", code == 1 and "CLAUDE_CONFIG_DIR" in out, out[-250:])
newf = os.path.join(root, "brand-new.json")
code, out = run(["--target", newf, "--patch-json", '{"model": "x"}', "--dry-run"])
check("R3 new file (no backup needed) is not refused", code == 0, out[-200:])
env.clear(); env.update(env_saved)
# R4 warnings never echo values
r4 = os.path.join(root, "r4.json"); write(r4, '{"permissions": {"defaultMode": "sk-demoSecret123456"}}')
code, js = run(["--target", r4, "--patch-json", '{"model": "x"}', "--dry-run", "--json"])
check("R4 unknown defaultMode reported without its value", code == 0 and "sk-demoSecret123456" not in js and "defaultMode" in js, js[-300:])
# R5 malformed structures become validation errors, not crashes
for label, ptxt in [("skillOverrides value is an object", '{"skillOverrides": {"demo": {}}}'),
                    ("http hook url is a number", '{"hooks": {"Stop": [{"hooks": [{"type": "http", "url": 123}]}]}}'),
                    ("hook command is a list", '{"hooks": {"Stop": [{"hooks": [{"type": "command", "command": ["a"]}]}]}}'),
                    ("groups is an object", '{"hooks": {"Stop": {"hooks": []}}}')]:
    code, out = run(["--target", r1, "--patch-json", ptxt, "--dry-run"])
    check("R5 rejected cleanly: " + label, code == 1 and "Traceback" not in out and "invalid patch" in out, out[-200:])
# R6 execution checks the plan id before deciding there is nothing to do
r6 = os.path.join(root, "r6.json"); write(r6, '{"model": "opus"}')
P6 = '{"permissions": {"deny": ["Bash(rm -rf /)"]}}'
code, js = run(["--target", r6, "--patch-json", P6, "--dry-run", "--json"]); stale = json.loads(js)["plan_id"]
write(r6, '{"model": "opus", "permissions": {"deny": ["Bash(rm -rf /)"]}}')   # now the patch is a no-op
code, out = run(["--target", r6, "--patch-json", P6, "--expect-plan", stale])
check("R6 stale plan id refused even when nothing would change", code == 4, out[-200:])
code, out = run(["--target", r6, "--patch-json", P6])
check("R6 missing --expect-plan refused even when nothing would change", code == 4)
code, js = run(["--target", r6, "--patch-json", P6, "--dry-run", "--json"]); fresh = json.loads(js)["plan_id"]
code, out = run(["--target", r6, "--patch-json", P6, "--expect-plan", fresh])
check("R6 matching plan id with nothing to change exits 0 without writing", code == 0 and "nothing written" in out)
# R7 unexpected internal errors are reported, not raised
real_merge = ms.merge
def boom(*a, **k): raise TypeError("synthetic")
ms.merge = boom
buf = io.StringIO()
with contextlib.redirect_stdout(buf): rc = ms.main(["--target", r1, "--patch-json", '{"model": "y"}', "--dry-run", "--json"])
ms.merge = real_merge
check("R7 unexpected exception -> exit 3 with a JSON error, no traceback", rc == 3 and json.loads(buf.getvalue())["error"].startswith("error: unexpected TypeError"), buf.getvalue())
print("SUMMARY: %d/%d passed (%s)" % (sum(r for _, r in results), len(results), PY))
sys.exit(0 if all(r for _, r in results) else 1)
