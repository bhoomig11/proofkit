"""RED: UI extras (upload, sample gallery, SMS card, metric tiles). Pure helpers only; Streamlit never starts."""
from __future__ import annotations

import ast
import base64
import json
from datetime import date
from pathlib import Path

import pytest

from proofkit.common.llm import FakeLLM
from proofkit.contracts import DocumentType, OverallStatus
from proofkit.integration import build_status, run_member
from proofkit.integration.demo import demo_llm
from proofkit.wallet import load_wallet_rules

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"
WALLET_RULES = ROOT / "config" / "wallet_rules.json"
EXTRA_MODULES = ("upload.py", "samples.py", "sms_card.py", "metrics.py")
REAL_BRANDS = ("uber", "doordash", "instacart", "upwork", "taskrabbit")
CSV_BYTES = (b"platform,period_start,period_end,hours,gross_pay\n"
             b"quickdash,2027-02-01,2027-02-28,85,700.00\n")


@pytest.fixture
def rules():
    return load_wallet_rules(WALLET_RULES)


@pytest.fixture
def dev(members):
    return members["SYN-0004"]


@pytest.fixture
def dev_status(dev, notes_by_member, earnings_docs_by_member, frailty_rules_path, wallet_rules_path, demo_today):
    return run_member(dev, notes_by_member.get("SYN-0004", []), earnings_docs_by_member["SYN-0004"], demo_llm(),
                      frailty_rules_path, wallet_rules_path, demo_today)


# ─────────────────────────── upload: to_document ───────────────────────────
@pytest.mark.parametrize(("name", "data", "doc_type", "field"), [
    ("stmt.csv", CSV_BYTES, DocumentType.CSV, "content_text"),
    ("stmt.txt", b"QuickDash Courier\nTotal earnings: $10.00\n", DocumentType.TEXT, "content_text"),
    ("stmt.pdf", b"%PDF-1.4 fake", DocumentType.PDF, "content_b64"),
    ("shot.png", b"\x89PNG\r\n\x1a\nfake", DocumentType.IMAGE, "content_b64"),
    ("shot.jpg", b"\xff\xd8\xff\xe0fake", DocumentType.IMAGE, "content_b64"),
    ("shot.jpeg", b"\xff\xd8\xff\xe0fake", DocumentType.IMAGE, "content_b64"),
])
def test_to_document_maps_extension_to_type_and_content(rules, name, data, doc_type, field):
    from app.upload import to_document
    doc = to_document(name, data, "SYN-0004", 3, rules)
    assert doc.doc_type == doc_type
    assert doc.member_id == "SYN-0004"
    assert doc.doc_id == "U-SYN-0004-3"
    assert doc.filename == name
    if field == "content_text":
        assert doc.content_text == data.decode("utf-8") and doc.content_b64 is None
    else:
        assert doc.content_b64 == base64.b64encode(data).decode("ascii") and doc.content_text is None


def test_upload_constants():
    from app.upload import IMAGE_NOTE, UPLOAD_QUEUE_KEY, UPLOAD_TYPES
    assert UPLOAD_TYPES == ("csv", "txt", "pdf", "png", "jpg", "jpeg")
    assert UPLOAD_QUEUE_KEY == "ui_extras_upload_queue"
    assert IMAGE_NOTE == ("Image received. We don't read images yet, so this month is flagged for a navigator "
                          "to review.")


@pytest.mark.parametrize(("name", "display"), [
    ("../../etc/passwd.csv", "passwd.csv"),
    ("..\\..\\Windows\\system.csv", "system.csv"),
    ("/abs/path/stmt.csv", "stmt.csv"),
])
def test_filename_is_display_basename_only(rules, name, display):
    from app.upload import to_document
    doc = to_document(name, CSV_BYTES, "SYN-0004", 0, rules)
    assert doc.filename == display
    assert "/" not in doc.filename and "\\" not in doc.filename and ".." not in doc.filename


