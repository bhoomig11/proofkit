"""Sign-up / sign-in: salted PBKDF2 hashes, 5 demo accounts linked to the synthetic personas."""
import json

import pytest

from app.auth import DEMO_LOGINS, AccountStore, AuthError, hash_password, verify_password


def test_hash_round_trip_and_salting():
    a, b = hash_password("correct horse 1"), hash_password("correct horse 1")
    assert a != b                                   # random salt each time
    assert verify_password("correct horse 1", a) and not verify_password("wrong", a)
    assert "correct horse" not in a


def test_five_demo_accounts_sign_in_and_link_to_personas(tmp_path):
    store = AccountStore(tmp_path / "accounts.json")
    assert [d["member_id"] for d in DEMO_LOGINS] == ["SYN-0001", "SYN-0002", "SYN-0003", "SYN-0004", "SYN-0005"]
    for d in DEMO_LOGINS:
        account = store.sign_in(d["email"], d["password"])
        assert account is not None and account.member_id == d["member_id"]


def test_wrong_password_unknown_email_and_case(tmp_path):
    store = AccountStore(tmp_path / "accounts.json")
    first = DEMO_LOGINS[0]
    assert store.sign_in(first["email"], "nope-nope-nope") is None
    assert store.sign_in("nobody@example.com", first["password"]) is None
    assert store.sign_in(first["email"].upper(), first["password"]) is not None


def test_sign_up_then_sign_in_without_storing_plaintext(tmp_path):
    path = tmp_path / "accounts.json"
    store = AccountStore(path)
    created = store.sign_up("Rosa Diaz", "Rosa@Example.com", "a-long-pass-9")
    assert created.email == "rosa@example.com" and created.member_id is None
    assert AccountStore(path).sign_in("rosa@example.com", "a-long-pass-9") == created   # persisted
    assert "a-long-pass-9" not in path.read_text()
    assert "hash" in json.loads(path.read_text())[0]


@pytest.mark.parametrize("name,email,password", [
    ("", "a@example.com", "a-long-pass-9"),            # name required
    ("Ann", "not-an-email", "a-long-pass-9"),          # email format
    ("Ann", "ann@example.com", "short"),               # password too short
])
def test_sign_up_validation(tmp_path, name, email, password):
    with pytest.raises(AuthError):
        AccountStore(tmp_path / "a.json").sign_up(name, email, password)


def test_duplicate_email_rejected_including_demo_accounts(tmp_path):
    store = AccountStore(tmp_path / "a.json")
    store.sign_up("Ann", "ann@example.com", "a-long-pass-9")
    with pytest.raises(AuthError):
        store.sign_up("Ann 2", "ANN@example.com", "a-long-pass-9")
    with pytest.raises(AuthError):
        store.sign_up("Fake Maria", DEMO_LOGINS[0]["email"], "a-long-pass-9")
