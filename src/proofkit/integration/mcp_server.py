"""
FINAL: RenewRight, a read-only MCP server over newline-delimited JSON-RPC 2.0 on stdio.

Runs offline on the synthetic fixtures with `demo_llm()` and today = the fixtures' `demo_today`, so it needs no
API key and no network. Tools: list_members, member_status, wallet_months, sms_reminder, triage.

stdout carries only JSON-RPC response lines. Logging goes to stderr and never includes note or document content.
Tool outputs carry statuses, dates, money and template text only; never note quotes or document text.
"""
from __future__ import annotations

import json
import logging
import re
import sys
from collections.abc import Callable, Mapping
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, TextIO

from proofkit.common.redact import get_logger
from proofkit.contracts import (
    ClinicalNote,
    EarningsDocument,
    Member,
    MonthlyCompliance,
    OverallStatus,
    ProofKitStatus,
)
from proofkit.integration.demo import demo_llm
from proofkit.integration.orchestrator import run_member
from proofkit.integration.reminder import sms_reminder

__all__ = ["handle", "main", "serve"]

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "fixtures"
CONFIG = ROOT / "config"
FRAILTY_RULES_PATH = CONFIG / "frailty_rules.json"
WALLET_RULES_PATH = CONFIG / "wallet_rules.json"

SERVER_INFO: Mapping[str, str] = MappingProxyType({"name": "renewright", "version": "1.0.0"})
SUPPORTED_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
LATEST_PROTOCOL = SUPPORTED_PROTOCOLS[0]
MAX_LINE_CHARS = 1_000_000
MEMBER_ID_PATTERN = r"^SYN-\d{4}$"
_MEMBER_ID_RE = re.compile(r"SYN-\d{4}")

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

_STATUS_RANK: Mapping[OverallStatus, int] = MappingProxyType(
    {OverallStatus.AT_RISK: 0, OverallStatus.NEEDS_REVIEW: 1, OverallStatus.PROTECTED: 2})
_CENT = Decimal("0.01")

log = get_logger(__name__)

Json = dict[str, Any]


class ToolError(Exception):
    """A tool failure with a short, content-free message for the client."""


# ─────────────────────────── fixture data (loaded and computed once) ───────────────────────────
def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _roster() -> tuple[date, Mapping[str, Member]]:
    """fixtures/members/members.json -> (demo_today, {member_id: Member}) in file order."""
    data = _read_json(FIXTURES / "members" / "members.json")
    members = {m.member_id: m for m in (Member.model_validate(raw) for raw in data["members"])}
    return date.fromisoformat(data["demo_today"]), MappingProxyType(members)


@lru_cache(maxsize=1)
def _inputs() -> tuple[Mapping[str, tuple[ClinicalNote, ...]], Mapping[str, tuple[EarningsDocument, ...]]]:
    """Fixture notes and earnings documents grouped by member_id."""
    notes: dict[str, list[ClinicalNote]] = {}
    for path in sorted((FIXTURES / "notes").glob("*.json")):
        note = ClinicalNote.model_validate(_read_json(path))
        notes.setdefault(note.member_id, []).append(note)
    docs: dict[str, list[EarningsDocument]] = {}
    for path in sorted((FIXTURES / "earnings_docs").glob("*.json")):
        doc = EarningsDocument.model_validate(_read_json(path))
        docs.setdefault(doc.member_id, []).append(doc)
    return (MappingProxyType({k: tuple(v) for k, v in notes.items()}),
            MappingProxyType({k: tuple(v) for k, v in docs.items()}))


@lru_cache(maxsize=None)
def _status(member_id: str) -> ProofKitStatus:
    """member_id -> ProofKitStatus via run_member with the offline demo LLM. Computed once per member."""
    today, members = _roster()
    notes, docs = _inputs()
    status = run_member(members[member_id], list(notes.get(member_id, ())), list(docs.get(member_id, ())),
                        demo_llm(FIXTURES), FRAILTY_RULES_PATH, WALLET_RULES_PATH, today)
    log.info("mcp status computed member_id=%s", member_id)
    return status


# ─────────────────────────── serializers ───────────────────────────
def _money(x: Decimal) -> str:
    """Decimal -> '60.00' (half-up, two places)."""
    return str(x.quantize(_CENT, rounding=ROUND_HALF_UP))


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d is not None else None


