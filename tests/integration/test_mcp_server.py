"""
FINAL SPEC: RenewRight as a read-only MCP server (src/proofkit/integration/mcp_server.py).

JSON-RPC 2.0 over newline-delimited stdio. Runs offline on the synthetic fixtures with demo_llm() and
today = demo_today, so no API key and no network are needed. Tools: list_members, member_status, wallet_months,
sms_reminder, triage. Tool failures are isError results with a short message; protocol failures are JSON-RPC
errors (-32700 parse, -32600 invalid request, -32601 unknown method, -32602 unknown tool).
"""
from __future__ import annotations

import io
import json
import os
import socket
import subprocess  # nosec B404 - runs this repo's own server module with a fixed argv, no shell
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from proofkit.integration.mcp_server import handle, serve

ROOT = Path(__file__).resolve().parents[2]
MEMBER_IDS = ["SYN-0001", "SYN-0002", "SYN-0003", "SYN-0004", "SYN-0005"]
TOOL_NAMES = {"list_members", "member_status", "wallet_months", "sms_reminder", "triage"}
MEMBER_TOOLS = ["member_status", "wallet_months", "sms_reminder"]
STATUS_RANK = {"at_risk": 0, "needs_review": 1, "protected": 2}


# ─────────────────────────── helpers ───────────────────────────
def _request(method: str, params: dict | None = None, msg_id: int = 1) -> dict:
    msg = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        msg["params"] = params
    return msg


def _call_raw(name: str, arguments: dict | None = None, msg_id: int = 1) -> dict:
    """tools/call -> the full JSON-RPC response."""
    resp = handle(_request("tools/call", {"name": name, "arguments": arguments or {}}, msg_id))
    assert resp is not None
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == msg_id
    return resp


def _call(name: str, arguments: dict | None = None):
    """tools/call that must succeed -> the parsed JSON payload of its single text content block."""
    resp = _call_raw(name, arguments)
    assert "error" not in resp, resp
    result = resp["result"]
    assert result["isError"] is False, result
    assert len(result["content"]) == 1
    block = result["content"][0]
    assert block["type"] == "text"
    return json.loads(block["text"])


def _all_tool_texts() -> list[str]:
    """Every tool for every member, through handle() -> the raw text of each content block."""
    texts = []
    calls = [("list_members", {}), ("triage", {})]
    calls += [(tool, {"member_id": mid}) for mid in MEMBER_IDS for tool in MEMBER_TOOLS]
    for name, args in calls:
        resp = _call_raw(name, args)
        assert resp["result"]["isError"] is False, (name, args)
        texts += [block["text"] for block in resp["result"]["content"]]
    return texts


# ─────────────────────────── 1-2: lifecycle ───────────────────────────
@pytest.mark.parametrize("client_version, expected", [
    ("2025-06-18", "2025-06-18"),
    ("2025-03-26", "2025-03-26"),
    ("2024-11-05", "2024-11-05"),
    ("1999-01-01", "2025-06-18"),
])
def test_initialize_handshake(client_version, expected):
    resp = handle(_request("initialize", {
        "protocolVersion": client_version,
        "capabilities": {},
        "clientInfo": {"name": "pytest", "version": "0"},
    }, msg_id=7))
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 7
    result = resp["result"]
    assert result["protocolVersion"] == expected
    assert result["capabilities"] == {"tools": {}}
    assert result["serverInfo"] == {"name": "renewright", "version": "1.0.0"}


def test_initialized_notification_has_no_response():
    assert handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


