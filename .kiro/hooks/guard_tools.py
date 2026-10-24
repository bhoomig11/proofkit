"""Kiro PreToolUse guard for ProofKit: exit 0 allows the tool call, exit 2 blocks it.

Blocks destructive git and shell commands, uploads, .env paths, writes to FROZEN paths or .git/, and
writes outside the branch's owned paths (FROZEN/OWNED/ANYONE from scripts/check_ownership.py).
Standard library only. Logs one line per call to <tempdir>/kiro-guard.log, never inside the repo.
"""
from __future__ import annotations

import fnmatch
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterator

LOG_PATH = os.path.join(tempfile.gettempdir(), "kiro-guard.log")
NAME_KEYS = ("tool_name", "toolName", "tool", "name")
INPUT_KEYS = ("tool_input", "toolInput", "input", "arguments", "rawInput", "parameters")
SHELL_KEYS = {"command", "cmd", "script", "commandLine"}
PATH_KEYS = {"path", "paths", "file", "files", "file_path", "filePath", "targetFile", "target_file",
             "source", "destination", "old_path", "new_path", "oldPath", "newPath", "includePattern"}
CONTENT_KEYS = {"content", "new_str", "old_str", "newText"}
WRITE_VERBS = ("write", "edit", "create", "replace", "insert", "append", "delete", "remove", "move", "rename")
SEG = r"[^|;&\n]*"  # stays inside one shell command segment
GIT = r"\bgit(?:\.exe)?['\"]?(?:\s+(?:-[cC]\s+\S+|--?[\w-]+(?:=\S+)?))*\s+"
GIT_SUBS = "push|commit|reset|rebase|merge|checkout|switch|stash|clean|tag|worktree|remote|config|cherry-pick|revert|am|filter-branch|update-ref"
UPLOAD = (r"(?-i:-[dFT])(?![a-z])|--data|--form|--upload-file|--json|--post-|--body-|-body\b|-infile\b"
          r"|-form\b|(?:-x|--request|--?method)[\s=:]*['\"]?(?:post|put|patch)\b")
SHELL_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("git write command", re.compile(rf"{GIT}(?:{GIT_SUBS})(?![\w-])", re.I)),
    ("git branch delete", re.compile(rf"\bgit(?:\.exe)?\b{SEG}\bbranch\b{SEG}\s(?:-d|--delete)\b", re.I)),
    ("recursive rm", re.compile(rf"(?<![\w-])rm(?![\w-]){SEG}\s(?:-[dfiv]*r[dfiv]*|-r[a-z]*|--recursive)\b", re.I)),
    ("Remove-Item -Recurse", re.compile(rf"\b(?:remove-item|ri|del|erase)\b{SEG}\s-r[a-z]*\b", re.I)),
    ("rmdir", re.compile(r"\brmdir\b", re.I)),
    ("del /s", re.compile(rf"\b(?:del|erase)\b{SEG}\s/s\b", re.I)),
    ("network upload", re.compile(rf"\b(?:curl|wget|invoke-webrequest|iwr|invoke-restmethod|irm)\b{SEG}\s(?:{UPLOAD})", re.I)),
]
ENV_RE = re.compile(r"(?<![\w.-])\.env(?:\.([\w.*-]*))?(?![\w.-])", re.I)


def walk(obj: Any) -> Iterator[tuple[str, Any]]:
    """Yield every (key, value) pair from nested dicts and lists."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield str(key), value
            yield from walk(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk(item)


def strings(value: Any) -> list[str]:
    return [v for v in (value if isinstance(value, list) else [value]) if isinstance(v, str)]


def names_env(text: str) -> bool:
    """True if text names .env or .env.<x> as a whole path segment; .env.example is allowed."""
    return any((m.group(1) or "").lower() != "example" for m in ENV_RE.finditer(text))


def write_reason(paths: list[str], root: str) -> str | None:
    """Check in-repo write targets against .git/, FROZEN and the current branch's owned paths."""
    rels: list[str] = []
    for raw in paths:
        try:
            rel = os.path.relpath(os.path.abspath(os.path.join(root, raw)), root).replace(os.sep, "/")
        except ValueError:  # another drive, so outside the repo
            continue
        if rel not in (".", "..") and not rel.startswith("../"):
            rels.append(rel)
    if not rels:
        return None
    try:
        spec = importlib.util.spec_from_file_location("check_ownership", os.path.join(root, "scripts", "check_ownership.py"))
        rules = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(rules)  # type: ignore[union-attr]
        frozen, owned, anyone = list(rules.FROZEN), dict(rules.OWNED), list(rules.ANYONE)
    except Exception as exc:  # fail closed: no ownership data, no writes
        return f"cannot load scripts/check_ownership.py ({type(exc).__name__})"
    try:
        branch = subprocess.run(["git", "branch", "--show-current"], cwd=root, capture_output=True,
                                text=True, timeout=5, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        branch = ""
    prefix = next((p for p in owned if branch.startswith(p)), None)
    if branch != "main" and prefix is None:
        return f"branch '{branch or 'unknown'}' has no owner prefix ({', '.join(owned)}) and is not main"
    for rel in rels:
        if ".git" in rel.lower().split("/"):
            return f"{rel} is inside .git/"
        if any(fnmatch.fnmatch(rel, g) for g in frozen):
            return f"{rel} is FROZEN (contract change protocol, docs/05_INTEGRATION.md)"
        if prefix and not any(fnmatch.fnmatch(rel, g) for g in [*owned[prefix], *anyone, ".kiro/specs/*"]):
            return f"{rel} is outside {prefix} ownership"
    return None


def check(tool: str, data: Any, root: str) -> str | None:
    """Return the reason to block this tool call, or None to allow it."""
    pairs = list(walk(data))
    for key, value in pairs:
        if key in SHELL_KEYS:
            command = " ".join(strings(value))
            hit = next((label for label, rule in SHELL_RULES if rule.search(command)), None)
            if hit or names_env(command):
                return f"{hit or '.env reference'} in shell command"
    paths = [s for key, value in pairs if key in PATH_KEYS for s in strings(value)]
    if any(names_env(p) for p in paths):
        return "path names a .env file"
    if any(v in tool.lower() for v in WRITE_VERBS) or any(k in CONTENT_KEYS for k, _ in pairs):
        return write_reason(paths, root)
    return None


def main() -> int:
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8-sig", errors="replace"))
    except ValueError:
        return 0
    if not isinstance(payload, dict):
        return 0
    tool = next((v for k in NAME_KEYS if isinstance(v := payload.get(k), str) and v), "")
    data = next((v for k in INPUT_KEYS if (v := payload.get(k)) is not None), {})
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError:
            data = {"command": data}
    try:
        reason = check(tool, data, os.path.abspath(os.getcwd()))
    except Exception as exc:  # fail closed if the guard itself breaks
        reason = f"guard error ({type(exc).__name__})"
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} tool={tool[:80] or '?'} {'BLOCK ' + reason if reason else 'ALLOW'}\n")
    except OSError:
        pass  # logging must never break the hook
    if reason:
        print(f"BLOCKED by guard: {reason}".encode("ascii", "backslashreplace").decode(), file=sys.stderr)
    return 2 if reason else 0


if __name__ == "__main__":
    sys.exit(main())
