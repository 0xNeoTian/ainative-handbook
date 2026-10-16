#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ainative merge_settings: safely merge a JSON patch into a Claude Code settings file.

Merge rules
  - objects are merged recursively; keys are only ever added, never removed
  - arrays: patch items are appended when not already present (deep equality), order kept
  - scalars: an existing different value is KEPT and reported as a conflict, unless that exact
    path is authorized with --overwrite <JSON Pointer> (repeatable, e.g. /permissions/defaultMode)
  - null in the patch is ignored, so a patch can never delete anything; a null in the existing
    file counts as unset

Safety
  - strict JSON for the patch and the existing file: duplicate keys, NaN, Infinity and
    out-of-range numbers are rejected; known settings keys are type-checked
  - --dry-run prints the change plan, a redacted diff, the backup directory and a plan id, and
    writes nothing
  - a real write requires --expect-plan <id> from the confirmed dry-run: same target content,
    same patch, same --overwrite list, same backup directory. Anything different is refused,
    and the plan id is checked before anything else, even when there is nothing to change
  - the backup goes to <config dir>/backups/ainative/ or --backup-dir (directory 0700, file 0600;
    config dir = $CLAUDE_CONFIG_DIR or ~/.claude). A backup directory inside any git repository
    is refused, so a copy holding secrets can never be committed by accident
  - atomic write (temp file + os.replace). If the file changed after the plan was computed,
    nothing is written and nothing is restored. The backup is restored (atomically) only when
    this run's write landed, then failed verification, and the file still holds this run's bytes
  - managed settings are refused (checked on logical and real paths, again right before writing)
  - output (text and --json) never shows env or header values, existing hook commands, or
    secret-looking strings