# ─────────────────────────── 3: tools/list ───────────────────────────
def test_tools_list_names_and_schemas():
    resp = handle(_request("tools/list", {}))
    tools = resp["result"]["tools"]
    assert {t["name"] for t in tools} == TOOL_NAMES
    assert len(tools) == len(TOOL_NAMES)
    for tool in tools:
        assert isinstance(tool.get("description"), str) and tool["description"], tool["name"]
        schema = tool["inputSchema"]
        assert schema["type"] == "object", tool["name"]
        assert schema["additionalProperties"] is False, tool["name"]
        if tool["name"] in MEMBER_TOOLS:
            assert schema["required"] == ["member_id"], tool["name"]
            prop = schema["properties"]["member_id"]
            assert prop["type"] == "string"
            assert prop["pattern"] == r"^SYN-\d{4}$"
        else:
            assert schema.get("properties", {}) == {}, tool["name"]
            assert schema.get("required", []) == [], tool["name"]


# ─────────────────────────── 4-8: tool results ───────────────────────────
def test_list_members_lists_every_persona():
    members = _call("list_members")
    assert [m["member_id"] for m in members] == MEMBER_IDS
    assert members[3] == {"member_id": "SYN-0004", "first_name": "Dev"}


def test_member_status_matches_expected_for_every_persona(expected_status, expected_wallet):
    for mid in MEMBER_IDS:
        out = _call("member_status", {"member_id": mid})
        assert set(out) == {"member_id", "status", "protected_by", "next_deadline", "action_items",
                            "verification_months", "proof_due_date"}, mid
        assert out["member_id"] == mid
        assert out["status"] == expected_status[mid]["status"], mid
        assert out["protected_by"] == expected_status[mid]["protected_by"], mid
        assert out["verification_months"] == expected_wallet["verification_months_for_renewal_2027-03-20"], mid
        assert out["proof_due_date"] == expected_wallet["proof_due_date_for_renewal_2027-03-20"], mid
        for item in out["action_items"]:
            assert set(item) == {"title", "detail", "due"}, mid
    dev = _call("member_status", {"member_id": "SYN-0004"})
    assert dev["next_deadline"] == "2027-03-06"
    assert dev["action_items"], "an at-risk member needs action items"


def test_wallet_months_shows_dev_shortfall(expected_wallet):
    months = _call("wallet_months", {"member_id": "SYN-0004"})
    by_month = {m["month"]: m for m in months}
    feb = by_month["2027-02"]
    assert set(feb) == {"month", "total_hours", "total_income", "qualifies", "basis", "shortfall_hours",
                        "shortfall_income", "needs_review"}
    exp = expected_wallet["SYN-0004"]["2027-02"]
    assert feb["shortfall_income"] == "60.00"
    assert feb["qualifies"] is False
    assert feb["basis"] == "none"
    for key in ("total_hours", "total_income", "shortfall_hours", "shortfall_income"):
        assert isinstance(feb[key], str), key
    assert Decimal(feb["total_income"]) == Decimal(exp["total_income"])
    assert Decimal(feb["total_hours"]) == Decimal(exp["total_hours"])


def test_sms_reminder_for_dev():
    out = _call("sms_reminder", {"member_id": "SYN-0004"})
    assert set(out) == {"text", "length"}
    assert "$60.00 short" in out["text"]
    assert out["length"] == len(out["text"])
    assert out["length"] <= 160


def test_triage_orders_at_risk_first():
    entries = _call("triage")
    assert [e["member_id"] for e in entries[:2]] == ["SYN-0004", "SYN-0005"]
    assert sorted(e["member_id"] for e in entries) == MEMBER_IDS
    for e in entries:
        assert set(e) == {"member_id", "first_name", "status", "next_deadline", "protected_by"}
    assert all(e["status"] == "protected" for e in entries[2:])
    keys = [(STATUS_RANK[e["status"]], e["next_deadline"] is None, e["next_deadline"] or "", e["member_id"])
            for e in entries]
    assert keys == sorted(keys)


# ─────────────────────────── 9: tool and protocol errors ───────────────────────────
@pytest.mark.parametrize("arguments", [
    {"member_id": "SYN-9999"},
    {"member_id": "../etc/passwd"},
    {"member_id": "SYN-0001; rm"},
    {"member_id": "SYN-0001", "extra": "x"},
], ids=["unknown-member", "path-traversal", "shell-suffix", "extra-argument"])
@pytest.mark.parametrize("tool", MEMBER_TOOLS)
def test_bad_member_ids_are_tool_errors(tool, arguments):
    resp = _call_raw(tool, arguments)
    assert "error" not in resp, resp
    result = resp["result"]
    assert result["isError"] is True
    text = " ".join(block["text"] for block in result["content"])
    assert text
    assert len(text) <= 200
    assert "Traceback" not in text


