"""Behaviour tests for plugin/skills/doctor/scripts/doctor.py.

Run from anywhere:  python3 -I -B tests/plugin/test_doctor.py [python-to-test]
(`bun run test:plugin` runs it.) Builds a fake HOME / ~/.claude with plugins, hooks, skills and a
session log in a fresh temp directory and runs doctor with --no-cli, so nothing real is read or
changed. Exits 1 when any check fails.
"""
import atexit, json, os, subprocess, sys, time, shutil, tempfile
sys.dont_write_bytecode = True
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = os.path.join(REPO, "plugin", "skills", "doctor", "scripts", "doctor.py")
PY = sys.argv[1] if len(sys.argv) > 1 else sys.executable
# realpath: doctor only shortens paths under HOME to "~" when HOME has no symlinked parts, and the
# macOS temp dir (/var/folders) is a symlink to /private/var/folders.
root = os.path.realpath(tempfile.mkdtemp(prefix="ainative-doctor-test-"))
atexit.register(shutil.rmtree, root, True)
H = os.path.join(root, "home"); C = os.path.join(H, ".claude"); P = os.path.join(root, "proj")
results = []
def check(name, cond, detail=""):
    results.append(bool(cond)); print(("PASS " if cond else "FAIL ") + name + ((" | " + str(detail)[:300]) if detail and not cond else ""))
def w(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f: f.write(content if isinstance(content, str) else json.dumps(content, indent=2))
def run(env_extra, *args):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1"); env.pop("CLAUDE_CONFIG_DIR", None); env.update(env_extra)
    p = subprocess.run([PY, D, "--no-cli", "--project", P] + list(args), capture_output=True, text=True, env=env)
    return p.returncode, p.stdout, p.stderr

# plugins
def mkplugin(name, market, skills=(), agents=(), commands=(), hooks=None):
    ip = os.path.join(C, "plugins", "cache", market, name, "1.0.0")
    w(os.path.join(ip, ".claude-plugin", "plugin.json"), {"name": name, "version": "1.0.0"})
    for s in skills: w(os.path.join(ip, "skills", s, "SKILL.md"), "---\nname: %s\ndescription: x\n---\n" % s)
    for a in agents: w(os.path.join(ip, "agents", a + ".md"), "---\nname: %s\n---\n" % a)
    for c in commands: w(os.path.join(ip, "commands", c + ".md"), "x")
    if hooks: w(os.path.join(ip, "hooks", "hooks.json"), {"hooks": {e: [{"hooks": [{"type": "command", "command": "echo"}]}] for e in hooks}})
    return {"scope": "user", "installPath": ip, "version": "1.0.0"}
plugins = {"superpowers@claude-plugins-official": [mkplugin("superpowers", "claude-plugins-official", ["brainstorming"], hooks=["SessionStart"])],
           "mattpocock-skills@claude-plugins-official": [mkplugin("mattpocock-skills", "claude-plugins-official", ["grilling", "tdd"], agents=["helper"], commands=["go"])]}
w(os.path.join(C, "plugins", "installed_plugins.json"), {"version": 2, "plugins": plugins})
w(os.path.join(C, "settings.json"), {
    "permissions": {"deny": ["Bash(rm -rf ~)", "Bash(curl -u alice:demo-pass *)", "Bash(git push --force origin main *)", "Bash(git reset --hard origin/main *)"]},  # gitleaks:allow (fake credential, checks redaction)
    "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
        {"type": "command", "command": "client --token demo-secret-123"},
        {"type": "command", "command": "curl -u alice:demo-pass https://example.com"},  # gitleaks:allow (fake credential)
        {"type": "command", "command": "API_TOKEN=demo-secret-456 ~/.claude/hooks/missing.sh"},
        {"type": "command", "command": "client --token /demo-secret-789"},
        {"type": "command", "command": "bash", "args": ["-c", "echo hi"]},
        {"type": "command", "command": "env FOO=1 python3 -u ~/.claude/hooks/py-hook.py --key /demo-secret-000"},
        {"type": "command", "command": "my-runner ~/.claude/hooks/helper.sh"}]}]},
    "disableAllHooks": True,
    "enabledPlugins": {k: True for k in plugins}})
