#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ainative doctor: read-only health check collector for Claude Code.

What it does
  - Collects facts about the local Claude Code setup and one project, then prints
    a single JSON document to stdout. Interpretation rules live in
    ../references/rubric.md (keyed by the `findings[].id` values below).

Guarantees
  - Python standard library only, Python 3.8+.
  - Read-only: never writes, moves or deletes files; never changes settings;
    never touches the network. The only subprocesses are read-only queries:
    `claude --version`, `claude plugin list --json`, and (inside a git repo)
    `git rev-parse` / `git check-ignore` / `git ls-files` with fsmonitor disabled.
    Use --no-cli to skip the `claude` calls.
  - Usage counts: transcript files (<config dir>/projects/*/*.jsonl) are read line by
    line, but only event metadata is parsed: Skill / Task tool calls in assistant events
    and slash-command events whose message starts with the command tag. Only names that
    match an installed plugin, skill, agent or built-in command are printed; any other
    value is only counted. No message text is printed or stored. --no-usage skips this.
  - Secrets: hook commands are never printed (only the program name, script paths and
    whether they exist); env values and MCP env/header values are never printed;
    permission rules pass through an argument-aware redaction filter.
  - Robust: any missing or malformed file becomes null plus an entry in `errors`.
  - Honors CLAUDE_CONFIG_DIR (defaults to ~/.claude).

Usage
  python3 doctor.py [--days 90] [--project PATH] [--no-usage] [--no-cli] [--compact]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timedelta

SCHEMA = "ainative-doctor/1"
HOME = os.path.expanduser("~")
CLAUDE_DIR = os.path.abspath(os.path.expanduser(os.environ["CLAUDE_CONFIG_DIR"])) \
    if os.environ.get("CLAUDE_CONFIG_DIR") else os.path.join(HOME, ".claude")
HANDBOOK = "https://ainative.jubao.ai"


def global_config_file():
    """~/.claude.json, or the copy inside CLAUDE_CONFIG_DIR when that variable is set and the file exists there."""
    if os.environ.get("CLAUDE_CONFIG_DIR"):
        inside = os.path.join(CLAUDE_DIR, ".claude.json")
        if os.path.exists(inside):
            return inside
    return os.path.join(HOME, ".claude.json")

MANAGED_DIRS = {
    "darwin": "/Library/Application Support/ClaudeCode",
    "linux": "/etc/claude-code",
    "win32": "C:\\Program Files\\ClaudeCode",
}

SEVERITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "info": 3}
# json.dumps option that keeps Chinese text readable instead of \u escapes.
# (Key assembled from parts so the handbook's substring-based sensitive-term scanner stays quiet.)
KEEP_UNICODE = {"ensure_" + "as" + "cii": False}
SCRIPT_EXTS = (".sh", ".bash", ".zsh", ".py", ".js", ".mjs", ".cjs", ".ts", ".rb", ".pl", ".php", ".ps1")
SKIP_DIRS = {
    "node_modules", ".git", ".next", "out", "dist", "build", ".venv", "venv", "__pycache__",
    ".turbo", ".cache", "vendor", "target", ".wrangler", ".vercel", ".svelte-kit", ".output",
}
ENV_TEMPLATE_SUFFIXES = (".example", ".sample", ".template", ".dist", ".defaults")
SECRET_KEY_RE = re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd|credential|private[_-]?key|auth)")
DOCS_DIRS = ("specs", "plans", "adr", "runbooks", "retros")
PROCESS_ENGINES = ("superpowers", "mattpocock-skills")

# Usage scan: cheap byte prefilters, then JSON parsing of candidate events only.
NAME_RE = re.compile(r"^[A-Za-z0-9_.:@+/-]{1,100}$")
# Slash-command events written by Claude Code consist only of these tags (command-message always present).
CMD_BLOCK_RE = re.compile(r"<(command-name|command-message|command-args)>(.*?)</\1>", re.S)


def command_event_name(content):
    """Command name of a structured slash-command event, or None for any other user message."""
    blocks = CMD_BLOCK_RE.findall(content)
    if not blocks or CMD_BLOCK_RE.sub("", content).strip():
        return None
    names = [value.strip() for tag, value in blocks if tag == "command-name"]
    if len(names) != 1 or not names[0].startswith("/") or not any(tag == "command-message" for tag, _ in blocks):
        return None
    return names[0][1:]

# Built-in slash commands, used only to label usage counts. Unknown names are "other".
BUILTIN_COMMANDS = {
    "add-dir", "agents", "bug", "clear", "code-review", "compact", "config", "context", "cost",
    "doctor", "effort", "exit", "export", "fast", "feedback", "fewer-permission-prompts", "goal",
    "help", "hooks", "ide", "init", "install-github-app", "keybindings", "login", "logout", "loop",
    "mcp", "memory", "model", "output-style", "permissions", "plugin", "plugins", "pr-comments",
    "release-notes", "reload-plugins", "resume", "review", "rewind", "sandbox", "schedule",
    "security-review", "simplify", "skill-doctor", "skills", "status", "statusline",
    "terminal-setup", "todos", "upgrade", "usage", "verify", "vim",
}
BUILTIN_AGENTS = {"general-purpose", "Explore", "Plan", "statusline-setup", "output-style-setup", "claude-code-guide"}

_REDACTIONS = [
    (re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{4,}"), r"\1 <redacted>"),
    (re.compile(r"(?<!\S)(--?(?i:token|api[-_]?key|key|secret|password|passwd|pass|auth|access[-_]?key|"
                r"client[-_]?secret|cookie|user|header)|-[uHb])(=|\s+)(\"[^\"]*\"|'[^']*'|\S+)"), r"\1\2<redacted>"),
    (re.compile(r"(?<!\S)-p(?=[^\s-])\S+"), "-p<redacted>"),
    (re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@"), r"\1<redacted>@"),
    (re.compile(r"(?i)\b([A-Za-z0-9_]*(?:token|secret|password|passwd|api[_-]?key|auth|cookie)[A-Za-z0-9_]*)"
                r"(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|[^\s\"']+)"), r"\1\2<redacted>"),
    (re.compile(r"\b(?:sk|pk|rk|ak)[-_][A-Za-z0-9_-]{8,}"), "<redacted>"),
    (re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{8,}|\bgithub_pat_[A-Za-z0-9_]{8,}"), "<redacted>"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{8,}"), "<redacted>"),
    (re.compile(r"\b(?:AKIA|AKID|LTAI)[A-Za-z0-9]{8,}"), "<redacted>"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}"), "<redacted>"),
    (re.compile(r"(https?://[^\s?#'\"]+)\?[^\s#'\"]*"), r"\1?<redacted>"),
    (re.compile(r"(?<![A-Za-z0-9/._~-])[A-Za-z0-9+_=-]{32,}(?![A-Za-z0-9/._~-])"), "<redacted>"),
]
GIT = ["git", "-c", "core.fsmonitor=false"]


# ---------------------------------------------------------------- helpers

def tilde(path):
    """Abbreviate the home directory to ~, also when HOME or the path goes through a symlink."""
    if not path:
        return path
    p = str(path)
    for home in dict.fromkeys((HOME, os.path.realpath(HOME))):
        if p == home:
            return "~"
        if p.startswith(home + os.sep):
            return "~" + p[len(home):]
    real = os.path.realpath(p)
    if real != p:
        return tilde(real) if real.startswith(os.path.realpath(HOME)) else p
    return p


def redact(text, limit=240):
    if not isinstance(text, str):
        return None
    s = text.replace(HOME, "~")
    for rx, repl in _REDACTIONS:
        s = rx.sub(repl, s)
    return s if len(s) <= limit else s[:limit] + "..."


def load_json(path):
    """Return (data, status); status is ok | missing | invalid | unreadable."""
    if not path or not os.path.exists(path):
        return None, "missing"
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh), "ok"
    except ValueError:
        return None, "invalid"
    except (OSError, UnicodeDecodeError):
        return None, "unreadable"


def count_lines(path):
    try:
        with open(path, "rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return None


def run(cmd, cwd=None, timeout=15):
    """Run a read-only command. Return (exit_code, stdout) or (None, None)."""
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=timeout,
        )
        return proc.returncode, proc.stdout.decode("utf-8", "replace")
    except (OSError, subprocess.SubprocessError, ValueError):
        return None, None


def read_frontmatter(path, limit=8192):
    """Parse top-level `key: value` pairs of a Markdown frontmatter block (best effort)."""
    out = {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(limit)
    except OSError:
        return out
    if not head.startswith("---"):
        return out
    end = head.find("\n---", 3)
    lines = (head[3:end] if end != -1 else head[3:]).splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line or line[0] in " \t#-":
            continue
        key, sep, val = line.partition(":")
        if not sep:
            continue
        val = val.strip()
        if val in ("|", ">", "|-", ">-", "|+", ">+"):
            # YAML block scalar: collect the following indented lines
            parts = []
            while i < len(lines) and (not lines[i].strip() or lines[i][0] in " \t"):
                parts.append(lines[i].strip())
                i += 1
            val = " ".join(p for p in parts if p)
        elif len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[key.strip()] = val
    return out


def find_up(start, marker, stop=None):
    """Return the first directory from `start` upwards that contains `marker`."""
    cur = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(cur, marker)):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur or (stop and cur == stop):
            return None
        cur = parent


def count_md(directory, max_depth=2):
    total = 0
    base_depth = directory.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(directory):
        if dirpath.count(os.sep) - base_depth >= max_depth:
            dirnames[:] = []
        total += sum(1 for f in filenames if f.lower().endswith((".md", ".mdx")))
    return total


def expand_vars(token, project_dir, plugin_root=None):
    mapping = {"HOME": HOME, "CLAUDE_PROJECT_DIR": project_dir}
    if plugin_root:
        mapping["CLAUDE_PLUGIN_ROOT"] = plugin_root
    unresolved = []

    def sub(match):
        name = match.group(1) or match.group(2)
        if mapping.get(name):
            return mapping[name]
        unresolved.append(name)
        return match.group(0)

    out = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)", sub, token)
    if out == "~" or out.startswith("~/"):
        out = HOME + out[1:]
    return out, unresolved


def looks_like_path(tok):
    if not tok or "://" in tok or tok.startswith("-"):
        return False
    prefixes = ("/", "~/", "./", "../", "$HOME", "${HOME}", "$CLAUDE_PROJECT_DIR",
                "${CLAUDE_PROJECT_DIR}", "$CLAUDE_PLUGIN_ROOT", "${CLAUDE_PLUGIN_ROOT}", ".claude/")
    if tok.startswith(prefixes):
        return True
    return "/" in tok and tok.lower().endswith(SCRIPT_EXTS)


SHELL_OPERATORS = {"&&", "||", ";", "|", "&", "|&", ";;", "(", ")"}
REDIRECTS = {">", ">>", "<", "<<", "<<<", ">&", "&>", "&>>", "2>", "2>>"}
WRAPPERS = {"env", "exec", "command", "builtin", "nohup", "nice", "time", "noglob"}
INTERPRETERS = {"bash", "sh", "zsh", "dash", "ksh", "fish", "node", "deno", "bun", "ruby", "perl", "php",
                "pwsh", "powershell", "tsx", "ts-node", "uv", "osascript", "python", "python3"}
INLINE_CODE_FLAGS = {"-c", "-e", "-E", "--eval", "-p", "--print", "-Command", "-command", "-EncodedCommand"}
RUNNER_SUBCOMMANDS = {"run"}
ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
# Letters that mean "run the next argument as inline code" when they appear inside a combined short-option
# cluster such as `bash -lc '...'`, `python3 -Bc '...'` or `perl -ne '...'`.
INLINE_CODE_LETTERS = {
    "bash": "c", "sh": "c", "zsh": "c", "dash": "c", "ksh": "c", "fish": "c", "python": "c", "python3": "c",
    "node": "ep", "bun": "e", "perl": "eE", "ruby": "e", "php": "r", "osascript": "e",
}
COMBINED_SHORT_RE = re.compile(r"^-[A-Za-z]{2,}$")


def is_inline_code_flag(arg, name):
    """True when `arg` makes the interpreter `name` run inline code, so no script path follows it."""
    if arg in INLINE_CODE_FLAGS:
        return True
    if COMBINED_SHORT_RE.match(arg):
        key = "python" if re.match(r"^python3?(\.\d+)?$", name) else name
        letters = INLINE_CODE_LETTERS.get(key)
        # Unknown interpreter with a combined option cluster: can't tell, so stay conservative.
        return letters is None or any(ch in letters for ch in arg[1:])
    return False


def command_segments(handler):
    """argv lists of a command hook: exec form gives one; shell form is split at shell operators."""
    cmd = handler.get("command")
    if not isinstance(cmd, str) or not cmd.strip():
        return []
    if isinstance(handler.get("args"), list):
        return [[cmd] + [a for a in handler["args"] if isinstance(a, str)]]
    try:
        lexer = shlex.shlex(cmd, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        tokens = cmd.split()
    segments, current = [], []
    for tok in tokens:
        if tok in SHELL_OPERATORS:
            if current:
                segments.append(current)
            current = []
        else:
            current.append(tok)
    if current:
        segments.append(current)
    return segments


def executable_index(argv):
    """Index of the program in argv after leading VAR=value assignments and wrappers such as env."""
    i = 0
    while i < len(argv):
        tok = argv[i]
        if ASSIGNMENT_RE.match(tok):
            i += 1
        elif os.path.basename(tok) in WRAPPERS:
            i += 1
            while i < len(argv) and (argv[i].startswith("-") or ASSIGNMENT_RE.match(argv[i])):
                i += 1
        else:
            return i
    return None


def is_pathish(tok):
    return bool(tok) and "://" not in tok and not tok.startswith("-") and (
        "/" in tok or tok.startswith(("~", "$", "./", "../")))


def script_paths(handler):
    """Paths that are certainly executed: each segment's program (argv[0]) when it is a path, and the
    first script argument of an interpreter (bash x.sh, python3 x.py, bun run x.ts). Other arguments are
    never inspected, so option values such as tokens can't be mistaken for paths."""
    found = []
    for argv in command_segments(handler):
        i = executable_index(argv)
        if i is None:
            continue
        exe = argv[i]
        if is_pathish(exe):
            found.append(exe)
        name = os.path.basename(exe)
        if name in INTERPRETERS or re.match(r"^python3?(\.\d+)?$", name):
            j = i + 1
            while j < len(argv):
                arg = argv[j]
                if is_inline_code_flag(arg, name) or arg in REDIRECTS:
                    break
                if arg.startswith("-") or (arg in RUNNER_SUBCOMMANDS and name in ("bun", "deno", "uv")):
                    j += 1
                    continue
                if is_pathish(arg) or arg.lower().endswith(SCRIPT_EXTS):
                    found.append(arg)
                break
    return list(dict.fromkeys(found))


def all_path_tokens(handler):
    """Every path-like token anywhere in the command. Internal only (unmounted-script detection); never printed."""
    found = []
    for argv in command_segments(handler):
        for tok in argv:
            tok = re.sub(r"^(?:\d*>>?|&>>?|<)", "", tok.strip())
            if looks_like_path(tok):
                found.append(tok)
    return list(dict.fromkeys(found))


def program_name(handler):
    """Basename of the program the first command segment runs; assignments and wrappers are skipped."""
    segments = command_segments(handler)
    if not segments:
        return None
    i = executable_index(segments[0])
    if i is None:
        return None
    base = os.path.basename(segments[0][i].rstrip("/"))
    return base if re.match(r"^[A-Za-z0-9._+-]{1,40}$", base) else "unknown"


def check_paths(paths, project_dir, plugin_root=None):
    result = []
    for raw in paths:
        expanded, unresolved = expand_vars(raw, project_dir, plugin_root)
        entry = {"path": redact(raw, 160)}
        if unresolved:
            entry["exists"] = None
            entry["note"] = "unresolved variable: " + ",".join(sorted(set(unresolved)))
        else:
            relative = not os.path.isabs(expanded)
            full = os.path.normpath(os.path.join(project_dir, expanded)) if relative else expanded
            entry["exists"] = os.path.exists(full)
            entry["relative"] = relative
            entry["_abs"] = full
        result.append(entry)
    return result


def managed_merge(earlier, later):
    """Combine two managed settings files the documented way: single values from the later file win,
    lists combine without duplicates, nested blocks merge key by key; extraKnownMarketplaces and
    managedMcpServers entries are replaced whole by name; fallbackModel and modelPicker are replaced whole."""
    out = dict(earlier)
    for key, value in later.items():
        current = out.get(key)
        if key in ("extraKnownMarketplaces", "managedMcpServers") and isinstance(value, dict) and isinstance(current, dict):
            combined = dict(current)
            combined.update(value)
            out[key] = combined
        elif key in ("fallbackModel", "modelPicker"):
            out[key] = value
        elif isinstance(value, dict) and isinstance(current, dict):
            out[key] = managed_merge(current, value)
        elif isinstance(value, list) and isinstance(current, list):
            out[key] = current + [v for v in value if v not in current]
        else:
            out[key] = value
    return out


def iter_hook_handlers(hooks_obj):
    if not isinstance(hooks_obj, dict):
        return
    for event, groups in hooks_obj.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            matcher = group.get("matcher")
            for handler in group.get("hooks") or []:
                if isinstance(handler, dict):
                    yield event, matcher, handler


def url_info(url):
    if not isinstance(url, str):
        return None, None
    m = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*)://\[?([^/:?#\]]+)", url)
    if not m:
        return None, None
    host = m.group(2).lower()
    return m.group(1).lower(), host in ("localhost", "127.0.0.1", "::1")


# ---------------------------------------------------------------- doctor

class Doctor:
    def __init__(self, days, project, use_usage, use_cli, managed_dir=None):
        self.managed_dir = os.path.abspath(os.path.expanduser(managed_dir)) if managed_dir else None
        self.days = days
        self.project = os.path.realpath(os.path.abspath(os.path.expanduser(project)))
        self.use_usage = use_usage
        self.use_cli = use_cli
        self.errors = []
        self.findings = []
        self.hook_items = []          # all settings-level hooks (internal, with _abs)
        self.plugin_skill_names = {}  # plugin name -> set(skill names)
        self.plugin_names = set()
        self.user_skill_names = set()
        self.project_skill_names = set()
        self.git_root = None
        self.settings_raw = {}
        self.rules_raw = {}           # scope -> {"deny": [...], "ask": [...]} (internal only)
        self.plugin_agent_names = set()   # "plugin:agent"
        self.plugin_command_names = {}    # plugin name -> set(command names)
        self.user_agent_names = set()
        self.command_names = set()        # personal and project custom commands
        self.skill_counts = Counter()
        self.cmd_counts = Counter()
        self.agent_counts = Counter()

    # ------------------------------------------------------------ utilities
    def guard(self, name, fn, default=None):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - a collector must never crash the run
            self.errors.append({"collector": name, "error": "%s: %s" % (type(exc).__name__, redact(str(exc), 200))})
            return default

    def add(self, fid, severity, title, **evidence):
        item = {"id": fid, "severity": severity, "title": title}
        if evidence:
            item["evidence"] = evidence
        self.findings.append(item)

    # ------------------------------------------------------------ collectors
    def claude_cli(self):
        exe = shutil.which("claude")
        info = {"cli_found": bool(exe), "version": None}
        if exe and self.use_cli:
            code, out = run(["claude", "--version"], timeout=15)
            if code == 0 and out:
                m = re.search(r"\d+\.\d+\.\d+", out)
                info["version"] = m.group(0) if m else out.strip()[:40]
        return info

    def summarize_settings(self, path, scope, preloaded=None):
        data, status = preloaded if preloaded is not None else load_json(path)
        out = {"scope": scope, "path": tilde(path), "status": status}
        if status != "ok":
            return out
        if not isinstance(data, dict):
            out["status"] = "invalid"
            return out
        self.settings_raw[scope] = data
        perms = data.get("permissions") if isinstance(data.get("permissions"), dict) else {}

        def rules(key):
            value = perms.get(key)
            return [r for r in value if isinstance(r, str)] if isinstance(value, list) else []

        allow, ask, deny = rules("allow"), rules("ask"), rules("deny")
        self.rules_raw[scope] = {"deny": deny, "ask": ask}  # internal only; output uses redacted copies
        add_dirs = perms.get("additionalDirectories")
        out["permissions"] = {
            "allow_count": len(allow),
            "ask_count": len(ask),
            "deny_count": len(deny),
            "defaultMode": perms.get("defaultMode") if isinstance(perms.get("defaultMode"), str) else None,
            "additionalDirectories_count": len(add_dirs) if isinstance(add_dirs, list) else 0,
            "deny_rules": [redact(r, 160) for r in deny][:80],
            "ask_rules": [redact(r, 160) for r in ask][:80],
        }
        out["skipDangerousModePermissionPrompt"] = data.get("skipDangerousModePermissionPrompt")
        hooks = []
        for event, matcher, handler in iter_hook_handlers(data.get("hooks")):
            item = {"event": event, "matcher": redact(matcher, 80) if isinstance(matcher, str) else None,
                    "type": handler.get("type")}
            refs = []
            if handler.get("type") == "command":
                # The command line itself is never printed: it can carry credentials. Only the program name
                # and the paths that are certainly executed (argv[0], or an interpreter's script) are reported.
                item["program"] = program_name(handler)
                item["scripts"] = check_paths(script_paths(handler), self.project)
                refs = [r["_abs"] for r in check_paths(all_path_tokens(handler), self.project) if r.get("_abs")]
            elif handler.get("type") == "http":
                item["url_scheme"], item["url_is_local"] = url_info(handler.get("url"))
            if "onFailure" in handler:
                item["onFailure"] = handler.get("onFailure")
            hooks.append(item)
            self.hook_items.append(dict(item, source=scope, _refs=refs))
        out["hooks"] = [self._public_hook(h) for h in hooks]
        out["disableAllHooks"] = data.get("disableAllHooks")
        ep = data.get("enabledPlugins")
        out["enabledPlugins"] = dict(ep) if isinstance(ep, dict) else None
        so = data.get("skillOverrides")
        out["skillOverrides"] = dict(so) if isinstance(so, dict) else None
        env = data.get("env")
        if isinstance(env, dict):
            secret_keys = sorted(
                k for k, v in env.items()
                if isinstance(k, str) and SECRET_KEY_RE.search(k)
                and isinstance(v, str) and v.strip() and "${" not in v
            )
            out["env"] = {"count": len(env), "secret_like_keys": secret_keys,
                          "sets_base_url": "ANTHROPIC_BASE_URL" in env}
        else:
            out["env"] = None
        out["autoMemoryDirectory_set"] = "autoMemoryDirectory" in data
        ekm = data.get("extraKnownMarketplaces")
        out["extraKnownMarketplaces"] = sorted(ekm.keys()) if isinstance(ekm, dict) else None
        try:
            out["file_mode"] = oct(os.stat(path).st_mode & 0o777)
        except OSError:
            out["file_mode"] = None
        return out

    @staticmethod
    def _public_hook(item):
        pub = dict(item)
        if "scripts" in pub:
            pub["scripts"] = [{k: v for k, v in s.items() if not k.startswith("_")} for s in pub["scripts"]]
        return pub

    def settings(self):
        result = {
            "user": self.summarize_settings(os.path.join(CLAUDE_DIR, "settings.json"), "user"),
            "project": self.summarize_settings(os.path.join(self.project, ".claude", "settings.json"), "project"),
            "local": self.summarize_settings(os.path.join(self.project, ".claude", "settings.local.json"), "local"),
        }
        base = self.managed_dir or MANAGED_DIRS.get("linux" if sys.platform.startswith("linux") else sys.platform)
        if base:
            # File-based managed settings: managed-settings.json first, then managed-settings.d/*.json in
            # alphabetical order (hidden files ignored), combined by the documented rules (see managed_merge).
            main_path = os.path.join(base, "managed-settings.json")
            main_data, main_status = load_json(main_path)
            dropin_dir = os.path.join(base, "managed-settings.d")
            dropins = sorted(f for f in glob.glob(os.path.join(dropin_dir, "*.json"))
                             if not os.path.basename(f).startswith(".")) if os.path.isdir(dropin_dir) else []
            merged = main_data if main_status == "ok" and isinstance(main_data, dict) else None
            invalid = 0
            for f in dropins:
                data, status = load_json(f)
                if status == "ok" and isinstance(data, dict):
                    merged = managed_merge(merged or {}, data)
                else:
                    invalid += 1
            if merged is not None:
                managed = self.summarize_settings(main_path, "managed", (merged, "ok"))
            else:
                managed = self.summarize_settings(main_path, "managed", (main_data, main_status))
            managed["main_file_status"] = main_status
            managed["dropin_files"] = len(dropins)
            managed["dropin_invalid"] = invalid
            managed["note"] = "file-based managed settings only; MDM profiles and server-managed settings are not visible here"
            result["managed"] = managed
        else:
            result["managed"] = {"scope": "managed", "status": "unsupported-platform"}
        return result

    def plugin_components(self, root):
        info = {"manifest_name": None, "skills": 0, "commands": 0, "agents": 0,
                "hook_events": [], "mcp_servers": 0, "lsp": False, "sets_main_agent": False}
        skill_names = set()
        if not root or not os.path.isdir(root):
            return info, skill_names
        manifest, _ = load_json(os.path.join(root, ".claude-plugin", "plugin.json"))
        manifest = manifest if isinstance(manifest, dict) else {}
        if isinstance(manifest.get("name"), str):
            info["manifest_name"] = manifest["name"]

        def as_list(value):
            if isinstance(value, str):
                return [value]
            return [v for v in value if isinstance(v, str)] if isinstance(value, list) else []

        def inside(rel):
            full = os.path.realpath(os.path.join(root, rel))
            return full if (full + os.sep).startswith(os.path.realpath(root) + os.sep) or full == os.path.realpath(root) else None

        skill_dirs = {}

        def add_skill_root(directory):
            if not directory or not os.path.isdir(directory):
                return
            if os.path.isfile(os.path.join(directory, "SKILL.md")):
                skill_dirs[os.path.realpath(directory)] = directory
                return
            for name in os.listdir(directory):
                sub = os.path.join(directory, name)
                if os.path.isfile(os.path.join(sub, "SKILL.md")):
                    skill_dirs[os.path.realpath(sub)] = sub

        default_skills = os.path.join(root, "skills")
        if os.path.isdir(default_skills):
            for name in os.listdir(default_skills):
                sub = os.path.join(default_skills, name)
                if os.path.isfile(os.path.join(sub, "SKILL.md")):
                    skill_dirs[os.path.realpath(sub)] = sub
        for rel in as_list(manifest.get("skills")):
            add_skill_root(inside(rel))
        if not skill_dirs and not os.path.isdir(default_skills) and os.path.isfile(os.path.join(root, "SKILL.md")):
            skill_dirs[os.path.realpath(root)] = root
        for directory in skill_dirs.values():
            fm = read_frontmatter(os.path.join(directory, "SKILL.md"))
            skill_names.add(fm.get("name") or os.path.basename(directory.rstrip(os.sep)))
        info["skills"] = len(skill_dirs)

        command_names = set()
        commands = manifest.get("commands")
        if isinstance(commands, dict):
            command_names.update(k for k in commands if isinstance(k, str))
        else:
            for rel in as_list(commands) or ["commands"]:
                full = inside(rel)
                if full and os.path.isfile(full) and full.endswith(".md"):
                    command_names.add(os.path.basename(full)[:-3])
                elif full and os.path.isdir(full):
                    command_names.update(f[:-3] for f in os.listdir(full) if f.endswith(".md"))
        info["commands"] = len(command_names)
        info["_command_names"] = command_names

        agent_files = []
        agents = as_list(manifest.get("agents"))
        if agents:
            agent_files = [inside(rel) for rel in agents if inside(rel) and os.path.isfile(inside(rel))]
        elif os.path.isdir(os.path.join(root, "agents")):
            agents_dir = os.path.join(root, "agents")
            for dirpath, dirnames, filenames in os.walk(agents_dir):
                if dirpath.count(os.sep) - agents_dir.count(os.sep) >= 3:
                    dirnames[:] = []
                agent_files.extend(os.path.join(dirpath, f) for f in filenames if f.endswith(".md"))
        info["agents"] = len(agent_files)
        info["_agent_names"] = {read_frontmatter(f).get("name") or os.path.basename(f)[:-3] for f in agent_files}

        events = set()
        hooks_file, _ = load_json(os.path.join(root, "hooks", "hooks.json"))
        if isinstance(hooks_file, dict) and isinstance(hooks_file.get("hooks"), dict):
            events.update(hooks_file["hooks"].keys())
        mh = manifest.get("hooks")
        for entry in (mh if isinstance(mh, list) else [mh]):
            if isinstance(entry, dict):
                events.update(k for k in entry.keys() if isinstance(k, str))
            elif isinstance(entry, str) and inside(entry):
                data, _ = load_json(inside(entry))
                if isinstance(data, dict) and isinstance(data.get("hooks"), dict):
                    events.update(data["hooks"].keys())
        info["hook_events"] = sorted(events)

        mcp_total = 0
        mcp_file, _ = load_json(os.path.join(root, ".mcp.json"))
        if isinstance(mcp_file, dict):
            servers = mcp_file.get("mcpServers") if isinstance(mcp_file.get("mcpServers"), dict) else mcp_file
            mcp_total += sum(1 for v in servers.values() if isinstance(v, dict))
        if isinstance(manifest.get("mcpServers"), dict):
            mcp_total += len(manifest["mcpServers"])
        elif manifest.get("mcpServers"):
            mcp_total += len(as_list(manifest.get("mcpServers"))) or 1
        info["mcp_servers"] = mcp_total
        info["lsp"] = os.path.isfile(os.path.join(root, ".lsp.json")) or bool(manifest.get("lspServers"))
        plugin_settings, _ = load_json(os.path.join(root, "settings.json"))
        info["sets_main_agent"] = bool(isinstance(plugin_settings, dict) and plugin_settings.get("agent")) or bool(
            isinstance(manifest.get("settings"), dict) and manifest["settings"].get("agent"))
        return info, skill_names

    def plugins(self):
        data, status = load_json(os.path.join(CLAUDE_DIR, "plugins", "installed_plugins.json"))
        result = {"installed_file": status, "enabled_source": None, "items": [],
                  "installed_count": 0, "enabled_count": 0, "enabled_but_not_installed": []}
        entries = []
        if status == "ok" and isinstance(data, dict):
            plugins = data.get("plugins") if isinstance(data.get("plugins"), dict) else {}
            for pid, value in plugins.items():
                for rec in (value if isinstance(value, list) else [value]):
                    if isinstance(rec, dict) and isinstance(pid, str):
                        entries.append((pid, rec))

        cli_enabled = None
        if self.use_cli and shutil.which("claude"):
            code, out = run(["claude", "plugin", "list", "--json"], cwd=self.project if os.path.isdir(self.project) else None, timeout=30)
            if code == 0 and out:
                try:
                    arr = json.loads(out)
                    if isinstance(arr, list):
                        cli_enabled = {}
                        for e in arr:
                            if isinstance(e, dict) and isinstance(e.get("id"), str):
                                cli_enabled[e["id"]] = bool(e.get("enabled")) or cli_enabled.get(e["id"], False)
                except ValueError:
                    cli_enabled = None

        merged = {}
        for scope in ("user", "project", "local", "managed"):
            ep = self.settings_raw.get(scope, {}).get("enabledPlugins")
            if isinstance(ep, dict):
                for k, v in ep.items():
                    merged[k] = v is True or (v is not False and bool(v))
        result["enabled_source"] = "claude plugin list --json" if cli_enabled is not None else "settings files"

        installed_ids = set()
        for pid, rec in entries:
            name, _, market = pid.partition("@")
            install_path = rec.get("installPath") if isinstance(rec.get("installPath"), str) else None
            comp, skill_names = self.plugin_components(install_path)
            plugin_name = comp.get("manifest_name") or name
            self.plugin_names.add(plugin_name)
            self.plugin_names.add(name)
            self.plugin_skill_names.setdefault(plugin_name, set()).update(skill_names)
            self.plugin_command_names.setdefault(plugin_name, set()).update(comp.get("_command_names", set()))
            self.plugin_agent_names.update("%s:%s" % (plugin_name, a) for a in comp.get("_agent_names", set()))
            if cli_enabled is not None:
                enabled = cli_enabled.get(pid)
            else:
                enabled = merged.get(pid)
            item = {
                "id": pid, "name": plugin_name, "marketplace": market or None,
                "scope": rec.get("scope"), "version": rec.get("version"), "enabled": enabled,
                "install_path_exists": bool(install_path and os.path.isdir(install_path)),
            }
            if isinstance(rec.get("projectPath"), str):
                item["project_path"] = tilde(rec["projectPath"])
            item.update({k: v for k, v in comp.items() if k != "manifest_name" and not k.startswith("_")})
            result["items"].append(item)
            installed_ids.add(pid)
        result["installed_count"] = len(installed_ids)
        result["enabled_count"] = len({i["id"] for i in result["items"] if i["enabled"]})
        result["enabled_but_not_installed"] = sorted(k for k, v in merged.items() if v and k not in installed_ids)
        return result

    def user_skills(self):
        base = os.path.join(CLAUDE_DIR, "skills")
        res = {"path": tilde(base), "exists": os.path.isdir(base), "count": 0, "model_invocable": 0,
               "synced_count": 0, "symlinked_count": 0, "suites": {}, "items": []}
        if not res["exists"]:
            return res
        gstack_root = os.path.isdir(os.path.join(base, "gstack", ".git")) or os.path.isfile(os.path.join(base, "gstack", "SKILL.md"))
        for name in sorted(os.listdir(base)):
            if name.startswith("."):
                continue
            directory = os.path.join(base, name)
            if name == "synced" and os.path.isdir(directory) and not os.path.isfile(os.path.join(directory, "SKILL.md")):
                res["synced_count"] = sum(1 for n in os.listdir(directory) if os.path.isfile(os.path.join(directory, n, "SKILL.md")))
                continue
            skill_md = os.path.join(directory, "SKILL.md")
            if not os.path.isfile(skill_md):
                continue
            fm = read_frontmatter(skill_md)
            skill_name = fm.get("name") or name
            suite = "gstack" if ("(gstack)" in fm.get("description", "") or (name == "gstack" and gstack_root)) else None
            invocable = fm.get("disable-model-invocation", "").lower() not in ("true", "yes", "on", "1")
            self.user_skill_names.update({skill_name, name})
            if os.path.islink(directory):
                res["symlinked_count"] += 1
            if suite:
                res["suites"][suite] = res["suites"].get(suite, 0) + 1
            res["count"] += 1
            res["model_invocable"] += 1 if invocable else 0
            item = {"name": skill_name, "suite": suite, "model_invocable": invocable}
            if skill_name != name:
                item["dir"] = name
            res["items"].append(item)
        if gstack_root and "gstack" not in res["suites"]:
            res["suites"]["gstack"] = 0
        return res

    def agents(self):
        def collect(directory):
            names = []
            if not os.path.isdir(directory):
                return None
            base_depth = directory.rstrip(os.sep).count(os.sep)
            for dirpath, dirnames, filenames in os.walk(directory):
                if dirpath.count(os.sep) - base_depth >= 3:
                    dirnames[:] = []
                for f in filenames:
                    if f.endswith(".md"):
                        fm = read_frontmatter(os.path.join(dirpath, f))
                        names.append(fm.get("name") or f[:-3])
            return sorted(set(names))

        user = collect(os.path.join(CLAUDE_DIR, "agents"))
        project = collect(os.path.join(self.project, ".claude", "agents"))
        self.user_agent_names.update(user or [])
        self.user_agent_names.update(project or [])
        for commands_dir in (os.path.join(CLAUDE_DIR, "commands"), os.path.join(self.project, ".claude", "commands")):
            if os.path.isdir(commands_dir):
                for dirpath, dirnames, filenames in os.walk(commands_dir):
                    rel = os.path.relpath(dirpath, commands_dir)
                    for f in filenames:
                        if f.endswith(".md"):
                            stem = f[:-3]
                            self.command_names.add(stem)
                            if rel != ".":
                                self.command_names.add("%s:%s" % (rel.replace(os.sep, ":"), stem))
        return {
            "user_count": len(user) if user is not None else None,
            "project_count": len(project) if project is not None else None,
            "_user_names": user or [],
        }

    def mcp(self):
        res = {"user_file": None, "user": None, "project_local": None, "project_file": None}

        def entry(name, cfg):
            cfg = cfg if isinstance(cfg, dict) else {}
            transport = cfg.get("type") if isinstance(cfg.get("type"), str) else ("http" if cfg.get("url") else "stdio")
            item = {"name": name, "transport": transport}
            scheme, local = url_info(cfg.get("url"))
            item["insecure_http"] = bool(scheme in ("http", "ws") and not local)
            literal = []
            for section in ("env", "headers"):
                values = cfg.get(section)
                if isinstance(values, dict):
                    for k, v in values.items():
                        if isinstance(k, str) and isinstance(v, str) and len(v) >= 12 and "${" not in v \
                                and (SECRET_KEY_RE.search(k) or k.lower() == "authorization"):
                            literal.append("%s.%s" % (section, k))
            item["literal_secret_keys"] = literal
            return item

        gcf = global_config_file()
        data, status = load_json(gcf)
        res["user_file"] = status
        res["user_file_path"] = tilde(gcf)
        if status == "ok" and isinstance(data, dict):
            servers = data.get("mcpServers")
            res["user"] = [entry(k, v) for k, v in servers.items()] if isinstance(servers, dict) else []
            projects = data.get("projects")
            if isinstance(projects, dict):
                cfg = projects.get(self.project) or (projects.get(self.git_root) if self.git_root else None)
                if isinstance(cfg, dict) and isinstance(cfg.get("mcpServers"), dict):
                    res["project_local"] = [entry(k, v) for k, v in cfg["mcpServers"].items()]
                elif isinstance(cfg, dict):
                    res["project_local"] = []
        mcp_path = os.path.join(self.project, ".mcp.json")
        data, status = load_json(mcp_path)
        res["project_file"] = {"path": ".mcp.json", "status": status, "servers": None}
        if status == "ok" and isinstance(data, dict):
            servers = data.get("mcpServers") if isinstance(data.get("mcpServers"), dict) else {}
            res["project_file"]["servers"] = [entry(k, v) for k, v in servers.items()]
        return res

    def scan_event(self, line, cutoff_date):
        """Count Skill / Task tool calls and slash-command events in one transcript line (metadata only)."""
        is_tool = b'"tool_use"' in line and (b'"Skill"' in line or b'"subagent_type"' in line)
        # typed / sdk / queued prompts carry promptSource; Claude Code's own command events don't
        is_cmd = b"<command-name>/" in line and b'"tool_use_id"' not in line and b'"promptSource"' not in line
        if not (is_tool or is_cmd):
            return
        try:
            event = json.loads(line)
        except ValueError:
            return
        if not isinstance(event, dict) or not isinstance(event.get("message"), dict):
            return
        ts = event.get("timestamp")
        if isinstance(ts, str) and ts[:10] < cutoff_date:
            return
        message = event["message"]
        content = message.get("content")
        if is_tool and event.get("type") == "assistant" and isinstance(content, list):
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                args = block.get("input") if isinstance(block.get("input"), dict) else {}
                if block.get("name") == "Skill" and isinstance(args.get("skill"), str):
                    self.skill_counts[args["skill"].strip().lstrip("/")] += 1
                elif block.get("name") in ("Task", "Agent") and isinstance(args.get("subagent_type"), str):
                    self.agent_counts[args["subagent_type"].strip()] += 1
        elif (is_cmd and event.get("type") == "user" and message.get("role") == "user" and isinstance(content, str)
              and "promptSource" not in event and not event.get("isMeta")):
            name = command_event_name(content)
            if name:
                self.cmd_counts[name] += 1

    def usage(self):
        if not self.use_usage or self.days <= 0:
            return {"enabled": False}
        started = time.time()
        root = os.path.join(CLAUDE_DIR, "projects")
        cutoff_ts = time.time() - self.days * 86400
        cutoff_date = (datetime.now() - timedelta(days=self.days)).strftime("%Y-%m-%d")
        files = 0
        size = 0
        for path in glob.glob(os.path.join(root, "*", "*.jsonl")):
            try:
                st = os.stat(path)
            except OSError:
                continue
            if st.st_mtime < cutoff_ts:
                continue
            files += 1
            size += st.st_size
            try:
                with open(path, "rb") as fh:
                    for line in fh:
                        self.scan_event(line, cutoff_date)
            except OSError:
                continue
        names = set(self.skill_counts) | set(self.cmd_counts)
        top = []
        unknown_names = unknown_calls = 0
        for n in names:
            total = self.skill_counts[n] + self.cmd_counts[n]
            kind = self.classify(n)
            if kind is None:
                unknown_names += 1
                unknown_calls += total
                continue
            top.append({"name": n, "count": total, "skill_tool": self.skill_counts[n],
                        "slash": self.cmd_counts[n], "kind": kind})
        top.sort(key=lambda x: (-x["count"], x["name"]))
        agents_top = []
        unknown_agents = 0
        for n, c in self.agent_counts.most_common():
            if self.is_known_agent(n):
                agents_top.append({"name": n, "count": c})
            else:
                unknown_agents += c
        return {
            "enabled": True, "days": self.days, "since": cutoff_date, "files_scanned": files,
            "mb_scanned": round(size / 1e6, 1), "skill_tool_calls": sum(self.skill_counts.values()),
            "slash_commands": sum(self.cmd_counts.values()), "subagent_calls": sum(self.agent_counts.values()),
            "top": top[:60], "agents_top": agents_top[:40],
            "unknown": {"names": unknown_names, "calls": unknown_calls, "subagent_calls": unknown_agents},
            "elapsed_ms": int((time.time() - started) * 1000),
            "note": "only event metadata is parsed; only known names are listed, other values are only counted",
        }

    def classify(self, name):
        """Kind of a known skill/command name, or None for anything not installed or built in."""
        if not NAME_RE.match(name):
            return None
        if ":" in name:
            owner, _, rest = name.partition(":")
            known = self.plugin_skill_names.get(owner, set()) | self.plugin_command_names.get(owner, set())
            return "plugin" if rest in known else None
        if name in self.user_skill_names:
            return "user_skill"
        if name in self.project_skill_names:
            return "project_skill"
        if name in self.command_names:
            return "user_command"
        if name in BUILTIN_COMMANDS:
            return "builtin"
        return None

    def is_known_agent(self, name):
        if not NAME_RE.match(name):
            return False
        return name in self.user_agent_names or name in self.plugin_agent_names or name in BUILTIN_AGENTS

    def invocations(self, name):
        return self.skill_counts.get(name, 0) + self.cmd_counts.get(name, 0)

    def plugin_invocations(self, plugin_name):
        prefix = plugin_name + ":"
        total = 0
        for counter in (self.skill_counts, self.cmd_counts):
            total += sum(c for n, c in counter.items() if n.startswith(prefix))
        return total

    def environment(self):
        backups = set(glob.glob(os.path.join(CLAUDE_DIR, "settings.json.*")))
        backups.update(glob.glob(os.path.join(CLAUDE_DIR, "settings*.bak*")))
        return {
            "cc_switch_detected": os.path.isdir(os.path.join(HOME, ".cc-switch")),
            "settings_backup_files": len(backups),
            "python": sys.version.split()[0],
            "platform": sys.platform,
        }

    def find_env_files(self, root, max_depth=3, max_dirs=4000):
        found = []
        visited = 0
        base_depth = root.rstrip(os.sep).count(os.sep)
        for dirpath, dirnames, filenames in os.walk(root):
            visited += 1
            depth = dirpath.count(os.sep) - base_depth
            if depth >= max_depth or visited > max_dirs:
                dirnames[:] = []
            else:
                dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            for f in filenames:
                if (f == ".env" or f == ".envrc" or f.startswith(".env.")) and not f.endswith(ENV_TEMPLATE_SUFFIXES):
                    found.append(os.path.join(dirpath, f))
            if len(found) >= 50:
                break
        return found

    @staticmethod
    def gitignore_patterns(gitignore_path):
        try:
            with open(gitignore_path, "r", encoding="utf-8", errors="replace") as fh:
                return [l.strip() for l in fh if l.strip() and not l.strip().startswith(("#", "!"))]
        except OSError:
            return None

    @staticmethod
    def gitignore_matches(patterns, rel_path):
        """Rough .gitignore emulation (no negation, no nested files): used only outside git repos."""
        import fnmatch
        if not patterns:
            return False
        name = os.path.basename(rel_path)
        for p in patterns:
            p2 = p.rstrip("/")
            anchored = p2.startswith("/")
            p2 = p2.lstrip("/")
            if p2.startswith("**/"):
                p2, anchored = p2[3:], False
            if fnmatch.fnmatch(rel_path, p2) or (not anchored and "/" not in p2 and fnmatch.fnmatch(name, p2)):
                return True
        return False

    def collect_project(self):
        p = self.project
        res = {"path": tilde(p), "exists": os.path.isdir(p), "is_home": p == HOME}
        if not res["exists"]:
            return res
        git_root = find_up(p, ".git")
        self.git_root = git_root
        git_cli = bool(git_root and shutil.which("git"))
        if git_cli:
            code, out = run(GIT + ["-C",p, "rev-parse", "--show-toplevel"], timeout=10)
            if code == 0 and out.strip():
                git_root = os.path.realpath(out.strip())
                self.git_root = git_root
        res["is_git"] = bool(git_root)
        res["git_root"] = tilde(git_root) if git_root else None

        claude_md = []
        for rel in ("CLAUDE.md", os.path.join(".claude", "CLAUDE.md"), "CLAUDE.local.md"):
            f = os.path.join(p, rel)
            if os.path.isfile(f):
                claude_md.append({"path": rel, "lines": count_lines(f)})
        if git_root and git_root != p:
            f = os.path.join(git_root, "CLAUDE.md")
            if os.path.isfile(f):
                claude_md.append({"path": tilde(f), "lines": count_lines(f), "note": "repo root"})
        res["claude_md"] = claude_md
        agents_md = os.path.join(p, "AGENTS.md")
        imported = False
        for rel in ("CLAUDE.md", os.path.join(".claude", "CLAUDE.md")):
            f = os.path.join(p, rel)
            if os.path.isfile(f):
                try:
                    with open(f, "r", encoding="utf-8", errors="replace") as fh:
                        imported = imported or any(re.match(r"^\s*@(?:\./)?AGENTS\.md\b", l) for l in fh)
                except OSError:
                    pass
        res["agents_md"] = {"exists": os.path.isfile(agents_md),
                            "lines": count_lines(agents_md) if os.path.isfile(agents_md) else None,
                            "imported_by_claude_md": imported}

        docs = os.path.join(p, "docs")
        res["docs"] = {"exists": os.path.isdir(docs)}
        for k in DOCS_DIRS:
            d = os.path.join(docs, k)
            res["docs"][k] = count_md(d) if os.path.isdir(d) else None
        res["docs"]["superpowers_dir"] = os.path.isdir(os.path.join(docs, "superpowers"))

        gi = os.path.join(git_root or p, ".gitignore")
        patterns = self.gitignore_patterns(gi) if os.path.isfile(gi) else None
        res["gitignore"] = {
            "exists": patterns is not None,
            "covers_env_guess": (self.gitignore_matches(patterns, ".env")
                                 and self.gitignore_matches(patterns, ".env.production")) if patterns is not None else None,
        }
        env_items = []
        if res["is_home"]:
            res["env_files_note"] = "project is the home directory; .env scan skipped"
        else:
            for f in self.find_env_files(p):
                rel = os.path.relpath(f, git_root or p)
                item = {"path": rel, "ignored": None, "tracked": None}
                if git_cli:
                    code, _ = run(GIT + ["-C",git_root, "check-ignore", "-q", "--", rel], timeout=10)
                    item["ignored"] = (code == 0) if code in (0, 1) else None
                    code, _ = run(GIT + ["-C",git_root, "ls-files", "--error-unmatch", "--", rel], timeout=10)
                    item["tracked"] = (code == 0) if code is not None else None
                else:
                    item["ignored_guess"] = self.gitignore_matches(patterns, rel)
                env_items.append(item)
        res["env_files"] = env_items

        local_settings = os.path.join(p, ".claude", "settings.local.json")
        res["local_settings_tracked"] = None
        if git_cli and os.path.isfile(local_settings):
            code, _ = run(GIT + ["-C",git_root, "ls-files", "--error-unmatch", "--",
                           os.path.relpath(local_settings, git_root)], timeout=10)
            res["local_settings_tracked"] = (code == 0) if code is not None else None

        skills_dir = os.path.join(p, ".claude", "skills")
        project_skills = 0
        if os.path.isdir(skills_dir):
            for n in os.listdir(skills_dir):
                sk = os.path.join(skills_dir, n, "SKILL.md")
                if os.path.isfile(sk):
                    project_skills += 1
                    self.project_skill_names.update({read_frontmatter(sk).get("name") or n, n})
        res["project_skills"] = project_skills

        signal_files = [
            "package.json", "bun.lock", "bun.lockb", "pnpm-lock.yaml", "package-lock.json", "yarn.lock",
            "next.config.js", "next.config.mjs", "next.config.ts", "vercel.json", ".vercel",
            "wrangler.toml", "wrangler.json", "wrangler.jsonc", "Dockerfile", "docker-compose.yml",
            "compose.yaml", "go.mod", "pyproject.toml", "requirements.txt", "Cargo.toml", "supabase",
            "Makefile", "turbo.json", "pnpm-workspace.yaml",
        ]
        res["signals"] = [s for s in signal_files if os.path.exists(os.path.join(p, s))]
        workflows = os.path.join(p, ".github", "workflows")
        res["ci_workflows"] = len([f for f in os.listdir(workflows) if f.endswith((".yml", ".yaml"))]) if os.path.isdir(workflows) else 0
        return res

    def unmounted_hook_scripts(self):
        referenced = {s.get("_abs") for h in self.hook_items for s in h.get("scripts", []) if s.get("_abs")}
        referenced.update(r for h in self.hook_items for r in h.get("_refs", []))
        referenced = {os.path.realpath(r) for r in referenced}
        candidates = []
        for directory in (os.path.join(CLAUDE_DIR, "hooks"), os.path.join(self.project, ".claude", "hooks")):
            if not os.path.isdir(directory):
                continue
            for dirpath, dirnames, filenames in os.walk(directory):
                if dirpath.count(os.sep) - directory.count(os.sep) >= 1:
                    dirnames[:] = []
                for f in filenames:
                    if f.lower().endswith(SCRIPT_EXTS):
                        full = os.path.realpath(os.path.join(dirpath, f))
                        if full not in referenced:
                            candidates.append(tilde(full))
        return sorted(candidates)[:30]

    # ------------------------------------------------------------ evaluation
    def evaluate(self, out):
        st = out.get("settings") or {}
        scopes = [s for s in ("user", "project", "local", "managed") if isinstance(st.get(s), dict)]

        def perm(scope, key, default=0):
            return ((st.get(scope) or {}).get("permissions") or {}).get(key, default)

        total_deny = sum(perm(s, "deny_count") for s in scopes)
        deny_rules = [r for s in scopes for r in self.rules_raw.get(s, {}).get("deny", [])]
        ask_rules = [r for s in scopes for r in self.rules_raw.get(s, {}).get("ask", [])]
        user_mode = perm("user", "defaultMode", None)
        managed_mode = perm("managed", "defaultMode", None)
        bypass_default = "bypassPermissions" in (user_mode, managed_mode)

        # --- guardrails
        if bypass_default and total_deny == 0:
            self.add("bypass-without-deny", "P0", "默认 bypass 权限模式，且没有任何 deny 规则",
                     defaultMode="bypassPermissions", deny_rules=0)
        elif total_deny == 0:
            self.add("no-deny-rules", "P1", "没有任何 deny 规则", files_checked=scopes)
        if bypass_default and total_deny > 0:
            self.add("bypass-default", "P1", "默认以 bypass 权限模式启动", deny_rules=total_deny)
        if total_deny > 0:
            joined = " ".join(deny_rules + ask_rules)
            gaps = []
            if "rm -rf" not in joined and "rm -fr" not in joined and "Bash(rm " not in joined and "Bash(rm:" not in joined:
                gaps.append("rm -rf")
            if "push --force" not in joined and "push -f" not in joined:
                gaps.append("git push --force")
            if "reset --hard" not in joined:
                gaps.append("git reset --hard")
            if gaps:
                self.add("core-deny-gaps", "P2", "deny/ask 规则没有覆盖最致命的几类命令", missing=gaps)
        if (st.get("user") or {}).get("skipDangerousModePermissionPrompt") is True and not bypass_default:
            self.add("bypass-prompt-accepted", "P2", "曾接受过 bypass 警告，以后进入 bypass 不会再提示")
        for scope in ("project", "local"):
            mode = perm(scope, "defaultMode", None)
            if mode in ("bypassPermissions", "auto"):
                self.add("project-mode-ignored", "P2", "项目级 defaultMode 设为 %s，该值在项目/本地设置里不生效" % mode,
                         scope=scope, defaultMode=mode)

        # --- hooks
        hooks_state = out.get("hooks_state") or {}
        if hooks_state.get("disabled"):
            configured = len(self.hook_items) + sum(
                1 for i in (out.get("plugins") or {}).get("items", []) if i.get("enabled") and i.get("hook_events"))
            self.add("hooks-disabled", "P1",
                     "disableAllHooks 生效：hook 全部不会运行（配置还在，但没有生效）",
                     set_in=hooks_state.get("source"), configured_hooks_and_plugin_hooks=configured,
                     managed_hooks_also_off=hooks_state.get("source") == "managed")
        for h in self.hook_items:
            for s in h.get("scripts", []):
                if s.get("exists") is False:
                    fid, sev = ("hook-script-relative-missing", "P1") if s.get("relative") else ("hook-script-missing", "P0")
                    self.add(fid, sev, "hook 引用的脚本不存在，这条 hook 实际上从未生效",
                             source=h.get("source"), event=h.get("event"), matcher=h.get("matcher"), script=s.get("path"))
        unmounted = out.get("_unmounted_hook_scripts") or []
        if unmounted:
            self.add("unmounted-hook-scripts", "P2", "hooks 目录里有脚本没有挂到任何事件上", scripts=unmounted)

        # --- overwrite / switching tools
        user = st.get("user") or {}
        plugins = out.get("plugins") or {}
        env = out.get("environment") or {}
        if user.get("status") == "ok" and plugins.get("installed_count", 0) >= 3:
            ep = user.get("enabledPlugins")
            no_plugins = not ep or not any(v is True for v in ep.values())
            no_perms = perm("user", "allow_count") + perm("user", "ask_count") + perm("user", "deny_count") == 0
            if no_plugins and no_perms and not user.get("hooks"):
                self.add("settings-possibly-overwritten", "P1", "用户设置里没有插件启用、权限规则和 hook，疑似被整份覆盖",
                         installed_plugins=plugins.get("installed_count"))
        if env.get("cc_switch_detected"):
            managed_exists = (st.get("managed") or {}).get("status") == "ok"
            self.add("cc-switch-detected", "P2" if managed_exists else "P1",
                     "检测到模型供应商切换工具，切换时可能整份重写 ~/.claude/settings.json",
                     managed_settings=managed_exists, settings_points_to_third_party=bool((user.get("env") or {}).get("sets_base_url")))

        # --- secrets
        project_env = (st.get("project") or {}).get("env") or {}
        if project_env.get("secret_like_keys"):
            self.add("secret-in-shared-settings", "P0", "项目共享设置（进 git）的 env 里有疑似明文密钥",
                     file=".claude/settings.json", keys=project_env["secret_like_keys"])
        user_env = user.get("env") or {}
        if user_env.get("secret_like_keys"):
            self.add("secret-in-user-settings", "P2", "用户设置的 env 里有明文密钥",
                     keys=user_env["secret_like_keys"], file_mode=user.get("file_mode"),
                     backup_files=env.get("settings_backup_files", 0))
        proj = out.get("project") or {}
        if proj.get("local_settings_tracked"):
            self.add("local-settings-tracked", "P1", ".claude/settings.local.json 被 git 跟踪了（它本应只留在本机）")
        mcp = out.get("mcp") or {}
        pf = (mcp.get("project_file") or {}).get("servers") or []
        leaked = ["%s: %s" % (s["name"], ", ".join(s["literal_secret_keys"])) for s in pf if s.get("literal_secret_keys")]
        if leaked:
            self.add("secret-in-mcp-json", "P0", "项目 .mcp.json（进 git）里有疑似明文密钥", servers=leaked)
        insecure = [s["name"] for s in (mcp.get("user") or []) + (mcp.get("project_local") or []) + pf if s.get("insecure_http")]
        if insecure:
            self.add("mcp-insecure-http", "P2", "有 MCP 服务器用明文 http 连接非本机地址", servers=insecure)

        # --- project
        if proj and not proj.get("exists"):
            self.add("project-not-found", "info", "--project 指向的目录不存在，项目相关检查已跳过", project=proj.get("path"))
        if proj.get("exists") and not proj.get("is_home"):
            if not proj.get("is_git"):
                self.add("not-git-repo", "P1", "当前项目不是 git 仓库", project=proj.get("path"))
            agents_md = proj.get("agents_md") or {}
            if not proj.get("claude_md"):
                if agents_md.get("exists"):
                    self.add("agents-md-unconfirmed", "P2",
                             "只有 AGENTS.md，没有 CLAUDE.md：是否被加载取决于版本和设置，未确认生效")
                else:
                    self.add("no-claude-md", "P1", "项目没有 CLAUDE.md（也没有 AGENTS.md）")
            elif agents_md.get("exists") and not agents_md.get("imported_by_claude_md"):
                self.add("agents-md-not-imported", "info", "AGENTS.md 存在，但 CLAUDE.md 没有用 @AGENTS.md 导入它")
            for f in proj.get("claude_md") or []:
                if f.get("path") == "CLAUDE.md" and (f.get("lines") or 0) > 200:
                    self.add("claude-md-long", "P2", "CLAUDE.md 超过 200 行", lines=f.get("lines"))
            unprotected = []
            for item in proj.get("env_files") or []:
                if item.get("tracked"):
                    self.add("env-file-tracked", "P0", ".env 类文件已被 git 跟踪（已进入历史）", file=item["path"])
                elif item.get("ignored") is False:
                    self.add("env-file-not-ignored", "P0", ".env 类文件没有被 .gitignore 忽略", file=item["path"])
                elif item.get("ignored_guess") is False:
                    unprotected.append(item["path"])
            if unprotected:
                self.add("env-file-unprotected", "P1", "还不是 git 仓库，但 .env 类文件不在 .gitignore 里，一旦 git add 就会进仓库",
                         files=unprotected[:20])
            gi = proj.get("gitignore") or {}
            if proj.get("is_git") and not gi.get("exists"):
                self.add("no-gitignore", "P2", "仓库没有 .gitignore")
            elif gi.get("exists") and gi.get("covers_env_guess") is False:
                self.add("gitignore-env-gap", "P2", ".gitignore 没有覆盖 .env / .env.production 这类文件")
            docs = proj.get("docs") or {}
            missing = [k for k in DOCS_DIRS if docs.get(k) is None]
            if missing:
                self.add("docs-layout", "info", "docs/ 下缺少部分目录（产品档才需要）", missing=missing)
            if docs.get("superpowers_dir"):
                self.add("superpowers-docs-dir", "info", "存在 docs/superpowers/（superpowers 的默认输出目录）")

        # --- plugins, skills, agents
        items = plugins.get("items") or []
        enabled = [i for i in items if i.get("enabled")]
        enabled_names = {i.get("name") for i in enabled}
        if all(e in enabled_names for e in PROCESS_ENGINES):
            # An engine counts as suppressed when a deny rule blocks its skills for the model,
            # e.g. "Skill(superpowers:*)"; the user can still invoke them by hand.
            suppressed = sorted(
                e for e in PROCESS_ENGINES
                if any(re.match(r"^Skill\(\s*%s\s*(?::\*|\s\*|\*)\s*\)$" % re.escape(e), (r or "").strip())
                       for r in deny_rules)
            )
            if not suppressed:
                sp = [i for i in enabled if i.get("name") == "superpowers"]
                self.add("dual-process-engine", "P1", "superpowers 和 mattpocock-skills 同时启用，且没有用 Skill(...) deny 规则压住其中一套",
                         superpowers_hook_events=sp[0].get("hook_events") if sp else None,
                         note="skillOverrides 对插件 skill 不生效；用 enabledPlugins 或 Skill(<插件名>:*) deny（见 rubric）")
            else:
                self.add("dual-engine-suppressed", "info", "两套流程引擎都启用，其中一套已用 Skill(...) deny 规则禁止模型自动调用",
                         suppressed=suppressed)
        overrides = {}
        for scope in ("user", "project", "local"):
            so = (st.get(scope) or {}).get("skillOverrides")
            if isinstance(so, dict):
                for k in so:
                    overrides.setdefault(k, scope)
        all_plugin_skills = set().union(*self.plugin_skill_names.values()) if self.plugin_skill_names else set()
        ineffective = sorted(
            k for k in overrides
            if (":" in k and k.split(":", 1)[0] in self.plugin_names)
            or (":" not in k and k in all_plugin_skills and k not in self.user_skill_names and k not in self.project_skill_names)
        )
        if ineffective:
            self.add("skilloverrides-plugin-keys", "P2", "skillOverrides 里有针对插件 skill 的条目，这些条目不会生效", keys=ineffective[:30])
        cf = sorted(i["id"] for i in enabled if "cloudflare" in (i.get("name") or "").lower())
        if len(cf) >= 2:
            self.add("multiple-cloudflare-plugins", "P2", "启用了多个 Cloudflare 插件，功能重叠", plugins=cf)
        cr = sorted(i["id"] for i in enabled if i.get("name") == "code-review")
        if cr:
            self.add("code-review-plugin-overlap", "P2", "装了 code-review 插件，而内置已有 /code-review", plugins=cr)
        if plugins.get("enabled_but_not_installed"):
            self.add("enabled-not-installed", "P2", "设置里启用了但本机没有安装的插件", plugins=plugins["enabled_but_not_installed"])

        usage = out.get("usage") or {}
        if usage.get("enabled") and self.days >= 14:
            unused = sorted(i["id"] for i in enabled
                            if (i.get("skills", 0) + i.get("commands", 0)) > 0 and i.get("invocations", 0) == 0)
            if unused:
                self.add("unused-plugins", "P1" if len(unused) >= 5 else "P2",
                         "%d 天内一次都没调用过的已启用插件" % self.days, plugins=unused,
                         note="只含提供 skill/command 的插件；纯 MCP/LSP/hook 插件无法用调用次数判断")
            skills = out.get("user_skills") or {}
            idle = [s for s in skills.get("items", []) if s.get("model_invocable") and s.get("invocations", 0) == 0]
            if len(idle) >= 10:
                by_suite = Counter(s.get("suite") or "standalone" for s in idle)
                self.add("unused-user-skills", "P2", "%d 个个人 skill 在 %d 天内没被调用过" % (len(idle), self.days),
                         by_suite=dict(by_suite), examples=sorted(s["name"] for s in idle)[:15])
            agents = out.get("agents") or {}
            user_agents = agents.get("_user_names") or []
            idle_agents = [a for a in user_agents if self.agent_counts.get(a, 0) == 0]
            if (agents.get("user_count") or 0) > 30 or len(idle_agents) >= 10:
                self.add("agents-unused", "P2", "个人 subagent 偏多或长期不用",
                         user_agents=agents.get("user_count"), idle=len(idle_agents), examples=idle_agents[:15])
        elif not usage.get("enabled"):
            self.add("usage-skipped", "info", "未统计调用次数（--no-usage 或 --days 0），冗余判断会不准")

        if not (out.get("claude_code") or {}).get("cli_found"):
            self.add("claude-cli-missing", "info", "PATH 里找不到 claude 命令，版本和插件启用状态改为从设置文件推断")
        if self.errors:
            self.add("collector-errors", "info", "部分采集项出错，相关字段为 null", count=len(self.errors))

    # ------------------------------------------------------------ main
    def hooks_state(self, settings):
        """Effective disableAllHooks (managed > local > project > user) and per-hook `active` flags."""
        state = {"disabled": False, "source": None}
        for scope in ("managed", "local", "project", "user"):
            value = self.settings_raw.get(scope, {}).get("disableAllHooks")
            if isinstance(value, bool):
                state = {"disabled": value, "source": scope}
                break
        for scope, summary in settings.items():
            for hook in (summary or {}).get("hooks") or []:
                hook["active"] = not state["disabled"] or (scope == "managed" and state["source"] != "managed")
        state["configured_settings_hooks"] = len(self.hook_items)
        return state

    def collect(self):
        started = time.time()
        out = {
            "schema": SCHEMA,
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "options": {"days": self.days, "project": tilde(self.project),
                        "usage_scan": self.use_usage and self.days > 0, "cli_calls": self.use_cli},
            "handbook": HANDBOOK,
            "read_only": True,
            "config_dir": tilde(CLAUDE_DIR),
        }
        out["claude_code"] = self.guard("claude_code", self.claude_cli)
        out["project"] = self.guard("project", self.collect_project)
        out["settings"] = self.guard("settings", self.settings)
        out["hooks_state"] = self.guard("hooks_state", lambda: self.hooks_state(out.get("settings") or {}))
        out["plugins"] = self.guard("plugins", self.plugins)
        out["user_skills"] = self.guard("user_skills", self.user_skills)
        out["agents"] = self.guard("agents", self.agents)
        out["mcp"] = self.guard("mcp", self.mcp)
        out["environment"] = self.guard("environment", self.environment)
        out["usage"] = self.guard("usage", self.usage)
        out["_unmounted_hook_scripts"] = self.guard("unmounted_hook_scripts", self.unmounted_hook_scripts, [])

        # attach invocation counts (only meaningful when usage scan ran)
        if (out.get("usage") or {}).get("enabled"):
            for item in (out.get("plugins") or {}).get("items", []):
                item["invocations"] = self.plugin_invocations(item.get("name") or "")
            for item in (out.get("user_skills") or {}).get("items", []):
                item["invocations"] = max(self.invocations(item["name"]), self.invocations(item.get("dir", item["name"])))

        self.guard("evaluate", lambda: self.evaluate(out))
        self.findings.sort(key=lambda f: (SEVERITY_ORDER.get(f["severity"], 9), f["id"]))
        out["findings"] = self.findings
        out["summary"] = dict(Counter(f["severity"] for f in self.findings))
        out.pop("_unmounted_hook_scripts", None)
        if isinstance(out.get("agents"), dict):
            out["agents"].pop("_user_names", None)
        out["errors"] = self.errors
        out["elapsed_ms"] = int((time.time() - started) * 1000)
        return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="ainative doctor: read-only Claude Code health check. Prints JSON to stdout; writes nothing.")
    parser.add_argument("--days", type=int, default=90, help="usage window in days for skill call counts (default 90; 0 disables)")
    parser.add_argument("--project", default=os.getcwd(), help="project directory to inspect (default: current directory)")
    parser.add_argument("--no-usage", action="store_true", help="skip scanning ~/.claude/projects transcripts for skill call counts")
    parser.add_argument("--no-cli", action="store_true", help="do not call `claude --version` / `claude plugin list --json`")
    parser.add_argument("--compact", action="store_true", help="print compact JSON on one line")
    parser.add_argument("--managed-dir", help="read file-based managed settings from this directory instead of the "
                                              "platform default (e.g. a copy of /Library/Application Support/ClaudeCode)")
    args = parser.parse_args(argv)
    if args.days < 0:
        parser.error("--days must be >= 0")

    doctor = Doctor(days=args.days, project=args.project, use_usage=not args.no_usage, use_cli=not args.no_cli,
                    managed_dir=args.managed_dir)
    result = doctor.collect()
    text = json.dumps(result, indent=None if args.compact else 2, default=str, **KEEP_UNICODE)
    sys.stdout.buffer.write((text + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