def test_filename_cut_to_255_characters(rules):
    from app.upload import to_document
    doc = to_document("a" * 300 + ".csv", CSV_BYTES, "SYN-0004", 0, rules)
    assert len(doc.filename) == 255
    assert doc.filename == ("a" * 300 + ".csv")[:255]


def test_oversize_upload_raises_value_error_naming_file(rules):
    from app.upload import to_document
    small = rules.model_copy(update={"max_bytes": 10})
    with pytest.raises(ValueError) as exc:
        to_document("big.csv", CSV_BYTES, "SYN-0004", 0, small)
    assert str(exc.value).startswith("big.csv")


def test_unsupported_extension_raises_value_error_naming_file(rules):
    from app.upload import to_document
    with pytest.raises(ValueError) as exc:
        to_document("notes.docx", b"PK\x03\x04", "SYN-0004", 0, rules)
    assert str(exc.value).startswith("notes.docx")


def test_type_not_allowed_by_rules_raises_value_error_naming_file(rules):
    from app.upload import to_document
    csv_only = rules.model_copy(update={"allowed_doc_types": frozenset({DocumentType.CSV})})
    with pytest.raises(ValueError) as exc:
        to_document("stmt.pdf", b"%PDF-1.4 fake", "SYN-0004", 0, csv_only)
    assert str(exc.value).startswith("stmt.pdf")


@pytest.mark.parametrize("name", ["latin.csv", "latin.txt"])
def test_non_utf8_text_raises_value_error_naming_file(rules, name):
    from app.upload import to_document
    with pytest.raises(ValueError) as exc:
        to_document(name, b"\xff\xfe\x00caf\xe9", "SYN-0004", 0, rules)
    assert str(exc.value).startswith(name)


# ─────────────────────────── upload: needs_live_ai ───────────────────────────
@pytest.mark.parametrize(("names", "expected"), [
    (["a.txt"], True),
    (["a.pdf"], True),
    (["a.csv"], False),
    (["a.png"], False),
    (["a.csv", "b.png"], False),
    (["a.csv", "b.txt"], True),
    ([], False),
])
def test_needs_live_ai_only_for_text_or_pdf(rules, names, expected):
    from app.upload import needs_live_ai, to_document
    data = {"txt": b"hello", "pdf": b"%PDF-1.4", "csv": CSV_BYTES, "png": b"\x89PNG"}
    docs = [to_document(n, data[n.rsplit(".", 1)[1]], "SYN-0004", i, rules) for i, n in enumerate(names)]
    assert needs_live_ai(docs) is expected


# ─────────────────────────── upload: upload_results ───────────────────────────
def test_upload_results_csv_computes_months_without_llm(rules, dev, demo_today):
    from app.upload import to_document, upload_results
    llm = FakeLLM({})
    doc = to_document("stmt.csv", CSV_BYTES, dev.member_id, 0, rules)
    wallet, error = upload_results(dev, [doc], llm, rules, demo_today)
    assert error is None and wallet is not None
    assert llm.calls == []
    feb = {m.month: m for m in wallet.months}["2027-02"]
    assert feb.qualifies and feb.total_hours == 85


def test_upload_results_image_gives_no_records_and_flags_verification_month(rules, dev, demo_today):
    from app.upload import to_document, upload_results
    llm = FakeLLM({})
    doc = to_document("shot.png", b"\x89PNG\r\n\x1a\nfake", dev.member_id, 0, rules)
    wallet, error = upload_results(dev, [doc], llm, rules, demo_today)
    assert error is None and wallet is not None
    assert wallet.records == []
    assert llm.calls == []
    months = {m.month: m for m in wallet.months}
    for month in wallet.verification_months:
        assert months[month].needs_review


def test_upload_results_wrong_member_gives_friendly_message_naming_file(rules, dev, demo_today):
    from app.upload import to_document, upload_results
    doc = to_document("someone_else.csv", CSV_BYTES, "SYN-0009", 0, rules)
    wallet, error = upload_results(dev, [doc], FakeLLM({}), rules, demo_today)
    assert wallet is None
    assert isinstance(error, str)
    assert "someone_else.csv" in error
    assert doc.doc_id not in error


