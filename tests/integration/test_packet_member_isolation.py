"""render_packet refuses to mix another member's data into a packet.

Every member-scoped input that render_packet receives must belong to the packet's
member. A mismatch raises ValueError before any HTML is returned, and the error
message never echoes note or document text.

render_packet takes ``findings: Sequence[Finding]``, not a ``FindingsBundle``, and
``Finding`` carries no ``member_id``, so there is no bundle case to parametrize.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from proofkit.contracts import ClinicalNote, Finding, Member, ProofKitStatus
from proofkit.integration.packet import render_packet
from tests.integration.test_packet_complete import _complete_packet_inputs

MEMBER_ID = "SYN-0001"
FOREIGN_MEMBER_ID = "SYN-0002"
FOREIGN_NOTE_TEXT = "FOREIGN-NOTE-SENTINEL: other member <lupus> & private history."
FOREIGN_SOURCE_QUOTE = "FOREIGN-DOC-SENTINEL <gross> $999.99 other member"
FOREIGN_STATEMENT = "FOREIGN-STATEMENT-SENTINEL <other member> statement."

PacketInputs = tuple[Member, ProofKitStatus, list[Finding], list[ClinicalNote]]


def _own_inputs() -> PacketInputs:
    """Reuse the complete-packet builder, re-scoped to SYN-0001 everywhere."""
    member, status, findings, notes = _complete_packet_inputs()
    wallet = status.wallet
    exemption = status.exemption
    assert wallet is not None and exemption is not None
    status = status.model_copy(
        update={
            "member_id": MEMBER_ID,
            "wallet": wallet.model_copy(
                update={
                    "member_id": MEMBER_ID,
                    "records": [record.model_copy(update={"member_id": MEMBER_ID}) for record in wallet.records],
                }
            ),
            "exemption": exemption.model_copy(update={"member_id": MEMBER_ID}),
        }
    )
    member = member.model_copy(update={"member_id": MEMBER_ID})
    notes = [note.model_copy(update={"member_id": MEMBER_ID}) for note in notes]
    return member, status, list(findings), notes


def _foreign_status(inputs: PacketInputs) -> PacketInputs:
    member, status, findings, notes = inputs
    return member, status.model_copy(update={"member_id": FOREIGN_MEMBER_ID}), findings, notes


def _foreign_wallet(inputs: PacketInputs) -> PacketInputs:
    member, status, findings, notes = inputs
    assert status.wallet is not None
    wallet = status.wallet.model_copy(update={"member_id": FOREIGN_MEMBER_ID})
    return member, status.model_copy(update={"wallet": wallet}), findings, notes


def _foreign_record(index: int) -> Callable[[PacketInputs], PacketInputs]:
    def build(inputs: PacketInputs) -> PacketInputs:
        member, status, findings, notes = inputs
        assert status.wallet is not None
        records = list(status.wallet.records)
        records[index] = records[index].model_copy(
            update={"member_id": FOREIGN_MEMBER_ID, "source_quote": FOREIGN_SOURCE_QUOTE}
        )
        wallet = status.wallet.model_copy(update={"records": records})
        return member, status.model_copy(update={"wallet": wallet}), findings, notes

    return build


def _foreign_exemption(inputs: PacketInputs) -> PacketInputs:
    member, status, findings, notes = inputs
    assert status.exemption is not None
    exemption = status.exemption.model_copy(
        update={"member_id": FOREIGN_MEMBER_ID, "statement_draft": FOREIGN_STATEMENT}
    )
    return member, status.model_copy(update={"exemption": exemption}), findings, notes


def _foreign_note(index: int) -> Callable[[PacketInputs], PacketInputs]:
    def build(inputs: PacketInputs) -> PacketInputs:
        member, status, findings, notes = inputs
        notes = list(notes)
        notes[index] = notes[index].model_copy(update={"member_id": FOREIGN_MEMBER_ID, "text": FOREIGN_NOTE_TEXT})
        return member, status, findings, notes

    return build


MISMATCH_CASES = [
    pytest.param(_foreign_status, id="status.member_id"),
    pytest.param(_foreign_wallet, id="status.wallet.member_id"),
    pytest.param(_foreign_record(0), id="wallet.records[0].member_id"),
    pytest.param(_foreign_record(-1), id="wallet.records[-1].member_id"),
    pytest.param(_foreign_exemption, id="status.exemption.member_id"),
    pytest.param(_foreign_note(0), id="notes[0].member_id"),
    pytest.param(_foreign_note(-1), id="notes[-1].member_id"),
]


def _content_texts(inputs: PacketInputs) -> list[str]:
    """Every note and document text in the inputs, own and foreign."""
    _, status, findings, notes = inputs
    texts = [note.text for note in notes]
    texts.extend(finding.quote for finding in findings)
    if status.wallet is not None:
        texts.extend(record.source_quote for record in status.wallet.records)
        texts.extend(record.platform for record in status.wallet.records)
    if status.exemption is not None and status.exemption.statement_draft is not None:
        texts.append(status.exemption.statement_draft)
    return texts


def test_own_member_inputs_render_without_error() -> None:
    """Control: the re-scoped builder is consistent, so mismatch cases fail only on the swapped field."""
    member, status, findings, notes = _own_inputs()

    document = render_packet(member, status, findings=findings, notes=notes)

    assert document.startswith("<!doctype html>\n")


@pytest.mark.parametrize("make_foreign", MISMATCH_CASES)
def test_member_id_mismatch_raises_before_rendering(
    make_foreign: Callable[[PacketInputs], PacketInputs],
) -> None:
    inputs = make_foreign(_own_inputs())
    member, status, findings, notes = inputs
    assert member.member_id == MEMBER_ID

    with pytest.raises(ValueError) as excinfo:
        render_packet(member, status, findings=findings, notes=notes)

    message = str(excinfo.value)
    assert "<!doctype" not in message.lower()
    assert "<html" not in message.lower()
    for sentinel in (FOREIGN_NOTE_TEXT, FOREIGN_SOURCE_QUOTE, FOREIGN_STATEMENT):
        assert sentinel not in message
    for text in _content_texts(inputs):
        assert text not in message