def _first_name(member: Member) -> str:
    """'Dev (synthetic)' -> 'Dev'."""
    parts = member.display_name.split()
    return parts[0] if parts else ""


def _month_json(mc: MonthlyCompliance) -> Json:
    return {
        "month": mc.month,
        "total_hours": _money(mc.total_hours),
        "total_income": _money(mc.total_income),
        "qualifies": mc.qualifies,
        "basis": mc.basis.value,
        "shortfall_hours": _money(mc.shortfall_hours),
        "shortfall_income": _money(mc.shortfall_income),
        "needs_review": mc.needs_review,
    }


# ─────────────────────────── argument validation ───────────────────────────
def _no_args(arguments: Json) -> None:
    if arguments:
        raise ToolError("this tool takes no arguments")


def _member_arg(arguments: Json) -> str:
    """Validate that arguments hold only member_id, matching MEMBER_ID_PATTERN, for a known member -> member_id."""
    if set(arguments) != {"member_id"}:
        raise ToolError("expected exactly one argument: member_id")
    member_id = arguments["member_id"]
    if not isinstance(member_id, str) or _MEMBER_ID_RE.fullmatch(member_id) is None:
        raise ToolError("member_id must match SYN-#### (4 digits)")
    if member_id not in _roster()[1]:
        raise ToolError("unknown member_id")
    return member_id


# ─────────────────────────── tools ───────────────────────────
def _tool_list_members(arguments: Json) -> Any:
    """-> [{member_id, first_name}] in roster order."""
    _no_args(arguments)
    return [{"member_id": m.member_id, "first_name": _first_name(m)} for m in _roster()[1].values()]


def _tool_member_status(arguments: Json) -> Any:
    """-> the member's status, deadline, action items and verification window."""
    member_id = _member_arg(arguments)
    s = _status(member_id)
    return {
        "member_id": member_id,
        "status": s.status.value,
        "protected_by": s.protected_by,
        "next_deadline": _iso(s.next_deadline),
        "action_items": [{"title": a.title, "detail": a.detail, "due": _iso(a.due)} for a in s.action_items],
        "verification_months": list(s.wallet.verification_months) if s.wallet else [],
        "proof_due_date": _iso(s.wallet.proof_due_date) if s.wallet else None,
    }


def _tool_wallet_months(arguments: Json) -> Any:
    """-> the member's monthly compliance, money and hours as strings."""
    s = _status(_member_arg(arguments))
    return [_month_json(mc) for mc in s.wallet.months] if s.wallet else []


def _tool_sms_reminder(arguments: Json) -> Any:
    """-> {text, length} of the member's SMS reminder."""
    member_id = _member_arg(arguments)
    text = sms_reminder(_roster()[1][member_id], _status(member_id))
    return {"text": text, "length": len(text)}


def _tool_triage(arguments: Json) -> Any:
    """-> every member, at-risk first, then needs-review, then protected; earliest deadline first."""
    _no_args(arguments)
    entries = []
    for member in _roster()[1].values():
        s = _status(member.member_id)
        entries.append(((_STATUS_RANK[s.status], s.next_deadline is None, _iso(s.next_deadline) or "",
                         member.member_id),
                        {"member_id": member.member_id, "first_name": _first_name(member), "status": s.status.value,
                         "next_deadline": _iso(s.next_deadline), "protected_by": s.protected_by}))
    return [entry for _, entry in sorted(entries, key=lambda e: e[0])]


def _schema(member: bool) -> Json:
    if member:
        return {"type": "object",
                "properties": {"member_id": {"type": "string", "pattern": MEMBER_ID_PATTERN,
                                             "description": "Synthetic member id, e.g. SYN-0004"}},
                "required": ["member_id"], "additionalProperties": False}
    return {"type": "object", "properties": {}, "required": [], "additionalProperties": False}


_TOOLS: Mapping[str, tuple[str, bool, Callable[[Json], Any]]] = MappingProxyType({
    "list_members": ("List the synthetic members (id and first name).", False, _tool_list_members),
    "member_status": ("A member's status (protected / needs_review / at_risk), next deadline and action items.",
                      True, _tool_member_status),
    "wallet_months": ("A member's monthly hours and income against the 80 h / $580 requirement.",
                      True, _tool_wallet_months),
    "sms_reminder": ("A short SMS reminder (at most 160 characters) for a member.", True, _tool_sms_reminder),
    "triage": ("All members ordered for a navigator: at risk first, then by deadline.", False, _tool_triage),
})