# ─────────────────────────── samples ───────────────────────────
def test_sample_documents_include_pdf_csv_redteam_and_member_fixtures():
    from app.samples import SampleDoc, sample_documents
    samples = sample_documents("SYN-0002")
    assert samples and all(isinstance(s, SampleDoc) for s in samples)
    datas = [s.data for s in samples]

    pdf_fixture = json.loads((FIXTURES / "wallet" / "D-0002-ridenow-feb-pdf.json").read_text(encoding="utf-8"))
    pdf_bytes = base64.b64decode(pdf_fixture["content_b64"])
    assert pdf_bytes in datas
    assert any(s.data.startswith(b"%PDF") for s in samples)

    assert any(s.filename.lower().endswith(".csv") and b"quickdash" in s.data.lower() for s in samples)

    redteam = json.loads((FIXTURES / "earnings_docs" / "D-0005-qd-feb.json").read_text(encoding="utf-8"))
    assert redteam["content_text"].encode("utf-8") in datas

    own = json.loads((FIXTURES / "earnings_docs" / "D-0002-ridenow-feb.json").read_text(encoding="utf-8"))
    assert own["content_text"].encode("utf-8") in datas


def test_sample_documents_have_label_filename_and_mime():
    from app.samples import sample_documents
    for s in sample_documents("SYN-0002"):
        assert s.label and s.filename and s.mime
        assert "/" not in s.filename and "\\" not in s.filename


@pytest.mark.parametrize("member_id", ["SYN-0001", "SYN-0002", "SYN-0004", "SYN-0005"])
def test_samples_use_no_real_brand_names(member_id):
    from app.samples import sample_documents
    for s in sample_documents(member_id):
        blob = " ".join([s.label, s.filename, s.mime, s.data.decode("latin-1")]).lower()
        for brand in REAL_BRANDS:
            assert brand not in blob, f"{brand!r} found in sample {s.filename!r}"


# ─────────────────────────── SMS card ───────────────────────────
def test_sms_langs():
    from app.sms_card import SMS_LANGS
    assert SMS_LANGS == {"EN": "en", "ES": "es", "PT": "pt"}


@pytest.mark.parametrize("lang", ["en", "es", "pt"])
def test_sms_preview_fits_one_ascii_sms_with_matching_counter(dev, dev_status, lang):
    from app.sms_card import sms_preview
    assert dev_status.status == OverallStatus.AT_RISK
    text, counter = sms_preview(dev, dev_status, lang)
    assert 0 < len(text) <= 160
    assert text.isascii()
    assert counter == f"{len(text)}/160"


def test_sms_preview_spanish_greets_dev(dev, dev_status):
    from app.sms_card import sms_preview
    text, _ = sms_preview(dev, dev_status, "es")
    assert text.startswith("Hola Dev,")


# ─────────────────────────── metric tiles ───────────────────────────
def test_metric_tiles_for_dev(dev_status, demo_today):
    from app.metrics import Tile, metric_tiles
    tiles = metric_tiles(dev_status, demo_today)
    assert len(tiles) == 3 and all(isinstance(t, Tile) for t in tiles)
    hours, income, deadline = tiles
    assert "18.00" in hours.value and "80" in hours.value
    assert "$520.00" in income.value and "$580.00" in income.value
    assert income.delta == "-$60.00"
    assert (date(2027, 3, 6) - demo_today).days == 5
    assert "5 days" in deadline.value
    assert all(isinstance(t.help, str) and t.help for t in tiles)


def test_metric_tiles_read_thresholds_from_rules(dev_status, demo_today, rules):
    from app.metrics import metric_tiles
    default = metric_tiles(dev_status, demo_today)
    explicit = metric_tiles(dev_status, demo_today, rules)
    assert default == explicit


