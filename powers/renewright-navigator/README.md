# RenewRight Navigator power

Helps navigators (CHWs, enrollment assisters, clinic care teams) triage MassHealth members facing the 2027 work requirements. The power connects Kiro to the RenewRight MCP server and adds a `navigator-triage` skill that:

- lists members and finds those at risk,
- reports each one's status (PROTECTED / NEEDS_REVIEW / AT_RISK), proof due date and monthly shortfall,
- shows the drafted SMS reminder.

RenewRight organizes evidence. It does not make eligibility determinations; MassHealth does.

## Tools

| Tool | Arguments |
|---|---|
| `list_members` | none |
| `member_status` | `member_id` (`^SYN-\d{4}$`) |
| `wallet_months` | `member_id` |
| `sms_reminder` | `member_id` |
| `triage` | none |

## Import

- Kiro IDE: open the Powers panel, choose Add Custom Power, then Import power from a folder, and select `powers/renewright-navigator`.
- Kiro CLI: `kiro-cli powers install powers/renewright-navigator`

The server starts with `python .kiro/mcp/renewright.py`, which runs `python -m proofkit.integration.mcp_server` using the repo's `.venv` interpreter when one exists. Open the RenewRight repo as your workspace so the relative path resolves.

## Safety

- Read-only: no tool writes files, changes state or submits anything to MassHealth.
- Offline: no network calls and no LLM calls. Every answer comes from the synthetic fixtures.
- Synthetic data only: members are `SYN-0001` to `SYN-0005`. Don't use it with real member data.