def _tools_list() -> Json:
    return {"tools": [{"name": name, "description": desc, "inputSchema": _schema(member)}
                      for name, (desc, member, _) in _TOOLS.items()]}


def _tool_result(text: str, is_error: bool) -> Json:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


# ─────────────────────────── JSON-RPC ───────────────────────────
class _RpcError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _error(msg_id: Any, code: int, message: str) -> Json:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def _initialize(params: Json) -> Json:
    requested = params.get("protocolVersion")
    version = requested if requested in SUPPORTED_PROTOCOLS else LATEST_PROTOCOL
    return {"protocolVersion": version, "capabilities": {"tools": {}}, "serverInfo": dict(SERVER_INFO)}


def _tools_call(params: Json) -> Json:
    name = params.get("name")
    if not isinstance(name, str) or name not in _TOOLS:
        raise _RpcError(INVALID_PARAMS, "unknown tool")
    arguments = params.get("arguments", {})
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        return _tool_result("arguments must be an object", True)
    try:
        payload = _TOOLS[name][2](arguments)
    except ToolError as exc:
        return _tool_result(str(exc), True)
    except Exception:  # noqa: BLE001 - never leak a traceback or content to the client
        log.warning("mcp tool failed tool=%s", name)
        return _tool_result("internal error while running the tool", True)
    return _tool_result(json.dumps(payload, ensure_ascii=True), False)


def _dispatch(method: str, params: Json) -> Json:
    if method == "initialize":
        return _initialize(params)
    if method == "ping":
        return {}
    if method == "tools/list":
        return _tools_list()
    if method == "tools/call":
        return _tools_call(params)
    raise _RpcError(METHOD_NOT_FOUND, "method not found")


def handle(message: Any) -> Json | None:
    """One parsed JSON-RPC message -> its response dict, or None for a notification."""
    if not isinstance(message, dict):
        return _error(None, INVALID_REQUEST, "invalid request")
    msg_id = message.get("id")
    if not isinstance(msg_id, (str, int)) or isinstance(msg_id, bool):
        msg_id = None
    method = message.get("method")
    params = message.get("params", {})
    if message.get("jsonrpc") != "2.0" or not isinstance(method, str) or not isinstance(params, (dict, type(None))):
        return _error(msg_id, INVALID_REQUEST, "invalid request")
    if "id" not in message:
        return None  # notification: never answered
    try:
        result = _dispatch(method, params or {})
    except _RpcError as exc:
        return _error(msg_id, exc.code, exc.message)
    except Exception:  # noqa: BLE001 - never leak a traceback to the client
        log.warning("mcp request failed method=%s", method[:40])
        return _error(msg_id, INTERNAL_ERROR, "internal error")
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _write(stdout: TextIO, response: Json) -> None:
    stdout.write(json.dumps(response, ensure_ascii=True) + "\n")
    stdout.flush()


def _skip_rest_of_line(stdin: TextIO) -> None:
    """Discard an oversized line up to and including its newline, in bounded chunks."""
    while True:
        chunk = stdin.readline(MAX_LINE_CHARS)
        if not chunk or chunk.endswith("\n"):
            return


def serve(stdin: TextIO, stdout: TextIO) -> None:
    """Read newline-delimited JSON-RPC from stdin until EOF; write one response line per request to stdout."""
    while True:
        line = stdin.readline(MAX_LINE_CHARS + 1)
        if not line:
            return
        if len(line) > MAX_LINE_CHARS and not line.endswith("\n"):
            _skip_rest_of_line(stdin)
            _write(stdout, _error(None, INVALID_REQUEST, "message too long"))
            continue
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except (ValueError, RecursionError):  # JSONDecodeError, and int-digit-limit ValueError on huge numbers
            _write(stdout, _error(None, PARSE_ERROR, "parse error"))
            continue
        response = handle(message)
        if response is not None:
            _write(stdout, response)


def main() -> None:
    """Entry point: serve on stdio, logging warnings to stderr only."""
    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    serve(sys.stdin, sys.stdout)


if __name__ == "__main__":
    main()