def test_metric_tiles_without_wallet_are_na(dev, demo_today):
    from app.metrics import metric_tiles
    status = build_status(dev, None, None, demo_today)
    tiles = metric_tiles(status, demo_today)
    assert len(tiles) == 3
    assert [t.value for t in tiles] == ["n/a", "n/a", "n/a"]


# ─────────────────────────── render functions exist ───────────────────────────
def test_render_functions_exist():
    from app.metrics import render_metric_tiles
    from app.samples import render_sample_gallery
    from app.sms_card import render_sms_card
    from app.upload import render_upload
    assert all(callable(f) for f in (render_upload, render_sample_gallery, render_sms_card, render_metric_tiles))


# ─────────────────────────── static safety ───────────────────────────
def _tree(name: str) -> ast.Module:
    return ast.parse((ROOT / "app" / name).read_text(encoding="utf-8"), filename=name)


@pytest.mark.parametrize("name", EXTRA_MODULES)
def test_no_unsafe_allow_html_true(name):
    for node in ast.walk(_tree(name)):
        if isinstance(node, ast.keyword) and node.arg == "unsafe_allow_html":
            assert not (isinstance(node.value, ast.Constant) and node.value.value is True), name


@pytest.mark.parametrize("name", EXTRA_MODULES)
def test_no_file_writes_or_opens(name):
    for node in ast.walk(_tree(name)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        assert not (isinstance(func, ast.Name) and func.id == "open"), f"{name}: open()"
        if isinstance(func, ast.Attribute):
            assert func.attr not in ("write_text", "write_bytes"), f"{name}: .{func.attr}()"
            assert not (func.attr == "remove" and isinstance(func.value, ast.Name) and func.value.id == "os"), \
                f"{name}: os.remove()"


@pytest.mark.parametrize("name", EXTRA_MODULES)
def test_does_not_import_app_main(name):
    for node in ast.walk(_tree(name)):
        if isinstance(node, ast.Import):
            assert all(a.name != "app.main" and not a.name.startswith("app.main.") for a in node.names), name
        elif isinstance(node, ast.ImportFrom):
            assert node.module != "app.main", name
            if node.module == "app" or (node.module is None and node.level > 0):
                assert all(a.name != "main" for a in node.names), name


# ─────────────────────────── review follow-ups (gpt-5.6-sol) ───────────────────────────
class _RecordingAnthropic:
    """Stub for proofkit.integration.demo.AnthropicClient: records every construction, never calls out."""

    constructed: list[object] = []

    def __init__(self, settings):
        type(self).constructed.append(settings)

    def complete_json(self, *, task, instructions, untrusted_text=None):  # pragma: no cover - never called
        raise AssertionError("live client must not be used in tests")


@pytest.fixture
def keyed_demo(monkeypatch):
    """Pretend an API key is configured, and replace the live client with a recording stub."""
    import proofkit.integration.demo as demo_mod
    from proofkit.common.config import Settings

    monkeypatch.delenv("PROOFKIT_DEMO", raising=False)
    fake = Settings(anthropic_api_key="placeholder-not-a-key", model="placeholder-model", max_tokens=16,
                    llm_timeout_s=1.0)
    monkeypatch.setattr(demo_mod, "load_settings", lambda: fake)
    _RecordingAnthropic.constructed = []
    monkeypatch.setattr(demo_mod, "AnthropicClient", _RecordingAnthropic)
    return _RecordingAnthropic


def test_upload_never_uses_live_ai_without_opt_in(keyed_demo):
    from app.upload import upload_llm
    llm, mode = upload_llm(False)
    assert mode == "offline-demo"
    assert not isinstance(llm, keyed_demo)
    assert keyed_demo.constructed == []

    llm, mode = upload_llm(True)
    assert mode == "live"
    assert isinstance(llm, keyed_demo)
    assert len(keyed_demo.constructed) == 1


class _BoomLLM:
    """LLMClient whose every call fails with a message that quotes (fake) document text."""

    def __init__(self):
        self.calls: list[str] = []

    def complete_json(self, *, task, instructions, untrusted_text=None):
        self.calls.append(task)
        raise RuntimeError("SECRET-DOC-TEXT boom")


def test_upload_results_turns_any_llm_failure_into_a_fixed_message(rules, dev, demo_today):
    from app.upload import to_document, upload_results
    doc = to_document("../my statement.txt", b"QuickDash Courier\nTotal earnings: $10.00\n", dev.member_id, 0,
                      rules)
    wallet, error = upload_results(dev, [doc], _BoomLLM(), rules, demo_today)
    assert wallet is None
    assert isinstance(error, str)
    assert doc.filename in error
    assert "SECRET-DOC-TEXT" not in error
    assert "Traceback" not in error
    assert doc.doc_id not in error


def test_sample_queue_dedupes_and_caps():
    from app.samples import queue_sample
    original: list[tuple[str, bytes]] = []
    q = queue_sample(original, "a.csv", b"A")
    assert q == [("a.csv", b"A")]
    assert original == []  # returns a new list, input untouched

    q = queue_sample(q, "a.csv", b"A")
    assert q == [("a.csv", b"A")]  # exact duplicate ignored

    q = queue_sample(q, "b.csv", b"B")
    assert q == [("a.csv", b"A"), ("b.csv", b"B")]

    q = []
    for i in range(15):
        q = queue_sample(q, f"f{i}.csv", bytes([i]))
    assert len(q) == 10
    assert q[0] == ("f0.csv", bytes([0]))

    small: list[tuple[str, bytes]] = []
    for i in range(5):
        small = queue_sample(small, f"s{i}.csv", bytes([i]), cap=3)
    assert len(small) == 3


# ─────────────────────────── live AI only behind an explicit button (product decision, Karthik) ───────────────────
LIVE_AI_BUTTON = "Process with live AI"


def _render_upload_def() -> ast.FunctionDef:
    for node in ast.walk(_tree("upload.py")):
        if isinstance(node, ast.FunctionDef) and node.name == "render_upload":
            return node
    raise AssertionError("render_upload not found in app/upload.py")


def _is_live_button_call(node: ast.AST) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "button"
            and bool(node.args) and isinstance(node.args[0], ast.Constant) and node.args[0].value == LIVE_AI_BUTTON)