def test_unknown_tool_and_method_errors():
    bad_tool = handle(_request("tools/call", {"name": "delete_member", "arguments": {}}, msg_id=3))
    assert bad_tool["id"] == 3
    assert bad_tool["error"]["code"] == -32602
    assert "result" not in bad_tool

    bad_method = handle(_request("resources/write", {}, msg_id=4))
    assert bad_method["id"] == 4
    assert bad_method["error"]["code"] == -32601
    assert "result" not in bad_method


# ─────────────────────────── 10-11: stdio transport ───────────────────────────
def test_serve_handles_malformed_json_and_keeps_going():
    stdin = io.StringIO("{not json\n" + json.dumps(_request("ping", msg_id=9)) + "\n")
    stdout = io.StringIO()
    serve(stdin, stdout)
    lines = [line for line in stdout.getvalue().splitlines() if line.strip()]
    assert len(lines) == 2
    first, second = (json.loads(line) for line in lines)
    assert first["jsonrpc"] == "2.0"
    assert first["id"] is None
    assert first["error"]["code"] == -32700
    assert second == {"jsonrpc": "2.0", "id": 9, "result": {}}


def test_subprocess_stdio_round_trip():
    messages = [
        _request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                "clientInfo": {"name": "pytest", "version": "0"}}, msg_id=1),
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        _request("tools/list", {}, msg_id=2),
        _request("tools/call", {"name": "member_status", "arguments": {"member_id": "SYN-0004"}}, msg_id=3),
    ]
    stdin = "".join(json.dumps(m) + "\n" for m in messages)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(p for p in (str(ROOT / "src"), env.get("PYTHONPATH", "")) if p)
    proc = subprocess.run(  # nosec B603 - fixed argv, no shell
        [sys.executable, "-m", "proofkit.integration.mcp_server"],
        input=stdin, capture_output=True, text=True, cwd=ROOT, env=env, timeout=60, check=False,
    )
    assert proc.returncode == 0, proc.stderr[-500:]
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    responses = [json.loads(line) for line in lines]
    assert all(r.get("jsonrpc") == "2.0" for r in responses)
    assert [r["id"] for r in responses] == [1, 2, 3]
    assert responses[0]["result"]["serverInfo"]["name"] == "renewright"
    assert {t["name"] for t in responses[1]["result"]["tools"]} == TOOL_NAMES
    call = responses[2]["result"]
    assert call["isError"] is False
    status = json.loads(call["content"][0]["text"])
    assert status["member_id"] == "SYN-0004"
    assert status["status"] == "at_risk"
    assert status["next_deadline"] == "2027-03-06"


# ─────────────────────────── 12-13: offline and no content leaks ───────────────────────────
def test_tools_open_no_socket(monkeypatch):
    def guard(*args, **kwargs):
        raise RuntimeError("the MCP server must not open a socket")

    monkeypatch.setattr(socket, "socket", guard)
    monkeypatch.setattr(socket, "create_connection", guard)
    texts = _all_tool_texts()
    assert len(texts) == 2 + len(MEMBER_IDS) * len(MEMBER_TOOLS)


def test_outputs_never_contain_note_quotes(golden_findings):
    quotes = [f.quote for f in golden_findings["SYN-0001"].findings]
    assert quotes, "SYN-0001 golden findings must have quotes"
    outputs = [_call_raw(tool, {"member_id": "SYN-0001"})["result"]["content"][0]["text"] for tool in MEMBER_TOOLS]
    outputs += _all_tool_texts()
    for text in outputs:
        for quote in quotes:
            assert quote not in text
