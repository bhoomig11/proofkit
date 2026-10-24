"""Validated synthetic demo fixture loading."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from proofkit.contracts import ClinicalNote, EarningsDocument, EarningsRecord, FindingsBundle, Member


@dataclass(frozen=True)
class DemoData:
    today: date
    members: dict[str, Member]
    notes: dict[str, list[ClinicalNote]]
    documents: dict[str, list[EarningsDocument]]
    golden_findings: dict[str, FindingsBundle]
    golden_records: dict[str, list[EarningsRecord]]
    expected_status: dict[str, dict[str, str | None]]


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_demo_data(root: Path | None = None) -> DemoData:
    """Load and contract-validate the five synthetic demo personas and their evidence."""
    project = root or Path(__file__).resolve().parents[1]
    fixtures = project / "fixtures"
    member_data = _json(fixtures / "members" / "members.json")
    members = {raw["member_id"]: Member.model_validate(raw) for raw in member_data["members"]}

    notes: dict[str, list[ClinicalNote]] = {member_id: [] for member_id in members}
    for path in sorted((fixtures / "notes").glob("*.json")):
        note = ClinicalNote.model_validate(_json(path))
        notes.setdefault(note.member_id, []).append(note)

    documents: dict[str, list[EarningsDocument]] = {member_id: [] for member_id in members}
    for path in sorted((fixtures / "earnings_docs").glob("*.json")):
        document = EarningsDocument.model_validate(_json(path))
        documents.setdefault(document.member_id, []).append(document)

    findings = {
        path.name.split(".")[0]: FindingsBundle.model_validate(_json(path))
        for path in sorted((fixtures / "findings").glob("*.golden.json"))
    }
    records = {
        path.name.split(".")[0]: [EarningsRecord.model_validate(raw) for raw in _json(path)]
        for path in sorted((fixtures / "earnings").glob("*.golden.json"))
    }
    expected_raw = _json(fixtures / "members" / "expected_status.json")
    expected = {key: value for key, value in expected_raw.items() if key.startswith("SYN-")}
    return DemoData(
        today=date.fromisoformat(member_data["demo_today"]),
        members=members,
        notes=notes,
        documents=documents,
        golden_findings=findings,
        golden_records=records,
        expected_status=expected,
    )