def _may_request_live(call: ast.Call) -> bool:
    """upload_llm(...) call -> True unless its opt-in is provably falsy (a falsy constant, or no argument)."""
    if call.args:
        arg = call.args[0]
    else:
        kw = [k for k in call.keywords if k.arg == "live_opt_in"]
        if not kw:
            return False
        arg = kw[0].value
    return not (isinstance(arg, ast.Constant) and not arg.value)


def _call_label(call: ast.Call) -> str | None:
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        return call.args[0].value
    for k in call.keywords:
        if k.arg == "label" and isinstance(k.value, ast.Constant) and isinstance(k.value.value, str):
            return k.value.value
    return None


def test_live_ai_only_inside_process_button():
    fn = _render_upload_def()

    button_ifs = [n for n in ast.walk(fn) if isinstance(n, ast.If) and _is_live_button_call(n.test)]
    assert button_ifs, f'render_upload needs `if st.button("{LIVE_AI_BUTTON}", ...):`'

    guarded: set[int] = set()
    for if_node in button_ifs:
        for stmt in if_node.body:
            guarded.update(id(n) for n in ast.walk(stmt))

    live_calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id == "upload_llm" and _may_request_live(n)]
    for call in live_calls:
        assert id(call) in guarded, \
            f'upload_llm(...) at line {call.lineno} may go live outside the "{LIVE_AI_BUTTON}" button body'

    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "checkbox":
            label = (_call_label(node) or "").lower()
            assert "live ai" not in label, f"line {node.lineno}: a checkbox must not opt in to live AI"