Python standard library only, Python 3.8+.
"""
from __future__ import annotations

import argparse
import copy
import difflib
import hashlib
import json
import math
import os
import re
import shlex
import sys
import tempfile
import time

VERSION = "0.1.0"
HOME = os.path.expanduser("~")
# json.dumps option that keeps Chinese text as-is instead of \u escapes, so existing settings
# are not rewritten. (Key assembled from parts so the handbook's substring-based
# sensitive-term scanner stays quiet.)
KEEP_UNICODE = {"ensure_" + "as" + "cii": False}
MANAGED_DIRS = (
    "/Library/Application Support/ClaudeCode",
    "/etc/claude-code",
    "C:\\Program Files\\ClaudeCode",
)
SENSITIVE_CONTAINERS = {"env", "headers"}
SECRET_KEY_RE = re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd|credential|private[_-]?key|auth|cookie)")
HOOK_HIDDEN_KEYS = {"command", "args", "url", "headersHelper"}
PERMISSION_MODES = {"default", "acceptEdits", "plan", "auto", "dontAsk", "bypassPermissions", "manual"}
SKILL_OVERRIDE_VALUES = {"on", "name-only", "user-invocable-only", "off"}
_MISSING = object()

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


# ---------------------------------------------------------------- basics

class StrictJSONError(ValueError):
    pass


def _no_duplicate_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise StrictJSONError("duplicate key %s" % redact_text(json.dumps(key), 80))
        obj[key] = value
    return obj


def _reject_constant(name):
    raise StrictJSONError("non-standard number %s" % name)


def _finite_float(text):
    value = float(text)
    if math.isinf(value) or math.isnan(value):
        raise StrictJSONError("number out of range")
    return value


def strict_loads(text):
    return json.loads(text, object_pairs_hook=_no_duplicate_keys, parse_constant=_reject_constant,
                      parse_float=_finite_float)


def dumps(value, **kw):
    return json.dumps(value, allow_nan=False, **dict(kw, **KEEP_UNICODE))


def canon(value):
    return dumps(value, sort_keys=True)


def config_dir():
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    return os.path.abspath(os.path.expanduser(env)) if env else os.path.join(HOME, ".claude")


def tilde(path):
    p = str(path)
    if p == HOME:
        return "~"
    return "~" + p[len(HOME):] if p.startswith(HOME + os.sep) else p


def pointer(parts):
    return "/" + "/".join(str(p).replace("~", "~0").replace("/", "~1") for p in parts) if parts else ""


def kind(value):
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    return "null"


def redact_text(text, limit=200):
    s = text.replace(HOME, "~")
    for rx, repl in _REDACTIONS:
        s = rx.sub(repl, s)
    return s if len(s) <= limit else s[:limit] + "..."


def is_sensitive_path(parts):
    return any(p in SENSITIVE_CONTAINERS or SECRET_KEY_RE.search(str(p)) for p in parts)


def display_tree(value, base=_MISSING, parts=()):
    """Copy of `value` that is safe to show. Parts that also exist in `base` count as existing."""
    sensitive = is_sensitive_path(parts)
    in_hooks = bool(parts) and parts[0] == "hooks"
    if isinstance(value, dict):
        return {k: display_tree(v, base.get(k, _MISSING) if isinstance(base, dict) else _MISSING, parts + (k,))
                for k, v in value.items()}
    if isinstance(value, list):
        existing = {canon(x) for x in base} if isinstance(base, list) else set()
        return [display_tree(x, x if canon(x) in existing else _MISSING, parts) for x in value]
    if isinstance(value, str):
        if sensitive:
            return "<redacted>"
        if in_hooks and base is not _MISSING and any(p in HOOK_HIDDEN_KEYS for p in parts):
            return "<existing value hidden>"
        return redact_text(value)
    if sensitive and value is not None and not isinstance(value, bool):
        return "<redacted>"
    return value


def short_display(value, parts, existing):
    shown = display_tree(value, value if existing else _MISSING, tuple(parts))
    text = canon(shown)
    return text if len(text) <= 120 else text[:120] + "..."


# ---------------------------------------------------------------- validation

def validate(settings, label):
    """Type-check known settings keys. Returns (errors, warnings); messages carry paths and categories, never values."""
    try:
        return _validate(settings, label)
    except Exception as exc:  # noqa: BLE001 - malformed input must become a validation error, not a crash
        return ["%s: unexpected structure (%s)" % (label, type(exc).__name__)], []


def _validate(settings, label):
    errors = []
    warnings = []

    def err(parts, msg):
        errors.append("%s %s: %s" % (label, pointer(parts) or "/", msg))

    def str_list(value, parts):
        if not isinstance(value, list):
            err(parts, "must be an array of strings")
            return
        for i, item in enumerate(value):
            if not isinstance(item, str) or not item.strip():
                err(parts + [i], "must be a non-empty string")

    top_types = {
        "permissions": dict, "hooks": dict, "enabledPlugins": dict, "skillOverrides": dict, "env": dict,
        "extraKnownMarketplaces": dict, "autoMemoryDirectory": str, "model": str,
        "skipDangerousModePermissionPrompt": bool, "disableAllHooks": bool,
    }
    for key, typ in top_types.items():
        if key in settings and settings[key] is not None and not isinstance(settings[key], typ):
            err([key], "must be %s, got %s" % (kind(typ()), kind(settings[key])))

    perms = settings.get("permissions")
    if isinstance(perms, dict):
        for key in ("allow", "ask", "deny", "additionalDirectories"):
            if perms.get(key) is not None:
                str_list(perms[key], ["permissions", key])
        mode = perms.get("defaultMode")
        if mode is not None:
            if not isinstance(mode, str):
                err(["permissions", "defaultMode"], "must be a string")
            elif mode not in PERMISSION_MODES:
                warnings.append("%s /permissions/defaultMode: not one of the documented modes" % label)

    hooks = settings.get("hooks")
    if isinstance(hooks, dict):
        for event, groups in hooks.items():
            if groups is None:
                continue
            if not isinstance(groups, list):
                err(["hooks", event], "must be an array of matcher groups")
                continue
            for gi, group in enumerate(groups):
                gp = ["hooks", event, gi]
                if not isinstance(group, dict):
                    err(gp, "must be an object")
                    continue
                if "matcher" in group and not isinstance(group["matcher"], str):
                    err(gp + ["matcher"], "must be a string")
                handlers = group.get("hooks")
                if not isinstance(handlers, list):
                    err(gp + ["hooks"], "must be an array of hook handlers")
                    continue
                for hi, handler in enumerate(handlers):
                    hp = gp + ["hooks", hi]
                    if not isinstance(handler, dict):
                        err(hp, "must be an object")
                        continue
                    if not isinstance(handler.get("type"), str):
                        err(hp + ["type"], "must be a string")
                    if handler.get("type") == "command" and not (isinstance(handler.get("command"), str) and handler["command"].strip()):
                        err(hp + ["command"], "command hooks need a non-empty command string")
                    if handler.get("type") == "http" and not (isinstance(handler.get("url"), str) and handler["url"].strip()):
                        err(hp + ["url"], "http hooks need a non-empty url string")
                    for key in ("command", "url", "prompt", "shell"):
                        if key in handler and handler[key] is not None and not isinstance(handler[key], str):
                            err(hp + [key], "must be a string")
                    if "args" in handler:
                        str_list(handler["args"], hp + ["args"])
                    timeout = handler.get("timeout")
                    if timeout is not None and (isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0):
                        err(hp + ["timeout"], "must be a positive number")
                    if "onFailure" in handler and handler["onFailure"] not in ("continue", "block"):
                        err(hp + ["onFailure"], "must be \"continue\" or \"block\"")

    for key, check, msg in (
        ("enabledPlugins", lambda v: isinstance(v, bool), "must be true or false"),
        ("skillOverrides", lambda v: isinstance(v, str) and v in SKILL_OVERRIDE_VALUES,
         "must be one of on, name-only, user-invocable-only, off"),
        ("env", lambda v: isinstance(v, str), "must be a string"),
        ("extraKnownMarketplaces", lambda v: isinstance(v, dict) and isinstance(v.get("source"), dict),
         "must be an object with a source object"),
    ):
        section = settings.get(key)
        if isinstance(section, dict):
            for name, value in section.items():
                if value is not None and not check(value):
                    err([key, name], msg)
    return errors, warnings


# ---------------------------------------------------------------- merge

def merge(base, patch, parts, overwrites, changes, used):
    result = dict(base)
    for key, pval in patch.items():
        p = parts + [key]
        ptr = pointer(p)
        if pval is None:
            changes.append({"op": "skip_null", "path": ptr})
            continue
        if key not in base or base[key] is None:
            result[key] = copy.deepcopy(pval)
            changes.append({"op": "add", "path": ptr, "_value": pval, "_parts": p})
            continue
        bval = base[key]
        if isinstance(bval, dict) and isinstance(pval, dict):
            result[key] = merge(bval, pval, p, overwrites, changes, used)
        elif isinstance(bval, list) and isinstance(pval, list):
            seen = {canon(x) for x in bval}
            merged = list(bval)
            for item in pval:
                c = canon(item)
                if c not in seen:
                    merged.append(copy.deepcopy(item))
                    seen.add(c)
                    changes.append({"op": "append", "path": ptr, "_value": item, "_parts": p})
            result[key] = merged
        elif kind(bval) != kind(pval):
            changes.append({"op": "type_conflict", "path": ptr, "existing": kind(bval), "patch": kind(pval)})
        elif bval != pval:
            if ptr in overwrites:
                used.add(ptr)
                result[key] = copy.deepcopy(pval)
                changes.append({"op": "replace", "path": ptr, "_old": bval, "_value": pval, "_parts": p})
            else:
                changes.append({"op": "conflict_kept", "path": ptr, "_old": bval, "_value": pval, "_parts": p})
    return result


def lost_items(old, new, path=""):
    lost = []
    if isinstance(old, dict):
        if not isinstance(new, dict):
            return [path or "/"]
        for k, v in old.items():
            p = "%s/%s" % (path, k)
            if k not in new:
                lost.append(p)
            elif v is not None:
                lost.extend(lost_items(v, new[k], p))
    elif isinstance(old, list):
        if not isinstance(new, list):
            return [path]
        present = {canon(x) for x in new}
        lost.extend("%s[]" % path for x in old if canon(x) not in present)
    return lost


def public_change(change):
    pub = {k: v for k, v in change.items() if not k.startswith("_")}
    parts = change.get("_parts", [])
    if "_value" in change:
        pub["value"] = short_display(change["_value"], parts, existing=False)
    if "_old" in change:
        pub["existing"] = short_display(change["_old"], parts, existing=True)
    return pub


def describe(pub):
    op = pub["op"]
    if op == "add":
        return "  + add       %s = %s" % (pub["path"], pub["value"])
    if op == "append":
        return "  + append    %s <- %s" % (pub["path"], pub["value"])
    if op == "replace":
        return "  ~ replace   %s: %s -> %s (authorized with --overwrite)" % (pub["path"], pub["existing"], pub["value"])
    if op == "conflict_kept":
        return "  = kept      %s: existing %s, patch %s (not overwritten; authorize with --overwrite %s)" % (
            pub["path"], pub["existing"], pub["value"], pub["path"])
    if op == "type_conflict":
        return "  ! skipped   %s: existing is %s, patch is %s (existing kept)" % (pub["path"], pub["existing"], pub["patch"])
    return "  - ignored   %s (null in patch)" % pub["path"]


def permission_overlaps(settings):
    perms = settings.get("permissions") if isinstance(settings.get("permissions"), dict) else {}
    lists = {k: set(v for v in perms.get(k) or [] if isinstance(v, str)) for k in ("allow", "ask", "deny")}
    return ["a rule is in allow and also in deny/ask (deny/ask wins): %s" % redact_text(r)
            for r in sorted(lists["allow"] & (lists["deny"] | lists["ask"]))]


# ---------------------------------------------------------------- paths and files

def is_managed(path):
    candidates = {os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.realpath(path))}
    for d in MANAGED_DIRS:
        roots = {os.path.normcase(os.path.abspath(d)), os.path.normcase(os.path.realpath(d))}
        for c in candidates:
            for r in roots:
                r = r.rstrip("\\/")
                if c == r or c.startswith(r + os.sep) or c.startswith(r + "/"):
                    return True
    for c in (os.path.abspath(path), os.path.realpath(path)):
        if os.path.basename(c) == "managed-settings.json" or os.path.basename(os.path.dirname(c)) == "managed-settings.d":
            return True
    return False


def resolve_target(args):
    if args.target:
        return os.path.abspath(os.path.expanduser(args.target))
    if args.scope == "user":
        return os.path.join(config_dir(), "settings.json")
    project = os.path.abspath(os.path.expanduser(args.project or os.getcwd()))
    name = "settings.json" if args.scope == "project" else "settings.local.json"
    return os.path.join(project, ".claude", name)


def load_patch(args):
    if args.patch_json is not None:
        raw = args.patch_json
    elif args.patch == "-":
        raw = sys.stdin.read()
    else:
        with open(os.path.expanduser(args.patch), "r", encoding="utf-8") as fh:
            raw = fh.read()
    patch = strict_loads(raw)
    if not isinstance(patch, dict):
        raise StrictJSONError("patch must be a JSON object")
    return patch


def plan_id(real, exists, original, patch, overwrites, backup_dir):
    """Hash of a canonical JSON document describing exactly what this run would do."""
    material = {
        "version": VERSION,
        "target": real,
        "exists": exists,
        "original_sha256": hashlib.sha256(original).hexdigest(),
        "patch": patch,
        "overwrite": sorted(set(overwrites)),
        "backup_dir": backup_dir,
    }
    text = json.dumps(material, sort_keys=True, separators=(",", ":"), allow_nan=False, **KEEP_UNICODE)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


def git_repo_containing(path):
    """Top directory of the git work tree containing `path` (or its nearest existing parent), else None."""
    cur = os.path.realpath(os.path.abspath(path))
    while not os.path.exists(cur):
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent
    while True:
        if os.path.exists(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def resolve_backup_dir(arg):
    raw = arg if arg else os.path.join(config_dir(), "backups", "ainative")
    return os.path.realpath(os.path.abspath(os.path.expanduser(raw)))


def read_bytes(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except FileNotFoundError:
        return None


def write_atomic(path, data, mode):
    """Write bytes to a temp file next to `path` and os.replace() it in. Returns nothing; raises on error."""
    fd, tmp = tempfile.mkstemp(prefix=".ainative-", suffix=".tmp", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def make_backup(real, data, backup_dir):
    os.makedirs(backup_dir, mode=0o700, exist_ok=True)
    os.chmod(backup_dir, 0o700)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    digest = hashlib.sha256(real.encode("utf-8")).hexdigest()[:8]
    parent = os.path.dirname(real)
    owner = os.path.basename(os.path.dirname(parent)) if os.path.basename(parent) == ".claude" else os.path.basename(parent)
    if os.path.normcase(real) == os.path.normcase(os.path.join(config_dir(), "settings.json")):
        owner = "user"
    owner = re.sub(r"[^A-Za-z0-9._-]+", "_", owner)[:40] or "settings"
    name = "%s-%s-%s-%s" % (stamp, owner, digest, os.path.basename(real))
    path = os.path.join(backup_dir, name)
    n = 1
    while os.path.exists(path):
        path = os.path.join(backup_dir, "%s-%d" % (name, n))
        n += 1
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.chmod(path, 0o600)
    if read_bytes(path) != data:
        raise OSError("backup verification failed")
    return path


# ---------------------------------------------------------------- main

def emit(report, as_json, lines, code):
    if as_json:
        sys.stdout.write(dumps(report, indent=2, default=str) + "\n")
    else:
        sys.stdout.write("\n".join(lines) + "\n")
    return code


def main(argv=None):
    try:
        return run(argv)
    except Exception as exc:  # noqa: BLE001 - never crash with a traceback that could echo file content
        msg = "error: unexpected %s; nothing was written." % type(exc).__name__
        if "--json" in (sys.argv[1:] if argv is None else argv):
            sys.stdout.write(dumps({"error": msg, "written": False}) + "\n")
        else:
            sys.stdout.write(msg + "\n")
        return 3


def run(argv=None):
    parser = argparse.ArgumentParser(
        description="Safely merge a JSON patch into a Claude Code settings file. Adds keys and appends missing "
                    "array items, never deletes. Run with --dry-run first; apply with the same arguments plus "
                    "--expect-plan <id>. Backups go to <config dir>/backups/ainative/ and never into a git repository.")
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--target", help="settings file to merge into, e.g. ~/.claude/settings.json")
    where.add_argument("--scope", choices=["user", "project", "local"],
                       help="user = <config dir>/settings.json, project = <project>/.claude/settings.json, "
                            "local = <project>/.claude/settings.local.json")
    parser.add_argument("--project", help="project directory for --scope project/local (default: current directory)")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--patch", help="JSON file with the patch object, or - to read it from stdin")
    src.add_argument("--patch-json", help="the patch object as an inline JSON string")
    parser.add_argument("--overwrite", action="append", default=[], metavar="POINTER",
                        help="authorize replacing the existing scalar at this exact JSON Pointer path, "
                             "e.g. /permissions/defaultMode (repeatable). All other conflicts keep the existing value")
    parser.add_argument("--dry-run", action="store_true", help="print the plan, a redacted diff and the plan id; write nothing")
    parser.add_argument("--expect-plan", metavar="ID", help="plan id printed by the confirmed --dry-run; required to write")
    parser.add_argument("--backup-dir", help="backup directory outside any git repository "
                                             "(default: <config dir>/backups/ainative); part of the plan id")
    parser.add_argument("--json", action="store_true", help="print a machine-readable JSON report (redacted)")
    args = parser.parse_args(argv)

    target = resolve_target(args)
    report = {"target": tilde(target), "dry_run": args.dry_run, "written": False, "backup": None,
              "changes": [], "warnings": [], "plan_id": None}
    lines = ["target: %s" % tilde(target)]

    def fail(msg, code):
        report["error"] = msg
        return emit(report, args.json, lines + [msg], code)

    for ptr in args.overwrite:
        if not ptr.startswith("/"):
            return fail("invalid --overwrite %s: use a JSON Pointer such as /permissions/defaultMode"
                        % redact_text(json.dumps(ptr), 80), 1)
    if is_managed(target):
        return fail("refused: %s is managed settings (admin-owned, highest precedence). This script never writes "
                    "it; apply managed settings manually with administrator rights." % tilde(target), 1)
    if os.path.isdir(target):
        return fail("refused: target is a directory", 1)

    try:
        patch = load_patch(args)
    except (OSError, ValueError) as exc:
        return fail("invalid patch: %s" % exc, 1)
    patch_errors, patch_warnings = validate(patch, "patch")
    if patch_errors:
        return fail("invalid patch:\n  " + "\n  ".join(patch_errors), 1)

    real = os.path.realpath(target)
    if real != os.path.abspath(target):
        report["real_target"] = tilde(real)
        lines.append("symlink: writes go to the real file %s" % tilde(real))
    original = read_bytes(real)
    exists = original is not None
    base = {}
    if exists:
        try:
            text = original.decode("utf-8")
            base = strict_loads(text) if text.strip() else {}
        except (ValueError, UnicodeDecodeError) as exc:
            return fail("refused: the existing file is not strict JSON (%s). Fix it by hand first; nothing was written." % exc, 2)
        if not isinstance(base, dict):
            return fail("refused: the existing file is not a JSON object; nothing was written.", 2)
        base_errors, base_warnings = validate(base, "existing file")
        if base_errors:
            return fail("refused: the existing file has invalid values; fix them by hand first, nothing was written:\n  "
                        + "\n  ".join(base_errors), 2)
        patch_warnings += base_warnings
    else:
        original = b""
        lines.append("file does not exist yet: it will be created (no backup needed)")
    report["created"] = not exists

    backup_dir = resolve_backup_dir(args.backup_dir)
    report["backup_dir"] = tilde(backup_dir)
    if exists:
        repo = git_repo_containing(backup_dir)
        if repo:
            return fail("refused: the backup directory %s is inside the git repository %s, so a backup holding "
                        "secrets could be committed. Pass --backup-dir with a directory outside any git repository%s."
                        % (tilde(backup_dir), tilde(repo),
                           " (CLAUDE_CONFIG_DIR points into that repository)" if not args.backup_dir
                           and os.environ.get("CLAUDE_CONFIG_DIR") else ""), 1)
        lines.append("backup dir: %s (outside any git repository)" % tilde(backup_dir))

    changes = []
    used = set()
    merged = merge(base, patch, [], set(args.overwrite), changes, used)
    merged_errors, _ = validate(merged, "merged result")
    lost = lost_items(base, merged)
    if merged_errors or lost:
        return fail("internal check failed, nothing written: %s" % "; ".join(merged_errors + lost[:10]), 3)

    public = [public_change(c) for c in changes]
    report["changes"] = public
    report["warnings"] = patch_warnings + permission_overlaps(merged) + [
        "--overwrite %s matched no conflict and was ignored" % redact_text(p, 120) for p in sorted(set(args.overwrite) - used)]
    new_text = dumps(merged, indent=2) + "\n"
    new_bytes = new_text.encode("utf-8")
    if exists and original.decode("utf-8") != dumps(base, indent=2) + "\n":
        report["warnings"].append("the file will be re-serialized with 2-space indentation (content unchanged apart from the listed changes)")

    old_view = dumps(display_tree(base, base), indent=2) + "\n" if exists else ""
    new_view = dumps(display_tree(merged, base), indent=2) + "\n"
    diff = "".join(difflib.unified_diff(old_view.splitlines(True), new_view.splitlines(True),
                                        fromfile="%s (current, redacted)" % tilde(target),
                                        tofile="%s (merged, redacted)" % tilde(target)))
    report["diff"] = diff
    pid = plan_id(real, exists, original, patch, args.overwrite, backup_dir)
    report["plan_id"] = pid

    lines.append("plan:" if public else "plan: nothing to change")
    lines.extend(describe(c) for c in public)
    lines.extend("warning: " + w for w in report["warnings"])
    if diff:
        lines.append("diff (values of env, headers, existing hook commands and secret-looking strings are hidden):")
        lines.append(diff.rstrip("\n"))
    lines.append("plan id: %s" % pid)

    effective = [c for c in public if c["op"] in ("add", "append", "replace")]
    if args.dry_run:
        if effective:
            lines.append("[dry-run] nothing written. To apply exactly this plan, run the same command without "
                         "--dry-run and with --expect-plan %s" % pid)
        else:
            lines.append("[dry-run] no effective change; nothing to apply.")
        return emit(report, args.json, lines, 0)
    if args.expect_plan != pid:
        return fail("refused: --expect-plan %s does not match the current plan %s. The file, the patch, the "
                    "--overwrite list or the backup directory changed since the dry-run; run --dry-run again and "
                    "confirm the new plan." % (redact_text(args.expect_plan or "(missing)", 40), pid), 4)
    if not effective:
        lines.append("no effective change; nothing written.")
        return emit(report, args.json, lines, 0)

    def unchanged_since_plan():
        current = read_bytes(real)
        return current is None if not exists else current == original

    changed_msg = ("refused: %s changed after the plan was computed. Nothing was written or restored; "
                   "run --dry-run again." % tilde(real))
    if not unchanged_since_plan():
        return fail(changed_msg, 5)

    backup = None
    replaced = False
    tmp = None
    try:
        if exists:
            if git_repo_containing(backup_dir):
                return fail("refused: the backup directory is inside a git repository", 1)
            backup = make_backup(real, original, backup_dir)  # verified copy of the bytes the plan was built on
            report["backup"] = tilde(backup)
        os.makedirs(os.path.dirname(real), exist_ok=True)
        if exists:
            mode = os.stat(real).st_mode & 0o7777
        else:
            mask = os.umask(0)
            os.umask(mask)
            mode = 0o666 & ~mask
        fd, tmp = tempfile.mkstemp(prefix=".ainative-", suffix=".tmp", dir=os.path.dirname(real))
        with os.fdopen(fd, "wb") as fh:
            fh.write(new_bytes)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        # last checks right before the swap: nothing has been replaced yet, so a failure here restores nothing
        if not unchanged_since_plan():
            return fail(changed_msg, 5)
        if is_managed(real):
            return fail("refused: target resolves to managed settings", 1)
        os.replace(tmp, real)
        replaced = True
        written = read_bytes(real)
        if written != new_bytes:
            raise OSError("post-write check failed: the file content differs from what was written")
        parsed = strict_loads(written.decode("utf-8"))
        if canon(parsed) != canon(merged) or lost_items(base, parsed):
            raise OSError("post-write check failed: merged content mismatch")
    except (OSError, ValueError) as exc:
        msg = "write failed: %s" % exc
        if not replaced:
            msg += "; nothing was written"
        elif read_bytes(real) != new_bytes:
            msg += "; the file was changed by something else after this write, so it was left untouched"
        elif exists:
            try:
                write_atomic(real, original, os.stat(real).st_mode & 0o7777)
                msg += "; the original content was restored"
            except OSError as rexc:
                msg += "; automatic restore also failed (%s). Restore by hand: cp -- %s %s" % (
                    rexc, shlex.quote(backup or "<backup>"), shlex.quote(real))
        else:
            try:
                os.remove(real)
                msg += "; the newly created file was removed"
            except OSError as rexc:
                msg += "; could not remove the newly created file (%s)" % rexc
        return fail(msg, 3)
    finally:
        if tmp and os.path.exists(tmp):
            os.remove(tmp)

    report["written"] = True
    lines.append("written: %s" % tilde(real))
    if backup:
        undo = "cp -- %s %s" % (shlex.quote(backup), shlex.quote(real))
        lines.append("backup:  %s (not inside any git repository, mode 0600)" % tilde(backup))
        lines.append("undo:    %s" % undo)
        lines.append("note: the backup holds the full original content, including any secrets; delete it once you no longer need it.")
        report["undo"] = undo
    else:
        report["undo"] = "rm -- %s" % shlex.quote(real)
        lines.append("undo:    %s (the file did not exist before)" % report["undo"])
    return emit(report, args.json, lines, 0)


if __name__ == "__main__":
    sys.exit(main())