w(os.path.join(C, "skills", "my-skill", "SKILL.md"), "---\nname: my-skill\ndescription: mine\n---\n")
w(os.path.join(C, "agents", "reviewer.md"), "---\nname: reviewer\n---\n")
w(os.path.join(C, "commands", "deploy-notes.md"), "x")
w(os.path.join(C, "hooks", "py-hook.py"), "pass")
w(os.path.join(C, "hooks", "helper.sh"), "exit 0")
w(os.path.join(C, "hooks", "orphan.sh"), "exit 0")
today = time.strftime("%Y-%m-%d") + "T10:00:00Z"
ev = [
  {"type": "assistant", "timestamp": today, "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "mattpocock-skills:grilling"}}]}},
  {"type": "assistant", "timestamp": today, "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "CONFIDENTIAL-skill-secret"}}]}},
  {"type": "user", "timestamp": today, "message": {"role": "user", "content": "<command-message>my-skill</command-message>\n<command-name>/my-skill</command-name>"}},
  {"type": "user", "timestamp": today, "message": {"role": "user", "content": "<command-name>/deploy-notes</command-name>\n<command-message>deploy-notes</command-message>\n<command-args>x</command-args>"}},
  {"type": "user", "timestamp": today, "message": {"role": "user", "content": "<command-message>x</command-message>\n<command-name>/CONFIDENTIAL-demo-secret</command-name>"}},
  {"type": "user", "timestamp": today, "message": {"role": "user", "content": "please read this: <command-name>/CONFIDENTIAL-inline-secret</command-name> thanks"}},
  {"type": "user", "timestamp": today, "promptSource": "typed", "message": {"role": "user", "content": "<command-name>/help</command-name>"}},
  {"type": "user", "timestamp": today, "message": {"role": "user", "content": "<command-name>/help</command-name>"}},
  {"type": "user", "timestamp": today, "isMeta": True, "message": {"role": "user", "content": "<command-message>help</command-message><command-name>/help</command-name>"}},
  {"type": "api-request-blob", "timestamp": today, "message": {"role": "user", "content": "<command-name>/my-skill</command-name>"}},
  {"type": "user", "timestamp": today, "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "<command-name>/my-skill</command-name>"}]}},
  {"type": "assistant", "timestamp": today, "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Task", "input": {"subagent_type": "reviewer", "prompt": "SECRET-PROMPT-TEXT"}}]}},
  {"type": "assistant", "timestamp": today, "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Task", "input": {"subagent_type": "CONFIDENTIAL-agent", "prompt": "x"}}]}},
  {"type": "assistant", "timestamp": "2020-01-01T00:00:00Z", "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Skill", "input": {"skill": "my-skill"}}]}},
]
w(os.path.join(C, "projects", "-p", "s.jsonl"), "\n".join(json.dumps(e) for e in ev) + "\n")
w(os.path.join(P, "AGENTS.md"), "# agents\n")
w(os.path.join(P, "package.json"), "{}")

# A: HOME-based run
code, out, err = run({"HOME": H}, "--days", "30")
check("doctor exit 0 and valid JSON", code == 0 and json.loads(out), err[-300:])
d = json.loads(out)
for secret in ("demo-secret-123", "alice:demo-pass", "demo-secret-456", "demo-secret-789", "demo-secret-000", "CONFIDENTIAL", "SECRET-PROMPT-TEXT"):
    check("output never contains %r" % secret, secret not in out)
