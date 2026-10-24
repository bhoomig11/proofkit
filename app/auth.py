"""Demo sign-up / sign-in for the RenewRight UI.

Passwords are stored only as salted PBKDF2-SHA256 hashes (standard library, no new dependency).
New accounts are saved to app/accounts.generated.json, which is gitignored (*.generated.json).

The 5 DEMO_LOGINS are PUBLIC test credentials for the synthetic personas (judges need them to try the app).
They are not secrets and must never be reused for anything real.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ITERATIONS = 200_000
MIN_PASSWORD = 8
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
DEFAULT_STORE = Path(__file__).resolve().parent / "accounts.generated.json"

DEMO_LOGINS: tuple[dict[str, str], ...] = (
    {"name": "Maria", "email": "maria@example.com", "password": "maria-demo-2027", "member_id": "SYN-0001"},
    {"name": "James", "email": "james@example.com", "password": "james-demo-2027", "member_id": "SYN-0002"},
    {"name": "Priya", "email": "priya@example.com", "password": "priya-demo-2027", "member_id": "SYN-0003"},
    {"name": "Dev", "email": "dev@example.com", "password": "dev-demo-2027", "member_id": "SYN-0004"},
    {"name": "Red team", "email": "redteam@example.com", "password": "redteam-demo-2027", "member_id": "SYN-0005"},
)


class AuthError(ValueError):
    """A user-facing sign-up problem (safe to show)."""


@dataclass(frozen=True)
class Account:
    name: str
    email: str
    member_id: str | None      # linked synthetic record; None for a brand-new sign-up


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iterations, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
    return hmac.compare_digest(digest.hex(), digest_hex)


@lru_cache(maxsize=1)
def _demo_records() -> tuple[dict[str, str | None], ...]:
    return tuple({"name": d["name"], "email": d["email"], "member_id": d["member_id"],
                  "hash": hash_password(d["password"])} for d in DEMO_LOGINS)


def _normal(email: str) -> str:
    return email.strip().lower()


class AccountStore:
    """Demo accounts (built in) + sign-ups persisted to a JSON file."""

    def __init__(self, path: Path = DEFAULT_STORE):
        self.path = Path(path)

    def _saved(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return []
        return data if isinstance(data, list) else []

    def _all(self) -> list[dict]:
        return [*_demo_records(), *self._saved()]

    def sign_in(self, email: str, password: str) -> Account | None:
        email = _normal(email)
        for rec in self._all():
            if rec.get("email") == email:
                if verify_password(password, str(rec.get("hash", ""))):
                    return Account(name=str(rec["name"]), email=email, member_id=rec.get("member_id"))
                return None
        hash_password(password)  # spend similar time for unknown emails (no account probing by timing)
        return None

    def sign_up(self, name: str, email: str, password: str) -> Account:
        name, email = " ".join(name.split()), _normal(email)
        if not name or len(name) > 80:
            raise AuthError("Please enter your name (up to 80 characters).")
        if not EMAIL.match(email):
            raise AuthError("Please enter a valid email address.")
        if len(password) < MIN_PASSWORD:
            raise AuthError(f"Use a password with at least {MIN_PASSWORD} characters.")
        if any(rec.get("email") == email for rec in self._all()):
            raise AuthError("An account with this email already exists. Try signing in.")
        saved = self._saved()
        saved.append({"name": name, "email": email, "member_id": None, "hash": hash_password(password)})
        self.path.write_text(json.dumps(saved, indent=2))
        return Account(name=name, email=email, member_id=None)
