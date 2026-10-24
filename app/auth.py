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
from datetime import date
from functools import lru_cache
from pathlib import Path

ITERATIONS = 200_000
MIN_PASSWORD = 8
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
DEFAULT_STORE = Path(__file__).resolve().parent / "accounts.generated.json"
LEGACY_TODAY = date(2027, 3, 1)   # demo date; old accounts get a renewal 90 days after it

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
    member_id: str | None      # the user's synthetic record (demo persona, or SYN-1001+ for sign-ups)
    renewal_date: date | None = None   # set for sign-ups; demo personas use their fixture record


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
                    if not rec.get("member_id"):          # account made before profiles existed
                        rec = self._upgrade_legacy(email)
                    renewal = rec.get("renewal_date")
                    return Account(name=str(rec["name"]), email=email, member_id=rec.get("member_id"),
                                   renewal_date=date.fromisoformat(renewal) if renewal else None)
                return None
        hash_password(password)  # spend similar time for unknown emails (no account probing by timing)
        return None

    def _upgrade_legacy(self, email: str) -> dict:
        """Give an old sign-up (no member record) its own member ID and a default renewal date; save it."""
        from datetime import timedelta

        from app.profile import next_member_id

        saved = self._saved()
        taken = [str(r.get("member_id")) for r in self._all() if r.get("member_id")]
        for rec in saved:
            if rec.get("email") == email and not rec.get("member_id"):
                rec["member_id"] = next_member_id(taken)
                rec["renewal_date"] = rec.get("renewal_date") or (LEGACY_TODAY + timedelta(days=90)).isoformat()
                self.path.write_text(json.dumps(saved, indent=2))
                return rec
        raise AuthError("Account not found.")

    def sign_up(self, name: str, email: str, password: str, renewal_date: date) -> Account:
        name, email = " ".join(name.split()), _normal(email)
        if not name or len(name) > 80:
            raise AuthError("Please enter your name (up to 80 characters).")
        if not EMAIL.match(email):
            raise AuthError("Please enter a valid email address.")
        if len(password) < MIN_PASSWORD:
            raise AuthError(f"Use a password with at least {MIN_PASSWORD} characters.")
        if any(rec.get("email") == email for rec in self._all()):
            raise AuthError("An account with this email already exists. Try signing in.")
        from app.profile import next_member_id   # local import: profile depends on app.data only

        saved = self._saved()
        member_id = next_member_id([str(r.get("member_id")) for r in self._all() if r.get("member_id")])
        saved.append({"name": name, "email": email, "member_id": member_id, "renewal_date": renewal_date.isoformat(),
                      "hash": hash_password(password)})
        self.path.write_text(json.dumps(saved, indent=2))
        return Account(name=name, email=email, member_id=member_id, renewal_date=renewal_date)