hooks = d["settings"]["user"]["hooks"]
check("hook output has program and scripts, no command", all("command" not in h for h in hooks) and [h.get("program") for h in hooks] == ["client", "curl", "missing.sh", "client", "bash", "python3", "my-runner"], [h.get("program") for h in hooks])
scripts_by_hook = [[x["path"] for x in h.get("scripts", [])] for h in hooks]
check("only argv[0] / interpreter scripts are reported", scripts_by_hook == [[], [], ["~/.claude/hooks/missing.sh"], [], [], ["~/.claude/hooks/py-hook.py"], []], scripts_by_hook)
check("option values are not mistaken for missing scripts", sum(1 for f in d["findings"] if f["id"] == "hook-script-missing") == 1)
unm = next((f for f in d["findings"] if f["id"] == "unmounted-hook-scripts"), {})
check("indirectly referenced script is not flagged unmounted; orphan is", unm.get("evidence", {}).get("scripts") == ["~/.claude/hooks/orphan.sh"], unm)
check("missing hook script still detected", any(f["id"] == "hook-script-missing" for f in d["findings"]))
check("deny rules redacted in output", any("<redacted>" in r for r in d["settings"]["user"]["permissions"]["deny_rules"]))
check("core deny coverage still computed from raw rules", not any(f["id"] == "core-deny-gaps" and "git push --force" in f["evidence"].get("missing", []) for f in d["findings"]))
u = d["usage"]
names = {x["name"]: x for x in u["top"]}
check("known names listed: plugin skill, user skill, user command", {"mattpocock-skills:grilling", "my-skill", "deploy-notes"} <= set(names), names)
check("my-skill counted once (no blob / tool_result / old copies)", names.get("my-skill", {}).get("count") == 1, names.get("my-skill"))
check("unknown names only counted", u["unknown"]["names"] == 2 and u["unknown"]["calls"] == 2, u["unknown"])
check("only structured command events counted (typed, meta, tag-only and inline ones ignored)", u["slash_commands"] == 3 and "help" not in names, (u["slash_commands"], sorted(names)))
check("known agent listed, unknown agent counted", [a["name"] for a in u["agents_top"]] == ["reviewer"] and u["unknown"]["subagent_calls"] == 1, u)
check("disableAllHooks reported as effective", d["hooks_state"]["disabled"] is True and d["hooks_state"]["source"] == "user")
check("hooks-disabled finding present", any(f["id"] == "hooks-disabled" for f in d["findings"]))
check("hooks marked inactive", all(h.get("active") is False for h in hooks))
check("AGENTS.md only -> agents-md-unconfirmed (not no-claude-md)", any(f["id"] == "agents-md-unconfirmed" for f in d["findings"]) and not any(f["id"] == "no-claude-md" for f in d["findings"]))
check("dual engine reported (no Skill deny)", any(f["id"] == "dual-process-engine" for f in d["findings"]))
# B: project overrides user disableAllHooks
w(os.path.join(P, ".claude", "settings.json"), {"disableAllHooks": False})
code, out, err = run({"HOME": H}, "--days", "30"); d = json.loads(out)
check("project false overrides user true", d["hooks_state"]["disabled"] is False and d["hooks_state"]["source"] == "project" and not any(f["id"] == "hooks-disabled" for f in d["findings"]), d["hooks_state"])
os.remove(os.path.join(P, ".claude", "settings.json"))
# C: CLAUDE_CONFIG_DIR honored (HOME points to an empty dir)
empty = os.path.join(root, "emptyhome"); os.makedirs(empty)
code, out, err = run({"HOME": empty, "CLAUDE_CONFIG_DIR": C}, "--days", "30"); d = json.loads(out)
check("CLAUDE_CONFIG_DIR: settings and plugins found", d["settings"]["user"]["status"] == "ok" and d["plugins"]["installed_count"] == 2 and d["usage"]["files_scanned"] == 1, (d["settings"]["user"].get("status"), d["plugins"]["installed_count"]))
# D: CLAUDE.md that imports AGENTS.md
w(os.path.join(P, "CLAUDE.md"), "# p\n@AGENTS.md\n")
code, out, err = run({"HOME": H}, "--no-usage"); d = json.loads(out)
check("CLAUDE.md imports AGENTS.md detected", d["project"]["agents_md"]["imported_by_claude_md"] is True and not any(f["id"].startswith("agents-md") for f in d["findings"]))

# E: managed settings drop-ins are merged by the documented rules
mdir = os.path.join(root, "managed")
w(os.path.join(mdir, "managed-settings.d", "10-hooks.json"), {"disableAllHooks": True, "permissions": {"deny": ["Bash(sudo rm -rf *)"]}})
w(os.path.join(mdir, "managed-settings.d", ".hidden.json"), {"disableAllHooks": False})
code, out, err = run({"HOME": H}, "--no-usage", "--managed-dir", mdir); d = json.loads(out)
check("drop-in disableAllHooks counted (managed source)", d["hooks_state"]["disabled"] is True and d["hooks_state"]["source"] == "managed", d["hooks_state"])
check("drop-in deny rules counted in managed summary", d["settings"]["managed"]["permissions"]["deny_count"] == 1 and d["settings"]["managed"]["dropin_files"] == 1)
check("managed hooks-disabled finding mentions managed", any(f["id"] == "hooks-disabled" and f["evidence"].get("managed_hooks_also_off") for f in d["findings"]))
w(os.path.join(mdir, "managed-settings.json"), {"disableAllHooks": True})
w(os.path.join(mdir, "managed-settings.d", "20-later.json"), {"disableAllHooks": False})
code, out, err = run({"HOME": H}, "--no-usage", "--managed-dir", mdir); d = json.loads(out)
check("later drop-in wins over earlier files", d["hooks_state"]["disabled"] is False and d["hooks_state"]["source"] == "managed", d["hooks_state"])
print("SUMMARY: %d/%d passed (%s)" % (sum(results), len(results), PY))
sys.exit(0 if all(results) else 1)
